"""The sector cap: the guard, the budget, and what the decision path does with them.

`DR-006` §2 requires an ETF to consume its constituents' sector budget rather than sitting outside
it - Appendix C's control cell, *count ETFs and correlations toward sector risk*. §3 called the
whole constraint unevaluable because `Instrument.sector` is `None`; §8.4 found the vendor serves
both the sector and the fund look-through, and that what is genuinely missing is only the
POINT-IN-TIME version, which restricts a backtest and not live admission.

**§8.7 is why the guard is tested first and at length.** The vendor answers `NEAR` - a
short-maturity bond fund with no equity sectors at all - as healthcare 100.0%, confidently and
wrongly. Consumed naively, one bond ETF spends an entire sector budget on a fiction. The guard is a
precondition of this feature, not a refinement of it, so it gets the first section here.

Same three failure directions as `test_correlation.py`, and they are kept apart for the same
reason: an UNSET cap refuses every candidate, an unclassifiable CANDIDATE is admitted unchecked,
and an unclassifiable POSITION makes the split understate without refusing anything.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tests.conftest import TEST_US, fixture_fetcher

from swingdesk.application.pipeline import run
from swingdesk.contracts.position import Position
from swingdesk.contracts.reference import Classification, SectorWeight
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data.classification import (
    ClassificationStore,
    Exposure,
    look_through,
)
from swingdesk.trade_management import portfolio
from swingdesk.trade_management.sizing import Refusal

AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
EARLIER = datetime(2026, 1, 2, 21, 0, tzinfo=UTC)

#: The authored cap, as `conftest.registry` carries it.
CAP = Decimal(2)

#: 1R in base currency at the fixture's equity (10,000) and risk percent (1.0).
R = Decimal(100)


def _sessions(start: date = date(2025, 1, 1), end: date = date(2026, 1, 15)) -> list[date]:
    return [s.session_date for s in cal.sessions(TEST_US.exchange, start, end)]


def _classification(
    instrument_id: str,
    quote_type: str = "EQUITY",
    weights: dict[str, str] | None = None,
    knowledge_time: datetime = EARLIER,
) -> Classification:
    return Classification(
        instrument_id=instrument_id,
        quote_type=quote_type,
        industry=None,
        weights=tuple(
            SectorWeight(sector=sector, weight=Decimal(value))
            for sector, value in (weights or {}).items()
        ),
        knowledge_time=knowledge_time,
    )


def _equity(instrument_id: str, sector: str, knowledge_time: datetime = EARLIER) -> Classification:
    return _classification(instrument_id, "EQUITY", {sector: "1"}, knowledge_time)


def _exposure(instrument_id: str, weights: dict[str, str]) -> Exposure:
    return look_through(_classification(instrument_id, "EQUITY", weights), instrument_id)


def _position(instrument: str, *, index: int = 1, shares: int = 50, stop: str = "96") -> Position:
    """Entry 100, stop 96, 50 shares -> open risk 200 = 2R at the fixture's 1R of 100."""
    return Position(
        position_id=f"POS-{index}", version=1, instrument_id=instrument,
        opened_on=date(2025, 12, 1), entry_price=Decimal(100), shares=shares,
        initial_stop=Decimal(stop), current_stop=Decimal(stop),
        initial_costs_per_share=Decimal("0.50"),
        knowledge_time=datetime(2025, 12, 1, tzinfo=UTC),
    )


def _usd_only(currency: str) -> tuple[Decimal, tuple[()]] | Refusal:
    if currency == "USD":
        return Decimal(1), ()
    return Refusal("RISK", f"no rate for {currency}", parameter_id="account.fx_rate_cad")


def _without(registry: ParameterRegistry, parameter_id: str) -> ParameterRegistry:
    entries = {pid: dict(entry) for pid, entry in registry._entries.items()}
    entries[parameter_id]["value"] = None
    return type(registry)(entries)


# ------------------------------------------------------------------ the guard (DR-006 §8.7)


def test_a_share_carries_its_own_sector_as_a_single_weight() -> None:
    """Not a look-through and not pretending to be one - it is the same quantity, which is what
    lets the budget add a share and an ETF without a special case."""
    exposure = look_through(_equity("AAA.1", "technology"), "AAA.1")
    assert exposure.is_available
    assert [(w.sector, w.weight) for w in exposure.weights] == [("technology", Decimal(1))]
    assert exposure.coverage == Decimal(1)


def test_a_genuine_fund_look_through_is_accepted() -> None:
    """The positive control for the guard. Without it, a guard that refused every fund would pass
    every negative test below - and would make the ETF half of `DR-006` §2 unenforceable."""
    exposure = look_through(
        _classification("SPY.1", "ETF", {"technology": "0.374", "financial services": "0.122",
                                         "communication services": "0.099"}),
        "SPY.1",
    )
    assert exposure.is_available
    assert exposure.coverage == Decimal("0.595")


def test_the_bond_fund_look_through_is_refused_and_not_consumed() -> None:
    """`NEAR` measured on 2026-08-22: healthcare 100.0%, every other sector 0.0%, on a
    short-maturity BOND fund with no equity sectors at all. Consumed naively it would spend an
    entire sector budget on a fiction, silently - which is worse than the check not existing."""
    exposure = look_through(
        _classification("NEAR.1", "ETF",
                        {"healthcare": "1", "technology": "0", "energy": "0"}),
        "NEAR.1",
    )
    assert not exposure.is_available
    assert exposure.weights == (), "a refused look-through must carry no weights to spend"
    assert exposure.unavailable is not None
    assert "healthcare" in exposure.unavailable and "degenerate" in exposure.unavailable


def test_the_degeneracy_test_is_exact_so_a_real_sector_etf_still_passes() -> None:
    """Exactness is load-bearing. A genuine sector ETF is legitimately almost all one sector, so a
    tolerance would refuse the instruments this cap most needs to see. The bond funds §8.7 measured
    come back at exactly 1 with every other sector at exactly 0."""
    almost = look_through(
        _classification("XLK.1", "ETF", {"technology": "0.998", "industrials": "0.002"}),
        "XLK.1",
    )
    assert almost.is_available, "a 99.8% technology fund is a real fund, not a vendor artefact"


def test_a_single_sector_equity_is_not_treated_as_a_degenerate_look_through() -> None:
    """The guard applies to FUNDS. An ordinary share at 100% of its own sector is the normal case
    and refusing it would make the cap unenforceable for every equity in the universe."""
    assert look_through(_equity("AAA.1", "energy"), "AAA.1").is_available


def test_no_stored_classification_is_unavailable_and_says_which_way() -> None:
    """`None` from the store means the store cannot answer - never that the instrument has no
    sector. The two render identically if the distinction is dropped, and only one is true."""
    exposure = look_through(None, "AAA.1")
    assert not exposure.is_available
    assert exposure.unavailable is not None
    assert "no classification is stored" in exposure.unavailable


def test_a_vendor_answer_with_no_sector_is_unavailable_rather_than_empty() -> None:
    exposure = look_through(_classification("IDX.1", "INDEX", {}), "IDX.1")
    assert not exposure.is_available
    assert exposure.unavailable is not None and "INDEX" in exposure.unavailable


def test_every_sector_at_zero_is_the_same_non_answer_as_no_sector() -> None:
    """The vendor returns the full sector list with every share zeroed more often than it returns
    an empty one. Left as "available with zero coverage" it would place none of the position's risk
    and report the book COMPLETE - a fabricated clean bill of health."""
    exposure = look_through(
        _classification("ETF.1", "ETF", {"technology": "0", "energy": "0"}), "ETF.1"
    )
    assert not exposure.is_available


# ------------------------------------------------------------------ the store


@pytest.fixture
def classifications(tmp_path):
    with ClassificationStore(tmp_path / "classifications.duckdb") as store:
        yield store


def test_the_store_round_trips_a_look_through(classifications) -> None:
    classifications.record([
        _classification("SPY.1", "ETF", {"technology": "0.374", "energy": "0.05"})
    ])
    stored = classifications.as_of("SPY.1", AS_OF)
    assert stored is not None
    assert stored.quote_type == "ETF"
    assert {w.sector: w.weight for w in stored.weights} == {
        "technology": Decimal("0.374000"), "energy": Decimal("0.050000"),
    }


def test_a_classification_learned_later_is_invisible_to_an_earlier_as_of(classifications) -> None:
    """The point-in-time gap ENCODED, not described. A replay before the first pull finds nothing
    and reports `unavailable`; it does not answer an older question with today's classification
    (`DR-006` §8.4 d)."""
    classifications.record([_equity("AAA.1", "technology", knowledge_time=AS_OF)])
    assert classifications.as_of("AAA.1", EARLIER) is None
    assert classifications.as_of("AAA.1", AS_OF) is not None


def test_a_reclassification_appends_and_the_latest_known_wins(classifications) -> None:
    """Append-only in the sense `BarStore` is: a sector that changed is a new row at a later
    knowledge time, never an update. It is the only evidence this project will ever hold about how
    its own classification drifted, because the vendor publishes no archive."""
    classifications.record([_equity("AAA.1", "technology", knowledge_time=EARLIER)])
    classifications.record([_equity("AAA.1", "energy", knowledge_time=AS_OF)])

    assert classifications.as_of("AAA.1", EARLIER).weights[0].sector == "technology"
    assert classifications.as_of("AAA.1", AS_OF).weights[0].sector == "energy"


def test_a_later_pull_reporting_fewer_sectors_does_not_leave_the_dropped_ones_standing(
    classifications
) -> None:
    """Re-recording at the SAME knowledge time is one answer being replaced, not two answers being
    merged. Without the clear, a fund that dropped a sector would keep it forever."""
    classifications.record([
        _classification("SPY.1", "ETF", {"technology": "0.4", "energy": "0.1"})
    ])
    classifications.record([_classification("SPY.1", "ETF", {"technology": "0.5"})])

    stored = classifications.as_of("SPY.1", AS_OF)
    assert [w.sector for w in stored.weights] == ["technology"]


def test_the_store_reports_what_it_can_answer_for(classifications) -> None:
    classifications.record([_equity("BBB.1", "energy"), _equity("AAA.1", "technology")])
    assert classifications.instrument_ids(AS_OF) == ("AAA.1", "BBB.1")
    assert classifications.instrument_ids(datetime(2025, 1, 1, tzinfo=UTC)) == ()


# ------------------------------------------------------------------ the parameter


def test_the_cap_is_read_from_the_registry(registry) -> None:
    assert portfolio.sector_limit(registry) == CAP


def test_an_unset_cap_refuses_and_names_itself(registry) -> None:
    with pytest.raises(ParameterUnset) as unset:
        portfolio.sector_limit(_without(registry, portfolio.MAX_SECTOR_RISK))
    assert unset.value.parameter_id == portfolio.MAX_SECTOR_RISK


# ------------------------------------------------------------------ the budget


def _book(
    *holdings: tuple[str, dict[str, str]], shares: int = 50, stop: str = "96"
) -> portfolio.SectorBook:
    """A priced book from `(instrument_id, weights)` pairs. Each position is 2R by default."""
    exposures = {
        instrument_id: _exposure(instrument_id, weights)
        for instrument_id, weights in holdings
    }
    priced = portfolio.sector_book(
        [
            _position(instrument_id, index=index + 1, shares=shares, stop=stop)
            for index, (instrument_id, _) in enumerate(holdings)
        ],
        _usd_only,
        R,
        lambda instrument_id: exposures[instrument_id],
    )
    assert isinstance(priced, portfolio.SectorBook)
    return priced


def test_an_empty_book_places_nothing_and_is_complete() -> None:
    book = portfolio.sector_book([], _usd_only, R, lambda _id: _exposure(_id, {}))
    assert isinstance(book, portfolio.SectorBook)
    assert book.by_sector == {} and book.total_r == 0
    assert book.is_complete, "an empty book is fully attributed, not partially unknown"


def test_a_share_puts_all_its_risk_in_one_sector() -> None:
    book = _book(("AAA.1", {"technology": "1"}))
    assert book.by_sector == {"technology": Decimal(2)}
    assert book.total_r == Decimal(2) and book.is_complete


def test_an_etf_spreads_its_risk_across_its_constituents_sectors() -> None:
    """Appendix C's control cell in arithmetic: an ETF consumes its constituents' sector budget
    rather than sitting outside it."""
    book = _book(("SPY.1", {"technology": "0.4", "financial services": "0.6"}))
    assert book.by_sector == {
        "financial services": Decimal("1.2"), "technology": Decimal("0.8"),
    }
    assert book.is_complete


def test_a_share_and_an_etf_add_in_the_same_sector() -> None:
    book = _book(("AAA.1", {"technology": "1"}), ("SPY.1", {"technology": "0.5", "energy": "0.5"}))
    assert book.by_sector["technology"] == Decimal(3)
    assert book.by_sector["energy"] == Decimal(1)


def test_a_partial_look_through_spends_what_it_reports_and_no_more() -> None:
    """Not normalised. Normalising invents composition the vendor did not report; dropping the
    position hides exposure that was measured. The remainder is carried visibly instead."""
    book = _book(("SPY.1", {"technology": "0.4", "energy": "0.1"}))
    assert book.by_sector == {"energy": Decimal("0.2"), "technology": Decimal("0.8")}
    assert book.unclassified_r == Decimal("1.0")
    assert not book.is_complete


def test_an_unclassifiable_position_is_counted_apart_from_the_sectors() -> None:
    priced = portfolio.sector_book(
        [_position("AAA.1")], _usd_only, R, lambda instrument_id: look_through(None, instrument_id)
    )
    assert isinstance(priced, portfolio.SectorBook)
    assert priced.by_sector == {}
    assert priced.total_r == Decimal(2), "the risk is still real, it just has no sector"
    assert len(priced.unmeasured) == 1 and not priced.is_complete
    assert priced.unmeasured_r == Decimal(2)
    assert priced.unclassified_r == Decimal(0), (
        "a position that could not be CLASSIFIED is not the same gap as a partial look-through, "
        "and merging them makes one number that answers neither question"
    )


def test_the_two_kinds_of_gap_are_reported_apart() -> None:
    """One unclassifiable position and one partial look-through, in the same book.

    The reason must name both quantities. It printed a fixed sentence until 2026-08-23, so a book
    with an unclassifiable position and NO partial look-through read "0.00R sits in no sector" -
    a zero offering reassurance about the wrong quantity, next to 2R nobody could place.
    """
    exposures = {
        "AAA.1": look_through(None, "AAA.1"),
        "SPY.1": _exposure("SPY.1", {"technology": "0.5"}),
    }
    priced = portfolio.sector_book(
        [_position("AAA.1", index=1), _position("SPY.1", index=2)],
        _usd_only, R, lambda instrument_id: exposures[instrument_id],
    )
    assert isinstance(priced, portfolio.SectorBook)
    assert priced.unmeasured_r == Decimal(2)
    assert priced.unclassified_r == Decimal(1)

    reason = portfolio.assess_sector(
        priced, CAP, _exposure("CCC.1", {"energy": "1"}), Decimal("0.5")
    ).reason
    assert "holding 2.00R could not be classified" in reason
    assert "1.00R sits in no sector from partial look-throughs" in reason


def test_the_split_is_sorted_so_two_runs_read_alike() -> None:
    book = _book(("AAA.1", {"utilities": "0.5", "energy": "0.3", "technology": "0.2"}))
    assert list(book.by_sector) == sorted(book.by_sector)


def test_a_book_that_cannot_be_totalled_refuses_and_names_the_position(registry) -> None:
    """The same FX rule the book cap follows. Adding CAD to USD to keep the run moving is the
    substitution `AGENTS.md` §3 forbids by name."""
    from swingdesk.trade_management.sizing import to_base_currency

    priced = portfolio.sector_book(
        [_position("TEST.2.TO")],
        lambda currency: to_base_currency(currency, registry),
        R,
        lambda instrument_id: _exposure(instrument_id, {"energy": "1"}),
    )
    assert isinstance(priced, Refusal)
    assert priced.parameter_id == "account.fx_rate_cad"
    assert "POS-1" in priced.reason


def test_sector_risk_cannot_be_measured_when_one_r_is_not_positive() -> None:
    priced = portfolio.sector_book([], _usd_only, Decimal(0), lambda _id: _exposure(_id, {}))
    assert isinstance(priced, Refusal) and priced.code == "RISK"


# ------------------------------------------------------------------ the verdict


def test_a_candidate_inside_the_budget_is_admitted() -> None:
    """The positive control. Without it every refusal below would pass on a cap that refused
    unconditionally."""
    verdict = portfolio.assess_sector(
        _book(("AAA.1", {"technology": "1"})), CAP,
        _exposure("BBB.1", {"energy": "1"}), Decimal("0.5"),
    )
    assert verdict.admitted and verdict.binding is None
    assert "energy" in verdict.reason


def test_a_candidate_that_would_pass_the_cap_in_one_sector_is_refused() -> None:
    verdict = portfolio.assess_sector(
        _book(("AAA.1", {"technology": "1"})), CAP,
        _exposure("BBB.1", {"technology": "1"}), Decimal("0.5"),
    )
    assert not verdict.admitted and verdict.binding == "technology"
    assert "2.50R in technology" in verdict.reason
    assert "already carries 2.00R" in verdict.reason


def test_the_cap_binds_at_the_value_itself_not_above_it() -> None:
    """`>`, as this arithmetic is worded: 2R exactly is inside the cap and a hair past it is not.
    Tested ON the boundary, because an off-by-one there is invisible in every test that stays away
    from it."""
    book = _book(("AAA.1", {"technology": "1"}))   # 2.00R in technology, exactly the cap
    exactly = portfolio.assess_sector(book, CAP, _exposure("B.1", {"technology": "0"}), Decimal(1))
    assert exactly.admitted, "a candidate adding nothing to a sector at the cap still fits"

    over = portfolio.assess_sector(
        book, CAP, _exposure("B.1", {"technology": "0.01"}), Decimal(1)
    )
    assert not over.admitted, "0.01R past the cap must refuse"


def test_an_etf_candidate_is_measured_through_its_weights_not_by_a_label() -> None:
    """A broad fund spends a little of every sector and clears a book a pure-technology name of the
    same size would not. That contrast IS the look-through requirement - both halves are asserted,
    because either alone is satisfied by a cap that ignores weights entirely."""
    book = _book(("AAA.1", {"technology": "1"}), stop="97")   # 1.50R technology

    pure = portfolio.assess_sector(
        book, CAP, _exposure("BBB.1", {"technology": "1"}), Decimal(1)
    )
    assert not pure.admitted, "1.50R + 1.00R is 2.50R, past the 2R cap"

    broad = portfolio.assess_sector(
        book, CAP, _exposure("SPY.1", {"technology": "0.3", "energy": "0.7"}), Decimal(1)
    )
    assert broad.admitted, "the same 1R through a 30%-technology fund is 1.80R, inside it"
    assert broad.projected("technology") == Decimal("1.8")
    assert broad.projected("energy") == Decimal("0.7")


def test_the_worst_sector_binds_when_two_would_go_over() -> None:
    """The reason names one sector, and it must name the strongest cause. A refusal with two causes
    is a refusal an owner cannot answer."""
    book = _book(("AAA.1", {"technology": "0.5", "energy": "0.5"}))   # 1R each
    verdict = portfolio.assess_sector(
        book, CAP, _exposure("BBB.1", {"technology": "0.4", "energy": "0.6"}), Decimal(3)
    )
    assert not verdict.admitted
    assert verdict.binding == "energy", f"expected the heavier sector, got {verdict.binding}"


def test_an_unclassifiable_candidate_is_admitted_unchecked() -> None:
    """`DR-006` §3: a check the system could not perform must not fail closed into a blanket
    refusal. A sector cap that refused every unclassified name would refuse the whole universe on
    the day the store was created."""
    verdict = portfolio.assess_sector(
        _book(("AAA.1", {"technology": "1"})), CAP, look_through(None, "BBB.1"), Decimal(5)
    )
    assert verdict.admitted, "a gap in the SYSTEM must not refuse the trade"
    assert verdict.is_unavailable
    assert verdict.reason.startswith("UNAVAILABLE")


def test_an_incomplete_book_admits_and_says_the_split_understates() -> None:
    """The dangerous middle. Unattributed risk makes every sector figure an understatement, which
    is the PERMISSIVE direction, so it can never be silent."""
    priced = portfolio.sector_book(
        [_position("AAA.1", index=1), _position("BBB.1", index=2)],
        _usd_only, R,
        lambda instrument_id: (
            _exposure(instrument_id, {"technology": "1"}) if instrument_id == "AAA.1"
            else look_through(None, instrument_id)
        ),
    )
    assert isinstance(priced, portfolio.SectorBook)
    verdict = portfolio.assess_sector(
        priced, CAP, _exposure("CCC.1", {"energy": "1"}), Decimal("0.5")
    )
    assert verdict.admitted and not verdict.is_unavailable
    assert "could not be classified" in verdict.reason
    assert "understates" in verdict.reason


# ------------------------------------------------------------------ through the pipeline


@pytest.fixture
def wired(tmp_path):
    with (
        BarStore(tmp_path / "bars.duckdb") as bars,
        Journal(tmp_path / "journal.duckdb") as journal,
        PositionStore(tmp_path / "positions.duckdb") as positions,
        ClassificationStore(tmp_path / "classifications.duckdb") as sectors,
    ):
        yield bars, journal, positions, sectors


def _run(wired, registry, *, held: list[str] = (),
         sectors: dict[str, Classification] | None = None, with_store: bool = True):
    bars, journal, positions, classifications = wired
    for index, instrument_id in enumerate(held):
        # 0.10R each, so the BOOK cap never binds first and the sector check is what is exercised.
        positions.record(_position(instrument_id, index=index + 1, shares=10, stop="99"))
    if sectors:
        classifications.record(sectors.values())
    sessions = _sessions()
    by_instrument = {instrument_id: sessions for instrument_id in held}
    by_instrument[TEST_US.id] = sessions
    return run(
        [TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
        positions=positions,
        classifications=classifications if with_store else None,
        # Every held name on the alternating path, so the CORRELATION cap - which runs one step
        # earlier - never refuses first and hides what this file is testing.
        fetcher=fixture_fetcher(by_instrument, zigzag=set(held)),
    )


def test_the_run_reads_the_store_and_places_held_risk_in_its_sector(wired, registry) -> None:
    """The wiring, asserted on the arithmetic the run actually did rather than on a verdict.

    Two held positions at 0.10R each in the same sector: the store is read, both are classified,
    and their risk lands together. The candidate fits, so no refusal is proven here - that is
    `test_a_full_sector_refuses_the_candidate`, one test down.
    """
    result = _run(
        wired, registry, held=["HELD.1", "HELD.2"],
        sectors={
            "HELD.1": _equity("HELD.1", "technology"),
            "HELD.2": _equity("HELD.2", "technology"),
            TEST_US.id: _equity(TEST_US.id, "technology"),
        },
    )
    outcome = result.outcomes[0]
    assert outcome.sector is not None
    assert outcome.sector.book.by_sector == {"technology": Decimal("0.2")}
    assert outcome.sector.book.is_complete, "both positions were classified, so nothing understates"
    assert outcome.decision.decision == "Watch"


def test_a_full_sector_refuses_the_candidate(wired, registry) -> None:
    bars, journal, positions, classifications = wired
    # 2.00R already in technology: one position of 50 shares with a 4-point stop.
    positions.record(_position("HELD.1", index=1, shares=50, stop="96"))
    classifications.record([
        _equity("HELD.1", "technology"), _equity(TEST_US.id, "technology"),
    ])
    sessions = _sessions()
    result = run(
        [TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
        positions=positions, classifications=classifications,
        fetcher=fixture_fetcher({TEST_US.id: sessions, "HELD.1": sessions}, zigzag={"HELD.1"}),
    )

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip" and decision.reason_code == "RISK"
    assert "technology" in decision.reason
    assert decision.parameter_id is None, (
        "a full sector is a fact about the account, not an unset threshold"
    )


def test_a_different_sector_lets_the_candidate_through(wired, registry) -> None:
    """The positive control through the whole run. Without it the test above passes on a pipeline
    that refuses every candidate whose book holds anything at all."""
    bars, journal, positions, classifications = wired
    positions.record(_position("HELD.1", index=1, shares=50, stop="96"))
    classifications.record([_equity("HELD.1", "technology"), _equity(TEST_US.id, "energy")])
    sessions = _sessions()
    result = run(
        [TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
        positions=positions, classifications=classifications,
        fetcher=fixture_fetcher({TEST_US.id: sessions, "HELD.1": sessions}, zigzag={"HELD.1"}),
    )

    outcome = result.outcomes[0]
    assert outcome.decision.decision == "Watch"
    assert outcome.sector is not None and outcome.sector.admitted
    assert outcome.sector.book.by_sector == {"technology": Decimal(2)}


def test_without_a_classification_store_every_candidate_is_admitted_unchecked(
    wired, registry
) -> None:
    """Production's own state until `tools/refresh_classifications.py` has run, and it must read as
    `unavailable` rather than as an empty book with nothing in any sector."""
    result = _run(wired, registry, held=["HELD.1"], with_store=False)

    outcome = result.outcomes[0]
    assert outcome.decision.decision == "Watch"
    assert outcome.sector is not None and outcome.sector.is_unavailable
    assert "no classification store" in outcome.sector.candidate.unavailable


def test_an_unset_cap_refuses_every_candidate_and_names_the_parameter(wired, registry) -> None:
    """The opposite direction from `unavailable`, and the pair this file exists to keep apart."""
    result = _run(wired, _without(registry, portfolio.MAX_SECTOR_RISK), held=["HELD.1"])

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip" and decision.reason_code == "RISK"
    assert decision.parameter_id == portfolio.MAX_SECTOR_RISK
    assert isinstance(result.sector_limit, Refusal)


def test_a_degenerate_look_through_admits_unchecked_rather_than_spending_the_budget(
    wired, registry
) -> None:
    """§8.7 end to end. A bond fund the vendor calls healthcare 100% must not consume the healthcare
    budget - and must not refuse either. It is `unavailable`, and it is loud."""
    bars, journal, positions, classifications = wired
    positions.record(_position("NEAR.1", index=1, shares=50, stop="96"))   # 2.00R
    classifications.record([
        _classification("NEAR.1", "ETF", {"healthcare": "1", "technology": "0"}),
        _equity(TEST_US.id, "healthcare"),
    ])
    sessions = _sessions()
    result = run(
        [TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
        positions=positions, classifications=classifications,
        fetcher=fixture_fetcher({TEST_US.id: sessions, "NEAR.1": sessions}, zigzag={"NEAR.1"}),
    )

    outcome = result.outcomes[0]
    assert outcome.decision.decision == "Watch", "the guard must not refuse the candidate"
    assert outcome.sector is not None
    assert outcome.sector.book.by_sector == {}, (
        "the bond fund must spend NO healthcare budget - that is the fiction the guard stops"
    )
    assert len(outcome.sector.book.unmeasured) == 1
    assert not outcome.sector.book.is_complete


def test_the_output_hash_moves_when_a_sector_fills(wired, registry, tmp_path) -> None:
    """Two runs the owner could act on differently must not hash alike."""
    bars, journal, positions, classifications = wired
    positions.record(_position("HELD.1", index=1, shares=50, stop="96"))
    classifications.record([_equity("HELD.1", "technology"), _equity(TEST_US.id, "energy")])
    sessions = _sessions()
    admitted = run(
        [TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
        positions=positions, classifications=classifications,
        fetcher=fixture_fetcher({TEST_US.id: sessions, "HELD.1": sessions}, zigzag={"HELD.1"}),
    ).manifest.output_hash

    with (
        BarStore(tmp_path / "b2.duckdb") as bars2,
        Journal(tmp_path / "j2.duckdb") as journal2,
        PositionStore(tmp_path / "p2.duckdb") as positions2,
        ClassificationStore(tmp_path / "c2.duckdb") as classifications2,
    ):
        positions2.record(_position("HELD.1", index=1, shares=50, stop="96"))
        classifications2.record([
            _equity("HELD.1", "technology"), _equity(TEST_US.id, "technology"),
        ])
        refused = run(
            [TEST_US], FixedClock(AS_OF), registry, bars2, journal2, mode=RunMode.LIVE_AS_OF,
            positions=positions2, classifications=classifications2,
            fetcher=fixture_fetcher({TEST_US.id: sessions, "HELD.1": sessions},
                                    zigzag={"HELD.1"}),
        ).manifest.output_hash

    assert admitted != refused


# ------------------------------------------------------------------ the report


def test_the_report_prints_the_split_and_the_cap(wired, registry) -> None:
    from swingdesk.presentation.report import render

    bars, journal, positions, classifications = wired
    positions.record(_position("HELD.1", index=1, shares=50, stop="96"))
    classifications.record([_equity("HELD.1", "technology"), _equity(TEST_US.id, "energy")])
    sessions = _sessions()
    text = render(run(
        [TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
        positions=positions, classifications=classifications,
        fetcher=fixture_fetcher({TEST_US.id: sessions, "HELD.1": sessions}, zigzag={"HELD.1"}),
    ))

    assert "SECTOR" in text
    assert "risk.max_sector_risk" in text
    assert "technology" in text and "2.00R" in text
    assert "AT OR PAST THE CAP" in text


def test_the_report_says_when_nothing_could_be_classified(wired, registry) -> None:
    from swingdesk.presentation.report import render

    text = render(_run(wired, registry, held=["HELD.1"], with_store=False))
    assert "could not be placed at all" in text
    assert "UNDERSTATES" in text
    assert "admitted UNCHECKED" in text
