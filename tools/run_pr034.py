"""`PR-034` - small caps' night, asked properly: on funds `PR-033` never read, at a cent a share,
against holding them.

**What `PR-033` left.** Splitting the calendar day on five index funds, the night earned +8.2% a
year and the session +3.4% - and the night's Sharpe ratio, 0.67, sat under holding the same basket,
0.81. **`IWM` was the exception**: its night earned +13.1% a year at 0.91 while its session LOST
3.3%, against holding's 0.56. That was one of ten arms and it was read after the fact, so it is a
lead and not a finding.

**This asks it as a hypothesis.** `IJR` (S&P SmallCap 600) and `VB` (Vanguard's small caps) carry
the verdict as an equally weighted basket; `MDY` (S&P MidCap 400) is the boundary case, counted and
never read. None has been read by anything in this repository.

**What is honestly new here, and what is not.** A different wrapper on largely the same asset class
is NOT an independent sample of small-cap returns: `IJR` and `IWM` hold overlapping companies, and
if the night pays in small caps it pays in both. What these funds test is whether `IWM`'s reading
was its own - its liquidity, its wrapper, its index's quirks - and whether the effect survives the
two gates `PR-033` failed: **a whole cent a share a side**, and **beating the fund held outright per
unit of risk**. Both are registered as gates on `ACCEPT`, not as diagnostics.

Everything else is `PR-033`'s module, imported unchanged: the two arms, the dividend paid to the
night, the costs, the bootstrap and the identity check.

    PYTHONPATH=$PWD/src python tools/run_pr034.py --minutes <store> --minutes-as-of <t> \
        --data <history store dir> --as-of <t> --resamples 10000
    python tools/run_pr034.py --report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr031 as p31
import run_pr033 as p33
from run_pr016 import BLOCK, cluster_of
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import MinuteStore
from swingdesk.reference_data import calendar as cal
from swingdesk.validation.backtest.intraday import regular_hours, session_for

RESULT = p31.RESULTS / "PR-034.json"
POWER = p31.RESULTS / "PR-034-power.json"

#: The verdict's funds, and the boundary case that is counted and never read.
SMALL = ("IJR", "VB")
BOUNDARY = ("MDY",)
FUNDS = (*SMALL, *BOUNDARY)
BASKET = "small"
NIGHT, SESSION = p33.NIGHT, p33.SESSION

BOOTSTRAP_SEED = 20260924
MIN_DAYS, MIN_MONTHS = 1000, 24

TOKEN = {**p33.TOKEN, "NOT_BETTER_HELD": "inconclusive"}


#: How far from the bell the session's first and last stored minute may sit. `PR-033` read every
#: minute of the session and so required 90% coverage; this reads TWO prices, the open and the
#: close, and a fund whose middle minutes hold no trade has neither price missing. Measured on
#: every seventh session of the window before registration: `VB`'s median coverage is 0.877 and
#: `MDY`'s 0.928, which `PR-033`'s rule would have thrown away - 61% and 36% of their sessions -
#: while the opening minute and the closing minute are present on 100% of them.
BELL = 5


def load_sessions(store: MinuteStore, fund: str, as_of: datetime,
                  dividends: Mapping[date, float]) -> tuple[list[p33.Session], dict[str, int]]:
    """Every session whose first and last stored minute sit at the bells, with its dividend."""
    missing: dict[str, int] = defaultdict(int)
    out: list[p33.Session] = []
    for session in cal.sessions(cal.exchange_for(fund), p33.START, p33.END):
        minutes = store.session(fund, session.session_date, as_of)
        if minutes is None:
            missing["never_fetched"] += 1
            continue
        found = session_for(fund, session.session_date)
        regular = [] if found is None else regular_hours(minutes, found)
        if found is None or not regular:
            missing["no_regular_minutes"] += 1
            continue
        length = int((found.close_time - found.open_time) / timedelta(minutes=1))
        first = int((regular[0].at - found.open_time) / timedelta(minutes=1))
        last = length - 1 - int((regular[-1].at - found.open_time) / timedelta(minutes=1))
        if first > BELL:
            missing["no_opening_minute"] += 1
        elif last > BELL:
            missing["no_closing_minute"] += 1
        else:
            out.append(p33.Session(session=session.session_date, open=float(regular[0].open),
                                   close=float(regular[-1].close),
                                   dividend=dividends.get(session.session_date, 0.0)))
    return out, dict(missing)


def reading(series: Mapping[date, float], resamples: int, sessions: int) -> dict[str, Any]:
    """`PR-033`'s reading under this study's own bootstrap seed."""
    cell = dict(p31.clustered_mean(series, resamples, BOOTSTRAP_SEED))
    cell["days"] = len(series)
    cell["sessions"] = sessions
    cell["complete_share"] = len(series) / sessions if sessions else 0.0
    cell["months"] = len({cluster_of(session) for session in series})
    return cell


def branch_for(cell: Mapping[str, Any], adverse: Mapping[str, Any], recent: Mapping[str, Any],
               night: Mapping[str, float], held: Mapping[str, float],
               floor: float = p31.POWER_FLOOR) -> str:
    """`PR-033`'s order with one gate added: an `ACCEPT` must beat holding per unit of risk."""
    if (cell["days"] < MIN_DAYS or cell["months"] < MIN_MONTHS
            or cell["complete_share"] < p31.MIN_COMPLETE_SHARE):
        return "REFUSED"
    if cell["lo"] > 0:
        if not adverse["lo"] > 0:
            return "COST_FRAGILE"
        if not recent["estimate"] > 0:
            return "RECENT_FRAGILE"
        if not night["sharpe"] > held["sharpe"]:
            return "NOT_BETTER_HELD"
        return "ACCEPT"
    if cell["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if cell["width"] > floor else "NULL"


def build(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    minutes = MinuteStore(args.minutes)
    bars = BarStore(args.data / "bars.duckdb")
    minutes_as_of = p31.read_instant(args.minutes_as_of, datetime.max.replace(tzinfo=UTC))
    latest = bars.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC)
    bars_as_of = p31.read_instant(args.as_of, latest)
    by_arm: dict[str, dict[str, dict[date, float]]] = {NIGHT: {}, SESSION: {}, "hold": {}}
    excluded: dict[str, dict[str, int]] = {}
    counted: dict[str, int] = {}
    paid: dict[str, float] = {}
    identity: dict[str, float] = {}
    for fund in FUNDS:
        dividends = p33.dividends_of(bars, fund, bars_as_of)
        sessions, missing = load_sessions(minutes, fund, minutes_as_of, dividends)
        night, inside, held = p33.returns_of(sessions, args.per_share)
        by_arm[NIGHT][fund], by_arm[SESSION][fund], by_arm["hold"][fund] = night, inside, held
        if args.per_share == 0:
            identity[fund] = p33.adds_up(night, inside, held, dividends)
        excluded[fund] = missing
        counted[fund] = len(cal.sessions(cal.exchange_for(fund), p33.START, p33.END)) - 1
        paid[fund] = sum(s.dividend for s in sessions)
    minutes.close()
    bars.close()

    most = max((counted[fund] for fund in SMALL), default=0)
    cells: dict[str, Any] = {}

    def add(name: str, series: Mapping[date, float], sessions: int) -> None:
        cell = reading(series, resamples, sessions)
        cell["described"] = p31.described(list(series.values()))
        cells[name] = cell

    small = {arm: p33.basket_of({f: by_arm[arm][f] for f in SMALL})
             for arm in (NIGHT, SESSION, "hold")}
    recent = p33.basket_of({f: by_arm[NIGHT][f] for f in SMALL}, p33.RECENT)
    add(f"{BASKET}-{NIGHT}", small[NIGHT], most)
    add(f"{BASKET}-{SESSION}", small[SESSION], most)
    add(f"{BASKET}-{NIGHT}-recent", recent, len(recent))
    add(f"{BASKET}-{NIGHT}-less-{SESSION}", p33.difference(small[NIGHT], small[SESSION]), most)
    add(f"{BASKET}-hold", small["hold"], most)
    for fund in FUNDS:
        for arm in (NIGHT, SESSION, "hold"):
            add(f"{fund}-{arm}", by_arm[arm][fund], counted[fund])
    return {"as_of": {"minutes": minutes_as_of.isoformat(), "bars": bars_as_of.isoformat()},
            "cells": cells, "excluded": excluded,
            "dividends_paid": {fund: round(value, 4) for fund, value in paid.items()},
            "arms_add_up_to_holding": identity, "per_share_cost": args.per_share}


def costed(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    """The primary reading under every costing, each a full pass at its own cost per share."""
    out: dict[str, Any] = {}
    for costing, per_share in p31.COSTS.items():
        built = build(argparse.Namespace(**{**vars(args), "per_share": per_share}), resamples)
        if costing == "net":
            out = built
        else:
            out["cells"][f"{BASKET}-{NIGHT}-{costing}"] = built["cells"][f"{BASKET}-{NIGHT}"]
            if costing == "gross":
                out["arms_add_up_to_holding"] = built["arms_add_up_to_holding"]
    return out


def power(args: argparse.Namespace) -> dict[str, Any]:
    """Each reading's WIDTH before registration, and nothing else."""
    from power_pr019 import assert_no_effect_leaked

    built = build(args, p31.POWER_RESAMPLES)
    widths = {name: {"width": round(cell["width"], 6), "days": cell["days"]}
              for name, cell in built["cells"].items()}
    payload = {"for": "PR-034", "as_of": built["as_of"], "resamples": p31.POWER_RESAMPLES,
               "widths": widths, "power_floor_width": p31.POWER_FLOOR}
    assert_no_effect_leaked(payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=Path, help="the minute store holding the three funds")
    parser.add_argument("--minutes-as-of", help="the minute store's knowledge instant")
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb with actions")
    parser.add_argument("--as-of", help="the bar store's knowledge instant")
    parser.add_argument("--per-share", type=float, default=p31.COSTS["net"],
                        help="dollars a share a side for the two arms")
    parser.add_argument("--resamples", type=int, default=p31.BOOTSTRAP_RESAMPLES,
                        help="bootstrap resamples; anything but the registered 10000 is a smoke run")
    parser.add_argument("--report", action="store_true", help="print the stored result")
    parser.add_argument("--power", action="store_true",
                        help="write each reading's interval width only, before registration")
    args = parser.parse_args(argv)
    if args.report:
        p33.report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.minutes is None or args.data is None:
        parser.error("--minutes and --data are required")
    if args.power:
        estimate = power(args)
        POWER.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
        print(f"PR-034 power: widths {estimate['widths']}")
        return 0
    built = costed(args, args.resamples)
    registered = args.resamples == p31.BOOTSTRAP_RESAMPLES
    branch = (branch_for(built["cells"][f"{BASKET}-{NIGHT}"],
                         built["cells"][f"{BASKET}-{NIGHT}-cost_adverse"],
                         built["cells"][f"{BASKET}-{NIGHT}-recent"],
                         built["cells"][f"{BASKET}-{NIGHT}"]["described"],
                         built["cells"][f"{BASKET}-hold"]["described"])
              if registered else "SMOKE")
    payload: dict[str, Any] = {
        "prereg": "PR-034", "trials": 6, "verdict": TOKEN[branch], "branch": branch,
        "country": "USA", "as_of": built["as_of"],
        "measured_span": {"first_session": p33.START.isoformat(),
                          "last_session": p33.END.isoformat()},
        "split": {"registered": "none - PR-033's two arms, unchanged, on three funds it never read",
                  "buys": "nothing a split could buy: no constant is chosen here"},
        "perturbations": {"registered": ["paper", "cost_adverse", "gross"],
                          "run": ["paper", "cost_adverse", "gross"]},
        "registered_settings": {"funds": FUNDS, "verdict_funds": SMALL, "boundary": BOUNDARY,
                                "primary": f"{BASKET}-{NIGHT}",
                                "recent_since": p33.RECENT.isoformat(),
                                "costs_per_share": p31.COSTS,
                                "gates": ["cost_adverse above zero", "recent estimate above zero",
                                          "sharpe above holding's"],
                                "bootstrap": {"unit": "month", "block": BLOCK,
                                              "seed": BOOTSTRAP_SEED, "resamples": args.resamples},
                                "power_floor": p31.POWER_FLOOR, "min_days": MIN_DAYS,
                                "min_months": MIN_MONTHS,
                                "min_complete_share": p31.MIN_COMPLETE_SHARE},
        **built,
    }
    if registered:
        RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    p33.report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
