"""`PR-021`'s machinery: the loser decile, the overlapping book, its turnover, and section 6.

Hand-built panels for the arithmetic, where every number can be checked on paper, and one synthetic
store for the plumbing - a five-second fake is what found the faults that killed two fifty-minute
runs before (`tools/run_pr016.py`'s history).
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import sys
from array import array
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
    return _load("run_pr021")


@pytest.fixture(scope="module")
def power() -> ModuleType:
    return _load("power_pr021")


def _panel(run: ModuleType, closes: dict[str, list[float]], opens: dict[str, list[float]] | None = None,
           start: int = 11, spy: list[float] | None = None):
    length = len(next(iter(closes.values())))
    calendar = [date(2024, 1, 1) + timedelta(days=i) for i in range(length)]
    panel = run.Panel(calendar, 0, start, spy or [100.0] * length)
    for name, values in closes.items():
        panel.closes[name] = array("d", values)
        panel.opens[name] = array("d", (opens or {}).get(name, values))
    return panel


# ------------------------------------------------------------------------------------ formation


def test_the_losers_are_the_most_negative_five_session_returns(run: ModuleType) -> None:
    closes = {f"N{i:02d}": [100.0] * 12 for i in range(20)}
    closes["N03"][6] = 80.0   # -20% from t=1 to t=6
    closes["N17"][6] = 90.0   # -10%
    closes["N09"][6] = 95.0   # -5%, third - outside a decile of two
    panel = _panel(run, closes)
    assert run.losers(panel, 6, sorted(closes), min_names=10) == ["N03", "N17"]


def test_nothing_after_the_formation_close_is_read(run: ModuleType) -> None:
    """A crash on the session after formation cannot move who was selected at it."""
    closes = {f"N{i:02d}": [100.0] * 12 for i in range(20)}
    closes["N03"][6] = 80.0
    closes["N17"][6] = 90.0
    before = run.losers(_panel(run, closes), 6, sorted(closes), min_names=10)
    closes["N05"][7] = 1.0
    closes["N05"][8] = 1.0
    assert run.losers(_panel(run, closes), 6, sorted(closes), min_names=10) == before


def test_an_unscored_name_is_counted_in_the_decile_and_never_bought(run: ModuleType) -> None:
    closes = {f"N{i:02d}": [100.0] * 12 for i in range(20)}
    closes["N00"][1] = NAN  # no close five sessions back
    for name, value in (("N04", 70.0), ("N05", 71.0)):
        closes[name][6] = value
    picked = run.losers(_panel(run, closes), 6, sorted(closes), min_names=10)
    assert picked == ["N04", "N05"], "twenty names, a decile of two, the unscored one last"


def test_ties_break_on_the_instrument_id(run: ModuleType) -> None:
    closes = {f"N{i:02d}": [100.0] * 12 for i in range(20)}
    for name in ("N12", "N07", "N15"):
        closes[name][6] = 90.0
    assert run.losers(_panel(run, closes), 6, sorted(closes), min_names=10) == ["N07", "N12"]


def test_a_thin_cross_section_forms_no_cohort(run: ModuleType) -> None:
    """Fifteen names would make a decile of one; under a minimum of twenty they make none."""
    closes = {f"N{i:02d}": [100.0] * 12 for i in range(15)}
    assert run.losers(_panel(run, closes), 6, sorted(closes), min_names=20) is None
    assert run.losers(_panel(run, closes), 6, sorted(closes), min_names=15) == ["N00"]


def test_the_decile_is_sized_exactly(run: ModuleType) -> None:
    """`int(len * 0.10)` in Decimal, as `run_pr014.select` sizes it - never a float's rounding."""
    closes = {f"N{i:03d}": [100.0] * 12 for i in range(139)}
    assert len(run.losers(_panel(run, closes), 6, sorted(closes), min_names=10)) == 13


# ----------------------------------------------------------------------------------------- book


def _flat(run: ModuleType, names: list[str], length: int = 16, start: int = 11):
    return _panel(run, {n: [100.0] * length for n in names}, start=start)


def test_the_book_holds_the_last_hold_cohorts_at_equal_capital(run: ModuleType) -> None:
    panel = _flat(run, ["A", "B", "C"])
    e = panel.start
    panel.opens["A"][e + 1] = 110.0   # +10% over session e
    panel.opens["C"][e + 1] = 95.0    # -5%
    cohorts = {e - 2: ["A", "B"], e - 1: ["C"]}
    book = run.build_book(panel, cohorts, {}, hold=2)
    assert book.sessions[0] == panel.calendar[e]
    assert book.gross[0] == pytest.approx(0.5 * (0.10 + 0.0) / 2 + 0.5 * (-0.05))


def test_a_name_two_cohorts_share_is_kept_not_bought_again(run: ModuleType) -> None:
    """Hold 1: {A, B} then {A, C}. Only C is bought - half the book, not all of it."""
    panel = _flat(run, ["A", "B", "C"])
    e = panel.start
    cohorts = {e - 2: ["A", "B"], e - 1: ["A", "C"]}
    book = run.build_book(panel, cohorts, {}, hold=1)
    assert book.turnover[0] == pytest.approx(0.5)


def test_the_round_trip_is_charged_on_what_was_bought(run: ModuleType) -> None:
    panel = _flat(run, ["A", "B", "C"])
    e = panel.start
    book = run.build_book(panel, {e - 2: ["A", "B"], e - 1: ["A", "C"]}, {}, hold=1)
    assert run.net(book)[0] == pytest.approx(book.gross[0] - 0.5 * 2 * 25 / 10_000)
    assert run.net(book, 3.0)[0] == pytest.approx(book.gross[0] - 0.5 * 2 * 75 / 10_000)


def test_a_missing_price_drops_the_name_and_is_counted(run: ModuleType) -> None:
    panel = _flat(run, ["A", "B"])
    e = panel.start
    panel.opens["A"][e + 1] = NAN
    panel.opens["B"][e + 1] = 104.0
    book = run.build_book(panel, {e - 1: ["A", "B"]}, {}, hold=1)
    assert book.gross[0] == pytest.approx(0.04)
    assert book.unpriced == 1


def test_a_thin_formation_leaves_its_share_in_cash(run: ModuleType) -> None:
    panel = _flat(run, ["A"])
    e = panel.start
    panel.opens["A"][e + 1] = 110.0
    book = run.build_book(panel, {e - 1: ["A"]}, {}, hold=2)   # formation e - 2 was thin
    assert book.gross[0] == pytest.approx(0.10 / 2)
    assert book.idle_cohorts >= 1


def test_the_pool_is_the_latest_formations_admitted_names(run: ModuleType) -> None:
    panel = _flat(run, ["A", "B", "C"])
    e = panel.start
    panel.opens["B"][e + 1] = 102.0
    panel.opens["C"][e + 1] = 96.0
    book = run.build_book(panel, {e - 1: ["A"]}, {e - 1: ["B", "C"]}, hold=1)
    assert book.pool[0] == pytest.approx((0.02 - 0.04) / 2)


def test_spy_is_read_over_the_same_open_to_open_session(run: ModuleType) -> None:
    spy = [100.0] * 16
    panel = _panel(run, {"A": [100.0] * 16}, spy=spy)
    e = panel.start
    spy[e + 1] = 101.0
    book = run.build_book(panel, {e - 1: ["A"]}, {}, hold=1)
    assert book.spy[0] == pytest.approx(0.01)


# ----------------------------------------------------------------------------- section 6


def _cell(mean: float, lo: float, hi: float, absolute_hi: float = 5.0, sessions: int = 1000,
          thin: float = 0.0, stressed: float = 1.0) -> dict[str, object]:
    return {"sessions": sessions, "thin_share": thin,
            "excess": {"mean": mean, "lo": lo, "hi": hi, "width": hi - lo},
            "absolute": {"mean": 0.0, "lo": absolute_hi - 5, "hi": absolute_hi,
                         "width": 5.0},
            "excess_cost_stress_3x": {"mean": stressed}}


@pytest.mark.parametrize(("cell", "branch"), [
    (_cell(-3, -8, 2, sessions=499), "REFUSED"),
    (_cell(-3, -8, 2, thin=0.06), "REFUSED"),
    (_cell(-3, -14, 8), "INCONCLUSIVE"),
    (_cell(6, 1, 11, absolute_hi=-0.5), "BOTH_NEGATIVE"),
    (_cell(6, 1, 11, stressed=0.0), "COST_FRAGILE"),
    (_cell(6, 1, 11, stressed=-4.0), "COST_FRAGILE"),
    (_cell(6, 1, 11), "ACCEPT"),
    (_cell(-9, -15, -3), "REJECT"),
    (_cell(-2, -9, 5), "NULL"),
    # Wider than the floor and still a sign: PR-019b's refused reading, read.
    (_cell(-25, -41, -9), "REJECT"),
    (_cell(20, 4, 36), "ACCEPT"),
    (_cell(20, 4, 36, absolute_hi=-1.0), "BOTH_NEGATIVE"),
])
def test_section_six_in_its_order(run: ModuleType, cell: dict[str, object], branch: str) -> None:
    assert run.branch_for(cell) == branch


def test_the_power_floor_is_inclusive(run: ModuleType) -> None:
    assert run.branch_for(_cell(-2, -12, 8)) == "NULL"


def test_the_hold_is_the_largest_selection_half_excess(run: ModuleType) -> None:
    cells = {h: _cell(value, value - 5, value + 5) for h, value in zip(range(1, 6), (-9, -4, -2, -3, -7),
                                                                       strict=True)}
    assert run.select_hold(cells) == 3


def test_a_tie_selects_nothing(run: ModuleType) -> None:
    cells = {1: _cell(-2, -7, 3), 2: _cell(-2, -7, 3)}
    assert run.select_hold(cells) is None
    assert run.TOKEN["TIE"] == "inconclusive"


def test_the_window_is_48_months_from_the_run_itself(run: ModuleType) -> None:
    assert run.window_start(date(2026, 9, 13), 48) == date(2022, 9, 13)
    assert run.window_start(date(2024, 3, 31), 1) == date(2024, 2, 29)


# --------------------------------------------------------------------------- power estimate


def test_the_width_is_the_verdict_estimators_and_carries_no_level(power: ModuleType,
                                                                  run: ModuleType) -> None:
    """The width is the bootstrap's own, and shifting a series - its level - does not move it."""
    rng = random.Random(1)
    series = [rng.gauss(0.001, 0.01) for _ in range(300)]
    shifted = [value + 0.004 for value in series]
    assert power.width(series, 200)["full_width_points"] == pytest.approx(
        power.width(shifted, 200)["full_width_points"])
    assert power.width(series, 200)["full_width_points"] == pytest.approx(
        run.interval(series, 200)["width"])


def test_the_power_payload_carries_no_level(power: ModuleType) -> None:
    from power_pr019 import assert_no_effect_leaked

    assert_no_effect_leaked({"cells": {"1": power.width([0.01, -0.02, 0.005] * 50, 50)}})


# ------------------------------------------------------------------------ the synthetic store


def _synthetic_store(root: Path) -> Path:
    """Forty stocks, two funds and `SPY` over 420 weekday sessions, and a directory saying which."""
    from swingdesk.contracts.market import Bar, Interval, Series
    from swingdesk.market_data import BarStore
    from swingdesk.reference_data.directory import DirectoryStore
    from swingdesk.reference_data.universe import DirectoryEntry

    known = datetime(2025, 12, 1, tzinfo=UTC)
    days: list[date] = []
    day = date(2024, 3, 1)
    while len(days) < 420:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    rng = random.Random(7)
    stocks = [f"S{i:02d}" for i in range(40)]
    funds = ["FUNDA", "FUNDB"]
    bars = []
    for name in [*stocks, *funds, "SPY"]:
        price = 40.0
        for d in days:
            opened = price * (1 + rng.gauss(0, 0.004))
            price = opened * (1 + rng.gauss(0, 0.02))
            price = max(price, 6.0)
            bars.append(Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                            event_time=datetime.combine(d, time(14, 30), tzinfo=UTC), session_date=d,
                            open=Decimal(f"{opened:.4f}"), high=Decimal(f"{max(opened, price) + 0.5:.4f}"),
                            low=Decimal(f"{max(min(opened, price) - 0.5, 1):.4f}"),
                            close=Decimal(f"{price:.4f}"), volume=1_000_000, knowledge_time=known))
    with BarStore(root / "bars.duckdb") as store:
        store.write(bars, known)
    entries = [DirectoryEntry(symbol=n, name=n, venue="Q", is_etf=False, is_test_issue=False)
               for n in [*stocks, "SPY"]]
    entries[-1] = DirectoryEntry(symbol="SPY", name="SPY", venue="P", is_etf=True, is_test_issue=False)
    entries += [DirectoryEntry(symbol=n, name=n, venue="P", is_etf=True, is_test_issue=False) for n in funds]
    directory = DirectoryStore(root / "directory.duckdb")
    directory.record(entries, known - timedelta(days=1), source="test")
    directory.close()
    return root


def _args(root: Path) -> argparse.Namespace:
    return argparse.Namespace(data=root, as_of=None, window_months=6, resamples=50, min_names=5)


def test_the_run_goes_end_to_end_on_a_synthetic_store(run: ModuleType, tmp_path: Path) -> None:
    payload = run.build(_args(_synthetic_store(tmp_path)))
    assert payload["branch"] == "SMOKE" and payload["verdict"] == "smoke"
    assert payload["universe"]["funds_excluded"] == 2
    assert set(payload["cells"]) == {"A", "B"}
    assert set(payload["cells"]["A"]) == {"1", "2", "3", "4", "5"}
    judged = payload["cells"]["B"]["5"]
    # The synthetic history ends seven weeks before its `as_of`, so six months hold ~94 sessions.
    assert judged["sessions"] >= 90
    assert not math.isnan(judged["excess"]["width"])
    assert payload["selected_hold"] in (1, 2, 3, 4, 5)
    assert payload["measured_span"]["years"] < 1


def test_the_power_estimate_never_loads_the_holdout(power: ModuleType, run: ModuleType,
                                                   tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                                   ) -> None:
    from run_pr015 import half_of

    seen: list[str] = []
    real = power.load_panel

    def spy_on(store, as_of, rule, stocks, funds, keep, months):  # type: ignore[no-untyped-def]
        seen.extend(name for name in sorted(stocks) if keep(name))
        return real(store, as_of, rule, stocks, funds, keep, months)

    monkeypatch.setattr(power, "load_panel", spy_on)
    payload = power.build(_args(_synthetic_store(tmp_path)))
    assert seen and all(half_of(name) == "A" for name in seen)
    assert payload["half"] == "A"
    assert set(payload["cells"]) == {"1", "2", "3", "4", "5"}
