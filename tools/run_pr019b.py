"""`PR-019b` - is `PR-019`'s candidate exit the MARKET, or does it out-earn the index over the same days?

`PR-019` selected `h60_stop4.0` in sample - a 4 x ATR(14) stop, no target, 60 sessions - and read it
out of sample at +0.0528R a trade. Every arm there is long-only and holds a median 85 calendar days,
and the same exit on every admitted name still read +0.0202R: which is what the index's drift would
look like. **No study since `PR-015` has compared a trade with the index over the same days**, and
`STRATEGY_CONTRACT` C-3 owes it.

**The null, per trade.** The same notional in `rs.benchmark`, bought at the benchmark's OPEN on the
trade's own entry session and sold at its CLOSE on the trade's exit session, in the trade's own R
(`power_pr019b.market_r`). The statistic is the mean of `trade net R - market R`, resampled on
entry months. One number per trade, so the pairing is exact by construction - and the power estimate
measured what that buys: a predicted out-of-sample half-width of 0.074R where the trade alone reads
0.181R.

**Nothing is selected.** The cell is fixed by `PR-019`'s in-sample rule: one configuration, one
trial. The verdict is read OUT OF SAMPLE only; the in-sample difference is printed and never read,
because the cell was chosen there.

    PYTHONPATH=$PWD/src python tools/run_pr019b.py --data <store> --as-of <instant>
    python tools/run_pr019b.py --report

`PRELIMINARY` on `DR-042`'s terms, as `PR-016` to `PR-019` are.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from power_pr019 import MAX_HOLD, spaced
from power_pr019b import CANDIDATE, market_r
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import BENCHMARK, DECILE, Candidate, select
from run_pr016 import (
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
    STRESS_MULTIPLE,
    WINDOW_START,
    OnDates,
    atr_registry,
    block_bootstrap,
    by_month,
    cluster_of,
    distribution,
    window_sessions,
)
from run_pr019 import common_entries, mae_profile
from stream_selection import score_instrument, select_streamed
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import Trade
from swingdesk.decision_logic.ranking import ByMarketPathStrength, daily_returns
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: `PR-019`'s in-sample selection. Fixed here; `PR-019b` selects nothing.
CELL = "h60_stop4.0"

POWER_FLOOR = Decimal("0.15")
#: The predicted out-of-sample half-width of `trade - market`, from `tools/power_pr019b.py`,
#: committed as `PR-019b-power.json` before this registration. A normal approximation to the
#: moving-block bootstrap, so a LOWER bound.
MINIMUM_DETECTABLE_EFFECT = Decimal("0.0743")

#: §5's perturbations, declared in the result because gate 25 reads the declaration. Each moves ONE
#: thing against the primary - `run_pr016.control_arm_for` is the record of what happens otherwise.
PERTURBATIONS: dict[str, Any] = {
    "registered": ["benchmark_costed_1x", "cost_stress_3x"],
    "run": ["benchmark_costed_1x", "cost_stress_3x"],
    "note": ("benchmark_costed_1x charges the benchmark leg DR-005's model, symmetric with the "
             "trade; cost_stress_3x charges the TRADE three times DR-005 and keeps the benchmark at "
             "the primary's zero"),
}

RESULT = REPO / "docs" / "prereg" / "results" / "PR-019b.json"
#: §9 reproduces `PR-019`'s committed cells from this file, so no number is typed twice.
REFERENCE = REPO / "docs" / "prereg" / "results" / "PR-019.json"

PRELIMINARY = {
    "status": "PRELIMINARY - not a final result",
    "why": (
        "DR-042's tie-break is unruled and this study runs under it. Measured 2026-09-08: at most "
        "0.0006R a trade, and it binds only on cells with a protective stop."
    ),
    "settled_by": "docs/decisions/DR-042 §8",
}


@dataclass(frozen=True, slots=True)
class Paired:
    """One trade and the benchmark over exactly its sessions, both in the trade's R."""

    entry_date: date
    trade_r: float
    market_r: float
    market_r_costed: float


def market_r_costed(trade: Trade, opens: dict[date, Decimal], closes: dict[date, Decimal],
                    slippage_bps: Decimal, commission: Decimal) -> float | None:
    """`market_r` with the benchmark leg charged the way a trade is: slippage on both fills and a
    commission per benchmark share on both sides.

    Same notional `N = shares x entry price`. Bought at `open x (1 + s)` and sold at
    `close x (1 - s)`; the benchmark position is `N / buy` shares, so commission is `2c x N / buy`.
    Divided by the trade's risk, `shares x initial risk per share`, every `N` cancels.
    """
    entry, exit_ = opens.get(trade.entry_date), closes.get(trade.exit_date)
    if entry is None or exit_ is None or entry <= 0 or trade.initial_risk_per_share <= 0:
        return None
    side = slippage_bps / Decimal(10_000)
    buy, sell = entry * (1 + side), exit_ * (1 - side)
    per_notional = (sell - buy) / buy - 2 * commission / buy
    return float(per_notional * trade.entry_price / trade.initial_risk_per_share)


def pair(trades: list[Trade], opens: dict[date, Decimal],
         closes: dict[date, Decimal]) -> tuple[list[Paired], int]:
    """Every trade with its benchmark leg, and how many could not be priced. Never dropped silently."""
    paired: list[Paired] = []
    unpriced = 0
    for trade in trades:
        plain = market_r(trade, opens, closes)
        costed = market_r_costed(trade, opens, closes, SLIPPAGE_BPS, COMMISSION_PER_SHARE)
        if plain is None or costed is None:
            unpriced += 1
            continue
        paired.append(Paired(trade.entry_date, float(trade.net_r), plain, costed))
    return paired, unpriced


def monthly(values: list[tuple[date, float]]) -> list[list[Decimal]]:
    """Per-trade values grouped by entry month, in month order - the bootstrap's clusters."""
    grouped: dict[str, list[Decimal]] = defaultdict(list)
    for entry, value in values:
        grouped[cluster_of(entry)].append(Decimal(repr(value)))
    return [grouped[month] for month in sorted(grouped)]


def interval(values: list[tuple[date, float]]) -> dict[str, float] | None:
    """The mean and its 95% moving-block interval over entry months, as `PR-016` resamples."""
    got = block_bootstrap(monthly(values), "mean", BLOCK, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES)
    if got is None:
        return None
    return {"observed": round(got[0], 4), "low": round(got[1], 4), "high": round(got[2], 4)}


def summarise(trades: list[Trade], paired: list[Paired],
              stressed: list[Paired] | None = None) -> dict[str, Any]:
    """One window of one book: the trade's own distribution and interval - computed exactly as
    `PR-019` did, so §9 can compare them digit for digit - then the benchmark leg and the
    differences §6 reads."""
    out = distribution(trades)
    if not trades:
        return out
    months = by_month(trades)
    out["months"] = len(months)
    own = block_bootstrap([months[m] for m in sorted(months)], "mean", BLOCK, BOOTSTRAP_SEED,
                          BOOTSTRAP_RESAMPLES)
    if own:
        out["mean_interval"] = {"low": round(own[1], 4), "high": round(own[2], 4)}
    out["mae"] = mae_profile(trades)
    out["paired_trades"] = len(paired)
    out["market_mean"] = interval([(p.entry_date, p.market_r) for p in paired])
    out["market_mean_costed"] = interval([(p.entry_date, p.market_r_costed) for p in paired])
    out["difference"] = interval([(p.entry_date, p.trade_r - p.market_r) for p in paired])
    out["difference_benchmark_costed"] = interval(
        [(p.entry_date, p.trade_r - p.market_r_costed) for p in paired])
    if stressed is not None:
        out["difference_stress_3x"] = interval(
            [(p.entry_date, p.trade_r - p.market_r) for p in stressed])
    return out


def qualifies(cell: dict[str, Any]) -> bool:
    return bool(cell.get("trades", 0) >= MIN_TRADES and cell.get("months", 0) >= MIN_MONTHS)


def underpowered(cell: dict[str, Any]) -> bool:
    difference = cell.get("difference")
    if not difference:
        return True
    return bool((difference["high"] - difference["low"]) > float(POWER_FLOOR))


def verdict_for(cell: dict[str, Any]) -> str:
    """§6, read on the candidate OUT OF SAMPLE only. Six outcomes, all registered before the run.

    `both_negative` is `PREREG_TEMPLATE` rule 8 - comparing two losers is not a finding - and comes
    first for that reason. `null` is rule 10: the instrument was sharp enough and the candidate is
    the market at this precision.
    """
    if not qualifies(cell):
        return "refused"
    if underpowered(cell):
        return "inconclusive"
    difference = cell["difference"]
    own, market = cell.get("mean_interval"), cell.get("market_mean")
    if own and market and own["high"] < 0 and market["high"] < 0:
        return "both_negative"
    if difference["low"] > 0:
        return "accept"
    if difference["high"] < 0:
        return "reject"
    return "null"


def windowed(rows: list[Any], first: date, last: date) -> list[Any]:
    return [row for row in rows if first <= row.entry_date <= last]


def reproduction(result: dict[str, Any], reference: Path) -> dict[str, Any]:
    """§9: the candidate and its no-selection null, against `PR-019`'s committed numbers.

    Read from the committed file, never typed, so there is no second copy to drift. Anything but
    every digit is a defect in this runner and is reported before the verdict.
    """
    if not reference.exists():
        return {"reference": str(reference), "available": False}
    committed = json.loads(reference.read_text(encoding="utf-8"))
    rows: dict[str, Any] = {"reference": reference.name, "available": True, "checks": []}
    every = True
    for group in ("cells", "unselected"):
        fields = ["trades", "mean_net_r"] + (["mean_interval"] if group == "cells" else [])
        for window in ("in_sample", "out_of_sample"):
            got = result[group][window].get(CELL) or {}
            want = committed.get(group, {}).get(window, {}).get(CELL) or {}
            match = all(got.get(f) == want.get(f) for f in fields)
            every &= match
            rows["checks"].append({"label": CELL, "group": group, "window": window,
                                   "match": match,
                                   "got": {f: got.get(f) for f in fields},
                                   "committed": {f: want.get(f) for f in fields}})
    rows["every_digit"] = every
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        raise SystemExit("the bar store is empty")

    # `--streamed` - loader phase A. One series in memory at a time: selection is scored name by name
    # and ranked from scores alone (`stream_selection`), and each name is read again to simulate and
    # then dropped. Added after this study reported, because it peaked at 22.4 GB with 0.9 GB to
    # spare. The in-memory path is unchanged and stays the reference the test holds it to.
    streamed = bool(getattr(args, "streamed", False))
    min_bars = 252 + HOLD + 1
    names = sorted(store.instrument_ids(as_of))
    series_by_name: dict[str, BarSeries] = {}
    if streamed:
        head = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
        if head and len(head.bars) >= min_bars:
            series_by_name[BENCHMARK] = head
    else:
        for name in names:
            series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
            if series and len(series.bars) >= min_bars:
                series_by_name[name] = series
        store.close()
    if BENCHMARK not in series_by_name:
        if streamed:
            store.close()
        raise SystemExit(f"{BENCHMARK} has too little history to fix the calendar")

    benchmark = series_by_name[BENCHMARK]
    calendar = [bar.session_date for bar in benchmark.bars]
    calendar_index = {session: i for i, session in enumerate(calendar)}
    opens = {bar.session_date: bar.open for bar in benchmark.bars}
    closes = {bar.session_date: bar.close for bar in benchmark.bars}
    start, end = WINDOW_START, calendar[-1]
    sessions = window_sessions(calendar, start, end)
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    # PR-019's formation dates exactly, so §9's reproduction sees PR-019's entries.
    formations = ([d for d in sessions[::STEP] if earliest <= d <= sessions[-HOLD - 1]]
                  if len(sessions) > HOLD else [])
    selected: dict[str, list[date]] = {}
    everything: dict[str, list[date]] = {}
    thin = 0
    if streamed:
        benchmark_daily = daily_returns(benchmark)
        scores: dict[str, dict[date, Decimal]] = {}
        instruments = 0
        for name in names:
            series = (benchmark if name == BENCHMARK
                      else store.as_of(name, Interval.DAY, Series.RAW, as_of))
            if not series or len(series.bars) < min_bars:
                continue
            instruments += 1
            got = score_instrument(series, formations, benchmark_daily, LOOKBACK)
            if got:
                scores[name] = got
        chosen = select_streamed(scores, formations, DECILE)
        selected, everything, thin = chosen.selected, chosen.everything, chosen.thin
    else:
        instruments = len(series_by_name)
        index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                    for n, s in series_by_name.items()}
        admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}
        for session in formations:
            pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                    if session in admitted[n]]
            if len(pool) < MIN_NAMES_PER_DATE:
                thin += 1
                continue
            for candidate in pool:
                everything.setdefault(candidate.instrument_id, []).append(session)
            ranker = ByMarketPathStrength(series=series_by_name, benchmark=benchmark,
                                          lookback=LOOKBACK)
            top, _ = select(ranker, pool, DECILE)
            for name in top:
                selected.setdefault(name, []).append(session)
    print(f"as_of {as_of.isoformat()}   instruments {instruments}   "
          f"formation dates {len(formations)}   loader {'streamed' if streamed else 'in memory'}",
          flush=True)

    spaced_selected = {n: spaced(d, calendar_index, MAX_HOLD) for n, d in selected.items()}
    base_costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    stress_costs = CostModel(COMMISSION_PER_SHARE * STRESS_MULTIPLE, SLIPPAGE_BPS * STRESS_MULTIPLE)
    registry = atr_registry()
    atr_cache: dict[str, Any] = {}

    def load(name: str) -> BarSeries:
        """The series to simulate: already held in memory, or read now and dropped after."""
        if name in series_by_name:
            return series_by_name[name]
        return store.as_of(name, Interval.DAY, Series.RAW, as_of)

    def simulate(series: BarSeries, policy: ExitPolicy, dates: list[date], costs: CostModel,
                 label: str) -> list[Trade]:
        name = series.instrument_id
        if name not in atr_cache:
            atr_cache[name] = atr_component.compute(series, registry)
        config = BacktestConfig(arm=label, exits=policy, costs=costs,
                                trigger=OnDates(frozenset(dates)), risk_per_trade=RISK_PER_TRADE)
        return run_arm(series, [True] * len(series.bars), atr_cache[name], config).trades

    # --- phase 1: the candidate at 1x and 3x costs, on the selected decile ----------------------
    # Names in the in-memory run's ORDER in both loaders, so the trade lists - and every float sum
    # and month grouping downstream - come out identical rather than merely equal in total.
    books: dict[str, list[Trade]] = {CELL: [], f"{CELL}_3x": []}
    for count, name in enumerate(sorted(selected), start=1):
        series = load(name)
        books[CELL].extend(simulate(series, CANDIDATE, spaced_selected[name], base_costs, CELL))
        books[f"{CELL}_3x"].extend(simulate(series, CANDIDATE, spaced_selected[name], stress_costs,
                                            f"{CELL}_3x"))
        atr_cache.pop(name, None)
        if count % 250 == 0:
            print(f"  phase 1: {count}/{len(selected)} selected instruments", flush=True)
    before = {label: len(book) for label, book in books.items()}
    books, dropped = common_entries(books)

    # --- phase 2: the same exit on every admitted name - diagnostic, never read by §6 -----------
    unselected: list[Trade] = []
    for count, name in enumerate(sorted(everything), start=1):
        dates = spaced(everything[name], calendar_index, MAX_HOLD)
        unselected.extend(simulate(load(name), CANDIDATE, dates, base_costs,
                                   f"unselected_{CELL}"))
        atr_cache.pop(name, None)
        if count % 1000 == 0:
            print(f"  phase 2: {count}/{len(everything)} admitted instruments", flush=True)
    if streamed:
        store.close()

    paired, unpriced = pair(books[CELL], opens, closes)
    paired_stressed, unpriced_stressed = pair(books[f"{CELL}_3x"], opens, closes)
    paired_unselected, unpriced_unselected = pair(unselected, opens, closes)

    day_after = PRIMARY_END + timedelta(days=1)
    windows = {"in_sample": (start, min(PRIMARY_END, end)),
               "out_of_sample": (max(day_after, start), end)}

    result: dict[str, Any] = {
        "prereg": "PR-019b", "trials": 1, "as_of": as_of.isoformat(), "country": "USA",
        "preliminary": PRELIMINARY,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "sessions": len(sessions)},
        "candidate": {"cell": CELL, "atr_stop_multiple": str(CANDIDATE.atr_stop_multiple),
                      "max_holding_period": CANDIDATE.max_holding_bars, "target": None,
                      "selected_by": "PR-019 §6, in sample"},
        "null": {"benchmark": BENCHMARK,
                 "leg": "same notional, benchmark OPEN on the trade's entry session to its CLOSE "
                        "on the trade's exit session, in the trade's own R",
                 "primary_cost": "zero", "perturbation_cost": "DR-005, symmetric"},
        "split": {"in_sample": f"entries on or before {PRIMARY_END} - printed, NEVER read",
                  "out_of_sample": f"entries after {PRIMARY_END} - the verdict",
                  "buys": "nothing is selected here; the split is PR-019's, and reading only its "
                          "out-of-sample window keeps the cell's selection off the verdict"},
        "perturbations": PERTURBATIONS,
        "power_floor": str(POWER_FLOOR),
        "minimum_detectable_effect": str(MINIMUM_DETECTABLE_EFFECT),
        "bootstrap": {"unit": "entry month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                      "resamples": BOOTSTRAP_RESAMPLES},
        "instruments": instruments, "formation_dates": len(formations),
        "formations_skipped_for_a_thin_cross_section": thin,
        "entries": {"selected_signals": sum(len(v) for v in selected.values()),
                    "after_spacing": sum(len(v) for v in spaced_selected.values()),
                    "realised_before_restriction": before,
                    "dropped_to_common_entries": dropped},
        "trades_without_a_benchmark_price": {CELL: unpriced, f"{CELL}_3x": unpriced_stressed,
                                             f"unselected_{CELL}": unpriced_unselected},
        "survivorship": "ABSENT and material, as PR-016..PR-019",
        "cells": {window: {CELL: summarise(windowed(books[CELL], *windows[window]),
                                           windowed(paired, *windows[window]),
                                           windowed(paired_stressed, *windows[window]))}
                  for window in windows},
        "unselected": {window: {CELL: summarise(windowed(unselected, *windows[window]),
                                                windowed(paired_unselected, *windows[window]))}
                       for window in windows},
        "not_measured": [
            "beta: the null holds the same NOTIONAL in the index, not a beta-matched position",
            "the stop-out day: the trade leaves at its stop intraday, the null at that session's "
            "close - a few hours' more index exposure on those days, stated not modelled",
            "the book: one trade at a time, no cap and no capacity",
        ],
    }
    if streamed:
        # Only when streamed, so a default run's result stays field for field what it was.
        result["loader"] = "streamed - one series in memory at a time (loader phase A)"
    entered = sorted(t.entry_date for t in books[CELL])
    if entered:
        span = (entered[-1] - entered[0]).days
        result["measured_span"] = {
            "first_entry": entered[0].isoformat(), "last_entry": entered[-1].isoformat(),
            "years": round(span / 365.25, 2),
            "meets_the_ten_year_instruction": span / 365.25 >= 10.0,
        }
    result["reproduction"] = reproduction(result, args.reference)
    result["verdict"] = verdict_for(result["cells"]["out_of_sample"][CELL])
    return result


def _interval(block: dict[str, float] | None) -> str:
    if not block:
        return "-"
    return f"{block['observed']:+.4f} [{block['low']:+.4f},{block['high']:+.4f}]"


def report(result: dict[str, Any]) -> None:
    preliminary = result.get("preliminary")
    if preliminary:
        print(f"*** {preliminary['status']} ***\n    {preliminary['why']}\n")
    print(f"PR-019b   as_of {result['as_of']}   verdict {result['verdict'].upper()}")
    print(f"  candidate {result['candidate']['cell']}   null {result['null']['benchmark']}, "
          f"primary cost {result['null']['primary_cost']}")
    print(f"  unpriced: {result['trades_without_a_benchmark_price']}")
    lost = {k: v for k, v in result["entries"]["dropped_to_common_entries"].items() if v}
    print(f"  dropped to the common entry set: {lost or 'none'}\n")

    repro = result.get("reproduction", {})
    print(f"  section 9 first - reproduction of {repro.get('reference')}: "
          f"every digit {repro.get('every_digit')}")
    for row in repro.get("checks", []):
        print(f"    {'ok ' if row['match'] else 'NO '} {row['group']:10} {row['window']:14} "
              f"got {row['got']}   committed {row['committed']}")

    print(f"\n  {'book':22} {'window':14} {'n':>6} {'trade mean':>10} {'market':>28} "
          f"{'trade - market':>28}")
    for name, group in ((CELL, result["cells"]), (f"unselected {CELL}", result["unselected"])):
        for window in ("in_sample", "out_of_sample"):
            c = group[window].get(CELL) or {}
            if not c.get("trades"):
                continue
            print(f"  {name:22} {window:14} {c['trades']:>6} {c['mean_net_r']:>+10.4f} "
                  f"{_interval(c.get('market_mean')):>28} {_interval(c.get('difference')):>28}")
    oos = result["cells"]["out_of_sample"][CELL]
    print(f"\n  perturbations, out of sample, {CELL}:")
    print(f"    benchmark costed 1x : {_interval(oos.get('difference_benchmark_costed'))}")
    print(f"    trade at 3x costs   : {_interval(oos.get('difference_stress_3x'))}")
    own = oos.get("mean_interval") or {}
    print(f"    trade's own interval: [{own.get('low')}, {own.get('high')}]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--as-of", help="knowledge instant, ISO-8601; defaults to the latest")
    parser.add_argument("--reference", type=Path, default=REFERENCE,
                        help="PR-019's committed result, which §9 reproduces")
    parser.add_argument("--streamed", action="store_true",
                        help="hold one series in memory at a time (loader phase A); the same "
                             "study, a fraction of the memory")
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
    print(f"\nwrote {args.out}")
    report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
