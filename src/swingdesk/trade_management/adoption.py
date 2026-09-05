"""Turning a filled venue holding into a `Position` this system's book carries. `DR-031`.

**`DR-026` refused this, and the refusal has a stated reason that has since gone.** It recorded
that a broker's answer cannot construct a `Position` *because the venue does not know the stop*.
That was true of a book somebody else opened. It is not true of an entry **this system placed**:
`DR-027` §3.2 submits the stop as a bracket leg, and §8 records it in `journal.duckdb` before the
order goes. So the stop is not read back from the venue at all - it is read from OUR OWN RECORD of
what we decided, which is a stronger source than the venue's echo of it.

**The split of authority is the whole design, and it runs one way each.**

| field | whose | why |
|---|---|---|
| `entry_price`, `shares` | the VENUE's | what actually filled, averaged by the party that filled it |
| `initial_stop` | OURS, from `submissions` | the stop is a decision, frozen at submission (`RISK_SPEC` §2) |
| `initial_costs_per_share` | OURS, from `DR-010` | the venue does not charge what the model charges |
| `opened_on` | the VENUE's | the session the fill happened in, not the one that decided it |

Nothing here is inferred from a shape. A holding that traces to no `sent` submission of ours is
**not adopted** - it is somebody trading by hand, and `DR-027` §11's guard should keep stopping
submission until a person deals with it. Adopting it would be this module deciding that anything at
the venue must have been ours, which is the assumption most likely to be wrong on the day it
matters.

Pure: no store, no clock, no network. The caller reads both sides and this decides what the book
should say.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from swingdesk.contracts.broker import BrokerFill, BrokerPosition, PositionSide, Side
from swingdesk.contracts.position import Position
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.trade_management.sizing import Refusal, costs_per_share


@dataclass(frozen=True, slots=True)
class SubmittedEntry:
    """The half of a fill the venue does not know: what this system decided when it sent the order.

    Deliberately NOT `journal.Submission` - this module holds no store, and a pure function taking
    a persistence row would be one import away from reading one.
    """

    instrument_id: str
    stop_price: Decimal
    client_order_id: str


def adopt(
    holding: BrokerPosition,
    submitted: SubmittedEntry,
    opened_on: date,
    knowledge_time: datetime,
    registry: ParameterRegistry,
    strategy: str,
) -> Position | Refusal:
    """One venue holding plus the order we sent for it, or a coded refusal naming what stopped it.

    **Every refusal here is a fact this system cannot describe**, never a threshold and never a
    preference. `RISK_SPEC` sizes a long equity position from a per-share stop below entry; a short,
    a fraction of a share and a stop above the fill are each outside what a `Position` can say, and
    recording one anyway would put a number in the book that every downstream `R` is computed from.
    """
    if holding.side is not PositionSide.LONG:
        return Refusal(
            "RISK",
            f"{holding.symbol} is held {holding.side.value} at the venue and this system cannot "
            f"describe a short: every stop validator in contracts.position requires the stop below "
            f"entry. Recorded by hand or closed at the venue, never adopted.",
        )

    if holding.shares != holding.shares.to_integral_value():
        return Refusal(
            "RISK",
            f"{holding.symbol} is held as {holding.shares} shares and Position.shares is a whole "
            f"number. Rounding it to record it would make the two books disagree by design.",
        )
    shares = int(holding.shares)
    if shares <= 0:
        return Refusal("RISK", f"{holding.symbol} is held as {shares} shares, which is not a holding")

    entry = holding.average_entry_price
    if submitted.stop_price >= entry:
        # NOT a validation detail. The fill came in at or below the stop we sent, which means the
        # position is already past its exit at the moment it is recorded - a fact about the trade
        # that a person has to look at, and one this system would otherwise write down as a
        # position with a negative R denominator.
        return Refusal(
            "STOP",
            f"{holding.symbol} filled at {entry} and the stop we submitted was "
            f"{submitted.stop_price}, at or above it. A position whose stop is not below its entry "
            f"has no R denominator; this needs a person, not a record.",
        )

    costs = costs_per_share(entry, VENUE_CURRENCY, registry)
    if isinstance(costs, Refusal):
        # Fail closed, exactly as `open-position` does: a missing cost parameter is refused and
        # never assumed. `costs` is inside the R denominator, so a guess here flatters every
        # statistic the validation programme is measured in.
        return costs
    costs_value, _bp, _floor = costs

    return Position(
        position_id=f"POS-{submitted.instrument_id}-{opened_on.isoformat()}",
        version=1,
        instrument_id=submitted.instrument_id,
        opened_on=opened_on,
        entry_price=entry,
        shares=shares,
        # BOTH from our own submission. `current_stop` starts where `initial_stop` does because
        # `D6` governs every move after that and no move has happened yet.
        initial_stop=submitted.stop_price,
        current_stop=submitted.stop_price,
        initial_costs_per_share=costs_value,
        strategy=strategy,
        knowledge_time=knowledge_time,
    )


#: The currency `DR-010`'s cost model is charged in for anything this venue can hold.
#:
#: `broker_policy.yml` declares `venue.market: NYSE` and `broker.submit.entry_order` refuses any
#: instrument the calendar puts on another exchange, so a holding that reaches this module is a US
#: listing and its costs are USD. Named rather than defaulted to a base currency, because
#: `AGENTS.md` §3 keeps USA and Canada separate and `account.base_currency` could one day be either.
VENUE_CURRENCY = "USD"


@dataclass(frozen=True, slots=True)
class VenueExit:
    """The venue's own account of how a position ended: what filled, at what, and settling which order."""

    shares: int
    price: Decimal
    closed_on: date
    order_ids: tuple[str, ...]
    activity_ids: tuple[str, ...]


def closing_exit(
    position: Position,
    fills: Sequence[BrokerFill],
    ours: Callable[[str], bool],
) -> VenueExit | Refusal | None:
    """How the venue says a position ended, or a coded refusal, or `None` when it cannot say.

    **This is `adopt` in the other direction and it obeys the same rule: only what THIS SYSTEM
    placed.** `DR-031` adopts an entry because the fill traces to an order in `submissions`; a close
    is attributed the same way, by asking whether the order the SELL fill settled is one of ours.
    `ours` answers that by id, which is exact - the alternative, assuming the newest attempt for an
    instrument must be the one that sold, credits a close to an order that may not have produced it.

    **It never reads ABSENCE.** A position missing from the venue is not evidence of anything here:
    the venue's silence could be a hand-sale, a transfer, or an account this system does not
    understand. What closes a position is a POSITIVE record of shares leaving - the same standard
    `DR-031` applies to shares arriving. `None` means the venue offered no such record, and the
    caller leaves the divergence to a person (`DR-027` §11).

    Three refusals, each a fact the book cannot describe rather than a threshold:

      - fewer shares sold than held - a PARTIAL exit, which is a different action with different
        vocabulary and a size the book would otherwise record wrongly;
      - more shares sold than held - the book and the venue disagree about the size, and guessing
        which is right is exactly what a reconciliation guard exists to prevent;
      - a sell dated before the position opened, which cannot have closed it.

    Pure, like everything else here: no store, no clock, no network.
    """
    relevant = [
        fill for fill in fills
        if fill.symbol == position.instrument_id
        and fill.side is Side.SELL
        and ours(fill.order_id)
    ]
    if not relevant:
        return None

    early = [f for f in relevant if f.transaction_time.date() < position.opened_on]
    if early:
        return Refusal(
            "TECH",
            f"{position.instrument_id}: a sell dated {min(f.transaction_time.date() for f in early)} "
            f"cannot have closed a position opened {position.opened_on}. The book and the venue "
            f"disagree about which position this is.",
        )

    sold = sum((fill.shares for fill in relevant), start=Decimal(0))
    if sold < position.shares:
        return Refusal(
            "TECH",
            f"{position.instrument_id}: the venue sold {sold} of {position.shares} shares. A "
            f"partial exit is a different action from a close and this does not record one.",
        )
    if sold > position.shares:
        return Refusal(
            "TECH",
            f"{position.instrument_id}: the venue sold {sold} shares against {position.shares} in "
            f"the book. Which figure is wrong is a person's question.",
        )

    # Share-weighted, because a position closed over several partial fills left at several prices
    # and the average of the PRICES would misreport whichever leg was larger.
    paid = sum((fill.price * fill.shares for fill in relevant), start=Decimal(0))
    return VenueExit(
        shares=int(sold),
        price=paid / sold,
        # The LAST fill: the position ended when the last share left, not when the first did.
        closed_on=max(fill.transaction_time.date() for fill in relevant),
        order_ids=tuple(sorted({fill.order_id for fill in relevant})),
        activity_ids=tuple(sorted(fill.activity_id for fill in relevant)),
    )
