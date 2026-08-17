"""An open position, and the actions this system may PROPOSE for it.

Two owner decisions shape this record and neither is negotiable in code:

  D1  the system never places orders. Nothing here executes; every action is a proposal.
  D6  Telegram approves open-position actions - stop moves and partial exits. So a proposal has a
      lifecycle, and `proposed` is not `approved`.

The R denominator is `initial_risk_per_share` and it never changes (`RISK_SPEC.md` §2). A stop that
moves does not rescale the position's history: a trade that is +1.5R stays +1.5R after the stop is
raised, because R is what was risked when the decision was made, not what is at risk now.

`open risk` is recomputed from the CURRENT stop and never decremented - the same section - which is
why it is a property rather than a stored field. A stored open risk drifts from the stop that
defines it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionKind(StrEnum):
    """What the system proposes. `HOLD` is a decision and is recorded like any other.

    Nothing here has an execute verb. `EXIT_NOW` proposes that the owner exits; it does not exit.
    """

    HOLD = "hold"
    MOVE_STOP = "move_stop"
    PARTIAL_EXIT = "partial_exit"
    EXIT_NOW = "exit_now"
    PAUSE = "pause"


class ActionStatus(StrEnum):
    """D6's approval lifecycle. A proposal that nobody answered is not an approval."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Position(BaseModel):
    """One open position, as of a knowledge time.

    Frozen, and stored append-only: a stop move writes a NEW row superseding this one rather than
    updating it. Error `HINDSIGHT`'s required control is an immutable pre-trade snapshot
    (`AUDIT_AND_IMMUTABILITY.md`), and a mutable position record would remove it.
    """

    model_config = ConfigDict(frozen=True)

    position_id: str = Field(description="Stable across every version of this position.")
    version: int = Field(ge=1, description="Increments on each recorded change.")

    instrument_id: str
    opened_on: date
    entry_price: Decimal = Field(gt=0)
    shares: int = Field(gt=0)

    initial_stop: Decimal = Field(gt=0, description="The stop at entry. Never changes.")
    current_stop: Decimal = Field(gt=0, description="The stop now. May only move up for a long.")

    strategy: str = Field(default="unspecified")
    strategy_version: int = Field(default=1)

    knowledge_time: datetime = Field(description="When this version became true for us.")
    closed_on: date | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Position:
        if self.initial_stop >= self.entry_price:
            raise ValueError(
                f"long stop {self.initial_stop} is not below entry {self.entry_price}"
            )
        if self.current_stop < self.initial_stop:
            raise ValueError(
                f"current stop {self.current_stop} is below the initial stop {self.initial_stop}. "
                f"Widening a stop increases risk after the fact - error code WIDE_STOP."
            )
        if self.closed_on is not None and self.closed_on < self.opened_on:
            raise ValueError(f"closed {self.closed_on} before opened {self.opened_on}")
        return self

    @property
    def is_open(self) -> bool:
        return self.closed_on is None

    @property
    def initial_risk_per_share(self) -> Decimal:
        """The R denominator. Fixed at entry, forever."""
        return self.entry_price - self.initial_stop

    @property
    def initial_risk(self) -> Decimal:
        return self.initial_risk_per_share * self.shares

    @property
    def open_risk(self) -> Decimal:
        """What is at risk NOW, from the current stop. Recomputed, never decremented.

        Goes negative once the stop is above entry - the position can no longer lose money at the
        stop - and that is reported as a negative number rather than clamped to zero, because a
        clamp hides the difference between "risk removed" and "risk locked in as profit".
        """
        return (self.entry_price - self.current_stop) * self.shares

    def r_at(self, price: Decimal) -> Decimal:
        """R multiple at a price, on the ORIGINAL denominator."""
        return (price - self.entry_price) / self.initial_risk_per_share


class ManagementAction(BaseModel):
    """One proposed action on an open position.

    Maps to Appendix G's `Management` entity: action, reason, old/new stop, risk change, timestamp.
    Every field there is present, and `reason_code` is coded rather than free text so the twelve
    error codes stay computable (`CODES.md`).
    """

    model_config = ConfigDict(frozen=True)

    position_id: str
    proposed_at: datetime
    kind: ActionKind
    status: ActionStatus = ActionStatus.PROPOSED

    reason_code: str | None = Field(
        default=None, description="A skip or exit code where one applies. Coded, not prose."
    )
    reason: str = Field(description="Why, in one line. Required by 3.8's human-judgment rule.")

    old_stop: Decimal | None = None
    new_stop: Decimal | None = None
    shares_affected: int | None = Field(
        default=None, description="For a partial exit. None means the whole position."
    )

    @model_validator(mode="after")
    def _coherent(self) -> ManagementAction:
        if self.kind is ActionKind.MOVE_STOP:
            if self.old_stop is None or self.new_stop is None:
                raise ValueError("a stop move must record both the old and the new stop")
            if self.new_stop < self.old_stop:
                raise ValueError(
                    f"proposed stop {self.new_stop} is below the current {self.old_stop}. "
                    f"A stop move that increases risk is rejected (CODES WIDE_STOP)."
                )
        if self.kind is ActionKind.PARTIAL_EXIT and not self.shares_affected:
            raise ValueError("a partial exit must say how many shares")
        if not self.reason.strip():
            raise ValueError("every action carries a reason (Production Rules 3.8)")
        return self

    @property
    def is_actionable(self) -> bool:
        """True when the action needs the owner's answer before anything can happen (D6)."""
        return self.status is ActionStatus.PROPOSED and self.kind is not ActionKind.HOLD


class Fill(BaseModel):
    """What actually happened at the broker, against what was approved (`US-011`).

    D1 again, from the other side: the system never placed this order, so it cannot know the fill
    until the owner reports it. A fill is therefore evidence arriving after the fact, not an
    outcome the system produced - and it settles a specific approved action, so a fill can never
    exist for something nobody approved.

    Frozen and stored append-only, like everything else here. A fill that can be edited is not
    evidence (`AUDIT_AND_IMMUTABILITY.md`).
    """

    model_config = ConfigDict(frozen=True)

    position_id: str
    sequence: int = Field(ge=1, description="The approved action this settles.")

    filled_on: date
    shares: int = Field(gt=0, description="Shares actually transacted, which may not be the plan.")
    price: Decimal = Field(gt=0, description="What the broker actually filled at.")
    commission: Decimal = Field(ge=0, description="As charged. Not the modelled estimate.")

    planned_price: Decimal | None = Field(
        default=None,
        description="The price the approved plan named, when it named one. None is not zero - see "
                    "`slippage_per_share`.",
    )
    recorded_at: datetime = Field(description="When we learned this. Not when it happened.")

    @property
    def slippage_per_share(self) -> Decimal | None:
        """Adverse slippage per share, or None when the plan named no price to slip against.

        **None is a refusal, not a zero, and this is the whole reason the field is optional.** An
        `EXIT_NOW` is proposed for two different reasons (`trade_management.manage`): a broken stop,
        where the plan names a price and the stop IS the reference; and a maximum holding period
        reached, which is an exit at market and names no price at all. Reporting 0.00 slippage for
        the second would be a manufactured measurement of exactly the kind `HANDOFF` 3 forbids -
        and it would flatter the strategy, because a time exit's true slippage is unknown rather
        than absent.

        Positive is ADVERSE for a long exit: the plan said sell at the stop and the fill came in
        below it.
        """
        if self.planned_price is None:
            return None
        return self.planned_price - self.price

    def slippage_r(self, initial_risk_per_share: Decimal) -> Decimal | None:
        """Slippage as a fraction of R, against the ORIGINAL denominator (`US-011`, `RISK_SPEC` 2).

        The denominator is the risk planned at entry and never moves - not the risk after a stop
        was trailed, and not the risk on the shares that remain. Measuring slippage against a
        shrinking denominator would make the same dollar miss look worse and worse as a position
        is scaled out, which is the opposite of comparable.
        """
        per_share = self.slippage_per_share
        if per_share is None:
            return None
        if initial_risk_per_share <= 0:
            raise ValueError("the R denominator is not positive; slippage in R is undefined")
        return per_share / initial_risk_per_share
