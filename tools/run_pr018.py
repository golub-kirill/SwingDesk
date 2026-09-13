"""`PR-018` — on the entries the screen actually selects, does the exit policy beat doing nothing?

**The comparison has never been made on entries anyone would trade.** `measure_exit_surface` makes
it on UNSELECTED names and is exploratory; `PR-016` and `PR-017` compare exits to each other and
never to none. The selected decile is where the money would go.

**And the numbers that make it worth asking** — the same entries, one round trip each, therefore
the same cost:

    buy and hold, 20 sessions      gross +0.140R    net at 50 bps  -0.031R
    the ratified 2.0 x 1R cell     gross +0.042R    net at 50 bps  -0.128R

**§3 predicts H1 FAILS**, and the hypothesis is registered that way round on purpose: the incumbent
is what costs something, so the incumbent is what has to prove itself.

**§6 reads the MAE beside the mean, in the same paragraph.** An exit policy that costs 0.1R and
removes a -47R tail is a different object from one that costs 0.1R and removes nothing, and a study
reporting only the mean would answer half the question while sounding like it had answered all of
it.

    PYTHONPATH=$PWD/src python tools/run_pr018.py --data <store>
    python tools/run_pr018.py --report

`PRELIMINARY` on `DR-042`'s terms, as `PR-016` and `PR-017` are.
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
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import BENCHMARK, DECILE, Candidate, select
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
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import Trade
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: `EVIDENCE_SUMMARY` §10's measured 11:00 median, registered in §5 as a perturbation and NOT as a
#: claim that the strategy can be executed there - a later entry changes the gross as well as the
#: cost (`DR-040` §4), and this re-prices an entry struck at the open.
CHEAP_BPS = Decimal("5.75")

POWER_FLOOR = Decimal("0.15")
MINIMUM_DETECTABLE_EFFECT = Decimal("0.05")

#: The incumbent is on trial; the null is doing nothing.
INCUMBENT = "ratified"
NULL_ARM = "hold_only"
ARMS = (INCUMBENT, NULL_ARM)
DIAGNOSTICS = ("ratified_no_target", "unselected_ratified", "unselected_hold_only")

#: MAE thresholds the report counts trades below. The exit policy exists to bound this tail, so
#: these are the numbers §6 reads beside the mean.
MAE_BANDS = (Decimal("-1"), Decimal("-2"), Decimal("-3"))

RESULT = REPO / "docs" / "prereg" / "results" / "PR-018.json"

PRELIMINARY = {
    "status": "PRELIMINARY - not a final result",
    "why": (
        "DR-042's tie-break is unruled and this study runs under it. Measured 2026-09-08: the rule "
        "takes the wrong leg 56.2% of the time and is consulted on 0.05% of exits, so at most "
        "0.0006R a trade - and it can only bind on the RATIFIED arm, since hold_only has no stop "
        "to be ambiguous about. The ruling is the owner's and this file may not close it."
    ),
    "direction": (
        "the assumption understates the ratified arm only, so it makes H1 HARDER rather than "
        "easier - the direction §3 predicts is not the direction the assumption pushes."
    ),
    "settled_by": "docs/decisions/DR-042 §8",
}


def policies() -> dict[str, ExitPolicy]:
    """Two arms and one diagnostic policy. Only the exit differs; the stop is computed for all.

    `hold_only` keeps `atr_stop_multiple` so R is `entry - stop` in every arm - a null priced in
    different units cannot be subtracted from anything (`RISK_SPEC` 2).
    """
    return {
        "ratified": ExitPolicy(STOP_MULTIPLE, HOLD, target_r_multiple=TARGET_R),
        "hold_only": ExitPolicy(STOP_MULTIPLE, HOLD, protective=False),
        "ratified_no_target": ExitPolicy(STOP_MULTIPLE, HOLD),
    }


def mae_profile(trades: list[Trade]) -> dict[str, Any]:
    """The left tail, which is what an exit policy is for.

    Counted as SHARES below each band rather than as a mean, because the mean of an excursion
    distribution is dominated by the many trades that never went far and says nothing about the few
    that decide whether an account survives.
    """
    if not trades:
        return {}
    values = sorted(float(t.mae) for t in trades)
    total = len(values)
    out: dict[str, Any] = {
        "worst_mae": round(values[0], 4),
        "p01_mae": round(values[int(0.01 * (total - 1))], 4),
        "p05_mae": round(values[int(0.05 * (total - 1))], 4),
        "median_mae": round(values[total // 2], 4),
    }
    for band in MAE_BANDS:
        out[f"share_below_{band}R"] = round(
            sum(1 for v in values if v < float(band)) / total, 5
        )
    return out


def underpowered(cell: dict[str, Any]) -> bool:
    interval = cell.get("difference_mean")
    if not interval:
        return True
    return bool((interval["high"] - interval["low"]) > float(POWER_FLOOR))


def qualifies(cell: dict[str, Any]) -> bool:
    return bool(cell.get("trades", 0) >= MIN_TRADES and cell.get("months", 0) >= MIN_MONTHS)


def verdict_for(cells: dict[str, dict[str, Any]]) -> str:
    """§6. Reads `ratified` minus `hold_only`, and carries `PREREG_TEMPLATE` rule 10's NULL branch -
    the first study to do so.
    """
    windows = ("in_sample", "out_of_sample")
    if not all(qualifies(cells.get(w, {})) for w in windows):
        return "inconclusive"
    if any(underpowered(cells[w]) for w in windows):
        return "inconclusive"
    if all(cells[w]["difference_mean"]["low"] > 0 for w in windows):
        return "accept"
    if all(cells[w]["difference_mean"]["high"] < 0 for w in windows):
        return "reject"
    if all(cells[w]["difference_mean"]["low"] <= 0 <= cells[w]["difference_mean"]["high"]
           for w in windows):
        return "null"
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
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to fix the calendar")

    benchmark = series_by_name[BENCHMARK]
    calendar = [bar.session_date for bar in benchmark.bars]
    start = date.fromisoformat(args.start) if args.start else WINDOW_START
    end = date.fromisoformat(args.end) if args.end else calendar[-1]
    sessions = window_sessions(calendar, start, end)
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    formations = ([d for d in sessions[::STEP] if earliest <= d <= sessions[-HOLD - 1]]
                  if len(sessions) > HOLD else [])
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    print(f"as_of {as_of.isoformat()}   instruments {len(series_by_name)}   "
          f"formation dates {len(formations)}")

    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}

    # The SELECTED entries: the live ranker, through `select`, exactly as PR-016's `ranked` arm.
    selected: dict[str, set[date]] = {}
    everything: dict[str, set[date]] = {}
    thin = 0
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            thin += 1
            continue
        for candidate in pool:
            everything.setdefault(candidate.instrument_id, set()).add(session)
        ranker = ByMarketPathStrength(series=series_by_name, benchmark=benchmark, lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top:
            selected.setdefault(name, set()).add(session)

    every = policies()
    costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    #: `series -> (policy, entries, costs)`. Naming the entry set per series is what keeps the
    #: unselected diagnostics from silently running on the selected pool.
    plan: dict[str, tuple[str, dict[str, set[date]], CostModel]] = {
        "ratified": ("ratified", selected, costs),
        "hold_only": ("hold_only", selected, costs),
        "ratified_no_target": ("ratified_no_target", selected, costs),
        "unselected_ratified": ("ratified", everything, costs),
        "unselected_hold_only": ("hold_only", everything, costs),
        "ratified_3x": ("ratified", selected,
                        CostModel(COMMISSION_PER_SHARE * STRESS_MULTIPLE,
                                  SLIPPAGE_BPS * STRESS_MULTIPLE)),
        "hold_only_3x": ("hold_only", selected,
                         CostModel(COMMISSION_PER_SHARE * STRESS_MULTIPLE,
                                   SLIPPAGE_BPS * STRESS_MULTIPLE)),
        "ratified_cheap": ("ratified", selected, CostModel(COMMISSION_PER_SHARE, CHEAP_BPS)),
        "hold_only_cheap": ("hold_only", selected, CostModel(COMMISSION_PER_SHARE, CHEAP_BPS)),
    }

    registry = atr_registry()
    trades: dict[str, list[Trade]] = {name: [] for name in plan}
    ambiguous: Counter[str] = Counter()
    for count, (name, series) in enumerate(sorted(series_by_name.items()), start=1):
        if name not in everything:
            continue
        atr_series = atr_component.compute(series, registry)
        gate: list[bool | None] = [True] * len(series.bars)
        for label, (policy, entry_set, cost_model) in plan.items():
            dates = entry_set.get(name)
            if not dates:
                continue
            config = BacktestConfig(arm=label, exits=every[policy], costs=cost_model,
                                    trigger=OnDates(frozenset(dates)),
                                    risk_per_trade=RISK_PER_TRADE)
            armed = run_arm(series, gate, atr_series, config)
            trades[label].extend(armed.trades)
            ambiguous[label] += armed.ambiguous_exits
        if count % 500 == 0:
            print(f"  simulated {count}/{len(series_by_name)} instruments")

    day_after = PRIMARY_END + timedelta(days=1)
    windows = {"full": (start, end), "in_sample": (start, min(PRIMARY_END, end)),
               "out_of_sample": (max(day_after, start), end)}

    result: dict[str, Any] = {
        "prereg": "PR-018", "trials": 2, "as_of": as_of.isoformat(), "country": "USA",
        "preliminary": PRELIMINARY,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "sessions": len(sessions)},
        "exit": {"atr_period": ATR_PERIOD, "atr_stop_multiple": str(STOP_MULTIPLE),
                 "target_r_multiple": str(TARGET_R), "max_holding_period": HOLD,
                 "null_arm": "protective=False - the stop is computed for R and never acted on"},
        "split": {"in_sample": f"entries on or before {PRIMARY_END}",
                  "out_of_sample": f"entries after {PRIMARY_END}",
                  "buys": ("a second window at the boundary PR-014, PR-016 and PR-017 already "
                           "registered, so the cut was not chosen after seeing these data")},
        "perturbations": {
            "registered": ["cost_stress_1x", "cost_stress_3x", "cheap_execution_5.75bps"],
            "run": ["cost_stress_1x", "cost_stress_3x", "cheap_execution_5.75bps"],
            "note": ("each arm differenced against its OWN cost level. The cheap-execution pair "
                     "re-prices an entry struck at the OPEN and is NOT a claim the strategy can "
                     "be executed at 11:00 - DR-040 §4 records that a later entry changes the "
                     "gross too. It says which arm the cost level favours."),
        },
        "stress_multiple": STRESS_MULTIPLE, "cheap_bps_per_side": str(CHEAP_BPS),
        "power_floor": str(POWER_FLOOR),
        "minimum_detectable_effect": str(MINIMUM_DETECTABLE_EFFECT),
        "bootstrap": {"unit": "entry month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                      "resamples": BOOTSTRAP_RESAMPLES},
        "instruments": len(series_by_name), "formation_dates": len(formations),
        "formations_skipped_for_a_thin_cross_section": thin,
        "ambiguous_exits": dict(ambiguous),
        "survivorship": ("ABSENT and material - 2,598 of 2,598 decade-long instruments in this "
                         "store are still trading"),
        "not_measured": [
            "execution time. Both arms enter at the next session's open, which EVIDENCE_SUMMARY "
            "§10 measures as the most expensive minute of the session",
            "the book: one trade at a time, no cap and no capacity",
            "what a person would do watching a position run to -20R, which is the whole of what "
            "the hold_only arm assumes away",
        ],
        "arms": {}, "diagnostics": {}, "mae": {},
    }

    entered = sorted(t.entry_date for t in trades[INCUMBENT])
    if entered:
        span = (entered[-1] - entered[0]).days
        result["measured_span"] = {
            "first_entry": entered[0].isoformat(), "last_entry": entered[-1].isoformat(),
            "years": round(span / 365.25, 2),
            "meets_the_ten_year_instruction": span / 365.25 >= 10.0,
        }

    for label in plan:
        against = NULL_ARM
        for suffix in ("_3x", "_cheap"):
            if label.endswith(suffix):
                against = f"{NULL_ARM}{suffix}"
        if label.startswith("unselected_"):
            against = "unselected_hold_only"
        cells: dict[str, Any] = {}
        for window, (first, last) in windows.items():
            chosen = [t for t in trades[label] if first <= t.entry_date <= last]
            control = [t for t in trades[against] if first <= t.entry_date <= last]
            cells[window] = cell_for(chosen, control if label != against else chosen)
        target = result["arms"] if label in ARMS else result["diagnostics"]
        target[label] = cells
        result["mae"][label] = mae_profile(trades[label])

    result["verdict"] = verdict_for(result["arms"][INCUMBENT])
    return result


def report(result: dict[str, Any]) -> None:
    preliminary = result.get("preliminary")
    if preliminary:
        print(f"*** {preliminary['status']} ***")
        print(f"    {preliminary['why']}\n")
    print(f"PR-018   as_of {result['as_of']}   verdict {result['verdict'].upper()}")
    span = result.get("measured_span")
    if span:
        print(f"  entries {span['first_entry']} .. {span['last_entry']} = {span['years']} years")
    print(f"  {result['instruments']} instruments, {result['formation_dates']} formation dates\n")

    print(f"  {'series':24} {'window':14} {'n':>7} {'win%':>6} {'meanR':>9} {'p95':>7}")
    for group in ("arms", "diagnostics"):
        for label, cells in result[group].items():
            for window in ("in_sample", "out_of_sample"):
                cell = cells.get(window, {})
                if not cell.get("trades"):
                    continue
                pct = cell.get("percentiles", {})
                p95 = f"{pct['p95']:>+7.3f}" if "p95" in pct else f"{'-':>7}"
                print(f"  {label:24} {window:14} {cell['trades']:>7} "
                      f"{cell['win_rate'] * 100:>6.2f} {cell['mean_net_r']:>+9.4f} {p95}")
        print()

    print("  section 6, and the MAE sits in the same paragraph by design:")
    for window in ("in_sample", "out_of_sample"):
        diff = result["arms"][INCUMBENT].get(window, {}).get("difference_mean")
        if not diff:
            continue
        flag = "*" if diff["low"] > 0 or diff["high"] < 0 else " "
        wide = "  UNDERPOWERED" if (diff["high"] - diff["low"]) > float(POWER_FLOOR) else ""
        print(f"    {window:14} ratified - hold_only  {diff['observed']:>+8.4f} "
              f"[{diff['low']:>+8.4f}, {diff['high']:>+8.4f}] {flag}{wide}")

    print(f"\n  {'series':24} {'worst':>9} {'p01':>8} {'p05':>8} " +
          " ".join(f"{'<' + str(b) + 'R':>9}" for b in MAE_BANDS))
    for label in (INCUMBENT, NULL_ARM, "ratified_no_target"):
        profile = result["mae"].get(label)
        if not profile:
            continue
        bands = " ".join(f"{profile[f'share_below_{b}R'] * 100:>8.3f}%" for b in MAE_BANDS)
        print(f"  {label:24} {profile['worst_mae']:>+9.2f} {profile['p01_mae']:>+8.3f} "
              f"{profile['p05_mae']:>+8.3f} {bands}")
    print("\n  MAE is what the exit policy is FOR. A policy that costs return and removes no tail "
          "is a different\n  object from one that costs return and removes one.")


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
