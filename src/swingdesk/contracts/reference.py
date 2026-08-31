"""Reference data: instruments and exchange sessions."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from swingdesk.contracts.market import Interval


class Exchange(StrEnum):
    """Exchanges in scope. USA and Canada are never merged (BR-9), which is why this is an
    enum rather than a free string - a typo cannot silently create a third market."""

    NYSE = "NYSE"
    TSX = "TSX"


class Instrument(BaseModel):
    """An instrument. Identity is `id`, never the ticker.

    Tickers get reused after a delisting, and we cannot detect reuse from price continuity because
    no free source serves delisted history (DATA_QUALITY_SPEC 3). The ticker is a label attached to
    the id, not the identity itself.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Internal stable identity. Never derived from the ticker alone.")
    ticker: str
    exchange: Exchange = Field(
        description="The SESSION CALENDAR this instrument trades on, not necessarily the venue "
                    "that lists it. NASDAQ and NYSE were measured identical over 2016-2026 - 2523 "
                    "sessions each, no one-sided session, no differing open or close - so both map "
                    "here and the listing venue is recorded separately."
    )
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217. Mandatory (BR-9).")
    listing_venue: str | None = Field(
        default=None,
        description="Where the symbol directory says it is listed: NASDAQ, NYSE Arca, IEX. "
                    "Reference metadata - nothing computes from it. Kept because collapsing it "
                    "into `exchange` would make the record assert something it never measured.",
    )
    sector: str | None = None
    industry: str | None = None

    @property
    def vendor_symbol(self) -> str:
        """The symbol Yahoo uses: TSX names carry a .TO suffix."""
        return self.ticker if self.exchange is not Exchange.TSX else f"{self.ticker}.TO"


class SectorWeight(BaseModel):
    """One sector's share of an instrument, as the vendor reports it.

    A fraction, not a percent: 0.374, never 37.4. The vendor serves fractions and converting at the
    boundary would put two conventions for one quantity into the tree.
    """

    model_config = ConfigDict(frozen=True)

    sector: str = Field(min_length=1, description="The vendor's own sector label, not translated.")
    weight: Decimal = Field(ge=0, le=1)


class Classification(BaseModel):
    """What the vendor says an instrument is made of, at a knowledge time (`DR-006` §8.7).

    **Recorded as the vendor answered, guard applied later and elsewhere.** The vendor answers
    confidently and wrongly for bond funds - `NEAR` comes back healthcare 100.0% with every other
    sector at 0.0%, and it is a short-maturity bond fund with no equity sectors at all. Refusing at
    the fetch boundary would store nothing and make "we asked and the answer was unusable"
    indistinguishable from "we never asked", which are different facts about the same instrument.
    `reference_data.classification.look_through` is where the answer is judged.

    An ordinary share carries its own sector as a single weight of 1. That is not a look-through and
    is not pretending to be one - it is the same quantity, which is what lets the sector budget add a
    share and an ETF without a special case.
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    quote_type: str = Field(
        min_length=1,
        description="The vendor's own instrument kind: EQUITY, ETF, MUTUALFUND, INDEX. Kept "
                    "verbatim - it is what tells a look-through apart from a direct sector.",
    )
    industry: str | None = None
    weights: tuple[SectorWeight, ...] = ()
    """Empty means the vendor served no sector at all, which is `unavailable` and not `none`."""

    equity_share: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
        description="What share of the fund the vendor says is EQUITY - "
                    "`funds_data.asset_classes.stockPosition` (`DR-021`). `None` means the vendor "
                    "did not answer, which is not the same as answering zero: `NEAR` reports 0.0 "
                    "and is a bond fund, while an unanswered field is a fact about the vendor. "
                    "`look_through` treats both as a refusal and only a POSITIVE share as evidence "
                    "of equity, so absence stays fail-closed.",
    )

    knowledge_time: datetime = Field(description="When this was learned. Timezone-aware.")

    @property
    def coverage(self) -> Decimal:
        """How much of the instrument the reported sectors account for. 1 for a complete answer."""
        return sum((weight.weight for weight in self.weights), Decimal(0))


class ExchangeSession(BaseModel):
    """One trading session, from the authoritative calendar (ADR-0002).

    This record is what makes a short session classifiable. Bar data alone cannot distinguish a
    scheduled early close from a vendor gap - both are simply fewer bars (CALENDAR_SPEC 2c).
    """

    model_config = ConfigDict(frozen=True)

    exchange: Exchange
    session_date: date
    open_time: datetime = Field(description="Session open, timezone-aware.")
    close_time: datetime = Field(description="Session close, timezone-aware.")
    is_early_close: bool = False

    @property
    def duration_minutes(self) -> int:
        return int((self.close_time - self.open_time).total_seconds() // 60)

    def expected_bars(self, interval: Interval) -> int:
        """Bars this session contains at `interval`, by the calendar.

        This is SESSION TRUTH, not vendor behaviour. A 6.5-hour session does not divide into whole
        hours, so the final bar is a trailing stub (CALENDAR_SPEC 3), and the stub is counted here
        because it is a real part of the session.

        Vendors do not all agree with that. Measured, Yahoo keeps the trailing stub on a regular
        session (7 bars at 1h) and drops it on an early close (3 bars, not the 4 this returns).
        That discrepancy belongs in the market_data adapter's vendor profile, never here - if the
        calendar bent to match a vendor it would stop being an independent check, which is the
        whole reason it exists (ADR-0002).

        Verified against measurement for a regular session: 13 at 30m, 7 at 1h, 1 at 1d.
        """
        if interval is Interval.DAY:
            return 1
        minutes = interval.minutes
        full, remainder = divmod(self.duration_minutes, minutes)
        return full + (1 if remainder else 0)

    def bar_open_times(self, interval: Interval) -> tuple[time, ...]:
        """Open time of each bar in this session, anchored at the session open."""
        if interval is Interval.DAY:
            return (self.open_time.timetz().replace(tzinfo=None),)
        step = interval.minutes
        return tuple(
            (self.open_time + timedelta(minutes=step * i)).time()
            for i in range(self.expected_bars(interval))
        )
