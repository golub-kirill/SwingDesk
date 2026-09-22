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


def test_a_second_price_basis_is_refused(tmp_path: Path) -> None:
    """Two adjustments in one instrument's minutes make an overnight ratio cross a split wrong.

    `minute_fetches` has recorded the basis since it was written and NOTHING read it: `minute_bars`
    carries none, `session()` never joined to the fetch table, and `write()` took any source. A
    `--adjustment raw` probe into a `split` store left a series whose sessions sit on two price
    scales, silently, on exactly the sessions a split makes interesting. `PR-025` is what an
    unchecked price basis costs - a REJECT that was a unit error.
    """
    import pytest

    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "alpaca:sip:split")
        with pytest.raises(ValueError, match=r"[Tt]wo price bases"):
            store.write("SPY", SESSION + timedelta(days=1), [_minute(1)], KNOWN, "alpaca:sip:raw")


def test_the_same_basis_from_another_feed_is_allowed(tmp_path: Path) -> None:
    """A feed difference is a data-quality question, not two price scales.

    `alpaca:iex:split` and `alpaca:sip:split` are the same numbers from different tapes. Refusing
    that would be guarding the wrong field, and a guard that fires on the wrong thing gets removed.
    """
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "alpaca:sip:split")
        store.write("SPY", SESSION + timedelta(days=1), [_minute(1)], KNOWN, "alpaca:iex:split")
        assert store.sources("SPY", KNOWN) == ("alpaca:iex:split", "alpaca:sip:split")


def test_a_source_that_claims_no_basis_is_not_accused(tmp_path: Path) -> None:
    """A store written before the convention carries `old`, and re-sourcing it is legitimate.

    The first cut refused any source that differed at all and broke the migration test. Accusing on
    a shape the check cannot read is the mistake it exists to prevent.
    """
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "old")
        store.write("SPY", SESSION + timedelta(days=1), [_minute(1)], KNOWN, "new")
        assert store.sources("SPY", KNOWN) == ("new", "old")


def test_another_instrument_is_its_own_question(tmp_path: Path) -> None:
    """One store may hold two instruments on two bases; a RATIO is only ever within one."""
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "alpaca:sip:split")
        store.write("QQQ", SESSION, [_minute(1)], KNOWN, "alpaca:sip:raw")
        assert store.sources("SPY", KNOWN) == ("alpaca:sip:split",)
        assert store.sources("QQQ", KNOWN) == ("alpaca:sip:raw",)


def test_sources_are_read_as_of_a_knowledge_time(tmp_path: Path) -> None:
    """A study asks what it is reading AT its pinned instant, like every other read here."""
    later = KNOWN + timedelta(days=1)
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], later, "alpaca:sip:split")
        assert store.sources("SPY", KNOWN) == ()
        assert store.sources("SPY", later) == ("alpaca:sip:split",)


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
