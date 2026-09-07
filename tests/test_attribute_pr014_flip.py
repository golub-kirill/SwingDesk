"""Re-pricing a committed cell, and the one line that decides whether the attribution is real.

`attribute_pr014_flip.py` answers which of two simultaneous changes flipped `PR-014` - the cost
correction or the backfill - by re-pricing committed cells under the other cost model. The whole
method rests on one property of `run_pr014.py`: **cost is a constant annual subtraction from a
bootstrapped GROSS interval**, so the gross bound is recoverable and the re-price is arithmetic
rather than a re-estimate.

Two things can silently destroy that and neither raises:

* **copying the qualification flag instead of re-deriving it.** `net_excludes_zero` is what §6
  selects on. A re-price that carries the old flag forward reports the OLD verdict under the NEW
  cost and the tool then attributes the flip to whichever change it happened to apply second - a
  wrong answer that looks exactly like a right one.
* **losing the sign of the adjustment.** Re-pricing UP must move a net figure DOWN. Getting that
  backwards still produces a plausible table.

No store, no network, no committed file: every fixture is a cell built here.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def attribute():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "_attribute", REPO / "tools" / "attribute_pr014_flip.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def cell(net: float, low: float, high: float, control: float = 0.05) -> dict[str, object]:
    return {
        "rebalances": 40,
        "sample_rule_met": True,
        "gross_annual": net + 0.02,
        "net_annual": net,
        "net_low": low,
        "net_high": high,
        "net_excludes_zero": low > 0 or high < 0,
        "control_universe_annual": control,
    }


def row(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "horizon": 42,
        "arm": "long_short",
        "K": 2,
        "annual_cost": 0.02,
        "annual_cost_as_first_published": 0.06,
        "primary": cell(0.05, 0.01, 0.09),
        "holdout": cell(0.04, 0.01, 0.07),
    }
    base.update(kwargs)
    return base


def test_repricing_at_the_same_cost_changes_nothing(attribute):
    """The identity case. A re-price that shifts anything here shifts everything else too."""
    same = attribute.reprice(row(), "annual_cost")
    for window in ("primary", "holdout"):
        for key in ("net_annual", "net_low", "net_high"):
            assert Decimal(str(same[window][key])) == Decimal(str(row()[window][key]))


def test_a_dearer_cost_moves_the_whole_interval_down_by_the_difference(attribute):
    """Sign and magnitude together: 6% instead of 2% must cost exactly four points."""
    dearer = attribute.reprice(row(), "annual_cost_as_first_published")
    for key in ("net_annual", "net_low", "net_high"):
        moved = Decimal(str(row()["primary"][key])) - Decimal(str(dearer["primary"][key]))
        assert moved == Decimal("0.04")


def test_the_qualification_flag_is_re_derived_and_not_carried_over(attribute):
    """The mutation this file exists for.

    The cell qualifies at 2% - its interval is [+1%, +9%]. At 6% the same interval is [-3%, +5%]
    and straddles zero, so it must STOP qualifying. Returning the stored `True` here is what would
    make the tool attribute the flip to the wrong change while printing a well-formed table.
    """
    assert row()["primary"]["net_excludes_zero"] is True
    dearer = attribute.reprice(row(), "annual_cost_as_first_published")
    assert dearer["primary"]["net_excludes_zero"] is False
    assert dearer["holdout"]["net_excludes_zero"] is False


def test_a_cell_can_start_qualifying_when_the_cost_falls(attribute):
    """The direction that actually happened: cheaper costs let SHORTER horizons in.

    §6 takes the shortest qualifying horizon, so a flag that only ever turns off would still hide
    the real finding - the corrected cost model admits horizons the published one suppressed.
    """
    suppressed = row(annual_cost=0.02, annual_cost_as_first_published=0.06,
                     primary=cell(-0.01, -0.05, 0.03))
    cheaper = attribute.reprice(suppressed, "annual_cost")
    assert suppressed["primary"]["net_excludes_zero"] is False
    dearer = attribute.reprice(suppressed, "annual_cost_as_first_published")
    # priced AS PUBLISHED the cell is [-9%, -1%], excluding zero on the losing side; priced at the
    # measured cost it is [-5%, +3%] and does not. Same series, opposite qualification.
    assert dearer["primary"]["net_excludes_zero"] is True
    assert cheaper["primary"]["net_excludes_zero"] is False


def test_both_negative_is_re_derived_too(attribute):
    """§6's second guard reads a net figure, so it moves with the cost like the first one."""
    losing = row(primary=cell(0.01, -0.03, 0.05, control=-0.02))
    assert attribute.reprice(losing, "annual_cost")["primary"]["both_negative"] is False
    assert attribute.reprice(losing, "annual_cost_as_first_published")["primary"][
        "both_negative"] is True


def test_a_window_the_sample_rule_refused_passes_through_untouched(attribute):
    """`run_pr014` omits `net_annual` when a window has too few rebalances. Re-pricing an absent
    number would invent one, and the guard has to be there rather than implied."""
    refused = row(holdout={"rebalances": 9, "sample_rule_met": False})
    priced = attribute.reprice(refused, "annual_cost_as_first_published")
    assert priced["holdout"] == {"rebalances": 9, "sample_rule_met": False}


def test_the_decision_is_taken_by_the_study_and_not_restated_here(attribute):
    """A-2's rule applied to this tool: the verdict must come from `run_pr014.decide` itself.

    If the tool grew its own copy of §6 the two could drift, and the drift would be invisible -
    both would print a verdict.
    """
    import run_pr014

    assert attribute.decide is run_pr014.decide
    assert attribute.STRESS_MULTIPLE == run_pr014.STRESS_MULTIPLE


def test_a_short_window_never_qualifies_however_the_interval_lands(attribute):
    """The mutant that survived the first pass, and it was a real gap.

    `run_pr014` writes `net_annual` for ANY window the bootstrap could price - the sample rule
    gates `net_excludes_zero`, not the numbers - so a window with nine rebalances arrives here
    carrying a perfectly clean interval. Re-deriving the flag from the bounds alone would let §8's
    minimum fall out of the re-price, and the tool would qualify a horizon the study refused.
    """
    thin = cell(0.05, 0.01, 0.09)
    thin["rebalances"] = 9
    thin["sample_rule_met"] = False
    thin["net_excludes_zero"] = False
    priced = attribute.reprice(row(primary=thin), "annual_cost")
    assert priced["primary"]["net_low"] > 0
    assert priced["primary"]["net_excludes_zero"] is False


# --- the reproduction check ----------------------------------------------------------------------
#
# The 2x2 is only an attribution if the control run IS the published run with one thing changed.
# That is a claim about numbers, and `check_reproduction` is where it stops being a claim.


def run(gross_primary: float = 0.15, cost: float = 0.02, rebalances: int = 48,
        as_of: str = "2026-09-06T11:00:01.845569-05:00") -> dict[str, object]:
    def window(gross: float) -> dict[str, object]:
        return {"rebalances": rebalances, "sample_rule_met": True,
                "gross_annual": round(gross, 6), "net_annual": round(gross - cost, 6)}
    return {"as_of": as_of,
            "rows": [{"horizon": 126, "arm": "long_short", "annual_cost": cost,
                      "primary": window(gross_primary), "holdout": window(0.13)}]}


def test_an_exact_reproduction_reports_no_drift(attribute):
    assert attribute.check_reproduction(run(cost=0.02), run(cost=0.0178)) == []


def test_a_moved_gross_figure_is_caught(attribute):
    """The fault the check exists for: the control drifted and the 2x2 would compare two samples."""
    drift = attribute.check_reproduction(run(gross_primary=0.15), run(gross_primary=0.151))
    assert len(drift) == 1
    assert "gross" in drift[0]


def test_a_different_knowledge_instant_is_caught_on_its_own(attribute):
    """`as_of` is the whole definition of "the same sample", so it is checked before any number."""
    drift = attribute.check_reproduction(run(), run(as_of="2026-09-06T22:36:49.635786-05:00"))
    assert any("as_of" in line for line in drift)


def test_one_unit_in_the_last_place_is_not_drift(attribute):
    """The false alarm the first version of this check produced, pinned so it cannot come back.

    `net` and `cost` are rounded to six places independently, so `net + cost` can miss `gross` by
    a whole unit at that place with nothing wrong. A check that compared THAT sum across two files
    reported six differences on a run that reproduces exactly - and a reproduction check which
    cries wolf is worse than none, because the honest response to it is to stop reading it.
    """
    published = run(cost=0.02)
    published["rows"][0]["primary"]["net_annual"] = 0.129999  # gross 0.15, cost 0.02, off by 1 ulp
    assert attribute.check_reproduction(published, run(cost=0.0178)) == []


def test_a_genuinely_inconsistent_file_is_still_caught(attribute):
    """The tolerance above is one unit, not a shrug. Ten of them is a file that does not add up."""
    published = run(cost=0.02)
    published["rows"][0]["primary"]["net_annual"] = 0.12999
    drift = attribute.check_reproduction(published, run(cost=0.0178))
    assert any("gross - net - cost" in line for line in drift)


def test_a_cell_missing_from_the_published_run_is_reported(attribute):
    """A grid that grew between the runs is not a reproduction either, and would otherwise pass by
    simply not being compared."""
    control = run()
    control["rows"].append({"horizon": 20, "arm": "long_only", "annual_cost": 0.02,
                            "primary": {"rebalances": 53, "sample_rule_met": True,
                                        "gross_annual": 0.02, "net_annual": 0.0},
                            "holdout": {"rebalances": 55, "sample_rule_met": True,
                                        "gross_annual": 0.01, "net_annual": -0.01}})
    drift = attribute.check_reproduction(run(), control)
    assert any("absent from the published run" in line for line in drift)
