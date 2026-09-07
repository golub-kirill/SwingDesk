"""What a rebalance actually buys, and the two ways a turnover measurement flatters itself.

This tool exists because `PR-014` charged GROSS turnover and its `ACCEPT` did not survive the
correction. Two things would let the same error back in and neither raises:

* **counting names instead of weight.** A book going from two names to four has not turned over
  100% — it kept both and bought two more, and the weight it had to buy is half. A tool that counts
  set differences reports the churn of a book that is growing as if it were a book that sold out.
* **charging turnover without annualising by the horizon it belongs to.** The whole finding is that
  the overcharge is a function of the holding period. A cost that ignored `252 / horizon` would be
  wrong by a constant, which is the one shape that changes no ordering and hides the point.

No store, no network.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def persistence():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "_persistence", REPO / "tools" / "measure_decile_persistence.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_an_unchanged_selection_buys_nothing(persistence):
    """The case the corrected cost model exists for: the names persisted, so the book held them."""
    assert persistence.one_sided(["A", "B", "C"], ["A", "B", "C"]) == Decimal(0)


def test_a_completely_replaced_selection_buys_the_whole_book(persistence):
    assert persistence.one_sided(["A", "B"], ["C", "D"]) == Decimal(1)


def test_half_the_names_replaced_buys_half_the_book(persistence):
    assert persistence.one_sided(["A", "B", "C", "D"], ["A", "B", "E", "F"]) == Decimal("0.5")


def test_a_growing_book_is_measured_in_WEIGHT_and_not_in_names(persistence):
    """The mutation this file exists for.

    Two names at 50% each become four at 25% each. Two of the four are NEW, so a set-difference
    count says the book turned over 50% of its NAMES — and by weight it bought exactly 50%, which
    happens to agree. Make it two names becoming three and the two readings part company: by name
    one of three is new (33%), by weight the book bought 1/3 and sold 2 x 1/6, and only the weight
    reading is what a broker charges for.
    """
    bought = persistence.one_sided(["A", "B"], ["A", "B", "C"])
    assert bought == Decimal(1) / Decimal(3)
    # And the book pays going the OTHER way too, which is the part that is easy to get wrong and
    # is worth pinning. Three names at 1/3 becoming two at 1/2 sells C and BUYS 1/6 of each
    # survivor, because the book stays fully invested and has to concentrate to do it. That is a
    # real trade at a real spread, and a model that called a shrinking book free would understate
    # exactly the dates when the admitted cross-section contracts.
    # Compared to within a Decimal ulp rather than exactly: this direction sums TWO increases of
    # 1/6, each rounded at Decimal's 28 significant digits, where the direction above is one
    # increase of 1/3 and lands exact. A turnover measured to 28 digits and reported to 1 decimal
    # place has no use for the last of them.
    assert abs(persistence.one_sided(["A", "B", "C"], ["A", "B"])
               - Decimal(1) / Decimal(3)) < Decimal("1e-20")


def test_an_empty_previous_book_buys_everything(persistence):
    """The first rebalance of a run. Charging it as free would understate a short horizon most,
    because a short horizon has more rebalances for the error to hide in."""
    assert persistence.one_sided([], ["A", "B"]) == Decimal(1)


def test_the_cost_is_annualised_by_the_HORIZON_and_not_by_a_constant(persistence):
    """The second way this measurement could flatter itself.

    A book rebalanced every 14 sessions rebalances 18 times a year and one rebalanced every 252
    sessions once. Identical turnover therefore costs eighteen times as much at the short horizon,
    and that ratio IS the finding about where the old cost model went wrong.
    """
    short = persistence.annual_cost(Decimal("0.5"), 14, "long_only", Decimal(25))
    long = persistence.annual_cost(Decimal("0.5"), 252, "long_only", Decimal(25))
    assert short == long * 18


def test_a_spread_pays_four_sides_and_a_long_only_book_two(persistence):
    spread = persistence.annual_cost(Decimal("0.5"), 21, "long_short", Decimal(25))
    long_only = persistence.annual_cost(Decimal("0.5"), 21, "long_only", Decimal(25))
    assert spread == long_only * 2


def test_full_turnover_reproduces_the_charge_the_uncorrected_tools_make(persistence):
    """The `as charged` column has to be the OLD model exactly, or the overcharge ratio is fiction.

    `run_pr013.py` charges `4 x 25bp` at every formation. At 126 sessions that is two formations a
    year, so 2.00% — the figure `PR-014` published for its 126-session spread.
    """
    charged = persistence.annual_cost(Decimal(1), 126, "long_short", Decimal(25))
    assert charged == Decimal("0.02")


def test_the_overcharge_is_exactly_the_reciprocal_of_the_turnover(persistence):
    """The ratio printed in the table, checked against the two costs it summarises rather than
    trusted as arithmetic done once in a print statement."""
    for turns in (Decimal("0.25"), Decimal("0.4"), Decimal("0.831")):
        measured = persistence.annual_cost(turns, 20, "long_only", Decimal(25))
        charged = persistence.annual_cost(Decimal(1), 20, "long_only", Decimal(25))
        assert charged / measured == 1 / turns
