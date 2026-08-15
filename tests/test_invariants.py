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
        "risk.costs_bp_usd": "50",
        "risk.costs_floor_usd": "0.02",
        "risk.costs_bp_cad": "50",
        "risk.costs_floor_cad": "0.02",
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
    result = size_long(entry, entry - distance, "USD", _registry())
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
    result = size_long(entry, entry - distance, "USD", _registry())
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
    result = size_long(entry, stop, "USD", _registry())
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
    sized = size_long(Decimal("100.00"), Decimal("95.00"), "USD", _registry())
    assert not isinstance(sized, Refusal)
    assert r_multiple(net, sized) * sized.planned_risk == pytest.approx(net)


def test_unset_parameter_refuses_and_names_itself() -> None:
    """An unset threshold produces a coded refusal naming the parameter, never a default."""
    result = size_long(
        Decimal("100"), Decimal("95"), "USD", _registry(**{"risk.per_trade_pct": None})
    )
    assert isinstance(result, Refusal)
    assert result.code == "RISK"
    assert result.parameter_id == "risk.per_trade_pct"


# ----------------------------------------------------------- costs (DR-010)

def test_costs_use_the_floor_below_the_crossover_price() -> None:
    """At 50bp and a $0.02 floor, the crossover is $4 - below it the floor governs, unchanged from
    a flat constant's behaviour at that end of the range."""
    sized = size_long(Decimal("2.00"), Decimal("1.00"), "USD", _registry())
    assert not isinstance(sized, Refusal)
    assert sized.costs_per_share == Decimal("0.02")  # floor, not 50bp * 2.00 = 0.01


def test_costs_scale_with_price_above_the_crossover() -> None:
    """Above the crossover the proportional term governs - the fix DR-009 confessed it needed."""
    sized = size_long(Decimal("200.00"), Decimal("190.00"), "USD", _registry())
    assert not isinstance(sized, Refusal)
    assert sized.costs_per_share == Decimal("1.0000")  # 50bp * 200.00, not the flat floor


def test_understating_costs_is_impossible_by_construction() -> None:
    """max(floor, proportional) can never charge less than either term alone would - the unsafe
    direction (smaller costs -> more shares) is closed at the formula, not by a price band."""
    for entry in (Decimal("1"), Decimal("50"), Decimal("500"), Decimal("9999")):
        sized = size_long(entry, entry - Decimal("1"), "USD", _registry())
        if isinstance(sized, Refusal):
            continue
        floor = Decimal("0.02")
        proportional = (Decimal(50) / Decimal(10_000) * entry).quantize(Decimal("0.0001"))
        assert sized.costs_per_share >= floor
        assert sized.costs_per_share >= proportional


def test_an_unsupported_currency_refuses_rather_than_guesses() -> None:
    """Unset is not default. A currency with no cost parameters refuses; it does not fall back to
    USD or to any other currency's numbers."""
    result = size_long(Decimal("100"), Decimal("95"), "EUR", _registry())
    assert isinstance(result, Refusal)
    assert result.code == "RISK"
    assert "EUR" in result.reason


def test_cad_and_usd_can_be_priced_independently() -> None:
    """The two currencies read different parameters - proven by making them disagree, not just by
    both defaulting to the same fixture value."""
    registry = _registry(**{"risk.costs_bp_cad": "200", "risk.costs_floor_cad": "0.02"})
    usd = size_long(Decimal("200.00"), Decimal("190.00"), "USD", registry)
    cad = size_long(Decimal("200.00"), Decimal("190.00"), "CAD", registry)
    assert not isinstance(usd, Refusal)
    assert not isinstance(cad, Refusal)
    assert usd.costs_per_share != cad.costs_per_share


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


# --------------------------------------------------------------------- spread estimators
#
# An estimator that reads ordinary volatility as transaction cost is the failure PR-008 nearly
# shipped: the per-pair Corwin-Schultz form reported ~+80bp of round-trip spread on bars containing
# none, and it passed every example test written for it because it ran, returned a plausible
# number, and had the right units.
#
# The guard is discovery-based rather than a list. Any new estimator added to the module is covered
# the moment it exists, without anyone remembering to write this test for it - which is the whole
# difference between a gate and a habit.

#: Estimators exempt from the null check, each with the reason. Adding a name here is a visible
#: decision someone made, not a silent omission - the same discipline pyproject uses for untyped
#: imports and ignored lint rules.
KNOWN_BIASED_ESTIMATORS = {
    "corwin_schultz_per_pair": (
        "documented Jensen bias, retained only as a diagnostic. Its magnitude is pinned by "
        "test_the_per_pair_form_is_biased_and_stays_biased, so it is measured rather than ignored."
    ),
}

#: What the null check tolerates, as a round-trip proportion, applied to the MEDIAN over seeds.
#:
#: The first version of this constant was set from a single draw (0.001451) and asserted on that one
#: draw. It was wrong: across 30 seeds the same call ranges 0.000000 to 0.004240 and **8 of them
#: exceed this tolerance**. A gate built to catch an estimator that manufactures signal was itself a
#: single sample of a noisy quantity - the identical error PR-008's report made in prose and
#: DR-005's test made in code, all three on the same estimator.
#:
#: So the assertions below sweep seeds and test the distribution. Medians, measured:
#:
#:     corwin_schultz           0.000000
#:     abdi_ranaldo             0.000000
#:     corwin_schultz_per_pair  ~0.008     <- must fail
NULL_SPREAD_TOLERANCE = 0.002

#: Seeds swept by every distributional assertion here. Enough that a lucky draw cannot carry a claim,
#: few enough that the suite stays fast at SWEEP_DAYS x SWEEP_STEPS per seed.
SWEEP_SEEDS = tuple(range(12))
SWEEP_DAYS = 400
SWEEP_STEPS = 400


def _discovered_estimators() -> dict[str, object]:
    """Every public spread estimator in the module, found by signature rather than by name.

    An estimator takes (highs, lows, closes) and returns an optional estimate as the first element
    of its tuple. `beta_gamma` shares the parameters but returns per-pair inputs, and is excluded by
    the return annotation - which is also how a genuinely new estimator gets picked up.
    """
    import inspect

    from swingdesk.validation.studies import effective_spread

    found: dict[str, object] = {}
    for name, function in inspect.getmembers(effective_spread, inspect.isfunction):
        if name.startswith("_") or function.__module__ != effective_spread.__name__:
            continue
        signature = inspect.signature(function)
        if list(signature.parameters)[:3] != ["highs", "lows", "closes"]:
            continue
        if "float | None" not in str(signature.return_annotation):
            continue
        found[name] = function
    return found


def test_estimator_discovery_still_works() -> None:
    """The guard below is worthless if discovery silently finds nothing.

    A rename or a signature change that breaks discovery must fail here, loudly, rather than turn
    `test_no_estimator_manufactures_a_spread` into a no-op that keeps passing.
    """
    discovered = _discovered_estimators()
    assert "corwin_schultz" in discovered
    assert "abdi_ranaldo" in discovered
    assert "beta_gamma" not in discovered, "beta_gamma returns pair inputs, not an estimate"
    assert set(KNOWN_BIASED_ESTIMATORS) <= set(discovered), (
        "an exemption names an estimator that no longer exists - delete the exemption"
    )


def _sweep(name: str, true_spread: float) -> list[float]:
    """One estimator's readings across SWEEP_SEEDS, in canonical seed order."""
    from tests.conftest import synthetic_ohlc

    function = _discovered_estimators()[name]
    readings: list[float] = []
    for seed in SWEEP_SEEDS:
        highs, lows, closes = synthetic_ohlc(
            SWEEP_DAYS, true_spread, seed=seed, steps=SWEEP_STEPS
        )
        value = function(highs, lows, closes)[0]  # type: ignore[operator]
        assert value is not None, f"{name} declined on seed {seed}"
        readings.append(value)
    return readings


@pytest.mark.parametrize("name", sorted(_discovered_estimators()))
def test_no_estimator_manufactures_a_spread(name: str) -> None:
    """On bars with no spread in them, the MEDIAN reading across seeds must be near zero.

    Median across a seed sweep, never one draw. On a spreadless series Abdi-Ranaldo clamps to zero
    about half the time and scatters to ~0.004 the rest, so a single seed proves nothing in either
    direction - which is how three separate artefacts in this repository came to rest on one.
    """
    if name in KNOWN_BIASED_ESTIMATORS:
        pytest.skip(f"{name}: {KNOWN_BIASED_ESTIMATORS[name]}")

    readings = sorted(_sweep(name, 0.0))
    median = readings[len(readings) // 2]

    # Measured against the known-biased form on the SAME sweep, not against a constant. An absolute
    # threshold here would be calibration-dependent - it moves with the intraday grid and the series
    # length - and picking one that passes is how the first version of this gate came to assert a
    # single lucky draw. A ratio cancels the calibration out.
    reference = sorted(_sweep("corwin_schultz_per_pair", 0.0))
    biased_median = reference[len(reference) // 2]

    assert median < biased_median / 2, (
        f"{name} median {median:.6f} round-trip on bars containing NO spread, against "
        f"{biased_median:.6f} for the known-biased per-pair form on the same sweep. "
        f"It is measuring volatility, not cost. Readings {readings[0]:.6f}..{readings[-1]:.6f}"
    )
    assert median < NULL_SPREAD_TOLERANCE * 2, (
        f"{name} median {median:.6f} exceeds even the generous absolute bound - "
        f"the ratio test above may be passing only because the reference is also inflated"
    )


@pytest.mark.parametrize("name", sorted(_discovered_estimators()))
def test_every_estimator_clamps_far_less_often_when_a_spread_is_present(name: str) -> None:
    """The sign property, which needs no calibration at all - and is what settled DR-005 vs PR-008.

    An estimator floored at zero clamps when its underlying quantity comes out negative. With no
    spread present that is noise about zero, so it should clamp often; with a real spread the
    quantity is shifted positive and clamping should become rare.

    This holds whatever the intraday grid or the volatility is, which is precisely why it can decide
    a disagreement that was entirely about calibration. On real bars the clamp rate was 19.1%
    against 45.5% for spreadless synthetic at matched volatility.
    """
    if name in KNOWN_BIASED_ESTIMATORS:
        pytest.skip(f"{name}: {KNOWN_BIASED_ESTIMATORS[name]}")

    without = sum(1 for value in _sweep(name, 0.0) if value == 0.0)
    with_spread = sum(1 for value in _sweep(name, 0.020) if value == 0.0)

    assert with_spread < without or without == 0, (
        f"{name} clamps {with_spread}/{len(SWEEP_SEEDS)} times with a 2% spread present and "
        f"{without}/{len(SWEEP_SEEDS)} without one - it is not responding to the spread at all"
    )


@pytest.mark.parametrize("true_spread", [0.010, 0.020])
def test_every_estimator_moves_with_the_real_spread(true_spread: float) -> None:
    """Returning zero always would pass the null check. This is the other half of the property."""
    for name in sorted(_discovered_estimators()):
        if name in KNOWN_BIASED_ESTIMATORS:
            continue
        readings = sorted(_sweep(name, true_spread))
        median = readings[len(readings) // 2]
        assert median > true_spread / 2, (
            f"{name} median {median:.6f} against a true spread of {true_spread} - "
            f"an estimator that cannot see a spread this large is not measuring one"
        )
