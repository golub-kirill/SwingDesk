"""`tools/measure_tsmom_power.py` - the widths that decided a time-series momentum study was not run.

The measurement's whole claim is a WIDTH, so these tests hold the two things that could make one
wrong without anyone noticing: the total-return index a split or a dividend would bend, and a
payload that must never carry the random book's own level.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def power():
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "measure_tsmom_power", REPO / "tools" / "measure_tsmom_power.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_a_split_does_not_move_the_index(power) -> None:
    """A 2-for-1 halves the price and not the holder's wealth."""
    closes = [(date(2026, 1, 30), 100.0), (date(2026, 2, 2), 50.0), (date(2026, 2, 27), 55.0)]
    index = power.month_end_index(closes, {}, {date(2026, 2, 2): 2.0})
    assert index["2026-01"] == pytest.approx(1.0)
    assert index["2026-02"] == pytest.approx(1.10)


def test_a_dividend_is_earned_on_its_ex_date(power) -> None:
    closes = [(date(2026, 1, 30), 100.0), (date(2026, 2, 2), 99.0)]
    index = power.month_end_index(closes, {date(2026, 2, 2): 1.0}, {})
    assert index["2026-02"] == pytest.approx(1.0)


def test_a_missing_close_carries_the_index(power) -> None:
    closes = [(date(2026, 1, 30), 100.0), (date(2026, 2, 2), float("nan")),
              (date(2026, 2, 3), 110.0)]
    assert power.month_end_index(closes, {}, {})["2026-02"] == pytest.approx(1.10)


def test_a_book_that_is_the_benchmark_reads_zero_on_both_contrasts(power) -> None:
    spy = [0.02, -0.01, 0.03, -0.02, 0.01, 0.015]
    cash = [0.001] * len(spy)
    excess, matched = power.contrasts(spy, spy, cash)
    assert excess == pytest.approx(0.0) and matched == pytest.approx(0.0, abs=1e-12)


def test_the_widths_carry_no_level(power) -> None:
    """Widths, minimum detectable effects and a month count - never the book's own return."""
    months = 60
    returns = {f: [0.01 * ((i % 7) - 3) / 3 for i in range(months)]
               for f in (*power.FUNDS, power.CASH)}
    cell = power.widths(returns, 0, months)
    assert set(cell) == {"months", "excess_vs_spy_width", "excess_vs_spy_minimum_detectable",
                         "vs_volatility_matched_spy_width",
                         "vs_volatility_matched_spy_minimum_detectable"}
    assert cell["excess_vs_spy_width"] >= 0
