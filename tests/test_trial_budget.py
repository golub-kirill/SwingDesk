"""The trial counter, and the distinction the whole file is built on.

`b.deflated_sharpe` reads *"the CUMULATIVE trial count across the whole programme"*, and until
2026-09-06 the counter read `docs/prereg/results/` alone — so `measure_exit_surface.py` could sweep
twenty-five stop/target cells and spend nothing. These tests hold the correction in place.

**The load-bearing distinction is UNDECLARED versus ZERO.** They are the same number and different
claims: one says *this measurement cannot produce a Sharpe to deflate*, the other says *nobody has
said*. A test that only asserted `trials == 0` for both would pass with the distinction deleted, and
the deletion is exactly the failure that let 34 configurations go uncounted.

Reads the repository's own committed measurements, so the assertions are about properties rather
than about a total that moves whenever a study lands.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def budget():
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location("_trial_budget", REPO / "tools" / "trial_budget.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- every committed measurement is accounted for ----------------------------------------------

def test_every_committed_measurement_gets_exactly_one_row(budget):
    """A measurement the counter does not see is a configuration the programme forgot it tried."""
    files = {p.stem for p in budget.MEASUREMENTS.glob("*.json")}
    rows = budget.exploratory_spends()
    assert files, "there are no committed measurements to count"
    assert [r.study for r in rows] == sorted(files)


def test_a_declared_sweep_is_counted_with_its_own_rule(budget):
    """The exit surface swept 25 cells against a null; 26 is the number and the rule says why."""
    rows = {r.study: r for r in budget.exploratory_spends()}
    surface = rows["exit-surface-2026-09-06"]
    assert surface.trials == 26
    assert "stop multiples" in surface.rule


def test_one_tool_sweep_outweighs_the_largest_pre_registration(budget):
    """The claim that justifies this change, in a form that does not go stale.

    **The first version of this test asserted the exit surface outweighed EVERY pre-registration
    put together.** That was true at 20 registered trials and became false hours later, when
    `PR-014` declared 12 — the test failed and caught its own sentence expiring. The durable claim
    is the comparison against the largest single study, which is what makes a tool sweep worth
    counting at all: it is not a rounding error beside a filing.
    """
    largest = max(s.trials for s in budget.spends())
    surface = {r.study: r for r in budget.exploratory_spends()}["exit-surface-2026-09-06"]
    assert surface.trials > largest


# --- UNDECLARED is not zero --------------------------------------------------------------------

def test_a_cost_input_spends_nothing_and_says_so(budget):
    """Zero WITH a reason. The reason is what separates it from an oversight."""
    row = {r.study: r for r in budget.exploratory_spends()}["quoted-spread-2026-09-06"]
    assert row.trials == 0
    assert row.what == "-"
    assert "cost input" in row.rule


def test_an_unknown_measurement_is_reported_as_a_gap_not_a_zero(budget):
    """This is the assertion that fails if UNDECLARED is ever collapsed into a plain zero."""
    rows = budget.exploratory_spends()
    undeclared = [r for r in rows if r.what == "UNDECLARED"]
    assert undeclared, "no undeclared measurement to judge; add one or drop this test"
    for row in undeclared:
        assert row.trials == 0
        assert "GAP" in row.rule
        assert row.study not in budget.NO_SPEND_MEASUREMENTS
        assert row.study not in budget.EXPLORATORY


def test_declared_and_no_spend_are_disjoint(budget):
    """A measurement declared in both tables would be counted by whichever branch ran first."""
    assert not set(budget.EXPLORATORY) & set(budget.NO_SPEND_MEASUREMENTS)


# --- the hurdle ---------------------------------------------------------------------------------

def test_the_hurdle_rises_with_the_trial_count(budget):
    """More shots, a higher expected best under the null. If this inverts, the budget inverts."""
    values = [budget.expected_max_sharpe(n) for n in (2, 5, 10, 20, 50, 100)]
    assert values == sorted(values)


def test_one_trial_clears_nothing(budget):
    """With a single shot there is no maximum to correct for."""
    assert budget.expected_max_sharpe(1) == 0.0
    assert budget.expected_max_sharpe(0) == 0.0


def test_the_hurdle_matches_the_one_case_that_has_a_closed_form(budget):
    """E[max of two standard normals] is exactly 1/sqrt(pi). The approximation must land near it.

    This is the only rung of the ladder with an answer independent of the paper, which makes it the
    only one that checks the FORMULA rather than the code's memory of it. Monotonicity does not:
    perturbing the first order-statistic term leaves the curve rising and moves every hurdle - at
    N=2 from 0.520 to 0.805 - and a shape-only test passes through it.

    The tolerance is 10%: Bailey & Lopez de Prado's expression is an asymptotic approximation and
    reads 0.520 against the exact 0.564, about 8% low, which is the approximation's own error and
    not a defect.
    """
    exact = 1 / math.sqrt(math.pi)
    assert budget.expected_max_sharpe(2) == pytest.approx(exact, rel=0.10)


def test_the_published_ladder_is_pinned(budget):
    """A characterisation, and labelled as one: it locks the AUTHORED IMPORT against silent drift.

    These figures are quoted in `DR-040`, `TODO.md` and the trial-budget output. If the constant or
    either order-statistic term moves, the documents that quote them become wrong with nothing
    failing — which is `AGENTS.md` §10.6's whole complaint about hand-carried numbers.
    """
    assert budget.expected_max_sharpe(20) == pytest.approx(1.9007, abs=0.0001)
    assert budget.expected_max_sharpe(50) == pytest.approx(2.2763, abs=0.0001)
    assert budget.expected_max_sharpe(100) == pytest.approx(2.5306, abs=0.0001)


def test_the_first_trials_cost_more_than_the_last(budget):
    """The finding a budget turns on: the curve is logarithmic, so rationing late buys little."""
    first_five = budget.expected_max_sharpe(5) - budget.expected_max_sharpe(1)
    next_forty_five = budget.expected_max_sharpe(50) - budget.expected_max_sharpe(5)
    assert first_five > next_forty_five


def test_counting_only_pre_registrations_understates_the_search(budget):
    """The whole point, as a number: the exploratory column is not a rounding error."""
    registered = sum(s.trials for s in budget.spends())
    exploratory = sum(s.trials for s in budget.exploratory_spends())
    assert exploratory > 0
    assert budget.expected_max_sharpe(registered + exploratory) > \
        budget.expected_max_sharpe(registered)
