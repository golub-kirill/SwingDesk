"""`PR-032` - does the published intraday momentum rule still work on funds this project has never
read, in the years since the paper appeared?

**Why this and not more of `SPY`.** `PR-031` found the rule earning 8.5% a year on `SPY` over
2016-2026 at a Sharpe ratio of 1.01 - and **+0.0018% a day since publication**, a Sharpe ratio of
0.06 on 590 sessions. On `QQQ`, counted and never read there, it kept earning. Two stories fit: the
rule decayed everywhere when it was published, or `SPY`'s last two years are one fund's bad run.
They differ on funds nobody here has looked at.

**Three funds, chosen for what they are and not for how they did**: `IWM` (small caps), `DIA`
(thirty large caps, price-weighted) and `EFA` (developed markets outside the US). Each is liquid
enough to quote a one-cent spread, each has minutes back to 2016, and none has been read by any
tool in this repository. `SPY` and `QQQ` are `PR-031`'s and are not in the basket.

**The verdict reads the BASKET since publication**: equal capital across the three, each fund
traded by `PR-031`'s rule, long only, with `PR-031`'s costs and its no-look-ahead decision. The
funds one at a time, and the same basket BEFORE publication, are counted and never read.

    PYTHONPATH=$PWD/src python tools/run_pr032.py --minutes <store> --minutes-as-of <t> \
        --resamples 10000
    python tools/run_pr032.py --report
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr031 as p31
from run_pr016 import BLOCK, cluster_of
from swingdesk.market_data.minutes import MinuteStore
from swingdesk.reference_data import calendar as cal
from swingdesk.validation.backtest.intraday import session_for

RESULT = p31.RESULTS / "PR-032.json"
POWER = p31.RESULTS / "PR-032-power.json"

#: The funds, and the basket that carries the verdict. Long only, as `PR-031` ran them.
FUNDS = ("IWM", "DIA", "EFA")
BASKET = "basket"

#: The window: `PR-031`'s, read from the first session after the paper appeared. Sessions before it
#: are loaded for warm-up and reported as the secondary reading.
START = date(2016, 1, 4)
END = date(2026, 9, 18)
SINCE = date(2024, 5, 13)

BOOTSTRAP_SEED = 20260922
MIN_DAYS, MIN_MONTHS = 500, 24


def load_days(store: MinuteStore, instrument: str, as_of: datetime
              ) -> tuple[list[p31.Day], dict[str, int], int]:
    """Every session of the window the store holds for one fund, `PR-031`'s `Day` for each."""
    sessions = cal.sessions(cal.exchange_for(instrument), START, END)
    days: list[p31.Day] = []
    missing: dict[str, int] = defaultdict(int)
    for session in sessions:
        minutes = store.session(instrument, session.session_date, as_of)
        if minutes is None:
            missing["never_fetched"] += 1
            continue
        found = session_for(instrument, session.session_date)
        day = None if found is None else p31.build_day(minutes, found)
        if day is None:
            missing["no_regular_minutes"] += 1
        elif day.coverage < p31.MIN_COVERAGE:
            missing["thin"] += 1
        else:
            days.append(day)
    return days, dict(missing), len(sessions)


def basket_of(traded: Mapping[str, Sequence[p31.Traded]], costing: str,
              since: date | None = SINCE) -> dict[date, float]:
    """Equal capital across the funds: each session's mean over the funds that read it."""
    by_session: dict[date, list[float]] = defaultdict(list)
    for rows in traded.values():
        for row in rows:
            if since is None or row.session >= since:
                by_session[row.session].append(row.returns[costing])
    return {session: statistics.fmean(values) for session, values in by_session.items()}


def reading(returns: Mapping[date, float], resamples: int, sessions: int) -> dict[str, Any]:
    cell = dict(p31.clustered_mean(returns, resamples, BOOTSTRAP_SEED))
    cell["days"] = len(returns)
    cell["sessions"] = sessions
    cell["complete_share"] = len(returns) / sessions if sessions else 0.0
    cell["months"] = len({cluster_of(session) for session in returns})
    return cell


def branch_for(cell: Mapping[str, Any], adverse: Mapping[str, Any],
               floor: float = p31.POWER_FLOOR) -> str:
    if (cell["days"] < MIN_DAYS or cell["months"] < MIN_MONTHS
            or cell["complete_share"] < p31.MIN_COMPLETE_SHARE):
        return "REFUSED"
    if cell["lo"] > 0:
        return "ACCEPT" if adverse["lo"] > 0 else "COST_FRAGILE"
    if cell["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if cell["width"] > floor else "NULL"


def repeats_pr031(store: MinuteStore, as_of: datetime,
                  prior: Path = p31.RESULTS / "PR-031.json") -> dict[str, Any]:
    """`SPY` through THIS tool's loader must come back to `PR-031`'s own number.

    The rule, the walk and the costs are `PR-031`'s module; only the loading and the windowing are
    written here, and a defect in either would move every fund at once. `PR-031`'s reported estimate
    since publication is the fixed point that catches it.
    """
    if not prior.exists():
        return {"checked": False}
    days, _, _ = load_days(store, "SPY", as_of)
    rows, _ = p31.run_instrument(days, both=False)
    since = [row.returns["net"] for row in rows if row.session > p31.PUBLISHED]
    theirs = json.loads(prior.read_text(encoding="utf-8"))["cells"]["SPY-long"][
        "after_publication"]["estimate"]
    ours = statistics.fmean(since) if since else float("nan")
    return {"checked": True, "days": len(since), "differs_by": abs(ours - theirs)}


def build(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    store = MinuteStore(args.minutes)
    as_of = p31.read_instant(args.minutes_as_of, datetime.max.replace(tzinfo=UTC))
    traded: dict[str, list[p31.Traded]] = {}
    excluded: dict[str, dict[str, int]] = {}
    sessions: dict[str, int] = {}
    whole: dict[str, int] = {}
    held: dict[str, dict[str, float]] = {}
    for fund in FUNDS:
        days, missing, count = load_days(store, fund, as_of)
        rows, skipped = p31.run_instrument(days, both=False)
        since = [row for row in rows if row.session >= SINCE]
        traded[fund] = rows
        excluded[fund] = {**missing, **skipped}
        # The denominator is the CALENDAR's sessions, so an unfetched one counts against the share.
        sessions[fund] = len(cal.sessions(cal.exchange_for(fund), SINCE, END))
        whole[fund] = count
        held[fund] = p31.holding([d for d in days if d.session >= SINCE], since)
    repeats = repeats_pr031(store, as_of)
    store.close()

    counted = max(sessions.values(), default=0)
    cells: dict[str, Any] = {}
    for costing in p31.COSTS:
        name = BASKET if costing == "net" else f"{BASKET}-{costing}"
        cells[name] = reading(basket_of(traded, costing), resamples, counted)
    cells[f"{BASKET}-before-publication"] = reading(
        basket_of(traded, "net", since=None), resamples, max(whole.values(), default=0))
    for fund in FUNDS:
        rows = [row for row in traded[fund] if row.session >= SINCE]
        cells[fund] = reading({row.session: row.returns["net"] for row in rows}, resamples,
                              sessions[fund])
        cells[fund]["described"] = p31.described([row.returns["net"] for row in rows])
        cells[fund]["holding"] = held[fund]
        cells[fund]["mean_leverage"] = (statistics.fmean(row.leverage for row in rows) if rows
                                        else float("nan"))
        cells[fund]["days_traded"] = sum(1 for row in rows if row.trades)
    cells[BASKET]["described"] = p31.described(list(basket_of(traded, "net").values()))
    cells[f"{BASKET}-before-publication"]["described"] = p31.described(
        list(basket_of(traded, "net", since=None).values()))
    return {"as_of": {"minutes": as_of.isoformat()}, "cells": cells, "excluded": excluded,
            "reproduces_pr031": repeats}


def power(args: argparse.Namespace) -> dict[str, Any]:
    """Each reading's WIDTH before registration, and nothing else."""
    from power_pr019 import assert_no_effect_leaked

    built = build(args, p31.POWER_RESAMPLES)
    widths = {name: {"width": round(cell["width"], 6), "days": cell["days"]}
              for name, cell in built["cells"].items()}
    # The reproduction check is a DIFFERENCE from a published number, not a level of this study.
    built["reproduces_pr031"].pop("differs_by", None)
    payload = {"for": "PR-032", "as_of": built["as_of"], "resamples": p31.POWER_RESAMPLES,
               "widths": widths, "power_floor_width": p31.POWER_FLOOR}
    assert_no_effect_leaked(payload)
    return payload


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-032   verdict {payload['verdict']}   branch {payload['branch']}")
    print(f"  excluded {payload['excluded']}")
    print(f"  reproduces PR-031 {payload['reproduces_pr031']}")
    for name, cell in payload["cells"].items():
        print(f"  {name:<28} days {cell['days']:>5}  months {cell['months']:>3}  "
              f"complete {cell['complete_share']:.1%}   {p31._fmt(cell)}")  # noqa: SLF001
        if "described" in cell:
            print(f"      {cell['described']}")
        if "holding" in cell:
            print(f"      holding {cell['holding']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=Path, help="the minute store holding the three funds")
    parser.add_argument("--minutes-as-of", help="the minute store's knowledge instant")
    parser.add_argument("--resamples", type=int, default=p31.BOOTSTRAP_RESAMPLES,
                        help="bootstrap resamples; anything but the registered 10000 is a smoke run")
    parser.add_argument("--report", action="store_true", help="print the stored result")
    parser.add_argument("--power", action="store_true",
                        help="write each reading's interval width only, before registration")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.minutes is None:
        parser.error("--minutes is required")
    if args.power:
        estimate = power(args)
        POWER.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
        print(f"PR-032 power: widths {estimate['widths']}")
        return 0
    built = build(args, args.resamples)
    registered = args.resamples == p31.BOOTSTRAP_RESAMPLES
    branch = (branch_for(built["cells"][BASKET], built["cells"][f"{BASKET}-cost_adverse"])
              if registered else "SMOKE")
    payload: dict[str, Any] = {
        "prereg": "PR-032", "trials": 3, "verdict": p31.TOKEN[branch], "branch": branch,
        "country": "USA and developed markets", "as_of": built["as_of"],
        "measured_span": {"first_session": SINCE.isoformat(), "last_session": END.isoformat()},
        "split": {"registered": "none - PR-031's rule, unchanged, on three funds it never read",
                  "buys": "nothing a split could buy: no constant is chosen here"},
        "perturbations": {"registered": ["paper", "cost_adverse", "gross"],
                          "run": ["paper", "cost_adverse", "gross"]},
        "registered_settings": {"funds": FUNDS, "since": SINCE.isoformat(), "primary": BASKET,
                                "rule": "run_pr031, long only", "costs_per_share": p31.COSTS,
                                "bootstrap": {"unit": "month", "block": BLOCK,
                                              "seed": BOOTSTRAP_SEED, "resamples": args.resamples},
                                "power_floor": p31.POWER_FLOOR, "min_days": MIN_DAYS,
                                "min_months": MIN_MONTHS,
                                "min_complete_share": p31.MIN_COMPLETE_SHARE},
        **built,
    }
    if registered:
        RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
