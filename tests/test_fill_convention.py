"""How a resting day limit meets the next session — three outcomes, and the ORDER of the tests.

`measure_fill_convention.py` compares what the backtest fills against what the live path fills. The
whole comparison rests on `classify`, and every way it can be wrong produces a plausible trade
rather than an error:

* **a session that opens BELOW the limit fills at the OPEN, not at the limit.** The order was
  already marketable; the limit never bound. Charging the limit there quietly improves every
  gap-down entry, which is the half of the population that most needs to be honest.
* **a session that opens ABOVE and trades down fills AT the limit** — not at the open it never had,
  and not at the low it never chased.
* **a session that never trades down fills at nothing.** A price here invents a position.

And one rule about the two columns: an unfilled entry contributes to the BACKTEST population and
not to the live one. Substituting the backtest's number for the missing fill would make the two
series agree by construction on exactly the rows where they differ.

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
def fills():
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "_fill_convention", REPO / "tools" / "measure_fill_convention.py"
    )
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: `@dataclass` resolves its annotations through `sys.modules`, and a
    # module loaded by path alone is not there yet.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def bar(day: int, open_: str, high: str, low: str, close: str) -> Bar:
    when = datetime(2024, 1, 1, tzinfo=UTC)
    return Bar(
        instrument_id="TEST",
        interval=Interval.DAY,
        series=Series.RAW,
        event_time=when,
        session_date=date(2024, 1, 1) + timedelta(days=day),
        open=Decimal(open_), high=Decimal(high), low=Decimal(low), close=Decimal(close),
        volume=Decimal(1_000_000),
        knowledge_time=when,
    )


# --- the three outcomes ------------------------------------------------------------------------

def test_a_session_that_opens_below_the_limit_fills_at_the_open(fills):
    """Open 95 against a limit of 100. The order was marketable; 100 would be a free 5 points."""
    fill = fills.classify(Decimal(100), bar(1, "95", "99", "90", "97"))
    assert fill.kind == fills.MARKETABLE
    assert fill.price == Decimal(95)


def test_a_session_that_opens_above_and_trades_down_fills_at_the_limit(fills):
    """Open 105, low 99, limit 100. Not the open it never had, not the low it never chased."""
    fill = fills.classify(Decimal(100), bar(1, "105", "107", "99", "101"))
    assert fill.kind == fills.PASSIVE
    assert fill.price == Decimal(100)


def test_a_session_that_never_trades_down_fills_at_nothing(fills):
    """A price here would invent a position the live system does not hold."""
    fill = fills.classify(Decimal(100), bar(1, "105", "110", "101", "108"))
    assert fill.kind == fills.UNFILLED
    assert fill.price is None


def test_touching_the_limit_exactly_fills(fills):
    """A limit is filled AT it, not through it — the boundary belongs to the fill."""
    assert fills.classify(Decimal(100), bar(1, "105", "107", "100", "104")).kind == fills.PASSIVE
    opened_at = fills.classify(Decimal(100), bar(1, "100", "107", "98", "104"))
    assert opened_at.kind == fills.MARKETABLE
    assert opened_at.price == Decimal(100)


def test_a_gap_down_is_marketable_and_not_passive(fills):
    """Both branches are true of a gap-down bar; only the first one is right.

    Open 90, low 85, limit 100: the low is under the limit too, so a classifier that tested the low
    first would call this passive and fill at 100 — ten points of invented price improvement on the
    worst entries in the sample.
    """
    fill = fills.classify(Decimal(100), bar(1, "90", "95", "85", "92"))
    assert fill.kind == fills.MARKETABLE
    assert fill.price == Decimal(90)


# --- the return --------------------------------------------------------------------------------

def test_the_return_is_measured_on_the_entry_actually_paid(fills):
    assert fills.forward_return(Decimal(100), Decimal(110)) == Decimal("0.1")
    assert fills.forward_return(Decimal(100), Decimal(90)) == Decimal("-0.1")


def test_a_cheaper_entry_produces_a_larger_return_to_the_same_exit(fills):
    """The mechanism that offsets adverse selection; if it inverts, the finding inverts."""
    assert fills.forward_return(Decimal(95), Decimal(110)) > \
        fills.forward_return(Decimal(100), Decimal(110))


# --- the two populations -----------------------------------------------------------------------

def _flat_series(n: int, opens: list[str] | None = None) -> list[Bar]:
    """A rising series; `opens` overrides the open of each bar where given."""
    bars = []
    for i in range(n):
        price = 100 + i
        o = opens[i] if opens and i < len(opens) and opens[i] else str(price)
        bars.append(bar(i, o, str(price + 5), str(price - 5), str(price)))
    return bars


def test_an_unfilled_entry_counts_for_the_backtest_and_not_for_the_live_path(fills):
    """The engine assumes it trades every candidate; the live path holds only what filled."""
    # A series rising fast enough that each bar's LOW clears the previous bar's close, so no limit
    # at a prior close is ever reached. The bars stay internally valid: low <= open, close <= high.
    bars = []
    for i in range(30):
        price = 100 + i * 10
        bars.append(bar(i, str(price - 2), str(price + 1), str(price - 3), str(price)))
    assert all(bars[i + 1].low > bars[i].close for i in range(len(bars) - 1)), \
        "the fixture must make every limit unreachable, or it tests nothing"
    walked = fills.walk(bars, hold=5, warmup=0)
    assert walked, "the walk produced no entries to judge"
    assert all(kind == fills.UNFILLED for kind, _, _ in walked)
    assert all(live is None for _, live, _ in walked)
    assert all(backtest is not None for _, _, backtest in walked)


def test_entries_do_not_overlap(fills):
    """Two entries inside one holding period would double-count the same forward window."""
    walked = fills.walk(_flat_series(60), hold=5, warmup=0)
    assert len(walked) == len(set(range(len(walked))))
    assert len(walked) <= 60 // 5


def test_the_warmup_is_skipped(fills):
    assert len(fills.walk(_flat_series(60), hold=5, warmup=50)) < \
        len(fills.walk(_flat_series(60), hold=5, warmup=0))


# --- the summary -------------------------------------------------------------------------------

def test_interval_reports_a_mean_and_a_half_width(fills):
    mean, half = fills.interval([Decimal(1), Decimal(2), Decimal(3)])
    assert mean == Decimal(2)
    assert half > 0


def test_interval_on_one_observation_claims_no_precision(fills):
    """A half-width from a single point would be zero by accident, not by evidence."""
    assert fills.interval([Decimal(7)]) == (Decimal(7), Decimal(0))
    assert fills.interval([]) == (Decimal(0), Decimal(0))
