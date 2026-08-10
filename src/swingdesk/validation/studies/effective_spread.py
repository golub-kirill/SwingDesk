"""Effective bid-ask spread, estimated from daily OHLC. PR-008.

`DR-004` set `costs.slippage_model` to 5bp per side by assumption, and rejected a spread-derived
value because no free source serves historical intraday bid/ask point-in-time. That is true of
QUOTED spreads. It is not true of the EFFECTIVE spread, which two published estimators recover from
daily bars alone - data this project already holds.

Two estimators rather than one, because they are independent in construction and a single estimator
agreeing with itself is not a measurement:

  Corwin & Schultz (2012)  from the high-low ranges of two consecutive days. A two-day range
                           contains two days of volatility and one spread; a one-day range contains
                           one of each. That difference identifies the spread.
  Abdi & Ranaldo (2017)    from the gap between a day's close and the mid-range of the days either
                           side of it. The close sits on a bid or an ask; the mid-range does not.

Both return the PROPORTIONAL ROUND-TRIP spread. A single crossing pays half of it, which is the
figure comparable to `DR-004`'s per-side 5bp - `half_spread_bps` does that conversion once, here,
rather than in each caller.

Pure. No I/O, no clock, no randomness.

**On float.** The prices arrive as `Decimal` and the results are returned as `Decimal`, but the
estimators themselves run in float. `DETERMINISM_SPEC` §3.3 reserves exactness for money and permits
floats where the aggregation order is fixed, which it is here (canonical order, single-threaded).
A spread ratio is not money: it is a statistic whose own sampling error is larger than float epsilon
by roughly ten orders of magnitude, and `Decimal.ln()` over ~1.8M bar pairs costs minutes to buy
precision the estimator cannot deliver. Outputs are quantised on the way out so the JSON of record
is stable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

#: Corwin & Schultz (2012) equation 14. Named because it appears three times and 0.1715... is not
#: self-explanatory at the call site. Note (3 - 2*sqrt(2)) == (sqrt(2) - 1)**2, which is why the
#: formula collapses to zero when beta equals gamma - the no-spread case.
K1 = 3 - 2 * math.sqrt(2)

#: Proportions are reported to ten places. Far beyond the estimator's resolution, and enough that
#: quantisation never shows up in a basis-point figure.
QUANTUM = Decimal("0.0000000001")


@dataclass(frozen=True, slots=True)
class SpreadWindow:
    """Both estimators over one instrument and one window.

    `None` means the estimator declined - too few usable pairs, or unusable prices. It never means
    zero. A zero spread is a measurement; a refusal is the absence of one, and collapsing them would
    put free trading into the average (`FAIL_CLOSED_POLICY`).
    """

    instrument_id: str
    label: str
    sessions: int
    pairs: int
    corwin_schultz: Decimal | None
    abdi_ranaldo: Decimal | None
    cs_negative: bool
    ar_negative: bool
    cs_negative_pairs: int

    @property
    def cs_negative_pair_rate(self) -> Decimal:
        """Share of two-day pairs whose unpooled estimate came out below zero.

        A diagnostic, not the study statistic. A high rate says the estimator's assumptions do not
        hold on this window, which is different from saying the spread is narrow.
        """
        if self.pairs == 0:
            return Decimal(0)
        return Decimal(self.cs_negative_pairs) / Decimal(self.pairs)


def half_spread_bps(proportional: Decimal) -> Decimal:
    """Round-trip proportional spread -> per-side cost in basis points.

    `DR-004` states its slippage per side, so every comparison against it needs the half.
    """
    return (proportional / 2 * Decimal(10_000)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)


def _quantise(value: float) -> Decimal:
    return Decimal(repr(value)).quantize(QUANTUM, rounding=ROUND_HALF_EVEN)


def _adjust_overnight(
    high_next: float, low_next: float, close_previous: float
) -> tuple[float, float]:
    """Shift day t+1's range back onto day t's, when the two do not overlap.

    Corwin & Schultz §II. The estimator reads a two-day range as two days of trading volatility plus
    one spread. An overnight gap adds range that no amount of intraday trading produced, so an
    unadjusted gap inflates gamma and biases the spread downward - and gaps are exactly what a
    breakout universe is full of.
    """
    if close_previous < low_next:
        gap = low_next - close_previous
        return high_next - gap, low_next - gap
    if close_previous > high_next:
        gap = close_previous - high_next
        return high_next + gap, low_next + gap
    return high_next, low_next


def beta_gamma(
    highs: list[float], lows: list[float], closes: list[float]
) -> list[tuple[float, float]]:
    """Per two-day pair, the (beta, gamma) inputs to equation 14.

    beta is the sum of the two single-day squared log ranges; gamma is the squared log range of the
    two days taken together. Both contain one spread; beta contains one day of volatility and gamma
    two, and that asymmetry is what identifies the spread.

    A pair is skipped rather than zeroed when its prices cannot support an estimate: a non-positive
    price, or two consecutive zero-range days, which makes beta zero and equation 14 degenerate.
    """
    pairs: list[tuple[float, float]] = []
    for index in range(len(highs) - 1):
        high_t, low_t, close_t = highs[index], lows[index], closes[index]
        high_next, low_next = highs[index + 1], lows[index + 1]
        if min(high_t, low_t, high_next, low_next, close_t) <= 0:
            continue

        high_adjusted, low_adjusted = _adjust_overnight(high_next, low_next, close_t)
        if high_adjusted <= 0 or low_adjusted <= 0:
            continue

        beta = math.log(high_t / low_t) ** 2 + math.log(high_adjusted / low_adjusted) ** 2
        if beta <= 0:
            continue
        gamma = math.log(max(high_t, high_adjusted) / min(low_t, low_adjusted)) ** 2
        pairs.append((beta, gamma))
    return pairs


def spread_from(beta: float, gamma: float) -> float:
    """Corwin & Schultz equations 14 and 18. May return a negative spread; callers decide."""
    alpha = (math.sqrt(2 * beta) - math.sqrt(beta)) / K1 - math.sqrt(gamma / K1)
    return 2 * (math.exp(alpha) - 1) / (1 + math.exp(alpha))


def corwin_schultz(
    highs: list[float], lows: list[float], closes: list[float]
) -> tuple[float | None, int, bool]:
    """Window CS estimate: average beta and gamma over the window, then solve alpha ONCE.

    Returns (spread, pairs_used, was_negative).

    **Pooling is not an optimisation, it is the correction.** Equation 14 defines beta and gamma as
    expectations. Solving alpha from a single two-day pair and averaging the results afterwards
    estimates E[f(beta, gamma)] where f is a difference of square roots - and by Jensen's inequality
    that is not f(E[beta], E[gamma]). The error does not average away with sample size:
    `corwin_schultz_per_pair` reports roughly +80bp of round-trip spread on synthetic bars
    containing NO spread at all, and that offset is stable as intraday sampling grows finer. Against
    a question posed at 10bp round trip, the per-pair form is unusable. This one converges to the
    true spread in the same simulation (`tests/test_effective_spread.py`).

    A negative pooled estimate is returned as 0.0 with the flag set. The flag is what PR-008 §6
    counts, because a negative estimate means the estimator's assumptions failed on this window -
    not that trading was free.
    """
    pairs = beta_gamma(highs, lows, closes)
    if not pairs:
        return None, 0, False

    beta = sum(value for value, _ in pairs) / len(pairs)
    gamma = sum(value for _, value in pairs) / len(pairs)
    estimate_value = spread_from(beta, gamma)
    if estimate_value < 0:
        return 0.0, len(pairs), True
    return estimate_value, len(pairs), False


def corwin_schultz_per_pair(
    highs: list[float], lows: list[float], closes: list[float]
) -> tuple[float | None, int, int]:
    """The per-pair form: solve alpha for each two-day pair, zero the negatives, average.

    Returns (spread, pairs_used, negative_pairs).

    **Diagnostic only. Not a spread estimate.** It carries the Jensen bias described in
    `corwin_schultz` and reads roughly +80bp round trip off spreadless bars. It is kept for two
    reasons: the negative-pair count is a real signal about whether the estimator is in its regime
    on a given window, and deleting the biased form would delete the evidence for preferring the
    pooled one.
    """
    estimates: list[float] = []
    negatives = 0
    for beta, gamma in beta_gamma(highs, lows, closes):
        value = spread_from(beta, gamma)
        if value < 0:
            negatives += 1
            estimates.append(0.0)
        else:
            estimates.append(value)

    if not estimates:
        return None, 0, 0
    return sum(estimates) / len(estimates), len(estimates), negatives


def abdi_ranaldo(
    highs: list[float], lows: list[float], closes: list[float]
) -> tuple[float | None, int, bool]:
    """Window CHL estimate. Returns (spread, pairs_used, mean_was_negative).

    s^2 = 4 (c_t - eta_t)(c_t - eta_t+1), averaged over the window, then rooted. eta is the log
    mid-range, which estimates the efficient price; the close sits on one side of the spread or the
    other. The product of the two deviations is positive when a spread exists and noise around zero
    when it does not, so a negative mean is a real outcome - returned as 0.0 with the flag set
    rather than hidden inside the root.

    Averaging before rooting is deliberate and is the same correction pooling makes for CS: the root
    is concave, so rooting each term and averaging would bias the result.
    """
    if len(highs) < 3:
        return None, 0, False

    etas: list[float] = []
    log_closes: list[float] = []
    for high, low, close in zip(highs, lows, closes, strict=True):
        if min(high, low, close) <= 0:
            return None, 0, False
        etas.append((math.log(high) + math.log(low)) / 2)
        log_closes.append(math.log(close))

    products = [
        4 * (log_closes[index] - etas[index]) * (log_closes[index] - etas[index + 1])
        for index in range(len(etas) - 1)
    ]
    if not products:
        return None, 0, False

    mean = sum(products) / len(products)
    if mean <= 0:
        return 0.0, len(products), True
    return math.sqrt(mean), len(products), False


def estimate(
    instrument_id: str,
    label: str,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    minimum_pairs: int,
) -> SpreadWindow:
    """Both estimators over one window, refusing below `minimum_pairs` usable pairs."""
    cs, cs_pairs, cs_negative = corwin_schultz(highs, lows, closes)
    ar, ar_pairs, ar_negative = abdi_ranaldo(highs, lows, closes)
    _, _, negative_pairs = corwin_schultz_per_pair(highs, lows, closes)

    usable = max(cs_pairs, ar_pairs)
    if usable < minimum_pairs:
        return SpreadWindow(
            instrument_id=instrument_id, label=label, sessions=len(highs), pairs=usable,
            corwin_schultz=None, abdi_ranaldo=None,
            cs_negative=cs_negative, ar_negative=ar_negative, cs_negative_pairs=negative_pairs,
        )

    return SpreadWindow(
        instrument_id=instrument_id,
        label=label,
        sessions=len(highs),
        pairs=usable,
        corwin_schultz=None if cs is None else _quantise(cs),
        abdi_ranaldo=None if ar is None else _quantise(ar),
        cs_negative=cs_negative,
        ar_negative=ar_negative,
        cs_negative_pairs=negative_pairs,
    )


def median(values: list[Decimal]) -> Decimal | None:
    """Exact median. Sorted here rather than assumed sorted, so callers cannot get it wrong."""
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def quantile(values: list[Decimal], fraction: Decimal) -> Decimal | None:
    """Nearest-rank quantile. No interpolation, so the result is always an observed value."""
    if not values or not 0 <= fraction <= 1:
        return None
    ordered = sorted(values)
    rank = int((Decimal(len(ordered)) - 1) * fraction)
    return ordered[rank]


def weighted_mean(pairs: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    """Mean of (value, weight), in the order given.

    The order is the caller's and is expected to be canonical - `DETERMINISM_SPEC` §3.3 requires
    aggregation order be fixed by sort key rather than by arrival.
    """
    total = sum((weight for _, weight in pairs), Decimal(0))
    if total <= 0:
        return None
    return sum((value * weight for value, weight in pairs), Decimal(0)) / total


def edge(
    opens: list[float], highs: list[float], lows: list[float], closes: list[float]
) -> tuple[float | None, int, bool]:
    """EDGE - Ardia, Guidotti & Kroencke, *Journal of Financial Economics* 161 (2024), 103916.

    Returns (spread, observations_used, was_negative).

    **Why this exists.** `corwin_schultz` and `abdi_ranaldo` are the 2012 and 2017 estimators, and
    their documented failure mode is the one PR-008 measured by hand: the estimate tracks realised
    volatility, and its cross-sectional correlation with the true spread collapses as liquidity
    rises. EDGE is built to fix exactly that, and it uses the **open** - the one OHLC field neither
    of the others touches, and one this project has stored all along.

    **Transcribed from the reference implementation, not reinvented** (`github.com/eguidotti/bidask`,
    `python/bidask/edge.py`), which is what `AGENTS.md` §10.3 asks for. It is not imported: adding a
    numpy-backed dependency for one research tool would put a package in the lock file that `src/`
    never touches, and the other two estimators here are hand-written for the same reason. The
    formula below is the paper's; the arithmetic is ours and is tested against a known spread.

    The reference guards every step with NaN handling. This one does not need to: `Bar` rejects a
    non-positive or inconsistent OHLC at the contract boundary, so a series that reaches here has
    none. Missing sessions are absent rows, never NaN rows.

    `tau` marks the periods that actually traded - where the high differs from the low, or the low
    from the previous close. A frozen or limit-locked session carries no spread information and is
    excluded rather than averaged in as a zero.
    """
    count = len(opens)
    if not (count == len(highs) == len(lows) == len(closes)):
        raise ValueError("open, high, low and close must have the same length")
    if count < 3:
        return None, 0, False
    if min(min(opens), min(highs), min(lows), min(closes)) <= 0:
        return None, 0, False

    log_o = [math.log(value) for value in opens]
    log_h = [math.log(value) for value in highs]
    log_l = [math.log(value) for value in lows]
    log_c = [math.log(value) for value in closes]
    mid = [(high + low) / 2 for high, low in zip(log_h, log_l, strict=True)]

    n = count - 1
    # `_prev` is the reference implementation's 1-suffix: the previous session's value.
    o, h, low = log_o[1:], log_h[1:], log_l[1:]
    high_prev, low_prev, c1, m1 = log_h[:-1], log_l[:-1], log_c[:-1], mid[:-1]
    m = mid[1:]

    r1 = [m[i] - o[i] for i in range(n)]
    r2 = [o[i] - m1[i] for i in range(n)]
    r3 = [m[i] - c1[i] for i in range(n)]
    r4 = [c1[i] - m1[i] for i in range(n)]
    r5 = [o[i] - c1[i] for i in range(n)]

    tau = [1.0 if (h[i] != low[i] or low[i] != c1[i]) else 0.0 for i in range(n)]
    po1 = [tau[i] * (1.0 if o[i] != h[i] else 0.0) for i in range(n)]
    po2 = [tau[i] * (1.0 if o[i] != low[i] else 0.0) for i in range(n)]
    pc1 = [tau[i] * (1.0 if c1[i] != high_prev[i] else 0.0) for i in range(n)]
    pc2 = [tau[i] * (1.0 if c1[i] != low_prev[i] else 0.0) for i in range(n)]

    def mean(values: list[float]) -> float:
        return sum(values) / len(values)

    pt = mean(tau)
    po = mean(po1) + mean(po2)
    pc = mean(pc1) + mean(pc2)
    if sum(tau) < 2 or po == 0 or pc == 0 or pt == 0:
        return None, 0, False

    mean_r1, mean_r3, mean_r5 = mean(r1), mean(r3), mean(r5)
    d1 = [r1[i] - mean_r1 / pt * tau[i] for i in range(n)]
    d3 = [r3[i] - mean_r3 / pt * tau[i] for i in range(n)]
    d5 = [r5[i] - mean_r5 / pt * tau[i] for i in range(n)]

    x1 = [-4.0 / po * d1[i] * r2[i] + -4.0 / pc * d3[i] * r4[i] for i in range(n)]
    x2 = [-4.0 / po * d1[i] * r5[i] + -4.0 / pc * d5[i] * r4[i] for i in range(n)]

    e1, e2 = mean(x1), mean(x2)
    v1 = mean([value * value for value in x1]) - e1 * e1
    v2 = mean([value * value for value in x2]) - e2 * e2
    total = v1 + v2

    squared = (v2 * e1 + v1 * e2) / total if total > 0 else (e1 + e2) / 2
    # The reference roots the ABSOLUTE value rather than clamping, so a negative estimate becomes a
    # small positive one. The sign is returned separately instead of being thrown away.
    return math.sqrt(abs(squared)), n, squared < 0
