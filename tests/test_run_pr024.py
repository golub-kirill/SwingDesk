"""`tools/run_pr024.py`: entering near the close against entering at the open, for `CARD-001`.

The cases that carry the study:

* **the entry day is read from the fill.** A fall at 10:00 stops the open arm and cannot touch the
  close arm, whose order did not exist yet;
* **the walk IS the engine.** Priced at the daily open with `PR-016`'s costs, it equals `run_arm`
  trade for trade across every exit the engine can produce;
* **each entry pays its own spread**, a stale or crossed window prices nothing, and every entry that
  cannot be priced is counted under its reason;
* **section 6 in its order**, the floor gating NULL only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.trade import ExitReason
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import Minute, MinuteStore
from swingdesk.market_data.quotes import CLOSE, ELEVEN, OPEN, Quote, QuoteStore
from swingdesk.reference_data import calendar as cal

REPO = Path(__file__).resolve().parents[1]
KNOWN = datetime(2026, 1, 5, tzinfo=UTC)
NYSE = cal.exchange_for("SPY")


@pytest.fixture(scope="module")
def run() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_run_pr024", REPO / "tools" / "run_pr024.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sessions(start: date, end: date):
    return list(cal.sessions(NYSE, start, end))


def _bar(name: str, session, o: float, h: float, lo: float, c: float) -> Bar:
    return Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
               event_time=session.open_time, session_date=session.session_date,
               open=Decimal(f"{o:.4f}"), high=Decimal(f"{h:.4f}"), low=Decimal(f"{lo:.4f}"),
               close=Decimal(f"{c:.4f}"), volume=1_000_000, knowledge_time=KNOWN)


def _minutes(session, path) -> list[Minute]:
    """Regular-hours minutes whose price at minute `i` is `path(i)`, each with a 0.05 range."""
    out = []
    at = session.open_time.astimezone(UTC)
    for i in range(session.duration_minutes):
        price = Decimal(f"{path(i):.4f}")
        out.append(Minute(at=at + timedelta(minutes=i), open=price, high=price + Decimal("0.05"),
                          low=price - Decimal("0.05"), close=price))
    return out


def _bar_from(name: str, session, minutes: list[Minute]) -> Bar:
    return Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
               event_time=session.open_time, session_date=session.session_date,
               open=minutes[0].open, high=max(m.high for m in minutes),
               low=min(m.low for m in minutes), close=minutes[-1].close,
               volume=1_000_000, knowledge_time=KNOWN)


def _quotes(at: datetime, half_bps: float, mid: float = 100.0, n: int = 5) -> list[Quote]:
    half = mid * half_bps / 10000
    return [Quote(at=at + timedelta(seconds=i), bid=Decimal(f"{mid - half:.6f}"),
                  ask=Decimal(f"{mid + half:.6f}")) for i in range(n)]


# --- pricing ------------------------------------------------------------------------------------------


def test_the_half_spread_is_half_the_median_proportional_spread(run) -> None:
    at = datetime(2026, 3, 2, 14, 30, 5, tzinfo=UTC)
    quotes = [Quote(at, Decimal("99.9"), Decimal("100.1")),        # 20 bps
              Quote(at, Decimal("99.8"), Decimal("100.2")),        # 40 bps
              Quote(at, Decimal("99.95"), Decimal("100.05"))]      # 10 bps
    assert run.half_spread_bps(quotes, at) == Decimal("10")


def test_crossed_locked_and_one_sided_quotes_are_dropped_not_read_as_zero(run) -> None:
    at = datetime(2026, 3, 2, 14, 30, 5, tzinfo=UTC)
    quotes = [Quote(at, Decimal("100"), Decimal("100")),           # locked
              Quote(at, Decimal("100.1"), Decimal("100")),         # crossed
              Quote(at, Decimal("0"), Decimal("100")),             # one-sided
              Quote(at, Decimal("99.9"), Decimal("100.1"))]        # 20 bps
    assert run.half_spread_bps(quotes, at) == Decimal("10")
    assert run.half_spread_bps(quotes[:3], at) is None


def test_a_stale_window_prices_nothing(run) -> None:
    """A first quote a minute and more after the instant describes a later book."""
    at = datetime(2026, 3, 2, 14, 30, 5, tzinfo=UTC)
    late = [Quote(at + timedelta(seconds=61), Decimal("99.9"), Decimal("100.1"))]
    fresh = [Quote(at + timedelta(seconds=60), Decimal("99.9"), Decimal("100.1"))]
    assert run.half_spread_bps(late, at) is None
    assert run.half_spread_bps(fresh, at) == Decimal("10")
    assert run.half_spread_bps([], at) is None


def test_the_fill_minute_starts_at_the_instant_or_within_five_minutes(run) -> None:
    at = datetime(2026, 3, 2, 20, 55, tzinfo=UTC)
    minute = lambda offset: Minute(at + timedelta(minutes=offset), *[Decimal(1)] * 4)  # noqa: E731
    assert run.fill_minute([minute(-1), minute(0), minute(1)], at).at == at
    assert run.fill_minute([minute(-2), minute(4)], at).at == at + timedelta(minutes=4)
    assert run.fill_minute([minute(-2), minute(5)], at) is None, "five minutes late is too late"
    assert run.fill_minute([minute(-3)], at) is None


@pytest.mark.parametrize(("day", "moment", "local"), [
    (date(2026, 3, 2), OPEN, (9, 30)),
    (date(2026, 3, 2), ELEVEN, (11, 0)),
    (date(2026, 3, 2), CLOSE, (15, 55)),
    (date(2026, 11, 27), CLOSE, (12, 55)),
])
def test_each_arm_meets_the_tape_at_its_own_minute(run, day, moment, local) -> None:
    instant = run.fill_instant(cal.session(NYSE, day), moment)
    assert (instant.hour, instant.minute) == local


def test_after_fill_keeps_the_fill_minute_and_everything_after_it(run) -> None:
    session = cal.session(NYSE, date(2026, 3, 2))
    minutes = _minutes(session, lambda i: 100 + i * 0.01)
    fill = minutes[10]
    kept = run.after_fill(list(reversed(minutes)), fill)
    assert kept[0] == fill and len(kept) == len(minutes) - 10


# --- the walk ---------------------------------------------------------------------------------------------


def _day_and_after(run, entry_path):
    """Thirty flat sessions, an entry session driven by `entry_path`, then thirty flat sessions."""
    sessions = _sessions(date(2026, 1, 2), date(2026, 5, 29))[:61]
    signal, entered = sessions[29], sessions[30]
    bars = [_bar("X", s, 100, 100.5, 99.5, 100) for s in sessions]
    minutes = _minutes(entered, entry_path)
    bars[30] = _bar_from("X", entered, minutes)
    entry = run.Entry("X", signal.session_date, entered.session_date)
    return entry, bars, minutes, entered


def test_a_fall_at_ten_stops_the_open_arm_and_not_the_close_arm(run) -> None:
    """THE LOOK-AHEAD GUARD. ATR 2 puts the stop 4 below the fill; the name falls 6 at 10:00 and
    is back by 11:00. The open arm held through the fall; the close arm's order did not exist."""
    def path(i: int) -> float:
        return 94.0 if 30 <= i < 60 else 100.0

    entry, bars, minutes, entered = _day_and_after(run, path)
    free = run.cost(Decimal(0))
    counts: Counter[str] = Counter()

    opened = run.walk_entry(entry, bars, Decimal(2), minutes[0].open, free, lambda _r: free,
                            run.after_fill(minutes, minutes[0]), None, counts, "O")
    late_fill = run.fill_minute(minutes, run.fill_instant(entered, CLOSE))
    closed = run.walk_entry(entry, bars, Decimal(2), late_fill.open, free, lambda _r: free,
                            run.after_fill(minutes, late_fill), None, counts, "C")

    assert opened.exit_reason is ExitReason.STOP and opened.exit_date == entry.session_date
    assert closed.exit_date != entry.session_date
    assert closed.exit_reason is ExitReason.TIME


def test_both_arms_risk_the_same_dollars_per_share(run) -> None:
    """The stop sits 2xATR below each arm's own fill, so R and the share count are the same."""
    entry, bars, minutes, entered = _day_and_after(run, lambda i: 100 + i * 0.002)
    free = run.cost(Decimal(0))
    late_fill = run.fill_minute(minutes, run.fill_instant(entered, CLOSE))
    o = run.walk_entry(entry, bars, Decimal(2), minutes[0].open, free, lambda _r: free,
                       run.after_fill(minutes, minutes[0]), None, Counter(), "O")
    c = run.walk_entry(entry, bars, Decimal(2), late_fill.open, free, lambda _r: free,
                       run.after_fill(minutes, late_fill), None, Counter(), "C")
    assert o.initial_risk_per_share == c.initial_risk_per_share == Decimal(4)
    assert o.shares == c.shares
    assert o.entry_price != c.entry_price


def test_an_exit_is_charged_at_its_own_moment(run) -> None:
    entry, bars, minutes, _ = _day_and_after(run, lambda i: 100.0)
    asked: list[ExitReason] = []

    def exits(reason: ExitReason):
        asked.append(reason)
        return run.cost(Decimal(50))

    trade = run.walk_entry(entry, bars, Decimal(2), minutes[0].open, run.cost(Decimal(10)), exits,
                           run.after_fill(minutes, minutes[0]), None, Counter(), "O")
    assert asked == [ExitReason.TIME]
    assert trade.entry_price == Decimal("100") * Decimal("1.001")
    assert trade.exit_price == Decimal("100.0000") * Decimal("0.995")
    assert trade.costs == 0, "commission is zero (DR-039)"


def test_an_entry_day_tie_is_answered_by_the_minutes_after_the_fill(run) -> None:
    """Target (fill + 4) prints at 10:00, the stop (fill - 4) at 14:00: the target came first."""
    def path(i: int) -> float:
        if 30 <= i < 40:
            return 105.0
        if 270 <= i < 280:
            return 95.0
        return 100.0

    entry, bars, minutes, _ = _day_and_after(run, path)
    free = run.cost(Decimal(0))
    counts: Counter[str] = Counter()
    trade = run.walk_entry(entry, bars, Decimal(2), minutes[0].open, free, lambda _r: free,
                           run.after_fill(minutes, minutes[0]), None, counts, "O")
    assert trade.exit_reason is ExitReason.TARGET
    assert counts["entry_day_target"] == 1


def test_an_anchor_places_the_legs_from_the_decision_not_from_the_fill(run) -> None:
    """The live bracket's stop is priced in the evening. A cheaper fill keeps the same stop, so the
    saving is not given back when the stop is hit."""
    entry, bars, minutes, _entered = _day_and_after(run, lambda i: 100.0)
    free = run.cost(Decimal(0))
    anchored = run.walk_entry(entry, bars, Decimal(2), Decimal("99"), free, lambda _r: free,
                              run.after_fill(minutes, minutes[0]), None, Counter(), "C",
                              anchor=Decimal("100"))
    assert anchored.stop_price == Decimal("96")
    assert anchored.initial_risk_per_share == Decimal("3"), "R is still the position's own"
    assert anchored.shares == int(Decimal(1000) / Decimal(3))


def test_an_anchored_stop_above_the_fill_is_a_reason(run) -> None:
    """The fill gapped below where the evening placed the stop: the order would have been stopped
    at once, and that is counted, not traded."""
    entry, bars, minutes, _ = _day_and_after(run, lambda i: 100.0)
    free = run.cost(Decimal(0))
    assert run.walk_entry(entry, bars, Decimal(2), Decimal("95"), free, lambda _r: free,
                          run.after_fill(minutes, minutes[0]), None, Counter(), "C",
                          anchor=Decimal("100")) == "stop_not_below_entry"


def test_an_entry_on_the_last_stored_bar_ends_the_data_there(run) -> None:
    """The engine never evaluates the final bar, so neither does the walk."""
    sessions = _sessions(date(2026, 1, 2), date(2026, 3, 2))[:20]
    bars = [_bar("X", s, 100, 100.5, 99.5, 100) for s in sessions]
    entry = run.Entry("X", sessions[-2].session_date, sessions[-1].session_date)
    free = run.cost(Decimal(0))
    trade = run.walk_entry(entry, bars, Decimal(2), Decimal(100), free, lambda _r: free, None,
                           None, Counter(), "O")
    assert trade.exit_reason is ExitReason.END_OF_DATA
    assert trade.exit_date == sessions[-1].session_date


def test_per_dollar_is_net_of_the_commission(run) -> None:
    from swingdesk.contracts.trade import Trade

    trade = Trade(instrument_id="X", arm="O", signal_date=date(2026, 3, 2),
                  entry_date=date(2026, 3, 3), exit_date=date(2026, 3, 10),
                  entry_price=Decimal(100), stop_price=Decimal(96), exit_price=Decimal(102),
                  shares=10, initial_risk_per_share=Decimal(4), costs=Decimal(5),
                  mfe=Decimal(0), mae=Decimal(0), exit_reason=ExitReason.TIME)
    assert run.per_dollar(trade) == (20 - 5) / 1000


def test_an_entry_the_store_does_not_hold_is_a_reason(run) -> None:
    sessions = _sessions(date(2026, 1, 2), date(2026, 3, 2))[:20]
    bars = [_bar("X", s, 100, 100.5, 99.5, 100) for s in sessions]
    entry = run.Entry("X", date(2026, 6, 1), date(2026, 6, 2))
    free = run.cost(Decimal(0))
    assert run.walk_entry(entry, bars, Decimal(2), Decimal(100), free, lambda _r: free, None,
                          None, Counter(), "O") == "entry_session_not_stored"


def test_a_stop_that_is_not_a_price_is_a_reason_not_a_crash(run) -> None:
    sessions = _sessions(date(2026, 1, 2), date(2026, 3, 2))[:20]
    bars = [_bar("X", s, 100, 100.5, 99.5, 100) for s in sessions]
    entry = run.Entry("X", sessions[5].session_date, sessions[6].session_date)
    free = run.cost(Decimal(0))
    assert run.walk_entry(entry, bars, Decimal(60), Decimal(100), free, lambda _r: free, None,
                          None, Counter(), "O") == "stop_not_positive"


# --- parity with the engine ------------------------------------------------------------------------------


def _random_series(seed: int, count: int = 160, vol: float = 0.03) -> BarSeries:
    rng = random.Random(seed)
    sessions = _sessions(date(2024, 1, 2), date(2025, 12, 31))[:count]
    price, bars = 50.0, []
    for s in sessions:
        opened = price * (1 + rng.gauss(0, vol))
        close = opened * (1 + rng.gauss(0, vol))
        high = max(opened, close) * (1 + abs(rng.gauss(0, vol / 2)))
        low = min(opened, close) * (1 - abs(rng.gauss(0, vol / 2)))
        bars.append(_bar("R", s, opened, high, low, close))
        price = close
    return BarSeries(instrument_id="R", interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=KNOWN, bars=bars)


def test_the_walk_is_the_engine_on_every_exit_it_can_produce(run) -> None:
    """THE PARITY. Priced at the daily open with PR-016's costs, every signal date of several
    volatile random series gives the engine's own trade - and between them those dates cover the
    gap, the stop, the target, the clock and the end of the data."""
    from swingdesk.derived_observations import atr as atr_component

    reasons: Counter[str] = Counter()
    checked = 0
    for seed in range(6):
        series = _random_series(seed)
        atr_series = atr_component.compute(series, run.atr_registry())
        for index in range(20, len(series.bars) - 1, 3):
            bar, nxt = series.bars[index], series.bars[index + 1]
            entry = run.Entry("R", bar.session_date, nxt.session_date)
            ours, theirs = run.parity_trade(entry, series, atr_series, None)
            assert run.same_trade(ours, theirs), (seed, index, ours, theirs)
            checked += 1
            if not isinstance(ours, str):
                reasons[ours.exit_reason.value] += 1
    assert checked > 200
    assert {"stop", "stop_gap", "target", "time", "end_of_data"} <= set(reasons), reasons


def test_same_trade_notices_a_different_exit(run) -> None:
    from swingdesk.derived_observations import atr as atr_component

    series = _random_series(3)
    atr_series = atr_component.compute(series, run.atr_registry())
    bar, nxt = series.bars[40], series.bars[41]
    ours, theirs = run.parity_trade(run.Entry("R", bar.session_date, nxt.session_date), series,
                                    atr_series, None)
    moved = theirs.model_copy(update={"exit_price": theirs.exit_price + 1})
    assert run.same_trade(ours, theirs) and not run.same_trade(ours, moved)
    assert not run.same_trade(ours, None)
    assert run.same_trade("no_atr", None)


# --- the sample -------------------------------------------------------------------------------------------


def _selection(run, picks: dict[str, list[date]]):
    from stream_selection import Selection

    return Selection(selected=picks)


def test_each_date_draws_its_own_names_with_its_own_seed(run) -> None:
    """Dropping a date moves nothing about any other date's draw."""
    calendar = [s.session_date for s in _sessions(date(2026, 3, 2), date(2026, 3, 13))]
    d1, d2 = calendar[0], calendar[3]
    names = [f"N{i:02d}" for i in range(20)]
    selection = _selection(run, {n: [d1, d2] for n in names})

    both = run.draw(selection, calendar, [d1, d2], 6, 7)
    alone = run.draw(selection, calendar, [d2], 6, 7)

    assert [e for e in both if e.signal_date == d2] == alone
    assert len(both) == 12
    firsts = {e.instrument_id for e in both if e.signal_date == d1}
    seconds = {e.instrument_id for e in both if e.signal_date == d2}
    assert firsts != seconds, "two dates with one pool must not draw the same six names"
    assert all(e.session_date == calendar[calendar.index(e.signal_date) + 1] for e in both)


def test_a_date_with_fewer_names_than_asked_keeps_them_all(run) -> None:
    calendar = [s.session_date for s in _sessions(date(2026, 3, 2), date(2026, 3, 13))]
    selection = _selection(run, {"A": [calendar[0]], "B": [calendar[0]]})
    drawn = run.draw(selection, calendar, [calendar[0]], 6, 7)
    assert [e.instrument_id for e in drawn] == ["A", "B"]


def test_a_date_without_a_next_session_draws_nothing(run) -> None:
    calendar = [s.session_date for s in _sessions(date(2026, 3, 2), date(2026, 3, 13))]
    selection = _selection(run, {"A": [calendar[-1]]})
    assert run.draw(selection, calendar, [calendar[-1]], 6, 7) == []


def test_formation_dates_leave_room_for_the_lookback_and_the_hold(run) -> None:
    calendar = [date(2020, 1, 1) + timedelta(days=i) for i in range(400)]
    got = run.formation_dates(calendar, calendar[0], calendar[-1])
    assert got[0] == calendar[run.LOOKBACK]
    assert got[-1] == calendar[-run.HOLD - 2]
    assert run.formation_dates(calendar[:50], calendar[0], calendar[49]) == []


def test_the_window_is_the_last_forty_eight_months(run) -> None:
    """Not `PR-016`'s 2016 start: a session before the cut is never a formation date."""
    calendar = [s.session_date for s in _sessions(date(2019, 1, 2), date(2026, 9, 15))]
    start, got = run.window_formations(calendar)
    assert start == date(2022, 9, 15)
    assert got[0] >= start and got[0] < date(2022, 9, 23)
    assert got[-1] == calendar[-run.HOLD - 2]


def test_no_count_picks_every_formation_date(run) -> None:
    formations = [date(2020, 1, 1) + timedelta(days=i) for i in range(30)]
    assert run.pick_dates(formations, None, 5) == formations
    assert run.DATES is None, "the registered draw is every formation session"


def test_picked_dates_are_seeded_and_in_order(run) -> None:
    formations = [date(2020, 1, 1) + timedelta(days=i) for i in range(100)]
    first = run.pick_dates(formations, 10, 5)
    assert first == sorted(first) and first == run.pick_dates(formations, 10, 5)
    assert run.pick_dates(formations, 200, 5) == formations


def test_the_sample_round_trips_through_its_file(run, tmp_path) -> None:
    entries = [run.Entry("A", date(2026, 3, 2), date(2026, 3, 3))]
    run.write_sample(entries, tmp_path / "s.jsonl")
    assert run.read_sample(tmp_path / "s.jsonl") == entries
    assert set(json.loads((tmp_path / "s.jsonl").read_text().splitlines()[0])) == {
        "instrument_id", "signal_date", "session_date"}, "nothing known after the signal"


# --- section 6 ------------------------------------------------------------------------------------------


def _cell(lo=0.001, hi=0.002, level_hi=0.01, adverse=0.001, share=0.95, pairs=3000, months=60):
    width = hi - lo
    return {"difference": {"estimate": (lo + hi) / 2, "lo": lo, "hi": hi, "width": width},
            "level": {"estimate": 0.0, "lo": -0.01, "hi": level_hi, "width": 0.02},
            "cost_adverse": {"estimate": adverse, "lo": 0.0, "hi": 0.0, "width": 0.0},
            "complete_share": share, "pairs": pairs, "months": months}


@pytest.mark.parametrize(("cell", "branch"), [
    (_cell(share=0.89), "REFUSED"),
    (_cell(pairs=10), "REFUSED"),
    (_cell(months=5), "REFUSED"),
    (_cell(level_hi=-0.001), "BOTH_NEGATIVE"),
    (_cell(adverse=0.0), "COST_FRAGILE"),
    (_cell(), "ACCEPT"),
    (_cell(lo=0.0001, hi=0.02), "ACCEPT"),
    (_cell(lo=-0.003, hi=-0.001), "REJECT"),
    (_cell(lo=-0.003, hi=-0.0005, level_hi=-0.1), "REJECT"),
    (_cell(lo=-0.002, hi=0.002), "INCONCLUSIVE"),
    (_cell(lo=-0.001, hi=0.001), "NULL"),
    (_cell(lo=-0.0015, hi=0.0015), "NULL"),
    (_cell(lo=-0.0004, hi=0.0004), "NULL"),
    (_cell(lo=-0.00001, hi=0.002), "NULL"),
])
def test_section_six_in_its_order(run, cell, branch) -> None:
    assert run.branch_for(cell) == branch


def test_an_interval_that_could_not_be_computed_is_inconclusive(run) -> None:
    cell = _cell()
    cell["difference"] = {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "width": math.nan}
    assert run.branch_for(cell) == "INCONCLUSIVE"


def test_the_floor_gates_null_only(run) -> None:
    """A wide interval wholly above zero is an ACCEPT; a wide one straddling zero is not a NULL."""
    assert run.branch_for(_cell(lo=0.0001, hi=0.05)) == "ACCEPT"
    assert run.branch_for(_cell(lo=-0.004, hi=0.001)) == "INCONCLUSIVE"


def test_every_branch_has_a_token(run) -> None:
    assert set(run.TOKEN) == {"ACCEPT", "REJECT", "NULL", "BOTH_NEGATIVE", "COST_FRAGILE",
                              "INCONCLUSIVE", "REFUSED"}


# --- one entry, every arm, and the end-to-end smoke --------------------------------------------------------


def _world(tmp_path: Path, run, names=("AAA", "BBB"), spread_bps=(20.0, 5.0, 2.0)):
    """A bar store, a minute store and a quote store for a handful of entries on real sessions."""
    sessions = _sessions(date(2025, 1, 2), date(2025, 12, 31))
    bars, entries = [], []
    minutes_store = MinuteStore(tmp_path / "minutes.duckdb")
    quotes_store = QuoteStore(tmp_path / "quotes.duckdb")
    rng = random.Random(4)
    for name in ("SPY", *names):
        price = 100.0
        for i, s in enumerate(sessions):
            if name != "SPY" and 40 <= i <= 200 and i % 20 == 0:
                start = price
                minutes = _minutes(s, lambda k, p=start: p * (1 + 0.0001 * math.sin(k / 30)))
                bars.append(_bar_from(name, s, minutes))
                minutes_store.write(name, s.session_date, minutes, KNOWN, "test")
                for moment, half in zip((OPEN, ELEVEN, CLOSE), spread_bps, strict=True):
                    asked = {OPEN: s.open_time + timedelta(seconds=5),
                             ELEVEN: s.open_time.replace(hour=11, minute=0),
                             CLOSE: s.close_time - timedelta(minutes=5)}[moment].astimezone(UTC)
                    quotes_store.write(name, s.session_date, moment, asked,
                                       _quotes(asked, half, start), KNOWN, "test")
                entries.append(run.Entry(name, sessions[i - 1].session_date, s.session_date))
                price = float(minutes[-1].close)
                continue
            opened = price * (1 + rng.gauss(0, 0.004))
            price = opened * (1 + rng.gauss(0.0005, 0.01))
            bars.append(_bar(name, s, opened, max(opened, price) * 1.004,
                             min(opened, price) * 0.996, price))
    minutes_store.close()
    quotes_store.close()
    with BarStore(tmp_path / "bars.duckdb") as store:
        store.write(bars, KNOWN)
    sample = tmp_path / "sample.jsonl"
    run.write_sample(entries, sample)
    return argparse.Namespace(data=tmp_path, minutes=tmp_path / "minutes.duckdb",
                              quotes=tmp_path / "quotes.duckdb", sample=sample, as_of=None,
                              minutes_as_of=None, quotes_as_of=None, resamples=50), entries


def test_the_run_goes_end_to_end_on_synthetic_stores(run, tmp_path) -> None:
    args, entries = _world(tmp_path, run)
    payload = run.build(args)

    assert payload["branch"] == "SMOKE" and payload["verdict"] == "smoke"
    assert payload["prereg"] == "PR-024" and payload["trials"] == 2
    assert payload["sample"]["drawn"] == len(entries)
    assert payload["sample"]["complete"] == len(entries), payload["sample"]["excluded"]
    for key in ("country", "split", "perturbations", "measured_span", "registered_settings",
                "cells", "as_of"):
        assert key in payload
    assert payload["split"]["buys"]
    assert set(payload["perturbations"]["registered"]) == set(payload["perturbations"]["run"])
    cell = payload["cells"]["C"]
    assert cell["pairs"] == len(entries) and cell["complete_share"] == 1.0
    # The close arm paid 2 bps where the open arm paid 20 and the price barely moved, so the
    # close arm is ahead net and the cost part is positive.
    assert cell["cost_part"] > 0
    assert cell["difference"]["estimate"] > cell["gross_part"]["estimate"]
    assert "anchored_stop" in cell
    json.dumps(payload, default=run._default)


def test_where_both_arms_leave_at_one_price_the_stress_shrinks_the_saving(run, tmp_path) -> None:
    """The clock and a gap fill both arms at the same quoted price, so the whole difference is the
    entry cost - and tripling the close arm's spread must shrink it. At a stop or a target the
    engine's legs sit relative to each arm's own fill, so most of the saving comes back out; that is
    measured here rather than assumed, and it is what `anchored_stop` exists to separate."""
    args, _ = _world(tmp_path, run)
    priced, *_ = run.price_sample(args, run.read_sample(args.sample))

    def difference(p, costing):
        return (run.per_dollar(p.trades[costing]["C"]) - run.per_dollar(p.trades[costing]["O"]))

    same_price = [p for p in priced
                  if p.trades["net"]["O"].exit_reason in (ExitReason.TIME, ExitReason.STOP_GAP)
                  and p.trades["net"]["C"].exit_reason is p.trades["net"]["O"].exit_reason
                  and p.trades["net"]["C"].exit_date == p.trades["net"]["O"].exit_date
                  and p.trades["cost_adverse"]["C"].exit_date == p.trades["net"]["C"].exit_date]
    assert same_price, "the synthetic world must hold at least one clock or gap exit"
    for p in same_price:
        assert difference(p, "cost_adverse") < difference(p, "net")
        assert difference(p, "net") > 0.0015, "about the 18 bps the spreads differ by"

    from_the_fill = [p for p in priced
                     if p.trades["gross"]["O"].exit_reason is ExitReason.STOP
                     and p.trades["gross"]["C"].exit_date == p.trades["gross"]["O"].exit_date]
    for p in from_the_fill:
        assert abs(difference(p, "gross")) < 0.0001, "gross, a stop is the same loss per dollar"


def test_every_entry_that_cannot_be_priced_is_counted_under_its_reason(run, tmp_path) -> None:
    args, entries = _world(tmp_path, run)
    sessions = [s.session_date for s in _sessions(date(2025, 1, 2), date(2025, 12, 31))]
    extra = [run.Entry("AAA", sessions[49], sessions[50]),     # a session whose minutes nobody stored
             run.Entry("ZZZ", sessions[49], sessions[50])]     # a name the store has never held
    assert all(e.session_date != sessions[50] for e in entries)
    run.write_sample([*entries, *extra], args.sample)
    payload = run.build(args)
    assert payload["sample"]["excluded"] == {"minutes_unavailable": 1, "series_unavailable": 1}
    assert payload["cells"]["C"]["complete_share"] == len(entries) / (len(entries) + 2)


def test_price_entry_refuses_minutes_that_are_not_the_bar(run, tmp_path) -> None:
    _args, entries = _world(tmp_path, run)
    entry = entries[0]
    session = cal.session(NYSE, entry.session_date)
    with BarStore(tmp_path / "bars.duckdb") as store:
        series = store.as_of(entry.instrument_id, Interval.DAY, Series.RAW, KNOWN)
    shifted = [Minute(m.at, m.open * 2, m.high * 2, m.low * 2, m.close * 2)
               for m in _minutes(session, lambda k: 100.0)]
    got = run.price_entry(entry, series, Decimal(2), tuple(shifted), {}, session, None, Counter())
    assert got == "minutes_mismatch"


def test_price_entry_needs_every_moment_s_fresh_quote(run, tmp_path) -> None:
    _args, entries = _world(tmp_path, run)
    entry = entries[0]
    session = cal.session(NYSE, entry.session_date)
    with BarStore(tmp_path / "bars.duckdb") as store:
        series = store.as_of(entry.instrument_id, Interval.DAY, Series.RAW, KNOWN)
    with MinuteStore(tmp_path / "minutes.duckdb") as minutes_store:
        minutes = minutes_store.session(entry.instrument_id, entry.session_date, KNOWN)
    with QuoteStore(tmp_path / "quotes.duckdb") as quotes_store:
        windows = {m: quotes_store.window(entry.instrument_id, entry.session_date, m, KNOWN)
                   for m in (OPEN, ELEVEN, CLOSE)}

    missing = {**windows, CLOSE: None}
    assert run.price_entry(entry, series, Decimal(2), minutes, missing, session, None,
                           Counter()) == "quotes_unavailable"
    requested, quotes = windows[OPEN]
    stale = {**windows, OPEN: (requested - timedelta(minutes=5), quotes)}
    assert run.price_entry(entry, series, Decimal(2), minutes, stale, session, None,
                           Counter()) == "no_fresh_two_sided_quote"
    no_late_print = tuple(m for m in minutes if m.at < run.fill_instant(session, CLOSE))
    assert run.price_entry(entry, series, Decimal(2), no_late_print, windows, session, None,
                           Counter()) in ("no_print_at_the_moment", "minutes_mismatch")
    assert run.price_entry(entry, series, Decimal(2), None, windows, session, None,
                           Counter()) == "minutes_unavailable"
    priced = run.price_entry(entry, series, Decimal(2), minutes, windows, session, None, Counter())
    assert set(priced.trades) == set(run.COSTINGS)
    assert all(set(priced.trades[c]) == set(run.ARMS) for c in run.COSTINGS)
    assert priced.spreads == {OPEN: Decimal("20"), ELEVEN: Decimal("5"), CLOSE: Decimal("2")} or \
        all(abs(priced.spreads[k] - v) < Decimal("0.001")
            for k, v in {OPEN: 20, ELEVEN: 5, CLOSE: 2}.items())


def test_each_exit_is_charged_the_spread_of_its_own_moment(run, tmp_path) -> None:
    """The clock exits at the close's spread, a gap at the open's, an intraday leg at 11:00's."""
    args, _ = _world(tmp_path, run)
    priced, *_ = run.price_sample(args, run.read_sample(args.sample))
    expected = {ExitReason.TIME: Decimal("2"), ExitReason.END_OF_DATA: Decimal("2"),
                ExitReason.STOP_GAP: Decimal("20"), ExitReason.STOP: Decimal("5"),
                ExitReason.TARGET: Decimal("5")}
    seen = set()
    for p in priced:
        with BarStore(tmp_path / "bars.duckdb") as store:
            series = store.as_of(p.entry.instrument_id, Interval.DAY, Series.RAW, KNOWN)
        closes = {b.session_date: b for b in series.bars}
        for arm in run.ARMS:
            trade = p.trades["net"][arm]
            bar = closes[trade.exit_date]
            quoted = {ExitReason.TIME: bar.close, ExitReason.END_OF_DATA: bar.close,
                      ExitReason.STOP_GAP: bar.open, ExitReason.STOP: trade.stop_price,
                      ExitReason.TARGET: trade.entry_price + trade.initial_risk_per_share}
            if trade.exit_reason not in quoted:
                continue
            spread = p.spreads[run.EXIT_MOMENT[trade.exit_reason]]
            assert abs(spread - expected[trade.exit_reason]) < Decimal("0.001")
            assert trade.exit_price == quoted[trade.exit_reason] * (1 - spread / 10000)
            seen.add(trade.exit_reason)
    assert ExitReason.TIME in seen or ExitReason.END_OF_DATA in seen


def test_the_cost_adverse_reading_triples_only_the_close_arm(run, tmp_path) -> None:
    _args, entries = _world(tmp_path, run)
    entry = entries[0]
    session = cal.session(NYSE, entry.session_date)
    with BarStore(tmp_path / "bars.duckdb") as store:
        series = store.as_of(entry.instrument_id, Interval.DAY, Series.RAW, KNOWN)
    with MinuteStore(tmp_path / "minutes.duckdb") as minutes_store:
        minutes = minutes_store.session(entry.instrument_id, entry.session_date, KNOWN)
    with QuoteStore(tmp_path / "quotes.duckdb") as quotes_store:
        windows = {m: quotes_store.window(entry.instrument_id, entry.session_date, m, KNOWN)
                   for m in (OPEN, ELEVEN, CLOSE)}
    priced = run.price_entry(entry, series, Decimal(2), minutes, windows, session, None, Counter())
    net, adverse = priced.trades["net"], priced.trades["cost_adverse"]
    fill_c = priced.fills["C"]
    assert adverse["C"].entry_price == fill_c * (1 + priced.spreads[CLOSE] * 3 / 10000)
    assert adverse["O"].entry_price == net["O"].entry_price
    assert priced.trades["gross"]["C"].entry_price == fill_c


def test_the_date_weighted_reading_matches_when_every_date_carries_the_same_count(run, tmp_path):
    args, _entries = _world(tmp_path, run)
    payload = run.build(args)
    cell = payload["cells"]["C"]
    assert math.isclose(cell["difference"]["estimate"], cell["date_weighted"]["estimate"],
                        rel_tol=1e-9)


def test_the_diagnostics_count_every_arm_s_exits_and_spreads(run, tmp_path) -> None:
    """Section 5a promises them: each arm's exit reasons and the spread it paid to enter."""
    args, entries = _world(tmp_path, run, spread_bps=(20.0, 5.0, 2.0))
    payload = run.build(args)
    seen = payload["diagnostics"]
    assert set(seen) == set(run.ARMS)
    for arm, paid in (("O", 20.0), ("T", 5.0), ("C", 2.0)):
        assert sum(seen[arm]["exit_reasons"].values()) == len(entries)
        spread = seen[arm]["entry_half_spread_bps"]
        assert spread["entries"] == len(entries)
        assert spread["p10"] == pytest.approx(paid, abs=1e-3)
        assert spread["p90"] == pytest.approx(paid, abs=1e-3)
    assert 0 <= seen["C"]["exited_on_the_entry_session"] <= len(entries)
    json.dumps(payload, default=run._default)


def test_the_spread_summary_reads_its_percentiles(run) -> None:
    got = run._spread_summary([float(v) for v in range(20, 0, -1)])
    assert (got["p10"], got["p50"], got["p90"], got["average"]) == (3.0, 11.0, 19.0, 10.5)
    assert run._spread_summary([]) == {"entries": 0}


def test_the_report_prints_every_reading(run, tmp_path, capsys) -> None:
    args, _ = _world(tmp_path, run)
    run.report(run.build(args))
    printed = capsys.readouterr().out
    for label in ("net per dollar", "gross part", "cost-adverse", "exits at registry",
                  "stops from the decision", "date-weighted", "instrument-clustered",
                  "arm's own level", "entry half-spread bps", "same day"):
        assert label in printed
