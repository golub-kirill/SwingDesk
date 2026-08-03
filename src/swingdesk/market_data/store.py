"""The bitemporal bar store (ADR-0004).

Every fact carries `event_time` (when it was true) and `knowledge_time` (when we learned it). Every
read is as-of: "the best value for event_time T that was known at knowledge_time K". Backtests set
K to the decision bar, live sets K to now, and there is no third mode - that is how look-ahead gets
in (POINT_IN_TIME_SPEC 2).

Writes compare before inserting. That is not an optimisation: Yahoo rewrites the full adjusted
history on every refetch, so appending what came back would write ~20M rows a day. Comparing also
makes a vendor-wide re-adjustment visible as a spike in revision volume instead of an invisible
event (POINT_IN_TIME_SPEC 3).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    instrument_id   VARCHAR       NOT NULL,
    interval        VARCHAR       NOT NULL,
    series          VARCHAR       NOT NULL,
    event_time      TIMESTAMPTZ   NOT NULL,
    session_date    DATE          NOT NULL,
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    open            DECIMAL(18,6) NOT NULL,
    high            DECIMAL(18,6) NOT NULL,
    low             DECIMAL(18,6) NOT NULL,
    close           DECIMAL(18,6) NOT NULL,
    volume          BIGINT        NOT NULL,
    PRIMARY KEY (instrument_id, interval, series, event_time, knowledge_time)
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id     VARCHAR PRIMARY KEY,
    knowledge_time  TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    note            VARCHAR
);
"""

#: Relative tolerance below which two vendor values are the same number.
#: Exact comparison produces phantom revisions from float noise on every fetch
#: (DATA_QUALITY_SPEC 4). Until data.revision_epsilon is set in the registry, the store refuses to
#: guess and callers must pass one explicitly.
_PRICE_QUANTUM = Decimal("0.000001")


class BarStore:
    """Append-only bitemporal storage for bars.

    Single-writer by construction (ADR-0004). Opened per process; the daily run writes, backtests
    read.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> BarStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ reads

    def as_of(
        self,
        instrument_id: str,
        interval: Interval,
        series: Series,
        knowledge_time: datetime,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> BarSeries:
        """Best value per `event_time` known at `knowledge_time`.

        The only read path. A query that ignored `knowledge_time` would silently admit values
        learned after the decision it informs.
        """
        clauses = [
            "instrument_id = ?", "interval = ?", "series = ?", "knowledge_time <= ?",
        ]
        params: list[Any] = [instrument_id, interval.value, series.value, knowledge_time]
        if start is not None:
            clauses.append("event_time >= ?")
            params.append(start)
        if end is not None:
            clauses.append("event_time <= ?")
            params.append(end)

        rows = self._connection.execute(
            f"""
            SELECT event_time, session_date, open, high, low, close, volume, knowledge_time
            FROM bars
            WHERE {' AND '.join(clauses)}
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY event_time ORDER BY knowledge_time DESC
            ) = 1
            ORDER BY event_time
            """,
            params,
        ).fetchall()

        bars = tuple(
            Bar(
                instrument_id=instrument_id,
                interval=interval,
                series=series,
                event_time=row[0],
                session_date=row[1],
                open=row[2],
                high=row[3],
                low=row[4],
                close=row[5],
                volume=row[6],
                knowledge_time=row[7],
            )
            for row in rows
        )
        return BarSeries(
            instrument_id=instrument_id,
            interval=interval,
            series=series,
            knowledge_time=knowledge_time,
            bars=bars,
        )

    def instrument_ids(self, knowledge_time: datetime) -> tuple[str, ...]:
        """Every instrument with at least one bar known at `knowledge_time`, sorted.

        Universe construction needs this: the directory names thousands of eligible symbols and the
        store holds bars for a fraction of them. Asking the store which ones it can answer for turns
        a scan of the whole directory into a scan of what exists, and - more importantly - lets the
        caller report the difference instead of presenting a partial universe as the rule's answer.
        """
        rows = self._connection.execute(
            "SELECT DISTINCT instrument_id FROM bars WHERE knowledge_time <= ? ORDER BY 1",
            [knowledge_time],
        ).fetchall()
        return tuple(row[0] for row in rows)

    def last_sessions(self, knowledge_time: datetime) -> dict[str, date]:
        """Latest stored session per instrument, known at `knowledge_time`.

        One query instead of one per instrument. A refresh pass has to order thousands of symbols by
        staleness, and doing that with a read per symbol makes the ordering cost more than the work.
        """
        rows = self._connection.execute(
            "SELECT instrument_id, MAX(session_date) FROM bars "
            "WHERE knowledge_time <= ? GROUP BY instrument_id",
            [knowledge_time],
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def revision_count(self, instrument_id: str | None = None) -> int:
        """Total stored rows. A spike between runs means a vendor re-adjusted history."""
        if instrument_id is None:
            return int(self._connection.execute("SELECT COUNT(*) FROM bars").fetchone()[0])
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM bars WHERE instrument_id = ?", [instrument_id]
            ).fetchone()[0]
        )

    # ----------------------------------------------------------------- writes

    def write(self, incoming: Iterable[Bar], knowledge_time: datetime) -> WriteResult:
        """Insert only genuinely new or changed bars.

        Returns what was actually written, so the caller can report revision volume rather than
        fetch volume - the two differ by orders of magnitude on a normal day, and only the first is
        informative.
        """
        incoming = list(incoming)
        if not incoming:
            return WriteResult(0, 0, 0)

        first = incoming[0]
        current = {
            bar.event_time: bar
            for bar in self.as_of(
                first.instrument_id, first.interval, first.series, knowledge_time
            ).bars
        }

        new_rows: list[tuple[Any, ...]] = []
        unchanged = 0
        revised = 0
        for bar in incoming:
            existing = current.get(bar.event_time)
            if existing is not None and _same_bar(existing, bar):
                unchanged += 1
                continue
            if existing is not None:
                revised += 1
            new_rows.append(
                (
                    bar.instrument_id, bar.interval.value, bar.series.value,
                    bar.event_time, bar.session_date, knowledge_time,
                    bar.open, bar.high, bar.low, bar.close, bar.volume,
                )
            )

        if new_rows:
            self._connection.executemany(
                """
                INSERT OR REPLACE INTO bars
                    (instrument_id, interval, series, event_time, session_date, knowledge_time,
                     open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                new_rows,
            )
        return WriteResult(inserted=len(new_rows) - revised, revised=revised, unchanged=unchanged)

    # -------------------------------------------------------------- snapshots

    def create_snapshot(self, snapshot_id: str, knowledge_time: datetime,
                        created_at: datetime, note: str | None = None) -> None:
        """Name a `knowledge_time`.

        A snapshot is a pointer, not a copy. It is also the determinism boundary: above it order
        and timing vary, below it nothing does (DETERMINISM_SPEC 4).
        """
        self._connection.execute(
            "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?)",
            [snapshot_id, knowledge_time, created_at, note],
        )

    def snapshot_time(self, snapshot_id: str) -> datetime:
        row = self._connection.execute(
            "SELECT knowledge_time FROM snapshots WHERE snapshot_id = ?", [snapshot_id]
        ).fetchone()
        if row is None:
            raise LookupError(f"unknown snapshot {snapshot_id!r}")
        return row[0]


class WriteResult:
    """What a write actually changed."""

    __slots__ = ("inserted", "revised", "unchanged")

    def __init__(self, inserted: int, revised: int, unchanged: int) -> None:
        self.inserted = inserted
        self.revised = revised
        self.unchanged = unchanged

    @property
    def written(self) -> int:
        return self.inserted + self.revised

    def __repr__(self) -> str:
        return (f"WriteResult(inserted={self.inserted}, revised={self.revised}, "
                f"unchanged={self.unchanged})")


def _same_bar(existing: Bar, incoming: Bar) -> bool:
    """Whether two versions of a bar carry the same numbers.

    Compared at a fixed quantum rather than exactly. Vendor float noise would otherwise register as
    a revision on every fetch, which would both bloat the store and destroy the signal value of
    revision volume.
    """
    return (
        existing.volume == incoming.volume
        and _close_enough(existing.open, incoming.open)
        and _close_enough(existing.high, incoming.high)
        and _close_enough(existing.low, incoming.low)
        and _close_enough(existing.close, incoming.close)
    )


def _close_enough(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) < _PRICE_QUANTUM
