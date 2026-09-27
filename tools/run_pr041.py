"""`PR-041` - do Asia-Pacific funds earn while their home markets are shut, through the US session?

**The source, and why it is the third leg `DR-055` names.** `PR-033`..`PR-036` measured the
equity premium accruing while the HOME market is closed: small caps earn their return overnight and
lose it in the session. A US-listed fund on Japanese, Chinese or Australian shares has its home
market shut for the whole US session - so if the mechanism is real, that fund's US SESSION is its
night, and it is where its return should accrue. `PR-033` saw it once, on `EFA`, after the fact:
night negative, session positive. This asks it of eight funds no study here has read for it.

**The universe, fixed by rule before any bar was fetched:** the eight largest Asia-Pacific equity
markets with a US-listed single-country fund - Japan, China, Hong Kong, India, Korea, Taiwan,
Australia, Singapore: `EWJ`, `FXI`, `EWH`, `INDA`, `EWY`, `EWT`, `EWA`, `EWS`, equally weighted.
Every one of those exchanges is closed for the whole US session. Europe is not, and is left out.

**The costing is `PR-040`'s economics on bars.** An auction order pays the cross and the regulatory
fees; the bar's open and close stand in for the crosses, and a sample of real cross prints must
agree with them (§9) or the study refuses. A half cent and a cent a share a side are perturbations -
these funds trade near $20-70, where a modelled cent is 3-10 basis points a side.

**A registered secondary, never read by the decision rule:** the three-leg book - `IJR`+`VB` by
night, and the day split equally between `SPY` and this basket - against `SPY` held and against
`PR-035`'s two-leg book, over the window and over the last three years.

    PYTHONPATH=$PWD/src python tools/run_pr041.py --power --data DIR --as-of T
    PYTHONPATH=$PWD/src python tools/run_pr041.py --data DIR --as-of T --auctions FILE [--auctions-as-of T]
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr025 as p25
import run_pr031 as p31
import run_pr033 as p33
import run_pr035 as p35
import run_pr036 as p36
import run_pr037 as p37
import run_pr040 as p40
from run_pr016 import cluster_of
from swingdesk.market_data import BarStore
from swingdesk.market_data.auctions import CLOSING, OPENING, AuctionStore

RESULT = p31.RESULTS / "PR-041.json"
POWER = p31.RESULTS / "PR-041-power.json"

FUNDS = ("EWJ", "FXI", "EWH", "INDA", "EWY", "EWT", "EWA", "EWS")
NIGHT_FUNDS = ("IJR", "VB")
DAY_FUND = "SPY"
FIRST = date(2016, 1, 4)
LAST = date(2026, 9, 25)
RECENT_MONTHS = 48
THREE_YEARS_FROM = date(2023, 9, 26)
#: `DR-049` §4.2: the window this study does NOT read, named before it runs. The funds' bars reach
#: back to 1996-2012; 2004-2015 is left for a confirmation of its own.
HOLDOUT = (date(2004, 1, 1), date(2015, 12, 31))

#: Extra cost a share a side on top of the fees. `auction_fees` carries the verdict.
COSTINGS: dict[str, float | None] = {"auction_fees": 0.0, "half_cent": 0.005, "cent": 0.01,
                                     "gross": None}
SEED = 20260927
MIN_DAYS, MIN_MONTHS, MIN_COMPLETE_SHARE = 1000, 24, 0.90
FLOOR = p31.POWER_FLOOR
BASIS_TOLERANCE = 0.0005
#: The cross-print sample §9 checks the bars against: sessions a fund, drawn once, seeded.
SAMPLE_PER_FUND = 30


def side_cost(price: float, selling: bool, extra: float | None) -> float:
    """One side's cost as a fraction of the position: the venue's fees, plus `extra` a share."""
    if extra is None or price <= 0:
        return 0.0
    cost = p40.CAT_PER_SHARE / price + extra / price
    if selling:
        cost += p40.SEC_RATE + p40.TAF_PER_SHARE / price
    return cost


def arms(sessions: Sequence[p33.Session], extra: float | None
         ) -> tuple[dict[date, float], dict[date, float], dict[date, float]]:
    """`PR-033`'s night, session and holding, charged per side by `side_cost`."""
    night: dict[date, float] = {}
    inside: dict[date, float] = {}
    held: dict[date, float] = {}
    for before, now in itertools.pairwise(sessions):
        if before.close <= 0 or now.open <= 0:
            continue
        night[now.session] = ((now.open + now.dividend - before.close) / before.close
                              - side_cost(before.close, False, extra)
                              - side_cost(now.open, True, extra))
        inside[now.session] = ((now.close - now.open) / now.open
                               - side_cost(now.open, False, extra)
                               - side_cost(now.close, True, extra))
        held[now.session] = (now.close + now.dividend - before.close) / before.close
    return night, inside, held


def last_months(series: Mapping[date, float], count: int = RECENT_MONTHS) -> dict[date, float]:
    months = sorted({cluster_of(day) for day in series})[-count:]
    keep = set(months)
    return {day: value for day, value in series.items() if cluster_of(day) in keep}


def branch_for(cell: Mapping[str, Any], half_cent: Mapping[str, Any], recent: float,
               session_sharpe: float, held_sharpe: float, basis_ok: bool) -> str:
    """`PR-034`'s order, with `DR-055`'s recency condition and §9's basis refusal first."""
    if (not basis_ok or cell["days"] < MIN_DAYS or cell["months"] < MIN_MONTHS
            or cell["complete_share"] < MIN_COMPLETE_SHARE):
        return "REFUSED"
    if cell["lo"] > 0:
        if not half_cent["lo"] > 0:
            return "COST_FRAGILE"
        if not recent > 0:
            return "RECENT_FRAGILE"
        if not session_sharpe > held_sharpe:
            return "NOT_BETTER_HELD"
        return "ACCEPT"
    if cell["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if cell["width"] > FLOOR else "NULL"


def load(args: argparse.Namespace) -> tuple[dict[str, list[p33.Session]], datetime]:
    store = BarStore(args.data / "bars.duckdb")
    latest = store.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC)
    as_of = p31.read_instant(args.as_of, latest)
    try:
        return ({fund: [s for s in p36.sessions_from_bars(store, fund, as_of)
                        if HOLDOUT[1] < s.session <= LAST]
                 for fund in (*FUNDS, *NIGHT_FUNDS, DAY_FUND)}, as_of)
    finally:
        store.close()


def basket(sessions: Mapping[str, Sequence[p33.Session]], funds: Sequence[str],
           extra: float | None) -> dict[str, dict[date, float]]:
    per = {fund: arms(sessions[fund], extra) for fund in funds}
    return {name: p36.within(p33.basket_of({f: per[f][i] for f in funds}), FIRST, LAST)
            for i, name in enumerate(("night", "session", "hold"))}


def reading(series: Mapping[date, float], resamples: int) -> dict[str, Any]:
    cell: dict[str, Any] = dict(p31.clustered_mean(series, resamples, SEED))
    cell["days"] = len(series)
    cell["complete_share"] = 1.0 if series else 0.0
    cell["months"] = len({cluster_of(day) for day in series})
    cell["described"] = p31.described([series[d] for d in sorted(series)])
    return cell


def basis_check(sessions: Mapping[str, Sequence[p33.Session]], auctions: AuctionStore,
                auctions_as_of: datetime) -> dict[str, Any]:
    """The median gap between a fund's crosses and its own bars, on a seeded sample of sessions."""
    import random

    rng = random.Random(SEED)
    gaps: dict[str, float] = {}
    for fund in FUNDS:
        rows = [s for s in sessions[fund] if FIRST <= s.session <= LAST]
        drawn = rng.sample(rows, min(SAMPLE_PER_FUND, len(rows)))
        found: list[float] = []
        for s in drawn:
            opening = p25.cross_price(auctions.window(fund, s.session, OPENING, auctions_as_of),
                                      OPENING)
            closing = p25.cross_price(auctions.window(fund, s.session, CLOSING, auctions_as_of),
                                      CLOSING)
            factor = p25.adjustment_factor(opening, Decimal(str(s.open)), closing,
                                           Decimal(str(s.close)))
            for cross, level in ((opening, s.open), (closing, s.close)):
                if cross is not None and level > 0:
                    found.append(abs(float(cross.price / factor) / level - 1))
        gaps[fund] = statistics.median(found) if found else math.nan
    ok = all(not math.isnan(v) and v <= BASIS_TOLERANCE for v in gaps.values())
    return {"median_gap": gaps, "basis_ok": ok, "sample_per_fund": SAMPLE_PER_FUND}


def sample_sessions(sessions: Mapping[str, Sequence[p33.Session]]) -> list[dict[str, str]]:
    """The (fund, session) pairs §9's sample reads - written for the fetcher, drawn the same way."""
    import random

    rng = random.Random(SEED)
    out: list[dict[str, str]] = []
    for fund in FUNDS:
        rows = [s for s in sessions[fund] if FIRST <= s.session <= LAST]
        for s in rng.sample(rows, min(SAMPLE_PER_FUND, len(rows))):
            out.append({"instrument_id": fund, "session_date": s.session.isoformat()})
    return out


def book(sessions: Mapping[str, Sequence[p33.Session]], extra: float | None,
         asia_share: float) -> tuple[dict[date, float], dict[date, float]]:
    """The book: the night basket, then a day split between `SPY` and the Asia basket.

    `asia_share` 0 is `PR-035`'s two-leg book; 0.5 is the registered three-leg one.
    """
    night = basket(sessions, NIGHT_FUNDS, extra)["night"]
    asia = basket(sessions, FUNDS, extra)["session"]
    _, spy_day, spy_hold = arms(sessions[DAY_FUND], extra)
    day = {d: (1 - asia_share) * spy_day[d] + asia_share * asia.get(d, spy_day[d])
           for d in spy_day}
    return (p36.within(p35.compounded(night, day), FIRST, LAST),
            p36.within(spy_hold, FIRST, LAST))


def secondary(sessions: Mapping[str, Sequence[p33.Session]], resamples: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    three, spy = book(sessions, 0.0, 0.5)
    two, _ = book(sessions, 0.0, 0.0)
    for label, since in (("window", FIRST), ("last_three_years", THREE_YEARS_FROM)):
        cells: dict[str, Any] = {}
        for name, series in (("three_leg", three), ("two_leg", two), ("hold_SPY", spy)):
            kept = {d: v for d, v in series.items() if d >= since}
            cells[name] = p31.described([kept[d] for d in sorted(kept)])
        three_m = p40.monthly({d: v for d, v in three.items() if d >= since})
        spy_m = p40.monthly({d: v for d, v in spy.items() if d >= since})
        two_m = p40.monthly({d: v for d, v in two.items() if d >= since})
        cells["three_leg_over_SPY"] = p37.paired_bootstrap(three_m, spy_m, resamples, SEED)
        cells["three_leg_over_two_leg"] = p37.paired_bootstrap(three_m, two_m, resamples, SEED)
        out[label] = cells
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    sessions, as_of = load(args)
    auctions = AuctionStore(args.auctions)
    try:
        auctions_as_of = p31.read_instant(args.auctions_as_of, datetime.now(UTC))
        checks = basis_check(sessions, auctions, auctions_as_of)
    finally:
        auctions.close()
    cells: dict[str, Any] = {}
    for costing, extra in COSTINGS.items():
        arms_of = basket(sessions, FUNDS, extra)
        for name, series in arms_of.items():
            cells[f"{name}-{costing}"] = reading(series, p31.BOOTSTRAP_RESAMPLES)
    primary = cells["session-auction_fees"]
    recent_series = last_months(basket(sessions, FUNDS, 0.0)["session"])
    recent = statistics.fmean(recent_series.values()) if recent_series else math.nan
    identity = {}
    for fund in FUNDS:
        night, inside, held = arms(sessions[fund], None)
        identity[fund] = p33.adds_up(night, inside, held,
                                     {s.session: s.dividend for s in sessions[fund]})
    branch = branch_for(primary, cells["session-half_cent"], recent,
                        primary["described"].get("sharpe", math.nan),
                        cells["hold-auction_fees"]["described"].get("sharpe", math.nan),
                        checks["basis_ok"])
    return {
        "prereg": "PR-041", "trials": 2, "branch": branch,
        "verdict": {"ACCEPT": "accept", "REJECT": "reject", "REFUSED": "refused"}.get(
            branch, "inconclusive"),
        "country": "USA-listed, Asia-Pacific underlying",
        "as_of": {"bars": as_of.isoformat(), "auctions": args.auctions_as_of},
        "measured_span": {"first_session": FIRST.isoformat(), "last_session": LAST.isoformat(),
                          "years": round((LAST - FIRST).days / 365.25, 2)},
        "holdout": {"first": HOLDOUT[0].isoformat(), "last": HOLDOUT[1].isoformat(),
                    "read": False},
        "split": {"registered": "none - one basket, one arm, one window",
                  "buys": "nothing a split could buy: no constant is chosen here"},
        "perturbations": {"registered": ["half_cent", "cent", "gross"],
                          "run": ["half_cent", "cent", "gross"]},
        "recent_mean_daily": recent, "checks": checks, "arms_add_up_to_holding": identity,
        "cells": cells, "secondary": secondary(sessions, p31.BOOTSTRAP_RESAMPLES),
    }


def power(args: argparse.Namespace) -> dict[str, Any]:
    from power_pr019 import assert_no_effect_leaked

    sessions, as_of = load(args)
    series = basket(sessions, FUNDS, 0.0)["session"]
    cell = p31.clustered_mean(series, p31.POWER_RESAMPLES, SEED)
    payload = {"for": "PR-041", "as_of": {"bars": as_of.isoformat()},
               "resamples": p31.POWER_RESAMPLES,
               "widths": {"session-auction_fees": {"width": round(cell["width"], 6),
                                                   "days": len(series)}},
               "power_floor_width": FLOOR}
    assert_no_effect_leaked(payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--auctions", type=Path)
    parser.add_argument("--auctions-as-of")
    parser.add_argument("--power", action="store_true")
    parser.add_argument("--sample-out", type=Path,
                        help="write the cross-print sample's (fund, session) pairs and stop")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.sample_out:
        sessions, _ = load(args)
        pairs = sample_sessions(sessions)
        args.sample_out.write_text("".join(json.dumps(p) + "\n" for p in pairs), encoding="utf-8")
        print(f"{len(pairs)} (fund, session) pairs written to {args.sample_out}")
        return 0
    if args.power:
        payload = power(args)
        out = args.out or POWER
        width = payload["widths"]["session-auction_fees"]["width"]
        print(f"PR-041 power  width {width:.6f} a day   minimum detectable "
              f"{width / 2 * (1.96 + 0.84) / 1.96:.6f}")
    else:
        if args.auctions is None:
            parser.error("--auctions is required for the run")
        payload = run(args)
        out = args.out or RESULT
        print(f"PR-041   branch {payload['branch']}")
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
