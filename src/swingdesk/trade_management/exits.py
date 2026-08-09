"""How a position ends, decided by rule.

Lives in `trade_management` because that is the layer the course assigns exits to - M52-M58 are
Trade Management topics, and `EXIT_MODEL_SPEC.md` owns the four-slot model. It sat in
`validation.backtest` until N2 needed it on the live path too, which is the moment a shared rule
stops being a backtest detail. The backtest imports it from here; there is one implementation, not
two (Production Rules 3.8).

Appendix J's Exit stage: all rules, without discretionary hindsight - every exit follows a rule, and
the thing being excluded is named as discretionary hindsight.

This implements two of the course's four exit slots (`EXIT_MODEL_SPEC.md`): protective and time.
The profit and contextual slots are absent, and that is a stated limitation of the harness rather
than an oversight - adding a profit target would mean PR-005 compared five gates through two exit
models, which is a different study.

Gap handling is the part worth reading. A session that OPENS below the stop fills at the open, and
the loss recorded is the actual loss. Assuming every stopped trade loses exactly 1R is the single
most common way a backtest flatters itself, and on the instruments where it matters most - the ones
that gap - it is wrong by a lot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from swingdesk.contracts.market import Bar
from swingdesk.contracts.trade import ExitReason


@dataclass(frozen=True, slots=True)
class ExitDecision:
    """What happened to the position on this bar."""

    exited: bool
    price: Decimal | None = None
    reason: ExitReason | None = None

    def __post_init__(self) -> None:
        """An exit without a price or a reason is not an exit.

        The fields are optional because a non-exit has neither, and that left
        `ExitDecision(exited=True)` constructible - it would have produced a Trade with a None exit
        price and no recorded reason. mypy surfaced it at the backtest engine's call site as an
        unnarrowed `Decimal | None`; the fix belongs here, where the invariant lives.
        """
        if self.exited and (self.price is None or self.reason is None):
            raise ValueError("an exit must carry both a price and a reason")


@dataclass(frozen=True, slots=True)
class ExitPolicy:
    """Protective stop plus a maximum holding period.

    `atr_stop_multiple` and `max_holding_bars` are study constants pinned by the caller, not
    registry reads - `exit.atr_stop_multiple` and `exit.max_holding_period` are both `unset` and a
    study that inherited them would change meaning the day they were ratified.
    """

    atr_stop_multiple: Decimal
    max_holding_bars: int

    def __post_init__(self) -> None:
        if self.atr_stop_multiple <= 0:
            raise ValueError(f"atr_stop_multiple must be > 0, got {self.atr_stop_multiple}")
        if self.max_holding_bars < 1:
            raise ValueError(f"max_holding_bars must be >= 1, got {self.max_holding_bars}")

    def stop_for(self, entry_price: Decimal, atr: Decimal) -> Decimal:
        """Initial protective stop. Set before size, always (RISK_SPEC 3)."""
        return entry_price - self.atr_stop_multiple * atr

    def evaluate(self, bar: Bar, stop: Decimal, bars_held: int) -> ExitDecision:
        """Check one bar against the policy, protective slot first.

        Order matters and is not arbitrary: the protective exit is checked before the time exit,
        because a bar that both breaks the stop and completes the holding period is a stop-out. The
        opposite order would silently convert some losses into time exits at their closing price,
        which is usually a better price.
        """
        if bar.open <= stop:
            # Gapped through. The fill is the open, not the stop.
            return ExitDecision(True, bar.open, ExitReason.STOP_GAP)
        if bar.low <= stop:
            return ExitDecision(True, stop, ExitReason.STOP)
        if bars_held >= self.max_holding_bars:
            return ExitDecision(True, bar.close, ExitReason.TIME)
        return ExitDecision(False)
