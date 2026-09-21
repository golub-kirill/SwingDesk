"""`tools/run_pr036.py`: the same two arms on daily bars, over the window before 2016.

What must hold:

* **a daily bar becomes a session** with its open, its close and the dividend of its own date;
* **the windows do not leak into each other** — the verdict reads 2004-2015 and nothing later;
* **the overlap reading exists and is compared with `PR-034`**, because the pre-2016 number is
  only worth what that comparison says;
* **no recency gate**, and the remaining gates are `PR-034`'s.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def run() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_run_pr036", REPO / "tools" / "run_pr036.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- windows and gates -------------------------------------------------------------------------------


def test_the_verdict_window_ends_before_the_minute_feed_starts(run) -> None:
    assert run.BEFORE_LAST < run.OVERLAP_FIRST
    assert run.BEFORE_FIRST == date(2004, 1, 30), "VB's first session"


def test_a_window_takes_its_own_sessions_only(run) -> None:
    series = {date(2003, 12, 31): 1.0, date(2004, 1, 30): 2.0, date(2015, 12, 31): 3.0,
              date(2016, 1, 4): 4.0}
    assert sorted(run.within(series, run.BEFORE_FIRST, run.BEFORE_LAST)) == [
        date(2004, 1, 30), date(2015, 12, 31)]


def _cell(lo, hi, days=2000, months=120, share=1.0):
    return {"lo": lo, "hi": hi, "width": hi - lo, "estimate": (lo + hi) / 2, "days": days,
            "months": months, "complete_share": share}


GOOD, POOR = {"sharpe": 1.06}, {"sharpe": 0.59}


@pytest.mark.parametrize(("cell", "adverse", "night", "held", "branch"), [
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), GOOD, POOR, "ACCEPT"),
    (_cell(0.0002, 0.0009), _cell(-0.0001, 0.0008), GOOD, POOR, "COST_FRAGILE"),
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), POOR, GOOD, "NOT_BETTER_HELD"),
    (_cell(-0.0009, -0.0002), _cell(-0.0009, -0.0002), POOR, GOOD, "REJECT"),
    (_cell(-0.0005, 0.0005), _cell(-0.0005, 0.0005), GOOD, POOR, "INCONCLUSIVE"),
    (_cell(-0.0003, 0.0003), _cell(-0.0003, 0.0003), GOOD, POOR, "NULL"),
    (_cell(0.0002, 0.0009, days=999), _cell(0.0001, 0.0008), GOOD, POOR, "REFUSED"),
])
def test_the_branches(run, cell, adverse, night, held, branch) -> None:
    assert run.branch_for(cell, adverse, night, held) == branch


def test_there_is_no_recency_gate(run) -> None:
    """This window IS the old one, so a 'recent' reading would be meaningless here."""
    import inspect

    assert "recent" not in inspect.getsource(run.branch_for)


# --- the price source --------------------------------------------------------------------------------


def _store(run, tmp_path, days=40, dividend_on=10):
    from swingdesk.contracts.market import (
        Bar,
        CorporateAction,
        CorporateActionKind,
        Interval,
        Series,
    )
    from swingdesk.market_data import BarStore
    from swingdesk.reference_data import calendar as cal

    known = datetime(2026, 9, 20, tzinfo=UTC)
    sessions = cal.sessions(cal.exchange_for("IJR"), date(2004, 2, 2), date(2004, 12, 31))[:days]
    store = BarStore(tmp_path / "bars.duckdb")
    for fund in run.FUNDS:
        bars = []
        for n, s in enumerate(sessions):
            base = Decimal(str(round(100 + n * 0.2, 4)))
            bars.append(Bar(instrument_id=fund, session_date=s.session_date, interval=Interval.DAY,
                            series=Series.RAW, event_time=s.open_time, knowledge_time=known,
                            open=base, high=base + Decimal("1"), low=base - Decimal("1"),
                            close=base + Decimal("0.1"), volume=1000))
        store.write(bars, knowledge_time=known)
        store.write_actions([CorporateAction(
            instrument_id=fund, kind=CorporateActionKind.DIVIDEND,
            effective_date=sessions[dividend_on].session_date, value=Decimal("0.3"),
            knowledge_time=known)], knowledge_time=known)
    store.close()
    return tmp_path, known, sessions


def test_a_daily_bar_becomes_a_session_with_its_own_dividend(run, tmp_path) -> None:
    from swingdesk.market_data import BarStore

    path, known, sessions = _store(run, tmp_path)
    with BarStore(path / "bars.duckdb") as store:
        got = run.sessions_from_bars(store, "IJR", known)
    assert len(got) == len(sessions)
    assert got[0].open == pytest.approx(100.0) and got[0].close == pytest.approx(100.1)
    paid = [s for s in got if s.dividend]
    assert len(paid) == 1 and paid[0].session == sessions[10].session_date


def test_the_reproduction_check_reports_the_gap_and_refuses_without_the_prior(run,
                                                                             tmp_path) -> None:
    payload = {"cells": {"small-N-overlap": {"described": {"annual_mean": 0.1400}}}}
    prior = tmp_path / "PR-034.json"
    prior.write_text(json.dumps({"cells": {"small-N": {"described": {"annual_mean": 0.1383}}}}),
                     encoding="utf-8")
    got = run.reproduces_pr034(payload, prior)
    assert got["checked"] and got["differ_by"] == pytest.approx(0.0017, abs=1e-6)
    assert run.reproduces_pr034(payload, tmp_path / "absent.json") == {"checked": False}


def test_the_run_goes_end_to_end_on_a_synthetic_store(run, tmp_path, monkeypatch) -> None:
    import argparse

    path, known, sessions = _store(run, tmp_path)
    monkeypatch.setattr(run, "BEFORE_FIRST", sessions[0].session_date)
    monkeypatch.setattr(run, "BEFORE_LAST", sessions[-1].session_date)
    built = run.costed(argparse.Namespace(data=path, as_of=known.isoformat(), per_share=0.005), 50)
    for name in ("small-N-before", "small-D-before", "small-hold-before",
                 "small-N-before-cost_adverse", "IJR-N-before", "VB-N-before"):
        assert name in built["cells"], name
    assert max(built["arms_add_up_to_holding"].values()) < 1e-12
    json.dumps(built)


def test_the_power_mode_writes_widths_and_no_level(run, tmp_path, monkeypatch) -> None:
    import argparse

    path, known, sessions = _store(run, tmp_path)
    monkeypatch.setattr(run, "BEFORE_FIRST", sessions[0].session_date)
    monkeypatch.setattr(run, "BEFORE_LAST", sessions[-1].session_date)
    estimate = run.power(argparse.Namespace(data=path, as_of=known.isoformat(), per_share=0.005))
    assert "cells" not in estimate
    assert set(estimate["widths"]["small-N-before"]) == {"width", "days"}
