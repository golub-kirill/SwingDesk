"""Breadth and the regime classifier.

The fit/apply split is tested first, because a classifier that fits on the window it labels is the
exact hindsight PR-002's null describes - and it produces a beautifully separated result.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.observation import Observation, ObservationSeries
from swingdesk.derived_observations import breadth, regime
from swingdesk.derived_observations.regime import Classifier, Variant

KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


def _series(instrument_id: str, closes: list[str], start: date = date(2025, 1, 6)) -> BarSeries:
    bars = []
    for offset, close in enumerate(closes):
        session = start + timedelta(days=offset)
        c = Decimal(close)
        bars.append(
            Bar(
                instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session, open=c, high=c, low=c, close=c,
                volume=1_000_000, knowledge_time=KNOWN,
            )
        )
    return BarSeries(
        instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
        knowledge_time=KNOWN, bars=tuple(bars),
    )


def _sma(series: BarSeries, values: list[str | None]) -> ObservationSeries:
    return ObservationSeries(
        component="M25-T0382-v5.0", component_version=1, instrument_id=series.instrument_id,
        units="price units", parameters=(), validation_status="Not Applicable",
        knowledge_time=KNOWN,
        observations=tuple(
            Observation(
                component="M25-T0382-v5.0", component_version=1,
                instrument_id=series.instrument_id, event_time=bar.event_time,
                value=None if value is None else Decimal(value),
                units="price units", knowledge_time=KNOWN,
            )
            for bar, value in zip(series.bars, values, strict=False)
        ),
    )


# ------------------------------------------------------------------ breadth

def test_breadth_counts_only_members_with_a_warmed_up_average() -> None:
    """A young member is excluded from BOTH sides.

    Counting it as "not above" reports a market as broadly weak whenever many members are young -
    a statement about listing dates, not about breadth.
    """
    a = _series("A", ["10", "10", "10"])
    b = _series("B", ["10", "10", "10"])
    series = {"A": a, "B": b}
    smas = {"A": _sma(a, ["5", "5", "5"]), "B": _sma(b, [None, None, "20"])}

    points = breadth.above_average(series, smas, min_members=1)
    assert [p.members for p in points] == [1, 1, 2]
    assert points[0].value == Decimal(1), "only A counted, and A is above"
    assert points[2].value == Decimal("0.5"), "A above, B below"


def test_breadth_declines_below_the_member_floor() -> None:
    """A ratio over three members and over sixty are different claims."""
    a = _series("A", ["10", "10"])
    points = breadth.above_average({"A": a}, {"A": _sma(a, ["5", "5"])}, min_members=10)
    assert [p.value for p in points] == [None, None]
    assert [p.members for p in points] == [1, 1]


def test_breadth_excludes_a_member_that_did_not_trade_that_session() -> None:
    a = _series("A", ["10", "10", "10"])
    b = _series("B", ["10", "10"], start=date(2025, 1, 7))
    smas = {"A": _sma(a, ["5", "5", "5"]), "B": _sma(b, ["20", "20"])}

    points = breadth.above_average({"A": a, "B": b}, smas, min_members=1)
    assert [p.members for p in points] == [1, 2, 2]


def test_breadth_rejects_a_nonsense_floor() -> None:
    a = _series("A", ["10"])
    with pytest.raises(ValueError, match="min_members must be >= 1"):
        breadth.above_average({"A": a}, {"A": _sma(a, ["5"])}, min_members=0)


# ------------------------------------------------------------------ fit / apply

def test_an_unfitted_classifier_refuses_rather_than_inventing_a_threshold() -> None:
    """A classifier that invents a boundary is one fitted on whatever it happens to be looking at."""
    with pytest.raises(regime.UnfittedClassifier, match="fit it on a training window"):
        Classifier(Variant.BREADTH_MEDIAN).label(Decimal("0.5"), None)


def test_thresholds_come_from_the_training_window_only() -> None:
    """The fit/apply split is the whole point.

    Thresholds fitted on a low-breadth training window must keep labelling a later high-breadth
    period as HIGH. A classifier refitted on the labelled window would call it average - which is
    the hindsight PR-002's null describes.
    """
    train = [Decimal("0.10"), Decimal("0.20"), Decimal("0.30"), Decimal("0.40")]
    fitted = regime.fit(Variant.BREADTH_MEDIAN, train, [])

    assert fitted.label(Decimal("0.90"), None) == "BREADTH_HIGH"
    assert fitted.label(Decimal("0.05"), None) == "BREADTH_LOW"
    # Refitting on a later, higher window moves the boundary from 0.30 to 0.85, so the SAME
    # reading changes regime. That is the hindsight this split exists to prevent.
    refitted = regime.fit(Variant.BREADTH_MEDIAN, [Decimal("0.85"), Decimal("0.95")], [])
    assert fitted.label(Decimal("0.50"), None) == "BREADTH_HIGH"
    assert refitted.label(Decimal("0.50"), None) == "BREADTH_LOW", "same value, different answer"


def test_terciles_split_into_three_populated_regimes() -> None:
    train = [Decimal(str(v / 100)) for v in range(0, 100, 5)]
    fitted = regime.fit(Variant.BREADTH_TERCILE, train, [])
    labels = {fitted.label(value, None) for value in train}
    assert labels == {"BREADTH_LOW", "BREADTH_MID", "BREADTH_HIGH"}


def test_a_missing_input_yields_no_label_not_a_default_one() -> None:
    fitted = regime.fit(Variant.BREADTH_X_VOL, [Decimal("0.4"), Decimal("0.6")],
                        [Decimal("0.01"), Decimal("0.03")])
    assert fitted.label(None, Decimal("0.02")) is None
    assert fitted.label(Decimal("0.5"), None) is None
    assert fitted.label(Decimal("0.7"), Decimal("0.04")) == "LOUD_STRONG"
    assert fitted.label(Decimal("0.3"), Decimal("0.005")) == "QUIET_WEAK"


def test_every_variant_declares_its_regimes() -> None:
    for variant in Variant:
        fitted = Classifier(variant, breadth_cuts=(Decimal("0.4"), Decimal("0.6")),
                            volatility_cuts=(Decimal("0.02"), Decimal("0.04")), fitted_on=10)
        assert len(fitted.regimes) >= 2
        assert len(set(fitted.regimes)) == len(fitted.regimes)


def test_fit_refuses_a_window_too_small_to_fit() -> None:
    with pytest.raises(ValueError, match="not enough breadth"):
        regime.fit(Variant.BREADTH_TERCILE, [Decimal("0.5")], [])


def test_four_variants_are_registered() -> None:
    """PR-002 named four. Not a menu to extend after seeing results."""
    assert [v.value for v in Variant] == [
        "BREADTH_TERCILE", "BREADTH_MEDIAN", "VOL_TERCILE", "BREADTH_X_VOL"
    ]


# ------------------------------------------------------------------ selection rule

def test_label_changes_counts_flips_and_ignores_gaps() -> None:
    """PR-002 selects the most STABLE variant on validation, never the most separating one."""
    assert regime.label_changes(["A", "A", "B", "B", "A"]) == 2
    assert regime.label_changes(["A", None, "A"]) == 0, "a gap is not a flip"
    assert regime.label_changes([None, None]) == 0
    assert regime.label_changes(["A", "B", "A", "B"]) == 3
