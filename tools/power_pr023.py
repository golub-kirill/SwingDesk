"""The power estimate `PR-023` needs BEFORE it registers: what excess-Sharpe difference can it read?

**Widths only**, as `power_pr022.py`: both arms are simulated - the width of a difference between two
books depends on what the one holds, so it cannot be sized without the path - and the verdict's own
paired moving-block bootstrap is applied to the excess returns over `BIL`. Only WIDTHS and the arms'
construction leave this file, and `power_pr019.assert_no_effect_leaked` refuses a level.

**Nothing is held out**: `PR-023` selects nothing, so the estimate runs on the window the verdict reads.

    PYTHONPATH=$PWD/src python tools/power_pr023.py --data <store directory> --as-of <instant>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from power_pr019 import assert_no_effect_leaked
from run_pr022 import (
    BLOCK,
    POWER_FLOOR,
    RECENT_MONTHS,
    SESSIONS_PER_YEAR,
    mean_difference,
    month_ends,
    sharpe_readings,
    window_start,
)
from run_pr023 import (
    ARMS,
    ASSETS,
    BENCHMARK,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    CASH,
    SLIPPAGE_BPS,
    first_decision,
    held,
    load,
    minus,
    signals_for,
    simulate,
)
from swingdesk.market_data import BarStore

RESULT = REPO / "docs" / "prereg" / "results" / "PR-023-power.json"


def widths(book: list[float], spy: list[float], cash: list[float], resamples: int) -> dict[str, Any]:
    s = sharpe_readings(minus(book, cash), minus(spy, cash), resamples, seed=BOOTSTRAP_SEED)
    m = mean_difference(book, spy, resamples)
    return {"excess_sharpe_difference_width": s["difference"]["width"],
            "return_difference_width_points": m["hi"] - m["lo"],
            "sessions": len(book),
            "readable_at_floor": s["difference"]["width"] <= POWER_FLOOR}


def build(args: argparse.Namespace) -> dict[str, Any]:
    with BarStore(args.data / "bars.duckdb") as store:
        as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("the bar store is empty")
        market = load(store, as_of)
    ends = month_ends(market.calendar)
    decided = {name: signals_for(market, name, ends) for name in ASSETS}
    start = first_decision(market, ends, decided)
    spy, cash = held(market, BENCHMARK, start), held(market, CASH, start)
    sessions = market.calendar[start + 1:]
    cut = next(i for i, d in enumerate(sessions) if d >= window_start(as_of.date(), RECENT_MONTHS))
    years = len(sessions) / SESSIONS_PER_YEAR
    arms: dict[str, Any] = {}
    for arm in ARMS:
        book = simulate(market, arm, decided, start, 1.0)
        arms[arm] = {
            "construction": {"share_of_the_book_in_risk_assets": statistics.fmean(book.risky_share),
                             "traded_a_year": book.traded / years,
                             "cost_points_a_year": book.traded / years * SLIPPAGE_BPS / 100.0,
                             "asset_switches_a_year": book.switches / years},
            "registered_window": widths(book.returns, spy, cash, args.resamples),
            "last_48_months": widths(book.returns[cut:], spy[cut:], cash[cut:], args.resamples),
        }
        print(f"  {arm} sized", flush=True)
    payload: dict[str, Any] = {
        "for": "PR-023",
        "purpose": "a variance estimate for PREREG_TEMPLATE rule 9: the widths the verdict estimator "
                   "produces for each arm against SPY on excess returns over BIL. No level.",
        "as_of": as_of.isoformat(),
        "window": {"start": sessions[0].isoformat(), "end": sessions[-1].isoformat(),
                   "note": "the verdict's own window - PR-023 selects nothing and holds nothing out"},
        "block": BLOCK, "resamples": args.resamples, "seed": BOOTSTRAP_SEED,
        "power_floor_sharpe": POWER_FLOOR,
        "arms": arms,
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-023 power estimate - widths only, no level\n{'=' * 72}")
    print(f"  window {payload['window']['start']} .. {payload['window']['end']}")
    for arm, cell in payload["arms"].items():
        c = cell["construction"]
        print(f"\n  {arm}: in risk assets {c['share_of_the_book_in_risk_assets']:.1%}   traded "
              f"{c['traded_a_year']:.2f} a year   cost {c['cost_points_a_year']:.2f} points a year   "
              f"asset switches {c['asset_switches_a_year']:.2f} a year")
        for label in ("registered_window", "last_48_months"):
            w = cell[label]
            readable = "readable" if w["readable_at_floor"] else "NOT readable"
            print(f"    {label:18} {w['sessions']:>5} sessions   excess Sharpe difference width "
                  f"{w['excess_sharpe_difference_width']:.3f} ({readable})   return difference width "
                  f"{w['return_difference_width_points']:.2f} points")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data",
                        help="directory holding the bars.duckdb with the five funds and BIL")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true",
                        help="re-read an existing estimate instead of running it")
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
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
