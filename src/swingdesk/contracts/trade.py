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
    harness implements the protective, profit and time slots, and says so rather than pretending
    otherwise. The contextual slot is still absent.

    `TARGET` arrived on 2026-09-07 with `DR-042`. Before it, the harness could not simulate the exit
    this system actually places: `exit.target_r_multiple` was ratified at 1R on 2026-09-01
    (`DR-029`) and lived only in `broker/submit.py`, so every backtested trade ran the stop and the
    clock while every live trade also carried a take-profit leg. A study measuring "the ratified
    exit" was measuring two thirds of it.
    """

    STOP = "stop"                 # protective slot: the stop was touched intraday
    STOP_GAP = "stop_gap"         # protective slot: the session opened through the stop
    TARGET = "target"             # profit slot: the take-profit limit was reached
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

    # --- the profit slot's partial, M54. Optional, and the default is what protects every log
    # already published: with `partial_shares` at 0 the arithmetic below reduces EXACTLY to what
    # it was, so `PR-002`, `PR-005`, `PR-011` and `PR-012` keep their numbers. A published trade
    # log that changes when nobody re-ran it is not evidence.
    partial_shares: int = Field(
        default=0, ge=0,
        description="Shares sold at the partial trigger. 0 means the slot was not used.",
    )
    partial_price: Decimal | None = Field(
        default=None, description="Fill price of the partial, after slippage."
    )
    partial_date: date | None = Field(default=None, description="Session the partial filled.")

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
        self._coherent_partial()
        return self

    def _coherent_partial(self) -> None:
        """A partial is three facts or none of them, and a partial of the WHOLE position is an exit.

        The three fields travel together because two of them without the third is a trade nobody
        can price: shares with no price, or a price with no date, would each pass every other
        check here and produce a plausible wrong `net_r`.
        """
        given = [self.partial_shares > 0, self.partial_price is not None,
                 self.partial_date is not None]
        if any(given) and not all(given):
            raise ValueError(
                f"a partial needs shares, price and date together, got shares="
                f"{self.partial_shares} price={self.partial_price} date={self.partial_date}"
            )
        if self.partial_shares == 0:
            return
        if self.partial_shares >= self.shares:
            raise ValueError(
                f"partial of {self.partial_shares} of {self.shares} shares closes the position - "
                f"that is an exit, and recording it as a partial would double-count the final leg"
            )
        if self.partial_price is not None and self.partial_price <= 0:
            raise ValueError(f"partial price must be > 0, got {self.partial_price}")
        if self.partial_date is not None and not (
            self.entry_date <= self.partial_date <= self.exit_date
        ):
            raise ValueError(
                f"partial {self.partial_date} is outside the position's life "
                f"{self.entry_date}..{self.exit_date}"
            )

    @property
    def runner_shares(self) -> int:
        """What is left after the partial. The whole position when the slot is unused."""
        return self.shares - self.partial_shares

    @property
    def _gross(self) -> Decimal:
        """Money before costs, across every leg.

        Share-weighted rather than price-differenced, because a partial fills at a different price
        from the final exit and the two legs are different sizes. With `partial_shares` at 0 this
        is `(exit - entry) * shares`, which is what it always was.
        """
        return (self.partial_shares * (self.partial_price - self.entry_price)
                if self.partial_price is not None else Decimal(0)) + (
            self.runner_shares * (self.exit_price - self.entry_price)
        )

    @property
    def gross_r(self) -> Decimal:
        """R before costs."""
        return self._gross / (self.initial_risk_per_share * self.shares)

    @property
    def net_r(self) -> Decimal:
        """R after costs. The reported figure, always.

        Appendix J says `Net R`, not R. Reporting gross and mentioning costs in a footnote is how a
        strategy that loses money looks profitable.
        """
        return (self._gross - self.costs) / (self.initial_risk_per_share * self.shares)

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
