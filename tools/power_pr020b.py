"""The power estimate a re-registration of `PR-020` needs, under a construction that cannot turn a
low-volatility name's notional into tens of R.

`PR-020` (2026-09-13) was unreadable out of sample and failed its own null check: the pool leg was
expressed in each trade's R, and T-bill funds in the screen's top decile carry an `entry / risk`
above a thousand, so an ordinary pool week read as +73R (`PR-020-report.md`). The question - does
the ratified screen know anything, held with no stop, against its own universe - is still open.
This sizes two constructions side by side, on `power_pr020`'s entries and subsample:

* **A - in R, under the owner's floor.** `risk.min_stop_distance_fraction` (2 x ATR / price >=
  0.005, ratified 2026-09-13) is the live system's own admission now. A trade counts only when its
  risk per share is at least 0.5% of its entry, and a name joins the pool on a day only when its
  ratio cleared the floor at the previous close - both legs held to the rule the book is.
* **B - per unit invested.** `(trade net R - costed pool R) / (entry / risk)`: the two returns per
  dollar, every trade, the full pool, no weighting by `entry / risk` at all. Its floor is not in R,
  so reading it needs the owner's 0.15R restated as a return; the trades' `entry / risk` at the
  50th percentile is printed as the conversion that restatement would ratify.

**Dispersion only**, under `power_pr019.assert_no_effect_leaked`, in sample only. It chooses the
construction and the hold by precision; no level is computed.

    PYTHONPATH=$PWD/src python tools/power_pr020b.py --data <store> --as-of <instant>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from measure_universe_null import contribute, daily_pool, pool_r, segments
from power_pr019 import (
    DEFAULT_FRACTION,
    DEFAULT_SEED,
    MAX_HOLD,
    OOS_MONTHS,
    READABLE_HALF_WIDTH,
    assert_no_effect_leaked,
    spaced,
    subsample,
)
from power_pr020 import CELLS, dispersion, policy_for
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
from run_pr020 import pool_slipped
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.observation import ObservationSeries
from swingdesk.contracts.trade import Trade
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: The owner's floor, ratified 2026-09-13 - the number `sizing.size_long` reads as
#: `risk.min_stop_distance_fraction`. A study constant here; the test pins it to the registry.
FLOOR = Decimal("0.005")

RESULT = REPO / "docs" / "prereg" / "results" / "PR-020b-power.json"

#: The half-width a registration reads, per construction.
READ = "half_width_predicted_oos_overlap"


def floor_ratio(series: BarSeries, atr: ObservationSeries) -> dict[date, Decimal]:
    """`2 x ATR / close` on every session with a warm ATR - the floor's ratio, point in time.

    ATR emits one observation per bar, `None` until warm, so the two sequences align by index.
    """
    out: dict[date, Decimal] = {}
    for bar, observation in zip(series.bars, atr.observations, strict=True):
        if observation.value is not None and bar.close > 0:
            out[bar.session_date] = 2 * observation.value / bar.close
    return out


def tradeable_days(series: BarSeries, days: Iterable[date],
                   ratio: dict[date, Decimal]) -> list[date]:
    """The pool days on which this member counts: its PREVIOUS session cleared the floor.

    Point in time - the ratio known the evening before - and a member whose ratio is not yet warm
    does not count, which is the refusal the live path makes.
    """
    position = {bar.session_date: i for i, bar in enumerate(series.bars)}
    kept: list[date] = []
    for day in days:
        i = position.get(day)
        if i is None or i == 0:
            continue
        previous = ratio.get(series.bars[i - 1].session_date)
        if previous is not None and previous >= FLOOR:
            kept.append(day)
    return kept


def clears_floor(trade: Trade) -> bool:
    """A trade the live system would size: risk per share at least `FLOOR` of the entry."""
    return bool(trade.initial_risk_per_share / trade.entry_price >= FLOOR)


def per_unit(trade: Trade, difference_r: float) -> float:
    """A difference in the trade's R restated per unit invested: divided by `entry / risk`."""
    return difference_r * float(trade.initial_risk_per_share / trade.entry_price)


def cell_payload(hold: int, counts: dict[str, int], scales: list[float],
                 a_months: dict[str, list[float]],
                 b_months: dict[str, list[float]]) -> dict[str, Any]:
    """One hold's dispersion under both constructions, and B's half-width converted to R."""
    p50 = statistics.median(scales) if scales else None
    a = dispersion(a_months, hold)
    b = dispersion(b_months, hold)
    return {
        "max_holding_period": hold, "protective_stop": False, **counts,
        "entry_over_risk_p50": p50,
        "dispersion": {"A_in_r_under_the_floor": a, "B_per_unit_invested": b},
        "b_half_width_in_r_at_p50": None if p50 is None else b[READ] * p50,
    }


Pool = tuple[dict[date, float], dict[date, float]]


def build_pools(everything: dict[str, list[date]], series_by_name: dict[str, BarSeries],
                days_of: dict[date, list[date]],
                ratios: dict[str, dict[date, Decimal]]) -> tuple[Pool, Pool]:
    """Two pools over the same sessions: every admitted name (B's), and only the names the floor
    would let the book hold that day (A's)."""
    full_sums: dict[date, list[float]] = defaultdict(lambda: [0.0, 0, 0.0, 0])
    floored_sums: dict[date, list[float]] = defaultdict(lambda: [0.0, 0, 0.0, 0])
    for name, dates in everything.items():
        series = series_by_name[name]
        days = [day for f in dates for day in days_of.get(f, ())]
        contribute(full_sums, series, days)
        contribute(floored_sums, series, tradeable_days(series, days, ratios[name]))
    return daily_pool(full_sums), daily_pool(floored_sums)


def trade_values(trade: Trade, full_pool: Pool, floored_pool: Pool, calendar: list[date],
                 calendar_index: dict[date, int]) -> tuple[str, float | None, float | None]:
    """One trade's two readings - A in R against the FLOORED pool, B per unit invested against the
    FULL one - and, when A is missing, why."""
    full_leg = pool_r(trade, *full_pool, calendar, calendar_index)
    if full_leg is None:
        return "without_a_pool_price", None, None
    b = per_unit(trade, float(trade.net_r) - pool_slipped(full_leg, trade))
    if not clears_floor(trade):
        return "cut_by_floor", None, b
    floored_leg = pool_r(trade, *floored_pool, calendar, calendar_index)
    if floored_leg is None:
        return "without_a_floored_pool_price", None, b
    return "ok", float(trade.net_r) - pool_slipped(floored_leg, trade), b


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
    everything: dict[str, list[date]] = {}
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            continue
        for candidate in pool:
            everything.setdefault(candidate.instrument_id, []).append(session)
        ranker = ByMarketPathStrength(series=series_by_name, benchmark=benchmark, lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top:
            selected.setdefault(name, []).append(session)

    registry = atr_registry()
    atrs = {n: atr_component.compute(series_by_name[n], registry) for n in everything}
    ratios = {n: floor_ratio(series_by_name[n], atrs[n]) for n in everything}

    live = sorted({d for dates in everything.values() for d in dates})
    full_pool, floored_pool = build_pools(everything, series_by_name, segments(live, calendar),
                                          ratios)

    costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    per_cell: dict[str, dict[str, Any]] = {}
    for label in CELLS:
        policy = policy_for(label)
        a_months: dict[str, list[float]] = defaultdict(list)
        b_months: dict[str, list[float]] = defaultdict(list)
        counts = {"trades": 0, "cut_by_floor": 0, "without_a_pool_price": 0,
                  "without_a_floored_pool_price": 0}
        scales: list[float] = []
        for name in sorted(selected):
            series = series_by_name[name]
            config = BacktestConfig(
                arm=label, exits=policy, costs=costs, risk_per_trade=RISK_PER_TRADE,
                trigger=OnDates(frozenset(spaced(selected[name], calendar_index, MAX_HOLD))))
            for trade in run_arm(series, [True] * len(series.bars), atrs[name], config).trades:
                status, a_value, b_value = trade_values(trade, full_pool, floored_pool, calendar,
                                                        calendar_index)
                if b_value is None:
                    counts[status] += 1
                    continue
                counts["trades"] += 1
                month = trade.entry_date.strftime("%Y-%m")
                scales.append(float(trade.entry_price / trade.initial_risk_per_share))
                b_months[month].append(b_value)
                if a_value is None:
                    counts[status] += 1
                    continue
                a_months[month].append(a_value)
        per_cell[label] = cell_payload(policy.max_holding_bars, counts, scales, a_months,
                                       b_months)

    payload: dict[str, Any] = {
        "for": "PR-020b, a re-registration of PR-020 - not yet written",
        "purpose": ("a variance estimate for PREREG_TEMPLATE rule 9 under two constructions "
                    "that cannot weigh a trade by an absurd entry / risk: A in R under the "
                    "owner's floor on both legs, B per unit invested. Dispersion only."),
        "as_of": as_of.isoformat(), "fraction": args.fraction, "seed": args.seed,
        "universe": len(every), "subsample": len(series_by_name),
        "formation_dates": len(formations), "floor": str(FLOOR),
        "window": {"start": WINDOW_START.isoformat(), "end": end.isoformat(),
                   "note": "IN SAMPLE ONLY - the holdout is not touched by a power estimate"},
        "entry_spacing_sessions": MAX_HOLD,
        "cells": per_cell,
        "oos_months": OOS_MONTHS, "readable_half_width": READABLE_HALF_WIDTH,
        "b_units": ("B's half-widths are a return per unit invested; b_half_width_in_r_at_p50 "
                    "converts one at the trades' own entry / risk at the 50th percentile, which "
                    "is the conversion a restated floor would ratify"),
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-020b power estimate - dispersion only, no level\n{'=' * 72}")
    print(f"  subsample {payload['subsample']} of {payload['universe']}, floor {payload['floor']}")
    print(f"\n  {'cell':14} {'trades':>7} {'cut':>5} {'A: OOS hw, R':>13} "
          f"{'B: OOS hw, per unit':>20} {'B in R at p50':>14} {'p50 entry/risk':>15}")
    for label, cell in payload["cells"].items():
        a = cell["dispersion"]["A_in_r_under_the_floor"][READ]
        b = cell["dispersion"]["B_per_unit_invested"][READ]
        b_r = cell["b_half_width_in_r_at_p50"]
        print(f"  {label:14} {cell['trades']:>7} {cell['cut_by_floor']:>5} {a:>13.4f} "
              f"{b:>20.5f} {b_r if b_r is not None else float('nan'):>14.4f} "
              f"{cell['entry_over_risk_p50'] or float('nan'):>15.1f}")
    print(f"\n  readable at the 0.15R floor: OOS half width <= {payload['readable_half_width']}")


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
