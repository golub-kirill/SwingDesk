"""The symbol directory store.

The tests that matter are about the store's one deliberate difference from `BarStore`: a directory
pull is a complete snapshot, not a set of independent facts. Reading "everything known by K" would
union every symbol ever seen and make a delisting invisible — which is precisely the bias this
project cannot afford to add to the one it already cannot escape.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.reference_data.universe import DirectoryEntry

UTC = UTC
MONDAY = datetime(2026, 1, 12, 21, 0, tzinfo=UTC)
FRIDAY = MONDAY + timedelta(days=4)


def _entry(symbol: str, venue: str = "Q", **kwargs) -> DirectoryEntry:
    return DirectoryEntry(
        symbol=symbol, name=f"{symbol} Inc", venue=venue,
        is_etf=kwargs.get("is_etf", False),
        is_test_issue=kwargs.get("is_test_issue", False),
    )


@pytest.fixture
def store(tmp_path):
    with DirectoryStore(tmp_path / "directory.duckdb") as opened:
        yield opened


# ------------------------------------------------------------------ snapshot semantics

def test_a_read_before_any_pull_is_empty_not_an_error(store) -> None:
    """"We did not know" is a real answer, and the caller must not read it as "nothing was listed"."""
    assert store.as_of(MONDAY) == ()
    assert store.latest_pull(MONDAY) is None


def test_as_of_reads_one_pull_not_the_union_of_all_of_them(store) -> None:
    """The load-bearing test.

    If `as_of` unioned every row known by K, a symbol that stopped being listed would stay in the
    universe forever and the store would manufacture survivorship bias rather than measure it.
    """
    store.record([_entry("TEST1"), _entry("TEST2")], MONDAY, "fixture")
    store.record([_entry("TEST1")], FRIDAY, "fixture")

    assert [e.symbol for e in store.as_of(FRIDAY)] == ["TEST1"]
    assert [e.symbol for e in store.as_of(MONDAY)] == ["TEST1", "TEST2"]


def test_a_read_between_pulls_gets_the_earlier_one(store) -> None:
    """Point-in-time: a run pinned to Wednesday must not see Friday's directory."""
    store.record([_entry("TEST1"), _entry("TEST2")], MONDAY, "fixture")
    store.record([_entry("TEST1")], FRIDAY, "fixture")

    wednesday = MONDAY + timedelta(days=2)
    assert [e.symbol for e in store.as_of(wednesday)] == ["TEST1", "TEST2"]


def test_recording_the_same_instant_twice_replaces_rather_than_merges(store) -> None:
    """Re-running a fetch must not half-merge two downloads into a snapshot that never existed."""
    store.record([_entry("TEST1"), _entry("TEST2")], MONDAY, "fixture")
    store.record([_entry("TEST3")], MONDAY, "fixture")

    assert [e.symbol for e in store.as_of(MONDAY)] == ["TEST3"]
    assert store.pulls() == ((MONDAY, "fixture", 1),)


def test_an_empty_pull_is_refused(store) -> None:
    """An empty snapshot is indistinguishable from every symbol delisting at once.

    A failed download that returned nothing would otherwise be recorded as a market event.
    """
    with pytest.raises(ValueError, match="empty directory pull"):
        store.record([], MONDAY, "fixture")


# ------------------------------------------------------------------ eligibility

def test_eligible_only_drops_test_issues_and_unknown_venues(store) -> None:
    store.record(
        [
            _entry("TEST1"),
            _entry("TEST2", is_test_issue=True),
            _entry("TEST3", venue="ZZ"),
            _entry("TEST4", is_etf=True),
        ],
        MONDAY, "fixture",
    )
    assert [e.symbol for e in store.as_of(MONDAY, eligible_only=True)] == ["TEST1", "TEST4"]


def test_etfs_stay_in_scope(store) -> None:
    """CHARTER: equities *and* ETFs. 58 of 115 sampled instruments were ETFs (DR-003)."""
    store.record([_entry("TEST1", is_etf=True)], MONDAY, "fixture")
    assert len(store.as_of(MONDAY, eligible_only=True)) == 1


# ------------------------------------------------------------------ departures

def test_departures_report_what_stopped_appearing(store) -> None:
    """The only free survivorship evidence this project can ever collect."""
    store.record([_entry("TEST1"), _entry("TEST2"), _entry("TEST3")], MONDAY, "fixture")
    store.record([_entry("TEST1"), _entry("TEST4")], FRIDAY, "fixture")

    assert store.departures(MONDAY, FRIDAY) == ("TEST2", "TEST3")


def test_departures_are_directional(store) -> None:
    """Arrivals are not departures. Reversing the arguments must not report new symbols as gone."""
    store.record([_entry("TEST1")], MONDAY, "fixture")
    store.record([_entry("TEST1"), _entry("TEST2")], FRIDAY, "fixture")

    assert store.departures(MONDAY, FRIDAY) == ()
    assert store.departures(FRIDAY, MONDAY) == ("TEST2",)
