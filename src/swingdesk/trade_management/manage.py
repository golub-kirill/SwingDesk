"""What to propose for an open position, decided by rule.

Pure. Takes a position, the latest bar and the exit policy; returns a proposal. No I/O, no clock,
no journal - the same purity boundary the rest of `trade_management` sits behind, which is what
makes the proposal reproducible from its inputs.

It proposes and never acts. D1 forbids placing orders and D6 routes stop moves and partial exits
through the owner's approval, so the output of this module is a `ManagementAction` at status
`proposed` and nothing further happens without an answer.

`CHECKLIST_SPEC.md` §4 - `Открытые позиции и gaps проверены первыми` - is why the pipeline calls
this before it looks at a single candidate.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from swingdesk.contracts.market import Bar
from swingdesk.contracts.position import ActionKind, ManagementAction, Position
from swingdesk.trade_management.exits import ExitPolicy


def evaluate(
    position: Position,
    bar: Bar,
    policy: ExitPolicy,
    now: datetime,
    *,
    bars_held: int,
    atr: Decimal | None = None,
) -> ManagementAction:
    """One position, one bar, one proposal.

    Order matters and mirrors the backtest engine: the protective exit is checked before anything
    else, because a bar that breaks the stop is a stop-out regardless of what else it did. The live
    path and the simulated path must agree here or the backtest is measuring a different system.
    """
    decision = policy.evaluate(bar, position.current_stop, bars_held)

    if decision.exited:
        gapped = bar.open <= position.current_stop
        return ManagementAction(
            position_id=position.position_id,
            proposed_at=now,
            kind=ActionKind.EXIT_NOW,
            reason_code=decision.reason.value.upper() if decision.reason else None,
            reason=(
                f"stop {position.current_stop} touched at {bar.session_date}"
                + (" - session opened through it, so the fill is the open" if gapped else "")
                if decision.reason and decision.reason.value.startswith("stop")
                else f"maximum holding period reached at {bar.session_date}"
            ),
            old_stop=position.current_stop,
        )

    if atr is not None and atr > 0:
        # A trailing stop is a SEPARATE, unregistered choice and PR-005 tested none - so this
        # proposes a move only when the rule-derived stop is HIGHER than the current one, never
        # lower. A stop that can move down is not a stop.
        candidate = policy.stop_for(bar.close, atr)
        if candidate > position.current_stop:
            return ManagementAction(
                position_id=position.position_id,
                proposed_at=now,
                kind=ActionKind.MOVE_STOP,
                reason=(
                    f"{policy.atr_stop_multiple}xATR below {bar.close} is {candidate}, above the "
                    f"current stop {position.current_stop}"
                ),
                old_stop=position.current_stop,
                new_stop=candidate,
            )

    return ManagementAction(
        position_id=position.position_id,
        proposed_at=now,
        kind=ActionKind.HOLD,
        reason=(
            f"stop {position.current_stop} intact; {bars_held} of "
            f"{policy.max_holding_bars} bars held"
        ),
        old_stop=position.current_stop,
    )


def apply_approved(position: Position, action: ManagementAction, now: datetime) -> Position:
    """The next version of a position after an APPROVED action.

    Returns a new record; it never mutates. The store appends it, so the prior version stays
    readable and the audit trail is the sequence of versions rather than a field someone overwrote.

    Refuses anything not approved. A proposal is not permission (D6).
    """
    from swingdesk.contracts.position import ActionStatus

    if action.status is not ActionStatus.APPROVED:
        raise ValueError(
            f"action is {action.status}, not approved. A proposal is not permission (D6)."
        )
    if action.position_id != position.position_id:
        raise ValueError("action does not belong to this position")

    update: dict[str, Any] = {"version": position.version + 1, "knowledge_time": now}
    if action.kind is ActionKind.MOVE_STOP and action.new_stop is not None:
        update["current_stop"] = action.new_stop
    elif action.kind is ActionKind.PARTIAL_EXIT and action.shares_affected:
        remaining = position.shares - action.shares_affected
        if remaining < 1:
            raise ValueError(
                f"partial exit of {action.shares_affected} would leave {remaining} shares; "
                f"that is a full exit and must be recorded as one"
            )
        update["shares"] = remaining
    elif action.kind is ActionKind.EXIT_NOW:
        update["closed_on"] = now.date()

    return position.model_copy(update=update)
