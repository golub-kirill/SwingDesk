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
