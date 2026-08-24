"""The split guard: the one place in this system where being wrong costs money.

`DR-015` §4 handed corporate actions over as the more dangerous of the two data risks it found, and
`DR-016` §7 named the held-position path as where the danger lands. The mechanism is short enough
to state in one sentence: both decision paths read `Series.RAW`, raw bars are unadjusted, so a split
does not restate history — **the next bars simply arrive at a different price level**. A 2:1 split
over a weekend leaves a stored stop of 290 being compared against Monday prices near 145, and
`manage.evaluate` reads that as a stop touched. It would propose `EXIT_NOW` on a stop-out that
never happened, confidently, with every freshness check passing.

Everything else a split could distort produces a wrong `Watch`. This produces a wrong exit on a
position the owner actually holds, which is why the guard pauses rather than evaluating.

Structured like `test_correlation.py`: the pure verdict first, then the pipeline through it, then
the case where the check could not run at all.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tests.conftest import TEST_US, fixture_fetcher

from swingdesk.application.pipeline import run
from swingdesk.contracts.market import CorporateAction, CorporateActionKind
from swingdesk.contracts.position import ActionKind, Position
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore, VendorUnavailable
from swingdesk.platform.clock import FixedClock
from swingdesk.reference_data import calendar as cal
from swingdesk.trade_management import manage

AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)

#: When the position's current stop became true. Every action is measured against THIS, not against
#: `opened_on` — a stop moved later was set against later prices.
STOP_SET_AT = datetime(2025, 12, 1, tzinfo=UTC)


def _sessions(start: date = date(2025, 1, 1), end: date = date(2026, 1, 15)) -> list[date]:
    return [s.session_date for s in cal.sessions(TEST_US.exchange, start, end)]


def _position(instrument: str = TEST_US.id, *, stop: str = "96",
              knowledge_time: datetime = STOP_SET_AT) -> Position:
    return Position(
        position_id=f"POS-{instrument}", version=1, instrument_id=instrument,
        opened_on=date(2025, 12, 1), entry_price=Decimal(100), shares=10,
        initial_stop=Decimal(stop), current_stop=Decimal(stop),
        initial_costs_per_share=Decimal("0.50"),
        knowledge_time=knowledge_time,
    )


def _split(day: date, ratio: str = "2", instrument: str = TEST_US.id) -> CorporateAction:
    return CorporateAction(
        instrument_id=instrument, kind=CorporateActionKind.SPLIT,
        effective_date=day, value=Decimal(ratio), knowledge_time=AS_OF,
    )


def _dividend(day: date, amount: str = "0.85") -> CorporateAction:
    return CorporateAction(
        instrument_id=TEST_US.id, kind=CorporateActionKind.DIVIDEND,
        effective_date=day, value=Decimal(amount), knowledge_time=AS_OF,
    )


# ------------------------------------------------------------------ the verdict


def test_a_split_after_the_stop_was_set_raises_an_alert() -> None:
    guard = manage.split_guard(
        _position(), [_split(date(2025, 12, 20))], refreshed=True
    )
    assert guard.alert is not None
    assert guard.alert.factor == Decimal("0.5")
    assert guard.alert.stop_before == Decimal(96)
    assert guard.alert.stop_after == Decimal(48)
    assert "2:1 split" in guard.alert.reason
    assert "never happened" in guard.alert.reason


def test_a_split_before_the_stop_was_set_raises_nothing() -> None:
    """The positive control, and the reason the reference instant matters. A split the owner
    already saw is baked into the stop they chose."""
    guard = manage.split_guard(
        _position(), [_split(date(2025, 11, 3))], refreshed=True
    )
    assert guard.alert is None
    assert not guard.is_unavailable
    assert "no split since the stop was set" in guard.note


def test_the_reference_instant_is_the_version_not_the_open_date() -> None:
    """A stop moved last week was set against last week's prices. `Position` is append-only and a
    stop move writes a new version, so the version's knowledge time is when its stop became true —
    using `opened_on` would re-alert on every split the owner already handled."""
    moved = _position(stop="98", knowledge_time=datetime(2026, 1, 5, tzinfo=UTC))
    # Effective after `opened_on` (2025-12-01) but BEFORE the stop was moved (2026-01-05).
    assert manage.split_guard(moved, [_split(date(2025, 12, 20))], refreshed=True).alert is None
    assert manage.split_guard(moved, [_split(date(2026, 1, 9))], refreshed=True).alert is not None


def test_a_split_on_the_very_day_the_stop_was_set_is_treated_as_already_reflected() -> None:
    """Authored, and stated in the guard's own docstring: splits take effect at the open, so a stop
    set during that session was set against post-split prices. The boundary is tested from both
    sides because an off-by-one here pauses a position for nothing."""
    on_the_day = manage.split_guard(
        _position(), [_split(STOP_SET_AT.date())], refreshed=True
    )
    assert on_the_day.alert is None

    next_day = manage.split_guard(
        _position(), [_split(date(2025, 12, 2))], refreshed=True
    )
    assert next_day.alert is not None


def test_a_dividend_is_not_a_split_and_raises_nothing() -> None:
    """`price_factor` returns 1 for a dividend because the ex-date move is a market reaction rather
    than a re-denomination. Pausing on one would cry wolf on every dividend-paying holding."""
    guard = manage.split_guard(_position(), [_dividend(date(2025, 12, 20))], refreshed=True)
    assert guard.alert is None
    assert guard.stored == 1, "the dividend is still on record; it just is not an alert"


def test_two_splits_compound_and_both_are_named() -> None:
    guard = manage.split_guard(
        _position(),
        [_split(date(2026, 1, 5), "2"), _split(date(2025, 12, 10), "5")],
        refreshed=True,
    )
    assert guard.alert is not None
    assert guard.alert.factor == Decimal("0.1"), "5:1 then 2:1 is a tenth"
    assert guard.alert.stop_after == Decimal("9.6")
    assert "a 5:1 split on 2025-12-10" in guard.alert.reason
    assert "a 2:1 split on 2026-01-05" in guard.alert.reason


def test_a_reverse_split_moves_the_stop_the_other_way() -> None:
    """A 1-for-10 reverse split arrives as a ratio of 0.1, so the factor is 10 and a stop of 96
    corresponds to 960. The arithmetic is the same and the direction is not."""
    guard = manage.split_guard(_position(), [_split(date(2025, 12, 20), "0.1")], refreshed=True)
    assert guard.alert is not None
    assert guard.alert.stop_after == Decimal(960)


def test_nothing_stored_and_nothing_fetched_is_unavailable_rather_than_clean() -> None:
    """The distinction the store cannot record. Zero actions means either "this instrument never
    split" or "nobody asked", and only the run knows which — so it carries whether it ASKED."""
    unasked = manage.split_guard(_position(), [], refreshed=False)
    assert unasked.alert is None
    assert unasked.is_unavailable
    assert unasked.note.startswith("UNAVAILABLE")
    assert "gap in the check, not a fact about the trade" in unasked.note

    asked = manage.split_guard(_position(), [], refreshed=True)
    assert not asked.is_unavailable, "asked and told there are none is a real answer"
    assert asked.alert is None


def test_stored_actions_answer_even_when_the_fetch_failed() -> None:
    """Fail-open on the fetch, exactly as the bar path is: a vendor outage leaves what is stored
    standing, and a split already on record still pauses the position."""
    guard = manage.split_guard(_position(), [_split(date(2025, 12, 20))], refreshed=False)
    assert guard.alert is not None
    assert not guard.is_unavailable


# ------------------------------------------------------------------ through the pipeline


@pytest.fixture
def wired(tmp_path):
    with (
        BarStore(tmp_path / "bars.duckdb") as bars,
        Journal(tmp_path / "journal.duckdb") as journal,
        PositionStore(tmp_path / "positions.duckdb") as positions,
    ):
        yield bars, journal, positions


def _actions_from(*actions: CorporateAction):
    def _fetch(instrument, knowledge_time, period="max"):
        return tuple(a for a in actions if a.instrument_id == instrument.id)

    return _fetch


def _run(wired, registry, *, held: Position, actions_fetcher=None):
    bars, journal, positions = wired
    positions.record(held)
    sessions = _sessions()
    return run(
        [TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
        positions=positions, actions_fetcher=actions_fetcher,
        fetcher=fixture_fetcher({TEST_US.id: sessions}),
    )


def test_a_held_position_pauses_when_a_split_re_denominated_it(wired, registry) -> None:
    result = _run(
        wired, registry, held=_position(),
        actions_fetcher=_actions_from(_split(date(2025, 12, 20))),
    )

    managed = result.positions[0]
    assert managed.action is not None
    assert managed.action.kind is ActionKind.PAUSE
    assert managed.action.reason_code == "DATA"
    assert "corresponds to 48" in managed.action.reason
    assert managed.stale
    assert managed.action.old_stop == Decimal(96), (
        "the stop is REPORTED, never adjusted - CHARTER A-001 reserves that to the owner"
    )


def test_a_position_with_no_split_is_managed_normally(wired, registry) -> None:
    """The positive control through the whole run. Without it the test above passes on a pipeline
    that pauses every position that has any action on record at all."""
    result = _run(
        wired, registry, held=_position(),
        actions_fetcher=_actions_from(_dividend(date(2025, 12, 20))),
    )

    managed = result.positions[0]
    assert managed.action is not None
    assert managed.action.kind is not ActionKind.PAUSE
    assert managed.split is not None and managed.split.alert is None
    assert managed.split.refreshed, "the run asked, so a clean answer is a real one"


def test_the_run_feeds_the_actions_store_it_reads(wired, registry) -> None:
    """`DR-016` §8.5 found the actions table holding zero rows with every part of the path built.
    The guard is what feeds it, and only for HELD names - bounded by
    `risk.max_concurrent_positions`, which is what makes it affordable in the evening run."""
    bars, _journal, _positions = wired
    result = _run(
        wired, registry, held=_position(),
        actions_fetcher=_actions_from(_split(date(2025, 12, 20))),
    )
    assert result.positions

    stored = bars.actions_as_of(TEST_US.id, AS_OF)
    assert len(stored) == 1 and stored[0].kind is CorporateActionKind.SPLIT


def test_a_run_given_no_actions_fetcher_reports_unavailable_and_still_manages(
    wired, registry
) -> None:
    """The default, and production's own state before `cli.py` was wired. It must read as a gap in
    the CHECK rather than as a clean instrument - and it must not stop the position being managed,
    because `CHECKLIST_SPEC` §4 exists so a data failure cannot lock the owner out of risk they
    already carry."""
    result = _run(wired, registry, held=_position())

    managed = result.positions[0]
    assert managed.split is not None and managed.split.is_unavailable
    assert managed.action is not None
    assert managed.action.kind is not ActionKind.PAUSE, "an unchecked guard must not pause"


def test_a_vendor_failure_leaves_the_position_managed_and_the_guard_honest(
    wired, registry
) -> None:
    def _broken(instrument, knowledge_time, period="max"):
        raise VendorUnavailable("actions endpoint down")

    result = _run(wired, registry, held=_position(), actions_fetcher=_broken)

    managed = result.positions[0]
    assert managed.split is not None
    assert not managed.split.refreshed
    assert managed.split.is_unavailable
    assert managed.action is not None and managed.action.kind is not ActionKind.PAUSE


def test_the_split_pause_moves_the_output_hash(wired, registry, tmp_path) -> None:
    """Two runs the owner would act on differently must not hash alike, and "hold" versus "your
    stop is denominated in pre-split prices" is as different as this system gets."""
    clean = _run(
        wired, registry, held=_position(), actions_fetcher=_actions_from()
    ).manifest.output_hash

    with (
        BarStore(tmp_path / "b2.duckdb") as bars,
        Journal(tmp_path / "j2.duckdb") as journal,
        PositionStore(tmp_path / "p2.duckdb") as positions,
    ):
        positions.record(_position())
        split = run(
            [TEST_US], FixedClock(AS_OF), registry, bars, journal, mode=RunMode.LIVE_AS_OF,
            positions=positions, actions_fetcher=_actions_from(_split(date(2025, 12, 20))),
            fetcher=fixture_fetcher({TEST_US.id: _sessions()}),
        ).manifest.output_hash

    assert clean != split


# ------------------------------------------------------------------ the report


def test_the_report_names_the_split_and_the_restated_stop(wired, registry) -> None:
    from swingdesk.presentation.report import render

    text = render(_run(
        wired, registry, held=_position(),
        actions_fetcher=_actions_from(_split(date(2025, 12, 20))),
    ))
    assert "splits:" in text
    assert "2:1 split" in text
    assert "corresponds to 48" in text


def test_the_report_says_when_the_guard_could_not_run(wired, registry) -> None:
    from swingdesk.presentation.report import render

    text = render(_run(wired, registry, held=_position()))
    assert "UNAVAILABLE" in text
    assert "whether a split has re-denominated its prices is unknown" in text


def test_a_clean_check_prints_nothing(wired, registry) -> None:
    """The ordinary evening. A line every night trains the eye past the two that matter."""
    from swingdesk.presentation.report import render

    text = render(_run(
        wired, registry, held=_position(),
        actions_fetcher=_actions_from(_dividend(date(2025, 12, 20))),
    ))
    assert "splits:" not in text
