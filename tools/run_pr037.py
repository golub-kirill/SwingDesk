"""`PR-037` - do sectors trend as a block? Industry momentum on the eleven sector funds.

**The first study under `DR-047`, and it is built to that record's shape rather than to this
project's habit.** The unit is a SOURCE OF RETURN with a mechanism and a literature - industry
momentum, Moskowitz and Grinblatt (1999), whose claim is that a large part of what looks like
individual stock momentum is the industry moving as a block. The rule below is one expression of
that source, and it is the only expression this registration evaluates.

**What `DR-047` forces that earlier studies here did not do:**

* **no stop, no target and no sizing rule** (§3.2). Exit is the rebalance. A first test that carries
  risk management cannot separate "the source pays" from "the stop pays", which is what
  `PR-016`..`PR-019` spent nineteen registrations learning;
* **the benchmark is a SET on one equity curve** (§3.4): the strategy, its own universe held
  passively, `SPY` total return, and `SPY` matched to the strategy's own volatility. `PR-021` is why
  the fourth is mandatory - beta 1.45 and a worse result than the index;
* **the primary metric is geometric excess return** (§3.5), not mean `R` a trade. `criteria.yml`'s
  `b.excess_cagr` and `b.beta_matched` are the two this reads;
* **rolling three-year excess is reported** (§3.6), because a strategy that earns its whole
  advantage in one era has not been shown to have one - `PR-031` is that case;
* **one registration, one hypothesis** (§3.7). `12-1` is the rule; `9-1`, `6-1` and the rest are
  other studies and are declared NOT RUN.

**Why sectors and not stocks.** A fund's provider maintains its own constituents, so the
survivorship problem `DR-047` §3.9 makes a blocker for stock studies does not arise, and no
point-in-time index membership is needed. The eleven funds also carry almost no idiosyncratic risk -
three of them hold roughly 150 companies between them - which is the concern §3.3's twenty-name
floor was written about. **What the eleven DO limit is the cross-section**: eleven candidates is a
thin pool to rank, and that is a weakness of this source rather than a flaw in its test.

**The universe changes size, and that is handled before the run rather than explained after.**
`XLRE` began in 2015-10 and `XLC` in 2018-06, so the eligible pool is nine funds, then ten, then
eleven. A fund enters the ranking only once its whole formation window is observed, which is
membership as of the decision date and nothing else.

**AND IT IS NOT REGISTERED, which is the most important line in this file.**
`tools/measure_sector_power.py` asked, before any registration and on a RANDOM ranking that carries
no effect, how large an effect this design could actually detect. Against the funds' own pool: two
of eleven separates 4.56 points a year from zero, three 3.18, four 2.32, five 2.16, and the tercile
rule 2.86 - every one above the **two points a year** this literature claims. Only six of eleven
gets under it, and six of eleven is 55% of the pool.

**So the trial was not spent.** Every configuration evaluated raises the deflated-Sharpe hurdle for
every study after it, and a design that cannot detect its own claimed effect buys nothing with that.
The source stays `open` in `RETURN_SOURCE_REGISTER` §3.1 with a stated trigger - a wider
cross-section - and this runner is the instrument waiting for one. **Nothing here has read a
return**: the only thing ever run against it is the width proxy.

    PYTHONPATH=$PWD/src python tools/measure_sector_power.py --data <store dir>

    # and, if the source is ever reopened on a wider cross-section:
    PYTHONPATH=$PWD/src python tools/run_pr037.py --data <store dir> --as-of <t> --resamples 10000
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr031 as p31
from run_pr016 import BLOCK
from swingdesk.contracts.market import CorporateActionKind, Interval, Series
from swingdesk.market_data import BarStore

RESULT = p31.RESULTS / "PR-037.json"
POWER = p31.RESULTS / "PR-037-power.json"

#: The eleven Select Sector SPDRs. The card of this source: one fund an economic sector.
FUNDS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")
BENCH = "SPY"

#: `12-1`: the formation window is the twelve months ENDING ONE MONTH BEFORE the decision, and the
#: decision month itself is skipped. Jegadeesh and Titman's construction, and the skip is the part
#: that matters - the most recent month carries short-horizon reversal, which `PR-021` measured
#: here as −25 points a year and which would otherwise contaminate the signal.
FORMATION, SKIP = 12, 1

#: **The book is the top TERCILE of the eligible pool**, `ceil(n / 3)` - four funds of eleven,
#: three of nine. A rule rather than a number, so a pool that changes size does not silently change
#: what "selection" means, and the standard cross-sectional construction rather than one invented
#: here. `tools/measure_sector_power.py` measured what each book size could detect BEFORE this was
#: fixed, on a random ranking that carries no effect: a book of three could separate 3.18 points a
#: year from zero against a literature claiming about two, and the tercile 2.32. The choice is
#: recorded as made on those widths.
HOLD_DIVISOR = 3

#: Costs in BASIS POINTS OF NOTIONAL TRADED, which is the honest unit for a monthly fund rebalance.
#: The equivalence, so it is comparable with every other study here: `PR-031`..`PR-036` charged half
#: a cent a share, and these funds averaged about $40 over the window, so half a cent is ~1.25 bps.
#: **5 bps a side is therefore about four times the cost model this project has been using**, and
#: 15 is twelve times it. Deliberately harsh, because a monthly rebalance of liquid funds is the
#: cheapest thing this project has ever priced and a flattering assumption would prove nothing.
COSTS: dict[str, float] = {"net": 5.0, "cost_adverse": 15.0, "gross": 0.0}

BOOTSTRAP_SEED = 20260928
POWER_SEED = 20260929

#: A month is the unit, so the block is three MONTHS - `run_pr016`'s BLOCK, reused rather than
#: re-chosen, because choosing it again on this sample would be a decision made after seeing it.
MIN_MONTHS = 120

#: Gates NULL only, in annualised geometric excess. A 2-point-a-year effect is what this literature
#: claims, so a window this cannot separate at 6 points is a window that answers nothing.
POWER_FLOOR = 0.06

TOKEN = {"ACCEPT": "accept", "REJECT": "reject", "INCONCLUSIVE": "inconclusive",
         "NULL": "inconclusive", "COST_FRAGILE": "inconclusive", "PAID_FOR_EXPOSURE": "inconclusive",
         "NOT_BETTER_HELD": "inconclusive", "REFUSED": "refused", "SMOKE": "smoke"}


@dataclass(frozen=True)
class Month:
    """One fund-month: what it returned, dividends included."""

    month: str
    ret: float


def month_of(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def dividends_of(store: BarStore, fund: str, as_of: datetime) -> dict[date, float]:
    out: dict[date, float] = defaultdict(float)
    for action in store.actions_as_of(fund, as_of):
        if action.kind is CorporateActionKind.DIVIDEND:
            out[action.effective_date] += float(action.value)
    return dict(out)


def monthly_returns(bars: Sequence[Any], dividends: Mapping[date, float]) -> dict[str, float]:
    """Total return a calendar month, compounded from daily total returns.

    A daily total return is `(close_t + dividend_t) / close_{t-1} - 1`, the convention
    `PR-033`..`PR-036` measured on: a dividend detaches at its ex-date's open, so it belongs to the
    day it detaches. Compounding the days rather than dividing the month's endpoints is what makes
    a dividend paid mid-month reinvest rather than appear as a lump at the end.

    **The first stored month is dropped**, because its first session has no prior close and a month
    computed from a partial series is not that month's return.
    """
    by_month: dict[str, float] = {}
    for earlier, later in itertools.pairwise(bars):
        close = float(earlier.close)
        if close <= 0:
            continue
        session = later.session_date
        daily = (float(later.close) + dividends.get(session, 0.0)) / close - 1.0
        key = month_of(session)
        by_month[key] = (1.0 + by_month.get(key, 0.0)) * (1.0 + daily) - 1.0
    first = month_of(bars[0].session_date) if bars else ""
    return {k: v for k, v in by_month.items() if k != first}


def formation(series: Mapping[str, float], months: Sequence[str], at: int) -> float | None:
    """The compounded return over the formation window ending SKIP months before `months[at]`.

    Returns `None` when any month of the window is missing for this fund, which is how a fund that
    did not exist yet stays out of the ranking. It is never filled with a zero: a fund with no
    history has no momentum, and a zero would rank it in the middle of the pool.
    """
    start = at - SKIP - FORMATION + 1
    if start < 0:
        return None
    window = months[start:at - SKIP + 1]
    compounded = 1.0
    for month in window:
        value = series.get(month)
        if value is None:
            return None
        compounded *= 1.0 + value
    return compounded - 1.0


def eligible(by_fund: Mapping[str, Mapping[str, float]], months: Sequence[str],
             at: int) -> dict[str, float]:
    """Every fund with a complete formation window AND a return in the decision month itself.

    The second condition is not redundant: a fund whose history ends is not buyable now, whatever
    its past looks like.
    """
    out: dict[str, float] = {}
    for fund, series in by_fund.items():
        signal = formation(series, months, at)
        if signal is not None and months[at] in series:
            out[fund] = signal
    return out


def hold_for(eligible_count: int) -> int:
    """How many funds the book holds: the top tercile of the pool, at least one."""
    return max(1, -(-eligible_count // HOLD_DIVISOR))


def book_size(override: int | None, eligible_count: int) -> int:
    """The book the power proxy draws: `override` when one is given, else the registered tercile.

    A named function rather than an inline expression because it is the difference between
    `measure_sector_power.py` asking "what could a book of four detect" and asking the same
    question five times about the tercile - and a test can only hold that difference if it has
    something to call.
    """
    return min(override or hold_for(eligible_count), eligible_count)


def chosen(signals: Mapping[str, float]) -> tuple[str, ...]:
    """The top tercile by formation return. Ties break by symbol, so the choice is reproducible."""
    order = sorted(signals, key=lambda fund: (-signals[fund], fund))
    return tuple(sorted(order[:hold_for(len(signals))]))


def turnover_cost(previous: Sequence[str], now: Sequence[str], bps: float) -> float:
    """What replacing part of the book costs, as a fraction of the book.

    Each position is `1 / len(now)` of the book. `k` arrive and `k` leave, so the notional traded is
    `2k / len(now)` and the cost is that times the one-way rate. The first month charges a full
    entry and no exit, because there was nothing to sell.

    **The denominator is the CURRENT book**, not a constant, because the tercile changes size when
    the pool does - nine funds give three, eleven give four - and a fixed denominator would
    misprice every month on the other side of that change.
    """
    if not now:
        return 0.0
    if not previous:
        return bps / 10_000.0
    changed = len(set(now) - set(previous))
    return 2.0 * changed / len(now) * bps / 10_000.0


def walk(by_fund: Mapping[str, Mapping[str, float]], months: Sequence[str], bps: float,
         choose: Callable[[Mapping[str, float]], tuple[str, ...]] | None = None
         ) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Run the rule month by month and return its returns plus the decision trail.

    The decision at the end of month `months[at]` is held through `months[at + 1]`, so every return
    this produces is earned AFTER the data that chose it. That is the whole of the look-ahead
    discipline here and it is ONE line: the signal reads `at`, the return reads `at + 1`.

    **`choose` is why that line appears once rather than twice.** The power proxy needs the same
    walk with the ranking replaced by a coin, and the obvious way to get it - a second loop in
    `power` - would put the `at + 1` in two places. Two copies of a look-ahead rule is one copy
    that can rot silently, so the ranking is the argument and the calendar is not.
    """
    pick = choose or chosen
    returns: dict[str, float] = {}
    trail: list[dict[str, Any]] = []
    held: tuple[str, ...] = ()
    for at in range(len(months) - 1):
        signals = eligible(by_fund, months, at)
        if len(signals) < HOLD_DIVISOR:
            continue
        picks = pick(signals)
        held_month = months[at + 1]
        parts = [by_fund[fund].get(held_month) for fund in picks]
        if any(part is None for part in parts):
            continue
        gross = statistics.fmean([p for p in parts if p is not None])
        cost = turnover_cost(held, picks, bps)
        returns[held_month] = gross - cost
        trail.append({"decided": months[at], "held": held_month, "picks": list(picks),
                      "eligible": len(signals), "gross": gross, "cost": cost})
        held = picks
    return returns, trail


def universe_returns(by_fund: Mapping[str, Mapping[str, float]],
                     months: Sequence[str], over: Sequence[str]) -> dict[str, float]:
    """The strategy's own pool held passively: every ELIGIBLE fund, equally weighted, each month.

    Eligible by the same rule the strategy uses, so the two read the same pool - a benchmark that
    quietly held funds the strategy could not choose would answer a different question. It is
    charged NO cost, which favours the benchmark and makes the strategy's hurdle harder.
    """
    index = {month: i for i, month in enumerate(months)}
    out: dict[str, float] = {}
    for month in over:
        at = index[month] - 1
        if at < 0:
            continue
        pool = [by_fund[fund][month] for fund in eligible(by_fund, months, at)
                if month in by_fund[fund]]
        if pool:
            out[month] = statistics.fmean(pool)
    return out


def scaled(series: Mapping[str, float], to: Mapping[str, float]) -> dict[str, float]:
    """`series` levered to `to`'s volatility, one constant over the whole sample.

    **The constant is computed in sample and that is declared rather than hidden**: this is a
    BENCHMARK, not a strategy, and its job is to answer "am I paid for skill or for exposure" -
    a forecast volatility would add noise to the question without making it fairer.
    """
    shared = sorted(set(series) & set(to))
    if len(shared) < 2:
        return dict(series)
    mine = statistics.stdev(series[m] for m in shared)
    theirs = statistics.stdev(to[m] for m in shared)
    factor = theirs / mine if mine else 1.0
    return {m: series[m] * factor for m in series}


def cagr(values: Sequence[float]) -> float:
    equity = 1.0
    for value in values:
        equity *= 1.0 + value
    years = len(values) / 12.0
    return equity ** (1.0 / years) - 1.0 if years and equity > 0 else math.nan


def geometric_excess(strategy: Sequence[float], benchmark: Sequence[float]) -> float:
    """`(1 + CAGR_strategy) / (1 + CAGR_benchmark) - 1` - `DR-047` §3.5's primary metric.

    A RATIO rather than a difference of CAGRs, because compounding is multiplicative: two curves
    that differ by a constant factor every month differ by that factor in the end, and subtracting
    annualised rates reports something that is neither the money made nor the ratio earned.
    """
    top, bottom = cagr(strategy), cagr(benchmark)
    return (1.0 + top) / (1.0 + bottom) - 1.0 if bottom > -1.0 else math.nan


def paired_bootstrap(strategy: Mapping[str, float], benchmark: Mapping[str, float],
                     resamples: int, seed: int = BOOTSTRAP_SEED) -> dict[str, float]:
    """A 95% interval for the geometric excess, resampling MONTHS in moving blocks of `BLOCK`.

    **Paired**: a block carries the strategy's month and the benchmark's SAME month together, so
    every resample compares the two over the same drawn calendar. Resampling them independently
    would break the pairing and widen the interval with a difference that never happened.
    """
    shared = sorted(set(strategy) & set(benchmark))
    n = len(shared)
    if n < 2:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "width": math.nan}
    pairs = [(strategy[m], benchmark[m]) for m in shared]
    block = min(BLOCK, n)
    starts = n - block + 1
    rng = random.Random(seed)

    observed = geometric_excess([p[0] for p in pairs], [p[1] for p in pairs])
    draws: list[float] = []
    for _ in range(resamples):
        pool: list[tuple[float, float]] = []
        while len(pool) < n:
            start = rng.randrange(starts)
            pool.extend(pairs[start:start + block])
        pool = pool[:n]
        draws.append(geometric_excess([p[0] for p in pool], [p[1] for p in pool]))
    draws = sorted(d for d in draws if not math.isnan(d))
    if not draws:
        return {"estimate": observed, "lo": math.nan, "hi": math.nan, "width": math.nan}
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    return {"estimate": observed, "lo": lo, "hi": hi, "width": hi - lo}


def described(values: Sequence[float]) -> dict[str, float]:
    """Annualised and descriptive. Never read by the decision rule."""
    if len(values) < 2:
        return {}
    mean, spread = statistics.fmean(values), statistics.stdev(values)
    equity, peak, worst = 1.0, 1.0, 0.0
    for value in values:
        equity *= 1.0 + value
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return {"months": len(values), "annual_mean": mean * 12,
            "annual_volatility": spread * math.sqrt(12),
            "sharpe": mean / spread * math.sqrt(12) if spread else math.nan,
            "cagr": cagr(values), "max_drawdown": worst}


def rolling_excess(strategy: Mapping[str, float], benchmark: Mapping[str, float],
                   window: int = 36) -> dict[str, Any]:
    """`DR-047` §3.6: the excess over every rolling three-year window, not only over the whole.

    A strategy that earns its whole advantage in one era has not been shown to have one, and the
    headline cannot show that. The share of windows above zero is the number that can.
    """
    shared = sorted(set(strategy) & set(benchmark))
    if len(shared) < window:
        return {"windows": 0}
    values = [geometric_excess([strategy[m] for m in shared[i:i + window]],
                               [benchmark[m] for m in shared[i:i + window]])
              for i in range(len(shared) - window + 1)]
    return {"windows": len(values), "share_positive": sum(v > 0 for v in values) / len(values),
            "worst": min(values), "best": max(values), "median": statistics.median(values)}


def branch_for(excess: Mapping[str, Any], adverse: Mapping[str, Any],
               matched: Mapping[str, Any], own: Mapping[str, Any], months: int) -> str:
    """`DR-047`'s order: is it real, does it survive cost, is it skill, and can it pick in its pool."""
    if months < MIN_MONTHS:
        return "REFUSED"
    if excess["lo"] > 0:
        if not adverse["lo"] > 0:
            return "COST_FRAGILE"
        if not matched["lo"] > 0:
            return "PAID_FOR_EXPOSURE"
        if not own["lo"] > 0:
            return "NOT_BETTER_HELD"
        return "ACCEPT"
    if excess["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if excess["width"] > POWER_FLOOR else "NULL"


def load(store: BarStore, fund: str, as_of: datetime) -> dict[str, float]:
    series = store.as_of(fund, Interval.DAY, Series.RAW, as_of)
    return monthly_returns(series.bars, dividends_of(store, fund, as_of))


def daily_cagr(store: BarStore, fund: str, as_of: datetime, over: Sequence[str]) -> float:
    """`fund`'s compounded return over the same calendar months, read from the DAILY series.

    The study's own refutation (§9): the monthly aggregation must not lose a dividend or a day. If
    this disagrees with the monthly figure, every number above it is measuring something else.
    """
    span = set(over)
    series = store.as_of(fund, Interval.DAY, Series.RAW, as_of)
    dividends = dividends_of(store, fund, as_of)
    values = []
    for earlier, later in itertools.pairwise(series.bars):
        close = float(earlier.close)
        if close <= 0 or month_of(later.session_date) not in span:
            continue
        values.append((float(later.close) + dividends.get(later.session_date, 0.0)) / close - 1.0)
    equity = 1.0
    for value in values:
        equity *= 1.0 + value
    years = len(over) / 12.0
    return equity ** (1.0 / years) - 1.0 if years and equity > 0 else math.nan


def build(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    try:
        latest = store.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC)
        as_of = datetime.fromisoformat(args.as_of) if args.as_of else latest
        by_fund = {fund: load(store, fund, as_of) for fund in FUNDS}
        bench = load(store, BENCH, as_of)
        months = sorted({m for series in by_fund.values() for m in series})

        net, trail = walk(by_fund, months, COSTS["net"])
        held_months = sorted(net)
        curves: dict[str, dict[str, float]] = {"strategy": net}
        for costing, bps in COSTS.items():
            if costing != "net":
                curves[f"strategy-{costing}"] = walk(by_fund, months, bps)[0]
        curves["universe"] = universe_returns(by_fund, months, held_months)
        curves[BENCH] = {m: bench[m] for m in held_months if m in bench}
        curves[f"{BENCH}-vol-matched"] = scaled(curves[BENCH], net)

        bench_check = {
            "monthly_cagr": cagr([curves[BENCH][m] for m in sorted(curves[BENCH])]),
            "daily_cagr": daily_cagr(store, BENCH, as_of, sorted(curves[BENCH])),
        }
        bench_check["differ_by"] = abs(bench_check["monthly_cagr"] - bench_check["daily_cagr"])
    finally:
        store.close()

    cells: dict[str, Any] = {}
    for name, curve in curves.items():
        cells[name] = {"months": len(curve),
                       "described": described([curve[m] for m in sorted(curve)])}

    cells["excess"] = paired_bootstrap(net, curves[BENCH], resamples)
    cells["excess-cost_adverse"] = paired_bootstrap(
        curves["strategy-cost_adverse"], curves[BENCH], resamples)
    cells["excess-gross"] = paired_bootstrap(curves["strategy-gross"], curves[BENCH], resamples)
    cells["excess-vol-matched"] = paired_bootstrap(net, curves[f"{BENCH}-vol-matched"], resamples)
    cells["excess-own-universe"] = paired_bootstrap(net, curves["universe"], resamples)

    # The identity §9 makes this study's own refutation: every month's net return must be the mean
    # of the three funds held, less exactly the cost charged for that month's turnover.
    worst_identity = 0.0
    for row in trail:
        worst_identity = max(worst_identity, abs(net[row["held"]] - (row["gross"] - row["cost"])))

    eligibility = {row["held"]: row["eligible"] for row in trail}
    return {
        "as_of": as_of.isoformat(),
        "months": len(net),
        "first_held": held_months[0] if held_months else "",
        "last_held": held_months[-1] if held_months else "",
        "cells": cells,
        "rolling_three_year": rolling_excess(net, curves[BENCH]),
        "identity_worst": worst_identity,
        "benchmark_check": bench_check,
        "eligibility": {"first": eligibility.get(held_months[0]) if held_months else 0,
                        "last": eligibility.get(held_months[-1]) if held_months else 0,
                        "distinct": sorted(set(eligibility.values()))},
        "trail": trail,
    }


def power(args: argparse.Namespace, hold: int | None = None) -> dict[str, Any]:
    """Widths only, from a ranking with the signal REMOVED.

    `power_pr019.assert_no_effect_leaked` is the rule: an estimate computed before the run is a
    result seen before the registration. So the proxy ranks the eligible funds at RANDOM each month
    - same pool, same turnover, same costs, no signal - and reports how wide the interval comes out.
    That is the sampling width of this design and it carries no information about the effect.

    `hold` fixes the book size instead of using the registered tercile rule. It exists for
    `tools/measure_sector_power.py`, which asks what EACH book size could detect - a question about
    the design that has to be answered before one of them is registered.
    """
    store = BarStore(args.data / "bars.duckdb")
    try:
        latest = store.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC)
        as_of = datetime.fromisoformat(args.as_of) if args.as_of else latest
        by_fund = {fund: load(store, fund, as_of) for fund in FUNDS}
        bench = load(store, BENCH, as_of)
        months = sorted({m for series in by_fund.values() for m in series})
    finally:
        store.close()

    rng = random.Random(POWER_SEED)

    def at_random(signals: Mapping[str, float]) -> tuple[str, ...]:
        return tuple(sorted(rng.sample(sorted(signals), book_size(hold, len(signals)))))

    returns, _ = walk(by_fund, months, COSTS["net"], choose=at_random)

    # Both contrasts a selection rule can be judged on, because they have very different
    # variances and the difference is the whole design question. Against SPY the market's own
    # moves are in the contrast; against the fund's OWN POOL they cancel, because both sides hold
    # the same kind of asset over the same months. Widths only - the ranking is random, so nothing
    # here carries a sign.
    against_bench = {m: bench[m] for m in returns if m in bench}
    pool = universe_returns(by_fund, months, sorted(returns))
    widths = {
        "excess-vs-SPY-random-ranking": paired_bootstrap(returns, against_bench, args.resamples,
                                                        seed=POWER_SEED),
        "excess-vs-own-pool-random-ranking": paired_bootstrap(returns, pool, args.resamples,
                                                             seed=POWER_SEED),
    }
    return {"for": "PR-037", "as_of": {"bars": as_of.isoformat()},
            "resamples": args.resamples,
            "widths": {name: {"width": round(cell["width"], 6), "months": len(returns)}
                       for name, cell in widths.items()},
            "power_floor_width": POWER_FLOOR}


def _pct(value: float) -> str:
    return f"{100 * value:+.2f}%"


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-037   verdict {payload['verdict']}   branch {payload['branch']}")
    check = payload["benchmark_check"]
    print(f"  SPY monthly vs daily CAGR {check['monthly_cagr']:.6f} vs {check['daily_cagr']:.6f}"
          f"  differ by {check['differ_by']:.2e}")
    print(f"  identity worst {payload['identity_worst']:.2e}"
          f"   months {payload['months']}   {payload['first_held']} .. {payload['last_held']}")
    print(f"  eligible funds {payload['eligibility']['distinct']}")
    for name in ("excess", "excess-cost_adverse", "excess-gross", "excess-vol-matched",
                 "excess-own-universe"):
        cell = payload["cells"][name]
        print(f"  {name:24s} {_pct(cell['estimate'])} [{_pct(cell['lo'])}, {_pct(cell['hi'])}]"
              f"  width {100 * cell['width']:.2f}")
    for name in ("strategy", "strategy-cost_adverse", "strategy-gross", "universe", BENCH,
                 f"{BENCH}-vol-matched"):
        shown = payload["cells"][name]["described"]
        if shown:
            print(f"  {name:24s} cagr {_pct(shown['cagr'])}"
                  f"  vol {100 * shown['annual_volatility']:.1f}%"
                  f"  sharpe {shown['sharpe']:+.2f}"
                  f"  worst {100 * shown['max_drawdown']:.1f}%")
    rolling = payload["rolling_three_year"]
    if rolling.get("windows"):
        print(f"  rolling 3y excess: {rolling['windows']} windows, "
              f"{100 * rolling['share_positive']:.0f}% positive, "
              f"median {_pct(rolling['median'])}, worst {_pct(rolling['worst'])}, "
              f"best {_pct(rolling['best'])}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb with actions")
    parser.add_argument("--as-of", help="the bar store's knowledge instant")
    parser.add_argument("--resamples", type=int, default=p31.BOOTSTRAP_RESAMPLES)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--power", action="store_true")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.data is None:
        parser.error("--data is required")
    if args.power:
        estimate = power(args)
        POWER.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
        print(f"PR-037 power: widths {estimate['widths']}")
        return 0

    built = build(args, args.resamples)
    registered = args.resamples == p31.BOOTSTRAP_RESAMPLES
    branch = (branch_for(built["cells"]["excess"], built["cells"]["excess-cost_adverse"],
                         built["cells"]["excess-vol-matched"],
                         built["cells"]["excess-own-universe"], built["months"])
              if registered else "SMOKE")
    payload: dict[str, Any] = {
        "prereg": "PR-037", "trials": 1, "verdict": TOKEN[branch], "branch": branch,
        "country": "USA", **built,
        "measured_span": {"first_month": built["first_held"], "last_month": built["last_held"]},
        "split": {"registered": "none - one rule, one pool, one window",
                  "buys": "nothing: no constant is chosen here"},
        "perturbations": {"registered": ["cost_adverse", "gross"],
                          "run": ["cost_adverse", "gross"]},
        "registered_settings": {
            "funds": list(FUNDS), "benchmark": BENCH, "formation": FORMATION, "skip": SKIP,
            "hold": "top tercile, ceil(eligible / 3)", "costs_bps_of_notional": COSTS,
            "primary": "excess",
            "gates": ["cost_adverse above zero", "vol-matched above zero",
                      "own universe above zero"],
            "bootstrap": {"unit": "month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                          "resamples": args.resamples},
        },
    }
    payload.pop("trail", None)
    RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
