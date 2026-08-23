"""What to propose for an open position, decided by rule.

Pure. Takes a position, the latest bar and the exit policy; returns a proposal. No I/O, no clock,
no journal - the same purity boundary the rest of `trade_management` sits behind, which is what
makes the proposal reproducible from its inputs.

It proposes and never acts. D1 forbids placing orders and D6 routes stop moves and partial exits
through the owner's approval, so the output of this module is a `ManagementAction` at status
`proposed` and nothing further happens without an answer.

`CHECKLIST_SPEC.md` §4 - open positions and gaps are checked first - is why the pipeline calls
this before it looks at a single candidate.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import reduce
from typing import Any

from swingdesk.contracts.market import Bar, CorporateAction, CorporateActionKind
from swingdesk.contracts.position import ActionKind, ManagementAction, Position
from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal
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


#: The only kinds a proposal may age out of (`DR-013` 2). Everything else NEVER expires, and the
#: list is a whitelist rather than a blacklist on purpose: `EXIT_NOW` is critical because not acting
#: leaves risk uncontrolled, and `PAUSE` means management could not be evaluated at all - which
#: `DR-013` did not classify, so it inherits the fail-closed side rather than a classification this
#: module invented. A kind added later expires only when a decision record says it may.
EXPIRING_KINDS = (ActionKind.MOVE_STOP, ActionKind.PARTIAL_EXIT)


def is_expired(
    action: ManagementAction, as_of: datetime, expiry_days: int, exchange: Exchange
) -> bool:
    """Has this proposal aged past `DR-013`'s window, measured in SESSIONS rather than days?

    Read-time only. Nothing writes `ActionStatus.EXPIRED` to a row, and `DR-013` 6.4 says why: a
    status somebody has to remember to write is the defect `pending` already avoids by defining
    pending as the ABSENCE of a response. There is no daemon here to write it, so a stored value
    would be correct only until the next moment nobody was looking.

    **Sessions, not calendar days.** A proposal made Friday is not stale on Monday - no bar existed
    over the weekend and no risk changed. Counting calendar days would expire proposals during
    exactly the intervals in which nothing could have invalidated them.

    **Critical kinds never expire** (`EXPIRING_KINDS`). Expiring an `EXIT_NOW` would convert the
    system's loudest statement into silence, and silence reads as "nothing to do" - `DR-013` 2.1.
    """
    if action.kind not in EXPIRING_KINDS:
        return False
    elapsed = cal.sessions(exchange, action.proposed_at.date(), as_of.date())
    # The proposal's own session is not elapsed time. A proposal made this morning has seen zero
    # sessions pass, not one - off by one here would expire everything a full day early.
    return max(len(elapsed) - 1, 0) > expiry_days


# ------------------------------------------------------------------ the split guard


def _ratio(value: Decimal) -> str:
    """A split ratio as a human would write it: `2`, not `2.000000` and not `2E+0`.

    The store holds `CorporateAction.value` as `DECIMAL(18,6)`, so a ratio that went in as `2`
    comes back as `2.000000` and a plain format renders every trailing zero. `normalize()` strips
    them and can produce exponent notation on a round number, which `:f` then undoes - a reason
    reading "a 1E+2:1 split" would be arithmetically correct and useless to the person acting on it.
    """
    return f"{value.normalize():f}"


@dataclass(frozen=True, slots=True)
class SplitAlert:
    """A split re-denominated this instrument's prices after the position's stop was set.

    **The failure this exists to stop.** Both decision paths read `Series.RAW`, and raw bars are
    unadjusted - so a split does not restate history, the next bars simply arrive at a different
    price level. A 2:1 split over a weekend leaves a stored stop of 290 being compared against
    Monday prices near 145: an instant stop-out that never happened, on a position still held
    (`DR-015` §4, `DR-016` §7).

    It is the one place in this system where being wrong costs money rather than a skipped
    candidate, because everything else it could distort produces a wrong `Watch`.
    """

    splits: tuple[CorporateAction, ...]
    """Every split effective after the stop was set, oldest first. More than one compounds."""

    stop_before: Decimal
    """The stop as recorded, denominated in pre-split prices."""

    @property
    def factor(self) -> Decimal:
        """What a pre-split price must be multiplied by to compare with a post-split one."""
        return reduce(lambda total, split: total * split.price_factor, self.splits, Decimal(1))

    @property
    def stop_after(self) -> Decimal:
        """What the stop corresponds to now. **Reported, never applied.**

        Adjusting the stop here would be the system rewriting a risk parameter the owner set, on
        its own authority - `CHARTER.md` A-001 makes the trading decision human-only and
        `AUDIT_AND_IMMUTABILITY.md` makes a position record immutable. So this number goes in the
        proposal's reason and the owner moves the stop, or does not.
        """
        return self.stop_before * self.factor

    @property
    def reason(self) -> str:
        ratios = " and ".join(
            f"a {_ratio(split.value)}:1 split on {split.effective_date}" for split in self.splits
        )
        return (
            f"{ratios} re-denominated this instrument after the stop was set, so the "
            f"recorded stop of {self.stop_before} corresponds to {self.stop_after:.4f} now. "
            f"Management cannot be evaluated against raw prices until the stop is restated - "
            f"the comparison would read as an immediate stop-out that never happened"
        )


@dataclass(frozen=True, slots=True)
class SplitGuard:
    """The guard's verdict for one position, including when it could not run.

    `refreshed` and `stored` are carried apart because zero actions is genuinely ambiguous: an
    instrument may have had no splits ever, or nobody may have asked. The store cannot record a
    negative, so the run records whether it successfully ASKED this evening. Without that, an
    unfed store and a clean instrument render identically - and only one of them is safe.
    """

    alert: SplitAlert | None
    refreshed: bool
    """Actions were successfully re-fetched for this instrument during this run."""

    stored: int
    """Actions the store held for it, as of the run's knowledge time."""

    @property
    def is_unavailable(self) -> bool:
        """Nothing was fetched and nothing is stored, so the question was never answered."""
        return not self.refreshed and self.stored == 0

    @property
    def note(self) -> str:
        if self.alert is not None:
            return self.alert.reason
        if self.is_unavailable:
            return (
                "UNAVAILABLE - no corporate action is stored for this instrument and none could be "
                "fetched, so whether a split has re-denominated its prices is unknown. The position "
                "is still managed; this is a gap in the check, not a fact about the trade"
            )
        return f"no split since the stop was set ({self.stored} action(s) on record)"


def split_guard(
    position: Position,
    actions: Sequence[CorporateAction],
    *,
    refreshed: bool,
) -> SplitGuard:
    """Has a split invalidated the comparison between this position's stop and raw prices?

    **The reference instant is the position VERSION's `knowledge_time`, not `opened_on`.** A stop
    moved last week was set against last week's prices, so a split before that move is already
    reflected in it and a split after it is not. `Position` is append-only and a stop move writes a
    new version, so the version's own knowledge time is exactly when its `current_stop` became
    true.

    **Strictly after, and that is an authored reading.** A split effective on the same date the
    stop was set is treated as already reflected: splits take effect at the open, so a stop set
    during that session was set against post-split prices. The opposite reading would pause a
    position for a split the owner had already seen.

    **Dividends are not splits and raise nothing.** `CorporateAction.price_factor` returns 1 for a
    dividend because the ex-date move is a market reaction rather than a re-denomination, and
    pausing on one would cry wolf on every dividend-paying holding. Filtered by kind here as well
    as by factor, so a future action type cannot fall through by having a factor of 1.
    """
    since = tuple(
        action
        for action in sorted(actions, key=lambda a: a.effective_date)
        if action.kind is CorporateActionKind.SPLIT
        and action.effective_date > position.knowledge_time.date()
    )
    alert = (
        SplitAlert(splits=since, stop_before=position.current_stop) if since else None
    )
    return SplitGuard(alert=alert, refreshed=refreshed, stored=len(actions))
