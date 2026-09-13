"""The owner's operations review of 2026-09-12: the three fixes that are read-time and safe.

Measured on the live book that evening: 52 of 52 proposed stop moves and 3 open book stops carried
sub-penny prices; `unprotected` compared book and venue stops exactly, so a venue that can only hold
cents read every such position as a stop somebody moved and `DR-036` paused entries; BTSG carried 15
unanswered stop moves at once; AIS closed with 13 still pending. `TODO.md` §6b has the whole review.

**What these tests hold, and why each one fails silently if it drifts:**

* **within a tick, strictly.** A tolerance of a whole tick would call a stop one tick away "the same"
  and hide a real disagreement; exact equality is the defect.
* **a real gap is still a gap.** A move approved in the book and never sent leaves the venue a
  whole ATR away, and that must keep being reported - it is `D6`'s and nothing here may paper it.
* **no tick, no tolerance.** A policy without a write block compares exactly: more findings, never
  fewer.
* **only a stop move is ever superseded.** An `EXIT_NOW` or `PAUSE` hidden behind a newer proposal
  would be `DR-013` 2.1's silence.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from swingdesk.broker import load_policy, unprotected
from swingdesk.broker.reconcile import same_trigger
from swingdesk.contracts.broker import PlacedOrder
from swingdesk.contracts.position import ActionKind, Position
from swingdesk.trade_management import manage

CENT = Decimal("0.01")


def _cent(_: Decimal) -> Decimal:
    return CENT


def _position(stop: str) -> Position:
    return Position(
        position_id="POS-T-2026-09-01", version=1, instrument_id="T",
        opened_on=date(2026, 9, 1), entry_price=Decimal(110), shares=100,
        initial_stop=Decimal(98), current_stop=Decimal(stop),
        initial_costs_per_share=Decimal("0.25"),
        knowledge_time=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
    )


def _stop(price: str) -> PlacedOrder:
    return PlacedOrder(
        order_id="leg-T", client_order_id="", symbol="T", status="new",
        submitted_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
        order_type="stop", stop_price=Decimal(price),
        observed_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
    )


# --- within one tick -----------------------------------------------------------------------------


@pytest.mark.parametrize("venue", ["100.76", "100.77"])
def test_a_sub_penny_book_stop_matches_both_cents_beside_it(venue):
    """DINO's book stop was 100.761817. The venue can hold 100.76 or 100.77 and nothing between."""
    assert unprotected([_position("100.761817")], [_stop(venue)], "NYSE", tick_for=_cent) == ()


def test_a_stop_a_full_tick_away_is_still_the_wrong_price():
    findings = unprotected([_position("100.761817")], [_stop("100.75")], "NYSE", tick_for=_cent)
    assert len(findings) == 1
    assert findings[0].venue_stop == Decimal("100.75")


def test_an_on_tick_book_stop_still_needs_the_exact_cent():
    """For a stop the venue CAN hold, a cent away is a cent moved - the tolerance buys nothing."""
    assert unprotected([_position("100.76")], [_stop("100.76")], "NYSE", tick_for=_cent) == ()
    assert unprotected([_position("100.76")], [_stop("100.77")], "NYSE", tick_for=_cent)


def test_an_approved_move_the_venue_never_saw_is_still_reported():
    """The review's root cause (#2): the book moved to 100.761817, the venue still holds 98.59.
    That gap is real and belongs to `D6`; the tolerance must not reach it."""
    findings = unprotected([_position("100.761817")], [_stop("98.59")], "NYSE", tick_for=_cent)
    assert len(findings) == 1
    assert findings[0].venue_stop == Decimal("98.59")


def test_no_tick_means_exact():
    """A policy with no write block has no tick, and a check handed none compares exactly."""
    assert unprotected([_position("100.761817")], [_stop("100.76")], "NYSE",
                       tick_for=lambda _: None)


def test_nothing_resting_is_reported_whatever_the_tick():
    findings = unprotected([_position("100.76")], [], "NYSE", tick_for=_cent)
    assert len(findings) == 1 and findings[0].venue_stop is None


@pytest.mark.parametrize(("venue", "book", "tick", "same"), [
    ("100.76", "100.761817", "0.01", True),
    ("100.77", "100.761817", "0.01", True),
    ("100.75", "100.761817", "0.01", False),
    ("100.77", "100.76", "0.01", False),   # exactly one tick is NOT within a tick
    ("0.5012", "0.50123", "0.0001", True),  # below a dollar the tick is finer
    ("0.5013", "0.50118", "0.0001", False),
])
def test_same_trigger_is_strictly_within_one_tick(venue, book, tick, same):
    assert same_trigger(Decimal(venue), Decimal(book), Decimal(tick)) is same


def test_the_committed_policy_supplies_the_venues_tick():
    """The live callers pass `BrokerPolicy.tick_for`; it must answer from the committed file."""
    policy = load_policy()
    assert policy.write is not None, "the committed policy carries a write block"
    assert policy.tick_for(Decimal("100.761817")) == policy.write.tick_size
    assert policy.tick_for(Decimal("0.5")) == policy.write.sub_dollar_tick


# --- superseded stop moves -----------------------------------------------------------------------


def test_only_the_latest_stop_move_on_a_position_is_live():
    unanswered = [("POS-A", 1, ActionKind.MOVE_STOP), ("POS-A", 3, ActionKind.MOVE_STOP),
                  ("POS-A", 2, ActionKind.MOVE_STOP), ("POS-B", 7, ActionKind.MOVE_STOP)]
    assert manage.superseded(unanswered) == {("POS-A", 1), ("POS-A", 2)}


@pytest.mark.parametrize("kind", [ActionKind.EXIT_NOW, ActionKind.PAUSE, ActionKind.PARTIAL_EXIT])
def test_nothing_but_a_stop_move_is_ever_superseded(kind):
    unanswered = [("POS-A", 1, kind), ("POS-A", 2, ActionKind.MOVE_STOP),
                  ("POS-A", 3, kind), ("POS-A", 4, ActionKind.MOVE_STOP)]
    assert manage.superseded(unanswered) == {("POS-A", 2)}


def test_a_single_stop_move_supersedes_nothing():
    assert manage.superseded([("POS-A", 5, ActionKind.MOVE_STOP)]) == frozenset()


def test_positions_do_not_supersede_each_other():
    unanswered = [("POS-A", 9, ActionKind.MOVE_STOP), ("POS-B", 1, ActionKind.MOVE_STOP)]
    assert manage.superseded(unanswered) == frozenset()


def test_an_answered_later_stop_move_still_supersedes():
    """Live 2026-09-13: rejecting VGT #4 brought #3 back as awaiting an answer."""
    unanswered = [("POS-A", 1, ActionKind.MOVE_STOP), ("POS-A", 3, ActionKind.MOVE_STOP),
                  ("POS-B", 2, ActionKind.MOVE_STOP)]
    assert manage.superseded(unanswered, {"POS-A": 4}) == {("POS-A", 1), ("POS-A", 3)}


def test_an_older_answered_stop_move_supersedes_nothing_newer():
    unanswered = [("POS-A", 5, ActionKind.MOVE_STOP)]
    assert manage.superseded(unanswered, {"POS-A": 2}) == frozenset()


# --- the stop in force ---------------------------------------------------------------------------


def _order(symbol: str, kind: str, stop: str | None) -> PlacedOrder:
    return PlacedOrder(
        order_id=f"{kind}-{symbol}-{stop}", client_order_id="", symbol=symbol, status="new",
        submitted_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC), order_type=kind,
        stop_price=None if stop is None else Decimal(stop),
        observed_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
    )


def test_the_highest_protective_trigger_per_symbol_is_the_one_in_force():
    """The one definition `unprotected` and `swingdesk status` both use, so the screen cannot show
    a venue stop the check did not compare."""
    from swingdesk.broker import resting_stops

    orders = [_order("T", "stop", "100.00"), _order("T", "stop", "101.50"),
              _order("U", "stop_limit", "50.00")]
    assert resting_stops(orders) == {"T": Decimal("101.50"), "U": Decimal("50.00")}


def test_a_take_profit_or_a_triggerless_order_protects_nothing():
    from swingdesk.broker import resting_stops

    assert resting_stops([_order("T", "limit", None), _order("T", "stop", None)]) == {}


def test_a_non_protective_order_with_a_price_protects_nothing_either():
    """A `limit` carrying a stop price is still not a stop - the order TYPE decides."""
    from swingdesk.broker import resting_stops

    assert resting_stops([_order("T", "limit", "99.00")]) == {}
