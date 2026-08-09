"""A simulated trade, and the record it leaves.

Appendix J's Result stage requires net R, MFE, MAE and holding period; its Risk stage
requires entry, stop, shares, slippage and gap handling. This record carries all of them, and it
carries the exit reason as an enum rather than a string so an exit cannot be recorded as having
happened for a reason nobody defined.

The R denominator is the **initial planned risk** and never changes (`RISK_SPEC.md` §2,
`INVARIANTS`). A stop that moves does not rescale the trade's history.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExitReason(StrEnum):
    """How a trade ended. Four slots exist in the course's exit model (EXIT_MODEL_SPEC); this
    harness implements the protective and time slots and says so rather than pretending otherwise.
    """

    STOP = "stop"                 # protective slot: the stop was touched intraday
    STOP_GAP = "stop_gap"         # protective slot: the session opened through the stop
    TIME = "time"                 # time slot: maximum holding period reached
    END_OF_DATA = "end_of_data"   # the window ended while the position was open


class Trade(BaseModel):
    """One completed simulated trade.

    Frozen. A trade record that can be edited after the fact is not evidence, and the same
    immutability argument applies here as to the journal (`AUDIT_AND_IMMUTABILITY.md`).
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    arm: str = Field(description="Which study arm produced this trade.")

    signal_date: date = Field(description="Session the trigger and gate both passed.")
    entry_date: date = Field(description="Session the position opened. Never the signal date.")
    exit_date: date

    entry_price: Decimal = Field(gt=0, description="Fill price, after slippage.")
    stop_price: Decimal = Field(gt=0, description="Initial protective stop. Fixed at entry.")
    exit_price: Decimal = Field(gt=0, description="Fill price, after slippage.")
    shares: int = Field(gt=0)

    initial_risk_per_share: Decimal = Field(
        gt=0, description="entry - stop, before costs. The R denominator, fixed forever."
    )
    costs: Decimal = Field(ge=0, description="Commission plus the modelled spread cost, both sides.")

    mfe: Decimal = Field(description="Maximum favourable excursion in R, from entry.")
    mae: Decimal = Field(description="Maximum adverse excursion in R, from entry.")
    exit_reason: ExitReason

    @model_validator(mode="after")
    def _coherent(self) -> Trade:
        if self.entry_date <= self.signal_date:
            raise ValueError(
                f"entry {self.entry_date} must be after signal {self.signal_date} - a decision "
                f"made on the signal bar cannot execute on it"
            )
        if self.exit_date < self.entry_date:
            raise ValueError(f"exit {self.exit_date} before entry {self.entry_date}")
        if self.stop_price >= self.entry_price:
            raise ValueError(
                f"long stop {self.stop_price} is not below entry {self.entry_price}"
            )
        if self.mae > 0:
            raise ValueError(f"MAE must be <= 0 (it is adverse), got {self.mae}")
        if self.mfe < 0:
            raise ValueError(f"MFE must be >= 0 (it is favourable), got {self.mfe}")
        return self

    @property
    def gross_r(self) -> Decimal:
        """R before costs."""
        return (self.exit_price - self.entry_price) / self.initial_risk_per_share

    @property
    def net_r(self) -> Decimal:
        """R after costs. The reported figure, always.

        Appendix J says `Net R`, not R. Reporting gross and mentioning costs in a footnote is how a
        strategy that loses money looks profitable.
        """
        gross = (self.exit_price - self.entry_price) * self.shares
        return (gross - self.costs) / (self.initial_risk_per_share * self.shares)

    @property
    def holding_days(self) -> int:
        return (self.exit_date - self.entry_date).days

    @property
    def is_gap_loss(self) -> bool:
        """True when the exit gapped through the stop.

        Worth its own flag: assuming every stopped trade loses exactly 1R is the single most common
        way a backtest flatters itself, and this is the field that proves the harness did not.
        """
        return self.exit_reason is ExitReason.STOP_GAP
