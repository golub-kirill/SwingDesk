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

Two limits, stated because they bound every result computed from this store:

  1. **It accumulates, it cannot reconstruct.** The vendor publishes a current file, not an archive.
     Before the first pull there is no answer, and there never will be one.
  2. **A departure is not a delisting.** Ticker changes, venue moves and symbol reuse all look the
     same from here. The record says what was observed, not what happened.

Fetching lives in `tools/fetch_directory.py`, so nothing in the layer graph reaches the network to
answer a question about eligibility (CI_POLICY 4).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
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
    knowledge_time  TIMESTAMPTZ PRIMARY KEY,
    source          VARCHAR     NOT NULL,
    rows            INTEGER     NOT NULL
);
"""


class DirectoryStore:
    """Symbol directory pulls, read as-of a knowledge time."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)

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
    ) -> int:
        """Store one complete pull.

        Replaces any pull already recorded at the same instant, so re-running a fetch is idempotent
        rather than half-merging two downloads into one snapshot that never existed.
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

        self._connection.execute("DELETE FROM directory WHERE knowledge_time = ?", [knowledge_time])
        self._connection.executemany(
            "INSERT OR REPLACE INTO directory VALUES (?, ?, ?, ?, ?, ?)", rows
        )
        self._connection.execute(
            "INSERT OR REPLACE INTO directory_pulls VALUES (?, ?, ?)",
            [knowledge_time, source, len(rows)],
        )
        return len(rows)

    # ------------------------------------------------------------------ reads

    def pulls(self) -> tuple[tuple[datetime, str, int], ...]:
        """Every recorded pull, oldest first: (knowledge_time, source, rows)."""
        return tuple(
            self._connection.execute(
                "SELECT knowledge_time, source, rows FROM directory_pulls ORDER BY knowledge_time"
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
