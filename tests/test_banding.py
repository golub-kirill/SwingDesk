"""The buy/hold band, and the three ways a band flatters itself without being wrong-looking.

`measure_banding.py` compares a fixed top-decile book against one that buys narrow and sells wide.
The comparison is only meaningful if the band changes exactly one thing:

* **the book must be the SAME SIZE under both policies.** A band that quietly holds more names beats
  a fixed book by diversification and reports it as a cost saving.
* **`hold == buy` must reproduce the fixed policy exactly**, because that is the control. If the
  degenerate case drifts, every "banded beats fixed" reading is against a straw man.
* **only genuinely new names count as bought**, since `bought` is the entire cost term. Counting a
  keeper as a purchase would erase the mechanism being measured.

And one correctness rule: a held name that has fallen out of the ranking altogether — delisted, or
no longer admitted by the liquidity rule — is sold, not assumed still good.

No store, no network. Rankings are literal lists.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def banding():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "_banding", REPO / "tools" / "measure_banding.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ranking(n: int = 100) -> list[str]:
    """`N000` best, `N099` worst."""
    return [f"N{i:03d}" for i in range(n)]


TENTH = Decimal("0.10")
THIRD = Decimal("0.30")


# --- the control -------------------------------------------------------------------------------

def test_equal_bands_reproduce_the_fixed_policy(banding):
    """`hold == buy` must sell anything outside the top decile — this is the comparison's baseline."""
    ranked = ranking()
    held = {f"N{i:03d}" for i in range(20, 30)}  # all outside the top 10
    book, bought = banding.rebalance(held, ranked, TENTH, TENTH)
    assert book == set(ranked[:10])
    assert bought == 10, "a fixed book rebuilt from nothing turns over completely"


def test_a_fixed_book_already_at_the_top_trades_nothing(banding):
    ranked = ranking()
    book, bought = banding.rebalance(set(ranked[:10]), ranked, TENTH, TENTH)
    assert book == set(ranked[:10])
    assert bought == 0


# --- the band ----------------------------------------------------------------------------------

def test_a_slipped_name_inside_the_wider_band_is_kept(banding):
    """Rank 15 of 100: sold under a top-decile rule, held under a top-30% band. The mechanism."""
    ranked = ranking()
    held = {"N015"}
    kept, _ = banding.rebalance(held, ranked, TENTH, THIRD)
    assert "N015" in kept
    sold, _ = banding.rebalance(held, ranked, TENTH, TENTH)
    assert "N015" not in sold


def test_a_name_outside_the_wider_band_is_sold(banding):
    ranked = ranking()
    book, _ = banding.rebalance({"N035"}, ranked, TENTH, THIRD)
    assert "N035" not in book


def test_the_boundary_of_the_hold_band_is_exclusive_and_consistent(banding):
    """Rank 29 is inside the top 30 of 100; rank 30 is not."""
    ranked = ranking()
    assert "N029" in banding.rebalance({"N029"}, ranked, TENTH, THIRD)[0]
    assert "N030" not in banding.rebalance({"N030"}, ranked, TENTH, THIRD)[0]


def test_a_held_name_that_left_the_ranking_is_sold(banding):
    """Delisted, or no longer admitted. Keeping it would hold a position in a name with no price."""
    ranked = ranking()
    book, _ = banding.rebalance({"GONE"}, ranked, TENTH, THIRD)
    assert "GONE" not in book


# --- the comparison must be fair ---------------------------------------------------------------

def test_both_policies_run_the_same_book_size(banding):
    """A band that held more names would win by diversification and report it as a cost saving."""
    ranked = ranking()
    held = {f"N{i:03d}" for i in range(10, 25)}
    fixed, _ = banding.rebalance(held, ranked, TENTH, TENTH)
    banded, _ = banding.rebalance(held, ranked, TENTH, THIRD)
    assert len(fixed) == len(banded) == 10


def test_surplus_keepers_are_trimmed_to_the_best(banding):
    """Fifteen names inside the band, ten seats. The five worst go, not five arbitrary ones."""
    ranked = ranking()
    held = {f"N{i:03d}" for i in range(15, 30)}
    book, bought = banding.rebalance(held, ranked, TENTH, THIRD)
    assert book == {f"N{i:03d}" for i in range(15, 25)}
    assert bought == 0, "the seats were all filled by keepers; nothing was purchased"


def test_only_new_names_count_as_bought(banding):
    """`bought` is the whole cost term. Counting a keeper would erase the mechanism."""
    ranked = ranking()
    held = {f"N{i:03d}" for i in range(12, 20)}  # 8 keepers inside the band, 2 seats free
    book, bought = banding.rebalance(held, ranked, TENTH, THIRD)
    assert len(book) == 10
    assert bought == 2


def test_a_band_turns_over_less_than_a_fixed_book_on_the_same_drift(banding):
    """The claim under test, in its smallest form."""
    ranked = ranking()
    held = {f"N{i:03d}" for i in range(11, 21)}
    _, fixed_bought = banding.rebalance(held, ranked, TENTH, TENTH)
    _, banded_bought = banding.rebalance(held, ranked, TENTH, THIRD)
    assert banded_bought < fixed_bought


# --- the pieces around it ----------------------------------------------------------------------

def test_ranking_is_best_first_and_ties_break_by_name(banding):
    scores = {"B": Decimal(1), "A": Decimal(1), "C": Decimal(2)}
    assert banding.rank_names(scores) == ["C", "A", "B"]


def test_cost_charges_two_sides_of_the_traded_fraction(banding):
    """Half the book turning over at 25 bps per side is 25 bps on the whole book."""
    assert banding.cost_of(5, 10, Decimal(25)) == Decimal("0.0025")
    assert banding.cost_of(10, 10, Decimal(25)) == Decimal("0.005")
    assert banding.cost_of(0, 10, Decimal(25)) == Decimal(0)


def test_cost_refuses_an_empty_book_rather_than_dividing(banding):
    assert banding.cost_of(0, 0, Decimal(25)) == Decimal(0)


def test_the_book_return_is_equal_weighted_and_skips_the_priceless(banding):
    forward = {"A": Decimal("0.10"), "B": Decimal("0.20")}
    assert banding.book_return({"A", "B"}, forward) == Decimal("0.15")
    assert banding.book_return({"A", "B", "MISSING"}, forward) == Decimal("0.15")
    assert banding.book_return({"MISSING"}, forward) is None


def test_an_empty_ranking_produces_no_book(banding):
    assert banding.rebalance(set(), [], TENTH, THIRD) == (set(), 0)
