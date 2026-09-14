"""`PR-023`'s machinery: five signals, the monthly targets, the rebalance-day arithmetic, excess returns.

Hand-built markets for the arithmetic, one synthetic store for the plumbing.
"""

from __future__ import annotations

import argparse
import importlib.util
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
NAN = float("nan")
NAMES = ("SPY", "EFA", "IEF", "VNQ", "DBC", "BIL")


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
    return _load("run_pr023")


@pytest.fixture(scope="module")
def power() -> ModuleType:
    return _load("power_pr023")


#: May 31 is a month-end, June runs three sessions to its month-end on the 28th, then two of July.
DAYS = [date(2024, 5, 31), date(2024, 6, 3), date(2024, 6, 4), date(2024, 6, 28), date(2024, 7, 1),
        date(2024, 7, 2)]


def _market(run: ModuleType):
    flat = {n: [100.0] * len(DAYS) for n in NAMES}
    return run.Market(list(DAYS), {n: list(v) for n, v in flat.items()},
                      {n: list(v) for n, v in flat.items()}, {n: {} for n in NAMES})


def _decided(below: dict[int, set[str]]) -> dict[str, dict[int, bool]]:
    """Every asset above its average at month-ends 0, 3 and 5 except those named below at each."""
    return {n: {end: n not in below.get(end, set()) for end in (0, 3, 5)} for n in NAMES[:5]}


# ------------------------------------------------------------------------------------ signals


def test_a_month_without_a_close_decides_nothing(run: ModuleType) -> None:
    days: list[date] = []
    for k in range(11):
        days += [date(2020 + k // 12, k % 12 + 1, 1), date(2020 + k // 12, k % 12 + 1, 20)]
    closes = [100.0] * len(days)
    closes[5] = NAN                              # the third month-end has no close
    market = run.Market(days, {"SPY": closes}, {"SPY": closes}, {"SPY": {}})
    ends = run.month_ends(days)
    decided = run.signals_for(market, "SPY", ends)
    assert ends[9] not in decided, "its ten-month window holds the missing month"
    assert ends[10] not in decided


def test_a_timed_fifth_below_its_average_is_cash_and_the_held_arm_ignores_it(run: ModuleType) -> None:
    decided = _decided({0: {"EFA", "DBC"}})
    assert run.targets("TIMED_5", 0, decided) == pytest.approx(
        {"SPY": 0.2, "IEF": 0.2, "VNQ": 0.2, "BIL": 0.4})
    assert run.targets("HOLD_5", 0, decided) == pytest.approx({n: 0.2 for n in NAMES[:5]})


def test_the_window_waits_for_all_five_and_the_cash_fund(run: ModuleType) -> None:
    market = _market(run)
    market.opens["BIL"][1] = NAN
    decided = _decided({})
    del decided["DBC"][3]
    decided["DBC"][0] = True
    ends = [0, 3, 5]
    # Month-end 0: BIL has no next open. Month-end 3: DBC has not decided. None qualifies.
    with pytest.raises(SystemExit):
        run.first_decision(market, ends, decided)
    decided["DBC"][3] = True
    assert run.first_decision(market, ends, decided) == 3


# ------------------------------------------------------------------------------------ the book


def test_the_first_session_buys_the_targets_at_the_open_for_nothing(run: ModuleType) -> None:
    market = _market(run)
    market.closes["SPY"][1] = 102.0
    book = run.simulate(market, "TIMED_5", _decided({}), 0)
    assert book.returns[0] == pytest.approx(0.2 * 0.02)
    assert book.traded == 0.0


def test_between_month_ends_the_weights_drift(run: ModuleType) -> None:
    market = _market(run)
    market.closes["SPY"][1] = 110.0            # day one: SPY +10%, the book +2%
    market.closes["SPY"][2] = 121.0            # day two: SPY +10% again, on a larger weight
    book = run.simulate(market, "HOLD_5", _decided({}), 0)
    weight = 0.2 * 1.10 / 1.02
    assert book.returns[1] == pytest.approx(weight * 0.10)


def test_the_rebalance_day_earns_the_night_trades_then_earns_the_day(run: ModuleType) -> None:
    market = _market(run)
    market.opens["SPY"][4] = 99.0
    market.dividends["SPY"][DAYS[4]] = 0.5     # ex-date July 1: the prior close's holder gets it
    market.closes["BIL"][4] = 100.5            # the fund rises open to close
    book = run.simulate(market, "TIMED_5", _decided({3: {"SPY"}}), 0)
    night_spy = (99.0 + 0.5) / 100.0 - 1.0
    night = 0.2 * night_spy
    drifted_spy = 0.2 * (1 + night_spy) / (1 + night)
    drifted_other = 0.2 / (1 + night)
    traded = drifted_spy + 4 * abs(0.2 - drifted_other) + 0.2   # SPY sold, four trimmed, BIL bought
    day = 0.2 * 0.005                                             # BIL's fifth, open to close
    expected = (1 + night) * (1 - traded * 25 / 10_000) * (1 + day) - 1
    assert book.returns[3] == pytest.approx(expected)
    assert book.traded == pytest.approx(traded)
    assert book.switches == 1
    assert book.risky_share[3] == pytest.approx(0.8 * 1.0 / (1 + day), rel=1e-6)


def test_the_held_arm_rebalances_its_drift_back_to_fifths(run: ModuleType) -> None:
    market = _market(run)
    market.closes["SPY"][1] = 110.0
    market.closes["SPY"][2] = 110.0
    market.closes["SPY"][3] = 110.0
    market.opens["SPY"][4] = 110.0
    market.closes["SPY"][4] = 110.0
    book = run.simulate(market, "HOLD_5", _decided({}), 0)
    spy = 0.2 * 1.10 / 1.02
    assert book.traded == pytest.approx(abs(spy - 0.2) + 4 * abs(0.2 / 1.02 - 0.2))
    assert book.switches == 0


def test_a_dividend_between_month_ends_is_the_holders(run: ModuleType) -> None:
    market = _market(run)
    market.dividends["IEF"][DAYS[2]] = 0.3
    book = run.simulate(market, "HOLD_5", _decided({}), 0)
    assert book.returns[1] == pytest.approx(0.2 * 0.003)


def test_a_switch_is_counted_against_last_months_decision_not_the_first(run: ModuleType) -> None:
    """SPY leaves at the end of June and stays out at the end of July: one switch, not two."""
    days = [date(2024, 5, 31), date(2024, 6, 3), date(2024, 6, 28), date(2024, 7, 1), date(2024, 7, 31),
            date(2024, 8, 1)]
    flat = {n: [100.0] * len(days) for n in NAMES}
    market = run.Market(days, {n: list(v) for n, v in flat.items()}, {n: list(v) for n, v in flat.items()},
                        {n: {} for n in NAMES})
    decided = {n: {0: True, 2: True, 4: True, 5: True} for n in NAMES[:5]}
    decided["SPY"].update({2: False, 4: False})
    book = run.simulate(market, "TIMED_5", decided, 0)
    assert book.rebalances == 2
    assert book.switches == 1


def test_a_held_asset_without_a_price_is_counted_and_moves_nothing(run: ModuleType) -> None:
    market = _market(run)
    market.closes["VNQ"][2] = NAN
    market.closes["SPY"][2] = 101.0
    book = run.simulate(market, "HOLD_5", _decided({}), 0)
    assert book.unpriced == 1
    assert book.returns[1] == pytest.approx(0.2 * 0.01)


def test_three_times_the_cost_is_three_times_the_rate(run: ModuleType) -> None:
    market = _market(run)
    book = run.simulate(market, "TIMED_5", _decided({3: {"SPY"}}), 0, cost_multiple=3.0)
    assert book.returns[3] == pytest.approx((1 - 0.4 * 75 / 10_000) - 1)


def test_the_benchmark_and_the_cash_leg_are_total_return(run: ModuleType) -> None:
    market = _market(run)
    market.closes["BIL"][1] = 100.1
    market.dividends["BIL"][DAYS[2]] = 0.4
    assert run.held(market, "BIL", 0)[:2] == pytest.approx([0.001, (100.0 + 0.4) / 100.1 - 1])


def test_the_sharpe_read_is_of_the_excess_over_cash(run: ModuleType) -> None:
    rng = random.Random(2)
    n = 300
    book = [rng.gauss(0.0004, 0.008) for _ in range(n)]
    spy = [rng.gauss(0.0005, 0.012) for _ in range(n)]
    cash = [0.0002] * n
    sessions = [date(2024, 1, 1) + timedelta(days=i) for i in range(n)]
    cell = run.readings(sessions, book, spy, cash, 100)
    expected = run.sharpe(run.minus(book, cash)) - run.sharpe(run.minus(spy, cash))
    assert cell["sharpe"]["difference"]["point"] == pytest.approx(expected)
    assert cell["sharpe_rf0"]["difference"] == pytest.approx(run.sharpe(book) - run.sharpe(spy))


# --------------------------------------------------------------------------- the synthetic store


def _synthetic_store(root: Path) -> Path:
    """Three years of five funds and the cash fund from month thirteen, with dividends."""
    from swingdesk.contracts.market import Bar, CorporateAction, CorporateActionKind, Interval, Series
    from swingdesk.market_data import BarStore

    known = datetime(2026, 1, 5, tzinfo=UTC)
    days: list[date] = []
    day = date(2021, 1, 4)
    while len(days) < 780:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    cash_from = next(i for i, d in enumerate(days) if (d.year, d.month) == (2022, 1))
    rng = random.Random(21)
    bars, actions = [], []
    for name in NAMES:
        price = 50.0
        for i, d in enumerate(days):
            if name == "BIL" and i < cash_from:
                continue
            opened = price * (1 + rng.gauss(0, 0.002))
            price = opened * (1 + rng.gauss(0.0003, 0.01 if name != "BIL" else 0.0))
            stamp = datetime.combine(d, time(14, 30), tzinfo=UTC)
            bars.append(Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW, event_time=stamp,
                            session_date=d, open=Decimal(f"{opened:.4f}"),
                            high=Decimal(f"{max(opened, price) + 0.5:.4f}"),
                            low=Decimal(f"{min(opened, price) - 0.5:.4f}"), close=Decimal(f"{price:.4f}"),
                            volume=100_000, knowledge_time=known))
            if name in ("BIL", "IEF") and d.day <= 3 and d.weekday() == 0 and i >= cash_from:
                actions.append(CorporateAction(instrument_id=name, kind=CorporateActionKind.DIVIDEND,
                                               effective_date=d, value=Decimal("0.10"), knowledge_time=known))
    with BarStore(root / "bars.duckdb") as store:
        store.write(bars, known)
        store.write_actions(actions, known)
    return root


def test_the_run_goes_end_to_end_on_a_synthetic_store(run: ModuleType, tmp_path: Path) -> None:
    payload = run.build(argparse.Namespace(data=_synthetic_store(tmp_path), as_of=None, resamples=50))
    assert payload["branch"] == "SMOKE" and payload["verdict"] == "smoke"
    assert payload["trials"] == 2
    assert payload["window"]["start"] >= "2022-01-01"
    for arm in ("TIMED_5", "HOLD_5"):
        cell = payload["cells"][arm]
        assert cell["sessions"] > 400 and cell["unpriced"] == 0
        assert cell["branch"] in {"REFUSED", "INCONCLUSIVE", "NULL", "ACCEPT", "REJECT", "BOTH_NEGATIVE",
                                  "COST_FRAGILE"}
    assert payload["cells"]["HOLD_5"]["switches"] == 0
    assert payload["cells"]["HOLD_5"]["risky_share"] == pytest.approx(1.0)


def test_the_power_estimate_carries_no_level(power: ModuleType, tmp_path: Path) -> None:
    payload = power.build(argparse.Namespace(data=_synthetic_store(tmp_path), as_of=None, resamples=50))
    assert set(payload["arms"]) == {"TIMED_5", "HOLD_5"}
    assert payload["arms"]["TIMED_5"]["registered_window"]["sessions"] > 400
