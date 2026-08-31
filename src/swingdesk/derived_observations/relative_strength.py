"""Relative strength against a benchmark: the RS line. `M31-T0464`.

The course names three indexes as Definitions - S&P 500, Nasdaq-100, Russell 2000 - and then names
*relative strength against the index* as a Derived Observation. This is that observation: the ratio
of an instrument's close to the benchmark's, rebased to 1.0 at the first session they share, which
is the RS line as every chart draws it.

**Why the RATIO and not a windowed change.** The ratio is the observation; a change in it over a
lookback is a *reading* of the observation, and readings belong to whatever consumes them. Keeping
the component parameter-free is not a convenience - a component with no unset parameter is one that
can never refuse for want of a value, and `rs.lookback` genuinely belongs to the ranking that
measures a change rather than to the line itself.

**What this component CANNOT do, stated here because the misuse is natural.** Ranking a
cross-section by this value on one date is identical to ranking by raw price change over the same
window: the benchmark's return is one constant for every name that day, so dividing by it is a
strictly monotone transform. `DR-018` §1 measured that at Spearman **1.000000** across 15 benchmark
x lookback pairs over 1,148 names, and `tests/test_ranking.py` pins it. The RS line is a legitimate
thing to look at and a decorative thing to sort by.

**Rebasing is a display choice and it is recorded as one.** Dividing by the first shared session's
ratio makes two instruments comparable on a chart and changes nothing about the shape. It does not
make the level meaningful: an RS line of 1.4 says "up 40% relative to the benchmark since the window
opened", never "strong".

ALGORITHM_SPEC record:
  inputs           raw daily bars for the instrument and for the benchmark, field close
  formula          RS(t) = (close(t) / benchmark_close(t)) / (close(t0) / benchmark_close(t0)),
                   where t0 is the first session both series hold
  parameters       none. The benchmark is an INPUT, chosen by rs.benchmark (DR-018), not a
                   threshold this component reads
  units            ratio (dimensionless), 1.0 at t0
  output_range     (0, inf)
  timeframe        any single interval; instrument and benchmark must share it
  session rules    sessions the two series do not share emit no value - a benchmark that did not
                   trade cannot be a denominator, and carrying the previous one forward would
                   invent a comparison
  warm-up          none beyond the first shared session
  missing data     a session present for one series and absent for the other yields an empty
                   observation, never an interpolated one
  time alignment   the value for session T uses closes at T only, and is emitted at T
  version          1
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from swingdesk.contracts.component import ComponentSpec
from swingdesk.contracts.market import Bar, BarSeries
from swingdesk.contracts.observation import Observation, ObservationSeries

#: Mirrored from registry/course_index.yml, which is generated and must not be hand-edited
#: (COMPONENT_REGISTRY_SPEC 2). `validation` is "Not Applicable" because a ratio of two prices is
#: arithmetic - there is nothing here for a study to accept or refute. The HYPOTHESIS that ordering
#: by it predicts anything is M31-T0465, a separate component the course itself flags as untested.
SPEC = ComponentSpec(
    component="M31-T0464-v5.0", name="Relative strength vs index", version=1,
    validation="Not Applicable", units="ratio",
)

#: ONE component row, and the constraint is not this module's preference. `M77-T1138` is the same
#: measure at the Setup stage and it is deliberately NOT claimed here: Production Rules 3.8 forbids
#: two components sharing one definition, and gate 11 enforces it - the first version of this file
#: claimed both rows and the gate refused. Whether M77-T1138 names something genuinely distinct is
#: a question for the source PDFs, which are not in this repository; until someone reads them it
#: stays `registered`, which is the honest state for a row nobody has implemented.
SPECS = (SPEC,)

COMPONENT = SPEC.component
VERSION = SPEC.version
VALIDATION = SPEC.validation
UNITS = SPEC.units


def _empty(series: BarSeries, bar: Bar) -> Observation:
    return Observation(
        component=COMPONENT, component_version=VERSION, instrument_id=series.instrument_id,
        event_time=bar.event_time, value=None, units=UNITS,
        knowledge_time=series.knowledge_time,
    )


def compute(series: BarSeries, benchmark: BarSeries) -> ObservationSeries:
    """The RS line for `series` against `benchmark`, rebased to 1.0 at their first shared session.

    Emits an empty observation for any session the benchmark does not hold. That is the
    `unavailable`-is-not-`fail` rule at the level of a single bar: a missing denominator makes the
    comparison unanswerable, and carrying the previous benchmark close forward would answer it with
    a number nobody measured.

    Takes no `ParameterRegistry` and cannot refuse for want of a value - see the module docstring.
    The benchmark is an argument because WHICH benchmark is `DR-018`'s decision and this component
    should not be able to disagree with it.
    """
    if series.interval is not benchmark.interval:
        raise ValueError(
            f"interval mismatch: {series.interval} against {benchmark.interval}. An RS line over "
            f"two timeframes compares nothing."
        )

    closes: dict[date, Decimal] = {
        bar.session_date: bar.close for bar in benchmark.bars if bar.close > 0
    }

    base: Decimal | None = None
    observations: list[Observation] = []
    for bar in series.bars:
        denominator = closes.get(bar.session_date)
        if denominator is None or bar.close <= 0:
            observations.append(_empty(series, bar))
            continue

        ratio = bar.close / denominator
        if base is None:
            base = ratio
        observations.append(
            Observation(
                component=COMPONENT, component_version=VERSION,
                instrument_id=series.instrument_id, event_time=bar.event_time,
                value=ratio / base, units=UNITS, knowledge_time=series.knowledge_time,
            )
        )

    return _series_of(series, tuple(observations))


def latest(series: BarSeries, benchmark: BarSeries) -> ObservationSeries:
    """The RS line's LAST value and only that - the same definition, evaluated at one point.

    **Identical to `compute(series, benchmark).observations[-1]`, and a test proves it** rather than
    this docstring asserting it. The formula, the rebasing and the missing-denominator rule are
    `compute`'s; nothing is redefined here. What changes is that 2,516 `Observation` objects are not
    built to use one.

    **Measured 2026-08-30 on the live universe, which is why this exists.** `compute` over 1,186
    candidates against a 2,516-bar benchmark took **41.8 seconds** and produced 2.6 million
    observations, of which the run reads 1,186 - the last one per candidate. `DR-024` §7 named run
    duration as its own overturning condition and this is it: 41.8s against a six-minute pass is
    about 12% of the evening, spent building objects nobody reads. The same values cost **2.2s**
    here.

    **The empty-observation case is the whole reason this is not a two-line loop.** `compute` emits
    an observation for EVERY bar, so its last one is the observation for the series' last BAR - and
    that is empty when the benchmark has no session for it, which happens whenever the benchmark is
    one session behind the candidate. A "last non-empty value" shortcut is faster still, returns a
    different number, and would differ only on the days a stale benchmark makes it matter.

    `compute` remains the component's canonical form: it is the RS LINE, and a caller that wants the
    line rather than today's reading should keep using it.
    """
    if series.interval is not benchmark.interval:
        raise ValueError(
            f"interval mismatch: {series.interval} against {benchmark.interval}. An RS line over "
            f"two timeframes compares nothing."
        )
    if not series.bars:
        return _series_of(series, ())

    closes: dict[date, Decimal] = {
        bar.session_date: bar.close for bar in benchmark.bars if bar.close > 0
    }

    # The base is the FIRST shared session's ratio, so the search stops at the first hit rather
    # than walking the history the way `compute` must.
    base: Decimal | None = None
    for bar in series.bars:
        denominator = closes.get(bar.session_date)
        if denominator is None or bar.close <= 0:
            continue
        base = bar.close / denominator
        break

    final = series.bars[-1]
    denominator = closes.get(final.session_date)
    if base is None or denominator is None or final.close <= 0:
        return _series_of(series, (_empty(series, final),))

    return _series_of(series, (
        Observation(
            component=COMPONENT, component_version=VERSION, instrument_id=series.instrument_id,
            event_time=final.event_time, value=(final.close / denominator) / base, units=UNITS,
            knowledge_time=series.knowledge_time,
        ),
    ))


def _series_of(series: BarSeries, observations: tuple[Observation, ...]) -> ObservationSeries:
    """The wrapper both entry points return, so the two cannot drift on anything but the values."""
    return ObservationSeries(
        component=COMPONENT, component_version=VERSION, instrument_id=series.instrument_id,
        units=UNITS, parameters=(), validation_status=VALIDATION,
        knowledge_time=series.knowledge_time, observations=observations,
    )


__all__ = ["COMPONENT", "SPEC", "SPECS", "UNITS", "VALIDATION", "VERSION", "compute", "latest"]
