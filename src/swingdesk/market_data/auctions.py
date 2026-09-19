"""The opening and closing auction prints of a session. Bitemporal. `PR-025`.

**Why the auction and not the bar.** An order that joins the opening or closing auction pays the
cross's single price and no quoted spread, and `PR-024` priced only orders meeting the continuous
book. The stored daily bar's open is not always that price: on a probe of twelve `PR-024` entries
the close matched the listing market's closing cross every time and the open matched its opening
cross ten times in twelve, missing by up to 0.3% where the first trade of the day came before the
cross. So the prints are read from the SIP trade tape, which flags them, and kept here.

**Prints are stored as served, the choice is the study's.** A window holds every print the tape
flagged as an opening or closing trade or an official open or close - from the listing market and
from every other market center that stamps its own. Which one is THE cross is a rule, and it can
only be revisited if the store did not apply it first.

**A print's price is what TRADED, never adjusted.** The bars and minutes in this project carry every
later split and spin-off; the tape does not. A reader pricing a cross against them must bring the
two onto one basis first - `PR-025`'s registered run did not, and read a 2-for-1 split as a 50%
loss (`run_pr025.adjustment_factor`, its amendment A-1).

**Never fetched, fetched with nothing flagged, and prints are three answers**, kept apart as
`MinuteStore` and `QuoteStore` keep them.
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

#: The two auctions a window may be named for.
OPENING = "opening"
CLOSING = "closing"
SIDES = (OPENING, CLOSING)

#: The trade conditions a stored print carries at least one of. `O` opening trade and `6` closing
#: trade are the crosses themselves; `Q` and `M` are each market center's official open and close.
#: The same letters on all three tapes (Alpaca's condition tables, read 2026-09-19).
FLAGS = frozenset({"O", "Q", "6", "M"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS auction_prints (
    instrument_id   VARCHAR       NOT NULL,
    session_date    DATE          NOT NULL,
    side            VARCHAR       NOT NULL,
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    ordinal         INTEGER       NOT NULL,
    printed_at      TIMESTAMPTZ   NOT NULL,
    price           DECIMAL(18,6) NOT NULL,
    size            BIGINT        NOT NULL,
    exchange        VARCHAR       NOT NULL,
    conditions      VARCHAR       NOT NULL,
    PRIMARY KEY (instrument_id, session_date, side, knowledge_time, ordinal)
);

CREATE TABLE IF NOT EXISTS auction_fetches (
    instrument_id   VARCHAR       NOT NULL,
    session_date    DATE          NOT NULL,
    side            VARCHAR       NOT NULL,
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    requested_at    TIMESTAMPTZ   NOT NULL,
    source          VARCHAR       NOT NULL,
    prints          INTEGER       NOT NULL,
    trades_scanned  INTEGER       NOT NULL,
    PRIMARY KEY (instrument_id, session_date, side, knowledge_time)
);
"""


@dataclass(frozen=True, slots=True)
class Print:
    """One flagged trade: when, at what price, how many shares, where, and every condition."""

    at: datetime
    price: Decimal
    size: int
    exchange: str
    conditions: tuple[str, ...]


class UnknownSide(ValueError):
    """An auction this store does not name."""


def _check(side: str) -> None:
    if side not in SIDES:
        raise UnknownSide(f"{side!r} is not one of {SIDES}")


class AuctionStore:
    """Append-only bitemporal storage for auction windows. Single-writer, like `QuoteStore`."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)
        schema.reconcile(self._connection, _SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> AuctionStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write(self, instrument_id: str, session_date: date, side: str, requested_at: datetime,
              prints: Iterable[Print], trades_scanned: int, knowledge_time: datetime,
              source: str) -> int:
        """Record one fetch of one auction window: its flagged prints in tape order, and the fetch."""
        _check(side)
        rows = [(instrument_id, session_date, side, knowledge_time, ordinal, p.at, p.price, p.size,
                 p.exchange, ",".join(p.conditions))
                for ordinal, p in enumerate(prints)]
        insert_many(self._connection,
                    "INSERT OR REPLACE INTO auction_prints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    rows)
        self._connection.execute(
            "INSERT OR REPLACE INTO auction_fetches VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [instrument_id, session_date, side, knowledge_time, requested_at, source, len(rows),
             trades_scanned])
        return len(rows)

    def window(self, instrument_id: str, session_date: date, side: str,
               knowledge_time: datetime) -> tuple[Print, ...] | None:
        """The prints of the latest fetch known at `knowledge_time`, in tape order.

        `None` when no fetch is known; an empty tuple when one is and the tape flagged nothing.
        """
        _check(side)
        fetch = self._connection.execute(
            """
            SELECT knowledge_time FROM auction_fetches
            WHERE instrument_id = ? AND session_date = ? AND side = ? AND knowledge_time <= ?
            ORDER BY knowledge_time DESC LIMIT 1
            """,
            [instrument_id, session_date, side, knowledge_time]).fetchone()
        if fetch is None:
            return None
        rows = self._connection.execute(
            """
            SELECT printed_at, price, size, exchange, conditions FROM auction_prints
            WHERE instrument_id = ? AND session_date = ? AND side = ? AND knowledge_time = ?
            ORDER BY ordinal
            """,
            [instrument_id, session_date, side, fetch[0]]).fetchall()
        return tuple(Print(at=row[0], price=row[1], size=int(row[2]), exchange=row[3],
                           conditions=tuple(c for c in row[4].split(",") if c))
                     for row in rows)

    def fetched(self, instrument_id: str, session_date: date, side: str,
                knowledge_time: datetime) -> bool:
        """Whether any fetch of the window is known at `knowledge_time`. For a tool's skip check."""
        _check(side)
        row = self._connection.execute(
            "SELECT count(*) FROM auction_fetches WHERE instrument_id = ? AND session_date = ? "
            "AND side = ? AND knowledge_time <= ?",
            [instrument_id, session_date, side, knowledge_time]).fetchone()
        return bool(row and row[0])
