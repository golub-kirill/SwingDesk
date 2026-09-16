"""`swingdesk status` - one screen for the operator. It reads only.

The owner's operations review of 2026-09-12, medium #4: the state of the system was spread over
`broker`, `pending` and the Task Scheduler, and nothing answered the one question - *is anything
wrong tonight?* - on one screen. This module turns values the command has already read into that
screen. It performs no I/O, so every branch is testable without a venue or a scheduler.

**And when something is wrong at the venue, the screen says what to type.** On 2026-09-14 four open
positions stood with no stop at the venue and the fix was four commands a person worked out by
hand: the book's stop, rounded UP to the venue's tick (`DR-033`), for the book's share count, `gtc`.
The system still sends none of them - it has no verb that cancels or amends an order, and a stop
move is `D6`'s - but it can print exactly what the operator would otherwise compute, from numbers
it has already read, in the shell the operator actually uses.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from swingdesk.broker import MISMATCH_CODE, reconcile, resting_stops, unprotected
from swingdesk.broker.armed import Arming
from swingdesk.broker.reconcile import PROTECTIVE_TYPES, withdrawn_stops
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
class Handover:
    """What a printed command needs, and nothing more.

    **The NAMES of the key variables, never their values** - the operator's shell expands them
    (`cmd.exe`: `%NAME%`), so nothing secret is ever on the screen or in a scrollback. The stop is
    rounded by `stop_at_tick`, which the command builds from the committed policy's tick and
    `DR-033`'s direction for a stop, UP: a stop nearer the entry risks less than the book, never more.
    """

    orders_url: str
    key_env: str
    secret_env: str
    stop_at_tick: Callable[[Decimal], Decimal]


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
    #: What to type at the venue, in order. Empty when nothing is wrong or no handover was given.
    commands: tuple[str, ...] = ()
    #: Findings that need no command, each saying why.
    venue_notes: tuple[str, ...] = ()

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


def _newest_proposals(split: PendingSplit) -> dict[str, tuple[str, Decimal | None]]:
    """The newest answerable proposal per position: a short phrase, and the stop it asks for."""
    newest: dict[str, tuple[int, str, Decimal | None]] = {}
    for item in (*split.waiting, *split.expired):
        action = item.action
        phrase = f"#{item.sequence} {action.kind.value.upper()}"
        if action.new_stop is not None:
            phrase += f" -> {action.new_stop}"
        seen = newest.get(action.position_id)
        if seen is None or item.sequence > seen[0]:
            newest[action.position_id] = (item.sequence, phrase, action.new_stop)
    return {position_id: (phrase, asked)
            for position_id, (_, phrase, asked) in newest.items()}


def _headers(handover: Handover) -> str:
    return (f'-H "APCA-API-KEY-ID: %{handover.key_env}%" '
            f'-H "APCA-API-SECRET-KEY: %{handover.secret_env}%"')


def _place(line: PositionLine, handover: Handover) -> str:
    """A `gtc` sell stop for the book's shares at the book's stop, rounded to the venue's tick."""
    body = json.dumps({"symbol": line.instrument_id, "qty": str(line.shares), "side": "sell",
                       "type": "stop", "stop_price": str(handover.stop_at_tick(line.book_stop)),
                       "time_in_force": "gtc"}, separators=(",", ":"))
    quoted = body.replace('"', '\\"')
    return (f"curl -s -X POST {handover.orders_url} {_headers(handover)} "
            f'-H "Content-Type: application/json" -d "{quoted}"')


def _cancel(order_id: str, handover: Handover) -> str:
    return f"curl -s -X DELETE {handover.orders_url}/{order_id} {_headers(handover)}"


def _handover(lines: Sequence[PositionLine], live_orders: Sequence[PlacedOrder],
              handover: Handover) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The commands that would make the venue hold the book's stop, and the findings that need none.

    * **No stop at all** - place one. That is `DR-037`'s restoration, which the evening pass also
      does when it runs armed; the command is for the operator who cannot wait for it.
    * **A stop LOOSER than the book's** - a move approved in the book and never sent. Cancel what is
      resting for the symbol, then place the book's. Cancel first: the venue reserves the shares for
      the old order until the cancel lands, and a stop placed before it is refused for
      `insufficient qty` (measured 2026-09-12, over a weekend when the cancel waited for Monday).
    * **A stop TIGHTER than the book's** - nothing to send. `sync-fills` adopts the venue's number
      into the book (`DR-041`), and replacing it would widen a protection somebody raised.
    """
    commands: list[str] = []
    notes: list[str] = []
    # `DR-044`: a stop whose cancel is queued protects nothing AND still holds the shares, so the
    # screen must not print a place command that the venue would refuse for `insufficient qty`.
    queued = withdrawn_stops(live_orders)
    for line in lines:
        if line.protection == NO_STOP:
            going = queued.get(line.instrument_id)
            if going is not None:
                notes.append(
                    f"{line.instrument_id}: the stop at {going} is being withdrawn - its cancel is "
                    f"queued at the venue and it holds the {line.shares} shares until that lands. A "
                    f"stop placed now is refused for insufficient qty; the next armed pass restores "
                    f"this system's own (DR-044)")
                continue
        elif line.protection == WRONG_PRICE and line.venue_stop is not None:
            if line.venue_stop > line.book_stop:
                notes.append(f"{line.instrument_id}: the venue's stop {line.venue_stop} is tighter than "
                             f"the book's {line.book_stop}; the next sync-fills adopts it (DR-041) - "
                             f"nothing to send")
                continue
            commands.extend(_cancel(order.order_id, handover) for order in live_orders
                            if order.symbol == line.instrument_id
                            and order.order_type in PROTECTIVE_TYPES and order.stop_price is not None)
        else:
            continue
        # A resting SELL that is not a stop - a take-profit - holds the same shares, and the venue
        # refuses the stop while it rests. It may be the one the operator wants, so it is named and
        # left alone rather than cancelled on the screen's say-so.
        commands.append(_place(line, handover))
        notes.extend(f"{line.instrument_id}: order {order.order_id} ({order.order_type}) holds the "
                     f"shares - the stop above is refused for insufficient qty until it is cancelled"
                     for order in live_orders
                     if order.symbol == line.instrument_id and order.side == "sell"
                     and order.order_type not in PROTECTIVE_TYPES)
    return tuple(commands), tuple(notes)


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
    handover: Handover | None = None,
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
        proposal = None
        found = proposals.get(position.position_id)
        if found is not None:
            phrase, asked = found
            if asked is not None and asked <= position.current_stop:
                # Asked before the book's stop rose to where it is: approving would not raise it,
                # and `respond` refuses an approval that would lower it.
                phrase += " (obsolete - at or below the book stop)"
            proposal = phrase
        lines.append(PositionLine(
            instrument_id=position.instrument_id, shares=position.shares,
            entry=position.entry_price, book_stop=position.current_stop,
            venue_stop=in_force.get(position.instrument_id), protection=protection,
            proposal=proposal))

    # An unread venue leaves every line UNKNOWN, so there is nothing to print for it.
    commands: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    if handover is not None:
        commands, notes = _handover(lines, live_orders, handover)

    return StatusView(
        at=at, switch=switch, schedule=tuple(schedule), account=account,
        venue_error=venue_error, positions=tuple(lines), divergences=divergences,
        waiting=len(split.waiting), superseded=len(split.superseded),
        expired=len(split.expired), unjudgeable=len(split.unjudgeable),
        commands=commands, venue_notes=notes)


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

    if view.commands or view.venue_notes:
        out += ["", "at the venue - the system sends none of these; run them in cmd.exe, in order"]
        if any(" -X DELETE " in command for command in view.commands):
            out.append("  a cancel must show as gone in `swingdesk status` before its stop is placed:")
            out.append("  the venue holds the shares for the old order until the cancel lands")
        out += [f"  {command}" for command in view.commands]
        out += [f"  {note}" for note in view.venue_notes]

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
