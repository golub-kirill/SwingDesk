"""PR-002: does a regime label carry decision-relevant information, or only relabel outcomes?

The statistic is the **range of mean net R across regime cells** - best cell minus worst - compared
against the same statistic computed on random partitions of the same trades into cells of the same
sizes.

That baseline is not a refinement, it is the requirement. M30-T0450:

    "добавленная ценность проверяется против простой базовой модели"

Any partition of a noisy series produces cells with different means. Comparing a regime partition
against *nothing* finds a difference every time, which is why the comparison is against a partition
that is known to carry no information.

Pure and seeded. No unseeded RNG anywhere (DETERMINISM_SPEC 3.4).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import Decimal

from swingdesk.contracts.trade import Trade


@dataclass(frozen=True, slots=True)
class CellStats:
    """One regime's trades."""

    regime: str
    trades: int
    mean_r: Decimal


@dataclass(frozen=True, slots=True)
class RegimeValue:
    """A fitted variant's separation, against the random-partition baseline."""

    variant: str
    cells: tuple[CellStats, ...]
    observed_range: Decimal
    percentile: Decimal
    baseline_p80: Decimal
    baseline_p95: Decimal
    resamples: int
    unlabelled: int = 0
    thin_cells: tuple[str, ...] = field(default_factory=tuple)

    @property
    def separates(self) -> bool:
        """PR-002 section 6 accept branch: above the 95th percentile of the baseline."""
        return self.observed_range > self.baseline_p95

    @property
    def refuted(self) -> bool:
        """Reject branch: below the 80th percentile."""
        return self.observed_range < self.baseline_p80


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / len(values) if values else Decimal(0)


def _range_across(groups: list[list[Decimal]]) -> Decimal:
    """Best cell mean minus worst. One number, comparable across variants with different cell
    counts, and the quantity a trader would act on: how much better is the best regime."""
    means = [_mean(group) for group in groups if group]
    if len(means) < 2:
        return Decimal(0)
    return max(means) - min(means)


def evaluate(
    variant: str,
    labelled: list[tuple[str | None, Trade]],
    *,
    seed: int,
    resamples: int = 1000,
    min_trades_per_cell: int = 1,
) -> RegimeValue:
    """Compare a variant's cross-regime spread against equal-sized random partitions.

    `labelled` pairs each trade with the regime in force on its SIGNAL date. Trades whose session
    could not be labelled are excluded and counted - a session the classifier cannot label is not a
    regime, and assigning it a default one would be inventing the very thing under test.
    """
    usable = [(label, trade) for label, trade in labelled if label is not None]
    unlabelled = len(labelled) - len(usable)

    by_regime: dict[str, list[Decimal]] = {}
    for label, trade in usable:
        by_regime.setdefault(label, []).append(trade.net_r)

    cells = tuple(
        CellStats(regime=name, trades=len(values), mean_r=_mean(values))
        for name, values in sorted(by_regime.items())
    )
    thin = tuple(cell.regime for cell in cells if cell.trades < min_trades_per_cell)

    if len(by_regime) < 2:
        return RegimeValue(variant, cells, Decimal(0), Decimal(0), Decimal(0), Decimal(0),
                           0, unlabelled, thin)

    observed = _range_across(list(by_regime.values()))

    # The baseline: same trades, same cell sizes, membership shuffled.
    pooled = [trade.net_r for _, trade in usable]
    sizes = [len(values) for values in by_regime.values()]
    rng = random.Random(seed)

    baseline: list[Decimal] = []
    for _ in range(resamples):
        shuffled = pooled[:]
        rng.shuffle(shuffled)
        groups: list[list[Decimal]] = []
        start = 0
        for size in sizes:
            groups.append(shuffled[start: start + size])
            start += size
        baseline.append(_range_across(groups))

    baseline.sort()
    below = sum(1 for value in baseline if value < observed)
    percentile = Decimal(below) / Decimal(len(baseline)) * 100

    def at(fraction: float) -> Decimal:
        return baseline[min(len(baseline) - 1, int(fraction * len(baseline)))]

    return RegimeValue(
        variant=variant,
        cells=cells,
        observed_range=observed,
        percentile=percentile,
        baseline_p80=at(0.80),
        baseline_p95=at(0.95),
        resamples=resamples,
        unlabelled=unlabelled,
        thin_cells=thin,
    )


# ---------------------------------------------------------------- the stronger null


def evaluate_by_date(
    variant: str,
    labels_by_date: dict,
    trades: list[Trade],
    *,
    seed: int,
    resamples: int = 1000,
) -> RegimeValue:
    """The same statistic against a baseline that permutes DATES, not trades.

    `evaluate` shuffles individual trades, which assumes they are exchangeable. They are not: on any
    given session dozens of instruments fire together, and trades within a regime are clustered in
    time and correlated with each other. Under that clustering the effective sample is far smaller
    than the trade count, and a trade-level permutation understates the null's spread - which
    inflates the observed statistic's percentile.

    This permutes the date -> label assignment instead, preserving both the number of sessions per
    regime and the clustering of trades within a session. It is the null a regime study actually
    needs, and it is strictly harder to beat.
    """
    dates = sorted(labels_by_date)
    observed_labels = [labels_by_date[d] for d in dates]

    by_regime: dict[str, list[Decimal]] = {}
    for trade in trades:
        label = labels_by_date.get(trade.signal_date)
        if label is None:
            continue
        by_regime.setdefault(label, []).append(trade.net_r)

    cells = tuple(
        CellStats(regime=name, trades=len(values), mean_r=_mean(values))
        for name, values in sorted(by_regime.items())
    )
    unlabelled = sum(1 for t in trades if labels_by_date.get(t.signal_date) is None)

    if len(by_regime) < 2:
        return RegimeValue(variant, cells, Decimal(0), Decimal(0), Decimal(0), Decimal(0),
                           0, unlabelled, ())

    observed = _range_across(list(by_regime.values()))

    trades_by_date: dict = {}
    for trade in trades:
        trades_by_date.setdefault(trade.signal_date, []).append(trade.net_r)

    rng = random.Random(seed)
    baseline: list[Decimal] = []
    for _ in range(resamples):
        shuffled = observed_labels[:]
        rng.shuffle(shuffled)
        groups: dict[str, list[Decimal]] = {}
        for session, label in zip(dates, shuffled):
            if label is None:
                continue
            groups.setdefault(label, []).extend(trades_by_date.get(session, []))
        baseline.append(_range_across(list(groups.values())))

    baseline.sort()
    below = sum(1 for value in baseline if value < observed)
    percentile = Decimal(below) / Decimal(len(baseline)) * 100

    def at(fraction: float) -> Decimal:
        return baseline[min(len(baseline) - 1, int(fraction * len(baseline)))]

    return RegimeValue(
        variant=variant, cells=cells, observed_range=observed, percentile=percentile,
        baseline_p80=at(0.80), baseline_p95=at(0.95), resamples=resamples,
        unlabelled=unlabelled, thin_cells=(),
    )
