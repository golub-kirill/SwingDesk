"""`PR-023`: five asset classes, each held above its ten-month average and in T-bills below, against SPY.

**Why this is next, and why it is not `PR-022` again.** Every study here held US equities only, and
`PR-022` found one index with a trend exit matched the index per unit of risk - on an instrument that
could not tell +/-0.38 of Sharpe apart. The published case for trend rules is not one index; it is
many markets at once (Hurst, Ooi & Pedersen 2017), and Faber's (2007) headline strategy is exactly
that - the same ten-month rule applied to five asset classes, a fifth each:

* **SPY** US stocks, **EFA** developed stocks outside the US, **IEF** 7-10 year Treasuries, **VNQ** US
  real estate, **DBC** commodities;
* each held while its month-end close is above the mean of its last ten, its fifth in **BIL**
  otherwise; rebalanced to those targets at each month's first open, `DR-005` charged on every unit
  traded - a sale and a purchase are a fill each.

**Two arms, both registered and both counted.** `TIMED_5` is the rule; `HOLD_5` is the same five, a
fifth each, rebalanced monthly and never timed - what diversification does without the rule.
`TIMED_5` carries the study's verdict.

**The statistic is the Sharpe ratio of the excess return over `BIL`**, not `stats.sharpe_convention`'s
rf = 0: a book paid the T-bill yield a fifth of the time or more has that yield counted as reward for
risk under rf = 0, and `PR-022`'s own difference moved from +0.011 to -0.027 when it was removed. The
convention is reported beside it.

    PYTHONPATH=$PWD/src python tools/run_pr023.py --data <store directory> --as-of <instant>
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr022 import (
    BLOCK,
    MIN_MONTHS,
    POWER_FLOOR,
    RECENT_MONTHS,
    SESSIONS_PER_YEAR,
    TOKEN,
    Paths,
    branch_for,
    cagr,
    drawdown,
    episodes,
    mean_difference,
    month_ends,
    per_year,
    sharpe,
    sharpe_readings,
    window_start,
)
from swingdesk.contracts.market import CorporateActionKind, Interval, Series
from swingdesk.market_data import BarStore

#: Faber's (2007) five, as exchange-traded funds that existed before the window opens.
ASSETS = ("SPY", "EFA", "IEF", "VNQ", "DBC")
CASH = "BIL"
BENCHMARK = "SPY"
SMA_MONTHS = 10

#: `DR-005`, 25 bps of price on each fill.
SLIPPAGE_BPS = 25.0
STRESS_MULTIPLE = 3.0

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260915

ARMS = ("TIMED_5", "HOLD_5")
PRIMARY_ARM = "TIMED_5"

RESULT = REPO / "docs" / "prereg" / "results" / "PR-023.json"

NAN = float("nan")


@dataclass
class Market:
    """Every instrument on the benchmark's calendar; `nan` where one has no bar."""

    calendar: list[date]
    opens: dict[str, list[float]]
    closes: dict[str, list[float]]
    dividends: dict[str, dict[date, float]]


def load(store: BarStore, as_of: datetime) -> Market:
    spy = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    calendar = [bar.session_date for bar in spy.bars]
    market = Market(calendar, {}, {}, {})
    for name in (*ASSETS, CASH):
        by_day = {bar.session_date: bar for bar in store.as_of(name, Interval.DAY, Series.RAW, as_of).bars}
        market.opens[name] = [float(by_day[d].open) if d in by_day else NAN for d in calendar]
        market.closes[name] = [float(by_day[d].close) if d in by_day else NAN for d in calendar]
        paid: dict[date, float] = {}
        for action in store.actions_as_of(name, as_of):
            if action.kind is CorporateActionKind.DIVIDEND:
                paid[action.effective_date] = paid.get(action.effective_date, 0.0) + float(action.value)
        market.dividends[name] = paid
    return market


def signals_for(market: Market, name: str, ends: Sequence[int]) -> dict[int, bool]:
    """Month-end index -> above its ten-month average. A month with no close decides nothing."""
    closes = market.closes[name]
    decided: dict[int, bool] = {}
    for k in range(SMA_MONTHS - 1, len(ends)):
        window = [closes[ends[j]] for j in range(k - SMA_MONTHS + 1, k + 1)]
        if any(math.isnan(value) for value in window):
            continue
        decided[ends[k]] = closes[ends[k]] > statistics.fmean(window)
    return decided


def targets(arm: str, month_end: int, decided: dict[str, dict[int, bool]]) -> dict[str, float]:
    """The book's weights for the month after `month_end`. A timed fifth below its average is cash."""
    share = 1.0 / len(ASSETS)
    out: dict[str, float] = {}
    for name in ASSETS:
        held = name if arm == "HOLD_5" or decided[name][month_end] else CASH
        out[held] = out.get(held, 0.0) + share
    return out


def first_decision(market: Market, ends: Sequence[int], decided: dict[str, dict[int, bool]]) -> int:
    """The first month-end every asset has decided at and whose next open the cash fund prices."""
    for end in ends[:-1]:
        if all(end in decided[name] for name in ASSETS) and not math.isnan(market.opens[CASH][end + 1]):
            return end
    raise SystemExit("no month-end has all five assets decided and the cash fund priced after it")


@dataclass
class Book:
    """One arm's daily total returns, and what it traded."""

    sessions: list[date] = field(default_factory=list)
    returns: list[float] = field(default_factory=list)
    risky_share: list[float] = field(default_factory=list)
    traded: float = 0.0
    rebalances: int = 0
    switches: int = 0
    unpriced: int = 0


def _step(weights: dict[str, float], gains: dict[str, float]) -> tuple[float, dict[str, float]]:
    """(the book's return, its weights after the move). Weights sum to one before and after."""
    total = sum(weights[name] * gains[name] for name in weights)
    return total, {name: weights[name] * (1.0 + gains[name]) / (1.0 + total) for name in weights}


def _gain(value: float, out: Book) -> float:
    if math.isnan(value):
        out.unpriced += 1
        return 0.0
    return value


def _prior(closes: list[float], d: int) -> float:
    """The last close before session `d`. A session with no bar leaves the holding where it was, so
    the move across it is earned on the next session that prices it - once, and counted once."""
    k = d - 1
    while k > 0 and math.isnan(closes[k]):
        k -= 1
    return closes[k]


def simulate(market: Market, arm: str, decided: dict[str, dict[int, bool]], start_end: int,
             cost_multiple: float = 1.0, last: int | None = None) -> Book:
    """One arm from the open of the session after `start_end`.

    On the first session after each month-end the book first earns the night with the weights it
    drifted to - a dividend with that ex-date belongs to whoever held at the prior close - then
    trades to the month's targets at the open, paying a fill on every unit bought or sold, and earns
    open to close with the targets. Other sessions are close to close with drifting weights.
    """
    rate = SLIPPAGE_BPS * cost_multiple / 10_000.0
    calendar, opens, closes, dividends = market.calendar, market.opens, market.closes, market.dividends
    ends = set(month_ends(calendar))
    out = Book()
    stop = len(calendar) - 1 if last is None else last
    begin = start_end + 1
    weights: dict[str, float] = {}
    previous_end = start_end
    for d in range(begin, stop + 1):
        day = calendar[d]
        if d == begin:
            weights = targets(arm, start_end, decided)
            day_return, weights = _step(weights, {
                n: _gain(closes[n][d] / opens[n][d] - 1.0, out) for n in weights})
        elif d - 1 in ends:
            night, weights = _step(weights, {
                n: _gain((opens[n][d] + dividends[n].get(day, 0.0)) / _prior(closes[n], d) - 1.0, out)
                for n in weights})
            goal = targets(arm, d - 1, decided)
            traded = sum(abs(goal.get(n, 0.0) - weights.get(n, 0.0)) for n in set(goal) | set(weights))
            day_part, weights = _step(goal, {n: _gain(closes[n][d] / opens[n][d] - 1.0, out) for n in goal})
            day_return = (1.0 + night) * (1.0 - traded * rate) * (1.0 + day_part) - 1.0
            out.traded += traded
            out.rebalances += 1
            if arm == "TIMED_5":
                out.switches += sum(decided[n][d - 1] != decided[n][previous_end] for n in ASSETS)
            previous_end = d - 1
        else:
            day_return, weights = _step(weights, {
                n: _gain((closes[n][d] + dividends[n].get(day, 0.0)) / _prior(closes[n], d) - 1.0, out)
                for n in weights})
        out.sessions.append(day)
        out.returns.append(day_return)
        out.risky_share.append(1.0 - weights.get(CASH, 0.0))
    return out


def held(market: Market, name: str, start_end: int, last: int | None = None) -> list[float]:
    """One fund held from the same open, total return, no cost - the benchmark and the cash leg."""
    calendar, opens, closes, dividends = market.calendar, market.opens, market.closes, market.dividends
    stop = len(calendar) - 1 if last is None else last
    begin = start_end + 1
    out = [closes[name][begin] / opens[name][begin] - 1.0]
    for d in range(begin + 1, stop + 1):
        out.append((closes[name][d] + dividends[name].get(calendar[d], 0.0)) / closes[name][d - 1] - 1.0)
    return out


def minus(left: Sequence[float], right: Sequence[float]) -> list[float]:
    return [a - b for a, b in zip(left, right, strict=True)]


def readings(sessions: list[date], book: list[float], spy: list[float], cash: list[float],
             resamples: int) -> dict[str, Any]:
    """Every figure for one arm over one span. §6 reads `sharpe` and, on an ACCEPT, the stress point."""
    years = len(book) / SESSIONS_PER_YEAR
    paths = Paths(sessions, list(book), list(spy), [True] * len(book))
    return {
        "sessions": len(book),
        "months": len({(d.year, d.month) for d in sessions}),
        "sharpe": sharpe_readings(minus(book, cash), minus(spy, cash), resamples, seed=BOOTSTRAP_SEED),
        "sharpe_rf0": {"book": sharpe(book), "spy": sharpe(spy), "difference": sharpe(book) - sharpe(spy)},
        "mean_difference_points": mean_difference(book, spy, resamples),
        "cagr": {"book": cagr(book), "spy": cagr(spy), "cash": cagr(cash)},
        "volatility": {"book": statistics.stdev(book) * math.sqrt(SESSIONS_PER_YEAR),
                       "spy": statistics.stdev(spy) * math.sqrt(SESSIONS_PER_YEAR)},
        "max_drawdown": {"book": drawdown(book, sessions), "spy": drawdown(spy, sessions)},
        "episodes": episodes(paths),
        "years": years,
    }


def arm_cell(market: Market, arm: str, decided: dict[str, dict[int, bool]], start_end: int,
             spy: list[float], cash: list[float], cut: int, resamples: int) -> dict[str, Any]:
    net = simulate(market, arm, decided, start_end, 1.0)
    gross = simulate(market, arm, decided, start_end, 0.0)
    stressed = simulate(market, arm, decided, start_end, STRESS_MULTIPLE)
    cell = readings(net.sessions, net.returns, spy, cash, resamples)
    excess_spy = minus(spy, cash)
    cell["gross_difference_point"] = sharpe(minus(gross.returns, cash)) - sharpe(excess_spy)
    cell["stress_difference_point"] = sharpe(minus(stressed.returns, cash)) - sharpe(excess_spy)
    cell["risky_share"] = statistics.fmean(net.risky_share)
    cell["traded_a_year"] = net.traded / cell["years"]
    cell["cost_points_a_year"] = net.traded / cell["years"] * SLIPPAGE_BPS / 100.0
    cell["switches"] = net.switches
    cell["rebalances"] = net.rebalances
    cell["unpriced"] = net.unpriced
    cell["per_year"] = per_year(Paths(net.sessions, net.returns, spy, [True] * len(spy)))
    cell["recent_48_months"] = readings(net.sessions[cut:], net.returns[cut:], spy[cut:], cash[cut:],
                                        resamples)
    cell["branch"] = branch_for(cell)
    return cell


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
    recent_from = window_start(as_of.date(), RECENT_MONTHS)
    cut = next(i for i, d in enumerate(sessions) if d >= recent_from)
    cells = {arm: arm_cell(market, arm, decided, start, spy, cash, cut, args.resamples) for arm in ARMS}
    governing = [e for e in ends if start <= e < len(market.calendar) - 1]
    assets = {name: {"cagr": cagr(held(market, name, start)),
                     "months_above_average": sum(decided[name][e] for e in governing),
                     "months": len(governing)}
              for name in ASSETS}
    registered = args.resamples == BOOTSTRAP_RESAMPLES
    branch = cells[PRIMARY_ARM]["branch"]
    return {
        "prereg": "PR-023",
        "trials": len(ARMS),
        "country": "USA",
        "as_of": as_of.isoformat(),
        "registered_settings": registered,
        "rule": {"assets": list(ASSETS), "cash": CASH, "sma_months": SMA_MONTHS, "weight": "a fifth each",
                 "evaluated": "each month's last session close, per asset; equality is cash",
                 "executed": "rebalanced to targets at the next session's open",
                 "slippage_bps_a_fill": SLIPPAGE_BPS,
                 "statistic": "Sharpe of the daily excess return over BIL, x sqrt(252)"},
        "window": {"first_decision": market.calendar[start].isoformat(),
                   "start": sessions[0].isoformat(), "end": sessions[-1].isoformat()},
        "measured_span": {"first_session": sessions[0].isoformat(), "last_session": sessions[-1].isoformat(),
                          "years": round((sessions[-1] - sessions[0]).days / 365.25, 2)},
        "split": {"registered": "none",
                  "buys": "nothing is selected - two arms fixed before the run, both read, neither chosen "
                          "- so a split would halve nineteen years for a protection there is nothing "
                          "to protect (PREREG_TEMPLATE 7)"},
        "perturbations": {"registered": ["cost_stress_3x"], "run": ["cost_stress_3x"]},
        "inference": {"block": BLOCK, "resamples": args.resamples, "seed": BOOTSTRAP_SEED,
                      "power_floor_sharpe": POWER_FLOOR, "min_months": MIN_MONTHS},
        "assets": assets,
        "cells": cells,
        "recent_from": recent_from.isoformat(),
        "branch": branch if registered else "SMOKE",
        "verdict": TOKEN[branch] if registered else "smoke",
    }


def _interval(reading: dict[str, float], digits: int = 3) -> str:
    return f"{reading['point']:+.{digits}f} [{reading['lo']:+.{digits}f}, {reading['hi']:+.{digits}f}]"


def _block(label: str, cell: dict[str, Any]) -> None:
    s = cell["sharpe"]
    print(f"\n  {label}")
    print(f"    excess Sharpe difference {_interval(s['difference'])}   width {s['difference']['width']:.3f}")
    print(f"    excess Sharpe book / SPY {_interval(s['timed'])}  /  {_interval(s['held'])}")
    print(f"    rf = 0 difference        {cell['sharpe_rf0']['difference']:+.3f}")
    print(f"    mean difference, points  {_interval(cell['mean_difference_points'], 2)}")
    c, v = cell["cagr"], cell["volatility"]
    print(f"    CAGR book / SPY / BIL    {c['book']:+.2%} / {c['spy']:+.2%} / {c['cash']:+.2%}")
    print(f"    volatility book / SPY    {v['book']:.1%} / {v['spy']:.1%}")
    b, h = cell["max_drawdown"]["book"], cell["max_drawdown"]["spy"]
    print(f"    worst drawdown           {b['depth']:.1%} ({b['peak']}..{b['trough']}) / "
          f"{h['depth']:.1%} ({h['peak']}..{h['trough']})")


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-023 - five asset classes, timed and held, against SPY\n{'=' * 72}")
    print(f"  as_of {payload['as_of']}   window {payload['window']['start']} .. {payload['window']['end']}"
          f"   ({payload['measured_span']['years']} years)")
    for name, a in payload["assets"].items():
        print(f"    {name:4} CAGR {a['cagr']:+.2%}   above its average {a['months_above_average']} of "
              f"{a['months']} months")
    for arm, cell in payload["cells"].items():
        _block(f"{arm} - registered window - branch {cell['branch']}", cell)
        print(f"    risky share {cell['risky_share']:.1%}   traded {cell['traded_a_year']:.2f} a year   "
              f"cost {cell['cost_points_a_year']:.2f} points a year   switches {cell['switches']}   "
              f"unpriced {cell['unpriced']}")
        print(f"    difference gross {cell['gross_difference_point']:+.3f}   at 3x DR-005 "
              f"{cell['stress_difference_point']:+.3f}")
        for e in cell["episodes"]:
            print(f"      {e['peak']} -> {e['trough']}   SPY {e['held_fall']:+.1%}   book "
                  f"{e['timed_over_the_fall']:+.1%} (worst inside {e['timed_worst_inside']:+.1%})   "
                  f"recovery SPY {e['held_recovery']:+.1%} book {e['timed_over_the_recovery']:+.1%}")
        _block(f"{arm} - last 48 months (diagnostic)", cell["recent_48_months"])
        print("    per year, book / SPY: " + "  ".join(
            f"{y} {r['timed']:+.1%}/{r['held']:+.1%}" for y, r in cell["per_year"].items()))
    print(f"\n  study branch ({PRIMARY_ARM}) {payload['branch']}   verdict {payload['verdict']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data",
                        help="directory holding the bars.duckdb with the five funds and BIL")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true",
                        help="re-read an existing result instead of running it")
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES,
                        help="smoke tests only; anything but 10,000 emits no verdict")
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
