"""The symbol directory, stored rather than fetched per run.

"Which symbols were listed on date D" is a point-in-time question, and this project treats those
carefully everywhere else. Until now the directory was downloaded inside research tools, which meant
every study silently used *today's* listings to describe an older window.

**A pull is a complete snapshot, not a set of independent facts.** That is the one place this store
differs from `BarStore`: reading "everything known by K" would union every symbol ever seen and make
a delisting invisible. So `as_of` reads the latest pull at or before K, and nothing else.

That difference is what makes departures detectable. A symbol that stops appearing has almost
certainly been delisted or renamed, and `departures()` is the **only free evidence this project can
ever collect about survivorship** (`DATA_QUALITY_SPEC.md`) - Yahoo serves no delisted history, so
what is not recorded going forward is unrecoverable.

Three limits, stated because they bound every result computed from this store:

  1. **It accumulates, it cannot reconstruct.** The vendor publishes a current file, not an archive.
     Before the first pull there is no answer, and there never will be one.
  2. **A departure is not a delisting.** Ticker changes, venue moves and symbol reuse all look the
     same from here. The record says what was observed, not what happened.
  3. **A pull is attributed to a session only when the vendor's own claim is corroborated.**
     `knowledge_time` - when *this machine* fetched - was never a safe stand-in for which session
     the vendor's file described; a `gaps()` built on that inference was written and withdrawn on
     2026-08-12, misattributing evening pulls that cross UTC midnight. `source_session_date`
     replaces it: `tools/fetch_directory.py` parses the vendor's `File Creation Time` trailer,
     confirmed 2026-08-13 to be America/New_York local time (empirically, against the same
     response's `Last-Modified` header - not assumed), and stores a date only when the two agree
     within tolerance on every file, every pull. Disagreement, a missing header, or a
     not-strictly-increasing date against prior pulls all refuse the CLAIM - the rows are still
     recorded (`AGENTS.md`: fail closed on the claim, not the data). The six pulls made before this
     existed have no trailer preserved (`DR-008` forbids archiving raw responses) and stay
     permanently `NULL` - `DR-008` consequence 3 forbids backfilling a date they never stored.

Fetching lives in `tools/fetch_directory.py`, so nothing in the layer graph reaches the network to
answer a question about eligibility (CI_POLICY 4).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

import duckdb

from swingdesk.reference_data.universe import DirectoryEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS directory (
    knowledge_time  TIMESTAMPTZ NOT NULL,
    symbol          VARCHAR     NOT NULL,
    name            VARCHAR     NOT NULL,
    venue           VARCHAR     NOT NULL,
    is_etf          BOOLEAN     NOT NULL,
    is_test_issue   BOOLEAN     NOT NULL,
    PRIMARY KEY (knowledge_time, symbol, venue)
);

CREATE TABLE IF NOT EXISTS directory_pulls (
    knowledge_time      TIMESTAMPTZ PRIMARY KEY,
    source              VARCHAR     NOT NULL,
    rows                INTEGER     NOT NULL,
    source_session_date DATE
);
"""

#: Added after `directory_pulls` already shipped without it - existing production databases need
#: this run once, and DuckDB's `CREATE TABLE IF NOT EXISTS` above does not alter an existing table.
#: `IF NOT EXISTS` makes it safe to run on every connect, including a fresh database that already
#: has the column from `_SCHEMA`.
_MIGRATION = """
ALTER TABLE directory_pulls ADD COLUMN IF NOT EXISTS source_session_date DATE;
"""


class DirectoryStore:
    """Symbol directory pulls, read as-of a knowledge time."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)
        self._connection.execute(_MIGRATION)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> DirectoryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ----------------------------------------------------------------- writes

    def record(
        self,
        entries: Iterable[DirectoryEntry],
        knowledge_time: datetime,
        source: str,
        source_session_date: date | None = None,
    ) -> date | None:
        """Store one complete pull. Returns the session date actually stored.

        Replaces any pull already recorded at the same instant, so re-running a fetch is idempotent
        rather than half-merging two downloads into one snapshot that never existed.

        `source_session_date` is the caller's already-corroborated claim (`tools/fetch_directory.py`
        derives and cross-checks it; this method does not re-derive it). The one check made here is
        monotonicity: it must be strictly greater than every session date already stored, or it is
        dropped to `None` rather than accepted. A repeat or earlier date most likely means the
        vendor's file did not regenerate between two pulls - a stale-file symptom this project has
        already observed - not a second, legitimate observation of an earlier session. This fails
        closed on the CLAIM: the rows are still recorded either way.
        """
        rows = [
            (knowledge_time, e.symbol, e.name, e.venue, e.is_etf, e.is_test_issue)
            for e in entries
        ]
        if not rows:
            raise ValueError(
                "refusing to record an empty directory pull: an empty snapshot is "
                "indistinguishable from every symbol being delisted at once"
            )

        if source_session_date is not None:
            row = self._connection.execute(
                "SELECT MAX(source_session_date) FROM directory_pulls "
                "WHERE source_session_date IS NOT NULL"
            ).fetchone()
            latest = row[0] if row else None
            if latest is not None and source_session_date <= latest:
                source_session_date = None

        self._connection.execute("DELETE FROM directory WHERE knowledge_time = ?", [knowledge_time])
        self._connection.executemany(
            "INSERT OR REPLACE INTO directory VALUES (?, ?, ?, ?, ?, ?)", rows
        )
        self._connection.execute(
            "INSERT OR REPLACE INTO directory_pulls VALUES (?, ?, ?, ?)",
            [knowledge_time, source, len(rows), source_session_date],
        )
        return source_session_date

    # ------------------------------------------------------------------ reads

    def pulls(self) -> tuple[tuple[datetime, str, int, date | None], ...]:
        """Every recorded pull, oldest first: (knowledge_time, source, rows, source_session_date)."""
        return tuple(
            self._connection.execute(
                "SELECT knowledge_time, source, rows, source_session_date "
                "FROM directory_pulls ORDER BY knowledge_time"
            ).fetchall()
        )

    def latest_pull(self, knowledge_time: datetime) -> datetime | None:
        """The most recent pull at or before `knowledge_time`, or None if nothing was known yet."""
        row = self._connection.execute(
            "SELECT MAX(knowledge_time) FROM directory_pulls WHERE knowledge_time <= ?",
            [knowledge_time],
        ).fetchone()
        return row[0] if row and row[0] is not None else None

    def as_of(self, knowledge_time: datetime, eligible_only: bool = False) -> tuple[DirectoryEntry, ...]:
        """The directory as it was known at `knowledge_time`, sorted by symbol.

        Empty when no pull had happened yet. That is a real answer - "we did not know" - and the
        caller must not read it as "no symbols were listed".
        """
        pull = self.latest_pull(knowledge_time)
        if pull is None:
            return ()

        rows = self._connection.execute(
            """
            SELECT symbol, name, venue, is_etf, is_test_issue
            FROM directory WHERE knowledge_time = ? ORDER BY symbol, venue
            """,
            [pull],
        ).fetchall()
        entries = tuple(
            DirectoryEntry(symbol=r[0], name=r[1], venue=r[2], is_etf=r[3], is_test_issue=r[4])
            for r in rows
        )
        return tuple(e for e in entries if e.is_eligible) if eligible_only else entries

    def departures(self, earlier: datetime, later: datetime) -> tuple[str, ...]:
        """Symbols present in the pull as of `earlier` and absent from the one as of `later`.

        The project's only free survivorship evidence, and it only ever looks forward. Reported as
        observations, not as delistings - a ticker change looks identical from here.
        """
        before = {e.symbol for e in self.as_of(earlier)}
        after = {e.symbol for e in self.as_of(later)}
        return tuple(sorted(before - after))


__all__ = ["DirectoryStore"]
