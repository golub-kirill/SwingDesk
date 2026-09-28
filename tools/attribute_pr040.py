"""EXPLORATORY: `PR-040`'s book against `SPY`, re-read by calendar year and by trailing window.

**Why this exists.** `PR-040` gated the last 48 months on the SIGN of one point estimate, as
`DR-055` §1.3 wrote the condition, and reported no interval for it. A proof read by its sign alone
says nothing about how far that sign could be trusted, and the owner asked for conclusions that
hold. This reports the width the registered bootstrap gives those 48 months, and the same excess
by calendar year and over the trailing 12, 24, 36 and 48 months - every window fixed here, none
chosen on its answer.

**So this spends no trial and carries no verdict.** It adds no fund, price, cost or rule: it
imports `run_pr040`'s loading and book unchanged and groups the same monthly returns differently.
A sub-window that reads worse than the whole is a smaller sample, not a refutation - and one that
reads better is not a confirmation either.

    PYTHONPATH=$PWD/src python tools/attribute_pr040.py --data <dir> --as-of <t> \
        --auctions <store> --auctions-as-of <t>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr037 as p37
import run_pr040 as p40

RESULT = p40.RESULT.parent / "PR-040-attribution.json"

#: Trailing windows in months, read back from the last month of the window.
TRAILING = (12, 24, 36, 48)
COSTINGS = ("auction", "auction_plus_half_cent")


def excess(book: Mapping[str, float], hold: Mapping[str, float], months: Sequence[str]) -> float:
    """Geometric excess over `months`, the same statistic the registration reads."""
    return p37.geometric_excess([book[m] for m in months], [hold[m] for m in months])


def by_year(book: Mapping[str, float], hold: Mapping[str, float]) -> dict[str, float]:
    """Each calendar year's compounded book over compounded `SPY`, less one. A part year is a part
    year - 2016 and the window's last year are not annualised."""
    out: dict[str, float] = {}
    for year in sorted({m[:4] for m in book if m in hold}):
        grown_book = grown_hold = 1.0
        for month in sorted(m for m in book if m.startswith(year) and m in hold):
            grown_book *= 1.0 + book[month]
            grown_hold *= 1.0 + hold[month]
        out[year] = grown_book / grown_hold - 1.0
    return out


def trailing(book: Mapping[str, float], hold: Mapping[str, float],
             windows: Sequence[int] = TRAILING) -> dict[str, float]:
    shared = sorted(m for m in book if m in hold)
    return {f"last_{n}_months": excess(book, hold, shared[-n:]) for n in windows if n <= len(shared)}


def build(args: argparse.Namespace) -> dict[str, Any]:
    priced = p40.load(args, use_crosses=True)
    cells: dict[str, Any] = {}
    for costing in COSTINGS:
        book, hold, _ = p40.book_of(priced, costing)
        book_m, hold_m = p40.monthly(book), p40.monthly(hold)
        recent_book, recent_hold = p40.recent(book_m), p40.recent(hold_m)
        cells[costing] = {
            "last_48_months_interval": p37.paired_bootstrap(recent_book, recent_hold,
                                                            p40.RESAMPLES, p40.SEED),
            "trailing": trailing(book_m, hold_m),
            "by_year": by_year(book_m, hold_m),
        }
    return {"for": "PR-040", "exploratory": True,
            "note": "descriptive re-reading of PR-040's registered book; no trial, no verdict",
            "as_of": {"bars": args.as_of, "auctions": args.auctions_as_of},
            "cells": cells}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--auctions", type=Path, required=True)
    parser.add_argument("--auctions-as-of", required=True)
    parser.add_argument("--out", type=Path, default=RESULT)
    args = parser.parse_args(argv)
    payload = build(args)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for costing, cell in payload["cells"].items():
        interval = cell["last_48_months_interval"]
        print(f"{costing:<24} last 48 months {interval['estimate']:+.2%} "
              f"[{interval['lo']:+.2%}, {interval['hi']:+.2%}]")
        print("    trailing  " + "  ".join(f"{k.split('_')[1]}m {v:+.2%}"
                                          for k, v in cell["trailing"].items()))
        print("    by year   " + "  ".join(f"{k} {v:+.1%}" for k, v in cell["by_year"].items()))
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
