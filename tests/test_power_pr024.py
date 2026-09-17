"""`tools/power_pr024.py`: the width PR-024 can reach, from daily bars, before any minute is fetched.

What carries it, each a way to size the study wrongly without an error:

* **dates and names are separated.** The shared market move averages over DATES only; a formula
  that divided everything by the entry count would promise a width ten names a date cannot buy.
* **the choice is the cheapest READABLE cell** - within the floor, within the calendar, and with
  enough pairs to clear the sample rule even at the lowest admitted complete share.
* **the proxy is the study's own walk** with the close arm's entry day holding nothing after its
  fill, so an entry-day stop the open arm takes is a difference and not a skipped entry.
* **no level leaks** into the payload, or sizing the study could reveal its answer.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import statistics
import sys
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import Minute
from swingdesk.reference_data import calendar as cal

REPO = Path(__file__).resolve().parents[1]
KNOWN = datetime(2026, 1, 5, tzinfo=UTC)


@pytest.fixture(scope="module")
def power():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_power_pr024", REPO / "tools" / "power_pr024.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- the two parts ------------------------------------------------------------------------------------


def test_components_separate_the_shared_move_from_the_names(power) -> None:
    by_date = {date(2025, 1, 2): [0.01, 0.03], date(2025, 1, 3): [-0.01, -0.03],
               date(2025, 1, 6): [0.0, 0.0]}
    parts = power.components(by_date)
    assert parts["between_date_sd"] == pytest.approx(statistics.stdev([0.02, -0.02, 0.0]))
    # Deviations +-0.01 on two dates, 0 on the third; pooled over 1 + 1 + 1 degrees of freedom.
    assert parts["within_date_sd"] == pytest.approx(math.sqrt(4 * 0.01 ** 2 / 3))


def test_a_date_with_nothing_on_it_is_left_out(power) -> None:
    by_date = {date(2025, 1, 2): [0.01, 0.03], date(2025, 1, 3): [], date(2025, 1, 6): [0.0, 0.0]}
    assert power.components(by_date)["between_date_sd"] == pytest.approx(
        statistics.stdev([0.02, 0.0]))


def test_one_date_cannot_separate_them(power) -> None:
    with pytest.raises(ValueError, match="two dates"):
        power.components({date(2025, 1, 2): [0.01, 0.02]})


def test_one_name_a_date_has_no_within_part(power) -> None:
    parts = power.components({date(2025, 1, 2): [0.01], date(2025, 1, 3): [0.03]})
    assert parts["within_date_sd"] == 0.0


def test_the_width_falls_with_dates_not_with_names_alone(power) -> None:
    """More names a date only thins the part the names do not share."""
    parts = {"between_date_sd": 0.01, "within_date_sd": 0.03}
    half = power.predicted_half_width(parts, 500, 6, 0.004)
    assert half == pytest.approx(1.96 * math.sqrt(0.01 ** 2 / 500 + (0.03 ** 2 + 0.004 ** 2) / 3000))
    floor = 1.96 * 0.01 / math.sqrt(500)
    assert power.predicted_half_width(parts, 500, 10_000, 0.0) > floor
    assert power.predicted_half_width(parts, 1000, 6, 0.004) < half


def test_the_detectable_difference_is_the_half_width_at_eighty_percent_power(power) -> None:
    assert power.detectable(0.00196) == pytest.approx(0.00196 + 0.0008416)


# --- the choice ---------------------------------------------------------------------------------------


def test_the_cheapest_readable_cell_is_chosen(power) -> None:
    parts = {"between_date_sd": 0.01, "within_date_sd": 0.03}
    got = power.grid(parts, 0.004, 10_000)
    readable = {key: cell for key, cell in got["cells"].items()
                if cell["readable_at_floor"] and cell["within_the_calendar"] and cell["enough_pairs"]}
    cheapest = min(cell["requests"] for cell in readable.values())
    chosen = got["chosen"]
    assert chosen["dates"] * chosen["per_date"] * power.REQUESTS_PER_ENTRY == cheapest
    assert got["cells"][f"D{chosen['dates']}_k{chosen['per_date']}"]["readable_at_floor"]
    assert chosen["half_width_at_min_share"] <= power.study.POWER_FLOOR / 2
    assert chosen["half_width"] < chosen["half_width_at_min_share"]


def test_readable_means_readable_at_the_lowest_admitted_share(power) -> None:
    """A cell inside the floor only when every drawn entry is priced is not readable: the sample
    rule reads a verdict down to 90% complete."""
    floor = power.study.POWER_FLOOR / 2
    assert power.at_min_share(floor * 0.96) > floor


def test_the_last_row_is_every_session_the_calendar_holds(power) -> None:
    """Only every session is readable here; a round count above the calendar never is."""
    parts = {"between_date_sd": 0.016, "within_date_sd": 0.047}
    got = power.grid(parts, 0.004, 982)
    assert got["cells"]["Dall_k10"]["dates"] == 982
    assert not got["cells"]["D1000_k12"]["within_the_calendar"]
    chosen = got["chosen"]
    assert chosen["every_session"] and chosen["dates"] == 982
    # Eight names a date read 0.1446 with every entry priced and 0.1524 at 90%: not readable.
    assert chosen["cell"] == "Dall_k10" and chosen["per_date"] == 10
    assert not got["cells"]["Dall_k8"]["readable_at_floor"]
    assert got["cells"]["Dall_k8"]["half_width"] <= power.study.POWER_FLOOR / 2


def test_a_tie_keeps_the_cell_met_first(power, monkeypatch) -> None:
    """D1000 k4 and D500 k8 cost the same. The comparison is strict and the grid runs dates
    ascending, so D500 k8 - met first - stays; pinned so a reordered grid is a visible change."""
    monkeypatch.setattr(power, "GRID_DATES", (500, 1000))
    monkeypatch.setattr(power, "GRID_PER_DATE", (8, 4))
    monkeypatch.setattr(power, "predicted_half_width", lambda *a: 0.0)
    monkeypatch.setattr(power.study, "MIN_PAIRS", 3000)
    got = power.grid({}, 0.0, 10_000)["chosen"]
    assert (got["dates"], got["per_date"]) == (500, 8)


def test_a_cell_the_calendar_cannot_hold_is_never_chosen(power) -> None:
    parts = {"between_date_sd": 0.0, "within_date_sd": 0.0}
    got = power.grid(parts, 0.0, 300)
    assert got["chosen"]["dates"] <= 300
    assert not got["cells"]["D400_k4"]["within_the_calendar"]
    assert got["cells"]["Dall_k4"]["within_the_calendar"]


def test_a_cell_too_small_for_the_sample_rule_is_never_chosen(power, monkeypatch) -> None:
    monkeypatch.setattr(power.study, "MIN_PAIRS", 1500)
    parts = {"between_date_sd": 0.0, "within_date_sd": 0.0}
    got = power.grid(parts, 0.0, 10_000)
    # 250 x 4 x 0.9 = 900 and 250 x 6 x 0.9 = 1350 miss 1500; 250 x 8 x 0.9 = 1800 clears it,
    # and so does 400 x 6 x 0.9 = 2160 - at 9,600 requests against 8,000.
    assert not got["cells"]["D250_k6"]["enough_pairs"]
    assert (got["chosen"]["dates"], got["chosen"]["per_date"]) == (250, 8)


def test_no_readable_cell_says_so(power) -> None:
    parts = {"between_date_sd": 1.0, "within_date_sd": 1.0}
    got = power.grid(parts, 0.0, 10_000)["chosen"]
    assert got["dates"] is None and "floor" in got["why"]


# --- the entry-spread bound ---------------------------------------------------------------------------


def test_the_cost_bound_is_the_widest_opening_range_as_a_normal_spread(power, tmp_path) -> None:
    path = tmp_path / "spreads.json"
    path.write_text(json.dumps({"rows": [
        {"window": "09:30 open", "year": 2016, "p10": "2", "p90": "90"},
        {"window": "09:30 open", "year": 2019, "p10": "4", "p90": "60"},
        {"window": "15:55 close", "year": 2016, "p10": "0", "p90": "500"},
    ]}), encoding="utf-8")
    assert power.cost_sd(path) == pytest.approx(88 / 2.563 / 10000)


def test_the_registered_spread_file_has_an_opening_window(power) -> None:
    assert 0 < power.cost_sd() < 0.01


# --- the proxy ----------------------------------------------------------------------------------------


def _store(tmp_path: Path, rng: random.Random, names=("AAA", "BBB", "CCC"), count: int = 200,
           crash_on: int | None = None):
    """A daily store; with `crash_on`, the names fall 40% intraday that session and close flat."""
    nyse = cal.exchange_for("SPY")
    sessions = list(cal.sessions(nyse, date(2024, 1, 2), date(2025, 12, 31)))[:count]
    bars = []
    for name in ("SPY", *names):
        price = 100.0
        for i, s in enumerate(sessions):
            if name != "SPY" and i == crash_on:
                bars.append(Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                                event_time=datetime.combine(s.session_date, time(21), tzinfo=UTC),
                                session_date=s.session_date, open=Decimal(f"{price:.2f}"),
                                high=Decimal(f"{price:.2f}"), low=Decimal(f"{price * 0.6:.2f}"),
                                close=Decimal(f"{price:.2f}"), volume=1_000_000,
                                knowledge_time=KNOWN))
                continue
            opened = price * (1 + rng.gauss(0, 0.005))
            price = opened * (1 + rng.gauss(0.0005, 0.012))
            bars.append(Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                            event_time=datetime.combine(s.session_date, time(21), tzinfo=UTC),
                            session_date=s.session_date,
                            open=Decimal(f"{opened:.2f}"),
                            high=Decimal(f"{max(opened, price) * 1.006:.2f}"),
                            low=Decimal(f"{min(opened, price) * 0.994:.2f}"),
                            close=Decimal(f"{price:.2f}"), volume=1_000_000, knowledge_time=KNOWN))
    with BarStore(tmp_path / "bars.duckdb") as store:
        store.write(bars, KNOWN)
    return [s.session_date for s in sessions]


def test_the_proxy_is_close_entry_minus_open_entry_through_the_study_walk(power, tmp_path) -> None:
    calendar = _store(tmp_path, random.Random(7))
    study = power.study
    entries = [study.Entry(name, calendar[i], calendar[i + 1])
               for i in range(30, 150, 10) for name in ("AAA", "BBB")]
    with BarStore(tmp_path / "bars.duckdb") as store:
        differences, skipped = power.proxy_differences(store, KNOWN, entries)
        series = store.as_of("AAA", Interval.DAY, Series.RAW, KNOWN)
    assert skipped == 0
    assert sum(len(v) for v in differences.values()) == len(entries)

    # Recomputed by hand from the same walk: the open arm reads its whole entry bar, the close
    # arm meets only its own closing print.
    first = entries[0]
    atr_series = atr_component.compute(series, power.atr_registry())
    atr_value = study.atr_at(atr_series, series, first.signal_date)
    bar = next(b for b in series.bars if b.session_date == first.session_date)
    free = study.cost(Decimal(0))
    opened = study.walk_entry(first, series.bars, atr_value, bar.open, free, lambda _r: free,
                              None, None, Counter(), "O")
    closing = [Minute(at=bar.event_time, open=bar.close, high=bar.close, low=bar.close,
                      close=bar.close)]
    closed = study.walk_entry(first, series.bars, atr_value, bar.close, free, lambda _r: free,
                              closing, None, Counter(), "C")
    assert not isinstance(opened, str) and not isinstance(closed, str)
    assert differences[first.signal_date][0] == pytest.approx(
        study.per_dollar(closed) - study.per_dollar(opened))


def test_an_entry_day_stop_is_a_difference_not_a_skip(power, tmp_path) -> None:
    """The open arm stops out inside its entry bar; the close arm, entered at that bar's close,
    cannot have seen the fall. Both are priced and the difference is kept."""
    calendar = _store(tmp_path, random.Random(11), names=("AAA",), crash_on=60)
    entry = power.study.Entry("AAA", calendar[59], calendar[60])
    with BarStore(tmp_path / "bars.duckdb") as store:
        differences, skipped = power.proxy_differences(store, KNOWN, [entry])
        series = store.as_of("AAA", Interval.DAY, Series.RAW, KNOWN)
    assert skipped == 0 and len(differences[calendar[59]]) == 1

    study = power.study
    free = study.cost(Decimal(0))
    atr_value = study.atr_at(atr_component.compute(series, power.atr_registry()), series,
                              calendar[59])
    bar = next(b for b in series.bars if b.session_date == calendar[60])
    opened = study.walk_entry(entry, series.bars, atr_value, bar.open, free, lambda _r: free,
                              None, None, Counter(), "O")
    assert not isinstance(opened, str)
    assert opened.exit_date == calendar[60], "the open arm left on its entry day"
    assert differences[calendar[59]][0] != 0.0


def test_an_entry_the_store_cannot_price_is_skipped_and_counted(power, tmp_path) -> None:
    calendar = _store(tmp_path, random.Random(3), names=("AAA",))
    study = power.study
    entries = [study.Entry("ZZZ", calendar[40], calendar[41]),        # not stored
               study.Entry("AAA", calendar[2], calendar[3]),          # ATR still warming up
               study.Entry("AAA", calendar[40], date(2031, 1, 2))]    # session not stored
    with BarStore(tmp_path / "bars.duckdb") as store:
        differences, skipped = power.proxy_differences(store, KNOWN, entries)
    assert skipped == 3 and sum(len(v) for v in differences.values()) == 0


# --- the payload --------------------------------------------------------------------------------------


def test_the_run_goes_end_to_end_and_leaks_no_level(power, tmp_path, monkeypatch) -> None:
    """The selection is the study's own scoring; only the cross-section size is relaxed, since a
    synthetic store holds twelve names where the registered rule asks for a hundred."""
    _store(tmp_path, random.Random(5), names=tuple(f"N{i:02d}" for i in range(12)),
           count=480)
    real = power.study.select_streamed
    monkeypatch.setattr(power.study, "select_streamed",
                        lambda scores, dates, _decile: real(scores, dates, Decimal("0.5"), 1))
    monkeypatch.setattr(power.study, "WINDOW_MONTHS", 6)
    monkeypatch.setattr(power, "RESULT", tmp_path / "power.json")
    args = argparse.Namespace(data=tmp_path, as_of=None, pilot_dates=12, pilot_per_date=3,
                              resamples=50)
    payload = power.build(args)

    power.assert_no_effect_leaked(payload)
    assert payload["for"] == "PR-024"
    assert payload["pilot"]["entries"] > 0 and payload["pilot"]["dates"] >= 2
    assert payload["formula_check"]["formula_half_width"] > 0
    assert payload["grid"]["cells"]
    json.dumps(payload)


def test_build_itself_refuses_a_payload_that_carries_a_level(power, tmp_path, monkeypatch) -> None:
    """The guard is inside `build`, not left to the caller: a grid that grew a level stops the run
    before anything is written."""
    _store(tmp_path, random.Random(5), names=tuple(f"N{i:02d}" for i in range(12)),
           count=480)
    real = power.study.select_streamed
    monkeypatch.setattr(power.study, "select_streamed",
                        lambda scores, dates, _decile: real(scores, dates, Decimal("0.5"), 1))
    monkeypatch.setattr(power.study, "WINDOW_MONTHS", 6)
    monkeypatch.setattr(power, "grid", lambda *a: {"mean_difference": 0.001})
    args = argparse.Namespace(data=tmp_path, as_of=None, pilot_dates=12, pilot_per_date=3,
                              resamples=50)
    with pytest.raises(AssertionError, match="leaked"):
        power.build(args)


def test_the_bootstrap_check_is_a_half_width(power) -> None:
    rng = random.Random(1)
    by_date = {date(2020, 1, 1) + timedelta(days=31 * i): [rng.gauss(0, 0.01) for _ in range(5)]
               for i in range(30)}
    half = power.bootstrap_half_width(by_date, 400, 9)
    formula = power.predicted_half_width(power.components(by_date), 30, 5, 0.0)
    assert 0.5 < half / formula < 2.0
