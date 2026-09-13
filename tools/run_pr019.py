"""`PR-019` - what holding period and stop width does THIS combination want, on selected entries?

**Owed by `STRATEGY_CONTRACT.md` C-7**, and by the owner's point that raised it: *"max hold days
must be researched and per strategy."* `exit.max_holding_period` is 20 trading days, status
`assumed`, provenance `assumed:DR-012`, held as a study condition by every study since `PR-005` and
**varied on selected entries by none of them.**

**Twelve cells, one entry set.** Holds 10, 20, 40, 60 sessions; stops 2.0 ATR, 4.0 ATR, and none. No
cell carries a target: `PR-018` measured that the 1R target costs about 0.05R and buys nothing on the
tail. Every cell trades the SAME entries, spaced at the longest hold (`power_pr019.spaced`), so the
paired difference is paired exactly - the property `PR-018` A-1 found missing and could only report.

**The split buys selection, for once.** §6 picks ONE cell in sample by a rule fixed in advance -
the highest mean net R among cells whose share of trades below -2R does not exceed the ratified
policy's - and reads only that cell out of sample. No threshold is invented: the tail benchmark is
the one the owner already ratified by ratifying the exit.

**R is each cell's OWN risk unit**, `entry - stop`, under the ratified constant-risk sizing
(`RISK_SPEC` 2). A 4 ATR stop therefore trades half the position a 2 ATR stop does, and every figure
is in units of the risk budget, which is what an account experiences. The no-stop cells keep a
2 ATR denominator and bound nothing, exactly as `PR-018`'s `hold_only` did.

**Two phases in one process.** Phase 1 simulates every selected arm, which is small. §6's in-sample
selection is then a pure function of phase 1, and phase 2 simulates the no-selection null (contract
C-3) and the cheap-execution perturbation for the selected cell and the incumbent only - on the
series already in memory. Twelve cells over the whole universe would be hours of simulation for
eleven numbers §6 never reads.

    PYTHONPATH=$PWD/src python tools/run_pr019.py --data <store> --as-of <instant>
    python tools/run_pr019.py --report

`PRELIMINARY` on `DR-042`'s terms, as `PR-016`, `PR-017` and `PR-018` are.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
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
from power_pr019 import (
    GRID,
    HOLDS,
    INCUMBENT,
    MAX_HOLD,
    STOPS,
    cell_name,
    cells,
    incumbent_policy,
    spaced,
)
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

#: `EVIDENCE_SUMMARY` §10's measured 11:00 median. A perturbation, NOT a claim the strategy can be
#: executed there - a later entry changes the gross as well as the cost (`DR-040` §4).
CHEAP_BPS = Decimal("5.75")

POWER_FLOOR = Decimal("0.15")
#: PER CELL, and not a constant: the predicted out-of-sample half-width of each cell's paired
#: difference against the incumbent, from `tools/power_pr019.py --report`. Precision falls with the
#: hold - 0.05R at ten sessions, 0.20R at sixty with a 2 ATR stop - so one number would be wrong
#: for eleven cells of twelve. §3 of the pre-registration carries the table.
MINIMUM_DETECTABLE_EFFECT = "per cell - PR-019-power.json, pre-registration §3"

#: The tail band §6's eligibility reads, and the bands every cell reports.
TAIL_BAND = Decimal("-2")
MAE_BANDS = (Decimal("-1"), Decimal("-2"), Decimal("-3"))

#: `PR-016`'s `ranked` arm and `PR-018`'s `ratified_no_target`, at their own `as_of`. The free-entry
#: diagnostics re-run exactly those constructions, and §9 requires them to match before anything
#: else is read. Values are the committed ones; the report prints both sides.
REPRODUCE: dict[str, dict[str, tuple[int | None, float]]] = {
    "free_ratified": {"in_sample": (11019, -0.0797), "out_of_sample": (16320, -0.1144)},
    f"free_{cell_name(HOLD, '2.0')}": {"in_sample": (None, -0.0261),
                                        "out_of_sample": (None, -0.0650)},
}

#: §5's perturbations, declared in the result because gate 25 reads the declaration and not the
#: prose. The first run of this file wrote no such block and the gate refused it - the block was
#: then added from this constant to the committed result, which changes no measured number.
PERTURBATIONS: dict[str, Any] = {
    "registered": ["cost_stress_3x", "cheap_execution_5.75bps"],
    "run": ["cost_stress_3x", "cheap_execution_5.75bps"],
    "note": ("the 3x stress is run for every cell and differenced against the incumbent at 3x; "
             "cheap execution is run for the selected cell and the incumbent only (phase 2) and "
             "re-prices an entry struck at the OPEN - not a claim it can be executed at 11:00"),
}

RESULT = REPO / "docs" / "prereg" / "results" / "PR-019.json"

PRELIMINARY = {
    "status": "PRELIMINARY - not a final result",
    "why": (
        "DR-042's tie-break is unruled and this study runs under it. Measured 2026-09-08: at most "
        "0.0006R a trade, and it binds only on cells with a protective stop."
    ),
    "settled_by": "docs/decisions/DR-042 §8",
}


def common_entries(
    books: dict[str, list[Trade]],
) -> tuple[dict[str, list[Trade]], dict[str, int]]:
    """Restrict every book to the trades EVERY book realised, and count what each one lost.

    **Spacing makes the entry SCHEDULE identical; it cannot make the engine accept every entry in
    every cell.** The power run found 1,166 trades shared out of 1,169: the engine refuses an entry
    whose stop is not a positive price below it, or whose risk buys zero shares, and a 4 ATR stop
    hits both refusals on names a 2 ATR stop does not. A paired difference over unequal sets is
    not paired, so the study reads the intersection and reports the loss per cell and by reason.
    """
    keys = [{(t.instrument_id, t.entry_date) for t in book} for book in books.values()]
    shared = set.intersection(*keys) if keys else set()
    kept = {label: [t for t in book if (t.instrument_id, t.entry_date) in shared]
            for label, book in books.items()}
    dropped = {label: len(book) - len(kept[label]) for label, book in books.items()}
    return kept, dropped


def mae_profile(trades: list[Trade]) -> dict[str, Any]:
    """The left tail, counted as SHARES below each band. As `PR-018`, per window here."""
    if not trades:
        return {}
    values = sorted(float(t.mae) for t in trades)
    total = len(values)
    out: dict[str, Any] = {
        "worst_mae": round(values[0], 4),
        "p01_mae": round(values[int(0.01 * (total - 1))], 4),
        "p05_mae": round(values[int(0.05 * (total - 1))], 4),
        "below_counts": {},
    }
    for band in MAE_BANDS:
        below = sum(1 for v in values if v < float(band))
        out[f"share_below_{band}R"] = round(below / total, 5)
        out["below_counts"][str(band)] = below
    out["trades"] = total
    return out


def wilson_upper(successes: int, total: int, z: float = 1.96) -> float:
    """The upper end of a Wilson score interval. Used for ONE thing: whether the selected cell's
    out-of-sample tail share is within sampling noise of the incumbent's, so §6 does not have to
    invent a tolerance to answer it.
    """
    if total <= 0:
        return 1.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre + spread) / denominator


def qualifies(cell: dict[str, Any]) -> bool:
    return bool(cell.get("trades", 0) >= MIN_TRADES and cell.get("months", 0) >= MIN_MONTHS)


def underpowered(cell: dict[str, Any]) -> bool:
    interval = cell.get("difference_mean")
    if not interval:
        return True
    return bool((interval["high"] - interval["low"]) > float(POWER_FLOOR))


def tail_share(cell: dict[str, Any]) -> float:
    return float(cell["mae"][f"share_below_{TAIL_BAND}R"])


def select_cell(grid: dict[str, dict[str, Any]], incumbent: dict[str, Any]) -> str | None:
    """§6's IN-SAMPLE selection, and the only place a cell is chosen.

    Eligible: the cell meets the sample rule in sample, and its in-sample share of trades below -2R
    does not exceed the incumbent's. Among the eligible, the highest in-sample mean net R. Ties -
    which a float mean makes academic - break to the shorter hold and then the tighter stop, which is
    `GRID`'s order, so the rule is total and nobody chooses.

    **The out-of-sample window is not an argument to this function**, and that is the point: the
    selection cannot see the data it will be judged on.
    """
    ceiling = tail_share(incumbent)
    eligible = [name for name in GRID
                if qualifies(grid[name]) and tail_share(grid[name]) <= ceiling]
    if not eligible:
        return None
    return max(eligible, key=lambda name: (grid[name]["mean_net_r"], -GRID.index(name)))


def verdict_for(selected: str | None, oos: dict[str, dict[str, Any]]) -> str:
    """§6's verdict, read on the selected cell OUT OF SAMPLE only.

    Seven outcomes, each registered before the run, and two of them exist because this programme
    paid for their absence: `both_negative` is `PREREG_TEMPLATE` rule 8 and `null` is rule 10.
    `tail_breach` is new here and is contract clause C-8 made mechanical: a cell that earns but
    runs a fatter tail than the incumbent out of sample is not a strategy this repository may call
    better, whatever its mean.
    """
    if selected is None:
        return "no_eligible_cell"
    cell, base = oos[selected], oos[INCUMBENT]
    if not qualifies(cell) or underpowered(cell):
        return "inconclusive"
    diff, own = cell["difference_mean"], cell.get("mean_interval")
    below = base["mae"]["below_counts"][str(TAIL_BAND)]
    tail_holds = tail_share(cell) <= wilson_upper(below, base["mae"]["trades"])
    if diff["low"] > 0 and own and own["low"] > 0:
        return "accept" if tail_holds else "tail_breach"
    if diff["high"] < 0:
        return "reject"
    if own and own["high"] < 0:
        return "both_negative"
    if diff["low"] <= 0 <= diff["high"]:
        return "null"
    return "inconclusive"


def windowed(trades: list[Trade], first: date, last: date) -> list[Trade]:
    return [t for t in trades if first <= t.entry_date <= last]


def light(trades: list[Trade]) -> list[tuple[date, float]]:
    """A diagnostic keeps `(entry_date, net_r)` and nothing else - it is read for a level only."""
    return [(t.entry_date, float(t.net_r)) for t in trades]


def level(rows: list[tuple[date, float]], first: date, last: date) -> dict[str, Any]:
    chosen = [r for d, r in rows if first <= d <= last]
    if not chosen:
        return {"trades": 0}
    return {"trades": len(chosen), "mean_net_r": round(statistics.fmean(chosen), 4)}


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
    calendar_index = {session: i for i, session in enumerate(calendar)}
    start = date.fromisoformat(args.start) if args.start else WINDOW_START
    end = date.fromisoformat(args.end) if args.end else calendar[-1]
    sessions = window_sessions(calendar, start, end)
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    # Formation dates stop HOLD sessions before the end, exactly as PR-016 - so the free-entry
    # reproduction sees PR-016's dates. A 60-session cell entering late is closed END_OF_DATA and
    # counted, never dropped; the report states how many.
    formations = ([d for d in sessions[::STEP] if earliest <= d <= sessions[-HOLD - 1]]
                  if len(sessions) > HOLD else [])
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    print(f"as_of {as_of.isoformat()}   instruments {len(series_by_name)}   "
          f"formation dates {len(formations)}", flush=True)

    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}
    selected: dict[str, list[date]] = {}
    everything: dict[str, list[date]] = {}
    thin = 0
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            thin += 1
            continue
        for candidate in pool:
            everything.setdefault(candidate.instrument_id, []).append(session)
        ranker = ByMarketPathStrength(series=series_by_name, benchmark=benchmark, lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top:
            selected.setdefault(name, []).append(session)

    spaced_selected = {n: spaced(d, calendar_index, MAX_HOLD) for n, d in selected.items()}
    policies: dict[str, ExitPolicy] = {**cells(), INCUMBENT: incumbent_policy()}
    base_costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    stress_costs = CostModel(COMMISSION_PER_SHARE * STRESS_MULTIPLE, SLIPPAGE_BPS * STRESS_MULTIPLE)
    cheap_costs = CostModel(COMMISSION_PER_SHARE, CHEAP_BPS)
    registry = atr_registry()
    atr_cache: dict[str, Any] = {}

    skipped: dict[str, Counter[str]] = {label: Counter() for label in policies}

    def simulate(name: str, policy: ExitPolicy, dates: list[date], costs: CostModel,
                 label: str) -> tuple[list[Trade], int]:
        series = series_by_name[name]
        if name not in atr_cache:
            atr_cache[name] = atr_component.compute(series, registry)
        config = BacktestConfig(arm=label, exits=policy, costs=costs,
                                trigger=OnDates(frozenset(dates)), risk_per_trade=RISK_PER_TRADE)
        armed = run_arm(series, [True] * len(series.bars), atr_cache[name], config)
        if label in skipped:
            skipped[label].update({str(k): v for k, v in armed.skipped.items()})
        return armed.trades, armed.ambiguous_exits

    # --- phase 1: every selected arm ----------------------------------------------------------
    trades: dict[str, list[Trade]] = {label: [] for label in policies}
    stressed: dict[str, list[Trade]] = {label: [] for label in policies}
    free: dict[str, list[tuple[date, float]]] = {label: [] for label in policies}
    ambiguous: Counter[str] = Counter()
    for count, name in enumerate(sorted(selected), start=1):
        for label, policy in policies.items():
            got, amb = simulate(name, policy, spaced_selected[name], base_costs, label)
            trades[label].extend(got)
            ambiguous[label] += amb
            got, _ = simulate(name, policy, spaced_selected[name], stress_costs, f"{label}_3x")
            stressed[label].extend(got)
            got, _ = simulate(name, policy, selected[name], base_costs, f"free_{label}")
            free[label].extend(light(got))
        if count % 250 == 0:
            print(f"  phase 1: {count}/{len(selected)} selected instruments", flush=True)
        atr_cache.pop(name, None)

    # One intersection over the base AND the stressed books, so both read the same trades.
    before = {label: len(book) for label, book in trades.items()}
    merged, dropped = common_entries({**trades, **{f"{k}_3x": v for k, v in stressed.items()}})
    trades = {label: merged[label] for label in policies}
    stressed = {label: merged[f"{label}_3x"] for label in policies}
    identical = len(set(before.values())) == 1 and not any(dropped.values())

    day_after = PRIMARY_END + timedelta(days=1)
    windows = {"in_sample": (start, min(PRIMARY_END, end)),
               "out_of_sample": (max(day_after, start), end)}

    def cell(label: str, book: dict[str, list[Trade]], window: str) -> dict[str, Any]:
        first, last = windows[window]
        own = windowed(book[label], first, last)
        base = windowed(book[INCUMBENT], first, last)
        out = cell_for(own, own if label == INCUMBENT else base)
        out["mae"] = mae_profile(own)
        return out

    grid_cells = {window: {label: cell(label, trades, window) for label in policies}
                  for window in windows}
    chosen = select_cell(grid_cells["in_sample"], grid_cells["in_sample"][INCUMBENT])
    print(f"  section 6 selected in sample: {chosen}", flush=True)

    # --- phase 2: the no-selection null and cheap execution, for the chosen cell only -----------
    phase_two = [INCUMBENT] + ([chosen] if chosen else [])
    unselected: dict[str, list[tuple[date, float]]] = {label: [] for label in phase_two}
    cheap: dict[str, list[tuple[date, float]]] = {label: [] for label in phase_two}
    for count, name in enumerate(sorted(everything), start=1):
        dates = spaced(everything[name], calendar_index, MAX_HOLD)
        for label in phase_two:
            got, _ = simulate(name, policies[label], dates, base_costs, f"unselected_{label}")
            unselected[label].extend(light(got))
            if name in spaced_selected:
                got, _ = simulate(name, policies[label], spaced_selected[name], cheap_costs,
                                  f"cheap_{label}")
                cheap[label].extend(light(got))
        atr_cache.pop(name, None)
        if count % 1000 == 0:
            print(f"  phase 2: {count}/{len(everything)} admitted instruments", flush=True)

    result: dict[str, Any] = {
        "prereg": "PR-019", "trials": len(GRID), "as_of": as_of.isoformat(), "country": "USA",
        "preliminary": PRELIMINARY,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "sessions": len(sessions)},
        "grid": {"holds": list(HOLDS), "stops": [label for label, _ in STOPS],
                 "entry_spacing_sessions": MAX_HOLD, "target": None,
                 "r_unit": "each cell's own entry - stop; 2 ATR for cells with no stop"},
        "incumbent": {"atr_stop_multiple": str(STOP_MULTIPLE), "target_r_multiple": str(TARGET_R),
                      "max_holding_period": HOLD, "atr_period": ATR_PERIOD},
        "split": {"in_sample": f"entries on or before {PRIMARY_END}",
                  "out_of_sample": f"entries after {PRIMARY_END}",
                  "buys": "SELECTION: §6 picks one of twelve cells in sample and reads it out"},
        "perturbations": PERTURBATIONS,
        "power_floor": str(POWER_FLOOR),
        "minimum_detectable_effect": str(MINIMUM_DETECTABLE_EFFECT),
        "bootstrap": {"unit": "entry month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                      "resamples": BOOTSTRAP_RESAMPLES},
        "instruments": len(series_by_name), "formation_dates": len(formations),
        "formations_skipped_for_a_thin_cross_section": thin,
        "entries": {"selected_signals": sum(len(v) for v in selected.values()),
                    "after_spacing": sum(len(v) for v in spaced_selected.values()),
                    "realised_per_cell_before_restriction": before,
                    "dropped_to_common_entries": dropped,
                    "engine_refusals_by_cell": {k: dict(v) for k, v in skipped.items()},
                    "every_cell_realised_the_same_entries": identical},
        "ambiguous_exits": dict(ambiguous),
        "survivorship": "ABSENT and material, as PR-016..PR-018",
        "selected_in_sample": chosen,
        "cells": grid_cells,
        "stress_3x": {window: {label: cell(label, stressed, window) for label in phase_two}
                      for window in windows},
        "free_entry": {window: {f"free_{label}": level(free[label], *windows[window])
                                for label in policies} for window in windows},
        "unselected": {window: {label: level(unselected[label], *windows[window])
                                for label in phase_two} for window in windows},
        "cheap_execution": {window: {label: level(cheap[label], *windows[window])
                                     for label in phase_two} for window in windows},
        "not_measured": [
            "trades per year: the entry schedule is fixed at the LONGEST hold for every cell, so "
            "this ranks cells per TRADE only. free_entry reports each cell's own count and level",
            "execution time: every arm enters at the next session's open",
            "the book: one trade at a time, no cap and no capacity",
        ],
    }
    entered = sorted(t.entry_date for t in trades[INCUMBENT])
    if entered:
        span = (entered[-1] - entered[0]).days
        result["measured_span"] = {
            "first_entry": entered[0].isoformat(), "last_entry": entered[-1].isoformat(),
            "years": round(span / 365.25, 2),
            "meets_the_ten_year_instruction": span / 365.25 >= 10.0,
        }
    result["verdict"] = verdict_for(chosen, grid_cells["out_of_sample"])
    return result


def report(result: dict[str, Any]) -> None:
    preliminary = result.get("preliminary")
    if preliminary:
        print(f"*** {preliminary['status']} ***\n    {preliminary['why']}\n")
    print(f"PR-019   as_of {result['as_of']}   verdict {result['verdict'].upper()}")
    print(f"  selected in sample: {result['selected_in_sample']}")
    entries = result["entries"]
    print(f"  {entries['selected_signals']} signals -> {entries['after_spacing']} entries, "
          f"identical in every cell: {entries['every_cell_realised_the_same_entries']}")
    lost = {k: v for k, v in entries.get("dropped_to_common_entries", {}).items() if v}
    print(f"  dropped to the common entry set: {lost or 'none'}\n")

    print("  section 9 first - the free-entry reproductions:")
    for label, expected in REPRODUCE.items():
        for window, (n, mean) in expected.items():
            got = result["free_entry"][window].get(label, {})
            print(f"    {label:24} {window:14} got n={got.get('trades')} "
                  f"mean={got.get('mean_net_r')}   committed n={n} mean={mean}")

    print(f"\n  {'cell':16} {'window':14} {'n':>6} {'meanR':>8} {'diff vs ratified':>28} "
          f"{'<-2R':>7} {'<-3R':>7} {'worst':>8}")
    for label in (*GRID, INCUMBENT):
        for window in ("in_sample", "out_of_sample"):
            c = result["cells"][window][label]
            if not c.get("trades"):
                continue
            d = c.get("difference_mean")
            diff = (f"{d['observed']:+.4f} [{d['low']:+.4f},{d['high']:+.4f}]" if d else "-")
            m = c["mae"]
            print(f"  {label:16} {window:14} {c['trades']:>6} {c['mean_net_r']:>+8.4f} "
                  f"{diff:>28} {m['share_below_-2R'] * 100:>6.2f}% "
                  f"{m['share_below_-3R'] * 100:>6.2f}% {m['worst_mae']:>+8.2f}")

    for group in ("unselected", "cheap_execution", "free_entry"):
        print(f"\n  {group}:")
        for window, rows in result[group].items():
            for label, row in rows.items():
                if row.get("trades"):
                    print(f"    {label:24} {window:14} n={row['trades']:>7} "
                          f"mean={row['mean_net_r']:+.4f}")


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
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n",
                        encoding="utf-8")
    print(f"\nwrote {args.out}")
    report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
