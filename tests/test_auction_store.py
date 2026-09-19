"""`AuctionStore`: auction prints as known at an instant (`PR-025`).

The three answers a store must keep apart - never fetched, fetched with nothing flagged, and prints
- and that a window is one fetch, so a later fetch replaces the earlier one rather than merging.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.market_data.auctions import CLOSING, OPENING, AuctionStore, Print, UnknownSide

SESSION = date(2026, 9, 15)
ASKED = datetime(2026, 9, 15, 13, 30, tzinfo=UTC)
FIRST = datetime(2026, 9, 16, 1, 0, tzinfo=UTC)
LATER = FIRST + timedelta(days=1)


def _print(ms: int, price: str, size: int, exchange: str = "Q",
           conditions: tuple[str, ...] = ("@", "O", "X")) -> Print:
    return Print(at=ASKED + timedelta(milliseconds=ms), price=Decimal(price), size=size,
                 exchange=exchange, conditions=conditions)


@pytest.fixture
def store(tmp_path: Path):
    with AuctionStore(tmp_path / "auctions.duckdb") as opened:
        yield opened


def test_a_window_nobody_fetched_is_none(store) -> None:
    assert store.window("SPY", SESSION, OPENING, FIRST) is None
    assert not store.fetched("SPY", SESSION, OPENING, FIRST)


def test_a_window_with_nothing_flagged_is_an_answer(store) -> None:
    """The tape flagged no cross: a fact about the session, not a gap in the data."""
    store.write("SPY", SESSION, OPENING, ASKED, [], 240, FIRST, "alpaca:sip")
    assert store.window("SPY", SESSION, OPENING, FIRST) == ()
    assert store.fetched("SPY", SESSION, OPENING, FIRST)


def test_prints_come_back_as_served_with_every_condition(store) -> None:
    served = [_print(946, "103.77", 21096), _print(947, "103.77", 21096, conditions=("@", "Q")),
              _print(2340, "103.705", 65, "P", ("@", "Q"))]
    assert store.write("STX", SESSION, OPENING, ASKED, served, 81, FIRST, "alpaca:sip") == 3
    assert store.window("STX", SESSION, OPENING, FIRST) == tuple(served)


def test_a_fetch_is_invisible_before_it_was_learned(store) -> None:
    store.write("SPY", SESSION, CLOSING, ASKED, [_print(0, "1", 1)], 1, LATER, "alpaca:sip")
    assert store.window("SPY", SESSION, CLOSING, FIRST) is None
    assert store.window("SPY", SESSION, CLOSING, LATER) is not None


def test_a_later_fetch_replaces_the_window_rather_than_merging_with_it(store) -> None:
    store.write("SPY", SESSION, OPENING, ASKED, [_print(0, "1", 1), _print(1, "2", 2)], 9, FIRST,
                "alpaca:sip")
    store.write("SPY", SESSION, OPENING, ASKED, [_print(0, "3", 3)], 9, LATER, "alpaca:sip")
    assert store.window("SPY", SESSION, OPENING, LATER) == (_print(0, "3", 3),)
    assert len(store.window("SPY", SESSION, OPENING, FIRST)) == 2


def test_sides_and_names_do_not_leak_into_each_other(store) -> None:
    store.write("SPY", SESSION, OPENING, ASKED, [_print(0, "1", 1)], 1, FIRST, "alpaca:sip")
    assert store.window("SPY", SESSION, CLOSING, FIRST) is None
    assert store.window("QQQ", SESSION, OPENING, FIRST) is None


def test_an_unknown_side_is_refused(store) -> None:
    with pytest.raises(UnknownSide):
        store.write("SPY", SESSION, "noon", ASKED, [], 0, FIRST, "alpaca:sip")
    with pytest.raises(UnknownSide):
        store.window("SPY", SESSION, "noon", FIRST)
