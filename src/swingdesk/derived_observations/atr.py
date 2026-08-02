"""Average True Range (Wilder).

A pure function over a BarSeries. No I/O, no clock, no journal - this package is the purity
boundary (ARCHITECTURE 3), and everything downstream depends on it holding.

Course grounding: ATR is named across M18, M27 and M48, described as measuring the typical true
range and explicitly not direction. The course gives no period, no smoothing method and no
computation, so the definition here is Wilder's and the period is an assumed parameter carrying
that citation.

ALGORITHM_SPEC record:
  inputs           adjusted daily bars, fields high/low/close
  formula          TR = max(H-L, |H-Cprev|, |L-Cprev|); ATR = Wilder RMA of TR over `period`
  parameters       atr.period
  units            price units (same currency as the instrument)
  output_range     [0, inf)
  timeframe        any single interval; not mixed
  session rules    regular hours only, exchange calendar per instrument
  warm-up          period + 1 bars (the first TR needs a previous close)
  missing data     a bar absent from the series shortens the window; sessions failing the
                   completeness check are excluded upstream and never reach here
  time alignment   the value for bar T uses bars <= T and is emitted at T
  version          1
"""

from __future__ import annotations

from decimal import Decimal

from swingdesk.contracts.market import BarSeries
from swingdesk.contracts.observation import Observation, ObservationSeries, ParameterUse
from swingdesk.platform.parameters import ParameterRegistry

COMPONENT = "M18-T0280-v5.0"
VERSION = 1
UNITS = "price units"


def true_range(high: Decimal, low: Decimal, previous_close: Decimal) -> Decimal:
    """Wilder's true range: the largest of the three candidate ranges.

    The previous close matters because a gap is real range that the bar's own high-low misses.
    """
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


def compute(series: BarSeries, registry: ParameterRegistry) -> ObservationSeries:
    """ATR over `series`.

    Emits no value until warm-up completes. A partially-warmed average looks exactly like a valid
    one downstream, so the component declines rather than emitting something plausible
    (ALGORITHM_SPEC 3).

    Raises ParameterUnset if `atr.period` has no value - the component refuses rather than
    assuming a default.
    """
    period, parameter = registry.int_value("atr.period")
    if period < 1:
        raise ValueError(f"atr.period must be >= 1, got {period}")

    observations: list[Observation] = []
    ranges: list[Decimal] = []
    average: Decimal | None = None

    for index, bar in enumerate(series.bars):
        if index == 0:
            observations.append(_empty(series, bar))
            continue

        ranges.append(true_range(bar.high, bar.low, series.bars[index - 1].close))

        if len(ranges) < period:
            observations.append(_empty(series, bar))
            continue

        if average is None:
            # Wilder seeds with a simple mean of the first `period` true ranges, then smooths.
            average = sum(ranges[:period], Decimal(0)) / period
        else:
            average = (average * (period - 1) + ranges[-1]) / period

        observations.append(
            Observation(
                component=COMPONENT,
                component_version=VERSION,
                instrument_id=series.instrument_id,
                event_time=bar.event_time,
                value=average,
                units=UNITS,
                knowledge_time=series.knowledge_time,
            )
        )

    return ObservationSeries(
        component=COMPONENT,
        component_version=VERSION,
        instrument_id=series.instrument_id,
        units=UNITS,
        parameters=(parameter,),
        validation_status="Untested",
        knowledge_time=series.knowledge_time,
        observations=tuple(observations),
    )


def warm_up_bars(registry: ParameterRegistry) -> int:
    """Bars required before the first value. Used to check universe eligibility."""
    period, _ = registry.int_value("atr.period")
    return period + 1


def _empty(series: BarSeries, bar) -> Observation:  # noqa: ANN001 - Bar, avoiding a cycle
    return Observation(
        component=COMPONENT,
        component_version=VERSION,
        instrument_id=series.instrument_id,
        event_time=bar.event_time,
        value=None,
        units=UNITS,
        knowledge_time=series.knowledge_time,
    )
