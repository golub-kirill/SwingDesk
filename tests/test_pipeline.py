"""End-to-end slice tests, offline.

Covers the two properties the walking skeleton exists to prove: a run is reproducible from its
manifest, and every candidate leaves with a coded decision.

Also covers the three measured pathologies from real data, using synthetic sessions so the tests
neither fetch nor depend on the current date (CI_POLICY 4).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from tests.conftest import TEST_CA, TEST_US, fixture_fetcher, series_for

from swingdesk.application.pipeline import run
from swingdesk.contracts.market import Interval, Series
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import YAHOO, BarStore, check
from swingdesk.platform.clock import FixedClock
from swingdesk.reference_data import calendar as cal

MODE = RunMode.LIVE_AS_OF
AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


def _sessions(exchange, start: date, end: date) -> list[date]:
    """Real sessions from the authoritative calendar, so fixtures agree with it by construction."""
    return [s.session_date for s in cal.sessions(exchange, start, end)]


@pytest.fixture
def stores(tmp_path):
    with BarStore(tmp_path / "bars.duckdb") as store, Journal(tmp_path / "journal.duckdb") as journal:
        yield store, journal


def test_run_is_reproducible(stores, registry) -> None:
    """Same inputs, same output hash. The ratified Track A criterion a.reproducible."""
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    first = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    second = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)

    assert first.manifest.output_hash == second.manifest.output_hash
    assert first.manifest.output_hash is not None
    # Identity differs; inputs do not.
    assert first.manifest.run_id != second.manifest.run_id


def test_every_candidate_leaves_with_a_decision(stores, registry) -> None:
    """No candidate is left without a next action - M32/M33 operational standard."""
    store, journal = stores
    us = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    ca = _sessions(TEST_CA.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: us, TEST_CA.id: ca})

    result = run([TEST_US, TEST_CA], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)

    assert len(result.decisions) == 2
    assert all(d.decision in {"Trade", "Watch", "Skip", "Pause"} for d in result.decisions)
    assert all(d.reason_code for d in result.decisions if d.decision == "Skip")
    assert journal.uncoded_refusals(result.manifest.run_id) == 0


def test_missing_vendor_data_skips_with_a_code(stores, registry) -> None:
    """Fetch failure degrades to a coded refusal, never an exception escaping the run."""
    store, journal = stores
    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE,
                 fetcher=fixture_fetcher({}))
    assert result.decisions[0].decision == "Skip"
    assert result.decisions[0].reason_code == "DATA"


def test_revision_deltas_not_snapshots(stores, registry) -> None:
    """Re-fetching identical data must not grow the store.

    Yahoo rewrites full adjusted history on every refetch, so appending what came back would write
    ~20M rows a day (POINT_IN_TIME_SPEC 3).
    """
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 6, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    after_first = store.revision_count(TEST_US.id)
    run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)

    assert store.revision_count(TEST_US.id) == after_first
    assert after_first == len(sessions)


# ------------------------------------------------- the three measured pathologies

def test_half_day_does_not_raise_data(registry) -> None:
    """A scheduled early close is normal and must not block.

    Without the vendor profile modelling Yahoo dropping the trailing stub, every half-day would
    raise DATA - the exact false positive ADR-0002 was adopted to avoid.
    """
    window = (date(2025, 11, 24), date(2025, 11, 28))
    sessions = _sessions(TEST_US.exchange, *window)
    assert date(2025, 11, 28) in sessions, "fixture must include the known half-day"
    assert date(2025, 11, 27) not in sessions, "US Thanksgiving is a closure"

    report = check(series_for(TEST_US, sessions), TEST_US.exchange, YAHOO, *window)
    assert report.is_complete


def test_exchange_divergence_is_not_a_gap(registry) -> None:
    """One exchange open while the other is closed is normal, and the calendars differ."""
    window = (date(2025, 11, 24), date(2025, 11, 28))
    us = _sessions(TEST_US.exchange, *window)
    ca = _sessions(TEST_CA.exchange, *window)
    assert us != ca, "NYSE and TSX must diverge in this window"

    assert check(series_for(TEST_US, us), TEST_US.exchange, YAHOO, *window).is_complete
    assert check(series_for(TEST_CA, ca), TEST_CA.exchange, YAHOO, *window).is_complete


def test_missing_session_raises_data(registry) -> None:
    """A vendor gap is abnormal and must block, with a code."""
    window = (date(2025, 6, 2), date(2025, 6, 30))
    sessions = _sessions(TEST_US.exchange, *window)
    dropped = sessions[5]
    gapped = [s for s in sessions if s != dropped]

    report = check(series_for(TEST_US, gapped), TEST_US.exchange, YAHOO, *window)
    assert not report.is_complete
    assert dropped in report.incomplete_dates
    assert all(finding.code == "DATA" for finding in report.findings)


def test_as_of_ignores_later_knowledge(stores, registry) -> None:
    """A query dated before a revision must not see it. This is the look-ahead guard."""
    store, _ = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 12, 1), date(2025, 12, 31))
    original = series_for(TEST_US, sessions)
    early = datetime(2026, 1, 1, tzinfo=UTC)
    store.write(original.bars, early)

    from decimal import Decimal
    later = datetime(2026, 2, 1, tzinfo=UTC)
    revised = tuple(
        bar.model_copy(update={"close": bar.close + Decimal("5.00"),
                               "high": bar.high + Decimal("5.00")})
        for bar in original.bars
    )
    store.write(revised, later)

    before = store.as_of(TEST_US.id, Interval.DAY, Series.RAW, early)
    after = store.as_of(TEST_US.id, Interval.DAY, Series.RAW, later)
    assert [b.close for b in before.bars] == [b.close for b in original.bars]
    assert [b.close for b in after.bars] == [b.close for b in revised]


# ------------------------------------------------------------------ the universe path


def _universe_selection(instruments):
    """A selection standing in for one the builder would produce, so the pipeline test stays
    about the pipeline rather than about two stores."""
    from decimal import Decimal

    from swingdesk.application.universe import Membership, UniverseSelection
    from swingdesk.reference_data.universe import LiquidityRule

    return UniverseSelection(
        as_of=AS_OF,
        rule=LiquidityRule(min_price=Decimal("5.00"), min_adtv=Decimal("5000000"),
                           adtv_window=20, min_history=250),
        parameters=(), directory_pull=AS_OF,
        eligible=len(instruments), measured=len(instruments),
        members=tuple(
            Membership(instrument=i, close=Decimal("100"), adtv=Decimal("10000000"), bars=300)
            for i in instruments
        ),
    )


def test_a_universe_supplies_the_candidates(stores, registry) -> None:
    """The CHARTER 4 shape: the run starts from a rule, not from a typed list."""
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    selection = _universe_selection([TEST_US])

    result = run([], FixedClock(AS_OF), registry, store, journal, mode=MODE,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}), universe=selection)

    assert [o.instrument.id for o in result.outcomes] == [TEST_US.id]
    assert result.universe is selection


def test_the_universe_is_pinned_in_the_manifest(stores, registry) -> None:
    """The universe is a run INPUT. Unpinned, a changed universe moves output_hash with nothing in
    the manifest explaining why - the defect gate 9 caught in config_hash."""
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions, TEST_CA.id: sessions})

    one = run([], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher,
              universe=_universe_selection([TEST_US]))
    two = run([], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher,
              universe=_universe_selection([TEST_US, TEST_CA]))

    assert one.manifest.universe_hash is not None
    assert one.manifest.universe_hash != two.manifest.universe_hash


def test_a_run_without_a_universe_pins_nothing(stores, registry) -> None:
    """None means "explicit instrument list", and must not be confused with an empty universe."""
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}))
    assert result.manifest.universe_hash is None
    assert result.universe is None


def test_the_universe_hash_moves_when_the_rule_moves(stores, registry) -> None:
    """Members alone would not move when a threshold changed on a day it admitted the same names."""
    from dataclasses import replace
    from decimal import Decimal

    from swingdesk.reference_data.universe import LiquidityRule

    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    loose = _universe_selection([TEST_US])
    strict = replace(
        loose,
        rule=LiquidityRule(min_price=Decimal("5.00"), min_adtv=Decimal("25000000"),
                           adtv_window=20, min_history=250),
    )

    one = run([], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher, universe=loose)
    two = run([], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher, universe=strict)

    assert one.manifest.universe_hash != two.manifest.universe_hash


# --------------------------------------------------------------- mode and from_state


def test_the_mode_is_recorded_and_cannot_be_omitted(stores, registry) -> None:
    """A journalled run must be able to answer "was this real?" without inference.

    `mode` is keyword-only and has no default, so the failure is a TypeError at the call site rather
    than a manifest that quietly claims a mode nobody chose. Deriving it from the injected clock and
    fetcher would be automatic and would re-create the inference SYSTEM_MODES 3 objects to.
    """
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    assert result.manifest.mode is RunMode.LIVE_AS_OF

    with pytest.raises(TypeError, match="mode"):
        run([TEST_US], FixedClock(AS_OF), registry, store, journal, fetcher=fetcher)  # type: ignore[call-arg]


def test_a_decision_records_what_it_was_before(stores, registry) -> None:
    """from_state, TRANSITION_SPEC 4.

    The first run has no previous decision and says so with None - a first sighting is not
    "unchanged". The second run carries the first run's decision, which is what makes a Watch that
    became a Skip distinguishable from a Skip that has been a Skip all week.
    """
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    first = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    assert first.decisions[0].previous_decision is None

    later = AS_OF + timedelta(days=1)
    second = run([TEST_US], FixedClock(later), registry, store, journal, mode=MODE, fetcher=fetcher)

    assert second.decisions[0].previous_decision == first.decisions[0].decision
    # And it survives the round trip, which is the point of recording it at all.
    stored = journal.decisions_for(second.manifest.run_id)
    assert stored[0].previous_decision == first.decisions[0].decision


def test_from_state_is_read_as_of_the_run_start_not_as_of_now(stores, registry) -> None:
    """A run reports what the journal said when it BEGAN.

    Read after its own decisions were written, the query would return this run's own verdict as its
    predecessor - a record that says every instrument's decision is unchanged from itself.
    """
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    result = run([TEST_US], FixedClock(AS_OF + timedelta(days=1)), registry, store, journal,
                 mode=MODE, fetcher=fetcher)

    decision = result.decisions[0]
    assert decision.previous_decision is not None
    assert journal.latest_decisions([TEST_US.id], AS_OF) == {}, (
        "as of the FIRST run's start the journal held nothing for this instrument"
    )
