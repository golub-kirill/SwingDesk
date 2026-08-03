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
"""

#: The four states of the candidate-decision enum (DECISION_STATE_MACHINE 1). A decision outside
#: this set is a defect, not a new state.
DECISIONS = frozenset({"Trade", "Watch", "Skip", "Pause"})


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """One candidate's outcome. Every candidate leaves a run with one of these.

    "Нет кандидатов без следующего действия" - a candidate with no decision is a defect
    (M32/M33 operational standard), and a Skip without a reason code is too.
    """

    instrument_id: str
    decision: str
    reason_code: str | None = None
    reason: str | None = None
    parameter_id: str | None = None

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
                              parameters_json, components_json, output_hash)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            [
                manifest.run_id, manifest.started_at, manifest.code_hash, manifest.code_dirty,
                manifest.config_hash, manifest.snapshot_id, manifest.calendar_version,
                manifest.platform, manifest.seed,
                json.dumps([p.model_dump() for p in manifest.parameters], sort_keys=True),
                json.dumps(manifest.component_versions, sort_keys=True),
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
                (run_id, recorded_at, instrument_id, decision, reason_code, reason, parameter_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (run_id, recorded_at, d.instrument_id, d.decision, d.reason_code, d.reason,
                 d.parameter_id)
                for d in decisions
            ],
        )

    def decisions_for(self, run_id: str) -> list[DecisionRecord]:
        rows = self._connection.execute(
            "SELECT instrument_id, decision, reason_code, reason, parameter_id "
            "FROM decisions WHERE run_id = ? ORDER BY instrument_id",
            [run_id],
        ).fetchall()
        return [DecisionRecord(*row) for row in rows]

    def uncoded_refusals(self, run_id: str) -> int:
        """Skips with no reason code. Track A `a.no_uncoded_failures` requires this to be zero."""
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM decisions "
                "WHERE run_id = ? AND decision = 'Skip' AND (reason_code IS NULL OR reason_code = '')",
                [run_id],
            ).fetchone()[0]
        )
