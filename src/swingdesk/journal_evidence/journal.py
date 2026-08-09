"""The append-only journal (ADR-0004, AUDIT_AND_IMMUTABILITY).

No UPDATE, no DELETE. A correction is a new version linked to the original. This is a storage
guarantee rather than a discipline: error HINDSIGHT's required control is "immutable pre-trade
snapshot", so if records were mutable the control would not exist.

Depends only on platform (DEPENDENCY_LAW), so the pure layers cannot reach it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb

from swingdesk.contracts.run import RunManifest

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          VARCHAR PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    completed_at    TIMESTAMPTZ,
    code_hash       VARCHAR NOT NULL,
    code_dirty      BOOLEAN NOT NULL,
    config_hash     VARCHAR NOT NULL,
    snapshot_id     VARCHAR NOT NULL,
    calendar_version VARCHAR NOT NULL,
    platform        VARCHAR NOT NULL,
    seed            BIGINT,
    parameters_json VARCHAR NOT NULL,
    components_json VARCHAR NOT NULL,
    output_hash     VARCHAR
);

CREATE TABLE IF NOT EXISTS decisions (
    run_id          VARCHAR NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL,
    instrument_id   VARCHAR NOT NULL,
    decision        VARCHAR NOT NULL,
    reason_code     VARCHAR,
    reason          VARCHAR,
    parameter_id    VARCHAR,
    version         INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (run_id, instrument_id, version)
);

-- Added after `runs` shipped. Written as a migration rather than folded into the CREATE above,
-- because an existing journal is append-only: its rows must survive the schema growing.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS universe_hash VARCHAR;

-- Mode (SYSTEM_MODES). Nullable in the table and REQUIRED on the manifest, deliberately: rows
-- written before the column existed cannot acquire one, and a NULL that says "this run predates
-- the field" is honest where a backfilled guess would not be. Every row written from now on has it.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS mode VARCHAR;

-- from_state (TRANSITION_SPEC 4). What this instrument's decision WAS when the run began. Null
-- means the run had no prior decision for it - a first sighting, or a journal that does not go back
-- that far - and is not the same as "unchanged".
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS previous_decision VARCHAR;
"""

#: The four states of the candidate-decision enum (DECISION_STATE_MACHINE 1). A decision outside
#: this set is a defect, not a new state.
DECISIONS = frozenset({"Trade", "Watch", "Skip", "Pause"})


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """One candidate's outcome. Every candidate leaves a run with one of these.

    No candidate may be left without a next action - a candidate with no decision is a defect
    (M32/M33 operational standard), and a Skip without a reason code is too.
    """

    instrument_id: str
    decision: str
    reason_code: str | None = None
    reason: str | None = None
    parameter_id: str | None = None
    previous_decision: str | None = None
    """What this instrument's decision was when the run began (TRANSITION_SPEC 4).

    Every other field records what the candidate BECAME. Without this one, a `Skip` that was a
    `Watch` yesterday reads exactly like a `Skip` that has been a `Skip` all week, and the first is
    the one worth reviewing.

    `None` means the journal held no earlier decision for this instrument as of the run's start -
    a first sighting, or a journal that does not reach back that far. It does not mean unchanged.
    """

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"{self.decision!r} is not one of {sorted(DECISIONS)}")
        if self.decision == "Skip" and not self.reason_code:
            raise ValueError("a Skip requires a reason code")


class Journal:
    """Append-only run and decision storage."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Journal:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def start_run(self, manifest: RunManifest) -> None:
        """Record a run before any work. A run without a manifest cannot be replayed."""
        self._connection.execute(
            """
            INSERT INTO runs (run_id, started_at, completed_at, code_hash, code_dirty,
                              config_hash, snapshot_id, calendar_version, platform, seed,
                              parameters_json, components_json, output_hash, universe_hash, mode)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            [
                manifest.run_id, manifest.started_at, manifest.code_hash, manifest.code_dirty,
                manifest.config_hash, manifest.snapshot_id, manifest.calendar_version,
                manifest.platform, manifest.seed,
                json.dumps([p.model_dump() for p in manifest.parameters], sort_keys=True),
                json.dumps(manifest.component_versions, sort_keys=True),
                manifest.universe_hash, manifest.mode.value,
            ],
        )

    def complete_run(self, run_id: str, output_hash: str, completed_at: datetime) -> None:
        """Mark a run finished.

        This is the one permitted update, and it only ever writes fields that were NULL - a run's
        inputs are never rewritten. An incomplete run stays incomplete forever, which is correct:
        its output is not a decision input.
        """
        self._connection.execute(
            "UPDATE runs SET output_hash = ?, completed_at = ? "
            "WHERE run_id = ? AND output_hash IS NULL",
            [output_hash, completed_at, run_id],
        )

    def record_decisions(
        self, run_id: str, recorded_at: datetime, decisions: list[DecisionRecord]
    ) -> None:
        """Record every candidate's outcome. An empty run is a run, not an error.

        A day on which the universe produces no candidates is ordinary - everything filtered out,
        or a run whose only work was managing open positions. duckdb's executemany rejects an empty
        batch, so this returned an exception where it should have returned nothing. Found when
        positions landed and the first positions-only run crashed.
        """
        if not decisions:
            return
        self._connection.executemany(
            """
            INSERT INTO decisions
                (run_id, recorded_at, instrument_id, decision, reason_code, reason, parameter_id,
                 previous_decision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (run_id, recorded_at, d.instrument_id, d.decision, d.reason_code, d.reason,
                 d.parameter_id, d.previous_decision)
                for d in decisions
            ],
        )

    def decisions_for(self, run_id: str) -> list[DecisionRecord]:
        rows = self._connection.execute(
            "SELECT instrument_id, decision, reason_code, reason, parameter_id, previous_decision "
            "FROM decisions WHERE run_id = ? ORDER BY instrument_id",
            [run_id],
        ).fetchall()
        return [DecisionRecord(*row) for row in rows]

    def latest_decisions(
        self, instrument_ids: list[str], as_of: datetime
    ) -> dict[str, str]:
        """The most recent decision per instrument, as of a knowledge time.

        Read at the START of a run, before it writes anything, so it answers "what did this
        instrument's decision say when we began" rather than "what does it say now" - the same
        as-of discipline the bar store uses, applied to decisions.

        Absent instruments are simply missing from the result: a first sighting has no previous
        state, and inventing one would make `from_state` a lie in exactly the case a reviewer cares
        about least and trusts most.
        """
        if not instrument_ids:
            return {}
        placeholders = ", ".join("?" for _ in instrument_ids)
        rows = self._connection.execute(
            f"""
            SELECT instrument_id, decision FROM decisions
            WHERE instrument_id IN ({placeholders}) AND recorded_at < ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY recorded_at DESC) = 1
            """,
            [*instrument_ids, as_of],
        ).fetchall()
        return {instrument_id: decision for instrument_id, decision in rows}

    def uncoded_refusals(self, run_id: str) -> int:
        """Skips with no reason code. Track A `a.no_uncoded_failures` requires this to be zero."""
        row = self._connection.execute(
            "SELECT COUNT(*) FROM decisions "
            "WHERE run_id = ? AND decision = 'Skip' AND (reason_code IS NULL OR reason_code = '')",
            [run_id],
        ).fetchone()
        return int(row[0]) if row is not None else 0
