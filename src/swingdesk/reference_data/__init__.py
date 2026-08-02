"""Symbology, exchange calendars, corporate actions, sector classification.

Source Facts layer. The calendar here is the system's only independent knowledge of whether a
market was open (ADR-0002).
"""

from swingdesk.reference_data.calendar import (
    calendar_version,
    exchange_for,
    is_open,
    last_completed_session,
    session,
    sessions,
    sessions_behind,
)

__all__ = [
    "calendar_version",
    "exchange_for",
    "is_open",
    "last_completed_session",
    "session",
    "sessions",
    "sessions_behind",
]
