"""Open positions: the record, the store, the proposals, and the run order.

Two rules are asserted more than once because two owner decisions depend on them: nothing here
executes anything (D1), and a proposal is not permission (D6).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from tests.conftest import TEST_CA, TEST_US, fixture_fetcher

from swingdesk.application.pipeline import run
from swingdesk.contracts.position import (
    ActionKind,
    ActionStatus,
    ManagementAction,
    Position,
)
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock
from swingdesk.trade_management import manage
from swingdesk.trade_management.exits import ExitPolicy

AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


def _position(**kwargs) -> Position:
    base = dict(
        position_id="POS-1", version=1, instrument_id=TEST_US.id,
        opened_on=date(2025, 12, 1), entry_price=Decimal(100), shares=50,
        initial_stop=Decimal(96), current_stop=Decimal(96),
        knowledge_time=datetime(2025, 12, 1, tzinfo=UTC),
    )
    base.update(kwargs)
    return Position(**base)


# ------------------------------------------------------------------ the R denominator

def test_r_denominator_survives_a_stop_move() -> None:
    """RISK_SPEC 2: R is what was risked when the decision was made, not what is at risk now."""
    position = _position()
    assert position.initial_risk_per_share == Decimal(4)
    assert position.r_at(Decimal(106)) == Decimal("1.5")

    moved = position.model_copy(update={"current_stop": Decimal(102), "version": 2})
    assert moved.initial_risk_per_share == Decimal(4), "unchanged by the stop move"
    assert moved.r_at(Decimal(106)) == Decimal("1.5"), "a +1.5R trade stays +1.5R"


def test_open_risk_is_recomputed_and_may_go_negative() -> None:
    """Recomputed from the CURRENT stop, never decremented.

    Clamping at zero would hide the difference between risk removed and risk locked in as profit.
    """
    assert _position().open_risk == Decimal(200)
    assert _position(current_stop=Decimal(100), version=2).open_risk == Decimal(0)
    assert _position(current_stop=Decimal(104), version=2).open_risk == Decimal(-200)


def test_a_stop_below_the_initial_one_is_refused() -> None:
    """Widening a stop increases risk after the fact — error code WIDE_STOP."""
    with pytest.raises(ValidationError, match="WIDE_STOP"):
        _position(current_stop=Decimal(90))


def test_a_stop_above_entry_is_refused_at_entry() -> None:
    with pytest.raises(ValidationError, match="not below entry"):
        _position(initial_stop=Decimal(105), current_stop=Decimal(105))


# ------------------------------------------------------------------ proposals

def test_a_stop_move_must_record_both_stops() -> None:
    with pytest.raises(ValidationError, match="old and the new stop"):
        ManagementAction(position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.MOVE_STOP,
                         reason="tighten", old_stop=Decimal(96))


def test_a_proposed_stop_move_downward_is_refused() -> None:
    with pytest.raises(ValidationError, match="WIDE_STOP"):
        ManagementAction(position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.MOVE_STOP,
                         reason="loosen", old_stop=Decimal(96), new_stop=Decimal(90))


def test_every_action_carries_a_reason() -> None:
    with pytest.raises(ValidationError, match="carries a reason"):
        ManagementAction(position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.HOLD, reason="  ")


def test_actions_start_proposed_and_hold_needs_no_answer() -> None:
    """D6: stop moves and partial exits need the owner. A hold does not."""
    hold = ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                            kind=ActionKind.HOLD, reason="stop intact")
    move = ManagementAction(position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.MOVE_STOP,
                            reason="raise", old_stop=Decimal(96), new_stop=Decimal(98))
    assert hold.status is ActionStatus.PROPOSED and not hold.is_actionable
    assert move.is_actionable


def test_an_unapproved_action_cannot_be_applied() -> None:
    """A proposal is not permission (D6). This is the line D1 and D6 both rest on."""
    position = _position()
    proposal = ManagementAction(position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.MOVE_STOP,
                                reason="raise", old_stop=Decimal(96), new_stop=Decimal(98))
    with pytest.raises(ValueError, match="not approved"):
        manage.apply_approved(position, proposal, AS_OF)


def test_an_approved_stop_move_creates_a_new_version() -> None:
    position = _position()
    approved = ManagementAction(
        position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.MOVE_STOP,
        status=ActionStatus.APPROVED, reason="raise",
        old_stop=Decimal(96), new_stop=Decimal(98),
    )
    updated = manage.apply_approved(position, approved, AS_OF)

    assert updated.version == 2
    assert updated.current_stop == Decimal(98)
    assert position.current_stop == Decimal(96), "the original is untouched"
    assert updated.initial_stop == position.initial_stop


def test_a_partial_exit_leaving_nothing_is_refused() -> None:
    approved = ManagementAction(
        position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.PARTIAL_EXIT,
        status=ActionStatus.APPROVED, reason="scale out", shares_affected=50,
    )
    with pytest.raises(ValueError, match="that is a full exit"):
        manage.apply_approved(_position(), approved, AS_OF)


# ------------------------------------------------------------------ the store

@pytest.fixture
def store(tmp_path):
    with PositionStore(tmp_path / "positions.duckdb") as s:
        yield s


def test_the_store_is_append_only(store) -> None:
    store.record(_position())
    with pytest.raises(ValueError, match="append-only"):
        store.record(_position())


def test_a_stop_move_keeps_the_earlier_version_readable(store) -> None:
    """Appendix G's Audit entity is "immutable initial plan AND ALL LATER VERSIONS"."""
    store.record(_position())
    store.record(_position(version=2, current_stop=Decimal(102),
                           knowledge_time=datetime(2025, 12, 10, tzinfo=UTC)))

    history = store.history("POS-1")
    assert [p.version for p in history] == [1, 2]
    assert [p.current_stop for p in history] == [Decimal(96), Decimal(102)]


def test_open_as_of_returns_the_version_current_then(store) -> None:
    """Replaying an earlier run must see the stop that was current then, not today's."""
    store.record(_position())
    store.record(_position(version=2, current_stop=Decimal(102),
                           knowledge_time=datetime(2025, 12, 10, tzinfo=UTC)))

    early = store.open_as_of(datetime(2025, 12, 5, tzinfo=UTC))
    late = store.open_as_of(datetime(2025, 12, 20, tzinfo=UTC))
    assert [p.current_stop for p in early] == [Decimal(96)]
    assert [p.current_stop for p in late] == [Decimal(102)]


def test_a_closed_position_is_not_open(store) -> None:
    store.record(_position())
    store.record(_position(version=2, closed_on=date(2025, 12, 15),
                           knowledge_time=datetime(2025, 12, 15, tzinfo=UTC)))
    assert store.open_as_of(AS_OF) == []


def test_pending_approvals_counts_only_what_needs_an_answer(store) -> None:
    store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                   kind=ActionKind.HOLD, reason="intact"))
    store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                   kind=ActionKind.MOVE_STOP, reason="raise",
                                   old_stop=Decimal(96), new_stop=Decimal(98)))
    assert store.pending_approvals() == 1


def test_positions_are_returned_sorted(store) -> None:
    """Unordered iteration feeding the first step of the run is the named determinism hazard."""
    for pid in ("POS-9", "POS-1", "POS-5"):
        store.record(_position(position_id=pid))
    assert [p.position_id for p in store.open_as_of(AS_OF)] == ["POS-1", "POS-5", "POS-9"]


# ------------------------------------------------------------------ the run order

def _sessions(exchange, start: date, end: date) -> list[date]:
    from swingdesk.reference_data import calendar as cal
    return [s.session_date for s in cal.sessions(exchange, start, end)]


@pytest.fixture
def wired(tmp_path):
    with (
        BarStore(tmp_path / "bars.duckdb") as bars,
        Journal(tmp_path / "journal.duckdb") as journal,
        PositionStore(tmp_path / "positions.duckdb") as positions,
    ):
        yield bars, journal, positions


def test_open_positions_are_evaluated_before_candidates(wired, registry) -> None:
    """CHECKLIST_SPEC 4, asserted from the run's own trace rather than from a claim."""
    bars, journal, positions = wired
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    positions.record(_position())

    result = run([TEST_US, TEST_CA], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}), positions=positions)

    assert result.steps == ("positions", "candidates")
    assert result.positions_ran_first
    assert len(result.positions) == 1


def test_a_position_with_no_bars_is_paused_not_skipped(wired, registry) -> None:
    """The owner must be told a position could not be evaluated, not left to infer it."""
    bars, journal, positions = wired
    positions.record(_position(instrument_id="TEST.NOBARS"))

    result = run([], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({}), positions=positions)

    outcome = result.positions[0]
    assert outcome.stale
    assert outcome.action.kind is ActionKind.PAUSE
    assert outcome.action.reason_code == "DATA"


def test_the_run_proposes_and_never_applies(wired, registry) -> None:
    """D1 and D6 together: the stored position is untouched by the run."""
    bars, journal, positions = wired
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    positions.record(_position())

    run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
        fetcher=fixture_fetcher({TEST_US.id: sessions}), positions=positions)

    assert [p.version for p in positions.history("POS-1")] == [1], "no new version was written"
    assert positions.actions_for("POS-1"), "but the proposal was recorded"
    for action in positions.actions_for("POS-1"):
        assert action.status is ActionStatus.PROPOSED


def test_a_run_without_a_position_store_still_works(wired, registry) -> None:
    """The store is optional so the walking skeleton keeps running while N2 lands."""
    bars, journal, _ = wired
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}))
    assert result.steps == ("candidates",)
    assert result.positions == []


# ------------------------------------------------------------------ the proposal rule

def test_a_broken_stop_proposes_an_exit_before_anything_else(registry) -> None:
    """Same ordering as the backtest engine. The live and simulated paths must agree here."""
    from tests.conftest import make_bars

    bar = make_bars(TEST_US, [date(2026, 1, 14)])[0]
    low_bar = bar.model_copy(update={"low": Decimal(90), "open": Decimal(99)})
    action = manage.evaluate(
        _position(), low_bar, ExitPolicy(Decimal(2), 20), AS_OF, bars_held=3, atr=Decimal(2)
    )
    assert action.kind is ActionKind.EXIT_NOW


def test_a_stop_is_only_ever_proposed_upward(registry) -> None:
    """A stop that can move down is not a stop."""
    from tests.conftest import make_bars

    bar = make_bars(TEST_US, [date(2026, 1, 14)])[0]
    # Close far above entry: the ATR-derived stop is well above the current one.
    high = bar.model_copy(update={"close": Decimal(140), "high": Decimal(141),
                                  "low": Decimal(139), "open": Decimal(139)})
    up = manage.evaluate(_position(), high, ExitPolicy(Decimal(2), 20), AS_OF,
                         bars_held=3, atr=Decimal(2))
    assert up.kind is ActionKind.MOVE_STOP and up.new_stop > up.old_stop

    # Close just above entry: the derived stop is BELOW the current one, so nothing is proposed.
    modest = bar.model_copy(update={"close": Decimal(99), "high": Decimal(100),
                                    "low": Decimal(98), "open": Decimal(98)})
    held = manage.evaluate(_position(), modest, ExitPolicy(Decimal(2), 20), AS_OF,
                           bars_held=3, atr=Decimal(2))
    assert held.kind is ActionKind.HOLD
