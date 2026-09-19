"""`tools/run_pr026.py`: four single changes to `CARD-001`, each against one baseline, read against SPY.

The cases that carry the four studies:

* **the leveraged-fund rule** marks leveraged and inverse funds and leaves ultra-short BOND funds
  alone - a garbage filter that dropped bond funds would be a different filter;
* **the entry is the session's close**, so nothing of that session can stop it out, and every
  trade is read net of SPY over its own days;
* **each contrast is the one registered** - the kept subset against everything for garbage and
  pullback, the same entry under two exits for the exit, dates below against above for the regime.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.reference_data.universe import DirectoryEntry

REPO = Path(__file__).resolve().parents[1]
KNOWN = datetime(2026, 1, 5, tzinfo=UTC)
NYSE = cal.exchange_for("SPY")


@pytest.fixture(scope="module")
def run() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_run_pr026", REPO / "tools" / "run_pr026.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sessions(start: date, end: date) -> list[date]:
    return [s.session_date for s in cal.sessions(NYSE, start, end)]


def _bar(name: str, day: date, o: float, h: float, lo: float, c: float) -> Bar:
    return Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
               event_time=datetime.combine(day, time(21), tzinfo=UTC), session_date=day,
               open=Decimal(f"{o:.4f}"), high=Decimal(f"{h:.4f}"), low=Decimal(f"{lo:.4f}"),
               close=Decimal(f"{c:.4f}"), volume=1_000_000, knowledge_time=KNOWN)


def _flat(name: str, days: list[date], price: float = 100.0, spread: float = 1.0) -> list[Bar]:
    return [_bar(name, d, price, price + spread, price - spread, price) for d in days]


def _series(bars: list[Bar], name: str = "X") -> BarSeries:
    return BarSeries(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=KNOWN, bars=tuple(bars))


# --- the leveraged-fund rule ----------------------------------------------------------------------


@pytest.mark.parametrize(("name", "levered"), [
    ("Direxion Daily Semiconductor Bull 3X Shares", True),
    ("ProShares UltraPro QQQ", True),
    ("ProShares UltraShort 20+ Year Treasury", True),
    ("ProShares Short S&P500", True),
    ("-1x Short VIX Futures ETF", True),
    ("T-Rex 2X Inverse NVIDIA Daily Target ETF", True),
    ("MicroSectors U.S. Big Banks -3 Inverse Leveraged ETNs", True),
    ("JPMorgan Ultra-Short Municipal Income ETF", False),
    ("American Century Ultrashort Income ETF", False),
    ("iShares Short Treasury Bond ETF", False),
    ("Vanguard Short-Term Treasury ETF", False),
    ("SPDR S&P 500 ETF Trust", False),
    ("Invesco BulletShares 2029 Corporate Bond ETF", False),
])
def test_the_rule_marks_leverage_and_spares_short_bond_funds(run, name, levered) -> None:
    assert run.levered_name(name) is levered


def test_a_stock_is_never_levered_whatever_its_name(run) -> None:
    stock = DirectoryEntry(symbol="BEAR", name="Bear Creek 3X Holdings", venue="NYSE",
                           is_etf=False, is_test_issue=False)
    fund = DirectoryEntry(symbol="SPXL", name="Direxion Daily S&P 500 Bull 3X Shares",
                          venue="NYSE Arca", is_etf=True, is_test_issue=False)
    assert not run.is_levered(stock) and run.is_levered(fund) and not run.is_levered(None)


# --- features at the signal -----------------------------------------------------------------------


def test_features_read_the_signal_close_against_its_own_means(run) -> None:
    days = _sessions(date(2017, 1, 3), date(2018, 12, 31))
    signal = days[-1]
    bars = _flat("X", days[:-1], 100.0) + [_bar("X", signal, 95, 96, 94, 95)]
    spy = [(d, 200.0 + i * 0.1) for i, d in enumerate(days)]
    pullback, regime = run.features(_series(bars), signal, spy)
    assert pullback is True and regime is True
    pullback, regime = run.features(_series(bars), days[-2], [(d, 300.0 - i * 0.1)
                                                              for i, d in enumerate(days)])
    assert pullback is False and regime is False


def test_without_enough_history_a_feature_is_unknown(run) -> None:
    days = _sessions(date(2018, 1, 2), date(2018, 1, 12))
    pullback, regime = run.features(_series(_flat("X", days)), days[-1],
                                    [(d, 100.0) for d in days])
    assert pullback is None and regime is None


# --- the walk -------------------------------------------------------------------------------------


def _walk_world(run, entry_bar: tuple[float, float, float, float], after: float = 100.0):
    days = _sessions(date(2018, 1, 2), date(2018, 8, 31))
    bars = _flat("X", days[:30]) + [_bar("X", days[30], *entry_bar)] + _flat("X", days[31:], after)
    spy = {d: 400.0 for d in days}
    spy[days[-1]] = 404.0
    entry = run.p24.Entry("X", days[29], days[30])
    return entry, _series(bars), spy, days


def test_the_entry_is_the_close_and_its_own_session_cannot_stop_it(run) -> None:
    """Opened at 97, fell to 90, closed at 100: an order filled AT the close paid 100 and never saw
    the fall."""
    entry, series, spy, _ = _walk_world(run, (97, 101, 90, 100))
    trade, _ = run.walk(entry, series, Decimal(2), spy, run.BASE_POLICY, Decimal(1))
    assert trade.entry_price == Decimal(100) * (1 + Decimal("5.0") / 10000)
    assert trade.exit_date != entry.session_date
    assert trade.exit_reason.value == "time"


def test_a_trade_is_read_net_of_spy_over_its_own_days(run) -> None:
    entry, series, spy, days = _walk_world(run, (100, 101, 99, 100))
    spy[days[30]], spy[days[30 + 20]] = 400.0, 408.0
    trade, excess = run.walk(entry, series, Decimal(2), spy, run.BASE_POLICY, Decimal(1))
    assert trade.exit_date == days[30 + 20]
    assert excess == pytest.approx(run.p24.per_dollar(trade) - 0.02), "SPY rose 2% over the days"


def test_costs_scale_by_the_costing(run) -> None:
    entry, series, spy, _ = _walk_world(run, (100, 101, 99, 100))
    gross, _ = run.walk(entry, series, Decimal(2), spy, run.BASE_POLICY, Decimal(0))
    stressed, _ = run.walk(entry, series, Decimal(2), spy, run.BASE_POLICY, Decimal(3))
    assert gross.entry_price == Decimal(100)
    assert stressed.entry_price == Decimal(100) * (1 + Decimal("15.0") / 10000)


def test_the_wide_exit_has_no_target_and_holds_sixty(run) -> None:
    """A rise to 110 takes the baseline's 1R target (4 above); the wide exit rides it to the clock."""
    entry, series, spy, days = _walk_world(run, (100, 101, 99, 100), after=110.0)
    base, _ = run.walk(entry, series, Decimal(2), spy, run.BASE_POLICY, Decimal(1))
    wide, _ = run.walk(entry, series, Decimal(2), spy, run.WIDE_POLICY, Decimal(1))
    assert base.exit_reason.value == "target" and base.exit_date == days[31]
    # A target is charged the 11:00 spread, not the close's: whichever price it filled at.
    level = base.entry_price + (base.entry_price - base.stop_price)
    charged = 1 - Decimal("8.4") / 10000
    assert base.exit_price in (Decimal(110) * charged, level * charged)
    assert wide.exit_reason.value == "time" and wide.exit_date == days[30 + 60]


# --- the contrasts --------------------------------------------------------------------------------


def _walked(run, day: date, name: str, excess: float, *, levered=False, pullback=False,
            regime=True, wide: float | None = None):
    w = run.Walked(run.p24.Entry(name, day, day + timedelta(days=1)), levered, pullback, regime)
    for costing in run.COSTINGS:
        w.excess[("base", costing)] = excess
        if wide is not None:
            w.excess[("wide", costing)] = wide
    return w


def test_garbage_reads_the_kept_names_against_everything(run) -> None:
    day = date(2019, 3, 1)
    walked = [_walked(run, day, "A", 0.02), _walked(run, day, "L", -0.10, levered=True)]
    contrast, level = run.contrast_values(walked, run.GARBAGE, "net")
    assert contrast[day] == pytest.approx(0.02 - (-0.04))
    assert level[day] == pytest.approx(0.02)


def test_pullback_reads_the_pullback_names_against_everything(run) -> None:
    day = date(2019, 3, 1)
    walked = [_walked(run, day, "A", 0.03, pullback=True), _walked(run, day, "B", -0.01),
              _walked(run, day, "C", -0.02)]
    contrast, level = run.contrast_values(walked, run.PULLBACK, "net")
    assert contrast[day] == pytest.approx(0.03 - 0.0)
    assert level[day] == pytest.approx(0.03)


def test_the_exit_reads_the_same_entry_under_two_exits(run) -> None:
    day = date(2019, 3, 1)
    walked = [_walked(run, day, "A", 0.01, wide=0.05), _walked(run, day, "B", -0.02, wide=-0.04),
              _walked(run, day, "C", 0.00)]
    contrast, level = run.contrast_values(walked, run.EXIT, "net")
    assert contrast[day] == pytest.approx(((0.05 - 0.01) + (-0.04 + 0.02)) / 2)
    assert level[day] == pytest.approx(0.005)


def test_the_regime_reads_dates_below_against_dates_above(run) -> None:
    rows = []
    for i in range(40):
        day = date(2019, 1, 1) + timedelta(days=15 * i)
        up = i % 2 == 0
        rows.append(_walked(run, day, "A", -0.01 if up else 0.02, regime=up))
    contrast, _ = run.contrast_values(rows, run.REGIME, "net")
    cell = run.two_group_interval(contrast, {w.entry.signal_date: w.regime_up for w in rows}, 200)
    assert cell["estimate"] == pytest.approx(0.03)
    assert cell["lo"] <= 0.03 <= cell["hi"]


def test_one_regime_alone_has_no_contrast(run) -> None:
    values = {date(2019, 1, 1) + timedelta(days=i): 0.01 for i in range(30)}
    cell = run.two_group_interval(values, dict.fromkeys(values, True), 50)
    assert cell["estimate"] != cell["estimate"], "nan: there is nothing to subtract"


# --- the verdict ----------------------------------------------------------------------------------


def _cell(lo=0.001, hi=0.003, level_hi=0.01, adverse=0.001, dates=900, months=48, share=0.95):
    return {"difference": {"estimate": (lo + hi) / 2, "lo": lo, "hi": hi, "width": hi - lo},
            "level": {"hi": level_hi}, "cost_adverse": {"estimate": adverse},
            "dates": dates, "months": months, "complete_share": share}


@pytest.mark.parametrize(("cell", "branch"), [
    (_cell(), "ACCEPT"),
    (_cell(dates=400), "REFUSED"),
    (_cell(months=20), "REFUSED"),
    (_cell(share=0.8), "REFUSED"),
    (_cell(level_hi=-0.001), "BOTH_NEGATIVE"),
    (_cell(adverse=-0.001), "COST_FRAGILE"),
    (_cell(lo=-0.003, hi=-0.001), "REJECT"),
    (_cell(lo=-0.001, hi=0.001), "NULL"),
    (_cell(lo=-0.004, hi=0.004), "INCONCLUSIVE"),
])
def test_section_six_in_its_order_with_the_sample_rule_in_dates(run, cell, branch) -> None:
    assert run.branch_for(cell) == branch


# --- end to end -----------------------------------------------------------------------------------


def _world(tmp_path: Path, run):
    days = _sessions(date(2017, 6, 1), date(2019, 6, 28))
    bars = []
    import random

    rng = random.Random(9)
    for name in ("SPY", "AAA", "BBB", "LEV"):
        price = 100.0
        for d in days:
            opened = price * (1 + rng.gauss(0, 0.004))
            price = opened * (1 + rng.gauss(0.0004, 0.012))
            bars.append(_bar(name, d, opened, max(opened, price) * 1.004,
                             min(opened, price) * 0.996, price))
    with BarStore(tmp_path / "bars.duckdb") as store:
        store.write(bars, KNOWN)
    with DirectoryStore(tmp_path / "directory.duckdb") as directory:
        directory.record([
            DirectoryEntry("AAA", "Alpha Corp", "NYSE", False, False),
            DirectoryEntry("BBB", "Beta Inc", "NYSE", False, False),
            DirectoryEntry("LEV", "Direxion Daily Widget Bull 3X Shares", "NYSE Arca", True, False),
        ], KNOWN, "test")
    entries = [run.p24.Entry(name, days[i], days[i + 1])
               for i in range(320, 460, 5) for name in ("AAA", "BBB", "LEV")]
    sample = tmp_path / "sample.jsonl"
    run.p24.write_sample(entries, sample)
    return argparse.Namespace(data=tmp_path, directory=tmp_path / "directory.duckdb",
                              directory_as_of=None, sample=sample, as_of=None, resamples=50,
                              per_date=3), entries


def test_the_four_studies_go_end_to_end_on_a_synthetic_store(run, tmp_path) -> None:
    args, entries = _world(tmp_path, run)
    payloads = run.build(args)
    assert list(payloads) == list(run.STUDIES)
    for study, payload in payloads.items():
        assert payload["prereg"] == study and payload["trials"] == 1
        assert payload["branch"] == "SMOKE"
        for key in ("country", "split", "perturbations", "measured_span", "as_of",
                    "registered_settings", "diagnostics", "cell"):
            assert key in payload
        assert set(payload["perturbations"]["registered"]) == set(payload["perturbations"]["run"])
        json.dumps(payload, default=run.p24._default)
    seen = payloads[run.GARBAGE]["diagnostics"]
    assert seen["levered_entries"] == len(entries) // 3
    assert payloads[run.GARBAGE]["sample"]["priced"] == len(entries)


def test_the_report_prints_each_study(run, tmp_path, capsys) -> None:
    args, _ = _world(tmp_path, run)
    run.report(run.build(args))
    printed = capsys.readouterr().out
    for label in ("PR-026 (garbage)", "PR-027 (pullback)", "PR-028 (exit)", "PR-029 (regime)",
                  "own level vs SPY", "cost-adverse"):
        assert label in printed
