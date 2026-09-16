"""Monthly and quarterly bars, rolled up from daily bars by calendar period. `DR-046`.

**The top of the ladder, and only its data.** `M29-T0427` names *monthly context* as the first step
of the course's top-down analysis, and `CONSTRAINTS` D9 names a three-month context above the daily
decision. Both are read off a chart whose candles are calendar months or quarters, so that is what
this builds: one bar per calendar period, from the daily bars already stored. What a monthly bar
SAYS about direction is `M29-T0427`'s reading, and it stays a registered component until a study or
the course text defines it - this module decides nothing.

**Calendar periods, never rolling session counts.** A month here is the calendar month, the way a
monthly chart draws it; it holds 19 to 23 sessions. A rolling 21-session window is a different
object - a reading of the daily series - and a consumer that wants one computes it from daily bars.

**A period is a fact only once it has closed.** A monthly candle read mid-month is a candle whose
high, low and close are still moving, and treating it as settled is the look-ahead this project's
point-in-time rules exist to prevent. So only COMPLETE periods are returned by default, and complete
is measured, not assumed: the period holds a daily bar for every session the exchange calendar says
it had. A past month missing one daily bar is incomplete too - a gap in the data, said as one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from swingdesk.contracts.market import Bar, Interval
from swingdesk.reference_data import calendar as cal

MONTH = "month"
QUARTER = "quarter"
PERIODS = (MONTH, QUARTER)


class NotRollable(ValueError):
    """The bars cannot be rolled into calendar periods as asked.

    Raised for a period this module does not build, for bars that are not daily, and for bars of
    more than one instrument - each a way to produce a bar that describes nothing real.
    """


@dataclass(frozen=True, slots=True)
class PeriodBar:
    """One calendar month or quarter, built from the daily bars that fall inside it."""

    instrument_id: str
    period: str
    starts: date
    """The period's first CALENDAR day - the 1st of the month, or of the quarter's first month."""

    first_session: date
    last_session: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    sessions: int
    """How many daily bars it was built from."""

    expected: int
    """How many sessions the exchange calendar says the period had, up to its last calendar day."""

    @property
    def complete(self) -> bool:
        """Every session of the period is present. The only state in which the bar is a fact."""
        return self.sessions == self.expected


def period_start(day: date, period: str) -> date:
    """The first calendar day of the month or quarter `day` falls in."""
    if period == MONTH:
        return day.replace(day=1)
    if period == QUARTER:
        return day.replace(month=(day.month - 1) // 3 * 3 + 1, day=1)
    raise NotRollable(f"{period!r} is not one of {PERIODS}")


def period_end(start: date, period: str) -> date:
    """The last calendar day of the period that begins on `start`."""
    months = 1 if period == MONTH else 3
    year, month = divmod(start.month - 1 + months, 12)
    return date(start.year + year, month + 1, 1) - timedelta(days=1)


def roll_up_daily(
    bars: Sequence[Bar], period: str, *, include_partial: bool = False
) -> tuple[PeriodBar, ...]:
    """One bar per calendar `period`, oldest first, from one instrument's daily bars.

    `include_partial` returns the periods that are not complete as well - the month still forming,
    or a past month with a missing daily bar - each carrying `complete = False`. It defaults to
    False because an unfinished candle read as a finished one is look-ahead, and nothing in the
    bar itself would show it.
    """
    if period not in PERIODS:
        raise NotRollable(f"{period!r} is not one of {PERIODS}")
    if not bars:
        return ()
    instruments = {bar.instrument_id for bar in bars}
    if len(instruments) != 1:
        raise NotRollable(
            f"bars of {len(instruments)} instruments ({', '.join(sorted(instruments))}); a period "
            f"bar is one instrument's, and a mixed high and low describe no market"
        )
    if any(bar.interval is not Interval.DAY for bar in bars):
        raise NotRollable(
            "only daily bars roll up into calendar periods. Intraday bars roll up through "
            "market_data.intraday (DR-045), and a month built from them would be a second definition "
            "of the same month"
        )

    sessions = [bar.session_date for bar in bars]
    if len(set(sessions)) != len(sessions):
        # Two versions of one session - a revision read alongside the original. Summing both would
        # double the volume and could count a period complete that is missing a day.
        raise NotRollable(
            "a session appears more than once. Read the bars as-of one knowledge time, so each "
            "session is one version, before rolling them up"
        )

    [instrument_id] = instruments
    exchange = cal.exchange_for(instrument_id)
    groups: dict[date, list[Bar]] = {}
    for bar in sorted(bars, key=lambda b: b.session_date):
        groups.setdefault(period_start(bar.session_date, period), []).append(bar)

    built: list[PeriodBar] = []
    for starts in sorted(groups):
        group = groups[starts]
        expected = len(cal.sessions(exchange, starts, period_end(starts, period)))
        rolled = PeriodBar(
            instrument_id=instrument_id,
            period=period,
            starts=starts,
            first_session=group[0].session_date,
            last_session=group[-1].session_date,
            open=group[0].open,
            high=max(bar.high for bar in group),
            low=min(bar.low for bar in group),
            close=group[-1].close,
            volume=sum(bar.volume for bar in group),
            sessions=len(group),
            expected=expected,
        )
        if rolled.complete or include_partial:
            built.append(rolled)
    return tuple(built)
