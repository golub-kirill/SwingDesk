"""The universe null's arithmetic - what makes `trade - pool` mean "inside the universe".

Three things carry it, and each fails silently:

* **membership is known BEFORE the session it prices.** The pool on a day is the one formed at the
  latest formation strictly before it; a pool formed ON the day would know that day's close.
* **the pool is an equal-weighted MEAN of its members**, and a member with no bar that day is not in
  that day's mean rather than counted as a zero.
* **the leg has the `SPY` leg's form**: bought at the entry session's open, marked at the exit's
  close, compounded, and scaled into the trade's own R - or the two nulls are not comparable.
"""

from __future__ import annotations

import importlib.util
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tool():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_universe_null",
                                                  REPO / "tools" / "measure_universe_null.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


D = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]


def _series(name: str, rows: list[tuple[date, str, str]]):
    """A series of `(session, open, close)`; high and low bracket them."""
    from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

    known = datetime(2024, 2, 1, tzinfo=UTC)
    bars = tuple(Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                     event_time=datetime.combine(d, time(14, 30), tzinfo=UTC), session_date=d,
                     open=Decimal(o), close=Decimal(c), high=max(Decimal(o), Decimal(c)),
                     low=min(Decimal(o), Decimal(c)), volume=1000, knowledge_time=known)
                 for d, o, c in rows)
    return BarSeries(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=known, bars=bars)


# --- membership -------------------------------------------------------------------------------------


def test_a_session_belongs_to_the_latest_formation_strictly_before_it(tool):
    live = [D[2], D[5]]
    assert tool.pool_formation(D[3], live) == D[2]
    assert tool.pool_formation(D[6], live) == D[5]


def test_a_formation_day_is_priced_by_the_previous_pool_not_its_own(tool):
    """The pool formed at D5 is known at D5's CLOSE, so it cannot own D5's return."""
    assert tool.pool_formation(D[5], [D[2], D[5]]) == D[2]


def test_a_session_before_the_first_formation_has_no_pool(tool):
    assert tool.pool_formation(D[1], [D[2], D[5]]) is None
    assert tool.pool_formation(D[2], [D[2], D[5]]) is None


def test_segments_partition_the_sessions_after_the_first_formation(tool):
    got = tool.segments([D[2], D[5]], D)
    assert got == {D[2]: D[3:6], D[5]: D[6:]}


# --- the pool's mean --------------------------------------------------------------------------------


def test_a_member_adds_its_close_to_close_and_open_to_close_returns(tool):
    sums = defaultdict(lambda: [0.0, 0, 0.0, 0])
    tool.contribute(sums, _series("A", [(D[0], "10", "10"), (D[1], "10", "11")]), [D[1]])
    assert sums[D[1]] == pytest.approx([0.1, 1, 0.1, 1])


def test_a_gap_day_keeps_the_two_returns_apart(tool):
    """Every other fixture opens at the previous close, where the two returns coincide. Closed at
    10, opened at 12, closed at 13.2: the session earned +32% and the open-to-close +10%."""
    sums = defaultdict(lambda: [0.0, 0, 0.0, 0])
    tool.contribute(sums, _series("A", [(D[0], "10", "10"), (D[1], "12", "13.2")]), [D[1]])
    close_to_close, open_to_close = tool.daily_pool(sums)
    assert close_to_close[D[1]] == pytest.approx(0.32)
    assert open_to_close[D[1]] == pytest.approx(0.10)


def test_the_pool_is_the_mean_of_its_members_not_their_sum(tool):
    """+10% and +20%: the mean is 15%, the sum 30%. (The first draft used +10% and -10%, where a
    sum and a mean are both zero - a surviving mutant found it.)"""
    sums = defaultdict(lambda: [0.0, 0, 0.0, 0])
    tool.contribute(sums, _series("A", [(D[0], "10", "10"), (D[1], "10", "11")]), [D[1]])
    tool.contribute(sums, _series("B", [(D[0], "20", "20"), (D[1], "20", "24")]), [D[1]])
    close_to_close, open_to_close = tool.daily_pool(sums)
    assert close_to_close[D[1]] == pytest.approx(0.15)
    assert open_to_close[D[1]] == pytest.approx(0.15)


def test_a_members_first_bar_has_no_previous_close_and_adds_nothing(tool):
    """Without the guard, `bars[i - 1]` at `i = 0` is the member's LAST bar, and its first session
    would carry a return against a price from the far end of the series."""
    sums = defaultdict(lambda: [0.0, 0, 0.0, 0])
    tool.contribute(sums, _series("A", [(D[1], "10", "11"), (D[2], "11", "30")]), [D[1]])
    assert sums[D[1]] == [0.0, 0, 0.0, 0]


def test_a_member_without_a_bar_that_day_is_out_of_the_mean_not_a_zero(tool):
    sums = defaultdict(lambda: [0.0, 0, 0.0, 0])
    tool.contribute(sums, _series("A", [(D[0], "10", "10"), (D[1], "10", "11")]), [D[1]])
    tool.contribute(sums, _series("B", [(D[0], "20", "20")]), [D[1]])
    close_to_close, _ = tool.daily_pool(sums)
    assert close_to_close[D[1]] == pytest.approx(0.1)


def test_only_the_days_asked_for_are_added(tool):
    sums = defaultdict(lambda: [0.0, 0, 0.0, 0])
    tool.contribute(sums, _series("A", [(D[0], "10", "10"), (D[1], "10", "11"),
                                        (D[2], "11", "12")]), [D[2]])
    assert set(sums) == {D[2]}


# --- the leg ----------------------------------------------------------------------------------------


def _trade(entry: date, exit_: date, price: str = "50", risk: str = "5"):
    return SimpleNamespace(entry_date=entry, exit_date=exit_, entry_price=Decimal(price),
                           initial_risk_per_share=Decimal(risk), net_r=Decimal("0.2"))


def test_the_leg_opens_at_the_entry_open_and_compounds_to_the_exit_close(tool):
    """+2% open-to-close on the entry day, then +1% and -1% close-to-close: 1.02 x 1.01 x 0.99."""
    calendar = D[:5]
    index = {d: i for i, d in enumerate(calendar)}
    close_to_close = {D[1]: 0.5, D[2]: 0.01, D[3]: -0.01}
    open_to_close = {D[1]: 0.02}
    got = tool.pool_r(_trade(D[1], D[3]), close_to_close, open_to_close, calendar, index)
    assert got == pytest.approx((1.02 * 1.01 * 0.99 - 1) * 10)


def test_a_same_day_exit_is_the_open_to_close_alone(tool):
    index = {d: i for i, d in enumerate(D)}
    got = tool.pool_r(_trade(D[1], D[1]), {D[1]: 0.5}, {D[1]: 0.02}, D, index)
    assert got == pytest.approx(0.02 * 10)


def test_the_leg_is_scaled_into_the_trades_own_R(tool):
    index = {d: i for i, d in enumerate(D)}
    wide = tool.pool_r(_trade(D[1], D[1], risk="10"), {}, {D[1]: 0.02}, D, index)
    assert wide == pytest.approx(0.02 * 5)


def test_a_session_without_a_pool_return_leaves_the_trade_unpriced(tool):
    index = {d: i for i, d in enumerate(D)}
    assert tool.pool_r(_trade(D[1], D[3]), {D[2]: 0.01}, {D[1]: 0.02}, D, index) is None
    assert tool.pool_r(_trade(D[1], D[3]), {D[2]: 0.01, D[3]: 0.0}, {}, D, index) is None


def test_legs_count_what_either_null_cannot_price(tool):
    index = {d: i for i, d in enumerate(D)}
    spy = ({D[1]: Decimal("400")}, {D[1]: Decimal("404"), D[2]: Decimal("408")})
    pool = ({D[2]: 0.01}, {D[1]: 0.02})
    rows, unpriced = tool.legs([_trade(D[1], D[1]), _trade(D[1], D[4])], spy, pool, D, index)
    assert unpriced == 1 and len(rows) == 1
    entry, trade_r, spy_r, pool_r = rows[0]
    assert (entry, trade_r) == (D[1], pytest.approx(0.2))
    assert spy_r == pytest.approx(0.01 * 10) and pool_r == pytest.approx(0.02 * 10)
