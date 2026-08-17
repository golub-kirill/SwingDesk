"""Append-only storage for positions and the actions proposed on them.

No UPDATE, no DELETE — the same rule as the run journal, for the same reason. A stop move writes a
new row at `version + 1`; the previous version stays readable forever. Appendix G's `Audit` entity
is "Immutable initial plan and all later versions", and the plural is the requirement.

Reads are as-of. `open_as_of(t)` returns the latest version of each position whose knowledge time is
at or before `t`, which is what makes a past run reproducible: replaying yesterday must see
yesterday's stop, not today's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from swingdesk.contracts.position import (
    ActionKind,
    ActionStatus,
    Fill,
    ManagementAction,
    Position,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    position_id      VARCHAR NOT NULL,
    version          INTEGER NOT NULL,
    instrument_id    VARCHAR NOT NULL,
    opened_on        DATE NOT NULL,
    entry_price      DECIMAL(18, 6) NOT NULL,
    shares           INTEGER NOT NULL,
    initial_stop     DECIMAL(18, 6) NOT NULL,
    current_stop     DECIMAL(18, 6) NOT NULL,
    strategy         VARCHAR NOT NULL,
    strategy_version INTEGER NOT NULL,
    knowledge_time   TIMESTAMPTZ NOT NULL,
    closed_on        DATE,
    PRIMARY KEY (position_id, version)
);

CREATE TABLE IF NOT EXISTS management (
    position_id     VARCHAR NOT NULL,
    proposed_at     TIMESTAMPTZ NOT NULL,
    sequence        BIGINT NOT NULL,
    kind            VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,
    reason_code     VARCHAR,
    reason          VARCHAR NOT NULL,
    old_stop        DECIMAL(18, 6),
    new_stop        DECIMAL(18, 6),
    shares_affected INTEGER,
    run_id          VARCHAR,
    PRIMARY KEY (position_id, sequence)
);

-- The owner's answer to a proposal (US-010, D6). A SEPARATE table rather than a status column
-- updated in place, for the append-only reason this module opens with: `management.status` records
-- what the RUN proposed and has to stay readable as that forever. Rewriting it to `approved` would
-- destroy the record of what was asked, which is half of what an audit trail is for.
--
-- It also carries what `management` has nowhere to put. Production rule 3.8 requires a response to
-- record the choice, a reason and a timestamp: `management.reason` is the SYSTEM's reason for
-- proposing and `proposed_at` is when it asked, so the owner's reason and the moment they answered
-- are different facts and need their own columns.
--
-- The primary key is the proposal being answered, so a second answer to the same proposal is
-- refused by the schema rather than by a check someone has to remember. A recorded decision is
-- immutable; changing your mind is a new proposal, never an edited answer.
CREATE TABLE IF NOT EXISTS management_responses (
    position_id  VARCHAR NOT NULL,
    sequence     BIGINT NOT NULL,
    responded_at TIMESTAMPTZ NOT NULL,
    choice       VARCHAR NOT NULL,
    reason       VARCHAR NOT NULL,
    PRIMARY KEY (position_id, sequence)
);

-- What the broker actually did (US-011). Keyed on the approved action it settles, so a fill cannot
-- exist for something nobody approved - D6 from the far side of the trade.
--
-- `planned_price` is nullable and the null MEANS something: an exit on a maximum holding period
-- names no price to slip against, and recording 0.00 there would be a manufactured measurement.
-- See `contracts.position.Fill.slippage_per_share`.
CREATE TABLE IF NOT EXISTS fills (
    position_id   VARCHAR NOT NULL,
    sequence      BIGINT NOT NULL,
    filled_on     DATE NOT NULL,
    shares        INTEGER NOT NULL,
    price         DECIMAL(18, 6) NOT NULL,
    commission    DECIMAL(18, 6) NOT NULL,
    planned_price DECIMAL(18, 6),
    recorded_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (position_id, sequence)
);
"""


@dataclass(frozen=True, slots=True)
class Response:
    """The owner's answer to one proposal: the choice, a reason and when (Production Rules 3.8)."""

    responded_at: datetime
    choice: ActionStatus
    reason: str


@dataclass(frozen=True, slots=True)
class Pending:
    """A proposal nobody has answered, with the sequence needed to answer it.

    The sequence is carried alongside rather than folded into `ManagementAction`, which is a
    contract shared with the pure layers and has no business knowing about storage keys.
    """

    sequence: int
    action: ManagementAction


class PositionStore:
    """Positions and management proposals, append-only, read as-of."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> PositionStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ writes

    def record(self, position: Position) -> None:
        """Append one version. Rejects a version that already exists rather than overwriting it."""
        existing = self._connection.execute(
            "SELECT 1 FROM positions WHERE position_id = ? AND version = ?",
            [position.position_id, position.version],
        ).fetchone()
        if existing:
            raise ValueError(
                f"{position.position_id} v{position.version} already recorded. Positions are "
                f"append-only; a change is a new version, never a rewrite."
            )
        self._connection.execute(
            "INSERT INTO positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                position.position_id, position.version, position.instrument_id,
                position.opened_on, position.entry_price, position.shares,
                position.initial_stop, position.current_stop, position.strategy,
                position.strategy_version, position.knowledge_time, position.closed_on,
            ],
        )

    def propose(self, action: ManagementAction, run_id: str | None = None) -> None:
        """Append a proposal. Sequence is monotonic per position, so order survives equal clocks."""
        row = self._connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM management WHERE position_id = ?",
            [action.position_id],
        ).fetchone()
        # COALESCE guarantees a row and a value; 1 is the same answer this query gives for a
        # position with no proposals yet, so the fallback cannot introduce a different sequence.
        next_sequence = int(row[0]) if row is not None else 1
        self._connection.execute(
            "INSERT INTO management VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                action.position_id, action.proposed_at, next_sequence, action.kind.value,
                action.status.value, action.reason_code, action.reason,
                action.old_stop, action.new_stop, action.shares_affected, run_id,
            ],
        )

    # ------------------------------------------------------------------ reads

    def open_as_of(self, knowledge_time: datetime) -> list[Position]:
        """Every position open at `knowledge_time`, latest version each, sorted by id.

        The as-of clause is the point: replaying an earlier run must see the stop that was current
        then. Sorted because unordered iteration feeding a decision is the named determinism hazard
        (DETERMINISM_SPEC 3.2), and this feeds the first step of the run.
        """
        rows = self._connection.execute(
            """
            SELECT position_id, version, instrument_id, opened_on, entry_price, shares,
                   initial_stop, current_stop, strategy, strategy_version, knowledge_time, closed_on
            FROM positions
            WHERE knowledge_time <= ?
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY position_id ORDER BY version DESC
            ) = 1
            ORDER BY position_id
            """,
            [knowledge_time],
        ).fetchall()
        return [p for p in (self._row(r) for r in rows) if p.is_open]

    def history(self, position_id: str) -> list[Position]:
        """Every version, oldest first. The audit trail Appendix G requires."""
        rows = self._connection.execute(
            """
            SELECT position_id, version, instrument_id, opened_on, entry_price, shares,
                   initial_stop, current_stop, strategy, strategy_version, knowledge_time, closed_on
            FROM positions WHERE position_id = ? ORDER BY version
            """,
            [position_id],
        ).fetchall()
        return [self._row(r) for r in rows]

    def actions_for(self, position_id: str) -> list[ManagementAction]:
        rows = self._connection.execute(
            """
            SELECT position_id, proposed_at, kind, status, reason_code, reason,
                   old_stop, new_stop, shares_affected
            FROM management WHERE position_id = ? ORDER BY sequence
            """,
            [position_id],
        ).fetchall()
        return [
            ManagementAction(
                position_id=r[0], proposed_at=r[1], kind=ActionKind(r[2]),
                status=ActionStatus(r[3]), reason_code=r[4], reason=r[5],
                old_stop=None if r[6] is None else Decimal(str(r[6])),
                new_stop=None if r[7] is None else Decimal(str(r[7])),
                shares_affected=r[8],
            )
            for r in rows
        ]

    def pending(self) -> list[Pending]:
        """Every proposal the owner has not answered, oldest first.

        "Unanswered" is the absence of a response row, NOT `status = 'proposed'`. The status column
        is what the run proposed and never changes (see the schema), so counting on it would have
        left every answered proposal pending forever the moment responses existed.
        """
        rows = self._connection.execute(
            """
            SELECT m.position_id, m.sequence, m.proposed_at, m.kind, m.status, m.reason_code,
                   m.reason, m.old_stop, m.new_stop, m.shares_affected
            FROM management m
            LEFT JOIN management_responses r
                   ON r.position_id = m.position_id AND r.sequence = m.sequence
            WHERE r.sequence IS NULL AND m.kind <> 'hold'
            ORDER BY m.proposed_at, m.position_id, m.sequence
            """
        ).fetchall()
        return [
            Pending(
                sequence=int(r[1]),
                action=ManagementAction(
                    position_id=r[0], proposed_at=r[2], kind=ActionKind(r[3]),
                    status=ActionStatus(r[4]), reason_code=r[5], reason=r[6],
                    old_stop=None if r[7] is None else Decimal(str(r[7])),
                    new_stop=None if r[8] is None else Decimal(str(r[8])),
                    shares_affected=r[9],
                ),
            )
            for r in rows
        ]

    def respond(
        self, position_id: str, sequence: int, *, choice: ActionStatus, reason: str, at: datetime
    ) -> None:
        """Record the owner's answer to one proposal. Append-only, and answerable exactly once.

        `reason` is required and must not be blank: production rule 3.8 wants the choice, a reason
        and a timestamp, and an approval with no stated reason is the unlogged judgment that rule
        exists to prevent. `apply_approved` in `trade_management.manage` is what acts on it - and
        it refuses anything not APPROVED, so nothing can be applied that was not answered here.
        """
        if choice not in (ActionStatus.APPROVED, ActionStatus.REJECTED):
            raise ValueError(
                f"a response is APPROVED or REJECTED, not {choice}. `proposed` is the absence of "
                f"an answer and `expired` is not something the owner chooses."
            )
        if not reason.strip():
            raise ValueError("every response carries a reason (Production Rules 3.8)")

        proposal = self._connection.execute(
            "SELECT 1 FROM management WHERE position_id = ? AND sequence = ?",
            [position_id, sequence],
        ).fetchone()
        if proposal is None:
            raise ValueError(f"no proposal {position_id} #{sequence} to answer")

        answered = self._connection.execute(
            "SELECT choice FROM management_responses WHERE position_id = ? AND sequence = ?",
            [position_id, sequence],
        ).fetchone()
        if answered is not None:
            raise ValueError(
                f"{position_id} #{sequence} was already answered {answered[0]!r}. Responses are "
                f"append-only; a change of mind is a new proposal, not an edited answer."
            )

        self._connection.execute(
            "INSERT INTO management_responses VALUES (?, ?, ?, ?, ?)",
            [position_id, sequence, at, choice.value, reason],
        )

    def proposal_at(self, position_id: str, sequence: int) -> ManagementAction | None:
        """One proposal by its sequence, answered or not.

        `actions_for` cannot serve this: it returns actions in sequence order but not the sequences
        themselves, so a caller had to assume they run 1..n contiguously. They are monotonic, not
        contiguous - nothing guarantees a gap can never appear - and an off-by-one there would
        apply the owner's answer to the WRONG proposal.
        """
        row = self._connection.execute(
            """
            SELECT position_id, proposed_at, kind, status, reason_code, reason,
                   old_stop, new_stop, shares_affected
            FROM management WHERE position_id = ? AND sequence = ?
            """,
            [position_id, sequence],
        ).fetchone()
        if row is None:
            return None
        return ManagementAction(
            position_id=row[0], proposed_at=row[1], kind=ActionKind(row[2]),
            status=ActionStatus(row[3]), reason_code=row[4], reason=row[5],
            old_stop=None if row[6] is None else Decimal(str(row[6])),
            new_stop=None if row[7] is None else Decimal(str(row[7])),
            shares_affected=row[8],
        )

    def response_for(self, position_id: str, sequence: int) -> Response | None:
        """The owner's answer, or None when the proposal is still unanswered."""
        row = self._connection.execute(
            "SELECT responded_at, choice, reason FROM management_responses "
            "WHERE position_id = ? AND sequence = ?",
            [position_id, sequence],
        ).fetchone()
        if row is None:
            return None
        return Response(responded_at=row[0], choice=ActionStatus(row[1]), reason=row[2])

    def record_fill(self, fill: Fill) -> None:
        """Append what the broker actually did. Refuses anything the owner did not approve.

        That refusal is D6 seen from the far side of the trade: an approval is what makes an action
        legitimate, so a fill settling an unapproved - or unanswered, or rejected - proposal is
        either a mis-keyed sequence or an action taken outside the system. Both are worth stopping.
        """
        answer = self.response_for(fill.position_id, fill.sequence)
        if answer is None:
            raise ValueError(
                f"{fill.position_id} #{fill.sequence} has no recorded response. A fill settles an "
                f"APPROVED action; nothing here was approved."
            )
        if answer.choice is not ActionStatus.APPROVED:
            raise ValueError(
                f"{fill.position_id} #{fill.sequence} was {answer.choice.value}, not approved. "
                f"A fill against a rejected proposal is an action taken outside this system."
            )
        existing = self._connection.execute(
            "SELECT 1 FROM fills WHERE position_id = ? AND sequence = ?",
            [fill.position_id, fill.sequence],
        ).fetchone()
        if existing is not None:
            raise ValueError(
                f"{fill.position_id} #{fill.sequence} is already filled. Fills are append-only; a "
                f"correction is a new record against a new action, never an edit."
            )
        self._connection.execute(
            "INSERT INTO fills VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                fill.position_id, fill.sequence, fill.filled_on, fill.shares, fill.price,
                fill.commission, fill.planned_price, fill.recorded_at,
            ],
        )

    def fills_for(self, position_id: str) -> list[Fill]:
        rows = self._connection.execute(
            """
            SELECT position_id, sequence, filled_on, shares, price, commission, planned_price,
                   recorded_at
            FROM fills WHERE position_id = ? ORDER BY sequence
            """,
            [position_id],
        ).fetchall()
        return [
            Fill(
                position_id=r[0], sequence=int(r[1]),
                filled_on=r[2] if isinstance(r[2], date) else date.fromisoformat(str(r[2])),
                shares=r[3], price=Decimal(str(r[4])), commission=Decimal(str(r[5])),
                planned_price=None if r[6] is None else Decimal(str(r[6])),
                recorded_at=r[7],
            )
            for r in rows
        ]

    def open_risk_as_of(self, knowledge_time: datetime) -> Decimal:
        """Open risk across the WHOLE BOOK, recomputed from current stops (`US-011`).

        Recomputed, never decremented - the same rule `Position.open_risk` follows per position,
        applied to the book. A running total that subtracted each exit as it happened would drift
        from the stops that define it, and would be wrong in the direction that matters: it would
        under-report risk after a stop was widened, which cannot happen here, or over-report it
        after a trail, which makes the book look more dangerous than it is and invites overriding
        the rule.

        Sums the LATEST version of every open position, so a partially exited position contributes
        its remaining shares at its current stop, not its original size.
        """
        return sum(
            (p.open_risk for p in self.open_as_of(knowledge_time)), start=Decimal(0)
        )

    def pending_approvals(self) -> int:
        """Proposals awaiting the owner. Reported on every run - a proposal nobody answered is not
        an approval, and an unanswered queue is an operational fact (D6)."""
        row = self._connection.execute(
            """
            SELECT COUNT(*) FROM management m
            LEFT JOIN management_responses r
                   ON r.position_id = m.position_id AND r.sequence = m.sequence
            WHERE r.sequence IS NULL AND m.kind <> 'hold'
            """
        ).fetchone()
        return int(row[0]) if row is not None else 0

    @staticmethod
    def _row(r: tuple[Any, ...]) -> Position:
        return Position(
            position_id=r[0], version=r[1], instrument_id=r[2],
            opened_on=r[3] if isinstance(r[3], date) else date.fromisoformat(str(r[3])),
            entry_price=Decimal(str(r[4])), shares=r[5],
            initial_stop=Decimal(str(r[6])), current_stop=Decimal(str(r[7])),
            strategy=r[8], strategy_version=r[9], knowledge_time=r[10],
            closed_on=r[11] if r[11] is None or isinstance(r[11], date)
            else date.fromisoformat(str(r[11])),
        )
