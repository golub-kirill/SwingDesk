"""What a given vendor actually returns, as distinct from what a session actually contains.

The calendar returns SESSION TRUTH and is never bent to match a vendor - bending it would destroy
the independence that makes it a check at all (ADR-0002). Vendors disagree with session truth in
specific, measured ways, and those live here.

Keeping the two apart is what lets the completeness check raise DATA on a genuine gap without
raising it on every half-day.
"""

from __future__ import annotations

from dataclasses import dataclass

from swingdesk.contracts.market import Interval
from swingdesk.contracts.reference import ExchangeSession


@dataclass(frozen=True, slots=True)
class VendorProfile:
    """How one vendor's bar counts relate to session truth."""

    name: str
    drops_trailing_stub_on_early_close: bool
    regular_hours_only: bool

    def expected_bars(self, session: ExchangeSession, interval: Interval) -> int:
        """Bars this vendor should return for this session at this interval.

        Starts from the calendar's session-truth count and applies the vendor's known deviations.
        """
        expected = session.expected_bars(interval)
        if (
            self.drops_trailing_stub_on_early_close
            and session.is_early_close
            and interval.is_intraday
            and session.duration_minutes % interval.minutes
        ):
            expected -= 1
        return expected


#: Measured 2026-08-01 across 5 half-days and a ~725-session window (CALENDAR_SPEC 2b).
#:
#: Yahoo keeps the trailing stub on a regular session (6.5h -> 7 hourly bars, the last covering
#: 15:30-16:00) and drops it on an early close (3.5h -> 3 bars, not 4; the 12:30-13:00 half-hour is
#: absent). The reason is unknown; the behaviour is consistent. Left unmodelled, the completeness
#: check would raise DATA on every half-day.
#:
#: At 30m the question does not arise: both 390 and 210 minutes divide evenly.
YAHOO = VendorProfile(
    name="yahoo",
    drops_trailing_stub_on_early_close=True,
    regular_hours_only=True,
)

#: Questrade returns deep extended hours on US symbols (03:30-19:30 measured) and a pre-open bar on
#: Canadian ones (09:00-15:30). Its intraday is NOT interchangeable with Yahoo's and must be
#: filtered to regular hours per exchange before any cross-source comparison, or every bar conflicts
#: (CALENDAR_SPEC 4). Second source, daily bars first (ADR-0001).
QUESTRADE = VendorProfile(
    name="questrade",
    drops_trailing_stub_on_early_close=False,
    regular_hours_only=False,
)
