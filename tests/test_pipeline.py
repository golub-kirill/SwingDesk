"""End-to-end slice tests, offline.

Covers the two properties the walking skeleton exists to prove: a run is reproducible from its
manifest, and every candidate leaves with a coded decision.

Also covers the three measured pathologies from real data, using synthetic sessions so the tests
neither fetch nor depend on the current date (CI_POLICY 4).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

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
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    first = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    second = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)

    assert first.manifest.output_hash == second.manifest.output_hash
    assert first.manifest.output_hash is not None
    # Identity differs; inputs do not.
    assert first.manifest.run_id != second.manifest.run_id


def _registry_like(registry, overrides: dict[str, object]):
    """The fixture registry with one value moved, so a test can vary a single input."""
    entries = {pid: dict(entry) for pid, entry in registry._entries.items()}
    for key, value in overrides.items():
        entries[key]["value"] = value
    return type(registry)(entries)


def test_output_hash_moves_when_the_size_moves(stores, registry) -> None:
    """Same decision word, different share count. A hash blind to this is not pinning the run.

    Measured before the fix (2026-08-16): halving every candidate's share count left the golden
    case at 78732401bd216ae2, and gate 9 passed. The payload carried the decision and the latest
    ATR but not one number the owner would act on.
    """
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    lean = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    rich = run([TEST_US], FixedClock(AS_OF), _registry_like(registry, {"account.equity": 40_000}),
               store, journal, mode=MODE, fetcher=fetcher)

    assert [d.decision for d in lean.decisions] == [d.decision for d in rich.decisions], (
        "the decision word must be identical, or this test would pass on the old payload too"
    )
    assert lean.outcomes[0].risk.shares != rich.outcomes[0].risk.shares
    assert lean.manifest.output_hash != rich.manifest.output_hash


def test_output_hash_moves_when_the_stop_moves(stores, registry) -> None:
    """A 2x ATR stop and a 3x ATR stop are different instructions at the same decision.

    They hashed the same until 2026-08-16, as did a stop moved 40% wider on the golden case.
    """
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    tight = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    wide = run([TEST_US], FixedClock(AS_OF),
               _registry_like(registry, {"exit.atr_stop_multiple": "3.0"}),
               store, journal, mode=MODE, fetcher=fetcher)

    assert [d.decision for d in tight.decisions] == [d.decision for d in wide.decisions]
    assert tight.outcomes[0].risk.stop != wide.outcomes[0].risk.stop
    assert tight.manifest.output_hash != wide.manifest.output_hash


def test_every_candidate_leaves_with_a_decision(stores, registry) -> None:
    """No candidate is left without a next action - M32/M33 operational standard."""
    store, journal = stores
    us = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    ca = _sessions(TEST_CA.exchange, date(2025, 1, 1), date(2026, 1, 15))
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
    sessions = _sessions(TEST_US.exchange, date(2025, 6, 1), date(2026, 1, 15))
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


def test_bars_outside_the_window_are_not_findings(registry) -> None:
    """A series wider than the window is normal, and none of the surplus is a finding.

    `check` is called by the pipeline over one instrument's WHOLE stored extent, but a caller may
    pass any window - and the code comment has said since it was written that out-of-window
    sessions must stay out of scope, because a bar the window does not cover would otherwise be
    reported as "vendor returned bars but NYSE was closed".

    Nothing asserted it. Measured 2026-08-24: deleting the window filter left all 794 tests green,
    because every fixture in this file builds its series exactly over the window it then checks.
    This one deliberately does not.
    """
    window = (date(2025, 6, 2), date(2025, 6, 30))
    wider = _sessions(TEST_US.exchange, date(2025, 3, 3), date(2025, 9, 30))
    assert wider[0] < window[0] and wider[-1] > window[1], "the series must overhang both ends"

    report = check(series_for(TEST_US, wider), TEST_US.exchange, YAHOO, *window)
    assert report.is_complete, (
        f"surplus bars reported as findings: {[str(f) for f in report.findings[:3]]}"
    )
    assert report.sessions_checked == len(_sessions(TEST_US.exchange, *window))


def test_a_window_is_exact_at_both_ends_and_spans_a_year_boundary() -> None:
    """Both bounds are inclusive, and a window crossing a New Year keeps both sides.

    Two things can go wrong here and neither is visible in a total: an inclusive bound read as
    exclusive silently drops the endpoints, and any scheme that answers from a coarser unit than
    the window — a whole year, a quarter — drops the other side of a boundary. One such scheme was
    built and removed on 2026-08-24 (`reference_data/calendar.py` records why), and this test is
    what caught its off-by-one. It is kept because the property is the calendar's, not that
    scheme's.
    """
    start, end = date(2026, 3, 2), date(2026, 3, 31)
    march = cal.sessions(TEST_US.exchange, start, end)
    assert march[0].session_date == start, "the first session of the window was sliced off"
    assert march[-1].session_date == end, "the last session of the window was sliced off"
    assert all(start <= s.session_date <= end for s in march)
    year = cal.sessions(TEST_US.exchange, date(2026, 1, 1), date(2026, 12, 31))
    assert len(march) < len(year), "the window was not sliced out of the span at all"

    crossing = cal.sessions(TEST_US.exchange, date(2025, 12, 29), date(2026, 1, 5))
    assert {s.session_date.year for s in crossing} == {2025, 2026}


def test_an_inverted_window_raises_rather_than_answering_empty() -> None:
    """A caller defect must stay loud. `test_freshness.py` records a real one found through it.

    `start > end` reaches the calendar library, which rejects it. Anything that answered it with an
    empty tuple would read exactly like "the exchange was shut all week", and a bar dated after the
    last completed session is how the inverted window actually arises.
    """
    with pytest.raises(ValueError):
        cal.sessions(TEST_US.exchange, date(2026, 8, 24), date(2026, 8, 10))


def test_a_window_the_exchange_was_shut_for_has_no_sessions() -> None:
    """A closed window is an empty answer, never an error.

    The calendar reads two columns of a pandas frame; an EMPTY frame carries no dtype and the
    vectorised read raises `AttributeError` on it rather than returning nothing. A weekend is the
    cheapest instance of a window with no session in it.
    """
    saturday, sunday = date(2026, 8, 22), date(2026, 8, 23)
    assert cal.sessions(TEST_US.exchange, saturday, sunday) == ()
    assert cal.sessions(TEST_CA.exchange, saturday, sunday) == ()


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
                           adtv_window=20, min_history=250, adtv_lag=0),
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
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    selection = _universe_selection([TEST_US])

    result = run([], FixedClock(AS_OF), registry, store, journal, mode=MODE,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}), universe=selection)

    assert [o.instrument.id for o in result.outcomes] == [TEST_US.id]
    assert result.universe is selection


def test_the_universe_is_pinned_in_the_manifest(stores, registry) -> None:
    """The universe is a run INPUT. Unpinned, a changed universe moves output_hash with nothing in
    the manifest explaining why - the defect gate 9 caught in config_hash."""
    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
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
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
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
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    loose = _universe_selection([TEST_US])
    strict = replace(
        loose,
        rule=LiquidityRule(min_price=Decimal("5.00"), min_adtv=Decimal("25000000"),
                           adtv_window=20, min_history=250, adtv_lag=0),
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
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
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
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
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
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    fetcher = fixture_fetcher({TEST_US.id: sessions})

    run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE, fetcher=fetcher)
    result = run([TEST_US], FixedClock(AS_OF + timedelta(days=1)), registry, store, journal,
                 mode=MODE, fetcher=fetcher)

    decision = result.decisions[0]
    assert decision.previous_decision is not None
    assert journal.latest_decisions([TEST_US.id], AS_OF) == {}, (
        "as of the FIRST run's start the journal held nothing for this instrument"
    )


# ------------------------------------------- the exit policy, added 2026-08-16


def test_an_unset_exit_policy_refuses_rather_than_defaulting(stores, registry) -> None:
    """`DR-012` SET both parameters on 2026-08-17, so this test builds an unset registry rather
    than finding one - see the `status: unset` override below. It is still the check that
    matters: it fixes the behaviour for the day a parameter is retired or an owner clears one,
    which is when "unset is not default" has to hold.

    (The first line read *"are UNSET in the real registry"* until 2026-09-05, which was true
    when written and false for nineteen days after. The assertions never depended on it.)

    The pipeline used to paper over the unset case with a literal `ExitPolicy(Decimal("2.0"), 20)`
    in two places - while the candidate path sized against `entry - 1x ATR`, a third distance that
    matched neither.

    "Unset is not default" is a non-negotiable, and this was the one place in the decision path that
    broke it. With the parameters unset every candidate now Skips with a coded refusal naming the
    parameter, which is the same shape the 4,486 `risk.per_trade_pct` refusals took.
    """
    from swingdesk.platform.parameters import ParameterRegistry

    entries = {
        key: dict(entry) for key, entry in registry._entries.items()
    }
    for key in ("exit.atr_stop_multiple", "exit.max_holding_period"):
        entries[key] = {**entries[key], "value": None, "provenance": None, "status": "unset"}
    unset = ParameterRegistry(entries)

    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    result = run([TEST_US], FixedClock(AS_OF), unset, store, journal, mode=MODE,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}))

    decision = result.decisions[0]
    assert decision.decision == "Skip"
    assert decision.reason_code == "RISK"
    assert decision.parameter_id in {"exit.atr_stop_multiple", "exit.max_holding_period"}
    # And the run still completed with every candidate coded - a.decisions_coded is unaffected.
    assert journal.uncoded_refusals(result.manifest.run_id) == 0


def test_the_sizing_stop_is_the_policy_stop(stores, registry) -> None:
    """One exit semantics for the whole run.

    The candidate path sized against `entry - 1x ATR` while management and the checklist used
    `2x ATR`, so the distance a candidate was sized on was not the distance it would be stopped at -
    and every position was sized about twice as large as its own exit rule implied.
    """
    from swingdesk.trade_management.exits import ExitPolicy

    store, journal = stores
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    policy = ExitPolicy(Decimal("2.0"), 20)
    result = run([TEST_US], FixedClock(AS_OF), registry, store, journal, mode=MODE,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}), exits=policy)

    risk = result.outcomes[0].risk
    atr_value = result.outcomes[0].observations.observations[-1].value
    assert risk is not None and atr_value is not None
    assert risk.stop == policy.stop_for(risk.entry, atr_value)
    assert risk.stop != risk.entry - atr_value, "1x ATR is the old, unrelated distance"
