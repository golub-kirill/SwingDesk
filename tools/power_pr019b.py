"""The power estimate `PR-019b` needs BEFORE it registers: is PR-019's candidate the market?

`PR-019` selected `h60_stop4.0` in sample - a 4 x ATR(14) stop, no target, 60 sessions - and read
it out of sample at +0.0528R, with the same exit on every admitted name at +0.0202R. Every arm is
long-only and holds a median 85 days, so part of that may be the index's drift. `PR-019b` pairs each
trade with the SAME notional in `rs.benchmark` over EXACTLY the trade's sessions, in the trade's own
R, and reads the difference.

**Why a power estimate first.** `PR-019`'s long-hold cells were unreadable because the difference
between two exits moved month to month with the market. Pairing a trade with the market over the
same days cancels exactly that component - which predicts a far tighter interval. That is a claim
to MEASURE (`AGENTS.md` §15), and `PREREG_TEMPLATE` rule 9 wants the number before a trial is spent.

**Dispersion only.** `power_pr019.assert_no_effect_leaked` refuses to write any level, so nothing
here can say which way the difference points.

    PYTHONPATH=$PWD/src python tools/power_pr019b.py --data <store> --as-of <instant>
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from power_pr019 import (
    DEFAULT_FRACTION,
    DEFAULT_SEED,
    MAX_HOLD,
    OOS_MONTHS,
    READABLE_HALF_WIDTH,
    assert_no_effect_leaked,
    half_width,
    lags_for_hold,
    overlap_inflation,
    predicted_oos,
    spaced,
    subsample,
    variance_components,
)
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import BENCHMARK, DECILE, Candidate, select
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
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import Trade
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: PR-019's in-sample selection, fixed - `PR-019b` selects nothing.
CANDIDATE = ExitPolicy(Decimal("4.0"), 60)

RESULT = REPO / "docs" / "prereg" / "results" / "PR-019b-power.json"


def market_r(trade: Trade, opens: dict[date, Decimal], closes: dict[date, Decimal]) -> float | None:
    """The same notional in the benchmark over the trade's own sessions, in the trade's own R.

    Bought at the benchmark's OPEN on the trade's entry session - the trade fills at the next
    session's open - and sold at the CLOSE of its exit session. A stop-out fills intraday at the
    stop, so the null holds a few hours longer on those days; stated rather than modelled. None when
    either price is missing, and the caller counts it.
    """
    entry, exit_ = opens.get(trade.entry_date), closes.get(trade.exit_date)
    if entry is None or exit_ is None or entry <= 0 or trade.initial_risk_per_share <= 0:
        return None
    market_return = (exit_ - entry) / entry
    return float(market_return * trade.entry_price / trade.initial_risk_per_share)


def dispersion(per_month: dict[str, list[float]]) -> dict[str, float]:
    components = variance_components(per_month)
    months = int(components["months"])
    corrected = half_width(components["var_between"], months)
    # The overlap correction, added after the registered run: the first three half-widths are
    # exactly what PR-019b-power.json holds, and these sit beside them. Same months as
    # `variance_components` - those with two or more trades - in month order.
    ordered = [statistics.fmean(per_month[m])
               for m in sorted(m for m, values in per_month.items() if len(values) >= 2)]
    lags = lags_for_hold(CANDIDATE.max_holding_bars)
    factor = overlap_inflation(ordered, components["var_between"], lags)
    overlapped = (half_width(components["var_between"] * factor, months)
                  if not math.isnan(factor) else float("nan"))
    return {**components,
            "half_width_uncorrected": half_width(components["var_observed"], months),
            "half_width_corrected": corrected,
            "half_width_predicted_oos": predicted_oos(corrected, months),
            "overlap_lags": float(lags),
            "overlap_factor": factor,
            "half_width_overlap": overlapped,
            "half_width_predicted_oos_overlap": predicted_oos(overlapped, months)}


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        raise SystemExit("the bar store is empty")
    every = sorted(store.instrument_ids(as_of))
    kept = set(subsample(every, args.fraction, args.seed)) | {BENCHMARK}
    series_by_name: dict[str, BarSeries] = {}
    for name in every:
        if name not in kept:
            continue
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= 252 + HOLD + 1:
            series_by_name[name] = series
    store.close()
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to fix the calendar")

    benchmark = series_by_name[BENCHMARK]
    calendar = [bar.session_date for bar in benchmark.bars]
    calendar_index = {session: i for i, session in enumerate(calendar)}
    opens = {bar.session_date: bar.open for bar in benchmark.bars}
    closes = {bar.session_date: bar.close for bar in benchmark.bars}
    end = min(PRIMARY_END, calendar[-1])
    sessions = window_sessions(calendar, WINDOW_START, end)
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    formations = ([d for d in sessions[::STEP] if earliest <= d <= sessions[-HOLD - 1]]
                  if len(sessions) > HOLD else [])
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    print(f"as_of {as_of.isoformat()}   universe {len(every)}   subsample {len(series_by_name)}   "
          f"formation dates {len(formations)}   window {WINDOW_START}..{end} (IN SAMPLE ONLY)",
          flush=True)

    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}
    selected: dict[str, list[date]] = {}
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            continue
        ranker = ByMarketPathStrength(series=series_by_name, benchmark=benchmark, lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top:
            selected.setdefault(name, []).append(session)

    costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    registry = atr_registry()
    paired: dict[str, list[float]] = defaultdict(list)
    alone: dict[str, list[float]] = defaultdict(list)
    market_only: dict[str, list[float]] = defaultdict(list)
    unpriced = 0
    trades = 0
    for count, name in enumerate(sorted(selected), start=1):
        series = series_by_name[name]
        config = BacktestConfig(arm="h60_stop4.0", exits=CANDIDATE, costs=costs,
                                trigger=OnDates(frozenset(spaced(selected[name], calendar_index,
                                                                 MAX_HOLD))),
                                risk_per_trade=RISK_PER_TRADE)
        armed = run_arm(series, [True] * len(series.bars),
                        atr_component.compute(series, registry), config)
        for trade in armed.trades:
            month = trade.entry_date.strftime("%Y-%m")
            benchmark_r = market_r(trade, opens, closes)
            if benchmark_r is None:
                unpriced += 1
                continue
            trades += 1
            paired[month].append(float(trade.net_r) - benchmark_r)
            alone[month].append(float(trade.net_r))
            market_only[month].append(benchmark_r)
        if count % 100 == 0:
            print(f"  simulated {count}/{len(selected)} selected instruments", flush=True)

    payload: dict[str, Any] = {
        "for": "PR-019b",
        "purpose": "a variance estimate for PREREG_TEMPLATE rule 9. No level is reported.",
        "as_of": as_of.isoformat(), "fraction": args.fraction, "seed": args.seed,
        "universe": len(every), "subsample": len(series_by_name),
        "formation_dates": len(formations),
        "window": {"start": WINDOW_START.isoformat(), "end": end.isoformat(),
                   "note": "IN SAMPLE ONLY - the holdout is not touched by a power estimate"},
        "cell": {"atr_stop_multiple": "4.0", "max_holding_period": 60, "target": None,
                 "entry_spacing_sessions": MAX_HOLD},
        "trades": trades, "trades_without_a_benchmark_price": unpriced,
        "dispersion": {
            "trade_minus_benchmark": dispersion(paired),
            "trade_alone": dispersion(alone),
            "benchmark_alone": dispersion(market_only),
        },
        "oos_months": OOS_MONTHS, "readable_half_width": READABLE_HALF_WIDTH,
        "approximation": ("half widths are a normal approximation to the moving-block bootstrap; "
                          "the block structure widens an interval, so each is a LOWER bound"),
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-019b power estimate - dispersion only, no level\n{'=' * 62}")
    print(f"  subsample {payload['subsample']} of {payload['universe']}, "
          f"{payload['trades']} trades ({payload['trades_without_a_benchmark_price']} unpriced)")
    print(f"\n  {'series':24} {'months':>7} {'corrected hw':>13} {'OOS hw, predicted':>18}")
    for name, cell in payload["dispersion"].items():
        hw, oos = cell["half_width_corrected"], cell["half_width_predicted_oos"]
        shown = "   n/a" if math.isnan(hw) else f"{hw:>13.4f}"
        shown_oos = "   n/a" if math.isnan(oos) else f"{oos:>18.4f}"
        print(f"  {name:24} {int(cell['months']):>7} {shown} {shown_oos}")
        if "overlap_factor" in cell:
            print(f"  {'':24} overlap: {int(cell['overlap_lags'])} lag(s), factor "
                  f"{cell['overlap_factor']:.3f}, half-width {cell['half_width_overlap']:.4f}, "
                  f"OOS predicted {cell['half_width_predicted_oos_overlap']:.4f}")
    print(f"\n  readable at the 0.15R floor: OOS half width <= {payload['readable_half_width']}")
    print(f"  {payload['approximation']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--fraction", type=float, default=DEFAULT_FRACTION)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true",
                        help="re-read an existing estimate instead of running it")
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
