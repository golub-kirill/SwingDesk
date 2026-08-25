"""The authoritative exchange calendar (ADR-0002).

This is the only thing in the system that knows independently whether a market was open, and for
how long. Bar data cannot answer that: a missing session and a closed market both present as absent
bars, and a scheduled early close and a vendor gap both present as fewer bars (CALENDAR_SPEC 2c).

NYSE and TSX diverge on 30 sessions over ~2.9 years, and one of those - 2025-01-09, an unscheduled
NYSE closure - is on no recurring holiday list. That is why this reads a maintained record rather
than generating dates from rules.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any, cast

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


def currency_for(ticker: str) -> str:
    """Trading currency for a vendor ticker, from the same symbology rule as `exchange_for`.

    Here rather than in a caller because it was already written twice - once where the pipeline
    mints an `Instrument` for a held position, once implicitly wherever a `.TO` name is treated as
    Canadian. A rule stated in two places is a rule that will disagree with itself, and this one
    decides which cost parameters apply and whether an FX rate is required (`DR-010`, `AGENTS.md`
    §3: USA and Canada are never merged).
    """
    return "CAD" if exchange_for(ticker) is Exchange.TSX else "USD"


@lru_cache(maxsize=4)
def _calendar(exchange: Exchange) -> Any:
    return mcal.get_calendar(exchange.value)


@lru_cache(maxsize=64)
def _schedule(exchange: Exchange, start: date, end: date) -> pd.DataFrame:
    schedule: pd.DataFrame = _calendar(exchange).schedule(start_date=start, end_date=end)
    return schedule


@lru_cache(maxsize=4)
def sessions(exchange: Exchange, start: date, end: date) -> tuple[ExchangeSession, ...]:
    """Every trading session for `exchange` in `[start, end]`, ascending.

    A date absent from the result is a date the exchange was closed - a fact no amount of bar data
    could establish.

    **Cached, and the result is safe to share**: the tuple and every `ExchangeSession` in it are
    frozen, and `_schedule` below has been cached since it was written, so this adds no staleness
    that was not already there.

    **`maxsize` is 4 because the fifth entry buys almost nothing.** Windows here are each
    instrument's stored extent, and the shape of that distribution decides the cache, not intuition:
    over the 1,141-member admitted universe there are **372 distinct windows**, of which two cover
    **669 instruments** and most of the rest appear once. Simulated over the run's actual window
    sequence, an LRU of 4 hits **58.7%** and an LRU of 64 hits **63.6%** - sixteen times the memory
    for five points. One entry can hold ~2,500 validated records at ~1.2 kB each, so the size is a
    memory decision.

    **A whole-year span cache was built here and removed the same day.** Quantising the ends to
    whole years collapses those 372 windows into 36 spans and cuts the full-universe pass from
    159 s to 136 s - and retains **228 MB**, measured, because the saving comes precisely from
    keeping ~199,000 built `ExchangeSession` objects alive. `NFR.md` §3 budgets the decision path at
    **5 minutes** and it now runs in about 2.6, so the 23 seconds bought nothing any requirement
    asks for while the memory was real. Recorded rather than deleted: the numbers are what a future
    session needs to revisit it, and the cheaper route is a lighter `ExchangeSession` rather than a
    bigger cache.
    """
    frame = _schedule(exchange, start, end)
    if frame.empty:
        # An empty frame's columns carry no dtype, so `.dt` below raises rather than returning
        # nothing. A window the exchange was shut for the whole of is a normal answer - a weekend,
        # a holiday week, or a date the calendar does not know - and it is an empty tuple.
        return ()
    tz = _calendar(exchange).tz
    # Converted for the whole column at once. Per row it built a pandas Series per access, which
    # cost 82 of the 230 seconds one profiled 150-instrument pass spent - `iterrows` is the
    # expensive way to read a frame this project only ever reads two columns of.
    opens = frame["market_open"].dt.tz_convert(tz)
    closes = frame["market_close"].dt.tz_convert(tz)
    # The index is a DatetimeIndex - that is what pandas_market_calendars returns - so the cast
    # states a fact the stubs cannot.
    index = cast(pd.DatetimeIndex, frame.index)
    return tuple(
        ExchangeSession(
            exchange=exchange,
            session_date=stamp.date(),
            open_time=open_local.to_pydatetime(),
            close_time=close_local.to_pydatetime(),
            is_early_close=close_local.hour < _REGULAR_CLOSE_HOUR,
        )
        for stamp, open_local, close_local in zip(index, opens, closes, strict=True)
    )


def session(exchange: Exchange, on: date) -> ExchangeSession | None:
    """The session on `on`, or None if the exchange was closed."""
    found = sessions(exchange, on, on)
    return found[0] if found else None


def is_open(exchange: Exchange, on: date) -> bool:
    return session(exchange, on) is not None


def last_completed_session(exchange: Exchange, as_of: datetime,
                           lookback_days: int = 15) -> ExchangeSession:
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


def sessions_behind(exchange: Exchange, last_bar: date, as_of: datetime) -> int:
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
