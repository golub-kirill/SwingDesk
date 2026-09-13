"""The power estimate a re-registration of `PR-020` needs - two constructions, dispersion only.

What carries it, each failing silently if wrong:

* **the floor is the owner's** - the study constant must equal the registry's
  `risk.min_stop_distance_fraction`, or A sizes a rule the live book does not run;
* **ATR and bars align by index**, warm-up skipped, or the ratio belongs to the wrong session;
* **pool membership is read at the PREVIOUS close** - today's ratio would be a look ahead;
* **B divides by `entry / risk`**, so no trade is weighted by it at all;
* **no level leaks** into the payload, or choosing the construction could choose the answer.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def power():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_power_pr020b",
                                                  REPO / "tools" / "power_pr020b.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _series(closes: list[str], start: date = date(2021, 1, 4), name: str = "T"):
    from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

    known = datetime(2021, 6, 1, tzinfo=UTC)
    days = [d for d in (start + timedelta(days=i) for i in range(len(closes) * 2))
            if d.weekday() < 5][:len(closes)]
    bars = tuple(Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                     event_time=datetime.combine(d, time(14, 30), tzinfo=UTC), session_date=d,
                     open=Decimal(c), high=Decimal(c) + 1, low=Decimal(c) - 1, close=Decimal(c),
                     volume=1_000_000, knowledge_time=known)
                 for d, c in zip(days, closes, strict=True))
    return BarSeries(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=known, bars=bars)


def test_the_floored_pool_leaves_out_a_member_under_the_floor(power):
    """B jumps 20% on the third session; it is under the floor, so only the full pool sees it."""
    a = _series(["100", "101", "103"], name="A")
    b = _series(["50", "50", "60"], name="B")
    d0, d1, d2 = (bar.session_date for bar in a.bars)
    over = {d: Decimal("0.02") for d in (d0, d1, d2)}
    under = {d: Decimal("0.001") for d in (d0, d1, d2)}
    full, floored = power.build_pools({"A": [d0], "B": [d0]}, {"A": a, "B": b}, {d0: [d1, d2]},
                                      {"A": over, "B": under})
    assert floored[0][d2] == pytest.approx(103 / 101 - 1)
    assert full[0][d2] == pytest.approx(((103 / 101 - 1) + (60 / 50 - 1)) / 2)


def test_a_is_read_against_the_floored_pool_and_b_against_the_full_one(power, monkeypatch):
    full_pool, floored_pool = ({}, {}), ({}, {})
    monkeypatch.setattr(power, "pool_slipped", lambda leg, trade: leg)
    monkeypatch.setattr(power, "pool_r", lambda trade, c2c, o2c, cal, idx:
                        0.10 if c2c is full_pool[0] else 0.02)
    trade = SimpleNamespace(net_r=Decimal("0.5"), initial_risk_per_share=Decimal(2),
                            entry_price=Decimal(100))
    status, a, b = power.trade_values(trade, full_pool, floored_pool, [], {})
    assert status == "ok"
    assert a == pytest.approx(0.5 - 0.02), "A pairs with the FLOORED pool, in R"
    assert b == pytest.approx((0.5 - 0.10) * 0.02), "B pairs with the FULL pool, per unit"
    cash = SimpleNamespace(net_r=Decimal("-5"), initial_risk_per_share=Decimal("0.04"),
                           entry_price=Decimal(100))
    status, a, b = power.trade_values(cash, full_pool, floored_pool, [], {})
    assert (status, a) == ("cut_by_floor", None) and b is not None


def test_the_floor_is_the_owners_registry_value(power):
    text = (REPO / "registry" / "parameters.yml").read_text(encoding="utf-8")
    block = text.split("id: risk.min_stop_distance_fraction", 1)[1].split("\n  - id:", 1)[0]
    value = next(line.split(":", 1)[1].strip() for line in block.splitlines()
                 if line.strip().startswith("value:"))
    assert Decimal(value) == power.FLOOR


def test_the_cells_are_pr020s(power):
    from power_pr020 import CELLS

    assert power.CELLS == CELLS


def test_the_ratio_aligns_atr_with_its_bar_and_skips_the_warm_up(power, registry):
    from swingdesk.derived_observations import atr as atr_component

    series = _series(["100"] * 20)
    ratio = power.floor_ratio(series, atr_component.compute(series, registry))
    warm = [bar.session_date for bar in series.bars[14:]]
    assert sorted(ratio) == warm, "the first value is the 15th bar's, for ATR(14)"
    # Every true range is high - low = 2 on a 100 close, so 2 x ATR / close is 0.04 throughout.
    assert set(ratio.values()) == {Decimal("0.04")}


def test_pool_membership_reads_the_previous_close(power):
    series = _series(["100", "100", "100", "100"])
    d0, d1, d2, d3 = (bar.session_date for bar in series.bars)
    ratio = {d0: Decimal("0.004"), d1: Decimal("0.006"), d2: Decimal("0.004")}
    got = power.tradeable_days(series, [d0, d1, d2, d3, date(2030, 1, 1)], ratio)
    # d0 has no previous bar; d1's previous (d0) is under; d2's previous (d1) clears; d3's (d2)
    # is under; a day the series never traded is not a day it contributed.
    assert got == [d2]


@pytest.mark.parametrize(("risk", "clears"), [("0.50", True), ("0.49", False), ("5", True)])
def test_a_trade_clears_the_floor_at_exactly_half_a_percent(power, risk, clears):
    trade = SimpleNamespace(initial_risk_per_share=Decimal(risk), entry_price=Decimal(100))
    assert power.clears_floor(trade) is clears


def test_per_unit_divides_by_entry_over_risk(power):
    trade = SimpleNamespace(initial_risk_per_share=Decimal(2), entry_price=Decimal(100))
    assert power.per_unit(trade, 1.0) == pytest.approx(0.02)


def _months(n: int = 40, per: int = 5, seed: int = 11) -> dict[str, list[float]]:
    rng = random.Random(seed)
    return {f"{2016 + m // 12}-{1 + m % 12:02d}": [rng.gauss(0, 1) for _ in range(per)]
            for m in range(n)}


def test_a_cell_carries_both_constructions_and_no_level(power):
    from power_pr019 import assert_no_effect_leaked

    cell = power.cell_payload(5, {"trades": 200, "cut_by_floor": 3}, [20.0, 30.0, 40.0],
                              _months(seed=1), _months(seed=2))
    assert set(cell["dispersion"]) == {"A_in_r_under_the_floor", "B_per_unit_invested"}
    assert cell["entry_over_risk_p50"] == 30.0
    assert math.isclose(cell["b_half_width_in_r_at_p50"],
                        cell["dispersion"]["B_per_unit_invested"][power.READ] * 30.0)
    assert_no_effect_leaked({"cells": {"h5_stopnone": cell}})


def test_a_run_on_a_synthetic_store_sizes_every_cell(power, tmp_path):
    """End to end on noise: every cell sized under both constructions, and the guard passes."""
    spec = importlib.util.spec_from_file_location("_t19b_for_20b",
                                                  REPO / "tests" / "test_run_pr019b.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    helpers._synthetic_store(tmp_path)

    payload = power.build(argparse.Namespace(data=tmp_path, as_of=None, fraction=1.0, seed=1))

    assert set(payload["cells"]) == set(power.CELLS)
    five = payload["cells"]["h5_stopnone"]
    assert five["trades"] > 0, "the fixture must trade"
    assert five["cut_by_floor"] == 0, "random walks at ~1% a day all clear a 0.5% floor"
