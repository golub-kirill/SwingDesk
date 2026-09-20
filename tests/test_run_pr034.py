"""`tools/run_pr034.py`: `PR-033`'s two arms on small-cap funds it never read, with harder gates.

What must hold:

* **the verdict's basket is the two SMALL-cap funds**, and the mid-cap one is counted apart;
* **an `ACCEPT` must clear three gates** — a whole cent a share, the recent window, and holding the
  same funds per unit of risk — and each has its own branch when it fails;
* **the arms are `PR-033`'s**, imported rather than copied.
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
    spec = importlib.util.spec_from_file_location("_run_pr034", REPO / "tools" / "run_pr034.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- the funds and the arms ---------------------------------------------------------------------------


def test_the_verdict_reads_the_small_caps_and_the_mid_cap_is_apart(run) -> None:
    assert run.SMALL == ("IJR", "VB")
    assert run.BOUNDARY == ("MDY",)
    assert "MDY" not in run.SMALL


def test_the_arms_are_pr033_s_own_functions(run) -> None:
    """Imported, not copied: a fix there must reach here."""
    import run_pr033 as p33

    assert run.p33.returns_of is p33.returns_of
    assert run.p33.adds_up is p33.adds_up
    assert (run.NIGHT, run.SESSION) == (p33.NIGHT, p33.SESSION)


# --- the gates ------------------------------------------------------------------------------------------


def _cell(lo, hi, days=2000, months=120, share=1.0):
    return {"lo": lo, "hi": hi, "width": hi - lo, "estimate": (lo + hi) / 2, "days": days,
            "months": months, "complete_share": share}


GOOD, POOR = {"sharpe": 0.91}, {"sharpe": 0.56}


@pytest.mark.parametrize(("cell", "adverse", "recent", "night", "held", "branch"), [
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(0.0001, 0.0009), GOOD, POOR, "ACCEPT"),
    (_cell(0.0002, 0.0009), _cell(-0.0001, 0.0008), _cell(0.0001, 0.0009), GOOD, POOR,
     "COST_FRAGILE"),
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(-0.0009, 0.0001), GOOD, POOR,
     "RECENT_FRAGILE"),
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(0.0001, 0.0009), POOR, GOOD,
     "NOT_BETTER_HELD"),
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(0.0001, 0.0009), GOOD, GOOD,
     "NOT_BETTER_HELD"),
    (_cell(-0.0009, -0.0002), _cell(-0.0009, -0.0002), _cell(-0.001, 0.0), POOR, GOOD, "REJECT"),
    (_cell(-0.0005, 0.0005), _cell(-0.0005, 0.0005), _cell(0.0, 0.001), GOOD, POOR,
     "INCONCLUSIVE"),
    (_cell(-0.0003, 0.0003), _cell(-0.0003, 0.0003), _cell(0.0, 0.001), GOOD, POOR, "NULL"),
    (_cell(0.0002, 0.0009, days=999), _cell(0.0001, 0.0008), _cell(0.0, 0.001), GOOD, POOR,
     "REFUSED"),
])
def test_the_branches(run, cell, adverse, recent, night, held, branch) -> None:
    assert run.branch_for(cell, adverse, recent, night, held) == branch


def test_a_tie_on_risk_is_not_better_than_holding(run) -> None:
    """Equal Sharpe ratios do not clear the gate: the night must BEAT holding, not match it."""
    assert run.branch_for(_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), _cell(0.0001, 0.0009),
                          {"sharpe": 0.8}, {"sharpe": 0.8}) == "NOT_BETTER_HELD"


def test_the_verdict_speaks_the_project_s_vocabulary(run) -> None:
    assert set(run.TOKEN.values()) <= {"accept", "reject", "inconclusive", "refused", "smoke"}
    assert run.TOKEN["NOT_BETTER_HELD"] == "inconclusive"


# --- end to end -------------------------------------------------------------------------------------------


def _stores(run, tmp_path):
    from swingdesk.contracts.market import CorporateAction, CorporateActionKind
    from swingdesk.market_data import BarStore
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.reference_data import calendar as cal
    from swingdesk.validation.backtest.intraday import session_for

    known = datetime(2026, 9, 20, tzinfo=UTC)
    days = cal.sessions(cal.exchange_for("IJR"), date(2024, 3, 1), date(2024, 8, 30))
    store = MinuteStore(tmp_path / "minutes.duckdb")
    for n, s in enumerate(days):
        for fund in run.FUNDS:
            session = session_for(fund, s.session_date)
            length = int((session.close_time - session.open_time) / timedelta(minutes=1))
            base = 100 + n * 0.4
            minutes = [
                Minute(at=session.open_time + timedelta(minutes=i),
                       open=(price := Decimal(str(round(base - 0.001 * i, 4)))),
                       high=price, low=price, close=price, volume=500, vwap=price)
                for i in range(length)]
            store.write(fund, s.session_date, minutes, known, "test")
    store.close()
    bars = BarStore(tmp_path / "bars.duckdb")
    bars.write_actions([CorporateAction(
        instrument_id=fund, kind=CorporateActionKind.DIVIDEND,
        effective_date=days[10].session_date, value=Decimal("0.25"), knowledge_time=known)
        for fund in run.FUNDS], knowledge_time=known)
    bars.close()
    return tmp_path, known, days


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
    for name in ("small-N", "small-D", "small-N-recent", "small-N-cost_adverse", "small-hold",
                 "IJR-N", "VB-hold", "MDY-N"):
        assert name in built["cells"], name
    assert built["cells"]["small-N"]["days"] == len(days) - 1
    assert built["cells"]["small-N-recent"]["days"] == len(days) - 60, "the gate reads the tail"
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
    assert set(estimate["widths"]["small-N"]) == {"width", "days"}


def test_a_session_missing_its_middle_minutes_is_still_read(run, tmp_path) -> None:
    """A fund whose middle minutes hold no trade still has an open and a close: PR-033's 90%
    coverage rule would throw the session away, and this study needs two prices."""
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.validation.backtest.intraday import session_for

    known = datetime(2026, 9, 20, tzinfo=UTC)
    day = date(2024, 6, 3)
    session = session_for("VB", day)
    length = int((session.close_time - session.open_time) / timedelta(minutes=1))
    price = Decimal("100")
    minutes = [Minute(at=session.open_time + timedelta(minutes=i), open=price, high=price,
                      low=price, close=price, volume=100)
               for i in (0, 1, 2, length - 2, length - 1)]
    with MinuteStore(tmp_path / "sparse.duckdb") as store:
        store.write("VB", day, minutes, known, "test")
    with MinuteStore(tmp_path / "sparse.duckdb") as store:
        sessions, missing = run.load_sessions(store, "VB", known, {})
    assert [s.session for s in sessions] == [day]
    assert "thin" not in missing


def test_a_session_whose_first_trade_is_late_is_left_out(run, tmp_path) -> None:
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.validation.backtest.intraday import session_for

    known = datetime(2026, 9, 20, tzinfo=UTC)
    day = date(2024, 6, 3)
    session = session_for("VB", day)
    length = int((session.close_time - session.open_time) / timedelta(minutes=1))
    price = Decimal("100")
    with MinuteStore(tmp_path / "late.duckdb") as store:
        store.write("VB", day, [Minute(at=session.open_time + timedelta(minutes=i), open=price,
                                       high=price, low=price, close=price, volume=100)
                                for i in (run.BELL + 1, length - 1)], known, "test")
    with MinuteStore(tmp_path / "late.duckdb") as store:
        sessions, missing = run.load_sessions(store, "VB", known, {})
    assert sessions == [] and missing["no_opening_minute"] == 1


def test_a_session_whose_last_trade_is_early_is_left_out(run, tmp_path) -> None:
    """The closing price is one of the two this study needs; a session that stops trading at
    lunchtime has no close to buy at."""
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.validation.backtest.intraday import session_for

    known = datetime(2026, 9, 20, tzinfo=UTC)
    day = date(2024, 6, 3)
    session = session_for("VB", day)
    length = int((session.close_time - session.open_time) / timedelta(minutes=1))
    price = Decimal("100")
    with MinuteStore(tmp_path / "early.duckdb") as store:
        store.write("VB", day, [Minute(at=session.open_time + timedelta(minutes=i), open=price,
                                       high=price, low=price, close=price, volume=100)
                                for i in (0, length - 20)], known, "test")
    with MinuteStore(tmp_path / "early.duckdb") as store:
        sessions, missing = run.load_sessions(store, "VB", known, {})
    assert sessions == [] and missing["no_closing_minute"] == 1
