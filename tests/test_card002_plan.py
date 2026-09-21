"""`tools/card002_plan.py` - the plan pass that prints what the owner types.

The four things worth breaking a build over, because each one was a real defect or a real
near-miss:

* the **session** comes from `Bar.session_date`, never from `event_time.date()`. The first cut used
  the timestamp and crashed against the contract, which says so in its own field description;
* a **stale fund refuses**, and refusing one does not refuse the other. The first live run found
  `VB` a session behind in the owner's own store, and the whole value of the pass is that it said
  so rather than sizing off Thursday's close;
* the **dividend belongs to the night**, because it detaches at the ex-date's open - the convention
  `PR-033`..`PR-036` measured on and the one a sign error would silently invert;
* **shares round DOWN**, because two legs rounded up are an account that cannot pay for its plan.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan():
    """The tool, imported by path - `tools/` is not a package and CI_POLICY 4 keeps it that way."""
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location("card002_plan", REPO / "tools" / "card002_plan.py")
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE it executes: `@dataclass` under `from __future__ import annotations`
    # resolves its annotations through `sys.modules[cls.__module__]`, and a module absent from
    # there fails at class creation rather than at use.
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _bar(session: date, open_: float, close: float, *, fund: str = "IJR"):
    from swingdesk.contracts.market import Bar, Interval, Series

    return Bar(
        instrument_id=fund, interval=Interval.DAY, series=Series.RAW,
        # DELIBERATELY a DIFFERENT calendar date from `session_date`. A stored bar's timestamp
        # need not agree with the session it belongs to - the contract says `session_date` is
        # stored and never derived from `event_time.date()` for exactly this reason - and every
        # bar here is timestamped 00:30 UTC the following day, which is what an evening fetch of a
        # 19:30 ET after-hours mark looks like. A code path that reads the timestamp therefore
        # reads a date one day ahead, and the refusal tests below catch it.
        event_time=datetime.combine(session, datetime.min.time(), tzinfo=UTC)
                   + timedelta(days=1, minutes=30),
        session_date=session,
        open=Decimal(str(open_)), high=Decimal(str(max(open_, close))),
        low=Decimal(str(min(open_, close))), close=Decimal(str(close)),
        volume=1_000, knowledge_time=datetime(2026, 9, 20, tzinfo=UTC),
    )


def _series(first: date, closes, opens, *, fund: str = "IJR"):
    """One bar a calendar day, which is enough - the pass reads consecutive STORED bars."""
    return [_bar(first + timedelta(days=i), opens[i], closes[i], fund=fund)
            for i in range(len(closes))]


# --- the arithmetic ---------------------------------------------------------------------------------


def test_a_night_is_the_next_open_over_this_close(plan) -> None:
    bars = _series(date(2026, 1, 5), closes=[100.0, 101.0], opens=[99.0, 102.0])
    nights = plan.nights_of(bars, {})
    assert len(nights) == 1
    assert nights[0].ret == pytest.approx(102.0 / 100.0 - 1.0)


def test_the_night_is_dated_by_the_session_it_ENDS_in(plan) -> None:
    bars = _series(date(2026, 1, 5), closes=[100.0, 101.0], opens=[99.0, 102.0])
    assert plan.nights_of(bars, {})[0].session == date(2026, 1, 6)


def test_the_dividend_is_paid_to_the_night_that_ends_at_its_ex_date(plan) -> None:
    bars = _series(date(2026, 1, 5), closes=[100.0, 101.0], opens=[99.0, 102.0])
    with_dividend = plan.nights_of(bars, {date(2026, 1, 6): 1.0})[0].ret
    assert with_dividend == pytest.approx(103.0 / 100.0 - 1.0)


def test_a_dividend_on_the_WRONG_session_does_not_reach_the_night(plan) -> None:
    bars = _series(date(2026, 1, 5), closes=[100.0, 101.0], opens=[99.0, 102.0])
    assert plan.nights_of(bars, {date(2026, 1, 5): 1.0})[0].ret == pytest.approx(0.02)


def test_the_session_is_read_from_session_date_and_not_from_the_timestamp(plan) -> None:
    bars = _series(date(2026, 1, 5), closes=[100.0, 101.0], opens=[99.0, 102.0])
    # The fixture's timestamp must disagree with its session, or this test proves nothing.
    assert bars[0].event_time.date() != bars[0].session_date
    assert plan.nights_of(bars, {})[0].session == bars[1].session_date
    # And the same for the freshness check, which is where reading the timestamp would admit a
    # fund a session behind: the bar's own timestamp is a day AHEAD of its session.
    three = _series(date(2026, 1, 5), closes=[100.0, 101.0, 102.0], opens=[99.0, 102.0, 103.0])
    fresh = plan.leg_for("IJR", three, {}, decision_session=three[-1].session_date, equity=10_000.0,
                         position_pct=50.0, lookback=2, owner_shares=1)
    assert fresh.admitted and fresh.prior_session == three[-1].session_date


@pytest.mark.parametrize(("equity", "pct", "price", "expected"), [
    (10_000.0, 50.0, 100.0, 50),
    (10_000.0, 50.0, 99.0, 50),      # 50.50 rounds DOWN
    (10_000.0, 50.0, 3_000.0, 1),
    (10_000.0, 50.0, 30_000.0, 0),   # not enough for one share
    (0.0, 50.0, 100.0, 0),
    (10_000.0, 50.0, 0.0, 0),
])
def test_shares_round_down_and_refuse_the_impossible(plan, equity, pct, price, expected) -> None:
    assert plan.size(equity, pct, price) == expected


# --- the refusals ------------------------------------------------------------------------------------


def _leg(plan, bars, *, session, lookback=3, dividends=None):
    return plan.leg_for("IJR", bars, dividends or {}, decision_session=session, equity=10_000.0,
                        position_pct=50.0, lookback=lookback, owner_shares=1)


def test_a_fund_a_session_behind_REFUSES_and_says_which_session(plan) -> None:
    bars = _series(date(2026, 1, 5), closes=[100.0] * 5, opens=[100.0] * 5)
    leg = _leg(plan, bars, session=date(2026, 1, 12))
    assert not leg.admitted
    assert "2026-01-09" in leg.refused and "2026-01-12" in leg.refused


def test_a_fund_with_too_few_stored_nights_REFUSES(plan) -> None:
    bars = _series(date(2026, 1, 5), closes=[100.0, 101.0], opens=[100.0, 101.0])
    leg = _leg(plan, bars, session=date(2026, 1, 6), lookback=14)
    assert not leg.admitted and "14 needed" in leg.refused


def test_a_lookback_of_one_REFUSES_rather_than_raising(plan) -> None:
    # A standard deviation of a single number is undefined, and `statistics.stdev` raises. The
    # registry says 14, so this cannot happen in production - but a pass whose contract is "refuse
    # cleanly" must not crash on the one input that has no answer.
    bars = _series(date(2026, 1, 5), closes=[100.0, 101.0], opens=[100.0, 101.0])
    leg = _leg(plan, bars, session=date(2026, 1, 6), lookback=1)
    assert not leg.admitted and "2 needed" in leg.refused


def test_a_fund_with_no_bars_at_all_REFUSES(plan) -> None:
    assert not _leg(plan, [], session=date(2026, 1, 6)).admitted


def test_an_admitted_fund_carries_R_as_notional_times_its_own_overnight_sd(plan) -> None:
    bars = _series(date(2026, 1, 5), closes=[100.0, 100.0, 100.0, 100.0],
                   opens=[100.0, 101.0, 99.0, 102.0])
    leg = plan.leg_for("IJR", bars, {}, decision_session=date(2026, 1, 8), equity=10_000.0,
                       position_pct=50.0, lookback=3, owner_shares=2)
    assert leg.admitted
    assert leg.nights == 3
    assert leg.notional == pytest.approx(200.0)
    assert leg.risk_r == pytest.approx(200.0 * leg.overnight_sd)
    assert leg.overnight_sd > 0


def test_the_decision_session_is_the_LATEST_any_fund_reached(plan) -> None:
    ahead = _series(date(2026, 1, 5), closes=[100.0] * 3, opens=[100.0] * 3)
    behind = _series(date(2026, 1, 5), closes=[100.0] * 2, opens=[100.0] * 2, fund="VB")
    assert plan.decision_session_of({"IJR": ahead, "VB": behind}) == date(2026, 1, 7)


def test_no_bars_anywhere_gives_no_decision_session(plan) -> None:
    assert plan.decision_session_of({"IJR": [], "VB": []}) is None


# --- end to end, on a synthetic store ------------------------------------------------------------------


def _store(plan, tmp_path, *, vb_behind: bool):
    from swingdesk.market_data import BarStore

    known = datetime(2026, 9, 20, tzinfo=UTC)
    first = date(2026, 1, 5)
    bars = []
    for fund in plan.FUNDS:
        length = 20 - (1 if (vb_behind and fund == "VB") else 0)
        bars += _series(first, closes=[100.0 + i for i in range(length)],
                        opens=[100.5 + i for i in range(length)], fund=fund)
    store = BarStore(tmp_path / "bars.duckdb")
    store.write(bars, known)
    store.close()
    return known


def _args(plan, tmp_path, known, **over):
    import argparse

    base = dict(data=tmp_path, equity=100_000.0, shares=1, session=None,
                as_of=known.isoformat(), out=None)
    return argparse.Namespace(**(base | over))


def test_both_funds_fresh_plans_both_and_exits_zero(plan, tmp_path, capsys) -> None:
    known = _store(plan, tmp_path, vb_behind=False)
    assert plan.main([
        "--data", str(tmp_path), "--equity", "100000", "--shares", "1",
        "--as-of", known.isoformat(),
    ]) == plan.PLANNED
    printed = capsys.readouterr().out
    assert "BUY  1  IJR   MOC" in printed and "BUY  1  VB   MOC" in printed
    assert "SELL 1  IJR   MOO" in printed
    # Both instructions carry the venue's own clock. An order typed after the cut-off is not a
    # late order, it is a rejected one, so the window is part of the instruction.
    assert plan.CLOSE_CUTOFF_ET in printed
    assert plan.OPEN_WINDOW_ET in printed


def test_one_stale_fund_refuses_ITSELF_and_the_other_still_trades(plan, tmp_path, capsys) -> None:
    known = _store(plan, tmp_path, vb_behind=True)
    assert plan.main([
        "--data", str(tmp_path), "--equity", "100000", "--as-of", known.isoformat(),
    ]) == plan.REFUSED
    printed = capsys.readouterr().out
    assert "VB    REFUSED" in printed
    assert "BUY  1  IJR   MOC" in printed
    assert "BUY  1  VB" not in printed


def test_a_missing_store_is_UNAVAILABLE_and_names_the_path_it_wanted(plan, tmp_path, capsys) -> None:
    # Naming the path is the whole difference between "unavailable" and "there is nothing to do".
    # A pass that reports an empty plan on a store it never found is the failure mode
    # FAIL_CLOSED_POLICY exists to prevent, and the two are told apart by the message.
    assert plan.main(["--data", str(tmp_path / "nowhere")]) == plan.UNAVAILABLE
    printed = capsys.readouterr().out
    assert "UNAVAILABLE" in printed
    assert "no store at" in printed and "nowhere" in printed


def test_the_plan_is_written_as_a_record_when_asked(plan, tmp_path) -> None:
    import json

    known = _store(plan, tmp_path, vb_behind=False)
    out = tmp_path / "plans" / "plan.json"
    plan.main(["--data", str(tmp_path), "--equity", "100000", "--as-of", known.isoformat(),
               "--out", str(out)])
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["card"] == "CARD-002"
    assert written["refused"] == []
    assert {leg["fund"] for leg in written["legs"]} == set(plan.FUNDS)
    assert written["position_pct"] == 50.0


def test_the_record_names_the_refused_fund(plan, tmp_path) -> None:
    import json

    known = _store(plan, tmp_path, vb_behind=True)
    out = tmp_path / "plan.json"
    plan.main(["--data", str(tmp_path), "--equity", "100000", "--as-of", known.isoformat(),
               "--out", str(out)])
    assert json.loads(out.read_text(encoding="utf-8"))["refused"] == ["VB"]


def test_nothing_admitted_says_so_instead_of_printing_an_empty_order(plan, capsys) -> None:
    plan.report({"decided_from": "2026-01-05", "as_of": "2026-09-20T00:00:00+00:00",
                 "position_pct": 50.0, "paper_equity": 0.0,
                 "legs": [{"fund": "IJR", "refused": "no stored bars"},
                          {"fund": "VB", "refused": "no stored bars"}]})
    printed = capsys.readouterr().out
    assert "nothing to enter" in printed
    assert "MOC" not in printed


def test_the_venue_cutoffs_are_the_ones_DR_048_names(plan) -> None:
    assert plan.CLOSE_CUTOFF_ET == "15:50"
    assert "19:00" in plan.OPEN_WINDOW_ET and "09:28" in plan.OPEN_WINDOW_ET


def test_the_card_trades_exactly_the_two_funds_PR_034_accepted(plan) -> None:
    assert plan.FUNDS == ("IJR", "VB")
