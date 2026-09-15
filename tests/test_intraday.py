"""The minute-bar resolver for an ambiguous daily bar (`DR-042` §9), end to end. No network.

An error anywhere here does not raise - it moves trades from one exit to the other on every study
run with minutes, and every count stays plausible. So each layer is pinned where it could go wrong:

* **`first_touch`** - time order, the boundary (`<=` stop, `>=` target), the residue.
* **`regular_hours`** - a pre-market print is not the session; an early close ends it early. Read
  from the real exchange calendar once, so the wiring is tested and not only the stub.
* **`reproduces`** - minutes in other units, or missing the bar's own extreme, are not that bar.
* **`MinuteStore`** - never fetched, fetched empty and fetched are three different answers.
* **`break_tie`** - asked only on an ambiguous bar, answers only for a TARGET, counts every answer.
* **the engine and the book** - both consult it, with the position's own stop and target, and a
  config without one behaves exactly as it did before 2026-09-14.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from tests.test_book import _atr, _book, _config, _fires_on, _series

from swingdesk.contracts.reference import Exchange, ExchangeSession
from swingdesk.contracts.trade import ExitReason
from swingdesk.market_data.minutes import Minute, MinuteStore
from swingdesk.trade_management.exits import ExitDecision, ExitPolicy
from swingdesk.validation.backtest import run_arm
from swingdesk.validation.backtest.engine import ArmResult
from swingdesk.validation.backtest.intraday import (
    MinuteTieBreak,
    Touch,
    break_tie,
    first_touch,
    regular_hours,
    reproduces,
    session_for,
)

STOP = Decimal(90)
TARGET = Decimal(110)
DAY = date(2025, 2, 21)                              # a Friday; NYSE 14:30-21:00 UTC
OPEN = datetime(2025, 2, 21, 14, 30, tzinfo=UTC)
FETCHED = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Day:
    session_date: date
    high: Decimal
    low: Decimal


def minute(offset: int, low: str, high: str, start: datetime = OPEN) -> Minute:
    return Minute(at=start + timedelta(minutes=offset), open=Decimal(low), high=Decimal(high),
                  low=Decimal(low), close=Decimal(high))


def nyse(open_time: datetime, close_time: datetime) -> ExchangeSession:
    return ExchangeSession(exchange=Exchange.NYSE, session_date=open_time.date(),
                           open_time=open_time, close_time=close_time)


# --- first_touch ---------------------------------------------------------------------------------

def test_the_earlier_minute_wins_though_a_later_one_reaches_the_other_leg() -> None:
    minutes = [minute(0, "95", "105"), minute(1, "89", "105"), minute(2, "95", "111")]
    assert first_touch(minutes, STOP, TARGET) is Touch.STOP


def test_the_same_session_the_other_way_round_answers_the_other_way() -> None:
    minutes = [minute(0, "95", "105"), minute(1, "95", "111"), minute(2, "89", "105")]
    assert first_touch(minutes, STOP, TARGET) is Touch.TARGET


def test_minutes_are_walked_in_time_order_and_never_in_the_order_given() -> None:
    minutes = [minute(2, "89", "105"), minute(1, "95", "111"), minute(0, "95", "105")]
    assert first_touch(minutes, STOP, TARGET) is Touch.TARGET


def test_a_print_exactly_at_a_leg_reaches_it() -> None:
    assert first_touch([minute(0, "90", "105")], STOP, TARGET) is Touch.STOP
    assert first_touch([minute(0, "95", "110")], STOP, TARGET) is Touch.TARGET


def test_a_minute_reaching_both_legs_is_reported_and_never_assigned() -> None:
    assert first_touch([minute(0, "89", "111")], STOP, TARGET) is Touch.WITHIN_A_MINUTE


def test_a_session_reaching_neither_says_so() -> None:
    assert first_touch([minute(0, "91", "109")], STOP, TARGET) is Touch.NEITHER
    assert first_touch([], STOP, TARGET) is Touch.NEITHER


# --- regular_hours -------------------------------------------------------------------------------

def test_the_session_starts_at_its_open_and_ends_before_its_close() -> None:
    session = nyse(OPEN, OPEN + timedelta(hours=6, minutes=30))
    minutes = [minute(-1, "1", "1"), minute(0, "1", "1"), minute(389, "1", "1"),
               minute(390, "1", "1")]
    assert [m.at for m in regular_hours(minutes, session)] == [minutes[1].at, minutes[2].at]


def test_a_pre_market_stop_touch_does_not_decide_a_regular_session() -> None:
    """A stop resting at the venue triggers in regular hours only; the daily bar being resolved is
    the regular session's."""
    session = nyse(OPEN, OPEN + timedelta(hours=6, minutes=30))
    minutes = [minute(-60, "85", "100"), minute(5, "95", "111"), minute(10, "89", "105")]
    assert first_touch(minutes, STOP, TARGET) is Touch.STOP
    assert first_touch(regular_hours(minutes, session), STOP, TARGET) is Touch.TARGET


def test_the_real_calendar_gives_the_session_its_own_hours_and_ends_an_early_close_early() -> None:
    regular = session_for("ABR", DAY)
    assert regular is not None
    assert (regular.open_time, regular.close_time) == (OPEN, OPEN + timedelta(hours=6, minutes=30))
    early = session_for("ABR", date(2025, 11, 28))      # the day after Thanksgiving, 13:00 ET
    assert early is not None
    assert early.close_time == datetime(2025, 11, 28, 18, 0, tzinfo=UTC)
    assert session_for("ABR", date(2025, 2, 22)) is None


# --- reproduces ----------------------------------------------------------------------------------

def test_minutes_within_half_a_percent_of_the_bars_extremes_are_that_bar() -> None:
    bar = Day(DAY, Decimal(100), Decimal(100))
    assert reproduces([minute(0, "99.5", "100.5")], bar)
    assert not reproduces([minute(0, "99.5", "100.6")], bar)
    assert not reproduces([minute(0, "99.4", "100.5")], bar)


def test_minutes_in_other_units_are_not_the_bar() -> None:
    """Measured 2026-09-14: BDX and FTV, whose histories two vendors adjusted by x1.30 and x1.33."""
    minutes = [minute(0, "117", "143")]
    assert reproduces(minutes, Day(DAY, Decimal(143), Decimal(117)))
    assert not reproduces(minutes, Day(DAY, Decimal(110), Decimal(90)))


def test_no_minutes_reproduce_nothing() -> None:
    assert not reproduces([], Day(DAY, Decimal(1), Decimal(1)))


# --- MinuteStore ---------------------------------------------------------------------------------

def test_never_fetched_fetched_empty_and_fetched_are_three_answers(tmp_path) -> None:
    with MinuteStore(tmp_path / "m.duckdb") as store:
        assert store.session("ABR", DAY, FETCHED) is None
        store.write("ABR", DAY, [], FETCHED, "test")
        assert store.session("ABR", DAY, FETCHED) == ()
        store.write("XYZ", DAY, [minute(1, "2", "3"), minute(0, "1", "2")], FETCHED, "test")
        got = store.session("XYZ", DAY, FETCHED)
    assert got is not None
    assert [m.at for m in got] == [OPEN, OPEN + timedelta(minutes=1)]
    assert got[0].low == Decimal(1)


def test_a_read_sees_only_what_was_known_at_its_instant(tmp_path) -> None:
    later = FETCHED + timedelta(days=1)
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("ABR", DAY, [minute(0, "1", "2")], FETCHED, "test")
        store.write("ABR", DAY, [minute(0, "5", "6")], later, "test")
        assert store.session("ABR", DAY, FETCHED - timedelta(seconds=1)) is None
        assert [m.low for m in store.session("ABR", DAY, FETCHED)] == [Decimal(1)]
        assert [m.low for m in store.session("ABR", DAY, later)] == [Decimal(5)]


# --- MinuteTieBreak ------------------------------------------------------------------------------

PRE_MARKET_THEN_TARGET = [minute(-60, "85", "100"), minute(5, "95", "111")]
THE_SESSION = Day(DAY, Decimal(111), Decimal(95))


def test_the_tie_break_reads_regular_hours_from_the_store(tmp_path) -> None:
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("ABR", DAY, PRE_MARKET_THEN_TARGET, FETCHED, "t")
        assert MinuteTieBreak(store, FETCHED)("ABR", THE_SESSION, STOP, TARGET) is Touch.TARGET


def test_minutes_that_are_not_the_bar_are_a_mismatch_and_decide_nothing(tmp_path) -> None:
    """Measured 2026-09-14: NZF's daily low is a print no consolidated minute contains. Here the
    bar says 85 and the session's minutes never went below 95 - they are not this bar."""
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("ABR", DAY, PRE_MARKET_THEN_TARGET, FETCHED, "t")
        bar = Day(DAY, Decimal(111), Decimal(85))
        assert MinuteTieBreak(store, FETCHED)("ABR", bar, STOP, TARGET) is Touch.MISMATCH


def test_what_the_store_cannot_answer_is_unavailable(tmp_path) -> None:
    with MinuteStore(tmp_path / "m.duckdb") as store:
        tie_break = MinuteTieBreak(store, FETCHED)
        assert tie_break("ABR", THE_SESSION, STOP, TARGET) is Touch.UNAVAILABLE    # never fetched
        store.write("ABR", DAY, [], FETCHED, "t")
        assert tie_break("ABR", THE_SESSION, STOP, TARGET) is Touch.UNAVAILABLE    # served empty
        store.write("PRE", DAY, [minute(-60, "95", "111")], FETCHED, "t")
        assert tie_break("PRE", THE_SESSION, STOP, TARGET) is Touch.UNAVAILABLE    # none in hours
        store.write("XYZ", DAY, [minute(5, "95", "111")], FETCHED, "t")
        shut = MinuteTieBreak(store, FETCHED, sessions=lambda instrument, on: None)
        assert shut("XYZ", THE_SESSION, STOP, TARGET) is Touch.UNAVAILABLE         # no session
        early = MinuteTieBreak(store, FETCHED - timedelta(seconds=1))
        assert early("XYZ", THE_SESSION, STOP, TARGET) is Touch.UNAVAILABLE        # not yet known


# --- break_tie -----------------------------------------------------------------------------------

AMBIGUOUS = ExitDecision(True, STOP, ExitReason.STOP, ambiguous=True)


def answering(touch: Touch):
    asked: list[tuple[str, date, Decimal, Decimal]] = []

    def tie_break(instrument_id: str, bar, stop: Decimal, target: Decimal) -> Touch:
        asked.append((instrument_id, bar.session_date, stop, target))
        return touch

    tie_break.asked = asked  # type: ignore[attr-defined]
    return tie_break


def refusing(*args: object) -> Touch:
    raise AssertionError("asked about a bar that was not ambiguous")


def test_a_target_printed_first_exits_at_the_target_and_stays_flagged() -> None:
    counts: Counter[str] = Counter()
    tie_break = answering(Touch.TARGET)
    got = break_tie(AMBIGUOUS, tie_break, "ABR", THE_SESSION, STOP, TARGET, counts)
    assert got == ExitDecision(True, TARGET, ExitReason.TARGET, ambiguous=True)
    assert tie_break.asked == [("ABR", DAY, STOP, TARGET)]
    assert counts == Counter({"target": 1})


@pytest.mark.parametrize("touch", [Touch.STOP, Touch.WITHIN_A_MINUTE, Touch.NEITHER,
                                   Touch.MISMATCH, Touch.UNAVAILABLE])
def test_every_other_answer_keeps_the_convention_and_is_counted(touch: Touch) -> None:
    counts: Counter[str] = Counter()
    got = break_tie(AMBIGUOUS, answering(touch), "ABR", THE_SESSION, STOP, TARGET, counts)
    assert got is AMBIGUOUS
    assert counts == Counter({touch.value: 1})


def test_a_bar_that_was_not_ambiguous_is_never_asked_about() -> None:
    counts: Counter[str] = Counter()
    plain = ExitDecision(True, STOP, ExitReason.STOP)
    assert break_tie(plain, refusing, "ABR", THE_SESSION, STOP, TARGET, counts) is plain
    assert counts == Counter()


def test_without_a_tie_break_or_a_target_nothing_changes_and_nothing_is_counted() -> None:
    counts: Counter[str] = Counter()
    assert break_tie(AMBIGUOUS, None, "ABR", THE_SESSION, STOP, TARGET, counts) is AMBIGUOUS
    assert break_tie(AMBIGUOUS, refusing, "ABR", THE_SESSION, STOP, None, counts) is AMBIGUOUS
    assert counts == Counter()


# --- the engine and the book ---------------------------------------------------------------------

#: Entry at 100 on bar 3, ATR 2 x 2 -> stop 96, 1R target 104. Bar 4 reaches both.
ROWS = [("100", "100", "100", "100")] * 4 + [("100", "105", "95", "100")] + \
       [("100", "100", "100", "100")] * 3
EXITS = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20, target_r_multiple=Decimal(1))
AMBIGUOUS_DAY = date(2025, 1, 6) + timedelta(days=4)


def arm(tie_break=None) -> ArmResult:
    series = _series("AAA", ROWS)
    config = _config(_fires_on(2), exits=EXITS, tie_break=tie_break)
    return run_arm(series, [True] * len(ROWS), _atr(series, "2"), config)


def test_the_engine_without_a_tie_break_takes_the_stop_as_it_always_did() -> None:
    result = arm()
    assert [(t.exit_reason, t.exit_price) for t in result.trades] == [(ExitReason.STOP, Decimal(96))]
    assert result.ambiguous_exits == 1
    assert result.tie_breaks == Counter()


def test_the_engine_asks_with_the_positions_own_stop_and_target_and_obeys() -> None:
    tie_break = answering(Touch.TARGET)
    result = arm(tie_break)
    assert tie_break.asked == [("AAA", AMBIGUOUS_DAY, Decimal(96), Decimal(104))]
    assert [(t.exit_reason, t.exit_price) for t in result.trades] == [
        (ExitReason.TARGET, Decimal(104))]
    assert result.ambiguous_exits == 1
    assert len(result.ambiguous_trades) == 1
    assert result.tie_breaks == Counter({"target": 1})


def test_the_engine_keeps_the_stop_when_the_minutes_say_stop() -> None:
    result = arm(answering(Touch.STOP))
    assert [t.exit_reason for t in result.trades] == [ExitReason.STOP]
    assert result.tie_breaks == Counter({"stop": 1})


def test_after_a_partial_the_engine_asks_with_the_stop_where_it_now_rests() -> None:
    """A target and a partial can coexist. The partial at 0.5R (102) moves the stop to breakeven,
    and the tie on the next bar is between THAT stop and the target - the trigger resting at the
    venue, not the one placed at entry."""
    rows = [("100", "100", "100", "100")] * 4 + [("100", "102.5", "99", "100"),
                                                 ("101", "105", "99", "100")] + \
           [("100", "100", "100", "100")] * 2
    exits = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                       target_r_multiple=Decimal(1), partial_trigger=Decimal("0.5"),
                       partial_fraction=Decimal("0.5"), stop_after_partial="breakeven")
    series = _series("AAA", rows)
    tie_break = answering(Touch.STOP)
    run_arm(series, [True] * len(rows), _atr(series, "2"),
            _config(_fires_on(2), exits=exits, tie_break=tie_break))
    assert tie_break.asked == [("AAA", AMBIGUOUS_DAY + timedelta(days=1), Decimal(100),
                                Decimal(104))]


def test_merging_arm_results_adds_their_tie_break_counts() -> None:
    first, second = arm(answering(Touch.TARGET)), arm(answering(Touch.STOP))
    first.merge(second)
    assert first.tie_breaks == Counter({"target": 1, "stop": 1})


def test_the_book_asks_the_same_question_and_obeys_the_same_answer() -> None:
    tie_break = answering(Touch.TARGET)
    result = _book(["AAA"], ROWS, _fires_on(2), exits=EXITS, tie_break=tie_break)
    assert tie_break.asked == [("AAA", AMBIGUOUS_DAY, Decimal(96), Decimal(104))]
    assert [(t.exit_reason, t.exit_price) for t in result.trades] == [
        (ExitReason.TARGET, Decimal(104))]
    assert result.ambiguous_exits == 1
    assert result.tie_breaks == Counter({"target": 1})


def test_the_book_without_a_tie_break_is_unchanged() -> None:
    result = _book(["AAA"], ROWS, _fires_on(2), exits=EXITS)
    assert [t.exit_reason for t in result.trades] == [ExitReason.STOP]
    assert result.tie_breaks == Counter()
