"""`PR-019`'s decision logic, which is the whole of what makes a twelve-cell grid a test and not a search.

Three things carry it, and every one of them fails silently:

* **the selection sees only the in-sample window.** `select_cell` takes no out-of-sample argument, so
  the property is structural; these tests pin the RULE it applies - the tail ceiling is the
  incumbent's, and the pick is the highest mean among cells under it.
* **the verdict reads only the selected cell, out of sample**, with seven outcomes registered before
  the run. `both_negative` and `null` exist because earlier studies paid for their absence;
  `tail_breach` is the contract's C-8 made mechanical.
* **the tail tolerance is sampling noise, not a number somebody chose.** Wilson's upper bound on the
  incumbent's own share is the only slack the verdict allows.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def study():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_run_pr019", REPO / "tools" / "run_pr019.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _cell(mean: float, tail: float, *, trades: int = 5000, months: int = 60,
          diff: tuple[float, float] | None = None, own: tuple[float, float] | None = None,
          below: int | None = None) -> dict[str, Any]:
    cell: dict[str, Any] = {
        "trades": trades, "months": months, "mean_net_r": mean,
        "mae": {"share_below_-2R": tail, "trades": trades,
                "below_counts": {"-2": below if below is not None else round(tail * trades)}},
    }
    if diff is not None:
        cell["difference_mean"] = {"observed": sum(diff) / 2, "low": diff[0], "high": diff[1]}
    if own is not None:
        cell["mean_interval"] = {"low": own[0], "high": own[1]}
    return cell


def _grid(study, **overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every cell a loser with a fat tail unless the test says otherwise."""
    grid = {name: _cell(-0.5, 0.50) for name in study.GRID}
    grid.update(overrides)
    return grid


# --- the grid ------------------------------------------------------------------------------------


def test_twelve_cells_and_the_incumbent_is_not_one_of_them(study):
    assert len(study.GRID) == 12
    assert study.INCUMBENT not in study.GRID


def test_the_trial_count_is_the_grid(study):
    """A trial is a configuration evaluated (`TRIAL_BUDGET.md`). The incumbent reproduces a published
    arm on a new entry schedule; the pre-registration says why it is not counted and that a reader
    who counts it gets thirteen."""
    assert len(study.GRID) == 12


def test_the_incumbent_is_the_ratified_exit(study):
    policy = study.incumbent_policy()
    assert policy.atr_stop_multiple == study.STOP_MULTIPLE
    assert policy.target_r_multiple == study.TARGET_R
    assert policy.max_holding_bars == study.HOLD


# --- selection, in sample ------------------------------------------------------------------------


def test_the_highest_mean_under_the_incumbents_tail_is_chosen(study):
    grid = _grid(study, **{"h40_stop4.0": _cell(0.05, 0.01), "h60_stop4.0": _cell(0.03, 0.01)})
    assert study.select_cell(grid, _cell(-0.08, 0.023)) == "h40_stop4.0"


def test_a_higher_mean_with_a_fatter_tail_is_NOT_chosen(study):
    """The contract's C-8: `PR-018`'s hold_only earned more and ran 21.7% below -2R."""
    grid = _grid(study, **{"h60_stopnone": _cell(0.20, 0.217), "h20_stop2.0": _cell(-0.02, 0.02)})
    assert study.select_cell(grid, _cell(-0.08, 0.023)) == "h20_stop2.0"


def test_a_tail_EQUAL_to_the_incumbents_is_eligible(study):
    grid = _grid(study, **{"h20_stop2.0": _cell(0.01, 0.023)})
    assert study.select_cell(grid, _cell(-0.08, 0.023)) == "h20_stop2.0"


def test_a_cell_short_of_the_sample_rule_is_not_eligible(study):
    grid = _grid(study, **{"h40_stop4.0": _cell(0.30, 0.0, trades=study.MIN_TRADES - 1),
                           "h20_stop2.0": _cell(0.01, 0.01)})
    assert study.select_cell(grid, _cell(-0.08, 0.023)) == "h20_stop2.0"


def test_too_few_months_is_not_eligible_either(study):
    grid = _grid(study, **{"h40_stop4.0": _cell(0.30, 0.0, months=study.MIN_MONTHS - 1),
                           "h20_stop2.0": _cell(0.01, 0.01)})
    assert study.select_cell(grid, _cell(-0.08, 0.023)) == "h20_stop2.0"


def test_no_eligible_cell_selects_nothing(study):
    assert study.select_cell(_grid(study), _cell(-0.08, 0.023)) is None


def test_a_tie_breaks_to_the_shorter_hold(study):
    grid = _grid(study, **{"h60_stop2.0": _cell(0.02, 0.01), "h10_stop2.0": _cell(0.02, 0.01)})
    assert study.select_cell(grid, _cell(-0.08, 0.023)) == "h10_stop2.0"


def test_selection_can_pick_a_losing_cell(study):
    """It picks the BEST eligible, not a good one - the verdict decides whether best is enough."""
    grid = _grid(study, **{"h20_stop2.0": _cell(-0.03, 0.01)})
    assert study.select_cell(grid, _cell(-0.08, 0.023)) == "h20_stop2.0"


# --- the verdict, out of sample ------------------------------------------------------------------

BASE = {"mean_net_r": -0.11, "tail": 0.023}


def _oos(study, selected: str, cell: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {selected: cell, study.INCUMBENT: _cell(BASE["mean_net_r"], BASE["tail"])}


def test_nothing_selected_is_its_own_outcome(study):
    assert study.verdict_for(None, {}) == "no_eligible_cell"


def test_accept_needs_a_positive_level_a_positive_difference_and_the_tail(study):
    cell = _cell(0.05, 0.02, diff=(0.10, 0.20), own=(0.01, 0.09))
    assert study.verdict_for("h40_stop4.0", _oos(study, "h40_stop4.0", cell)) == "accept"


def test_beating_the_incumbent_while_losing_money_is_not_accept(study):
    """`PR-016`'s shape: a winning difference between two losers."""
    cell = _cell(-0.01, 0.02, diff=(0.05, 0.15), own=(-0.05, 0.03))
    assert study.verdict_for("h40_stop4.0", _oos(study, "h40_stop4.0", cell)) != "accept"


def test_earning_with_a_fatter_tail_out_of_sample_is_a_tail_breach(study):
    cell = _cell(0.05, 0.10, diff=(0.10, 0.20), own=(0.01, 0.09))
    assert study.verdict_for("h40_stop4.0", _oos(study, "h40_stop4.0", cell)) == "tail_breach"


def test_a_tail_within_wilson_noise_of_the_incumbents_still_holds(study):
    """2.3% on 5,000 trades has a Wilson upper bound near 2.75%; 2.6% is inside it."""
    cell = _cell(0.05, 0.026, diff=(0.10, 0.20), own=(0.01, 0.09))
    assert study.verdict_for("h40_stop4.0", _oos(study, "h40_stop4.0", cell)) == "accept"


def test_a_difference_wholly_below_zero_is_reject(study):
    cell = _cell(-0.20, 0.02, diff=(-0.14, -0.04), own=(-0.25, -0.15))
    assert study.verdict_for("h20_stop2.0", _oos(study, "h20_stop2.0", cell)) == "reject"


def test_a_cell_wholly_below_zero_that_does_not_lose_to_the_incumbent_is_both_negative(study):
    """`PREREG_TEMPLATE` rule 8: ranking losers is not a finding."""
    cell = _cell(-0.08, 0.02, diff=(-0.03, 0.07), own=(-0.12, -0.04))
    assert study.verdict_for("h20_stop2.0", _oos(study, "h20_stop2.0", cell)) == "both_negative"


def test_a_sharp_interval_around_zero_is_null(study):
    cell = _cell(0.0, 0.02, diff=(-0.05, 0.06), own=(-0.04, 0.04))
    assert study.verdict_for("h20_stop2.0", _oos(study, "h20_stop2.0", cell)) == "null"


def test_an_interval_wider_than_the_floor_is_inconclusive_whatever_it_excludes(study):
    """`PR-018`'s out-of-sample interval excluded zero and was still not read."""
    cell = _cell(0.05, 0.02, diff=(0.01, 0.30), own=(0.01, 0.09))
    assert study.verdict_for("h40_stop4.0", _oos(study, "h40_stop4.0", cell)) == "inconclusive"


def test_short_of_the_sample_rule_out_of_sample_is_inconclusive(study):
    cell = _cell(0.05, 0.02, trades=study.MIN_TRADES - 1, diff=(0.10, 0.20), own=(0.01, 0.09))
    assert study.verdict_for("h40_stop4.0", _oos(study, "h40_stop4.0", cell)) == "inconclusive"


# --- Wilson -------------------------------------------------------------------------------------


def test_wilson_upper_is_above_the_point_share(study):
    assert study.wilson_upper(115, 5000) > 115 / 5000


def test_wilson_upper_matches_the_closed_form(study):
    """p = 0.023, n = 5000: (p + z²/2n + z·sqrt(p(1-p)/n + z²/4n²)) / (1 + z²/n)."""
    assert study.wilson_upper(115, 5000) == pytest.approx(0.02756, abs=1e-4)


def test_wilson_upper_of_nothing_is_certainty(study):
    assert study.wilson_upper(0, 0) == 1.0


def test_wilson_upper_narrows_with_sample(study):
    assert study.wilson_upper(1150, 50000) < study.wilson_upper(115, 5000)


# --- one entry set, enforced after the engine has had its say ------------------------------------


def _trade(name: str, day: int):
    from datetime import date
    from types import SimpleNamespace

    return SimpleNamespace(instrument_id=name, entry_date=date(2020, 1, day))


def test_common_entries_keeps_only_what_every_book_realised(study):
    books = {"a": [_trade("X", 1), _trade("Y", 2), _trade("Z", 3)],
             "b": [_trade("X", 1), _trade("Z", 3)],
             "c": [_trade("X", 1), _trade("Y", 2), _trade("Z", 3)]}
    kept, dropped = study.common_entries(books)
    assert {(t.instrument_id, t.entry_date.day) for t in kept["a"]} == {("X", 1), ("Z", 3)}
    assert all(len(book) == 2 for book in kept.values())
    assert dropped == {"a": 1, "b": 0, "c": 1}


def test_the_same_name_on_a_different_date_is_a_different_trade(study):
    books = {"a": [_trade("X", 1)], "b": [_trade("X", 2)]}
    kept, dropped = study.common_entries(books)
    assert kept == {"a": [], "b": []}
    assert dropped == {"a": 1, "b": 1}


def test_identical_books_lose_nothing(study):
    books = {"a": [_trade("X", 1)], "b": [_trade("X", 1)]}
    assert study.common_entries(books)[1] == {"a": 0, "b": 0}


def test_the_power_estimate_sizes_every_contrast_section_six_can_read(study):
    """The first cut sized three grid contrasts and never the one §6 reads."""
    import power_pr019

    sized = set(power_pr019.CONTRASTS)
    assert all((name, study.INCUMBENT) in sized for name in study.GRID)


def test_every_registered_perturbation_is_declared_run(study):
    """Gate 25 reads the declaration. The first run wrote none and was refused for it."""
    block = study.PERTURBATIONS
    assert block["registered"], "§5 registers two perturbations"
    assert set(block["run"]) >= set(block["registered"])


def test_the_committed_result_carries_the_same_declaration(study):
    import json

    committed = json.loads(study.RESULT.read_text(encoding="utf-8"))
    assert committed["perturbations"] == study.PERTURBATIONS


# --- the tail profile ---------------------------------------------------------------------------


def test_mae_profile_counts_strictly_below_each_band(study):
    from types import SimpleNamespace

    trades = [SimpleNamespace(mae=v) for v in (-0.5, -1.0, -2.0, -2.5, -3.5)]
    profile = study.mae_profile(trades)
    assert profile["below_counts"] == {"-1": 3, "-2": 2, "-3": 1}
    assert profile["share_below_-2R"] == pytest.approx(0.4)
    assert profile["worst_mae"] == -3.5
    assert profile["trades"] == 5
