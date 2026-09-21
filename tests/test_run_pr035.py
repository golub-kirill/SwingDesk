"""`tools/run_pr035.py`: small caps overnight plus `SPY` through the session, against holding `SPY`.

What must hold, each a way to report a book nobody could run:

* **the two legs COMPOUND**, because the second is bought with what the first returned;
* **`SPY`'s dividends are not earned by this book** — they detach at the open and go to whoever
  held overnight, which here is the small-cap leg;
* **the benchmark is holding `SPY` with its dividends**, paired session by session;
* **an `ACCEPT` clears three gates** — a cent a share on four sides, the recent window, and
  `SPY`'s own Sharpe ratio.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def run() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_run_pr035", REPO / "tools" / "run_pr035.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- the book ---------------------------------------------------------------------------------------


def test_the_two_legs_compound_rather_than_add(run) -> None:
    day = date(2025, 3, 3)
    got = run.compounded({day: 0.10}, {day: 0.10})
    assert got[day] == pytest.approx(0.21), "0.21, not 0.20 - the day leg is bought with the night's"


def test_a_session_only_one_leg_read_is_not_in_the_book(run) -> None:
    first, second = date(2025, 3, 3), date(2025, 3, 4)
    assert list(run.compounded({first: 0.01, second: 0.02}, {first: 0.01})) == [first]


def test_the_excess_pairs_with_the_benchmark_by_session(run) -> None:
    first, second = date(2025, 3, 3), date(2025, 3, 4)
    got = run.excess({first: 0.03, second: 0.01}, {first: 0.01})
    assert got == {first: pytest.approx(0.02)}


# --- the gates --------------------------------------------------------------------------------------


def _cell(lo, hi, days=2000, months=120, share=1.0):
    return {"lo": lo, "hi": hi, "width": hi - lo, "estimate": (lo + hi) / 2, "days": days,
            "months": months, "complete_share": share}


GOOD, POOR = {"sharpe": 1.06}, {"sharpe": 0.88}


@pytest.mark.parametrize(("cell", "adverse", "recent", "book", "held", "branch"), [
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(0.0001, 0.0009), GOOD, POOR, "ACCEPT"),
    (_cell(0.0002, 0.0009), _cell(-0.0001, 0.0008), _cell(0.0001, 0.0009), GOOD, POOR,
     "COST_FRAGILE"),
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(-0.0009, 0.0001), GOOD, POOR,
     "RECENT_FRAGILE"),
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(0.0001, 0.0009), POOR, GOOD,
     "NOT_BETTER_HELD"),
    (_cell(-0.0009, -0.0002), _cell(-0.0009, -0.0002), _cell(-0.001, 0.0), POOR, GOOD, "REJECT"),
    (_cell(-0.0005, 0.0005), _cell(-0.0005, 0.0005), _cell(0.0, 0.001), GOOD, POOR,
     "INCONCLUSIVE"),
    (_cell(-0.0003, 0.0003), _cell(-0.0003, 0.0003), _cell(0.0, 0.001), GOOD, POOR, "NULL"),
    (_cell(0.0002, 0.0009, months=23), _cell(0.0001, 0.0008), _cell(0.0, 0.001), GOOD, POOR,
     "REFUSED"),
])
def test_the_branches(run, cell, adverse, recent, book, held, branch) -> None:
    assert run.branch_for(cell, adverse, recent, book, held) == branch


def test_the_verdict_speaks_the_project_s_vocabulary(run) -> None:
    assert set(run.TOKEN.values()) <= {"accept", "reject", "inconclusive", "refused", "smoke"}


# --- end to end -------------------------------------------------------------------------------------


def _stores(run, tmp_path):
    from swingdesk.contracts.market import CorporateAction, CorporateActionKind
    from swingdesk.market_data import BarStore
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.reference_data import calendar as cal
    from swingdesk.validation.backtest.intraday import session_for

    known = datetime(2026, 9, 20, tzinfo=UTC)
    days = cal.sessions(cal.exchange_for("SPY"), date(2024, 3, 1), date(2024, 8, 30))
    funds = (*run.NIGHT_FUNDS, run.DAY_FUND)
    store = MinuteStore(tmp_path / "minutes.duckdb")
    for n, s in enumerate(days):
        for fund in funds:
            session = session_for(fund, s.session_date)
            length = int((session.close_time - session.open_time) / timedelta(minutes=1))
            base = 100 + n * 0.3
            minutes = [
                Minute(at=session.open_time + timedelta(minutes=i),
                       open=(price := Decimal(str(round(base + 0.0005 * i, 4)))),
                       high=price, low=price, close=price, volume=800, vwap=price)
                for i in range(length)]
            store.write(fund, s.session_date, minutes, known, "test")
    store.close()
    bars = BarStore(tmp_path / "bars.duckdb")
    bars.write_actions([CorporateAction(
        instrument_id=fund, kind=CorporateActionKind.DIVIDEND,
        effective_date=days[15].session_date, value=Decimal("0.4"), knowledge_time=known)
        for fund in funds], knowledge_time=known)
    bars.close()
    return tmp_path, known, days


def test_spy_dividends_reach_the_benchmark_and_not_the_day_leg(run, tmp_path,
                                                               monkeypatch) -> None:
    """The book holds SPY only through the session, so its dividends are simply not earned."""
    import argparse

    import run_pr033 as p33

    path, known, days = _stores(run, tmp_path)
    monkeypatch.setattr(p33, "START", days[0].session_date)
    monkeypatch.setattr(p33, "END", days[-1].session_date)
    series, _ = run.legs(argparse.Namespace(
        minutes=path / "minutes.duckdb", minutes_as_of=known.isoformat(), data=path,
        as_of=known.isoformat(), per_share=0.0))
    ex_date = days[15].session_date
    assert series["spy_night"][ex_date] > series["day"][ex_date], "the night took the dividend"
    plain = days[16].session_date
    dividend_sized = 0.4 / 100  # the fixture pays 0.4 on a price near 100
    assert abs(series["day"][plain] - series["day"][ex_date]) < dividend_sized / 10, \
        "the session leg does not jump on the ex-date - it never owned the dividend"


def test_the_run_goes_end_to_end_on_synthetic_stores(run, tmp_path, monkeypatch) -> None:
    import argparse

    import run_pr033 as p33

    path, known, days = _stores(run, tmp_path)
    monkeypatch.setattr(p33, "START", days[0].session_date)
    monkeypatch.setattr(p33, "END", days[-1].session_date)
    monkeypatch.setattr(p33, "RECENT", days[60].session_date)
    built = run.costed(argparse.Namespace(
        minutes=path / "minutes.duckdb", minutes_as_of=known.isoformat(), data=path,
        as_of=known.isoformat(), per_share=0.005), 50)
    for name in ("combined-less-hold-SPY", "combined", "hold-SPY", "night-small-caps", "day-SPY",
                 "night-SPY", "combined-less-hold-SPY-recent",
                 "combined-less-hold-SPY-cost_adverse"):
        assert name in built["cells"], name
    assert max(built["arms_add_up_to_holding"].values()) < 1e-12
    json.dumps(built)


def test_the_power_mode_writes_widths_and_no_level(run, tmp_path, monkeypatch) -> None:
    import argparse

    import run_pr033 as p33

    path, known, days = _stores(run, tmp_path)
    monkeypatch.setattr(p33, "START", days[0].session_date)
    monkeypatch.setattr(p33, "END", days[-1].session_date)
    estimate = run.power(argparse.Namespace(
        minutes=path / "minutes.duckdb", minutes_as_of=known.isoformat(), data=path,
        as_of=known.isoformat(), per_share=0.005))
    assert "cells" not in estimate
    assert set(estimate["widths"]["combined"]) == {"width", "days"}


def test_the_benchmark_cell_is_holding_spy_not_a_leg_of_it(run, tmp_path, monkeypatch) -> None:
    """`hold-SPY` must be the whole day plus its dividends - the thing the book is trying to beat."""
    import argparse

    import run_pr033 as p33

    path, known, days = _stores(run, tmp_path)
    monkeypatch.setattr(p33, "START", days[0].session_date)
    monkeypatch.setattr(p33, "END", days[-1].session_date)
    monkeypatch.setattr(p33, "RECENT", days[60].session_date)
    args = argparse.Namespace(minutes=path / "minutes.duckdb", minutes_as_of=known.isoformat(),
                              data=path, as_of=known.isoformat(), per_share=0.0)
    series, _ = run.legs(args)
    built = run.build(args, 50)
    held = built["cells"]["hold-SPY"]["described"]["annual_mean"]
    from statistics import fmean
    assert held == pytest.approx(fmean(series["hold"].values()) * 252)
    assert held != pytest.approx(fmean(series["spy_night"].values()) * 252), \
        "the benchmark is not SPY's night"
