"""`tools/fetch_entry_quotes.py` against a fake vendor. No network.

What it must get right, each one a way to charge a study the wrong spread without an error:

* **the instant.** Five seconds after the open, 11:00, and five minutes before the CLOSE - which on
  a half day is 12:55, not 15:55 - converted to UTC across daylight saving.
* **the record.** A failed request writes nothing, so the window still reads as never fetched; a
  served-empty window IS written. `measure_quoted_spread.fetch_quotes` could not tell them apart.
* **the request.** `feed=sip`, 25 quotes, the vendor's spelling of a share class.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from swingdesk.market_data.quotes import CLOSE, ELEVEN, OPEN, QuoteStore

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 16, 22, 0, tzinfo=UTC)
SUMMER = date(2026, 9, 15)       # EDT, UTC-4
WINTER = date(2026, 1, 14)       # EST, UTC-5
HALF_DAY = date(2026, 11, 27)    # closes 13:00
HOLIDAY = date(2026, 7, 3)


@pytest.fixture(scope="module")
def tool():
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "_fetch_entry_quotes", REPO / "tools" / "fetch_entry_quotes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def served(*rows: tuple[str, float, float]) -> dict[str, object]:
    return {"quotes": [{"t": t, "bp": bid, "ap": ask, "bs": 1, "as": 1} for t, bid, ask in rows],
            "symbol": "X"}


class Vendor:
    """Answers in order and records every URL."""

    def __init__(self, *responses: tuple[int, object]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url: str) -> tuple[int, object]:
        self.urls.append(url)
        return self.responses.pop(0)


def query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


def _sessions_file(tmp_path: Path, *pairs: tuple[str, str]) -> Path:
    path = tmp_path / "sessions.jsonl"
    path.write_text("".join(f'{{"instrument_id": "{i}", "session_date": "{d}"}}\n'
                            for i, d in pairs), encoding="utf-8")
    return path


# --- the instant ----------------------------------------------------------------------------------


@pytest.mark.parametrize(("day", "moment", "expected"), [
    (SUMMER, OPEN, datetime(2026, 9, 15, 13, 30, 5, tzinfo=UTC)),
    (SUMMER, ELEVEN, datetime(2026, 9, 15, 15, 0, tzinfo=UTC)),
    (SUMMER, CLOSE, datetime(2026, 9, 15, 19, 55, tzinfo=UTC)),
    (WINTER, OPEN, datetime(2026, 1, 14, 14, 30, 5, tzinfo=UTC)),
    (WINTER, CLOSE, datetime(2026, 1, 14, 20, 55, tzinfo=UTC)),
    (HALF_DAY, CLOSE, datetime(2026, 11, 27, 17, 55, tzinfo=UTC)),
])
def test_each_moment_resolves_from_the_session_not_the_wall_clock(tool, day, moment, expected):
    assert tool.instant_for("SPY", day, moment) == expected


def test_a_day_the_exchange_was_shut_has_no_instant(tool) -> None:
    assert tool.instant_for("SPY", HOLIDAY, OPEN) is None


def test_an_unknown_moment_is_refused(tool) -> None:
    with pytest.raises(ValueError, match="not one of"):
        tool.instant_for("SPY", SUMMER, "noon")


# --- the request ----------------------------------------------------------------------------------


def test_the_request_asks_sip_for_twenty_five_quotes_from_the_instant(tool) -> None:
    vendor = Vendor((200, served(("2026-09-15T13:30:05.1Z", 100.0, 100.02))))

    tool.fetch("BRK-B", datetime(2026, 9, 15, 13, 30, 5, tzinfo=UTC), vendor)

    [url] = vendor.urls
    assert "/v2/stocks/BRK.B/quotes" in url, "the vendor spells a share class with a dot"
    assert query(url) == {"start": "2026-09-15T13:30:05Z", "limit": "25", "feed": "sip"}


def test_quotes_are_kept_as_served_including_a_one_sided_one(tool) -> None:
    """Which quotes a spread may use is the study's rule, not the store's."""
    vendor = Vendor((200, served(("2026-09-15T13:30:05.1Z", 100.1, 100.3),
                                 ("2026-09-15T13:30:05.2Z", 0, 100.3))))

    got = tool.fetch("SPY", datetime(2026, 9, 15, 13, 30, 5, tzinfo=UTC), vendor)

    assert [(q.bid, q.ask) for q in got] == [(Decimal("100.1"), Decimal("100.3")),
                                             (Decimal("0"), Decimal("100.3"))]
    assert got[0].at == datetime(2026, 9, 15, 13, 30, 5, 100000, tzinfo=UTC)


def test_a_refusal_is_a_reason_not_an_empty_window(tool) -> None:
    got = tool.fetch("SPY", NOW, Vendor((500, "upstream went away")))
    assert isinstance(got, str) and got.startswith("HTTP 500")


def test_a_rate_limit_is_retried_with_a_growing_pause(tool) -> None:
    pauses: list[float] = []
    vendor = Vendor((429, "slow down"), (429, "slow down"), (200, served()))

    got = tool.fetch_with_retry("SPY", NOW, vendor, pauses.append)

    assert got == []
    assert pauses == [2.0, 4.0]


def test_a_rate_limit_that_never_lifts_is_a_failure(tool) -> None:
    vendor = Vendor(*[(429, "slow down")] * tool.RETRIES)
    got = tool.fetch_with_retry("SPY", NOW, vendor, lambda _: None)
    assert isinstance(got, str) and got.startswith("HTTP 429")


def test_any_other_refusal_is_not_retried(tool) -> None:
    vendor = Vendor((403, "no entitlement"))
    got = tool.fetch_with_retry("SPY", NOW, vendor, lambda _: None)
    assert isinstance(got, str) and len(vendor.urls) == 1


# --- the record -----------------------------------------------------------------------------------


def test_a_failed_window_writes_nothing_and_a_served_empty_one_is_written(tool, tmp_path) -> None:
    """THE PROPERTY. The open failed and stays unfetched; the close was served empty and is an
    answer; eleven was served quotes."""
    vendor = Vendor((500, "boom"), (200, served(("2026-09-15T15:00:00.5Z", 10.0, 10.02))),
                    (200, served()))
    store_path = tmp_path / "q.duckdb"

    code = tool.main(["--store", str(store_path), "--sessions",
                      str(_sessions_file(tmp_path, ("SPY", "2026-09-15")))],
                     getter=vendor, now=lambda: NOW, pause=lambda _: None)

    assert code == 1, "one window failed"
    with QuoteStore(store_path) as store:
        assert store.window("SPY", SUMMER, OPEN, NOW) is None
        requested, quotes = store.window("SPY", SUMMER, ELEVEN, NOW)
        assert len(quotes) == 1 and requested == datetime(2026, 9, 15, 15, 0, tzinfo=UTC)
        assert store.window("SPY", SUMMER, CLOSE, NOW)[1] == ()


def test_held_windows_are_skipped_unless_refetched(tool, tmp_path) -> None:
    sessions = _sessions_file(tmp_path, ("SPY", "2026-09-15"))
    store_path = tmp_path / "q.duckdb"
    args = ["--store", str(store_path), "--sessions", str(sessions), "--moment", "open"]

    assert tool.main(args, getter=Vendor((200, served())), now=lambda: NOW,
                     pause=lambda _: None) == 0
    untouched = Vendor()
    assert tool.main(args, getter=untouched, now=lambda: NOW, pause=lambda _: None) == 0
    assert untouched.urls == [], "already held"

    again = Vendor((200, served()))
    assert tool.main([*args, "--refetch"], getter=again, now=lambda: NOW,
                     pause=lambda _: None) == 0
    assert len(again.urls) == 1


def test_only_the_named_moments_are_fetched(tool, tmp_path) -> None:
    vendor = Vendor((200, served()), (200, served()))
    tool.main(["--store", str(tmp_path / "q.duckdb"), "--moment", "open", "--moment", "close",
               "--sessions", str(_sessions_file(tmp_path, ("SPY", "2026-09-15")))],
              getter=vendor, now=lambda: NOW, pause=lambda _: None)

    starts = [query(url)["start"] for url in vendor.urls]
    assert starts == ["2026-09-15T13:30:05Z", "2026-09-15T19:55:00Z"]


def test_every_request_is_paced(tool, tmp_path) -> None:
    pauses: list[float] = []
    tool.main(["--store", str(tmp_path / "q.duckdb"),
               "--sessions", str(_sessions_file(tmp_path, ("SPY", "2026-09-15")))],
              getter=Vendor(*[(200, served())] * 3), now=lambda: NOW, pause=pauses.append)
    assert pauses == [tool.PACE_SECONDS] * 3


def test_a_session_that_never_happened_is_a_failure_not_a_fetch(tool, tmp_path) -> None:
    vendor = Vendor()
    code = tool.main(["--store", str(tmp_path / "q.duckdb"), "--moment", "open",
                      "--sessions", str(_sessions_file(tmp_path, ("SPY", "2026-07-03")))],
                     getter=vendor, now=lambda: NOW, pause=lambda _: None)
    assert code == 1 and vendor.urls == []


def test_without_credentials_the_real_getter_is_never_used(tool, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    code = tool.main(["--store", str(tmp_path / "q.duckdb"),
                      "--sessions", str(_sessions_file(tmp_path, ("SPY", "2026-09-15")))])
    assert code == 2 and "UNAVAILABLE" in capsys.readouterr().out


def test_a_missing_sessions_file_is_unavailable(tool, tmp_path) -> None:
    code = tool.main(["--store", str(tmp_path / "q.duckdb"),
                      "--sessions", str(tmp_path / "absent.jsonl")],
                     getter=Vendor(), now=lambda: NOW, pause=lambda _: None)
    assert code == 2
