"""How precisely could a time-series momentum study on ETFs be read? Widths only, from random books.

**EXPLORATORY. It spends no trial and reads no return of the rule.** `RETURN_SOURCE_REGISTER` §3.3
names time-series momentum across asset classes as open and never tested here; the owner chose it
on 2026-09-26. Before a registration, `PREREG_TEMPLATE` rule 9 wants the minimum detectable effect
at the window actually used - and this project's habit is to size a study by its own variance, not
by a borrowed number.

**How, without reading the answer.** Each month every fund is held with probability `P`, and in
`BIL` otherwise - a RANDOM long/flat book on the same funds, weights and calendar the study would
use. The dispersion of the registered contrasts across a moving-block bootstrap of such a book is
what the design can separate from zero; the book's own level means nothing and is never printed.

**The universe, fixed by rule before any bar was fetched:** US-listed ETFs, one per market, across
equities, government and credit bonds, commodities, currencies and real estate, each launched on or
before 2007-01-31 so the window contains 2008. `BIL` is the cash leg and starts 2007-05-30.

**Measured 2026-09-26** (`docs/decisions/measurements/tsmom-power-2026-09-26.json`): over 230 months
the design separates an excess over `SPY` of about 11 points a year from zero, and about 9.5 over
`SPY` held at the book's own volatility. The published premium is a few points. The owner ruled the
same night not to spend a trial on it.

    python tools/fetch_history.py --data DIR SPY IWM ... BIL      # the funds, into a study store
    python tools/measure_tsmom_power.py --data DIR [--out FILE]
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(REPO / "src"))

from swingdesk.contracts.market import CorporateActionKind, Interval, Series
from swingdesk.market_data import BarStore

FUNDS = (
    "SPY", "IWM", "EFA", "EEM", "EWJ", "VGK", "FXI", "EWZ",   # equities
    "SHY", "IEF", "TLT", "TIP", "LQD",                        # government and credit bonds
    "GLD", "SLV", "DBC", "USO",                               # commodities
    "FXE", "FXB", "FXA", "FXC", "FXF",                        # currencies against the dollar
    "VNQ",                                                    # real estate
)
CASH = "BIL"
BENCHMARK = "SPY"

FIRST_MONTH = "2007-06"
P = 0.6
BLOCK = 3
RESAMPLES = 2000
SEED = 20260927
#: The same 80%-power scale `measure_sector_power.minimum_detectable` uses.
POWER_SCALE = (1.96 + 0.84) / 1.96


def month_end_index(closes: Sequence[tuple[date, float]], dividends: dict[date, float],
                    splits: dict[date, float]) -> dict[str, float]:
    """A total-return index at each month's last session: price, dividends reinvested, splits undone.

    A split's ratio divides the prior close, so the index does not jump; a missing close carries
    the index rather than inventing a move.
    """
    index, prior, out = 1.0, None, {}
    for session, close in closes:
        if close != close:  # NaN: no price that session
            continue
        if prior is not None:
            index *= (close + dividends.get(session, 0.0)) / (prior / splits.get(session, 1.0))
        prior = close
        out[session.strftime("%Y-%m")] = index
    return out


def cagr(returns: Sequence[float]) -> float:
    grown = 1.0
    for r in returns:
        grown *= 1.0 + r
    return float(grown ** (12.0 / len(returns))) - 1.0


def _sd(values: Sequence[float]) -> float:
    mean = sum(values) / len(values)
    variance: float = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return float(variance ** 0.5)


def contrasts(book: Sequence[float], spy: Sequence[float],
              cash: Sequence[float]) -> tuple[float, float]:
    """`DR-047` §3.5's two readings: geometric excess over `SPY`, and over `SPY` at the book's vol."""
    k = _sd(book) / _sd(spy)
    matched = [k * s + (1.0 - k) * c for s, c in zip(spy, cash, strict=True)]
    return cagr(book) - cagr(spy), cagr(book) - cagr(matched)


def widths(returns: dict[str, list[float]], lo: int, hi: int) -> dict[str, float]:
    """Interval widths of both contrasts for a random long/flat book over months `lo`..`hi`."""
    rng = random.Random(SEED)
    span = range(lo, hi)
    book = [sum(returns[f][i] if rng.random() < P else returns[CASH][i] for f in FUNDS) / len(FUNDS)
            for i in span]
    spy = [returns[BENCHMARK][i] for i in span]
    cash = [returns[CASH][i] for i in span]
    n = len(book)
    excess: list[float] = []
    matched: list[float] = []
    for _ in range(RESAMPLES):
        chosen: list[int] = []
        while len(chosen) < n:
            start = rng.randrange(n - BLOCK + 1)
            chosen.extend(range(start, start + BLOCK))
        chosen = chosen[:n]
        e, m = contrasts([book[j] for j in chosen], [spy[j] for j in chosen],
                         [cash[j] for j in chosen])
        excess.append(e)
        matched.append(m)
    out: dict[str, float] = {"months": float(n)}
    for name, draws in (("excess_vs_spy", excess), ("vs_volatility_matched_spy", matched)):
        draws.sort()
        width = draws[int(0.975 * RESAMPLES)] - draws[int(0.025 * RESAMPLES)]
        out[f"{name}_width"] = width
        out[f"{name}_minimum_detectable"] = width / 2.0 * POWER_SCALE
    return out


def load(path: Path, as_of: datetime) -> tuple[list[str], dict[str, list[float]]]:
    store = BarStore(path)
    try:
        indices: dict[str, dict[str, float]] = {}
        for fund in (*FUNDS, CASH):
            dividends: dict[date, float] = defaultdict(float)
            splits: dict[date, float] = {}
            for action in store.actions_as_of(fund, as_of):
                if action.kind is CorporateActionKind.DIVIDEND:
                    dividends[action.effective_date] += float(action.value)
                elif action.kind is CorporateActionKind.SPLIT:
                    splits[action.effective_date] = float(action.value)
            bars = store.as_of(fund, Interval.DAY, Series.RAW, as_of).bars
            indices[fund] = month_end_index([(b.session_date, float(b.close)) for b in bars],
                                            dividends, splits)
    finally:
        store.close()
    last = max(indices[CASH])
    # The last month is dropped: it is not over, and a partial month is not a month.
    months = sorted(m for m in indices[CASH] if FIRST_MONTH <= m < last)
    missing = [f for f in (*FUNDS, CASH) if any(m not in indices[f] for m in months)]
    if missing:
        raise SystemExit(f"these funds lack a month-end in the window: {', '.join(missing)}")
    returns = {f: [indices[f][b] / indices[f][a] - 1.0 for a, b in itertools.pairwise(months)]
               for f in (*FUNDS, CASH)}
    return months, returns


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--data", type=Path, required=True,
                        help="a study store holding the funds (tools/fetch_history.py)")
    parser.add_argument("--as-of", help="the store's knowledge instant, ISO; default now")
    parser.add_argument("--out", type=Path, help="write the widths as JSON here")
    args = parser.parse_args(argv)

    as_of = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(UTC)
    months, returns = load(args.data / "bars.duckdb", as_of)
    n = len(months) - 1
    windows = {"whole": widths(returns, 0, n), "last_48_months": widths(returns, n - 48, n)}
    payload: dict[str, Any] = {
        "measurement": "tsmom-power", "exploratory": True, "trials_spent": 0,
        "funds": list(FUNDS), "cash": CASH, "benchmark": BENCHMARK,
        "window": {"first_month_end": months[0], "last_month_end": months[-1]},
        "random_book": {"p_long": P, "block": BLOCK, "resamples": RESAMPLES, "seed": SEED},
        "windows": windows,
    }
    for name, cell in windows.items():
        print(f"{name:>15}  {int(cell['months'])} months   excess vs SPY: MDE "
              f"{cell['excess_vs_spy_minimum_detectable']:.4f}   vs volatility-matched SPY: MDE "
              f"{cell['vs_volatility_matched_spy_minimum_detectable']:.4f}")
    if args.out:
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"written to {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
