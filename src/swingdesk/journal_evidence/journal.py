"""The append-only journal (ADR-0004, AUDIT_AND_IMMUTABILITY).

No UPDATE, no DELETE. A correction is a new version linked to the original. This is a storage
guarantee rather than a discipline: error HINDSIGHT's required control is "immutable pre-trade
snapshot", so if records were mutable the control would not exist.

Depends only on platform (DEPENDENCY_LAW), so the pure layers cannot reach it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from swingdesk.contracts.run import RunManifest
from swingdesk.platform import schema

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

-- Every attempt to place an order at the paper venue, INCLUDING the ones a guard stopped
-- (`DR-027` 6, `CHARTER` A-002). A row here is an ATTEMPT and not a position: the venue accepting
-- an order is not a fill, and `Position` is still created from the fill.
--
-- **The stopped rows are the point, not the overhead.** A run that had nothing to submit and a run
-- that was stopped from submitting something are different facts, and only this table can tell
-- them apart afterwards. `SECURITY.md` 4's rule for the approval channel is the one being
-- honoured - an action with no record did not happen - and the `REVENGE` and `HINDSIGHT` controls
-- both depend on the ATTEMPT being recorded rather than on the result.
--
-- Keyed by `(run_id, client_order_id)` rather than by the client order id alone. The id is derived
-- from the SESSION and the instrument (`DR-027` 5), so a run stopped by the switch and a later run
-- that the owner armed share one - and both attempts are facts. Append-only, like everything here.
CREATE TABLE IF NOT EXISTS submissions (
    run_id          VARCHAR NOT NULL,
    client_order_id VARCHAR NOT NULL,
    attempted_at    TIMESTAMPTZ NOT NULL,
    session_date    DATE NOT NULL,
    instrument_id   VARCHAR NOT NULL,
    shares          INTEGER NOT NULL,
    limit_price     DECIMAL(18, 6) NOT NULL,
    stop_price      DECIMAL(18, 6) NOT NULL,
    outcome         VARCHAR NOT NULL,
    detail          VARCHAR,
    venue_order_id  VARCHAR,
    venue_status    VARCHAR,
    PRIMARY KEY (run_id, client_order_id)
);
"""

#: The four states of the candidate-decision enum (DECISION_STATE_MACHINE 1). A decision outside
#: this set is a defect, not a new state.
DECISIONS = frozenset({"Trade", "Watch", "Skip", "Pause"})

#: What became of one attempt to place an order. Coded rather than free text, for the reason
#: `DecisionRecord.reason_code` is: a vocabulary can be counted and a sentence cannot.
#:
#:   sent      the venue accepted the order
#:   stopped   a guard refused before anything reached the wire (`DR-027` 4)
#:   refused   the order could not be BUILT - wrong market, no shares, an impossible bracket
#:   rejected  the venue refused it, a duplicate client order id among the reasons
SUBMISSION_OUTCOMES = frozenset({"sent", "stopped", "refused", "rejected"})


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


@dataclass(frozen=True, slots=True)
class Submission:
    """One attempt to place an order at the venue, and what became of it.

    **An attempt, not a position, and not a fill.** The venue accepting an order says only that it
    took it; `leaves_qty` exists because partial fills do. `Position` is still built from the fill
    (`DR-027` 6).

    A row exists for an attempt a guard STOPPED, with `outcome="stopped"` and the guard's reason in
    `detail`. That is deliberate and it is most of this record's value: afterwards, a session on
    which the machine would have entered three names and was stopped is otherwise indistinguishable
    from a session on which it found nothing.
    """

    run_id: str
    client_order_id: str
    attempted_at: datetime
    session_date: date
    instrument_id: str
    shares: int
    limit_price: Decimal
    stop_price: Decimal
    outcome: str
    detail: str | None = None
    venue_order_id: str | None = None
    venue_status: str | None = None

    def __post_init__(self) -> None:
        if self.outcome not in SUBMISSION_OUTCOMES:
            raise ValueError(f"{self.outcome!r} is not one of {sorted(SUBMISSION_OUTCOMES)}")
        if self.outcome == "sent" and not self.venue_order_id:
            raise ValueError(
                "a `sent` submission carries the venue's order id. Without it the row asserts "
                "something happened at the venue that nothing can be traced back to."
            )
        if self.outcome != "sent" and not self.detail:
            raise ValueError(
                f"a {self.outcome!r} submission carries the reason. An attempt recorded without "
                f"why it failed is the sentence `AGENTS.md` 10.4 is about, stored."
            )


class Journal:
    """Append-only run and decision storage."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)
        # A store never opens against a schema it cannot serve. `CREATE TABLE IF NOT
        # EXISTS` above is silent when a COLUMN is added to a table that already exists,
        # and that silence cost four trading days - see `platform/schema.py`.
        schema.reconcile(self._connection, _SCHEMA)

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

    def record_submission(self, submission: Submission) -> None:
        """Write one attempt. Append-only: a second attempt on the same order is a new RUN's row.

        Called for every eligible candidate on a `--submit` run, whether or not anything reached
        the wire - see `Submission`.
        """
        self._connection.execute(
            """
            INSERT INTO submissions
                (run_id, client_order_id, attempted_at, session_date, instrument_id, shares,
                 limit_price, stop_price, outcome, detail, venue_order_id, venue_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                submission.run_id, submission.client_order_id, submission.attempted_at,
                submission.session_date, submission.instrument_id, submission.shares,
                submission.limit_price, submission.stop_price, submission.outcome,
                submission.detail, submission.venue_order_id, submission.venue_status,
            ],
        )

    def submissions_for(self, run_id: str) -> list[Submission]:
        """Every attempt one run made, in client-order-id order.

        Sorted here rather than left to the store: `DETERMINISM_SPEC` wants a re-run to match, and
        an unordered read would compare two orderings of the same set.
        """
        rows = self._connection.execute(
            "SELECT run_id, client_order_id, attempted_at, session_date, instrument_id, shares, "
            "limit_price, stop_price, outcome, detail, venue_order_id, venue_status "
            "FROM submissions WHERE run_id = ? ORDER BY client_order_id",
            [run_id],
        ).fetchall()
        return [Submission(*row) for row in rows]

    def sent_client_order_ids(self) -> frozenset[str]:
        """Every order id this system has actually PUT ON THE WIRE. `DR-032`.

        The set answers one question and it is narrow: *did we send this?* A live order at the
        venue whose id is in here is exposure this system created an hour ago and journalled - not
        something it cannot account for. `outcome = 'sent'` only, for the reason
        `latest_sent_submission` gives: a stopped or refused attempt never reached the venue, so
        no order there can carry its id.

        Whole table rather than a session filter, deliberately. The id already encodes the session
        (`DR-027` §5), so filtering by it here would be the same predicate written twice - and an
        order that outlived its session is still one we sent, which is the fact being asked about.
        """
        rows = self._connection.execute(
            "SELECT DISTINCT client_order_id FROM submissions WHERE outcome = 'sent'"
        ).fetchall()
        return frozenset(row[0] for row in rows)

    def submission_by_order_id(self, client_order_id: str) -> Submission | None:
        """The `sent` attempt carrying this id, or `None`.

        Keyed by the venue-visible id rather than the instrument, because the caller already has
        the id from the venue and wants the shares and the stop we sent with it - the numbers that
        say how much capacity that live order is consuming.
        """
        row = self._connection.execute(
            "SELECT run_id, client_order_id, attempted_at, session_date, instrument_id, shares, "
            "limit_price, stop_price, outcome, detail, venue_order_id, venue_status "
            "FROM submissions WHERE client_order_id = ? AND outcome = 'sent' "
            "ORDER BY attempted_at DESC LIMIT 1",
            [client_order_id],
        ).fetchone()
        return Submission(*row) if row else None

    def latest_sent_submission(self, instrument_id: str) -> Submission | None:
        """The most recent order this system actually PUT ON THE WIRE for one instrument.

        `outcome = 'sent'` and nothing else: a `stopped`, `refused` or `rejected` row is an attempt
        that never reached the venue, so a holding could not have come from one. Adopting a venue
        position against a stopped attempt would credit this system with an order it did not place
        and, worse, write that attempt's stop into the book (`DR-031`).

        `None` when there is none, which is the answer that keeps `DR-027` §11's guard stopping
        submission: a holding we cannot trace to an order of ours is somebody trading by hand.
        """
        row = self._connection.execute(
            "SELECT run_id, client_order_id, attempted_at, session_date, instrument_id, shares, "
            "limit_price, stop_price, outcome, detail, venue_order_id, venue_status "
            "FROM submissions WHERE instrument_id = ? AND outcome = 'sent' "
            # Ties broken by the id, so two attempts recorded in the same instant resolve the same
            # way on every read - `DETERMINISM_SPEC` §3.2 applied to a store, not to a report.
            "ORDER BY attempted_at DESC, client_order_id DESC LIMIT 1",
            [instrument_id],
        ).fetchone()
        return Submission(*row) if row else None

    def decisions_for(self, run_id: str) -> list[DecisionRecord]:
        rows = self._connection.execute(
            "SELECT instrument_id, decision, reason_code, reason, parameter_id, previous_decision "
            "FROM decisions WHERE run_id = ? ORDER BY instrument_id",
            [run_id],
        ).fetchall()
        return [DecisionRecord(*row) for row in rows]

    def runs_starting_between(
        self, start: datetime, end: datetime
    ) -> list[tuple[str, datetime]]:
        """Every run's id and clock-recorded start within `[start, end]`, oldest first.

        For `tools/track_a_streak.py`'s idle-day diagnostic (2026-08-16, council-reviewed): the log
        says a scheduled attempt happened and how it exited, never what it decided - this is the
        only way to learn that, because the log has no decision-level detail (see this module's own
        docstring, "distinct from the log"). Not used by anything on the decision path.
        """
        rows = self._connection.execute(
            "SELECT run_id, started_at FROM runs WHERE started_at BETWEEN ? AND ? "
            "ORDER BY started_at",
            [start, end],
        ).fetchall()
        return [(run_id, started_at) for run_id, started_at in rows]

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
