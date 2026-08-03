"""What a trade costs, charged rather than mentioned.

`costs.commission_model` and `costs.slippage_model` are registry entries and both are `unset`
(M72-T1081, M72-T1082). They are models rather than scalars because a per-share commission and a
proportional spread are different functions, and the course names both concepts and chooses neither.

A study pins its own values and records them. This class takes them as arguments and reads no
registry, so a result cannot silently change meaning when a value is later ratified.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CostModel:
    """Per-share commission plus proportional slippage, charged on both sides.

    Slippage is applied to the FILL PRICE, not deducted at the end. A long pays up on entry and
    down on exit, which also means the recorded entry price is the price actually paid - so MFE and
    MAE are measured from a real fill rather than from an idealised one.
    """

    commission_per_share: Decimal
    slippage_bps: Decimal

    def __post_init__(self) -> None:
        if self.commission_per_share < 0 or self.slippage_bps < 0:
            raise ValueError("costs cannot be negative")

    def stressed(self, multiple: Decimal) -> CostModel:
        """The same model at a higher cost. WALKFORWARD_SPEC 4, perturbations 3 and 4."""
        if multiple <= 0:
            raise ValueError(f"stress multiple must be > 0, got {multiple}")
        return CostModel(
            commission_per_share=self.commission_per_share * multiple,
            slippage_bps=self.slippage_bps * multiple,
        )

    def buy_fill(self, quoted: Decimal) -> Decimal:
        """A buyer pays up."""
        return quoted * (Decimal(1) + self.slippage_bps / Decimal(10_000))

    def sell_fill(self, quoted: Decimal) -> Decimal:
        """A seller receives less."""
        return quoted * (Decimal(1) - self.slippage_bps / Decimal(10_000))

    def commission(self, shares: int) -> Decimal:
        """Both sides, so twice the per-share rate."""
        return self.commission_per_share * shares * 2
