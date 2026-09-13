"""`PR-020` - the selected decile held with no stop, against its own universe over the same days.

What carries it, each failing silently if wrong:

* **the candidate is the registered hold with NO protective stop**, priced in the same 2 ATR R as
  every `PR-019` cell, or `trade - pool` is in different units from everything it is compared with;
* **the partner binds `PR-019`'s common entry set**, or §9 cannot reproduce `PR-019` to the digit;
* **the pool's slippage is charged on both fills and in the trade's R**;
* **§9 compares exactly the committed fields**, and says when it had nothing to compare.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def study():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_run_pr020", REPO / "tools" / "run_pr020.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_candidate_is_the_registered_hold_with_no_stop_in_pr019s_units(study):
    from power_pr019 import R_DENOMINATOR_MULTIPLE

    policy = study.CANDIDATE
    assert study.CELL == f"h{study.READ_HOLD}_stopnone"
    assert policy.max_holding_bars == study.READ_HOLD
    assert policy.protective is False and policy.target_r_multiple is None
    assert policy.atr_stop_multiple == R_DENOMINATOR_MULTIPLE


def test_the_partner_is_the_cell_that_bound_pr019s_common_entries(study):
    """Read from the committed result: the partner dropped nothing, and the no-stop cells dropped
    exactly what it refused - which is what makes the intersection reproduce `PR-019`."""
    committed = json.loads((REPO / "docs" / "prereg" / "results" / "PR-019.json")
                           .read_text(encoding="utf-8"))
    dropped = committed["entries"]["dropped_to_common_entries"]
    assert dropped[study.PARTNER] == 0
    assert dropped["h60_stopnone"] == dropped["h10_stopnone"] == max(dropped.values())


def test_the_pool_is_slipped_on_both_fills_in_the_trades_own_r(study):
    trade = SimpleNamespace(entry_price=Decimal(100), initial_risk_per_share=Decimal(10))
    side = float(study.SLIPPAGE_BPS) / 10_000
    assert study.pool_slipped(0.0, trade) == pytest.approx(((1 - side) / (1 + side) - 1) * 10)
    assert study.pool_slipped(1.0, trade) < 1.0, "slippage only ever costs"


def test_the_primary_difference_is_against_the_pool_charged_the_same_slippage(study, monkeypatch):
    """Decided before the run: a free pool at 5 sessions would read the trade's round trip as the
    screen's verdict. `difference` must be trade minus the COSTED pool; the free pool is only the
    `pool_zero_cost` perturbation."""
    monkeypatch.setattr(sys.modules["run_pr019b"], "BOOTSTRAP_RESAMPLES", 200)
    monkeypatch.setattr(study, "own", lambda trades: {})
    monkeypatch.setattr(study, "mae_profile", lambda trades: {})
    rows = [(date(2022, 1 + m % 12, 3) if m < 12 else date(2023, 1 + m % 12, 3),
             0.10 + 0.01 * (m % 5), 0.02 + 0.001 * m, -0.08 + 0.001 * m, 0.03)
            for m in range(24)]
    got = study.cell([object()], rows)
    assert got["difference"] == study.interval([(r[0], r[1] - r[3]) for r in rows])
    assert got["difference_pool_zero_cost"] == study.interval([(r[0], r[1] - r[2]) for r in rows])
    assert got["market_mean"] == study.interval([(r[0], r[3]) for r in rows])
    assert got["difference"]["observed"] > got["difference_pool_zero_cost"]["observed"]


def test_a_missing_reference_is_said_not_passed(study, tmp_path):
    assert study.reproduction({}, tmp_path / "absent.json") == {
        "reference": str(tmp_path / "absent.json"), "available": False}


def _result(study, partner_mean: float, cell_mean: float) -> dict:
    block = {"trades": 10, "mean_interval": {"low": -0.1, "high": 0.1}}
    return {"partner": {w: {**block, "mean_net_r": partner_mean}
                        for w in ("in_sample", "out_of_sample")},
            "cells": {w: {study.CELL: {**block, "mean_net_r": cell_mean}}
                      for w in ("in_sample", "out_of_sample")}}


def test_section_9_compares_the_partner_and_the_candidate_when_pr019_ran_it(study, tmp_path,
                                                                            monkeypatch):
    monkeypatch.setattr(study, "CELL", "h10_stopnone")
    reference = tmp_path / "PR-019.json"
    block = {"trades": 10, "mean_interval": {"low": -0.1, "high": 0.1}}
    reference.write_text(json.dumps({"cells": {w: {
        study.PARTNER: {**block, "mean_net_r": 0.05}, "h10_stopnone": {**block, "mean_net_r": -0.03},
    } for w in ("in_sample", "out_of_sample")}}), encoding="utf-8")

    same = study.reproduction(_result(study, 0.05, -0.03), reference)
    assert same["every_digit"] is True and len(same["checks"]) == 4
    off = study.reproduction(_result(study, 0.05, -0.0301), reference)
    assert off["every_digit"] is False, "one digit on the candidate is a defect in the runner"
    widened = _result(study, 0.05, -0.03)
    widened["partner"]["out_of_sample"]["mean_interval"] = {"low": -0.1, "high": 0.1001}
    assert study.reproduction(widened, reference)["every_digit"] is False, (
        "the interval is a committed field too - a mean can match on a different bootstrap")


def test_a_candidate_pr019_never_ran_is_skipped_not_failed(study, tmp_path, monkeypatch):
    monkeypatch.setattr(study, "CELL", "h5_stopnone")
    reference = tmp_path / "PR-019.json"
    block = {"trades": 10, "mean_interval": {"low": -0.1, "high": 0.1}, "mean_net_r": 0.05}
    reference.write_text(json.dumps({"cells": {w: {study.PARTNER: block}
                                               for w in ("in_sample", "out_of_sample")}}),
                         encoding="utf-8")
    got = study.reproduction(_result(study, 0.05, 0.9), reference)
    assert got["every_digit"] is True
    assert {c["cell"] for c in got["checks"]} == {study.PARTNER}


def test_a_run_on_a_synthetic_store_reads_the_registered_cell_by_the_registered_rule(
        study, tmp_path, monkeypatch):
    """End to end, streamed: both windows, the partner, the null's check, and the verdict formed by
    `run_pr019b.verdict_for` on the out-of-sample candidate - and nothing else."""
    spec = importlib.util.spec_from_file_location("_t19b", REPO / "tests" / "test_run_pr019b.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    helpers._synthetic_store(tmp_path)
    monkeypatch.setattr(study, "BOOTSTRAP_RESAMPLES", 200)
    monkeypatch.setattr(sys.modules["run_pr019b"], "BOOTSTRAP_RESAMPLES", 200)

    result = study.build(argparse.Namespace(data=tmp_path, as_of="2022-07-01T12:00:00+00:00",
                                            reference=tmp_path / "absent.json"))

    assert set(result["cells"]) == {"in_sample", "out_of_sample"} == set(result["partner"])
    assert result["cells"]["in_sample"][study.CELL].get("trades", 0) > 0, "the fixture must trade"
    assert result["null_check"]["in_sample"][f"unselected_{study.CELL}"].get("trades", 0) > 0
    assert result["verdict"] == study.verdict_for(result["cells"]["out_of_sample"][study.CELL])
    assert result["reproduction"]["available"] is False
    realised = result["entries"]["realised_before_restriction"]
    dropped = result["entries"]["dropped_to_common_entries"]
    assert realised[study.CELL] - dropped[study.CELL] == (
        realised[study.PARTNER] - dropped[study.PARTNER]), "one entry set after the intersection"
    first = result["measured_span"]["first_entry"]
    assert date.fromisoformat(first) >= date(2020, 6, 1)
