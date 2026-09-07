"""`PR-014`'s machinery, and the four places an overlapping book flatters itself.

The study's whole claim is that overlapping windows use every formation date **without inventing
information**. Four things carry that and none raises an error when wrong:

* **the block bootstrap** — overlapping sub-portfolios share holdings, so an i.i.d. resample reports
  an interval several times too narrow. That is the flattering direction, so a test that only
  checked "an interval comes back" would pass through the bug the method exists to prevent.
* **the cost** — and this is where the study was WRONG when it published. It charged `252/horizon`
  FULL book turns a year, which is GROSS turnover: what a book would trade if every rebalance sold
  everything. A real book nets — a name still in the decile is held, not sold and re-bought — and
  the measured net turnover is 39.0% of the book per rebalance at horizon 20 against the 12.6 full
  turns charged. The overcharge was 2.7x at short horizons and nil at long ones, so it tilted the
  study's own conclusion toward long holding periods. The cost now comes from MEASURED turnover
  between consecutive books and the fixtures below pin that, because the analytic form looked
  right and was not.
* **the ranking** — `PR-014` A-2: the study must score the way the card scores. The selection is
  taken from the LIVE `ByMarketPathStrength`, and both legs come from ONE ordering.
* **a missing price** — a name whose bar cannot be read on either end contributes nothing, rather
  than being carried at zero. Zero is a claim that it did not move.

No store, no network.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pr014():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_pr014", REPO / "tools" / "run_pr014.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def series(name: str, closes: list[str]) -> BarSeries:
    when = datetime(2015, 1, 1, tzinfo=UTC)
    bars = tuple(
        Bar(
            instrument_id=name, interval=Interval.DAY, series=Series.RAW,
            event_time=when + timedelta(days=i),
            session_date=date(2015, 1, 1) + timedelta(days=i),
            open=Decimal(c), high=Decimal(c), low=Decimal(c), close=Decimal(c),
            volume=Decimal(1_000_000), knowledge_time=when,
        )
        for i, c in enumerate(closes)
    )
    return BarSeries(
        instrument_id=name, interval=Interval.DAY, series=Series.RAW,
        knowledge_time=when, bars=bars,
    )


# --- what a year of turnover costs, and the netting the first version got wrong ------------------

def test_a_name_that_stays_in_the_book_is_not_rebought(pr014):
    """**The correction.** The first version charged a full turn every rebalance at K=1.

    Two consecutive selections sharing three of four names buy one name, not four. Charging four
    is charging GROSS turnover where a book pays NET, and it is why the 20-session cell was first
    published at 6.30% a year against a measured 1.75%.
    """
    from datetime import date as d
    before = pr014.book_weights([d(2024, 1, 1)], {d(2024, 1, 1): ["A", "B", "C", "D"]})
    after = pr014.book_weights([d(2024, 2, 1)], {d(2024, 2, 1): ["A", "B", "C", "E"]})
    assert pr014.turnover(before, after) == Decimal("0.25")


def test_an_unchanged_book_turns_over_nothing(pr014):
    from datetime import date as d
    book = pr014.book_weights([d(2024, 1, 1)], {d(2024, 1, 1): ["A", "B"]})
    assert pr014.turnover(book, book) == Decimal(0)


def test_a_completely_replaced_book_turns_over_once(pr014):
    from datetime import date as d
    before = pr014.book_weights([d(2024, 1, 1)], {d(2024, 1, 1): ["A", "B"]})
    after = pr014.book_weights([d(2024, 2, 1)], {d(2024, 2, 1): ["C", "D"]})
    assert pr014.turnover(before, after) == Decimal(1)


def test_the_book_sums_to_one_whatever_the_legs_hold(pr014):
    """Each sub-portfolio contributes 1/K in total, however many names it picked.

    Weighting a name by 1/K alone makes a leg of four names four times the size of a leg of one,
    and the turnover that implies is four times too large. Caught here, not by the run.
    """
    from datetime import date as d
    legs = [d(2024, m, 1) for m in (1, 2, 3, 4)]
    picks = {legs[0]: ["A", "B"], legs[1]: ["A", "B"], legs[2]: ["C"], legs[3]: ["D"]}
    weights = pr014.book_weights(legs, picks)
    assert sum(weights.values()) == Decimal(1)
    assert weights["A"] == Decimal("0.25"), "half of two legs, each of two names"
    assert weights["C"] == Decimal("0.25"), "all of one leg"


def test_an_empty_leg_does_not_break_the_weighting(pr014):
    from datetime import date as d
    legs = [d(2024, 1, 1), d(2024, 2, 1)]
    weights = pr014.book_weights(legs, {legs[0]: ["A"], legs[1]: []})
    assert weights == {"A": Decimal("0.5")}


def test_only_weight_INCREASES_are_bought(pr014):
    """A name being trimmed is sold, and its sale was paid for by the round trip at entry."""
    before = {"A": Decimal("0.5"), "B": Decimal("0.5")}
    after = {"A": Decimal("0.75"), "B": Decimal("0.25")}
    assert pr014.turnover(before, after) == Decimal("0.25")


def test_a_spread_pays_four_sides_and_a_long_only_book_two(pr014):
    turns = [Decimal("0.25")] * 4
    assert pr014.annual_cost_from(turns, "long_short", Decimal(25)) == \
        2 * pr014.annual_cost_from(turns, "long_only", Decimal(25))


def test_the_cost_is_read_from_measured_turnover_not_from_the_horizon(pr014):
    """Two books with the same horizon and different turnover must not cost the same.

    This is the property the first version could not express: its cost was a function of the
    horizon alone, so a book that held its names and one that churned them were charged identically.
    """
    churning = pr014.annual_cost_from([Decimal(1)] * 10, "long_only", Decimal(25))
    holding = pr014.annual_cost_from([Decimal("0.1")] * 10, "long_only", Decimal(25))
    assert churning == holding * 10


def test_no_rebalances_costs_nothing_rather_than_dividing(pr014):
    assert pr014.annual_cost_from([], "long_only", Decimal(25)) == Decimal(0)


# --- the interval must survive autocorrelation -----------------------------------------------------

def test_the_block_bootstrap_reports_a_mean_and_an_interval(pr014):
    values = [Decimal(v) for v in range(1, 41)]
    out = pr014.moving_block_bootstrap(values, 6, 20260906, 500)
    assert out is not None
    mean, low, high = out
    assert mean == pytest.approx(20.5)
    assert low < mean < high


def test_a_longer_block_widens_the_interval_on_dependent_data(pr014):
    """The reason the method exists, in its smallest form.

    A run of twenty zeros followed by twenty ones is maximally dependent. Resampled one observation
    at a time the interval is tight; resampled in long blocks it is not, because a block-resample
    can draw the same regime repeatedly.
    """
    values = [Decimal(0)] * 20 + [Decimal(1)] * 20
    tight = pr014.moving_block_bootstrap(values, 1, 20260906, 2000)
    wide = pr014.moving_block_bootstrap(values, 10, 20260906, 2000)
    assert tight is not None and wide is not None
    assert (wide[2] - wide[1]) > (tight[2] - tight[1])


def test_the_bootstrap_is_seeded_so_a_rerun_reproduces_it(pr014):
    values = [Decimal(v) for v in range(1, 31)]
    assert pr014.moving_block_bootstrap(values, 6, 7, 300) == \
        pr014.moving_block_bootstrap(values, 6, 7, 300)


def test_a_block_longer_than_the_sample_is_clamped_not_crashed(pr014):
    assert pr014.moving_block_bootstrap([Decimal(1), Decimal(2)], 99, 1, 100) is not None


def test_too_few_observations_return_nothing(pr014):
    assert pr014.moving_block_bootstrap([Decimal(1)], 6, 1, 100) is None
    assert pr014.moving_block_bootstrap([], 6, 1, 100) is None


# --- the book -------------------------------------------------------------------------------------

def test_a_book_return_is_equal_weighted(pr014):
    up = series("UP", ["100"] * 5 + ["110"])
    flat = series("FLAT", ["100"] * 6)
    by_name = {"UP": up, "FLAT": flat}
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)} for n, s in by_name.items()}
    start, end = date(2015, 1, 1), date(2015, 1, 6)
    assert pr014.book_return(["UP", "FLAT"], by_name, index_of, start, end) == Decimal("0.05")


def test_a_name_with_no_bar_on_either_end_contributes_nothing(pr014):
    """Not zero. A price that cannot be read is not a price that did not move."""
    up = series("UP", ["100"] * 5 + ["110"])
    by_name = {"UP": up}
    index_of = {"UP": {b.session_date: i for i, b in enumerate(up.bars)}}
    start, end = date(2015, 1, 1), date(2015, 1, 6)
    with_ghost = pr014.book_return(["UP", "GONE"], by_name, index_of, start, end)
    alone = pr014.book_return(["UP"], by_name, index_of, start, end)
    assert with_ghost == alone == Decimal("0.10")


def test_a_name_whose_PRICE_is_unusable_contributes_nothing_either(pr014):
    """The other way a name goes unreadable, and the one a missing-key fixture cannot reach.

    `GONE` above never appears in the index at all. This name is fully present and its start price
    is zero, so the return is undefined rather than absent — a different branch, and mutation
    testing found the first test passed with it deleted.
    """
    up = series("UP", ["100"] * 5 + ["110"])
    dead = series("DEAD", ["0"] * 5 + ["50"])
    by_name = {"UP": up, "DEAD": dead}
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)} for n, s in by_name.items()}
    start, end = date(2015, 1, 1), date(2015, 1, 6)
    assert index_of["DEAD"][start] is not None, "the fixture must be present, not missing"
    assert pr014.book_return(["UP", "DEAD"], by_name, index_of, start, end) == Decimal("0.10")


def test_a_book_of_unreadable_names_returns_none(pr014):
    assert pr014.book_return(["GONE"], {}, {}, date(2015, 1, 1), date(2015, 1, 6)) is None


def test_period_return_refuses_a_backwards_or_missing_window(pr014):
    flat = series("F", ["100"] * 5)
    assert pr014.period_return(flat, 3, 1) is None
    assert pr014.period_return(flat, 0, 99) is None
    assert pr014.period_return(flat, -1, 3) is None


# --- the selection is the card's, and both legs come from one ordering -----------------------------

def test_both_legs_are_the_two_ends_of_one_ranking(pr014):
    """Not two separately-computed lists — the short leg must be the same ordering's tail."""
    class FakeRanker:
        def __call__(self, candidates):
            return sorted(candidates, key=lambda c: c.instrument_id)

    names = [pr014.Candidate(f"N{i:02d}", 0) for i in range(20)]
    top, bottom = pr014.select(FakeRanker(), names, Decimal("0.10"))
    assert top == ["N00", "N01"]
    assert bottom == ["N18", "N19"]


def test_a_cross_section_too_thin_to_fill_a_decile_selects_nothing(pr014):
    class FakeRanker:
        def __call__(self, candidates):
            return list(candidates)

    assert pr014.select(FakeRanker(), [pr014.Candidate("A", 0)], Decimal("0.10")) == ([], [])


def test_the_study_scores_with_the_ratified_inputs(pr014):
    """`PR-014` A-2: 126 and the PATH form, not the 252-session point-to-point every sweep used."""
    from swingdesk.decision_logic.ranking import ByMarketPathStrength

    assert pr014.LOOKBACK == 126
    assert pr014.DECILE == Decimal("0.10")
    assert pr014.ByMarketPathStrength is ByMarketPathStrength


# --- the decision rule, applied by the machine ------------------------------------------------------

def cell(net_excludes_zero: bool, gross: float = 0.16, both_negative: bool = False) -> dict:
    return {
        "net_excludes_zero": net_excludes_zero, "gross_annual": gross,
        "both_negative": both_negative, "net_annual": gross - 0.02,
    }


def row(horizon: int, arm: str, primary: dict, holdout: dict, cost: float = 0.02) -> dict:
    return {"horizon": horizon, "arm": arm, "annual_cost": cost,
            "primary": primary, "holdout": holdout}


def test_the_rule_takes_the_SHORTEST_qualifying_horizon_not_the_biggest(pr014):
    """The one thing a horizon sweep must not do. The 252 cell is richer and must lose."""
    rows = [
        row(126, "long_short", cell(True, gross=0.16), cell(True)),
        row(252, "long_short", cell(True, gross=0.90), cell(True)),
    ]
    out = pr014.decide(rows, Decimal(3))
    assert out["verdict"] == "accept"
    assert out["horizon"] == 126


def test_no_qualifying_horizon_is_a_reject(pr014):
    rows = [row(126, "long_short", cell(False), cell(True))]
    assert pr014.decide(rows, Decimal(3))["verdict"] == "reject"


def test_failing_the_holdout_is_inconclusive_not_a_reject(pr014):
    """Qualifying on primary and failing on holdout is the case the split exists to catch."""
    out = pr014.decide([row(126, "long_short", cell(True), cell(False))], Decimal(3))
    assert out["verdict"] == "inconclusive"
    assert "holdout" in str(out["why"])


def test_a_cell_that_dies_under_tripled_costs_is_inconclusive(pr014):
    """Gross 0.05 against a 0.02 cost tripled to 0.06 is negative, so the arm does not survive."""
    out = pr014.decide(
        [row(126, "long_short", cell(True, gross=0.05), cell(True))], Decimal(3)
    )
    assert out["verdict"] == "inconclusive"
    assert out["stressed_net"] < 0


def test_both_negative_is_inconclusive_however_the_arm_looks(pr014):
    """PREREG_TEMPLATE rule 8: comparing two losers on which loses less is not a finding."""
    out = pr014.decide(
        [row(126, "long_short", cell(True, both_negative=True), cell(True))], Decimal(3)
    )
    assert out["verdict"] == "inconclusive"


def test_two_arms_at_the_shortest_horizon_refuse_rather_than_choose(pr014):
    """§6 names a HORIZON, not an arm. Picking between them after the run is not registered."""
    rows = [
        row(126, "long_only", cell(True, gross=0.20), cell(True)),
        row(126, "long_short", cell(True, gross=0.16), cell(True)),
    ]
    out = pr014.decide(rows, Decimal(3))
    assert out["verdict"] == "inconclusive"
    assert "not registered" in str(out["why"])


def test_the_registered_grid_and_split_are_what_the_prereg_says(pr014):
    """These are the pre-registered constants; drifting them silently would void the study."""
    assert pr014.HORIZONS == (20, 42, 63, 126, 189, 252)
    assert pr014.STEP == 21
    assert pr014.PRIMARY_END == date(2021, 12, 31)
    assert pr014.MIN_REBALANCES == 24
    assert pr014.BOOTSTRAP_SEED == 20260906
    assert pr014.SLIPPAGE_BPS == Decimal("25")
