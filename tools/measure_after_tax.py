"""`PR-040`'s book against holding `SPY` after Canadian tax, as a taxed account would pay it. A measurement.

**Why this exists.** `PR-040` measured the book before tax. The owner's money is held in a TFSA
(owner, 2026-09-27), which pays no tax on investment income - unless it carries on a business of
trading, which *Ahamed v. The King*, 2023 TCC 17 (upheld, 2024 FCA 108) taxed as business income.
The book trades both auctions every session, so that is a live question, and when it applies the
two things compared are taxed on different clocks: the book turns over every session, so every
gain it makes is realised in the year it is made, while `SPY` held pays tax on its dividends
yearly and on its price gain only when sold.
A pre-tax margin can be a post-tax loss, and nothing in this project had measured which.

**What it computes.** The registered book at the crosses and the fees, and `SPY` held, as
`run_pr040` builds them - unchanged - re-read through a yearly tax model over a grid of marginal
rates, because the owner's own rate is theirs and this does not need it:

* **the book, as capital gains** - dividends taxed at the full marginal rate (foreign dividends,
  the US withholding credited), the net price gain of each calendar year at half the rate, a net
  capital loss carried forward against later gains;
* **the book, as business income** - the year's whole net gain at the full rate, a loss carried
  forward. Which of the two applies is a question for an accountant (`CARD-002` §2);
* **`SPY` held** - dividends taxed yearly at the full rate and reinvested after tax; the price gain
  either taxed at half the rate when sold at the window's end, or not at all while still held.

**What it leaves out, each named so nobody reads the table as more than it is:**

* the SUPERFICIAL LOSS rule. Under the capital-gains treatment, a loss on shares bought back within
  thirty days is denied and deferred, and the book buys the same two funds back every evening - so
  its losses would be deferred while its gains are taxed. That makes the capital-gains rows
  OPTIMISTIC for the book, never pessimistic;
* currency: returns are in US dollars; a Canadian return also carries the exchange rate, on both
  sides alike, and the conversion costs;
* instalments, credits other than the dividend withholding, and every provincial detail beyond one
  combined marginal rate.

**Nothing here is tax advice.** It is arithmetic on a registered result under stated assumptions.

    PYTHONPATH=$PWD/src python tools/measure_after_tax.py --data <dir> --as-of <t> \
        --auctions <store> --auctions-as-of <t>
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr040 as p40
from swingdesk.reference_data import calendar as cal

OUT = REPO / "docs" / "decisions" / "measurements" / "after-tax-2026-09-27.json"

#: Combined federal and provincial marginal rates. A grid, because the owner's rate is theirs.
RATES = (0.20, 0.30, 0.40, 0.50)
#: Canada's capital-gains inclusion rate. The 2024 proposal to raise it was withdrawn in 2025.
CAPITAL_INCLUSION = 0.5
TREATMENTS = ("capital_gains", "business_income")
RECENT_FROM = date(2022, 10, 1)


@dataclass(frozen=True)
class Day:
    """One session: the whole return, and the part of it that was a dividend."""

    session: date
    total: float
    dividend: float


def _carry(gain: float, carried: float) -> tuple[float, float]:
    """`(taxable gain, loss still carried)` - a loss joins the carry, a gain uses it up first."""
    if gain <= 0:
        return 0.0, carried - gain
    used = min(carried, gain)
    return gain - used, carried - used


def realised_yearly(days: Sequence[Day], rate: float, treatment: str) -> float:
    """Terminal wealth of 1 invested, every gain realised and taxed in the calendar year it is made.

    Tax is paid out of the account at each year's end, so it compounds as a cost.
    """
    wealth, carried = 1.0, 0.0
    by_year: dict[int, list[Day]] = {}
    for day in days:
        by_year.setdefault(day.session.year, []).append(day)
    for year in sorted(by_year):
        start, dividends = wealth, 0.0
        for day in by_year[year]:
            dividends += wealth * day.dividend
            wealth *= 1.0 + day.total
        gain = wealth - start
        if treatment == "business_income":
            taxable, carried = _carry(gain, carried)
            tax = rate * taxable
        elif treatment == "capital_gains":
            capital, carried = _carry(gain - dividends, carried)
            tax = rate * (max(dividends, 0.0) + CAPITAL_INCLUSION * capital)
        else:
            raise ValueError(f"unknown treatment {treatment!r}")
        wealth -= tax
    return wealth


def held(days: Sequence[Day], rate: float, sold_at_end: bool) -> float:
    """Terminal wealth of 1 held: dividends taxed yearly and reinvested after tax, the price gain
    taxed at the capital-gains inclusion when sold at the end, or not at all while held."""
    wealth, basis = 1.0, 1.0
    by_year: dict[int, list[Day]] = {}
    for day in days:
        by_year.setdefault(day.session.year, []).append(day)
    for year in sorted(by_year):
        dividends = 0.0
        for day in by_year[year]:
            dividends += wealth * day.dividend
            wealth *= 1.0 + day.total
        tax = rate * max(dividends, 0.0)
        wealth -= tax
        basis += dividends - tax
    if sold_at_end:
        wealth -= rate * CAPITAL_INCLUSION * max(wealth - basis, 0.0)
    return wealth


def cagr(multiple: float, first: date, last: date) -> float:
    years = (last - first).days / 365.25
    return multiple ** (1.0 / years) - 1.0 if years > 0 and multiple > 0 else float("nan")


def series(priced: Mapping[str, Sequence[Any]]) -> tuple[list[Day], list[Day]]:
    """The registered book and `SPY` held, day by day, each with its dividend part."""
    book, hold, _ = p40.book_of(priced, "auction")
    dividend_of: dict[str, dict[date, float]] = {}
    for fund, rows in priced.items():
        dividend_of[fund] = {now.session: now.dividend / before.close
                             for before, now in itertools.pairwise(rows)
                             if before.close > 0 and now.dividend
                             and cal.consecutive(cal.exchange_for(fund), before.session,
                                                 now.session)}
    night = [dividend_of[fund] for fund in p40.NIGHT_FUNDS]
    book_days = [Day(d, book[d], sum(n.get(d, 0.0) for n in night) / len(night))
                 for d in sorted(book)]
    hold_days = [Day(d, hold[d], dividend_of[p40.DAY_FUND].get(d, 0.0)) for d in sorted(hold)]
    return book_days, hold_days


def grid(book: Sequence[Day], hold: Sequence[Day]) -> dict[str, Any]:
    first, last = book[0].session, book[-1].session
    rows: list[dict[str, Any]] = []
    for rate in (0.0, *RATES):
        spy_sold = cagr(held(hold, rate, True), first, last)
        spy_kept = cagr(held(hold, rate, False), first, last)
        for treatment in TREATMENTS:
            ours = cagr(realised_yearly(book, rate, treatment), first, last)
            rows.append({"rate": rate, "treatment": treatment, "book_cagr": ours,
                         "spy_cagr_sold_at_end": spy_sold, "spy_cagr_still_held": spy_kept,
                         "excess_vs_sold": (1 + ours) / (1 + spy_sold) - 1,
                         "excess_vs_held": (1 + ours) / (1 + spy_kept) - 1})
    return {"first": first.isoformat(), "last": last.isoformat(), "rows": rows}


def build(args: argparse.Namespace) -> dict[str, Any]:
    priced = p40.load(args, use_crosses=True)
    book, hold = series(priced)
    recent_book = [d for d in book if d.session >= RECENT_FROM]
    recent_hold = [d for d in hold if d.session >= RECENT_FROM]
    return {
        "measurement": "after-tax-2026-09-27", "of": "PR-040", "exploratory": True,
        "note": "arithmetic on PR-040's registered book under stated tax assumptions; not tax "
                "advice. Capital-gains rows are OPTIMISTIC for the book: the superficial loss "
                "rule, which would defer its losses, is not modelled. USD returns; currency and "
                "conversion costs are left out",
        "as_of": {"bars": args.as_of, "auctions": args.auctions_as_of},
        "capital_inclusion": CAPITAL_INCLUSION,
        "whole_window": grid(book, hold),
        "last_48_months": grid(recent_book, recent_hold),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--auctions", type=Path, required=True)
    parser.add_argument("--auctions-as-of", required=True)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    payload = build(args)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for window in ("whole_window", "last_48_months"):
        block = payload[window]
        print(f"{window}: {block['first']} .. {block['last']}")
        for row in block["rows"]:
            print(f"  rate {row['rate']:.0%}  {row['treatment']:<16} book {row['book_cagr']:+.2%}  "
                  f"SPY sold {row['spy_cagr_sold_at_end']:+.2%} / held {row['spy_cagr_still_held']:+.2%}"
                  f"   excess vs sold {row['excess_vs_sold']:+.2%}  vs held {row['excess_vs_held']:+.2%}")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
