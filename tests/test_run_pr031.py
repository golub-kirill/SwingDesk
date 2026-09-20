"""`tools/run_pr031.py`: the published intraday momentum rule, read without look-ahead.

What must hold, each a way to report a rule that was not the paper's:

* **the noise area is the paper's**: the mean absolute move from the open at each minute over the
  last 14 sessions, the upper bound from the higher of the open and the prior close;
* **a decision reads the minute that ENDS at the half hour and fills at the next minute's open** -
  a spike inside the decision minute itself is not seen until the next half hour;
* **long only means long only**: a price under the lower bound is flat unless the short leg trades;
* **the day's return is the leverage times the moves, less two sides' cost a trade, over the open.**
"""

from __future__ import annotations

import importlib.util
import json
import math
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
    spec = importlib.util.spec_from_file_location("_run_pr031", REPO / "tools" / "run_pr031.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _day(run, closes, open_=100.0, vwap=None, session=date(2024, 1, 2)):
    """A day whose every minute opens where the last one closed."""
    opens = [open_, *closes[:-1]]
    return run.Day(session=session, open=open_, close=closes[-1], opens=tuple(opens),
                   closes=tuple(closes), vwap=tuple(vwap or [open_] * len(closes)), coverage=1.0)


def _flat(run, value=0.01, length=390):
    return [value] * length


# --- the noise area ----------------------------------------------------------------------------------


def test_the_noise_is_the_mean_absolute_move_from_the_open(run) -> None:
    ups = [_day(run, [101.0] * 390) for _ in range(7)]
    downs = [_day(run, [97.0] * 390) for _ in range(7)]
    sigma = run.noise(ups + downs, 390)
    assert sigma[0] == pytest.approx((7 * 0.01 + 7 * 0.03) / 14)


def test_the_noise_reads_only_the_last_fourteen_sessions(run) -> None:
    old = [_day(run, [150.0] * 390)]
    recent = [_day(run, [101.0] * 390) for _ in range(14)]
    assert run.noise(old + recent, 390)[5] == pytest.approx(0.01)
    assert run.noise(recent[:13], 390) is None


def test_leverage_targets_two_percent_and_caps_at_four(run) -> None:
    calm = [_day(run, [100.0 * (1.001 if i % 2 else 1.0)] * 390) for i in range(15)]
    assert run.leverage(calm) == 4.0
    wild = [_day(run, [100.0 * (1.05 if i % 2 else 1.0)] * 390) for i in range(15)]
    closes = [d.close for d in wild]
    import statistics
    from itertools import pairwise

    spread = statistics.stdev([b / a - 1 for a, b in pairwise(closes)])
    assert run.leverage(wild) == pytest.approx(0.02 / spread)
    assert run.leverage(wild[:14]) is None


# --- the decisions -----------------------------------------------------------------------------------


def test_a_break_above_the_upper_bound_and_the_vwap_goes_long_at_the_next_open(run) -> None:
    """Upper bound 101 (100 x 1.01); the minute ending at 10:00 closes at 102."""
    closes = [100.0] * 29 + [102.0] * 361
    trades = run.trade_day(_day(run, closes), 100.0, _flat(run), both=False)
    assert trades == [(1, 102.0, 102.0)]


def test_the_decision_minute_itself_is_not_seen(run) -> None:
    """A spike in the 10:00 minute (offset 30) is read at 10:30, not at 10:00."""
    closes = [100.0] * 30 + [102.0] * 360
    trades = run.trade_day(_day(run, closes), 100.0, _flat(run), both=False)
    assert trades == [(1, 102.0, 102.0)], "read at 10:00 it would have filled at 100"


def test_the_fill_is_the_next_minute_s_open_not_the_close_read(run) -> None:
    """The 10:00 minute opens at 102.5 after the 09:59 minute closed at 102."""
    closes = [100.0] * 29 + [102.0] * 361
    day = _day(run, closes)
    opens = list(day.opens)
    opens[30] = 102.5
    day = run.Day(session=day.session, open=day.open, close=day.close, opens=tuple(opens),
                  closes=day.closes, vwap=day.vwap, coverage=1.0)
    assert run.trade_day(day, 100.0, _flat(run), both=False) == [(1, 102.5, 102.0)]


def test_nothing_is_decided_before_ten(run) -> None:
    """A break in the first ten minutes that is over by 10:00 is never traded."""
    closes = [102.0] * 10 + [100.0] * 380
    assert run.trade_day(_day(run, closes), 100.0, _flat(run), both=False) == []


def test_a_price_under_the_vwap_is_flat_even_above_the_bound(run) -> None:
    closes = [100.0] * 29 + [102.0] * 361
    trades = run.trade_day(_day(run, closes, vwap=[103.0] * 390), 100.0, _flat(run), both=False)
    assert trades == []


def test_the_upper_bound_starts_from_the_prior_close_after_a_gap_down(run) -> None:
    """Opened at 100 after closing at 103: the bound is 103 x 1.01, and 102 is inside it."""
    closes = [100.0] * 29 + [102.0] * 361
    assert run.trade_day(_day(run, closes), 103.0, _flat(run), both=False) == []


def test_a_fall_back_under_the_bound_exits_at_the_next_open(run) -> None:
    closes = [100.0] * 29 + [102.0] * 30 + [100.5] * 331
    trades = run.trade_day(_day(run, closes), 100.0, _flat(run), both=False)
    assert trades == [(1, 102.0, 100.5)]


def test_long_only_ignores_a_break_below_and_both_sells_it(run) -> None:
    closes = [100.0] * 29 + [98.0] * 361
    day = _day(run, closes, vwap=[100.0] * 390)
    assert run.trade_day(day, 100.0, _flat(run), both=False) == []
    assert run.trade_day(day, 100.0, _flat(run), both=True) == [(-1, 98.0, 98.0)]


def test_a_half_day_decides_only_inside_its_session(run) -> None:
    closes = [100.0] * 179 + [102.0] * 31
    trades = run.trade_day(_day(run, closes), 100.0, _flat(run, length=210), both=False)
    assert trades == [(1, 102.0, 102.0)]


# --- the day's return ----------------------------------------------------------------------------------


def test_the_return_is_leverage_times_the_move_less_two_sides_a_trade(run) -> None:
    closes = [100.0] * 29 + [102.0] * 330 + [104.0] * 31
    got = run.day_result(_day(run, closes), 100.0, _flat(run), 2.0, both=False)
    assert got.trades == 1
    assert got.returns["gross"] == pytest.approx(2.0 * 2.0 / 100.0)
    assert got.returns["net"] == pytest.approx(2.0 * (2.0 - 2 * 0.005) / 100.0)
    assert got.returns["cost_adverse"] == pytest.approx(2.0 * (2.0 - 2 * 0.01) / 100.0)


def test_warm_up_sessions_are_not_traded(run) -> None:
    days = [_day(run, [100.0 + (i % 3)] * 390, session=date(2024, 1, 1) + timedelta(days=i))
            for i in range(20)]
    traded, skipped = run.run_instrument(days, both=False)
    assert skipped == {"warm_up": 15} and len(traded) == 5


# --- the branches -------------------------------------------------------------------------------------


def _cell(lo, hi, adverse_lo=0.001, after=0.001, days=2000, months=120, share=1.0):
    return {"days": days, "months": months, "complete_share": share,
            "mean": {"estimate": (lo + hi) / 2, "lo": lo, "hi": hi, "width": hi - lo},
            "cost_adverse": {"lo": adverse_lo},
            "after_publication": {"estimate": after}}


@pytest.mark.parametrize(("cell", "branch"), [
    (_cell(0.0002, 0.0009), "ACCEPT"),
    (_cell(0.0002, 0.0009, adverse_lo=-0.0001), "COST_FRAGILE"),
    (_cell(0.0002, 0.0009, after=-0.0001), "PUBLICATION_FRAGILE"),
    (_cell(0.0002, 0.0009, after=0.0), "PUBLICATION_FRAGILE"),
    (_cell(-0.0009, -0.0002), "REJECT"),
    (_cell(-0.0005, 0.0005), "INCONCLUSIVE"),
    (_cell(-0.0003, 0.0003), "NULL"),
    (_cell(0.0002, 0.0009, days=999), "REFUSED"),
    (_cell(0.0002, 0.0009, months=23), "REFUSED"),
    (_cell(0.0002, 0.0009, share=0.89), "REFUSED"),
])
def test_the_branches(run, cell, branch) -> None:
    assert run.branch_for(cell) == branch


# --- end to end ---------------------------------------------------------------------------------------


def _store(run, tmp_path, sessions=40):
    from swingdesk.market_data.minutes import Minute, MinuteStore
    from swingdesk.reference_data import calendar as cal
    from swingdesk.validation.backtest.intraday import session_for

    store = MinuteStore(tmp_path / "minutes.duckdb")
    known = datetime(2026, 9, 19, tzinfo=UTC)
    days = cal.sessions(cal.exchange_for("SPY"), date(2024, 3, 1), date(2024, 8, 30))[:sessions]
    for n, s in enumerate(days):
        for name in ("SPY", "QQQ"):
            session = session_for(name, s.session_date)
            length = int((session.close_time - session.open_time) / timedelta(minutes=1))
            drift = 0.02 if n % 2 else -0.01
            minutes = []
            for i in range(length):
                price = Decimal(str(round(100 * (1 + drift * i / length) + n * 0.1, 4)))
                minutes.append(Minute(at=session.open_time + timedelta(minutes=i), open=price,
                                      high=price + Decimal("0.02"), low=price - Decimal("0.02"),
                                      close=price, volume=1000, vwap=price))
            store.write(name, s.session_date, minutes, known, "test")
    store.close()
    return tmp_path / "minutes.duckdb", known, days


def test_the_run_goes_end_to_end_on_a_synthetic_store(run, tmp_path, monkeypatch) -> None:
    path, known, days = _store(run, tmp_path)
    monkeypatch.setattr(run, "START", days[0].session_date)
    monkeypatch.setattr(run, "END", days[-1].session_date)
    monkeypatch.setattr(run, "PUBLISHED", days[25].session_date)
    import argparse

    args = argparse.Namespace(minutes=path, minutes_as_of=known.isoformat())
    built = run.build(args, 50)
    cell = built["cells"]["SPY-long"]
    assert cell["days"] == len(days) - 15
    assert cell["excluded"] == {"warm_up": 15}
    assert cell["after_publication"]["days"] + cell["before_publication"]["days"] == cell["days"]
    assert set(built["cells"]) == {"SPY-long", "QQQ-long", "SPY-both"}
    json.dumps(built)


def test_the_power_mode_writes_widths_and_no_level(run, tmp_path, monkeypatch) -> None:
    path, known, days = _store(run, tmp_path)
    monkeypatch.setattr(run, "START", days[0].session_date)
    monkeypatch.setattr(run, "END", days[-1].session_date)
    import argparse

    estimate = run.power(argparse.Namespace(minutes=path, minutes_as_of=known.isoformat()))
    assert set(estimate["widths"]) == {"SPY-long", "QQQ-long", "SPY-both"}
    assert "cells" not in estimate
    assert not math.isnan(estimate["widths"]["SPY-long"]["whole"])


def test_the_verdict_speaks_the_project_s_vocabulary(run) -> None:
    """`verify_studies` knows four verdicts; a branch like NULL reports as INCONCLUSIVE."""
    assert set(run.TOKEN.values()) <= {"accept", "reject", "inconclusive", "refused", "smoke"}
    assert run.TOKEN["NULL"] == "inconclusive"
    assert run.TOKEN["PUBLICATION_FRAGILE"] == "inconclusive"
