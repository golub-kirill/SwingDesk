"""`calendar.session` answers from a year's schedule; it must answer what a one-day schedule did."""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal

YEARS = range(2016, 2027)


def _one_day(exchange: Exchange, on: date):
    """What `session` returned before 2026-09-26: the schedule of that single date."""
    found = cal.sessions.__wrapped__(exchange, on, on)
    return found[0] if found else None


def _hard_days(exchange: Exchange, year: int) -> list[date]:
    """The dates a year's schedule could get wrong: every weekday holiday and every early close.

    Taken from the year's own schedule, then checked against the one-day schedule - so a date the
    year dropped or shortened that the day did not would show up as a mismatch on that date.
    """
    held = cal._year(exchange, year)
    day, out = date(year, 1, 1), []
    while day.year == year:
        if day.weekday() < 5 and (day not in held or held[day].is_early_close):
            out.append(day)
        day += timedelta(days=1)
    return out


@pytest.mark.parametrize("exchange", [Exchange.NYSE, Exchange.TSX])
def test_every_holiday_and_early_close_reads_as_the_single_day_schedule_does(
        exchange: Exchange) -> None:
    """2016 to 2026 on both exchanges, plus the first and last day of each year and a sample."""
    sample = random.Random(20260926)
    for year in YEARS:
        days = _hard_days(exchange, year)
        assert days, f"{exchange.value} {year} has no holiday: the check would be empty"
        days += [date(year, 1, 1), date(year, 12, 31),
                 *(date(year, 1, 1) + timedelta(days=sample.randrange(365)) for _ in range(4))]
        for on in days:
            assert cal.session(exchange, on) == _one_day(exchange, on), (exchange.value, on)


def test_the_unscheduled_closure_is_nyse_only() -> None:
    """2025-01-09 is on no recurring list, which is why the calendar is read rather than generated."""
    assert cal.session(Exchange.NYSE, date(2025, 1, 9)) is None
    assert cal.session(Exchange.TSX, date(2025, 1, 9)) is not None


def test_a_scan_does_not_evict_the_windows_sessions_is_holding() -> None:
    """`sessions` keeps four windows; years built for `session` must not push them out."""
    window = (Exchange.NYSE, date(2016, 1, 4), date(2026, 9, 18))
    cal.sessions(*window)
    cal._year.cache_clear()
    for year in range(2016, 2022):
        cal.session(Exchange.NYSE, date(year, 6, 1))
    misses = cal.sessions.cache_info().misses
    cal.sessions(*window)
    assert cal.sessions.cache_info().misses == misses, "the scan evicted a caller's window"


def test_a_year_of_daily_lookups_builds_the_schedule_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The point of the change, pinned: a day-by-day scan asks pandas once a year, not once a day."""
    built: list[tuple[Exchange, date, date]] = []
    real = cal._schedule.__wrapped__

    def counting(exchange: Exchange, start: date, end: date):
        built.append((exchange, start, end))
        return real(exchange, start, end)

    monkeypatch.setattr(cal, "_schedule", counting)
    cal._year.cache_clear()
    try:
        day = date(2024, 1, 1)
        while day.year == 2024:
            cal.session(Exchange.NYSE, day)
            day += timedelta(days=1)
    finally:
        cal._year.cache_clear()
    assert built == [(Exchange.NYSE, date(2024, 1, 1), date(2024, 12, 31))]
