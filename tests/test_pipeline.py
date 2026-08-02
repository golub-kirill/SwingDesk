"""End-to-end slice tests, offline.

Covers the two properties the walking skeleton exists to prove: a run is reproducible from its
manifest, and every candidate leaves with a coded decision.

Also covers the three measured pathologies from real data, using synthetic sessions so the tests
neither fetch nor depend on the current date (CI_POLICY 4).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from swingdesk.application.pipeline import run
from swingdesk.contracts.market import Interval, Series
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import BarStore, YAHOO, check
from swingdesk.platform.clock import FixedClock
from swingdesk.reference_data import calendar as cal
from tests.conftest import TEST_CA, TEST_US, fixture_fetcher, series_for

UTC = timezone.utc
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

    first = run([TEST_US], FixedClock(AS_OF), registry, store, journal, fetcher=fetcher)
    second = run([TEST_US], FixedClock(AS_OF), registry, store, journal, fetcher=fetcher)

    assert first.manifest.output_hash == second.manifest.output_hash
    assert first.manifest.output_hash is not None
    # Identity differs; inputs do not.
    assert first.manifest.run_id != second.manifest.run_id


def test_every_candidate_leaves_with_a_decision(stores, registry) -> None:
    """"Нет кандидатов без следующего действия" - M32/M33 operational standard."""
    store, journal = stores
    us = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 14))
    ca = _sessions(TEST_CA.exchange, date(2025, 1, 1), date(2026, 1, 14))
    fetcher = fixture_fetcher({TEST_US.id: us, TEST_CA.id: ca})

    result = run([TEST_US, TEST_CA], FixedClock(AS_OF), registry, store, journal, fetcher=fetcher)

    assert len(result.decisions) == 2
    assert all(d.decision in {"Trade", "Watch", "Skip", "Pause"} for d in result.decisions)
    assert all(d.reason_code for d in result.decisions if d.decision == "Skip")
    assert journal.uncoded_refusals(result.manifest.run_id) == 0


def test_missing_vendor_data_skips_with_a_code(stores, registry) -> None:
    """Fetch failure degrades to a coded refusal, never an exception escaping the run."""
    store, journal = stores
    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal,
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

    run([TEST_US], FixedClock(AS_OF), registry, store, journal, fetcher=fetcher)
    after_first = store.revision_count(TEST_US.id)
    run([TEST_US], FixedClock(AS_OF), registry, store, journal, fetcher=fetcher)
    run([TEST_US], FixedClock(AS_OF), registry, store, journal, fetcher=fetcher)

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
