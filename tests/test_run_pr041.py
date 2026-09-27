"""`tools/run_pr041.py` - Asia-Pacific funds through the US session, the third leg `DR-055` names.

What these hold: the cost of each side, the identity the arms must satisfy, which session a dividend
belongs to, the decision rule's order, the three-leg book's construction, and the sample the basis
check reads - which must be the same pairs the fetcher was given.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pr41():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("run_pr041", REPO / "tools" / "run_pr041.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _sessions(pr41, rows):
    import run_pr033 as p33

    return [p33.Session(session=d, open=o, close=c, dividend=v) for d, o, c, v in rows]


D1, D2, D3 = date(2016, 1, 4), date(2016, 1, 5), date(2016, 1, 6)


def test_the_cost_of_a_side(pr41) -> None:
    import run_pr040 as p40

    assert pr41.side_cost(30.0, True, None) == 0.0, "gross costs nothing"
    assert pr41.side_cost(30.0, False, 0.0) == pytest.approx(p40.CAT_PER_SHARE / 30.0)
    assert pr41.side_cost(30.0, True, 0.0) == pytest.approx(
        p40.SEC_RATE + (p40.TAF_PER_SHARE + p40.CAT_PER_SHARE) / 30.0)
    assert pr41.side_cost(30.0, False, 0.005) == pytest.approx(
        (p40.CAT_PER_SHARE + 0.005) / 30.0)


def test_at_zero_cost_the_arms_compound_to_holding(pr41) -> None:
    sessions = _sessions(pr41, [(D1, 30, 30.5, 0), (D2, 31, 30.2, 0), (D3, 29.9, 31.4, 0)])
    night, inside, held = pr41.arms(sessions, None)
    for day in (D2, D3):
        assert (1 + night[day]) * (1 + inside[day]) - 1 == pytest.approx(held[day], abs=1e-12)


def test_the_dividend_belongs_to_the_night(pr41) -> None:
    sessions = _sessions(pr41, [(D1, 30, 30, 0), (D2, 29.5, 29.5, 0.5)])
    night, inside, _ = pr41.arms(sessions, None)
    assert night[D2] == pytest.approx(0.0) and inside[D2] == pytest.approx(0.0)


def _cell(lo, hi):
    return {"lo": lo, "hi": hi, "width": hi - lo, "days": 2697, "months": 129,
            "complete_share": 1.0}


@pytest.mark.parametrize(("cell", "half", "recent", "sharpe", "held", "basis", "expected"), [
    (_cell(0.0001, 0.0005), _cell(0.00005, 0.0004), 0.0002, 0.9, 0.4, True, "ACCEPT"),
    (_cell(0.0001, 0.0005), _cell(-0.0001, 0.0004), 0.0002, 0.9, 0.4, True, "COST_FRAGILE"),
    (_cell(0.0001, 0.0005), _cell(0.00005, 0.0004), -0.0001, 0.9, 0.4, True, "RECENT_FRAGILE"),
    (_cell(0.0001, 0.0005), _cell(0.00005, 0.0004), 0.0002, 0.3, 0.4, True, "NOT_BETTER_HELD"),
    (_cell(-0.0005, -0.0001), _cell(-0.0006, -0.0002), 0.0, 0.0, 0.4, True, "REJECT"),
    (_cell(-0.0005, 0.0005), _cell(-0.0006, 0.0004), 0.0, 0.0, 0.4, True, "INCONCLUSIVE"),
    (_cell(-0.0002, 0.0002), _cell(-0.0003, 0.0001), 0.0, 0.0, 0.4, True, "NULL"),
    (_cell(0.0001, 0.0005), _cell(0.00005, 0.0004), 0.0002, 0.9, 0.4, False, "REFUSED"),
])
def test_the_decision_rule_refuses_first_then_gates(pr41, cell, half, recent, sharpe, held,
                                                     basis, expected) -> None:
    assert pr41.branch_for(cell, half, recent, sharpe, held, basis) == expected


def test_the_recent_window_is_the_last_48_months(pr41) -> None:
    series = {date(2020, 1, 1) + timedelta(days=30 * i): 0.0 for i in range(80)}
    kept = pr41.last_months(series)
    months = sorted({(d.year, d.month) for d in kept})
    assert len(months) == 48 and months[-1] == max((d.year, d.month) for d in series)


def _book_sessions(pr41):
    rows = {}
    base = [(D1, 100, 101, 0), (D2, 102, 101.5, 0), (D3, 101, 103, 0)]
    for fund in (*pr41.FUNDS, *pr41.NIGHT_FUNDS, pr41.DAY_FUND):
        rows[fund] = _sessions(pr41, base)
    return rows


def test_a_book_with_no_asia_share_is_pr035s_two_leg_book(pr41, monkeypatch) -> None:
    import run_pr033 as p33
    import run_pr035 as p35

    monkeypatch.setattr(pr41, "FIRST", D1)
    sessions = _book_sessions(pr41)
    two, _ = pr41.book(sessions, None, 0.0)
    night = p33.basket_of({f: pr41.arms(sessions[f], None)[0] for f in pr41.NIGHT_FUNDS})
    _, spy_day, _ = pr41.arms(sessions[pr41.DAY_FUND], None)
    assert two == pytest.approx(p35.compounded(night, spy_day))


def test_the_three_leg_book_splits_the_day_equally(pr41, monkeypatch) -> None:
    monkeypatch.setattr(pr41, "FIRST", D1)
    sessions = _book_sessions(pr41)
    # Make the Asia funds' sessions differ from SPY's, so the split is visible.
    for fund in pr41.FUNDS:
        sessions[fund] = _sessions(pr41, [(D1, 100, 101, 0), (D2, 100, 104, 0),
                                          (D3, 101, 103, 0)])
    three, _ = pr41.book(sessions, None, 0.5)
    night = (102 - 101) / 101
    spy_day, asia_day = (101.5 - 102) / 102, (104 - 100) / 100
    assert three[D2] == pytest.approx((1 + night) * (1 + 0.5 * spy_day + 0.5 * asia_day) - 1)


def test_the_basis_sample_is_the_same_pairs_every_time(pr41) -> None:
    rows = [(date(2016, 1, 4) + timedelta(days=i), 30, 30, 0) for i in range(200)]
    sessions = {fund: _sessions(pr41, rows) for fund in pr41.FUNDS}
    first, second = pr41.sample_sessions(sessions), pr41.sample_sessions(sessions)
    assert first == second
    assert len(first) == pr41.SAMPLE_PER_FUND * len(pr41.FUNDS)
