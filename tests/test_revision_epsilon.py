"""The restated-close fault: `data.revision_epsilon`, scoped to `close` by owner ruling 2026-08-23.

`DR-016` §8.4 is the ruling and §9.5 named this as the half that was waiting on it. Two things it
must keep apart, and both are tested from both sides:

  1. **Storing a revision and raising a fault are different acts.** Every revision is written
     either way; the epsilon governs only the alarm (§8.4 corollary 1). A test that checked the
     fault without checking the row would pass on an implementation that discarded the audit trail
     for a 5% open restatement, which is the failure that corollary exists to forbid.
  2. **Scope is `close` and nothing else.** `open`, `high` and `low` revise an order of magnitude
     wider and get no fault (§8.4 corollary 2). If a change makes them behave alike, these are the
     tests that will say so - the wide form raises ~94 faults an evening, which is the crying-wolf
     failure §5 of that record already rejected once for volume.

**No epsilon passed means NOT CHECKED, not clean.** Distinguishing the two is the same
`unavailable`-is-not-`pass` rule the rest of this project runs on, applied to a write.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tests.conftest import TEST_US

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.market_data import BarStore, close_revision

KNOWN_AT = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 16, 21, 0, tzinfo=UTC)

#: The ratified value. Written here rather than read from the registry so the test pins the number
#: the ruling chose: a registry edit that moved it should fail these, not silently retarget them.
EPSILON = Decimal("0.001")

#: A settled session, well before `KNOWN_AT`, so nothing here trips the unclosed-bar guard.
SESSION = date(2026, 1, 8)


def _bar(*, close: str, open_: str | None = None, high: str | None = None, low: str | None = None,
         volume: int = 1_000_000) -> Bar:
    """One settled bar. `high` and `low` bracket the close unless a test overrides them.

    Derived rather than fixed because `Bar` validates `low <= close <= high`, so a hard-coded
    envelope would make every close a test wanted to try out of range. The envelope is what these
    tests vary in the scope cases and what they must NOT accidentally vary elsewhere.
    """
    value = Decimal(close)
    return Bar(
        instrument_id=TEST_US.id,
        interval=Interval.DAY,
        series=Series.RAW,
        event_time=datetime(SESSION.year, SESSION.month, SESSION.day, tzinfo=UTC),
        session_date=SESSION,
        open=Decimal(open_) if open_ is not None else value,
        high=Decimal(high) if high is not None else value + Decimal(1),
        low=Decimal(low) if low is not None else value - Decimal(1),
        close=value,
        volume=volume,
        knowledge_time=KNOWN_AT,
    )


@pytest.fixture
def store(tmp_path):
    with BarStore(tmp_path / "bars.duckdb") as bars:
        yield bars


# ---------------------------------------------------------------- the comparison, in isolation


def test_an_unchanged_close_is_not_a_revision() -> None:
    assert close_revision(_bar(close="100.00"), _bar(close="100.00"), EPSILON) is None


def test_a_close_inside_the_tolerance_raises_nothing() -> None:
    """0.05% on a 100.00 close. DR-016 §8.1 measured the close's LARGEST revision in the whole
    window at 0.084%, so this is the shape of a real one and it must stay quiet."""
    assert close_revision(_bar(close="100.00"), _bar(close="100.05"), EPSILON) is None


def test_a_close_exactly_at_the_tolerance_raises_nothing() -> None:
    """The boundary is closed, and which side it falls on is a decision rather than an accident:
    `<=` keeps a threshold of 0.001 meaning "a tenth of a percent is tolerated", not "all but a
    tenth of a percent"."""
    assert close_revision(_bar(close="100.00"), _bar(close="100.10"), EPSILON) is None


def test_a_close_past_the_tolerance_is_reported_with_its_magnitude() -> None:
    fault = close_revision(_bar(close="100.00"), _bar(close="100.50"), EPSILON)
    assert fault is not None
    assert fault.stored == Decimal("100.00")
    assert fault.restated == Decimal("100.50")
    assert fault.relative == Decimal("0.005")
    assert fault.instrument_id == TEST_US.id
    assert fault.session_date == SESSION


def test_the_comparison_is_relative_and_not_absolute() -> None:
    """One cent is 0.2% of a $5 stock and 0.002% of a $500 one. An absolute tolerance would fire
    constantly on the cheap end of the universe and never on the expensive end, and
    `universe.min_price` admits names down to exactly $5."""
    assert close_revision(_bar(close="5.00"), _bar(close="5.01"), EPSILON) is not None
    assert close_revision(_bar(close="500.00"), _bar(close="500.01"), EPSILON) is None


def test_a_downward_restatement_counts_the_same() -> None:
    """The magnitude is unsigned. A close revised down is exactly as wrong as one revised up, and
    sizing spends its risk against whichever number is stored."""
    fault = close_revision(_bar(close="100.00"), _bar(close="99.50"), EPSILON)
    assert fault is not None
    assert fault.relative == Decimal("0.005")


def test_a_zero_stored_close_reports_the_change_with_no_magnitude() -> None:
    """The change is real and its ratio is undefined. Reporting it with an invented number would be
    the `unavailable`-becomes-a-value collapse; suppressing it would hide the more serious defect,
    because a stored close of zero should not exist at all."""
    stored = _bar(close="0.00", open_="0.00", low="0.00", high="1.00")
    fault = close_revision(stored, _bar(close="10.00"), EPSILON)
    assert fault is not None
    assert fault.relative is None


# ---------------------------------------------------------------- scope: the close, and only it


@pytest.mark.parametrize(
    ("field", "moved"),
    [("open_", "100.90"), ("high", "150.00"), ("low", "50.00")],
)
def test_the_other_three_price_fields_raise_nothing(field: str, moved: str) -> None:
    """DR-016 §8.1: the open's MEDIAN revision is 0.128%, larger than this threshold; the close's
    largest across the window is 0.084%, twelve times under it. They are not one population and
    0.001 is not one threshold for them. §8.4 corollary 2 accepts that `high` and `low` still reach
    a decision through ATR and get no fault anyway - a field whose revisions form no separable
    population gets none rather than a worse one.

    **The close moves here too, by 0.05% - deliberately, and it is what makes this a scope test.**
    Holding the close identical lets the comparison return early on "the close did not change", so
    a version that faulted on all four fields would still pass. Measured: the four-field form
    survives that phrasing of this test and fails this one. The move is under the threshold on its
    own and each other field is moved far past it, so only a correctly scoped rule stays quiet.
    """
    stored = _bar(close="100.00")
    restated = _bar(close="100.05", **{field: moved})
    assert getattr(restated, field.rstrip("_")) != getattr(stored, field.rstrip("_"))
    assert close_revision(stored, restated, EPSILON) is None


def test_volume_raises_nothing() -> None:
    """DR-016 §5 rejected the volume form outright: it would raise a Critical fault on ~1,150
    instruments an evening, and a gate that cries wolf nightly gets ignored regardless of policy."""
    stored = _bar(close="100.00")
    assert close_revision(stored, _bar(close="100.05", volume=99), EPSILON) is None


# ---------------------------------------------------------------- through the store


def test_a_revision_is_stored_whether_or_not_it_faults(store) -> None:
    """§8.4 corollary 1, and the one that would be easiest to get wrong. The epsilon governs the
    ALARM; `POINT_IN_TIME_SPEC` §3 requires the version regardless."""
    store.write([_bar(close="100.00")], KNOWN_AT)
    result = store.write([_bar(close="100.05")], LATER, EPSILON)

    assert result.revised == 1
    assert result.close_revisions == ()
    assert store.as_of(TEST_US.id, Interval.DAY, Series.RAW, LATER).bars[-1].close \
        == Decimal("100.05")
    assert store.revision_count(TEST_US.id) >= 1


def test_a_faulting_revision_is_also_stored(store) -> None:
    store.write([_bar(close="100.00")], KNOWN_AT)
    result = store.write([_bar(close="105.00")], LATER, EPSILON)

    assert result.revised == 1
    assert len(result.close_revisions) == 1
    assert store.as_of(TEST_US.id, Interval.DAY, Series.RAW, LATER).bars[-1].close \
        == Decimal("105.00")


def test_no_epsilon_means_not_checked_rather_than_clean(store) -> None:
    """The distinction the whole fail-closed discipline turns on. A caller that passes nothing gets
    an empty tuple because nothing was asked, not because nothing was found - and the same write
    with an epsilon finds a fault in the identical data."""
    store.write([_bar(close="100.00")], KNOWN_AT)
    unchecked = store.write([_bar(close="105.00")], LATER)
    assert unchecked.revised == 1
    assert unchecked.close_revisions == ()

    store.write([_bar(close="100.00")], LATER)
    checked = store.write([_bar(close="105.00")], datetime(2026, 1, 17, 21, 0, tzinfo=UTC), EPSILON)
    assert len(checked.close_revisions) == 1


def test_a_first_insert_is_never_a_revision(store) -> None:
    """Nothing to compare against. A bar the store has not seen cannot have been restated, and
    counting it as one would make every fresh instrument fault on its first fetch."""
    result = store.write([_bar(close="100.00")], KNOWN_AT, EPSILON)
    assert result.inserted == 1
    assert result.revised == 0
    assert result.close_revisions == ()
