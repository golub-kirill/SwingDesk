"""The profit slot, tested where the rules live (`DR-042`).

**These are tests of `ExitPolicy.evaluate`, not of a backtest run, and that is deliberate.** On
2026-09-07 five mutants of `DR-041`'s guard survived a suite whose tests reached the rule through a
CLI: the assertions could not tell the guard's refusal from the contract's, so removing the guard
changed nothing they could see. The rules that matter here are four ordering decisions, each of
which is a one-line branch, and each is asserted here against a hand-built bar whose right answer is
arithmetic.

The ordering under test, from `evaluate`'s own docstring:

1. a session opening below the stop fills at the OPEN
2. a session opening above the target fills at the TARGET, not at the open
3. intraday, the stop is checked BEFORE the target, and the bar is flagged `ambiguous`
4. the stop is checked before the TIME exit
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.contracts.trade import ExitReason
from swingdesk.trade_management.exits import ExitPolicy

KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)

ENTRY = Decimal(100)
RISK = Decimal(10)          # entry - stop
STOP = Decimal(90)
TARGET = Decimal(110)       # 1R above entry, which is `exit.target_r_multiple` ratified by DR-029

TWO_SLOT = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20)
THREE_SLOT = ExitPolicy(
    atr_stop_multiple=Decimal(2), max_holding_bars=20, target_r_multiple=Decimal(1)
)


def bar(open_: str, high: str, low: str, close: str) -> Bar:
    return Bar(
        instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
        event_time=datetime(2026, 1, 15, tzinfo=UTC), session_date=date(2026, 1, 15),
        open=Decimal(open_), high=Decimal(high), low=Decimal(low), close=Decimal(close),
        volume=1_000_000, knowledge_time=KNOWN,
    )


# --- the target price itself -------------------------------------------------------------------

def test_target_is_r_multiples_above_entry_on_the_positions_own_denominator() -> None:
    assert THREE_SLOT.target_for(ENTRY, RISK) == Decimal(110)
    assert ExitPolicy(
        atr_stop_multiple=Decimal(2), max_holding_bars=20, target_r_multiple=Decimal("2.5")
    ).target_for(ENTRY, RISK) == Decimal(125)


def test_an_unused_profit_slot_has_no_target() -> None:
    assert TWO_SLOT.target_for(ENTRY, RISK) is None


@pytest.mark.parametrize("multiple", [Decimal(0), Decimal("-1")])
def test_a_target_at_or_below_the_entry_is_refused(multiple: Decimal) -> None:
    """The same refusal `broker/submit.py:target_price` makes. The harness must not be able to
    express an order the venue would reject."""
    with pytest.raises(ValueError, match="target_r_multiple must be > 0"):
        ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20, target_r_multiple=multiple)


# --- rule 1: the open, below the stop ------------------------------------------------------------

def test_a_gap_through_the_stop_fills_at_the_open_even_when_the_target_was_also_reachable() -> None:
    """A bar that opened at 85, then rallied through 110. The stop leg was already filled at the
    open; the rally is not available to a position that no longer exists."""
    decision = THREE_SLOT.evaluate(bar("85", "112", "84", "111"), STOP, 5, TARGET)
    assert decision.exited
    assert decision.reason is ExitReason.STOP_GAP
    assert decision.price == Decimal(85)
    assert not decision.ambiguous


# --- rule 2: the open, above the target ----------------------------------------------------------

def test_a_gap_through_the_target_fills_at_the_target_and_not_at_the_better_open() -> None:
    """The favourable gap is NOT credited. A real limit order would have filled at 118; this
    records 110. Convention set by `measure_exit_surface.py` on 2026-09-06 and kept because a
    harness that credits its own good luck is the one that produces a beautiful equity curve."""
    decision = THREE_SLOT.evaluate(bar("118", "120", "117", "119"), STOP, 5, TARGET)
    assert decision.exited
    assert decision.reason is ExitReason.TARGET
    assert decision.price == TARGET


# --- rule 3: intraday, the tie-break -------------------------------------------------------------

def test_a_bar_reaching_both_legs_intraday_takes_the_stop_and_is_flagged_ambiguous() -> None:
    """Opened inside the range, traded down to 89 and up to 111. A daily bar cannot say which came
    first, so the stop wins - and the flag is what makes the size of that assumption countable."""
    decision = THREE_SLOT.evaluate(bar("100", "111", "89", "105"), STOP, 5, TARGET)
    assert decision.exited
    assert decision.reason is ExitReason.STOP
    assert decision.price == STOP
    assert decision.ambiguous


def test_a_bar_reaching_only_the_target_is_not_ambiguous() -> None:
    decision = THREE_SLOT.evaluate(bar("100", "111", "99", "108"), STOP, 5, TARGET)
    assert decision.exited
    assert decision.reason is ExitReason.TARGET
    assert decision.price == TARGET
    assert not decision.ambiguous


def test_a_bar_reaching_only_the_stop_is_not_ambiguous() -> None:
    decision = THREE_SLOT.evaluate(bar("100", "105", "89", "92"), STOP, 5, TARGET)
    assert decision.exited
    assert decision.reason is ExitReason.STOP
    assert not decision.ambiguous


def test_touching_the_target_exactly_is_a_fill() -> None:
    """`>=`, not `>`. A limit resting at 110 fills when the print is 110."""
    assert THREE_SLOT.evaluate(bar("100", "110", "99", "109"), STOP, 5, TARGET).reason is (
        ExitReason.TARGET
    )


# --- rule 4: the clock, last ---------------------------------------------------------------------

def test_the_target_beats_the_clock_on_the_final_bar() -> None:
    """Session 20 that also reached +1R exits at the target, not at the close. The profit slot
    fires intraday; the time slot only ever fires at a close."""
    decision = THREE_SLOT.evaluate(bar("100", "111", "99", "101"), STOP, 20, TARGET)
    assert decision.reason is ExitReason.TARGET
    assert decision.price == TARGET


def test_the_stop_still_beats_the_clock() -> None:
    decision = THREE_SLOT.evaluate(bar("100", "105", "89", "104"), STOP, 20, TARGET)
    assert decision.reason is ExitReason.STOP


def test_a_bar_reaching_neither_leg_on_the_final_session_is_a_time_exit() -> None:
    decision = THREE_SLOT.evaluate(bar("100", "105", "99", "104"), STOP, 20, TARGET)
    assert decision.reason is ExitReason.TIME
    assert decision.price == Decimal(104)


# --- the two-slot policy is unchanged, which is what protects every published trade log ----------

@pytest.mark.parametrize(
    ("row", "reason", "price"),
    [
        (("85", "112", "84", "111"), ExitReason.STOP_GAP, Decimal(85)),
        (("118", "120", "117", "119"), None, None),
        (("100", "111", "89", "105"), ExitReason.STOP, STOP),
        (("100", "111", "99", "108"), None, None),
    ],
)
def test_without_a_target_every_decision_is_what_it_was_before_dr_042(
    row: tuple[str, str, str, str], reason: ExitReason | None, price: Decimal | None
) -> None:
    """`PR-002`, `PR-005`, `PR-011` and `PR-012` published trade logs under the two-slot policy. A
    default target would have re-priced all four silently."""
    decision = TWO_SLOT.evaluate(bar(*row), STOP, 5)
    assert decision.exited is (reason is not None)
    assert decision.reason is reason
    assert decision.price == price
    assert not decision.ambiguous


def test_an_omitted_target_argument_is_the_same_as_no_profit_slot() -> None:
    """The three-slot policy called WITHOUT a target price behaves as two-slot. This is what makes
    `book.py` and `manage.py` safe to leave alone: they pass three arguments and always will."""
    assert THREE_SLOT.evaluate(bar("100", "111", "99", "108"), STOP, 5).exited is False
