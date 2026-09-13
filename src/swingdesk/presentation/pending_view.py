"""`pending`'s read-time split, shared by `swingdesk pending` and `swingdesk status`.

Moved out of `cli.py` on 2026-09-12 so the status screen counts what `pending` lists, by the same
rules, rather than a second reading of `DR-013`. Nothing here writes: expiry and supersession are
both read-time, and `PositionStore.pending` says why a stored status would be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from swingdesk.contracts.position import ManagementAction
from swingdesk.journal_evidence.positions import Pending, PositionStore
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import calendar as cal
from swingdesk.trade_management import manage
from swingdesk.trade_management.sizing import Refusal


def expiry(
    positions: PositionStore, action: ManagementAction, now: datetime
) -> bool | Refusal:
    """Is this proposal past `DR-013`'s window? A `Refusal` when the rule cannot be applied.

    The exchange comes from the POSITION, never from parsing `position_id`. That id defaults to
    `POS-<instrument id>-<opened-on>` but `--position-id` overrides it, so splitting the string
    would work until the first time somebody used the flag - and then it would pick the wrong
    calendar silently, which is the worst way for a date rule to be wrong.
    """
    try:
        days, _ = ParameterRegistry.load().int_value("management.proposal_expiry_days")
    except ParameterUnset as unset:
        return Refusal("RISK", "no expiry window is set, so staleness cannot be judged",
                       parameter_id=unset.parameter_id)
    history = positions.history(action.position_id)
    if not history:
        return Refusal("DATA", f"no position {action.position_id} to date this proposal against")
    exchange = cal.exchange_for(history[-1].instrument_id)
    return manage.is_expired(action, now, days, exchange)


@dataclass
class PendingSplit:
    """Every unanswered proposal, in exactly one of four buckets."""

    waiting: list[Pending] = field(default_factory=list)
    expired: list[Pending] = field(default_factory=list)
    superseded: list[Pending] = field(default_factory=list)
    unjudgeable: list[tuple[Pending, Refusal]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (len(self.waiting) + len(self.expired) + len(self.superseded)
                + len(self.unjudgeable))


def split_pending(positions: PositionStore, now: datetime) -> PendingSplit:
    """Split at READ time (`DR-013` 6.4). Expired ones are SHOWN, not dropped: an owner who cannot
    tell "nothing pending" from "something aged out while I was away" has been told less than the
    truth, and the second is the case they most need to know about.

    Superseded BEFORE expiry: an older stop move that a newer one on the same position has replaced
    is the same question asked on staler data, whether or not it has also aged out. Counted per
    position rather than hidden - `manage.superseded` never touches a critical kind.
    """
    everything = positions.pending()
    replaced = manage.superseded(
        [(item.action.position_id, item.sequence, item.action.kind) for item in everything],
        positions.latest_stop_moves())
    out = PendingSplit()
    for item in everything:
        if (item.action.position_id, item.sequence) in replaced:
            out.superseded.append(item)
            continue
        verdict = expiry(positions, item.action, now)
        if isinstance(verdict, Refusal):
            out.unjudgeable.append((item, verdict))
        elif verdict:
            out.expired.append(item)
        else:
            out.waiting.append(item)
    return out
