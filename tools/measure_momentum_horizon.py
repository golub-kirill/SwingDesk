"""Does the cross-sectional momentum spread depend on the HOLDING HORIZON, in this store?

**EXPLORATORY. This sets no parameter and advances no validation status.** It is a measurement
taken before authoring anything, which is what `AGENTS.md` §8 asks for, and it is reported as
exploratory because it was designed after `PR-012`'s and `PR-013`'s numbers were seen
(`PREREG_TEMPLATE` rule 3).

**The question, and why it is worth one command.** Both studies of this family reported nothing:
`PR-012` refused a verdict for want of sample at a 20-session hold, and `PR-013`'s six gross
intervals all included zero at a **5-session** horizon. Neither result is surprising once the
literature is read, and reading it is what prompted this:

  - Jegadeesh (1990) documents **short-term REVERSAL at the one-month horizon** - buying the past
    month's losers earned about 2% a month over 1934-1987.
  - Lehmann (1990) documents the same at a **weekly** horizon.
  - Jegadeesh & Titman (1993) document **momentum** over 3-12 month formation AND 3-12 month
    holding periods; their shortest reported holding period is **three months**.
  - Which is why the standard academic construction skips the most recent month - the "12-2" or
    "12-1" convention - to keep the reversal window out of the formation signal.

**So both of this project's studies measured inside the band where the literature documents the
OPPOSITE sign, and neither skipped the recent month.** `exit.max_holding_period` is 20 sessions
(`DR-012`, ratified), which is about one month - below the shortest horizon at which the effect is
documented and inside the window where reversal is.

This tool asks whether that shows up in **our own store** rather than only in the literature: it
measures the top-minus-bottom decile spread at several horizons, with and without the skip.

**Gross, deliberately.** `PR-013` established that at short horizons the cost constant dominates
and a net figure measures the rebalance schedule rather than the signal. The question here is
whether a signal exists at all and how it moves with horizon, so costs would only obscure it. **A
gross spread is not a tradeable result** and nothing here should be read as one.

    PYTHONPATH=$PWD/src python tools/measure_momentum_horizon.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr012 import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, bootstrap_interval
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates, _forward_returns, _spread
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules

#: Formation window in sessions. 252 is about twelve months - Jegadeesh & Titman's longest and
#: best-performing formation window, and the one the 12-2 convention is built on.
FORMATION = 252

#: Sessions skipped between the end of the formation window and the ranking date. 21 is about one
#: month: the reversal window Jegadeesh (1990) documents, which the standard construction excludes.
#: 0 is what `PR-012` and `PR-013` both used.
SKIPS = (0, 21)

#: Holding horizons in sessions. 5 and 20 are what this project has tested and what `DR-012` allows;
#: 63 and 126 are three and six months, inside the band J&T report.
HORIZONS = (5, 20, 63, 126)

#: The cross-section floor is `PR-013`'s own `MIN_NAMES_PER_DATE`, imported rather than restated -
#: a second copy of a number is the failure `AGENTS.md` §10.5 names, and `_spread` enforces it too.

#: `DR-003`'s liquidity rule, pinned exactly as `PR-012` and `PR-013` pin it, INCLUDING `adtv_lag=0`.
#:
#: **This restriction is not optional and the first run of this tool omitted it.** Without it the
#: cross-section is every name in the store with enough history - 2,742 rather than the ~1,100 the
#: rule admits - which loads the top decile with leveraged and inverse ETFs whose 12-month returns
#: are large and whose reversals are violent. That measures the store, not the universe, and it is
#: not comparable to either study.
RULE = rules.LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal(5_000_000),
    adtv_window=20, min_history=250, adtv_lag=0,
)


def _formation_return(closes: list[Decimal], end: int, skip: int) -> Decimal | None:
    """Return over the FORMATION window ending `skip` sessions before `end`.

    `None` when the name has too little history, which excludes it from that date's cross-section
    rather than sorting it to the bottom - `_spread`'s own rule, and for its reason.
    """
    stop = end - skip
    start = stop - FORMATION
    if start < 0 or stop <= start or stop > len(closes):
        return None
    first, last = closes[start], closes[stop - 1]
    if first <= 0:
        return None
    return (last - first) / first


def measure(store: BarStore, as_of: datetime) -> list[dict[str, object]]:
    """One row per (skip, horizon): the decile spread and its bootstrap interval."""
    series_by_name = {}
    for name in store.instrument_ids(as_of):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if len(series.bars) >= FORMATION + max(SKIPS) + max(HORIZONS) + 1:
            series_by_name[name] = series
    print(f"names with enough history: {len(series_by_name)}")

    closes = {n: [b.close for b in s.bars] for n, s in series_by_name.items()}
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}

    rows: list[dict[str, object]] = []
    for horizon in HORIZONS:
        forward = {n: _forward_returns(s, horizon) for n, s in series_by_name.items()}
        # Formation dates every `horizon` sessions, so the holding windows do not overlap and each
        # observation is independent. Overlapping windows would inflate the sample and narrow every
        # interval - the mistake that makes a spread look significant when it is one bet.
        calendar = sorted({d for f in forward.values() for d in f})
        dates = calendar[::horizon]
        # The liquidity rule, judged at each date's own bar - `PR-013`'s `_admitted_dates`, so the
        # rule is `reference_data`'s and not a second copy of it here.
        admitted = {n: _admitted_dates(s, RULE, dates) for n, s in series_by_name.items()}

        for skip in SKIPS:
            spreads: list[Decimal] = []
            for session in dates:
                scores: dict[str, Decimal] = {}
                for name, positions in index_of.items():
                    end = positions.get(session)
                    if end is None or session not in admitted[name]:
                        continue
                    value = _formation_return(closes[name], end, skip)
                    if value is not None:
                        scores[name] = value
                if len(scores) < MIN_NAMES_PER_DATE:
                    continue
                observed = {n: forward[n][session] for n in scores if session in forward[n]}
                spread = _spread(scores, observed)
                if spread is not None:
                    spreads.append(spread)

            if not spreads:
                rows.append({"skip": skip, "horizon": horizon, "n": 0})
                continue
            interval = bootstrap_interval(spreads, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES)
            if interval is None:
                rows.append({"skip": skip, "horizon": horizon, "n": len(spreads)})
                continue
            mean, low, high = interval
            rows.append({
                "skip": skip, "horizon": horizon, "n": len(spreads),
                "mean_gross": repr(mean), "ci_low": repr(low), "ci_high": repr(high),
                "excludes_zero": bool(low > 0 or high < 0),
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    as_of = datetime.now().astimezone()
    with BarStore(args.data / "bars.duckdb") as store:
        rows = measure(store, as_of)

    print()
    print(f"{'skip':>5} {'horizon':>8} {'dates':>6} {'gross spread':>14} {'95% interval':>26}")
    for row in rows:
        if not row.get("n"):
            print(f"{row['skip']:>5} {row['horizon']:>8} {0:>6}   (no deciled cross-sections)")
            continue
        if "mean_gross" not in row:
            print(f"{row['skip']:>5} {row['horizon']:>8} {row['n']:>6}   (too few to bootstrap)")
            continue
        flag = "  <- excludes zero" if row["excludes_zero"] else ""
        print(f"{row['skip']:>5} {row['horizon']:>8} {row['n']:>6} "
              f"{float(row['mean_gross']) * 100:>13.3f}% "
              f"[{float(row['ci_low']) * 100:>8.3f}%, {float(row['ci_high']) * 100:>8.3f}%]{flag}")

    print()
    print("EXPLORATORY and GROSS. Sets no parameter, advances no validation status, and a gross")
    print("spread is not a tradeable result (PR-013: at short horizons the cost constant dominates).")

    if args.out:
        args.out.write_text(json.dumps({
            "exploratory": True,
            "exploratory_reason": "designed after PR-012 and PR-013 results were seen "
                                  "(PREREG_TEMPLATE rule 3); measures no registered hypothesis",
            "formation": FORMATION, "skips": list(SKIPS), "horizons": list(HORIZONS),
            "min_names": MIN_NAMES_PER_DATE, "rows": rows,
            "run_at": as_of.isoformat(),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
