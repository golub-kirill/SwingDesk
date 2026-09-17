"""Quoted bid/ask windows at named moments of a session. Bitemporal. `PR-024`.

**Why a store and not a live call.** `DR-040` measured the spread from quotes it fetched and kept
only the summary, which was right for a measurement and is wrong for a study: a registered run must
be replayable from what was known at an instant (`POINT_IN_TIME_SPEC` 2), and a vendor answering the
same question twice is two different inputs. So quotes are fetched by a tool
(`tools/fetch_entry_quotes.py`), written here with the instant they were learned, and read back
as-of.

**A window is one fetch, never a blend of fetches.** A request returns the first quotes after an
instant; a second fetch of the same window is a second answer to the same question, and mixing
quotes from both would build a window neither answer contained. `window` therefore returns the whole
of the latest fetch known at the instant, not the latest version of each quote.

**Never fetched, fetched empty, and data are three answers**, kept apart exactly as `MinuteStore`
keeps them - collapsing the first two is how a gap in the data gets read as a fact about the market.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from swingdesk.platform import schema
from swingdesk.platform.bulk import insert_many

#: The moments a window may be named for. Named, not timed: the instant a moment falls on depends
#: on the session (a half day closes at 13:00), and the fetch tool resolves it from the calendar.
OPEN = "open"
ELEVEN = "eleven"
CLOSE = "close"
MOMENTS = (OPEN, ELEVEN, CLOSE)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quote_ticks (
    instrument_id   VARCHAR       NOT NULL,
    session_date    DATE          NOT NULL,
    moment          VARCHAR       NOT NULL,
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    ordinal         INTEGER       NOT NULL,
    quoted_at       TIMESTAMPTZ   NOT NULL,
    bid             DECIMAL(18,6) NOT NULL,
    ask             DECIMAL(18,6) NOT NULL,
    PRIMARY KEY (instrument_id, session_date, moment, knowledge_time, ordinal)
);

CREATE TABLE IF NOT EXISTS quote_fetches (
    instrument_id   VARCHAR       NOT NULL,
    session_date    DATE          NOT NULL,
    moment          VARCHAR       NOT NULL,
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    requested_at    TIMESTAMPTZ   NOT NULL,
    source          VARCHAR       NOT NULL,
    quotes          INTEGER       NOT NULL,
    PRIMARY KEY (instrument_id, session_date, moment, knowledge_time)
);
"""


@dataclass(frozen=True, slots=True)
class Quote:
    """One quoted bid and ask, and the instant the venue stamped it."""

    at: datetime
    bid: Decimal
    ask: Decimal


class UnknownMoment(ValueError):
    """A moment this store does not name. Refused rather than stored under a word nobody reads."""


def _check(moment: str) -> None:
    if moment not in MOMENTS:
        raise UnknownMoment(f"{moment!r} is not one of {MOMENTS}")


class QuoteStore:
    """Append-only bitemporal storage for quote windows. Single-writer, like `MinuteStore`."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)
        schema.reconcile(self._connection, _SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> QuoteStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write(self, instrument_id: str, session_date: date, moment: str, requested_at: datetime,
              quotes: Iterable[Quote], knowledge_time: datetime, source: str) -> int:
        """Record one fetch of one window - its quotes in the vendor's order, and the fetch itself.

        `requested_at` is the instant the window was asked to start from, kept so a reader can tell
        how stale the first quote is without knowing how the fetch tool resolved the moment.
        """
        _check(moment)
        rows = [(instrument_id, session_date, moment, knowledge_time, ordinal, quote.at,
                 quote.bid, quote.ask)
                for ordinal, quote in enumerate(quotes)]
        insert_many(self._connection,
                    "INSERT OR REPLACE INTO quote_ticks VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        self._connection.execute(
            "INSERT OR REPLACE INTO quote_fetches VALUES (?, ?, ?, ?, ?, ?, ?)",
            [instrument_id, session_date, moment, knowledge_time, requested_at, source, len(rows)])
        return len(rows)

    def window(self, instrument_id: str, session_date: date, moment: str,
               knowledge_time: datetime) -> tuple[datetime, tuple[Quote, ...]] | None:
        """The latest fetch of the window known at `knowledge_time`: its requested instant and quotes.

        `None` when no fetch is known at that instant; an empty tuple of quotes when one is and it
        served nothing. The quotes come back in the vendor's order, which is time order.
        """
        _check(moment)
        fetch = self._connection.execute(
            """
            SELECT knowledge_time, requested_at FROM quote_fetches
            WHERE instrument_id = ? AND session_date = ? AND moment = ? AND knowledge_time <= ?
            ORDER BY knowledge_time DESC LIMIT 1
            """,
            [instrument_id, session_date, moment, knowledge_time]).fetchone()
        if fetch is None:
            return None
        learned, requested_at = fetch
        rows = self._connection.execute(
            """
            SELECT quoted_at, bid, ask FROM quote_ticks
            WHERE instrument_id = ? AND session_date = ? AND moment = ? AND knowledge_time = ?
            ORDER BY ordinal
            """,
            [instrument_id, session_date, moment, learned]).fetchall()
        return requested_at, tuple(Quote(at=row[0], bid=row[1], ask=row[2]) for row in rows)

    def fetched(self, instrument_id: str, session_date: date, moment: str,
                knowledge_time: datetime) -> bool:
        """Whether any fetch of the window is known at `knowledge_time`. For a tool's skip check."""
        _check(moment)
        row = self._connection.execute(
            "SELECT count(*) FROM quote_fetches WHERE instrument_id = ? AND session_date = ? "
            "AND moment = ? AND knowledge_time <= ?",
            [instrument_id, session_date, moment, knowledge_time]).fetchone()
        return bool(row and row[0])
