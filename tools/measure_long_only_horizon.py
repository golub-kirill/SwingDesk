"""The one significant signal this project has found is LONG-SHORT. The system is LONG-ONLY.

**EXPLORATORY. It sets no parameter and advances no validation status.**

**The gap this closes.** `measure_momentum_horizon` found the decile spread rising monotonically
with horizon and excluding zero only at **126 sessions: +7.271% [+1.899, +12.512]**. That is the
only measured, interval-excluding-zero result about this family in the store, and it is what any
argument for a longer hold rests on.

**It is `_spread` — top-decile mean MINUS bottom-decile mean.** Capturing it needs a short leg.
`trade_management/portfolio.py` says *"this system is long-only today"*, and `CARD-001` holds the
top decile and shorts nothing. **A long-only book earns the top decile's return against the
BENCHMARK, not against the bottom decile**, and those are different numbers: if the market rose 5%
while the top decile made 9% and the bottom 1.7%, the spread is 7.3% and the tradeable excess is 4%.

**Nobody had measured the tradeable half.** `measure_momentum_horizon`'s own docstring says *"a
gross spread is not a tradeable result and nothing here should be read as one"* — correctly — and
then the number was read as one anyway, by me among others.

So this measures, at each horizon and with the same construction:

  * **top decile, long only, minus the benchmark** — what a long-only book can actually earn
  * **NET of `DR-005`'s 25 bps per side**, charged once per rebalance, because
    `measure_exit_surface` established that on this store the cost term dominates everything at
    short horizons

Everything else is `measure_momentum_horizon`'s: the same formation window, the same skips, the same
liquidity rule, the same non-overlapping dates, the same bootstrap. Only the STATISTIC changes, so
the two are readable against each other.

    PYTHONPATH=$PWD/src python tools/measure_long_only_horizon.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import (
    FORMATION,
    HORIZONS,
    RULE,
    SKIPS,
    _formation_return,
)
from run_pr012 import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, bootstrap_interval
from run_pr013 import (
    MIN_NAMES_PER_DATE,
    _admitted_dates,
    _forward_returns,
)
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore

#: `rs.benchmark`, `assumed:DR-018`. The thing a long-only book is trying to beat.
BENCHMARK = "SPY"

#: `screen.relative_strength_rule` = `top_decile`, ratified by the owner via `DR-030`.
DECILE = Decimal("0.10")

#: `DR-005`, ratified: 25 bps per side. A rebalance is a round trip, so twice.
SLIPPAGE_BPS = Decimal("25")
ROUND_TRIP = 2 * SLIPPAGE_BPS / Decimal(10_000)


def _top_decile_excess(
    scores: dict[str, Decimal],
    forward: dict[str, Decimal],
    benchmark: Decimal,
) -> Decimal | None:
    """Top-decile mean forward return minus the benchmark's, over the same window.

    The long-only counterpart of `_spread`. A name without a forward return is excluded rather than
    sorted to the bottom, which is `_spread`'s rule and is kept so the two are comparable.
    """
    ranked = sorted(
        ((score, name) for name, score in scores.items() if name in forward),
        key=lambda pair: (-pair[0], pair[1]),
    )
    if len(ranked) < MIN_NAMES_PER_DATE:
        return None
    size = int(len(ranked) * DECILE)
    if size < 1:
        return None
    top = [forward[name] for _, name in ranked[:size]]
    return (sum(top, Decimal(0)) / len(top)) - benchmark


def measure(store: BarStore, as_of: datetime) -> list[dict[str, object]]:
    series_by_name = {}
    for name in store.instrument_ids(as_of):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if len(series.bars) >= FORMATION + max(SKIPS) + max(HORIZONS) + 1:
            series_by_name[name] = series
    print(f"names with enough history: {len(series_by_name)}")
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to serve as the benchmark")

    closes = {n: [b.close for b in s.bars] for n, s in series_by_name.items()}
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}

    rows: list[dict[str, object]] = []
    for horizon in HORIZONS:
        forward = {n: _forward_returns(s, horizon) for n, s in series_by_name.items()}
        calendar = sorted({d for f in forward.values() for d in f})
        dates = calendar[::horizon]
        admitted = {n: _admitted_dates(s, RULE, dates) for n, s in series_by_name.items()}
        bench = forward[BENCHMARK]

        for skip in SKIPS:
            gross: list[Decimal] = []
            for session in dates:
                if session not in bench:
                    continue
                scores: dict[str, Decimal] = {}
                for name, positions in index_of.items():
                    end = positions.get(session)
                    if end is None or session not in admitted[name]:
                        continue
                    value = _formation_return(closes[name], end, skip)
                    if value is not None:
                        scores[name] = value
                if len(scores) < MIN_NAMES_PER_DATE:
                    continue
                observed = {n: forward[n][session] for n in scores if session in forward[n]}
                excess = _top_decile_excess(scores, observed, bench[session])
                if excess is not None:
                    gross.append(excess)

            row: dict[str, object] = {"skip": skip, "horizon": horizon, "n": len(gross)}
            if not gross:
                rows.append(row)
                continue

            # One rebalance per holding window: the book is sold and rebought. The benchmark is
            # held, not traded, so the cost falls on the long leg alone - which is the honest
            # asymmetry and is why this is charged here rather than to the difference.
            net = [value - ROUND_TRIP for value in gross]
            for label, values in (("gross", gross), ("net", net)):
                interval = bootstrap_interval(values, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES)
                if interval is None:
                    continue
                mean, low, high = interval
                row[f"{label}_mean"] = repr(mean)
                row[f"{label}_ci_low"] = repr(low)
                row[f"{label}_ci_high"] = repr(high)
                row[f"{label}_excludes_zero"] = bool(low > 0 or high < 0)
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    as_of = datetime.now().astimezone()
    with BarStore(args.data / "bars.duckdb") as store:
        rows = measure(store, as_of)

    print()
    print(f"  TOP DECILE, LONG ONLY, minus {BENCHMARK} over the same window")
    print(f"  formation {FORMATION}, non-overlapping dates, "
          f"{BOOTSTRAP_RESAMPLES} bootstrap resamples")
    print(f"  net charges {SLIPPAGE_BPS}bp per side once per rebalance")
    print()
    print(f"{'skip':>5} {'horizon':>8} {'n':>5} {'gross':>9} {'95% interval':>22} "
          f"{'net':>9} {'95% interval':>22}")
    for row in rows:
        if not row.get("gross_mean"):
            print(f"{row['skip']:>5} {row['horizon']:>8} {row['n']:>5}   nothing measured")
            continue

        def cell(prefix: str, entry: dict[str, object] = row) -> str:
            # `entry` is bound at definition, not looked up from the loop variable: ruff B023,
            # and the bug it prevents is a formatter that silently reports the last row for all.
            mean = Decimal(entry[f"{prefix}_mean"])
            low = Decimal(entry[f"{prefix}_ci_low"])
            high = Decimal(entry[f"{prefix}_ci_high"])
            mark = "*" if entry[f"{prefix}_excludes_zero"] else " "
            return f"{mean:>+8.3%}{mark} [{low:>+7.3%}, {high:>+7.3%}]"

        print(f"{row['skip']:>5} {row['horizon']:>8} {row['n']:>5} {cell('gross')} {cell('net')}")
    print()
    print("  * = the bootstrap interval excludes zero")
    print("  For comparison, measure_momentum_horizon's LONG-SHORT spread at 126/skip 0 was")
    print("  +7.271% [+1.899, +12.512] gross. That needs a short leg this system does not have.")

    if args.out:
        args.out.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
