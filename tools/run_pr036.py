"""`PR-036` - did the night pay BEFORE 2016? The same two arms, on daily bars, back to 2000.

**Why this exists and why it is the study that could kill the whole line.** `PR-033`..`PR-035`
measured 2016-2026 because that is where the minute feed starts, and `SPY` returned 15.7% a year
over that decade. An advisor put the objection plainly: *what does the overnight book do in a decade
where the index returns nothing?* Without that number the result could be a wrapper around an
exceptional epoch rather than an effect.

**The two prices the arms need are in the DAILY bars**, and those go back to 1993 for `SPY`, 2000
for `IJR` and 2004 for `VB`: the night is the next open over this close, the session is this close
over this open. No minute is needed, nothing is fetched, and the untouched window - 2000-01 to
2015-12 - holds the dot-com unwind, 2008, and a decade in which the index went nowhere.

**The method must prove itself before it is believed.** A daily bar's open and close are the
vendor's consolidated prices, not the auction prints the minute feed carries. So this runner's
FIRST output is not the answer: it is the same reading over 2016-2026, which must reproduce
`PR-034`'s minute-based night. If it does not, the pre-2016 number means nothing and the study says
so (section 9).

**No new configuration.** The rule, the funds, the weighting and the costs are `PR-034`'s. Only the
window and the price source change, so this spends no trial - it is a replication on a sample
nobody here has read.

    PYTHONPATH=$PWD/src python tools/run_pr036.py --data <history store dir> --as-of <t> \
        --resamples 10000
    python tools/run_pr036.py --report
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
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore

RESULT = p31.RESULTS / "PR-036.json"
POWER = p31.RESULTS / "PR-036-power.json"

FUNDS = p34.SMALL
BASKET = "small"
NIGHT, SESSION = p33.NIGHT, p33.SESSION

#: The untouched window: from the first session both funds trade to the day before the minute
#: feed - and PR-033..PR-035 - begin. The overlap window is PR-034's own.
BEFORE_FIRST = date(2004, 1, 30)
BEFORE_LAST = date(2015, 12, 31)
OVERLAP_FIRST = date(2016, 1, 4)
OVERLAP_LAST = date(2026, 9, 18)

BOOTSTRAP_SEED = 20260926
MIN_DAYS, MIN_MONTHS = 1000, 24

TOKEN = {**p34.TOKEN}


def sessions_from_bars(store: BarStore, fund: str, as_of: datetime) -> list[p33.Session]:
    """Every stored daily bar as a `PR-033` session, with its ex-date dividend attached."""
    dividends = p33.dividends_of(store, fund, as_of)
    series = store.as_of(fund, Interval.DAY, Series.RAW, as_of)
    if series is None:
        return []
    return [p33.Session(session=bar.session_date, open=float(bar.open), close=float(bar.close),
                        dividend=dividends.get(bar.session_date, 0.0))
            for bar in series.bars]


def within(series: Mapping[date, float], first: date, last: date) -> dict[date, float]:
    return {day: value for day, value in series.items() if first <= day <= last}


def reading(series: Mapping[date, float], resamples: int, sessions: int) -> dict[str, Any]:
    cell: dict[str, Any] = dict(p31.clustered_mean(series, resamples, BOOTSTRAP_SEED))
    cell["days"] = len(series)
    cell["sessions"] = sessions
    cell["complete_share"] = len(series) / sessions if sessions else 0.0
    cell["months"] = len({cluster_of(day) for day in series})
    cell["described"] = p31.described(list(series.values()))
    return cell


def branch_for(cell: Mapping[str, Any], adverse: Mapping[str, Any], night: Mapping[str, float],
               held: Mapping[str, float], floor: float = p31.POWER_FLOOR) -> str:
    """`PR-034`'s order without the recency gate: this window IS the old one."""
    if (cell["days"] < MIN_DAYS or cell["months"] < MIN_MONTHS
            or cell["complete_share"] < p31.MIN_COMPLETE_SHARE):
        return "REFUSED"
    if cell["lo"] > 0:
        if not adverse["lo"] > 0:
            return "COST_FRAGILE"
        if not night["sharpe"] > held["sharpe"]:
            return "NOT_BETTER_HELD"
        return "ACCEPT"
    if cell["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if cell["width"] > floor else "NULL"


def build(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    latest = store.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC)
    as_of = p31.read_instant(args.as_of, latest)
    arms: dict[str, dict[str, dict[date, float]]] = {NIGHT: {}, SESSION: {}, "hold": {}}
    identity: dict[str, float] = {}
    for fund in FUNDS:
        sessions = sessions_from_bars(store, fund, as_of)
        night, inside, held = p33.returns_of(sessions, args.per_share)
        arms[NIGHT][fund], arms[SESSION][fund], arms["hold"][fund] = night, inside, held
        if args.per_share == 0:
            identity[fund] = p33.adds_up(night, inside, held,
                                         {s.session: s.dividend for s in sessions})
    store.close()

    baskets = {arm: p33.basket_of(arms[arm]) for arm in (NIGHT, SESSION, "hold")}
    cells: dict[str, Any] = {}
    for label, first, last in (("before", BEFORE_FIRST, BEFORE_LAST),
                               ("overlap", OVERLAP_FIRST, OVERLAP_LAST)):
        for arm, name in ((NIGHT, "N"), (SESSION, "D"), ("hold", "hold")):
            window = within(baskets[arm], first, last)
            cells[f"{BASKET}-{name}-{label}"] = reading(window, resamples, len(window))
    for fund in FUNDS:
        window = within(arms[NIGHT][fund], BEFORE_FIRST, BEFORE_LAST)
        cells[f"{fund}-N-before"] = reading(window, resamples, len(window))
    return {"as_of": {"bars": as_of.isoformat()}, "cells": cells,
            "arms_add_up_to_holding": identity, "per_share_cost": args.per_share}


def costed(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    key = f"{BASKET}-N-before"
    for costing, per_share in p31.COSTS.items():
        built = build(argparse.Namespace(**{**vars(args), "per_share": per_share}), resamples)
        if costing == "net":
            out = built
        else:
            out["cells"][f"{key}-{costing}"] = built["cells"][key]
            if costing == "gross":
                out["arms_add_up_to_holding"] = built["arms_add_up_to_holding"]
    return out


def reproduces_pr034(payload: Mapping[str, Any],
                     prior: Path = p31.RESULTS / "PR-034.json") -> dict[str, Any]:
    """The overlap window read from DAILY bars against `PR-034`'s minute-based night.

    The check the pre-2016 number depends on: a daily bar's open and close are the vendor's
    consolidated prices, not the auction prints the minute feed carries, so the two can differ.
    How far they differ here is how far the older reading may be trusted.
    """
    if not prior.exists():
        return {"checked": False}
    theirs = json.loads(prior.read_text(encoding="utf-8"))["cells"]["small-N"]["described"]
    ours = payload["cells"][f"{BASKET}-N-overlap"]["described"]
    return {"checked": True,
            "daily_bars_annual": round(ours["annual_mean"], 5),
            "minutes_annual": round(theirs["annual_mean"], 5),
            "differ_by": round(abs(ours["annual_mean"] - theirs["annual_mean"]), 5)}


def power(args: argparse.Namespace) -> dict[str, Any]:
    from power_pr019 import assert_no_effect_leaked

    built = build(args, p31.POWER_RESAMPLES)
    widths = {name: {"width": round(cell["width"], 6), "days": cell["days"]}
              for name, cell in built["cells"].items()}
    payload = {"for": "PR-036", "as_of": built["as_of"], "resamples": p31.POWER_RESAMPLES,
               "widths": widths, "power_floor_width": p31.POWER_FLOOR}
    assert_no_effect_leaked(payload)
    return payload


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-036   verdict {payload['verdict']}   branch {payload['branch']}")
    print(f"  arms add up to holding {payload.get('arms_add_up_to_holding')}")
    print(f"  reproduces PR-034 {payload.get('reproduces_pr034')}")
    for name, cell in payload["cells"].items():
        print(f"  {name:<26} days {cell['days']:>5}  months {cell['months']:>3}   "
              f"{p31._fmt(cell)}")  # noqa: SLF001
        d = cell.get("described")
        if d:
            print(f"      a year {d['annual_mean']:+.2%}  vol {d['annual_volatility']:.2%}  "
                  f"sharpe {d['sharpe']:+.2f}  worst {d['max_drawdown']:+.1%}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb with actions")
    parser.add_argument("--as-of", help="the bar store's knowledge instant")
    parser.add_argument("--per-share", type=float, default=p31.COSTS["net"])
    parser.add_argument("--resamples", type=int, default=p31.BOOTSTRAP_RESAMPLES)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--power", action="store_true")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.data is None:
        parser.error("--data is required")
    if args.power:
        estimate = power(args)
        POWER.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
        print(f"PR-036 power: widths {estimate['widths']}")
        return 0
    built = costed(args, args.resamples)
    registered = args.resamples == p31.BOOTSTRAP_RESAMPLES
    key = f"{BASKET}-N-before"
    branch = (branch_for(built["cells"][key], built["cells"][f"{key}-cost_adverse"],
                         built["cells"][key]["described"],
                         built["cells"][f"{BASKET}-hold-before"]["described"])
              if registered else "SMOKE")
    payload: dict[str, Any] = {
        "prereg": "PR-036", "trials": 0, "verdict": TOKEN[branch], "branch": branch,
        "country": "USA", "as_of": built["as_of"],
        "measured_span": {"first_session": BEFORE_FIRST.isoformat(),
                          "last_session": BEFORE_LAST.isoformat()},
        "split": {"registered": "none - PR-034's rule on a window nobody here has read",
                  "buys": "nothing a split could buy: no constant is chosen here"},
        "perturbations": {"registered": ["paper", "cost_adverse", "gross"],
                          "run": ["paper", "cost_adverse", "gross"]},
        "registered_settings": {
            "funds": list(FUNDS), "primary": key, "price_source": "daily bars, open and close",
            "before": [BEFORE_FIRST.isoformat(), BEFORE_LAST.isoformat()],
            "overlap": [OVERLAP_FIRST.isoformat(), OVERLAP_LAST.isoformat()],
            "costs_per_share": p31.COSTS,
            "gates": ["cost_adverse above zero", "sharpe above holding's"],
            "bootstrap": {"unit": "month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                          "resamples": args.resamples},
            "power_floor": p31.POWER_FLOOR, "min_days": MIN_DAYS, "min_months": MIN_MONTHS,
            "min_complete_share": p31.MIN_COMPLETE_SHARE},
        **built,
    }
    payload["reproduces_pr034"] = reproduces_pr034(payload)
    if registered:
        RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
