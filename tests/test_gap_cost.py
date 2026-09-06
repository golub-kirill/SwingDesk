"""The three-way split that carries `DR-006` §9's finding: clean stop, gap stop, time exit.

`measure_gap_cost.py` exists to re-derive one number — the R cost of a stop-out that gaps — on the
universe this system now trades rather than on the 68 names `PR-005` traded. **The classification is
the whole measurement.** Miscount one gap as a clean stop and the mean moves toward −1R; miscount a
clean stop as a gap and it moves away. Neither would raise an error.

Synthetic bars, built so each outcome is unambiguous, and asserted against the R the tool reports.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gap_cost():
    """`tools/measure_gap_cost.py`, loaded by path — it is a script, not a package module."""
    sys.path.insert(0, str(REPO / "tools"))
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "_gap_cost", REPO / "tools" / "measure_gap_cost.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bar(session: date, o: str, h: str, low: str, c: str) -> Bar:
    return Bar(
        instrument_id="TEST",
        interval=Interval.DAY,
        series=Series.RAW,
        event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
        session_date=session,
        open=Decimal(o), high=Decimal(h), low=Decimal(low), close=Decimal(c),
        volume=1_000_000,
        knowledge_time=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _series(bars: tuple[Bar, ...]) -> BarSeries:
    return BarSeries(
        instrument_id="TEST", interval=Interval.DAY, series=Series.RAW,
        bars=bars,
        knowledge_time=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _flat_history(sessions: int, price: str = "100.00") -> list[Bar]:
    """A quiet run-up so ATR is a known, non-zero constant: every bar has a range of exactly 1.00."""
    out = []
    start = date(2026, 1, 5)
    for offset in range(sessions):
        day = start + timedelta(days=offset)
        out.append(_bar(day, price, str(Decimal(price) + Decimal("0.50")),
                        str(Decimal(price) - Decimal("0.50")), price))
    return out


def _entry_bar(after: Bar) -> Bar:
    """A quiet session at 100.00, which becomes the ENTRY because entry is the NEXT open.

    The tool enters at `bars[index + 1].open` and that same bar opens the window, so a position can
    be stopped on its own entry session. A gap therefore cannot happen on the entry bar - the stop
    sits 2 ATR below its open by construction - and a fixture that puts the event there is testing
    the wrong bar. The first draft of this file did exactly that and three cases came back "time".
    """
    day = after.session_date + timedelta(days=1)
    return _bar(day, "100.00", "100.30", "99.70", "100.00")


def _outcome(gap_cost, tail: list[Bar]) -> tuple[str, float]:
    """Run the classifier over one entry window and return (outcome, gross R)."""
    history = _flat_history(gap_cost.ATR_PERIOD + 2)
    entry = _entry_bar(history[-1])
    # `tail` starts the session AFTER the entry bar, so shift its dates forward by one.
    shifted = [
        _bar(bar.session_date + timedelta(days=1), str(bar.open), str(bar.high),
             str(bar.low), str(bar.close))
        for bar in tail
    ]
    bars = tuple(history + [entry] + shifted)
    series = _series(bars)
    # The decision bar is the last of the history; entry is the next open.
    dates = {history[-1].session_date}
    found = gap_cost._r_multiples(series, dates)
    for kind in ("clean", "gap", "time"):
        values = found[f"{kind}_gross"]
        if values:
            return kind, values[0]
    raise AssertionError(f"nothing classified: {found}")


def _window(first: Bar, rest: int, price: str) -> list[Bar]:
    """`first` then `rest` quiet sessions, so the window fills the hold without another event."""
    out = [first]
    day = first.session_date
    for offset in range(1, rest + 1):
        day = first.session_date + timedelta(days=offset)
        out.append(_bar(day, price, str(Decimal(price) + Decimal("0.10")),
                        str(Decimal(price) - Decimal("0.10")), price))
    return out


# ATR over the flat history is 1.00, so R = 2 x ATR = 2.00 and the stop sits 2.00 below the entry.
ENTRY = Decimal("100.00")
STOP = Decimal("98.00")


def test_a_low_that_reaches_the_stop_from_above_is_a_CLEAN_stop(gap_cost) -> None:
    """Opened above the stop and traded down through it: the order fills AT the stop, costing 1R."""
    touch = _bar(date(2026, 2, 2), "100.00", "100.20", "97.50", "99.00")
    kind, r = _outcome(gap_cost, _window(touch, gap_cost.HOLD, "99.00"))
    assert kind == "clean"
    assert r == pytest.approx(-1.0), "a clean stop is exactly one R by construction"


def test_an_open_BELOW_the_stop_is_a_GAP_and_costs_more_than_one_R(gap_cost) -> None:
    """The whole point of the measurement. Filled at the OPEN, not at the stop.

    Opening at 96.00 against a stop of 98.00 and an entry of 100.00 is −2R, not −1R.
    """
    gapped = _bar(date(2026, 2, 2), "96.00", "96.50", "95.00", "96.00")
    kind, r = _outcome(gap_cost, _window(gapped, gap_cost.HOLD, "96.00"))
    assert kind == "gap"
    assert r == pytest.approx(-2.0)


def test_an_open_exactly_AT_the_stop_counts_as_a_gap(gap_cost) -> None:
    """The boundary, fixed deliberately rather than left to whichever branch runs first.

    At the stop the fill is the open and the cost is exactly 1R, so the two classifications give
    the same number here — which is why the boundary has to be pinned by a test rather than by
    noticing the totals look right.
    """
    at_stop = _bar(date(2026, 2, 2), "98.00", "98.50", "97.00", "98.00")
    kind, r = _outcome(gap_cost, _window(at_stop, gap_cost.HOLD, "98.00"))
    assert kind == "gap"
    assert r == pytest.approx(-1.0)


def test_a_window_that_never_reaches_the_stop_is_a_TIME_exit(gap_cost) -> None:
    """Priced at the close of the last session in the hold, not at −1R and not at zero."""
    quiet = _bar(date(2026, 2, 2), "100.00", "100.50", "99.50", "100.00")
    kind, r = _outcome(gap_cost, _window(quiet, gap_cost.HOLD, "103.00"))
    assert kind == "time"
    assert r == pytest.approx(1.5), "closed at 103 against an entry of 100 and R of 2.00"


def test_a_bar_that_gaps_down_and_then_recovers_is_still_a_gap_stop(gap_cost) -> None:
    """The position is gone at the open. What the session does afterwards is not ours.

    Named for what it asserts: this tool has NO target, only a stop and a time exit, so there is no
    stop-versus-target ordering here to test. An earlier draft called this "stop before target" and
    a mutation of the clean branch survived it, because the case never reaches that branch.
    """
    both = _bar(date(2026, 2, 2), "97.00", "110.00", "97.00", "109.00")
    kind, r = _outcome(gap_cost, _window(both, gap_cost.HOLD, "109.00"))
    assert kind == "gap"
    assert r == pytest.approx(-1.5), "filled at the 97.00 open despite closing at 109"


def test_an_INTRADAY_touch_stops_the_position_even_if_the_close_recovers(gap_cost) -> None:
    """The clean branch reads the LOW, not the close, and the difference is a whole category.

    A session that dips to 97.50 and closes at 99.00 has taken the stop out at 98.00. Reading the
    close instead would classify it a survivor and quietly move every one of these into the time
    bucket, which is priced at whatever session 20 closed at.
    """
    dip = _bar(date(2026, 2, 2), "100.00", "100.20", "97.50", "99.00")
    kind, r = _outcome(gap_cost, _window(dip, gap_cost.HOLD, "99.00"))
    assert kind == "clean"
    assert r == pytest.approx(-1.0)


def test_net_charges_slippage_on_both_fills(gap_cost) -> None:
    """`DR-005`'s 25bp per side, which is what makes these comparable with `DR-006` §8.1's NET."""
    touch = _bar(date(2026, 2, 2), "100.00", "100.20", "97.50", "99.00")
    history = _flat_history(gap_cost.ATR_PERIOD + 2)
    entry = _entry_bar(history[-1])
    shifted = [
        _bar(bar.session_date + timedelta(days=1), str(bar.open), str(bar.high),
             str(bar.low), str(bar.close))
        for bar in _window(touch, gap_cost.HOLD, "99.00")
    ]
    series = _series(tuple(history + [entry] + shifted))
    found = gap_cost._r_multiples(series, {history[-1].session_date})
    gross, net = found["clean_gross"][0], found["clean_net"][0]
    assert gross == pytest.approx(-1.0)
    assert net < gross, "costs make a loss larger, never smaller"
    # entry 100 x 1.0025 = 100.25, exit 98 x 0.9975 = 97.755, over R = 2.00
    assert net == pytest.approx((97.755 - 100.25) / 2.0, abs=1e-6)
