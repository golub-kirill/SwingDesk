"""Market data: bars and bar series.

Bars are the high-volume record (~20M rows, NFR 1). Validating each individually would cost more
than it protects, so `BarSeries` is the boundary record and `Bar` describes one row of it. This is
the single place a contract governs a collection rather than a record, and it is deliberate
(docs/contracts/README.md 4).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Interval(StrEnum):
    """Stored bar resolutions. Each is fetched independently, never derived from another.

    Deriving 1h from 30m would cap hourly history at 60 trading days while ~725 are available
    (ADR-0001). 1Y / 3M / 30D are windows over daily bars, not resolutions, so they are absent here.
    """

    DAY = "1d"
    HOUR = "1h"
    HALF_HOUR = "30m"

    @property
    def minutes(self) -> int:
        return {"1d": 390, "1h": 60, "30m": 30}[self.value]

    @property
    def is_intraday(self) -> bool:
        return self is not Interval.DAY


class Series(StrEnum):
    """Raw and adjusted are stored separately and never derived from one another on read.

    A raw bar should never change; a change is a data-quality event, not a revision. Adjusted
    history is rewritten by every corporate action (POINT_IN_TIME_SPEC 4).

    `POINT_IN_TIME_SPEC` §4 names a third series, `actions`. It is deliberately NOT a member here:
    this enum labels OHLCV bars, and a split has no open, high, low or close. Modelling one as a
    `Bar` would mean inventing five fields to leave empty and a `volume` that means nothing, and the
    first component to read it would get numbers back. Corporate actions get their own record
    (`CorporateAction`) and their own table, which is what "with their own `knowledge_time`" in that
    row of the spec actually requires.
    """

    RAW = "raw"
    ADJUSTED = "adjusted"


class CorporateActionKind(StrEnum):
    """What the issuer did. Named `CorporateActionKind` rather than `ActionKind` because
    `contracts.position.ActionKind` already means "what the run proposes to do about a position",
    and two enums called `ActionKind` in one system is the §11 terminology failure waiting to
    happen."""

    SPLIT = "split"
    DIVIDEND = "dividend"


class CorporateAction(BaseModel):
    """One split or cash dividend, as the issuer declared it.

    **Why this exists, and it is the biggest unguarded risk in the system** (`DR-015` §4, `DR-016`).
    Both decision paths read `Series.RAW`, and raw bars are unadjusted - so a split does not restate
    history, it means the next bars arrive at a different price level. A 2:1 split over a weekend
    leaves a stored stop of 290 compared against Monday raw prices near 145: an instant stop-out
    that never happened, on a position still held. Measured on this store, nine split-shaped jumps
    landed on current universe members in one year.

    `value` carries the ratio for a split and the per-share cash amount for a dividend. One field
    rather than two nullable ones, because the kind already says which it is and a nullable pair
    invites reading the wrong one.

    Bitemporal like every other fact here: `effective_date` is when the action took effect,
    `knowledge_time` when we learned of it. A vendor that revises an action writes a new row.
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    kind: CorporateActionKind
    effective_date: date = Field(
        description="The EXCHANGE-LOCAL session the action took effect on. Stored, never derived "
                    "from a timestamp's date - the same rule and the same reason as `Bar."
                    "session_date` (CALENDAR_SPEC 6)."
    )
    value: Decimal = Field(gt=0, description="Split ratio, or cash per share for a dividend.")
    knowledge_time: datetime = Field(description="When this was learned. Timezone-aware.")

    @property
    def price_factor(self) -> Decimal:
        """What a pre-action raw price must be multiplied by to compare with a post-action one.

        A 2:1 split has `value` 2 and a factor of 1/2: a stop of 290 set before it corresponds to
        145 after. A dividend returns 1 - it moves the price by roughly its amount on the ex-date,
        but that is a market reaction rather than a restatement, and pretending otherwise would
        silently adjust stops for something the exchange did not re-denominate.
        """
        if self.kind is not CorporateActionKind.SPLIT:
            return Decimal(1)
        return Decimal(1) / self.value


class Bar(BaseModel):
    """One OHLCV bar.

    `event_time` is when the bar happened; `knowledge_time` is when we learned this version of it.
    A revision is a new row with a later knowledge_time, never an update.
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    interval: Interval
    series: Series
    event_time: datetime = Field(description="Bar open, timezone-aware.")
    session_date: date = Field(
        description="The EXCHANGE-LOCAL calendar date this bar belongs to.\n\n"
                    "Stored, never derived from event_time.date(). A timestamp's date depends on "
                    "the timezone it happens to carry, and storage layers convert: DuckDB returns "
                    "TIMESTAMPTZ in the local system timezone, so a 00:00 New York bar read back "
                    "on a UTC-5 machine reports the previous day. That silently misaligned every "
                    "session against the calendar until it was caught. The session a bar belongs "
                    "to is a fact (CALENDAR_SPEC 6), so it is stored as one."
    )
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0)
    knowledge_time: datetime = Field(description="When this value was learned. Timezone-aware.")

    @model_validator(mode="after")
    def _ohlc_consistent(self) -> Bar:
        """High must bound the bar and low must floor it.

        Cheap, and it catches vendor corruption at the boundary rather than three layers deep in an
        indicator. yfinance scrapes a consumer site, so its output is untrusted input
        (SECURITY 6).
        """
        if self.high < self.low:
            raise ValueError(f"high {self.high} < low {self.low}")
        if not (self.low <= self.open <= self.high):
            raise ValueError(f"open {self.open} outside [{self.low}, {self.high}]")
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"close {self.close} outside [{self.low}, {self.high}]")
        return self


class BarSeries(BaseModel):
    """A validated container for one instrument, interval and series over a window.

    The boundary record. Carries the window and the knowledge_time so a consumer cannot use it
    without knowing what it is looking at, or mistake a partial window for a complete one.
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    interval: Interval
    series: Series
    knowledge_time: datetime
    bars: tuple[Bar, ...]

    @model_validator(mode="after")
    def _ordered_and_consistent(self) -> BarSeries:
        """Bars are ascending by event_time, unique, and all belong to this series.

        Ordering is not cosmetic: unordered input feeding output is a named determinism hazard
        (DETERMINISM_SPEC 3.2), and enforcing it at the boundary means downstream code can rely on
        it rather than re-sorting defensively.
        """
        previous: datetime | None = None
        for bar in self.bars:
            if bar.instrument_id != self.instrument_id:
                raise ValueError(f"bar instrument {bar.instrument_id} != {self.instrument_id}")
            if bar.interval is not self.interval or bar.series is not self.series:
                raise ValueError("bar interval/series does not match the container")
            if previous is not None and bar.event_time <= previous:
                raise ValueError(f"bars not strictly ascending at {bar.event_time}")
            previous = bar.event_time
        return self

    def __len__(self) -> int:
        return len(self.bars)

    @property
    def session_dates(self) -> tuple[date, ...]:
        """Distinct session dates present, ascending.

        The completeness check used to read this and then ask `bars_on` for each date; it buckets
        the bars in one pass now, so this has no caller in `src/`. Kept because it states a real
        property of the container and the cost of keeping it is a docstring.
        """
        seen: dict[date, None] = {}
        for bar in self.bars:
            seen.setdefault(bar.session_date, None)
        return tuple(seen)

    def bars_on(self, session_date: date) -> tuple[Bar, ...]:
        """Every bar on one session. A LINEAR SCAN - never call it once per session date.

        The warning is here because the one caller that did cost 90 seconds of a 150-instrument
        run: a series spanning n sessions asked n times and paid O(n^2). Iterate `self.bars` once
        and bucket by `session_date` instead (`market_data/completeness.py` is the worked example).
        """
        return tuple(bar for bar in self.bars if bar.session_date == session_date)
