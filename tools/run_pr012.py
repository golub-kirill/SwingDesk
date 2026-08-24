"""PR-012: does a cross-sectional ranking beat plain momentum on a capacity-constrained book?

Runs the three arms `docs/prereg/PR-012-cross-sectional-relative-strength.md` registered, over the
window that pre-registration defines by RULE rather than by date, and writes the result beside the
other studies. Nothing here chooses anything: every arm, the lookback, the capacity, the exits, the
costs and the split are read from the pre-registration and pinned as constants below, so a constant
that drifts makes this a different study under PR-012's name.

**Why there is a fast path, and what keeps it honest.** `AlwaysEligible` makes every admitted name a
candidate on every session, so a ranking scores roughly a thousand names a session across thousands
of sessions. `ByMarketPathStrength` is O(lookback) per score, which is hundreds of millions of
operations and not runnable. So the scores are precomputed with prefix sums - O(1) per query after
one linear pass - and `--verify-sample` checks the fast score against
`swingdesk.validation.backtest.ranking`'s reference implementation on a seeded random sample. **The
reference is the definition; this is an optimisation that has to prove it agrees.**

**The book is the point.** `run_book` enforces `risk.max_concurrent_positions` and
`risk.max_open_risk`, so the arms compete for four slots. Running this through `run_arm` would enter
every name ever ranked well, uncapped, and measure a strategy nobody declared.

    python tools/run_pr012.py --data C:/PycharmProjects/SwingDesk/data --write
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.application.universe import ADTV_WINDOW
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import Trade
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.classification import ClassificationStore, look_through
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.validation.backtest import (
    AlwaysEligible,
    BacktestConfig,
    Capacity,
    CostModel,
    ExitPolicy,
    run_book,
)
from swingdesk.validation.backtest.book import Candidate
from swingdesk.validation.backtest.ranking import (
    UNSCORED,
    ByMarketPathStrength,
    ByRawReturn,
    BySectorRelativeStrength,
    daily_returns,
)

RESULT = REPO / "docs" / "prereg" / "results" / "PR-012.json"

# ---- pinned by the pre-registration. A change here is a DIFFERENT study. -------------------------
LOOKBACK = 126
BENCHMARK = "SPY"
MIN_NAMES_FOR_WINDOW_START = 200
HOLDOUT_FRACTION = Decimal("0.30")
MAX_POSITIONS = 4
MAX_OPEN_RISK = Decimal(4)
ATR_STOP_MULTIPLE = Decimal("2.0")
MAX_HOLDING_BARS = 20
RISK_PER_TRADE = Decimal(1000)
COMMISSION_PER_SHARE = Decimal("0.005")
SLIPPAGE_BPS = Decimal(25)
STRESS_MULTIPLE = Decimal(3)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260824
MIN_TRADES_PER_ARM = 200
MIN_SECTOR_MEMBERS = 10
# -------------------------------------------------------------------------------------------------


def _atr_registry() -> ParameterRegistry:
    return ParameterRegistry(
        {"atr.period": {"id": "atr.period", "value": 14, "provenance": "assumed:Wilder 1978",
                        "status": "assumed", "unit": "bars", "named_in": ["M18-T0280"]}}
    )


@dataclass(frozen=True, slots=True)
class Precomputed:
    """Scores by (instrument, session). O(1) lookups; the reference implementations define them."""

    scores: dict[tuple[str, date], Decimal]

    def __call__(self, candidates: list[Candidate]) -> list[Candidate]:
        return [
            candidate for _, candidate in sorted(
                (
                    (self.scores.get((c.instrument_id, c.session_date), UNSCORED), c)
                    for c in candidates
                ),
                key=lambda pair: (-pair[0], pair[1].instrument_id),
            )
        ]


def _window_returns(series: BarSeries, lookback: int) -> dict[date, Decimal]:
    """Rolling `lookback` return at every session that has one. One linear pass."""
    out: dict[date, Decimal] = {}
    bars = series.bars
    for index in range(lookback, len(bars)):
        first = bars[index - lookback].close
        if first > 0:
            out[bars[index].session_date] = (bars[index].close - first) / first
    return out


def _beat_prefix(series: BarSeries, benchmark_by_session: dict[date, Decimal],
                 lookback: int) -> dict[date, Decimal]:
    """Share of the last `lookback` sessions whose daily return beat the benchmark's.

    Prefix sums over the name's OWN sessions, so a halted session shortens neither the window nor
    the claim. Equivalent to `ranking._beat_share` and checked against it by `--verify-sample`.
    """
    bars = series.bars
    wins: list[int] = [0]
    compared: list[int] = [0]
    for index in range(1, len(bars)):
        previous = bars[index - 1].close
        session = bars[index].session_date
        benchmark = benchmark_by_session.get(session)
        won = 0
        counted = 0
        if previous > 0 and benchmark is not None:
            counted = 1
            if (bars[index].close - previous) / previous > benchmark:
                won = 1
        wins.append(wins[-1] + won)
        compared.append(compared[-1] + counted)

    out: dict[date, Decimal] = {}
    for index in range(lookback, len(bars)):
        start = index - lookback
        seen = compared[index] - compared[start]
        if seen:
            out[bars[index].session_date] = Decimal(wins[index] - wins[start]) / Decimal(seen)
    return out


#: The reference's own helper, re-exported rather than reimplemented. A second copy of "the
#: benchmark's daily returns" is exactly the divergence the fast path already had to be caught for.
_daily_returns_by_session = daily_returns


def bootstrap_interval(values: list[Decimal], seed: int,
                       resamples: int) -> tuple[float, float, float] | None:
    """Mean, and a 95% percentile bootstrap interval. Seeded, so a re-run reproduces it."""
    if len(values) < 2:
        return None
    numbers = [float(v) for v in values]
    mean = sum(numbers) / len(numbers)
    rng = random.Random(seed)
    means: list[float] = []
    size = len(numbers)
    for _ in range(resamples):
        total = 0.0
        for _ in range(size):
            total += numbers[rng.randrange(size)]
        means.append(total / size)
    means.sort()
    return mean, means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def verdict(results: dict[str, dict[str, object]]) -> tuple[str, str]:
    """The pre-registration's own decision rule, in code. Returns (verdict, reason).

    Sections 6 and 8 of `PR-012` fix this before the run, and computing it here rather than reading
    it off a table is what makes the verdict a consequence of the numbers rather than of whoever
    looked at them.

    **The sample rule comes FIRST and it produces a fourth verdict.** Section 8: *"the study reports
    the measurement and refuses a verdict"* when the minimum is not met. `REFUSED` is not
    `INCONCLUSIVE` - the first says there was not enough data to look with, the second says the
    study looked and could not tell. Collapsing them reports an unmeasured question as a measured
    one, which `AGENTS.md` section 12 calls the most damaging error this product can make.
    """
    measured = {
        arm: results[f"1x/{arm}"]["holdout"] for arm in ("MOMENTUM", "MARKET", "SECTOR")
        if f"1x/{arm}" in results
    }
    if len(measured) < 3:
        return "REFUSED", "not every arm produced a holdout cell"

    thin = sorted(
        arm for arm, cell in measured.items()
        if not (isinstance(cell, dict) and cell.get("meets_minimum"))
    )
    if thin:
        counts = ", ".join(
            f"{arm} {measured[arm]['trades']}" for arm in thin  # type: ignore[index]
        )
        return "REFUSED", (
            f"section 8's minimum of {MIN_TRADES_PER_ARM} holdout trades is not met on {counts}"
            + (" - and one of them is the CONTROL, so the comparison does not exist"
               if "MOMENTUM" in thin else "")
        )

    control = measured["MOMENTUM"]
    assert isinstance(control, dict)
    for arm in ("MARKET", "SECTOR"):
        cell = measured[arm]
        assert isinstance(cell, dict)
        low, mean = cell["ci_low"], control["mean_net_r"]
        if low is not None and mean is not None and low > 0 and low > mean:
            return "ACCEPT", (
                f"{arm}'s holdout interval lies entirely above 0 and its lower bound {low:.6f} "
                f"exceeds the control's mean {mean:.6f}"
            )

    highs = [
        cell["ci_high"] for cell in measured.values()
        if isinstance(cell, dict) and cell["ci_high"] is not None
    ]
    if highs and all(h < 0 for h in highs):  # type: ignore[operator]
        return "REJECT", "every arm's holdout interval lies entirely below 0 at measured costs"

    return "INCONCLUSIVE", (
        "no ranking arm's interval clears both 0 and the control, and not every arm is negative"
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr012")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--write", action="store_true",
                        help="write the result. Without it nothing is written and the numbers are "
                             "printed only - a study's output is published deliberately")
    parser.add_argument("--verify-sample", type=int, default=300,
                        help="how many (name, session) scores to check against the reference "
                             "implementations. 0 disables the check, which is not recommended")
    args = parser.parse_args()

    clock = datetime.now(UTC)
    with (
        BarStore(args.data / "bars.duckdb") as store,
        DirectoryStore(args.data / "directory.duckdb") as directory,
        ClassificationStore(args.data / "classifications.duckdb") as classifications,
    ):
        as_of = store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("bar store is empty")

        benchmark = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
        if not benchmark.bars:
            raise SystemExit(f"{BENCHMARK} is not stored - DR-018's benchmark is missing")

        rule = rules.LiquidityRule(
            min_price=Decimal("5.00"), min_adtv=Decimal(5_000_000),
            adtv_window=ADTV_WINDOW, min_history=250,
        )
        stored = set(store.instrument_ids(as_of))
        universe: dict[str, BarSeries] = {}
        for entry in directory.as_of(as_of, eligible_only=True):
            if entry.symbol not in stored or entry.symbol == BENCHMARK:
                continue
            series = store.as_of(entry.symbol, Interval.DAY, Series.RAW, as_of)
            if series.bars and rule.admits(series):
                universe[entry.symbol] = series
        print(f"snapshot {as_of.isoformat()}  ·  admitted {len(universe)}")

        sector_of: dict[str, str] = {}
        for name in universe:
            exposure = look_through(classifications.as_of(name, clock), name)
            if exposure.is_available and exposure.weights:
                sector_of[name] = max(exposure.weights, key=lambda w: w.weight).sector
        print(f"classified {len(sector_of)} of {len(universe)}")

        # --- the window, by the pre-registration's RULE and not by a chosen date
        returns_by_name = {n: _window_returns(s, LOOKBACK) for n, s in universe.items()}
        per_session: dict[date, int] = defaultdict(int)
        for table in returns_by_name.values():
            for session in table:
                per_session[session] += 1
        eligible_sessions = sorted(
            s for s, count in per_session.items() if count >= MIN_NAMES_FOR_WINDOW_START
        )
        if not eligible_sessions:
            print(f"REFUSING: no session has {MIN_NAMES_FOR_WINDOW_START} scoreable names. "
                  f"Deepen the universe before running this study.")
            return 2
        window = (eligible_sessions[0], eligible_sessions[-1])
        boundary = eligible_sessions[
            int(len(eligible_sessions) * (1 - float(HOLDOUT_FRACTION)))
        ]
        print(f"window {window[0]} -> {window[1]}  ·  {len(eligible_sessions)} sessions  ·  "
              f"holdout from {boundary}")

        clipped: dict[str, BarSeries] = {}
        for name, series in universe.items():
            bars = tuple(b for b in series.bars if window[0] <= b.session_date <= window[1])
            if len(bars) > LOOKBACK:
                clipped[name] = BarSeries(
                    instrument_id=series.instrument_id, interval=series.interval,
                    series=series.series, knowledge_time=series.knowledge_time, bars=bars,
                )
        print(f"in-window instruments {len(clipped)}")

        # Only the DAILY benchmark returns are needed. Its window return is deliberately not used:
        # the market arm here is the PATH form, and the point-to-point form that would consume a
        # window return ranks identically to raw return (`DR-018` §1), so running it would be the
        # MOMENTUM arm under a second name and would spend a trial on a proven identity.
        benchmark_daily = _daily_returns_by_session(benchmark)

        # --- precomputed score tables, one per arm
        momentum_scores: dict[tuple[str, date], Decimal] = {}
        market_scores: dict[tuple[str, date], Decimal] = {}
        for name, series in clipped.items():
            for session, value in _window_returns(series, LOOKBACK).items():
                momentum_scores[(name, session)] = value
            for session, value in _beat_prefix(series, benchmark_daily, LOOKBACK).items():
                market_scores[(name, session)] = value

        sector_members: dict[str, list[str]] = defaultdict(list)
        for name in clipped:
            if name in sector_of:
                sector_members[sector_of[name]].append(name)
        usable = {s: n for s, n in sector_members.items() if len(n) >= MIN_SECTOR_MEMBERS}

        sector_scores: dict[tuple[str, date], Decimal] = {}
        by_session_returns: dict[date, dict[str, Decimal]] = defaultdict(dict)
        for name, series in clipped.items():
            for session, value in _window_returns(series, LOOKBACK).items():
                by_session_returns[session][name] = value
        for session, values in by_session_returns.items():
            means: dict[str, Decimal] = {}
            for sector, names in usable.items():
                have = [values[n] for n in names if n in values]
                if len(have) >= MIN_SECTOR_MEMBERS:
                    means[sector] = sum(have, start=Decimal(0)) / len(have)
            for name, own in values.items():
                sector = sector_of.get(name)
                mean = means.get(sector) if sector else None
                if mean is not None and mean != -1:
                    sector_scores[(name, session)] = (1 + own) / (1 + mean)

        if args.verify_sample:
            failures = _verify(
                clipped, benchmark, sector_of, usable, by_session_returns,
                momentum_scores, market_scores, sector_scores, args.verify_sample,
            )
            if failures:
                print(f"\nREFUSING: the fast path disagrees with the reference implementation on "
                      f"{failures} sampled score(s). The reference is the definition.")
                return 2
            print(f"fast-path check: {args.verify_sample} sampled scores agree with the reference")

        gates = {name: [True] * len(s.bars) for name, s in clipped.items()}
        registry = _atr_registry()
        atrs = {name: atr_component.compute(s, registry) for name, s in clipped.items()}

        base = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
        arms = {
            "MOMENTUM": Precomputed(momentum_scores),
            "MARKET": Precomputed(market_scores),
            "SECTOR": Precomputed(sector_scores),
        }
        capacity = Capacity(max_positions=MAX_POSITIONS, max_open_risk=MAX_OPEN_RISK)

        results: dict[str, dict[str, object]] = {}
        for regime, costs in (("1x", base), ("3x", base.stressed(STRESS_MULTIPLE))):
            for arm, ranking in arms.items():
                config = BacktestConfig(
                    arm=arm, exits=ExitPolicy(ATR_STOP_MULTIPLE, MAX_HOLDING_BARS),
                    costs=costs, trigger=AlwaysEligible(LOOKBACK),
                    risk_per_trade=RISK_PER_TRADE,
                )
                book = run_book(clipped, gates, atrs, config, capacity, ranking)
                periods: dict[str, list[Trade]] = {"primary": [], "holdout": []}
                for trade in book.trades:
                    periods["holdout" if trade.entry_date >= boundary else "primary"].append(trade)
                cell: dict[str, object] = {
                    "trades": len(book.trades),
                    "deferred": book.deferred,
                    "max_concurrent": book.max_concurrent,
                    "signals": book.signals,
                }
                for period, trades in periods.items():
                    stats = bootstrap_interval(
                        [t.net_r for t in trades], BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES
                    )
                    cell[period] = {
                        "trades": len(trades),
                        "mean_net_r": None if stats is None else stats[0],
                        "ci_low": None if stats is None else stats[1],
                        "ci_high": None if stats is None else stats[2],
                        "meets_minimum": len(trades) >= MIN_TRADES_PER_ARM,
                    }
                results[f"{regime}/{arm}"] = cell
                print(f"  {regime}/{arm:<9} trades {len(book.trades):>5}  deferred "
                      f"{book.deferred:>6}  max concurrent {book.max_concurrent}")

    print(f"\n{'cell':<16} {'period':<9} {'n':>6} {'mean net R':>12} {'95% CI':>28} {'n>=200':>7}")
    for cell, values in results.items():
        for period in ("primary", "holdout"):
            block = values[period]
            assert isinstance(block, dict)
            mean = block["mean_net_r"]
            print(f"{cell:<16} {period:<9} {block['trades']:>6} "
                  f"{'n/a' if mean is None else f'{mean:>12.6f}'} "
                  f"{'n/a' if mean is None else f'[{block['ci_low']:.6f}, {block['ci_high']:.6f}]':>28} "
                  f"{block['meets_minimum']!s:>7}")

    decided, reason = verdict(results)
    print(f"\nVERDICT: {decided}")
    print(f"  {reason}")

    payload = {
        "prereg": "PR-012",
        "run_at": clock.isoformat(),
        "snapshot": as_of.isoformat(),
        "window": [str(window[0]), str(window[1])],
        "holdout_from": str(boundary),
        "sessions": len(eligible_sessions),
        "instruments": len(clipped),
        "classified": len(sector_of),
        "survivorship": "absent - today's directory, so every figure is biased upward",
        "country": "US",
        "parameters": {
            "lookback": LOOKBACK, "benchmark": BENCHMARK,
            "max_positions": MAX_POSITIONS, "max_open_risk": str(MAX_OPEN_RISK),
            "atr_stop_multiple": str(ATR_STOP_MULTIPLE), "max_holding_bars": MAX_HOLDING_BARS,
            "risk_per_trade": str(RISK_PER_TRADE),
            "commission_per_share": str(COMMISSION_PER_SHARE),
            "slippage_bps": str(SLIPPAGE_BPS), "stress_multiple": str(STRESS_MULTIPLE),
            "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "min_trades_per_arm": MIN_TRADES_PER_ARM,
            "min_names_for_window_start": MIN_NAMES_FOR_WINDOW_START,
        },
        "trials": 3,
        # Gate 25 condition 4: a reported study DECLARES what it registered and what it ran. An
        # empty `registered` is a legitimate declaration; an absent block is indistinguishable from
        # nobody having looked. Section 5 registered ONE perturbation and named the two it
        # deliberately does not spend a trial on - those are recorded as `considered_not_registered`
        # so the distinction between "not registered" and "registered and skipped" survives.
        "perturbations": {
            "registered": ["cost_stress_3x"],
            "run": ["cost_stress_3x"],
            "considered_not_registered": ["lookback_sweep", "capacity_sweep"],
            "recorded": (
                "2026-08-24, from PR-012 section 5. The cost stress is a SENSITIVITY on the same "
                "configurations rather than a separate arm - TRIAL_BUDGET.md: a cost stress is not "
                "a new shot at the data - so it costs no additional trial."
            ),
        },
        "results": results,
        "verdict": decided,
        "verdict_reason": reason,
    }
    if args.write:
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {RESULT}")
    else:
        print("\nnot written - pass --write to publish")
    return 0


def _verify(clipped: dict[str, BarSeries], benchmark: BarSeries, sector_of: dict[str, str],
            usable: dict[str, list[str]], by_session_returns: dict[date, dict[str, Decimal]],
            momentum: dict[tuple[str, date], Decimal], market: dict[tuple[str, date], Decimal],
            sector: dict[tuple[str, date], Decimal], sample: int) -> int:
    """Check the fast tables against `ranking.py`'s reference implementations. Seeded."""
    rng = random.Random(BOOTSTRAP_SEED)
    keys = sorted(momentum)
    if not keys:
        return 0
    index_by_session = {
        name: {bar.session_date: i for i, bar in enumerate(series.bars)}
        for name, series in clipped.items()
    }
    failures = 0
    for _ in range(min(sample, len(keys))):
        name, session = keys[rng.randrange(len(keys))]
        index = index_by_session[name][session]
        candidate = Candidate(
            instrument_id=name, session_date=session, index=index,
            close=clipped[name].bars[index].close, entry_price=Decimal(1), stop=Decimal("0.5"),
            risk_per_share=Decimal("0.5"), shares=1,
        )
        reference_momentum = ByRawReturn(clipped, LOOKBACK)
        reference_market = ByMarketPathStrength(clipped, benchmark, LOOKBACK)
        means = {
            s: sum((by_session_returns[session][n] for n in names
                    if n in by_session_returns[session]), start=Decimal(0))
            / max(1, len([n for n in names if n in by_session_returns[session]]))
            for s, names in usable.items()
        }
        reference_sector = BySectorRelativeStrength(
            clipped, sector_of, lambda _s, m=means: m, LOOKBACK
        )
        for fast, reference in (
            (momentum, reference_momentum), (market, reference_market), (sector, reference_sector)
        ):
            ordered = reference([candidate])
            if not ordered:
                failures += 1
                continue
            # The reference returns the candidate; its SCORE is what we compare, recomputed the
            # same way the reference computes it. A mismatch means the fast path is not the rule.
            expected = _reference_score(reference, candidate, clipped, benchmark, sector_of, means)
            actual = fast.get((name, session))
            if expected is None:
                continue
            if actual is None or abs(actual - expected) > Decimal("0.000000001"):
                failures += 1
    return failures


def _reference_score(reference: object, candidate: Candidate, clipped: dict[str, BarSeries],
                     benchmark: BarSeries, sector_of: dict[str, str],
                     means: dict[str, Decimal]) -> Decimal | None:
    """The score `ranking.py` would assign, computed through its own helpers."""
    from swingdesk.validation.backtest.ranking import _beat_share, _window_return

    series = clipped[candidate.instrument_id]
    if isinstance(reference, ByRawReturn):
        return _window_return(series, candidate.index, LOOKBACK)
    if isinstance(reference, ByMarketPathStrength):
        return _beat_share(series, candidate.index, LOOKBACK, daily_returns(benchmark))
    own = _window_return(series, candidate.index, LOOKBACK)
    mean = means.get(sector_of.get(candidate.instrument_id, ""))
    if own is None or mean is None or mean == -1:
        return None
    return (1 + own) / (1 + mean)


if __name__ == "__main__":
    raise SystemExit(main())
