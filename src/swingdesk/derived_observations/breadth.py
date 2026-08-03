"""Market breadth: the share of a universe trading above its own moving average.

Course grounding: M31-T0459 `Доля акций выше средних`, and M31-T0457 `Рыночная ширина`. Both are
Definitions in the Derived Observations layer, and neither supplies a period or a threshold.

This is the one market-level measure this project can compute honestly on free data. Advance-decline
data (M31-T0458) needs exchange-level issue counts nobody serves free, and index membership needs a
point-in-time constituent list that does not exist for us (`DR-003`). The share of *our own
universe* above its own average needs nothing beyond the bars already fetched - which also means it
describes the universe rather than the market, and that distinction is stated rather than blurred.

Cross-sectional, so the record carries a **universe identifier** rather than a tradable instrument
id. `ObservationSeries` is per-instrument by contract; using it here keeps the component id, version
and parameter provenance travelling with the number, which is the whole point of the record, at the
cost of an id that names an aggregate. The alternative - a bare list of floats - loses the trace.

Pure. No I/O, no clock.

ALGORITHM_SPEC record:
  inputs           daily bars for every universe member, field close; one SMA series per member
  formula          count(close > SMA) / count(members with a warmed-up SMA), per session
  parameters       the SMA period, supplied by the caller
  units            fraction in [0, 1]
  output_range     [0, 1]
  timeframe        daily
  session rules    a session is measured only over members that traded it
  warm-up          no value until at least `min_members` members have a warmed-up SMA
  missing data     a member absent from a session is excluded from that session's denominator,
                   never counted as below its average
  time alignment   the value for session T uses data at T and is emitted at T
  version          1
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from swingdesk.contracts.component import ComponentSpec
from swingdesk.contracts.market import BarSeries
from swingdesk.contracts.observation import ObservationSeries

SPEC = ComponentSpec(
    component="M31-T0459-v5.0", name="Share of stocks above their averages", version=1,
    validation="Not Applicable", units="fraction",
)
SPECS = (SPEC,)

COMPONENT = SPEC.component
VERSION = SPEC.version
VALIDATION = SPEC.validation
UNITS = SPEC.units


@dataclass(frozen=True, slots=True)
class BreadthPoint:
    """One session's reading, with the denominator it was computed over.

    `members` is not decoration. A breadth of 0.6 over five members and over sixty are different
    claims, and a series that reports only the ratio hides which one it is making.
    """

    session_date: date
    value: Decimal | None
    members: int


def above_average(
    series_by_instrument: dict[str, BarSeries],
    sma_by_instrument: dict[str, ObservationSeries],
    *,
    min_members: int = 10,
) -> tuple[BreadthPoint, ...]:
    """Share of members closing above their own SMA, per session, ascending.

    A member whose SMA has not warmed up is excluded from BOTH numerator and denominator. Counting
    it as "not above" would report a market as broadly weak whenever many members were young, which
    is a statement about listing dates rather than about breadth.
    """
    if min_members < 1:
        raise ValueError(f"min_members must be >= 1, got {min_members}")

    sessions: set[date] = set()
    for series in series_by_instrument.values():
        sessions.update(bar.session_date for bar in series.bars)

    # Position lookups once, rather than scanning each series per session.
    positions = {
        instrument_id: {bar.session_date: index for index, bar in enumerate(series.bars)}
        for instrument_id, series in series_by_instrument.items()
    }

    points: list[BreadthPoint] = []
    for session in sorted(sessions):
        above = 0
        counted = 0
        for instrument_id, series in series_by_instrument.items():
            index = positions[instrument_id].get(session)
            if index is None:
                continue
            sma = sma_by_instrument.get(instrument_id)
            if sma is None:
                continue
            average = sma.observations[index].value
            if average is None:
                continue
            counted += 1
            if series.bars[index].close > average:
                above += 1

        value = Decimal(above) / Decimal(counted) if counted >= min_members else None
        points.append(BreadthPoint(session_date=session, value=value, members=counted))

    return tuple(points)
