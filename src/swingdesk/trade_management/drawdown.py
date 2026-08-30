"""The drawdown `k.drawdown_pause` actually means, and could not previously be asked for.

`k.drawdown_pause` has been ratified since v1.0.0 with scope `live`, and **nothing computed its
input**. `validation.max_allowable_drawdown` is owner-set at 20 percent of equity and its `read_by`
was `none`: a ratified kill criterion whose measurement did not exist, which is the inert-gate
failure `REQ-VALIDATION-001` names from the other direction.

**What the word means, ruled by the owner 2026-08-30** (`criteria.yml` amendment v1.1.2). The
trigger says *"Realised drawdown"* and the natural reading of "realised" - closed trades only -
inverts the requirement it comes from: an account can fall through the limit with every position
still open and never fire, because nothing has been realised. M69 wants the limit to reduce size and
pause *before* the loss is locked in. So it is the drawdown that actually **occurred**:

> **Peak-to-trough drawdown of account equity, including open positions marked to market.**

Peak-relative, because `GLOSSARY.md` transcribes the course's `Drawdown` as a decline from the
previous peak. Baseline `account.equity`.

**This module MEASURES and prescribes nothing.** `k.drawdown_pause`'s action names the risk-off
ladder, `risk.risk_off_ladder` is `unset`, and writing that ladder is the owner's. Nothing in the
decision path calls this: making a kill switch measurable is not the same as making it automatic,
and doing both in one change would have moved decision output for a measurement whose first honest
answer is 0.00%.

Pure - no store, no clock, no registry. Positions, fills and the mark source are passed in, the same
arrangement `portfolio` uses and for the same reason: the one place that reads a store stays a
caller, so a study can pin the inputs it ran on.

**A missing mark is `unavailable`, not zero.** An open position nobody could price contributes no
unrealised loss if you treat it as zero, which makes the drawdown look SMALLER than it is - the one
direction a kill switch must never be wrong in. `AGENTS.md` §12: unavailable is not fail, and it is
not pass either.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from swingdesk.contracts.position import Fill, Position

#: Price of one instrument on one session, or None when the caller cannot supply it.
MarkFor = Callable[[str, date], Decimal | None]


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """Account equity on one session, and the two halves it is made of."""

    #: `None` when nothing has ever traded. An account with no positions has a flat equity curve
    #: and no session to hang it on, and naming one would be a point-in-time claim about a day
    #: nothing happened - `REQ-DATA-001`, which is why there is no epoch constant here.
    session: date | None
    realised: Decimal
    unrealised: Decimal
    equity: Decimal


@dataclass(frozen=True, slots=True)
class Drawdown:
    """The peak-to-trough decline of the equity curve, and the evidence for it."""

    baseline: Decimal
    peak: Decimal
    trough: Decimal
    #: Currency amount from the peak down to the lowest point reached AFTER that peak.
    amount: Decimal
    #: `amount / peak`, the peak-relative fraction GLOSSARY.md's definition asks for.
    fraction: Decimal
    curve: tuple[EquityPoint, ...]

    @property
    def percent(self) -> Decimal:
        """The number `k.drawdown_pause` compares against `validation.max_allowable_drawdown`."""
        return (self.fraction * 100).quantize(Decimal("0.01"))

    def breaches(self, max_allowable_percent: Decimal) -> bool:
        """Whether the criterion's trigger is met. Says nothing about what to do about it."""
        return self.percent > max_allowable_percent


@dataclass(frozen=True, slots=True)
class Unavailable:
    """The measurement could not be made. Never a number, and never silently a zero."""

    reason: str
    #: The positions that could not be priced, so the caller can say which and on what session.
    unpriced: tuple[tuple[str, date], ...] = ()


def _exit_fills(
    actions_by_position: Mapping[str, Mapping[int, str]],
    fills: Sequence[Fill],
) -> list[Fill]:
    """Fills that settle an exit or a partial exit - the ones that realise a gain or a loss.

    A fill settles an approved action by `sequence`, and the action's kind is what says whether
    shares left the position. A fill against a `move_stop` moves no shares and realises nothing;
    counting it would book a P&L for an action that never transacted.
    """
    realising = {"exit_now", "partial_exit"}
    return [
        fill for fill in fills
        if actions_by_position.get(fill.position_id, {}).get(fill.sequence) in realising
    ]


def curve(
    positions: Sequence[Position],
    fills_by_position: Mapping[str, Sequence[Fill]],
    actions_by_position: Mapping[str, Mapping[int, str]],
    baseline: Decimal,
    sessions: Sequence[date],
    mark_for: MarkFor,
) -> tuple[EquityPoint, ...] | Unavailable:
    """Account equity on each of `sessions`, cheapest-correct rather than clever.

    `positions` is the latest version of each position, which is what the store's `open_as_of`
    hands back. Realised P&L accumulates from exit fills on or before the session; unrealised marks
    whatever remains open on that session.

    An empty `sessions` is not an error and not an empty answer - the caller gets one point at the
    baseline, because an account that has never traded has an equity curve and it is flat. That is
    the case that runs today, and returning nothing would have made the criterion unevaluable for a
    second reason after the first was fixed.
    """
    if not sessions:
        return (EquityPoint(None, Decimal(0), Decimal(0), baseline),)

    by_id = {position.position_id: position for position in positions}
    points: list[EquityPoint] = []
    unpriced: list[tuple[str, date]] = []

    for session in sorted(sessions):
        realised = Decimal(0)
        unrealised = Decimal(0)

        for position_id, position in sorted(by_id.items()):
            fills = list(fills_by_position.get(position_id, ()))
            exits = [
                fill for fill in _exit_fills(actions_by_position, fills)
                if fill.filled_on <= session
            ]
            gone = sum(fill.shares for fill in exits)
            for fill in exits:
                realised += (
                    (fill.price - position.entry_price) * fill.shares
                    - position.initial_costs_per_share * fill.shares
                    - fill.commission
                )

            if position.opened_on > session:
                continue
            if position.closed_on is not None and position.closed_on <= session:
                continue

            remaining = position.shares - gone
            if remaining <= 0:
                continue

            mark = mark_for(position.instrument_id, session)
            if mark is None:
                unpriced.append((position_id, session))
                continue
            unrealised += (
                (mark - position.entry_price) * remaining
                - position.initial_costs_per_share * remaining
            )

        points.append(EquityPoint(session, realised, unrealised, baseline + realised + unrealised))

    if unpriced:
        return Unavailable(
            reason=f"{len(unpriced)} open position-session(s) could not be marked to market; a "
                   f"drawdown computed without them would be smaller than the real one",
            unpriced=tuple(unpriced),
        )
    return tuple(points)


def peak_to_trough(points: Sequence[EquityPoint]) -> Drawdown | Unavailable:
    """The largest peak-relative decline anywhere in the curve.

    Peak-to-trough, not first-to-last and not peak-to-final: the criterion asks how far equity fell
    from a high-water mark, and an account that fell 30% and recovered has still been through a 30%
    drawdown. That is the whole reason the course defines it against the previous peak.
    """
    if not points:
        return Unavailable(reason="an empty curve has no peak and no trough")

    peak = points[0].equity
    worst_peak = peak
    worst_trough = peak
    worst = Decimal(0)

    for point in points:
        if point.equity > peak:
            peak = point.equity
        decline = peak - point.equity
        if decline > worst:
            worst = decline
            worst_peak = peak
            worst_trough = point.equity

    # Peak-relative, and a non-positive peak has no meaningful percentage. A wiped-out account is
    # not a division problem to be swallowed - the caller is told the measurement stopped.
    if worst_peak <= 0:
        return Unavailable(reason=f"the running peak is {worst_peak}, so a percentage of it is not "
                                  f"a drawdown; the account has no equity to draw down from")

    return Drawdown(
        baseline=points[0].equity,
        peak=worst_peak,
        trough=worst_trough,
        amount=worst,
        fraction=worst / worst_peak,
        curve=tuple(points),
    )


def measure(
    positions: Sequence[Position],
    fills_by_position: Mapping[str, Sequence[Fill]],
    actions_by_position: Mapping[str, Mapping[int, str]],
    baseline: Decimal,
    sessions: Sequence[date],
    mark_for: MarkFor,
) -> Drawdown | Unavailable:
    """The whole measurement in one call: build the curve, then read its worst decline."""
    built = curve(
        positions, fills_by_position, actions_by_position, baseline, sessions, mark_for
    )
    if isinstance(built, Unavailable):
        return built
    return peak_to_trough(built)


__all__ = [
    "Drawdown",
    "EquityPoint",
    "MarkFor",
    "Unavailable",
    "curve",
    "measure",
    "peak_to_trough",
]
