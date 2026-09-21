"""`PR-035` - the same dollar twice: small caps overnight, `SPY` through the session, against holding
`SPY`.

**What the arithmetic already says, written before the run so the result cannot be claimed as a
surprise.** A book that owns small caps from the close to the next open and `SPY` from that open to
that close is *holding `SPY` with its night swapped*: the session legs are the same asset in the
same hours and cancel. So

    combined  =  hold SPY  -  SPY's night  +  small caps' night  -  the extra trading

and `PR-033` and `PR-034` have already measured every term: 15.68% a year, less 9.25%, plus 13.83%,
less about 0.4% for two more auction fills a day. **The question this study answers is not the
direction - it is whether the interval clears zero once the two legs are compounded session by
session, whether it survives a cent a share on four sides, and whether the book's Sharpe ratio
beats the index it is trying to replace.**

**The trap this run must not fall into.** A book holding `SPY` only through the session **never
receives its dividends**: a cash dividend detaches at the ex-date's OPEN, so it is paid to whoever
held overnight, which here is the small-cap leg. `run_pr033.returns_of` already pays each dividend
to the night arm and none to the session arm, so the drag is in the numbers rather than argued
around - and `SPY`'s own dividends are simply not earned by this book.

**Four fills a day, all at the two auctions:** sell the small caps and buy `SPY` at the opening
cross, sell `SPY` and buy the small caps at the closing cross. Nothing is traded inside a session.

    PYTHONPATH=$PWD/src python tools/run_pr035.py --minutes <store> --minutes-as-of <t> \
        --data <history store dir> --as-of <t> --resamples 10000
    python tools/run_pr035.py --report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr031 as p31
import run_pr033 as p33
import run_pr034 as p34
from run_pr016 import BLOCK, cluster_of
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import MinuteStore

RESULT = p31.RESULTS / "PR-035.json"
POWER = p31.RESULTS / "PR-035-power.json"

#: The night leg is PR-034's verdict basket; the session leg and the benchmark are SPY.
NIGHT_FUNDS = p34.SMALL
DAY_FUND = "SPY"
COMBINED, BENCHMARK = "combined", "hold-SPY"

BOOTSTRAP_SEED = 20260925
MIN_DAYS, MIN_MONTHS = 1000, 24

TOKEN = {**p34.TOKEN}


def compounded(night: Mapping[date, float], day: Mapping[date, float]) -> dict[date, float]:
    """One session of the book: the night it opened with, then the session it spent in `SPY`.

    Compounded rather than added, because the second leg is bought with what the first returned.
    """
    return {session: (1 + value) * (1 + day[session]) - 1
            for session, value in night.items() if session in day}


def excess(book: Mapping[date, float], held: Mapping[date, float]) -> dict[date, float]:
    return {session: value - held[session] for session, value in book.items() if session in held}


def reading(series: Mapping[date, float], resamples: int, sessions: int) -> dict[str, Any]:
    cell = dict(p31.clustered_mean(series, resamples, BOOTSTRAP_SEED))
    cell["days"] = len(series)
    cell["sessions"] = sessions
    cell["complete_share"] = len(series) / sessions if sessions else 0.0
    cell["months"] = len({cluster_of(session) for session in series})
    return cell


def branch_for(cell: Mapping[str, Any], adverse: Mapping[str, Any], recent: Mapping[str, Any],
               book: Mapping[str, float], held: Mapping[str, float],
               floor: float = p31.POWER_FLOOR) -> str:
    """`PR-034`'s order, with the benchmark being `SPY` rather than the funds the book holds."""
    if (cell["days"] < MIN_DAYS or cell["months"] < MIN_MONTHS
            or cell["complete_share"] < p31.MIN_COMPLETE_SHARE):
        return "REFUSED"
    if cell["lo"] > 0:
        if not adverse["lo"] > 0:
            return "COST_FRAGILE"
        if not recent["estimate"] > 0:
            return "RECENT_FRAGILE"
        if not book["sharpe"] > held["sharpe"]:
            return "NOT_BETTER_HELD"
        return "ACCEPT"
    if cell["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if cell["width"] > floor else "NULL"


def legs(args: argparse.Namespace
         ) -> tuple[dict[str, dict[date, float]], dict[str, float]]:
    """The night basket, `SPY`'s session, and holding `SPY` - each with its own costs and dividends."""
    minutes = MinuteStore(args.minutes)
    bars = BarStore(args.data / "bars.duckdb")
    minutes_as_of = p31.read_instant(args.minutes_as_of, datetime.max.replace(tzinfo=UTC))
    latest = bars.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC)
    bars_as_of = p31.read_instant(args.as_of, latest)

    nights: dict[str, dict[date, float]] = {}
    identity: dict[str, float] = {}
    for fund in NIGHT_FUNDS:
        dividends = p33.dividends_of(bars, fund, bars_as_of)
        sessions, _ = p34.load_sessions(minutes, fund, minutes_as_of, dividends)
        night, inside, held = p33.returns_of(sessions, args.per_share)
        nights[fund] = night
        if args.per_share == 0:
            identity[fund] = p33.adds_up(night, inside, held, dividends)

    spy_dividends = p33.dividends_of(bars, DAY_FUND, bars_as_of)
    spy_sessions, _ = p34.load_sessions(minutes, DAY_FUND, minutes_as_of, spy_dividends)
    spy_night, spy_day, spy_hold = p33.returns_of(spy_sessions, args.per_share)
    if args.per_share == 0:
        identity[DAY_FUND] = p33.adds_up(spy_night, spy_day, spy_hold, spy_dividends)
    minutes.close()
    bars.close()

    night_basket = p33.basket_of(nights)
    return ({"night": night_basket, "day": spy_day, "spy_night": spy_night, "hold": spy_hold,
             "combined": compounded(night_basket, spy_day)}, identity)


def build(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    series, identity = legs(args)
    counted = len(series["hold"])
    cells: dict[str, Any] = {}

    def add(name: str, values: Mapping[date, float], sessions: int = counted) -> None:
        cell = reading(values, resamples, sessions)
        cell["described"] = p31.described(list(values.values()))
        cells[name] = cell

    add(f"{COMBINED}-less-{BENCHMARK}", excess(series["combined"], series["hold"]))
    add(COMBINED, series["combined"])
    add(BENCHMARK, series["hold"])
    add("night-small-caps", series["night"])
    add("day-SPY", series["day"])
    add("night-SPY", series["spy_night"])
    recent = {s: v for s, v in excess(series["combined"], series["hold"]).items()
              if s >= p33.RECENT}
    add(f"{COMBINED}-less-{BENCHMARK}-recent", recent, len(recent))
    return {"as_of": {"minutes": args.minutes_as_of, "bars": args.as_of},
            "cells": cells, "arms_add_up_to_holding": identity,
            "per_share_cost": args.per_share}


def costed(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for costing, per_share in p31.COSTS.items():
        built = build(argparse.Namespace(**{**vars(args), "per_share": per_share}), resamples)
        key = f"{COMBINED}-less-{BENCHMARK}"
        if costing == "net":
            out = built
        else:
            out["cells"][f"{key}-{costing}"] = built["cells"][key]
            if costing == "gross":
                out["arms_add_up_to_holding"] = built["arms_add_up_to_holding"]
    return out


def power(args: argparse.Namespace) -> dict[str, Any]:
    """Each reading's WIDTH before registration, and nothing else."""
    from power_pr019 import assert_no_effect_leaked

    built = build(args, p31.POWER_RESAMPLES)
    widths = {name: {"width": round(cell["width"], 6), "days": cell["days"]}
              for name, cell in built["cells"].items()}
    payload = {"for": "PR-035", "as_of": built["as_of"], "resamples": p31.POWER_RESAMPLES,
               "widths": widths, "power_floor_width": p31.POWER_FLOOR}
    assert_no_effect_leaked(payload)
    return payload


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-035   verdict {payload['verdict']}   branch {payload['branch']}")
    print(f"  arms add up to holding, worst gap {payload.get('arms_add_up_to_holding')}")
    for name, cell in payload["cells"].items():
        print(f"  {name:<34} days {cell['days']:>5}  months {cell['months']:>3}   "
              f"{p31._fmt(cell)}")  # noqa: SLF001
        d = cell.get("described")
        if d:
            print(f"      a year {d['annual_mean']:+.2%}  vol {d['annual_volatility']:.2%}  "
                  f"sharpe {d['sharpe']:+.2f}  worst {d['max_drawdown']:+.1%}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=Path)
    parser.add_argument("--minutes-as-of")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--as-of")
    parser.add_argument("--per-share", type=float, default=p31.COSTS["net"])
    parser.add_argument("--resamples", type=int, default=p31.BOOTSTRAP_RESAMPLES)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--power", action="store_true")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.minutes is None or args.data is None:
        parser.error("--minutes and --data are required")
    if args.power:
        estimate = power(args)
        POWER.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
        print(f"PR-035 power: widths {estimate['widths']}")
        return 0
    built = costed(args, args.resamples)
    registered = args.resamples == p31.BOOTSTRAP_RESAMPLES
    key = f"{COMBINED}-less-{BENCHMARK}"
    branch = (branch_for(built["cells"][key], built["cells"][f"{key}-cost_adverse"],
                         built["cells"][f"{key}-recent"], built["cells"][COMBINED]["described"],
                         built["cells"][BENCHMARK]["described"])
              if registered else "SMOKE")
    payload: dict[str, Any] = {
        "prereg": "PR-035", "trials": 1, "verdict": TOKEN[branch], "branch": branch,
        "country": "USA", "as_of": built["as_of"],
        "measured_span": {"first_session": p33.START.isoformat(),
                          "last_session": p33.END.isoformat()},
        "split": {"registered": "none - one book, one benchmark, both legs already measured",
                  "buys": "nothing a split could buy: no constant is chosen here"},
        "perturbations": {"registered": ["paper", "cost_adverse", "gross"],
                          "run": ["paper", "cost_adverse", "gross"]},
        "registered_settings": {
            "night_funds": list(NIGHT_FUNDS), "day_fund": DAY_FUND, "benchmark": BENCHMARK,
            "primary": key, "recent_since": p33.RECENT.isoformat(),
            "costs_per_share": p31.COSTS, "sides_a_day": 4,
            "gates": ["cost_adverse above zero", "recent estimate above zero",
                      "sharpe above holding SPY's"],
            "bootstrap": {"unit": "month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                          "resamples": args.resamples},
            "power_floor": p31.POWER_FLOOR, "min_days": MIN_DAYS, "min_months": MIN_MONTHS,
            "min_complete_share": p31.MIN_COMPLETE_SHARE},
        **built,
    }
    if registered:
        RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
