"""`PR-020` - does the ratified screen know anything once the exit's cost is out of the way?

`measure_universe_null` (2026-09-13, exploratory) decomposed `PR-019b`'s loss to `SPY`: the 4 ATR /
60-session exit on every admitted name loses to simply HOLDING the same equal-weighted universe over
the same days, and the screen claws back about 0.06R inside it. The exit is the largest cost. This
study removes it: the selected decile HELD with no stop for `READ_HOLD` sessions, on `PR-019`'s own
common entry set, against its own admitted universe over exactly the same sessions, in the trade's
own R. `trade - pool` is what the screen knows.

**The hold is the power estimate's, not a preference.** `tools/power_pr020.py` sized every no-stop
hold by dispersion alone and the registration took the one the 0.15R floor can read.

**The pool pays the trade's slippage.** At 5 sessions the round trip is about a tenth of an R, so a
free pool would measure the trade's costs and call it the screen. The free pool is a perturbation.

**The null has a built-in check.** Every admitted name held the same way is, nearly, the pool: its
difference to the costed pool should sit close to zero - commission and weighting apart. The runner
prints it before the verdict; one further than 0.05R from zero fails §9, and the verdict is not read.

**§9 reproduces `PR-019` before anything is read.** `PR-019` restricted every cell to the entries
every cell realised, and the binding cells were the 4 ATR ones - every other cell lost exactly the 5
entries they refused. So the candidate is simulated beside `PARTNER`, the intersection is taken, and
`PARTNER` - plus the candidate, when `PR-019`'s grid holds it - must match the committed cells to
every digit.

`SPY` is carried as a diagnostic - the question `PR-019b` asked - and never read by §6.

    PYTHONPATH=$PWD/src python tools/run_pr020.py --data <store>
    python tools/run_pr020.py --report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_universe_null import contribute, daily_pool, pool_r, segments
from power_pr019 import MAX_HOLD, cells, spaced
from power_pr019b import market_r
from power_pr020 import policy_for
from run_pr014 import BENCHMARK, DECILE
from run_pr016 import (
    COMMISSION_PER_SHARE,
    HOLD,
    LOOKBACK,
    PRIMARY_END,
    RISK_PER_TRADE,
    SLIPPAGE_BPS,
    STEP,
    STRESS_MULTIPLE,
    WINDOW_START,
    OnDates,
    atr_registry,
    block_bootstrap,
    by_month,
    distribution,
    window_sessions,
)
from run_pr019 import common_entries, mae_profile
from run_pr019b import BLOCK, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, interval, verdict_for
from stream_selection import score_instrument, select_streamed
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import Trade
from swingdesk.decision_logic.ranking import daily_returns
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: The registered hold - `PR-020-power.json`'s most precise no-stop hold, and the only one of five
#: the 0.15R floor can read: 0.0704 predicted against 0.075, with no overlap to correct at 5.
READ_HOLD = 5
CELL = f"h{READ_HOLD}_stopnone"
CANDIDATE: ExitPolicy = policy_for(CELL)

#: The cell that BINDS `PR-019`'s common entry set: it dropped nothing, every other cell dropped the
#: same 5 it refused. Simulated beside the candidate only for that intersection and for §9.
PARTNER = "h60_stop4.0"

#: The overlap-aware predicted OOS half-width of `trade - pool` at `READ_HOLD`, from
#: `PR-020-power.json` (in sample, 25% subsample, variance-components corrected). A LOWER bound.
MINIMUM_DETECTABLE_EFFECT = Decimal("0.0704")

RESULT = REPO / "docs" / "prereg" / "results" / "PR-020.json"
REFERENCE = REPO / "docs" / "prereg" / "results" / "PR-019.json"
AS_OF = "2026-09-06T22:36:49.635786-05:00"

PERTURBATIONS: dict[str, Any] = {
    "registered": ["pool_zero_cost", "cost_stress_3x"],
    "run": ["pool_zero_cost", "cost_stress_3x"],
    "note": ("the PRIMARY pool pays DR-005's slippage on both fills, as the trade does (a basket "
             "has no single price to charge commission per share on - stated). pool_zero_cost "
             "frees the pool and keeps the trade; cost_stress_3x charges the TRADE three times "
             "DR-005 and keeps the pool at the primary's 1x"),
}

#: §4's split and what it buys - gate 25 reads `split.buys`, and PREREG_TEMPLATE rule 7 is why.
SPLIT: dict[str, str] = {
    "in_sample": f"entries on or before {PRIMARY_END}, printed and never read",
    "out_of_sample": f"entries after {PRIMARY_END}, the verdict",
    "buys": ("the entries are PR-019's, whose cell was selected in its in-sample window, so reading "
             "only out of sample keeps that selection off the verdict; the boundary is "
             "PR-014..PR-019b's, not chosen after seeing these data"),
}

#: One row per trade both nulls can price: (entry date, trade R, pool R, pool R slipped, SPY R).
Row = tuple[date, float, float, float, float]


def pool_slipped(leg: float, trade: Trade) -> float:
    """The pool leg bought at `open x (1 + s)` and sold at `close x (1 - s)`, in the trade's R."""
    side = float(SLIPPAGE_BPS) / 10_000
    scale = float(trade.entry_price / trade.initial_risk_per_share)
    level = 1.0 + leg / scale
    return ((level * (1 - side)) / (1 + side) - 1.0) * scale


def rows_for(trades: list[Trade], spy: tuple[dict[date, Decimal], dict[date, Decimal]],
             pool: tuple[dict[date, float], dict[date, float]], calendar: list[date],
             calendar_index: dict[date, int]) -> tuple[list[Row], int]:
    rows: list[Row] = []
    unpriced = 0
    for trade in trades:
        pool_leg = pool_r(trade, *pool, calendar, calendar_index)
        spy_leg = market_r(trade, *spy)
        if pool_leg is None or spy_leg is None:
            unpriced += 1
            continue
        rows.append((trade.entry_date, float(trade.net_r), pool_leg,
                     pool_slipped(pool_leg, trade), spy_leg))
    return rows, unpriced


def own(trades: list[Trade]) -> dict[str, Any]:
    """A book's own distribution and mean interval, as `PR-019` computed its cells."""
    out = distribution(trades)
    if not trades:
        return out
    months = by_month(trades)
    out["months"] = len(months)
    got = block_bootstrap([months[m] for m in sorted(months)], "mean", BLOCK, BOOTSTRAP_SEED,
                          BOOTSTRAP_RESAMPLES)
    if got:
        out["mean_interval"] = {"low": round(got[1], 4), "high": round(got[2], 4)}
    return out


def cell(trades: list[Trade], rows: list[Row], stressed: list[Row] | None = None) -> dict[str, Any]:
    """`run_pr019b.verdict_for`'s keys, with the POOL as the null: `difference` is trade minus the
    pool CHARGED THE SAME SLIPPAGE, `market_mean` that pool leg, `mean_interval` the trade's own - so
    the tested branches read this study unchanged. `SPY` rides along under its own name.

    **The costed pool is the primary, and that was decided before the run.** At 5 sessions the round
    trip is about a tenth of an R, so trade minus a FREE pool would measure mostly the trade's own
    costs and read REJECT whatever the screen knew. The free pool is the perturbation.
    """
    out = own(trades)
    if not trades:
        return out
    out["mae"] = mae_profile(trades)
    out["paired_trades"] = len(rows)
    out["market_mean"] = interval([(r[0], r[3]) for r in rows])
    out["difference"] = interval([(r[0], r[1] - r[3]) for r in rows])
    out["difference_pool_zero_cost"] = interval([(r[0], r[1] - r[2]) for r in rows])
    out["difference_spy_diagnostic"] = interval([(r[0], r[1] - r[4]) for r in rows])
    if stressed is not None:
        out["difference_stress_3x"] = interval([(r[0], r[1] - r[3]) for r in stressed])
    return out


def windowed(rows: list[Any], first: date, last: date) -> list[Any]:
    return [r for r in rows if first <= (r[0] if isinstance(r, tuple) else r.entry_date) <= last]


def reproduction(result: dict[str, Any], reference: Path) -> dict[str, Any]:
    """§9: `PARTNER`, and the candidate when `PR-019`'s grid holds it, against the committed cells."""
    if not reference.exists():
        return {"reference": str(reference), "available": False}
    committed = json.loads(reference.read_text(encoding="utf-8"))
    fields = ("trades", "mean_net_r", "mean_interval")
    checks, every = [], True
    for window in ("in_sample", "out_of_sample"):
        ours = {PARTNER: result["partner"][window], CELL: result["cells"][window].get(CELL) or {}}
        for label, got in ours.items():
            want = committed["cells"][window].get(label)
            if want is None:
                continue  # PR-019 never ran this cell; nothing to reproduce
            match = all(got.get(f) == want.get(f) for f in fields)
            every &= match
            checks.append({"window": window, "cell": label, "match": match,
                           "got": {f: got.get(f) for f in fields},
                           "committed": {f: want.get(f) for f in fields}})
    return {"reference": reference.name, "available": True, "every_digit": every,
            "checks": checks}


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of)
    benchmark = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    min_bars = 252 + HOLD + 1
    if benchmark is None or len(benchmark.bars) < min_bars:
        store.close()
        raise SystemExit(f"{BENCHMARK} has too little history to fix the calendar")
    calendar = [bar.session_date for bar in benchmark.bars]
    calendar_index = {session: i for i, session in enumerate(calendar)}
    spy = ({b.session_date: b.open for b in benchmark.bars},
           {b.session_date: b.close for b in benchmark.bars})
    start, end = WINDOW_START, calendar[-1]
    sessions = window_sessions(calendar, start, end)
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    formations = ([d for d in sessions[::STEP] if earliest <= d <= sessions[-HOLD - 1]]
                  if len(sessions) > HOLD else [])

    def load(name: str) -> BarSeries | None:
        if name == BENCHMARK:
            return benchmark
        return store.as_of(name, Interval.DAY, Series.RAW, as_of)

    # --- pass A: scores one series at a time, then the selection - loader phase A ----------------
    benchmark_daily = daily_returns(benchmark)
    scores: dict[str, dict[date, Decimal]] = {}
    instruments = 0
    for name in sorted(store.instrument_ids(as_of)):
        series = load(name)
        if series is None or len(series.bars) < min_bars:
            continue
        instruments += 1
        got = score_instrument(series, formations, benchmark_daily, LOOKBACK)
        if got:
            scores[name] = got
    chosen = select_streamed(scores, formations, DECILE)
    selected, everything = chosen.selected, chosen.everything
    live = sorted({d for dates in everything.values() for d in dates})
    days_of = segments(live, calendar)
    print(f"as_of {as_of.isoformat()}   instruments {instruments}   formation dates "
          f"{len(formations)}   candidate {CELL}", flush=True)

    base = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    stress = CostModel(COMMISSION_PER_SHARE * STRESS_MULTIPLE, SLIPPAGE_BPS * STRESS_MULTIPLE)
    registry = atr_registry()
    policies = {CELL: CANDIDATE, PARTNER: cells()[PARTNER]}

    def simulate(series: BarSeries, atr: Any, policy: ExitPolicy, dates: list[date],
                 costs: CostModel, label: str) -> list[Trade]:
        config = BacktestConfig(arm=label, exits=policy, costs=costs,
                                trigger=OnDates(frozenset(dates)), risk_per_trade=RISK_PER_TRADE)
        return run_arm(series, [True] * len(series.bars), atr, config).trades

    # --- phase 1: the candidate, its intersection partner, and the candidate at 3x ---------------
    books: dict[str, list[Trade]] = {CELL: [], PARTNER: [], f"{CELL}_3x": []}
    for name in sorted(selected):
        series = load(name)
        if series is None:
            continue
        atr = atr_component.compute(series, registry)
        dates = spaced(selected[name], calendar_index, MAX_HOLD)
        for label, policy in policies.items():
            books[label].extend(simulate(series, atr, policy, dates, base, label))
        books[f"{CELL}_3x"].extend(simulate(series, atr, CANDIDATE, dates, stress, f"{CELL}_3x"))
    before = {label: len(book) for label, book in books.items()}
    books, dropped = common_entries(books)

    # --- phase 2: every admitted name - the null's own check, and the pool's sums ----------------
    unselected: list[Trade] = []
    sums: dict[date, list[float]] = defaultdict(lambda: [0.0, 0, 0.0, 0])
    for count, name in enumerate(sorted(everything), start=1):
        series = load(name)
        if series is None:
            continue
        atr = atr_component.compute(series, registry)
        unselected.extend(simulate(series, atr, CANDIDATE,
                                   spaced(everything[name], calendar_index, MAX_HOLD), base,
                                   f"unselected_{CELL}"))
        contribute(sums, series, (day for f in everything[name] for day in days_of.get(f, ())))
        if count % 1000 == 0:
            print(f"  phase 2: {count}/{len(everything)} admitted names", flush=True)
    store.close()
    pool = daily_pool(sums)

    rows, unpriced = rows_for(books[CELL], spy, pool, calendar, calendar_index)
    stressed, unpriced_3x = rows_for(books[f"{CELL}_3x"], spy, pool, calendar, calendar_index)
    rows_all, unpriced_all = rows_for(unselected, spy, pool, calendar, calendar_index)

    day_after = PRIMARY_END + timedelta(days=1)
    windows = {"in_sample": (start, min(PRIMARY_END, end)),
               "out_of_sample": (max(day_after, start), end)}
    result: dict[str, Any] = {
        "prereg": "PR-020", "trials": 1, "as_of": as_of.isoformat(), "country": "USA",
        "candidate": {"cell": CELL, "max_holding_period": CANDIDATE.max_holding_bars,
                      "protective_stop": False, "entries": "PR-019's common entry set"},
        "null": {"primary": "the equal-weighted admitted universe over the trade's own sessions, "
                            "charged DR-005's slippage on both fills",
                 "diagnostic": "SPY over the same sessions, never read"},
        "perturbations": PERTURBATIONS,
        "split": SPLIT,
        "minimum_detectable_effect": str(MINIMUM_DETECTABLE_EFFECT),
        "instruments": instruments, "formation_dates": len(formations),
        "formations_skipped_for_a_thin_cross_section": chosen.thin,
        "entries": {"realised_before_restriction": before, "dropped_to_common_entries": dropped},
        "unpriced": {CELL: unpriced, f"{CELL}_3x": unpriced_3x,
                     f"unselected_{CELL}": unpriced_all},
        "cells": {w: {CELL: cell(windowed(books[CELL], *span), windowed(rows, *span),
                                 windowed(stressed, *span))} for w, span in windows.items()},
        "partner": {w: own(windowed(books[PARTNER], *span)) for w, span in windows.items()},
        "null_check": {w: {f"unselected_{CELL}": cell(windowed(unselected, *span),
                                                      windowed(rows_all, *span))}
                       for w, span in windows.items()},
        "not_measured": [
            "the tail as a budget: C-8 is unruled, so the tail is printed beside the mean and no "
            "branch reads it",
            "commission on the pool leg: a basket has no single price to charge per share on",
            "the book: one trade at a time, no cap and no capacity",
        ],
    }
    entered = sorted(t.entry_date for t in books[CELL])
    if entered:
        span_days = (entered[-1] - entered[0]).days
        result["measured_span"] = {"first_entry": entered[0].isoformat(),
                                   "last_entry": entered[-1].isoformat(),
                                   "years": round(span_days / 365.25, 2)}
    result["reproduction"] = reproduction(result, args.reference)
    result["verdict"] = verdict_for(result["cells"]["out_of_sample"][CELL])
    return result


def _span(block: dict[str, float] | None) -> str:
    if not block:
        return "-"
    return f"{block['observed']:+.4f} [{block['low']:+.4f}, {block['high']:+.4f}]"


def report(result: dict[str, Any]) -> None:
    print(f"PR-020   as_of {result['as_of']}   verdict {result['verdict'].upper()}")
    repro = result.get("reproduction", {})
    print(f"  section 9 - reproduction of {repro.get('reference')}: every digit "
          f"{repro.get('every_digit')}")
    for check in repro.get("checks", []):
        print(f"    {'ok ' if check['match'] else 'NO '} {check['cell']:14} {check['window']:14} "
              f"got {check['got']}")
    print("\n  the null's own check - every admitted name held the same way, against the pool:")
    for window, group in result["null_check"].items():
        c = group[f"unselected_{CELL}"]
        print(f"    {window:14} {c.get('trades', 0):>6} trades   trade - pool "
              f"{_span(c.get('difference'))}")
    for window, group in result["cells"].items():
        c = group[CELL]
        if not c.get("trades"):
            continue
        tail = c["mae"]
        print(f"\n  {CELL} {window}: {c['trades']} trades, mean {c['mean_net_r']:+.4f}R")
        for key in ("market_mean", "difference", "difference_pool_zero_cost",
                    "difference_stress_3x", "difference_spy_diagnostic"):
            print(f"    {key:28} {_span(c.get(key))}")
        print(f"    tail: {tail['share_below_-2R'] * 100:.2f}% below -2R, "
              f"{tail['share_below_-3R'] * 100:.2f}% below -3R, worst {tail['worst_mae']:+.2f}R")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--as-of", default=AS_OF)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true", help="print an existing result and exit")
    args = parser.parse_args()
    if args.report:
        report(json.loads(args.out.read_text(encoding="utf-8")))
        return 0
    result = build(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n",
                        encoding="utf-8")
    print(f"wrote {args.out}")
    report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
