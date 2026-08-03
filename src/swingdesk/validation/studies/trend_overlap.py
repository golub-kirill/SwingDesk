"""PR-001: do the candidate trend definitions select different instruments, or the same ones?

The statistic is the daily Jaccard index between the sets each definition selects, reported as a
median and a 10th percentile per pair, per country.

The 10th percentile is the one that matters and the pre-registration says so: if definitions agree
on calm days and diverge exactly when the decision is hard, a high median hides the finding.

Pure. Takes assembled per-instrument inputs and returns numbers; it fetches nothing and reads no
registry. The rule and periods a run used are pinned by the caller and recorded in its evidence,
rather than inherited from whatever the registry says later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from itertools import combinations

from swingdesk.decision_logic.trend import TrendDefinition, TrendInputs, is_uptrend

#: Definitions this study can evaluate today. `ADX_DI` is absent: it needs a threshold that has no
#: course basis, and picking one would answer part of the question the study is asking.
RUNNABLE = (
    TrendDefinition.ABOVE_LONG_MA,
    TrendDefinition.MA_STACK,
    TrendDefinition.PRICE_AND_STACK,
    TrendDefinition.STRUCTURE,
)


@dataclass(frozen=True, slots=True)
class DailySelection:
    """Which instruments each definition selected on one session, and which could not answer."""

    session_date: date
    instruments: frozenset[str]
    selected: dict[str, frozenset[str]]
    undecided: dict[str, frozenset[str]]

    @property
    def sizes(self) -> dict[str, int]:
        return {name: len(members) for name, members in self.selected.items()}

    def decidable(self, left: str, right: str) -> frozenset[str]:
        """Instruments BOTH definitions could answer on.

        Comparing a pair over instruments one of them could not evaluate scores "cannot answer" as
        "answered no" - the exact conflation the three-valued verdict exists to prevent, arriving
        one level up at aggregation time. A test caught it doing precisely that.
        """
        return self.instruments - self.undecided[left] - self.undecided[right]


@dataclass(frozen=True, slots=True)
class PairOverlap:
    """Jaccard between two definitions, summarised over the window.

    `sessions` counts only those where both definitions could answer on at least one instrument.
    `mean_decidable` says how wide the comparison was - a pair judged on three instruments and a
    pair judged on forty deserve different amounts of belief, and a bare Jaccard hides which is
    which.
    """

    left: str
    right: str
    sessions: int
    median: Decimal
    p10: Decimal
    minimum: Decimal
    mean_decidable: Decimal = Decimal(0)

    @property
    def label(self) -> str:
        return f"{self.left}~{self.right}"


@dataclass
class OverlapResult:
    country: str
    instruments: int
    sessions: int
    pairs: list[PairOverlap] = field(default_factory=list)
    mean_selected: dict[str, Decimal] = field(default_factory=dict)
    undecided_rate: dict[str, Decimal] = field(default_factory=dict)

    def verdict(self, accept_median: Decimal, accept_p10: Decimal,
                reject_median: Decimal, reject_p10: Decimal) -> str:
        """PR-001 section 6, applied. Thresholds are passed in, never defaulted here.

        A decision rule that lives in the analysis code can be adjusted after seeing the result. The
        pre-registration fixed these numbers; the caller supplies them from it.
        """
        if not self.pairs:
            return "inconclusive"
        medians = [pair.median for pair in self.pairs]
        p10s = [pair.p10 for pair in self.pairs]
        if min(medians) >= accept_median and min(p10s) >= accept_p10:
            return "accept"
        # "One pair below the floor refutes it": the claim is that the FAMILY is interchangeable,
        # so a single member that is not is enough (PR-001 section 9).
        if min(medians) <= reject_median or min(p10s) <= reject_p10:
            return "reject"
        return "inconclusive"


def jaccard(left: frozenset[str], right: frozenset[str]) -> Decimal:
    """|A n B| / |A u B|, with the empty-empty case defined as 1.

    Two definitions that both selected nothing agree completely about that session. Returning 0
    would score perfect agreement as total disagreement and drag the p10 down on exactly the quiet
    days the statistic is least informative about.
    """
    union = left | right
    if not union:
        return Decimal(1)
    return Decimal(len(left & right)) / Decimal(len(union))


def select(
    session_date: date,
    inputs_by_instrument: dict[str, TrendInputs],
    definitions: tuple[TrendDefinition, ...] = RUNNABLE,
    pivot_count: int = 2,
) -> DailySelection:
    """Apply every definition to every instrument for one session.

    `None` verdicts go to `undecided`, never to `selected` and never to its complement. A definition
    that answers on fewer bars would otherwise look like it selected a different population for a
    reason having nothing to do with trend.
    """
    selected: dict[str, set[str]] = {d.name: set() for d in definitions}
    undecided: dict[str, set[str]] = {d.name: set() for d in definitions}

    for instrument_id, inputs in sorted(inputs_by_instrument.items()):
        for definition in definitions:
            verdict = is_uptrend(definition, inputs, pivot_count=pivot_count)
            if verdict is None:
                undecided[definition.name].add(instrument_id)
            elif verdict:
                selected[definition.name].add(instrument_id)

    return DailySelection(
        session_date=session_date,
        instruments=frozenset(inputs_by_instrument),
        selected={name: frozenset(members) for name, members in selected.items()},
        undecided={name: frozenset(members) for name, members in undecided.items()},
    )


def _percentile(values: list[Decimal], percentile: int) -> Decimal:
    """Nearest-rank on a sorted list. Explicit because numpy's default is a different estimator and
    a study that cannot say which one it used cannot be compared to another."""
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round(percentile / 100 * (len(ordered) - 1))))
    return ordered[int(rank)]


def summarise(country: str, instruments: int, daily: list[DailySelection]) -> OverlapResult:
    """Fold the per-session selections into per-pair overlap statistics."""
    result = OverlapResult(country=country, instruments=instruments, sessions=len(daily))
    if not daily:
        return result

    names = sorted(daily[0].selected)
    for left, right in combinations(names, 2):
        scores: list[Decimal] = []
        widths: list[Decimal] = []
        for day in daily:
            decidable = day.decidable(left, right)
            if not decidable:
                # Neither definition could answer anywhere. The session carries no information
                # about this pair, so it contributes no observation rather than a 1 or a 0.
                continue
            scores.append(
                jaccard(day.selected[left] & decidable, day.selected[right] & decidable)
            )
            widths.append(Decimal(len(decidable)))

        if not scores:
            continue
        result.pairs.append(
            PairOverlap(
                left=left, right=right, sessions=len(scores),
                median=_percentile(scores, 50),
                p10=_percentile(scores, 10),
                minimum=min(scores),
                mean_decidable=sum(widths, Decimal(0)) / len(widths),
            )
        )

    for name in names:
        sizes = [Decimal(len(day.selected[name])) for day in daily]
        result.mean_selected[name] = sum(sizes, Decimal(0)) / len(sizes)
        skipped = [Decimal(len(day.undecided[name])) for day in daily]
        result.undecided_rate[name] = (
            sum(skipped, Decimal(0)) / (len(skipped) * instruments) if instruments else Decimal(0)
        )

    return result
