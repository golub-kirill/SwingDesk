"""Universe construction: directory parsing and the liquidity rule.

Directory text is a fixture, never a fetch - CI must not touch the network (CI_POLICY 4). The
fixture is a trimmed copy of the real files' shape, including the trailing file-creation line and a
test issue, because both are what a naive parser gets wrong.
"""

from __future__ import annotations

from datetime import UTC, date, timedelta
from decimal import Decimal

import pytest

from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import universe

NASDAQ_LISTED = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAAP|Pacer Barings CLO Market Flex ETF|G|N|N|100|Y|N
ZZZZ|Deliberate Test Issue|G|Y|N|100|N|N
TEST1|Synthetic Common Stock|Q|N|N|100|N|N
File Creation Time: 0802202617:30|||||||
"""

OTHER_LISTED = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
TEST2|Synthetic NYSE Common Stock|N|TEST2|N|100|N|TEST2
TEST3|Synthetic Arca Fund|P|TEST3|Y|100|N|TEST3
TEST4|Synthetic Test Issue|N|TEST4|N|100|Y|TEST4
TEST5|Synthetic Unknown Venue|X|TEST5|N|100|N|TEST5
File Creation Time: 0802202617:30|||||||
"""


def test_parsing_drops_the_file_creation_line() -> None:
    """It is a data row by shape and not by meaning. A parser that keeps it produces an instrument
    named "File Creation Time" that fetches empty forever."""
    entries = universe.parse_nasdaq_listed(NASDAQ_LISTED)
    assert [e.symbol for e in entries] == ["AAAP", "ZZZZ", "TEST1"]


def test_test_issues_are_not_eligible() -> None:
    entries = {e.symbol: e for e in universe.parse_nasdaq_listed(NASDAQ_LISTED)}
    assert entries["ZZZZ"].is_test_issue
    assert not entries["ZZZZ"].is_eligible
    assert entries["TEST1"].is_eligible


def test_etfs_are_eligible() -> None:
    """Scope is equities AND ETFs (CHARTER). The flag is metadata, not a filter."""
    entries = {e.symbol: e for e in universe.parse_nasdaq_listed(NASDAQ_LISTED)}
    assert entries["AAAP"].is_etf
    assert entries["AAAP"].is_eligible


def test_other_listed_uses_the_act_symbol_and_maps_venues() -> None:
    entries = {e.symbol: e for e in universe.parse_other_listed(OTHER_LISTED)}
    assert entries["TEST2"].venue == "N"
    assert entries["TEST3"].venue == "P" and entries["TEST3"].is_etf
    assert not entries["TEST4"].is_eligible, "test issue"
    assert not entries["TEST5"].is_eligible, "unknown venue has no known calendar"


def test_instrument_records_the_venue_separately_from_the_calendar() -> None:
    """NASDAQ and NYSE share a session calendar - measured, not assumed - and are still different
    venues. Flattening one into the other would make the record assert something unmeasured."""
    entries = {e.symbol: e for e in universe.parse_nasdaq_listed(NASDAQ_LISTED)}
    instrument = universe.to_instrument(entries["TEST1"])
    assert instrument.exchange is Exchange.NYSE
    assert instrument.listing_venue == "NASDAQ"

    arca = {e.symbol: e for e in universe.parse_other_listed(OTHER_LISTED)}["TEST3"]
    assert universe.to_instrument(arca).listing_venue == "NYSE Arca"


# ------------------------------------------------------------------ liquidity

def _series(closes: list[str], volumes: list[int]):
    from datetime import datetime

    from tests.conftest import TEST_US

    from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

    known = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
    bars = []
    for offset, (close, volume) in enumerate(zip(closes, volumes, strict=False)):
        session = date(2025, 1, 6) + timedelta(days=offset)
        c = Decimal(close)
        bars.append(
            Bar(
                instrument_id=TEST_US.id, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session, open=c, high=c, low=c, close=c,
                volume=volume, knowledge_time=known,
            )
        )
    return BarSeries(
        instrument_id=TEST_US.id, interval=Interval.DAY, series=Series.RAW,
        knowledge_time=known, bars=tuple(bars),
    )


def test_adtv_declines_on_a_partial_window() -> None:
    """A 3-bar average called a 20-day average admits instruments that have barely traded."""
    series = _series(["10.00"] * 3, [1000] * 3)
    assert universe.average_dollar_volume(series, 20) is None
    assert universe.average_dollar_volume(series, 3) == Decimal("10000")


def test_adtv_is_as_of_the_index_not_the_end_of_the_series() -> None:
    """Point-in-time: the universe on a past date is computed from bars up to that date only."""
    series = _series(["10.00"] * 5 + ["100.00"] * 5, [1000] * 5 + [100000] * 5)
    early = universe.average_dollar_volume(series, 5, as_of_index=4)
    late = universe.average_dollar_volume(series, 5, as_of_index=9)
    assert early == Decimal("10000")
    assert late == Decimal("10000000")


def test_rule_requires_price_history_and_liquidity_together() -> None:
    rule = universe.LiquidityRule(
        min_price=Decimal("5"), min_adtv=Decimal("1000000"), adtv_window=5, min_history=8
    )
    liquid = _series(["50.00"] * 10, [100_000] * 10)
    penny = _series(["1.00"] * 10, [100_000_000] * 10)
    short = _series(["50.00"] * 6, [100_000] * 6)
    thin = _series(["50.00"] * 10, [10] * 10)

    assert rule.admits(liquid)
    assert not rule.admits(penny), "price floor"
    assert not rule.admits(short), "history floor"
    assert not rule.admits(thin), "liquidity floor"


def test_membership_is_sorted() -> None:
    """Unordered iteration feeding output is the named determinism hazard, and universe membership
    feeds everything downstream (DETERMINISM_SPEC 3.2)."""
    rule = universe.LiquidityRule(
        min_price=Decimal("1"), min_adtv=Decimal("1"), adtv_window=2, min_history=2
    )
    series = _series(["50.00"] * 5, [1000] * 5)
    unordered = {"ZZ": series, "AA": series, "MM": series}
    assert universe.members(rule, unordered) == ("AA", "MM", "ZZ")


def test_membership_as_of_a_past_date_ignores_later_bars() -> None:
    rule = universe.LiquidityRule(
        min_price=Decimal("5"), min_adtv=Decimal("1000000"), adtv_window=3, min_history=3
    )
    series = _series(["1.00"] * 5 + ["50.00"] * 5, [10] * 5 + [1_000_000] * 5)

    assert universe.members(rule, {"X": series}) == ("X",)
    early = series.bars[4].session_date
    assert universe.members(rule, {"X": series}, as_of=early) == ()


def test_adtv_rejects_a_nonsense_window() -> None:
    with pytest.raises(ValueError, match="window must be >= 1"):
        universe.average_dollar_volume(_series(["10.00"], [1]), 0)
