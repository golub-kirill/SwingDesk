"""`tools/measure_overnight_momentum_power.py` - winners by night, `SPY` by day, against `SPY` held.

What must hold: the rank reads the close 252 sessions back and the close 21 back and nothing later;
the book is the top decile of the names ADMITTED at the formation, fixed for the month; a night is
the previous close to the next open and never spans a missing session; the first night of a month is
bought at the formation's own close; and the power payload carries no level.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from array import array
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def run():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "measure_overnight_momentum_power", REPO / "tools" / "measure_overnight_momentum_power.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _calendar():
    from swingdesk.contracts.reference import Exchange
    from swingdesk.reference_data import calendar as cal

    return [s.session_date for s in cal.sessions(Exchange.NYSE, date(2021, 1, 4), date(2021, 12, 31))]


def _panel(run, series: dict[str, list[float]], opens: dict[str, list[float]] | None = None):
    calendar = _calendar()[:len(next(iter(series.values())))]
    panel = run.Panel(calendar, 0)
    for name, closes in series.items():
        panel.closes[name] = array("d", closes)
        panel.opens[name] = array("d", (opens or {}).get(name, closes))
    return panel


def test_momentum_reads_252_and_21_sessions_back_and_nothing_later(run) -> None:
    closes = [100.0] * 260
    closes[260 - 1 - 252] = 50.0      # the early close
    closes[260 - 1 - 21] = 75.0       # the late close
    closes[-1] = 1_000.0              # after the skip: must not count
    panel = _panel(run, {"TEST.1": closes})
    assert run.momentum(panel, "TEST.1", 259) == pytest.approx(0.5)


def test_the_book_is_the_top_decile_of_the_admitted_names(run, monkeypatch) -> None:
    monkeypatch.setattr(run, "MIN_NAMES", 10)
    names = {f"TEST.{i}": [100.0] * 238 + [100.0 + i] * 22 for i in range(20)}
    names["TEST.99"] = [100.0] * 238 + [10_000.0] * 22      # the best, and not admitted
    panel = _panel(run, names)
    panel.admitted[259] = [n for n in names if n != "TEST.99"]
    assert run.winners(panel, 259) == ["TEST.19", "TEST.18"]


def test_a_thin_cross_section_forms_no_book(run, monkeypatch) -> None:
    monkeypatch.setattr(run, "MIN_NAMES", 50)
    names = {f"TEST.{i}": [100.0 + i] * 260 for i in range(20)}
    panel = _panel(run, names)
    panel.admitted[259] = list(names)
    assert run.winners(panel, 259) == []


def test_a_night_is_the_previous_close_to_this_open_less_the_fees(run) -> None:
    panel = _panel(run, {"TEST.1": [100.0, 100.0]}, {"TEST.1": [100.0, 101.0]})
    import run_pr040 as p40

    expected = 0.01 - p40.CAT_PER_SHARE / 100.0 - (p40.SEC_RATE + (p40.TAF_PER_SHARE
                                                                    + p40.CAT_PER_SHARE) / 101.0)
    assert run.night_of(panel, "TEST.1", 1) == pytest.approx(expected)


def test_a_night_never_spans_a_missing_session(run) -> None:
    panel = _panel(run, {"TEST.1": [100.0, 100.0, 100.0]})
    full = _calendar()
    panel.calendar = [full[0], full[2], full[3]]   # the second session is skipped
    assert math.isnan(run.night_of(panel, "TEST.1", 1))


def test_the_first_night_of_a_month_is_bought_at_the_formation_close(run, monkeypatch) -> None:
    """The book formed at session 0's close holds its names from that close: session 1's night is
    the first one it earns, and SPY by day, compounded."""
    monkeypatch.setattr(run, "MIN_NAMES", 1)
    monkeypatch.setattr(run, "LOOKBACK", 0)
    monkeypatch.setattr(run, "SKIP", 0)
    panel = _panel(run, {"TEST.1": [100.0, 103.0, 103.0], run.BENCHMARK: [200.0, 204.0, 204.0]},
                   {"TEST.1": [100.0, 102.0, 103.0], run.BENCHMARK: [200.0, 202.0, 204.0]})
    panel.admitted[0] = ["TEST.1"]
    monkeypatch.setattr(run, "momentum", lambda panel, name, t: 1.0)
    daily, held, sizes = run.book(panel, [0], 2, {})
    first = panel.calendar[1]
    night = run.night_of(panel, "TEST.1", 1)
    import run_pr040 as p40

    day = ((204.0 - 202.0) / 202.0 - p40.CAT_PER_SHARE / 202.0
           - (p40.SEC_RATE + (p40.TAF_PER_SHARE + p40.CAT_PER_SHARE) / 204.0))
    assert daily[first] == pytest.approx((1 + night) * (1 + day) - 1)
    assert held[first] == pytest.approx(204.0 / 200.0 - 1)
    assert sizes == {panel.calendar[0].isoformat(): 1}


def test_the_window_is_48_holding_months_ending_with_the_last_month(run, monkeypatch) -> None:
    from swingdesk.contracts.reference import Exchange
    from swingdesk.reference_data import calendar as cal

    calendar = [s.session_date for s in cal.sessions(Exchange.NYSE, date(2020, 1, 2),
                                                        date(2026, 9, 25))]
    start, last, formations = run.window(calendar)
    assert len(formations) == 48 and start == formations[0]
    assert (calendar[last].year, calendar[last].month) == run.LAST_MONTH
    assert calendar[last + 1].month != calendar[last].month
    assert (calendar[formations[0]].year, calendar[formations[0]].month) == (2022, 8)


def test_the_power_payload_carries_no_level(run) -> None:
    from power_pr019 import assert_no_effect_leaked

    with pytest.raises(AssertionError):
        assert_no_effect_leaked({"mean_excess": 0.1})
    assert_no_effect_leaked({"width_a_year": 0.1, "winners_per_formation": {"fewest": 1}})
