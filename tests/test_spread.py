"""The spread estimators, checked against a series whose spread is known by construction.

The first test is the one that matters. An estimator returning a plausible number for every input is
exactly the defect `REQ-VALIDATION-001` exists to catch - TradAlert's R:R gate was
`if is_long: return True` and passed seven audits. So the sample here is built by applying a KNOWN
spread to a simulated true price, and the estimators have to find it back.

Seeded, so the series is the same on every run (DETERMINISM_SPEC 3.4).
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.validation.studies import spread as study

KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
QUANTUM = Decimal("0.000001")

#: Intraday steps per session - a five-minute grid over a six-and-a-half hour session. Both papers
#: derive their estimators for a continuously observed price, so a coarse grid understates the true
#: high and low and mismeasures the estimators rather than the sample.
STEPS = 78


def _bar(session: date, open_: Decimal, high: Decimal, low: Decimal, close: Decimal) -> Bar:
    return Bar(
        instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
        event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
        session_date=session,
        open=open_.quantize(QUANTUM), high=high.quantize(QUANTUM),
        low=low.quantize(QUANTUM), close=close.quantize(QUANTUM),
        volume=1_000_000, knowledge_time=KNOWN,
    )


def _synthetic(
    days: int,
    spread: Decimal,
    seed: int,
    *,
    sigma: float = 0.015,
    overnight_gap: Decimal = Decimal(0),
) -> tuple[Bar, ...]:
    """A price path with a known proportional spread applied to it.

    The true price is a random walk sampled `STEPS` times a session. The observed bar is what a
    quoted market would print over it: the high is an offer, the low is a bid, and the close is a
    trade at one side or the other - never at the mid, which is what Abdi-Ranaldo reads.

    `overnight_gap` moves the true price between sessions without any change in spread, which is the
    confound Corwin-Schultz's adjustment exists to remove.
    """
    rng = random.Random(seed)
    half = spread / 2
    price = Decimal(100)
    bars: list[Bar] = []
    first = date(2024, 1, 1)

    for index in range(days):
        if overnight_gap and index:
            direction = Decimal(1) if index % 2 else Decimal(-1)
            price = (price * (Decimal(1) + direction * overnight_gap)).quantize(QUANTUM)
        open_true = price
        high_true = low_true = price
        for _ in range(STEPS):
            step = Decimal(str(rng.gauss(0.0, sigma / STEPS**0.5)))
            price = (price * (Decimal(1) + step)).quantize(QUANTUM)
            high_true = max(high_true, price)
            low_true = min(low_true, price)
        close_true = price
        side = Decimal(1) if rng.random() < 0.5 else Decimal(-1)
        bars.append(
            _bar(
                session=first + timedelta(days=index),
                open_=open_true,
                high=high_true * (Decimal(1) + half),
                low=low_true * (Decimal(1) - half),
                close=close_true * (Decimal(1) + side * half),
            )
        )
    return tuple(bars)


def test_a_known_spread_is_recovered() -> None:
    """The load-bearing test: build a 2% spread in, both estimators must find it back."""
    true_spread = Decimal("0.020")
    estimate = study.estimate_instrument(_synthetic(800, true_spread, seed=20260805))
    assert estimate is not None
    assert estimate.corwin_schultz_mean is not None

    # Wide on purpose. These are noisy estimators on daily bars and the claim under test is that
    # they measure the spread at all, not that they measure it to a basis point.
    for measured in (estimate.corwin_schultz_mean, estimate.abdi_ranaldo):
        assert measured is not None
        assert Decimal("0.5") < measured / true_spread < Decimal("1.6")


def test_no_spread_reads_as_no_spread_and_corwin_schultz_keeps_a_floor() -> None:
    """The other half of the pair - and the reason the measurement leads with Abdi-Ranaldo.

    On a zero-spread series Abdi-Ranaldo reads zero. Corwin-Schultz does not: flooring its negative
    two-day estimates at zero leaves a positive residue that no amount of sample removes, which is
    its documented small-spread bias. Both facts are asserted, because the floor is the thing that
    decides which estimator a cost model should be built from.
    """
    estimate = study.estimate_instrument(_synthetic(800, Decimal(0), seed=20260805))
    assert estimate is not None
    assert estimate.abdi_ranaldo is not None
    assert estimate.corwin_schultz_mean is not None

    assert estimate.abdi_ranaldo < Decimal("0.001")
    assert estimate.corwin_schultz_mean > estimate.abdi_ranaldo
    # Still far below the 2% case above, so the estimator discriminates even where it is biased.
    assert estimate.corwin_schultz_mean < Decimal("0.008")


def test_the_estimate_rises_with_the_spread() -> None:
    """Monotonicity, which survives the estimators' bias where a point estimate does not."""
    measured = []
    for true_spread in (Decimal(0), Decimal("0.005"), Decimal("0.020"), Decimal("0.050")):
        estimate = study.estimate_instrument(_synthetic(800, true_spread, seed=41))
        assert estimate is not None
        assert estimate.corwin_schultz_mean is not None
        assert estimate.abdi_ranaldo is not None
        measured.append((estimate.corwin_schultz_mean, estimate.abdi_ranaldo))

    for (previous_cs, previous_ar), (cs, ar) in pairwise(measured):
        assert cs > previous_cs
        assert ar > previous_ar


def test_the_overnight_adjustment_raises_a_gapped_pair() -> None:
    """The correction is real and it is applied.

    A gap enlarges the two-day range without enlarging either single-day range, which drives the
    estimate DOWN - the opposite of the intuition that a gap looks like a cost. Asserted at the pair,
    because in aggregate both versions are negative on a gapping name and the zero rule floors them
    to the same number.
    """
    bars = _synthetic(6, Decimal("0.020"), seed=7, overnight_gap=Decimal("0.08"))
    previous, current = bars[0], bars[1]
    assert current.low > previous.high

    adjusted = study.corwin_schultz_pair(previous, current, adjust_overnight=True)
    unadjusted = study.corwin_schultz_pair(previous, current, adjust_overnight=False)
    assert adjusted is not None and unadjusted is not None
    assert adjusted > unadjusted


def test_gaps_break_corwin_schultz_and_not_abdi_ranaldo() -> None:
    """The second reason the measurement leads with Abdi-Ranaldo, and it is not a small effect.

    On a name that gaps every session, Corwin-Schultz loses a real 2% spread entirely even with the
    adjustment applied, because the enlarged two-day range makes almost every pair negative.
    Abdi-Ranaldo reads through it. A cost model built from Corwin-Schultz alone would price gapping
    instruments as free to trade.
    """
    bars = _synthetic(800, Decimal("0.020"), seed=7, overnight_gap=Decimal("0.08"))
    estimate = study.estimate_instrument(bars)
    assert estimate is not None
    assert estimate.corwin_schultz_mean is not None
    assert estimate.abdi_ranaldo is not None

    assert estimate.corwin_schultz_mean < Decimal("0.005")
    assert estimate.abdi_ranaldo > Decimal("0.015")


def test_per_side_is_half_the_spread() -> None:
    """The conversion DR-004's 5bps assumption lives on: 5bps per side IS a 10bps spread."""
    assert study.per_side_bps(Decimal("0.0010")) == Decimal(5)
    assert study.per_side_bps(Decimal("0.0040")) == Decimal(20)


def test_discarding_negatives_reads_higher_than_zeroing_them() -> None:
    """Both treatments bias upward; discarding biases harder, and the result records which was used."""
    bars = _synthetic(800, Decimal("0.002"), seed=99)
    zeroed = study.estimate_instrument(bars, negative_rule=study.NegativeRule.ZERO)
    discarded = study.estimate_instrument(bars, negative_rule=study.NegativeRule.DISCARD)
    assert zeroed is not None and discarded is not None
    assert zeroed.corwin_schultz_mean is not None
    assert discarded.corwin_schultz_mean is not None

    assert discarded.corwin_schultz_mean > zeroed.corwin_schultz_mean
    assert zeroed.negative_pairs > 0
    assert zeroed.negative_fraction > 0


def test_zero_range_sessions_are_skipped_not_read_as_zero_cost() -> None:
    """A halt is not a free market. The pair is dropped and the drop is counted."""
    flat = _bar(date(2024, 3, 1), Decimal(50), Decimal(50), Decimal(50), Decimal(50))
    normal = _bar(date(2024, 3, 4), Decimal(50), Decimal("50.5"), Decimal("49.5"), Decimal(50))
    assert study.corwin_schultz_pair(flat, normal) is None
    assert study.abdi_ranaldo_pair_squared(flat, normal) is None

    estimate = study.estimate_instrument((flat, normal, normal, flat))
    assert estimate is None or estimate.pairs_skipped > 0


def test_the_same_series_gives_the_same_digits() -> None:
    """Determinism at the digit, not at a tolerance - the estimator is Decimal all the way down."""
    bars = _synthetic(400, Decimal("0.01"), seed=1234)
    first = study.estimate_instrument(bars)
    second = study.estimate_instrument(bars)
    assert first is not None and second is not None
    assert first == second
    assert str(first.abdi_ranaldo) == str(second.abdi_ranaldo)


def test_a_series_too_short_to_pair_returns_nothing() -> None:
    """One bar is not a two-day estimator's input, and returning zero would be a lie about cost."""
    single = _synthetic(1, Decimal("0.01"), seed=3)
    assert study.estimate_instrument(single) is None
    assert study.estimate_instrument(()) is None


def test_summarise_reports_order_statistics_the_population_contains() -> None:
    """Nearest-rank, so every reported percentile is a value some instrument actually has."""
    estimates = [
        study.SpreadEstimate(
            instrument_id=f"TEST.{index}", pairs_used=10, pairs_skipped=0, negative_pairs=0,
            corwin_schultz=Decimal(index) / Decimal(1000),
            corwin_schultz_mean=Decimal(index) / Decimal(1000),
            abdi_ranaldo=Decimal(index) / Decimal(2000),
        )
        for index in range(1, 11)
    ]
    summary = study.summarise(estimates)
    assert summary.instruments == 10
    assert summary.estimated == 10
    assert summary.corwin_schultz[50] == Decimal("0.005")
    assert summary.corwin_schultz[90] == Decimal("0.009")
    assert summary.corwin_schultz_mean[50] == Decimal("0.005")
    assert summary.abdi_ranaldo[50] == Decimal("0.0025")
    assert all(value in {e.corwin_schultz for e in estimates}
               for value in summary.corwin_schultz.values())
