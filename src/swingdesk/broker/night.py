"""`CARD-002`'s paper ledger, and the venue as `CARD-001` sees it once two cards share it. `DR-054`.

**Why this module exists.** Every guard `CARD-001` carries asks the venue *what do you hold* and
treats anything its own book does not carry as a defect - and its submission path stops on that
BEFORE it restores a protective stop. Correct for one card. With `CARD-002` holding two funds every
night, the first paper night would have stopped `CARD-001` protecting its own positions, every
evening, for as long as both ran. Found while planning `DR-054`, not by a run.

**The rule: `CARD-001` sees the venue minus exactly what this ledger accounts for** (`DR-054` §3):

* an order is `CARD-002`'s if its client id is in a `sent` row - never a prefix, never a symbol,
  for the reason `reconcile.ours` gives: a prefix adopts whatever a person types with the right
  first word, and a symbol would hide a person's own order in the same fund;
* a fill is `CARD-002`'s if its venue order id is in an `answered` row;
* a holding is set aside by QUANTITY - what this card's buys filled less what its sells filled, on
  the nights not yet reconciled as closed. Anything beyond stays in view and is still a divergence.

**The ledger is append-only JSON lines**, `data/card002/paper.jsonl`, apart from the real
sessions' `executions.jsonl` so simulated paper fills can never reach the one number the real
sessions exist to measure (`DR-054` §6). A row is written BEFORE the order it names is sent.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from swingdesk.contracts.broker import BrokerFill, BrokerPosition, PlacedOrder, Side

#: Under the data directory. The real sessions' fills live beside it in `executions.jsonl`.
LEDGER = Path("card002") / "paper.jsonl"

#: The reason `CARD-001` journals against every candidate once this card has started. `DR-054` §4.
RETIRED = (
    "DR-054: CARD-001 takes no new entries once CARD-002 has placed its first paper order - the "
    "two cannot share the paper account's capital. Its open positions keep their protection and "
    "leave by their own rules"
)


class LedgerUnreadable(Exception):
    """The ledger exists and cannot be read. Never an empty ledger: that would set nothing aside
    AND let `CARD-001` resume entries, and only the first of those is the safe side."""


@dataclass(frozen=True)
class Sent:
    """An order this card is about to put on the wire - written before it is."""

    session: date
    fund: str
    side: Side
    shares: int
    client_order_id: str


@dataclass(frozen=True)
class Answered:
    """What the venue said. `order_id` is empty when the venue has never seen the order."""

    client_order_id: str
    order_id: str
    status: str


@dataclass(frozen=True)
class Ledger:
    """Every row, in the order written. Built by `read`, never edited."""

    sent: tuple[Sent, ...] = ()
    answered: Mapping[str, Answered] = field(default_factory=dict)
    closed: frozenset[tuple[date, str]] = frozenset()

    @property
    def started(self) -> bool:
        """Whether this card has ever put an order on the wire. `DR-054` §4's switch."""
        return bool(self.sent)

    @property
    def client_ids(self) -> frozenset[str]:
        return frozenset(row.client_order_id for row in self.sent)

    @property
    def order_ids(self) -> frozenset[str]:
        return frozenset(a.order_id for a in self.answered.values() if a.order_id)

    def owns(self, order: PlacedOrder) -> bool:
        """This card's order, by the id it journalled - or a leg of one, `DR-053`'s rule."""
        ids = self.client_ids
        return (order.client_order_id in ids
                or (bool(order.parent_client_order_id) and order.parent_client_order_id in ids))

    def orders(self, session: date, fund: str, side: Side) -> tuple[Sent, ...]:
        """Every attempt of this kind for one night, in the order sent.

        A buy is sent once - a missed buy is a missed night. A SELL may be sent again under a new
        id when the venue refused the last one, because that sell is the night's only protection
        and the venue rejects a repeated id even for an order it refused.
        """
        return tuple(row for row in self.sent
                     if row.session == session and row.fund == fund and row.side is side)

    def open_nights(self) -> tuple[tuple[date, str], ...]:
        """Nights with a buy sent and no reconciliation yet, oldest first."""
        return tuple(sorted({
            (row.session, row.fund) for row in self.sent
            if row.side is Side.BUY and (row.session, row.fund) not in self.closed
        }))

    def unanswered(self) -> tuple[Sent, ...]:
        """Orders written as sent whose answer never reached the ledger. `DR-054` §3.4."""
        return tuple(row for row in self.sent if row.client_order_id not in self.answered)


def ledger_path(data: Path) -> Path:
    return data / LEDGER


def read(data: Path) -> Ledger:
    """The ledger under `data`, or an empty one when the card has never run.

    Absent is an answer - nothing was ever sent. Present and unparseable is not, and raises.
    """
    path = ledger_path(data)
    if not path.exists():
        return Ledger()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise LedgerUnreadable(f"{path}: {error}") from error

    sent: list[Sent] = []
    answered: dict[str, Answered] = {}
    closed: set[tuple[date, str]] = set()
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            kind = row["kind"]
            if kind == "sent":
                sent.append(Sent(
                    session=date.fromisoformat(row["session"]), fund=str(row["fund"]),
                    side=Side(row["side"]), shares=int(row["shares"]),
                    client_order_id=str(row["client_order_id"]),
                ))
            elif kind == "answered":
                # The LAST answer wins: a heal that finds the order later overwrites an earlier
                # "the venue never saw it", which is the order in which the facts arrived.
                answered[str(row["client_order_id"])] = Answered(
                    client_order_id=str(row["client_order_id"]),
                    order_id=str(row.get("order_id") or ""), status=str(row.get("status") or ""),
                )
            elif kind == "night":
                closed.add((date.fromisoformat(row["session"]), str(row["fund"])))
        except (ValueError, KeyError, TypeError) as error:
            raise LedgerUnreadable(f"{path}:{number}: {error}") from error
    return Ledger(sent=tuple(sent), answered=answered, closed=frozenset(closed))


def append(data: Path, row: Mapping[str, Any]) -> None:
    """One row, flushed to disk before returning - a `sent` row must exist before its order does."""
    path = ledger_path(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class CardView:
    """The venue as `CARD-001` sees it: everything, less what `CARD-002`'s ledger accounts for.

    Every other attribute - `submit`, `protect`, `replace_stop`, `account`, `guards` - passes
    through untouched, so wrapping a client changes what `CARD-001` READS and nothing it can DO.

    `ledger` is `None` when the ledger could not be read: then nothing is set aside, the two funds
    read as divergences and `CARD-001` stops - the behaviour before `DR-054`, and the loud one -
    and `started` answers yes, so an unreadable ledger can never let `CARD-001` resume entries.
    """

    def __init__(self, client: Any, ledger: Ledger | None, unreadable: str = "") -> None:
        self._client = client
        self._ledger = ledger
        self.unreadable = unreadable

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    @property
    def card002_started(self) -> bool:
        return self._ledger is None or self._ledger.started

    def open_orders(self, observed_at: datetime) -> tuple[PlacedOrder, ...]:
        live = self._client.open_orders(observed_at)
        if self._ledger is None:
            return tuple(live)
        return tuple(order for order in live if not self._ledger.owns(order))

    def fills(self, observed_at: datetime, after: datetime | None = None) -> tuple[BrokerFill, ...]:
        executed = self._client.fills(observed_at, after=after)
        if self._ledger is None:
            return tuple(executed)
        ours = self._ledger.order_ids
        return tuple(fill for fill in executed if fill.order_id not in ours)

    def positions(self, observed_at: datetime) -> tuple[BrokerPosition, ...]:
        held = self._client.positions(observed_at)
        if self._ledger is None:
            return tuple(held)
        aside = accountable(self._ledger, self._client, observed_at)
        seen: list[BrokerPosition] = []
        for holding in held:
            shares = aside.get(holding.symbol, Decimal(0))
            if shares <= 0:
                seen.append(holding)
                continue
            rest = holding.shares - shares
            if rest > 0:
                # What is left is not this card's, and whose it is nobody here knows - so its
                # money fields are not scaled into something that looks measured. The entry price
                # is the venue's blend and will disagree with any book, which is the point.
                seen.append(holding.model_copy(update={
                    "shares": rest, "market_value": None, "cost_basis": None,
                    "unrealized_pl": None,
                }))
        return tuple(seen)


def accountable(ledger: Ledger, client: Any, observed_at: datetime) -> dict[str, Decimal]:
    """Shares this card holds at the venue, by fund: its buys' fills less its sells', on every
    night not yet reconciled as closed. `DR-054` §3.3.

    Asked of each ORDER, because a filled order is not in `open_orders` and a fill feed would
    have to be paged back to the night it started. A night whose buy was never answered
    contributes nothing: its fills cannot be attributed, so they stay in view as a divergence.
    """
    aside: dict[str, Decimal] = {}
    for session, fund in ledger.open_nights():
        net = Decimal(0)
        for side, sign in ((Side.BUY, 1), (Side.SELL, -1)):
            for sent in ledger.orders(session, fund, side):
                answer = ledger.answered.get(sent.client_order_id)
                if answer is None or not answer.order_id:
                    continue
                net += sign * client.order(answer.order_id, observed_at).filled_shares
        if net > 0:
            aside[fund] = aside.get(fund, Decimal(0)) + net
    return aside


def view(client: Any, data: Path) -> CardView:
    """The one way `cli.py` reads the venue once two cards share it."""
    try:
        return CardView(client, read(data))
    except LedgerUnreadable as unreadable:
        return CardView(client, None, unreadable=str(unreadable))


def retirement(client: Any) -> str | None:
    """Why `CARD-001` may add nothing, or `None` while `CARD-002` has not started. `DR-054` §4.

    A client that was NOT read through the view answers with a reason too: then nothing says
    whether the other card holds the account, and adding to an unknown book is what every guard
    in this package exists to refuse.
    """
    if not isinstance(client, CardView):
        return f"{RETIRED}. The venue was not read through DR-054's view, so nothing says whether " \
               f"CARD-002 holds the account"
    if client.unreadable:
        return f"{RETIRED}. The ledger could not be read ({client.unreadable}), so this card " \
               f"counts CARD-002 as started"
    if client.card002_started:
        return RETIRED
    return None
