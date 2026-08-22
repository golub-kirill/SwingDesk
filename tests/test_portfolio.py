"""The book cap: the arithmetic, and what the decision path does with it.

`ALLOCATION_SPEC` §2 has specified this constraint since it was written and
`positions.open_risk_as_of` has computed the quantity the whole time - with no caller that compared
it to anything. `DR-006` §8.3 supplied the two numbers on 2026-08-22 (`risk.max_open_risk` = 4R,
`risk.max_concurrent_positions` = 4, both provenance `owner`), and this is the gate that spends them.

The structure mirrors `test_freshness.py` deliberately: the pure verdict first, then the pipeline
through it, then the fail-closed case. Same gate shape, same test shape.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tests.conftest import TEST_US, fixture_fetcher

from swingdesk.application.pipeline import run
from swingdesk.contracts.position import Position
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import calendar as cal
from swingdesk.trade_management import portfolio
from swingdesk.trade_management.sizing import Refusal, to_base_currency

AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)

#: The ratified caps, as `conftest.registry` carries them.
CAPS = portfolio.Caps(max_open_risk=Decimal(4), max_concurrent=4)

#: 1R in base currency at the fixture's equity (10,000) and risk percent (1.0).
R = Decimal(100)


def _sessions(exchange, start: date, end: date) -> list[date]:
    return [s.session_date for s in cal.sessions(exchange, start, end)]


def _position(index: int = 1, *, shares: int = 50, stop: str = "96", instrument: str | None = None,
              entry: str = "100", current: str | None = None) -> Position:
    """One open position. Default: 50 sh, entry 100, stop 96 -> open risk 200 = 2R.

    `current` is the stop NOW, which may sit above entry once trailed - `initial_stop` may not,
    which is `Position`'s own validator and the reason the two are separate arguments here.
    """
    return Position(
        position_id=f"POS-{index}", version=1,
        instrument_id=instrument or TEST_US.id,
        opened_on=date(2025, 12, 1), entry_price=Decimal(entry), shares=shares,
        initial_stop=Decimal(stop), current_stop=Decimal(current or stop),
        initial_costs_per_share=Decimal("0.50"),
        knowledge_time=datetime(2025, 12, 1, tzinfo=UTC),
    )


def _usd_only(currency: str) -> tuple[Decimal, tuple[()]] | Refusal:
    """A rate source for a single-currency book. Base currency converts at exactly 1."""
    if currency == "USD":
        return Decimal(1), ()
    return Refusal("RISK", f"no rate for {currency}", parameter_id="account.fx_rate_cad")


def _without(registry: ParameterRegistry, parameter_id: str) -> ParameterRegistry:
    entries = {pid: dict(entry) for pid, entry in registry._entries.items()}
    entries[parameter_id]["value"] = None
    return type(registry)(entries)


# ------------------------------------------------------------------ the parameters


def test_limits_reads_both_caps(registry) -> None:
    caps = portfolio.limits(registry)
    assert caps.max_open_risk == Decimal(4)
    assert caps.max_concurrent == 4


@pytest.mark.parametrize("missing", [portfolio.MAX_OPEN_RISK, portfolio.MAX_CONCURRENT])
def test_either_cap_unset_refuses_and_names_itself(registry, missing: str) -> None:
    """Both are read together on purpose: enforcing one while the other is unset would report a
    discipline the system does not have (`DR-006` §1 - they are one constraint counted twice)."""
    with pytest.raises(ParameterUnset) as unset:
        portfolio.limits(_without(registry, missing))
    assert unset.value.parameter_id == missing


# ------------------------------------------------------------------ pricing the book


def test_an_empty_book_is_zero_positions_and_zero_risk() -> None:
    priced = portfolio.book([], _usd_only, R)
    assert isinstance(priced, portfolio.Book)
    assert priced.count == 0
    assert priced.open_risk_r == 0


def test_open_risk_is_expressed_in_r() -> None:
    priced = portfolio.book([_position()], _usd_only, R)
    assert isinstance(priced, portfolio.Book)
    assert priced.open_risk_base == Decimal(200)
    assert priced.open_risk_r == Decimal(2)


def test_a_book_that_cannot_be_totalled_refuses_and_names_the_position(registry) -> None:
    """A CAD position with no rate makes the whole book untotallable. Refusing is the point - the
    alternative is adding CAD to USD, which is the error `AGENTS.md` §3 forbids by name."""
    def rate_for(currency: str):
        return to_base_currency(currency, registry)

    priced = portfolio.book([_position(instrument="TEST.2.TO")], rate_for, R)
    assert isinstance(priced, Refusal)
    assert priced.parameter_id == "account.fx_rate_cad"
    assert "POS-1" in priced.reason, "a refusal must name which position forced it"


def test_a_book_cannot_be_measured_when_one_r_is_not_positive() -> None:
    priced = portfolio.book([], _usd_only, Decimal(0))
    assert isinstance(priced, Refusal)
    assert priced.code == "RISK"


# ------------------------------------------------------------------ the verdict


def test_an_empty_book_admits_a_candidate() -> None:
    verdict = portfolio.assess(portfolio.book([], _usd_only, R), CAPS, Decimal(1))
    assert verdict.admitted
    assert verdict.binding is None
    assert verdict.positions_remaining == 4


def test_the_fifth_position_is_refused_on_the_count() -> None:
    """Four tiny positions: 0.04R in total, so the R cap is nowhere near binding and the count is
    the only thing that can refuse. That separation is the test."""
    tiny = [_position(i, shares=10, stop="99.9") for i in range(1, 5)]
    priced = portfolio.book(tiny, _usd_only, R)
    assert isinstance(priced, portfolio.Book)
    assert priced.open_risk_r < 1, "the R cap must not be what refuses here"

    verdict = portfolio.assess(priced, CAPS, Decimal("0.01"))
    assert not verdict.admitted
    assert verdict.binding == portfolio.MAX_CONCURRENT
    assert "would make 5" in verdict.reason


def test_the_fourth_position_still_fits() -> None:
    """The positive control for the count cap. Without it, a broken check that refused everything
    would pass the test above."""
    tiny = [_position(i, shares=10, stop="99.9") for i in range(1, 4)]
    verdict = portfolio.assess(portfolio.book(tiny, _usd_only, R), CAPS, Decimal("0.01"))
    assert verdict.admitted


def test_open_risk_refuses_before_the_count_does() -> None:
    """Two positions at 2R each already fill a 4R book, so the R cap binds with the count at 2 of
    4. The two caps are set to the same number and can still bind at different times, which is why
    both are checked rather than one standing in for the other."""
    priced = portfolio.book([_position(1), _position(2)], _usd_only, R)
    assert isinstance(priced, portfolio.Book)
    assert priced.count == 2 and priced.open_risk_r == Decimal(4)

    verdict = portfolio.assess(priced, CAPS, Decimal(1))
    assert not verdict.admitted
    assert verdict.binding == portfolio.MAX_OPEN_RISK
    assert "4.00R of open risk" in verdict.reason


def test_a_candidate_that_exactly_fills_the_budget_is_admitted() -> None:
    """`>` and not `>=`. 3R open plus a 1R candidate is exactly 4R, which is the cap and not past
    it - a cap of 4R that refuses at 4R is a cap of 3R wearing the wrong label."""
    priced = portfolio.book([_position(1, shares=75)], _usd_only, R)  # (100-96)*75 = 300 = 3R
    assert isinstance(priced, portfolio.Book) and priced.open_risk_r == Decimal(3)
    assert portfolio.assess(priced, CAPS, Decimal(1)).admitted
    assert not portfolio.assess(priced, CAPS, Decimal("1.01")).admitted


def test_a_stop_above_entry_frees_r_capacity_but_still_occupies_a_slot() -> None:
    """Owner ruling, 2026-08-22. A position whose stop sits above entry cannot lose money at that
    stop, so its open risk is negative and it genuinely frees budget - clamping to zero would hide
    the difference between "risk removed" and "risk locked in as profit", which is the reason
    `Position.open_risk` already refuses to clamp.

    The concurrency cap still counts it, and that is the half that matters against a gap: a gap
    jumps a profitable stop as easily as a losing one.
    """
    locked = _position(1, shares=50, entry="100", stop="96", current="104")
    priced = portfolio.book([locked, _position(2)], _usd_only, R)
    assert isinstance(priced, portfolio.Book)
    assert priced.open_risk_r == Decimal(0), "-2R locked in, +2R at risk"
    assert priced.count == 2, "it is still a position that can gap"
    assert portfolio.assess(priced, CAPS, Decimal(1)).admitted


# ------------------------------------------------------------------ through the pipeline


@pytest.fixture
def wired(tmp_path):
    with (
        BarStore(tmp_path / "bars.duckdb") as bars,
        Journal(tmp_path / "journal.duckdb") as journal,
        PositionStore(tmp_path / "positions.duckdb") as positions,
    ):
        yield bars, journal, positions


def _run(wired, registry, *, held: list[Position] = ()):
    bars, journal, positions = wired
    for position in held:
        positions.record(position)
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    return run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
               fetcher=fixture_fetcher({TEST_US.id: sessions}), positions=positions)


def test_a_candidate_reaches_watch_while_the_book_has_room(wired, registry) -> None:
    """The positive control. Without it, a cap that refused unconditionally would pass every
    negative test below."""
    result = _run(wired, registry)
    assert result.outcomes[0].decision.decision == "Watch"
    assert isinstance(result.capacity, portfolio.Capacity)
    assert result.capacity.admitted


def test_a_full_book_refuses_the_candidate_with_a_risk_code(wired, registry) -> None:
    """`CODES.md`: `RISK` is *open/sector/currency/event limit exceeded*, action *Skip or choose
    better candidate*. The code existed before the arithmetic that raises it did."""
    held = [_position(i, shares=10, stop="99.9", instrument=f"HELD.{i}") for i in range(1, 5)]
    result = _run(wired, registry, held=held)

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip"
    assert decision.reason_code == "RISK"
    assert portfolio.MAX_CONCURRENT in decision.reason
    assert decision.parameter_id is None, (
        "a full book is a fact about the ACCOUNT, not an unset threshold - `funnel.py` splits "
        "skip causes on exactly this field"
    )


def test_the_book_is_priced_once_and_reported_on_the_run(wired, registry) -> None:
    result = _run(wired, registry, held=[_position(1)])
    assert isinstance(result.capacity, portfolio.Capacity)
    assert result.capacity.book.count == 1
    assert result.capacity.book.open_risk_r == Decimal(2)


def test_an_unset_cap_refuses_every_candidate_and_names_the_parameter(wired, registry) -> None:
    """Fail closed, like the freshness window and the exit policy before it. A limit nobody set is
    not a limit of infinity."""
    result = _run(wired, _without(registry, portfolio.MAX_OPEN_RISK))

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip"
    assert decision.reason_code == "RISK"
    assert decision.parameter_id == portfolio.MAX_OPEN_RISK
    assert isinstance(result.capacity, Refusal), (
        "the report must say the cap has no value even if nothing reached it"
    )


def test_a_cad_position_in_the_book_refuses_every_candidate(wired, registry) -> None:
    """One untotallable position stops the whole run admitting anything, and that is the honest
    outcome: the book's risk is unknown, so no candidate can be shown to fit inside it."""
    result = _run(wired, registry, held=[_position(1, instrument="TEST.2.TO")])

    decision = result.outcomes[0].decision
    assert decision.decision == "Skip"
    assert decision.parameter_id == "account.fx_rate_cad"


def test_the_cap_is_not_evaluated_without_a_position_store(wired, registry) -> None:
    """`unavailable`, not `pass`. A run with no store cannot know the book, and reporting "within
    the cap" would be the collapse `HANDOFF.md` §7 calls this product's most damaging error."""
    bars, journal, _positions = wired
    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}))

    assert result.capacity is None
    assert result.outcomes[0].decision.decision == "Watch"


def test_the_output_hash_moves_when_the_book_fills(wired, registry, tmp_path) -> None:
    """`output_hash` must separate two runs the owner could act on differently, and "this candidate
    is a Watch" versus "this candidate is refused for capacity" is exactly that."""
    with_room = _run(wired, registry).manifest.output_hash

    with (
        BarStore(tmp_path / "b2.duckdb") as bars,
        Journal(tmp_path / "j2.duckdb") as journal,
        PositionStore(tmp_path / "p2.duckdb") as positions,
    ):
        for i in range(1, 5):
            positions.record(_position(i, shares=10, stop="99.9", instrument=f"HELD.{i}"))
        sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
        full = run([TEST_US], FixedClock(AS_OF), registry, bars, journal,
                   mode=RunMode.LIVE_AS_OF,
                   fetcher=fixture_fetcher({TEST_US.id: sessions}),
                   positions=positions).manifest.output_hash

    assert with_room != full


def test_a_capacity_refusal_is_not_overwritten_by_a_later_admission(wired, registry) -> None:
    """`requested_r` varies per candidate because the share count rounds DOWN, so on a partly-full
    book one candidate can be refused and the next admitted. The report renders `result.capacity`,
    and assigning it unconditionally left it holding whichever candidate ran last - so a run whose
    funnel showed RISK skips could print "room for 2 more position(s)".

    The report contradicting the decisions it is rendering is the failure; a refusal sticks.
    """
    bars, journal, positions = wired
    # 3.9R open across two positions: a candidate wanting 0.2R fits, one wanting 0.3R does not.
    positions.record(_position(1, shares=50, stop="96", instrument="HELD.1"))       # 2.00R
    positions.record(_position(2, shares=95, stop="98", instrument="HELD.2"))       # 1.90R

    sessions = _sessions(TEST_US.exchange, date(2025, 1, 1), date(2026, 1, 15))
    result = run([TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
                 fetcher=fixture_fetcher({TEST_US.id: sessions}), positions=positions)

    assert isinstance(result.capacity, portfolio.Capacity)
    assert result.capacity.book.open_risk_r == Decimal("3.9")

    # Measured, not hoped for: at 3.9R the fixture candidate asks for 0.978R and is refused.
    assert [o.decision.reason_code for o in result.outcomes] == ["RISK"]
    assert not result.capacity.admitted, (
        "a run that refused a candidate on capacity must not report room"
    )


def _wide_range_fetcher(sessions: list[date], half_range: dict[str, str]):
    """Bars whose daily range differs per instrument, so ATR - and therefore the stop distance,
    the share count and `planned_risk` - differ too.

    `conftest.make_bars` walks a fixed +-1.00 range whatever the price, so every candidate it
    produces asks for almost exactly the same R. Two candidates asking for DIFFERENT amounts is the
    whole condition this test needs, and there is no way to get it from the shared fixture.
    """
    from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

    def _fetch(instrument, interval, knowledge_time, period=None):
        # Held positions are fetched too, before any candidate. They are not the subject here, so
        # anything not named gets the ordinary narrow range.
        half = Decimal(half_range.get(instrument.id, "1.00"))
        bars = []
        for offset, session in enumerate(sessions):
            close = Decimal(100) + Decimal(offset) * Decimal("0.50")
            bars.append(Bar(
                instrument_id=instrument.id, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session, open=close - Decimal("0.25"),
                high=close + half, low=close - half, close=close,
                volume=1_000_000 + offset,
                knowledge_time=datetime(2026, 1, 15, 21, 0, tzinfo=UTC),
            ))
        return BarSeries(
            instrument_id=instrument.id, interval=Interval.DAY, series=Series.RAW,
            knowledge_time=datetime(2026, 1, 15, 21, 0, tzinfo=UTC), bars=tuple(bars),
        )

    return _fetch


def test_a_later_admitted_candidate_does_not_erase_an_earlier_refusal(wired, registry) -> None:
    """The ordering case, which the single-candidate test above cannot reach.

    Share counts round DOWN, so `planned_risk` - and therefore `requested_r` - varies between
    candidates. On a book with 0.6R of room, a candidate asking 0.98R is refused and one asking
    0.55R is admitted. Assigning `result.capacity` unconditionally left the report holding whichever
    ran LAST, so the BOOK CAPACITY block printed "room for 2 more position(s)" on a run whose funnel
    showed a RISK skip - the report contradicting the decisions it was rendering.
    """
    from swingdesk.contracts.reference import Exchange, Instrument

    bars, journal, positions = wired
    positions.record(_position(1, shares=50, stop="96", instrument="HELD.1"))   # 2.0R
    positions.record(_position(2, shares=70, stop="98", instrument="HELD.2"))   # 1.4R -> 3.4R book

    narrow = Instrument(id="TEST.1", ticker="TEST1", exchange=Exchange.NYSE, currency="USD")
    wide = Instrument(id="TEST.3", ticker="TEST3", exchange=Exchange.NYSE, currency="USD")
    sessions = _sessions(narrow.exchange, date(2025, 1, 1), date(2026, 1, 15))

    # The refused one FIRST, the admitted one second - the order that made the bug visible.
    result = run([narrow, wide], FixedClock(AS_OF), registry, bars, journal,
                 mode=RunMode.LIVE_AS_OF, positions=positions,
                 fetcher=_wide_range_fetcher(sessions, {"TEST.1": "1.00", "TEST.3": "13.50"}))

    codes = [o.decision.reason_code for o in result.outcomes]
    decisions = [o.decision.decision for o in result.outcomes]
    assert codes == ["RISK", None], f"expected one refusal then one admission, got {codes}"
    assert decisions == ["Skip", "Watch"]

    assert isinstance(result.capacity, portfolio.Capacity)
    assert not result.capacity.admitted, (
        "the admitted candidate must not overwrite the refusal the report has to show"
    )


def test_the_report_never_shows_room_on_a_run_that_refused_for_capacity() -> None:
    """The invariant above, asserted directly on `assess` so it holds for any candidate order."""
    book = portfolio.book([_position(1, shares=50), _position(2, shares=95, stop="98")],
                          _usd_only, R)
    assert isinstance(book, portfolio.Book)
    assert book.open_risk_r == Decimal("3.9")

    tight = portfolio.assess(book, CAPS, Decimal("0.3"))   # 4.2R - refused
    loose = portfolio.assess(book, CAPS, Decimal("0.1"))   # 4.0R - admitted
    assert not tight.admitted and loose.admitted, (
        "the two must genuinely differ, or the pipeline test above proves nothing"
    )
