"""`tools/measure_first_touch.py` on synthetic stores where every answer is arithmetic. No network.

The tool exists to attribute: each difference from the 2026-09-08 probe must land on exactly one
cause - the price adjustment, the session window, or the check that the minutes are the bar - and a
later split must show in the units check as a factor. Each fixture is built so that exactly one of
those is true.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from swingdesk.contracts.reference import Exchange, ExchangeSession
from swingdesk.market_data.minutes import Minute, MinuteStore

REPO = Path(__file__).resolve().parents[1]
DAY = date(2025, 2, 21)
OPEN = datetime(2025, 2, 21, 14, 30, tzinfo=UTC)
FETCHED = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)
SESSION = ExchangeSession(exchange=Exchange.NYSE, session_date=DAY, open_time=OPEN,
                          close_time=OPEN + timedelta(hours=6, minutes=30))


@pytest.fixture(scope="module")
def tool():
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_first_touch",
                                                  REPO / "tools" / "measure_first_touch.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def minute(offset: int, low: str, high: str, factor: int = 1) -> Minute:
    return Minute(at=OPEN + timedelta(minutes=offset), open=Decimal(low) * factor,
                  high=Decimal(high) * factor, low=Decimal(low) * factor,
                  close=Decimal(high) * factor)


def row(instrument_id: str, arm: str = "ranked") -> dict[str, str]:
    return {"instrument_id": instrument_id, "session_date": DAY.isoformat(), "arm": arm,
            "entry_price": "100", "stop": "90", "target": "110"}


#: PRE: a pre-market print takes the stop; in regular hours the target prints first.
PRE = [minute(-60, "85", "100"), minute(5, "95", "111"), minute(10, "89", "105")]
#: SPL: split-adjusted, the stop prints first; raw prices are 2x, so the raw reading is `target`.
SPLIT = [minute(5, "89", "105"), minute(10, "95", "111")]


@pytest.fixture
def stores(tmp_path: Path):
    split = MinuteStore(tmp_path / "split.duckdb")
    raw = MinuteStore(tmp_path / "raw.duckdb")
    split.write("PRE", DAY, PRE, FETCHED, "t")
    raw.write("PRE", DAY, PRE, FETCHED, "t")
    split.write("SPL", DAY, SPLIT, FETCHED, "t")
    raw.write("SPL", DAY, [minute(5, "89", "105", 2), minute(10, "95", "111", 2)], FETCHED, "t")
    yield split, raw
    split.close()
    raw.close()


#: Both sessions' regular hours run 89-111, so both reproduce these bars.
DAILY = {("PRE", DAY): (Decimal(111), Decimal(89)), ("SPL", DAY): (Decimal(111), Decimal(89))}


def run(tool, stores, daily=DAILY):
    split, raw = stores
    return tool.measure([row("PRE"), row("SPL", "unselected")], split, raw, daily, FETCHED,
                        sessions=lambda instrument, on: SESSION)


def test_each_change_from_the_probe_lands_on_exactly_one_cause(tool, stores) -> None:
    report = run(tool, stores)
    assert report["changed_by_the_adjustment"] == ["SPL 2025-02-21 unselected: target -> stop"]
    assert report["changed_by_the_window"] == ["PRE 2025-02-21 ranked: stop -> target"]
    assert report["changed_by_the_check"] == []


def test_the_four_readings_are_counted_separately(tool, stores) -> None:
    readings = run(tool, stores)["readings"]
    assert (readings["probe"]["stop"], readings["probe"]["target"]) == (1, 1)
    assert (readings["split"]["stop"], readings["split"]["target"]) == (2, 0)
    assert (readings["window"]["stop"], readings["window"]["target"]) == (1, 1)
    assert (readings["resolver"]["stop"], readings["resolver"]["target"]) == (1, 1)


def test_a_later_split_shows_in_the_units_check_as_a_factor(tool, stores) -> None:
    units = run(tool, stores)["units"]
    assert units["split_agrees"] == 2
    assert units["split_disagrees"] == []
    assert units["raw_disagrees"] == ["SPL 2025-02-21: high x2.0000 low x2.0000"]


def test_a_daily_extreme_the_session_never_printed_is_a_mismatch(tool, stores) -> None:
    """NZF's shape, measured 2026-09-14: the bar's low is a print no regular-hours minute holds.
    The window reading still says `target`; the resolver refuses it, and the check is the cause."""
    daily = {("PRE", DAY): (Decimal(111), Decimal(85)), ("SPL", DAY): (Decimal(111), Decimal(89))}
    report = run(tool, stores, daily=daily)
    assert report["changed_by_the_check"] == ["PRE 2025-02-21 ranked: target -> mismatch"]
    assert report["units"]["split_disagrees"] == ["PRE 2025-02-21: high x1.0000 low x1.0471"]
    assert report["resolver_by_arm"]["ranked"]["mismatch"] == 1


def test_without_a_daily_bar_the_resolver_cannot_check_and_does_not_answer(tool, stores) -> None:
    report = run(tool, stores, daily={})
    assert report["readings"]["resolver"]["unavailable"] == 2
    assert (report["units"]["split_agrees"], report["units"]["split_unchecked"]) == (0, 2)


def test_the_impact_is_target_minus_stop_in_R_over_the_arms_trades(tool, stores) -> None:
    per_row = run(tool, stores)["per_row"]
    study = {"arms": {"ranked": {"full": {"trades": 40}}, "unselected": {"full": {"trades": 10}}},
             "ambiguous_exits": {"ranked": 1, "unselected": 1}}
    arms = tool.impact(per_row, study)
    assert arms["ranked"]["resolved_to_target"] == 1
    assert arms["ranked"]["gross_r_moved"] == pytest.approx(2.0)      # (110 - 90) / (100 - 90)
    assert arms["ranked"]["mean_r_per_trade_moves_by"] == pytest.approx(0.05)
    assert arms["unselected"]["gross_r_moved"] == 0
    assert arms["unselected"]["harness_counted"] == 1


def test_the_daily_bar_is_the_version_the_study_could_see(tool, tmp_path: Path) -> None:
    path = tmp_path / "bars.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE TABLE bars (instrument_id VARCHAR, interval VARCHAR, series VARCHAR, "
                       "session_date DATE, knowledge_time TIMESTAMPTZ, high DECIMAL(18,6), "
                       "low DECIMAL(18,6))")
    connection.execute("INSERT INTO bars VALUES "
                       "('PRE', '1d', 'raw', '2025-02-21', '2025-02-22 00:00:00+00', 100, 80), "
                       "('PRE', '1d', 'raw', '2025-02-21', '2025-06-01 00:00:00+00', 111, 89), "
                       "('PRE', '1d', 'raw', '2025-02-21', '2026-01-01 00:00:00+00', 222, 178)")
    connection.close()
    seen = tool.daily_bars(path, [("PRE", DAY), ("NONE", DAY)],
                           datetime(2025, 12, 31, tzinfo=UTC))
    assert seen == {("PRE", DAY): (Decimal(111), Decimal(89))}
