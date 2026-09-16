"""Monthly and quarterly bars from daily ones (`DR-046`).

Built on the real exchange calendar, because completeness is a claim about the calendar: a period is
a fact only when it holds a daily bar for every session the exchange says it had. August 2026 is the
fixture month - 21 sessions, none of them a holiday - and September 2026 carries Labor Day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.market_data.periods import (
    MONTH,
    QUARTER,
    NotRollable,
    PeriodBar,
    period_end,
    period_start,
    roll_up_daily,
)
from swingdesk.reference_data import calendar as cal

KNOWN = datetime(2026, 9, 16, 22, 0, tzinfo=UTC)
EXCHANGE = cal.exchange_for("SPY")


def _sessions(start: date, end: date) -> list[date]:
    return [session.session_date for session in cal.sessions(EXCHANGE, start, end)]


def _bar(session: date, close: str, *, instrument: str = "SPY",
         interval: Interval = Interval.DAY) -> Bar:
    price = Decimal(close)
    return Bar(
        instrument_id=instrument, interval=interval, series=Series.RAW,
        event_time=datetime(session.year, session.month, session.day, 13, 30, tzinfo=UTC),
        session_date=session, open=price - 1, high=price + 2, low=price - 2, close=price,
        volume=1000, knowledge_time=KNOWN,
    )


def _month(start: date, end: date, first: int = 100) -> list[Bar]:
    return [_bar(session, str(first + i)) for i, session in enumerate(_sessions(start, end))]


AUGUST = _month(date(2026, 8, 1), date(2026, 8, 31))


def test_a_complete_month_is_one_bar_with_the_month_s_own_prices() -> None:
    [month] = roll_up_daily(AUGUST, MONTH)

    assert isinstance(month, PeriodBar)
    assert month.starts == date(2026, 8, 1)
    assert month.first_session == AUGUST[0].session_date
    assert month.last_session == AUGUST[-1].session_date
    assert month.open == AUGUST[0].open, "the first session's open"
    assert month.close == AUGUST[-1].close, "the last session's close"
    assert month.high == max(bar.high for bar in AUGUST)
    assert month.low == min(bar.low for bar in AUGUST)
    assert month.volume == 1000 * len(AUGUST)
    assert month.sessions == month.expected == len(AUGUST)
    assert month.complete


def test_the_month_still_forming_is_not_returned_unless_asked_for() -> None:
    """THE LOOK-AHEAD GUARD. Mid-September the month's high, low and close are still moving; the
    calendar knows its remaining sessions, so the count says it is not done."""
    september_so_far = _month(date(2026, 9, 1), date(2026, 9, 16), first=130)
    bars = AUGUST + september_so_far

    assert [bar.starts for bar in roll_up_daily(bars, MONTH)] == [date(2026, 8, 1)]

    both = roll_up_daily(bars, MONTH, include_partial=True)
    assert [bar.starts for bar in both] == [date(2026, 8, 1), date(2026, 9, 1)]
    forming = both[1]
    assert not forming.complete
    assert forming.sessions == len(september_so_far) < forming.expected
    assert date(2026, 9, 7) not in {b.session_date for b in september_so_far}, "Labor Day"


def test_a_past_month_missing_one_session_is_a_gap_not_a_month() -> None:
    gapped = [bar for bar in AUGUST if bar.session_date != AUGUST[10].session_date]

    assert roll_up_daily(gapped, MONTH) == ()
    [partial] = roll_up_daily(gapped, MONTH, include_partial=True)
    assert partial.sessions == len(AUGUST) - 1 and partial.expected == len(AUGUST)


def test_a_quarter_spans_its_three_calendar_months() -> None:
    quarter_bars = _month(date(2026, 4, 1), date(2026, 6, 30))

    [quarter] = roll_up_daily(quarter_bars, QUARTER)

    assert quarter.starts == date(2026, 4, 1)
    assert quarter.complete and quarter.sessions == len(quarter_bars)
    assert quarter.open == quarter_bars[0].open and quarter.close == quarter_bars[-1].close
    months = roll_up_daily(quarter_bars, MONTH)
    assert [m.starts.month for m in months] == [4, 5, 6]
    assert sum(m.sessions for m in months) == quarter.sessions


def test_bars_out_of_order_give_the_same_period() -> None:
    assert roll_up_daily(list(reversed(AUGUST)), MONTH) == roll_up_daily(AUGUST, MONTH)


@pytest.mark.parametrize(("day", "period", "start", "end"), [
    (date(2026, 8, 17), MONTH, date(2026, 8, 1), date(2026, 8, 31)),
    (date(2026, 2, 10), MONTH, date(2026, 2, 1), date(2026, 2, 28)),
    (date(2026, 12, 31), MONTH, date(2026, 12, 1), date(2026, 12, 31)),
    (date(2026, 8, 17), QUARTER, date(2026, 7, 1), date(2026, 9, 30)),
    (date(2026, 1, 2), QUARTER, date(2026, 1, 1), date(2026, 3, 31)),
    (date(2026, 11, 30), QUARTER, date(2026, 10, 1), date(2026, 12, 31)),
])
def test_period_boundaries_are_calendar_boundaries(day, period, start, end) -> None:
    assert period_start(day, period) == start
    assert period_end(start, period) == end


def test_an_unknown_period_is_refused() -> None:
    with pytest.raises(NotRollable, match="'week' is not one of"):
        roll_up_daily(AUGUST, "week")
    with pytest.raises(NotRollable):
        period_start(date(2026, 8, 1), "year")


def test_intraday_bars_are_refused() -> None:
    """A month built from hourly bars would be a second definition of the same month."""
    hourly = [_bar(session, "100", interval=Interval.HOUR) for session in _sessions(
        date(2026, 8, 3), date(2026, 8, 5))]
    with pytest.raises(NotRollable, match="only daily bars"):
        roll_up_daily(hourly, MONTH)


def test_two_instruments_are_refused() -> None:
    mixed = [*AUGUST[:3], _bar(AUGUST[3].session_date, "50", instrument="QQQ")]
    with pytest.raises(NotRollable, match="2 instruments"):
        roll_up_daily(mixed, MONTH)


def test_a_session_given_twice_is_refused() -> None:
    """A revision read alongside its original would double the volume and fake a complete month."""
    with pytest.raises(NotRollable, match="more than once"):
        roll_up_daily([*AUGUST, AUGUST[5]], MONTH)


def test_no_bars_roll_up_to_nothing() -> None:
    assert roll_up_daily([], MONTH) == ()


def test_an_unknown_period_is_refused_even_with_no_bars() -> None:
    """A caller's typo must not read as "no data yet": an empty input would otherwise hide it."""
    with pytest.raises(NotRollable, match="'week' is not one of"):
        roll_up_daily([], "week")
