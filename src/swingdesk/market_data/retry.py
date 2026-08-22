"""Retrying a failed fetch, and the ceiling that stops a retry from eating the evening (`DR-015`).

`DR-015` §3: **three attempts, 30 seconds apart**, and the wrapper goes around the FETCHER rather
than inside `pipeline.py`. `run()` takes the fetcher as an injected argument, so this needs no
change to a frozen file and the pipeline stays pure - nothing sleeps inside the decision path.

**Why there is a per-run budget, which `DR-015` does not name in so many words.** The record states
the cost as *"ninety seconds inside a run that takes about five minutes"* and concludes *"it costs
nothing"*. That arithmetic holds for ONE instrument failing once. The wrapper is called per
instrument, and the scheduled run's universe was **1152 members** on 2026-08-17 - so the failure
this retry actually exists for, a vendor outage, is precisely the case where every call fails and
the sleeping multiplies. Unbounded, three attempts 30 seconds apart across 1152 members is over
nineteen hours of sleeping, on a job that must finish before a 19:30 second pass.

So the budget is not an added policy; it is what makes the record's own stated cost true. It is
spent across the whole run, not per instrument: the first failures get their full retries, and once
90 seconds of sleeping is gone the rest of the run fails fast. A vendor outage therefore costs the
run ninety seconds and a page of coded `DATA` refusals, which is the outcome `FAIL_CLOSED_POLICY`
row 1 describes anyway.

**`ATTEMPTS` and `BUDGET_SECONDS` come from the two numbers `DR-015` §3 states, which do not quite
agree.** "Three attempts, 30 seconds apart" is two sleeps and 60 seconds; "ninety seconds" is three
sleeps. The phrase stated twice - in the record and again in its handoff - is the attempt count, so
that is the per-instrument rule, and ninety seconds is read as what it says it is: the ceiling on a
run. Both numbers survive, neither is invented, and the discrepancy is recorded here rather than
silently resolved.

**Measured before building, and it is the reason none of this is hot-path.** Ten scheduled runs
(2026-08-09 to 08-17) across roughly 11,200 instrument-fetches produced **zero** `VendorUnavailable`
in `data/daily_run.log` - no "no data returned", no "no usable rows after validation". The retry is
insurance against a failure that has not yet been observed here, which is exactly why its worst case
had to be bounded rather than estimated from the observed one. `DR-015` §6 asks for this
distribution; `RetryingFetcher.retries` and `.exhausted` are what let a run report it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from swingdesk.contracts.market import BarSeries, Interval
from swingdesk.contracts.reference import Instrument
from swingdesk.market_data.vendor_yahoo import VendorUnavailable

#: `DR-015` §3. Attempts, not retries: three calls to the vendor, two sleeps between them.
ATTEMPTS = 3

#: `DR-015` §3, "30 seconds apart".
DELAY_SECONDS = 30.0

#: `DR-015` §3, "ninety seconds inside a run that takes about five minutes" - read as the ceiling on
#: a RUN, for the reason in the module docstring. Sleeping stops here; fetching does not.
BUDGET_SECONDS = 90.0


class Fetcher(Protocol):
    """What a bar source has to look like. Structurally identical to `pipeline.Fetcher`.

    Declared here rather than imported because `application` sits ABOVE `market_data` in the layer
    contract (gate 6), so importing the pipeline's copy would invert the dependency law. Protocols
    are structural, so the two are checked against each other for real at the injection site in
    `presentation.cli` - if they drift apart, mypy fails there, which is where it matters.
    """

    def __call__(
        self,
        instrument: Instrument,
        interval: Interval,
        knowledge_time: datetime,
        period: str | None = None,
    ) -> BarSeries: ...


class RetryingFetcher:
    """A fetcher that retries a `VendorUnavailable`, within a budget shared by the whole run.

    Stateful on purpose, and the state is the point: one instance per run means the budget is a
    property of the RUN rather than of a call, and the counters it accumulates are the measurement
    `DR-015` §6 asks for. A caller that wants the old behaviour passes the bare fetcher.

    Only `VendorUnavailable` is retried. It is the vendor adapter's declared way of saying "could
    not be reached, or returned nothing usable" - the transient failure this covers. Anything else
    is a defect, and retrying a defect three times just reports it three times slower.
    """

    def __init__(
        self,
        inner: Fetcher,
        *,
        attempts: int = ATTEMPTS,
        delay: float = DELAY_SECONDS,
        budget: float = BUDGET_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError(f"attempts must be at least 1, got {attempts}")
        self._inner = inner
        self._attempts = attempts
        self._delay = delay
        self._budget = budget
        # Injected so the suite never actually sleeps. A test that waits 30 real seconds to prove a
        # retry happened is a test that gets deleted the first time someone is in a hurry
        # (CI_POLICY 4 requires the suite to stay fast and offline).
        self._sleep = sleep
        self.slept = 0.0
        """Seconds spent waiting, this run. Never exceeds `budget`."""
        self.retries = 0
        """Fetches that failed and were tried again."""
        self.exhausted = 0
        """Instruments that failed every attempt they were given, and raised."""

    @property
    def budget_spent(self) -> bool:
        """True once another full delay would take the run past its ceiling."""
        return self.slept + self._delay > self._budget

    def __call__(
        self,
        instrument: Instrument,
        interval: Interval,
        knowledge_time: datetime,
        period: str | None = None,
    ) -> BarSeries:
        failure: VendorUnavailable | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                return self._inner(instrument, interval, knowledge_time, period=period)
            except VendorUnavailable as unavailable:
                failure = unavailable
                # No sleep after the last attempt: the run would wait for a call it will not make.
                if attempt == self._attempts or self.budget_spent:
                    break
                self._sleep(self._delay)
                self.slept += self._delay
                self.retries += 1

        self.exhausted += 1
        # `failure` is set on every path that reaches here - the loop runs at least once and only
        # leaves early through the `except`. Asserted rather than assumed so a future edit to the
        # loop cannot turn this into a bare `raise None`.
        assert failure is not None
        raise failure

    def summary(self) -> str:
        """One line for the run log, or an empty string when nothing failed.

        Empty rather than "0 retries" deliberately: on the evidence so far this is the normal case,
        and a line printed on all 1152 quiet instruments is a line nobody reads on the day it says
        something. `DR-015` §6 wants the distribution measured, and a message that only appears when
        there is something to measure is what gets noticed in `data/daily_run.log`.
        """
        if not self.retries and not self.exhausted:
            return ""
        return (
            f"vendor retries  {self.retries} retry/retries, {self.exhausted} instrument(s) failed "
            f"every attempt, {self.slept:.0f}s slept of a {self._budget:.0f}s budget"
            + ("  BUDGET SPENT - later failures got one attempt only" if self.budget_spent else "")
        )
