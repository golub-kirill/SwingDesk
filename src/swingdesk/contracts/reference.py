"""Reference data: instruments and exchange sessions."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
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
    exchange: Exchange
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217. Mandatory (BR-9).")
    sector: str | None = None
    industry: str | None = None

    @property
    def vendor_symbol(self) -> str:
        """The symbol Yahoo uses: TSX names carry a .TO suffix."""
        return self.ticker if self.exchange is not Exchange.TSX else f"{self.ticker}.TO"


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
