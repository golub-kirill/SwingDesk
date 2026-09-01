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
from datetime import date
from decimal import Decimal

from swingdesk.broker.policy import PolicyRefused, WritePolicy
from swingdesk.contracts.broker import EntryOrder
from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal

#: What may appear in an instrument id that becomes part of a `client_order_id`. Deliberately does
#: NOT sanitise: replacing an unexpected character would let two different instruments derive the
#: same id, and a collision on an idempotency key is the one failure this key exists to prevent.
SAFE_ID = re.compile(r"^[A-Za-z0-9.\-]+$")


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


def entry_order(
    instrument_id: str,
    shares: int,
    limit_price: Decimal,
    stop_price: Decimal,
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
    )
