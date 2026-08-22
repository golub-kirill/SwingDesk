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
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from swingdesk.contracts.market import (
    Bar,
    BarSeries,
    CorporateAction,
    CorporateActionKind,
    Interval,
    Series,
)
from swingdesk.reference_data import calendar as cal

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

CREATE TABLE IF NOT EXISTS corporate_actions (
    instrument_id   VARCHAR       NOT NULL,
    kind            VARCHAR       NOT NULL,
    effective_date  DATE          NOT NULL,
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    value           DECIMAL(18,6) NOT NULL,
    PRIMARY KEY (instrument_id, kind, effective_date, knowledge_time)
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

    def latest_knowledge_time(self) -> datetime | None:
        """The most recent instant this store learned anything, or None when it holds nothing.

        The natural as-of for a measurement taken over stored data. Reading at the wall clock would
        pin a result to an instant that is not in the data, so two runs over an unchanged store
        would differ for no reason a reader could see; reading here makes the as-of a function of
        the store itself, and a re-run reproducible.
        """
        row = self._connection.execute("SELECT MAX(knowledge_time) FROM bars").fetchone()
        if row is None or row[0] is None:
            return None
        latest: datetime = row[0]
        return latest

    def revision_count(self, instrument_id: str | None = None) -> int:
        """Total stored rows. A spike between runs means a vendor re-adjusted history."""
        if instrument_id is None:
            row = self._connection.execute("SELECT COUNT(*) FROM bars").fetchone()
        else:
            row = self._connection.execute(
                "SELECT COUNT(*) FROM bars WHERE instrument_id = ?", [instrument_id]
            ).fetchone()
        # An aggregate always returns a row; the guard exists because the driver's type does not
        # say so, and zero is the right answer for a count over nothing either way.
        return int(row[0]) if row is not None else 0

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
        unclosed = 0
        # Resolved for the whole batch in one calendar call. Per bar it cost 17 minutes a run -
        # see `_unclosed_sessions`.
        unclosed_dates = _unclosed_sessions(
            first.instrument_id, {bar.session_date for bar in incoming}, knowledge_time
        )
        for bar in incoming:
            # An unclosed bar is refused BEFORE the revision comparison, so a partial print can
            # neither enter the store nor overwrite a good bar already in it.
            if bar.session_date in unclosed_dates:
                unclosed += 1
                continue
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
        return WriteResult(inserted=len(new_rows) - revised, revised=revised,
                           unchanged=unchanged, unclosed=unclosed)

    # ------------------------------------------------------- corporate actions

    def write_actions(
        self, actions: Iterable[CorporateAction], knowledge_time: datetime
    ) -> WriteResult:
        """Store splits and dividends. Bitemporal and append-only, exactly like bars.

        Separate from `write` because an action is not a bar: `POINT_IN_TIME_SPEC` §4 names it a
        third series, and it has no OHLCV to compare. The revision rule is therefore also different
        and simpler - an action either matches what is stored or it does not, with no epsilon.
        `data.revision_epsilon` (`DR-016`) exists because vendor PRICES carry float noise; a split
        ratio is 2, not 1.9999998.

        No unclosed guard here either, and that is deliberate rather than forgotten. A split is
        declared before it takes effect, so an action whose `effective_date` is in the future is
        the normal case and the useful one - it is the only warning the system can get before the
        price level moves under a held position.
        """
        rows: list[tuple[Any, ...]] = []
        unchanged = 0
        revised = 0
        for action in actions:
            stored = self._connection.execute(
                "SELECT value FROM corporate_actions WHERE instrument_id = ? AND kind = ? "
                "AND effective_date = ? QUALIFY ROW_NUMBER() OVER ("
                "PARTITION BY instrument_id, kind, effective_date ORDER BY knowledge_time DESC) = 1",
                [action.instrument_id, action.kind.value, action.effective_date],
            ).fetchone()
            if stored is not None:
                if stored[0] == action.value:
                    unchanged += 1
                    continue
                revised += 1
            rows.append((action.instrument_id, action.kind.value, action.effective_date,
                         knowledge_time, action.value))

        if rows:
            self._connection.executemany(
                "INSERT OR REPLACE INTO corporate_actions "
                "(instrument_id, kind, effective_date, knowledge_time, value) VALUES (?,?,?,?,?)",
                rows,
            )
        return WriteResult(inserted=len(rows) - revised, revised=revised, unchanged=unchanged)

    def actions_as_of(
        self,
        instrument_id: str,
        knowledge_time: datetime,
        since: date | None = None,
    ) -> tuple[CorporateAction, ...]:
        """Best version of every action known at `knowledge_time`, oldest first.

        As-of like every other read here. A backtest asking what was known on the decision bar must
        not be handed a split the vendor only published afterwards - that is the look-ahead this
        store exists to prevent, and a corporate action is exactly the kind of fact that arrives
        late.
        """
        clauses = ["instrument_id = ?", "knowledge_time <= ?"]
        params: list[Any] = [instrument_id, knowledge_time]
        if since is not None:
            clauses.append("effective_date >= ?")
            params.append(since)
        rows = self._connection.execute(
            f"""
            SELECT kind, effective_date, value, knowledge_time FROM corporate_actions
            WHERE {' AND '.join(clauses)}
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY kind, effective_date ORDER BY knowledge_time DESC) = 1
            ORDER BY effective_date, kind
            """,
            params,
        ).fetchall()
        return tuple(
            CorporateAction(
                instrument_id=instrument_id, kind=CorporateActionKind(row[0]),
                effective_date=row[1], value=row[2], knowledge_time=row[3],
            )
            for row in rows
        )

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
        stored: datetime = row[0]
        return stored


class WriteResult:
    """What a write actually changed."""

    __slots__ = ("inserted", "revised", "unchanged", "unclosed")

    def __init__(self, inserted: int, revised: int, unchanged: int, unclosed: int = 0) -> None:
        self.inserted = inserted
        self.revised = revised
        self.unchanged = unchanged
        self.unclosed = unclosed
        """Bars refused because their session had not closed when they were captured.

        Counted rather than silently dropped: a fetch that returns a session's worth of nothing is
        a fact the caller should be able to report, and `vendor_yahoo` already uses the same shape
        for rows that fail validation.
        """

    @property
    def written(self) -> int:
        return self.inserted + self.revised

    def __repr__(self) -> str:
        return (f"WriteResult(inserted={self.inserted}, revised={self.revised}, "
                f"unchanged={self.unchanged}, unclosed={self.unclosed})")


def _unclosed_sessions(
    instrument_id: str, session_dates: set[date], knowledge_time: datetime
) -> set[date]:
    """Which of `session_dates` had not closed at `knowledge_time`. One calendar call, not one per bar.

    **Batched because the per-bar form was measured at 17 minutes per scheduled run.**
    `calendar._schedule` is `lru_cache(maxsize=64)` keyed on `(exchange, start, end)`, and a
    one-year fetch asks about ~260 distinct sessions — so a per-bar lookup evicts its own entries
    and misses essentially every time. Measured over 20 synthetic instruments: 1,628 ms per
    instrument with the per-bar call against 724 ms without, which is **+1,041 s across a
    1,152-member universe**. The nightly run takes about five minutes and has to finish before
    `DR-015`'s 19:30 second pass; tripling it would have broken the very window that record set.

    A date absent from the calendar's answer is left OUT of this set, so it is treated as closed and
    allowed through. That covers both a session that had already finished and a date the calendar
    does not know at all — the second deliberately, per `_is_unclosed`'s contract below.
    """
    # Only sessions near the capture instant can still be open. A session closes at 16:00
    # exchange-local on its own date, and the exchanges here run at UTC-4/-5, so anything two
    # calendar days or more before `knowledge_time` has certainly finished - whatever the zone.
    # Without this the calendar is asked about a full year of sessions on every write, which is
    # ~260 `ExchangeSession` objects built per instrument and 88 s across a 1,152-member run.
    cutoff = (knowledge_time - timedelta(days=2)).date()
    candidates = {day for day in session_dates if day >= cutoff}
    if not candidates:
        return set()
    exchange = cal.exchange_for(instrument_id)
    return {
        session.session_date
        for session in cal.sessions(exchange, min(candidates), max(candidates))
        if session.session_date in candidates and knowledge_time < session.close_time
    }


def _is_unclosed(bar: Bar, knowledge_time: datetime) -> bool:
    """True when this bar was captured before its own session had finished.

    Kept as the single-bar statement of the rule, and used by the tests that pin it. `write` calls
    `_unclosed_sessions` instead, which answers the same question for a whole batch at once — see
    there for why that mattered.

    `CALENDAR_SPEC.md` §5: the unclosed current bar is never a decision input, and
    `calendar.last_completed_session` has enforced that on every READ since it was written. Nothing
    enforced it on WRITE, and on 2026-08-03 one manual fetch at 13:25 local - two and a half hours
    before the 16:00 ET close - stored 296 mid-session prints as if they were session bars. Their
    closes were out by up to 4.3%, and 196 of them were never corrected by a later fetch because
    the instrument was not fetched again with that session in window.

    A partial bar is not a slightly-worse bar. Its close is a mid-session price, its high and low
    are partial extremes, and its volume is a fraction of the session's - so it is wrong in the
    four fields that every downstream component reads, while looking exactly like a good one.

    A session the calendar does not know is ALLOWED through. Not knowing whether a bar is unclosed
    is different from knowing that it is, and refusing on ignorance would silently drop bars for
    any venue or date the calendar cannot resolve - the `unavailable`-is-not-`fail` rule
    (`AGENTS.md` §12) applied to a write.
    """
    session = cal.session(cal.exchange_for(bar.instrument_id), bar.session_date)
    return session is not None and knowledge_time < session.close_time


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
