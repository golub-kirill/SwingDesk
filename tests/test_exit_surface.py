"""The walk that produces every cell of the exit surface, and the null it is read against.

`measure_exit_surface.py` sweeps stop × target and compares each cell to **buy-and-hold over the
same window**. Two things carry the whole measurement and neither raises an error when wrong:

* **the first-touch order** — a bar containing both the stop and the target must resolve as a stop,
  and a bar that opens through the stop must fill at the OPEN
* **the null** — every cell is marked against buy-and-hold rather than against zero, because over
  2016–2026 a time exit collects the decade's drift and a wide stop produces mostly time exits

Synthetic bars, one unambiguous outcome each.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.contracts.market import Bar, Interval, Series

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def surface():
    sys.path.insert(0, str(REPO / "tools"))
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "_exit_surface", REPO / "tools" / "measure_exit_surface.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bar(session: date, o: str, h: str, low: str, c: str) -> Bar:
    return Bar(
        instrument_id="TEST", interval=Interval.DAY, series=Series.RAW,
        event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
        session_date=session,
        open=Decimal(o), high=Decimal(h), low=Decimal(low), close=Decimal(c),
        volume=1_000_000, knowledge_time=datetime(2026, 1, 1, tzinfo=UTC),
    )


ENTRY = Decimal("100.00")
STOP = Decimal("98.00")      # 2 x ATR below, with ATR = 1.00
TARGET = Decimal("102.00")   # 1R above


# --------------------------------------------------------- first touch, three ways


def test_a_bar_containing_both_the_stop_and_the_target_is_a_STOP(surface) -> None:
    """A daily bar cannot say which traded first, so the pessimistic reading is the rule.

    `manage.evaluate`, `measure_target_reachability` and `measure_gap_cost` all resolve it this way.
    Reading it the other way would make every cell of the surface flatter than the system that
    trades it, and the surface exists to inform an exit policy.
    """
    both = _bar(date(2026, 2, 2), "100.00", "105.00", "97.00", "104.00")
    price, kind = surface._walk([both], STOP, TARGET)
    assert kind == "stop"
    assert price == STOP


def test_a_bar_that_OPENS_through_the_stop_fills_at_the_open(surface) -> None:
    """Worse than the stop, and it is the only branch that can lose more than 1R."""
    gapped = _bar(date(2026, 2, 2), "95.00", "99.00", "94.00", "96.00")
    price, kind = surface._walk([gapped], STOP, TARGET)
    assert kind == "gap"
    assert price == Decimal("95.00")


def test_a_favourable_gap_is_NOT_credited_above_the_target(surface) -> None:
    """Opening at 110 against a 102 target fills at 102. Conservative on purpose.

    The unfavourable gap fills at the open and the favourable one does not, which is deliberate
    asymmetry: this tool is used to argue for an exit policy, so both hands are tied behind it.
    """
    leapt = _bar(date(2026, 2, 2), "110.00", "112.00", "109.00", "111.00")
    price, kind = surface._walk([leapt], STOP, TARGET)
    assert kind == "hit"
    assert price == TARGET


def test_a_window_touching_neither_is_a_time_exit_priced_at_the_LAST_close(surface) -> None:
    """The closes must DIFFER across the window or the test cannot tell first from last.

    The first draft used one close for every bar, and a mutation pricing the exit at `window[0]`
    survived it - the two readings gave the same number. Each bar closes a little higher here, so
    only the last one is 100.90.
    """
    quiet = [
        _bar(date(2026, 2, 2) + timedelta(days=n),
             "100.00", "101.00", "99.00", str(Decimal("100.50") + Decimal("0.10") * n))
        for n in range(5)
    ]
    price, kind = surface._walk(quiet, STOP, TARGET)
    assert kind == "time"
    assert price == Decimal("100.90"), "the LAST close, not the first"


def test_the_stop_is_checked_before_the_target_across_bars_too(surface) -> None:
    """A later target does not rescue an earlier stop."""
    window = [
        _bar(date(2026, 2, 2), "100.00", "101.00", "97.00", "99.00"),      # stop
        _bar(date(2026, 2, 3), "99.00", "115.00", "99.00", "114.00"),      # target, too late
    ]
    _, kind = surface._walk(window, STOP, TARGET)
    assert kind == "stop"


# ------------------------------------------------------------------ the grid's shape


def test_the_ratified_pair_is_in_the_grid(surface) -> None:
    """`DR-012` ratified the 2.0 stop and `DR-029` the 1R target.

    A sweep that did not contain the value in force could not say whether a change is an improvement
    — the comparison would have no origin.
    """
    assert Decimal("2.0") in surface.STOPS
    assert Decimal("1.0") in surface.TARGETS


def test_the_grid_spans_both_sides_of_the_ratified_stop(surface) -> None:
    """`DR-029` §5's lever is a TIGHTER stop, so the sweep must reach below 2.0 as well as above.

    A grid that only widened could not test the lever it was built to test.
    """
    assert min(surface.STOPS) < Decimal("2.0") < max(surface.STOPS)
