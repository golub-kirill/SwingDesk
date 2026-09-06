"""The RS line inside the daily run (`M31-T0464`, `CARD-001`'s measure, `DR-024`).

`tests/test_relative_strength.py` covers the component: the ratio, the rebasing, the missing
denominator. This file covers the thing that made it `active` — that the run computes it, reports
it, replays it, and **cannot lose a decision to it**.

The last of those is the one worth having tests for. RS selects nothing today: `rs.benchmark_form`,
`rs.lookback`, `rs.ranking_method` and `screen.relative_strength_rule` are all unset and `CARD-001`
is blocked on them. So every failure mode of the benchmark has to cost an observation and nothing
else, and the natural bug is the opposite.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tests.conftest import TEST_US, series_for

from swingdesk.application.pipeline import run
from swingdesk.application.universe import Membership, UniverseSelection
from swingdesk.contracts.reference import Exchange, Instrument
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import BarStore, VendorUnavailable
from swingdesk.platform.clock import FixedClock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data.universe import LiquidityRule

MODE = RunMode.LIVE_AS_OF
AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)

BENCHMARK = Instrument(id="SPY", ticker="SPY", exchange=Exchange.NYSE, currency="USD")
OTHER = Instrument(id="TEST.3", ticker="TEST3", exchange=Exchange.NYSE, currency="USD")


def _sessions() -> list[date]:
    return [s.session_date for s in cal.sessions(Exchange.NYSE, date(2025, 1, 1), date(2026, 1, 15))]


@pytest.fixture
def stores(tmp_path):
    with BarStore(tmp_path / "bars.duckdb") as store, Journal(tmp_path / "journal.duckdb") as journal:
        yield store, journal


@pytest.fixture
def registry_with_benchmark(registry) -> ParameterRegistry:
    """The slice's registry plus `rs.benchmark`, which the real one has and the fixture did not."""
    entries = dict(registry._entries)
    entries["rs.benchmark"] = {"id": "rs.benchmark", "value": "SPY", "provenance": "assumed:DR-018"}
    return ParameterRegistry(entries)


def _universe(instruments) -> UniverseSelection:
    return UniverseSelection(
        as_of=AS_OF,
        rule=LiquidityRule(
            min_price=Decimal("5.00"), min_adtv=Decimal("5000000"),
            adtv_window=20, min_history=250, adtv_lag=0,
        ),
        parameters=(), directory_pull=AS_OF,
        eligible=len(instruments), measured=len(instruments),
        members=tuple(
            Membership(instrument=i, close=Decimal("100"), adtv=Decimal("10000000"), bars=300)
            for i in instruments
        ),
    )


def _counting_fetcher(sessions_by_instrument, counter: dict[str, int]):
    """A fetcher that records how many times each instrument was asked for."""

    def _fetch(instrument, interval, knowledge_time, period=None):
        counter[instrument.id] = counter.get(instrument.id, 0) + 1
        sessions = sessions_by_instrument.get(instrument.id, [])
        if not sessions:
            raise VendorUnavailable(f"no fixture for {instrument.id}")
        return series_for(instrument, sessions)

    return _fetch


# ------------------------------------------------------------------ one benchmark, fetched once

def test_the_benchmark_is_fetched_once_for_the_whole_cross_section(
    stores, registry_with_benchmark
) -> None:
    """Not once per candidate, and the reason is correctness rather than cost.

    RS is a comparison against a common denominator. Fetched inside the loop, names sorted before
    `SPY` would be measured against yesterday's benchmark and names after it against today's - a
    point-in-time split decided by alphabetical order. One fetch is what makes the cross-section a
    cross-section.
    """
    store, journal = stores
    sessions = _sessions()
    counter: dict[str, int] = {}
    fetcher = _counting_fetcher(
        {TEST_US.id: sessions, OTHER.id: sessions, BENCHMARK.id: sessions}, counter
    )

    result = run([], FixedClock(AS_OF), registry_with_benchmark, store, journal, mode=MODE,
                 fetcher=fetcher, universe=_universe([TEST_US, OTHER]))

    assert counter[BENCHMARK.id] == 1, counter
    assert counter[TEST_US.id] == 1 and counter[OTHER.id] == 1
    assert result.benchmark is not None and result.benchmark.is_available
    assert [o.relative_strength is not None for o in result.outcomes] == [True, True]


def test_every_candidate_is_measured_against_the_same_series(
    stores, registry_with_benchmark
) -> None:
    """Two candidates, one denominator. A run that rebuilt the benchmark per name could disagree
    with itself inside one cross-section and nothing would print differently."""
    store, journal = stores
    sessions = _sessions()
    counter: dict[str, int] = {}
    fetcher = _counting_fetcher(
        {TEST_US.id: sessions, OTHER.id: sessions, BENCHMARK.id: sessions}, counter
    )

    result = run([], FixedClock(AS_OF), registry_with_benchmark, store, journal, mode=MODE,
                 fetcher=fetcher, universe=_universe([TEST_US, OTHER]))

    lines = [o.relative_strength for o in result.outcomes]
    assert all(line is not None for line in lines)
    # The component rebases to 1.0 at the first shared session, so identical fixture paths give
    # identical lines. What is asserted is that both were measured over the SAME session set.
    spans = {(line.observations[0].event_time, line.observations[-1].event_time) for line in lines}
    assert len(spans) == 1, spans


# ------------------------------------------------- the measure can never cost a candidate anything

def test_an_unset_benchmark_leaves_every_decision_untouched(stores, registry) -> None:
    """`rs.benchmark` unset is the shipped state of nothing - but the run must not notice.

    The other run-level reads refuse: an unset stop multiple or freshness window makes a DECISION
    unsafe, so `_exit_policy` and `_freshness_window` return a `Refusal`. This one must not, because
    the RS line decides nothing. The comparison is against the same run with the benchmark present.
    """
    store, journal = stores
    sessions = _sessions()
    counter: dict[str, int] = {}
    fetcher = _counting_fetcher({TEST_US.id: sessions, BENCHMARK.id: sessions}, counter)

    without = run([], FixedClock(AS_OF), registry, store, journal, mode=MODE,
                  fetcher=fetcher, universe=_universe([TEST_US]))

    assert without.benchmark is not None
    assert not without.benchmark.is_available
    assert without.outcomes[0].relative_strength is None
    assert without.outcomes[0].decision is not None
    assert without.outcomes[0].decision.decision == "Watch", "the decision survives an absent RS line"


def test_a_benchmark_absent_from_the_registry_reports_rather_than_raising(
    stores, registry
) -> None:
    """`UnknownParameter` means code and registry disagree, which gates 1 and 28 make impossible in
    a shipped tree. The proportionate response HERE is still not to kill the run over a measure that
    decides nothing - it is to say so where the owner reads it."""
    store, journal = stores
    sessions = _sessions()
    counter: dict[str, int] = {}

    result = run([], FixedClock(AS_OF), registry, store, journal, mode=MODE,
                 fetcher=_counting_fetcher({TEST_US.id: sessions}, counter),
                 universe=_universe([TEST_US]))

    assert result.benchmark is not None
    assert result.benchmark.unavailable is not None
    assert "code and registry disagree" in result.benchmark.unavailable
    assert result.outcomes[0].decision is not None, "the run still decided"


def test_a_vendor_failure_falls_back_to_the_stored_benchmark_and_says_so(
    stores, registry_with_benchmark
) -> None:
    """A stale denominator is a real benchmark that is not today's, and both halves get printed.

    Refusing to report an RS line over a vendor blip would lose the measure for a reason that has
    nothing to do with it; reporting it silently would hide that it is stale.
    """
    store, journal = stores
    sessions = _sessions()
    store.write(series_for(BENCHMARK, sessions).bars, AS_OF)

    def _fetch(instrument, interval, knowledge_time, period=None):
        if instrument.id == BENCHMARK.id:
            raise VendorUnavailable("vendor down")
        return series_for(instrument, sessions)

    result = run([], FixedClock(AS_OF), registry_with_benchmark, store, journal, mode=MODE,
                 fetcher=_fetch, universe=_universe([TEST_US]))

    benchmark = result.benchmark
    assert benchmark is not None
    assert benchmark.is_available, "the stored series is still a benchmark"
    assert benchmark.unavailable is not None
    assert "not refreshed this run" in benchmark.unavailable
    assert result.outcomes[0].relative_strength is not None


# ------------------------------------------------------------------ the replay gate can see it

def test_the_rs_line_is_in_the_output_hash(stores, registry_with_benchmark) -> None:
    """A number the run computes and PRINTS, left out of the payload, is one gate 9 cannot see move.

    `_output_hash`'s docstring records four measured cases of exactly that - halved share counts,
    stops moved 40%, a whole open position - all hashing identically. This asserts the RS line is
    not the fifth.
    """
    store, journal = stores
    sessions = _sessions()

    def _fetch_against(benchmark_sessions):
        def _fetch(instrument, interval, knowledge_time, period=None):
            if instrument.id == BENCHMARK.id:
                return series_for(BENCHMARK, benchmark_sessions)
            return series_for(instrument, sessions)

        return _fetch

    with_benchmark = run([], FixedClock(AS_OF), registry_with_benchmark, store, journal, mode=MODE,
                         fetcher=_fetch_against(sessions), universe=_universe([TEST_US]))

    # The same run with no benchmark at all.
    entries = dict(registry_with_benchmark._entries)
    entries["rs.benchmark"] = {"id": "rs.benchmark", "value": None}
    without = run([], FixedClock(AS_OF), ParameterRegistry(entries), store, journal, mode=MODE,
                  fetcher=_fetch_against(sessions), universe=_universe([TEST_US]))

    assert with_benchmark.outcomes[0].decision is not None
    assert without.outcomes[0].decision is not None

    # **The decision USED to be the control here, and this line is the inversion.** Until
    # `DR-030` (2026-09-01) the RS line was computed, printed and read by nothing that decided -
    # `DR-024` says so in as many words - so removing the benchmark left the decision untouched
    # and only the hash moved. `DR-018` predicted the end of that state precisely: the benchmark
    # is "decorative until the FORM makes it otherwise", and the form chosen is the PATH form,
    # which compares session by session and cannot be computed without a benchmark series.
    #
    # So now: with a benchmark the cross-section ranks and the top decile becomes `Trade`; without
    # one the screen cannot score and every survivor stays `Watch` naming `rs.benchmark`. That is
    # the parameter becoming load-bearing, asserted rather than described.
    assert with_benchmark.outcomes[0].decision.decision == "Trade"
    assert without.outcomes[0].decision.decision == "Watch"
    assert without.outcomes[0].decision.parameter_id == "rs.benchmark"
    assert with_benchmark.manifest.output_hash != without.manifest.output_hash


# ------------------------------------------------------------------ what the owner is shown

def test_the_report_shows_the_validation_status_and_derives_what_the_measure_is_for(
    stores, registry_with_benchmark
) -> None:
    """`COMPONENT_REGISTRY_SPEC` §3: an ACTIVE component displays its validation status wherever its
    output appears. That status line is the condition this component was activated under.

    The second half is the other direction, and **the previous version of this test was the reason
    the report lied for five days.** It asserted the literal string *"rs.benchmark_form is unset"*,
    which was true when written and was ratified false by `DR-030` on 2026-09-01. The suite then
    held the stale sentence in place: on 2026-09-06 a live report printed *"CARD-001 is blocked"*
    beside 392 Trade decisions ranked by that very measure, 3,958 times in one file, and every test
    passed.

    So the assertion is now about the DERIVATION, not the sentence. `DR-018` §1's warning - ranking
    by this value is identical to ranking by raw return, Spearman 1.000000, so read it and do not
    sort by it - is what a run WITH a ranking must say. What a run WITHOUT one says is tested
    separately, because those are different claims and only one of them can be true per run.
    """
    from swingdesk.presentation.report import render

    store, journal = stores
    sessions = _sessions()

    def _fetch(instrument, interval, knowledge_time, period=None):
        return series_for(instrument, sessions)

    result = run([], FixedClock(AS_OF), registry_with_benchmark, store, journal, mode=MODE,
                 fetcher=_fetch, universe=_universe([TEST_US]))
    text = render(result)

    assert "M31-T0464-v5.0" in text
    assert "RS vs benchmark" in text
    assert "Not Applicable" in text
    assert "BENCHMARK (rs.benchmark, DR-018)" in text

    # Whichever branch this run took, the report must not claim the opposite of what it did.
    if result.selection is None:
        assert "selects nothing" in text
        assert "not the sort key" not in text
    else:
        assert "not the sort key" in text
        assert "Spearman 1.000000" in text
        assert "selects nothing" not in text
        assert "is unset" not in text, "a ratified parameter must never be reported as unset"
        assert "CARD-001 is blocked" not in text


def test_an_explicit_instrument_list_still_gets_the_measure(
    stores, registry_with_benchmark
) -> None:
    """The RS line belongs to the CANDIDATE, not to how the candidate was chosen.

    The first version of this test asserted the opposite - that a run without a universe prints no
    benchmark block - because `RunResult.benchmark`'s docstring said so. The code always looked, and
    the code was right: `scan AAPL` wanting the measure is the same wish as the scheduled run
    wanting it, and a hand-typed list is the case where someone is looking hardest at one name. The
    docstring was corrected to match rather than the behaviour narrowed to match the docstring.
    """
    from swingdesk.presentation.report import render

    store, journal = stores
    sessions = _sessions()
    store.write(series_for(TEST_US, sessions).bars, AS_OF)

    result = run([TEST_US], FixedClock(AS_OF), registry_with_benchmark, store, journal, mode=MODE,
                 fetcher=lambda i, iv, kt, period=None: series_for(i, sessions))

    assert result.benchmark is not None and result.benchmark.is_available
    assert result.outcomes[0].relative_strength is not None
    assert "BENCHMARK (rs.benchmark, DR-018)" in render(result)


# ------------------------------------------------------------------ the registry says it is active

def test_the_component_registry_calls_it_active() -> None:
    """`DR-024`. The claim and the wiring have to move together: a component the run does not call
    must not be `active`, and one it does call and prints must not be left at `specified`."""
    import yaml
    from tests.test_gates import REPO

    rows = yaml.safe_load(
        (REPO / "registry" / "components.yml").read_text(encoding="utf-8")
    )["components"]
    row = next(r for r in rows if r["component"] == "M31-T0464-v5.0")

    assert row["activation"] == "active"
    assert row["implements"] == "swingdesk.derived_observations.relative_strength:compute"
    assert row["verification"] == "property test"
    assert row["parameters"] == [], "no parameter, so nothing can leave it unable to activate"
