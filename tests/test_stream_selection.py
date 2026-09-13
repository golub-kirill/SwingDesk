"""The streamed selection must equal the in-memory one, date by date, or it is a second screen.

`tools/stream_selection.py` exists to stop a study holding the whole universe at once. The saving is
worthless if it selects different names, and the ways it could are all quiet:

* **ties.** `_beat_share` is a ratio of two small integers, so equal scores are common; the order is
  total only because `_ordered` breaks ties on instrument id. The fixture is built to produce them,
  and a test checks that it did.
* **the pool size.** The decile is `int(len(pool) * decile)` over every ADMITTED candidate,
  unscored ones included.
* **admission.** Illiquid names and a name whose history starts late are in the fixture, so the
  pool is not simply "everyone".
"""

from __future__ import annotations

import importlib.util
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series  # noqa: E402

KNOWN = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
SESSIONS = 420
LOOKBACK = 126
LIQUID = 120
ILLIQUID = 10


@pytest.fixture(scope="module")
def stream():
    spec = importlib.util.spec_from_file_location("_stream_selection",
                                                  REPO / "tools" / "stream_selection.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _days(n: int) -> list[date]:
    out, d = [], date(2020, 1, 6)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _series(name: str, days: list[date], rng: random.Random, volume: int) -> BarSeries:
    price = rng.uniform(10, 100)
    vol = rng.uniform(0.01, 0.03)
    bars = []
    for day in days:
        open_ = price * (1 + rng.gauss(0, vol / 3))
        close = open_ * (1 + rng.gauss(0, vol))
        q = Decimal("0.01")
        bars.append(Bar(
            instrument_id=name, interval=Interval.DAY, series=Series.RAW,
            event_time=datetime.combine(day, time(14, 30), tzinfo=UTC), session_date=day,
            open=Decimal(str(open_)).quantize(q),
            high=Decimal(str(max(open_, close) * (1 + abs(rng.gauss(0, vol / 2))))).quantize(q),
            low=Decimal(str(min(open_, close) * (1 - abs(rng.gauss(0, vol / 2))))).quantize(q),
            close=Decimal(str(close)).quantize(q), volume=volume, knowledge_time=KNOWN,
        ))
        price = close
    return BarSeries(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=KNOWN, bars=tuple(bars))


@pytest.fixture(scope="module")
def universe():
    rng = random.Random(20260912)
    days = _days(SESSIONS)
    series = {"SPY": _series("SPY", days, rng, 50_000_000)}
    for i in range(LIQUID):
        series[f"L{i:03d}"] = _series(f"L{i:03d}", days, rng, 1_000_000)
    for i in range(ILLIQUID):
        series[f"X{i:03d}"] = _series(f"X{i:03d}", days, rng, 1_000)
    # Starts late: short of min_history on the early formation dates, admitted on the late ones.
    series["LATE"] = _series("LATE", days[100:], rng, 1_000_000)
    formations = days[260::20]
    return series, formations


def _reference(series, formations):
    """The in-memory loop, as `run_pr016`..`run_pr019` run it, through the live ranker."""
    from measure_momentum_horizon import RULE
    from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
    from run_pr014 import DECILE, Candidate, select
    from swingdesk.decision_logic.ranking import ByMarketPathStrength

    benchmark = series["SPY"]
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)} for n, s in series.items()}
    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series.items()}
    selected, everything, thin = {}, {}, 0
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            thin += 1
            continue
        for candidate in pool:
            everything.setdefault(candidate.instrument_id, []).append(session)
        ranker = ByMarketPathStrength(series=series, benchmark=benchmark, lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top:
            selected.setdefault(name, []).append(session)
    return selected, everything, thin


def _streamed(stream, series, formations):
    from run_pr014 import DECILE
    from swingdesk.decision_logic.ranking import daily_returns

    benchmark_daily = daily_returns(series["SPY"])
    scores = {}
    for name, s in series.items():
        got = stream.score_instrument(s, formations, benchmark_daily, LOOKBACK)
        if got:
            scores[name] = got
    return stream.select_streamed(scores, formations, DECILE), scores


def test_the_streamed_selection_equals_the_in_memory_one(stream, universe):
    series, formations = universe
    selected, everything, thin = _reference(series, formations)
    got, _ = _streamed(stream, series, formations)
    assert got.selected == selected
    assert got.everything == everything
    assert got.thin == thin
    assert selected, "the fixture must select something or the equality proves nothing"


def test_the_fixture_actually_produces_ties(stream, universe):
    """Equality on a fixture without ties would not have tested the tie-break at all."""
    series, formations = universe
    _, scores = _streamed(stream, series, formations)
    session = formations[-1]
    values = [s[session] for s in scores.values() if session in s]
    assert len(values) > len(set(values))


def test_illiquid_names_are_never_in_a_pool(stream, universe):
    series, formations = universe
    got, _ = _streamed(stream, series, formations)
    assert not any(name.startswith("X") for name in got.everything)


def test_a_late_starter_enters_only_once_it_has_the_history(stream, universe):
    series, formations = universe
    got, _ = _streamed(stream, series, formations)
    entered = got.everything.get("LATE", [])
    assert entered, "LATE should be admitted on the later formation dates"
    assert formations[0] not in entered


def test_a_name_that_cannot_be_scored_is_kept_as_UNSCORED_not_dropped(stream, universe):
    """With no benchmark returns nothing can be compared, so every admitted date is UNSCORED -
    and still present, because the decile is sized over every admitted candidate."""
    from swingdesk.decision_logic.ranking import UNSCORED

    series, formations = universe
    got = stream.score_instrument(series["L000"], formations, {}, LOOKBACK)
    assert got, "L000 is liquid and should be admitted"
    assert set(got.values()) == {UNSCORED}


def test_pass_a_against_a_store_keeps_one_series_at_a_time_and_scores_the_same(stream, universe,
                                                                            tmp_path):
    from swingdesk.decision_logic.ranking import daily_returns
    from swingdesk.market_data import BarStore

    series, formations = universe
    benchmark_daily = daily_returns(series["SPY"])
    with BarStore(tmp_path / "bars.duckdb") as store:
        for name in ("L000", "L001", "LATE", "X000"):
            store.write(series[name].bars, KNOWN)
        got = stream.scores_from_store(store, ["L000", "L001", "LATE", "X000", "ABSENT"], KNOWN,
                                       formations, benchmark_daily, LOOKBACK,
                                       min_bars=len(series["L000"].bars))
    # LATE is shorter than the length filter, ABSENT is not in the store, and X000 is long enough
    # but never admitted - so it has no dates, and a name with no dates is not an entry at all.
    assert set(got) == {"L000", "L001"}
    assert got["L000"] == stream.score_instrument(series["L000"], formations, benchmark_daily,
                                                  LOOKBACK)


# --- pass B on its own ---------------------------------------------------------------------------


def test_an_unscored_candidate_still_counts_toward_the_decile(stream):
    from swingdesk.decision_logic.ranking import UNSCORED

    session = date(2021, 1, 4)
    scores = {f"N{i}": {session: Decimal(i) / 10} for i in range(8)}
    scores |= {"U1": {session: UNSCORED}, "U2": {session: UNSCORED}}
    got = stream.select_streamed(scores, [session], Decimal("0.2"), min_names=5)
    # Ten in the pool, so two selected - not 0.2 x 8, which would round to one.
    assert got.selected == {"N7": [session], "N6": [session]}
    assert len(got.everything) == 10


def test_ties_break_on_instrument_id(stream):
    session = date(2021, 1, 4)
    scores = {name: {session: Decimal("0.5")} for name in ("C", "A", "B", "D", "E")}
    got = stream.select_streamed(scores, [session], Decimal("0.4"), min_names=1)
    assert set(got.selected) == {"A", "B"}


def test_a_thin_date_records_nothing(stream):
    session = date(2021, 1, 4)
    scores = {f"N{i}": {session: Decimal(i)} for i in range(3)}
    got = stream.select_streamed(scores, [session], Decimal("0.5"), min_names=4)
    assert got.thin == 1
    assert got.selected == {} and got.everything == {}


def test_a_pool_of_exactly_min_names_is_not_thin(stream):
    """`MIN_NAMES_PER_DATE` is a minimum, so a pool that meets it exactly is read."""
    session = date(2021, 1, 4)
    scores = {f"N{i}": {session: Decimal(i)} for i in range(4)}
    got = stream.select_streamed(scores, [session], Decimal("0.5"), min_names=4)
    assert got.thin == 0
    assert len(got.everything) == 4


def test_the_decile_size_truncates_and_never_rounds(stream):
    """`select` takes `int(len * decile)`: seven names at one half is three, not four."""
    session = date(2021, 1, 4)
    scores = {f"N{i}": {session: Decimal(i)} for i in range(7)}
    got = stream.select_streamed(scores, [session], Decimal("0.5"), min_names=1)
    assert set(got.selected) == {"N6", "N5", "N4"}


def test_top_k_is_the_head_of_each_dates_order_and_off_by_default(stream):
    session = date(2021, 1, 4)
    scores = {f"N{i}": {session: Decimal(i)} for i in range(10)}
    got = stream.select_streamed(scores, [session], Decimal("0.5"), min_names=1, top_k=2)
    assert set(got.selected) == {"N9", "N8", "N7", "N6", "N5"}
    assert got.top == {"N9": [session], "N8": [session]}
    assert stream.select_streamed(scores, [session], Decimal("0.5"), min_names=1).top == {}


def test_the_streamed_top_four_equals_the_in_memory_prefix(stream, universe):
    """`PR-016`'s `ranked_top4` diagnostic is `top[:MAX_CONCURRENT]` of the live ranker's order."""
    from measure_momentum_horizon import RULE
    from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
    from run_pr014 import DECILE, Candidate, select
    from swingdesk.decision_logic.ranking import ByMarketPathStrength

    series, formations = universe
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)} for n, s in series.items()}
    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series.items()}
    reference: dict[str, list[date]] = {}
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            continue
        ranker = ByMarketPathStrength(series=series, benchmark=series["SPY"], lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top[:4]:
            reference.setdefault(name, []).append(session)
    _, scores = _streamed(stream, series, formations)
    assert reference, "the fixture must select something or the equality proves nothing"
    assert stream.select_streamed(scores, formations, DECILE, top_k=4).top == reference


def test_a_decile_below_one_name_selects_nobody(stream):
    session = date(2021, 1, 4)
    scores = {f"N{i}": {session: Decimal(i)} for i in range(5)}
    got = stream.select_streamed(scores, [session], Decimal("0.1"), min_names=1)
    assert got.selected == {}
    assert len(got.everything) == 5
