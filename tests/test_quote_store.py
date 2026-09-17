"""`QuoteStore`: quote windows as known at an instant (`PR-024`).

The three answers a store must keep apart - never fetched, fetched and empty, and quotes - and the
one property that makes a window different from a minute: a window is one fetch, so a later fetch
REPLACES the earlier one rather than merging with it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.market_data.quotes import CLOSE, OPEN, Quote, QuoteStore, UnknownMoment

SESSION = date(2026, 9, 15)
ASKED = datetime(2026, 9, 15, 13, 30, 5, tzinfo=UTC)
FIRST = datetime(2026, 9, 16, 1, 0, tzinfo=UTC)
LATER = FIRST + timedelta(days=1)


def _quote(seconds: int, bid: str, ask: str) -> Quote:
    return Quote(at=ASKED + timedelta(seconds=seconds), bid=Decimal(bid), ask=Decimal(ask))


@pytest.fixture
def store(tmp_path: Path):
    with QuoteStore(tmp_path / "quotes.duckdb") as opened:
        yield opened


def test_a_window_nobody_fetched_is_none(store) -> None:
    assert store.window("SPY", SESSION, OPEN, FIRST) is None
    assert not store.fetched("SPY", SESSION, OPEN, FIRST)


def test_a_window_fetched_empty_is_an_answer(store) -> None:
    """The vendor served nothing: that is a fact about the moment, not a gap in the data."""
    store.write("SPY", SESSION, OPEN, ASKED, [], FIRST, "alpaca:sip")

    requested, quotes = store.window("SPY", SESSION, OPEN, FIRST)
    assert quotes == () and requested == ASKED
    assert store.fetched("SPY", SESSION, OPEN, FIRST)


def test_quotes_come_back_in_the_vendor_s_order_even_at_one_instant(store) -> None:
    """Two quotes can share a timestamp; the ordinal keeps both and keeps their order."""
    served = [_quote(0, "100.00", "100.02"), _quote(0, "100.01", "100.02"),
              _quote(1, "100.00", "100.03")]
    assert store.write("SPY", SESSION, OPEN, ASKED, served, FIRST, "alpaca:sip") == 3

    _, quotes = store.window("SPY", SESSION, OPEN, FIRST)
    assert quotes == tuple(served)


def test_a_fetch_is_invisible_before_it_was_learned(store) -> None:
    store.write("SPY", SESSION, OPEN, ASKED, [_quote(0, "1", "2")], LATER, "alpaca:sip")

    assert store.window("SPY", SESSION, OPEN, FIRST) is None
    assert store.window("SPY", SESSION, OPEN, LATER) is not None


def test_a_later_fetch_replaces_the_window_rather_than_merging_with_it(store) -> None:
    """THE PROPERTY. A window of three quotes fetched again as one quote is a one-quote window."""
    store.write("SPY", SESSION, OPEN, ASKED,
                [_quote(0, "1.00", "1.10"), _quote(1, "1.00", "1.20"), _quote(2, "1.00", "1.30")],
                FIRST, "alpaca:sip")
    store.write("SPY", SESSION, OPEN, ASKED, [_quote(0, "1.00", "1.05")], LATER, "alpaca:sip")

    _, now = store.window("SPY", SESSION, OPEN, LATER)
    assert now == (_quote(0, "1.00", "1.05"),)
    _, then = store.window("SPY", SESSION, OPEN, FIRST)
    assert len(then) == 3, "and the earlier answer is still readable as of its own instant"


def test_moments_and_names_do_not_leak_into_each_other(store) -> None:
    store.write("SPY", SESSION, OPEN, ASKED, [_quote(0, "1", "2")], FIRST, "alpaca:sip")

    assert store.window("SPY", SESSION, CLOSE, FIRST) is None
    assert store.window("QQQ", SESSION, OPEN, FIRST) is None
    assert store.window("SPY", SESSION + timedelta(days=1), OPEN, FIRST) is None


def test_an_unknown_moment_is_refused_on_every_path(store) -> None:
    with pytest.raises(UnknownMoment):
        store.write("SPY", SESSION, "noon", ASKED, [], FIRST, "alpaca:sip")
    with pytest.raises(UnknownMoment):
        store.window("SPY", SESSION, "noon", FIRST)
    with pytest.raises(UnknownMoment):
        store.fetched("SPY", SESSION, "noon", FIRST)


def test_prices_survive_as_decimals(store) -> None:
    store.write("SPY", SESSION, OPEN, ASKED, [_quote(0, "0.1", "0.3")], FIRST, "alpaca:sip")
    _, [quote] = store.window("SPY", SESSION, OPEN, FIRST)
    assert quote.bid == Decimal("0.1") and quote.ask == Decimal("0.3")
