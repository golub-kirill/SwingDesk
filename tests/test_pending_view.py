"""`pending`'s read-time split, now shared with `status` - so the two screens cannot disagree
about what is waiting."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from swingdesk.contracts.position import ActionKind, ActionStatus, ManagementAction, Position
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.presentation.pending_view import split_pending

NOW = datetime(2026, 8, 18, 22, 0, tzinfo=UTC)


def _store(tmp_path, kinds):
    store = PositionStore(tmp_path / "positions.duckdb")
    store.record(Position(
        position_id="POS-1", version=1, instrument_id="AAPL", opened_on=date(2026, 8, 10),
        entry_price=Decimal(300), shares=8, initial_stop=Decimal(290), current_stop=Decimal(290),
        initial_costs_per_share=Decimal("1.50"), knowledge_time=datetime(2026, 8, 10, tzinfo=UTC)))
    for day, kind in kinds:
        store.propose(ManagementAction(
            position_id="POS-1", proposed_at=datetime(2026, 8, day, 21, 0, tzinfo=UTC), kind=kind,
            reason="fixture", reason_code="STOP" if kind is ActionKind.EXIT_NOW else None,
            old_stop=Decimal(290),
            new_stop=Decimal(290 + day) if kind is ActionKind.MOVE_STOP else None))
    return store


def test_older_stop_moves_are_superseded_and_the_latest_waits(tmp_path) -> None:
    with _store(tmp_path, [(16, ActionKind.MOVE_STOP), (17, ActionKind.MOVE_STOP),
                           (18, ActionKind.MOVE_STOP)]) as store:
        split = split_pending(store, NOW)
    assert [p.sequence for p in split.waiting] == [3]
    assert sorted(p.sequence for p in split.superseded) == [1, 2]
    assert split.total == 3


def test_rejecting_the_latest_does_not_revive_the_one_before(tmp_path) -> None:
    """Live 2026-09-13: VGT #4 rejected, and #3 came back as awaiting an answer."""
    with _store(tmp_path, [(16, ActionKind.MOVE_STOP), (17, ActionKind.MOVE_STOP),
                           (18, ActionKind.MOVE_STOP)]) as store:
        store.respond("POS-1", 3, choice=ActionStatus.REJECTED, reason="obsolete", at=NOW)
        split = split_pending(store, NOW)
    assert split.waiting == []
    assert sorted(p.sequence for p in split.superseded) == [1, 2]


def test_an_answered_later_exit_supersedes_no_stop_move(tmp_path) -> None:
    """Only a later STOP MOVE retires a stop move; an answered exit is a different question."""
    with _store(tmp_path, [(17, ActionKind.MOVE_STOP), (18, ActionKind.EXIT_NOW)]) as store:
        store.respond("POS-1", 2, choice=ActionStatus.REJECTED, reason="holding", at=NOW)
        split = split_pending(store, NOW)
    assert [p.sequence for p in split.waiting] == [1]
    assert split.superseded == []


def test_a_critical_proposal_is_never_superseded(tmp_path) -> None:
    with _store(tmp_path, [(16, ActionKind.EXIT_NOW), (17, ActionKind.MOVE_STOP)]) as store:
        split = split_pending(store, NOW)
    assert {p.action.kind for p in split.waiting} == {ActionKind.EXIT_NOW, ActionKind.MOVE_STOP}
    assert split.superseded == []


def test_an_aged_out_stop_move_is_expired_not_waiting(tmp_path) -> None:
    """The expiry half of the split, at the date `test_cli.py` already uses to expire one."""
    with _store(tmp_path, [(16, ActionKind.MOVE_STOP)]) as store:
        split = split_pending(store, datetime(2026, 8, 21, 22, 0, tzinfo=UTC))
    assert [p.sequence for p in split.expired] == [1]
    assert split.waiting == []


def test_nothing_pending_is_an_empty_split(tmp_path) -> None:
    with _store(tmp_path, []) as store:
        split = split_pending(store, NOW)
    assert split.total == 0
