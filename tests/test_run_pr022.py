"""`PR-022`'s machinery: the monthly signal, the switch-day arithmetic, the paired bootstrap, §6.

Hand-built prices for everything that can be checked on paper, and one synthetic store for the
plumbing, as `test_run_pr021.py` does.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import statistics
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
NAN = float("nan")


def _load(name: str) -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(f"_{name}", REPO / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def run() -> ModuleType:
    return _load("run_pr022")


@pytest.fixture(scope="module")
def power() -> ModuleType:
    return _load("power_pr022")


def _weekdays(start: date, count: int) -> list[date]:
    days: list[date] = []
    day = start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def _prices(run: ModuleType, days: list[date], spy: list[float], cash: list[float] | None = None):
    cash = cash or [100.0] * len(days)
    return run.Prices(days, list(spy), list(spy), list(cash), list(cash))


# ---------------------------------------------------------------------------------- the signal


def test_month_ends_are_each_months_last_session(run: ModuleType) -> None:
    days = [date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 1), date(2024, 2, 29), date(2024, 3, 1)]
    assert run.month_ends(days) == [1, 3, 4]


def _monthly(run: ModuleType, closes: list[float]):
    """One session per month-end plus one after it, so every month has an end and a next open."""
    days: list[date] = []
    spy: list[float] = []
    for k, close in enumerate(closes):
        year, month = 2020 + (k // 12), k % 12 + 1
        days += [date(year, month, 1), date(year, month, 20)]
        spy += [close, close]
    return _prices(run, days, spy)


def test_invested_only_when_the_close_is_above_its_ten_month_average(run: ModuleType) -> None:
    closes = [100.0] * 9 + [110.0, 100.0, 90.0]
    prices = _monthly(run, closes)
    ends = run.month_ends(prices.calendar)
    decided = run.signals(prices, ends)
    assert sorted(decided) == ends[9:], "ten month-ends before the first decision"
    assert decided[ends[9]] is True                 # 110 > mean(100 x 9, 110) = 101
    assert decided[ends[10]] is False               # 100 < mean(100 x 8, 110, 100) = 101
    assert decided[ends[11]] is False


def test_the_average_is_ten_month_ends_and_not_nine(run: ModuleType) -> None:
    """A high first month sits inside ten month-ends and outside nine, so the two answers differ."""
    prices = _monthly(run, [200.0] + [100.0] * 8 + [105.0])
    ends = run.month_ends(prices.calendar)
    assert run.signals(prices, ends)[ends[9]] is False   # 105 < mean(200, 100 x 8, 105) = 110.5


def test_a_close_equal_to_its_average_is_cash(run: ModuleType) -> None:
    prices = _monthly(run, [100.0] * 10)
    ends = run.month_ends(prices.calendar)
    assert run.signals(prices, ends)[ends[9]] is False


def test_a_decision_reads_nothing_after_its_month_end(run: ModuleType) -> None:
    closes = [100.0] * 9 + [110.0, 105.0]
    prices = _monthly(run, closes)
    ends = run.month_ends(prices.calendar)
    before = run.signals(prices, ends)[ends[9]]
    assert before is True
    # Pushed the way that would flip it: a later close so high that any average reading it falls
    # below the decision's own close no longer.
    prices.spy_close[ends[9] + 1] = 1e6
    prices.spy_close[ends[10]] = 1e6
    assert run.signals(prices, ends)[ends[9]] is True


# ------------------------------------------------------------------------------- the two books


def _week(run: ModuleType):
    """Month-end on the first Friday, then five sessions of the next month."""
    days = [date(2024, 5, 31), date(2024, 6, 3), date(2024, 6, 4), date(2024, 6, 5), date(2024, 6, 28),
            date(2024, 7, 1), date(2024, 7, 2)]
    prices = run.Prices(days, [100.0] * 7, [100.0] * 7, [50.0] * 7, [50.0] * 7)
    return prices


def test_the_decision_governs_the_sessions_after_its_month_end(run: ModuleType) -> None:
    prices = _week(run)
    ends = run.month_ends(prices.calendar)          # 0 (May 31), 4 (Jun 28), 6 (Jul 2)
    decided = {0: True, 4: False, 6: False}
    paths = run.build_paths(prices, decided, 0)
    assert paths.invested == [True, True, True, True, False, False]
    assert ends == [0, 4, 6]


def test_the_first_session_buys_both_books_at_its_open_for_nothing(run: ModuleType) -> None:
    prices = _week(run)
    prices.spy_close[1] = 102.0
    paths = run.build_paths(prices, {0: True, 4: True, 6: True}, 0)
    assert paths.timed[0] == pytest.approx(0.02)
    assert paths.held[0] == pytest.approx(0.02)
    assert paths.switches == 0


def test_the_switch_day_splits_at_the_open_and_pays_two_fills(run: ModuleType) -> None:
    prices = _week(run)
    prices.spy_open[5] = 99.0        # SPY gaps down overnight into the first July session
    prices.cash_close[5] = 50.5      # the fund rises open to close
    prices.spy_dividend[date(2024, 7, 1)] = 0.5
    paths = run.build_paths(prices, {0: True, 4: False, 6: False}, 0)
    switch = 4                        # the fifth session of the book, July 1
    c = 25 / 10_000
    assert paths.timed[switch] == pytest.approx((99.0 + 0.5) / 100.0 * (1 - c) ** 2 * (50.5 / 50.0) - 1)
    assert paths.switches == 1
    assert paths.held[switch] == pytest.approx((100.0 + 0.5) / 100.0 - 1), "held takes the dividend"


def test_three_times_the_cost_is_three_times_the_rate(run: ModuleType) -> None:
    prices = _week(run)
    paths = run.build_paths(prices, {0: True, 4: False, 6: False}, 0, cost_multiple=3.0)
    assert paths.timed[4] == pytest.approx((1 - 75 / 10_000) ** 2 - 1)


def test_cash_earns_its_dividend_on_its_ex_date(run: ModuleType) -> None:
    prices = _week(run)
    prices.cash_dividend[date(2024, 6, 4)] = 0.2
    paths = run.build_paths(prices, {0: False, 4: False, 6: False}, 0)
    assert paths.timed[1] == pytest.approx(0.2 / 50.0)


# --------------------------------------------------------------------------------- statistics


def test_sharpe_is_the_registered_convention(run: ModuleType) -> None:
    returns = [0.01, -0.005, 0.002, 0.004]
    assert run.sharpe(returns) == pytest.approx(statistics.fmean(returns) / statistics.stdev(returns)
                                                * math.sqrt(252))


def _naive(x: list[float], y: list[float], block: int, seed: int, resamples: int):
    n, width = len(x), min(block, len(x))
    rng = random.Random(seed)
    out = []
    for _ in range(resamples):
        xs: list[float] = []
        ys: list[float] = []
        while len(xs) < n:
            begin = rng.randrange(n - width + 1)
            take = min(width, n - len(xs))
            xs += x[begin:begin + take]
            ys += y[begin:begin + take]
        out.append((statistics.fmean(xs) / statistics.stdev(xs) * math.sqrt(252),
                    statistics.fmean(ys) / statistics.stdev(ys) * math.sqrt(252)))
    return out


def test_the_prefix_sum_bootstrap_equals_the_naive_one(run: ModuleType) -> None:
    rng = random.Random(3)
    x = [rng.gauss(0.0005, 0.01) for _ in range(137)]
    y = [rng.gauss(0.0004, 0.012) for _ in range(137)]
    fast = run.bootstrap_sharpes(x, y, 10, 5, 40)
    slow = _naive(x, y, 10, 5, 40)
    for (a, b), (c, d) in zip(fast, slow, strict=True):
        assert a == pytest.approx(c, rel=1e-9) and b == pytest.approx(d, rel=1e-9)


def test_identical_books_differ_by_nothing_in_every_resample(run: ModuleType) -> None:
    rng = random.Random(4)
    x = [rng.gauss(0.0005, 0.01) for _ in range(300)]
    readings = run.sharpe_readings(x, list(x), 200)
    assert readings["difference"]["lo"] == readings["difference"]["hi"] == 0.0


def test_the_worst_drawdown_names_its_dates(run: ModuleType) -> None:
    days = [date(2024, 1, d) for d in range(1, 7)]
    worst = run.drawdown([0.10, -0.20, 0.05, -0.10, 0.30, 0.0], days)
    assert worst["depth"] == pytest.approx(0.8 * 1.05 * 0.9 - 1)
    assert (worst["peak"], worst["trough"]) == ("2024-01-01", "2024-01-04")


def test_an_episode_is_read_on_both_books_over_the_same_sessions(run: ModuleType) -> None:
    held = [0.0, 0.10, -0.10, -0.10, 0.10, 0.20, 0.0]
    timed = [0.0, 0.10, -0.05, 0.0, 0.0, 0.10, 0.0]
    days = _weekdays(date(2024, 3, 4), 7)
    paths = run.Paths(days, timed, held, [True] * 7)
    [episode] = run.episodes(paths, depth=0.15)
    assert episode["held_fall"] == pytest.approx(0.81 - 1)
    assert episode["timed_over_the_fall"] == pytest.approx(-0.05)
    assert episode["timed_over_the_recovery"] == pytest.approx(0.10)
    assert episode["timed_worst_inside"] == pytest.approx(-0.05)
    assert (episode["peak"], episode["trough"], episode["recovered"]) == (
        days[1].isoformat(), days[3].isoformat(), days[5].isoformat())


def test_a_fall_shallower_than_the_depth_is_not_an_episode(run: ModuleType) -> None:
    days = _weekdays(date(2024, 3, 4), 4)
    paths = run.Paths(days, [0.0] * 4, [0.0, -0.10, 0.12, 0.0], [True] * 4)
    assert run.episodes(paths, depth=0.15) == []


def test_break_even_is_the_edge_over_two_fills_a_switch(run: ModuleType) -> None:
    days = _weekdays(date(2024, 3, 4), 4)
    gross = run.Paths(days, [0.002] * 4, [0.001] * 4, [True] * 4, switches=2)
    assert run.break_even_bps(gross) == pytest.approx(0.001 / (2 * 0.5) * 10_000)


# ------------------------------------------------------------------------------ section 6


def _cell(point: float, lo: float, hi: float, timed_hi: float = 1.0, months: int = 230,
          stressed: float = 0.1) -> dict[str, object]:
    return {"months": months, "stress_difference_point": stressed,
            "sharpe": {"difference": {"point": point, "lo": lo, "hi": hi, "width": hi - lo},
                       "timed": {"point": 0.5, "lo": timed_hi - 0.6, "hi": timed_hi, "width": 0.6}}}


@pytest.mark.parametrize(("cell", "branch"), [
    (_cell(0.1, -0.1, 0.3, months=119), "REFUSED"),
    (_cell(0.3, 0.1, 0.5, timed_hi=-0.1), "BOTH_NEGATIVE"),
    (_cell(0.3, 0.1, 0.5, stressed=0.0), "COST_FRAGILE"),
    (_cell(0.3, 0.1, 0.5), "ACCEPT"),
    (_cell(-0.3, -0.5, -0.1), "REJECT"),
    (_cell(0.1, -0.2, 0.4), "INCONCLUSIVE"),
    (_cell(0.05, -0.15, 0.25), "NULL"),
    (_cell(0.3, 0.05, 0.75), "ACCEPT"),
    (_cell(-0.4, -0.8, -0.05), "REJECT"),
])
def test_section_six_in_its_order(run: ModuleType, cell: dict[str, object], branch: str) -> None:
    assert run.branch_for(cell) == branch


def test_the_floor_is_inclusive(run: ModuleType) -> None:
    assert run.branch_for(_cell(0.0, -0.2, 0.2)) == "NULL"


# --------------------------------------------------------------------------- the synthetic store


def _synthetic_store(root: Path) -> Path:
    """Three years of SPY, the cash fund from month thirteen, and dividends on both."""
    from swingdesk.contracts.market import Bar, CorporateAction, CorporateActionKind, Interval, Series
    from swingdesk.market_data import BarStore

    known = datetime(2026, 1, 5, tzinfo=UTC)
    days = _weekdays(date(2021, 1, 4), 780)
    rng = random.Random(11)
    bars, actions = [], []
    price = 300.0
    cash_from = next(i for i, d in enumerate(days) if (d.year, d.month) == (2022, 1))
    for i, d in enumerate(days):
        opened = price * (1 + rng.gauss(0, 0.003))
        price = opened * (1 + rng.gauss(0.0004, 0.011))
        stamp = datetime.combine(d, time(14, 30), tzinfo=UTC)
        bars.append(Bar(instrument_id="SPY", interval=Interval.DAY, series=Series.RAW, event_time=stamp,
                        session_date=d, open=Decimal(f"{opened:.4f}"),
                        high=Decimal(f"{max(opened, price) + 1:.4f}"),
                        low=Decimal(f"{min(opened, price) - 1:.4f}"), close=Decimal(f"{price:.4f}"),
                        volume=1_000_000, knowledge_time=known))
        if i >= cash_from:
            bars.append(Bar(instrument_id="BIL", interval=Interval.DAY, series=Series.RAW, event_time=stamp,
                            session_date=d, open=Decimal("91.50"), high=Decimal("91.52"),
                            low=Decimal("91.48"), close=Decimal("91.50"), volume=10_000,
                            knowledge_time=known))
        if d.day <= 3 and d.weekday() == 0:
            actions.append(CorporateAction(instrument_id="BIL", kind=CorporateActionKind.DIVIDEND,
                                           effective_date=d, value=Decimal("0.30"), knowledge_time=known))
    with BarStore(root / "bars.duckdb") as store:
        store.write(bars, known)
        store.write_actions(actions, known)
    return root


def test_the_run_goes_end_to_end_on_a_synthetic_store(run: ModuleType, tmp_path: Path) -> None:
    payload = run.build(argparse.Namespace(data=_synthetic_store(tmp_path), as_of=None, resamples=50))
    assert payload["branch"] == "SMOKE" and payload["verdict"] == "smoke"
    assert payload["window"]["start"] >= "2022-01-01", "not before the cash fund exists"
    primary = payload["primary"]
    assert primary["sessions"] > 400
    assert not math.isnan(primary["sharpe"]["difference"]["width"])
    assert primary["cash_unpriced_sessions"] == 0
    assert payload["measured_span"]["years"] < 3
    assert set(payload["per_year"]) >= {"2022", "2023"}


def test_the_power_estimate_carries_no_level(power: ModuleType, tmp_path: Path) -> None:
    payload = power.build(argparse.Namespace(data=_synthetic_store(tmp_path), as_of=None, resamples=50))
    assert payload["registered_window"]["sessions"] > 400
    assert "sharpe_difference_width" in payload["registered_window"]
