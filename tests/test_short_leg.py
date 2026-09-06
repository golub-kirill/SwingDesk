"""Restricting the short leg, and the three ways a restriction quietly answers a different question.

`measure_short_leg.py` asks whether the one interval-excluding-zero result in this project survives
being restricted to names a short leg could borrow. The arms are only comparable if the restriction
touches exactly one thing:

* **the RANKING is never restricted.** A name that cannot be borrowed still competes for the top
  decile and still sets where the deciles fall. Restricting the ranking would move the LONG leg too,
  and the arms would no longer differ by one variable.
* **the short book stays the same size as the long book.** A smaller short leg is a different
  portfolio, not a restricted version of this one, and it would flatter the spread by holding fewer
  of the worst names.
* **the unrestricted arm must reproduce the published implementation exactly**, or the control is
  not a control.

That last one is asserted against `run_pr013._spread` itself rather than against remembered numbers.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def short_leg():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "_short_leg", REPO / "tools" / "measure_short_leg.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def published():
    """`run_pr013._spread`, the implementation the committed number was computed with."""
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    import run_pr013
    return run_pr013


def cross_section(n: int = 200) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """`n` names: score descends with the index, forward return descends with it too."""
    scores = {f"N{i:03d}": Decimal(n - i) for i in range(n)}
    forward = {f"N{i:03d}": Decimal(n - i) / Decimal(1000) for i in range(n)}
    return scores, forward


# --- the control ---------------------------------------------------------------------------------

def test_the_unrestricted_arm_reproduces_the_published_implementation(short_leg, published):
    """Not "close to the published number" - the same function, the same inputs, the same answer."""
    scores, forward = cross_section()
    assert short_leg.restricted_spread(scores, forward, None) == published._spread(scores, forward)


def test_a_short_pool_covering_everything_is_the_unrestricted_arm(short_leg):
    scores, forward = cross_section()
    everything = short_leg.eligible_shorts({n: Decimal(1) for n in scores}, Decimal("1.0"))
    assert short_leg.restricted_spread(scores, forward, everything) == \
        short_leg.restricted_spread(scores, forward, None)


# --- the restriction touches the SHORT leg only ---------------------------------------------------

def test_an_unborrowable_name_still_occupies_the_top_decile(short_leg):
    """The long leg must not move. If it does, the arms differ by two variables, not one.

    The borrowable set excludes BOTH ends: not the top decile, so the long leg has to come from
    names the short pool never contained, and not the true bottom decile, so the short leg is
    forced to move. One fixture, both properties, and the expected value is written out in full
    rather than compared against the function's own other branch.
    """
    scores, forward = cross_section()
    shortable = {f"N{i:03d}" for i in range(20, 180)}
    long_leg = sum((forward[f"N{i:03d}"] for i in range(20)), Decimal(0)) / 20
    short_leg_mean = sum((forward[f"N{i:03d}"] for i in range(160, 180)), Decimal(0)) / 20
    assert short_leg.restricted_spread(scores, forward, shortable) == long_leg - short_leg_mean


def test_restricting_to_the_best_names_shrinks_the_spread(short_leg):
    """Borrow only the most-traded names and you can no longer short the true bottom decile."""
    scores, forward = cross_section()
    # Only the strongest half is borrowable, so the shortable "worst" are mid-pack.
    shortable = {f"N{i:03d}" for i in range(100)}
    assert short_leg.restricted_spread(scores, forward, shortable) < \
        short_leg.restricted_spread(scores, forward, None)


def test_the_short_book_is_the_same_size_as_the_long_book(short_leg):
    """Twenty long against twenty short. A smaller short leg would be a different portfolio.

    Exactly twenty names are borrowable, so a short book that took "all of them" and a short book
    that took the worst twenty are the same set — and one that took fewer would differ.
    """
    scores, forward = cross_section()
    shortable = {f"N{i:03d}" for i in range(180, 200)}
    spread = short_leg.restricted_spread(scores, forward, shortable)
    long_leg = sum((forward[f"N{i:03d}"] for i in range(20)), Decimal(0)) / 20
    short_leg_mean = sum((forward[f"N{i:03d}"] for i in range(180, 200)), Decimal(0)) / 20
    assert spread == long_leg - short_leg_mean


def test_too_few_borrowable_names_refuses_rather_than_shorting_fewer(short_leg):
    """Nineteen borrowable names against a twenty-name book is not a smaller version of it."""
    scores, forward = cross_section()
    assert short_leg.restricted_spread(
        scores, forward, {f"N{i:03d}" for i in range(181, 200)}
    ) is None


def test_a_thin_cross_section_refuses(short_leg):
    scores, forward = cross_section(n=50)
    assert short_leg.restricted_spread(scores, forward, None) is None


# --- the borrow proxy ----------------------------------------------------------------------------

def test_eligible_shorts_takes_the_most_traded_fraction(short_leg):
    adtv = {f"N{i:02d}": Decimal(100 - i) for i in range(100)}
    half = short_leg.eligible_shorts(adtv, Decimal("0.50"))
    assert len(half) == 50
    assert "N00" in half, "the most-traded name must be borrowable"
    assert "N99" not in half, "the least-traded name must not be"


def test_a_name_with_no_volume_reading_is_excluded_not_ranked_last(short_leg):
    """An unmeasured name is not a thin one; sorting it to the bottom would invent a fact."""
    adtv = {"MEASURED": Decimal(100)}
    eligible = short_leg.eligible_shorts(adtv, Decimal("0.50"))
    assert "UNMEASURED" not in eligible


def test_the_unrestricted_pool_is_every_measured_name(short_leg):
    adtv = {"A": Decimal(1), "B": Decimal(2)}
    assert short_leg.eligible_shorts(adtv, Decimal("1.0")) == {"A", "B"}


# --- what a rebalance costs -----------------------------------------------------------------------

def test_a_spread_pays_four_sides_and_a_long_only_book_pays_two(short_leg):
    """The long leg turns and so does the short one. Charging one round trip halves the cost."""
    assert short_leg.rebalance_cost("short_pool=1.0", Decimal(25)) == Decimal("0.01")
    assert short_leg.rebalance_cost("long_only", Decimal(25)) == Decimal("0.005")


def test_every_spread_arm_is_charged_the_same(short_leg):
    """Restricting the borrow pool changes which names are shorted, not how many legs turn."""
    costs = {
        short_leg.rebalance_cost(f"short_pool={p}", Decimal(25)) for p in short_leg.SHORT_POOLS
    }
    assert len(costs) == 1


def test_the_20_session_spread_is_roughly_erased_by_costs_and_the_126_one_is_not(short_leg):
    """The arithmetic that decides whether this finding is actionable, asserted rather than said.

    A four-sided rebalance at `DR-005`'s 25 bps is 1.00%. The measured 20-session spread for the
    liquid quartile is +1.069% gross, so what is left is a rounding error; the 126-session spread is
    +8.704% and pays the same 1.00% a quarter as often.
    """
    cost = short_leg.rebalance_cost("short_pool=0.25", short_leg.SLIPPAGE_BPS)
    assert cost == Decimal("0.01")
    assert Decimal("0.01069") - cost < Decimal("0.001"), "the ratified horizon nets to nothing"
    assert Decimal("0.08704") - cost > Decimal("0.07"), "the long horizon survives comfortably"


# --- the long-only control ------------------------------------------------------------------------

def test_long_only_excess_is_the_top_decile_against_the_benchmark(short_leg):
    scores, forward = cross_section()
    top = sum((forward[f"N{i:03d}"] for i in range(20)), Decimal(0)) / 20
    assert short_leg.long_only_excess(scores, forward, Decimal("0.05")) == top - Decimal("0.05")


def test_long_only_ignores_the_bottom_decile_entirely(short_leg):
    """The whole point of §8a: a long-only book earns nothing from the losers."""
    scores, forward = cross_section()
    worse = dict(forward)
    for i in range(180, 200):
        worse[f"N{i:03d}"] = Decimal("-99")
    assert short_leg.long_only_excess(scores, worse, Decimal(0)) == \
        short_leg.long_only_excess(scores, forward, Decimal(0))
    assert short_leg.restricted_spread(scores, worse, None) != \
        short_leg.restricted_spread(scores, forward, None)
