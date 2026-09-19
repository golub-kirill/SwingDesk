"""`MinuteStore`: volume and the vendor's VWAP, stored when served and never invented.

A store written before the two columns existed must open, keep its minutes, and read them back
with `None` - a zero would be a volume nobody measured.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb

from swingdesk.market_data.minutes import Minute, MinuteStore

SESSION = date(2026, 9, 15)
OPENED = datetime(2026, 9, 15, 13, 30, tzinfo=UTC)
KNOWN = datetime(2026, 9, 16, 1, 0, tzinfo=UTC)


def _minute(i: int, volume: int | None = None, vwap: str | None = None) -> Minute:
    price = Decimal("100") + i
    return Minute(at=OPENED + timedelta(minutes=i), open=price, high=price, low=price, close=price,
                  volume=volume, vwap=None if vwap is None else Decimal(vwap))


def test_volume_and_vwap_round_trip(tmp_path: Path) -> None:
    served = [_minute(0, 5000, "100.02"), _minute(1, 7000, "101.01")]
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, served, KNOWN, "test")
        assert store.session("SPY", SESSION, KNOWN) == tuple(served)


def test_a_minute_served_without_volume_reads_back_without_it(tmp_path: Path) -> None:
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "test")
        [got] = store.session("SPY", SESSION, KNOWN)
    assert got.volume is None and got.vwap is None


def test_a_store_written_before_the_columns_opens_and_keeps_its_minutes(tmp_path: Path) -> None:
    """THE MIGRATION. The old four-price table gains two empty columns; nothing is invented."""
    path = tmp_path / "old.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("""
        CREATE TABLE minute_bars (
            instrument_id VARCHAR NOT NULL, session_date DATE NOT NULL,
            minute TIMESTAMPTZ NOT NULL, knowledge_time TIMESTAMPTZ NOT NULL,
            open DECIMAL(18,6) NOT NULL, high DECIMAL(18,6) NOT NULL,
            low DECIMAL(18,6) NOT NULL, close DECIMAL(18,6) NOT NULL,
            PRIMARY KEY (instrument_id, minute, knowledge_time));
        CREATE TABLE minute_fetches (
            instrument_id VARCHAR NOT NULL, session_date DATE NOT NULL,
            knowledge_time TIMESTAMPTZ NOT NULL, source VARCHAR NOT NULL,
            minutes INTEGER NOT NULL, PRIMARY KEY (instrument_id, session_date, knowledge_time));
    """)
    connection.execute("INSERT INTO minute_bars VALUES ('SPY', ?, ?, ?, 100, 101, 99, 100.5)",
                       [SESSION, OPENED, KNOWN])
    connection.execute("INSERT INTO minute_fetches VALUES ('SPY', ?, ?, 'old', 1)", [SESSION, KNOWN])
    connection.close()

    with MinuteStore(path) as store:
        [old] = store.session("SPY", SESSION, KNOWN)
        assert old.close == Decimal("100.5") and old.volume is None and old.vwap is None
        store.write("SPY", date(2026, 9, 16), [_minute(0, 900, "100.4")], KNOWN, "new")
        [new] = store.session("SPY", date(2026, 9, 16), KNOWN)
        assert new.volume == 900 and new.vwap == Decimal("100.4")
