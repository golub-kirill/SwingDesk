"""One-minute bars for the few sessions a daily bar cannot settle (`DR-042` §9). Bitemporal.

**Why a store and not a fetch inside the backtest.** A backtest reads what was known at an instant
and nothing else (`POINT_IN_TIME_SPEC` 2); a study that called a vendor while it ran would answer a
different question every time the vendor revised a minute, and could not be replayed. So minutes are
fetched by a tool (`tools/fetch_minutes.py`), written here with the instant they were learned, and
read back as-of like every bar in `store.py`.

**A session nobody fetched is not a session that printed nothing.** `minute_fetches` records every
fetch, served or empty, so `session` can answer three different things: never fetched (`None`),
fetched and empty (`()`), and the minutes themselves. Collapsing the first two is how a gap in the
data gets read as a fact about the market.

**Volume and the vendor's VWAP ride along when served**, as nullable columns: a rule that trails a
stop at the session's VWAP (the intraday momentum family `CHARTER` A-003 names) cannot be priced
from four prices, and the minutes fetched before 2026-09-19 read back without them - `None`, never
an invented zero.
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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS minute_bars (
    instrument_id   VARCHAR       NOT NULL,
    session_date    DATE          NOT NULL,
    minute          TIMESTAMPTZ   NOT NULL,
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    open            DECIMAL(18,6) NOT NULL,
    high            DECIMAL(18,6) NOT NULL,
    low             DECIMAL(18,6) NOT NULL,
    close           DECIMAL(18,6) NOT NULL,
    volume          BIGINT,
    vwap            DECIMAL(18,6),
    PRIMARY KEY (instrument_id, minute, knowledge_time)
);

CREATE TABLE IF NOT EXISTS minute_fetches (
    instrument_id   VARCHAR       NOT NULL,
    session_date    DATE          NOT NULL,
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    source          VARCHAR       NOT NULL,
    minutes         INTEGER       NOT NULL,
    PRIMARY KEY (instrument_id, session_date, knowledge_time)
);
"""


def _basis(source: str) -> str | None:
    """The price basis a source string claims, or `None` when it claims none.

    `alpaca:sip:split` -> `split`. Two fields or fewer is a source from before the convention and
    says nothing about adjustment; guessing one would be inventing a claim to then enforce.
    """
    parts = source.split(":")
    return parts[-1] if len(parts) >= 3 else None


@dataclass(frozen=True, slots=True)
class Minute:
    """One one-minute bar: the instant it STARTED, its four prices, and - when the vendor served
    them - the shares traded and their volume-weighted price."""

    at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None = None
    vwap: Decimal | None = None


class MinuteStore:
    """Append-only bitemporal storage for one-minute bars. Single-writer, like `BarStore`."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)
        schema.reconcile(self._connection, _SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> MinuteStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write(self, instrument_id: str, session_date: date, minutes: Iterable[Minute],
              knowledge_time: datetime, source: str) -> int:
        """Record one fetch of one session - its minutes, and the fact that it was fetched."""
        rows = [(instrument_id, session_date, m.at, knowledge_time, m.open, m.high, m.low, m.close,
                 m.volume, m.vwap)
                for m in minutes]
        insert_many(self._connection,
                    "INSERT OR REPLACE INTO minute_bars (instrument_id, session_date, minute, "
                    "knowledge_time, open, high, low, close, volume, vwap) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        # A SECOND PRICE BASIS IS REFUSED, not merged. `INSERT OR REPLACE` would have taken it
        # happily and left an instrument whose sessions sit on two price scales - unreadable rather
        # than untidy, because nothing downstream carries the basis and an overnight return is a
        # ratio of two sessions' prices. `PR-025` is what that costs: a REJECT that was a unit
        # error.
        #
        # The ADJUSTMENT only, which is the last field of `alpaca:{feed}:{adjustment}`. A feed
        # difference is a data-quality question and not two scales, and a source not in that shape
        # makes no basis claim at all - a store written before these columns existed carries `old`,
        # and re-sourcing it is legitimate. Accusing on a shape this cannot read is the mistake it
        # is here to prevent.
        incoming = _basis(source)
        if incoming is not None:
            held = {
                basis for basis in (
                    _basis(str(row[0])) for row in self._connection.execute(
                        "SELECT DISTINCT source FROM minute_fetches WHERE instrument_id = ?",
                        [instrument_id]).fetchall())
                if basis is not None
            }
            if held - {incoming}:
                raise ValueError(
                    f"{instrument_id}: this store already holds minutes adjusted "
                    f"{sorted(held)} and this fetch is {incoming!r}. Two price bases in one "
                    f"instrument's minutes make an overnight ratio cross a split on mismatched "
                    f"numbers. Fetch into a separate store, or re-fetch the whole instrument on "
                    f"one basis."
                )
        self._connection.execute(
            "INSERT OR REPLACE INTO minute_fetches VALUES (?, ?, ?, ?, ?)",
            [instrument_id, session_date, knowledge_time, source, len(rows)])
        return len(rows)

    def sources(self, instrument_id: str, knowledge_time: datetime) -> tuple[str, ...]:
        """Every price basis this instrument's minutes were fetched under, as known at an instant.

        **One element, or the series is not comparable to itself.** The source string carries the
        feed AND the adjustment - `alpaca:sip:split` against `alpaca:sip:raw` - and an overnight
        return is a ratio of two sessions' prices. Two bases in one instrument's history means that
        ratio crosses a split on mismatched numbers, silently, on exactly the sessions a split makes
        interesting.

        The fetch table has always recorded it; nothing read it. `minute_bars` carries no basis and
        `session()` cannot join to one without deciding which fetch a minute belongs to, so the
        question is asked here, by the study, before it reads anything. `PR-025` is what an
        unchecked price basis costs: a REJECT that was a unit error, and `AGENTS.md` §12 carries it
        as *tape prices are unadjusted*.
        """
        rows = self._connection.execute(
            "SELECT DISTINCT source FROM minute_fetches "
            "WHERE instrument_id = ? AND knowledge_time <= ? ORDER BY source",
            [instrument_id, knowledge_time]).fetchall()
        return tuple(str(row[0]) for row in rows)

    def session(self, instrument_id: str, session_date: date,
                knowledge_time: datetime) -> tuple[Minute, ...] | None:
        """The session's minutes as known at `knowledge_time`, in time order.

        `None` when no fetch of the session is known at that instant; `()` when one is and it served
        nothing. The latest version of each minute wins, as in `BarStore.as_of`.
        """
        fetched = self._connection.execute(
            "SELECT count(*) FROM minute_fetches "
            "WHERE instrument_id = ? AND session_date = ? AND knowledge_time <= ?",
            [instrument_id, session_date, knowledge_time]).fetchone()
        if fetched is None or fetched[0] == 0:
            return None
        rows = self._connection.execute(
            """
            SELECT minute, open, high, low, close, volume, vwap FROM minute_bars
            WHERE instrument_id = ? AND session_date = ? AND knowledge_time <= ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY minute ORDER BY knowledge_time DESC) = 1
            ORDER BY minute
            """,
            [instrument_id, session_date, knowledge_time]).fetchall()
        return tuple(Minute(at=row[0], open=row[1], high=row[2], low=row[3], close=row[4],
                            volume=None if row[5] is None else int(row[5]), vwap=row[6])
                     for row in rows)
