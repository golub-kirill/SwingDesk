"""`PR-040` - `PR-035`'s book priced at the auctions it would trade in, against holding `SPY`. `DR-055`.

**What this is.** `DR-055` made `PR-035`'s book the project's main hypothesis and defined proof. This
is proof (1): the same rule - `IJR` and `VB` from each close to the next open, `SPY` from that open
to that close, the same dollar twice - with every fill at the listing market's OFFICIAL cross, the
price an auction order is filled at, and the venue's regulatory fees instead of a modelled half
cent a share.

**Why the price source is the whole study.** `PR-035`'s margin over `SPY` was +3.25% a year at half
a cent a share a side and +0.35% at a cent, and 6.1% gross: the edge and its costs were the same
size. A market-on-open or market-on-close order pays the cross's single price and no spread, so the
modelled cent was never what such an order pays. The cross is read from the SIP tape
(`tools/fetch_auction_prints.py`), chosen by `PR-025`'s rule, and brought onto the bars' basis by
`PR-025`'s adjustment - the tape prints what traded and the bars carry every later split, which is
the unit error that sank `PR-025`'s first run (the smoke run here found `IJR` at exactly twice its
2016 bars).

**What it cannot see**, stated where the number is made: that the broker routes an `opg` or `cls`
order into the listing auction. That is the broker's documented behaviour; it has never been
observed here, because the paper venue's fills are simulated (`DR-055` §2).

    PYTHONPATH=$PWD/src python tools/run_pr040.py --power --data DIR --as-of T
    PYTHONPATH=$PWD/src python tools/run_pr040.py --data DIR --as-of T --auctions FILE \\
        --auctions-as-of T [--factors FILE]
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import factor_attribution as fa
import run_pr025 as p25
import run_pr031 as p31
import run_pr033 as p33
import run_pr035 as p35
import run_pr037 as p37
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.market_data.auctions import CLOSING, OPENING, AuctionStore

RESULT = p31.RESULTS / "PR-040.json"
POWER = p31.RESULTS / "PR-040-power.json"

NIGHT_FUNDS = ("IJR", "VB")
DAY_FUND = "SPY"
FUNDS = (*NIGHT_FUNDS, DAY_FUND)

#: `PR-035`'s own measured span. This re-prices that registration; it does not widen it.
FIRST = date(2016, 1, 4)
LAST = date(2026, 9, 18)
#: `DR-055` §1.3's second condition: a positive excess over the last forty-eight months.
RECENT_MONTHS = 48

#: The venue's regulatory fees (`docs/decisions/measurements/venue-fees-2026-09-05.json`, the
#: Alpaca Clearing schedule of 2026-09-01). Applied at today's rates to every session: the SEC rate
#: has moved over the decade, and a constant is declared rather than a history reconstructed.
SEC_RATE = 0.0000206      # of the value sold
TAF_PER_SHARE = 0.000195  # a share sold; its $9.79 cap binds at 50,205 shares, never at this size
CAT_PER_SHARE = 0.000003  # a share, bought or sold
#: A session missing a cross on a fund is priced at the bar and charged a whole cent a share there.
MISSING_PENALTY = 0.01
#: The costings. `auction` carries the verdict; the rest are printed and never read by it.
COSTINGS = ("auction", "auction_plus_half_cent", "gross", "bars_pr035")
PR035_PER_SHARE = 0.005

RESAMPLES = 10_000
SEED = 20260927
#: End-to-end width, a year, below which an interval containing zero is `NULL` rather than
#: `INCONCLUSIVE`: +-2% a year either side of zero is too narrow to hide the margin at stake.
FLOOR = 0.04
MIN_SESSIONS, MIN_MONTHS = 1000, 24
MIN_CROSSED_SHARE = 0.95
#: After the split adjustment, the cross and its own bar may differ by this much at the median.
#: Wider, and the two are not measuring the same price - `PR-025`'s lesson, made a refusal.
BASIS_TOLERANCE = 0.0005
#: `PR-035`'s registered contrast, the mean daily book-less-`SPY`, re-derived here on bars.
PR035_MEAN_DAILY = 0.00012877277713129124
REPRODUCTION_TOLERANCE = 0.02  # a year, `PR-036`'s tolerance for a change of price source


@dataclass(frozen=True)
class Priced:
    """One fund's session on the bars' basis, with the tape's own prices beside it for the fees."""

    session: date
    open: float
    close: float
    dividend: float
    tape_open: float
    tape_close: float
    bar_open: float
    bar_close: float
    crossed_open: bool
    crossed_close: bool
    gap_open: float | None
    gap_close: float | None


def priced_sessions(bars: Sequence[Any], dividends: Mapping[date, float],
                    crosses: Mapping[date, tuple[Any, Any]], first: date, last: date,
                    bars_as_crosses: bool = False) -> list[Priced]:
    """Every stored session in the window, priced at its crosses where the tape has them.

    `crosses` maps a session to `(opening print or None, closing print or None)`. A missing cross
    falls back to the bar's own price, flagged, so the costing can charge for it -
    unless `bars_as_crosses`, the power estimate's stand-in, which reads no print at all.
    """
    out: list[Priced] = []
    for bar in bars:
        if not first <= bar.session_date <= last:
            continue
        bar_open, bar_close = Decimal(str(bar.open)), Decimal(str(bar.close))
        if bar_open <= 0 or bar_close <= 0:
            continue
        opening, closing = crosses.get(bar.session_date, (None, None))
        factor = p25.adjustment_factor(opening, bar_open, closing, bar_close)
        o, tape_o, crossed_o, gap_o = _on_basis(opening, bar_open, factor, bars_as_crosses)
        c, tape_c, crossed_c, gap_c = _on_basis(closing, bar_close, factor, bars_as_crosses)
        out.append(Priced(bar.session_date, o, c, dividends.get(bar.session_date, 0.0),
                          tape_o, tape_c, float(bar_open), float(bar_close),
                          crossed_o, crossed_c, gap_o, gap_c))
    return out


def _on_basis(cross: Any, level: Decimal, factor: Decimal, bars_as_crosses: bool
              ) -> tuple[float, float, bool, float | None]:
    """`(price on the bars' basis, the tape's own price, crossed?, gap to the bar)`."""
    if cross is None:
        return float(level), float(level * factor), bars_as_crosses, None
    price = cross.price / factor
    return float(price), float(cross.price), True, float(price / level - 1)


def buy_cost(tape_price: float, crossed: bool, costing: str) -> float:
    """What one side costs as a fraction of the position, bought at `tape_price`."""
    if costing == "gross":
        return 0.0
    if costing == "bars_pr035":
        return PR035_PER_SHARE / tape_price
    cost = CAT_PER_SHARE / tape_price
    if not crossed:
        cost += MISSING_PENALTY / tape_price
    if costing == "auction_plus_half_cent":
        cost += 0.005 / tape_price
    return cost


def sell_cost(tape_price: float, crossed: bool, costing: str) -> float:
    if costing == "gross":
        return 0.0
    if costing == "bars_pr035":
        return PR035_PER_SHARE / tape_price
    return SEC_RATE + TAF_PER_SHARE / tape_price + buy_cost(tape_price, crossed, costing)


def arms(sessions: Sequence[Priced], costing: str
         ) -> tuple[dict[date, float], dict[date, float], dict[date, float]]:
    """The night, the session and holding, per session - `PR-033`'s arms with auction pricing.

    On `bars_pr035` the prices are the bars' own, as `PR-035` priced them, so the reproduction
    check reads the same construction on a known price source.
    """
    night: dict[date, float] = {}
    inside: dict[date, float] = {}
    held: dict[date, float] = {}
    bars_only = costing == "bars_pr035"
    for before, now in itertools.pairwise(sessions):
        if bars_only:
            # `PR-035`'s own construction: bar prices, and a per-share cost on the ADJUSTED price,
            # which is what its minute store carried.
            close0, open1, close1 = before.bar_close, now.bar_open, now.bar_close
            fee_c0, fee_o1, fee_c1 = close0, open1, close1
            crossed_c0 = crossed_o1 = crossed_c1 = True
        else:
            close0, open1, close1 = before.close, now.open, now.close
            fee_c0, fee_o1, fee_c1 = before.tape_close, now.tape_open, now.tape_close
            crossed_c0, crossed_o1 = before.crossed_close, now.crossed_open
            crossed_c1 = now.crossed_close
        night[now.session] = ((open1 + now.dividend - close0) / close0
                              - buy_cost(fee_c0, crossed_c0, costing)
                              - sell_cost(fee_o1, crossed_o1, costing))
        inside[now.session] = ((close1 - open1) / open1
                               - buy_cost(fee_o1, crossed_o1, costing)
                               - sell_cost(fee_c1, crossed_c1, costing))
        held[now.session] = (close1 + now.dividend - close0) / close0
    return night, inside, held


def monthly(daily: Mapping[date, float]) -> dict[str, float]:
    """Daily returns compounded into calendar months, keyed `YYYY-MM`."""
    grown: dict[str, float] = defaultdict(lambda: 1.0)
    for session in sorted(daily):
        grown[session.strftime("%Y-%m")] *= 1.0 + daily[session]
    return {month: value - 1.0 for month, value in grown.items()}


def recent(months: Mapping[str, float], count: int = RECENT_MONTHS) -> dict[str, float]:
    keys = sorted(months)[-count:]
    return {key: months[key] for key in keys}


def branch_for(primary: Mapping[str, float], recent_excess: float, checks: Mapping[str, Any],
               sessions: int, months: int) -> str:
    """`DR-055` §1.3's proof (1), with the study's own refusals first."""
    if (sessions < MIN_SESSIONS or months < MIN_MONTHS
            or checks["crossed_share"] < MIN_CROSSED_SHARE
            or not checks["basis_ok"] or not checks["reproduces_pr035"]):
        return "REFUSED"
    if primary["lo"] > 0:
        return "ACCEPT" if recent_excess > 0 else "RECENT_FRAGILE"
    if primary["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if primary["width"] > FLOOR else "NULL"


def load(args: argparse.Namespace, use_crosses: bool) -> dict[str, list[Priced]]:
    bars = BarStore(args.data / "bars.duckdb")
    as_of = p31.read_instant(args.as_of, bars.latest_knowledge_time() or datetime.now().astimezone())
    auctions = AuctionStore(args.auctions) if use_crosses else None
    auctions_as_of = p31.read_instant(getattr(args, "auctions_as_of", None), as_of)
    try:
        out: dict[str, list[Priced]] = {}
        for fund in FUNDS:
            series = bars.as_of(fund, Interval.DAY, Series.RAW, as_of).bars
            dividends = p33.dividends_of(bars, fund, as_of)
            crosses: dict[date, tuple[Any, Any]] = {}
            if auctions is not None:
                for bar in series:
                    if FIRST <= bar.session_date <= LAST:
                        day = bar.session_date
                        opening = p25.cross_price(
                            auctions.window(fund, day, OPENING, auctions_as_of), OPENING)
                        closing = p25.cross_price(
                            auctions.window(fund, day, CLOSING, auctions_as_of), CLOSING)
                        crosses[day] = (opening, closing)
            out[fund] = priced_sessions(series, dividends, crosses, FIRST, LAST,
                                        bars_as_crosses=not use_crosses)
    finally:
        bars.close()
        if auctions is not None:
            auctions.close()
    return out


def book_of(priced: Mapping[str, Sequence[Priced]], costing: str
            ) -> tuple[dict[date, float], dict[date, float], dict[str, dict[date, float]]]:
    nights = {fund: arms(priced[fund], costing)[0] for fund in NIGHT_FUNDS}
    _, spy_day, spy_hold = arms(priced[DAY_FUND], costing)
    book = p35.compounded(p33.basket_of(nights), spy_day)
    return book, spy_hold, {"night": p33.basket_of(nights), "day": spy_day}


def checks_of(priced: Mapping[str, Sequence[Priced]]) -> dict[str, Any]:
    sessions = sorted(set.intersection(*({s.session for s in v} for v in priced.values())))
    by_fund = {fund: {s.session: s for s in rows} for fund, rows in priced.items()}
    full = sum(1 for d in sessions if all(by_fund[f][d].crossed_open and by_fund[f][d].crossed_close
                                          for f in FUNDS))
    gaps: dict[str, float] = {}
    for fund, rows in priced.items():
        for side in ("open", "close"):
            values = [abs(g) for g in (getattr(r, f"gap_{side}") for r in rows) if g is not None]
            gaps[f"{fund}_{side}"] = statistics.median(values) if values else math.nan
    book, hold, _ = book_of(priced, "bars_pr035")
    difference = [book[d] - hold[d] for d in book if d in hold]
    mean_daily = statistics.fmean(difference) if difference else math.nan
    gross_identity = {}
    for fund in FUNDS:
        night, inside, held = arms(priced[fund], "gross")
        dividends = {s.session: s.dividend for s in priced[fund] if s.dividend}
        gross_identity[fund] = p33.adds_up(night, inside, held, dividends)
    return {
        "sessions": len(sessions), "crossed_sessions": full,
        "crossed_share": full / len(sessions) if sessions else 0.0,
        "median_basis_gap": gaps,
        "basis_ok": all(not math.isnan(v) and v <= BASIS_TOLERANCE for v in gaps.values()),
        "pr035_mean_daily_on_bars": mean_daily,
        "reproduces_pr035": (not math.isnan(mean_daily)
                             and abs(mean_daily - PR035_MEAN_DAILY) * 252 <= REPRODUCTION_TOLERANCE),
        "identity_worst_gap": gross_identity,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    priced = load(args, use_crosses=True)
    checks = checks_of(priced)
    cells: dict[str, Any] = {}
    for costing in COSTINGS:
        book, hold, legs = book_of(priced, costing)
        book_m, hold_m = monthly(book), monthly(hold)
        cell: dict[str, Any] = dict(p37.paired_bootstrap(book_m, hold_m, RESAMPLES, SEED))
        rb, rh = recent(book_m), recent(hold_m)
        cell["recent_excess"] = p37.geometric_excess([rb[m] for m in sorted(rb)],
                                                     [rh[m] for m in sorted(rh)])
        cell["recent_first_month"] = min(rb) if rb else None
        cell["months"] = len(book_m)
        cell["book"] = p31.described([book[d] for d in sorted(book)])
        cell["hold_SPY"] = p31.described([hold[d] for d in sorted(hold)])
        cell["night"] = p31.described([legs["night"][d] for d in sorted(legs["night"])])
        cell["day_SPY"] = p31.described([legs["day"][d] for d in sorted(legs["day"])])
        cells[costing] = cell
    primary = cells["auction"]
    branch = branch_for(primary, primary["recent_excess"], checks, checks["sessions"],
                        primary["months"])
    payload: dict[str, Any] = {
        "prereg": "PR-040", "trials": 1, "branch": branch,
        "verdict": {"ACCEPT": "accept", "REJECT": "reject", "REFUSED": "refused"}.get(
            branch, "inconclusive"),
        "country": "USA",
        "as_of": {"bars": args.as_of, "auctions": args.auctions_as_of},
        "measured_span": {"first_session": FIRST.isoformat(), "last_session": LAST.isoformat(),
                          "years": round((LAST - FIRST).days / 365.25, 2)},
        "split": {"registered": "none - one book, one benchmark, a re-pricing of a registered rule",
                  "buys": "nothing a split could buy: no constant is chosen here"},
        "perturbations": {"registered": list(COSTINGS[1:]), "run": list(COSTINGS[1:])},
        "fees": {"sec_rate": SEC_RATE, "taf_per_share": TAF_PER_SHARE,
                 "cat_per_share": CAT_PER_SHARE, "missing_cross_penalty": MISSING_PENALTY},
        "checks": checks, "cells": cells,
    }
    if args.factors:
        book, _, _ = book_of(priced, "auction")
        found = fa.attribute(book, fa.load(args.factors), 252)
        payload["factor_attribution"] = {
            "alpha_annual": found.alpha_annual, "alpha_t": found.alpha_t, "betas": found.betas,
            "r_squared": found.r_squared, "periods": found.periods,
            "first": str(found.first), "last": str(found.last)}
    return payload


def power(args: argparse.Namespace) -> dict[str, Any]:
    """The primary contrast's WIDTH with bar prices and the fees - never its centre.

    The cross prints are not read: bars stand in for them, which is the price source `PR-035`
    already reported this book on, so the width is the only thing this adds.
    """
    priced = load(args, use_crosses=False)
    book, hold, _ = book_of(priced, "auction")
    cell = p37.paired_bootstrap(monthly(book), monthly(hold), 2000, SEED)
    width = cell["width"]
    return {"prereg": "PR-040", "power": True, "months": len(monthly(book)),
            "width_a_year": width, "half_width": width / 2,
            "minimum_detectable": width / 2 * (1.96 + 0.84) / 1.96,
            "note": "bars with the fees; widths only, no estimate is written"}


def report(payload: Mapping[str, Any]) -> None:
    checks = payload["checks"]
    print(f"PR-040   branch {payload['branch']}")
    print(f"  checks  sessions {checks['sessions']}  crossed {checks['crossed_share']:.1%}  "
          f"basis ok {checks['basis_ok']}  reproduces PR-035 {checks['reproduces_pr035']} "
          f"({checks['pr035_mean_daily_on_bars'] * 252:+.2%} a year on bars against "
          f"{PR035_MEAN_DAILY * 252:+.2%})")
    for costing, cell in payload["cells"].items():
        print(f"  {costing:<24} excess {cell['estimate']:+.2%} [{cell['lo']:+.2%}, {cell['hi']:+.2%}]"
              f"   last {RECENT_MONTHS} months {cell['recent_excess']:+.2%}   "
              f"book CAGR {cell['book'].get('cagr', math.nan):+.2%}   "
              f"SPY {cell['hold_SPY'].get('cagr', math.nan):+.2%}")
    if "factor_attribution" in payload:
        found = payload["factor_attribution"]
        print(f"  six-factor alpha {found['alpha_annual']:+.2%} a year, t {found['alpha_t']:+.2f}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--data", type=Path, required=True, help="the study's bar store directory")
    parser.add_argument("--as-of", help="the bar store's knowledge instant")
    parser.add_argument("--auctions", type=Path, help="the auction print store")
    parser.add_argument("--auctions-as-of", help="the auction store's knowledge instant")
    parser.add_argument("--factors", type=Path, help="French's daily factors, for DR-049's reading")
    parser.add_argument("--power", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.power:
        payload = power(args)
        out = args.out or POWER
        print(f"PR-040 power  {payload['months']} months   width {payload['width_a_year']:.4f} "
              f"a year   minimum detectable {payload['minimum_detectable']:.4f}")
    else:
        if args.auctions is None:
            parser.error("--auctions is required for the run")
        payload = run(args)
        out = args.out or RESULT
        report(payload)
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
