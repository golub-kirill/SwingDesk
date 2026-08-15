"""US-022 - the refusal funnel aggregates a run's decisions, and can never disagree with them.

Builds `RunResult` directly rather than running the pipeline: `funnel()` is pure and reads only the
dataclass fields documented in `pipeline.py`, so a hand-built fixture exercises exactly the same
contract a real run produces, without a store, a journal, or a fetcher.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from tests.conftest import TEST_CA, TEST_US

from swingdesk.application.pipeline import InstrumentOutcome, RunResult
from swingdesk.application.universe import Membership, UniverseSelection
from swingdesk.contracts.run import RunManifest, RunMode
from swingdesk.journal_evidence.journal import DecisionRecord
from swingdesk.presentation.funnel import funnel
from swingdesk.reference_data.universe import LiquidityRule

NOW = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)

RULE = LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal("5000000"), adtv_window=20, min_history=20
)


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="run-test",
        started_at=NOW,
        mode=RunMode.LIVE_AS_OF,
        code_hash="abc123",
        config_hash="cfg123",
        snapshot_id="snap-test",
        calendar_version="test",
        platform="test",
    )


def _selection(*, eligible: int, measured: int, members: int) -> UniverseSelection:
    return UniverseSelection(
        as_of=NOW,
        rule=RULE,
        parameters=(),
        directory_pull=NOW,
        eligible=eligible,
        measured=measured,
        members=tuple(
            Membership(instrument=TEST_US, close=Decimal(100), adtv=Decimal(6000000), bars=30)
            for _ in range(members)
        ),
    )


def _outcome(instrument, decision: DecisionRecord | None) -> InstrumentOutcome:
    return InstrumentOutcome(instrument=instrument, decision=decision)


def _result(outcomes: list[InstrumentOutcome], universe: UniverseSelection | None = None) -> RunResult:
    return RunResult(manifest=_manifest(), outcomes=outcomes, universe=universe)


# --- totals reconcile -----------------------------------------------------------------------


def test_the_five_buckets_sum_to_evaluated() -> None:
    """US-022: `is_reconciled` holds when every outcome landed in exactly one bucket."""
    outcomes = [
        _outcome(TEST_US, DecisionRecord(TEST_US.id, "Watch")),
        _outcome(TEST_CA, DecisionRecord(TEST_CA.id, "Skip", "DATA", "no bars")),
    ]
    stats = funnel(_result(outcomes))
    assert stats.evaluated == 2
    assert stats.watch == 1
    assert stats.skip == 1
    assert stats.unaccounted == 0
    assert stats.is_reconciled


def test_a_candidate_with_no_decision_is_unaccounted_not_dropped() -> None:
    """US-022: a decisionless outcome is counted, never silently absent from the total.

    US-006 says no instrument may leave a run without a candidate record or a coded Skip - this is
    the funnel's own check for that invariant, reported rather than asserted (HANDOFF.md 8).
    """
    outcomes = [_outcome(TEST_US, DecisionRecord(TEST_US.id, "Watch")), _outcome(TEST_CA, None)]
    stats = funnel(_result(outcomes))
    assert stats.unaccounted == 1
    assert stats.is_reconciled  # unaccounted is itself one of the five buckets


def test_admitted_and_evaluated_track_the_universe_when_one_is_attached() -> None:
    selection = _selection(eligible=100, measured=60, members=2)
    outcomes = [
        _outcome(TEST_US, DecisionRecord(TEST_US.id, "Watch")),
        _outcome(TEST_CA, DecisionRecord(TEST_CA.id, "Watch")),
    ]
    stats = funnel(_result(outcomes, selection))
    assert stats.eligible == 100
    assert stats.measured == 60
    assert stats.admitted == 2
    assert stats.evaluated == 2


def test_no_universe_reports_zero_rule_stages_not_a_universe_that_admitted_nobody() -> None:
    """`eligible`/`measured`/`admitted` are 0 when there is no rule stage to report at all -
    an explicit instrument list carries no universe, and that is a different fact from a universe
    that ran and admitted zero members."""
    outcomes = [_outcome(TEST_US, DecisionRecord(TEST_US.id, "Watch"))]
    stats = funnel(_result(outcomes, universe=None))
    assert stats.eligible == 0
    assert stats.measured == 0
    assert stats.admitted == 1  # falls back to what was actually evaluated


# --- skip codes broken out, and the two RISK causes kept separate ---------------------------


def test_skip_codes_are_broken_out_by_code_and_parameter() -> None:
    """US-022: an unset-parameter refusal and a zero-shares refusal are different SkipCauses.

    `size_long` already distinguishes them - `parameter_id` set means a required parameter has no
    value (a system fault); `parameter_id` None on a RISK code means the account cannot carry the
    position (a fact about the account). Folding both into one `RISK` count is exactly how 1131
    unset-parameter refusals on 2026-08-09 read as an ordinary quiet market.
    """
    outcomes = [
        _outcome(
            TEST_US,
            DecisionRecord(TEST_US.id, "Skip", "RISK", "unset", parameter_id="risk.per_trade_pct"),
        ),
        _outcome(
            TEST_CA,
            DecisionRecord(TEST_CA.id, "Skip", "RISK", "buys 0 shares", parameter_id=None),
        ),
    ]
    stats = funnel(_result(outcomes))
    assert stats.skip == 2
    causes = {(c.code, c.parameter_id): c.count for c in stats.skip_causes}
    assert causes[("RISK", "risk.per_trade_pct")] == 1
    assert causes[("RISK", None)] == 1


def test_skip_causes_are_sorted_most_common_first() -> None:
    outcomes = [
        _outcome(TEST_US, DecisionRecord(TEST_US.id, "Skip", "DATA", "stale")),
        _outcome(TEST_CA, DecisionRecord(TEST_CA.id, "Skip", "LIQ", "thin")),
    ]
    # Two DATA skips, one LIQ skip - reuse TEST_US id twice by constructing a third outcome.
    outcomes.append(_outcome(TEST_US, DecisionRecord(TEST_US.id, "Skip", "DATA", "stale")))
    stats = funnel(_result(outcomes))
    assert stats.skip_causes[0].code == "DATA"
    assert stats.skip_causes[0].count == 2


# --- changed since last run, first sighting counted separately ------------------------------


def test_first_sighting_is_not_counted_as_changed() -> None:
    """US-022: `previous_decision is None` means the journal held no prior state - a first
    sighting - and is NOT the same claim as "unchanged" (`journal.py` `DecisionRecord` docstring).
    """
    outcomes = [
        _outcome(
            TEST_US,
            DecisionRecord(TEST_US.id, "Watch", previous_decision=None),
        ),
    ]
    stats = funnel(_result(outcomes))
    assert stats.first_sighting == 1
    assert stats.changed == 0


def test_a_decision_that_differs_from_yesterday_is_changed() -> None:
    outcomes = [
        _outcome(
            TEST_US,
            DecisionRecord(TEST_US.id, "Skip", "DATA", "stale", previous_decision="Watch"),
        ),
        _outcome(
            TEST_CA,
            DecisionRecord(TEST_CA.id, "Watch", previous_decision="Watch"),
        ),
    ]
    stats = funnel(_result(outcomes))
    assert stats.changed == 1
    assert stats.first_sighting == 0


# --- empty result -----------------------------------------------------------------------------


def test_an_empty_candidate_set_is_a_valid_funnel_not_an_error() -> None:
    """A day whose only work was managing open positions produces zero outcomes - ordinary, per
    `journal.record_decisions`'s own docstring, and the funnel must say so rather than raise."""
    stats = funnel(_result([]))
    assert stats.evaluated == 0
    assert stats.is_reconciled
    assert stats.skip_causes == ()
