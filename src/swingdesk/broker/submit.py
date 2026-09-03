"""Turning a sized decision into one submittable order. Pure, and it refuses more than it builds.

**No pipeline types reach this module and none may.** `swingdesk.broker` sits below `application`
in the layer chain (`ADR-0005`), so the caller maps whatever the run produced onto these arguments.
That is not ceremony: it means the rule *what may be submitted* is testable without constructing a
run, and it keeps the venue adapter from growing an opinion about strategy.

Everything here is `DR-027` §2 and §5 executed. The refusals are the substance - a builder that
always succeeds would push every one of these questions into the moment the order is already on
the wire.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_DOWN, ROUND_UP, Decimal

from swingdesk.broker.policy import PolicyRefused, WritePolicy
from swingdesk.contracts.broker import EntryOrder, ProtectiveOrder
from swingdesk.contracts.reference import Exchange
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import calendar as cal

#: What may appear in an instrument id that becomes part of a `client_order_id`. Deliberately does
#: NOT sanitise: replacing an unexpected character would let two different instruments derive the
#: same id, and a collision on an idempotency key is the one failure this key exists to prevent.
SAFE_ID = re.compile(r"^[A-Za-z0-9.\-]+$")


def trading_session(market: str, as_of: datetime) -> date:
    """The exchange session a decision taken at `as_of` belongs to. **Never a clock's date.**

    `DR-027` 5 keys idempotency on the session, so what counts as "the session" is load-bearing:
    two passes on one evening must derive the same key or the second submits the same entry again.

    **A clock's date does not do that, and a real order proved it.** The first probe ran at about
    19:57 New York time on 1 September and `datetime.now(UTC).date()` was already the **2nd**. The
    18:30 pass and the 19:30 retry `DR-015` explicitly provides for therefore straddle midnight UTC
    on every ordinary evening, and would have carried two different ids for one decision - which is
    the whole idempotency property, gone, in the one place it was supposed to hold.

    The exchange calendar has no such seam: both passes resolve to the session that closed at 16:00
    local, whatever the clock says elsewhere.
    """
    return cal.last_completed_session(Exchange(market), as_of).session_date


def client_order_id(
    session_date: date, instrument_id: str, write: WritePolicy
) -> str:
    """`<prefix>-<session>-<instrument>`, and the same inputs always give the same answer.

    **The SESSION DATE, never a run id and never a clock** (`DR-027` §5). `DR-015` provides for a
    retried evening pass; a retry carries a new run id, so an id derived from one would submit the
    same entry a second time. The decision belongs to a session, and the key says so.

    The venue rejects a duplicate, which puts the check with the party that knows what it accepted
    rather than with the local state that is what went wrong when a retry happens.
    """
    if not SAFE_ID.match(instrument_id):
        raise PolicyRefused(
            f"{instrument_id!r} carries characters that cannot go in a client order id. Rewriting "
            f"it would let two instruments derive one id, and a collision on an idempotency key is "
            f"exactly what that key exists to prevent."
        )
    derived = f"{write.client_order_id_prefix}-{session_date.isoformat()}-{instrument_id}"
    if len(derived) > write.max_client_order_id_length:
        raise PolicyRefused(
            f"the derived client order id is {len(derived)} characters, over the venue's "
            f"{write.max_client_order_id_length}. Truncating it would break idempotency silently."
        )
    return derived


def target_price(entry: Decimal, risk_per_share: Decimal, registry: ParameterRegistry) -> Decimal:
    """The take-profit leg, at `exit.target_r_multiple` R above the entry.

    **In R, not in percent and not in ATR**, because R is what the whole validation programme is
    denominated in and it is already volatility-normalised: `risk_per_share` is
    `entry - stop + costs`, frozen at entry (`RISK_SPEC` 2). A target in R is therefore comparable
    across instruments without a second convention, which `exit.percentage_target` would not be.

    **The form is the course's and the value is the owner's**, exactly as the stop multiple was.
    `M53-T0807`, `T0808` and `T0809` are "exit at 1R", "exit at 2R" and "exit at 3R" - three
    Definitions, no ruling between them.

    Raises `ParameterUnset` while the value is unset, which means no order at all: the venue
    requires both legs of a bracket, and inventing a target to satisfy a wire format would be
    authoring a threshold (`AGENTS.md` 8).
    """
    multiple, _ = registry.decimal_value("exit.target_r_multiple")
    if multiple <= 0:
        raise ValueError(
            f"exit.target_r_multiple is {multiple}; a target at or below the entry is an "
            f"instruction to sell at a loss on the way up"
        )
    return entry + multiple * risk_per_share


def to_tick(price: Decimal, write: WritePolicy, *, favouring: str) -> Decimal:
    """Snap a price to the venue's increment, always in the direction that cannot hurt. `DR-033`.

    **The tick is the venue's rule and the DIRECTION is ours**, and they are separate decisions.
    SEC Rule 612 forbids sub-penny pricing at or above a dollar; the venue enforces it and rejected
    the first four orders this system ever sent for `66.949997`, `106.059998`, `106.480003` and a
    take-profit carrying twenty-six decimal places. Nothing here chooses the increment - it is read
    from the committed policy beside the host.

    **`favouring` is `"cheaper"` or `"safer"`, and every leg gets the one that makes the trade no
    worse than the one the sizing computed:**

    - **the entry limit rounds DOWN**, so it can only ever fill at or BELOW the decision price.
      That is `DR-027` §3.1's argument made stronger rather than weakened.
    - **the stop rounds UP.** A stop nearer the entry risks LESS per share than planned, so the
      realised R can never exceed the one frozen at entry.
    - **the take-profit rounds DOWN**, asking less of the trade than planned.

    **Rounding is never allowed to move a price the flattering way**, which is the whole reason
    this takes a direction rather than calling `quantize` with a default. `ROUND_HALF_EVEN` on the
    limit would let an order fill a fraction above the price its `R` was computed against -
    permanently, on the one statistic the validation programme is measured in.
    """
    tick = write.tick_for(price)
    rounding = ROUND_DOWN if favouring == "cheaper" else ROUND_UP
    return (price / tick).quantize(Decimal(1), rounding=rounding) * tick


def entry_order(
    instrument_id: str,
    shares: int,
    limit_price: Decimal,
    stop_price: Decimal,
    target: Decimal,
    session_date: date,
    write: WritePolicy,
    market: str,
) -> EntryOrder:
    """One entry, or a refusal naming which of `DR-027` §2's rules it broke.

    `limit_price` is the price the SIZING used and is passed in rather than chosen here - the
    caller holds the `RiskSnapshot`, and a builder that picked its own price would be deciding the
    denominator of every `R` the resulting position reports.
    """
    exchange = cal.exchange_for(instrument_id)
    if exchange is not Exchange(market):
        # Not a gap and not a retry: this venue cannot hold the instrument at all. AGENTS 3 keeps
        # USA and Canada apart, and sending a `.TO` name to a US venue would either be rejected or,
        # worse, match some unrelated US symbol.
        raise PolicyRefused(
            f"{instrument_id} is {exchange.value} and this venue serves {market}. USA and Canada "
            f"are never merged."
        )

    if shares <= 0:
        raise PolicyRefused(
            f"{instrument_id}: the sizing produced {shares} shares, so there is nothing to submit. "
            f"A zero-share order is a refusal that reached the wire."
        )

    # Snapped to the venue's increment, each leg toward the side that cannot hurt (`DR-033`). Done
    # HERE rather than at the wire so the refusals below judge the prices that will actually be
    # sent: an order whose legs collapse into one another once rounded is not submittable, and
    # finding that out from a 422 is finding it out in the most expensive place.
    limit_price = to_tick(limit_price, write, favouring="cheaper")
    stop_price = to_tick(stop_price, write, favouring="safer")
    target = to_tick(target, write, favouring="cheaper")

    if stop_price >= limit_price:
        raise PolicyRefused(
            f"{instrument_id}: rounded to the venue's tick the stop is {stop_price} and the limit "
            f"is {limit_price}, so the stop is no longer below the entry. The R denominator this "
            f"trade would report does not exist."
        )
    if target <= limit_price:
        raise PolicyRefused(
            f"{instrument_id}: rounded to the venue's tick the take-profit is {target}, at or "
            f"below the {limit_price} entry. That is an instruction to sell at a loss on the way "
            f"up, and one tick of rounding is not a reason to send it."
        )

    return EntryOrder(
        client_order_id=client_order_id(session_date, instrument_id, write),
        session_date=session_date,
        instrument_id=instrument_id,
        # The venue's symbol. For a US listing this system's id IS the ticker; the `.TO` case is
        # refused above rather than translated, because a translation here would be the one place
        # a Canadian name could reach a US venue.
        symbol=instrument_id,
        shares=shares,
        limit_price=limit_price,
        stop_price=stop_price,
        target_price=target,
    )


def protective_order(
    instrument_id: str,
    shares: int,
    stop_price: Decimal,
    target: Decimal,
    session_date: date,
    write: WritePolicy,
    market: str,
) -> ProtectiveOrder:
    """One `oco` for a position already held, or a refusal naming what stopped it. `DR-037`.

    **The same refusals `entry_order` makes, for the same reasons**, because a protective order that
    could not be built is a position that stays naked and the caller has to be told which. What it
    does NOT repeat is the entry's price: there is no limit to chase here, the position is already
    open, and the two legs are the book's own stop and the target that stop implies.

    **Snapped by `DR-033`'s rule and in its directions.** The stop rounds UP - nearer the entry,
    risking less per share than the book planned - and the target rounds DOWN, asking less of the
    trade. Both are the conservative side, which is the only side rounding may take on a price this
    system will be measured by.
    """
    exchange = cal.exchange_for(instrument_id)
    if exchange is not Exchange(market):
        raise PolicyRefused(
            f"{instrument_id} is {exchange.value} and this venue serves {market}. A position this "
            f"venue cannot hold is one it cannot be asked to protect either."
        )
    if shares <= 0:
        raise PolicyRefused(
            f"{instrument_id}: {shares} shares to protect, so there is nothing to place an order "
            f"against."
        )

    stop_price = to_tick(stop_price, write, favouring="safer")
    target = to_tick(target, write, favouring="cheaper")

    return ProtectiveOrder(
        client_order_id=protective_order_id(session_date, instrument_id, write),
        session_date=session_date,
        instrument_id=instrument_id,
        symbol=instrument_id,
        shares=shares,
        stop_price=stop_price,
        target_price=target,
    )


def protective_order_id(
    session_date: date, instrument_id: str, write: WritePolicy
) -> str:
    """`<protect prefix>-<session>-<instrument>`, and never the entry's id.

    The entry for this instrument on this session already carries
    `<prefix>-<session>-<instrument>`, and the venue rejects a duplicate - which is `DR-027` §5
    working, not an obstacle. A distinct prefix keeps that property for the protective order too:
    one per instrument per session, and a second attempt refused by the party that knows.
    """
    if not SAFE_ID.match(instrument_id):
        raise PolicyRefused(
            f"{instrument_id!r} carries characters that cannot go in a client order id."
        )
    derived = f"{write.protect_client_order_id_prefix}-{session_date.isoformat()}-{instrument_id}"
    if len(derived) > write.max_client_order_id_length:
        raise PolicyRefused(
            f"the derived protective order id is {len(derived)} characters, over the venue's "
            f"{write.max_client_order_id_length}."
        )
    return derived
