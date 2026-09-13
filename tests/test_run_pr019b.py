"""`PR-019b`'s decision logic and its null - the arithmetic that decides whether a candidate is the market.

Three things carry it, and each fails silently:

* **the benchmark leg is priced in the trade's own R**, over exactly the trade's sessions. Get the
  scale wrong and the difference is a number with no unit; get the sessions wrong and it is the
  wrong market.
* **the difference is formed per trade before it is resampled**, so the pairing is exact by
  construction. A trade and a market leg that are equal must read a difference of exactly zero.
* **the verdict reads the candidate out of sample with six outcomes registered before the run**,
  and two of them - `both_negative` and `null` - exist because earlier studies paid for their
  absence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import statistics
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "docs" / "prereg" / "results"


@pytest.fixture(scope="module")
def study():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_run_pr019b", REPO / "tools" / "run_pr019b.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _trade(entry_price: str = "50", risk: str = "5", entry: date = date(2023, 3, 1),
           exit_: date = date(2023, 5, 1), net_r: str = "0.3") -> SimpleNamespace:
    """What the null reads of a trade, and nothing else."""
    return SimpleNamespace(entry_date=entry, exit_date=exit_, entry_price=Decimal(entry_price),
                           initial_risk_per_share=Decimal(risk), net_r=Decimal(net_r))


OPENS = {date(2023, 3, 1): Decimal("400")}
CLOSES = {date(2023, 5, 1): Decimal("404")}


def _cell(*, trades: int = 5000, months: int = 54, diff: tuple[float, float] = (-0.05, 0.05),
          own: tuple[float, float] = (-0.10, 0.20),
          market: tuple[float, float] = (0.0, 0.3)) -> dict[str, Any]:
    return {"trades": trades, "months": months,
            "difference": {"observed": sum(diff) / 2, "low": diff[0], "high": diff[1]},
            "mean_interval": {"low": own[0], "high": own[1]},
            "market_mean": {"observed": sum(market) / 2, "low": market[0], "high": market[1]}}


# --- the candidate is PR-019's, and nothing here chooses it -----------------------------------------


def test_the_cell_is_the_one_pr019_selected_in_sample(study):
    committed = json.loads((RESULTS / "PR-019.json").read_text(encoding="utf-8"))
    assert committed["selected_in_sample"] == study.CELL


def test_the_candidate_policy_is_pr019s_grid_cell_exactly(study):
    from power_pr019 import cells

    grid = cells()[study.CELL]
    assert study.CANDIDATE.atr_stop_multiple == grid.atr_stop_multiple == Decimal("4.0")
    assert study.CANDIDATE.max_holding_bars == grid.max_holding_bars == 60
    assert study.CANDIDATE.target_r_multiple is None and grid.target_r_multiple is None


def test_the_minimum_detectable_effect_is_the_committed_power_estimate(study):
    power = json.loads((RESULTS / "PR-019b-power.json").read_text(encoding="utf-8"))
    predicted = power["dispersion"]["trade_minus_benchmark"]["half_width_predicted_oos"]
    assert study.MINIMUM_DETECTABLE_EFFECT == Decimal(f"{predicted:.4f}")


def test_the_committed_power_estimate_carries_no_level(study):
    """It was written before the registration; if it reported a level, the registration would have
    been written by someone who had seen the answer."""
    from power_pr019 import assert_no_effect_leaked

    assert_no_effect_leaked(json.loads((RESULTS / "PR-019b-power.json").read_text(encoding="utf-8")))


def test_every_registered_perturbation_is_run(study):
    assert study.PERTURBATIONS["registered"] == study.PERTURBATIONS["run"]


# --- the null's arithmetic ---------------------------------------------------------------------------


def test_the_benchmark_leg_is_the_index_return_scaled_into_the_trades_R(study):
    """1% on the index, on a trade whose risk is a tenth of its price, is 0.1R."""
    assert study.market_r(_trade(), OPENS, CLOSES) == pytest.approx(0.1)


def test_a_wider_stop_shrinks_the_benchmark_leg_in_R(study):
    """The same notional over a risk twice as large is half the R - the unit is the trade's."""
    assert study.market_r(_trade(risk="10"), OPENS, CLOSES) == pytest.approx(0.05)


def test_the_benchmark_leg_runs_from_the_entry_open_to_the_exit_close(study):
    opens = {**OPENS, date(2023, 5, 1): Decimal("1")}
    closes = {**CLOSES, date(2023, 3, 1): Decimal("1")}
    assert study.market_r(_trade(), opens, closes) == pytest.approx(0.1)


def test_uncharged_costs_reproduce_the_primary_leg(study):
    costed = study.market_r_costed(_trade(), OPENS, CLOSES, Decimal("0"), Decimal("0"))
    assert costed == pytest.approx(study.market_r(_trade(), OPENS, CLOSES))


def test_the_costed_leg_pays_slippage_on_both_fills_and_commission_on_both_sides(study):
    """Bought at 401 (400 + 25bps), sold at 402.99 (404 - 25bps), and a half-cent a share twice on
    N / 401 shares: (402.99 - 401 - 0.01) / 401 per unit of notional, times entry / risk = 10."""
    costed = study.market_r_costed(_trade(), OPENS, CLOSES, Decimal("25"), Decimal("0.005"))
    assert costed == pytest.approx(1.98 / 401 * 10)


def test_a_missing_benchmark_price_is_counted_not_dropped(study):
    trades = [_trade(), _trade(exit_=date(2023, 6, 1))]
    paired, unpriced = study.pair(trades, OPENS, CLOSES)
    assert len(paired) == 1 and unpriced == 1
    assert paired[0].trade_r == pytest.approx(0.3) and paired[0].market_r == pytest.approx(0.1)


def test_the_paired_leg_is_charged_at_the_studys_own_cost_model(study):
    paired, _ = study.pair([_trade()], OPENS, CLOSES)
    expected = study.market_r_costed(_trade(), OPENS, CLOSES, study.SLIPPAGE_BPS,
                                     study.COMMISSION_PER_SHARE)
    assert paired[0].market_r_costed == pytest.approx(expected)
    assert paired[0].market_r_costed < paired[0].market_r


# --- the statistic ---------------------------------------------------------------------------------


def test_values_are_clustered_by_entry_month_in_month_order(study):
    rows = [(date(2023, 2, 3), 1.0), (date(2023, 1, 9), 2.0), (date(2023, 2, 20), 3.0)]
    assert study.monthly(rows) == [[Decimal("2.0")], [Decimal("1.0"), Decimal("3.0")]]


def test_a_trade_equal_to_its_market_leg_reads_a_difference_of_exactly_zero(study):
    """The pairing is per trade: however much the months differ from each other, a difference
    formed before resampling cannot pick that variance up."""
    paired = [study.Paired(date(2022, 1 + m % 12, 3), v, v, v)
              for m, v in enumerate([0.9, -1.4, 2.2, -0.3, 1.1, -2.0, 0.5, 0.7])]
    difference = study.interval([(p.entry_date, p.trade_r - p.market_r) for p in paired])
    assert difference == {"observed": 0.0, "low": 0.0, "high": 0.0}


def test_the_interval_brackets_the_observed_mean(study):
    rows = [(date(2022, 1 + m % 12, 1 + m // 12), 0.1 * ((m * 7) % 5 - 2)) for m in range(36)]
    got = study.interval(rows)
    assert got["low"] <= got["observed"] <= got["high"]


def _book(study, months: int = 30) -> tuple[list[SimpleNamespace], list[Any]]:
    """A month of one trade each, every market leg 0.1R plain and 0.08R costed."""
    trades, paired = [], []
    for m in range(months):
        entry = date(2022 + m // 12, 1 + m % 12, 5)
        net = 0.05 * ((m * 7) % 5 - 1)
        trades.append(SimpleNamespace(
            instrument_id=f"N{m % 4}", entry_date=entry, exit_date=entry, net_r=Decimal(repr(net)),
            mfe=Decimal("1"), mae=Decimal("-0.5"), is_gap_loss=False, exit_reason="TIME",
            holding_days=60))
        paired.append(study.Paired(entry, net, 0.1, 0.08))
    return trades, paired


def test_the_summary_differences_each_trade_against_its_own_market_leg(study):
    trades, paired = _book(study)
    got = study.summarise(trades, paired)
    mean = statistics.fmean(p.trade_r for p in paired)
    assert got["market_mean"]["observed"] == pytest.approx(0.1)
    assert got["market_mean_costed"]["observed"] == pytest.approx(0.08)
    assert got["difference"]["observed"] == pytest.approx(round(mean - 0.1, 4))
    assert got["difference_benchmark_costed"]["observed"] == pytest.approx(round(mean - 0.08, 4))
    assert "difference_stress_3x" not in got
    assert (got["trades"], got["months"], got["paired_trades"]) == (30, 30, 30)


def test_the_stress_difference_is_read_from_the_stressed_book(study):
    trades, paired = _book(study)
    stressed = [study.Paired(p.entry_date, p.trade_r - 0.2, p.market_r, p.market_r_costed)
                for p in paired]
    got = study.summarise(trades, paired, stressed)
    assert got["difference_stress_3x"]["observed"] == pytest.approx(
        got["difference"]["observed"] - 0.2, abs=1e-4)


# --- the verdict: six branches, in order -----------------------------------------------------------


def test_too_few_trades_refuses_the_window(study):
    assert study.verdict_for(_cell(trades=199, diff=(0.02, 0.10))) == "refused"


def test_too_few_months_refuses_the_window(study):
    assert study.verdict_for(_cell(months=23, diff=(0.02, 0.10))) == "refused"


def test_the_sample_rule_is_met_at_exactly_its_minimum(study):
    assert study.verdict_for(_cell(trades=200, months=24, diff=(0.02, 0.10))) == "accept"


def test_an_interval_wider_than_the_floor_is_inconclusive_whatever_its_sign(study):
    assert study.verdict_for(_cell(diff=(0.01, 0.17))) == "inconclusive"
    assert study.verdict_for(_cell(diff=(-0.17, -0.01))) == "inconclusive"


def test_an_interval_exactly_the_floor_wide_is_read(study):
    assert study.verdict_for(_cell(diff=(0.01, 0.16))) == "accept"


def test_no_difference_interval_is_underpowered(study):
    cell = _cell()
    del cell["difference"]
    assert study.verdict_for(cell) == "inconclusive"


def test_above_zero_is_accept(study):
    assert study.verdict_for(_cell(diff=(0.01, 0.12))) == "accept"


def test_below_zero_is_reject_the_market_beat_it(study):
    assert study.verdict_for(_cell(diff=(-0.12, -0.01))) == "reject"


def test_containing_zero_inside_the_floor_is_null_the_candidate_is_the_market(study):
    assert study.verdict_for(_cell(diff=(-0.06, 0.06))) == "null"


def test_an_interval_touching_zero_is_null_not_accept(study):
    assert study.verdict_for(_cell(diff=(0.0, 0.12))) == "null"
    assert study.verdict_for(_cell(diff=(-0.12, 0.0))) == "null"


def test_two_losers_are_both_negative_before_any_difference_is_read(study):
    """Rule 8: a trade losing money against an index losing more is not a finding."""
    losing = _cell(diff=(0.01, 0.12), own=(-0.3, -0.05), market=(-0.5, -0.1))
    assert study.verdict_for(losing) == "both_negative"


def test_a_losing_trade_against_a_rising_market_is_not_both_negative(study):
    assert study.verdict_for(_cell(diff=(-0.12, -0.01), own=(-0.3, -0.05))) == "reject"


def test_a_losing_market_against_a_trade_that_may_earn_is_not_both_negative(study):
    assert study.verdict_for(_cell(diff=(0.01, 0.12), market=(-0.5, -0.1))) == "accept"


# --- §9 ------------------------------------------------------------------------------------------


def _committed(study) -> dict[str, Any]:
    return {
        "cells": {w: {study.CELL: {"trades": 10, "mean_net_r": 0.1,
                                   "mean_interval": {"low": -0.1, "high": 0.3}}}
                  for w in ("in_sample", "out_of_sample")},
        "unselected": {w: {study.CELL: {"trades": 90, "mean_net_r": 0.02}}
                       for w in ("in_sample", "out_of_sample")},
    }


def test_the_reproduction_passes_only_on_every_digit(study, tmp_path):
    reference = tmp_path / "PR-019.json"
    reference.write_text(json.dumps(_committed(study)), encoding="utf-8")
    assert study.reproduction(_committed(study), reference)["every_digit"] is True


@pytest.mark.parametrize("group,field,value", [
    ("cells", "mean_net_r", 0.1001),
    ("cells", "trades", 11),
    ("cells", "mean_interval", {"low": -0.1, "high": 0.3001}),
    ("unselected", "mean_net_r", 0.0201),
])
def test_the_reproduction_flags_any_difference(study, tmp_path, group, field, value):
    reference = tmp_path / "PR-019.json"
    reference.write_text(json.dumps(_committed(study)), encoding="utf-8")
    ours = _committed(study)
    ours[group]["out_of_sample"][study.CELL][field] = value
    got = study.reproduction(ours, reference)
    assert got["every_digit"] is False
    assert [(r["group"], r["window"]) for r in got["checks"] if not r["match"]] == [
        (group, "out_of_sample")]


def test_a_missing_reference_is_said_not_passed(study, tmp_path):
    assert study.reproduction({}, tmp_path / "absent.json") == {
        "reference": str(tmp_path / "absent.json"), "available": False}


# --- loader phase A: the streamed path must be the same study ------------------------------------


def _synthetic_store(root: Path, names: int = 105) -> None:
    """Random walks, liquid enough to admit and long enough for the lookback. Noise, not an answer:
    the test compares two ways of computing one study, never what the study says."""
    from swingdesk.contracts.market import Bar, Interval, Series
    from swingdesk.market_data import BarStore

    known = datetime(2022, 7, 1, 12, 0, tzinfo=UTC)
    days = [d for d in (date(2020, 6, 1) + timedelta(days=i) for i in range(760))
            if d.weekday() < 5]
    rng = random.Random(20260913)
    cents = Decimal("0.01")
    with BarStore(root / "bars.duckdb") as store:
        for name in ["SPY"] + [f"SYN{i:03d}" for i in range(names)]:
            price = rng.uniform(40, 200)
            vol = 0.011 if name == "SPY" else rng.uniform(0.008, 0.03)
            drift = rng.gauss(0.0003, 0.0004)
            bars = []
            for day in days:
                open_ = price * (1 + rng.gauss(0, vol / 3))
                close = open_ * (1 + rng.gauss(drift, vol))
                high = max(open_, close) * (1 + abs(rng.gauss(0, vol / 2)))
                low = min(open_, close) * (1 - abs(rng.gauss(0, vol / 2)))
                bars.append(Bar(
                    instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                    event_time=datetime.combine(day, time(14, 30), tzinfo=UTC), session_date=day,
                    open=Decimal(str(open_)).quantize(cents), high=Decimal(str(high)).quantize(cents),
                    low=Decimal(str(low)).quantize(cents), close=Decimal(str(close)).quantize(cents),
                    volume=rng.randint(800_000, 5_000_000), knowledge_time=known))
                price = close
            store.write(bars, known)


def test_the_streamed_loader_is_the_same_study(study, tmp_path, monkeypatch):
    """Loader phase A. `PR-019b` peaked at 22.4 GB holding every series at once; `--streamed` holds
    one. That is worth nothing unless it computes the same study, so every field a verdict or a
    reproduction reads must come out identical - not close - to the in-memory run's."""
    monkeypatch.setattr(study, "BOOTSTRAP_RESAMPLES", 200)
    _synthetic_store(tmp_path)
    runs = {streamed: study.build(argparse.Namespace(
        data=tmp_path, as_of=None, reference=tmp_path / "absent.json", streamed=streamed))
        for streamed in (False, True)}
    memory, streamed = runs[False], runs[True]

    assert memory["cells"]["in_sample"][study.CELL].get("trades", 0) > 0, "the fixture must trade"
    assert memory["entries"]["selected_signals"] > 0
    for key in ("instruments", "formation_dates", "formations_skipped_for_a_thin_cross_section",
                "entries", "trades_without_a_benchmark_price", "cells", "unselected",
                "measured_span", "verdict"):
        assert streamed[key] == memory[key], key
    assert streamed["loader"].startswith("streamed") and "loader" not in memory
