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


# ------------------------------------------------- DR-038: the venue says HOW a position ended


def _fill(**kwargs):
    """One execution from the activities feed, shaped like the AIS sell of 2026-09-04."""
    from swingdesk.contracts.broker import BrokerFill, FillKind, Side

    base = dict(
        activity_id="20260904154601553::cda80f58", order_id="ours-1", symbol="AIS",
        side=Side.SELL, kind=FillKind.FILL,
        transaction_time=datetime(2026, 9, 4, 19, 46, 1, tzinfo=UTC),
        price=Decimal("70.03"), shares=Decimal(17), observed_at=KNOWLEDGE,
    )
    base.update(kwargs)
    return BrokerFill(**base)


def _position(**kwargs) -> Position:
    base = dict(
        position_id="POS-AIS-2026-09-02", version=1, instrument_id="AIS", opened_on=OPENED,
        entry_price=Decimal("65.70"), shares=17, initial_stop=Decimal("61.70"),
        current_stop=Decimal("61.70"), initial_costs_per_share=Decimal("0.33"),
        strategy="test", knowledge_time=KNOWLEDGE,
    )
    base.update(kwargs)
    return Position(**base)


OURS = lambda order_id: order_id.startswith("ours")  # noqa: E731 - a one-line predicate reads better


def test_a_full_sell_of_our_own_order_closes_the_position() -> None:
    """The live instance, 2026-09-04: the protective OCO's limit leg filled and the book never
    learned, so the machine stopped with `TECH` every pass afterwards."""
    result = adoption.closing_exit(_position(), [_fill()], OURS)

    assert isinstance(result, adoption.VenueExit)
    assert result.shares == 17
    assert result.price == Decimal("70.03")
    assert result.closed_on == date(2026, 9, 4)
    assert result.order_ids == ("ours-1",)


def test_the_price_is_share_weighted_across_partial_fills() -> None:
    """A position closed over several executions left at several prices, and the mean of the PRICES
    would misreport whichever leg was larger. 10 at 70 and 7 at 60 is 65.88, not 65.00."""
    result = adoption.closing_exit(
        _position(),
        [_fill(activity_id="a", shares=Decimal(10), price=Decimal(70)),
         _fill(activity_id="b", shares=Decimal(7), price=Decimal(60),
               transaction_time=datetime(2026, 9, 4, 19, 50, tzinfo=UTC))],
        OURS,
    )

    assert isinstance(result, adoption.VenueExit)
    assert result.price == Decimal("1120") / Decimal(17)
    assert result.price != Decimal(65), "the mean of the prices is the wrong answer"
    assert result.closed_on == date(2026, 9, 4)


def test_a_sell_that_is_NOT_ours_closes_NOTHING() -> None:
    """`DR-031`'s rule in the other direction. A sale this system did not place is somebody trading
    by hand, and adopting it would be this module deciding that anything at the venue must be ours -
    the assumption most likely to be wrong on the day it matters."""
    assert adoption.closing_exit(_position(), [_fill(order_id="theirs-9")], OURS) is None


def test_absence_alone_closes_nothing() -> None:
    """The boundary the owner ratified: closing reads a FILL, never the venue's silence."""
    assert adoption.closing_exit(_position(), [], OURS) is None


def test_a_partial_sell_REFUSES_rather_than_recording_a_close() -> None:
    """A partial exit is a different action with different vocabulary, and recording one as a close
    would put a position size in the book that never existed."""
    result = adoption.closing_exit(_position(), [_fill(shares=Decimal(9))], OURS)

    assert isinstance(result, Refusal)
    assert result.code == "TECH"
    assert "partial exit" in result.reason


def test_selling_MORE_than_the_book_holds_REFUSES() -> None:
    """Which figure is wrong is a person's question, and guessing is what a reconciliation guard
    exists to prevent."""
    result = adoption.closing_exit(_position(), [_fill(shares=Decimal(20))], OURS)

    assert isinstance(result, Refusal)
    assert "20" in result.reason


def test_a_sell_dated_BEFORE_the_position_opened_REFUSES() -> None:
    """It cannot have closed this position, so the book and the venue disagree about which position
    this is - and dating a close from it would put the exit before the entry."""
    result = adoption.closing_exit(
        _position(),
        [_fill(transaction_time=datetime(2026, 8, 30, 15, 0, tzinfo=UTC))],
        OURS,
    )

    assert isinstance(result, Refusal)
    assert "cannot have closed" in result.reason


def test_a_BUY_fill_is_not_an_exit() -> None:
    """The entry's own fills sit in the same feed, and reading one as a close would shut a position
    on the day it opened."""
    from swingdesk.contracts.broker import Side

    assert adoption.closing_exit(_position(), [_fill(side=Side.BUY)], OURS) is None
