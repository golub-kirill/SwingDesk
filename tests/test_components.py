"""Component metadata must agree with the registry it was transcribed from.

`component`, `validation` and the rest are generated from the course and must not be hand-edited
(COMPONENT_REGISTRY_SPEC 2). The pure packages cannot read the registry - they have no I/O - so each
module mirrors its row as constants, and this is what stops the mirror drifting.

It has already caught one: ATR emitted `Untested` while its registry row said `Not Applicable`.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
import yaml

from swingdesk.contracts.observation import VALIDATION_STATUSES, ParameterUse
from swingdesk.derived_observations import atr, moving_average
from swingdesk.validation.golden import GOLDEN_ROOT  # noqa: F401  (path anchor for the repo root)

MODULES = (atr, moving_average)


@pytest.fixture(scope="module")
def course_rows() -> dict[str, dict]:
    path = GOLDEN_ROOT.parents[1] / "registry" / "course_index.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = data["topics"] if isinstance(data, dict) and "topics" in data else data
    return {row["component"]: row for row in rows}


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_component_id_is_in_the_course(module, course_rows) -> None:
    assert module.COMPONENT in course_rows, (
        f"{module.__name__} claims component {module.COMPONENT}, which is not in the course index"
    )


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_validation_status_matches_the_registry(module, course_rows) -> None:
    """A component may not report a status its own registry row does not give it.

    Advancing above the course's status is the job of evidence (VALIDATION_PROGRAM 1), and evidence
    is recorded, not asserted in a module constant.
    """
    row = course_rows[module.COMPONENT]
    assert module.VALIDATION == row["validation"], (
        f"{module.__name__} declares {module.VALIDATION!r}, registry says {row['validation']!r}"
    )
    assert module.VALIDATION in VALIDATION_STATUSES


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_layer_is_derived_observations(module, course_rows) -> None:
    """Everything in this package must be a Derived Observations component.

    A Decision Logic topic implemented here would put a decision inside the pure calculation layer -
    the thing DEPENDENCY_LAW exists to prevent, and import analysis cannot see it.
    """
    assert course_rows[module.COMPONENT]["layer"] == "Derived Observations"


def test_series_rejects_a_status_outside_the_enum(registry) -> None:
    """The nine are the course's. A tenth needs a dated amendment, not a string literal."""
    from swingdesk.contracts.observation import ObservationSeries

    with pytest.raises(ValueError, match="not one of the nine"):
        ObservationSeries(
            component="M25-T0382-v5.0",
            component_version=1,
            instrument_id="TEST.1",
            units="price units",
            parameters=(),
            validation_status="Historically Tested (survivorship-limited)",
            knowledge_time=__import__("datetime").datetime(
                2026, 1, 15, tzinfo=__import__("datetime").timezone.utc
            ),
            observations=(),
        )


# ------------------------------------------------- SMA

def _period(value: int) -> ParameterUse:
    return ParameterUse(id="test.period", value=str(value), provenance="golden vector")


def test_sma_rolling_sum_equals_a_fresh_window_sum(registry) -> None:
    """The incremental sum must equal the direct one, exactly.

    SMA keeps a running total rather than re-summing each window, which is the difference between a
    fast study and an unusable one. With Decimal the two are exact at these magnitudes - this is the
    test that says so rather than assuming it.
    """
    from tests.conftest import TEST_US, series_for

    sessions = [date(2025, 1, 6) + timedelta(days=offset) for offset in range(40)]
    series = series_for(TEST_US, sessions)
    produced = moving_average.compute(series, 10, _period(10))

    for index, observation in enumerate(produced.observations):
        if index < 9:
            assert observation.value is None
            continue
        window = [bar.close for bar in series.bars[index - 9: index + 1]]
        assert observation.value == sum(window, Decimal(0)) / 10


def test_sma_declines_before_warm_up(registry) -> None:
    from tests.conftest import TEST_US, series_for

    series = series_for(TEST_US, [date(2025, 1, 6) + timedelta(days=offset) for offset in range(5)])
    produced = moving_average.compute(series, 5, _period(5))
    assert [o.value is None for o in produced.observations] == [True, True, True, True, False]
    assert moving_average.warm_up_bars(5) == 5


def test_sma_rejects_a_nonsense_period(registry) -> None:
    from tests.conftest import TEST_US, series_for

    series = series_for(TEST_US, [date(2025, 1, 6) + timedelta(days=offset) for offset in range(5)])
    with pytest.raises(ValueError, match="period must be >= 1"):
        moving_average.compute(series, 0, _period(0))
