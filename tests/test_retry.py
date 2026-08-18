"""The retry wrapper around the injected fetcher (`DR-015` §3).

Every test here injects its own `sleep`, so the suite never waits. A test that took 30 real seconds
to prove a retry happened would be deleted the first time someone was in a hurry, and CI_POLICY 4
requires the suite to stay fast and offline.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from tests.conftest import TEST_US, series_for

from swingdesk.contracts.market import Interval
from swingdesk.market_data import VendorUnavailable
from swingdesk.market_data.retry import ATTEMPTS, BUDGET_SECONDS, DELAY_SECONDS, RetryingFetcher

AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
SESSIONS = [date(2026, 1, 15)]


class Recorder:
    """A sleep that records instead of waiting."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


def _failing(times: int):
    """A fetcher that fails `times` times and then succeeds. Counts its calls."""
    state = {"calls": 0}

    def fetch(instrument, interval, knowledge_time, period=None):
        state["calls"] += 1
        if state["calls"] <= times:
            raise VendorUnavailable(f"attempt {state['calls']} refused")
        return series_for(instrument, SESSIONS)

    fetch.state = state  # type: ignore[attr-defined]
    return fetch


def _always_failing():
    return _failing(times=10_000)


def _call(fetcher):
    return fetcher(TEST_US, Interval.DAY, AS_OF, period="1y")


# ------------------------------------------------------------------ the rule DR-015 states


def test_three_attempts_thirty_seconds_apart() -> None:
    """`DR-015` §3, the whole rule: three attempts, 30 seconds apart.

    Attempts, not retries - three calls to the vendor and TWO sleeps between them. The record's
    other number, "ninety seconds", is read as the per-run ceiling rather than as a third sleep;
    `market_data/retry.py` records why, and `test_the_budget_is_the_records_own_ninety_seconds`
    pins that half.
    """
    inner = _always_failing()
    sleep = Recorder()
    fetcher = RetryingFetcher(inner, sleep=sleep)

    with pytest.raises(VendorUnavailable):
        _call(fetcher)

    assert inner.state["calls"] == ATTEMPTS == 3
    assert sleep.waits == [DELAY_SECONDS, DELAY_SECONDS], "two gaps between three attempts"


def test_a_transient_failure_is_absorbed_and_the_run_never_sees_it() -> None:
    """The failure this exists for: one bad call, then the vendor answers."""
    inner = _failing(times=1)
    sleep = Recorder()
    fetcher = RetryingFetcher(inner, sleep=sleep)

    series = _call(fetcher)

    assert series.instrument_id == TEST_US.id
    assert inner.state["calls"] == 2
    assert sleep.waits == [DELAY_SECONDS]
    assert fetcher.retries == 1
    assert fetcher.exhausted == 0, "it did not fail; nothing was exhausted"


def test_a_success_never_sleeps() -> None:
    """The normal case, and on the evidence so far the only case: 10 scheduled runs and roughly
    11,200 fetches produced zero `VendorUnavailable` in `data/daily_run.log`."""
    inner = _failing(times=0)
    sleep = Recorder()
    fetcher = RetryingFetcher(inner, sleep=sleep)

    _call(fetcher)

    assert sleep.waits == []
    assert fetcher.slept == 0.0
    assert fetcher.summary() == "", "nothing failed, so nothing is reported"


def test_the_last_attempt_is_not_followed_by_a_sleep() -> None:
    """A wait after the final attempt is a wait for a call that will never be made."""
    sleep = Recorder()
    fetcher = RetryingFetcher(_always_failing(), attempts=2, sleep=sleep)

    with pytest.raises(VendorUnavailable):
        _call(fetcher)

    assert len(sleep.waits) == 1, "two attempts, one gap"


def test_the_original_failure_is_what_reaches_the_caller() -> None:
    """The pipeline turns this into a coded `DATA` skip carrying the vendor's own text, so the last
    failure has to survive the retries rather than being replaced by a wrapper's summary."""
    fetcher = RetryingFetcher(_always_failing(), sleep=Recorder())

    with pytest.raises(VendorUnavailable, match="attempt 3 refused"):
        _call(fetcher)


def test_only_a_vendor_failure_is_retried() -> None:
    """`VendorUnavailable` is the adapter's declared "could not be reached". Anything else is a
    defect, and retrying a defect three times reports it three times slower."""
    calls = {"n": 0}

    def broken(instrument, interval, knowledge_time, period=None):
        calls["n"] += 1
        raise ValueError("a defect, not a vendor outage")

    sleep = Recorder()
    with pytest.raises(ValueError):
        _call(RetryingFetcher(broken, sleep=sleep))

    assert calls["n"] == 1
    assert sleep.waits == []


# ------------------------------------------------------------------ the ceiling DR-015 costed


def test_the_budget_is_the_records_own_ninety_seconds() -> None:
    """`DR-015` §3 costs the retry at "ninety seconds inside a run that takes about five minutes"
    and concludes "it costs nothing". That arithmetic is for ONE instrument failing once.

    The wrapper is called per instrument and the scheduled universe was 1152 members on
    2026-08-17, so an unbounded retry through a vendor outage is over nineteen hours of sleeping on
    a job that has to finish before a 19:30 second pass. The budget is what makes the record's own
    stated cost true, and it is spent across the run rather than per call.
    """
    sleep = Recorder()
    fetcher = RetryingFetcher(_always_failing(), sleep=sleep)

    for _ in range(50):  # a vendor outage: every instrument fails
        with pytest.raises(VendorUnavailable):
            _call(fetcher)

    assert sum(sleep.waits) == fetcher.slept
    assert fetcher.slept <= BUDGET_SECONDS == 90.0
    assert fetcher.exhausted == 50, "every instrument still got its refusal"


def test_once_the_budget_is_spent_later_instruments_fail_fast() -> None:
    """The point of the ceiling: the run keeps going, it just stops paying for hope."""
    inner = _always_failing()
    fetcher = RetryingFetcher(inner, sleep=Recorder())

    with pytest.raises(VendorUnavailable):
        _call(fetcher)          # 2 sleeps, 60s
    calls_after_first = inner.state["calls"]
    with pytest.raises(VendorUnavailable):
        _call(fetcher)          # 1 sleep, 90s - budget gone
    with pytest.raises(VendorUnavailable):
        _call(fetcher)          # no sleep at all

    assert calls_after_first == 3
    assert fetcher.slept == BUDGET_SECONDS
    assert fetcher.budget_spent
    assert inner.state["calls"] == 3 + 2 + 1


def test_the_budget_belongs_to_the_run_not_to_the_wrapper_type() -> None:
    """A fresh instance starts with a full budget, which is what "one per run" means."""
    first = RetryingFetcher(_always_failing(), sleep=Recorder())
    for _ in range(10):
        with pytest.raises(VendorUnavailable):
            _call(first)
    assert first.budget_spent

    second = RetryingFetcher(_always_failing(), sleep=Recorder())
    assert not second.budget_spent
    assert second.slept == 0.0


# ------------------------------------------------------------------ the measurement DR-015 §6 asks for


def test_a_run_with_failures_reports_them() -> None:
    """`DR-015` §6 wants a measured distribution of how often fetches fail and observes that nobody
    has counted one. This line, printed into `data/daily_run.log`, is where counting starts."""
    fetcher = RetryingFetcher(_always_failing(), sleep=Recorder())
    with pytest.raises(VendorUnavailable):
        _call(fetcher)

    summary = fetcher.summary()
    assert "1 instrument(s) failed every attempt" in summary
    assert "60s slept of a 90s budget" in summary
    assert "BUDGET SPENT" not in summary


def test_the_summary_says_when_the_ceiling_changed_the_behaviour() -> None:
    """A run whose budget ran out gave later instruments one attempt instead of three. The reader
    cannot tell that from the refusals alone, so the line says it."""
    fetcher = RetryingFetcher(_always_failing(), sleep=Recorder())
    for _ in range(5):
        with pytest.raises(VendorUnavailable):
            _call(fetcher)

    assert "BUDGET SPENT" in fetcher.summary()


def test_zero_attempts_is_rejected_at_construction() -> None:
    """A wrapper configured never to call the vendor would refuse every instrument while looking
    like a vendor outage."""
    with pytest.raises(ValueError, match="at least 1"):
        RetryingFetcher(_always_failing(), attempts=0)
