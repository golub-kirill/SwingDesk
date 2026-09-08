"""Which leg printed first, on synthetic minutes where the answer is arithmetic.

`first_touch` is the whole measurement. `DR-042` §4's tie-break is settled on the share it returns,
so an error here does not produce a wrong number — it produces a wrong RULING, on every backtest
this project runs afterwards. Three ways it could be wrong and none raises:

* **order.** Scanning the minutes in the wrong order, or checking the target before the stop within
  a minute, inverts the answer while every count stays plausible.
* **the residue.** A minute that reaches both legs is the same ambiguity one level down. Assigning
  it — to either side — turns a smaller assumption into a reported measurement.
* **the boundary.** `<=` on the stop and `>=` on the target, because a resting order fills when the
  print reaches it.

No network.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

STOP = Decimal("90")
TARGET = Decimal("110")


@pytest.fixture(scope="module")
def probe():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "_ambiguous", REPO / "tools" / "probe_ambiguous_bar.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def minute(low: str, high: str) -> dict[str, float]:
    return {"l": float(low), "h": float(high)}


# --- order ---------------------------------------------------------------------------------------

def test_the_earlier_minute_wins_even_though_the_later_one_reaches_the_other_leg(probe) -> None:
    """The whole point. Both legs are reached during the session; only the sequence separates them,
    and on a daily bar that sequence is invisible."""
    bars = [minute("95", "105"), minute("89", "105"), minute("95", "111")]
    assert probe.first_touch(bars, STOP, TARGET) == "stop"


def test_the_same_session_the_other_way_round_answers_the_other_way(probe) -> None:
    """The mutation this pair exists for: scanning in reverse, or returning the last touch. Both
    fixtures would still return a legitimate-looking answer."""
    bars = [minute("95", "105"), minute("95", "111"), minute("89", "105")]
    assert probe.first_touch(bars, STOP, TARGET) == "target"


def test_a_touch_in_the_very_first_minute_is_taken(probe) -> None:
    assert probe.first_touch([minute("85", "105"), minute("95", "111")], STOP, TARGET) == "stop"


# --- the residue ---------------------------------------------------------------------------------

def test_one_minute_reaching_both_legs_is_reported_and_never_assigned(probe) -> None:
    """A minute bar records four prices and no times, exactly like a daily one. Assigning this to
    the stop would be `DR-042` §4's assumption again, one level down and wearing a measurement's
    clothes."""
    assert probe.first_touch([minute("89", "111")], STOP, TARGET) == "within_a_minute"


def test_the_residue_is_decided_by_the_FIRST_minute_that_reaches_either_leg(probe) -> None:
    """A later both-legs minute cannot matter: the position was already closed."""
    bars = [minute("89", "105"), minute("89", "111")]
    assert probe.first_touch(bars, STOP, TARGET) == "stop"


# --- the boundary --------------------------------------------------------------------------------

def test_a_print_exactly_at_the_stop_is_a_touch(probe) -> None:
    assert probe.first_touch([minute("90", "105")], STOP, TARGET) == "stop"


def test_a_print_exactly_at_the_target_is_a_touch(probe) -> None:
    assert probe.first_touch([minute("95", "110")], STOP, TARGET) == "target"


def test_a_session_reaching_neither_leg_says_so_rather_than_guessing(probe) -> None:
    """This is a DEFECT signal, not a result: the daily bar said both legs were reachable. It is
    counted separately so a disagreement between the two feeds cannot be read as evidence."""
    assert probe.first_touch([minute("95", "105")], STOP, TARGET) == "neither"


def test_no_minutes_at_all_is_not_a_touch(probe) -> None:
    assert probe.first_touch([], STOP, TARGET) == "neither"


# --- the interval --------------------------------------------------------------------------------

def test_the_interval_stays_inside_zero_and_one_at_the_extremes(probe) -> None:
    """Why Wilson and not the normal approximation: at 200 of 200 the normal interval is
    [1.0, 1.0], which reads as certainty and is the most reassuring possible wrong answer."""
    low, high = probe.interval(200, 200)
    assert 0.0 <= low < 1.0
    assert high == pytest.approx(1.0, abs=1e-9)
    low, high = probe.interval(0, 200)
    assert low == pytest.approx(0.0, abs=1e-9)
    assert 0.0 < high <= 1.0


def test_the_interval_brackets_the_observed_share(probe) -> None:
    low, high = probe.interval(60, 100)
    assert low < 0.6 < high


def test_a_larger_sample_gives_a_narrower_interval(probe) -> None:
    small = probe.interval(30, 50)
    large = probe.interval(300, 500)
    assert (large[1] - large[0]) < (small[1] - small[0])


def test_no_trials_yields_no_interval_rather_than_a_division_by_zero(probe) -> None:
    assert probe.interval(0, 0) == (0.0, 0.0)


# --- what the probe promises about itself --------------------------------------------------------

def test_the_material_threshold_matches_the_one_registered_in_dr_042(probe) -> None:
    """Registered in `DR-042` §4a before the number existed, so it cannot be adjusted to suit the
    answer. A test is what stops the constant drifting to meet a result."""
    assert probe.MATERIAL_SHARE == 0.15


def test_the_sample_is_seeded_so_it_is_a_sample_and_not_a_choice(probe) -> None:
    assert probe.SEED == 20260908
