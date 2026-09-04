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
     recorded (`AGENTS.md`: fail closed on the claim, not the data). The pulls made before this
     existed have no trailer preserved (`DR-008` forbids archiving raw responses) and stay
     permanently `NULL` - `DR-008` consequence 3 forbids backfilling a date they never stored.
     **How many is a measured count and this docstring does not carry it**: it read *"the six
     pulls"* and the answer was seven by 2026-08-25. Derive it with `attributed_sessions()` and the
     pull list, or with `python tools/build_state.py`, whose directory row splits the unattributed
     pulls by REASON. A count typed into a docstring is `AGENTS.md` §10.5's disease one file type
     over, and gate 14 cannot see it - that gate scans markdown only.

Fetching lives in `tools/fetch_directory.py`, so nothing in the layer graph reaches the network to
answer a question about eligibility (CI_POLICY 4).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

import duckdb

from swingdesk.platform.bulk import insert_many
from swingdesk.reference_data.universe import DirectoryEntry

#: One `directory_audit` row, in column order: started, finished, mode, reason, enabled, attempts,
#: requests, received bytes, result code, and the successful snapshot's `knowledge_time` or `None`.
#: Spelled out rather than left as a bare `tuple` so a caller unpacking it is checked, and so the
#: column order lives beside the schema instead of in whoever last read the SQL.
AuditRow = tuple[
    datetime, datetime, str, str | None, bool, int, int, int, str, datetime | None
]

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
    source_session_date DATE,
    -- `DR-008`: a checksum is created before a snapshot becomes canonical, and checksums are among
    -- the few things stored with one. It answers a question nothing else here can: whether the
    -- vendor served the SAME BYTES again. An unattributed pull is currently ambiguous between "the
    -- file did not regenerate" and "the trailer was unreadable", and those want different responses.
    -- Raw bodies are never archived (the record forbids it), so the digest is the only trace.
    checksum            VARCHAR
);

-- `DR-008`: "Each invocation stores at most one compact aggregate audit row: timestamps, mode and
-- reason, enabled state, attempt count, HTTP request count, received bytes, result code and
-- successful snapshot id." One row per invocation, keyed on when it started, so a crashed run
-- cannot leave two.
--
-- **An invocation that made zero requests still writes a row**, and that is the point of having it:
-- a skipped evening and an evening that never ran are different facts, and until this table existed
-- the store could not tell them apart - the absence of a pull was the only evidence either way.
CREATE TABLE IF NOT EXISTS directory_audit (
    started_at      TIMESTAMPTZ PRIMARY KEY,
    finished_at     TIMESTAMPTZ NOT NULL,
    mode            VARCHAR     NOT NULL,
    reason          VARCHAR,
    enabled         BOOLEAN     NOT NULL,
    attempts        INTEGER     NOT NULL,
    requests        INTEGER     NOT NULL,
    received_bytes  BIGINT      NOT NULL,
    result          VARCHAR     NOT NULL,
    snapshot        TIMESTAMPTZ
);

-- `DR-008`: "If a valid same-session snapshot already exists, a successful forced pull appends a
-- replacement and an append-only supersession record. The previous snapshot remains stored but is
-- no longer canonical."
--
-- Append-only is what makes it evidence: the superseded pull is never deleted and never rewritten,
-- so the record shows that a correction happened rather than presenting the corrected state as if
-- it had always been so - `AUDIT_AND_IMMUTABILITY.md` §2.
CREATE TABLE IF NOT EXISTS directory_supersessions (
    recorded_at TIMESTAMPTZ NOT NULL,
    superseded  TIMESTAMPTZ NOT NULL,
    replacement TIMESTAMPTZ NOT NULL,
    reason      VARCHAR     NOT NULL,
    PRIMARY KEY (recorded_at, superseded)
);
"""

#: Added after `directory_pulls` already shipped without it - existing production databases need
#: this run once, and DuckDB's `CREATE TABLE IF NOT EXISTS` above does not alter an existing table.
#: `IF NOT EXISTS` makes it safe to run on every connect, including a fresh database that already
#: has the column from `_SCHEMA`.
_MIGRATION = """
ALTER TABLE directory_pulls ADD COLUMN IF NOT EXISTS source_session_date DATE;
ALTER TABLE directory_pulls ADD COLUMN IF NOT EXISTS checksum VARCHAR;
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
        supersedes: datetime | None = None,
        checksum: str | None = None,
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

        `supersedes` is the single documented exception, and only `DR-008`'s forced pull passes it:
        naming the `knowledge_time` of the pull being replaced says *this is a correction*, which is
        a different statement from *this is another observation*, and the monotonicity check is
        skipped for it. Callers that do not pass it keep the old behaviour exactly.
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

        # `supersedes` names the pull this one deliberately replaces (`DR-008`'s forced form). It is
        # the ONE case where a non-increasing session date is legitimate, because the caller has
        # declared a replacement rather than presented a second observation - and without it the
        # replacement would store a NULL date and `pull_for_session` would keep answering with the
        # snapshot the operator just corrected. The default stays fail-closed, and the exception has
        # to be asked for by name.
        if source_session_date is not None and supersedes is None:
            row = self._connection.execute(
                "SELECT MAX(source_session_date) FROM directory_pulls "
                "WHERE source_session_date IS NOT NULL"
            ).fetchone()
            latest = row[0] if row else None
            if latest is not None and source_session_date <= latest:
                source_session_date = None

        self._connection.execute("DELETE FROM directory WHERE knowledge_time = ?", [knowledge_time])
        # 13,339 rows on every pull. `executemany` runs the statement once per row, which on
        # this table's composite primary key measured 2.739 ms each - about half a minute of
        # a daily pull spent inserting a directory that fits in memory twice over.
        insert_many(
            self._connection, "INSERT OR REPLACE INTO directory VALUES (?, ?, ?, ?, ?, ?)",
            list(rows),
        )
        self._connection.execute(
            "INSERT OR REPLACE INTO directory_pulls VALUES (?, ?, ?, ?, ?)",
            [knowledge_time, source, len(rows), source_session_date, checksum],
        )
        return source_session_date

    def record_audit(
        self,
        *,
        started_at: datetime,
        finished_at: datetime,
        mode: str,
        reason: str | None,
        enabled: bool,
        attempts: int,
        requests: int,
        received_bytes: int,
        result: str,
        snapshot: datetime | None,
    ) -> None:
        """One aggregate row for one invocation of the collector (`DR-008`).

        `INSERT OR REPLACE` on `started_at` keeps "at most one" literally true even if a caller
        writes twice for the same invocation - the alternative is a table that silently answers
        "how many times did the collector run" wrongly, and this table exists to answer exactly
        that.
        """
        self._connection.execute(
            "INSERT OR REPLACE INTO directory_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [started_at, finished_at, mode, reason, enabled, attempts, requests,
             received_bytes, result, snapshot],
        )

    def audit(self) -> tuple[AuditRow, ...]:
        """Every audit row, oldest first."""
        return tuple(
            self._connection.execute(
                "SELECT started_at, finished_at, mode, reason, enabled, attempts, requests, "
                "received_bytes, result, snapshot FROM directory_audit ORDER BY started_at"
            ).fetchall()
        )

    def last_forced_reason(self) -> str | None:
        """The reason given by the most recent forced pull, or `None` if there has never been one.

        `DR-008` requires *"a new non-empty reason"* per forced command. A reason that can be
        repeated is a reason nobody reads: re-running the same emergency command by reflex would
        carry the same words and the audit row would look deliberate. Comparing against the last
        one is what makes the requirement mechanical rather than aspirational.
        """
        row = self._connection.execute(
            "SELECT reason FROM directory_audit WHERE mode = 'FORCED' AND reason IS NOT NULL "
            "ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def record_supersession(
        self, *, recorded_at: datetime, superseded: datetime, replacement: datetime, reason: str
    ) -> None:
        """Append the note that one pull replaced another. Never deletes the superseded pull."""
        self._connection.execute(
            "INSERT OR REPLACE INTO directory_supersessions VALUES (?, ?, ?, ?)",
            [recorded_at, superseded, replacement, reason],
        )

    def supersessions(self) -> tuple[tuple[datetime, datetime, datetime, str], ...]:
        """Every supersession note, oldest first."""
        return tuple(
            self._connection.execute(
                "SELECT recorded_at, superseded, replacement, reason FROM directory_supersessions "
                "ORDER BY recorded_at, superseded"
            ).fetchall()
        )

    # ------------------------------------------------------------------ reads

    def pull_for_session(self, session_date: date) -> datetime | None:
        """The `knowledge_time` of the pull attributed to `session_date`, if one exists.

        This is what makes `DR-008`'s *"an already-recorded session makes zero requests"* decidable
        BEFORE the network is touched. The vendor's own session date only arrives with the file, so
        a guard that waited for it would have already spent the requests it exists to save - which
        is exactly what the collector did until 2026-08-25, three times in eighteen pulls.
        """
        row = self._connection.execute(
            "SELECT knowledge_time FROM directory_pulls WHERE source_session_date = ? "
            "ORDER BY knowledge_time DESC LIMIT 1",
            [session_date],
        ).fetchone()
        return row[0] if row else None

    def checksum_at(self, knowledge_time: datetime) -> str | None:
        """The digest recorded with one pull, or `None` if that pull predates the column."""
        row = self._connection.execute(
            "SELECT checksum FROM directory_pulls WHERE knowledge_time = ?", [knowledge_time]
        ).fetchone()
        return row[0] if row else None

    def latest_checksum(self) -> str | None:
        """The digest of the most recent pull that has one.

        **What it is for, and it is one question:** whether the vendor served the same bytes again.
        An unattributed pull is ambiguous between *the file did not regenerate* and *the trailer was
        unreadable*, and those want different responses - the first is the vendor being slow, the
        second is a parsing problem on our side. Comparing digests separates them without archiving
        a single raw response, which `DR-008` forbids.
        """
        row = self._connection.execute(
            "SELECT checksum FROM directory_pulls WHERE checksum IS NOT NULL "
            "ORDER BY knowledge_time DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def attributed_sessions(self) -> tuple[date, ...]:
        """Every session a pull is attributed to, ascending and deduplicated.

        **Only an ATTRIBUTED pull can be placed on a session**, which is why this is not simply the
        pull list. A pull whose trailer and `Last-Modified` did not corroborate is a real snapshot
        of a directory and an unknown answer to "which session was this" - `DR-008` c3 forbids
        backfilling one. Coverage therefore starts at the first attributed pull, never at the first
        pull.
        """
        return tuple(
            row[0] for row in self._connection.execute(
                "SELECT DISTINCT source_session_date FROM directory_pulls "
                "WHERE source_session_date IS NOT NULL ORDER BY source_session_date"
            ).fetchall()
        )

    def gaps(self, expected: Iterable[date]) -> tuple[date, ...]:
        """Sessions in `expected` that no pull is attributed to (`DR-008`).

        **The caller supplies the sessions**, so this store never learns about exchanges or
        calendars - the layer contract, and also the reason the withdrawn version was wrong. A
        `gaps()` built on `knowledge_time` was written and removed on 2026-08-12 for misattributing
        evening pulls that cross UTC midnight; `source_session_date` is the vendor's own claim about
        which session its file describes, corroborated twice before it is stored, and it is the only
        field that can answer this.

        *"Research claiming continuous survivorship coverage must query and disclose those gaps"* -
        this is that query.
        """
        recorded = set(self.attributed_sessions())
        return tuple(session for session in expected if session not in recorded)

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
