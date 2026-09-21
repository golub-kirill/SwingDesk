"""`tools/card002_journal.py` - the reconcile that turns the owner's fills into the cost number.

What must never break:

* **the exit is priced against the NEXT session's open**, never the entry session's. Pricing it
  against today would compare the exit with a price from before the position existed;
* **an unpriced night is `pending`, not zero.** Counting it as a zero-cost night drags the mean
  toward the answer the trial exists to test;
* **the cent trip-wire fires only after the trial's own length**, and it fires on the mean cost a
  side - `PR-034`'s cost-adverse gate, past which the measured edge is gone;
* **the record is append-only.** A correction is a new row, because the one number this trial
  produces has to stay auditable.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def journal():
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "card002_journal", REPO / "tools" / "card002_journal.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _bar(session: date, open_: float, close: float, *, fund: str = "IJR"):
    from swingdesk.contracts.market import Bar, Interval, Series

    return Bar(
        instrument_id=fund, interval=Interval.DAY, series=Series.RAW,
        event_time=datetime.combine(session, datetime.min.time(), tzinfo=UTC) + timedelta(days=1),
        session_date=session,
        open=Decimal(str(open_)), high=Decimal(str(max(open_, close))),
        low=Decimal(str(min(open_, close))), close=Decimal(str(close)),
        volume=1_000, knowledge_time=datetime(2026, 9, 20, tzinfo=UTC),
    )


# --- pricing ------------------------------------------------------------------------------------


def test_the_exit_is_priced_against_the_NEXT_session_open(journal) -> None:
    bars = [_bar(date(2026, 1, 5), 99.0, 100.0), _bar(date(2026, 1, 6), 101.0, 102.0)]
    night = journal.price({"session": "2026-01-05", "fund": "IJR", "entry": 100.0, "exit": 101.0},
                          bars, {})
    assert night.priced
    assert night.bar_close == 100.0
    assert night.bar_open == 101.0          # the 6th's open, not the 5th's 99.0
    assert night.exit_session == date(2026, 1, 6)


def test_the_exit_is_the_IMMEDIATE_next_session_even_when_more_are_stored(journal) -> None:
    # A Friday entry with Monday AND Tuesday stored. Pricing against the last stored session would
    # compare the exit with an open two days after the position was sold, and no test with a single
    # later bar can tell the two apart.
    bars = [_bar(date(2026, 1, 9), 99.0, 100.0),     # the entry session
            _bar(date(2026, 1, 12), 101.0, 102.0),   # Monday: the exit
            _bar(date(2026, 1, 13), 150.0, 151.0)]   # Tuesday: must not be read
    night = journal.price({"session": "2026-01-09", "fund": "IJR", "entry": 100.0, "exit": 101.0},
                          bars, {})
    assert night.exit_session == date(2026, 1, 12)
    assert night.bar_open == 101.0


def test_a_night_whose_next_session_is_not_stored_is_PENDING(journal) -> None:
    bars = [_bar(date(2026, 1, 5), 99.0, 100.0)]
    night = journal.price({"session": "2026-01-05", "fund": "IJR", "entry": 100.0, "exit": 101.0},
                          bars, {})
    assert not night.priced and "not stored yet" in night.pending


def test_a_night_whose_own_session_is_missing_is_PENDING(journal) -> None:
    bars = [_bar(date(2026, 1, 6), 101.0, 102.0)]
    night = journal.price({"session": "2026-01-05", "fund": "IJR", "entry": 100.0, "exit": 101.0},
                          bars, {})
    assert not night.priced and "no stored bar" in night.pending


def test_slippage_is_signed_so_that_positive_is_always_a_COST(journal) -> None:
    bars = [_bar(date(2026, 1, 5), 99.0, 100.0), _bar(date(2026, 1, 6), 101.0, 102.0)]
    # Paid 2 cents above the close, received 3 cents below the open: both are costs.
    night = journal.price({"session": "2026-01-05", "fund": "IJR", "entry": 100.02, "exit": 100.97},
                          bars, {})
    assert night.entry_slippage == pytest.approx(0.02)
    assert night.exit_slippage == pytest.approx(0.03)
    assert night.cost_per_side == pytest.approx(0.025)


def test_a_fill_BETTER_than_the_benchmark_is_a_negative_cost(journal) -> None:
    bars = [_bar(date(2026, 1, 5), 99.0, 100.0), _bar(date(2026, 1, 6), 101.0, 102.0)]
    night = journal.price({"session": "2026-01-05", "fund": "IJR", "entry": 99.99, "exit": 101.01},
                          bars, {})
    assert night.cost_per_side < 0


def test_the_dividend_reaches_the_night_that_ends_at_its_ex_date(journal) -> None:
    bars = [_bar(date(2026, 1, 5), 99.0, 100.0), _bar(date(2026, 1, 6), 101.0, 102.0)]
    night = journal.price({"session": "2026-01-05", "fund": "IJR", "entry": 100.0, "exit": 101.0},
                          bars, {date(2026, 1, 6): 0.5})
    assert night.dividend == 0.5
    assert night.realised == pytest.approx((101.0 + 0.5) / 100.0 - 1.0)
    assert night.modelled == pytest.approx((101.0 + 0.5) / 100.0 - 1.0)


def test_a_dividend_on_the_entry_session_does_NOT_reach_the_night(journal) -> None:
    bars = [_bar(date(2026, 1, 5), 99.0, 100.0), _bar(date(2026, 1, 6), 101.0, 102.0)]
    night = journal.price({"session": "2026-01-05", "fund": "IJR", "entry": 100.0, "exit": 101.0},
                          bars, {date(2026, 1, 5): 0.5})
    assert night.dividend == 0.0


# --- the trip-wires -----------------------------------------------------------------------------


def _nights(journal, n, *, cost, ret=0.001):
    """`n` priced nights, each costing `cost` a side and returning `ret`."""
    out = []
    for i in range(n):
        close = 100.0
        entry = close + cost
        open_ = close * (1.0 + ret)
        out.append(journal.Night(session=date(2026, 1, 5) + timedelta(days=i), fund="IJR", shares=1,
                                 entry_fill=entry, exit_fill=open_ - cost, priced=True,
                                 bar_close=close, bar_open=open_))
    return out


def test_the_cent_tripwire_does_not_fire_before_twenty_priced_nights(journal) -> None:
    gates = journal.tripwires(_nights(journal, 19, cost=0.05))
    assert gates["mean_cost_per_side"] == pytest.approx(0.05)
    assert not gates["cost_tripwire"], "19 nights is not the trial's length"


def test_the_cent_tripwire_fires_at_twenty_when_the_cost_is_above_a_cent(journal) -> None:
    assert journal.tripwires(_nights(journal, 20, cost=0.05))["cost_tripwire"]


def test_a_cost_at_the_cent_exactly_does_NOT_fire(journal) -> None:
    # The gate is "above a cent". PR-034 measured a positive result AT a cent, so the boundary
    # belongs to the passing side.
    assert not journal.tripwires(_nights(journal, 20, cost=0.01))["cost_tripwire"]


def test_an_unpriced_night_is_not_counted_as_a_zero_cost_one(journal) -> None:
    nights = _nights(journal, 20, cost=0.05)
    nights += [journal.Night(session=date(2026, 3, 1), fund="IJR", shares=1, entry_fill=100.0,
                             exit_fill=100.0, priced=False, pending="not stored yet")] * 40
    gates = journal.tripwires(nights)
    assert gates["priced"] == 20 and gates["recorded"] == 60
    assert gates["mean_cost_per_side"] == pytest.approx(0.05)
    assert not gates["judgement_allowed"], "60 RECORDED is not 60 priced"


def test_the_drawdown_alert_fires_only_past_twenty_five_per_cent(journal) -> None:
    mild = journal.tripwires(_nights(journal, 5, cost=0.0, ret=-0.01))
    assert not mild["drawdown_alert"]
    steep = journal.tripwires(_nights(journal, 40, cost=0.0, ret=-0.01))
    assert steep["drawdown"] < journal.DRAWDOWN_ALERT and steep["drawdown_alert"]


def test_the_drawdown_is_measured_from_the_PEAK_and_not_from_the_start(journal) -> None:
    # Up 50%, then down 30% of that peak. Measured from the start the book is still ahead, so a
    # drawdown read that way would report zero and never alert. Measured from the peak - which is
    # what a drawdown IS - it is about -30%.
    rise = _nights(journal, 10, cost=0.0, ret=0.0414)     # ~+50% compounded
    fall = _nights(journal, 10, cost=0.0, ret=-0.0351)    # ~-30% compounded
    gates = journal.tripwires(rise + fall)
    assert gates["equity"] > 1.0, "the book ends ABOVE where it started"
    assert gates["drawdown"] < -0.25 and gates["drawdown_alert"]


def test_no_judgement_before_sixty_priced_nights(journal) -> None:
    assert not journal.tripwires(_nights(journal, 59, cost=0.0))["judgement_allowed"]
    assert journal.tripwires(_nights(journal, 60, cost=0.0))["judgement_allowed"]


def test_nothing_recorded_gives_empty_gates_rather_than_a_crash(journal) -> None:
    gates = journal.tripwires([])
    assert gates == {"priced": 0, "recorded": 0, "mean_cost_per_side": 0.0, "cost_tripwire": False,
                     "drawdown": 0.0, "drawdown_alert": False, "judgement_allowed": False,
                     "equity": 1.0}


# --- the record ---------------------------------------------------------------------------------


def test_recording_appends_and_never_rewrites(journal, tmp_path, capsys) -> None:
    for fill in (100.0, 100.5):
        assert journal.main(["record", "--data", str(tmp_path), "--session", "2026-01-05",
                             "--fund", "IJR", "--entry", str(fill), "--exit", "101.0"]) == journal.OK
    capsys.readouterr()
    rows = journal.read_rows(tmp_path)
    assert len(rows) == 2, "a correction is a NEW row"
    assert [row["entry"] for row in rows] == [100.0, 100.5]


def test_a_zero_fill_is_refused_rather_than_recorded(journal, tmp_path) -> None:
    with pytest.raises(SystemExit):
        journal.main(["record", "--data", str(tmp_path), "--session", "2026-01-05",
                      "--fund", "IJR", "--entry", "0", "--exit", "101.0"])
    assert journal.read_rows(tmp_path) == []


def test_recording_without_a_fill_is_refused(journal, tmp_path) -> None:
    with pytest.raises(SystemExit):
        journal.main(["record", "--data", str(tmp_path), "--session", "2026-01-05", "--fund", "IJR"])


def test_a_fund_the_card_does_not_trade_is_refused(journal, tmp_path) -> None:
    with pytest.raises(SystemExit):
        journal.main(["record", "--data", str(tmp_path), "--session", "2026-01-05",
                      "--fund", "SPY", "--entry", "100", "--exit", "101"])


# --- end to end ---------------------------------------------------------------------------------


def _store(journal, tmp_path):
    from swingdesk.market_data import BarStore

    known = datetime(2026, 9, 20, tzinfo=UTC)
    bars = [_bar(date(2026, 1, 5) + timedelta(days=i), 100.5 + i, 100.0 + i, fund=fund)
            for i in range(5) for fund in journal.FUNDS]
    store = BarStore(tmp_path / "bars.duckdb")
    store.write(bars, known)
    store.close()
    return known


def test_report_prices_what_it_can_and_names_what_it_cannot(journal, tmp_path, capsys) -> None:
    known = _store(journal, tmp_path)
    journal.main(["record", "--data", str(tmp_path), "--session", "2026-01-05", "--fund", "IJR",
                  "--entry", "100.01", "--exit", "101.49"])
    journal.main(["record", "--data", str(tmp_path), "--session", "2026-02-02", "--fund", "VB",
                  "--entry", "100.0", "--exit", "101.0"])
    capsys.readouterr()
    assert journal.main(["report", "--data", str(tmp_path), "--as-of", known.isoformat()]) == journal.OK
    printed = capsys.readouterr().out
    assert "2026-01-05 IJR" in printed
    assert "PENDING" in printed and "2026-02-02 VB" in printed
    assert "MEAN COST A SIDE" in printed
    assert "NO JUDGEMENT YET" in printed


def test_a_missing_store_is_UNAVAILABLE_and_names_the_path(journal, tmp_path, capsys) -> None:
    assert journal.main(["report", "--data", str(tmp_path / "nowhere")]) == journal.UNAVAILABLE
    printed = capsys.readouterr().out
    assert "UNAVAILABLE" in printed and "no store at" in printed


def test_an_empty_journal_reports_nothing_rather_than_a_verdict(journal, tmp_path, capsys) -> None:
    known = _store(journal, tmp_path)
    assert journal.main(["report", "--data", str(tmp_path), "--as-of", known.isoformat()]) == journal.OK
    assert "nothing recorded yet" in capsys.readouterr().out


def test_a_fired_tripwire_exits_two_so_a_schedule_can_see_it(journal, tmp_path, capsys, monkeypatch) -> None:
    known = _store(journal, tmp_path)
    # Four nights, each filled a dollar away from the benchmark on both sides: far past a cent.
    monkeypatch.setattr(journal, "COST_TRIPWIRE_AFTER", 4)
    for i in range(4):
        session = (date(2026, 1, 5) + timedelta(days=i)).isoformat()
        journal.main(["record", "--data", str(tmp_path), "--session", session, "--fund", "IJR",
                      "--entry", str(101.0 + i), "--exit", str(100.0 + i)])
    capsys.readouterr()
    code = journal.main(["report", "--data", str(tmp_path), "--as-of", known.isoformat()])
    printed = capsys.readouterr().out
    assert code == journal.TRIPPED
    assert "TRIP-WIRE FIRED" in printed


def test_the_rows_live_beside_the_store_and_not_inside_it(journal, tmp_path) -> None:
    # The executions are a measurement record, not a bar: a second writer inside bars.duckdb would
    # be a second owner of a fact the store never held.
    assert journal.rows_path(tmp_path) == tmp_path / "card002" / "executions.jsonl"


def test_the_gate_constants_are_the_ones_the_card_names(journal) -> None:
    assert journal.COST_TRIPWIRE_PER_SIDE == 0.01
    assert journal.COST_TRIPWIRE_AFTER == 20
    assert journal.DRAWDOWN_ALERT == -0.25
    assert journal.NO_JUDGEMENT_BEFORE == 60


def test_a_recorded_row_keeps_what_the_owner_reported(journal, tmp_path, capsys) -> None:
    journal.main(["record", "--data", str(tmp_path), "--session", "2026-01-05", "--fund", "VB",
                  "--entry", "100.25", "--exit", "101.75", "--shares", "2", "--note", "first"])
    capsys.readouterr()
    row = json.loads(journal.rows_path(tmp_path).read_text(encoding="utf-8").strip())
    assert row["fund"] == "VB" and row["shares"] == 2 and row["note"] == "first"
    assert row["entry"] == 100.25 and row["exit"] == 101.75
    assert "recorded_at" in row
