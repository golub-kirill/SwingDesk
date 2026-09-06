"""The actions series: the record, its storage, and the point-in-time rule it has to obey.

`POINT_IN_TIME_SPEC` §4 names three series and the tree implemented two. `DR-016` named the missing
one as its own precondition, so nothing about the corporate-actions gate could be built until this
existed.

**Nothing here is wired into the decision path**, and that is deliberate: the gate needs
`data.revision_epsilon`, which was unset and awaiting an owner ruling when this landed. THE OWNER
HAS SINCE SET IT (0.001, `owner`), so the precondition this file names is met and the wiring is
work nobody has done rather than work nobody could do. Storing an action changes no decision, so
this file still cannot affect the scheduled run.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tests.conftest import TEST_US

from swingdesk.contracts.market import CorporateAction, CorporateActionKind, Series
from swingdesk.market_data import BarStore

KNOWN_AT = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


def _split(effective: date, ratio: str, known_at: datetime = KNOWN_AT) -> CorporateAction:
    return CorporateAction(
        instrument_id=TEST_US.id, kind=CorporateActionKind.SPLIT,
        effective_date=effective, value=Decimal(ratio), knowledge_time=known_at,
    )


def _dividend(effective: date, amount: str) -> CorporateAction:
    return CorporateAction(
        instrument_id=TEST_US.id, kind=CorporateActionKind.DIVIDEND,
        effective_date=effective, value=Decimal(amount), knowledge_time=KNOWN_AT,
    )


@pytest.fixture
def store(tmp_path):
    with BarStore(tmp_path / "bars.duckdb") as bars:
        yield bars


# ------------------------------------------------------------------ the contract


def test_actions_are_not_a_bar_series() -> None:
    """A split has no open, high, low or close. Adding `actions` to `Series` would mean inventing
    five fields to leave empty, and the first component to read one would get numbers back."""
    assert [s.value for s in Series] == ["raw", "adjusted"]
    assert not hasattr(Series, "ACTIONS")


def test_a_split_factor_restates_a_price_and_a_dividend_does_not() -> None:
    """The number the whole risk turns on. A 2:1 split means a stop of 290 set before it corresponds
    to 145 after - `DR-015` §4's case, in one assertion."""
    assert _split(date(2026, 1, 15), "2").price_factor == Decimal("0.5")
    assert _split(date(2026, 1, 15), "4").price_factor == Decimal("0.25")

    # A dividend moves the price by roughly its amount on the ex-date, but that is a market
    # reaction, not a re-denomination. Adjusting a stop for it would move a real stop on a guess.
    assert _dividend(date(2026, 1, 15), "0.85").price_factor == Decimal(1)


def test_a_zero_or_negative_value_is_refused_at_the_boundary() -> None:
    """`price_factor` divides by `value`. A zero ratio would raise at exactly the moment someone is
    comparing a held stop against a new price level, three layers from here."""
    for bad in ("0", "-2"):
        with pytest.raises(ValueError):
            _split(date(2026, 1, 15), bad)


# ------------------------------------------------------------------ storage


def test_an_action_round_trips(store) -> None:
    store.write_actions([_split(date(2026, 1, 12), "2")], KNOWN_AT)

    stored = store.actions_as_of(TEST_US.id, KNOWN_AT)

    assert len(stored) == 1
    assert stored[0].kind is CorporateActionKind.SPLIT
    assert stored[0].value == Decimal(2)
    assert stored[0].effective_date == date(2026, 1, 12)


def test_writing_the_same_action_twice_writes_nothing_the_second_time(store) -> None:
    """Delta-based like the bar path, for the same reason: the vendor serves the full history on
    every call, so appending what came back would make revision volume meaningless."""
    first = store.write_actions([_split(date(2026, 1, 12), "2")], KNOWN_AT)
    later = KNOWN_AT.replace(day=16)
    second = store.write_actions([_split(date(2026, 1, 12), "2", later)], later)

    assert first.inserted == 1
    assert second.inserted == 0 and second.revised == 0
    assert second.unchanged == 1
    assert len(store.actions_as_of(TEST_US.id, later)) == 1


def test_a_corrected_ratio_supersedes_rather_than_overwrites(store) -> None:
    """Records are immutable (`AGENTS.md` §3). A vendor that corrects a ratio writes a new version;
    the old one stays readable as of the time it was believed."""
    store.write_actions([_split(date(2026, 1, 12), "2")], KNOWN_AT)
    later = KNOWN_AT.replace(day=16)
    result = store.write_actions([_split(date(2026, 1, 12), "3", later)], later)

    assert result.revised == 1
    assert store.actions_as_of(TEST_US.id, later)[0].value == Decimal(3)
    assert store.actions_as_of(TEST_US.id, KNOWN_AT)[0].value == Decimal(2), "the old belief stands"


def test_an_action_learned_later_is_invisible_to_an_earlier_read(store) -> None:
    """The look-ahead rule, and a corporate action is exactly the kind of fact that arrives late.

    A backtest asking what was known on the decision bar must not be handed a split the vendor only
    published afterwards - it would 'know' about a price level nobody could have known about.
    """
    late = KNOWN_AT.replace(day=20)
    store.write_actions([_split(date(2026, 1, 12), "2", late)], late)

    assert store.actions_as_of(TEST_US.id, KNOWN_AT) == ()
    assert len(store.actions_as_of(TEST_US.id, late)) == 1


def test_splits_and_dividends_on_the_same_date_are_separate_records(store) -> None:
    """They share an instrument and a date and are different facts, so the key has to carry the
    kind - otherwise one silently replaces the other."""
    store.write_actions(
        [_split(date(2026, 1, 12), "2"), _dividend(date(2026, 1, 12), "0.5")], KNOWN_AT
    )

    stored = store.actions_as_of(TEST_US.id, KNOWN_AT)
    assert {a.kind for a in stored} == {CorporateActionKind.SPLIT, CorporateActionKind.DIVIDEND}


def test_reads_are_ordered_and_can_be_windowed(store) -> None:
    store.write_actions(
        [_split(date(2025, 6, 1), "2"), _split(date(2026, 1, 12), "3")], KNOWN_AT
    )

    every = store.actions_as_of(TEST_US.id, KNOWN_AT)
    recent = store.actions_as_of(TEST_US.id, KNOWN_AT, since=date(2026, 1, 1))

    assert [a.effective_date for a in every] == [date(2025, 6, 1), date(2026, 1, 12)]
    assert [a.effective_date for a in recent] == [date(2026, 1, 12)]


def test_a_future_dated_action_is_stored_not_refused(store) -> None:
    """The opposite of the unclosed-bar rule, and deliberately so. A split is DECLARED before it
    takes effect, and an action dated ahead is the only warning this system can get before the
    price level moves under a position it is already holding."""
    ahead = date(2026, 2, 1)
    assert ahead > KNOWN_AT.date()

    result = store.write_actions([_split(ahead, "2")], KNOWN_AT)

    assert result.inserted == 1
    assert store.actions_as_of(TEST_US.id, KNOWN_AT)[0].effective_date == ahead


def test_actions_and_bars_do_not_share_a_table(store) -> None:
    """A positive control on the separation. If actions were being written as bars, the bar store
    would report rows for an instrument that has none."""
    store.write_actions([_split(date(2026, 1, 12), "2")], KNOWN_AT)

    from swingdesk.contracts.market import Interval

    assert store.as_of(TEST_US.id, Interval.DAY, Series.RAW, KNOWN_AT).bars == ()
    assert store.revision_count(TEST_US.id) == 0
