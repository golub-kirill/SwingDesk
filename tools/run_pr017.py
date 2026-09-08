"""`PR-017` — three exits on ONE entry set: all-out at 1R, half at 1R, and no target at all.

**Every exit this project has ever measured is all-or-nothing.** `measure_exit_surface` sweeps 25
stop × target cells and closes the whole position at whichever price comes first; `PR-016` runs the
ratified pair. Nothing has ever sold PART of a position, and until 2026-09-08 `ExitPolicy` could
not express it.

**The course has an opinion, and this study is built to test it rather than to repeat it.**
`M54-T0830` asserts the partial carries `Математические недостатки`; `M54-T0832` frames
partial-against-all-out as the comparison. That argument is against cutting a winner that would
have run — and **this system does not let winners run**. `exit.target_r_multiple` is ratified at 1R
and `PR-016` measures p95 at +0.971R in both of its arms, which is the target minus costs. Against
a capped incumbent a partial caps LESS.

**One entry set, three exits, so every difference is the exit.** The arms share names, dates and
fills exactly, which is why §3 tightens the power floor to 0.15R where `PR-016` needed 0.20R.

    PYTHONPATH=$PWD/src python tools/run_pr017.py --data <store>
    python tools/run_pr017.py --report

`PRELIMINARY` on `DR-042`'s terms, exactly as `PR-016` is: the tie-break is unruled, its measured
effect is 0.05% of exits, and the ruling is the owner's.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from run_pr013 import _admitted_dates
from run_pr016 import (
    ATR_PERIOD,
    BLOCK,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    COMMISSION_PER_SHARE,
    HOLD,
    LOOKBACK,
    MIN_MONTHS,
    MIN_TRADES,
    PRIMARY_END,
    RISK_PER_TRADE,
    SLIPPAGE_BPS,
    STEP,
    STOP_MULTIPLE,
    STRESS_MULTIPLE,
    TARGET_R,
    WINDOW_START,
    OnDates,
    atr_registry,
    cell_for,
    window_sessions,
)
from run_pr014 import BENCHMARK as PR016_BENCHMARK
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import Trade
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: `M54-T0821` puts the partial at 1R and `M54-T0823` sells a half. Both are course TITLES rather
#: than thresholds - `AGENTS.md` §16 - so the study pins its own and the registry entries stay
#: unset until an owner rules on a record.
PARTIAL_TRIGGER = Decimal("1.0")
HALF = Decimal("0.5")
THIRD = Decimal("1") / Decimal(3)

#: §8's floor, tighter than `PR-016`'s 0.20 because the arms here share entries exactly. Registered
#: in §3 before any number existed, from `PR-016`'s own realised half-widths of 0.040R and 0.070R.
POWER_FLOOR = Decimal("0.15")
MINIMUM_DETECTABLE_EFFECT = Decimal("0.05")

#: The incumbent is the comparison basis, not an arm: every difference is read against it.
INCUMBENT = "all_out_1r"
ARMS = ("all_out_1r", "partial_half", "no_target")
DIAGNOSTICS = ("partial_third", "partial_half_no_stop_move")

RESULT = REPO / "docs" / "prereg" / "results" / "PR-017.json"

PRELIMINARY = {
    "status": "PRELIMINARY - not a final result",
    "why": (
        "DR-042's tie-break is unruled and this study runs under it, exactly as PR-016 does. On a "
        "bar reaching both the stop and a profit leg - target or partial trigger - the STOP is "
        "taken. Measured 2026-09-08 on PR-016's own bars: the rule takes the wrong leg 56.2% of "
        "the time and is consulted on 0.05% of exits, so the effect is at most 0.0006R a trade. "
        "The ruling is still the owner's and this file may not close it."
    ),
    "direction": "the assumption can only UNDERSTATE every arm, and it understates them equally.",
    "settled_by": "docs/decisions/DR-042 §8",
}


def policies() -> dict[str, ExitPolicy]:
    """The three arms and the two diagnostics, each a policy and nothing else.

    Every one shares the ratified stop and the ratified hold. **Only the profit slot differs**, so
    a difference between any two of them is the profit slot and cannot be anything else.
    """
    return {
        "all_out_1r": ExitPolicy(STOP_MULTIPLE, HOLD, target_r_multiple=TARGET_R),
        "partial_half": ExitPolicy(STOP_MULTIPLE, HOLD, partial_trigger=PARTIAL_TRIGGER,
                                   partial_fraction=HALF, stop_after_partial="breakeven"),
        "no_target": ExitPolicy(STOP_MULTIPLE, HOLD),
        "partial_third": ExitPolicy(STOP_MULTIPLE, HOLD, partial_trigger=PARTIAL_TRIGGER,
                                    partial_fraction=THIRD, stop_after_partial="breakeven"),
        # The other reading of an unset `exit.stop_move_after_partial`: the stop does not move.
        # It is what says how much of any effect is the PARTIAL and how much is the moved stop.
        "partial_half_no_stop_move": ExitPolicy(STOP_MULTIPLE, HOLD,
                                                partial_trigger=PARTIAL_TRIGGER,
                                                partial_fraction=HALF),
    }


def underpowered(cell: dict[str, Any]) -> bool:
    interval = cell.get("difference_mean")
    if not interval:
        return True
    return bool((interval["high"] - interval["low"]) > float(POWER_FLOOR))


def qualifies(cell: dict[str, Any]) -> bool:
    return bool(cell.get("trades", 0) >= MIN_TRADES and cell.get("months", 0) >= MIN_MONTHS)


def verdict_for(cells: dict[str, dict[str, Any]]) -> str:
    """§6, and the only place a verdict is formed. Reads `partial_half` minus `all_out_1r`."""
    windows = ("in_sample", "out_of_sample")
    if not all(qualifies(cells.get(w, {})) for w in windows):
        return "inconclusive"
    if any(underpowered(cells[w]) for w in windows):
        return "inconclusive"
    if all(cells[w]["difference_mean"]["low"] > 0 for w in windows):
        return "accept"
    if all(cells[w]["difference_mean"]["high"] < 0 for w in windows):
        return "reject"
    return "inconclusive"


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        raise SystemExit("the bar store is empty")

    series_by_name: dict[str, BarSeries] = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= 252 + HOLD + 1:
            series_by_name[name] = series
    store.close()
    if PR016_BENCHMARK not in series_by_name:
        raise SystemExit(f"{PR016_BENCHMARK} has too little history to fix the calendar")

    calendar = [bar.session_date for bar in series_by_name[PR016_BENCHMARK].bars]
    start = date.fromisoformat(args.start) if args.start else WINDOW_START
    end = date.fromisoformat(args.end) if args.end else calendar[-1]
    sessions = window_sessions(calendar, start, end)
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    formations = ([d for d in sessions[::STEP] if earliest <= d <= sessions[-HOLD - 1]]
                  if len(sessions) > HOLD else [])
    print(f"as_of {as_of.isoformat()}   instruments {len(series_by_name)}   "
          f"formation dates {len(formations)}")

    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}
    every = policies()
    stressed = {f"{a}_3x": every[a] for a in ARMS}
    costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    stress_costs = CostModel(COMMISSION_PER_SHARE * STRESS_MULTIPLE,
                             SLIPPAGE_BPS * STRESS_MULTIPLE)
    registry = atr_registry()

    series_names = [*ARMS, *DIAGNOSTICS, *stressed]
    trades: dict[str, list[Trade]] = {a: [] for a in series_names}
    partials: Counter[str] = Counter()
    ambiguous: Counter[str] = Counter()
    for count, (name, series) in enumerate(sorted(series_by_name.items()), start=1):
        dates = admitted.get(name)
        if not dates:
            continue
        atr_series = atr_component.compute(series, registry)
        gate: list[bool | None] = [True] * len(series.bars)
        trigger = OnDates(frozenset(dates))
        for arm in series_names:
            policy = stressed[arm] if arm in stressed else every[arm]
            config = BacktestConfig(arm=arm, exits=policy,
                                    costs=stress_costs if arm in stressed else costs,
                                    trigger=trigger, risk_per_trade=RISK_PER_TRADE)
            result = run_arm(series, gate, atr_series, config)
            trades[arm].extend(result.trades)
            partials[arm] += result.partials
            ambiguous[arm] += result.ambiguous_exits
        if count % 500 == 0:
            print(f"  simulated {count}/{len(series_by_name)} instruments")

    day_after = PRIMARY_END + timedelta(days=1)
    windows = {"full": (start, end), "in_sample": (start, min(PRIMARY_END, end)),
               "out_of_sample": (max(day_after, start), end)}

    result: dict[str, Any] = {
        "prereg": "PR-017", "trials": 2, "as_of": as_of.isoformat(), "country": "USA",
        "preliminary": PRELIMINARY,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "sessions": len(sessions)},
        "exit": {"atr_period": ATR_PERIOD, "atr_stop_multiple": str(STOP_MULTIPLE),
                 "max_holding_period": HOLD, "target_r_multiple": str(TARGET_R),
                 "partial_trigger": str(PARTIAL_TRIGGER), "partial_fraction": str(HALF),
                 "stop_after_partial": "breakeven"},
        "split": {"in_sample": f"entries on or before {PRIMARY_END}",
                  "out_of_sample": f"entries after {PRIMARY_END}",
                  "buys": ("a second window at PR-014's and PR-016's own boundary, so the cut was "
                           "not chosen after seeing these data, and three studies are comparable "
                           "at one place")},
        "perturbations": {"registered": ["cost_stress_1x", "cost_stress_3x"],
                          "run": ["cost_stress_1x", "cost_stress_3x"],
                          "note": ("re-simulated at 3x and each arm differenced against its OWN "
                                   "cost level - PR-016 learned that one the hard way")},
        "stress_multiple": STRESS_MULTIPLE,
        "power_floor": str(POWER_FLOOR),
        "minimum_detectable_effect": str(MINIMUM_DETECTABLE_EFFECT),
        "bootstrap": {"unit": "entry month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                      "resamples": BOOTSTRAP_RESAMPLES},
        "instruments": len(series_by_name), "formation_dates": len(formations),
        "partials_taken": dict(partials), "ambiguous_exits": dict(ambiguous),
        "survivorship": ("ABSENT and material, as PR-016 records: 2,598 of 2,598 decade-long "
                         "instruments in this store are still trading"),
        "not_measured": [
            "the psychological advantage M54-T0829 names - not a property of a price series and "
            "not smuggled in as one",
            "any selection. Entries are unselected, so no arm claims an edge",
            "the book: one trade at a time, no cap and no capacity",
        ],
        "arms": {}, "diagnostics": {},
    }

    entered = sorted(t.entry_date for t in trades[INCUMBENT])
    if entered:
        span = (entered[-1] - entered[0]).days
        result["measured_span"] = {
            "first_entry": entered[0].isoformat(), "last_entry": entered[-1].isoformat(),
            "years": round(span / 365.25, 2),
            "meets_the_ten_year_instruction": span / 365.25 >= 10.0,
        }

    for arm in series_names:
        against = f"{INCUMBENT}_3x" if arm.endswith("_3x") else INCUMBENT
        cells: dict[str, Any] = {}
        for window, (first, last) in windows.items():
            selected = [t for t in trades[arm] if first <= t.entry_date <= last]
            control = [t for t in trades[against] if first <= t.entry_date <= last]
            cells[window] = cell_for(selected, control if arm != against else selected)
        target = result["arms"] if arm in ARMS else result["diagnostics"]
        target[arm] = cells

    result["verdict"] = verdict_for(result["arms"]["partial_half"])
    return result


def report(result: dict[str, Any]) -> None:
    preliminary = result.get("preliminary")
    if preliminary:
        print(f"*** {preliminary['status']} ***")
        print(f"    {preliminary['why']}\n")
    print(f"PR-017   as_of {result['as_of']}   verdict {result['verdict'].upper()}")
    exits = result["exit"]
    print(f"  stop {exits['atr_stop_multiple']} x ATR({exits['atr_period']}), hold "
          f"{exits['max_holding_period']}; the profit slot is what differs")
    span = result.get("measured_span")
    if span:
        print(f"  entries {span['first_entry']} .. {span['last_entry']} = {span['years']} years")
    print(f"  {result['instruments']} instruments, {result['formation_dates']} formation dates\n")

    print(f"  {'arm':28} {'window':14} {'n':>7} {'win%':>6} {'meanR':>8} {'skew':>7} "
          f"{'partials':>9}")
    for group in ("arms", "diagnostics"):
        for arm, cells in result[group].items():
            for window in ("in_sample", "out_of_sample"):
                cell = cells.get(window, {})
                if not cell.get("trades"):
                    continue
                print(f"  {arm:28} {window:14} {cell['trades']:>7} "
                      f"{cell['win_rate'] * 100:>6.2f} {cell['mean_net_r']:>+8.4f} "
                      f"{cell.get('skew') or 0:>+7.2f} "
                      f"{result['partials_taken'].get(arm, 0):>9}")
        print()

    print("  the only quantity section 6 reads: partial_half minus all_out_1r")
    for window in ("in_sample", "out_of_sample"):
        diff = result["arms"]["partial_half"].get(window, {}).get("difference_mean")
        if not diff:
            continue
        flag = "*" if diff["low"] > 0 or diff["high"] < 0 else " "
        wide = "  UNDERPOWERED" if (diff["high"] - diff["low"]) > float(POWER_FLOOR) else ""
        print(f"    {window:14} {diff['observed']:>+8.4f} "
              f"[{diff['low']:>+8.4f}, {diff['high']:>+8.4f}] {flag}{wide}")

    print("\n  every other arm, against the same incumbent:")
    for group in ("arms", "diagnostics"):
        for arm, cells in result[group].items():
            if arm == INCUMBENT:
                continue
            for window in ("in_sample", "out_of_sample"):
                diff = cells.get(window, {}).get("difference_mean")
                if diff:
                    print(f"    {arm:28} {window:14} {diff['observed']:>+8.4f} "
                          f"[{diff['low']:>+8.4f}, {diff['high']:>+8.4f}]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--as-of", help="knowledge instant, ISO-8601; defaults to the latest")
    parser.add_argument("--from", dest="start", help=f"first session (default {WINDOW_START})")
    parser.add_argument("--to", dest="end", help="last session (default: the latest)")
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true", help="print an existing result and exit")
    args = parser.parse_args()

    if args.report:
        report(json.loads(args.out.read_text(encoding="utf-8")))
        return 0
    result = build(args)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
