"""The display obligation: an `active` component shows its validation status where its output appears.

`COMPONENT_REGISTRY_SPEC.md` §3 permits `Untested` for an `active` component and forbids *hiding*
it — that is how full-catalogue coverage (owner decision D2) stays honest while nothing is proven.

Untested until 2026-08-10, when ATR (`M18-T0280-v5.0`) became the first `active` component and the
obligation stopped being hypothetical. The live run does print it — `data/daily_run.log` carries a
`validation` line per instrument — but nothing asserted it, so a refactor of the report could have
dropped the line and left every gate green.

Offline, like the rest of the suite: sessions come from the authoritative calendar and bars from a
fixture fetcher.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from tests.conftest import TEST_US, fixture_fetcher

from swingdesk.application.pipeline import run
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock
from swingdesk.presentation import report
from swingdesk.reference_data import calendar as cal

MODE = RunMode.LIVE_AS_OF
AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


@pytest.fixture
def rendered(tmp_path, registry) -> str:
    sessions = [
        s.session_date
        for s in cal.sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    ]
    fetcher = fixture_fetcher({TEST_US.id: sessions})
    with BarStore(tmp_path / "bars.duckdb") as store, Journal(tmp_path / "journal.duckdb") as journal:
        result = run([TEST_US], FixedClock(AS_OF), registry, store, journal,
                     mode=MODE, fetcher=fetcher)
        observations = result.outcomes[0].observations
        assert observations is not None, "the fixture must produce an observation to display"
        return "\n".join([report.render(result), "", f"__status__ {observations.validation_status}",
                          f"__component__ {observations.component}",
                          f"__version__ v{observations.component_version}"])


def test_the_validation_status_appears_in_the_report(rendered: str) -> None:
    body, _, markers = rendered.partition("__status__ ")
    status = markers.splitlines()[0]
    assert "validation" in body
    assert status in body, f"validation status {status!r} is computed but not displayed"


def test_the_component_and_version_travel_with_the_value(rendered: str) -> None:
    """Provenance travels with the number (`CHARTER.md` §4): an untraceable value is not permitted."""
    body = rendered.split("__status__ ")[0]
    component = rendered.split("__component__ ")[1].splitlines()[0]
    version = rendered.split("__version__ ")[1].splitlines()[0]
    assert component in body
    assert version in body


def test_an_assumed_parameter_is_flagged_as_not_evidence(rendered: str) -> None:
    """ATR's period is `assumed`. Nothing may look more validated than it is (`AGENTS.md` §3)."""
    body = rendered.split("__status__ ")[0]
    assert "ASSUMED, not evidence" in body


# --------------------------------------------------------------- US-022: the funnel block


def test_funnel_counts_appear_in_the_documented_order(rendered: str) -> None:
    """US-022: eligible, measured, admitted and evaluated, in that order."""
    body = rendered.split("__status__ ")[0]
    assert "FUNNEL" in body
    order = [body.find(f"  {label}") for label in
             ("eligible", "measured", "admitted", "evaluated")]
    assert order == sorted(order), "the four counts must appear in the documented order"


def test_a_run_with_no_candidates_still_prints_a_funnel_block() -> None:
    """US-022: zero is stated, not silence - a quiet day and a broken one must not read the same."""
    from swingdesk.application.pipeline import RunResult
    from swingdesk.contracts.run import RunManifest, RunMode

    manifest = RunManifest(
        run_id="r", started_at=AS_OF, mode=RunMode.LIVE, code_hash="a", config_hash="b",
        snapshot_id="s", calendar_version="c", platform="p",
    )
    out = report.render(RunResult(manifest=manifest, outcomes=[]))
    assert "FUNNEL" in out
    assert "evaluated        0" in out


def test_a_skip_naming_a_parameter_is_broken_out_from_one_that_does_not() -> None:
    """US-022: an unset-parameter Skip (a SYSTEM fault) is shown separately from the same code
    without a parameter (a fact about the account or the market) - the exact distinction
    `presentation.funnel.SkipCause` exists to preserve."""
    from tests.conftest import TEST_CA, TEST_US

    from swingdesk.application.pipeline import InstrumentOutcome, RunResult
    from swingdesk.contracts.run import RunManifest, RunMode
    from swingdesk.journal_evidence.journal import DecisionRecord

    manifest = RunManifest(
        run_id="r", started_at=AS_OF, mode=RunMode.LIVE, code_hash="a", config_hash="b",
        snapshot_id="s", calendar_version="c", platform="p",
    )
    outcomes = [
        InstrumentOutcome(
            instrument=TEST_US,
            decision=DecisionRecord(TEST_US.id, "Skip", "RISK", "no value",
                                    parameter_id="risk.per_trade_pct"),
        ),
        InstrumentOutcome(
            instrument=TEST_CA,
            decision=DecisionRecord(TEST_CA.id, "Skip", "RISK", "0 shares"),
        ),
    ]
    out = report.render(RunResult(manifest=manifest, outcomes=outcomes))
    assert "RISK [risk.per_trade_pct]" in out
    assert "RISK                             1" in out, "the unparameterised RISK skip is its own line"


def test_reconciliation_failure_is_reported_not_hidden() -> None:
    """`Funnel.is_reconciled` is checked by the render, not asserted in the pure module - a broken
    invariant must be visible to whoever reads the report, not raised mid-run over work already done.
    """
    from unittest.mock import patch

    from tests.conftest import TEST_US

    from swingdesk.application.pipeline import InstrumentOutcome, RunResult
    from swingdesk.contracts.run import RunManifest, RunMode
    from swingdesk.journal_evidence.journal import DecisionRecord
    from swingdesk.presentation import funnel as funnel_module

    manifest = RunManifest(
        run_id="r", started_at=AS_OF, mode=RunMode.LIVE, code_hash="a", config_hash="b",
        snapshot_id="s", calendar_version="c", platform="p",
    )
    outcomes = [InstrumentOutcome(instrument=TEST_US, decision=DecisionRecord(TEST_US.id, "Watch"))]
    result = RunResult(manifest=manifest, outcomes=outcomes)

    real = funnel_module.funnel(result)
    broken = funnel_module.Funnel(
        eligible=real.eligible, measured=real.measured, admitted=real.admitted,
        evaluated=real.evaluated, trade=0, watch=0, skip=0, pause=0,  # buckets don't sum
        unaccounted=0, skip_causes=(), changed=real.changed, first_sighting=real.first_sighting,
    )
    assert not broken.is_reconciled
    with patch("swingdesk.presentation.report.funnel", return_value=broken):
        out = report.render(result)
    assert "RECONCILIATION FAILED" in out
