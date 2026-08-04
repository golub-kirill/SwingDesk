"""Pivots and the trend filter, with the look-ahead guard as the first thing tested.

`подтверждается завершёнными барами` - confirmed by completed bars (M12-T0201). A pivot detector
that marks a swing at bar T and lets a caller read it at T has used bars T+1..T+right to make a
decision dated T. That is the single most likely way this component goes wrong, it produces an
excellent backtest, and it passes every test that does not specifically look for it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.observation import ParameterUse
from swingdesk.decision_logic import trend
from swingdesk.decision_logic.trend import TrendDefinition, TrendInputs, is_uptrend
from swingdesk.derived_observations import pivots

KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


def _series(highs: list[str], lows: list[str] | None = None) -> BarSeries:
    """A series with the given highs; lows mirror them unless supplied."""
    lows = lows or [str(Decimal(h) - Decimal("5.00")) for h in highs]
    bars = []
    for offset, (high, low) in enumerate(zip(highs, lows, strict=False)):
        session = date(2025, 1, 6) + timedelta(days=offset)
        h, low_d = Decimal(high), Decimal(low)
        mid = (h + low_d) / 2
        bars.append(
            Bar(
                instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session, open=mid, high=h, low=low_d, close=mid,
                volume=1_000_000, knowledge_time=KNOWN,
            )
        )
    return BarSeries(
        instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
        knowledge_time=KNOWN, bars=tuple(bars),
    )


def _param(name: str, value: int) -> ParameterUse:
    return ParameterUse(id=name, value=str(value), provenance="test fixture")


# ------------------------------------------------------------- the look-ahead guard

def test_pivot_is_confirmed_right_bars_after_it_happened() -> None:
    """The whole design, in one assertion."""
    #                  0      1      2      3      4      5      6
    series = _series(["10", "11", "15", "12", "11", "10", "10"])
    found = pivots.pivots(series, left=2, right=2, highs=True)

    assert len(found) == 1
    pivot = found[0]
    assert pivot.index == 2, "the swing high is bar 2"
    assert pivot.confirmed_index == 4, "and it is not knowable until bar 4"
    assert pivot.price == Decimal("15")


def test_the_series_is_empty_until_the_confirmation_bar() -> None:
    """A caller reading bar 3 must not see the pivot that happened at bar 2."""
    series = _series(["10", "11", "15", "12", "11", "10", "10"])
    produced = pivots.compute(
        series, 2, 2, _param("pivot.left", 2), _param("pivot.right", 2), highs=True
    )
    values = [o.value for o in produced.observations]

    assert values[:4] == [None, None, None, None]
    assert values[4] == Decimal("15")
    assert values[5] == Decimal("15"), "carried forward - a previous high stays the previous high"


def test_inputs_from_series_filters_by_confirmation_not_occurrence() -> None:
    """The composition-level guard: decision logic sees only what was confirmed by its bar."""
    series = _series(["10", "11", "15", "12", "11", "10", "10"])
    highs = pivots.pivots(series, 2, 2, highs=True)

    at_three = trend.inputs_from_series(3, Decimal("12"), highs=highs)
    at_four = trend.inputs_from_series(4, Decimal("11"), highs=highs)

    assert at_three.swing_highs == ()
    assert at_four.swing_highs == (Decimal("15"),)


# ------------------------------------------------------------- pivot detection

def test_tie_handling_keeps_the_first_bar_of_a_plateau() -> None:
    """Strict left, non-strict right.

    Both sides strict and a flat double top registers nothing, so the structure vanishes. Both sides
    non-strict and every bar of the plateau registers, so the structure becomes noise.
    """
    series = _series(["10", "11", "15", "15", "11", "10", "10"])
    found = pivots.pivots(series, left=2, right=2, highs=True)
    assert [p.index for p in found] == [2]


def test_swing_lows_mirror_swing_highs() -> None:
    series = _series(["20", "19", "15", "18", "19", "20", "20"],
                     ["15", "14", "10", "13", "14", "15", "15"])
    found = pivots.pivots(series, left=2, right=2, highs=False)
    assert [p.index for p in found] == [2]
    assert found[0].price == Decimal("10")


def test_pivot_needs_a_full_neighbourhood_on_both_sides() -> None:
    """No pivot within `left` of the start or `right` of the end - the neighbourhood is incomplete
    there, and an incomplete neighbourhood is a guess."""
    series = _series(["15", "11", "10", "11", "15"])
    found = pivots.pivots(series, left=2, right=2, highs=True)
    assert found == ()
    assert pivots.warm_up_bars(2, 2) == 5


def test_pivot_rejects_a_nonsense_neighbourhood() -> None:
    series = _series(["10", "11", "12"])
    with pytest.raises(ValueError, match="must both be >= 1"):
        pivots.pivots(series, left=0, right=2)


# ------------------------------------------------------------- the five definitions

def test_definitions_answer_none_when_inputs_have_not_warmed_up() -> None:
    """Three-valued, deliberately.

    Collapsing "not warmed up" into False makes an instrument look like it failed a filter it was
    never tested against - and PR-001 measures which instruments each definition selects, so a
    definition that answers on fewer bars would look different for a reason unrelated to trend.
    """
    empty = TrendInputs()
    for definition in (TrendDefinition.ABOVE_LONG_MA, TrendDefinition.MA_STACK,
                       TrendDefinition.PRICE_AND_STACK, TrendDefinition.STRUCTURE):
        assert is_uptrend(definition, empty) is None


def test_definition_a_b_c_on_the_same_inputs() -> None:
    """C is strictly the conjunction of A and B when short < long, which is the reason PR-001
    expects high overlap and the reason the study is worth running rather than assumed."""
    up = TrendInputs(close=Decimal("110"), sma_short=Decimal("105"), sma_long=Decimal("100"))
    assert is_uptrend(TrendDefinition.ABOVE_LONG_MA, up) is True
    assert is_uptrend(TrendDefinition.MA_STACK, up) is True
    assert is_uptrend(TrendDefinition.PRICE_AND_STACK, up) is True

    # Price above the long MA but below the short one: A says yes, C says no.
    mixed = TrendInputs(close=Decimal("102"), sma_short=Decimal("105"), sma_long=Decimal("100"))
    assert is_uptrend(TrendDefinition.ABOVE_LONG_MA, mixed) is True
    assert is_uptrend(TrendDefinition.MA_STACK, mixed) is True
    assert is_uptrend(TrendDefinition.PRICE_AND_STACK, mixed) is False


def test_structure_needs_both_rising_highs_and_rising_lows() -> None:
    rising = TrendInputs(
        swing_highs=(Decimal("10"), Decimal("12")), swing_lows=(Decimal("8"), Decimal("9"))
    )
    assert is_uptrend(TrendDefinition.STRUCTURE, rising) is True

    # Higher highs, lower lows - a broadening pattern, not an uptrend.
    broadening = TrendInputs(
        swing_highs=(Decimal("10"), Decimal("12")), swing_lows=(Decimal("8"), Decimal("7"))
    )
    assert is_uptrend(TrendDefinition.STRUCTURE, broadening) is False


def test_adx_definition_refuses_rather_than_inventing_a_threshold() -> None:
    """regime.adx_threshold is unset, and its citation is a chart label.

    A default here would silently become the answer PR-001 exists to find.
    """
    inputs = TrendInputs(adx=Decimal("30"), plus_di=Decimal("25"), minus_di=Decimal("15"))
    with pytest.raises(trend.UnsetThreshold, match=r"regime.adx_threshold"):
        is_uptrend(TrendDefinition.ADX_DI, inputs)


def test_five_definitions_are_registered() -> None:
    """PR-001 names five candidates; the enum must not quietly grow or shrink."""
    assert [d.value for d in TrendDefinition] == ["A", "B", "C", "D", "E"]
