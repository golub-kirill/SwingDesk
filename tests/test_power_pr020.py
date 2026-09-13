"""The power estimate that chose `PR-020`'s hold: the one no-stop hold the 0.15R floor can read.

* **it sizes `PR-019`'s own no-stop cells, and five sessions built the same way** - no protective
  stop, the same R denominator - or it sizes studies nobody would run.
* **each hold is overlap-aware at ITS OWN lags**: a 60-session hold spans three entry months, a
  10-session hold one. `PR-019b` paid 1.7x for assuming independent months.
* **no level leaks**: the hold is chosen by precision alone, and that is only safe while nothing
  here can say which way `trade - pool` points.
"""

from __future__ import annotations

import importlib.util
import math
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def power():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_power_pr020", REPO / "tools" / "power_pr020.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_cells_are_pr019s_own_no_stop_cells_and_five_sessions_built_the_same_way(power):
    from power_pr019 import GRID, R_DENOMINATOR_MULTIPLE, cells

    grid = tuple(name for name in GRID if name.endswith("stopnone"))
    assert power.CELLS == ("h5_stopnone", *grid)
    for name in grid:
        assert power.policy_for(name) is cells()[name] or power.policy_for(name) == cells()[name]
    for name in power.CELLS:
        policy = power.policy_for(name)
        assert policy.target_r_multiple is None
        assert name == f"h{policy.max_holding_bars}_stopnone"
    five = power.policy_for("h5_stopnone")
    assert five.max_holding_bars == 5
    assert (five.atr_stop_multiple, five.protective) == (R_DENOMINATOR_MULTIPLE, False), (
        "the same R denominator and no protective stop, or it is priced in different units")


def _months(n: int = 60, per: int = 6, width: int = 3, seed: int = 3) -> dict[str, list[float]]:
    """Months whose values share `width` consecutive shocks - an index leg held `width` months."""
    rng = random.Random(seed)
    shocks = [rng.gauss(0, 1) for _ in range(n + width)]
    return {f"{2016 + m // 12}-{1 + m % 12:02d}":
            [sum(shocks[m:m + width]) + rng.gauss(0, 0.5) for _ in range(per)]
            for m in range(n)}


def test_each_hold_is_corrected_at_its_own_lags(power):
    assert power.dispersion(_months(), 60)["overlap_lags"] == 2.0
    assert power.dispersion(_months(), 40)["overlap_lags"] == 1.0
    assert power.dispersion(_months(), 10)["overlap_lags"] == 0.0


def test_zero_lags_leave_the_independent_estimate_alone(power):
    got = power.dispersion(_months(), 10)
    assert got["overlap_factor"] == 1.0
    assert got["half_width_overlap"] == pytest.approx(got["half_width_corrected"])


def test_overlapping_months_widen_the_half_width_by_the_root_of_the_factor(power):
    got = power.dispersion(_months(), 60)
    assert got["overlap_factor"] > 1.5
    assert math.isclose(got["half_width_overlap"] / got["half_width_corrected"],
                        math.sqrt(got["overlap_factor"]), rel_tol=1e-9)


def test_every_dispersion_carries_the_fields_a_registration_reads(power):
    got = power.dispersion(_months(), 20)
    for key in ("half_width_corrected", "half_width_predicted_oos", "overlap_lags",
                "overlap_factor", "half_width_overlap", "half_width_predicted_oos_overlap"):
        assert key in got, key


def test_the_payload_guard_refuses_a_level(power):
    from power_pr019 import assert_no_effect_leaked

    with pytest.raises(AssertionError):
        assert_no_effect_leaked({"cells": {"h10_stopnone": {"dispersion": {"mean": 0.1}}}})


def test_the_committed_estimate_carries_no_level(power):
    """Written before any registration decision; a level in it would mean the hold was chosen by
    someone who had seen the answer."""
    import json

    from power_pr019 import assert_no_effect_leaked

    path = REPO / "docs" / "prereg" / "results" / "PR-020-power.json"
    assert_no_effect_leaked(json.loads(path.read_text(encoding="utf-8")))
