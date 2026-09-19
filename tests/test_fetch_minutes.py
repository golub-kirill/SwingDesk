"""`tools/fetch_minutes.py` against a fake vendor. No network.

What it must get right, each one a way to store the wrong minutes without an error:

* **the request.** `adjustment=split` (the bar store's prices are split-adjusted, Alpaca's default
  is not), `feed=sip` (`iex` serves no history), the whole UTC day, and every page.
* **the record.** A failed request writes nothing, so the session still reads as never fetched; a
  served-empty session IS written, as a fetch of zero minutes.
* **the prices.** Through `str`, so `0.1` is `Decimal("0.1")` and not a float's binary tail.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from swingdesk.market_data.minutes import MinuteStore

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def tool():
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_fetch_minutes", REPO / "tools" / "fetch_minutes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def bar(t: str, low: float, high: float) -> dict[str, object]:
    return {"t": t, "o": low, "h": high, "l": low, "c": high, "v": 100}


class Vendor:
    """Serves pages in order and records every URL it was asked for."""

    def __init__(self, *responses: tuple[int, object]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url: str) -> tuple[int, object]:
        self.urls.append(url)
        return self.responses.pop(0)


def query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


# --- the request ---------------------------------------------------------------------------------

def test_the_request_asks_for_split_adjusted_sip_minutes_over_the_whole_utc_day(tool) -> None:
    vendor = Vendor((200, {"bars": [], "next_page_token": None}))
    tool.fetch("ABR", date(2025, 2, 21), vendor)
    asked = query(vendor.urls[0])
    assert urlparse(vendor.urls[0]).path == "/v2/stocks/ABR/bars"
    assert asked["timeframe"] == "1Min"
    assert asked["adjustment"] == "split"
    assert asked["feed"] == "sip"
    assert asked["start"] == "2025-02-21T00:00:00Z"
    assert asked["end"] == "2025-02-21T23:59:59Z"


def test_every_page_is_followed_and_the_minutes_keep_their_order(tool) -> None:
    vendor = Vendor(
        (200, {"bars": [bar("2025-02-21T14:30:00Z", 13.9, 14.0)], "next_page_token": "abc"}),
        (200, {"bars": [bar("2025-02-21T14:31:00Z", 13.8, 13.95)], "next_page_token": None}),
    )
    got = tool.fetch("ABR", date(2025, 2, 21), vendor)
    assert [m.at.minute for m in got] == [30, 31]
    assert "page_token" not in query(vendor.urls[0])
    assert query(vendor.urls[1])["page_token"] == "abc"


def test_a_refused_page_is_a_reason_and_not_a_short_session(tool) -> None:
    vendor = Vendor(
        (200, {"bars": [bar("2025-02-21T14:30:00Z", 13.9, 14.0)], "next_page_token": "abc"}),
        (429, "rate limited"),
    )
    got = tool.fetch("ABR", date(2025, 2, 21), vendor)
    assert got == "HTTP 429: rate limited"


def test_a_share_class_is_asked_for_in_the_venues_spelling(tool) -> None:
    vendor = Vendor((200, {"bars": []}))
    tool.fetch("BRK-B", date(2025, 2, 21), vendor)
    assert urlparse(vendor.urls[0]).path == "/v2/stocks/BRK.B/bars"


def test_prices_go_through_str_and_the_minute_is_utc(tool) -> None:
    minute = tool.parse({"t": "2025-02-21T14:30:00Z", "o": 0.1, "h": 0.3, "l": 0.1, "c": 0.2})
    assert minute.open == Decimal("0.1")
    assert minute.high == Decimal("0.3")
    assert minute.close == Decimal("0.2")
    assert minute.at == datetime(2025, 2, 21, 14, 30, tzinfo=UTC)
    assert minute.volume is None and minute.vwap is None, "not served, so not invented"


def test_volume_and_the_vendor_s_vwap_are_kept_when_served(tool) -> None:
    minute = tool.parse({"t": "2025-02-21T14:30:00Z", "o": 0.1, "h": 0.3, "l": 0.1, "c": 0.2,
                         "v": 12345, "vw": 0.2112})
    assert minute.volume == 12345 and minute.vwap == Decimal("0.2112")


# --- the record ----------------------------------------------------------------------------------

def sessions_file(tmp_path: Path, *pairs: tuple[str, str]) -> Path:
    path = tmp_path / "sessions.jsonl"
    path.write_text("".join(json.dumps({"instrument_id": i, "session_date": d}) + "\n"
                            for i, d in pairs), encoding="utf-8")
    return path


def test_the_sessions_are_distinct_and_in_a_fixed_order(tool, tmp_path: Path) -> None:
    path = sessions_file(tmp_path, ("ZZ", "2025-01-02"), ("AA", "2025-01-03"), ("ZZ", "2025-01-02"))
    assert tool.sessions_from(path) == [("AA", date(2025, 1, 3)), ("ZZ", date(2025, 1, 2))]


def test_a_run_stores_what_was_served_and_skips_it_the_next_time(tool, tmp_path: Path) -> None:
    sessions = sessions_file(tmp_path, ("ABR", "2025-02-21"))
    store = tmp_path / "minutes.duckdb"
    served = Vendor((200, {"bars": [bar("2025-02-21T14:30:00Z", 13.9, 14.0)]}))
    assert tool.main(["--store", str(store), "--sessions", str(sessions)], served, lambda: NOW) == 0

    silent = Vendor()
    assert tool.main(["--store", str(store), "--sessions", str(sessions)], silent, lambda: NOW) == 0
    assert silent.urls == []
    with MinuteStore(store) as read:
        got = read.session("ABR", date(2025, 2, 21), NOW)
    assert got is not None
    assert [m.low for m in got] == [Decimal("13.9")]


def test_a_failed_session_writes_nothing_and_the_run_says_so(tool, tmp_path: Path) -> None:
    sessions = sessions_file(tmp_path, ("ABR", "2025-02-21"))
    store = tmp_path / "minutes.duckdb"
    code = tool.main(["--store", str(store), "--sessions", str(sessions)],
                     Vendor((500, "down")), lambda: NOW)
    assert code == 1
    with MinuteStore(store) as read:
        assert read.session("ABR", date(2025, 2, 21), NOW) is None


def test_a_session_served_empty_is_recorded_as_a_fetch_of_nothing(tool, tmp_path: Path) -> None:
    sessions = sessions_file(tmp_path, ("ABR", "2025-02-21"))
    store = tmp_path / "minutes.duckdb"
    code = tool.main(["--store", str(store), "--sessions", str(sessions)],
                     Vendor((200, {"bars": []})), lambda: NOW)
    assert code == 0
    with MinuteStore(store) as read:
        assert read.session("ABR", date(2025, 2, 21), NOW) == ()


def test_refetch_asks_again_and_the_newer_version_wins(tool, tmp_path: Path) -> None:
    sessions = sessions_file(tmp_path, ("ABR", "2025-02-21"))
    store = tmp_path / "minutes.duckdb"
    first = Vendor((200, {"bars": [bar("2025-02-21T14:30:00Z", 13.9, 14.0)]}))
    tool.main(["--store", str(store), "--sessions", str(sessions)], first, lambda: NOW)
    later = datetime(2026, 9, 15, tzinfo=UTC)
    second = Vendor((200, {"bars": [bar("2025-02-21T14:30:00Z", 13.7, 14.0)]}))
    tool.main(["--store", str(store), "--sessions", str(sessions), "--refetch"], second,
              lambda: later)
    with MinuteStore(store) as read:
        assert [m.low for m in read.session("ABR", date(2025, 2, 21), later)] == [Decimal("13.7")]
        assert [m.low for m in read.session("ABR", date(2025, 2, 21), NOW)] == [Decimal("13.9")]


# --- the date range, DR-045 ----------------------------------------------------------------------


def test_a_range_names_the_exchange_s_sessions_and_no_other_day(tool) -> None:
    """The calendar decides. 2026-09-05 is a Saturday and 2026-09-07 is Labor Day: a request for
    either would store an empty fetch as though the market had printed nothing."""
    pairs = tool.range_sessions(["SPY"], date(2026, 9, 3), date(2026, 9, 9))

    assert [session for _, session in pairs] == [
        date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 8), date(2026, 9, 9)]
    assert {instrument for instrument, _ in pairs} == {"SPY"}


def test_a_range_covers_every_named_instrument_once_and_in_order(tool) -> None:
    pairs = tool.range_sessions(["QQQ", "SPY", "SPY"], date(2026, 9, 3), date(2026, 9, 4))

    assert pairs == sorted(set(pairs)), "sorted and distinct, so a re-run asks the same questions"
    assert len(pairs) == 4, "two instruments, two sessions, no duplicate for the repeated name"


def test_a_range_without_both_ends_is_refused(tool, tmp_path, capsys) -> None:
    code = tool.main(["--store", str(tmp_path / "m.duckdb"), "--instrument", "SPY",
                      "--from", "2026-09-03"], getter=_no_vendor, now=lambda: NOW)

    assert code == 2
    assert "--from and --to" in capsys.readouterr().out


def test_a_backwards_range_is_refused_rather_than_fetched_empty(tool, tmp_path, capsys) -> None:
    code = tool.main(["--store", str(tmp_path / "m.duckdb"), "--instrument", "SPY",
                      "--from", "2026-09-09", "--to", "2026-09-03"], getter=_no_vendor,
                     now=lambda: NOW)

    assert code == 2
    assert "is after" in capsys.readouterr().out


def _no_vendor(url: str):
    raise AssertionError(f"the vendor was called for {url}")
