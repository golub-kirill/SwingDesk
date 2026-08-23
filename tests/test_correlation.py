"""The correlation cap: the statistic, the verdict, and what the decision path does with them.

`DR-006` §2 authored both numbers - `risk.correlation_threshold` = 0.70 over
`risk.correlation_lookback_sessions` = 60 - and §3 then recorded the constraint as *unevaluable*,
because "nothing computes a correlation matrix over the candidate set". §8.4 established that this
was a statement about missing CODE and not about missing data; this is the code, built 2026-08-23.

Structured the way `test_portfolio.py` is, and for the same reason: the pure statistic first, then
the pure verdict, then the pipeline through both, then the fail-closed case. The order matters here
more than usual, because the two halves fail in OPPOSITE directions - an unset threshold refuses
every candidate, and a pair that could not be measured refuses none - and a suite that did not test
them apart could not tell the two behaviours had been swapped.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Context, Decimal, localcontext

import pytest
from tests.conftest import TEST_US, fixture_fetcher, series_for

from swingdesk.application.pipeline import run
from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.position import Position
from swingdesk.contracts.run import RunMode
from swingdesk.derived_observations import correlation
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import calendar as cal
from swingdesk.trade_management import portfolio
from swingdesk.trade_management.sizing import Refusal

AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)

#: The authored cap, as `conftest.registry` carries it.
LIMIT = portfolio.CorrelationLimit(threshold=Decimal("0.70"), lookback=60)


def _sessions(start: date = date(2025, 1, 1), end: date = date(2026, 1, 15)) -> list[date]:
    return [s.session_date for s in cal.sessions(TEST_US.exchange, start, end)]


def _returns(*values: str, start: date = date(2025, 1, 2)) -> tuple[correlation.DailyReturn, ...]:
    """A hand-built return stream on consecutive calendar days.

    Calendar days rather than sessions on purpose: `measure` aligns on the session_date it is
    given and holds no calendar of its own, so a fixture that needed one would be testing the
    calendar as well.
    """
    return tuple(
        correlation.DailyReturn(date.fromordinal(start.toordinal() + offset), Decimal(value))
        for offset, value in enumerate(values)
    )


def _bars(closes: list[str], start: date = date(2025, 1, 2)) -> BarSeries:
    """One bar per consecutive calendar day at the given closes."""
    return BarSeries(
        instrument_id=TEST_US.id,
        interval=Interval.DAY,
        series=Series.RAW,
        knowledge_time=AS_OF,
        bars=tuple(
            Bar(
                instrument_id=TEST_US.id,
                interval=Interval.DAY,
                series=Series.RAW,
                event_time=datetime.combine(
                    date.fromordinal(start.toordinal() + offset), datetime.min.time(), tzinfo=UTC
                ),
                session_date=date.fromordinal(start.toordinal() + offset),
                open=Decimal(close),
                high=Decimal(close) + Decimal(1),
                low=Decimal(close) - Decimal(1),
                close=Decimal(close),
                volume=1_000,
                knowledge_time=AS_OF,
            )
            for offset, close in enumerate(closes)
        ),
    )


def _without(registry: ParameterRegistry, parameter_id: str) -> ParameterRegistry:
    entries = {pid: dict(entry) for pid, entry in registry._entries.items()}
    entries[parameter_id]["value"] = None
    return type(registry)(entries)


# ------------------------------------------------------------------ the returns


def test_returns_are_close_to_close_and_one_shorter_than_the_bars() -> None:
    returns = correlation.daily_returns(_bars(["100", "110", "99"]))
    assert [r.value for r in returns] == [Decimal("0.1"), Decimal("-0.1")]
    assert [r.session_date for r in returns] == [date(2025, 1, 3), date(2025, 1, 4)]


def test_a_non_positive_previous_close_yields_no_return_rather_than_a_zero() -> None:
    """A vendor that serves a zero close must not divide, and must not contribute a fabricated
    0.0% session to a window that is meant to hold real ones (`SECURITY` §6 - untrusted input)."""
    returns = correlation.daily_returns(_bars(["100", "0", "50", "60"]))
    assert [r.session_date for r in returns] == [date(2025, 1, 3), date(2025, 1, 5)]
    assert [r.value for r in returns] == [Decimal(-1), Decimal("0.2")]


def test_an_empty_series_has_no_returns() -> None:
    assert correlation.daily_returns(_bars([])) == ()
    assert correlation.daily_returns(_bars(["100"])) == ()


# ------------------------------------------------------------------ the statistic


def test_pearson_matches_a_hand_computed_sample() -> None:
    """The independent check. Every other assertion here is about a series this file built to have
    a property; this one is arithmetic anyone can redo on paper.

    x = 1..5, y = 2,4,5,4,5. Deviations give cov = 6, var_x = 10, var_y = 6, so
    r = 6 / sqrt(60) = 0.774596669...
    """
    x = [Decimal(v) for v in (1, 2, 3, 4, 5)]
    y = [Decimal(v) for v in (2, 4, 5, 4, 5)]
    r = correlation.pearson(x, y)
    assert r is not None
    assert abs(r - Decimal("0.7745966692414834")) < Decimal("1E-15")


def test_a_series_correlates_perfectly_with_itself_and_inversely_with_its_negation() -> None:
    values = [Decimal(v) for v in ("0.01", "-0.02", "0.03", "0.005", "-0.011")]
    assert correlation.pearson(values, values) == Decimal(1)
    assert correlation.pearson(values, [-v for v in values]) == Decimal(-1)


def test_a_series_that_never_moved_has_no_correlation_rather_than_zero() -> None:
    """`None`, not 0. Zero is the strongest available claim of independence and this is the weakest
    available data - a halted or barely-traded name. Reporting one as the other is the collapse
    `AGENTS.md` §12 names."""
    flat = [Decimal(0)] * 5
    moving = [Decimal(v) for v in ("0.01", "-0.02", "0.03", "0.005", "-0.011")]
    assert correlation.pearson(flat, moving) is None
    assert correlation.pearson(flat, flat) is None


def test_pearson_refuses_mismatched_samples_and_returns_nothing_for_one_point() -> None:
    with pytest.raises(ValueError, match="differ in length"):
        correlation.pearson([Decimal(1)], [Decimal(1), Decimal(2)])
    assert correlation.pearson([Decimal(1)], [Decimal(1)]) is None


def test_the_result_does_not_depend_on_the_ambient_decimal_context() -> None:
    """The pinned context earning its place. `decimal` precision is process-global mutable state,
    and a statistic whose digits move when some other module widens it is not reproducible in the
    sense `DETERMINISM_SPEC` §3 means."""
    x = [Decimal(v) for v in (1, 2, 3, 4, 5)]
    y = [Decimal(v) for v in (2, 4, 5, 4, 5)]
    with localcontext(Context(prec=6)):
        coarse = correlation.pearson(x, y)
    with localcontext(Context(prec=50)):
        fine = correlation.pearson(x, y)
    assert coarse == fine


# ------------------------------------------------------------------ the window


def test_the_window_is_the_last_shared_sessions_not_the_last_calendar_sessions() -> None:
    """A hole on one side removes that session from the PAIR, not from the window. Intersecting a
    fixed slice instead would silently measure 59 sessions and call the result a 60-session
    correlation."""
    left = _returns(*["0.01", "-0.02", "0.03"] * 30)          # 90 sessions
    right = tuple(r for r in left if r.session_date != left[85].session_date)  # one hole near the end
    measured = correlation.measure(left, right, 60)
    assert measured.overlap == 60
    assert measured.is_available


def test_too_little_overlap_is_unavailable_and_names_the_shortfall() -> None:
    left = _returns("0.01", "-0.02", "0.03", "0.04")
    measured = correlation.measure(left, left, 60)
    assert measured.r is None
    assert measured.overlap == 4
    assert measured.unavailable is not None
    assert "4 session(s)" in measured.unavailable and "60" in measured.unavailable


def test_no_shared_session_at_all_is_unavailable_rather_than_an_error() -> None:
    left = _returns("0.01", "-0.02", start=date(2025, 1, 2))
    right = _returns("0.01", "-0.02", start=date(2025, 6, 2))
    measured = correlation.measure(left, right, 60)
    assert measured.overlap == 0 and measured.r is None


def test_a_flat_side_is_unavailable_and_says_which_way_it_failed() -> None:
    moving = _returns(*["0.01", "-0.02", "0.03"] * 20)   # 60 sessions
    flat = tuple(correlation.DailyReturn(r.session_date, Decimal(0)) for r in moving)
    measured = correlation.measure(moving, flat, 60)
    assert measured.r is None
    assert measured.unavailable is not None
    assert "did not move" in measured.unavailable


def test_a_lookback_under_two_sessions_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="lookback must be"):
        correlation.measure(_returns("0.01", "0.02"), _returns("0.01", "0.02"), 1)


# ------------------------------------------------------------------ the parameters


def test_the_limit_reads_both_numbers(registry) -> None:
    limit = portfolio.correlation_limit(registry)
    assert limit.threshold == Decimal("0.70")
    assert limit.lookback == 60


@pytest.mark.parametrize(
    "missing", [portfolio.CORRELATION_THRESHOLD, portfolio.CORRELATION_LOOKBACK]
)
def test_either_half_unset_refuses_and_names_itself(registry, missing: str) -> None:
    """Read together for the same reason the book's two are: a threshold measured over an unknown
    window is not a threshold (`DR-006` §7, the defect this pair closed)."""
    with pytest.raises(ParameterUnset) as unset:
        portfolio.correlation_limit(_without(registry, missing))
    assert unset.value.parameter_id == missing


# ------------------------------------------------------------------ the verdict


def _stream(*values: str) -> tuple[correlation.DailyReturn, ...]:
    """60 sessions built by repeating a short pattern, so a pair can be made to any r on purpose."""
    return _returns(*(list(values) * (60 // len(values) + 1))[:60])


#: Two streams whose correlation is exactly -1, and two whose correlation is exactly 1.
UP = _stream("0.01", "-0.02", "0.03", "0.005")
DOWN = tuple(correlation.DailyReturn(r.session_date, -r.value) for r in UP)
SAME = tuple(correlation.DailyReturn(r.session_date, r.value) for r in UP)


def test_an_empty_book_admits_and_says_there_was_nothing_to_duplicate() -> None:
    verdict = portfolio.assess_correlation(UP, {}, LIMIT)
    assert verdict.admitted and verdict.binding is None
    assert not verdict.is_unavailable, "an empty book is a fact, not a gap in the system"
    assert "nothing to duplicate" in verdict.reason


def test_a_duplicate_refuses_and_names_the_position_it_duplicates() -> None:
    verdict = portfolio.assess_correlation(UP, {"HELD.1": SAME}, LIMIT)
    assert not verdict.admitted
    assert verdict.binding is not None and verdict.binding.instrument_id == "HELD.1"
    assert "HELD.1" in verdict.reason and "1.00" in verdict.reason


def test_an_uncorrelated_candidate_is_admitted_and_the_closest_pair_is_reported() -> None:
    """The positive control. Without it every negative test below would pass on a cap that refused
    unconditionally."""
    other = _stream("0.01", "-0.02", "-0.03", "0.005")   # measured: r = -0.1311 against UP
    verdict = portfolio.assess_correlation(UP, {"HELD.1": other}, LIMIT)
    assert verdict.admitted and verdict.binding is None
    assert verdict.closest is not None and verdict.closest.instrument_id == "HELD.1"
    assert abs(verdict.closest.measurement.r or Decimal(1)) < LIMIT.threshold
    assert "closest open position is HELD.1" in verdict.reason


def test_the_threshold_binds_at_the_value_itself_not_above_it() -> None:
    """`>=`, as `DR-006` §2 words it - *at* r = 0.7 two names stop being independent bets.

    Tested ON the boundary rather than near it, and that distinction is the whole test: an earlier
    version asserted this with an r of 1.00 against a threshold of 0.70, which is refused by `>=`
    and by `>` alike. Mutating the comparison left it green. A pair whose r is EXACTLY the
    threshold is the only input that can tell the two operators apart.
    """
    exactly = portfolio.CorrelationLimit(threshold=Decimal(1), lookback=60)
    assert not portfolio.assess_correlation(UP, {"HELD.1": SAME}, exactly).admitted, (
        "r == threshold must refuse; `>` instead of `>=` would admit it"
    )

    generous = portfolio.CorrelationLimit(threshold=Decimal("1.01"), lookback=60)
    assert portfolio.assess_correlation(UP, {"HELD.1": SAME}, generous).admitted, (
        "at r = 1.00 against a threshold of 1.01 the candidate is inside the cap"
    )

    assert not portfolio.assess_correlation(UP, {"HELD.1": SAME}, LIMIT).admitted, (
        "and the authored 0.70 refuses a pair well past it"
    )


def test_a_strongly_negative_correlation_does_not_refuse() -> None:
    """The sign is kept: the test is `r >= threshold`, never `abs(r) >= threshold`. What
    `DR-006` §2 bounds is DUPLICATE exposure, and r = -1 is the opposite arrangement - refusing it
    would forbid the one pairing that reduces what the cap exists to bound."""
    verdict = portfolio.assess_correlation(UP, {"HELD.1": DOWN}, LIMIT)
    assert verdict.admitted
    assert verdict.closest is not None
    assert verdict.closest.measurement.r == Decimal(-1)


def test_the_highest_correlation_binds_not_the_first_one_sorted() -> None:
    """The reason names one position, and it must name the strongest cause rather than whichever id
    happened to sort earliest - otherwise the owner is answering the wrong question."""
    mild = _stream("0.01", "-0.019", "0.03", "-0.02")
    verdict = portfolio.assess_correlation(
        UP, {"AAA.1": mild, "ZZZ.9": SAME}, LIMIT
    )
    assert not verdict.admitted
    assert verdict.binding is not None
    assert verdict.binding.instrument_id == "ZZZ.9", (
        f"expected the r = 1.00 pair to bind, got {verdict.binding.instrument_id}"
    )


def test_an_unmeasurable_pair_admits_and_is_reported_as_unavailable() -> None:
    """`DR-006` §3, verbatim in effect: a check the system could not perform must not fail closed
    into a blanket refusal. A sector or correlation gate that refused every candidate for want of
    data would stop the system entirely while looking like risk discipline."""
    verdict = portfolio.assess_correlation(UP, {"HELD.1": _returns("0.01", "0.02")}, LIMIT)
    assert verdict.admitted, "a gap in the SYSTEM must not refuse the trade"
    assert verdict.is_unavailable
    assert verdict.closest is None
    assert verdict.reason.startswith("UNAVAILABLE")
    assert "overlapping daily returns" in verdict.reason


def test_a_partly_measurable_book_admits_and_counts_what_it_could_not_check() -> None:
    """The dangerous middle case. "Cleared the one position I could measure" and "cleared the book"
    are different claims, and only the second is what an owner would act on."""
    verdict = portfolio.assess_correlation(
        UP, {"HELD.1": DOWN, "HELD.2": _returns("0.01", "0.02")}, LIMIT
    )
    assert verdict.admitted
    assert not verdict.is_unavailable, "one measured pair is not a wholly unmeasurable book"
    assert len(verdict.measured) == 1 and len(verdict.unmeasured) == 1
    assert "could not be measured and are unchecked rather than clear" in verdict.reason


def test_an_unmeasurable_pair_can_never_bind() -> None:
    """The property behind the two tests above, stated once: `binding` is only ever set from a pair
    that carries a coefficient, so no refusal can rest on a measurement that does not exist."""
    verdict = portfolio.assess_correlation(
        UP, {"HELD.1": _returns("0.01"), "HELD.2": SAME}, LIMIT
    )
    assert verdict.binding is not None
    assert verdict.binding.measurement.is_available


# ------------------------------------------------------------------ through the pipeline


@pytest.fixture
def wired(tmp_path):
    with (
        BarStore(tmp_path / "bars.duckdb") as bars,
        Journal(tmp_path / "journal.duckdb") as journal,
        PositionStore(tmp_path / "positions.duckdb") as positions,
    ):
        yield bars, journal, positions


def _position(instrument: str) -> Position:
    """One small open position: 10 shares, entry 100, stop 99.9 - 0.01R, so the BOOK cap never
    binds first and the correlation check is what the test is actually exercising."""
    return Position(
        position_id=f"POS-{instrument}", version=1, instrument_id=instrument,
        opened_on=date(2025, 12, 1), entry_price=Decimal(100), shares=10,
        initial_stop=Decimal("99.9"), current_stop=Decimal("99.9"),
        initial_costs_per_share=Decimal("0.50"),
        knowledge_time=datetime(2025, 12, 1, tzinfo=UTC),
    )


def _run(wired, registry, *, held: list[str] = (), zigzag: set[str] = frozenset(),
         candidate_sessions: list[date] | None = None):
    bars, journal, positions = wired
    for instrument_id in held:
        positions.record(_position(instrument_id))
    sessions = _sessions()
    by_instrument = {instrument_id: sessions for instrument_id in held}
    by_instrument[TEST_US.id] = candidate_sessions if candidate_sessions is not None else sessions
    return run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
               fetcher=fixture_fetcher(by_instrument, zigzag=zigzag), positions=positions)


def test_a_candidate_duplicating_an_open_position_is_skipped_for_risk(wired, registry) -> None:
    """Every fixture instrument walks the same arithmetic path, so a held name and a candidate
    correlate at exactly 1.00 - which is what makes this the clean end of the range."""
    result = _run(wired, registry, held=["HELD.1"])

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip"
    assert decision.reason_code == "RISK"
    assert "HELD.1" in decision.reason
    assert decision.parameter_id is None, (
        "a duplicate is a fact about the account, not an unset threshold - `funnel.py` splits "
        "skip causes on exactly that field"
    )


def test_an_uncorrelated_book_lets_the_candidate_through(wired, registry) -> None:
    """The positive control through the whole run, not just the verdict. Without it the test above
    passes on a pipeline that refuses every candidate that meets an open position at all."""
    result = _run(wired, registry, held=["HELD.1"], zigzag={"HELD.1"})

    outcome = result.outcomes[0]
    assert outcome.decision.decision == "Watch"
    assert outcome.correlation is not None and outcome.correlation.admitted
    assert outcome.correlation.closest is not None
    assert abs(outcome.correlation.closest.measurement.r) < Decimal("0.70")


def test_a_candidate_already_in_the_book_meets_itself_and_refuses(wired, registry) -> None:
    """r = 1 with itself, and that is the rule working. Adding to a position is the most complete
    duplicate exposure there is, and the course supplies no pyramiding rule that would tell it
    apart from a second bet (`DR-006` §11)."""
    result = _run(wired, registry, held=[TEST_US.id])

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip" and decision.reason_code == "RISK"
    assert TEST_US.id in decision.reason


def test_a_short_candidate_history_is_admitted_unchecked_rather_than_refused(
    wired, registry
) -> None:
    """The `unavailable` path end to end. A candidate with three months of bars cannot be measured
    over a 60-session window against a book that has a year, and `DR-006` §3 forbids turning that
    into a refusal."""
    result = _run(wired, registry, held=["HELD.1"],
                  candidate_sessions=_sessions(date(2025, 11, 1), date(2026, 1, 15)))

    outcome = result.outcomes[0]
    assert outcome.decision.decision == "Watch"
    assert outcome.correlation is not None
    assert outcome.correlation.admitted and outcome.correlation.is_unavailable


def test_the_cap_is_not_evaluated_without_a_position_store(wired, registry) -> None:
    """A third state, distinct from "cleared" and from "could not measure": the check was never
    reached, because the run had no way to know what the book holds."""
    bars, journal, _positions = wired
    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: _sessions()}))

    assert result.outcomes[0].decision.decision == "Watch"
    assert result.outcomes[0].correlation is None
    assert isinstance(result.correlation, portfolio.CorrelationLimit), (
        "the LIMIT is still reported even on a run that could not apply it"
    )


@pytest.mark.parametrize(
    "missing", [portfolio.CORRELATION_THRESHOLD, portfolio.CORRELATION_LOOKBACK]
)
def test_an_unset_half_refuses_every_candidate_and_names_the_parameter(
    wired, registry, missing: str
) -> None:
    """The opposite direction from `unavailable`, and the pair of behaviours this file exists to
    keep apart. An unset parameter is the registry failing closed on a number nobody ruled; it
    refuses, and it names what is missing. A pair that could not be measured does neither."""
    result = _run(wired, _without(registry, missing), held=["HELD.1"], zigzag={"HELD.1"})

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip" and decision.reason_code == "RISK"
    assert decision.parameter_id == missing
    assert isinstance(result.correlation, Refusal)


def test_an_unset_half_refuses_even_with_no_position_store(wired, registry) -> None:
    """Outside the position-store branch, exactly as the book cap is. A limit with no value is a
    fact about the registry and holds whether or not this run knows what the book contains."""
    bars, journal, _positions = wired
    result = run([TEST_US], FixedClock(AS_OF), _without(registry, portfolio.CORRELATION_THRESHOLD),
                 bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: _sessions()}))

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip"
    assert decision.parameter_id == portfolio.CORRELATION_THRESHOLD


def test_the_output_hash_moves_when_a_candidate_becomes_a_duplicate(wired, registry) -> None:
    """`output_hash` has to separate two runs the owner could act on differently, and "Watch" versus
    "refused as a duplicate of a position you hold" is exactly that."""
    admitted = _run(wired, registry, held=["HELD.1"], zigzag={"HELD.1"}).manifest.output_hash

    bars, _journal, _positions = wired
    with (
        BarStore(bars.path.parent / "b2.duckdb") as second_bars,
        Journal(bars.path.parent / "j2.duckdb") as second_journal,
        PositionStore(bars.path.parent / "p2.duckdb") as second_positions,
    ):
        second_positions.record(_position("HELD.2"))
        sessions = _sessions()
        refused = run(
            [TEST_US], FixedClock(AS_OF), registry, second_bars, second_journal,
            mode=RunMode.LIVE_AS_OF, positions=second_positions,
            fetcher=fixture_fetcher({TEST_US.id: sessions, "HELD.2": sessions}),
        ).manifest.output_hash

    assert admitted != refused


def test_two_positions_in_one_instrument_are_correlated_once(wired, registry) -> None:
    """Keyed by INSTRUMENT, not by position. Two lots of the same name are one comparison, and
    counting the pair twice would say nothing new while making the reason twice as long."""
    bars, journal, positions = wired
    positions.record(_position("HELD.1"))
    positions.record(
        _position("HELD.1").model_copy(update={"position_id": "POS-HELD.1-b", "shares": 5})
    )
    sessions = _sessions()
    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 positions=positions,
                 fetcher=fixture_fetcher({TEST_US.id: sessions, "HELD.1": sessions},
                                         zigzag={"HELD.1"}))

    outcome = result.outcomes[0]
    assert outcome.correlation is not None
    assert len(outcome.correlation.pairs) == 1


# ------------------------------------------------------------------ the report


def test_the_report_prints_the_limit_and_what_it_did(wired, registry) -> None:
    from swingdesk.presentation.report import render

    text = render(_run(wired, registry, held=["HELD.1"]))
    assert "CORRELATION" in text
    assert "risk.correlation_threshold" in text
    assert "60 shared session(s)" in text
    assert "refused        1" in text


def test_the_report_separates_unavailable_from_admitted(wired, registry) -> None:
    """The one distinction this block exists for. "Nothing was close" and "nothing could be
    measured" must never render the same (`AGENTS.md` §12)."""
    from swingdesk.presentation.report import render

    text = render(
        _run(wired, registry, held=["HELD.1"],
             candidate_sessions=_sessions(date(2025, 11, 1), date(2026, 1, 15)))
    )
    assert "UNAVAILABLE" in text
    assert "admitted UNCHECKED" in text


def test_the_report_says_so_when_the_book_was_never_read(wired, registry) -> None:
    from swingdesk.presentation.report import render

    bars, journal, _positions = wired
    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: _sessions()}))
    text = render(result)
    assert "the book was not read this run" in text
    assert "not the same claim as `these are independent`" in text


def test_the_fixture_paths_are_genuinely_different_bets(registry) -> None:
    """The premise every pipeline test above rests on, asserted rather than assumed.

    `conftest.make_bars` gives every instrument the same closes, so the whole suite would correlate
    at 1.00 and the admitting tests would be proving nothing. The zigzag path is what makes a
    fixture pair that is NOT the same bet, and if it ever stopped being one these tests would go
    green for the wrong reason.
    """
    sessions = _sessions()
    walk = correlation.daily_returns(series_for(TEST_US, sessions))
    zig = correlation.daily_returns(series_for(TEST_US, sessions, zigzag=True))

    assert correlation.measure(walk, walk, 60).r == Decimal(1)
    apart = correlation.measure(walk, zig, 60)
    assert apart.r is not None and abs(apart.r) < Decimal("0.10")
