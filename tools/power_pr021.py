"""The power estimate `PR-021` needs BEFORE it registers: can 48 months read the loser book at all?

**Dispersion only, and on the SELECTION half only.** `PR-021` selects its hold on half A and reads
the verdict on half B, which neither this estimate nor the selection ever loads. Each contrast is
resampled by the verdict's own moving-block bootstrap and ONLY the interval's width leaves the
function - a percentile interval's width does not move when the series is shifted, so it carries
nothing about where the answer sits. `power_pr019.assert_no_effect_leaked` refuses the payload if
any key names a level.

**Why half A's width predicts half B's.** The halves share every session and differ only in which
names they hold; each forms its decile from its own admitted names, so a half-B book holds as many
names as a half-A one and moves with the same market. The prediction is that the widths match, and
the report prints the realised one beside it.

**What it prints that is not the answer.** Turnover and the yearly cost it implies are properties
of the CONSTRUCTION - how much of the book changes hands - and say nothing about what the book
earns. The registration's cost arithmetic needs them before the run.

    PYTHONPATH=$PWD/src python tools/power_pr021.py --data <store directory> --as-of <instant>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from power_pr019 import assert_no_effect_leaked
from run_pr014 import moving_block_bootstrap
from run_pr015 import half_of
from run_pr021 import (
    BLOCK,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    HOLDS,
    MIN_NAMES_PER_DATE,
    POWER_FLOOR,
    SELECTION_HALF,
    SIDES,
    SLIPPAGE_BPS,
    WINDOW_MONTHS,
    annual,
    build_book,
    cohorts_for,
    liquidity_rule,
    load_panel,
    minus,
    net,
    open_stores,
    stock_symbols,
)

RESULT = REPO / "docs" / "prereg" / "results" / "PR-021-power.json"

#: The two contrasts the registration can choose between: against the index, and against the
#: stocks the book was drawn from. Both net of `DR-005` at 1x.
CONTRASTS = ("book_net_minus_spy", "book_net_minus_pool")


def width(values: Sequence[float], resamples: int) -> dict[str, Any]:
    """The verdict estimator's interval width on this series. The bounds themselves are dropped."""
    result = moving_block_bootstrap(list(values), BLOCK, BOOTSTRAP_SEED, resamples)  # type: ignore[arg-type]
    if result is None:
        raise SystemExit("too few sessions to resample")
    _, lo, hi = result
    full = annual(hi - lo)
    return {"full_width_points": full, "half_width_points": full / 2,
            "sd_per_session_points": statistics.pstdev(values) * 100.0,
            "sessions": len(values), "readable_at_floor": full <= POWER_FLOOR}


def build(args: argparse.Namespace) -> dict[str, Any]:
    store, directory = open_stores(args.data)
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        raise SystemExit("the bar store is empty")
    stocks, funds = stock_symbols(directory, as_of)
    directory.close()
    rule, rule_values = liquidity_rule()
    print(f"as_of {as_of.isoformat()}   loading half {SELECTION_HALF} only ...", flush=True)
    panel = load_panel(store, as_of, rule, stocks, funds,
                       lambda name: half_of(name) == SELECTION_HALF, args.window_months)
    store.close()
    cohorts, pools, thin = cohorts_for(panel, SELECTION_HALF, args.min_names)
    cells: dict[str, dict[str, Any]] = {}
    for hold in HOLDS:
        book = build_book(panel, cohorts, pools, hold)
        one = net(book)
        turnover = statistics.fmean(book.turnover)
        cells[str(hold)] = {
            "sessions": len(book.sessions),
            "cohort_size_typical": statistics.median(book.cohort_sizes),
            "turnover_per_session": turnover,
            "cost_points_a_year": annual(turnover * SIDES * SLIPPAGE_BPS / 10_000.0),
            "book_net_minus_spy": width(minus(one, book.spy), args.resamples),
            "book_net_minus_pool": width(minus(one, book.pool), args.resamples),
        }
        print(f"  hold {hold} sized", flush=True)
    payload: dict[str, Any] = {
        "for": "PR-021",
        "purpose": "a variance estimate for PREREG_TEMPLATE rule 9: the interval width the verdict "
                   "estimator produces on each hold and contrast, on the selection half only, from "
                   "centred series. No level.",
        "as_of": as_of.isoformat(),
        "half": SELECTION_HALF,
        "window": {"asked_months": args.window_months,
                   "start": panel.calendar[panel.start].isoformat(),
                   "end": panel.calendar[-2].isoformat(),
                   "note": "half A only - half B, the holdout, is never loaded here"},
        "universe": {"rule": rule_values, "stocks_only": True, **dict(panel.counts)},
        "thin_formations": thin,
        "block": BLOCK, "resamples": args.resamples, "seed": BOOTSTRAP_SEED,
        "power_floor_points": POWER_FLOOR,
        "cells": cells,
        "approximation": "half B's width is predicted equal to half A's: same sessions, a cohort of "
                         "the same size, the same market. The report prints the realised width",
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-021 power estimate - dispersion only, half {payload['half']}, no level\n{'=' * 72}")
    print(f"  window {payload['window']['start']} .. {payload['window']['end']}   "
          f"universe {json.dumps(payload['universe'])}")
    print(f"\n  {'hold':>4} {'sessions':>8} {'cohort':>7} {'turnover':>9} {'cost/yr':>8} "
          f"{'width vs SPY':>13} {'width vs pool':>14}")
    for hold, cell in payload["cells"].items():
        spy, pool = cell["book_net_minus_spy"], cell["book_net_minus_pool"]
        print(f"  {hold:>4} {cell['sessions']:>8} {cell['cohort_size_typical']:>7} "
              f"{cell['turnover_per_session']:>9.3f} {cell['cost_points_a_year']:>8.1f} "
              f"{spy['full_width_points']:>10.2f} {'ok' if spy['readable_at_floor'] else '--':>2} "
              f"{pool['full_width_points']:>11.2f} {'ok' if pool['readable_at_floor'] else '--':>2}")
    print(f"\n  readable: an interval no wider than {payload['power_floor_points']} points a year, "
          f"end to end")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data",
                        help="directory holding bars.duckdb and directory.duckdb")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true",
                        help="re-read an existing estimate instead of running it")
    parser.add_argument("--window-months", type=int, default=WINDOW_MONTHS)
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    parser.add_argument("--min-names", type=int, default=MIN_NAMES_PER_DATE)
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
