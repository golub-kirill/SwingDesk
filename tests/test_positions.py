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
    Fill,
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
        # Cost-inclusive R denominator (2026-08-16). DR-010 charges
        # `max(floor 0.25, 50bp x entry)`, which at a 100 entry is 0.50 - the bp term, not the
        # floor, which binds only below a 50 entry. So this fixture risks 4.50/share rather than
        # 4.00, and it is the number `size_long(100, 96, "USD")` freezes for the same instrument.
        initial_costs_per_share=Decimal("0.50"),
        knowledge_time=datetime(2025, 12, 1, tzinfo=UTC),
    )
    base.update(kwargs)
    return Position(**base)


# ------------------------------------------------------------------ the R denominator

def test_r_denominator_survives_a_stop_move() -> None:
    """RISK_SPEC 2: R is what was risked when the decision was made, not what is at risk now."""
    position = _position()
    # entry 100 - stop 96 + costs 0.50
    assert position.initial_risk_per_share == Decimal("4.50")

    moved = position.model_copy(update={"current_stop": Decimal(102), "version": 2})
    assert moved.initial_risk_per_share == Decimal("4.50"), "unchanged by the stop move"
    assert moved.r_at(Decimal(106)) == position.r_at(Decimal(106)), "R is unmoved by the stop"


def test_the_r_denominator_includes_costs() -> None:
    """`sizing.size_long` freezes `planned_risk` from `entry - stop + costs`, so that is what
    `RISK_SPEC.md` §2 means by the denominator.

    Until 2026-08-16 `Position` returned `entry - stop`, so the R a position reported and the R its
    own sizing planned were two different numbers - and the difference ran one way. At a 6% cost
    fraction a trade that made 0.94R reported as 1.00R, always flattering, on the one statistic the
    entire validation programme is denominated in.
    """
    priced = _position(initial_costs_per_share=Decimal("0.50"))
    free = _position(initial_costs_per_share=Decimal(0))

    assert priced.initial_risk_per_share > free.initial_risk_per_share
    assert free.initial_risk_per_share == Decimal(4), "costs of zero recover the old arithmetic"
    # The same exit is worth LESS R once the costs of getting there are in the denominator.
    assert priced.r_at(Decimal(106)) < free.r_at(Decimal(106))


def test_costs_cannot_be_negative() -> None:
    """A negative cost would shrink the denominator and inflate every R computed from it."""
    with pytest.raises(ValidationError):
        _position(initial_costs_per_share=Decimal("-0.01"))


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


def test_a_held_dual_class_position_asks_the_vendor_for_the_right_symbol() -> None:
    """`BRK.B` is the directory's id; the vendor wants `BRK-B`. The id must not change either.

    Rebuilding the Instrument by stripping `.TO` produced ticker `BRK.B`, so the daily refresh of a
    held dual-class position raised `VendorUnavailable`, the caller swallowed it, and management
    continued against whatever was already stored. A position managed on silently stale bars looks
    exactly like a position managed correctly - which is why this is asserted rather than watched
    for. Same mapping defect that once left `BRK.A` and `BRK.B` out of every universe.
    """
    from swingdesk.application.pipeline import _held_instrument

    held = _held_instrument("BRK.B")
    assert held.id == "BRK.B", "the id is identity and is never re-derived"
    assert held.ticker == "BRK-B"
    assert held.vendor_symbol == "BRK-B"

    canadian = _held_instrument("SHOP.TO")
    assert canadian.id == "SHOP.TO"
    assert canadian.vendor_symbol == "SHOP.TO", "the .TO suffix is re-added by the contract"
    assert canadian.currency == "CAD"


def test_output_hash_covers_the_position_half_of_the_run(wired, registry) -> None:
    """A run proposing an action on a held position must not hash like a run holding nothing.

    Appendix T puts positions FIRST in the run, and until 2026-08-16 `output_hash` contained no
    trace of them in any form - not the proposal, not the position, not even its existence. So
    `a.reproducible` read "reproduces byte-identically" while half the run was outside the bytes.
    """
    bars, journal, positions = wired
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    without = run([TEST_US], FixedClock(AS_OF), registry, bars, journal,
                  mode=RunMode.LIVE_AS_OF, fetcher=fetcher)

    positions.record(_position())
    holding = run([TEST_US], FixedClock(AS_OF), registry, bars, journal,
                  mode=RunMode.LIVE_AS_OF, fetcher=fetcher, positions=positions)

    assert holding.positions[0].action is not None, "the run must have proposed something"
    assert without.manifest.output_hash != holding.manifest.output_hash


def test_output_hash_moves_when_the_proposed_stop_moves(tmp_path, registry) -> None:
    """Two positions differing only in their current stop are two different proposals.

    The action KIND can be identical - both EXIT_NOW - while the stop the owner is being told to
    move from is not. Hashing the kind alone would still leave that invisible.
    """
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    def hash_for(stop: Decimal, tag: str) -> str:
        with (
            BarStore(tmp_path / f"bars-{tag}.duckdb") as bars,
            Journal(tmp_path / f"journal-{tag}.duckdb") as journal,
            PositionStore(tmp_path / f"positions-{tag}.duckdb") as positions,
        ):
            positions.record(_position(current_stop=stop))
            result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal,
                         mode=RunMode.LIVE_AS_OF, fetcher=fetcher, positions=positions)
            return result.manifest.output_hash

    assert hash_for(Decimal(96), "low") != hash_for(Decimal("99.5"), "high")


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


# ------------------------------------------------- the owner's answer (US-010, TODO.md 6b 4 + 5)


def test_a_response_is_a_separate_fact_and_the_proposal_is_untouched(store) -> None:
    """`management.status` records what the RUN proposed and must stay readable as that forever.
    Rewriting it to `approved` would destroy the record of what was asked, which is half of what
    an audit trail is for - so the answer lives in its own append-only table.
    """
    store.record(_position())
    store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                   kind=ActionKind.MOVE_STOP, reason="raise",
                                   old_stop=Decimal(96), new_stop=Decimal(98)))

    store.respond("POS-1", 1, choice=ActionStatus.APPROVED, reason="trend intact", at=AS_OF)

    assert store.proposal_at("POS-1", 1).status is ActionStatus.PROPOSED
    answer = store.response_for("POS-1", 1)
    assert answer.choice is ActionStatus.APPROVED
    assert answer.reason == "trend intact"
    assert answer.responded_at == AS_OF


def test_a_proposal_can_be_answered_only_once(store) -> None:
    """A recorded decision is immutable. Changing your mind is a new proposal, not an edit."""
    store.record(_position())
    store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                   kind=ActionKind.MOVE_STOP, reason="raise",
                                   old_stop=Decimal(96), new_stop=Decimal(98)))
    store.respond("POS-1", 1, choice=ActionStatus.APPROVED, reason="yes", at=AS_OF)

    with pytest.raises(ValueError, match="already answered"):
        store.respond("POS-1", 1, choice=ActionStatus.REJECTED, reason="no", at=AS_OF)


def test_a_response_requires_a_reason(store) -> None:
    """Production rule 3.8. An approval with no stated reason is an unlogged judgment."""
    store.record(_position())
    store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                   kind=ActionKind.MOVE_STOP, reason="raise",
                                   old_stop=Decimal(96), new_stop=Decimal(98)))

    with pytest.raises(ValueError, match="carries a reason"):
        store.respond("POS-1", 1, choice=ActionStatus.APPROVED, reason="   ", at=AS_OF)


def test_only_approved_or_rejected_are_answers(store) -> None:
    """`proposed` is the ABSENCE of an answer and `expired` is not something the owner chooses."""
    store.record(_position())
    store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                   kind=ActionKind.MOVE_STOP, reason="raise",
                                   old_stop=Decimal(96), new_stop=Decimal(98)))

    for not_an_answer in (ActionStatus.PROPOSED, ActionStatus.EXPIRED):
        with pytest.raises(ValueError, match="APPROVED or REJECTED"):
            store.respond("POS-1", 1, choice=not_an_answer, reason="x", at=AS_OF)


def test_answering_a_proposal_that_does_not_exist_is_refused(store) -> None:
    store.record(_position())
    with pytest.raises(ValueError, match="no proposal"):
        store.respond("POS-1", 99, choice=ActionStatus.APPROVED, reason="x", at=AS_OF)


def test_pending_is_the_absence_of_an_answer_not_the_status_column(store) -> None:
    """The first definition counted `status = 'proposed'`, which never changes - so every answered
    proposal would have stayed pending forever the moment responses existed."""
    store.record(_position())
    store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                   kind=ActionKind.MOVE_STOP, reason="raise",
                                   old_stop=Decimal(96), new_stop=Decimal(98)))

    assert [p.sequence for p in store.pending()] == [1]
    assert store.pending_approvals() == 1

    store.respond("POS-1", 1, choice=ActionStatus.REJECTED, reason="too early", at=AS_OF)

    assert store.pending() == []
    assert store.pending_approvals() == 0, "an answered proposal is not still waiting"


def test_a_hold_never_awaits_an_answer(store) -> None:
    """D6 routes stop moves and partial exits through the owner. A hold is a decision the system
    records, not a question it asks."""
    store.record(_position())
    store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                   kind=ActionKind.HOLD, reason="stop intact"))
    assert store.pending() == []


def test_proposal_at_reads_by_sequence_not_by_list_position(store) -> None:
    """Sequences are monotonic, not contiguous. Indexing a list would apply the owner's answer to
    the wrong proposal the first time a gap appeared."""
    store.record(_position())
    for new_stop in (Decimal(97), Decimal(98), Decimal(99)):
        store.propose(ManagementAction(position_id="POS-1", proposed_at=AS_OF,
                                       kind=ActionKind.MOVE_STOP, reason=f"to {new_stop}",
                                       old_stop=Decimal(96), new_stop=new_stop))

    assert store.proposal_at("POS-1", 2).new_stop == Decimal(98)
    assert store.proposal_at("POS-1", 4) is None


# ------------------------------------------------------- fills (US-011, TODO.md 6b item 6)


def _approved_exit(store, *, reason_code: str = "STOP") -> None:
    """A position with one APPROVED EXIT_NOW on it, ready to be filled."""
    store.record(_position())
    store.propose(ManagementAction(
        position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.EXIT_NOW,
        reason_code=reason_code, reason="stop touched", old_stop=Decimal(96)))
    store.respond("POS-1", 1, choice=ActionStatus.APPROVED, reason="out", at=AS_OF)


def _fill(**kwargs) -> Fill:
    base = dict(position_id="POS-1", sequence=1, filled_on=date(2026, 1, 15), shares=50,
                price=Decimal("95.40"), commission=Decimal("1.25"),
                planned_price=Decimal(96), recorded_at=AS_OF)
    base.update(kwargs)
    return Fill(**base)


def test_slippage_is_measured_against_the_original_denominator(store) -> None:
    """US-011. The denominator never moves - not after a trail, not after a scale-out. Measuring
    against a shrinking one would make the same dollar miss look worse as a position is reduced."""
    _approved_exit(store)
    store.record_fill(_fill())

    recorded = store.fills_for("POS-1")[0]
    assert recorded.slippage_per_share == Decimal("0.60"), "planned 96, filled 95.40"
    # _position()'s R denominator is entry 100 - stop 96 = 4.
    assert recorded.slippage_r(Decimal(4)) == Decimal("0.15")


def test_slippage_refuses_when_the_plan_named_no_price(store) -> None:
    """A maximum-holding-period exit is at market. Reporting 0.00 slippage would be a manufactured
    measurement, and it would flatter the strategy - unknown slippage is not absent slippage."""
    _approved_exit(store, reason_code="TIME")
    store.record_fill(_fill(planned_price=None))

    recorded = store.fills_for("POS-1")[0]
    assert recorded.slippage_per_share is None, "None is a refusal, never a zero"
    assert recorded.slippage_r(Decimal(4)) is None


def test_slippage_in_r_refuses_a_non_positive_denominator() -> None:
    with pytest.raises(ValueError, match="not positive"):
        _fill().slippage_r(Decimal(0))


def test_a_fill_requires_an_approved_action(store) -> None:
    """D6 from the far side of the trade: a fill settling something nobody approved is either a
    mis-keyed sequence or an action taken outside this system."""
    store.record(_position())
    store.propose(ManagementAction(
        position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.EXIT_NOW,
        reason_code="STOP", reason="stop touched", old_stop=Decimal(96)))

    with pytest.raises(ValueError, match="no recorded response"):
        store.record_fill(_fill())


def test_a_fill_against_a_rejected_proposal_is_refused(store) -> None:
    store.record(_position())
    store.propose(ManagementAction(
        position_id="POS-1", proposed_at=AS_OF, kind=ActionKind.EXIT_NOW,
        reason_code="STOP", reason="stop touched", old_stop=Decimal(96)))
    store.respond("POS-1", 1, choice=ActionStatus.REJECTED, reason="holding", at=AS_OF)

    with pytest.raises(ValueError, match="not approved"):
        store.record_fill(_fill())


def test_a_fill_is_recorded_once(store) -> None:
    _approved_exit(store)
    store.record_fill(_fill())
    with pytest.raises(ValueError, match="already filled"):
        store.record_fill(_fill(price=Decimal(99)))


def test_open_risk_is_recomputed_across_the_book_not_decremented(store) -> None:
    """US-011's second clause. Two positions, one partially exited: the book's open risk is the sum
    of what the CURRENT stops imply, never a running total with the exited part subtracted."""
    store.record(_position())                                   # 50 sh, entry 100, stop 96 -> 200
    store.record(_position(position_id="POS-2", entry_price=Decimal(50),
                           initial_stop=Decimal(45), current_stop=Decimal(45), shares=10))  # -> 50
    assert store.open_risk_as_of(AS_OF) == Decimal(250)

    # POS-1 scales out to 20 shares and trails its stop to 98.
    store.record(_position(version=2, shares=20, current_stop=Decimal(98),
                           knowledge_time=datetime(2026, 1, 10, tzinfo=UTC)))

    # Recomputed: (100-98)*20 + (50-45)*10 = 40 + 50. A decremented total would still read 250
    # minus something, and would not know the stop moved at all.
    assert store.open_risk_as_of(AS_OF) == Decimal(90)


def test_a_closed_position_contributes_no_open_risk(store) -> None:
    store.record(_position())
    assert store.open_risk_as_of(AS_OF) == Decimal(200)
    store.record(_position(version=2, closed_on=date(2026, 1, 14),
                           knowledge_time=datetime(2026, 1, 14, tzinfo=UTC)))
    assert store.open_risk_as_of(AS_OF) == Decimal(0)
