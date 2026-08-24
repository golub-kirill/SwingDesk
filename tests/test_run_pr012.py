"""`PR-012`'s fast path, and whether it is the rule it claims to be.

`AlwaysEligible` makes every admitted name a candidate on every session, so the study scores about a
thousand names across thousands of sessions. `ranking.ByMarketPathStrength` is O(lookback) per score
- hundreds of millions of operations - so `run_pr012` precomputes with prefix sums.

**An optimisation of a decision rule is a second implementation of it** unless something binds them
together. The runner's `--verify-sample` does that at run time on a seeded sample; these tests do it
offline, exhaustively, on shapes chosen to break a prefix-sum implementation:

  - a name that did not trade on sessions the benchmark did, and the reverse;
  - a window that starts exactly at the first bar;
  - a benchmark that moves and one that does not.

The equivalence is the point. If these ever disagree, the study is measuring something nobody
registered.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from tests.conftest import KNOWLEDGE_TIME

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.validation.backtest.book import Candidate
from swingdesk.validation.backtest.ranking import _beat_share

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import run_pr012  # noqa: E402 - the path insert above is what makes this importable

START = date(2025, 1, 6)


def _series(instrument_id: str, closes: list[str | None]) -> BarSeries:
    """`None` means the instrument had no bar for that session at all."""
    bars = []
    for offset, close in enumerate(closes):
        if close is None:
            continue
        session = START + timedelta(days=offset)
        value = Decimal(close)
        bars.append(
            Bar(
                instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session, open=value, high=value + 1, low=value - 1, close=value,
                volume=1_000_000, knowledge_time=KNOWLEDGE_TIME,
            )
        )
    return BarSeries(
        instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
        knowledge_time=KNOWLEDGE_TIME, bars=tuple(bars),
    )


def _agrees(closes: list[str | None], benchmark_closes: list[str | None], lookback: int) -> None:
    """The prefix-sum table must equal the reference at every session both can score."""
    series = _series("AAA", closes)
    benchmark = _series("SPY", benchmark_closes)
    daily = run_pr012._daily_returns_by_session(benchmark)
    fast = run_pr012._beat_prefix(series, daily, lookback)

    for index, bar in enumerate(series.bars):
        expected = _beat_share(series, index, lookback, daily)
        actual = fast.get(bar.session_date)
        assert actual == expected, (
            f"session {bar.session_date}: fast {actual} vs reference {expected}"
        )


def test_the_fast_path_equals_the_reference_on_a_plain_series() -> None:
    _agrees(["100", "101", "102", "103", "104", "105"],
            ["100", "100", "100", "100", "100", "100"], lookback=3)


def test_they_agree_when_the_NAME_missed_sessions_the_benchmark_traded() -> None:
    """A halt shortens neither the window nor the claim. A prefix sum indexed by position rather
    than by session would silently compare the wrong days."""
    _agrees(["100", None, "102", "103", None, "105", "106"],
            ["100", "101", "102", "103", "104", "105", "106"], lookback=3)


def test_they_agree_when_the_BENCHMARK_missed_sessions_the_name_traded() -> None:
    """The other direction, and the one a naive implementation gets wrong: a session with no
    benchmark return is not a session the name lost."""
    _agrees(["100", "101", "102", "103", "104", "105", "106"],
            ["100", None, "102", None, "104", "105", "106"], lookback=3)


def test_they_agree_when_the_benchmark_moves() -> None:
    _agrees(["100", "99", "104", "103", "110", "108", "115"],
            ["100", "102", "101", "105", "104", "109", "107"], lookback=4)


def test_they_agree_at_the_shortest_possible_window() -> None:
    """A lookback of 1 is one comparison, and it is where an off-by-one hides."""
    _agrees(["100", "110", "105", "120"], ["100", "101", "108", "109"], lookback=1)


def test_the_fast_path_emits_nothing_before_the_window_is_full() -> None:
    """Same contract as the reference: no window, no score - never a partial one."""
    series = _series("AAA", ["100", "101", "102", "103"])
    benchmark = _series("SPY", ["100", "100", "100", "100"])
    fast = run_pr012._beat_prefix(series, run_pr012._daily_returns_by_session(benchmark), 3)
    assert START not in fast and START + timedelta(days=1) not in fast
    assert START + timedelta(days=3) in fast


# ------------------------------------------------------------------------ the bootstrap interval


def test_the_bootstrap_is_seeded_and_reproducible() -> None:
    """A study that could not reproduce its own interval could not be checked by anyone."""
    values = [Decimal(v) for v in ("1", "-1", "2", "-2", "0.5", "3", "-0.25", "1.5")]
    first = run_pr012.bootstrap_interval(values, seed=7, resamples=500)
    second = run_pr012.bootstrap_interval(values, seed=7, resamples=500)
    third = run_pr012.bootstrap_interval(values, seed=8, resamples=500)
    assert first == second
    assert first != third, "a different seed must give a different resampling"


def test_the_interval_brackets_the_mean_and_the_mean_is_exact() -> None:
    values = [Decimal(v) for v in ("1", "2", "3", "4", "5")]
    mean, low, high = run_pr012.bootstrap_interval(values, seed=1, resamples=2000)
    assert mean == 3.0, "the point estimate is arithmetic, not a resample"
    assert low < mean < high


def test_a_constant_series_has_a_zero_width_interval() -> None:
    """Every resample of a constant is the same constant. Anything else means the resampler is not
    resampling."""
    values = [Decimal("0.25")] * 20
    mean, low, high = run_pr012.bootstrap_interval(values, seed=3, resamples=500)
    assert mean == low == high == 0.25


def test_too_few_values_returns_None_rather_than_a_confident_interval() -> None:
    assert run_pr012.bootstrap_interval([], seed=1, resamples=10) is None
    assert run_pr012.bootstrap_interval([Decimal(1)], seed=1, resamples=10) is None


# ------------------------------------------------------------------------- the precomputed ranking


def _candidate(instrument_id: str) -> Candidate:
    return Candidate(
        instrument_id=instrument_id, session_date=START, index=0, close=Decimal(100),
        entry_price=Decimal(100), stop=Decimal(96), risk_per_share=Decimal(4), shares=250,
    )


def test_the_precomputed_ranking_orders_by_score_and_breaks_ties_on_id() -> None:
    ranking = run_pr012.Precomputed({
        ("AAA", START): Decimal(1), ("BBB", START): Decimal(3), ("CCC", START): Decimal(3),
    })
    ordered = ranking([_candidate(n) for n in ("CCC", "AAA", "BBB")])
    assert [c.instrument_id for c in ordered] == ["BBB", "CCC", "AAA"]


def test_a_candidate_with_no_precomputed_score_sorts_LAST_rather_than_vanishing() -> None:
    """Same rule the reference implementations keep: a dropped candidate is an unrecorded
    exclusion, and an unrecorded exclusion is a survivorship filter on the signal set."""
    ranking = run_pr012.Precomputed({("AAA", START): Decimal(1)})
    ordered = ranking([_candidate("AAA"), _candidate("ZZZ")])
    assert [c.instrument_id for c in ordered] == ["AAA", "ZZZ"]
    assert len(ordered) == 2


def test_the_study_constants_match_what_the_pre_registration_declared() -> None:
    """`PR-012` §5 pins these before the run, and a constant that drifts makes the runner a
    different study under the same id. The same guard `run_pr005_replay.py` applies to `PR-005`."""
    assert run_pr012.LOOKBACK == 126
    assert run_pr012.BENCHMARK == "SPY"
    assert run_pr012.MAX_POSITIONS == 4
    assert run_pr012.MAX_OPEN_RISK == Decimal(4)
    assert run_pr012.ATR_STOP_MULTIPLE == Decimal("2.0")
    assert run_pr012.MAX_HOLDING_BARS == 20
    assert run_pr012.MIN_TRADES_PER_ARM == 200
    assert run_pr012.HOLDOUT_FRACTION == Decimal("0.30")
    assert run_pr012.MIN_NAMES_FOR_WINDOW_START == 200
