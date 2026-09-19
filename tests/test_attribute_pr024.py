"""`tools/attribute_pr024.py`: PR-024's exclusions and the shape of its difference, after the run.

What it must get right, each a way to explain a verdict with numbers that are not the verdict's:

* **`registered` IS section 6's population.** Same entries, same first reasons, the same interval
  to the digit - or every comparison against it compares two different things;
* **the populations nest**, each needing less than the one before;
* **a failure is kept against the arm and costing that made it** - an 11:00 arm with no quote drops
  an entry from the registered reading and not from the two-arm one; a fall of more than two ATR
  before the close fill breaks only the anchored-stop costing of the close arm.
"""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.market_data.quotes import CLOSE, ELEVEN, OPEN

REPO = Path(__file__).resolve().parents[1]
KNOWN = datetime(2026, 1, 5, tzinfo=UTC)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    return _load("_attribute_pr024", REPO / "tools" / "attribute_pr024.py")


@pytest.fixture(scope="module")
def world() -> ModuleType:
    """`test_run_pr024`'s synthetic sessions, minutes, quotes and stores."""
    return _load("_run_pr024_world", REPO / "tests" / "test_run_pr024.py")


def _windows(world, session, spreads=(20.0, 5.0, 2.0), missing=()):
    asked = {OPEN: session.open_time + timedelta(seconds=5),
             ELEVEN: session.open_time.replace(hour=11, minute=0),
             CLOSE: session.close_time - timedelta(minutes=5)}
    out = {}
    for (moment, at), half in zip(asked.items(), spreads, strict=True):
        at = at.astimezone(UTC)
        out[moment] = None if moment in missing else (at, tuple(world._quotes(at, half)))
    return out


def _series(bars) -> BarSeries:
    return BarSeries(instrument_id="X", interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=KNOWN, bars=tuple(bars))


# --- the registered population ---------------------------------------------------------------------


def test_registered_is_section_six_s_population_to_the_digit(tool, world, tmp_path) -> None:
    args, _ = world._world(tmp_path, tool.study)
    registered = tool.study.build(args)
    payload = tool.build(args)

    ours = payload["populations"]["registered"]
    assert ours["entries"] == registered["sample"]["complete"]
    assert ours["difference"] == registered["cells"]["C"]["difference"]
    assert ours["gross_part"] == registered["cells"]["C"]["gross_part"]
    assert payload["excluded_first_reason"] == registered["sample"]["excluded"]
    assert payload["exploratory"] is True


def test_the_populations_nest(tool, world, tmp_path) -> None:
    args, _ = world._world(tmp_path, tool.study)
    walked, _, _ = tool.walk_sample(args, tool.study.read_sample(args.sample))
    registered = {id(w) for w in tool.population(walked, tool.REGISTERED)}
    three = {id(w) for w in tool.population(walked, tool.THREE_ARMS)}
    two = {id(w) for w in tool.population(walked, tool.TWO_ARMS)}
    assert registered <= three <= two


# --- failures kept against what made them -----------------------------------------------------------


def test_a_missing_eleven_quote_drops_the_registered_entry_and_not_the_two_arm_one(tool,
                                                                                   world) -> None:
    """A flat path: every arm leaves on the clock at the close's spread, so O and C need no 11:00."""
    entry, bars, minutes, entered = world._day_and_after(tool.study, lambda i: 100.0)
    walked = tool.walk_every(entry, _series(bars), Decimal(2), tuple(minutes),
                             _windows(world, entered, missing=(ELEVEN,)), entered, None)

    assert walked.first_reason() == "quotes_unavailable"
    assert "quotes_unavailable:eleven" in walked.failures()
    assert tool.population([walked], tool.REGISTERED) == []
    assert tool.population([walked], tool.THREE_ARMS) == []
    assert tool.population([walked], tool.TWO_ARMS) == [walked]
    assert walked.trade("C").exit_reason.value == "time"


def test_a_fall_before_the_close_fill_breaks_only_the_close_arm_s_anchored_stop(tool,
                                                                                world) -> None:
    """Signal close 100, ATR 2: the anchored stop sits at 96. The name holds 100 until 14:30 and
    trades at 94 from then, so the close arm buys at 94 - under its own anchored stop."""
    def path(i: int) -> float:
        return 100.0 if i < 300 else 94.0

    entry, bars, minutes, entered = world._day_and_after(tool.study, path)
    walked = tool.walk_every(entry, _series(bars), Decimal(2), tuple(minutes),
                             _windows(world, entered), entered, None)

    assert walked.first_reason() == "stop_not_below_entry"
    assert walked.failures() == ["stop_not_below_entry:C:anchored_stop"]
    assert tool.population([walked], tool.REGISTERED) == []
    assert tool.population([walked], tool.THREE_ARMS) == [walked]
    # The open arm bought at 100 and was stopped the same afternoon; the close arm bought after.
    assert walked.trade("O").exit_date == entry.session_date
    assert tool._difference(walked, "C") > 0


def test_a_quote_failure_is_named_before_a_missing_print(tool, world) -> None:
    """`price_entry` checks the quote windows before the fills, and the first reason follows it."""
    entry, bars, minutes, entered = world._day_and_after(tool.study, lambda i: 100.0)
    gapped = tuple(m for i, m in enumerate(minutes) if not 85 <= i <= 100)
    walked = tool.walk_every(entry, _series(bars), Decimal(2), gapped,
                             _windows(world, entered, missing=(ELEVEN,)), entered, None)
    assert walked.first_reason() == "quotes_unavailable"
    assert {"quotes_unavailable:eleven", "no_print_at_the_moment:T"} <= set(walked.failures())


def test_a_population_needs_the_gross_twin_as_well(tool, world) -> None:
    """The gross part is read on the same entries as the net difference, or it is another sample."""
    entry, bars, minutes, entered = world._day_and_after(tool.study, lambda i: 100.0)
    walked = tool.walk_every(entry, _series(bars), Decimal(2), tuple(minutes),
                             _windows(world, entered), entered, None)
    assert tool.population([walked], tool.TWO_ARMS) == [walked]
    walked.trades["C"]["gross"] = "zero_shares"
    assert tool.population([walked], tool.TWO_ARMS) == []


def test_an_entry_level_failure_is_its_only_reason(tool, world) -> None:
    entry, bars, _, entered = world._day_and_after(tool.study, lambda i: 100.0)
    walked = tool.walk_every(entry, _series(bars), Decimal(2), None,
                             _windows(world, entered), entered, None)
    assert walked.failures() == ["minutes_unavailable"] == [walked.first_reason()]
    assert tool.population([walked], tool.TWO_ARMS) == []


# --- the shape -------------------------------------------------------------------------------------


def test_the_shape_reads_its_median_trim_and_largest(tool, world, monkeypatch) -> None:
    entry, bars, minutes, entered = world._day_and_after(tool.study, lambda i: 100.0)
    picked = [tool.walk_every(entry, _series(bars), Decimal(2), tuple(minutes),
                              _windows(world, entered), entered, None) for _ in range(3)]
    value = {id(w): v for w, v in zip(picked, (0.01, -0.05, 0.04), strict=True)}

    def fake(w, arm, costing="net"):
        return value[id(w)] if (arm, costing) == ("C", "net") else 0.0

    monkeypatch.setattr(tool, "_difference", fake)
    monkeypatch.setattr(tool, "LARGEST", 1)
    got = tool.shape(picked, 20)
    assert got["median"] == 0.01
    assert got["share_close_ahead"] == pytest.approx(2 / 3)
    assert [row["difference"] for row in got["largest"]] == [-0.05], "largest by SIZE"
    assert got["mean_without_largest"] == pytest.approx(0.025)


def test_by_open_spread_orders_by_the_open_s_own_spread(tool, world) -> None:
    entry, bars, minutes, entered = world._day_and_after(tool.study, lambda i: 100.0)
    walked = [tool.walk_every(entry, _series(bars), Decimal(2), tuple(minutes),
                              _windows(world, entered, spreads=(half, 5.0, 2.0)), entered, None)
              for half in (40.0, 10.0, 30.0, 20.0, 50.0)]
    rows = tool.by_open_spread(walked)
    spreads = [row["open_half_spread_bps"] for row in rows]
    assert spreads == sorted(spreads) and len(rows) == 5
    # Flat prices: the whole difference is what the open paid over the close.
    assert rows[-1]["difference"] > rows[0]["difference"] > 0
    assert Counter(row["entries"] for row in rows) == Counter({1: 5})


def test_the_report_names_every_population(tool, world, tmp_path, capsys) -> None:
    args, _ = world._world(tmp_path, tool.study)
    tool.report(tool.build(args))
    printed = capsys.readouterr().out
    for label in ("EXPLORATORY", "registered", "three_arms", "two_arms", "open-spread Q1",
                  "O left by"):
        assert label in printed
