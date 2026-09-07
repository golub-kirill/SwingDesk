"""How much of the selected book survives to the next rebalance, and what that does to its cost.

**This is the cost input the next study cannot run without.** `PR-014` charged a full round trip on
the whole book at every rebalance and its `ACCEPT` did not survive the correction; the same shape is
still in `measure_short_leg.py` (`rebalance_cost`) and `run_pr013.py`
(`COST_SIDES_PER_FORMATION = 4`). Both charge GROSS turnover. A book pays NET: a name the new
selection re-picks is **held**, not sold and re-bought.

The quantity is one number per holding period - **the fraction of the book bought at a rebalance** -
and nothing in this repository had ever measured it outside `PR-014`'s own overlapping construction.
This measures it for the construction those two tools actually use: **non-overlapping formations
spaced `horizon` sessions apart**, the whole book rebuilt each time.

**Why it matters most where the owner is looking.** Persistence falls as the gap widens, so the
overcharge is largest at short holds. `PR-014` measured 2.69x at twenty sessions against 1.02x at a
year, on the overlapping book. A screen for a 14-20 session hold priced on gross turnover would
repeat that error exactly where it is biggest.

**Selection is the RATIFIED rule** - `decision_logic.ranking.ByMarketPathStrength` at
`rs.lookback` 126, top decile - called through the live class rather than reimplemented, for the
reason `PR-014` amendment A-2 gives: a study that reimplements the rule can drift from it.

**Spends no trials.** Turnover is a cost input and has no Sharpe to deflate. Declared in
`tools/trial_budget.py`; nothing here selects anything or compares a return.

    PYTHONPATH=$PWD/src python tools/measure_decile_persistence.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import (
    BENCHMARK,
    DECILE,
    LOOKBACK,
    SESSIONS_PER_YEAR,
    SLIPPAGE_BPS,
    Candidate,
    book_weights,
    select,
    turnover,
)
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.market_data import BarStore

#: The owner's target band first (14 and 20 sessions), then the horizons the two uncorrected tools
#: report at, so the size of their error is readable off the same table.
HORIZONS = (14, 20, 21, 42, 63, 126, 252)

#: A long-only book pays two sides a name; a decile SPREAD pays four, because both legs turn.
#: `measure_short_leg.py` and `run_pr013.py` charge four and `PR-014`'s long-only arm charges two.
SIDES = {"long_only": 2, "long_short": 4}

#: Fewer than this many rebalances and the mean turnover is an anecdote. `PR-014` §8 uses 24 for a
#: return; a turnover is far less noisy, and this is deliberately the same number rather than a
#: looser one chosen here.
MIN_REBALANCES = 24


def one_sided(previous: list[str], current: list[str]) -> Decimal:
    """The fraction of an equal-weighted book that must be BOUGHT to go from one list to the other.

    `run_pr014.book_weights` and `run_pr014.turnover` do the work, called with a single leg. Reusing
    them is not tidiness: the number this tool reports has to be the same quantity `PR-014` now
    charges, or the two studies would price the same book differently and the comparison in the
    report would be between two definitions rather than two constructions.
    """
    before = book_weights([date(2000, 1, 1)], {date(2000, 1, 1): previous}) if previous else {}
    after = book_weights([date(2000, 1, 2)], {date(2000, 1, 2): current}) if current else {}
    return turnover(before, after)


def annual_cost(mean_turnover: Decimal, horizon: int, arm: str, bps: Decimal) -> Decimal:
    """What a year of that turnover costs, at `bps` a side.

    `SESSIONS_PER_YEAR / horizon` rebalances a year, each buying `mean_turnover` of the book and
    selling as much. The round trip is charged at entry, which is why `SIDES` is 2 and not 1: a
    position that is bought will be sold, and deferring half the charge prices one decision twice.
    """
    per_rebalance = mean_turnover * Decimal(SIDES[arm]) * bps / Decimal(10000)
    return per_rebalance * Decimal(SESSIONS_PER_YEAR) / Decimal(horizon)


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_decile_persistence")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--as-of", default=None,
                        help="read the store at this knowledge instant instead of the latest")
    # Dated in the name, and the date is WRITTEN rather than read from the clock: `REQ-DATA-001`
    # keeps wall-clock reads out of this project, and the measurement's own date belongs to the
    # commit that files it rather than to whenever someone re-runs the tool.
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/"
                                     "decile-persistence-2026-09-07.json"))
    args = parser.parse_args()

    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        print("the bar store is empty")
        return 1

    series_by_name: dict[str, BarSeries] = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= LOOKBACK + min(HORIZONS) + 1:
            series_by_name[name] = series
    store.close()
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to serve as the benchmark")

    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    benchmark = series_by_name[BENCHMARK]
    calendar = [b.session_date for b in benchmark.bars]

    # Every date any horizon's grid needs, ranked ONCE. The grids for 14 and 42 sessions share
    # dates, and ranking nine thousand names twice at the same date to fill two rows of one table
    # would be the same work for the same answer.
    grids = {h: calendar[LOOKBACK::h] for h in HORIZONS}
    wanted = sorted({d for grid in grids.values() for d in grid})
    print(f"as_of {as_of.isoformat()}   instruments {len(series_by_name)}   "
          f"formation dates to rank {len(wanted)}   lookback {LOOKBACK} (ratified, path form)")

    admitted = {n: _admitted_dates(s, RULE, wanted) for n, s in series_by_name.items()}
    picks: dict[date, tuple[list[str], list[str]]] = {}
    for session in wanted:
        candidates = [
            Candidate(name, positions[session])
            for name, positions in index_of.items()
            if session in positions and session in admitted[name]
        ]
        if len(candidates) < MIN_NAMES_PER_DATE:
            continue
        ranker = ByMarketPathStrength(
            series=series_by_name, benchmark=benchmark, lookback=LOOKBACK
        )
        top, bottom = select(ranker, candidates, DECILE)
        if top and bottom:
            picks[session] = (top, bottom)
    print(f"  dates with a full cross-section: {len(picks)}\n")

    rows: list[dict[str, object]] = []
    for horizon in HORIZONS:
        grid = [d for d in grids[horizon] if d in picks]
        turns: dict[str, list[Decimal]] = {"top": [], "bottom": []}
        kept: dict[str, list[Decimal]] = {"top": [], "bottom": []}
        sizes: list[int] = []
        for i in range(1, len(grid)):
            for end, position in (("top", 0), ("bottom", 1)):
                before = picks[grid[i - 1]][position]
                after = picks[grid[i]][position]
                turns[end].append(one_sided(before, after))
                kept[end].append(Decimal(len(set(before) & set(after))) / Decimal(len(before)))
            sizes.append(len(picks[grid[i]][0]))
        if not turns["top"]:
            continue
        mean = {e: sum(v, Decimal(0)) / len(v) for e, v in turns.items()}
        row: dict[str, object] = {
            "horizon": horizon,
            "rebalances": len(turns["top"]),
            "sample_rule_met": len(turns["top"]) >= MIN_REBALANCES,
            "mean_book_size": round(sum(sizes) / len(sizes), 1),
            "one_sided_turnover": float(round(mean["top"], 4)),
            "one_sided_turnover_bottom": float(round(mean["bottom"], 4)),
            "names_retained": float(round(sum(kept["top"], Decimal(0)) / len(kept["top"]), 4)),
            "names_retained_bottom": float(round(
                sum(kept["bottom"], Decimal(0)) / len(kept["bottom"]), 4)),
        }
        # A long-only book pays two sides on the top decile alone. A SPREAD pays two sides on each
        # end, and the two ends are measured separately rather than assumed equal - which is what
        # the first version of this tool did, and it is the same class of assumption the whole
        # correction is about.
        row["annual_cost_long_only"] = float(round(
            annual_cost(mean["top"], horizon, "long_only", SLIPPAGE_BPS), 6))
        row["annual_cost_long_short"] = float(round(
            annual_cost(mean["top"], horizon, "long_only", SLIPPAGE_BPS)
            + annual_cost(mean["bottom"], horizon, "long_only", SLIPPAGE_BPS), 6))
        for arm in SIDES:
            row[f"annual_cost_{arm}_as_charged"] = float(round(
                annual_cost(Decimal(1), horizon, arm, SLIPPAGE_BPS), 6))
        row["overcharge"] = float(round(1 / mean["top"], 2)) if mean["top"] > 0 else None
        row["overcharge_long_short"] = (
            float(round(Decimal(str(row["annual_cost_long_short_as_charged"]))
                        / Decimal(str(row["annual_cost_long_short"])), 2))
            if row["annual_cost_long_short"] else None)
        rows.append(row)

    print("ONE-SIDED TURNOVER of the ratified top decile, non-overlapping formations")
    print(f"  {'horizon':>8}{'rebals':>7}{'names':>7}{'TOP bought':>12}{'kept':>7}"
          f"{'BTM bought':>12}{'kept':>7}{'long-only':>11}{'charged':>9}{'over':>7}"
          f"{'spread':>9}{'charged':>9}{'over':>7}")
    for row in rows:
        flag = "  (thin)" if not row["sample_rule_met"] else ""
        print(f"  {row['horizon']:>8}{row['rebalances']:>7}{row['mean_book_size']:>7.0f}"
              f"{row['one_sided_turnover'] * 100:>11.1f}%{row['names_retained'] * 100:>6.1f}%"
              f"{row['one_sided_turnover_bottom'] * 100:>11.1f}%"
              f"{row['names_retained_bottom'] * 100:>6.1f}%"
              f"{row['annual_cost_long_only'] * 100:>10.2f}%"
              f"{row['annual_cost_long_only_as_charged'] * 100:>8.2f}%"
              f"{row['overcharge']:>6.2f}x"
              f"{row['annual_cost_long_short'] * 100:>8.2f}%"
              f"{row['annual_cost_long_short_as_charged'] * 100:>8.2f}%"
              f"{row['overcharge_long_short']:>6.2f}x{flag}")
    print(f"\n  Cost at DR-005's {SLIPPAGE_BPS} bps a side, {SIDES['long_only']} sides for a "
          f"long-only book and {SIDES['long_short']} for a spread.")
    print("  'as charged' is what measure_short_leg.py and run_pr013.py charge today: the WHOLE "
          "book, every formation.")
    print(f"  Sample rule: >= {MIN_REBALANCES} rebalances, the same minimum PR-014 §8 uses.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "measures": "one-sided turnover of the ratified top decile, by holding period",
        "spends_trials": "none - turnover is a cost input and has no Sharpe to deflate",
        "as_of": as_of.isoformat(),
        "lookback": LOOKBACK,
        "decile": str(DECILE),
        "benchmark": BENCHMARK,
        "slippage_bps_per_side": str(SLIPPAGE_BPS),
        "sides": SIDES,
        "construction": "non-overlapping formations spaced `horizon` sessions apart, the whole "
                        "book rebuilt at each - the construction measure_short_leg.py and "
                        "run_pr013.py use. PR-014's own book overlaps and is priced by its own tool",
        "min_rebalances": MIN_REBALANCES,
        "instruments": len(series_by_name),
        "formation_dates_ranked": len(picks),
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
