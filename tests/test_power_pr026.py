"""`tools/power_pr026.py`: the widths the four studies can reach. Widths only.

* **the subsample is seeded per date** and never exceeds `k`, so a chosen `k` is re-derivable;
* **a pilot width is scaled to the window** and read at the lowest admitted complete share;
* **the choice is the smallest readable `k`**, or the largest with the unreadable studies named;
* **no level leaks** into the payload.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def power():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_power_pr026", REPO / "tools" / "power_pr026.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _walked(power, day: date, name: str):
    return power.study.Walked(power.p24.Entry(name, day, day + timedelta(days=1)))


def test_the_subsample_is_capped_per_date_and_seeded(power) -> None:
    days = [date(2019, 1, 2) + timedelta(days=i) for i in range(3)]
    walked = [_walked(power, d, f"N{i:02d}") for d in days for i in range(15)]
    first = power.subsample(walked, 4, 7)
    assert len(first) == 12
    assert [w.entry.instrument_id for w in first] == \
        [w.entry.instrument_id for w in power.subsample(list(reversed(walked)), 4, 7)]
    assert power.subsample(walked, 40, 7) == sorted(walked, key=lambda w: (w.entry.signal_date,
                                                                            w.entry.instrument_id))


def test_a_pilot_width_is_scaled_to_the_window_and_the_lowest_share(power) -> None:
    assert power.scaled(0.004, 250, 1000) == pytest.approx(0.002 / math.sqrt(0.9))


def test_the_smallest_readable_k_is_chosen(power) -> None:
    table = {10: {"PR-026": 0.004, "PR-027": 0.002}, 20: {"PR-026": 0.0029, "PR-027": 0.002},
             40: {"PR-026": 0.002, "PR-027": 0.001}}
    assert power.choose(table) == {"per_date": 20, "all_readable": True}


def test_when_nothing_is_readable_the_largest_k_is_kept_and_the_failures_named(power) -> None:
    table = {10: {"PR-026": 0.009, "PR-028": 0.002}, 40: {"PR-026": 0.005, "PR-028": 0.002}}
    assert power.choose(table) == {"per_date": 40, "all_readable": False,
                                   "unreadable": ["PR-026"]}


def test_build_writes_widths_and_no_level(power, monkeypatch, tmp_path) -> None:
    """The pipeline around the estimate, with the store and the walk replaced."""
    days = [date(2019, 1, 2) + timedelta(days=7 * i) for i in range(60)]

    class FakeStore:
        def __init__(self, *_):
            pass

        def latest_knowledge_time(self):
            return None

        def as_of(self, *_):
            return type("S", (), {"bars": [type("B", (), {"session_date": d})() for d in days]})()

        def close(self):
            pass

    import random
    rng = random.Random(1)

    def fake_walk(args, entries):
        out = []
        for e in entries:
            w = power.study.Walked(e, levered=rng.random() < 0.1, pullback=rng.random() < 0.4,
                                   regime_up=e.signal_date.month % 2 == 0)
            for costing in power.study.COSTINGS:
                w.excess[("base", costing)] = rng.gauss(0, 0.05)
                w.excess[("wide", costing)] = rng.gauss(0, 0.07)
            out.append(w)
        return out, {"bars": "fake"}

    monkeypatch.setattr(power, "BarStore", FakeStore)
    monkeypatch.setattr(power.p24, "read_instant", lambda text, fallback: datetime(2026, 1, 1, tzinfo=UTC))
    monkeypatch.setattr(power.study, "window_formations", lambda calendar: list(calendar))
    monkeypatch.setattr(power.p24, "frame", lambda *a: (object(), 5))
    monkeypatch.setattr(power.p24, "draw", lambda selection, calendar, dates, per, seed: [
        power.p24.Entry(f"N{i}", d, d + timedelta(days=1)) for d in dates for i in range(12)])
    monkeypatch.setattr(power.study, "walk_sample", fake_walk)
    args = argparse.Namespace(data=tmp_path, directory=tmp_path, directory_as_of=None, as_of=None,
                              resamples=30)
    payload = power.build(args)
    power.assert_no_effect_leaked(payload)
    assert set(payload["widths_at_min_share"]) == {str(k) for k in power.GRID}
    assert payload["chosen"]["per_date"] in power.GRID
