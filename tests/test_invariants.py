"""Property tests for the invariants in TEST_STRATEGY 2.

These are not example-based tests. Each asserts a property that must hold for *any* input, because
the failures they guard against are the ones that pass every example someone thought to write.

No network. Fixtures are synthetic and use TEST.n instruments, never real tickers - a vector naming
a real name invites someone to "fix" it against current market data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.derived_observations import atr
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.trade_management.sizing import Refusal, r_multiple, size_long


def _registry(**overrides: object) -> ParameterRegistry:
    """An in-memory registry. Tests never read the real one, so they cannot break when it changes."""
    base = {
        "atr.period": 14,
        "account.equity": 10000,
        "risk.per_trade_pct": "1.0",
        "risk.costs_allowance": "0.02",
        "risk.max_position_value": 1_000_000,
    }
    base.update(overrides)
    # A None override means UNSET, not absent. The two are different failures: unset is an expected
    # shippable state, absent means code and registry disagree. Dropping the key here would test
    # the wrong one.
    return ParameterRegistry(
        {
            key: {
                "id": key,
                "value": value,
                "provenance": "assumed:test" if value is not None else None,
                "status": "assumed" if value is not None else "unset",
                "unit": "",
                "named_in": ["test"],
            }
            for key, value in base.items()
        }
    )


def _series(closes: list[Decimal], instrument: str = "TEST.1") -> BarSeries:
    knowledge = datetime(2026, 1, 1, tzinfo=UTC)
    bars = []
    for offset, close in enumerate(closes):
        day = date(2025, 1, 1) + timedelta(days=offset)
        bars.append(
            Bar(
                instrument_id=instrument,
                interval=Interval.DAY,
                series=Series.ADJUSTED,
                event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
                session_date=day,
                open=close,
                high=close + Decimal("1"),
                low=close - Decimal("1"),
                close=close,
                volume=1000,
                knowledge_time=knowledge,
            )
        )
    return BarSeries(
        instrument_id=instrument,
        interval=Interval.DAY,
        series=Series.ADJUSTED,
        knowledge_time=knowledge,
        bars=tuple(bars),
    )


# --------------------------------------------------------------------- sizing

@given(
    entry=st.decimals(min_value=1, max_value=10_000, places=2),
    distance=st.decimals(min_value=Decimal("0.05"), max_value=500, places=2),
)
@settings(max_examples=200, deadline=None)
def test_shares_never_round_up(entry: Decimal, distance: Decimal) -> None:
    """Appendix C rounds down. Rounding up would breach the risk budget by up to one share."""
    result = size_long(entry, entry - distance, _registry())
    if isinstance(result, Refusal):
        return
    assert Decimal(result.shares) * result.risk_per_share <= result.allowed_risk


@given(
    entry=st.decimals(min_value=1, max_value=10_000, places=2),
    distance=st.decimals(min_value=Decimal("0.05"), max_value=500, places=2),
)
@settings(max_examples=200, deadline=None)
def test_planned_risk_never_exceeds_allowed(entry: Decimal, distance: Decimal) -> None:
    """The whole point of sizing: the position cannot risk more than the budget permits."""
    result = size_long(entry, entry - distance, _registry())
    if isinstance(result, Refusal):
        return
    assert result.planned_risk <= result.allowed_risk


@given(
    entry=st.decimals(min_value=1, max_value=10_000, places=2),
    stop=st.decimals(min_value=1, max_value=10_000, places=2),
)
@settings(max_examples=200, deadline=None)
def test_stop_at_or_above_entry_always_refuses(entry: Decimal, stop: Decimal) -> None:
    """A long whose stop is not below entry has no invalidation level. Never sized, always STOP."""
    assume(stop >= entry)
    result = size_long(entry, stop, _registry())
    assert isinstance(result, Refusal)
    assert result.code == "STOP"


@given(net=st.decimals(min_value=-10_000, max_value=10_000, places=2))
@settings(max_examples=100, deadline=None)
def test_r_denominator_is_the_planned_risk(net: Decimal) -> None:
    """R divides by risk planned at entry, never by anything that moved since.

    This is the invariant most often broken in systems of this kind: once the denominator follows
    the current stop, R stops being comparable across trades and every statistic built on it
    quietly changes meaning.
    """
    sized = size_long(Decimal("100.00"), Decimal("95.00"), _registry())
    assert not isinstance(sized, Refusal)
    assert r_multiple(net, sized) * sized.planned_risk == pytest.approx(net)


def test_unset_parameter_refuses_and_names_itself() -> None:
    """An unset threshold produces a coded refusal naming the parameter, never a default."""
    result = size_long(Decimal("100"), Decimal("95"), _registry(**{"risk.per_trade_pct": None}))
    assert isinstance(result, Refusal)
    assert result.code == "RISK"
    assert result.parameter_id == "risk.per_trade_pct"


# ------------------------------------------------------------------------ ATR

@given(
    closes=st.lists(
        st.decimals(min_value=10, max_value=1000, places=2), min_size=2, max_size=60
    )
)
@settings(max_examples=100, deadline=None)
def test_atr_is_never_negative(closes: list[Decimal]) -> None:
    """True range is a distance. A negative ATR would mean the formula inverted somewhere."""
    result = atr.compute(_series(closes), _registry())
    assert all(o.value is None or o.value >= 0 for o in result.observations)


@given(
    closes=st.lists(
        st.decimals(min_value=10, max_value=1000, places=2), min_size=1, max_size=40
    ),
    period=st.integers(min_value=2, max_value=20),
)
@settings(max_examples=100, deadline=None)
def test_atr_emits_nothing_before_warm_up(closes: list[Decimal], period: int) -> None:
    """A partially-warmed average is indistinguishable from a valid one downstream, so it is
    never emitted (ALGORITHM_SPEC 3)."""
    registry = _registry(**{"atr.period": period})
    result = atr.compute(_series(closes), registry)
    emitted = [i for i, o in enumerate(result.observations) if o.value is not None]
    assert all(index >= period for index in emitted)


@given(
    closes=st.lists(
        st.decimals(min_value=10, max_value=1000, places=2), min_size=20, max_size=40
    )
)
@settings(max_examples=50, deadline=None)
def test_atr_is_deterministic(closes: list[Decimal]) -> None:
    """Identical inputs always yield an identical classification.

    The course's own acceptance criterion for a detector: two observers give the same status.
    """
    series = _series(closes)
    first = atr.compute(series, _registry())
    second = atr.compute(series, _registry())
    assert [o.value for o in first.observations] == [o.value for o in second.observations]


def test_atr_carries_provenance_and_status() -> None:
    """A number arrives knowing what produced it and how trustworthy that is.

    The status is the one in this component's registry row - `Not Applicable`, which is what the
    course gives a calculation it treats as a definition. This test previously asserted `Untested`,
    a status the component emitted and the registry never granted it; tests/test_components.py now
    pins the two together so the mirror cannot drift again.
    """
    result = atr.compute(_series([Decimal(100 + i) for i in range(30)]), _registry())
    assert result.component == atr.COMPONENT
    assert result.validation_status == atr.VALIDATION == "Not Applicable"
    assert result.uses_assumed_parameters
    assert [p.id for p in result.parameters] == ["atr.period"]


# ---------------------------------------------------------------- bar ordering

def test_bar_series_rejects_unordered_input() -> None:
    """Unordered input feeding output is a named determinism hazard. Rejected at the boundary so
    downstream code can rely on ordering rather than defensively re-sorting."""
    series = _series([Decimal("100"), Decimal("101")])
    with pytest.raises(ValueError, match="ascending"):
        BarSeries(
            instrument_id=series.instrument_id,
            interval=series.interval,
            series=series.series,
            knowledge_time=series.knowledge_time,
            bars=tuple(reversed(series.bars)),
        )


def test_bar_rejects_impossible_ohlc() -> None:
    """yfinance scrapes a consumer site; its output is untrusted input."""
    with pytest.raises(ValueError):
        Bar(
            instrument_id="TEST.1",
            interval=Interval.DAY,
            series=Series.RAW,
            event_time=datetime(2026, 1, 2, tzinfo=UTC),
            session_date=date(2026, 1, 2),
            open=Decimal("10"),
            high=Decimal("9"),
            low=Decimal("8"),
            close=Decimal("8.5"),
            volume=1,
            knowledge_time=datetime(2026, 1, 2, tzinfo=UTC),
        )
