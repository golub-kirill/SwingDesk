"""The spread estimators, checked by handing them a spread they are supposed to find.

The load-bearing tests are `test_recovers_a_known_spread` and
`test_a_zero_spread_market_does_not_manufacture_one`. Together they are what caught the defect this
module now documents: solving Corwin & Schultz per two-day pair and averaging afterwards reports
roughly +80bp of round-trip spread on bars containing none, because alpha is a difference of square
roots and the average of a nonlinear function is not the function of the average. Against a question
posed at 10bp round trip, that form would have produced a confident wrong answer.

Everything else guards an edge a clean 2,000-day simulation never reaches.
"""

from __future__ import annotations

import math
import random
from decimal import Decimal

import pytest

from swingdesk.validation.studies import effective_spread as spread

SEED = 20260809

#: Intraday steps per session. The estimators assume a continuously observed diffusion, so a coarse
#: path under-samples the one-day range more than the two-day range and biases CS downward. At 1,000
#: the artefact is small; the tolerances below were set from the measured behaviour at this density,
#: not guessed. Real sessions carry far more prints than this.
INTRADAY_STEPS = 1000
DAILY_VOLATILITY = 0.02


def _simulate(
    days: int, proportional_spread: float, seed: int = SEED
) -> tuple[list[float], list[float], list[float]]:
    """Days of bars carrying a known spread, built the way the estimators assume.

    An efficient price walks intraday; the observed high and low are the true extremes widened by
    the half-spread; the close lands on the bid or the ask. That is the microstructure both papers
    model, and the simulation is deliberately not written in terms of either formula - so agreement
    is evidence rather than circularity.
    """
    rng = random.Random(seed)
    half = proportional_spread / 2
    step_volatility = DAILY_VOLATILITY / math.sqrt(INTRADAY_STEPS)

    price = 100.0
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []

    for _ in range(days):
        high = low = price
        for _ in range(INTRADAY_STEPS):
            price *= math.exp(rng.gauss(0.0, step_volatility))
            high = max(high, price)
            low = min(low, price)
        highs.append(high * (1 + half))
        lows.append(low * (1 - half))
        closes.append(price * (1 + half if rng.random() < 0.5 else 1 - half))

    return highs, lows, closes


@pytest.mark.parametrize("true_spread", [0.005, 0.010, 0.020])
def test_recovers_a_known_spread(true_spread: float) -> None:
    """Both estimators land within 25% of a spread that was put there on purpose.

    25% is loose because these estimators are noisy by construction, and tight enough to catch the
    error that actually matters: returning the half-spread where the round trip is meant, or the
    reverse, which is a factor of two.
    """
    highs, lows, closes = _simulate(2000, true_spread)

    cs, cs_pairs, cs_negative = spread.corwin_schultz(highs, lows, closes)
    ar, ar_pairs, ar_negative = spread.abdi_ranaldo(highs, lows, closes)

    assert cs is not None and ar is not None
    assert cs_pairs > 1900 and ar_pairs > 1900
    assert not cs_negative and not ar_negative

    assert cs == pytest.approx(true_spread, rel=0.25), f"CS {cs} vs {true_spread}"
    assert ar == pytest.approx(true_spread, rel=0.25), f"AR {ar} vs {true_spread}"


def test_a_zero_spread_market_does_not_manufacture_one() -> None:
    """With no spread in the data, both estimates collapse toward zero.

    This is the test that rejected the per-pair form. An estimator that reads ordinary volatility as
    cost makes every instrument look expensive and the whole study meaningless.
    """
    highs, lows, closes = _simulate(2000, 0.0)

    cs, _, _ = spread.corwin_schultz(highs, lows, closes)
    ar, _, _ = spread.abdi_ranaldo(highs, lows, closes)

    assert cs is not None and ar is not None
    # An order of magnitude below the smallest spread the recovery test resolves.
    assert cs < 0.0015, f"CS invented {cs} from a spreadless market"
    assert ar < 0.0015, f"AR invented {ar} from a spreadless market"


def test_the_per_pair_form_is_biased_and_stays_biased() -> None:
    """The rejected form, pinned so nobody quietly reinstates it.

    It reports a large spread on spreadless bars, and the offset does not shrink as the sample
    grows - which is exactly why averaging more data cannot rescue it.
    """
    highs, lows, closes = _simulate(2000, 0.0)
    biased, _, _ = spread.corwin_schultz_per_pair(highs, lows, closes)
    pooled, _, _ = spread.corwin_schultz(highs, lows, closes)

    assert biased is not None and pooled is not None
    assert biased > 0.005, "the documented bias should be plainly visible"
    assert biased > pooled * 4, "and far larger than the pooled estimate on the same bars"


def test_pooling_matches_solving_once_on_the_averages() -> None:
    """The pooled estimate is exactly equation 14 applied to mean beta and mean gamma."""
    highs, lows, closes = _simulate(200, 0.004)
    pairs = spread.beta_gamma(highs, lows, closes)

    beta = sum(value for value, _ in pairs) / len(pairs)
    gamma = sum(value for _, value in pairs) / len(pairs)

    pooled, count, _ = spread.corwin_schultz(highs, lows, closes)
    assert count == len(pairs)
    assert pooled == pytest.approx(spread.spread_from(beta, gamma))


def test_beta_equal_to_gamma_means_no_spread() -> None:
    """The formula's own fixed point: two days of volatility and no extra range is a zero spread.

    Worth pinning because (3 - 2*sqrt(2)) == (sqrt(2) - 1)**2 is what makes the terms cancel, and a
    mistyped constant would break this and almost nothing else.
    """
    assert spread.spread_from(0.01, 0.01) == pytest.approx(0.0, abs=1e-12)
    assert spread.spread_from(0.04, 0.04) == pytest.approx(0.0, abs=1e-12)
    # More two-day range than two one-day ranges implies a negative spread.
    assert spread.spread_from(0.01, 0.02) < 0


def test_half_spread_is_half() -> None:
    """A 10bp round trip costs 5bp to cross once - the number DR-004 states."""
    assert spread.half_spread_bps(Decimal("0.001")) == Decimal("5.0000")
    assert spread.half_spread_bps(Decimal("0.0005")) == Decimal("2.5000")
    assert spread.half_spread_bps(Decimal(0)) == Decimal("0.0000")


def test_overnight_gap_is_shifted_out() -> None:
    """A gapped day is moved back onto the previous close, keeping its width."""
    high, low = spread._adjust_overnight(115.0, 110.0, 100.0)
    assert high == pytest.approx(105.0)
    assert low == pytest.approx(100.0)
    assert high - low == pytest.approx(5.0), "the range must survive the shift"

    high, low = spread._adjust_overnight(90.0, 85.0, 100.0)
    assert high == pytest.approx(100.0)
    assert low == pytest.approx(95.0)

    # Overlapping days are left alone.
    assert spread._adjust_overnight(105.0, 95.0, 100.0) == (105.0, 95.0)


def test_the_gap_adjustment_keeps_a_drifting_series_honest() -> None:
    """A persistent overnight gap must not read as a wider or narrower spread.

    A breakout universe gaps constantly. Without the adjustment the gap enters gamma as if it were
    trading range, and the estimator reports trading as cheaper than it is.
    """
    highs, lows, closes = _simulate(1000, 0.006)
    ungapped, _, _ = spread.corwin_schultz(highs, lows, closes)

    gapped_high, gapped_low, gapped_close = [], [], []
    for index, (high, low, close) in enumerate(zip(highs, lows, closes, strict=True)):
        shift = 1.0 + 0.02 * index
        gapped_high.append(high * shift)
        gapped_low.append(low * shift)
        gapped_close.append(close * shift)

    gapped, _, _ = spread.corwin_schultz(gapped_high, gapped_low, gapped_close)

    assert ungapped is not None and gapped is not None
    assert gapped == pytest.approx(ungapped, rel=0.25)


def test_negative_pairs_are_counted_not_discarded() -> None:
    """A negative two-day estimate becomes zero and is tallied as a diagnostic."""
    highs, lows, closes = _simulate(500, 0.0)
    value, pairs, negatives = spread.corwin_schultz_per_pair(highs, lows, closes)

    assert value is not None
    assert pairs > 400
    assert negatives > 0, "a spreadless market must produce negative two-day estimates"
    assert negatives <= pairs


def test_refusal_is_not_zero() -> None:
    """Below the pair minimum the window declines. None and 0.0 must not be confused."""
    highs, lows, closes = _simulate(10, 0.005)
    window = spread.estimate("TEST.1", "2026-08", highs, lows, closes, minimum_pairs=15)

    assert window.corwin_schultz is None
    assert window.abdi_ranaldo is None
    assert window.pairs < 15
    assert window.sessions == 10


def test_a_window_that_meets_the_minimum_reports() -> None:
    highs, lows, closes = _simulate(40, 0.004)
    window = spread.estimate("TEST.1", "2026-08", highs, lows, closes, minimum_pairs=15)

    assert window.corwin_schultz is not None
    assert window.abdi_ranaldo is not None
    assert window.instrument_id == "TEST.1"
    assert window.label == "2026-08"
    assert 0 <= window.cs_negative_pair_rate <= 1


def test_non_positive_prices_are_skipped_or_refused() -> None:
    """A zero or negative price is not a cheap instrument, it is bad data."""
    assert spread.beta_gamma([10.0, 11.0], [0.0, 9.0], [9.5, 10.5]) == []

    value, pairs, _ = spread.abdi_ranaldo([10.0, 0.0, 11.0], [9.0, 8.0, 10.0], [9.5, 9.0, 10.5])
    assert value is None and pairs == 0


def test_a_flat_series_has_no_estimate() -> None:
    """Zero range on every day makes beta zero, and equation 14 undefined - so it refuses."""
    flat = [100.0] * 30
    value, pairs, _ = spread.corwin_schultz(flat, flat, flat)
    assert value is None
    assert pairs == 0


def test_abdi_ranaldo_needs_three_days() -> None:
    """The estimator pairs each close with the mid-range either side of it."""
    value, pairs, _ = spread.abdi_ranaldo([10.0, 11.0], [9.0, 10.0], [9.5, 10.5])
    assert value is None and pairs == 0


def test_median_is_exact_on_both_parities() -> None:
    assert spread.median([Decimal(3), Decimal(1), Decimal(2)]) == Decimal(2)
    assert spread.median([Decimal(1), Decimal(2), Decimal(3), Decimal(4)]) == Decimal("2.5")
    assert spread.median([]) is None


def test_quantile_returns_an_observed_value() -> None:
    values = [Decimal(n) for n in (5, 1, 4, 2, 3)]
    assert spread.quantile(values, Decimal(0)) == Decimal(1)
    assert spread.quantile(values, Decimal(1)) == Decimal(5)
    assert spread.quantile(values, Decimal("0.5")) == Decimal(3)
    assert spread.quantile([], Decimal("0.5")) is None


def test_weighted_mean_weights() -> None:
    pairs = [(Decimal(10), Decimal(1)), (Decimal(20), Decimal(3))]
    assert spread.weighted_mean(pairs) == Decimal("17.5")
    assert spread.weighted_mean([]) is None
    assert spread.weighted_mean([(Decimal(10), Decimal(0))]) is None
