"""Session-completeness checking: the gate that needed a calendar to exist at all.

A short session has two incompatible causes - a scheduled early close (normal, must not block) and
a vendor gap (abnormal, must raise DATA and block). Both present identically as fewer bars.

Measured, no signal available from the price data separates them (ADR-0002):
  bar count      - a half-day counts short too
  volume ratio   - ranges overlap: normal 0.366-0.824, half-day 0.160-0.749, gap 0.003-0.677
  close mismatch - blind to start-truncation
  daily bar      - proves the market opened, says nothing about intraday completeness

So the check is calendar-expected against vendor-actual, and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from swingdesk.contracts.market import BarSeries, Interval
from swingdesk.contracts.reference import Exchange, ExchangeSession
from swingdesk.market_data.vendor_profile import VendorProfile
from swingdesk.reference_data import calendar as cal


@dataclass(frozen=True, slots=True)
class SessionFinding:
    """One session that did not match its expectation."""

    session_date: date
    expected: int
    actual: int
    reason: str

    @property
    def code(self) -> str:
        """Always DATA: 'Automatic Skip until corrected' (Appendix N)."""
        return "DATA"

    def __str__(self) -> str:
        return (f"{self.session_date}: expected {self.expected} bars, got {self.actual} "
                f"({self.reason})")


@dataclass(frozen=True, slots=True)
class CompletenessReport:
    """The outcome for one instrument, interval and window."""

    instrument_id: str
    interval: Interval
    exchange: Exchange
    sessions_checked: int
    findings: tuple[SessionFinding, ...]

    @property
    def is_complete(self) -> bool:
        return not self.findings

    @property
    def incomplete_dates(self) -> frozenset[date]:
        """Sessions a decision must not be made on."""
        return frozenset(finding.session_date for finding in self.findings)


def check(
    series: BarSeries,
    exchange: Exchange,
    profile: VendorProfile,
    start: date,
    end: date,
) -> CompletenessReport:
    """Compare what the vendor returned against what the calendar says the sessions held.

    Two failure shapes, both DATA:
      * a session the calendar has and the data does not - a missing session
      * a session present with the wrong bar count - a truncated session

    A session the *data* has and the calendar does not is also a finding, and a more alarming one:
    it means the vendor believes the market was open when the exchange says it was closed.
    """
    expected_sessions: dict[date, ExchangeSession] = {
        s.session_date: s for s in cal.sessions(exchange, start, end)
    }
    # Only sessions inside the window are in scope. A series routinely spans far more than the
    # window being checked, and comparing its whole extent against the window's calendar would
    # report every out-of-window session as a closed-market violation.
    #
    # ONE PASS over the bars, not one pass PER SESSION. `BarSeries.bars_on` is a linear scan, so
    # calling it once per session date made this O(bars x sessions) - and the pipeline checks the
    # whole stored extent of each instrument, which means sessions ~= bars. On the ten-year store
    # that is ~2,500 x ~2,500 = 6.3 million comparisons for one instrument and 7.2 billion for a
    # 1,141-member run. Measured 2026-08-24: 90 of the 150 seconds one 150-instrument pass spent,
    # inside this expression alone. Counting instead of materialising the bars is also all this
    # needs - only `len()` was ever read.
    actual_counts: dict[date, int] = {}
    for bar in series.bars:
        if start <= bar.session_date <= end:
            actual_counts[bar.session_date] = actual_counts.get(bar.session_date, 0) + 1

    findings: list[SessionFinding] = []

    for session_date, session in sorted(expected_sessions.items()):
        expected = profile.expected_bars(session, series.interval)
        actual = actual_counts.get(session_date, 0)
        if actual == expected:
            continue
        if actual == 0:
            reason = "session absent from vendor data"
        elif actual < expected:
            reason = "truncated session" + (" on an early close" if session.is_early_close else "")
        else:
            reason = "more bars than the session contains"
        findings.append(SessionFinding(session_date, expected, actual, reason))

    for session_date in sorted(set(actual_counts) - set(expected_sessions)):
        findings.append(
            SessionFinding(
                session_date,
                expected=0,
                actual=actual_counts[session_date],
                reason=f"vendor returned bars but {exchange.value} was closed",
            )
        )

    return CompletenessReport(
        instrument_id=series.instrument_id,
        interval=series.interval,
        exchange=exchange,
        sessions_checked=len(expected_sessions),
        findings=tuple(findings),
    )
