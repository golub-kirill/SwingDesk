"""One statement per chunk, for every store that writes a batch.

**`executemany` is the slow path in DuckDB and it was in four places.** Measured 2026-09-04 by
profiling a bar write: `_duckdb.executemany` was 11.369 seconds of an 11.701-second pass — 97% —
because DuckDB runs the statement once per parameter set rather than vectorising it. On a table with
a composite primary key that is **2.739 ms a row**, for an engine built for bulk.

    executemany                      2.739 ms/row
    one VALUES statement per chunk   0.087 ms/row     31x
    a registered pandas relation     0.022 ms/row    125x

The middle one is here. The pandas relation is faster and would put a DataFrame into every storage
module to save seconds on passes whose time is elsewhere; these modules import `duckdb` and nothing
else, and that is worth more than the remaining difference.

**Which writes it matters for, stated so nobody expects a speed-up where there is none.** The cost
is per NEW row, so it lands on the batch writes and not on the incremental ones:

  - `directory.record` writes **13,339 rows on every pull**, daily;
  - `journal.record_decisions` writes one row per universe member, **twice an evening**;
  - `store.write` writes ~503 for an instrument the store has never seen, which is the coverage
    backfill — and about one for an instrument it has, which is every evening.

**Extracted rather than copied.** The bar store had this fix first and the same three lines were
about to appear in three more modules; `AGENTS.md` §10.5's argument about copies of a fact applies
to copies of a mechanism, and the specification's §8 forbids one logic in two places.
"""

from __future__ import annotations

from typing import Any

#: How many rows go into one statement. Bounded so a caller handing over a decade of half-hourly
#: bars cannot build a statement with a hundred thousand placeholders; 1,000 rows of an eleven-column
#: table is 11,000 parameters, which is comfortable, and it is above every batch this system writes
#: except a full directory pull - so the ordinary case is a single statement.
CHUNK = 1_000


def insert_many(connection: Any, statement: str, rows: list[tuple[Any, ...]]) -> None:
    """Run `statement` once per chunk of `rows` instead of once per row.

    `statement` carries a single `VALUES` placeholder group — `INSERT INTO t VALUES (?, ?, ?)` —
    which is repeated per row in the chunk. The group is taken from the statement itself rather than
    from a column count, so a caller cannot pass a statement and a width that disagree.

    **An empty batch runs nothing**, and that is a real case rather than an edge: a run whose only
    work was managing open positions records no decisions, and `executemany` on an empty sequence
    RAISED where it should have done nothing.

    It needs no guard here, which is worth saying because the first draft had one. `range(0, 0,
    CHUNK)` does not iterate, so the loop below never builds an empty `VALUES` list — and a
    mutation that deleted the early return passed every test, correctly. The docstring claimed the
    guard was load-bearing and it was not; `AGENTS.md` §10.8 says a claim about coverage is itself
    a claim, and this is that rule applied to a claim about a line of code.
    """
    head, _, group = statement.rpartition("VALUES")
    group = group.strip()
    if not head or not group.startswith("(") or not group.endswith(")"):
        raise ValueError(
            f"insert_many needs a statement ending in one VALUES group, got {statement!r}"
        )

    for start in range(0, len(rows), CHUNK):
        chunk = rows[start:start + CHUNK]
        connection.execute(
            f"{head}VALUES {', '.join([group] * len(chunk))}",
            [value for row in chunk for value in row],
        )
