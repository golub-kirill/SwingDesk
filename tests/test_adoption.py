"""`DR-031`: a filled venue holding becomes a `Position`, and the refusals are the substance.

The whole point of this module is what it will NOT adopt. A function that turned every holding into
a position would put a number in the book that every downstream `R` is computed from, and the book
is the thing `b.min_sample` counts toward `Validated`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from swingdesk.contracts.broker import BrokerPosition, PositionSide
from swingdesk.contracts.position import Position
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.trade_management import adoption
from swingdesk.trade_management.sizing import Refusal

KNOWLEDGE = datetime(2026, 9, 3, 22, 30, tzinfo=UTC)
OPENED = date(2026, 9, 2)


def _registry() -> ParameterRegistry:
    """Only the two `DR-010` cost parameters this path reads, at their committed values."""
    return ParameterRegistry({
        "risk.costs_bp_usd": {
            "id": "risk.costs_bp_usd", "value": "50", "provenance": "assumed:DR-010",
            "status": "assumed", "unit": "basis points", "named_in": [],
        },
        "risk.costs_floor_usd": {
            "id": "risk.costs_floor_usd", "value": "0.25", "provenance": "assumed:DR-010",
            "status": "assumed", "unit": "currency per share", "named_in": [],
        },
    })


def _holding(**kwargs) -> BrokerPosition:
    base = dict(
        symbol="AIS", asset_class="us_equity", exchange="NYSE", side=PositionSide.LONG,
        shares=Decimal(17), average_entry_price=Decimal("66.46"), observed_at=KNOWLEDGE,
    )
    base.update(kwargs)
    return BrokerPosition(**base)


def _submitted(stop: Decimal = Decimal("60.97")) -> adoption.SubmittedEntry:
    return adoption.SubmittedEntry(
        instrument_id="AIS", stop_price=stop, client_order_id="swingdesk-2026-09-02-AIS",
    )


def _adopt(holding=None, submitted=None) -> Position | Refusal:
    return adoption.adopt(
        holding=holding or _holding(),
        submitted=submitted or _submitted(),
        opened_on=OPENED,
        knowledge_time=KNOWLEDGE,
        registry=_registry(),
        strategy="CARD-001",
    )


def test_the_entry_comes_from_the_venue_and_the_stop_comes_from_our_own_record() -> None:
    """The split of authority, which is the entire design of this module.

    `DR-026` refused constructing a `Position` from a broker's answer BECAUSE the venue does not
    know the stop. It does not have to: the stop is a decision this system made and journalled
    before the order went (`DR-027` §8), so it is read from our record rather than the venue's echo.
    """
    position = _adopt()
    assert isinstance(position, Position)

    # The venue's, because it is what actually filled.
    assert position.entry_price == Decimal("66.46")
    assert position.shares == 17

    # Ours, because a stop is a decision and not an observation.
    assert position.initial_stop == Decimal("60.97")
    assert position.current_stop == position.initial_stop, \
        "no D6 move has happened, so the current stop starts where the initial one is"

    # Ours, from DR-010's model: max(floor 0.25, 50bp x 66.46) = 0.3323.
    assert position.initial_costs_per_share == Decimal("0.3323")

    # Event time from the fill, knowledge time from the caller. The bitemporal split
    # `open-position` keeps by hand.
    assert position.opened_on == OPENED
    assert position.knowledge_time == KNOWLEDGE
    assert position.strategy == "CARD-001", \
        "a position tagged `unspecified` cannot be grouped with the trades that validate its card"


def test_a_short_is_refused_because_this_system_cannot_describe_one() -> None:
    """Not a preference. Every stop validator in `contracts.position` requires the stop below entry."""
    refusal = _adopt(holding=_holding(side=PositionSide.SHORT))
    assert isinstance(refusal, Refusal)
    assert refusal.code == "RISK"
    assert "short" in refusal.reason


def test_a_fractional_holding_is_refused_rather_than_rounded() -> None:
    """Rounding to record it would make the two books disagree BY DESIGN, which is worse than a gap."""
    refusal = _adopt(holding=_holding(shares=Decimal("17.5")))
    assert isinstance(refusal, Refusal)
    assert refusal.code == "RISK"


def test_a_fill_at_or_below_the_stop_we_sent_is_refused_and_says_why() -> None:
    """A position past its exit at the moment it is recorded needs a person, not a record.

    Recording it would give the book a position whose R denominator is zero or negative, and R is
    what the entire validation programme is denominated in.
    """
    refusal = _adopt(submitted=_submitted(stop=Decimal("66.46")))
    assert isinstance(refusal, Refusal)
    assert refusal.code == "STOP"
    assert "R denominator" in refusal.reason


def test_an_unset_cost_parameter_refuses_rather_than_assuming_zero() -> None:
    """Fail closed, exactly as `open-position` and `sizing` do.

    `costs` sits inside `risk_per_share = entry - stop + costs`, so a smaller cost silently produces
    a flattering R on every trade that follows.
    """
    empty = ParameterRegistry({
        "risk.costs_bp_usd": {
            "id": "risk.costs_bp_usd", "value": None, "provenance": "unset",
            "status": "unset", "unit": "basis points", "named_in": [],
        },
    })
    refusal = adoption.adopt(
        holding=_holding(), submitted=_submitted(), opened_on=OPENED,
        knowledge_time=KNOWLEDGE, registry=empty, strategy="CARD-001",
    )
    assert isinstance(refusal, Refusal)


def test_the_position_id_is_derived_from_the_instrument_and_the_session_it_opened_in() -> None:
    """Same shape `open-position` derives, so a synced position and a hand-recorded one collide
    rather than quietly coexisting as two records of one holding."""
    position = _adopt()
    assert isinstance(position, Position)
    assert position.position_id == "POS-AIS-2026-09-02"
