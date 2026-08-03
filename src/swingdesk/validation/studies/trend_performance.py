"""PR-005: do the trend definitions' populations behave differently, net of costs?

Pure. Takes each arm's trades and returns the comparison; it fetches nothing, simulates nothing and
reads no registry.

The decision rule is NOT here. `PR-005` §6 fixed it before the run, and the caller supplies its
numbers - a rule living in analysis code is a rule that can be adjusted after seeing the result.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import Decimal

from swingdesk.contracts.trade import ExitReason, Trade


@dataclass(frozen=True, slots=True)
class ArmStats:
    """One arm's outcome distribution. Every figure is net of costs."""

    arm: str
    trades: int
    mean_r: Decimal
    median_r: Decimal
    hit_rate: Decimal
    mean_mfe: Decimal
    mean_mae: Decimal
    mean_holding_days: Decimal
    gap_exits: int
    exit_reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArmComparison:
    """One gated arm against the ungated reference."""

    arm: str
    difference: Decimal
    ci_low: Decimal
    ci_high: Decimal
    resamples: int

    @property
    def outside_interval(self) -> bool:
        """True when the observed difference falls outside the null interval.

        The interval is built by resampling the POOLED trades of both arms, so it describes what a
        difference of this size looks like when there is no difference. A difference outside it is
        larger than the sampling noise of an equally-sized split.
        """
        return self.difference < self.ci_low or self.difference > self.ci_high


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / len(values) if values else Decimal(0)


def _median(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def summarise_arm(arm: str, trades: list[Trade]) -> ArmStats:
    if not trades:
        return ArmStats(arm, 0, Decimal(0), Decimal(0), Decimal(0),
                        Decimal(0), Decimal(0), Decimal(0), 0, {})

    net = [trade.net_r for trade in trades]
    reasons: dict[str, int] = {}
    for trade in trades:
        reasons[trade.exit_reason.value] = reasons.get(trade.exit_reason.value, 0) + 1

    return ArmStats(
        arm=arm,
        trades=len(trades),
        mean_r=_mean(net),
        median_r=_median(net),
        hit_rate=Decimal(sum(1 for r in net if r > 0)) / Decimal(len(net)),
        mean_mfe=_mean([t.mfe for t in trades]),
        mean_mae=_mean([t.mae for t in trades]),
        mean_holding_days=_mean([Decimal(t.holding_days) for t in trades]),
        gap_exits=sum(1 for t in trades if t.exit_reason is ExitReason.STOP_GAP),
        exit_reasons=reasons,
    )


def compare_to_reference(
    arm: str,
    arm_trades: list[Trade],
    reference_trades: list[Trade],
    *,
    seed: int,
    resamples: int = 10_000,
    interval: Decimal = Decimal("0.95"),
) -> ArmComparison:
    """Difference in mean net R against a seeded permutation null.

    The null is built by pooling both arms' trades and repeatedly splitting them at the observed
    sizes. That answers the question actually being asked - "is a gap this large surprising if the
    gate did nothing?" - rather than assuming a distribution the R series does not have.

    Seeded and recorded (DETERMINISM_SPEC 3.4). There is no unseeded RNG anywhere in this project.
    """
    arm_r = [t.net_r for t in arm_trades]
    reference_r = [t.net_r for t in reference_trades]
    if not arm_r or not reference_r:
        return ArmComparison(arm, Decimal(0), Decimal(0), Decimal(0), 0)

    observed = _mean(arm_r) - _mean(reference_r)

    pooled = arm_r + reference_r
    size = len(arm_r)
    rng = random.Random(seed)
    differences: list[Decimal] = []
    for _ in range(resamples):
        shuffled = pooled[:]
        rng.shuffle(shuffled)
        differences.append(_mean(shuffled[:size]) - _mean(shuffled[size:]))

    differences.sort()
    tail = (Decimal(1) - interval) / 2
    low_index = int(tail * resamples)
    high_index = int((Decimal(1) - tail) * resamples) - 1
    return ArmComparison(
        arm=arm,
        difference=observed,
        ci_low=differences[low_index],
        ci_high=differences[high_index],
        resamples=resamples,
    )


def ranking(stats: list[ArmStats]) -> tuple[str, ...]:
    """Arms ordered by mean net R, best first, ties broken by name for determinism."""
    return tuple(
        item.arm for item in sorted(stats, key=lambda s: (-s.mean_r, s.arm))
    )
