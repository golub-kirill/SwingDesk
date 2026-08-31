"""Schema drift between a store's code and the file on disk, caught at open rather than at query.

**The defect this exists for, and it cost four trading days.** Every store here creates its tables
with `CREATE TABLE IF NOT EXISTS`. That is correct for a new file and **silently does nothing when a
column is added to an existing one** - the table exists, so the statement is skipped, and the new
column never appears. `PR #9` added `initial_costs_per_share` to `positions` on 2026-08-17. The code
selected it from 2026-08-18 onward; the file on disk never grew it.

The scheduled run then failed with `BinderException: Referenced column ... not found` on **every
evening from 2026-08-18 to 2026-08-21**, including both passes once the 19:30 task was registered.
Nothing noticed, because the failure was a stack trace in a log file rather than a coded refusal, and
`a.run_completes` only reports a number nobody reads between sessions.

**The rule this module enforces: a store never opens against a schema it cannot serve.**

- Missing column, table EMPTY -> migrate it. Lossless and unambiguous: there are no rows to invent a
  value for, and refusing here would make a first-run store unusable for no reason.
- Missing NULLABLE column, table HAS ROWS -> **add it**. This invents nothing: NULL is not a
  default, it is "this row was written before the column existed and nobody asked". Added 2026-08-31
  for `DR-021`, whose `classifications.equity_share` is nullable precisely so an unasked question
  reads as unasked. Refusing here would make a store unopenable to record a fact already true of
  every row in it.
- Missing NOT NULL column, table HAS ROWS -> **refuse, naming the drift**. Filling one on existing
  rows means inventing a value, and "unset is not a default" (`AGENTS.md` §3) is exactly as true of
  a backfill as of a parameter. That is a migration a human decides, not one a constructor performs
  on the way past.

Extra columns on disk are left alone. A column the code stopped reading is not a fault - it is what
an append-only history looks like after a field is retired.
"""

from __future__ import annotations

import re
from typing import Any, Protocol


class _Connection(Protocol):
    """The slice of a DuckDB connection this needs. Typed structurally so neither store has to be
    imported here - `platform` is the lowest layer and must not depend on the ones above it."""

    def execute(self, query: str, parameters: object = ...) -> Any: ...


class SchemaDrift(RuntimeError):
    """The file on disk cannot serve the schema the code expects, and no safe migration exists.

    Carries the table and the columns so the message is actionable rather than a stack trace - the
    failure mode this whole module exists to stop being.
    """

    def __init__(self, table: str, missing: list[str], rows: int) -> None:
        self.table = table
        self.missing = missing
        self.rows = rows
        super().__init__(
            f"table {table!r} on disk is missing column(s) {missing} and holds {rows} row(s), so "
            f"they cannot be added without inventing a value for existing rows. This store will not "
            f"open. Migrate the file deliberately, or move it aside if it is disposable."
        )


#: `CREATE TABLE IF NOT EXISTS <name> ( ... );` - the shape every store in this project declares.
_TABLE = re.compile(
    r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\n\);", re.DOTALL | re.IGNORECASE
)


def declared_statements(schema_sql: str) -> dict[str, str]:
    """The full `CREATE TABLE` statement per table, as the store declares it."""
    return {
        name: f"CREATE TABLE IF NOT EXISTS {name} ({body}\n);"
        for name, body in _TABLE.findall(schema_sql)
    }


def declared_columns(schema_sql: str) -> dict[str, list[tuple[str, str]]]:
    """Parse a store's own `_SCHEMA` into `{table: [(column, type), ...]}`.

    Read from the SQL the store already declares rather than from a second hand-written list, so the
    two can never disagree - the same rule `AGENTS.md` §10.5 applies to counts, applied to a schema.
    """
    tables: dict[str, list[tuple[str, str]]] = {}
    for name, body in _TABLE.findall(schema_sql):
        columns: list[tuple[str, str]] = []
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "--")):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                columns.append((parts[0], parts[1].strip()))
        tables[name] = columns
    return tables


def reconcile(connection: _Connection, schema_sql: str) -> list[str]:
    """Bring the file in line with `schema_sql`, or raise `SchemaDrift`. Returns what it migrated.

    Called after the store has run its own `CREATE TABLE IF NOT EXISTS`, so every table exists and
    the only question left is whether each has the columns the code will ask for.
    """
    migrated: list[str] = []
    statements = declared_statements(schema_sql)
    for table, columns in declared_columns(schema_sql).items():
        actual = {
            row[0] for row in connection.execute(f"DESCRIBE {table}").fetchall()
        }
        missing = [name for name, _ in columns if name not in actual]
        if not missing:
            continue

        rows = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if rows:
            declared = dict(columns)
            required = [name for name in missing if "NOT NULL" in declared[name].upper()]
            if required:
                raise SchemaDrift(table, required, rows)

            # A NULLABLE column added to a populated table INVENTS NOTHING, and that is the whole
            # of why this branch exists. The refusal above is about `NOT NULL`: filling one on
            # existing rows means choosing a value nobody measured, and "unset is not a default"
            # (`AGENTS.md` §3). NULL is not a default - it is precisely "this row was written
            # before the column existed, and nobody asked". Refusing here would have made a store
            # unopenable to record a fact that is already true of every row in it.
            #
            # `DR-021` is what surfaced the distinction: `classifications.equity_share` is nullable
            # by design, because a classification stored before the vendor was asked what share is
            # equity has no answer and must not be given one. `ALTER` rather than the DROP below
            # for the obvious reason - there are rows to keep.
            for name in missing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declared[name]}")
            migrated.extend(f"{table}.{name}" for name in missing)
            continue

        # DROP and re-create rather than ALTER, for two reasons. DuckDB refuses
        # `ADD COLUMN ... NOT NULL` outright ("adding columns with constraints not yet supported"),
        # and adding the column without its constraint would leave the file quietly weaker than the
        # schema that describes it - a second, subtler drift in place of the one being repaired.
        # Re-creating restores the declared types, the NOT NULLs and the primary key exactly, and is
        # lossless BY DEFINITION here: this branch is only reached when the table holds no rows.
        connection.execute(f"DROP TABLE {table}")
        connection.execute(statements[table])
        migrated.extend(f"{table}.{name}" for name in missing)
    return migrated
