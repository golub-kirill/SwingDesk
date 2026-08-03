"""Building the universe from a rule instead of a list.

The rule itself is tested in `test_universe.py`. What is tested here is the join of two stores and,
above all, the thing that join can quietly get wrong: presenting a universe computed from the bars
we happen to hold as though it were the rule's answer over the whole directory.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from swingdesk.application import universe as builder
from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.reference_data.universe import DirectoryEntry, LiquidityRule
from swingdesk.trade_management.sizing import Refusal

UTC = timezone.utc
AS_OF = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)

#: Deliberately small so a fixture can satisfy it. The shipped values are DR-003's.
RULE = LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal("5000000"), adtv_window=20, min_history=30
)


def _entry(symbol: str) -> DirectoryEntry:
    return DirectoryEntry(symbol=symbol, name=f"{symbol} Inc", venue="Q",
                          is_etf=False, is_test_issue=False)


def _bars(instrument_id: str, count: int, close: Decimal, volume: int) -> list[Bar]:
    """Flat bars, so admission depends only on the rule and not on where a walk happened to end."""
    start = date(2025, 1, 1)
    return [
        Bar(
            instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
            event_time=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=offset),
            session_date=start + timedelta(days=offset),
            open=close, high=close, low=close, close=close, volume=volume,
            knowledge_time=AS_OF,
        )
        for offset in range(count)
    ]


@pytest.fixture
def stores(tmp_path):
    with (
        DirectoryStore(tmp_path / "directory.duckdb") as directory,
        BarStore(tmp_path / "bars.duckdb") as bars,
    ):
        yield directory, bars


# ------------------------------------------------------------------ the rule from the registry

def test_an_unset_threshold_refuses_and_names_itself() -> None:
    """Fail-closed. A universe built on a guessed liquidity floor puts every downstream result on
    an unrecorded assumption, so it refuses rather than admitting everything."""
    registry = ParameterRegistry({
        "universe.min_price": {"id": "universe.min_price", "value": None},
        "universe.min_adtv_20d": {"id": "universe.min_adtv_20d", "value": None},
        "universe.min_bar_history": {"id": "universe.min_bar_history", "value": None},
    })
    built = builder.rule_from_registry(registry)
    assert isinstance(built, Refusal)
    assert built.code == "UNIVERSE"
    assert built.parameter_id == "universe.min_price"


def test_the_shipped_registry_builds_the_dr003_rule() -> None:
    """DR-003 set all three, so the real registry must produce a rule rather than a refusal."""
    built = builder.rule_from_registry(ParameterRegistry.load())
    assert not isinstance(built, Refusal)
    rule, parameters = built
    assert rule.min_price == Decimal("5.00")
    assert rule.min_adtv == Decimal("5000000")
    assert rule.min_history == 250
    assert rule.adtv_window == builder.ADTV_WINDOW == 20
    assert {p.id for p in parameters} == {
        "universe.min_price", "universe.min_adtv_20d", "universe.min_bar_history"
    }
    assert all(p.is_assumed for p in parameters), "DR-003 values are assumed, and must say so"


# ------------------------------------------------------------------ selection

def test_the_rule_selects_and_the_directory_bounds(stores) -> None:
    directory, bars = stores
    directory.record([_entry("TEST1"), _entry("TEST2")], AS_OF, "fixture")
    bars.write(_bars("TEST1", 40, Decimal("100"), 100_000), AS_OF)   # 10M ADTV - admitted
    bars.write(_bars("TEST2", 40, Decimal("100"), 1_000), AS_OF)     # 100k ADTV - too thin

    selection = builder.select(directory, bars, RULE, AS_OF)

    assert [m.instrument.id for m in selection.members] == ["TEST1"]
    assert selection.members[0].adtv == Decimal("10000000")
    assert selection.eligible == 2
    assert selection.measured == 2


def test_a_symbol_the_store_has_never_seen_is_not_measured_and_not_admitted(stores) -> None:
    """The chicken-and-egg the tiered refresh exists to resolve, made explicit.

    Silently dropping it would be indistinguishable from the rule rejecting it, and those are very
    different facts about the universe.
    """
    directory, bars = stores
    directory.record([_entry("TEST1"), _entry("TEST2")], AS_OF, "fixture")
    bars.write(_bars("TEST1", 40, Decimal("100"), 100_000), AS_OF)

    selection = builder.select(directory, bars, RULE, AS_OF)

    assert selection.eligible == 2
    assert selection.measured == 1
    assert selection.is_partial
    assert selection.coverage == Decimal("0.5")


def test_a_complete_universe_is_not_partial(stores) -> None:
    directory, bars = stores
    directory.record([_entry("TEST1")], AS_OF, "fixture")
    bars.write(_bars("TEST1", 40, Decimal("100"), 100_000), AS_OF)

    selection = builder.select(directory, bars, RULE, AS_OF)
    assert not selection.is_partial
    assert selection.coverage == Decimal("1")


def test_members_are_sorted_by_id_not_by_liquidity(stores) -> None:
    """An unordered collection feeding the run is the classic silent non-determinism, and ordering
    by ADTV would turn a membership rule into a ranking the moment anyone truncated the list."""
    directory, bars = stores
    directory.record([_entry("TEST1"), _entry("TEST2"), _entry("TEST3")], AS_OF, "fixture")
    bars.write(_bars("TEST1", 40, Decimal("100"), 100_000), AS_OF)
    bars.write(_bars("TEST2", 40, Decimal("100"), 900_000), AS_OF)
    bars.write(_bars("TEST3", 40, Decimal("100"), 500_000), AS_OF)

    selection = builder.select(directory, bars, RULE, AS_OF)
    assert [m.instrument.id for m in selection.members] == ["TEST1", "TEST2", "TEST3"]


def test_a_cap_is_recorded_as_a_cap(stores) -> None:
    """A cap is a RANKING and the rule is not. Reporting the truncated list without saying so would
    present "the most liquid three" as "the universe"."""
    directory, bars = stores
    directory.record([_entry("TEST1"), _entry("TEST2"), _entry("TEST3")], AS_OF, "fixture")
    bars.write(_bars("TEST1", 40, Decimal("100"), 100_000), AS_OF)
    bars.write(_bars("TEST2", 40, Decimal("100"), 900_000), AS_OF)
    bars.write(_bars("TEST3", 40, Decimal("100"), 500_000), AS_OF)

    selection = builder.select(directory, bars, RULE, AS_OF, limit=2)

    assert selection.capped_from == 3
    assert [m.instrument.id for m in selection.members] == ["TEST2", "TEST3"], "top two by ADTV"


def test_an_uncapped_selection_records_no_cap(stores) -> None:
    directory, bars = stores
    directory.record([_entry("TEST1")], AS_OF, "fixture")
    bars.write(_bars("TEST1", 40, Decimal("100"), 100_000), AS_OF)

    assert builder.select(directory, bars, RULE, AS_OF, limit=10).capped_from is None


# ------------------------------------------------------------------ point in time

def test_the_universe_is_read_as_of_not_as_now(stores) -> None:
    """Today's listings applied to an older window is survivorship bias with extra steps — the
    specific mistake DR-003 was written to avoid."""
    directory, bars = stores
    earlier = AS_OF - timedelta(days=30)
    directory.record([_entry("TEST1"), _entry("TEST2")], earlier, "fixture")
    directory.record([_entry("TEST1")], AS_OF, "fixture")
    bars.write(_bars("TEST1", 40, Decimal("100"), 100_000), earlier)
    bars.write(_bars("TEST2", 40, Decimal("100"), 100_000), earlier)

    assert builder.select(directory, bars, RULE, earlier).eligible == 2
    assert builder.select(directory, bars, RULE, AS_OF).eligible == 1


def test_an_empty_directory_yields_an_empty_universe_rather_than_everything(stores) -> None:
    """Fail-closed at the top of the funnel: an unfetched directory must not admit the whole store."""
    directory, bars = stores
    bars.write(_bars("TEST1", 40, Decimal("100"), 100_000), AS_OF)

    selection = builder.select(directory, bars, RULE, AS_OF)
    assert selection.members == ()
    assert selection.eligible == 0
    assert selection.directory_pull is None
