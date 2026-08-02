"""Simple moving average.

Course grounding: M25-T0382 `SMA`, claim type Derived Observation, layer Derived Observations. The
course names it and, as everywhere else, supplies no period - the period is a parameter of whatever
uses it, not of the component.

Pure, like everything in this package. No I/O, no clock (ARCHITECTURE 3).

ALGORITHM_SPEC record:
  inputs           daily bars, field close
  formula          mean of the last `period` closes, inclusive of the current bar
  parameters       supplied by the caller - SMA has no period of its own
  units            price units
  output_range     [min close, max close] over the window
  timeframe        any single interval; not mixed
  session rules    regular hours only, exchange calendar per instrument
  warm-up          `period` bars
  missing data     a bar absent from the series shortens the window; incomplete sessions are
                   excluded upstream and never reach here
  time alignment   the value for bar T uses bars <= T and is emitted at T
  version          1
"""

from __future__ import annotations

from decimal import Decimal

from swingdesk.contracts.market import BarSeries
from swingdesk.contracts.observation import Observation, ObservationSeries, ParameterUse

COMPONENT = "M25-T0382-v5.0"
VERSION = 1
UNITS = "price units"

#: The course's own validation status, mirrored from registry/course_index.yml and asserted by test.
VALIDATION = "Not Applicable"


def compute(series: BarSeries, period: int, parameter: ParameterUse) -> ObservationSeries:
    """SMA of close over `period`.

    The period arrives as a value plus its provenance rather than as a bare int, because a number
    that can lose its origin on the way to a report is a number that can be presented as a
    measurement (PARAMETER_REGISTRY 5). SMA is used by several callers with different periods, so
    it reads none from the registry itself.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")

    observations: list[Observation] = []
    running = Decimal(0)

    for index, bar in enumerate(series.bars):
        running += bar.close
        if index >= period:
            running -= series.bars[index - period].close

        value = running / period if index >= period - 1 else None
        observations.append(
            Observation(
                component=COMPONENT,
                component_version=VERSION,
                instrument_id=series.instrument_id,
                event_time=bar.event_time,
                value=value,
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
        validation_status="Not Applicable",
        knowledge_time=series.knowledge_time,
        observations=tuple(observations),
    )


def warm_up_bars(period: int) -> int:
    """Bars required before the first value. Unlike Wilder's ATR there is no seeding lag."""
    return period
