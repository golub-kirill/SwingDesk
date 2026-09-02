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

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from swingdesk.contracts.broker import BrokerPosition, PositionSide
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
