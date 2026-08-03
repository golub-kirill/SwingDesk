"""Append-only storage for positions and the actions proposed on them.

No UPDATE, no DELETE — the same rule as the run journal, for the same reason. A stop move writes a
new row at `version + 1`; the previous version stays readable forever. Appendix G's `Audit` entity
is "Immutable initial plan and all later versions", and the plural is the requirement.

Reads are as-of. `open_as_of(t)` returns the latest version of each position whose knowledge time is
at or before `t`, which is what makes a past run reproducible: replaying yesterday must see
yesterday's stop, not today's.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from swingdesk.contracts.position import ActionKind, ActionStatus, ManagementAction, Position

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
"""


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
        next_sequence = int(
            self._connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM management WHERE position_id = ?",
                [action.position_id],
            ).fetchone()[0]
        )
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

    def pending_approvals(self) -> int:
        """Proposals awaiting the owner. Reported on every run - a proposal nobody answered is not
        an approval, and an unanswered queue is an operational fact (D6)."""
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM management WHERE status = 'proposed' AND kind <> 'hold'"
            ).fetchone()[0]
        )

    @staticmethod
    def _row(r) -> Position:
        return Position(
            position_id=r[0], version=r[1], instrument_id=r[2],
            opened_on=r[3] if isinstance(r[3], date) else date.fromisoformat(str(r[3])),
            entry_price=Decimal(str(r[4])), shares=r[5],
            initial_stop=Decimal(str(r[6])), current_stop=Decimal(str(r[7])),
            strategy=r[8], strategy_version=r[9], knowledge_time=r[10],
            closed_on=r[11] if r[11] is None or isinstance(r[11], date)
            else date.fromisoformat(str(r[11])),
        )
