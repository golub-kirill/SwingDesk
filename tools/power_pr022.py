"""The power estimate `PR-022` needs BEFORE it registers: can nineteen years read a Sharpe difference?

**Widths only.** The rule is run - the width of a difference between two books depends on when one
of them steps aside, so there is no way to size it without the path - and the verdict's own
moving-block bootstrap is applied to the paired daily returns. Only interval WIDTHS leave this
file, and `power_pr019.assert_no_effect_leaked` refuses the payload if a key names a level.

**Nothing is held out, and that is stated rather than hidden.** `PR-022` selects nothing, so it has
no split and the estimate runs on the window the verdict reads. The widths say how precise the
verdict can be; they do not say where it sits.

**What it prints that is not the answer.** How often the rule is invested and how often it
switches are properties of the rule on this index - one public price series - and the cost
arithmetic needs them before the run.

    PYTHONPATH=$PWD/src python tools/power_pr022.py --data <store directory> --as-of <instant>
"""

from __future__ import annotations

import argparse
import json
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
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    POWER_FLOOR,
    RECENT_MONTHS,
    SLIPPAGE_BPS,
    build_paths,
    first_decision,
    load,
    mean_difference,
    month_ends,
    sharpe_readings,
    signals,
    window_start,
)
from swingdesk.market_data import BarStore

RESULT = REPO / "docs" / "prereg" / "results" / "PR-022-power.json"


def widths(timed: list[float], held: list[float], resamples: int) -> dict[str, Any]:
    """Every interval width the verdict and its diagnostics will carry. The bounds are dropped."""
    s = sharpe_readings(timed, held, resamples)
    m = mean_difference(timed, held, resamples)
    return {"sharpe_difference_width": s["difference"]["width"],
            "sharpe_timed_width": s["timed"]["width"],
            "sharpe_held_width": s["held"]["width"],
            "return_difference_width_points": m["hi"] - m["lo"],
            "sessions": len(timed),
            "readable_at_floor": s["difference"]["width"] <= POWER_FLOOR}


def build(args: argparse.Namespace) -> dict[str, Any]:
    with BarStore(args.data / "bars.duckdb") as store:
        as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("the bar store is empty")
        prices = load(store, as_of)
    ends = month_ends(prices.calendar)
    decided = signals(prices, ends)
    start = first_decision(prices, ends, decided)
    paths = build_paths(prices, decided, start, 1.0)
    cut = next(i for i, d in enumerate(paths.sessions) if d >= window_start(as_of.date(), RECENT_MONTHS))
    years = len(paths.sessions) / 252
    payload: dict[str, Any] = {
        "for": "PR-022",
        "purpose": "a variance estimate for PREREG_TEMPLATE rule 9: the interval widths the verdict "
                   "estimator produces on the registered window and on the last 48 months. No level.",
        "as_of": as_of.isoformat(),
        "window": {"start": paths.sessions[0].isoformat(), "end": paths.sessions[-1].isoformat(),
                   "note": "the verdict's own window - PR-022 selects nothing and holds nothing out"},
        "block": BLOCK, "resamples": args.resamples, "seed": BOOTSTRAP_SEED,
        "power_floor_sharpe": POWER_FLOOR,
        "construction": {"share_of_sessions_invested": sum(paths.invested) / len(paths.invested),
                         "switches": paths.switches, "switches_a_year": paths.switches / years,
                         "cost_points_a_year_at_dr005": paths.switches / years * 2 * SLIPPAGE_BPS / 100.0},
        "registered_window": widths(paths.timed, paths.held, args.resamples),
        "last_48_months": widths(paths.timed[cut:], paths.held[cut:], args.resamples),
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-022 power estimate - widths only, no level\n{'=' * 72}")
    print(f"  window {payload['window']['start']} .. {payload['window']['end']}")
    c = payload["construction"]
    print(f"  invested {c['share_of_sessions_invested']:.1%} of sessions   switches {c['switches']} "
          f"({c['switches_a_year']:.2f} a year)   DR-005 cost {c['cost_points_a_year_at_dr005']:.2f} "
          f"points a year")
    for label in ("registered_window", "last_48_months"):
        w = payload[label]
        print(f"\n  {label}: {w['sessions']} sessions")
        readable = "readable" if w["readable_at_floor"] else "NOT readable"
        print(f"    Sharpe difference width {w['sharpe_difference_width']:.3f} "
              f"({readable} at {payload['power_floor_sharpe']})")
        print(f"    own Sharpe widths       timed {w['sharpe_timed_width']:.3f}   "
              f"held {w['sharpe_held_width']:.3f}")
        print(f"    return difference width {w['return_difference_width_points']:.2f} points a year")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data",
                        help="directory holding the bars.duckdb with SPY and BIL")
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
