"""How wrong would the sample have to be to erase a result?

Survivorship cannot be measured on free data and, after owner decision D10, will not be. That leaves
two options: name the confound and stop, or bound it. This bounds it.

The question is not "how much bias is there" - unanswerable here - but "how much would there have to
be". That converts an open-ended caveat into a number the owner can weigh against what they know
about delisting rates, which is a judgement they can actually make.

Two shapes, and the difference between them is the whole analysis:

  concentrated  missing trades fall in ONE cell. Realistic when the cell is defined by market
                stress, because delisting is not independent of drawdown.
  proportional  missing trades are spread across cells in proportion to their size. The
                shape a survivorship-neutral sampling gap would take.

Pure. No I/O, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BreakEven:
    """What it would take to pull an observed gap down to a threshold."""

    missing_trades: int
    fraction_of_cell: Decimal
    fraction_of_total: Decimal
    assumed_r: Decimal
    shape: str

    @property
    def is_reachable(self) -> bool:
        """False when no finite number of missing trades at this R would close the gap."""
        return self.missing_trades >= 0


def concentrated_break_even(
    high_mean: Decimal,
    high_trades: int,
    low_mean: Decimal,
    low_trades: int,
    threshold: Decimal,
    missing_r: Decimal,
) -> BreakEven:
    """Missing trades added to the BETTER cell only, at mean R `missing_r`.

    `high_mean` is the better cell's mean and `high_trades` its count - the naming follows the
    result, not the regime labels. This is the worst case for a finding whose good cell is defined
    by market stress, and the realistic one when delisting concentrates in drawdowns.

    Solves (n*m + M*r) / (n + M) = other_mean + threshold for M.
    """
    if high_trades < 1 or low_trades < 1:
        raise ValueError("both cells need at least one trade")

    target = low_mean + threshold
    denominator = target - missing_r
    if denominator <= 0:
        # The missing trades are not bad enough to drag the cell down to the target, ever.
        return BreakEven(-1, Decimal(0), Decimal(0), missing_r, "concentrated")

    numerator = Decimal(high_trades) * (high_mean - target)
    if numerator <= 0:
        return BreakEven(0, Decimal(0), Decimal(0), missing_r, "concentrated")

    missing = int(numerator / denominator) + 1
    return BreakEven(
        missing_trades=missing,
        fraction_of_cell=Decimal(missing) / Decimal(high_trades + missing),
        fraction_of_total=Decimal(missing) / Decimal(high_trades + low_trades + missing),
        assumed_r=missing_r,
        shape="concentrated",
    )


def proportional_break_even(observed_gap: Decimal, threshold: Decimal) -> Decimal:
    """Fraction of ALL trades that would have to be missing, spread proportionally.

    Adding trades at the same mean R to every cell in proportion to its size scales the gap by
    1 / (1 + p), where p is the proportional inflation - and the R of the missing trades cancels
    entirely. So this shape has one answer regardless of how badly the missing trades did, which is
    exactly why the concentrated shape is the one that matters.
    """
    if observed_gap <= 0 or threshold <= 0 or observed_gap <= threshold:
        return Decimal(0)
    inflation = observed_gap / threshold - Decimal(1)
    return inflation / (Decimal(1) + inflation)
