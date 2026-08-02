"""The authoritative exchange calendar (ADR-0002).

This is the only thing in the system that knows independently whether a market was open, and for
how long. Bar data cannot answer that: a missing session and a closed market both present as absent
bars, and a scheduled early close and a vendor gap both present as fewer bars (CALENDAR_SPEC 2c).

NYSE and TSX diverge on 30 sessions over ~2.9 years, and one of those - 2025-01-09, an unscheduled
NYSE closure - is on no recurring holiday list. That is why this reads a maintained record rather
than generating dates from rules.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import pandas as pd
import pandas_market_calendars as mcal

from swingdesk.contracts.reference import Exchange, ExchangeSession

_TSX_SUFFIX = ".TO"

#: Regular close, exchange-local. A session closing earlier is an early close.
#: Both NYSE and TSX trade 09:30-16:00 ET, which is exactly what makes them look interchangeable
#: when they are not.
_REGULAR_CLOSE_HOUR = 16


def exchange_for(ticker: str) -> Exchange:
    """Exchange for a vendor ticker. `.TO` names are TSX; everything else is NYSE."""
    return Exchange.TSX if ticker.upper().endswith(_TSX_SUFFIX) else Exchange.NYSE


@lru_cache(maxsize=4)
def _calendar(exchange: Exchange):
    return mcal.get_calendar(exchange.value)


@lru_cache(maxsize=64)
def _schedule(exchange: Exchange, start: date, end: date) -> pd.DataFrame:
    return _calendar(exchange).schedule(start_date=start, end_date=end)


def sessions(exchange: Exchange, start: date, end: date) -> tuple[ExchangeSession, ...]:
    """Every trading session for `exchange` in `[start, end]`, ascending.

    A date absent from the result is a date the exchange was closed - a fact no amount of bar data
    could establish.
    """
    frame = _schedule(exchange, start, end)
    tz = _calendar(exchange).tz
    result: list[ExchangeSession] = []
    for stamp, row in frame.iterrows():
        open_local = row["market_open"].tz_convert(tz)
        close_local = row["market_close"].tz_convert(tz)
        result.append(
            ExchangeSession(
                exchange=exchange,
                session_date=stamp.date(),
                open_time=open_local.to_pydatetime(),
                close_time=close_local.to_pydatetime(),
                is_early_close=close_local.hour < _REGULAR_CLOSE_HOUR,
            )
        )
    return tuple(result)


def session(exchange: Exchange, on: date) -> ExchangeSession | None:
    """The session on `on`, or None if the exchange was closed."""
    found = sessions(exchange, on, on)
    return found[0] if found else None


def is_open(exchange: Exchange, on: date) -> bool:
    return session(exchange, on) is not None


def last_completed_session(exchange: Exchange, as_of, lookback_days: int = 15) -> ExchangeSession:
    """The most recent session whose close is at or before `as_of`.

    A still-open or not-yet-opened session is excluded, so a mid-session call resolves to the prior
    session - the last fully-formed bar. The unclosed current bar is never a decision input
    (CALENDAR_SPEC 5).
    """
    end = as_of.date()
    start = end - pd.Timedelta(days=lookback_days).to_pytimedelta()
    completed = [s for s in sessions(exchange, start, end) if s.close_time <= as_of]
    if not completed:
        raise LookupError(
            f"no completed {exchange.value} session within {lookback_days} days before {as_of}"
        )
    return completed[-1]


def sessions_behind(exchange: Exchange, last_bar: date, as_of) -> int:
    """How many completed sessions the data is behind. 0 means fresh.

    Staleness is measured in *sessions*, never in calendar days - a Friday close is not stale on
    Monday morning, and a holiday week is not a data failure.
    """
    latest = last_completed_session(exchange, as_of)
    if last_bar >= latest.session_date:
        return 0
    window = sessions(exchange, last_bar, latest.session_date)
    return max(0, len(window) - 1)


def calendar_version() -> str:
    """Recorded in every run manifest. A calendar that silently changed would change results."""
    from importlib.metadata import version

    return f"pandas-market-calendars=={version('pandas_market_calendars')}"
