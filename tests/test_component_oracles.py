"""Independent checks on components that have no external oracle.

A golden vector freezes behaviour; it does not prove correctness. If a hand-derivation and an
implementation share the same misreading of the definition, they agree and the vector passes. These
tests attack that from two directions that a vector cannot:

**Differential** - recompute breadth with an unrelated implementation (pandas) over randomised
panels. Different code, same definition. Catches an implementation bug that a small authored case
happened not to reach.

**Metamorphic** - the technique for a component with no oracle at all. You cannot say what the right
answer is, but you can say how it MUST CHANGE when the input changes. Breadth is a ratio of counts,
so scaling every price leaves it alone. Regime thresholds are percentiles, so shifting or scaling
every reading leaves the labels alone. A component that fails those is wrong regardless of what any
expected value says.

Both are free: synthetic panels, no vendor, no network.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.observation import Observation, ObservationSeries
from swingdesk.derived_observations import breadth, regime
from swingdesk.derived_observations.regime import Variant

UTC = timezone.utc
KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


def _panel(closes: dict[str, list[Decimal]], smas: dict[str, list[Decimal | None]]):
    sessions = [date(2025, 1, 6) + timedelta(days=i) for i in range(len(next(iter(closes.values()))))]
    series_by_id, sma_by_id = {}, {}
    for member, values in closes.items():
        bars = tuple(
            Bar(
                instrument_id=member, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(s.year, s.month, s.day, tzinfo=UTC), session_date=s,
                open=v, high=v, low=v, close=v, volume=1_000_000, knowledge_time=KNOWN,
            )
            for s, v in zip(sessions, values)
        )
        series_by_id[member] = BarSeries(
            instrument_id=member, interval=Interval.DAY, series=Series.RAW,
            knowledge_time=KNOWN, bars=bars,
        )
        sma_by_id[member] = ObservationSeries(
            component="M25-T0382-v5.0", component_version=1, instrument_id=member,
            units="price units", parameters=(), validation_status="Not Applicable",
            knowledge_time=KNOWN,
            observations=tuple(
                Observation(
                    component="M25-T0382-v5.0", component_version=1, instrument_id=member,
                    event_time=bar.event_time, value=v, units="price units", knowledge_time=KNOWN,
                )
                for bar, v in zip(bars, smas[member])
            ),
        )
    return series_by_id, sma_by_id


def _random_panel(seed: int, members: int = 12, sessions: int = 40):
    rng = random.Random(seed)
    closes, smas = {}, {}
    for index in range(members):
        member = f"TEST.{index}"
        closes[member] = [Decimal(rng.randrange(5000, 20000)) / 100 for _ in range(sessions)]
        smas[member] = [
            None if rng.random() < 0.15 else Decimal(rng.randrange(5000, 20000)) / 100
            for _ in range(sessions)
        ]
    return closes, smas


# --------------------------------------------------------------- differential

@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_breadth_matches_an_independent_pandas_implementation(seed: int) -> None:
    """Same definition, unrelated code.

    A bug the authored vectors happened not to reach would have to be reproduced identically here
    to survive, and a DataFrame comparison shares no code with the loop under test.
    """
    pandas = pytest.importorskip("pandas")

    closes, smas = _random_panel(seed)
    series_by_id, sma_by_id = _panel(closes, smas)
    produced = breadth.above_average(series_by_id, sma_by_id, min_members=1)

    close_frame = pandas.DataFrame({m: [float(v) for v in vs] for m, vs in closes.items()})
    sma_frame = pandas.DataFrame(
        {m: [None if v is None else float(v) for v in vs] for m, vs in smas.items()}
    )
    above = (close_frame > sma_frame) & sma_frame.notna()
    expected = above.sum(axis=1) / sma_frame.notna().sum(axis=1)

    for index, point in enumerate(produced):
        assert point.value is not None
        assert abs(float(point.value) - float(expected.iloc[index])) < 1e-12


# --------------------------------------------------------------- invariants

@pytest.mark.parametrize("seed", [11, 12, 13])
def test_breadth_stays_inside_its_declared_output_range(seed: int) -> None:
    closes, smas = _random_panel(seed)
    for point in breadth.above_average(*_panel(closes, smas), min_members=1):
        if point.value is not None:
            assert Decimal(0) <= point.value <= Decimal(1)


def test_k_of_n_above_is_exactly_k_over_n() -> None:
    """The definition, stated as arithmetic rather than as a case."""
    for k in range(6):
        closes = {f"TEST.{i}": [Decimal(10)] for i in range(5)}
        smas = {f"TEST.{i}": [Decimal(5) if i < k else Decimal(20)] for i in range(5)}
        point = breadth.above_average(*_panel(closes, smas), min_members=1)[0]
        assert point.value == Decimal(k) / Decimal(5)


# --------------------------------------------------------------- metamorphic

@pytest.mark.parametrize("factor", ["2", "0.5", "137.25"])
def test_breadth_is_invariant_to_scaling_every_price(factor: str) -> None:
    """A ratio of counts cannot depend on the currency the prices are quoted in.

    Scale closes and averages together and every comparison is preserved, so the answer must be
    identical - not approximately, identically.
    """
    closes, smas = _random_panel(21)
    base = [p.value for p in breadth.above_average(*_panel(closes, smas), min_members=1)]

    k = Decimal(factor)
    scaled_closes = {m: [v * k for v in vs] for m, vs in closes.items()}
    scaled_smas = {m: [None if v is None else v * k for v in vs] for m, vs in smas.items()}
    scaled = [p.value for p in breadth.above_average(*_panel(scaled_closes, scaled_smas),
                                                     min_members=1)]
    assert base == scaled


def test_breadth_is_invariant_to_member_order() -> None:
    """It is a set operation. Iteration order feeding a result is the named determinism hazard."""
    closes, smas = _random_panel(22)
    base = [p.value for p in breadth.above_average(*_panel(closes, smas), min_members=1)]

    keys = list(closes)
    random.Random(99).shuffle(keys)
    shuffled_closes = {k: closes[k] for k in keys}
    shuffled_smas = {k: smas[k] for k in keys}
    assert base == [
        p.value for p in breadth.above_average(*_panel(shuffled_closes, shuffled_smas),
                                               min_members=1)
    ]


@pytest.mark.parametrize("variant", [Variant.BREADTH_MEDIAN, Variant.BREADTH_TERCILE])
@pytest.mark.parametrize("shift", ["0.1", "-0.05", "10"])
def test_regime_labels_are_invariant_to_shifting_every_reading(variant, shift: str) -> None:
    """Percentile thresholds are equivariant, so labels must be shift-invariant.

    Shift the training window and the query by the same amount: the cut moves with the data and the
    label cannot change. A classifier that failed this would be comparing against an absolute level
    it never declared.
    """
    train = [Decimal(v) for v in ("0.10", "0.25", "0.40", "0.55", "0.70", "0.85")]
    queries = [Decimal(v) for v in ("0.15", "0.45", "0.80")]
    fitted = regime.fit(variant, train, [])
    base = [fitted.label(q, None) for q in queries]

    delta = Decimal(shift)
    shifted = regime.fit(variant, [v + delta for v in train], [])
    assert [shifted.label(q + delta, None) for q in queries] == base


@pytest.mark.parametrize("factor", ["2", "0.25"])
def test_regime_labels_are_invariant_to_positive_scaling(factor: str) -> None:
    """Same argument for a monotone rescale - the ordering is what the percentile reads."""
    train = [Decimal(v) for v in ("0.10", "0.25", "0.40", "0.55", "0.70", "0.85")]
    queries = [Decimal(v) for v in ("0.15", "0.45", "0.80")]
    fitted = regime.fit(Variant.BREADTH_TERCILE, train, [])
    base = [fitted.label(q, None) for q in queries]

    k = Decimal(factor)
    scaled = regime.fit(Variant.BREADTH_TERCILE, [v * k for v in train], [])
    assert [scaled.label(q * k, None) for q in queries] == base


def test_regime_is_monotone_in_breadth() -> None:
    """Raising the reading can never move a label down the ordered bands.

    Not a metamorphic relation about the whole output - a statement about the SHAPE of the map, and
    the one property a threshold classifier cannot be allowed to violate.
    """
    order = {"BREADTH_LOW": 0, "BREADTH_MID": 1, "BREADTH_HIGH": 2}
    train = [Decimal(v) / Decimal(100) for v in range(0, 100, 5)]
    fitted = regime.fit(Variant.BREADTH_TERCILE, train, [])

    previous = -1
    for step in range(0, 101):
        label = fitted.label(Decimal(step) / Decimal(100), None)
        assert order[label] >= previous
        previous = order[label]


def test_every_label_is_one_the_variant_declares() -> None:
    train = [Decimal(v) / Decimal(100) for v in range(0, 100, 5)]
    volatility = [Decimal(v) / Decimal(1000) for v in range(1, 40)]
    for variant in Variant:
        fitted = regime.fit(variant, train, volatility)
        declared = set(fitted.regimes)
        for b in train:
            for v in volatility[:5]:
                label = fitted.label(b, v)
                assert label is None or label in declared
