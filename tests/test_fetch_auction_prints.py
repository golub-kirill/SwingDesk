"""`tools/fetch_auction_prints.py` against a fake vendor. No network.

What it must get right, each a way to price an auction entry at the wrong print without an error:

* **the instant.** The open, or the close - 13:00 on a half day - converted to UTC across daylight
  saving, from the calendar;
* **how far it reads.** Past the first cross by a minute, so a larger listing-market cross that
  prints after another venue's flagged trade is still read; and no further, so a busy name does not
  page through five minutes of tape;
* **the record.** A failed request writes nothing; a window with no flagged print IS written.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from swingdesk.market_data.auctions import CLOSING, OPENING, AuctionStore

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 19, 22, 0, tzinfo=UTC)
SUMMER = date(2026, 9, 15)
WINTER = date(2026, 1, 14)
HALF_DAY = date(2026, 11, 27)
HOLIDAY = date(2026, 7, 3)
OPENED = datetime(2026, 9, 15, 13, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def tool():
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "_fetch_auction_prints", REPO / "tools" / "fetch_auction_prints.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def trade(seconds: float, price: float, size: int, conditions=("@",), exchange="Q"):
    at = OPENED + timedelta(seconds=seconds)
    return {"t": at.isoformat().replace("+00:00", "Z"), "p": price, "s": size, "x": exchange,
            "c": list(conditions)}


def page(rows, token=None):
    return 200, {"trades": rows, "next_page_token": token, "symbol": "X"}


class Vendor:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url: str):
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


@pytest.mark.parametrize(("day", "side", "expected"), [
    (SUMMER, OPENING, datetime(2026, 9, 15, 13, 30, tzinfo=UTC)),
    (SUMMER, CLOSING, datetime(2026, 9, 15, 20, 0, tzinfo=UTC)),
    (WINTER, OPENING, datetime(2026, 1, 14, 14, 30, tzinfo=UTC)),
    (WINTER, CLOSING, datetime(2026, 1, 14, 21, 0, tzinfo=UTC)),
    (HALF_DAY, CLOSING, datetime(2026, 11, 27, 18, 0, tzinfo=UTC)),
])
def test_each_auction_starts_at_its_session_s_own_bell(tool, day, side, expected) -> None:
    assert tool.instant_for("SPY", day, side) == expected


def test_a_shut_exchange_has_no_auction(tool) -> None:
    assert tool.instant_for("SPY", HOLIDAY, OPENING) is None


def test_an_unknown_side_is_refused(tool) -> None:
    with pytest.raises(ValueError, match="not one of"):
        tool.instant_for("SPY", SUMMER, "noon")


# --- what is kept ---------------------------------------------------------------------------------


def test_only_flagged_prints_are_kept_with_every_condition(tool) -> None:
    assert tool.parse(trade(0.1, 10.0, 5)) is None
    kept = tool.parse(trade(0.9, 103.77, 21096, ("@", "O", "X")))
    assert kept.price == Decimal("103.77") and kept.size == 21096
    assert kept.conditions == ("@", "O", "X") and kept.exchange == "Q"
    assert kept.at == OPENED + timedelta(seconds=0.9)


def test_the_request_asks_sip_trades_from_the_bell_in_pages_of_a_thousand(tool) -> None:
    vendor = Vendor(page([trade(0.9, 10, 100, ("@", "O"))]))
    tool.fetch("BRK-B", OPENED, OPENING, vendor, lambda _: None)
    [url] = vendor.urls
    assert "/v2/stocks/BRK.B/trades" in url
    assert query(url) == {"start": "2026-09-15T13:30:00Z", "end": "2026-09-15T13:35:00Z",
                          "limit": "1000", "feed": "sip"}


# --- how far it reads -----------------------------------------------------------------------------


def test_it_reads_a_minute_past_the_first_cross_and_no_further(tool) -> None:
    """Another venue flags `O` first; the listing market's larger cross is on the next page."""
    vendor = Vendor(page([trade(0.1, 10.0, 50, ("@", "O"), "P"), trade(30, 10.1, 5)], "p2"),
                    page([trade(45, 10.2, 9000, ("@", "O", "X"), "N"), trade(61, 10.2, 5)], "p3"),
                    page([trade(90, 10.3, 5)]))
    got = tool.fetch("X", OPENED, OPENING, vendor, lambda _: None)
    prints, scanned = got
    assert [p.size for p in prints] == [50, 9000]
    assert scanned == 4 and len(vendor.urls) == 2, "the page reaching past a minute ends it"


def test_without_a_cross_it_pages_to_the_end_of_the_window(tool) -> None:
    vendor = Vendor(page([trade(1, 10, 5)], "p2"), page([trade(200, 10, 5)]))
    prints, scanned = tool.fetch("X", OPENED, OPENING, vendor, lambda _: None)
    assert prints == [] and scanned == 2 and len(vendor.urls) == 2


def test_the_closing_side_looks_for_the_closing_condition(tool) -> None:
    vendor = Vendor(page([trade(0.2, 10, 100, ("@", "O")), trade(0.3, 10, 9000, ("@", "6"))],
                         "p2"),
                    page([trade(70, 10, 5)]))
    prints, _ = tool.fetch("X", OPENED, CLOSING, vendor, lambda _: None)
    assert len(prints) == 2 and len(vendor.urls) == 2


def test_an_opening_print_does_not_end_a_closing_window(tool) -> None:
    """At the close, a venue's `O` is not the cross: the reader keeps going to the `6`."""
    vendor = Vendor(page([trade(0.2, 10, 100, ("@", "O")), trade(61, 10, 5)], "p2"),
                    page([trade(100, 10.1, 9000, ("@", "6"))]))
    prints, _ = tool.fetch("X", OPENED, CLOSING, vendor, lambda _: None)
    assert len(vendor.urls) == 2 and prints[-1].size == 9000


def test_a_rate_limit_is_retried_and_any_other_refusal_is_final(tool) -> None:
    pauses: list[float] = []
    vendor = Vendor((429, "slow"), page([trade(0.5, 10, 100, ("@", "O"))]))
    got = tool.fetch("X", OPENED, OPENING, vendor, pauses.append)
    assert not isinstance(got, str)
    assert tool.BACKOFF_SECONDS in pauses
    refused = tool.fetch("X", OPENED, OPENING, Vendor((403, "no")), lambda _: None)
    assert isinstance(refused, str) and refused.startswith("HTTP 403")


# --- the record -----------------------------------------------------------------------------------


def test_a_failed_window_writes_nothing_and_an_unflagged_one_is_written(tool, tmp_path) -> None:
    """THE PROPERTY. The open failed and stays unfetched; the close had no flagged print."""
    vendor = Vendor((500, "boom"), page([trade(1, 10, 5)]))
    store_path = tmp_path / "a.duckdb"
    code = tool.main(["--store", str(store_path), "--sessions",
                      str(_sessions_file(tmp_path, ("SPY", "2026-09-15")))],
                     getter=vendor, now=lambda: NOW, pause=lambda _: None)
    assert code == 1
    with AuctionStore(store_path) as store:
        assert store.window("SPY", SUMMER, OPENING, NOW) is None
        assert store.window("SPY", SUMMER, CLOSING, NOW) == ()


def test_held_windows_are_skipped_unless_refetched(tool, tmp_path) -> None:
    sessions = _sessions_file(tmp_path, ("SPY", "2026-09-15"))
    args = ["--store", str(tmp_path / "a.duckdb"), "--sessions", str(sessions), "--side", "opening"]
    assert tool.main(args, getter=Vendor(page([])), now=lambda: NOW, pause=lambda _: None) == 0
    idle = Vendor()
    assert tool.main(args, getter=idle, now=lambda: NOW, pause=lambda _: None) == 0
    assert idle.urls == []
    again = Vendor(page([]))
    assert tool.main([*args, "--refetch"], getter=again, now=lambda: NOW,
                     pause=lambda _: None) == 0
    assert len(again.urls) == 1


def test_every_request_is_paced(tool, tmp_path) -> None:
    pauses: list[float] = []
    tool.main(["--store", str(tmp_path / "a.duckdb"),
               "--sessions", str(_sessions_file(tmp_path, ("SPY", "2026-09-15")))],
              getter=Vendor(page([]), page([])), now=lambda: NOW, pause=pauses.append)
    assert pauses == [tool.PACE_SECONDS] * 2


def test_without_credentials_the_real_getter_is_never_used(tool, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    code = tool.main(["--store", str(tmp_path / "a.duckdb"),
                      "--sessions", str(_sessions_file(tmp_path, ("SPY", "2026-09-15")))])
    assert code == 2 and "UNAVAILABLE" in capsys.readouterr().out
