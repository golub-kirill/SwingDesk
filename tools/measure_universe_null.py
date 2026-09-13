"""Is it the universe or the selection? A third null for `PR-019b`'s candidate: its own admitted pool.

`PR-019b` paired every trade of `PR-019`'s candidate (`h60_stop4.0`) with `SPY` over exactly its
sessions and read **-0.1543R** out of sample; the same exit on every admitted name read -0.2772R.
Both lose to the index. But the admitted universe is an equal-weighted pool that `PR-014`'s control
measured trailing `SPY` by 1.58% a year before any strategy touched it - so the loss has two
possible owners, and they call for different fixes:

* the **UNIVERSE** - a style gap between an equal-weighted pool and a cap-weighted index, which no
  selection or exit inside the pool can close;
* the **SELECTION and EXIT** - a skill gap, which a different universe would not close.

The null that belongs to the universe separates them: each trade paired with the equal-weighted
admitted pool over exactly its own sessions, in its own R. `trade - pool` is what the screen and the
exit add INSIDE the universe; `pool - SPY` over the same days is what the universe costs.

**The pool on a session** is the one formed at the latest formation strictly BEFORE it - known at
that formation's close, as the screen's own candidates are - and it is every name admitted there:
the membership `measure_benchmark_fit` and `PR-014`'s control equal-weight, and exactly the names
`PR-019b`'s no-selection book trades. Rebalanced daily, equal weights, bought at the entry session's
open and marked at the exit session's close - the `SPY` leg's own form, so the two nulls compare.

**EXPLORATORY.** No verdict, no parameter, no new trial: the configurations are `PR-019b`'s and
`PR-019`'s, already counted, and only the null differs. The trade books are rebuilt through the
streamed loader and must reproduce `PR-019b.json` to the digit before anything new is read.

    PYTHONPATH=$PWD/src python tools/measure_universe_null.py --data <store>
    python tools/measure_universe_null.py --report
"""

from __future__ import annotations

import argparse
import bisect
import json
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from power_pr019 import MAX_HOLD, spaced
from power_pr019b import CANDIDATE, market_r
from run_pr014 import BENCHMARK, DECILE
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
from run_pr019b import CELL, interval
from stream_selection import score_instrument, select_streamed
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import Trade
from swingdesk.decision_logic.ranking import daily_returns
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: `PR-019b`'s own instant, so the books it rebuilds are the books it reported.
AS_OF = "2026-09-06T22:36:49.635786-05:00"
RESULT = REPO / "docs" / "decisions" / "measurements" / "universe-null-2026-09-13.json"
REFERENCE = REPO / "docs" / "prereg" / "results" / "PR-019b.json"


def pool_formation(day: date, live: list[date]) -> date | None:
    """The formation whose pool holds `day`: the latest one strictly before it, or None."""
    at = bisect.bisect_left(live, day)
    return live[at - 1] if at > 0 else None


def segments(live: list[date], calendar: list[date]) -> dict[date, list[date]]:
    """Each live formation's sessions: after it, up to and including the next one."""
    out: dict[date, list[date]] = {f: [] for f in live}
    for day in calendar:
        f = pool_formation(day, live)
        if f is not None:
            out[f].append(day)
    return out


def contribute(sums: dict[date, list[float]], series: BarSeries, days: Iterable[date]) -> None:
    """Add one member's close-to-close and open-to-close returns on `days` to the pool's sums.

    `sums[day]` is `[close-to-close total, count, open-to-close total, count]`. A day the member has
    no bar for, or no previous bar, adds nothing - it was not tradeable that day. A member whose
    previous bar is older than the previous session (a halt) contributes the return since that bar;
    stated rather than modelled, and rare in a pool screened for dollar volume.
    """
    position = {bar.session_date: i for i, bar in enumerate(series.bars)}
    bars = series.bars
    for day in days:
        i = position.get(day)
        if i is None or i == 0:
            continue
        previous, bar = bars[i - 1], bars[i]
        cell = sums[day]
        if previous.close > 0:
            cell[0] += float(bar.close / previous.close - 1)
            cell[1] += 1
        if bar.open > 0:
            cell[2] += float(bar.close / bar.open - 1)
            cell[3] += 1


def daily_pool(sums: dict[date, list[float]]) -> tuple[dict[date, float], dict[date, float]]:
    """The equal-weighted pool's close-to-close and open-to-close return, per session."""
    close_to_close = {d: c[0] / c[1] for d, c in sums.items() if c[1]}
    open_to_close = {d: c[2] / c[3] for d, c in sums.items() if c[3]}
    return close_to_close, open_to_close


def pool_r(trade: Trade, close_to_close: dict[date, float], open_to_close: dict[date, float],
           calendar: list[date], calendar_index: dict[date, int]) -> float | None:
    """The pool over the trade's own sessions, in the trade's own R - the `SPY` leg's form.

    Bought at the entry session's OPEN, so that session contributes its open-to-close return;
    every later session through the exit contributes close-to-close. None when any session lacks a
    pool return, and the caller counts it.
    """
    first, last = calendar_index.get(trade.entry_date), calendar_index.get(trade.exit_date)
    opening = open_to_close.get(trade.entry_date)
    if first is None or last is None or opening is None or trade.initial_risk_per_share <= 0:
        return None
    level = 1.0 + opening
    for i in range(first + 1, last + 1):
        step = close_to_close.get(calendar[i])
        if step is None:
            return None
        level *= 1.0 + step
    return (level - 1.0) * float(trade.entry_price / trade.initial_risk_per_share)


def legs(trades: list[Trade], spy: tuple[dict[date, Decimal], dict[date, Decimal]],
         pool: tuple[dict[date, float], dict[date, float]], calendar: list[date],
         calendar_index: dict[date, int]) -> tuple[list[tuple[date, float, float, float]], int]:
    """`(entry date, trade R, SPY R, pool R)` for every trade both nulls can price."""
    rows: list[tuple[date, float, float, float]] = []
    unpriced = 0
    for trade in trades:
        index_leg = market_r(trade, *spy)
        pool_leg = pool_r(trade, *pool, calendar, calendar_index)
        if index_leg is None or pool_leg is None:
            unpriced += 1
            continue
        rows.append((trade.entry_date, float(trade.net_r), index_leg, pool_leg))
    return rows, unpriced


def summary(rows: list[tuple[date, float, float, float]], first: date, last: date,
            trades: list[Trade]) -> dict[str, Any]:
    chosen = [r for r in rows if first <= r[0] <= last]
    book = [t for t in trades if first <= t.entry_date <= last]
    if not chosen:
        return {"trades": 0}
    return {
        "trades": len(book),
        "paired_trades": len(chosen),
        "mean_net_r": round(statistics.fmean(float(t.net_r) for t in book), 4),
        "trade": interval([(d, t) for d, t, _, _ in chosen]),
        "spy_leg": interval([(d, s) for d, _, s, _ in chosen]),
        "pool_leg": interval([(d, p) for d, _, _, p in chosen]),
        "trade_minus_spy": interval([(d, t - s) for d, t, s, _ in chosen]),
        "trade_minus_pool": interval([(d, t - p) for d, t, _, p in chosen]),
        "pool_minus_spy": interval([(d, p - s) for d, _, s, p in chosen]),
    }


def reproduction(books: dict[str, dict[str, Any]], reference: Path) -> dict[str, Any]:
    """Both books against `PR-019b.json`: counts, levels and the trade-minus-SPY difference."""
    if not reference.exists():
        return {"available": False}
    committed = json.loads(reference.read_text(encoding="utf-8"))
    checks, every = [], True
    for ours, theirs in (("selected", "cells"), ("unselected", "unselected")):
        for window in ("in_sample", "out_of_sample"):
            got, want = books[ours][window], committed[theirs][window][CELL]
            pairs = [("trades", got.get("trades"), want.get("trades")),
                     ("mean_net_r", got.get("mean_net_r"), want.get("mean_net_r")),
                     ("trade_minus_spy", got.get("trade_minus_spy"), want.get("difference"))]
            match = all(a == b for _, a, b in pairs)
            every &= match
            checks.append({"book": ours, "window": window, "match": match,
                           "got": {k: a for k, a, _ in pairs},
                           "committed": {k: b for k, _, b in pairs}})
    return {"available": True, "every_digit": every, "checks": checks}


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of)
    benchmark = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    min_bars = 252 + HOLD + 1
    if len(benchmark.bars) < min_bars:
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

    def load(name: str) -> BarSeries:
        return benchmark if name == BENCHMARK else store.as_of(name, Interval.DAY, Series.RAW,
                                                               as_of)

    # --- pass A: scores, one series at a time, then the selection - `run_pr019b --streamed` ------
    benchmark_daily = daily_returns(benchmark)
    scores: dict[str, dict[date, Decimal]] = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = load(name)
        if len(series.bars) < min_bars:
            continue
        got = score_instrument(series, formations, benchmark_daily, LOOKBACK)
        if got:
            scores[name] = got
    chosen = select_streamed(scores, formations, DECILE)
    selected, everything = chosen.selected, chosen.everything
    live = sorted({d for dates in everything.values() for d in dates})
    days_of = segments(live, calendar)
    print(f"as_of {as_of.isoformat()}   live formations {len(live)}   "
          f"admitted names {len(everything)}   selected names {len(selected)}", flush=True)

    costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    registry = atr_registry()

    def simulate(series: BarSeries, dates: list[date], label: str) -> list[Trade]:
        config = BacktestConfig(arm=label, exits=CANDIDATE, costs=costs,
                                trigger=OnDates(frozenset(dates)), risk_per_trade=RISK_PER_TRADE)
        return run_arm(series, [True] * len(series.bars), atr_component.compute(series, registry),
                       config).trades

    # --- phase 1: the selected book, in PR-019b's order ------------------------------------------
    books: dict[str, list[Trade]] = {"selected": [], "unselected": []}
    for name in sorted(selected):
        books["selected"].extend(simulate(load(name), spaced(selected[name], calendar_index,
                                                              MAX_HOLD), CELL))

    # --- phase 2: every admitted name - the no-selection book AND the pool's sums ----------------
    sums: dict[date, list[float]] = defaultdict(lambda: [0.0, 0, 0.0, 0])
    for count, name in enumerate(sorted(everything), start=1):
        series = load(name)
        books["unselected"].extend(simulate(series, spaced(everything[name], calendar_index,
                                                            MAX_HOLD), f"unselected_{CELL}"))
        contribute(sums, series, (day for f in everything[name] for day in days_of.get(f, ())))
        if count % 1000 == 0:
            print(f"  phase 2: {count}/{len(everything)} admitted names", flush=True)
    store.close()
    pool = daily_pool(sums)

    day_after = PRIMARY_END + timedelta(days=1)
    windows = {"in_sample": (start, min(PRIMARY_END, end)),
               "out_of_sample": (max(day_after, start), end)}
    out_books: dict[str, dict[str, Any]] = {}
    unpriced: dict[str, int] = {}
    for label, trades in books.items():
        rows, unpriced[label] = legs(trades, spy, pool, calendar, calendar_index)
        out_books[label] = {w: summary(rows, *span, trades) for w, span in windows.items()}

    result: dict[str, Any] = {
        "measures": "each trade against its OWN admitted universe, equal-weighted, over exactly its "
                    "sessions and in its own R - beside the SPY leg PR-019b read",
        "exploratory": True,
        "spends_trials": "none - the configurations are PR-019b's and PR-019's, already counted; "
                         "only the null differs, and no configuration is selected on it",
        "as_of": as_of.isoformat(), "candidate": CELL,
        "pool": "every name admitted at the latest live formation strictly before the session, "
                "equal-weighted, rebalanced daily; bought at the entry session's open, marked at "
                "the exit session's close - the SPY leg's own form",
        "live_formations": len(live), "admitted_names": len(everything),
        "trades_without_both_legs": unpriced,
        "books": out_books,
        "not_measured": [
            "cap weighting within the pool: equal weights are the pool's own definition "
            "(measure_benchmark_fit, PR-014's control), not a claim about what an investor holds",
            "costs on either null: both are charged zero, the strictest reading, as PR-019b's "
            "primary",
            "a halted member's return since its last bar is attributed to the day it resumes",
        ],
    }
    result["reproduction"] = reproduction(out_books, args.reference)
    return result


def _span(block: dict[str, float] | None) -> str:
    if not block:
        return "-"
    return f"{block['observed']:+.4f} [{block['low']:+.4f}, {block['high']:+.4f}]"


def report(result: dict[str, Any]) -> None:
    repro = result.get("reproduction", {})
    print(f"universe null   as_of {result['as_of']}   EXPLORATORY - no verdict\n")
    print(f"  reproduction of PR-019b.json: every digit {repro.get('every_digit')}")
    for check in repro.get("checks", []):
        print(f"    {'ok ' if check['match'] else 'NO '} {check['book']:10} {check['window']:14} "
              f"got {check['got']}")
    print(f"\n  unpriced: {result['trades_without_both_legs']}")
    for label in ("selected", "unselected"):
        for window, cell in result["books"][label].items():
            if not cell.get("trades"):
                continue
            print(f"\n  {label} {window}   {cell['trades']} trades, mean {cell['mean_net_r']:+.4f}R")
            for key in ("trade", "spy_leg", "pool_leg", "trade_minus_spy", "trade_minus_pool",
                        "pool_minus_spy"):
                print(f"    {key:18} {_span(cell.get(key))}")


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
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
                        encoding="utf-8")
    print(f"wrote {args.out}")
    report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
