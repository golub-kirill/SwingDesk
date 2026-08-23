"""Correlation of daily returns, and the returns themselves (`M49-T0761`, `M51-T0781`).

The course names correlation twice - a correlation adjustment to size (`M49-T0761`) and correlation
between shares (`M51-T0781`) - and quantifies neither, so both the threshold and the window it is
measured over are authored (`DR-006` §2). This module supplies the statistic;
`trade_management.portfolio` decides what to do with it. That split follows the course's own
classification: the component registry files both topics under **Derived Observations**, and a
derived observation does not own a decision (`DEPENDENCY_LAW`).

Pure: no I/O, no clock, no registry. Bars are passed in, and the caller says how far back to look.

**Decimal, not float, and the reason is not money.** `DETERMINISM_SPEC` §3.3 records that
floating-point addition is not associative, so a sum over a window reproduces only if the order and
the arithmetic are both fixed. Returns here are exact ratios of exact prices, summed in a pinned
context, so a re-run of the same window returns the same digits rather than digits that depend on
what the platform rounds to.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, localcontext

from swingdesk.contracts.market import BarSeries

#: Arithmetic precision for every figure this module produces. Pinned rather than inherited: the
#: ambient decimal context is process-global mutable state, and a statistic whose last digits
#: depend on what some other module set is not reproducible in the sense `DETERMINISM_SPEC` §3
#: means. 28 is CPython's own default, so this changes nothing today and fixes it in place.
PRECISION = 28

#: Correlation is bounded on [-1, 1] by definition. Finite-precision arithmetic can land a hair
#: outside on a perfectly correlated pair, and an r of 1.000000000000000000000000003 would be a
#: true statement about the arithmetic and a false one about the world.
_ONE = Decimal(1)


@dataclass(frozen=True, slots=True)
class DailyReturn:
    """One close-to-close simple return, tagged with the session it closed."""

    session_date: date
    value: Decimal


def daily_returns(series: BarSeries) -> tuple[DailyReturn, ...]:
    """Close-to-close simple returns, oldest first, one per session after the first.

    `(close_t / close_prev) - 1`, exactly - not a log return. The two agree to first order and
    disagree in the tail, and the simple return is the one that composes with the position
    arithmetic everywhere else in this system.

    A non-positive previous close yields no return for that session rather than an exception or a
    zero. `Bar` validates OHLC consistency but does not require a positive price, and a vendor that
    served a zero close would otherwise divide by it - or, worse, contribute a fabricated 0.0%
    session to a window that is meant to hold real ones.
    """
    returns: list[DailyReturn] = []
    with localcontext(Context(prec=PRECISION)):
        previous: Decimal | None = None
        for bar in series.bars:
            if previous is not None and previous > 0:
                returns.append(DailyReturn(bar.session_date, (bar.close / previous) - _ONE))
            previous = bar.close
    return tuple(returns)


def pearson(left: Sequence[Decimal], right: Sequence[Decimal]) -> Decimal | None:
    """Pearson's r over two equal-length samples, or `None` when it is undefined.

    `None` is not zero and must never be read as "uncorrelated". A sample with no variance - a
    price that did not move across the whole window, which is what a halted or barely-traded
    instrument looks like - has no correlation with anything, because the denominator is zero.
    Returning zero there would report the strongest available evidence of independence from the
    weakest available data.
    """
    n = len(left)
    if n != len(right):
        raise ValueError(f"samples differ in length: {n} vs {len(right)}")
    if n < 2:
        return None

    with localcontext(Context(prec=PRECISION)):
        count = Decimal(n)
        mean_left = sum(left, Decimal(0)) / count
        mean_right = sum(right, Decimal(0)) / count

        covariance = Decimal(0)
        variance_left = Decimal(0)
        variance_right = Decimal(0)
        for a, b in zip(left, right, strict=True):
            deviation_left = a - mean_left
            deviation_right = b - mean_right
            covariance += deviation_left * deviation_right
            variance_left += deviation_left * deviation_left
            variance_right += deviation_right * deviation_right

        if variance_left <= 0 or variance_right <= 0:
            return None

        r = covariance / (variance_left.sqrt() * variance_right.sqrt())
        return max(-_ONE, min(_ONE, r))


@dataclass(frozen=True, slots=True)
class Measurement:
    """Correlation between two instruments over the sessions they share.

    `r is None` and `unavailable` always travel together: either the statistic exists, or the
    reason it does not does. A consumer reading only `r` cannot mistake a gap for independence,
    because there is no number there to mistake.
    """

    r: Decimal | None
    overlap: int
    """Sessions carrying a return on BOTH sides, after the lookback was applied."""

    unavailable: str | None = None

    @property
    def is_available(self) -> bool:
        return self.r is not None


def measure(
    left: Sequence[DailyReturn],
    right: Sequence[DailyReturn],
    lookback: int,
) -> Measurement:
    """Correlate two return streams over the last `lookback` sessions they share.

    **The window is the last `lookback` COMMON sessions, not the last `lookback` calendar
    sessions.** A halt, a late listing or a vendor gap on one side removes that session from the
    pair rather than from the window, so the statistic is always computed on the number of
    observations it claims. The alternative - intersecting a fixed slice - silently shortens the
    sample whenever one side has a hole, and a correlation over 41 sessions reported as one over 60
    is the kind of number this project counts as a defect rather than an approximation.

    **A short overlap is `unavailable`, never a pass.** The threshold `DR-006` §2 authored is
    defined over a stated window; measuring it over a shorter one measures something else and calls
    it by the same name. `DR-006` §3 is explicit that a check the system could not perform reports
    `unavailable` - and it is the caller's job not to turn that into a blanket refusal.
    """
    if lookback < 2:
        raise ValueError(f"lookback must be >= 2 sessions, got {lookback}")

    by_date = {item.session_date: item.value for item in right}
    shared = sorted(
        (
            (item.session_date, item.value, by_date[item.session_date])
            for item in left
            if item.session_date in by_date
        ),
        key=lambda row: row[0],
    )
    window = shared[-lookback:]

    if len(window) < lookback:
        return Measurement(
            r=None,
            overlap=len(window),
            unavailable=(
                f"{len(window)} session(s) of overlapping daily returns, and the threshold is "
                f"defined over {lookback}"
            ),
        )

    r = pearson([row[1] for row in window], [row[2] for row in window])
    if r is None:
        return Measurement(
            r=None,
            overlap=len(window),
            unavailable=(
                f"one side did not move across all {lookback} session(s), so correlation has no "
                f"denominator"
            ),
        )
    return Measurement(r=r, overlap=len(window))
