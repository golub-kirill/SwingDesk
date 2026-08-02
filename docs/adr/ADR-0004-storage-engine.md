# ADR-0004 — Storage engine

- **Status:** Proposed
- **Date:** 2026-08-02

## Context

Owner decision D4 fixed *local database, Firebase for push only*, without naming the engine. Two
stores are needed and they have different shapes:

| Store | Shape | Dominant query |
|---|---|---|
| **bars** | ~20M rows, append-only, bitemporal | *"latest value per `event_time` where `knowledge_time <= K`"* — runs on **every bar of every backtest** |
| **journal** | small, append-only, relational, audited | joins across 12 entities, transactional integrity |

Constraints: single user, single machine, one daily run, no server to operate, $0/month
(`NFR.md` §6), and reproducibility depends on the store returning identical results for identical
queries (`DETERMINISM_SPEC.md`).

## Decision

**DuckDB for both**, one embedded database file.

## Alternatives considered

- **Parquet for bars + SQLite for journal.** Cheap and portable, and Parquet is a good fit for
  columnar bars. Rejected because it is two mechanisms to maintain and the as-of query would be
  hand-rolled over file partitions — reimplementing, badly, what a database already does. DuckDB
  reads Parquet natively, so this remains available as an export format without being the store.
- **SQLite for both.** Stdlib, transactional, trivially backed up. Rejected on the as-of query:
  row-oriented scanning over ~20M rows is the one axis that would bite first, and it is the query on
  the hot path. Probably acceptable today; a poor thing to discover is not, mid-backtest.
- **PostgreSQL.** Most capable, real temporal support. Rejected as operational weight: a server to
  install, run, secure and back up, for one user on one machine — this project has avoided that
  everywhere else and there is no concurrency requirement to justify it.

## Consequences

- Positive: one file to back up (`BACKUP_AND_DR.md`), no server, columnar scans for the hot query,
  real SQL with window functions for as-of resolution, and `DECIMAL` support so money stays exact
  (`DETERMINISM_SPEC.md` §3.3).
- Negative: one more dependency, and **single-writer** — only one process may write at a time.
  Acceptable: the daily run is sequential and backtest workers read rather than write. It does mean
  a backtest cannot run while a fetch is writing, which should fail loudly rather than corrupt.
- Neutral: DuckDB is young relative to SQLite or Postgres. The mitigation is that the data is a
  plain table with an obvious schema — an export to Parquet is one statement, so this is not a
  one-way door.

## Rules

1. **Append-only.** No `UPDATE`, no `DELETE` on fact or journal tables
   (`AUDIT_AND_IMMUTABILITY.md`).
2. A bar row is keyed by `(instrument_id, interval, series, event_time, knowledge_time)`.
   A revision is a new row with a later `knowledge_time`.
3. **Every read is as-of.** There is no query that ignores `knowledge_time` — that is how
   look-ahead enters (`POINT_IN_TIME_SPEC.md` §2).
4. Money and prices are `DECIMAL`, never `DOUBLE`.
5. Writes compare before inserting, so only genuine changes are stored
   (`POINT_IN_TIME_SPEC.md` §3).
6. The database file is the backup unit, and a restore is verified by replaying a manifest and
   comparing `output_hash`.

## Revisit when

- The as-of query shows up in a profile of the daily run or a backtest.
- Concurrent writers become a requirement — which would mean the single-user constraint changed,
  and that is a charter-level change first.
