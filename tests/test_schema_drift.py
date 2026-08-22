"""Schema drift: caught at open, migrated when it is safe, refused when it is not.

**This is the test for a defect that killed four trading days silently.** `PR #9` added
`initial_costs_per_share` to `positions` on 2026-08-17. Every store creates its tables with
`CREATE TABLE IF NOT EXISTS`, which does exactly nothing to a table that already exists, so the
column never appeared on disk. From 2026-08-18 the scheduled run died on every evening with
`BinderException: Referenced column ... not found` - both passes, once the 19:30 task was registered
- and nothing raised its voice, because a stack trace in a log file is not a coded refusal.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import duckdb
import pytest

from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.platform.schema import SchemaDrift, declared_columns, reconcile

SCHEMA = """
CREATE TABLE IF NOT EXISTS thing (
    id      VARCHAR NOT NULL,
    weight  DECIMAL(18,6) NOT NULL,
    PRIMARY KEY (id)
);
"""


def _connect(tmp_path, sql: str):
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    con.execute(sql)
    return con


# ------------------------------------------------------------------ the parser


def test_the_expected_columns_are_read_from_the_store_s_own_sql() -> None:
    """Never a second hand-written list. Two declarations of one schema drift apart, which is the
    disease this module treats, one level up."""
    tables = declared_columns(SCHEMA)

    assert list(tables) == ["thing"]
    assert [name for name, _ in tables["thing"]] == ["id", "weight"]
    assert "PRIMARY KEY" not in [name for name, _ in tables["thing"]]


def test_every_real_store_schema_parses() -> None:
    """A positive control against the parser silently returning nothing - which would make
    `reconcile` a no-op that passes everywhere."""
    from swingdesk.journal_evidence import journal, positions
    from swingdesk.market_data import store

    for module, expected in ((store, "bars"), (positions, "positions"), (journal, "runs")):
        tables = declared_columns(module._SCHEMA)
        assert expected in tables, module.__name__
        assert tables[expected], f"{module.__name__}: {expected} parsed with no columns"


# ------------------------------------------------------------------ the behaviour


def test_a_missing_column_on_an_EMPTY_table_is_migrated(tmp_path) -> None:
    con = _connect(tmp_path, "CREATE TABLE thing (id VARCHAR NOT NULL, PRIMARY KEY (id));")

    migrated = reconcile(con, SCHEMA)

    assert migrated == ["thing.weight"]
    assert "weight" in {r[0] for r in con.execute("DESCRIBE thing").fetchall()}


def test_a_missing_column_on_a_POPULATED_table_refuses_and_names_the_drift(tmp_path) -> None:
    """The half that must never auto-migrate. Filling a NOT NULL column on existing rows means
    inventing a value, and "unset is not a default" is as true of a backfill as of a parameter."""
    con = _connect(tmp_path, "CREATE TABLE thing (id VARCHAR NOT NULL, PRIMARY KEY (id));")
    con.execute("INSERT INTO thing VALUES ('a')")

    with pytest.raises(SchemaDrift) as drift:
        reconcile(con, SCHEMA)

    assert drift.value.table == "thing"
    assert drift.value.missing == ["weight"]
    assert drift.value.rows == 1
    assert "weight" in str(drift.value) and "1 row" in str(drift.value)


def test_a_schema_already_in_step_migrates_nothing(tmp_path) -> None:
    """The positive control. Without it every test above passes against a `reconcile` that
    rewrites the table unconditionally."""
    con = _connect(tmp_path, SCHEMA)
    assert reconcile(con, SCHEMA) == []


def test_an_extra_column_on_disk_is_left_alone(tmp_path) -> None:
    """A column the code stopped reading is what an append-only history looks like after a field is
    retired, not a fault to be repaired."""
    con = _connect(tmp_path, SCHEMA)
    con.execute("ALTER TABLE thing ADD COLUMN retired VARCHAR")

    assert reconcile(con, SCHEMA) == []
    assert "retired" in {r[0] for r in con.execute("DESCRIBE thing").fetchall()}


# ------------------------------------------------------------------ the real store, the real defect


def test_a_position_store_missing_the_costs_column_opens_and_heals(tmp_path) -> None:
    """The exact 2026-08-18 failure, reproduced and then fixed by opening the store.

    `positions.duckdb` on the owner's machine held a `positions` table without
    `initial_costs_per_share` and zero rows. Every scheduled run since died selecting it.
    """
    path = tmp_path / "positions.duckdb"
    duckdb.connect(str(path)).execute("""
        CREATE TABLE positions (
            position_id VARCHAR NOT NULL, version INTEGER NOT NULL,
            instrument_id VARCHAR NOT NULL, opened_on DATE NOT NULL,
            entry_price DECIMAL(18,6) NOT NULL, shares INTEGER NOT NULL,
            initial_stop DECIMAL(18,6) NOT NULL, current_stop DECIMAL(18,6) NOT NULL,
            strategy VARCHAR NOT NULL, strategy_version INTEGER NOT NULL,
            knowledge_time TIMESTAMPTZ NOT NULL, closed_on DATE,
            PRIMARY KEY (position_id, version));
    """)

    # Opening it is what heals it - the store refuses to exist against a schema it cannot serve.
    with PositionStore(path) as store:
        assert store.open_as_of(datetime(2026, 8, 22, tzinfo=UTC)) == [], "the read that used to die"

        from swingdesk.contracts.position import Position

        store.record(Position(
            position_id="POS-1", version=1, instrument_id="AAPL", opened_on=date(2026, 8, 10),
            entry_price=Decimal(300), shares=8, initial_stop=Decimal(290),
            current_stop=Decimal(290), initial_costs_per_share=Decimal("1.50"),
            knowledge_time=datetime(2026, 8, 10, tzinfo=UTC),
        ))
        stored = store.open_as_of(datetime(2026, 8, 22, tzinfo=UTC))
        assert stored[0].initial_costs_per_share == Decimal("1.50"), "and it round-trips"
