"""`PR-016`'s statistics, its window guard, and the decision rule that reads two windows.

Five things carry this study and none of them raises an error when wrong:

* **the break-even win rate has to be `1 / (1 + payoff)`.** It is the number that makes a win rate
  readable, and getting it backwards would turn a losing arm into a winning one on the page while
  every other figure stayed correct.
* **the bootstrap has to resample MONTHS, not trades.** Trades opened in the same month share one
  market. An i.i.d. resample over 17,000 trades reports an interval several times too narrow, which
  is the flattering direction, and nothing about the output looks wrong.
* **the difference has to be PAIRED.** Both arms trade the same decade; resampling them
  independently adds the two arms' market variance instead of cancelling it.
* **§6 has to read BOTH windows.** The whole cost of the IIS/OOS split is paid at that line.
* **the window guard has to count SESSIONS.** A calendar minimum of 200 days admits 137 sessions,
  and the owner's instruction was about the size of the sample.

No store, no network.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pr016():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_pr016", REPO / "tools" / "run_pr016.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeTrade:
    """Only the fields `distribution` reads. A real `Trade` would need prices that produce the
    net R being tested, which puts the arithmetic under test into the fixture."""

    def __init__(self, net_r: str, entry: date, reason: str = "stop",
                 mfe: str = "0", mae: str = "0", gap: bool = False) -> None:
        self.net_r = Decimal(net_r)
        self.entry_date = entry
        self.exit_date = entry
        self.instrument_id = "TEST.1"
        self.exit_reason = reason
        self.mfe = Decimal(mfe)
        self.mae = Decimal(mae)
        self.is_gap_loss = gap
        self.holding_days = 20


def trades(values: list[str], entry: date = date(2018, 3, 5)) -> list[FakeTrade]:
    return [FakeTrade(v, entry) for v in values]


# --- the number the whole study turns on ---------------------------------------------------------

def test_the_break_even_win_rate_is_one_over_one_plus_the_payoff_ratio(pr016):
    """Two winners at +1R and two losers at -1R: payoff 1.0, so break-even is 50%."""
    cell = pr016.distribution(trades(["1", "1", "-1", "-1"]))
    assert cell["payoff_ratio"] == pytest.approx(1.0)
    assert cell["break_even_win_rate"] == pytest.approx(0.5)
    assert cell["win_rate"] == pytest.approx(0.5)


def test_a_bigger_average_win_lowers_the_win_rate_the_arm_needs(pr016):
    """+2R winners against -1R losers: payoff 2, so a third of trades winning is break-even. This
    is the mechanism the 1R target changes, and it is why the target is worth a study."""
    cell = pr016.distribution(trades(["2", "2", "-1", "-1"]))
    assert cell["payoff_ratio"] == pytest.approx(2.0)
    assert cell["break_even_win_rate"] == pytest.approx(1 / 3, abs=1e-4)


def test_an_arm_whose_win_rate_sits_at_break_even_has_a_mean_of_zero(pr016):
    """The identity that makes the comparison meaningful rather than decorative."""
    cell = pr016.distribution(trades(["3", "-1", "-1", "-1"]))
    assert cell["mean_net_r"] == pytest.approx(0.0)
    assert cell["win_rate"] == pytest.approx(cell["break_even_win_rate"], abs=1e-4)


def test_a_break_even_trade_counts_as_a_LOSS_not_a_win(pr016):
    """`> 0`, not `>= 0`. A trade that returns exactly zero paid the costs and made nothing."""
    cell = pr016.distribution(trades(["0", "1"]))
    assert cell["win_rate"] == pytest.approx(0.5)


def test_the_tails_are_reported_and_the_skew_has_the_sign_of_the_long_side(pr016):
    values = ["-1"] * 150 + ["4"] * 50
    cell = pr016.distribution(trades(values))
    assert cell["skew"] > 0
    assert cell["worst"] == pytest.approx(-1.0)
    assert cell["best"] == pytest.approx(4.0)
    assert cell["percentiles"]["p5"] == pytest.approx(-1.0)
    assert cell["percentiles"]["p95"] == pytest.approx(4.0)


def test_an_empty_arm_reports_no_trades_rather_than_dividing_by_zero(pr016):
    assert pr016.distribution([]) == {"trades": 0}


# --- the resampling unit -------------------------------------------------------------------------

def test_the_cluster_is_the_entry_month(pr016):
    assert pr016.cluster_of(date(2019, 7, 31)) == "2019-07"
    assert pr016.cluster_of(date(2019, 8, 1)) == "2019-08"


def test_trades_are_grouped_by_the_month_they_were_ENTERED(pr016):
    grouped = pr016.by_month([
        FakeTrade("1", date(2019, 7, 3)), FakeTrade("-1", date(2019, 7, 29)),
        FakeTrade("2", date(2019, 8, 1)),
    ])
    assert sorted(grouped) == ["2019-07", "2019-08"]
    assert len(grouped["2019-07"]) == 2


def test_the_bootstrap_interval_widens_when_the_months_disagree(pr016):
    """The mutation this test exists for: resampling TRADES instead of months. Two months that
    each hold twenty identical trades carry two independent observations, not forty."""
    agree = [[Decimal("1")] * 20 for _ in range(24)]
    disagree = [[Decimal("1")] * 20 if i % 2 else [Decimal("-1")] * 20 for i in range(24)]
    tight = pr016.block_bootstrap(agree, "mean", 3, 1, 500)
    loose = pr016.block_bootstrap(disagree, "mean", 3, 1, 500)
    assert tight[2] - tight[1] == pytest.approx(0.0)
    assert loose[2] - loose[1] > 0.3


def test_the_bootstrap_reports_the_observed_statistic_not_a_resample_mean(pr016):
    clusters = [[Decimal("1"), Decimal("-1")] for _ in range(24)]
    observed, low, high = pr016.block_bootstrap(clusters, "mean", 3, 1, 200)
    assert observed == pytest.approx(0.0)
    assert low <= observed <= high


def test_the_win_rate_statistic_is_a_ratio_over_pooled_trades(pr016):
    clusters = [[Decimal("1"), Decimal("1"), Decimal("-1")] for _ in range(24)]
    observed, _, _ = pr016.block_bootstrap(clusters, "win_rate", 3, 1, 200)
    assert observed == pytest.approx(2 / 3)


def test_an_unknown_statistic_is_refused_rather_than_silently_averaged(pr016):
    with pytest.raises(ValueError, match="unknown statistic"):
        pr016.block_bootstrap([[Decimal("1")], [Decimal("1")]], "sharpe", 1, 1, 10)


def test_a_single_month_cannot_be_bootstrapped(pr016):
    assert pr016.block_bootstrap([[Decimal("1")]], "mean", 3, 1, 100) is None


# --- the paired difference -----------------------------------------------------------------------

def test_the_difference_is_computed_on_months_BOTH_arms_traded(pr016):
    """A month the ranked arm never entered cannot contribute to the comparison — it would be
    comparing the control against nothing and calling the gap an effect."""
    left = {f"2019-{m:02d}": [Decimal("1")] for m in range(1, 13)}
    right = dict(left)
    right.pop("2019-06")
    observed, _, _ = pr016.paired_difference(left, right, "mean")
    assert observed == pytest.approx(0.0)


def test_a_constant_advantage_survives_the_pairing_with_a_tight_interval(pr016):
    """The mutation: resampling the two arms independently. Here every month has the ranked arm
    exactly 0.5R ahead, so a PAIRED interval collapses onto 0.5 and an unpaired one does not."""
    months = [f"20{y:02d}-{m:02d}" for y in range(16, 20) for m in range(1, 13)]
    left = {m: [Decimal("1.5")] for m in months}
    right = {m: [Decimal("1.0")] for m in months}
    observed, low, high = pr016.paired_difference(left, right, "mean")
    assert observed == pytest.approx(0.5)
    assert high - low == pytest.approx(0.0)


def test_fewer_than_two_shared_months_yields_no_difference(pr016):
    assert pr016.paired_difference({"2019-01": [Decimal("1")]}, {"2019-01": [Decimal("1")]},
                                   "mean") is None


# --- section 6 -----------------------------------------------------------------------------------

def cells(low_in: float, high_in: float, low_out: float, high_out: float,
          trades_n: int = 5000, months: int = 60) -> dict:
    def cell(low: float, high: float) -> dict:
        return {"trades": trades_n, "months": months,
                "difference_mean": {"observed": (low + high) / 2, "low": low, "high": high}}
    return {"in_sample": cell(low_in, high_in), "out_of_sample": cell(low_out, high_out)}


def test_both_windows_must_exclude_zero_for_an_accept(pr016):
    assert pr016.verdict_for(cells(0.02, 0.10, 0.03, 0.11)) == "accept"


def test_a_window_containing_zero_is_inconclusive_however_good_the_other(pr016):
    """The mutation this test exists for: reading only the in-sample window. The whole cost of the
    split is paid here."""
    assert pr016.verdict_for(cells(0.02, 0.10, -0.02, 0.06)) == "inconclusive"


def test_both_windows_below_zero_is_a_REJECT(pr016):
    """`PREREG_TEMPLATE` rule 8's both-negative branch. A selection rule that reliably loses to no
    selection at all is a finding, not an absence of one."""
    assert pr016.verdict_for(cells(-0.12, -0.02, -0.15, -0.03)) == "reject"


def test_a_thin_window_cannot_qualify_however_wide_its_interval_excludes_zero(pr016):
    assert pr016.verdict_for(cells(0.02, 0.10, 0.03, 0.11, trades_n=12)) == "inconclusive"


def test_too_few_months_cannot_qualify_even_with_enough_trades(pr016):
    """Trades are not the sample; months are. A hundred thousand trades in six months is six
    observations of one market."""
    assert pr016.verdict_for(cells(0.02, 0.10, 0.03, 0.11, months=6)) == "inconclusive"


def test_an_interval_wider_than_the_power_floor_is_inconclusive_even_when_it_excludes_zero(pr016):
    """§8's floor, registered before any number existed. A positive reading off an instrument this
    blunt is not evidence, and neither is a null."""
    assert pr016.verdict_for(cells(0.01, 0.60, 0.02, 0.61)) == "inconclusive"
    assert pr016.underpowered(cells(0.01, 0.60, 0, 0)["in_sample"])


def test_a_cell_with_no_difference_at_all_is_underpowered_rather_than_powered(pr016):
    assert pr016.underpowered({"trades": 5000, "months": 60})


# --- the window guard ----------------------------------------------------------------------------

def test_the_registered_minimum_is_counted_in_SESSIONS(pr016):
    """Owner instruction, and the unit is the point: 200 calendar days hold about 137 sessions."""
    assert pr016.MIN_SESSIONS_BETWEEN == 200
    calendar = [date(2019, 1, 1) + __import__("datetime").timedelta(days=i) for i in range(400)]
    assert len(pr016.window_sessions(calendar, date(2019, 1, 1), date(2019, 7, 19))) == 200


def test_the_window_is_inclusive_of_both_endpoints(pr016):
    calendar = [date(2019, 1, d) for d in range(1, 11)]
    assert pr016.window_sessions(calendar, date(2019, 1, 3), date(2019, 1, 5)) == [
        date(2019, 1, 3), date(2019, 1, 4), date(2019, 1, 5)
    ]


# --- the trigger ---------------------------------------------------------------------------------

def test_the_trigger_fires_only_on_the_chosen_sessions(pr016):
    """It never reads the series beyond the bar it was handed, which is what keeps the engine's
    look-ahead guarantee intact for an injected rule."""
    class Fake:
        def __init__(self) -> None:
            self.bars = [type("B", (), {"session_date": date(2019, 1, d)})() for d in range(1, 6)]

    trigger = pr016.OnDates(frozenset({date(2019, 1, 2), date(2019, 1, 4)}))
    assert [trigger(Fake(), i) for i in range(5)] == [False, True, False, True, False]


def test_the_trigger_records_what_it_ran(pr016):
    """A dataclass rather than a closure, so the study can print the rule it executed."""
    assert "datetime.date(2019, 1, 2)" in repr(pr016.OnDates(frozenset({date(2019, 1, 2)})))


# --- the ratified exit is the one being simulated ------------------------------------------------

def test_the_study_pins_the_ratified_exit_and_not_a_variant(pr016):
    """These four are registry values. A study that quietly ran a different stop or a different
    target would answer a question nobody asked, and every number would still look fine."""
    assert pr016.STOP_MULTIPLE == Decimal("2.0")     # exit.atr_stop_multiple, DR-012
    assert pr016.TARGET_R == Decimal("1.0")          # exit.target_r_multiple, DR-029
    assert pr016.HOLD == 20                          # exit.max_holding_period, DR-012
    assert pr016.ATR_PERIOD == 14                    # atr.period
    assert pr016.LOOKBACK == 126                     # rs.lookback, DR-030


def test_the_split_boundary_is_inherited_and_not_chosen_here(pr016):
    """`PR-014` and `PR-015` both end their primary window here. A boundary chosen today would be
    one chosen after seeing this data."""
    assert pr016.PRIMARY_END == date(2021, 12, 31)


# --- the window the study MEASURED, not the one it was asked for ---------------------------------
#
# Found 2026-09-07 by an arithmetic check: the run reported 113 formation dates where 2,522 sessions
# at a 20-session step should give 126. The missing 13 are 260 sessions - the history floor, charged
# a second time against the benchmark's calendar after `DR-003`'s `min_history` had already charged
# it against every instrument. The header window would still have read `2016-01-04 .. 2026-09-04`,
# and the owner asked for at least ten years.

def test_the_benchmark_gate_is_the_rankers_lookback_and_not_the_instrument_floor(pr016) -> None:
    """The constant this defect was. `HISTORY` is what an INSTRUMENT needs and `DR-003` already
    enforces it per name per date; the benchmark needs `rs.lookback` and no more. Charging 252
    twice costs a year of sample and nothing notices."""
    assert pr016.LOOKBACK < pr016.HISTORY
    assert pr016.LOOKBACK == 126


def test_the_instrument_floor_is_still_enforced_where_it_belongs(pr016) -> None:
    """Relaxing the benchmark gate must not relax the per-name one, or the two arms stop drawing
    from one pool. `DR-003`'s rule carries it."""
    assert pr016.RULE.min_history >= 250
    assert pr016.HISTORY == 252


# --- the reduction that makes the bootstrap finish -----------------------------------------------
#
# `totals_for` reduces a month to `(numerator, count)` so a resample never touches a trade. The
# first cut of this file pooled the trades on every resample: ~200,000 trades x 10,000 resamples x
# 66 runs. Found 2026-09-07 by watching a run reach that phase and stop producing output.
#
# A performance refactor of a statistic is the one refactor that can silently change a result, so
# the test is EQUIVALENCE against the naive form rather than a timing.

def _pooled(clusters: list[list[Decimal]], statistic: str) -> float:
    """The naive version this replaced, kept here as the oracle."""
    pool = [v for c in clusters for v in c]
    if statistic == "mean":
        return float(sum(pool) / len(pool))
    return sum(1 for v in pool if v > 0) / len(pool)


@pytest.mark.parametrize("statistic", ["mean", "win_rate"])
def test_the_reduction_gives_the_same_answer_as_pooling_the_trades(pr016, statistic: str) -> None:
    """Uneven months on purpose: if the reduction averaged the MONTHS instead of summing their
    parts, equal-sized fixtures would hide it and a month with one trade would count as much as a
    month with a thousand."""
    clusters = [
        [Decimal("1.5")] * 100,
        [Decimal("-1")],
        [Decimal("0.25"), Decimal("-2"), Decimal("3")] * 7,
        [Decimal("-1")] * 40,
    ]
    observed, _, _ = pr016.block_bootstrap(clusters, statistic, 2, 1, 50)
    assert observed == pytest.approx(_pooled(clusters, statistic))


def test_the_reduction_weights_a_month_by_how_many_trades_it_holds(pr016) -> None:
    """One month with 99 losers and one with a single winner is not 50/50."""
    clusters = [[Decimal("-1")] * 99, [Decimal("1")]]
    numerator, count = pr016.totals_for(clusters[0], "win_rate")
    assert (numerator, count) == (0.0, 99)
    observed, _, _ = pr016.block_bootstrap(clusters, "win_rate", 1, 1, 50)
    assert observed == pytest.approx(0.01)


def test_an_unknown_statistic_is_still_refused_inside_the_reduction(pr016) -> None:
    with pytest.raises(ValueError, match="unknown statistic"):
        pr016.totals_for([Decimal("1")], "sharpe")


def test_the_qa_sample_is_stratified_so_the_control_cannot_swamp_the_hypothesis(pr016) -> None:
    """`BACKTEST_PROTOCOL` §7. Drawing at random from the pooled set would return almost nothing
    but the control, which carries two orders of magnitude more trades - and a QA pass that never
    re-checks the ranked arm has not re-checked the study."""
    assert pr016.QA_SAMPLE_PER_ARM > 0
    assert pr016.QA_SEED == 20260908
    assert "arm" in pr016.TRADE_COLUMNS
    assert "net_r" in pr016.TRADE_COLUMNS
