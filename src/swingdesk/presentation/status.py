"""`swingdesk status` - one screen for the operator. It reads only.

The owner's operations review of 2026-09-12, medium #4: the state of the system was spread over
`broker`, `pending` and the Task Scheduler, and nothing answered the one question - *is anything
wrong tonight?* - on one screen. This module turns values the command has already read into that
screen. It performs no I/O, so every branch is testable without a venue or a scheduler.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from swingdesk.broker import MISMATCH_CODE, reconcile, resting_stops, unprotected
from swingdesk.broker.armed import Arming
from swingdesk.contracts.broker import BrokerAccount, BrokerPosition, PlacedOrder
from swingdesk.contracts.position import Position
from swingdesk.platform.schedule import TaskReading
from swingdesk.presentation.pending_view import PendingSplit

OK = "ok"
NO_STOP = "NO STOP"
WRONG_PRICE = "WRONG PRICE"
UNKNOWN = "UNKNOWN"
OUT_OF_SCOPE = "OUT OF SCOPE"


@dataclass(frozen=True)
class PositionLine:
    instrument_id: str
    shares: int
    entry: Decimal
    book_stop: Decimal
    venue_stop: Decimal | None
    protection: str
    proposal: str | None


@dataclass(frozen=True)
class StatusView:
    at: datetime
    switch: Arming
    schedule: tuple[TaskReading, ...]
    account: BrokerAccount | None
    venue_error: str | None
    positions: tuple[PositionLine, ...]
    divergences: tuple[str, ...]
    waiting: int
    superseded: int
    expired: int
    unjudgeable: int

    @property
    def findings(self) -> int:
        return len(self.divergences) + sum(
            1 for line in self.positions if line.protection in (NO_STOP, WRONG_PRICE))

    @property
    def exit_code(self) -> int:
        """`broker`'s three answers. Unavailable is checked FIRST: a book that could not be compared
        is not in order, and a script reading 0 would be told it was."""
        if self.venue_error is not None:
            return 2
        return 3 if self.findings else 0


def _newest_proposals(split: PendingSplit) -> dict[str, str]:
    """The newest answerable proposal per position, as one short phrase."""
    newest: dict[str, tuple[int, str]] = {}
    for item in (*split.waiting, *split.expired):
        action = item.action
        phrase = f"#{item.sequence} {action.kind.value.upper()}"
        if action.new_stop is not None:
            phrase += f" -> {action.new_stop}"
        seen = newest.get(action.position_id)
        if seen is None or item.sequence > seen[0]:
            newest[action.position_id] = (item.sequence, phrase)
    return {position_id: phrase for position_id, (_, phrase) in newest.items()}


def build(
    *,
    at: datetime,
    switch: Arming,
    schedule: Sequence[TaskReading],
    account: BrokerAccount | None,
    venue_error: str | None,
    book: Sequence[Position],
    held: Sequence[BrokerPosition],
    live_orders: Sequence[PlacedOrder],
    split: PendingSplit,
    market: str,
    label: str,
    tick_for: Callable[[Decimal], Decimal | None],
) -> StatusView:
    proposals = _newest_proposals(split)
    in_force = resting_stops(live_orders)
    naked: dict[str, bool] = {}
    divergences: tuple[str, ...] = ()
    out_of_scope: set[str] = set()
    if venue_error is None:
        naked = {finding.instrument_id: finding.venue_stop is None
                 for finding in unprotected(book, live_orders, market, tick_for=tick_for)}
        report = reconcile(book, held, venue=label, market=market)
        divergences = tuple(f"{d.reason} {d.instrument_id}" for d in report.divergences)
        out_of_scope = set(report.out_of_scope)

    lines: list[PositionLine] = []
    for position in book:
        if venue_error is not None:
            protection = UNKNOWN
        elif position.instrument_id in out_of_scope:
            protection = OUT_OF_SCOPE
        elif position.instrument_id in naked:
            protection = NO_STOP if naked[position.instrument_id] else WRONG_PRICE
        else:
            protection = OK
        lines.append(PositionLine(
            instrument_id=position.instrument_id, shares=position.shares,
            entry=position.entry_price, book_stop=position.current_stop,
            venue_stop=in_force.get(position.instrument_id), protection=protection,
            proposal=proposals.get(position.position_id)))

    return StatusView(
        at=at, switch=switch, schedule=tuple(schedule), account=account,
        venue_error=venue_error, positions=tuple(lines), divergences=divergences,
        waiting=len(split.waiting), superseded=len(split.superseded),
        expired=len(split.expired), unjudgeable=len(split.unjudgeable))


def render(view: StatusView) -> list[str]:
    out = [f"SwingDesk status   {view.at:%Y-%m-%d %H:%M %Z}", ""]
    word = "ARMED" if view.switch.armed else "STOPPED"
    out.append(f"  switch     {word} - {view.switch.reason}")
    if not view.schedule:
        out.append("  schedule   UNAVAILABLE - no task registered on this machine")
    for index, task in enumerate(view.schedule):
        lead = "  schedule   " if index == 0 else "             "
        out.append(f"{lead}{task.task:<22} next {task.next_run} · last {task.last_run} "
                   f"{task.judgement} ({task.phrase})")
    if view.account is not None:
        out.append(f"  account    equity {view.account.equity} · cash {view.account.cash} · "
                   f"{view.account.status}")
    else:
        out.append(f"  account    UNAVAILABLE - {view.venue_error}")

    out += ["", f"positions ({len(view.positions)} open)"]
    if not view.positions:
        out.append("  (none)")
    for line in view.positions:
        venue = "-" if line.venue_stop is None else str(line.venue_stop)
        row = (f"  {line.instrument_id:<8} {line.shares:>6} sh  entry {line.entry}  "
               f"stop {line.book_stop}  venue {venue:<10} {line.protection}")
        if line.proposal:
            row += f"   {line.proposal}"
        out.append(row)
    for divergence in view.divergences:
        out.append(f"  {MISMATCH_CODE}  {divergence}")

    unknown = f" · {view.unjudgeable} AGE UNKNOWN" if view.unjudgeable else ""
    out += ["", f"pending    {view.waiting} awaiting · {view.superseded} superseded · "
                f"{view.expired} expired{unknown}   -> swingdesk pending"]
    if view.exit_code == 2:
        out.append("verdict    UNAVAILABLE - the venue could not be read; that is not agreement")
    elif view.exit_code == 3:
        out.append(f"verdict    {MISMATCH_CODE} - {view.findings} finding(s); new entries pause "
                   f"until resolved (DR-035, DR-036) - swingdesk broker has the detail")
    else:
        out.append("verdict    OK - the venue and the book agree and every stop is standing")
    return out
