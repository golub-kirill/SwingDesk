"""Effective spread recovered from daily OHLC, so the cost model can be measured instead of assumed.

`costs.slippage_model` was `assumed` at 5bps per side (DR-004) while PR-005's verdict on the base
strategy moved from "flat" at 1x costs to "clearly negative" at 3x - so the sign of the project's
headline result sat inside an unmeasured number. This module is what replaced it: DR-005 sets 25bps
per side from the figures these estimators produce.

They recover the spread from daily high, low and close alone, needing no intraday quotes - which no
free tier serves point-in-time. DR-004 had rejected spread-derived slippage as "correct and
unavailable" for exactly that reason, and the rejection held for quotes while missing that a daily
bar carries the same information more cheaply.

  Corwin & Schultz (2012)   from the two-day high-low range
  Abdi & Ranaldo (2017)     from the close against the mid-range

Both estimate the PROPORTIONAL EFFECTIVE SPREAD, S = (ask - bid) / mid. A fill at the touch pays
half of S per side, and per-side is what `costs.slippage_model` holds. Getting that factor backwards
is a 2x error in a number sitting underneath every R in the system, so the conversion is named here
and performed in one place - `per_side_bps`.

Two estimators rather than one, because a single estimator cannot be checked. They share a sample
and differ in method, so where they disagree the disagreement is the finding.

They are not equally good, and `tests/test_spread.py` measures it on a series whose spread is known
by construction:

  * on a ZERO-spread series Abdi-Ranaldo reads zero and Corwin-Schultz reads a full spread near
    0.0053 - 27bps per side. Flooring negative two-day estimates at zero leaves a positive residue
    that no amount of sample removes.
  * on a name that GAPS every session, Corwin-Schultz loses a real 2% spread entirely - even with
    the overnight adjustment applied - because the enlarged two-day range makes almost every pair
    negative. Abdi-Ranaldo reads through it.

So Abdi-Ranaldo is the estimator to build a cost model from and Corwin-Schultz is the cross-check,
not the other way round. A cost model built on Corwin-Schultz alone would price the cheapest names
above their true spread and gapping ones as free to trade.

Pure: no I/O, no randomness, and no registry read. A study pins its own values and records them, so
a reported result cannot change meaning when a parameter is later ratified
(`validation/backtest/costs.py`).

Decimal at a declared precision throughout. `Decimal.ln`, `.exp` and `.sqrt` are correctly rounded
to the active context, so the same input yields the same digits anywhere; the `math` equivalents
carry platform float behaviour, which DETERMINISM_SPEC 4 names as the limit of reproducibility.
Nothing here aggregates enough terms for that to cost anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import StrEnum
from itertools import pairwise

from swingdesk.contracts.market import Bar

#: Working precision for ln / exp / sqrt. Well beyond what a spread estimate means - the point is
#: that it is DECLARED here rather than inherited from whatever context a caller happens to run in,
#: which is what makes two runs comparable.
PRECISION = 34

#: Reported percentiles. Nearest-rank (see `_percentile`), so they are order statistics the
#: population actually contains.
PERCENTILES = (10, 25, 50, 75, 90)


class NegativeRule(StrEnum):
    """What to do with a negative two-day Corwin-Schultz estimate.

    Roughly a third of pairs come back negative on real data. That is the estimator's known
    small-sample behaviour, not a defect: a spread cannot be negative, but an estimate of one can.
    Both treatments appear in the literature and they do not agree, so the choice is recorded with
    the result rather than buried.
    """

    ZERO = "zero"
    """Set to zero, then average. The paper's own treatment. Biases the mean upward."""

    DISCARD = "discard"
    """Drop the pair. Biases upward harder, since only positive noise survives."""


@dataclass(frozen=True, slots=True)
class SpreadEstimate:
    """What one instrument's daily bars say about its spread.

    Both figures are proportional spreads, not basis points and not per-side. `per_side_bps`
    converts.
    """

    instrument_id: str
    pairs_used: int
    pairs_skipped: int
    negative_pairs: int
    corwin_schultz: Decimal | None
    corwin_schultz_mean: Decimal | None
    abdi_ranaldo: Decimal | None

    @property
    def negative_fraction(self) -> Decimal:
        """Share of usable pairs that produced a negative Corwin-Schultz estimate.

        Reported because it is the estimator's own noise gauge: a name where most pairs come back
        negative has not measured a small spread, it has failed to measure anything.
        """
        if self.pairs_used == 0:
            return Decimal(0)
        return Decimal(self.negative_pairs) / Decimal(self.pairs_used)


@dataclass(frozen=True, slots=True)
class Summary:
    """Population percentiles across instruments. Empty mappings when nothing could be estimated.

    Corwin-Schultz appears twice for the same reason it does on `SpreadEstimate`: the two
    aggregations disagree materially, and a summary carrying only one of them would let a reader
    check a conclusion against a number that was not the one used to reach it.
    """

    instruments: int
    estimated: int
    corwin_schultz: dict[int, Decimal]
    corwin_schultz_mean: dict[int, Decimal]
    abdi_ranaldo: dict[int, Decimal]


def per_side_bps(spread: Decimal) -> Decimal:
    """Per-side slippage in basis points, from a proportional effective spread.

    S is the full spread. A buyer lifting the offer pays half of it away from the mid and a seller
    hitting the bid pays the other half, so a round trip costs S and one side costs S/2. This is the
    single conversion between what these estimators measure and what a backtest charges, and it is
    the step most likely to be got wrong by a factor of two.
    """
    with localcontext() as context:
        context.prec = PRECISION
        return spread / Decimal(2) * Decimal(10_000)


def corwin_schultz_pair(
    previous: Bar, current: Bar, *, adjust_overnight: bool = True
) -> Decimal | None:
    """One two-day estimate of S, or None when the pair cannot carry one.

    Returns the raw estimate, negative values included. What to do with those belongs to the
    aggregator and its `NegativeRule`, not here - an estimator that silently floors its own output
    cannot be measured for bias.

    `adjust_overnight` applies the paper's correction. When two sessions do not overlap, the gap
    between them is a price change rather than a cost of trading, and leaving it inside the two-day
    range inflates every estimate on a gapping name. It is switchable only so that a test can
    demonstrate the correction matters.
    """
    if not _usable(previous) or not _usable(current):
        return None

    with localcontext() as context:
        context.prec = PRECISION

        high_previous, low_previous = previous.high, previous.low
        high_current, low_current = current.high, current.low

        if adjust_overnight:
            if low_current > high_previous:
                gap = low_current - high_previous
                high_current, low_current = high_current - gap, low_current - gap
            elif high_current < low_previous:
                gap = low_previous - high_current
                high_current, low_current = high_current + gap, low_current + gap

        beta = (high_previous / low_previous).ln() ** 2 + (high_current / low_current).ln() ** 2
        gamma = (max(high_previous, high_current) / min(low_previous, low_current)).ln() ** 2

        # 3 - 2*sqrt(2), the constant the paper's variance ratio collapses to.
        scale = Decimal(3) - Decimal(2) * Decimal(2).sqrt()
        alpha = ((Decimal(2) * beta).sqrt() - beta.sqrt()) / scale - (gamma / scale).sqrt()

        exp_alpha = alpha.exp()
        return Decimal(2) * (exp_alpha - Decimal(1)) / (Decimal(1) + exp_alpha)


def abdi_ranaldo_pair_squared(previous: Bar, current: Bar) -> Decimal | None:
    """One two-day estimate of S SQUARED - not S, and the difference is load-bearing.

    The estimator is an expectation: E[4 (c - eta_t)(c - eta_t+1)] = S^2, where c is the log close
    of the earlier day and eta the log mid-range. Individual products are negative about as often as
    not, so taking a square root pair by pair would discard every negative one and bias the answer
    upward. `estimate_instrument` averages the products first and roots once, which is the estimator
    the paper actually proposes.
    """
    if not _usable(previous) or not _usable(current):
        return None

    with localcontext() as context:
        context.prec = PRECISION
        eta_previous = (previous.high.ln() + previous.low.ln()) / Decimal(2)
        eta_current = (current.high.ln() + current.low.ln()) / Decimal(2)
        close = previous.close.ln()
        return Decimal(4) * (close - eta_previous) * (close - eta_current)


def estimate_instrument(
    bars: Sequence[Bar],
    *,
    negative_rule: NegativeRule = NegativeRule.ZERO,
    adjust_overnight: bool = True,
) -> SpreadEstimate | None:
    """Both estimators over one instrument's consecutive daily bars, or None if none are usable.

    Corwin-Schultz is reported twice. The MEAN is the paper's own estimator and the one carrying the
    theoretical identity; the MEDIAN is the robust companion, because the per-pair distribution is
    heavy-tailed enough that a handful of pairs move a mean. Both travel with the result so the
    difference between them is visible rather than assumed away - where they diverge, the sample is
    telling you the estimator is struggling on that name.

    Abdi-Ranaldo is aggregated by mean-then-root, because its identity holds in expectation over the
    product and in no other order. There is no median form of it to report.
    """
    if len(bars) < 2:
        return None

    corwin_schultz: list[Decimal] = []
    products: list[Decimal] = []
    skipped = 0
    negatives = 0

    for previous, current in pairwise(bars):
        pair = corwin_schultz_pair(previous, current, adjust_overnight=adjust_overnight)
        product = abdi_ranaldo_pair_squared(previous, current)
        if pair is None or product is None:
            skipped += 1
            continue

        # Both estimators run on exactly the same pairs. Where they then disagree, the disagreement
        # is about method rather than about which sessions each one happened to see.
        products.append(product)

        if pair < 0:
            negatives += 1
            if negative_rule is NegativeRule.DISCARD:
                continue
            pair = Decimal(0)
        corwin_schultz.append(pair)

    if not products:
        return None

    with localcontext() as context:
        context.prec = PRECISION
        # Summed in chronological order, which is fixed by the caller's series - an aggregation
        # whose order varies is a determinism hazard (DETERMINISM_SPEC 3.2).
        mean_product = sum(products, Decimal(0)) / Decimal(len(products))
        abdi_ranaldo = mean_product.sqrt() if mean_product > 0 else Decimal(0)
        mean_corwin_schultz = (
            sum(corwin_schultz, Decimal(0)) / Decimal(len(corwin_schultz))
            if corwin_schultz
            else None
        )

    return SpreadEstimate(
        instrument_id=bars[0].instrument_id,
        pairs_used=len(products),
        pairs_skipped=skipped,
        negative_pairs=negatives,
        corwin_schultz=_percentile(corwin_schultz, 50) if corwin_schultz else None,
        corwin_schultz_mean=mean_corwin_schultz,
        abdi_ranaldo=abdi_ranaldo,
    )


def summarise(estimates: Sequence[SpreadEstimate]) -> Summary:
    """Population percentiles across instruments, each estimator and aggregation independently."""

    def percentiles(values: list[Decimal]) -> dict[int, Decimal]:
        return {p: _percentile(values, p) for p in PERCENTILES} if values else {}

    abdi_ranaldo = [e.abdi_ranaldo for e in estimates if e.abdi_ranaldo is not None]
    return Summary(
        instruments=len(estimates),
        estimated=len(abdi_ranaldo),
        corwin_schultz=percentiles(
            [e.corwin_schultz for e in estimates if e.corwin_schultz is not None]
        ),
        corwin_schultz_mean=percentiles(
            [e.corwin_schultz_mean for e in estimates if e.corwin_schultz_mean is not None]
        ),
        abdi_ranaldo=percentiles(abdi_ranaldo),
    )


def _usable(bar: Bar) -> bool:
    """Whether a bar can carry an estimate at all.

    A zero-range session is excluded rather than read as a zero spread: a high equal to its low is a
    halt, a limit lock or a name that barely traded, and it says nothing about the cost of crossing
    a spread. Non-positive prices cannot be logged.
    """
    return bar.low > 0 and bar.high > bar.low


def _percentile(values: Sequence[Decimal], percent: int) -> Decimal:
    """Nearest-rank percentile. One definition, no interpolation, exact on Decimals.

    Interpolating between two order statistics invents a value no instrument has. The competing
    definitions differ by a rank at small n, which is exactly the size at which someone would
    re-derive a number and get a different one.
    """
    ordered = sorted(values)
    rank = -(-percent * len(ordered) // 100)
    return ordered[max(0, min(len(ordered) - 1, rank - 1))]


__all__ = [
    "PERCENTILES",
    "PRECISION",
    "NegativeRule",
    "SpreadEstimate",
    "Summary",
    "abdi_ranaldo_pair_squared",
    "corwin_schultz_pair",
    "estimate_instrument",
    "per_side_bps",
    "summarise",
]
