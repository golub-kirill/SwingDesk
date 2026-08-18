"""The generated pre-trade checklist.

The tests that matter most are about what the checklist REFUSES to claim. A form that ticks an item
whose evidence does not exist is worse than no form: it converts a gap in the system into a
statement about the trade.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from tests.conftest import TEST_US

from swingdesk.application import checklist as builder
from swingdesk.contracts.checklist import TERMINAL_STATES, Checklist, ChecklistItem, ItemState
from swingdesk.journal_evidence.journal import DecisionRecord
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.trade_management.sizing import Refusal, RiskSnapshot

AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
POLICY = ExitPolicy(Decimal("2.0"), 20)


def _risk() -> RiskSnapshot:
    from swingdesk.contracts.observation import ParameterUse

    return RiskSnapshot(
        equity=Decimal(10000), risk_pct=Decimal("1.0"), allowed_risk=Decimal(100),
        entry=Decimal(100), stop=Decimal(96), costs_per_share=Decimal("0.02"),
        risk_per_share=Decimal("4.02"), shares=24, position_value=Decimal(2400),
        planned_risk=Decimal("96.48"),
        parameters=(ParameterUse(id="risk.per_trade_pct", value="1.0",
                                 provenance="assumed:test"),),
    )


def _generate(**kwargs) -> Checklist:
    base = dict(
        instrument=TEST_US, run_id="run-1", generated_at=AS_OF,
        risk=_risk(), decision=DecisionRecord(TEST_US.id, "Watch", None, "sized"),
        exits=POLICY,
    )
    base.update(kwargs)
    return builder.generate(**base)


# ------------------------------------------------------------------ shape

def test_the_pre_trade_checklist_has_all_eighteen_items() -> None:
    """Appendix E, counted by CHECKLIST_SPEC and parsed from its verbatim block."""
    assert len(_generate().items) == 18


def test_item_text_comes_from_the_transcription_not_a_third_copy() -> None:
    """PDF -> CHECKLIST_SPEC (gate 2) -> registry. A third hand-copy is a third place to drift."""
    spec = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "docs" / "04-journal" / "CHECKLIST_SPEC.md"
    ).read_text(encoding="utf-8")
    for item in _generate().items:
        assert item.text in spec, f"{item.id} text is not in CHECKLIST_SPEC"


# ------------------------------------------------------------------ what it refuses to claim

def test_an_item_whose_evidence_is_missing_is_unavailable_not_human() -> None:
    """The distinction the whole design rests on.

    An `UNAVAILABLE` item is a gap in the SYSTEM. Demoting it to a human question would hide that
    gap behind a person, and the count of what the system can answer would silently look better.
    """
    items = {item.id: item for item in _generate().items}
    assert items["E04"].state is ItemState.UNAVAILABLE, "regime is not wired into the daily run"
    assert items["E11"].state is ItemState.UNAVAILABLE, "no event calendar"
    assert items["E06"].state is ItemState.HUMAN, "'1Y and 3M support the idea' is a judgement"


def test_every_unavailable_item_says_what_is_missing() -> None:
    """An unexplained gap is not actionable."""
    for item in _generate().items:
        if item.state is ItemState.UNAVAILABLE:
            assert item.note and len(item.note) > 20, f"{item.id} does not say what is missing"


def test_a_tick_without_evidence_is_rejected_by_the_contract() -> None:
    with pytest.raises(ValidationError, match="must carry a note"):
        ChecklistItem(id="E01", text="anything", state=ItemState.PASS)


def test_a_half_answerable_item_is_not_answered() -> None:
    """E03 - data is fresh and corporate actions are accounted for - is two things.

    Session completeness is checked; corporate actions are not. Half an answer is not an answer,
    and ticking it would claim the half that was never checked.
    """
    items = {item.id: item for item in _generate().items}
    assert items["E03"].state is ItemState.UNAVAILABLE
    assert "corporate actions" in items["E03"].note


def test_machine_coverage_is_five_of_eighteen_today() -> None:
    """A number rather than an impression, and it is meant to go up.

    CHECKLIST_SPEC says twelve are machine-checkable given the data the system holds. It does not
    hold all of it, and this asserts the honest figure so an improvement is visible as a change.
    Went from four to five when the universe path landed (ROADMAP X1).
    """
    assert builder.machine_coverage() == (5, 18)


# ------------------------------------------------------------------ the answers it does give

def test_the_four_answerable_items_answer() -> None:
    """Four, not five: E02 is answerable by the SYSTEM but needs a universe, and this run has none."""
    items = {item.id: item for item in _generate().items}
    assert items["E01"].state is ItemState.PASS   # ticker / exchange / currency
    assert items["E13"].state is ItemState.PASS   # risk and shares recomputed
    assert items["E16"].state is ItemState.PASS   # time stop recorded
    assert items["E17"].state is ItemState.PASS   # no skip condition fired


# ------------------------------------------------------------------ E02, the universe item

def _selection(members=(TEST_US.id,), *, eligible=1, measured=1, capped_from=None):
    from swingdesk.application.universe import Membership, UniverseSelection
    from swingdesk.reference_data.universe import LiquidityRule

    rule = LiquidityRule(min_price=Decimal("5.00"), min_adtv=Decimal("5000000"),
                         adtv_window=20, min_history=250)
    return UniverseSelection(
        as_of=AS_OF, rule=rule, parameters=(), directory_pull=AS_OF,
        eligible=eligible, measured=measured, capped_from=capped_from,
        members=tuple(
            Membership(instrument=TEST_US, close=Decimal("100"),
                       adtv=Decimal("10000000"), bars=300)
            for member_id in members if member_id == TEST_US.id
        ),
    )


def test_without_a_universe_the_item_is_unavailable_not_a_pass() -> None:
    """Reporting PASS because the operator typed the symbol would make E02 mean "you asked for it"."""
    item = {i.id: i for i in _generate().items}["E02"]
    assert item.state is ItemState.UNAVAILABLE
    assert "--universe" in item.note


def test_a_member_passes_and_the_note_carries_the_measurements() -> None:
    """E02 has to say WHY something is in the universe, not merely that it is."""
    item = {i.id: i for i in _generate(universe=_selection()).items}["E02"]
    assert item.state is ItemState.PASS
    assert "10,000,000" in item.note
    assert "300 bars" in item.note


def test_an_instrument_outside_the_universe_fails() -> None:
    """Reachable for a held position the rule no longer admits — the case that must not pass."""
    item = {i.id: i for i in _generate(universe=_selection(members=())).items}["E02"]
    assert item.state is ItemState.FAIL
    assert "not admitted" in item.note


def test_a_partial_universe_still_answers_but_says_it_is_partial() -> None:
    """Coverage bounds which OTHER symbols might qualify; it does not weaken a measured member."""
    selection = _selection(eligible=13048, measured=312)
    item = {i.id: i for i in _generate(universe=selection).items}["E02"]
    assert item.state is ItemState.PASS
    assert "PARTIAL" in item.note
    assert "312 of 13048" in item.note


def test_a_capped_universe_says_it_was_capped() -> None:
    item = {i.id: i for i in _generate(universe=_selection(capped_from=900)).items}["E02"]
    assert "capped to 1 of 900" in item.note


def test_a_refused_sizing_fails_the_risk_item() -> None:
    refusal = Refusal(code="RISK", reason="risk.per_trade_pct is unset",
                      parameter_id="risk.per_trade_pct")
    items = {item.id: item for item in _generate(risk=refusal).items}
    assert items["E13"].state is ItemState.FAIL
    assert "risk.per_trade_pct" in items["E13"].note


def test_a_skipped_candidate_fails_the_no_skip_item() -> None:
    skip = DecisionRecord(TEST_US.id, "Skip", "DATA", "incomplete session")
    items = {item.id: item for item in _generate(decision=skip).items}
    assert items["E17"].state is ItemState.FAIL
    assert "DATA" in items["E17"].note


# ------------------------------------------------------------------ terminal state

def test_a_generated_checklist_never_completes_itself() -> None:
    """The system prepares the decision; the human makes it (CHARTER 2).

    Reaching `Complete` unaided would mean the system had answered a question only a person can.
    """
    generated = _generate()
    assert generated.terminal_state() == "Research"
    assert generated.terminal_state() in TERMINAL_STATES
    assert generated.unanswered


def test_a_failure_drives_the_checklist_to_skip() -> None:
    skip = DecisionRecord(TEST_US.id, "Skip", "DATA", "incomplete session")
    assert _generate(decision=skip).terminal_state() == "Skip"


def test_unanswered_includes_the_unavailable_ones() -> None:
    """An item the system could not answer lands on the person, not in a footnote."""
    generated = _generate()
    unanswered = {item.id for item in generated.unanswered}
    assert "E04" in unanswered, "unavailable"
    assert "E06" in unanswered, "human"
    assert generated.counts["pass"] == 4


# ------------------------------------------------------------------ the run

def test_the_run_generates_a_checklist_for_every_decided_candidate(tmp_path, registry) -> None:
    """Including a Skip - a skipped candidate's checklist is what makes the skip reviewable."""
    from tests.conftest import TEST_CA, fixture_fetcher

    from swingdesk.application.pipeline import run
    from swingdesk.contracts.run import RunMode
    from swingdesk.journal_evidence.journal import Journal
    from swingdesk.market_data import BarStore
    from swingdesk.platform.clock import FixedClock
    from swingdesk.reference_data import calendar as cal

    sessions = [s.session_date
                for s in cal.sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))]
    with (
        BarStore(tmp_path / "bars.duckdb") as bars,
        Journal(tmp_path / "journal.duckdb") as journal,
    ):
        result = run([TEST_US, TEST_CA], FixedClock(AS_OF), registry, bars, journal,
                     mode=RunMode.LIVE_AS_OF,
                     fetcher=fixture_fetcher({TEST_US.id: sessions}))

    assert len(result.outcomes) == 2
    for outcome in result.outcomes:
        assert outcome.checklist is not None, f"{outcome.instrument.id} has no checklist"
        assert len(outcome.checklist.items) == 18
        assert outcome.checklist.run_id == result.manifest.run_id
