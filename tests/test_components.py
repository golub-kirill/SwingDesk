"""Component metadata must agree with the registry it was transcribed from.

`component`, `layer` and `validation` are generated from the course and must not be hand-edited
(COMPONENT_REGISTRY_SPEC 2). The pure packages cannot read the registry - they have no I/O - so each
module mirrors the row it implements, and this is what stops the mirror drifting.

It has already caught one: ATR emitted `Untested` while its registry row said `Not Applicable`.
"""

from __future__ import annotations

from datetime import UTC, date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from swingdesk.contracts.observation import VALIDATION_STATUSES, ObservationSeries, ParameterUse
from swingdesk.decision_logic import trend
from swingdesk.derived_observations import (
    atr,
    breadth,
    moving_average,
    pivots,
    regime,
    relative_strength,
)

REPO = Path(__file__).resolve().parents[1]

#: (spec, owning module name). Every component this system implements appears exactly once - two
#: entries for one component id would be the "one canonical definition" violation that import
#: analysis cannot see (DEPENDENCY_LAW 4).
SPECS = [
    *[(spec, "derived_observations.atr") for spec in atr.SPECS],
    *[(spec, "derived_observations.moving_average") for spec in moving_average.SPECS],
    *[(spec, "derived_observations.pivots") for spec in pivots.SPECS],
    *[(spec, "derived_observations.breadth") for spec in breadth.SPECS],
    *[(spec, "derived_observations.regime") for spec in regime.SPECS],
    *[(spec, "derived_observations.relative_strength")
      for spec in relative_strength.SPECS],
    (trend.TREND_FILTER, "decision_logic.trend"),
]


def test_every_declared_spec_has_a_registry_row() -> None:
    """The list above is hand-maintained, and a hand-maintained list is what drifted.

    `registry/components.yml` is the authority; this asserts the two agree in both directions, so
    adding a component without registering it fails here rather than being noticed by counting
    months later.
    """
    data = yaml.safe_load((REPO / "registry" / "components.yml").read_text(encoding="utf-8"))
    registered = {
        row["component"] for row in data["components"] if row.get("implements")
    }
    declared = {spec.component for spec, _ in SPECS}
    assert declared == registered, (
        f"declared but unregistered: {sorted(declared - registered)}; "
        f"registered but undeclared: {sorted(registered - declared)}"
    )


@pytest.fixture(scope="module")
def course_rows() -> dict[str, dict]:
    data = yaml.safe_load((REPO / "registry" / "course_index.yml").read_text(encoding="utf-8"))
    rows = data["topics"] if isinstance(data, dict) and "topics" in data else data
    return {row["component"]: row for row in rows}


def _ids(pair) -> str:
    return f"{pair[0].component}"


def test_no_component_has_two_implementations() -> None:
    """"Each component has one canonical definition" - Production Rules 3.8."""
    seen = [spec.component for spec, _ in SPECS]
    assert len(seen) == len(set(seen)), f"duplicate component ids: {seen}"


@pytest.mark.parametrize("pair", SPECS, ids=_ids)
def test_component_id_is_in_the_course(pair, course_rows) -> None:
    spec, owner = pair
    assert spec.component in course_rows, f"{owner} claims {spec.component}, absent from the index"


@pytest.mark.parametrize("pair", SPECS, ids=_ids)
def test_validation_status_matches_the_registry(pair, course_rows) -> None:
    """A component may not report a status its own registry row does not give it.

    Advancing above the course's status is the job of evidence (VALIDATION_PROGRAM 1), and evidence
    is recorded, not asserted in a module constant.
    """
    spec, owner = pair
    row = course_rows[spec.component]
    assert spec.validation == row["validation"], (
        f"{owner} declares {spec.validation!r}, registry says {row['validation']!r}"
    )
    assert spec.validation in VALIDATION_STATUSES


@pytest.mark.parametrize("pair", SPECS, ids=_ids)
def test_layer_matches_the_registry(pair, course_rows) -> None:
    """A Decision Logic topic implemented in the pure observation package would put a decision
    inside the calculation layer - the thing DEPENDENCY_LAW exists to prevent, and one that import
    analysis cannot see because both are legal imports."""
    spec, owner = pair
    assert spec.layer == course_rows[spec.component]["layer"], owner


def test_series_rejects_a_status_outside_the_enum() -> None:
    """The nine are the course's. A tenth needs a dated amendment, not a string literal."""
    from datetime import datetime

    with pytest.raises(ValueError, match="not one of the nine"):
        ObservationSeries(
            component="M25-T0382-v5.0", component_version=1, instrument_id="TEST.1",
            units="price units", parameters=(),
            validation_status="Historically Tested (survivorship-limited)",
            knowledge_time=datetime(2026, 1, 15, tzinfo=UTC), observations=(),
        )


# ------------------------------------------------------------------- SMA

def _param(name: str, value: int) -> ParameterUse:
    return ParameterUse(id=name, value=str(value), provenance="test fixture")


def _sessions(count: int, start: date = date(2025, 1, 6)) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(count)]


def test_sma_rolling_sum_equals_a_fresh_window_sum() -> None:
    """The incremental sum must equal the direct one, exactly.

    SMA keeps a running total rather than re-summing each window, which is the difference between a
    fast study and an unusable one. With Decimal the two are exact at these magnitudes - this test
    says so rather than assuming it.
    """
    from tests.conftest import TEST_US, series_for

    series = series_for(TEST_US, _sessions(40))
    produced = moving_average.compute(series, 10, _param("sma.period", 10))

    for index, observation in enumerate(produced.observations):
        if index < 9:
            assert observation.value is None
            continue
        window = [bar.close for bar in series.bars[index - 9: index + 1]]
        assert observation.value == sum(window, Decimal(0)) / 10


def test_sma_declines_before_warm_up() -> None:
    from tests.conftest import TEST_US, series_for

    produced = moving_average.compute(series_for(TEST_US, _sessions(5)), 5, _param("sma.period", 5))
    assert [o.value is None for o in produced.observations] == [True, True, True, True, False]
    assert moving_average.warm_up_bars(5) == 5


def test_sma_rejects_a_nonsense_period() -> None:
    from tests.conftest import TEST_US, series_for

    with pytest.raises(ValueError, match="period must be >= 1"):
        moving_average.compute(series_for(TEST_US, _sessions(5)), 0, _param("sma.period", 0))
