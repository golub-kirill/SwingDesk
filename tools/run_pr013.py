"""PR-013: does relative strength separate forward returns at all, measured on names not on a book?

Runs the three arms `docs/prereg/PR-013-relative-strength-signal.md` registered, over the window
that pre-registration defines by RULE rather than by date. **The study is EXPLORATORY by declaration
(§0b)** - the drafter had seen PR-012's numbers - so no verdict here advances a validation status.

**Nothing here defines a score.** `LOOKBACK`, `BENCHMARK`, the three score tables and the bootstrap
are imported unchanged from `run_pr012`, whose own `--verify-sample` check binds those definitions to
the reference implementations in `validation/backtest/ranking.py`. A second copy of "share of
sessions that beat the benchmark" is exactly the divergence that check exists to catch, and this
runner introduces none.

**What is different from PR-012, and it is the whole point of the study:**

* the unit is a **formation date**, not a trade. On each date every admitted name is ranked and the
  statistic is the top-decile minus bottom-decile forward return - a property of the date.
* **admission is evaluated at each formation date's own bar index** (§10 amendment A-2), so a name
  that did not meet the price, ADTV or history floor on that date is not ranked on it. PR-012
  admitted once at the snapshot and used that set throughout.
* the horizon is **5 sessions**, which is what buys the sample: five times as many non-overlapping
  formation dates as the ratified 20-session holding period permits trades to be opened.

**Costs are slippage only** (§10 amendment A-1): commission is per SHARE and a decile of names has
no position size, so expressing it would mean inventing a number. The omission biases the net figure
UPWARD and the report says so.

    python tools/run_pr013.py --data C:/PycharmProjects/SwingDesk/data [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr012 import (
    BENCHMARK,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    LOOKBACK,
    MIN_SECTOR_MEMBERS,
    SLIPPAGE_BPS,
    STRESS_MULTIPLE,
    _beat_prefix,
    _daily_returns_by_session,
    _window_returns,
    add_vintage_arguments,
    bootstrap_interval,
    resolve_vintage,
)
from swingdesk.application.universe import ADTV_WINDOW
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.classification import ClassificationStore, look_through
from swingdesk.reference_data.directory import DirectoryStore

RESULT = REPO / "docs" / "prereg" / "results" / "PR-013.json"

# --- fixed by the pre-registration, before the run. A constant that drifts makes this a different
# --- study under PR-013's name.
HORIZON = 5
FORMATION_EVERY = 5
DECILE = Decimal("0.10")
MIN_NAMES_PER_DATE = 100
MIN_DATES_HOLDOUT = 100
MIN_NAMES_FOR_WINDOW_START = 200

#: Inherited from PR-012 rather than chosen, so that no split was picked to suit a result (§0b).
HOLDOUT_FROM = date(2023, 10, 12)

#: A decile-spread portfolio turns over both legs at each rebalance: two sides on each of two legs.
COST_SIDES_PER_FORMATION = 4

ARMS = ("MOMENTUM", "MARKET", "SECTOR")


def _forward_returns(series: BarSeries, horizon: int) -> dict[date, Decimal]:
    """Close-to-close return over the next `horizon` of the name's OWN sessions."""
    out: dict[date, Decimal] = {}
    bars = series.bars
    for index in range(len(bars) - horizon):
        start = bars[index].close
        if start > 0:
            out[bars[index].session_date] = (bars[index + horizon].close - start) / start
    return out


def _admitted_dates(series: BarSeries, rule: rules.LiquidityRule,
                    dates: list[date]) -> set[date]:
    """Which of `dates` the liquidity rule admits this name on, judged at that date's own bar.

    `LiquidityRule.admits` is called with the index rather than reimplemented - the rule is
    `reference_data`'s and a second copy of it here would be the one-logic-in-two-places failure.
    """
    index_of = {bar.session_date: i for i, bar in enumerate(series.bars)}
    return {d for d in dates if (i := index_of.get(d)) is not None and rule.admits(series, i)}


def _spread(scores: dict[str, Decimal], forward: dict[str, Decimal]) -> Decimal | None:
    """Top-decile mean minus bottom-decile mean, or None when the cross-section is too thin.

    A name without a score is EXCLUDED rather than sorted to the bottom. PR-012's rankers sort an
    unscoreable name last so it competes and loses, which is right for a book; in a decile study it
    would fill the bottom bucket with names the measure never scored and manufacture a spread.
    """
    ranked = sorted(
        ((s, n) for n, s in scores.items() if n in forward),
        key=lambda pair: (-pair[0], pair[1]),
    )
    if len(ranked) < MIN_NAMES_PER_DATE:
        return None
    size = int(len(ranked) * DECILE)
    if size < 1:
        return None
    top = [forward[n] for _, n in ranked[:size]]
    bottom = [forward[n] for _, n in ranked[-size:]]
    return (sum(top, Decimal(0)) / len(top)) - (sum(bottom, Decimal(0)) / len(bottom))


def verdict(arm: dict[str, object], control: dict[str, object]) -> str:
    """§6, applied to one arm's holdout against the control's. Fixed before the run."""
    low, high = Decimal(str(arm["ci_low"])), Decimal(str(arm["ci_high"]))
    if low > 0 and low > Decimal(str(control["mean_net"])):
        return "accept"
    if (low <= 0 <= high) or Decimal(str(arm["mean_net"])) <= Decimal(str(control["mean_net"])):
        return "reject"
    return "inconclusive"


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr013")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--write", action="store_true",
                        help="publish docs/prereg/results/PR-013.json. Without it, nothing is "
                             "written and the run is a measurement only")
    add_vintage_arguments(parser)
    args = parser.parse_args()

    vintage = resolve_vintage(as_of_arg=args.as_of, reproduce=args.reproduce,
                              result_path=RESULT, now=datetime.now(UTC))
    if args.reproduce and args.write:
        raise SystemExit("--reproduce does not publish. Drop --write, or run without --reproduce.")

    clock = vintage.clock
    with (
        BarStore(args.data / "bars.duckdb") as store,
        DirectoryStore(args.data / "directory.duckdb") as directory,
        ClassificationStore(args.data / "classifications.duckdb") as classifications,
    ):
        as_of = vintage.as_of or store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("bar store is empty")
        print(f"vintage: bars at {as_of.isoformat()}, classifications at {clock.isoformat()} "
              f"({vintage.source})")

        benchmark = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
        if not benchmark.bars:
            raise SystemExit(f"{BENCHMARK} is not stored - DR-018's benchmark is missing")

        # The same DR-003 rule PR-012 pinned. Admission at the snapshot bounds WHICH names are read;
        # admission per formation date, below, decides which are RANKED (amendment A-2).
        rule = rules.LiquidityRule(
            min_price=Decimal("5.00"), min_adtv=Decimal(5_000_000),
            adtv_window=ADTV_WINDOW, min_history=250,
            adtv_lag=0,  # DR-017's lag postdates this study; 0 is the rule it ran under
        )
        stored = set(store.instrument_ids(as_of))
        universe: dict[str, BarSeries] = {}
        for entry in directory.as_of(as_of, eligible_only=True):
            if entry.symbol not in stored or entry.symbol == BENCHMARK:
                continue
            series = store.as_of(entry.symbol, Interval.DAY, Series.RAW, as_of)
            if series.bars and rule.admits(series):
                universe[entry.symbol] = series
        print(f"snapshot {as_of.isoformat()}  ·  read {len(universe)} name(s)")

        sector_of: dict[str, str] = {}
        for name in universe:
            exposure = look_through(classifications.as_of(name, clock), name)
            if exposure.is_available and exposure.weights:
                sector_of[name] = max(exposure.weights, key=lambda w: w.weight).sector
        print(f"classified {len(sector_of)} of {len(universe)}")

        # --- the window, by the pre-registration's RULE and not by a chosen date. Same construction
        # --- as PR-012, so the two studies describe the same span.
        returns_by_name = {n: _window_returns(s, LOOKBACK) for n, s in universe.items()}
        per_session: dict[date, int] = defaultdict(int)
        for table in returns_by_name.values():
            for session in table:
                per_session[session] += 1
        eligible = sorted(s for s, c in per_session.items() if c >= MIN_NAMES_FOR_WINDOW_START)
        if not eligible:
            print(f"REFUSING: no session has {MIN_NAMES_FOR_WINDOW_START} scoreable names.")
            return 2
        window = (eligible[0], eligible[-1])
        formation = eligible[::FORMATION_EVERY]
        print(f"window {window[0]} -> {window[1]}  ·  {len(eligible)} sessions  ·  "
              f"{len(formation)} non-overlapping formation dates  ·  holdout from {HOLDOUT_FROM}")

        benchmark_daily = _daily_returns_by_session(benchmark)

        momentum: dict[tuple[str, date], Decimal] = {}
        market: dict[tuple[str, date], Decimal] = {}
        forward_by_name: dict[str, dict[date, Decimal]] = {}
        admitted_on: dict[str, set[date]] = {}
        for name, series in universe.items():
            for session, value in returns_by_name[name].items():
                momentum[(name, session)] = value
            for session, value in _beat_prefix(series, benchmark_daily, LOOKBACK).items():
                market[(name, session)] = value
            forward_by_name[name] = _forward_returns(series, HORIZON)
            admitted_on[name] = _admitted_dates(series, rule, formation)

        # The sector denominator: the mean window return of the name's own sector on that session,
        # over names that HAVE one. Supplied by the study, as `BySectorRelativeStrength` requires.
        members: dict[str, list[str]] = defaultdict(list)
        for name in universe:
            if name in sector_of:
                members[sector_of[name]].append(name)
        usable = {s: n for s, n in members.items() if len(n) >= MIN_SECTOR_MEMBERS}

        sector: dict[tuple[str, date], Decimal] = {}
        by_session: dict[date, dict[str, Decimal]] = defaultdict(dict)
        for name in universe:
            for session, value in returns_by_name[name].items():
                by_session[session][name] = value
        for session, values in by_session.items():
            means: dict[str, Decimal] = {}
            for sector_name, names in usable.items():
                have = [values[n] for n in names if n in values]
                if len(have) >= MIN_SECTOR_MEMBERS:
                    means[sector_name] = sum(have, Decimal(0)) / len(have)
            for name, own in values.items():
                mean = means.get(sector_of[name]) if name in sector_of else None
                if mean is not None and mean != -1:
                    sector[(name, session)] = (1 + own) / (1 + mean)

        tables = {"MOMENTUM": momentum, "MARKET": market, "SECTOR": sector}

    cost = SLIPPAGE_BPS * COST_SIDES_PER_FORMATION / Decimal(10_000)
    spreads: dict[str, dict[str, list[Decimal]]] = {
        arm: {"primary": [], "holdout": []} for arm in ARMS
    }
    thin = 0
    for day in formation:
        eligible_names = {n for n in universe if day in admitted_on[n]}
        forward = {
            n: forward_by_name[n][day]
            for n in eligible_names
            if day in forward_by_name[n]
        }
        period = "holdout" if day >= HOLDOUT_FROM else "primary"
        for arm in ARMS:
            table = tables[arm]
            scores = {n: table[(n, day)] for n in eligible_names if (n, day) in table}
            value = _spread(scores, forward)
            if value is None:
                if arm == "MOMENTUM":
                    thin += 1
                continue
            spreads[arm][period].append(value)  # GROSS; costs are applied at reporting time

    print(f"formation dates too thin to decile ({MIN_NAMES_PER_DATE} names): {thin}")

    results: dict[str, dict[str, dict[str, object]]] = {}
    print(f"\n{'arm':10} {'period':9} {'dates':>6} {'mean gross':>13} {'mean net':>13} "
          f"{'95% CI (net)':>26} {'net @3x cost':>13}")
    for arm in ARMS:
        results[arm] = {}
        for period in ("primary", "holdout"):
            values = spreads[arm][period]
            interval = bootstrap_interval(values, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES)
            if not values or interval is None:
                # `bootstrap_interval` returns None below two observations. A period with one
                # formation date has no interval, and reporting a point estimate without one would
                # be the false precision the whole study is trying to avoid.
                results[arm][period] = {"dates": len(values)}
                continue
            # The bootstrap returns (mean, low, high) and its mean is a float. The reported mean is
            # the Decimal one computed here - same value, exact arithmetic - and the interval is the
            # bootstrap's. Taking the mean from one place and the bounds from another is deliberate
            # rather than sloppy: this project's money and returns are Decimal by rule.
            _, low, high = interval
            gross = sum(values, Decimal(0)) / len(values)
            # GROSS beside NET, which section 4 requires and the first run omitted. Costs enter as
            # ONE constant per formation date, so every cost figure is an exact shift of the same
            # estimate rather than a second one - which is also what makes section 5's registered
            # 3x stress a sensitivity that spends no trial.
            #
            # Gross is the figure that answers "does the ordering carry information at all". Net
            # cannot separate that from "is it harvestable at this rebalance frequency", and at a
            # five-session rebalance the second question dominates by construction.
            results[arm][period] = {
                "dates": len(values),
                "mean_gross": str(gross),
                "ci_low_gross": str(low), "ci_high_gross": str(high),
                "mean_net": str(gross - cost),
                "ci_low": str(Decimal(str(low)) - cost),
                "ci_high": str(Decimal(str(high)) - cost),
                "mean_net_stress_3x": str(gross - cost * STRESS_MULTIPLE),
                "ci_low_stress_3x": str(Decimal(str(low)) - cost * STRESS_MULTIPLE),
                "ci_high_stress_3x": str(Decimal(str(high)) - cost * STRESS_MULTIPLE),
                "meets_minimum": len(values) >= MIN_DATES_HOLDOUT,
            }
            span = f"[{float(low) - float(cost):.6f}, {float(high) - float(cost):.6f}]"
            print(f"{arm:10} {period:9} {len(values):6d} {float(gross):13.6f} "
                  f"{float(gross - cost):13.6f} {span:>26} "
                  f"{float(gross - cost * STRESS_MULTIPLE):13.6f}")

    holdout_dates = results["MOMENTUM"]["holdout"].get("dates", 0)
    if not isinstance(holdout_dates, int) or holdout_dates < MIN_DATES_HOLDOUT:
        outcome = "REFUSED"
        reason = (f"section 8's minimum of {MIN_DATES_HOLDOUT} holdout formation dates is not met "
                  f"({holdout_dates}) - the study reports the measurement and refuses a verdict")
    else:
        control = results["MOMENTUM"]["holdout"]
        calls = {arm: verdict(results[arm]["holdout"], control) for arm in ("MARKET", "SECTOR")}
        outcome = "accept" if "accept" in calls.values() else (
            "reject" if all(c == "reject" for c in calls.values()) else "inconclusive"
        )
        reason = "; ".join(f"{arm} {call}" for arm, call in calls.items())

    print(f"\nVERDICT: {outcome}\n  {reason}")
    print("  EXPLORATORY by section 0b - this advances no validation status whatever it says.")

    payload = {
        "prereg": "PR-013",
        "exploratory": True,
        "exploratory_reason": "section 0b - the drafter had seen PR-012's results before designing",
        "run_at": clock.isoformat(),
        "snapshot": as_of.isoformat(),
        "window": [window[0].isoformat(), window[1].isoformat()],
        "holdout_from": HOLDOUT_FROM.isoformat(),
        "formation_dates": len(formation),
        "instruments": sorted(universe),
        "classified": len(sector_of),
        "parameters": {
            "lookback": LOOKBACK, "horizon": HORIZON, "formation_every": FORMATION_EVERY,
            "decile": str(DECILE), "benchmark": BENCHMARK,
            "slippage_bps": str(SLIPPAGE_BPS), "cost_sides_per_formation": COST_SIDES_PER_FORMATION,
            "commission": "excluded - amendment A-1, and the omission biases the result upward",
            "min_names_per_date": MIN_NAMES_PER_DATE, "min_dates_holdout": MIN_DATES_HOLDOUT,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES, "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "survivorship": "absent - today's directory, so every figure is biased upward",
        "country": "US",
        "perturbations": {
            "registered": ["cost_stress_3x"],
            "run": ["cost_stress_3x"],
            "considered_not_registered": [
                "lookback_sweep", "horizon_sweep", "decile_width_sweep", "execution_delay",
            ],
            "note": "section 5. Costs enter as one constant per formation date, so the stress is "
                    "an exact shift of the same estimates rather than a new shot at the data - "
                    "TRIAL_BUDGET.md: a cost stress spends no trial.",
        },
        "trials": 3,
        "results": results,
        "verdict": outcome,
        "verdict_reason": reason,
    }
    if args.write:
        RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {RESULT.relative_to(REPO)}")
    else:
        print("\nnot written - pass --write to publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
