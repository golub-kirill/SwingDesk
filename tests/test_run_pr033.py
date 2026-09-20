"""`tools/run_pr033.py`: the overnight return against the session's own, on five index funds.

What must hold, each a way to hand one arm the other's money:

* **the dividend goes to the OVERNIGHT arm**, because it detaches at the ex-date's open and the
  holder at the previous close owns the shares;
* **each arm pays two sides a day**, over the price it bought at, and holding pays none here;
* **the night is close-to-open and the session is open-to-close** — never the same bar twice;
* **the branch reads the primary, its cost-adverse twin and the recent window**, in that order.
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
    spec = importlib.util.spec_from_file_location("_run_pr033", REPO / "tools" / "run_pr033.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sessions(run, rows):
    return [run.Session(session=date(2024, 1, 2) + timedelta(days=n), open=o, close=c,
                        dividend=d)
            for n, (o, c, d) in enumerate(rows)]


# --- the two arms -------------------------------------------------------------------------------------


def test_the_night_is_close_to_open_and_the_session_open_to_close(run) -> None:
    sessions = _sessions(run, [(100.0, 110.0, 0.0), (121.0, 121.0, 0.0)])
    night, inside, _ = run.returns_of(sessions, per_share=0.0)
    day = sessions[1].session
    assert night[day] == pytest.approx(0.1)
    assert inside[day] == pytest.approx(0.0)


def test_the_dividend_is_paid_to_the_overnight_arm_and_not_the_session(run) -> None:
    """The fund opens a dollar lower on its ex-date; the dollar went to whoever held it overnight."""
    sessions = _sessions(run, [(100.0, 100.0, 0.0), (99.0, 99.0, 1.0)])
    night, inside, held = run.returns_of(sessions, per_share=0.0)
    day = sessions[1].session
    assert night[day] == pytest.approx(0.0), "down a dollar, paid a dollar"
    assert inside[day] == pytest.approx(0.0)
    assert held[day] == pytest.approx(0.0)


def test_holding_earns_the_dividend_too_and_pays_no_daily_cost(run) -> None:
    sessions = _sessions(run, [(100.0, 100.0, 0.0), (99.0, 101.0, 1.0)])
    night, _, held = run.returns_of(sessions, per_share=0.01)
    day = sessions[1].session
    assert held[day] == pytest.approx(0.02)
    assert night[day] == pytest.approx(-0.0002)


def test_each_arm_pays_two_sides_over_the_price_it_bought_at(run) -> None:
    sessions = _sessions(run, [(100.0, 200.0, 0.0), (200.0, 200.0, 0.0)])
    night, inside, _ = run.returns_of(sessions, per_share=0.5)
    day = sessions[1].session
    assert night[day] == pytest.approx(-2 * 0.5 / 200.0), "bought at the 200 close"
    assert inside[day] == pytest.approx(-2 * 0.5 / 200.0), "bought at the 200 open"


def test_the_first_session_has_no_night(run) -> None:
    sessions = _sessions(run, [(100.0, 100.0, 0.0), (100.0, 100.0, 0.0)])
    night, _, _ = run.returns_of(sessions, per_share=0.0)
    assert list(night) == [sessions[1].session]


# --- the basket and the branch --------------------------------------------------------------------------


def test_the_basket_weighs_every_fund_the_same_and_windows_by_date(run) -> None:
    early, late = run.RECENT - timedelta(days=1), run.RECENT
    by_fund = {"SPY": {early: 0.02, late: 0.04}, "QQQ": {late: 0.02}}
    assert run.basket_of(by_fund)[late] == pytest.approx(0.03)
    assert run.basket_of(by_fund)[early] == pytest.approx(0.02)
    assert list(run.basket_of(by_fund, since=run.RECENT)) == [late]


def test_the_difference_pairs_by_session(run) -> None:
    day = date(2025, 3, 3)
    assert run.difference({day: 0.03, date(2025, 3, 4): 0.01}, {day: 0.01}) == {day: pytest.approx(0.02)}


def _cell(lo, hi, days=2000, months=120, share=1.0):
    return {"lo": lo, "hi": hi, "width": hi - lo, "estimate": (lo + hi) / 2, "days": days,
            "months": months, "complete_share": share}


@pytest.mark.parametrize(("cell", "adverse", "recent", "branch"), [
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(0.0001, 0.0009), "ACCEPT"),
    (_cell(0.0002, 0.0009), _cell(-0.0001, 0.0008), _cell(0.0001, 0.0009), "COST_FRAGILE"),
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(-0.0009, 0.0001), "RECENT_FRAGILE"),
    (_cell(-0.0009, -0.0002), _cell(-0.0009, -0.0002), _cell(-0.0009, 0.0), "REJECT"),
    (_cell(-0.0005, 0.0005), _cell(-0.0005, 0.0005), _cell(0.0, 0.001), "INCONCLUSIVE"),
    (_cell(-0.0003, 0.0003), _cell(-0.0003, 0.0003), _cell(0.0, 0.001), "NULL"),
    (_cell(0.0002, 0.0009, days=999), _cell(0.0001, 0.0008), _cell(0.0, 0.001), "REFUSED"),
    (_cell(0.0002, 0.0009, share=0.89), _cell(0.0001, 0.0008), _cell(0.0, 0.001), "REFUSED"),
])
def test_the_branches(run, cell, adverse, recent, branch) -> None:
    assert run.branch_for(cell, adverse, recent) == branch


def test_the_verdict_speaks_the_project_s_vocabulary(run) -> None:
    assert set(run.TOKEN.values()) <= {"accept", "reject", "inconclusive", "refused", "smoke"}
    assert run.TOKEN["RECENT_FRAGILE"] == "inconclusive"


# --- end to end -----------------------------------------------------------------------------------------


def _stores(run, tmp_path):
    from swingdesk.contracts.market import CorporateAction, CorporateActionKind
    from swingdesk.market_data import BarStore
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.reference_data import calendar as cal
    from swingdesk.validation.backtest.intraday import session_for

    known = datetime(2026, 9, 20, tzinfo=UTC)
    days = cal.sessions(cal.exchange_for("SPY"), date(2024, 3, 1), date(2024, 8, 30))
    store = MinuteStore(tmp_path / "minutes.duckdb")
    for n, s in enumerate(days):
        for fund in run.FUNDS:
            session = session_for(fund, s.session_date)
            length = int((session.close_time - session.open_time) / timedelta(minutes=1))
            base = 100 + n * 0.5
            minutes = [
                Minute(at=session.open_time + timedelta(minutes=i),
                       open=(price := Decimal(str(round(base + 0.001 * i, 4)))),
                       high=price, low=price, close=price, volume=1000, vwap=price)
                for i in range(length)]
            store.write(fund, s.session_date, minutes, known, "test")
    store.close()
    bars = BarStore(tmp_path / "bars.duckdb")
    bars.write_actions([CorporateAction(
        instrument_id=fund, kind=CorporateActionKind.DIVIDEND,
        effective_date=days[20].session_date, value=Decimal("0.5"), knowledge_time=known)
        for fund in run.FUNDS], knowledge_time=known)
    bars.close()
    return tmp_path, known, days


def test_the_run_goes_end_to_end_on_synthetic_stores(run, tmp_path, monkeypatch) -> None:
    import argparse

    path, known, days = _stores(run, tmp_path)
    monkeypatch.setattr(run, "START", days[0].session_date)
    monkeypatch.setattr(run, "END", days[-1].session_date)
    monkeypatch.setattr(run, "RECENT", days[60].session_date)
    args = argparse.Namespace(minutes=path / "minutes.duckdb", minutes_as_of=known.isoformat(),
                              data=path, as_of=known.isoformat(), per_share=0.005)
    built = run.costed(args, 50)
    for name in (f"basket-{run.NIGHT}", f"basket-{run.SESSION}", f"basket-{run.NIGHT}-recent",
                 f"basket-{run.NIGHT}-cost_adverse", f"basket-{run.NIGHT}-less-{run.SESSION}",
                 "basket-hold", "SPY-N", "EFA-hold"):
        assert name in built["cells"], name
    assert built["cells"][f"basket-{run.NIGHT}"]["days"] == len(days) - 1
    assert built["dividends_paid"]["SPY"] == pytest.approx(0.5)
    json.dumps(built)


def test_the_power_mode_writes_widths_and_no_level(run, tmp_path, monkeypatch) -> None:
    import argparse

    path, known, days = _stores(run, tmp_path)
    monkeypatch.setattr(run, "START", days[0].session_date)
    monkeypatch.setattr(run, "END", days[-1].session_date)
    estimate = run.power(argparse.Namespace(
        minutes=path / "minutes.duckdb", minutes_as_of=known.isoformat(), data=path,
        as_of=known.isoformat(), per_share=0.005))
    assert "cells" not in estimate
    assert set(estimate["widths"][f"basket-{run.NIGHT}"]) == {"width", "days"}


def test_the_two_arms_multiply_back_to_holding(run) -> None:
    """§9's first check: same two prices, so on a session with no dividend they must agree."""
    sessions = _sessions(run, [(100.0, 103.0, 0.0), (101.0, 107.0, 0.0), (99.0, 104.0, 0.0)])
    night, inside, held = run.returns_of(sessions, per_share=0.0)
    assert run.adds_up(night, inside, held, {}) < 1e-12
    broken = {day: value + 0.001 for day, value in inside.items()}
    assert run.adds_up(night, broken, held, {}) > 1e-4


def test_an_ex_dividend_session_is_left_out_of_that_check(run) -> None:
    """Compounding reinvests the dividend at the open, holding takes it as cash: not an identity."""
    sessions = _sessions(run, [(100.0, 100.0, 0.0), (99.0, 105.0, 1.0)])
    night, inside, held = run.returns_of(sessions, per_share=0.0)
    day = sessions[1].session
    assert run.adds_up(night, inside, held, {}) > 1e-4, "it does not hold on an ex-date"
    assert run.adds_up(night, inside, held, {day: 1.0}) == 0.0, "so the ex-date is skipped"


def test_the_printer_names_the_study_that_calls_it(run, capsys) -> None:
    """`PR-034` borrows this printer; it must not print `PR-033`'s name over another study."""
    run.report({"prereg": "PR-034", "verdict": "accept", "branch": "ACCEPT", "excluded": {},
                "dividends_paid": {}, "cells": {}})
    assert capsys.readouterr().out.startswith("PR-034")
