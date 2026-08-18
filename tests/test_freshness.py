"""The staleness gate: the measurement, the window, and what the decision path does with them.

`DATA_QUALITY_SPEC` §2.1 has specified this rule since it was written and `calendar.sessions_behind`
has implemented the measurement the whole time - with no caller anywhere in `src/`. It was the last
mutant surviving the entire suite, and it survived because it was dead code rather than because the
tests were weak. `DR-015` supplied the number it was waiting for.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tests.conftest import TEST_US, fixture_fetcher

from swingdesk.application.pipeline import run
from swingdesk.contracts.position import ActionKind, Position
from swingdesk.contracts.reference import Exchange
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.market_data.freshness import PARAMETER, Verdict, assess, window
from swingdesk.platform.clock import FixedClock
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import calendar as cal

AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
WINDOW = 2


def _sessions(exchange, start: date, end: date) -> list[date]:
    return [s.session_date for s in cal.sessions(exchange, start, end)]


@pytest.fixture
def stores(tmp_path):
    with (
        BarStore(tmp_path / "bars.duckdb") as store,
        Journal(tmp_path / "journal.duckdb") as journal,
    ):
        yield store, journal


def _without(registry: ParameterRegistry, parameter_id: str) -> ParameterRegistry:
    entries = {pid: dict(entry) for pid, entry in registry._entries.items()}
    entries[parameter_id]["value"] = None
    return type(registry)(entries)


# ------------------------------------------------------------------ the measurement


def test_a_series_level_with_the_last_completed_session_is_fresh() -> None:
    assessment = assess(Exchange.NYSE, date(2026, 1, 15), AS_OF, WINDOW)
    assert assessment.sessions_behind == 0
    assert assessment.verdict is Verdict.FRESH


def test_friday_to_monday_is_one_session_not_three_days() -> None:
    """The case the owner raised, and the one the window is most likely to be misread on.

    2026-01-16 is a Friday and 2026-01-20 the following Tuesday - the Monday was Martin Luther King
    Jr. Day, so the calendar carries an extra closure on top of the weekend. A Friday series read on
    Tuesday evening is ONE session behind and four calendar days behind. Counting days would refuse
    the entire universe on the first working day of most weeks (`AGENTS.md` §3, `DR-015` §2.2).
    """
    tuesday = datetime(2026, 1, 20, 21, 0, tzinfo=UTC)
    assert not cal.is_open(Exchange.NYSE, date(2026, 1, 19)), "the fixture assumes the holiday"

    assessment = assess(Exchange.NYSE, date(2026, 1, 16), tuesday, WINDOW)

    assert assessment.sessions_behind == 1
    assert (tuesday.date() - date(2026, 1, 16)).days == 4, "four calendar days, one session"


def test_one_session_behind_is_stale_and_not_yet_dropped() -> None:
    """`DR-015` §2.1: the window is a stopping rule, not a tolerance. One behind still refuses to
    decide - it is short of the window, which only decides when to stop TRYING."""
    assessment = assess(Exchange.NYSE, date(2026, 1, 14), AS_OF, WINDOW)
    assert assessment.sessions_behind == 1
    assert assessment.verdict is Verdict.STALE


def test_the_window_is_reached_at_two_and_drops_the_instrument() -> None:
    assessment = assess(Exchange.NYSE, date(2026, 1, 13), AS_OF, WINDOW)
    assert assessment.sessions_behind == 2
    assert assessment.verdict is Verdict.DROPPED
    assert "dropped from this run" in assessment.reason


def test_the_reason_names_the_count_and_the_window() -> None:
    """"Stale" alone tells the owner nothing about whether tomorrow fixes it by itself."""
    stale = assess(Exchange.NYSE, date(2026, 1, 14), AS_OF, WINDOW)
    dropped = assess(Exchange.NYSE, date(2026, 1, 13), AS_OF, WINDOW)

    assert "1 session behind" in stale.reason
    assert "2 sessions behind" in dropped.reason
    assert f"2-session window {PARAMETER} allows" in dropped.reason


def test_the_window_is_read_from_the_registry_and_refuses_when_unset(registry) -> None:
    """Unset is not a default (`AGENTS.md` §3). An invented window is the silent default the
    registry exists to prevent, and a plausible one is the most dangerous kind."""
    assert window(registry) == 2

    with pytest.raises(ParameterUnset) as unset:
        window(_without(registry, PARAMETER))
    assert unset.value.parameter_id == PARAMETER


# ------------------------------------------------------------------ the candidate path


def test_a_stale_candidate_is_refused_instead_of_sized(stores, registry) -> None:
    """The defect this closes, and it is measured rather than imagined: on the 2026-08-17 scheduled
    run, 67 of 1152 candidates ended one session behind, every one reported `completeness clean`,
    and every one was sized and left on `Watch` against a stale close."""
    store, journal = stores
    stale = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))

    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: stale}))

    decision = result.decisions[0]
    assert decision.decision == "Skip"
    assert decision.reason_code == "DATA"
    assert "1 session behind" in decision.reason
    assert result.outcomes[0].risk is None, "it must not have been sized"


def test_the_same_candidate_one_session_fresher_is_sized(stores, registry) -> None:
    """The positive control. Without it, the test above passes against a pipeline that refuses
    everything, which is exactly what an over-eager freshness gate would look like."""
    store, journal = stores
    fresh = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))

    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: fresh}))

    assert result.decisions[0].decision == "Watch"
    assert result.outcomes[0].risk is not None


def test_a_candidate_past_the_window_says_it_was_dropped(stores, registry) -> None:
    store, journal = stores
    ancient = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 13))

    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: ancient}))

    decision = result.decisions[0]
    assert decision.decision == "Skip"
    assert decision.reason_code == "DATA"
    assert "dropped from this run" in decision.reason


def test_staleness_is_checked_before_completeness(stores, registry) -> None:
    """They are different questions and the spec asks both (§2.1 then §2.2). Completeness looks for
    a hole INSIDE the stored window, so a series that simply stops early passes it - which is why
    all 67 stale candidates on 2026-08-17 were reported `completeness clean`."""
    store, journal = stores
    # A gap in the middle AND a stale tail. Completeness would report the gap; freshness comes first.
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    del sessions[-5]

    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}))

    assert "session behind" in result.decisions[0].reason
    assert result.outcomes[0].completeness_findings == (), "completeness was never reached"


def test_an_unset_window_refuses_every_candidate_and_names_the_parameter(stores, registry) -> None:
    """The same fail-closed shape the exit policy takes, and the same consequence: every candidate
    leaves with a coded decision naming what is missing, and the run still completes."""
    store, journal = stores
    fresh = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))

    result = run([TEST_US], FixedClock(AS_OF), _without(registry, PARAMETER), store, journal,
                 mode=RunMode.LIVE_AS_OF, fetcher=fixture_fetcher({TEST_US.id: fresh}))

    decision = result.decisions[0]
    assert decision.decision == "Skip"
    assert decision.reason_code == "DATA"
    assert decision.parameter_id == PARAMETER


# ------------------------------------------------------------------ the held-position path


def _position(**kwargs) -> Position:
    base = dict(
        position_id="POS-1", version=1, instrument_id=TEST_US.id,
        opened_on=date(2025, 12, 1), entry_price=Decimal(100), shares=50,
        initial_stop=Decimal(96), current_stop=Decimal(96),
        initial_costs_per_share=Decimal("0.50"),
        knowledge_time=datetime(2025, 12, 1, tzinfo=UTC),
    )
    base.update(kwargs)
    return Position(**base)


@pytest.fixture
def wired(tmp_path):
    with (
        BarStore(tmp_path / "bars.duckdb") as bars,
        Journal(tmp_path / "journal.duckdb") as journal,
        PositionStore(tmp_path / "positions.duckdb") as positions,
    ):
        yield bars, journal, positions


def test_a_position_on_stale_bars_pauses_instead_of_being_managed(wired, registry) -> None:
    """The gap `TODO.md` §1 named. Fetching a held position is fail-open by design
    (`FAIL_CLOSED_POLICY` row 1) and `stale` was set ONLY when there were no bars at all - so a
    position whose fetch failed went on being managed against stored bars of any age, silently.

    Fail-open on the FETCH is correct and unchanged. What changes is that DECIDING on what it fell
    back to is now fail-closed, which is the distinction §7 row 2 of that policy draws.
    """
    bars, journal, positions = wired
    stale = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    positions.record(_position())

    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: stale}), positions=positions)

    managed = result.positions[0]
    assert managed.stale
    assert managed.action.kind is ActionKind.PAUSE
    assert managed.action.reason_code == "DATA"
    assert "session behind" in managed.action.reason
    assert managed.action.new_stop is None, "a stale run must not move a real stop"


def test_the_same_position_on_current_bars_is_managed(wired, registry) -> None:
    """The positive control for the pause above."""
    bars, journal, positions = wired
    fresh = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    positions.record(_position())

    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: fresh}), positions=positions)

    managed = result.positions[0]
    assert not managed.stale
    assert managed.action.kind is not ActionKind.PAUSE


def test_a_stale_position_is_never_dropped_from_the_run(wired, registry) -> None:
    """A held position past the window pauses like any other stale one. `CHECKLIST_SPEC` §4 exists
    so a data failure can never lock the owner out of managing risk on something already open, so
    "dropped from the run" is a candidate-path outcome and must not reach a position."""
    bars, journal, positions = wired
    ancient = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 13))
    positions.record(_position())

    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: ancient}), positions=positions)

    assert len(result.positions) == 1, "the position is still in the run"
    assert result.positions[0].action is not None, "and still leaves with a proposal"
    assert result.positions[0].action.kind is ActionKind.PAUSE


def test_the_staleness_of_a_position_moves_the_output_hash(wired, registry, tmp_path) -> None:
    """`stale` is carried in `output_hash` (PR #9). Two runs the owner would act on differently
    must not hash alike - that is the standard `_output_hash` was widened to."""
    bars, journal, positions = wired
    positions.record(_position())
    fresh = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    stale = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))

    current = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                  fetcher=fixture_fetcher({TEST_US.id: fresh}), positions=positions)

    with (
        BarStore(tmp_path / "other-bars.duckdb") as other_bars,
        Journal(tmp_path / "other-journal.duckdb") as other_journal,
        PositionStore(tmp_path / "other-positions.duckdb") as other_positions,
    ):
        other_positions.record(_position())
        behind = run([TEST_US], FixedClock(AS_OF), registry, other_bars, other_journal,
                     mode=RunMode.LIVE_AS_OF, fetcher=fixture_fetcher({TEST_US.id: stale}),
                     positions=other_positions)

    assert current.manifest.output_hash != behind.manifest.output_hash
