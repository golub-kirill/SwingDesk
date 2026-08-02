"""Swing pivots: the previous high and the previous low, as structure rather than as extremes.

Course grounding, M12-T0201 `Предыдущий максимум` and M12-T0202 `Предыдущий минимум`, both
Operational Course Rule, layer Derived Observations. The definition that constrains the
implementation:

    "Признак отмечается как зона или структура, подтверждается завершёнными барами и обязательно
    сопровождается альтернативным сценарием."

`подтверждается завершёнными барами` - confirmed by completed bars. That single clause is the whole
design, and it is the difference between a correct pivot detector and a look-ahead bug that survives
every unit test.

A swing high at bar T is only knowable once `right` further bars have completed and none exceeded
it. A detector that marks the pivot at T and lets a caller read it at T has used bars T+1..T+right to
make a decision dated T. The equity curve that results is excellent and imaginary.

So this component emits at the CONFIRMATION bar, not at the pivot bar. The value appears at
T + right, and the pivot's own date is recoverable by subtracting `right` sessions - a caller reading
the series at any bar sees only what was confirmed by then, by construction rather than by
discipline.

Pure. No I/O, no clock (ARCHITECTURE 3).

ALGORITHM_SPEC record:
  inputs           daily bars, fields high and low
  formula          bar P is a swing high when high[P] > high[P-left..P-1] and
                   high[P] >= high[P+1..P+right]; mirrored for lows
  parameters       left, right - supplied by the caller
  units            price units
  output_range     [min low, max high] over the window
  timeframe        any single interval; not mixed
  session rules    regular hours only, exchange calendar per instrument
  warm-up          left + right + 1 bars before the first confirmation is possible
  missing data     a bar absent from the series shortens the neighbourhood; incomplete sessions are
                   excluded upstream and never reach here
  time alignment   emitted at the CONFIRMATION bar P + right, never at P
  version          1
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from swingdesk.contracts.component import ComponentSpec
from swingdesk.contracts.market import BarSeries
from swingdesk.contracts.observation import Observation, ObservationSeries, ParameterUse

SWING_HIGH = ComponentSpec(
    component="M12-T0201-v5.0", name="Previous high", version=1,
    validation="Not Applicable", units="price units",
)
SWING_LOW = ComponentSpec(
    component="M12-T0202-v5.0", name="Previous low", version=1,
    validation="Not Applicable", units="price units",
)
SPECS = (SWING_HIGH, SWING_LOW)


@dataclass(frozen=True, slots=True)
class Pivot:
    """One confirmed swing point.

    `index` is where it happened; `confirmed_index` is where it became knowable. Decision logic must
    only ever read pivots whose `confirmed_index` is at or before the bar being decided.
    """

    index: int
    confirmed_index: int
    price: Decimal
    is_high: bool


def _is_swing(values: list[Decimal], pivot: int, left: int, right: int, high: bool) -> bool:
    """Strict on the left, non-strict on the right.

    Ties matter more than they look. With both sides strict, a flat double top registers no pivot at
    all and the structure disappears; with both non-strict, every bar of a flat stretch registers one
    and the structure becomes noise. Strict-left/non-strict-right keeps exactly the first bar of a
    plateau, which is the one that actually marked the level.
    """
    value = values[pivot]
    for offset in range(1, left + 1):
        other = values[pivot - offset]
        if (other >= value) if high else (other <= value):
            return False
    for offset in range(1, right + 1):
        other = values[pivot + offset]
        if (other > value) if high else (other < value):
            return False
    return True


def pivots(series: BarSeries, left: int, right: int, *, highs: bool = True) -> tuple[Pivot, ...]:
    """Every confirmed swing point in the series, ascending by confirmation.

    Returns structured data for decision logic. `compute` wraps the same result as the boundary
    record.
    """
    if left < 1 or right < 1:
        raise ValueError(f"left and right must both be >= 1, got left={left}, right={right}")

    values = [bar.high if highs else bar.low for bar in series.bars]
    found: list[Pivot] = []
    for index in range(left, len(values) - right):
        if _is_swing(values, index, left, right, highs):
            found.append(
                Pivot(
                    index=index,
                    confirmed_index=index + right,
                    price=values[index],
                    is_high=highs,
                )
            )
    return tuple(found)


def compute(
    series: BarSeries,
    left: int,
    right: int,
    left_parameter: ParameterUse,
    right_parameter: ParameterUse,
    *,
    highs: bool = True,
) -> ObservationSeries:
    """The most recent confirmed swing price, carried forward, emitted at the confirmation bar.

    Carried forward rather than emitted once: `Предыдущий максимум` is a level that stays relevant
    until a newer one replaces it, and a series that is empty on every bar but a handful is unusable
    as an input. Before the first confirmation the value is None - there is no previous high yet, and
    a component does not invent one (ALGORITHM_SPEC 3).
    """
    spec = SWING_HIGH if highs else SWING_LOW
    confirmed = {pivot.confirmed_index: pivot.price for pivot in pivots(series, left, right, highs=highs)}

    observations: list[Observation] = []
    current: Decimal | None = None
    for index, bar in enumerate(series.bars):
        if index in confirmed:
            current = confirmed[index]
        observations.append(
            Observation(
                component=spec.component,
                component_version=spec.version,
                instrument_id=series.instrument_id,
                event_time=bar.event_time,
                value=current,
                units=spec.units,
                knowledge_time=series.knowledge_time,
            )
        )

    return ObservationSeries(
        component=spec.component,
        component_version=spec.version,
        instrument_id=series.instrument_id,
        units=spec.units,
        parameters=(left_parameter, right_parameter),
        validation_status=spec.validation,
        knowledge_time=series.knowledge_time,
        observations=tuple(observations),
    )


def warm_up_bars(left: int, right: int) -> int:
    """Bars before a first confirmation is even possible."""
    return left + right + 1
