"""The power estimate `PR-020` needs BEFORE it registers: which hold can see the screen's skill at all?

`measure_universe_null` (2026-09-13, exploratory) found the 4 ATR / 60-session exit loses to simply
HOLDING the admitted universe over the same days, and the screen claws back about 0.06R inside it.
`PR-020` asks the clean version: the ratified decile's selected names HELD with no stop, against
their own equal-weighted universe over exactly the same sessions, in the trade's own R.

**Which hold is not chosen by preference, and not by level.** The first estimate sized only 60
sessions and it could not be read: a predicted out-of-sample half-width of 0.1828 against the 0.075
the 0.15R floor needs. So this sizes every no-stop cell `PR-019`'s grid holds - 10, 20, 40 and 60
sessions, the same spaced entries - and the registration takes the one this design can read. A
DISPERSION picks it; no level is computed, so choosing among them cannot choose the answer.

**Overlap-aware from the start.** `PR-019b` promised 0.0743 and realised 0.1214 because independent
months were assumed where holds overlap them. The `_overlap` fields here carry each hold's own lags.

**Dispersion only.** `power_pr019.assert_no_effect_leaked` refuses any level. In sample only.

**One approximation, stated.** The subsample's pool is the subsample's own admitted names, not the
full universe's - noisier by construction; the variance-components correction removes the
within-month noise of `trade - pool`, the pool's subsampling noise included.

    PYTHONPATH=$PWD/src python tools/power_pr020.py --data <store> --as-of <instant>
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from measure_universe_null import contribute, daily_pool, pool_r, segments
from power_pr019 import (
    DEFAULT_FRACTION,
    DEFAULT_SEED,
    MAX_HOLD,
    OOS_MONTHS,
    READABLE_HALF_WIDTH,
    assert_no_effect_leaked,
    cells,
    half_width,
    lags_for_hold,
    overlap_inflation,
    predicted_oos,
    spaced,
    subsample,
    variance_components,
)
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import BENCHMARK, DECILE, Candidate, select
from run_pr016 import (
    COMMISSION_PER_SHARE,
    HOLD,
    LOOKBACK,
    PRIMARY_END,
    RISK_PER_TRADE,
    SLIPPAGE_BPS,
    STEP,
    WINDOW_START,
    OnDates,
    atr_registry,
    window_sessions,
)
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: Every no-stop cell `PR-019`'s grid holds: no protective stop, R denominator 2 ATR, the same
#: entries spaced at 60 sessions. The registration takes the one the floor can read.
CELLS = ("h10_stopnone", "h20_stopnone", "h40_stopnone", "h60_stopnone")

RESULT = REPO / "docs" / "prereg" / "results" / "PR-020-power.json"


def dispersion(per_month: dict[str, list[float]], hold: int) -> dict[str, float]:
    """`power_pr019b.dispersion`'s fields, the overlap correction at THIS hold's lags."""
    components = variance_components(per_month)
    months = int(components["months"])
    corrected = half_width(components["var_between"], months)
    ordered = [statistics.fmean(per_month[m])
               for m in sorted(m for m, values in per_month.items() if len(values) >= 2)]
    lags = lags_for_hold(hold)
    factor = overlap_inflation(ordered, components["var_between"], lags)
    overlapped = (half_width(components["var_between"] * factor, months)
                  if not math.isnan(factor) else float("nan"))
    return {**components,
            "half_width_uncorrected": half_width(components["var_observed"], months),
            "half_width_corrected": corrected,
            "half_width_predicted_oos": predicted_oos(corrected, months),
            "overlap_lags": float(lags),
            "overlap_factor": factor,
            "half_width_overlap": overlapped,
            "half_width_predicted_oos_overlap": predicted_oos(overlapped, months)}


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        raise SystemExit("the bar store is empty")
    every = sorted(store.instrument_ids(as_of))
    kept = set(subsample(every, args.fraction, args.seed)) | {BENCHMARK}
    series_by_name: dict[str, BarSeries] = {}
    for name in every:
        if name not in kept:
            continue
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= 252 + HOLD + 1:
            series_by_name[name] = series
    store.close()
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to fix the calendar")

    benchmark = series_by_name[BENCHMARK]
    calendar = [bar.session_date for bar in benchmark.bars]
    calendar_index = {session: i for i, session in enumerate(calendar)}
    end = min(PRIMARY_END, calendar[-1])
    sessions = window_sessions(calendar, WINDOW_START, end)
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    formations = ([d for d in sessions[::STEP] if earliest <= d <= sessions[-HOLD - 1]]
                  if len(sessions) > HOLD else [])
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    print(f"as_of {as_of.isoformat()}   universe {len(every)}   subsample {len(series_by_name)}   "
          f"formation dates {len(formations)}   window {WINDOW_START}..{end} (IN SAMPLE ONLY)",
          flush=True)

    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}
    selected: dict[str, list[date]] = {}
    everything: dict[str, list[date]] = {}
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            continue
        for candidate in pool:
            everything.setdefault(candidate.instrument_id, []).append(session)
        ranker = ByMarketPathStrength(series=series_by_name, benchmark=benchmark, lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top:
            selected.setdefault(name, []).append(session)

    # The subsample's own universe, equal-weighted, over the sessions each live formation owns.
    live = sorted({d for dates in everything.values() for d in dates})
    days_of = segments(live, calendar)
    sums: dict[date, list[float]] = defaultdict(lambda: [0.0, 0, 0.0, 0])
    for name, dates in everything.items():
        contribute(sums, series_by_name[name], (day for f in dates for day in days_of.get(f, ())))
    close_to_close, open_to_close = daily_pool(sums)

    costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    registry = atr_registry()
    policies = {label: cells()[label] for label in CELLS}
    per_cell: dict[str, dict[str, Any]] = {}
    buckets = {label: (defaultdict(list), defaultdict(list), defaultdict(list)) for label in CELLS}
    counts = {label: [0, 0] for label in CELLS}  # trades, unpriced
    for name in sorted(selected):
        series = series_by_name[name]
        atr = atr_component.compute(series, registry)
        dates = frozenset(spaced(selected[name], calendar_index, MAX_HOLD))
        for label, policy in policies.items():
            config = BacktestConfig(arm=label, exits=policy, costs=costs, trigger=OnDates(dates),
                                    risk_per_trade=RISK_PER_TRADE)
            paired, alone, pool_only = buckets[label]
            for trade in run_arm(series, [True] * len(series.bars), atr, config).trades:
                leg = pool_r(trade, close_to_close, open_to_close, calendar, calendar_index)
                if leg is None:
                    counts[label][1] += 1
                    continue
                counts[label][0] += 1
                month = trade.entry_date.strftime("%Y-%m")
                paired[month].append(float(trade.net_r) - leg)
                alone[month].append(float(trade.net_r))
                pool_only[month].append(leg)
    for label, policy in policies.items():
        paired, alone, pool_only = buckets[label]
        hold = policy.max_holding_bars
        per_cell[label] = {
            "max_holding_period": hold, "protective_stop": False,
            "trades": counts[label][0], "trades_without_a_pool_price": counts[label][1],
            "dispersion": {"trade_minus_pool": dispersion(paired, hold),
                           "trade_alone": dispersion(alone, hold),
                           "pool_alone": dispersion(pool_only, hold)},
        }

    payload: dict[str, Any] = {
        "for": "PR-020",
        "purpose": "a variance estimate for PREREG_TEMPLATE rule 9, overlap-aware, across the "
                   "no-stop holds; the registration takes the hold the floor can read. No level.",
        "as_of": as_of.isoformat(), "fraction": args.fraction, "seed": args.seed,
        "universe": len(every), "subsample": len(series_by_name),
        "formation_dates": len(formations),
        "window": {"start": WINDOW_START.isoformat(), "end": end.isoformat(),
                   "note": "IN SAMPLE ONLY - the holdout is not touched by a power estimate"},
        "entry_spacing_sessions": MAX_HOLD,
        "cells": per_cell,
        "oos_months": OOS_MONTHS, "readable_half_width": READABLE_HALF_WIDTH,
        "approximation": ("the _overlap half-widths carry the measured autocorrelation of "
                          "overlapping holds; the others assume independent months and are a "
                          "LOWER bound - PR-019b's was 1.7x too low"),
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-020 power estimate - dispersion only, no level\n{'=' * 62}")
    print(f"  subsample {payload['subsample']} of {payload['universe']}")
    print(f"\n  {'cell':14} {'trades':>7} {'series':18} {'lags':>5} {'factor':>7} "
          f"{'OOS hw, overlap':>16}")
    for label, cell in payload["cells"].items():
        for name, block in cell["dispersion"].items():
            print(f"  {label:14} {cell['trades']:>7} {name:18} {int(block['overlap_lags']):>5} "
                  f"{block['overlap_factor']:>7.3f} {block['half_width_predicted_oos_overlap']:>16.4f}")
    print(f"\n  readable at the 0.15R floor: OOS half width <= {payload['readable_half_width']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--fraction", type=float, default=DEFAULT_FRACTION)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true",
                        help="re-read an existing estimate instead of running it")
    args = parser.parse_args()
    if args.report:
        report(json.loads(args.out.read_text(encoding="utf-8")))
        return 0
    payload = build(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report(payload)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
