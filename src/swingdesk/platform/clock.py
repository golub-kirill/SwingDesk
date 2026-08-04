"""Time, injected.

Domain code never reads the wall clock (DETERMINISM_SPEC 3.1). It receives a Clock and asks that.
This is not ceremony: `datetime.now()` inside a decision makes a run irreproducible in a way that
leaves no trace, and the fail-closed table's return condition after a screener failure is that a
re-run matches a control run - which is unachievable if the decision path reads the clock.

CI greps for wall-clock calls in the domain packages, because a rule this easy to break by accident
cannot be enforced by review.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Anything that can tell the time. Domain code depends on this, never on `datetime`."""

    def now(self) -> datetime:
        """Current instant, timezone-aware and in UTC."""
        ...


class SystemClock:
    """Real time. Used at the edges - scheduling, logging, fetch bookkeeping - never in a decision."""

    __slots__ = ()

    def now(self) -> datetime:
        return datetime.now(UTC)

    def __repr__(self) -> str:
        return "SystemClock()"


class FixedClock:
    """A clock frozen at one instant.

    Every backtest and every test uses this. A run replayed from a manifest uses the manifest's
    time, which is what makes the replay byte-identical.
    """

    __slots__ = ("_instant",)

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware instant")
        self._instant = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._instant

    def __repr__(self) -> str:
        return f"FixedClock({self._instant.isoformat()})"
