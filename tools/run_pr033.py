"""`PR-033` - is the money in the night? The overnight return against the session's own, on five
index funds, net of costs.

**The claim, published since 2008 and never tested here.** An index fund's gain accrues between the
close and the next open; the session itself adds little. If that holds net of what two trades a day
cost, then *holding the fund only overnight* earns near the fund's whole return at roughly half its
volatility - a better return per unit of risk than holding it, which is the bar `EVIDENCE_SUMMARY`
§20-§23 says nothing has cleared.

**Two arms a fund, and the dividend belongs to one of them.**

* `N` - **overnight**: buy in the closing auction, sell at the next session's open. A fund's cash
  dividend detaches at the ex-date's OPEN, so the holder at the previous close receives it: every
  dividend in this study is paid to `N` and none to `D`. That is not a convention, it is who owns
  the shares.
* `D` - **the session**: buy at the open, sell at the close.

Both pay two sides a day; holding the fund pays two sides in ten years, and it is reported beside
them with its dividends.

**The verdict reads the equally weighted basket of all five funds' `N` arm.** Per fund, the session
arm, the difference `N - D` and the last 590 sessions are counted and never read.

    PYTHONPATH=$PWD/src python tools/run_pr033.py --minutes <store> --minutes-as-of <t> \
        --data <history store dir> --as-of <t> --resamples 10000
    python tools/run_pr033.py --report
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from itertools import pairwise

import run_pr031 as p31
from run_pr016 import BLOCK, cluster_of
from swingdesk.contracts.market import CorporateActionKind
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import MinuteStore
from swingdesk.reference_data import calendar as cal
from swingdesk.validation.backtest.intraday import session_for

RESULT = p31.RESULTS / "PR-033.json"
POWER = p31.RESULTS / "PR-033-power.json"

FUNDS = ("SPY", "QQQ", "IWM", "DIA", "EFA")
BASKET = "basket"
NIGHT, SESSION = "N", "D"
ARMS = (NIGHT, SESSION)

START = date(2016, 1, 4)
END = date(2026, 9, 18)
#: The recent window the last two studies read, kept the same so the three are comparable.
RECENT = date(2024, 5, 13)

BOOTSTRAP_SEED = 20260923
MIN_DAYS, MIN_MONTHS = 1000, 24

TOKEN = {**p31.TOKEN, "RECENT_FRAGILE": "inconclusive"}


@dataclass(frozen=True)
class Session:
    """One fund's session: what it opened and closed at, and the dividend detaching at its open."""

    session: date
    open: float
    close: float
    dividend: float


def dividends_of(store: BarStore, fund: str, as_of: datetime) -> dict[date, float]:
    """Cash dividends by EX-DATE, summed where a fund pays more than one on a day."""
    out: dict[date, float] = defaultdict(float)
    for action in store.actions_as_of(fund, as_of):
        if action.kind is CorporateActionKind.DIVIDEND:
            out[action.effective_date] += float(action.value)
    return dict(out)


def load_sessions(store: MinuteStore, fund: str, as_of: datetime,
                  dividends: Mapping[date, float]) -> tuple[list[Session], dict[str, int]]:
    """Every session of the window the minutes cover, with its dividend attached."""
    missing: dict[str, int] = defaultdict(int)
    out: list[Session] = []
    for session in cal.sessions(cal.exchange_for(fund), START, END):
        minutes = store.session(fund, session.session_date, as_of)
        if minutes is None:
            missing["never_fetched"] += 1
            continue
        found = session_for(fund, session.session_date)
        day = None if found is None else p31.build_day(minutes, found)
        if day is None:
            missing["no_regular_minutes"] += 1
        elif day.coverage < p31.MIN_COVERAGE:
            missing["thin"] += 1
        else:
            out.append(Session(session=day.session, open=day.open, close=day.close,
                               dividend=dividends.get(day.session, 0.0)))
    return out, dict(missing)


def returns_of(sessions: Sequence[Session], per_share: float
               ) -> tuple[dict[date, float], dict[date, float], dict[date, float]]:
    """`N`, `D` and holding the fund, per session, net of two sides a day for the two arms.

    Holding pays no per-day cost: it trades twice in the whole window, which rounds to nothing a
    session, and the report says so rather than pretending the number is exact.
    """
    night: dict[date, float] = {}
    inside: dict[date, float] = {}
    held: dict[date, float] = {}
    for before, now in pairwise(sessions):
        night[now.session] = ((now.open + now.dividend - before.close) / before.close
                              - 2 * per_share / before.close)
        inside[now.session] = (now.close - now.open) / now.open - 2 * per_share / now.open
        held[now.session] = (now.close + now.dividend - before.close) / before.close
    return night, inside, held


def adds_up(night: Mapping[date, float], inside: Mapping[date, float],
            held: Mapping[date, float], dividends: Mapping[date, float]) -> float:
    """The largest gap between compounding the two arms and holding, on sessions with no dividend.

    `N` and `D` are the same two prices as holding, so on a session that pays nothing they must
    multiply back to it exactly. Where a dividend is paid they cannot: compounding reinvests it at
    the open and holding takes it as cash, and those are different amounts by a day's move on the
    dividend. Read at zero cost - a cost is not part of the identity.
    """
    worst = 0.0
    for session, value in night.items():
        if dividends.get(session) or session not in inside or session not in held:
            continue
        worst = max(worst, abs((1 + value) * (1 + inside[session]) - 1 - held[session]))
    return worst


def basket_of(by_fund: Mapping[str, Mapping[date, float]],
              since: date | None = None) -> dict[date, float]:
    """Equal capital across the funds: each session's mean over the funds that read it."""
    gathered: dict[date, list[float]] = defaultdict(list)
    for series in by_fund.values():
        for session, value in series.items():
            if since is None or session >= since:
                gathered[session].append(value)
    return {session: statistics.fmean(values) for session, values in gathered.items()}


def reading(series: Mapping[date, float], resamples: int, sessions: int) -> dict[str, Any]:
    cell = dict(p31.clustered_mean(series, resamples, BOOTSTRAP_SEED))
    cell["days"] = len(series)
    cell["sessions"] = sessions
    cell["complete_share"] = len(series) / sessions if sessions else 0.0
    cell["months"] = len({cluster_of(session) for session in series})
    return cell


def difference(first: Mapping[date, float], second: Mapping[date, float]) -> dict[date, float]:
    return {session: value - second[session] for session, value in first.items()
            if session in second}


def branch_for(cell: Mapping[str, Any], adverse: Mapping[str, Any], recent: Mapping[str, Any],
               floor: float = p31.POWER_FLOOR) -> str:
    if (cell["days"] < MIN_DAYS or cell["months"] < MIN_MONTHS
            or cell["complete_share"] < p31.MIN_COMPLETE_SHARE):
        return "REFUSED"
    if cell["lo"] > 0:
        if not adverse["lo"] > 0:
            return "COST_FRAGILE"
        if not recent["estimate"] > 0:
            return "RECENT_FRAGILE"
        return "ACCEPT"
    if cell["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if cell["width"] > floor else "NULL"


def build(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    minutes = MinuteStore(args.minutes)
    bars = BarStore(args.data / "bars.duckdb")
    minutes_as_of = p31.read_instant(args.minutes_as_of, datetime.max.replace(tzinfo=UTC))
    # A store that holds actions and no bars has no latest bar instant; the default is then
    # "everything known", which is what no --as-of asks for anyway.
    latest = bars.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC)
    bars_as_of = p31.read_instant(args.as_of, latest)
    by_arm: dict[str, dict[str, dict[date, float]]] = {NIGHT: {}, SESSION: {}, "hold": {}}
    excluded: dict[str, dict[str, int]] = {}
    counted: dict[str, int] = {}
    paid: dict[str, float] = {}
    identity: dict[str, float] = {}
    for fund in FUNDS:
        dividends = dividends_of(bars, fund, bars_as_of)
        sessions, missing = load_sessions(minutes, fund, minutes_as_of, dividends)
        night, inside, held = returns_of(sessions, args.per_share)
        by_arm[NIGHT][fund], by_arm[SESSION][fund], by_arm["hold"][fund] = night, inside, held
        if args.per_share == 0:
            free_night, free_inside, free_held = returns_of(sessions, 0.0)
            identity[fund] = adds_up(free_night, free_inside, free_held, dividends)
        excluded[fund] = missing
        counted[fund] = len(cal.sessions(cal.exchange_for(fund), START, END)) - 1
        paid[fund] = sum(s.dividend for s in sessions)
    minutes.close()
    bars.close()

    most = max(counted.values(), default=0)
    cells: dict[str, Any] = {}

    def add(name: str, series: Mapping[date, float], sessions: int) -> None:
        cell = reading(series, resamples, sessions)
        cell["described"] = p31.described(list(series.values()))
        cells[name] = cell

    night, inside, held = (basket_of(by_arm[arm]) for arm in (NIGHT, SESSION, "hold"))
    recent = basket_of(by_arm[NIGHT], RECENT)
    add(f"{BASKET}-{NIGHT}", night, most)
    add(f"{BASKET}-{SESSION}", inside, most)
    add(f"{BASKET}-{NIGHT}-recent", recent, len(recent))
    add(f"{BASKET}-{NIGHT}-less-{SESSION}", difference(night, inside), most)
    add(f"{BASKET}-hold", held, most)
    for fund in FUNDS:
        for arm in (*ARMS, "hold"):
            add(f"{fund}-{arm}", by_arm[arm][fund], counted[fund])
    return {"as_of": {"minutes": minutes_as_of.isoformat(), "bars": bars_as_of.isoformat()},
            "cells": cells, "excluded": excluded,
            "dividends_paid": {fund: round(value, 4) for fund, value in paid.items()},
            "arms_add_up_to_holding": identity,
            "per_share_cost": args.per_share}


def costed(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    """The primary reading under every costing, each a full pass at its own cost per share."""
    out: dict[str, Any] = {}
    for costing, per_share in p31.COSTS.items():
        pass_args = argparse.Namespace(**{**vars(args), "per_share": per_share})
        built = build(pass_args, resamples)
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
    payload = {"for": "PR-033", "as_of": built["as_of"], "resamples": p31.POWER_RESAMPLES,
               "widths": widths, "power_floor_width": p31.POWER_FLOOR}
    assert_no_effect_leaked(payload)
    return payload


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-033   verdict {payload['verdict']}   branch {payload['branch']}")
    print(f"  excluded {payload['excluded']}   dividends {payload['dividends_paid']}")
    print(f"  arms add up to holding, worst gap {payload.get('arms_add_up_to_holding')}")
    for name, cell in payload["cells"].items():
        print(f"  {name:<22} days {cell['days']:>5}  months {cell['months']:>3}  "
              f"complete {cell['complete_share']:.1%}   {p31._fmt(cell)}")  # noqa: SLF001
        if cell.get("described"):
            d = cell["described"]
            print(f"      a year {d['annual_mean']:+.2%}  vol {d['annual_volatility']:.2%}  "
                  f"sharpe {d['sharpe']:+.2f}  worst {d['max_drawdown']:+.1%}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=Path, help="the minute store holding the five funds")
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
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.minutes is None or args.data is None:
        parser.error("--minutes and --data are required")
    if args.power:
        estimate = power(args)
        POWER.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
        print(f"PR-033 power: widths {estimate['widths']}")
        return 0
    built = costed(args, args.resamples)
    registered = args.resamples == p31.BOOTSTRAP_RESAMPLES
    branch = (branch_for(built["cells"][f"{BASKET}-{NIGHT}"],
                         built["cells"][f"{BASKET}-{NIGHT}-cost_adverse"],
                         built["cells"][f"{BASKET}-{NIGHT}-recent"])
              if registered else "SMOKE")
    payload: dict[str, Any] = {
        "prereg": "PR-033", "trials": 10, "verdict": TOKEN[branch], "branch": branch,
        "country": "USA and developed markets", "as_of": built["as_of"],
        "measured_span": {"first_session": START.isoformat(), "last_session": END.isoformat()},
        "split": {"registered": "none - two arms of one decision on five funds, none selected",
                  "buys": "nothing a split could buy: no constant is chosen here"},
        "perturbations": {"registered": ["paper", "cost_adverse", "gross"],
                          "run": ["paper", "cost_adverse", "gross"]},
        "registered_settings": {"funds": FUNDS, "arms": ARMS, "primary": f"{BASKET}-{NIGHT}",
                                "recent_since": RECENT.isoformat(), "costs_per_share": p31.COSTS,
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
