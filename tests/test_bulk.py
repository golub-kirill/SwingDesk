"""One statement per chunk, and the three ways that can go wrong.

`executemany` was 97% of a bar write, measured 2026-09-04 by profiling one pass — DuckDB runs the
statement once per parameter set instead of vectorising it, which on a composite primary key is
2.739 ms a row. The same call was in four places: the bar store, corporate actions, the journal's
decisions and the directory pull. **The directory writes 13,339 rows daily** and went from 37
seconds to 0.57.

**Asserted as properties, never as durations.** A timing test on a shared machine fails on a busy
afternoon and gets deleted; what regressed here is the number of statements and whether every row
arrives, and both are checkable exactly.
"""

from __future__ import annotations

import duckdb
import pytest

from swingdesk.platform import bulk


class _Counting:
    """A connection that records the statements it is asked to run."""

    def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
        self._inner = inner
        self.statements: list[str] = []

    def execute(self, sql: str, *args: object, **kwargs: object) -> object:
        self.statements.append(sql)
        return self._inner.execute(sql, *args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


@pytest.fixture
def counted():
    inner = duckdb.connect(":memory:")
    inner.execute("CREATE TABLE t (a VARCHAR, b INTEGER, PRIMARY KEY (a))")
    return _Counting(inner)


def test_a_batch_inside_the_chunk_is_one_statement(counted) -> None:
    """THE REGRESSION. 503 bars used to be 503 statements."""
    bulk.insert_many(counted, "INSERT OR REPLACE INTO t VALUES (?, ?)",
                     [(f"k{n}", n) for n in range(503)])

    assert len(counted.statements) == 1
    assert counted.execute("SELECT count(*) FROM t").fetchone()[0] == 503


def test_a_larger_batch_is_split_and_every_row_arrives(counted) -> None:
    """Both halves matter: the split happens, AND nothing is lost in it.

    A chunking bug that dropped each chunk's last row would still make the statement count right,
    which is why the second assertion is not decoration.
    """
    rows = [(f"k{n}", n) for n in range(2_500)]
    bulk.insert_many(counted, "INSERT OR REPLACE INTO t VALUES (?, ?)", rows)

    inserts = [s for s in counted.statements if "INSERT" in s]
    assert len(inserts) == 3, "2,500 rows at 1,000 a chunk"
    stored = counted.execute("SELECT count(*), min(b), max(b) FROM t").fetchone()
    assert stored == (2_500, 0, 2_499), "every row, including each chunk's boundary"


def test_an_empty_batch_runs_no_statement(counted) -> None:
    """A real case, not defensive noise.

    A run whose only work was managing open positions records no decisions. `executemany` on an
    empty sequence RAISED, which is the bug that found this path; a built `VALUES` list with no
    groups is a syntax error, so the guard has to live here now.
    """
    bulk.insert_many(counted, "INSERT OR REPLACE INTO t VALUES (?, ?)", [])

    assert counted.statements == []


def test_a_statement_without_a_VALUES_group_is_REFUSED(counted) -> None:
    """The placeholder group is read from the statement, so a caller cannot pass a width that
    disagrees with it. A statement this function cannot repeat correctly is refused rather than
    mangled into one that runs and stores the wrong thing."""
    with pytest.raises(ValueError, match="one VALUES group"):
        bulk.insert_many(counted, "INSERT INTO t SELECT * FROM elsewhere", [("k", 1)])


def test_the_chunk_boundary_is_exact(counted) -> None:
    """Exactly `CHUNK` rows is one statement, one more is two. Off-by-one here would either split
    every batch or never split any, and both look like working code."""
    bulk.insert_many(counted, "INSERT OR REPLACE INTO t VALUES (?, ?)",
                     [(f"a{n}", n) for n in range(bulk.CHUNK)])
    assert len(counted.statements) == 1

    counted.statements.clear()
    bulk.insert_many(counted, "INSERT OR REPLACE INTO t VALUES (?, ?)",
                     [(f"b{n}", n) for n in range(bulk.CHUNK + 1)])
    assert len(counted.statements) == 2
