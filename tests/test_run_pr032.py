"""`tools/run_pr032.py`: `PR-031`'s rule on three funds it never read, since the paper appeared.

What must hold, each a way to answer a different question than the registered one:

* **the basket is equal capital**, so one fund's day cannot carry it by trading more;
* **the verdict's window starts at the paper**, and a session before it is not in the primary;
* **a fund with no minutes counts against the complete share** rather than shrinking the window;
* **the branch reads the basket and its cost-adverse twin**, in `PR-031`'s order.
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


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def run() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    return _load("_run_pr032", REPO / "tools" / "run_pr032.py")


def _traded(run, session: date, value: float, fund_days: int = 1):
    row = run.p31.Traded(session=session, leverage=2.0, trades=fund_days)
    row.returns = {costing: value for costing in run.p31.COSTS}
    return row


# --- the basket -------------------------------------------------------------------------------------


def test_the_basket_weighs_every_fund_the_same(run) -> None:
    day = date(2025, 1, 2)
    traded = {"IWM": [_traded(run, day, 0.03)], "DIA": [_traded(run, day, 0.01)],
              "EFA": [_traded(run, day, 0.02)]}
    assert run.basket_of(traded, "net")[day] == pytest.approx(0.02)


def test_a_fund_missing_a_session_does_not_weigh_the_others_down(run) -> None:
    day = date(2025, 1, 2)
    traded = {"IWM": [_traded(run, day, 0.03)], "DIA": [], "EFA": [_traded(run, day, 0.01)]}
    assert run.basket_of(traded, "net")[day] == pytest.approx(0.02)


def test_the_primary_starts_at_publication(run) -> None:
    before, after = run.SINCE - timedelta(days=1), run.SINCE
    traded = {"IWM": [_traded(run, before, 0.05), _traded(run, after, 0.01)]}
    assert list(run.basket_of(traded, "net")) == [after]
    assert sorted(run.basket_of(traded, "net", since=None)) == [before, after]


def test_each_costing_reads_its_own_column(run) -> None:
    day = date(2025, 1, 2)
    row = _traded(run, day, 0.02)
    row.returns["cost_adverse"] = 0.005
    assert run.basket_of({"IWM": [row]}, "cost_adverse")[day] == pytest.approx(0.005)


# --- the reading and the branch ----------------------------------------------------------------------


def test_an_unfetched_session_counts_against_the_complete_share(run) -> None:
    days = {date(2025, 1, 2) + timedelta(days=n): 0.001 for n in range(40)}
    cell = run.reading(days, 20, sessions=80)
    assert cell["days"] == 40 and cell["complete_share"] == pytest.approx(0.5)


def _cell(lo, hi, days=600, months=28, share=1.0):
    return {"lo": lo, "hi": hi, "width": hi - lo, "estimate": (lo + hi) / 2, "days": days,
            "months": months, "complete_share": share}


@pytest.mark.parametrize(("cell", "adverse", "branch"), [
    (_cell(0.0002, 0.0009), _cell(0.0001, 0.0008), "ACCEPT"),
    (_cell(0.0002, 0.0009), _cell(-0.0001, 0.0008), "COST_FRAGILE"),
    (_cell(-0.0009, -0.0002), _cell(-0.0009, -0.0002), "REJECT"),
    (_cell(-0.0005, 0.0005), _cell(-0.0005, 0.0005), "INCONCLUSIVE"),
    (_cell(-0.0003, 0.0003), _cell(-0.0003, 0.0003), "NULL"),
    (_cell(0.0002, 0.0009, days=499), _cell(0.0001, 0.0008), "REFUSED"),
    (_cell(0.0002, 0.0009, months=23), _cell(0.0001, 0.0008), "REFUSED"),
    (_cell(0.0002, 0.0009, share=0.89), _cell(0.0001, 0.0008), "REFUSED"),
])
def test_the_branches(run, cell, adverse, branch) -> None:
    assert run.branch_for(cell, adverse) == branch


# --- end to end ---------------------------------------------------------------------------------------


def _store(run, tmp_path, funds=("IWM", "DIA", "EFA")):
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.reference_data import calendar as cal
    from swingdesk.validation.backtest.intraday import session_for

    store = MinuteStore(tmp_path / "minutes.duckdb")
    known = datetime(2026, 9, 19, tzinfo=UTC)
    days = cal.sessions(cal.exchange_for("IWM"), date(2024, 4, 1), date(2024, 9, 30))
    for n, s in enumerate(days):
        for name in funds:
            session = session_for(name, s.session_date)
            length = int((session.close_time - session.open_time) / timedelta(minutes=1))
            drift = 0.02 if n % 2 else -0.01
            minutes = [
                Minute(at=session.open_time + timedelta(minutes=i),
                       open=(price := Decimal(str(round(100 * (1 + drift * i / length) + n * 0.1,
                                                        4)))),
                       high=price + Decimal("0.02"), low=price - Decimal("0.02"), close=price,
                       volume=1000, vwap=price)
                for i in range(length)]
            store.write(name, s.session_date, minutes, known, "test")
    store.close()
    return tmp_path / "minutes.duckdb", known, days


def test_the_run_goes_end_to_end_on_a_synthetic_store(run, tmp_path, monkeypatch) -> None:
    import argparse

    path, known, days = _store(run, tmp_path)
    monkeypatch.setattr(run, "START", days[0].session_date)
    monkeypatch.setattr(run, "END", days[-1].session_date)
    monkeypatch.setattr(run, "SINCE", days[30].session_date)
    built = run.build(argparse.Namespace(minutes=path, minutes_as_of=known.isoformat()), 50)
    assert set(built["cells"]) == {"basket", "basket-paper", "basket-cost_adverse", "basket-gross",
                                   "basket-before-publication", "IWM", "DIA", "EFA"}
    assert built["cells"]["basket"]["days"] == len(days) - 30
    assert built["cells"]["basket-before-publication"]["days"] == len(days) - 15
    json.dumps(built)


def test_the_power_mode_writes_widths_and_no_level(run, tmp_path, monkeypatch) -> None:
    import argparse

    path, known, days = _store(run, tmp_path)
    monkeypatch.setattr(run, "START", days[0].session_date)
    monkeypatch.setattr(run, "END", days[-1].session_date)
    monkeypatch.setattr(run, "SINCE", days[30].session_date)
    estimate = run.power(argparse.Namespace(minutes=path, minutes_as_of=known.isoformat()))
    assert "basket" in estimate["widths"] and "cells" not in estimate
    assert set(estimate["widths"]["basket"]) == {"width", "days"}


def test_a_session_with_half_its_minutes_is_left_out(run, tmp_path) -> None:
    """Coverage under 90% is thin: the gaps carry a stale close, and the noise area reads it."""
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.validation.backtest.intraday import session_for

    known = datetime(2026, 9, 19, tzinfo=UTC)
    store = MinuteStore(tmp_path / "thin.duckdb")
    session = session_for("IWM", date(2024, 6, 3))
    price = Decimal("100")
    store.write("IWM", session.session_date,
                [Minute(at=session.open_time + timedelta(minutes=i), open=price, high=price,
                        low=price, close=price, volume=10) for i in range(100)],
                known, "test")
    store.close()
    with MinuteStore(tmp_path / "thin.duckdb") as reading_store:
        days, missing, _ = run.load_days(reading_store, "IWM", known)
    assert days == [] and missing["thin"] == 1


def test_spy_through_this_loader_must_match_pr031(run, tmp_path) -> None:
    """The fixed point: PR-031's own after-publication estimate, from this tool's loader."""
    import statistics

    path, known, _days = _store(run, tmp_path, funds=("SPY",))
    prior = tmp_path / "PR-031.json"
    with __import__("swingdesk.market_data.minutes", fromlist=["MinuteStore"]).MinuteStore(
            path) as store:
        loaded, _, _ = run.load_days(store, "SPY", known)
        rows, _ = run.p31.run_instrument(loaded, both=False)
        truth = statistics.fmean([r.returns["net"] for r in rows
                                  if r.session > run.p31.PUBLISHED])
        prior.write_text(json.dumps({"cells": {"SPY-long": {"after_publication": {
            "estimate": truth}}}}), encoding="utf-8")
        assert run.repeats_pr031(store, known, prior)["differs_by"] == pytest.approx(0, abs=1e-12)
        prior.write_text(json.dumps({"cells": {"SPY-long": {"after_publication": {
            "estimate": truth + 0.001}}}}), encoding="utf-8")
        assert run.repeats_pr031(store, known, prior)["differs_by"] == pytest.approx(0.001)
        assert run.repeats_pr031(store, known, tmp_path / "absent.json") == {"checked": False}
