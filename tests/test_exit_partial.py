"""The partial exit: `M54`, the one slot the course specifies in detail, and it specifies no number.

Twelve topics carry it — the trigger at 1R (`T0821`), a half (`T0823`) or a third (`T0824`), the
stop move afterwards (`T0827`, an Operational Course Rule), and, in the course's own words,
`Психологические преимущества` against `Математические недостатки`.

Four things carry the implementation and none of them raises when wrong:

* **a partial must not close the position.** `exited` stays False and there is no `ExitReason`, or
  the caller books the same shares twice — once as a partial and once as an exit.
* **the arithmetic must reduce to today's when the slot is unused.** `PR-002`, `PR-005`, `PR-011`
  and `PR-012` published trade logs, and a default that re-priced them would change published
  evidence nobody re-ran.
* **the stop is checked before the partial**, exactly as it is before the target. Same unknowable
  sequence, same pessimistic resolution (`DR-042`).
* **breakeven means the entry FILL.** Moving to the quoted entry leaves the position short by one
  side's slippage and calls it flat.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.trade_management.exits import ExitDecision, ExitPolicy

KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
ENTRY, RISK, STOP, ONE_R = Decimal(100), Decimal(10), Decimal(90), Decimal(110)

TWO_SLOT = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20)
PARTIAL = ExitPolicy(
    atr_stop_multiple=Decimal(2), max_holding_bars=20,
    partial_trigger=Decimal(1), partial_fraction=Decimal("0.5"), stop_after_partial="breakeven",
)


def bar(open_: str, high: str, low: str, close: str) -> Bar:
    return Bar(
        instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
        event_time=datetime(2026, 1, 15, tzinfo=UTC), session_date=date(2026, 1, 15),
        open=Decimal(open_), high=Decimal(high), low=Decimal(low), close=Decimal(close),
        volume=1_000_000, knowledge_time=KNOWN,
    )


# --- the policy refuses what it cannot execute ---------------------------------------------------

def test_a_trigger_without_a_fraction_is_refused() -> None:
    with pytest.raises(ValueError, match="trigger AND a fraction"):
        ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                   partial_trigger=Decimal(1))


def test_a_fraction_without_a_trigger_is_refused() -> None:
    with pytest.raises(ValueError, match="trigger AND a fraction"):
        ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                   partial_fraction=Decimal("0.5"))


@pytest.mark.parametrize("fraction", [Decimal(0), Decimal(1), Decimal("1.5"), Decimal("-0.5")])
def test_a_fraction_that_is_not_strictly_part_of_the_position_is_refused(fraction) -> None:
    """1.0 closes the whole position and calls it a reduction. `Trade` refuses that too - the same
    invariant on both sides, so the harness cannot build a record the contract would reject."""
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                   partial_trigger=Decimal(1), partial_fraction=fraction)


def test_a_stop_move_with_no_partial_to_follow_is_refused() -> None:
    with pytest.raises(ValueError, match="no partial to follow"):
        ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                   stop_after_partial="breakeven")


def test_a_stop_rule_this_does_not_implement_is_refused_rather_than_ignored() -> None:
    """`M54-T0827` names the concept and quantifies nothing. Silently ignoring an unknown rule
    would run a study under a policy its own record does not describe."""
    with pytest.raises(ValueError, match="not a rule this implements"):
        ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                   partial_trigger=Decimal(1), partial_fraction=Decimal("0.5"),
                   stop_after_partial="trail")


# --- the price and the stop move -----------------------------------------------------------------

def test_the_partial_fills_r_multiples_above_entry_on_the_positions_own_denominator() -> None:
    assert PARTIAL.partial_for(ENTRY, RISK) == ONE_R
    assert TWO_SLOT.partial_for(ENTRY, RISK) is None


def test_breakeven_is_the_entry_FILL_and_not_the_original_stop() -> None:
    assert PARTIAL.stop_after(ENTRY, STOP) == ENTRY


def test_without_a_stop_rule_the_stop_does_not_move() -> None:
    """The course's other reading, and what an unset `exit.stop_move_after_partial` means."""
    policy = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                        partial_trigger=Decimal(1), partial_fraction=Decimal("0.5"))
    assert policy.stop_after(ENTRY, STOP) == STOP


# --- the ordering --------------------------------------------------------------------------------

def test_a_partial_reduces_and_does_not_exit() -> None:
    decision = PARTIAL.evaluate(bar("100", "111", "99", "108"), STOP, 5, None, ONE_R)
    assert decision.partial
    assert not decision.exited
    assert decision.reason is None
    assert decision.price == ONE_R


def test_the_stop_is_checked_BEFORE_the_partial_and_the_bar_is_flagged() -> None:
    """Same unknowable sequence as the target, same pessimistic resolution. A bar that reached
    both books the loss and the trigger is never taken."""
    decision = PARTIAL.evaluate(bar("100", "111", "89", "105"), STOP, 5, None, ONE_R)
    assert decision.exited
    assert decision.reason is ExitReason.STOP
    assert decision.ambiguous
    assert not decision.partial


def test_a_gap_through_the_stop_beats_the_partial_too() -> None:
    decision = PARTIAL.evaluate(bar("85", "112", "84", "111"), STOP, 5, None, ONE_R)
    assert decision.reason is ExitReason.STOP_GAP
    assert decision.price == Decimal(85)


def test_a_gap_above_the_trigger_fills_the_partial_at_the_TRIGGER_not_the_open() -> None:
    """The favourable gap is not credited here either — `measure_exit_surface`'s convention, and
    the same one `DR-042` applies to the target."""
    decision = PARTIAL.evaluate(bar("118", "120", "117", "119"), STOP, 5, None, ONE_R)
    assert decision.partial
    assert decision.price == ONE_R


def test_the_caller_disarms_the_slot_by_passing_None_and_the_rule_needs_no_memory() -> None:
    """Once taken, the caller stops passing a partial price. A policy that remembered would be
    stateful, and one `ExitPolicy` is shared by every position in a run."""
    already_taken = PARTIAL.evaluate(bar("100", "111", "99", "108"), STOP, 5, None, None)
    assert not already_taken.exited
    assert not already_taken.partial


def test_the_time_exit_still_comes_last() -> None:
    decision = PARTIAL.evaluate(bar("100", "111", "99", "101"), STOP, 20, None, ONE_R)
    assert decision.partial, "the partial fires on the final session rather than timing out"


def test_a_position_reaching_nothing_on_its_last_session_times_out() -> None:
    decision = PARTIAL.evaluate(bar("100", "105", "99", "104"), STOP, 20, None, ONE_R)
    assert decision.reason is ExitReason.TIME


# --- the decision cannot express nonsense --------------------------------------------------------

def test_a_partial_that_claims_to_have_exited_is_refused() -> None:
    with pytest.raises(ValueError, match="reduces a position"):
        ExitDecision(True, ONE_R, ExitReason.TARGET, partial=True)


def test_a_partial_with_no_price_is_refused() -> None:
    with pytest.raises(ValueError, match="price it filled at"):
        ExitDecision(False, None, partial=True)


# --- the trade record ----------------------------------------------------------------------------

def trade(**over) -> Trade:
    base = dict(
        instrument_id="TEST.1", arm="partial",
        signal_date=date(2026, 1, 1), entry_date=date(2026, 1, 2), exit_date=date(2026, 1, 30),
        entry_price=ENTRY, stop_price=STOP, exit_price=ENTRY, shares=100,
        initial_risk_per_share=RISK, costs=Decimal(0),
        mfe=Decimal(1), mae=Decimal(0), exit_reason=ExitReason.STOP,
    )
    base.update(over)
    return Trade(**base)


def test_a_trade_with_no_partial_prices_exactly_as_it_always_did() -> None:
    """The property every published log depends on."""
    plain = trade(exit_price=Decimal(120))
    assert plain.partial_shares == 0
    assert plain.gross_r == Decimal(2)
    assert plain.runner_shares == 100


def test_half_banked_at_1R_with_the_runner_flat_is_half_an_R() -> None:
    """The construction `PR-017` will measure: 50 shares at +1R, 50 back at breakeven."""
    partial = trade(partial_shares=50, partial_price=ONE_R, partial_date=date(2026, 1, 10),
                    exit_price=ENTRY)
    assert partial.gross_r == Decimal("0.5")
    assert partial.runner_shares == 50


def test_the_runner_carries_its_own_outcome() -> None:
    """Half at +1R and half stopped at -1R nets zero, which is the whole argument for the
    construction and the whole argument against it."""
    partial = trade(partial_shares=50, partial_price=ONE_R, partial_date=date(2026, 1, 10),
                    exit_price=Decimal(90))
    assert partial.gross_r == Decimal(0)


def test_costs_come_off_the_whole_position_and_not_off_a_leg() -> None:
    partial = trade(partial_shares=50, partial_price=ONE_R, partial_date=date(2026, 1, 10),
                    exit_price=ENTRY, costs=Decimal(100))
    assert partial.net_r == Decimal("0.5") - Decimal(100) / (RISK * 100)


@pytest.mark.parametrize(("field", "value"), [
    ("partial_shares", 50), ("partial_price", ONE_R), ("partial_date", date(2026, 1, 10)),
])
def test_a_partial_needs_all_three_facts_or_none(field, value) -> None:
    """Two without the third is a trade nobody can price, and every other check here passes."""
    with pytest.raises(ValueError, match="shares, price and date together"):
        trade(**{field: value})


def test_a_partial_of_the_whole_position_is_refused_as_an_exit() -> None:
    with pytest.raises(ValueError, match="closes the position"):
        trade(partial_shares=100, partial_price=ONE_R, partial_date=date(2026, 1, 10))


def test_a_partial_outside_the_positions_life_is_refused() -> None:
    with pytest.raises(ValueError, match="outside the position's life"):
        trade(partial_shares=50, partial_price=ONE_R, partial_date=date(2026, 2, 15))
