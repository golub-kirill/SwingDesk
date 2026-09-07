"""Which index is the honest passive alternative to this universe? `rs.benchmark` is `assumed`.

**The question is not academic and `PR-014` is why.** Its registered control measured the
equal-weighted ADMITTED UNIVERSE against `SPY` and found it **loses by 1.58% a year** on the primary
window and **4.27%** on the holdout. The entire pool a card selects from trails the index that
judges it. That is not a property of any strategy; it is a property of comparing an equal-weighted
mid-cap book to a capitalisation-weighted index that a handful of mega-caps carried over 2016-2026.

**And the comparison is load-bearing rather than cosmetic.** `criteria.yml`'s `k.strategy_rejected`
fires when *"the expectancy CI lies entirely below the benchmark"*. A wrong benchmark rejects a
working strategy or accepts a broken one, directly.

`rs.benchmark` is **`SPY`, status `assumed`, `assumed:DR-018`**, and has never been tested.

**THE SELECTION CRITERION IS TRACKING, NOT EXCESS, AND THAT IS THE WHOLE DESIGN.** Choosing the
index a card beats is the data snooping the course prohibits by name. The honest benchmark is the
one an investor would hold INSTEAD of this universe - the closest passive alternative - and
closeness is measured by correlation and tracking error against the universe itself, with the
strategy nowhere in the calculation.

The excess columns are printed **after** and are marked as what they are: a consequence of the
choice, never an input to it.

**EXPLORATORY. It sets no parameter.** `rs.benchmark` is ratified and only the owner moves it; this
is the measurement a decision record would argue from.

    python tools/measure_benchmark_fit.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import (
    DECILE,
    LOOKBACK,
    PERIODS_PER_YEAR,
    STEP,
    book_return,
    period_return,
    select,
)
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.market_data import BarStore

#: The passive alternatives a US equity book could actually be held instead of. Each is in the
#: store. `SPY` is the incumbent and is included so the incumbent competes on the same terms.
CANDIDATES = ("SPY", "RSP", "IWM", "MDY", "VTI", "QQQ")

#: `PR-014`'s accepted holding period, used only to price the CONSEQUENCE of each choice.
HORIZON = 126


@dataclass(frozen=True, slots=True)
class Candidate:
    """All three fields `ranking.Ranked` declares.

    **Defined here rather than imported from `run_pr014`, deliberately.** That tool's own candidate
    carries only two of the three, which works because `ByMarketPathStrength` never reads the third
    - but completing it there would change a file whose committed evidence must stay reproducible
    by exactly the version that produced it. The gap is recorded in `TODO.md` instead of patched in
    passing.
    """

    instrument_id: str
    index: int
    session_date: date


def tracking(universe: list[Decimal], benchmark: list[Decimal]) -> dict[str, float]:
    """How closely a benchmark follows the universe: correlation, tracking error, and mean gap.

    **Tracking error is the deciding number**: the standard deviation of the period-by-period
    difference, annualised. A benchmark that moves with the universe is the thing an investor holds
    instead of it, whatever the average gap turns out to be - and the average gap is precisely what
    must NOT decide, because choosing the index a strategy beats is choosing the answer.
    """
    gaps = [float(u - b) for u, b in zip(universe, benchmark, strict=True)]
    us = [float(v) for v in universe]
    bs = [float(v) for v in benchmark]
    annualise = float(PERIODS_PER_YEAR) ** 0.5
    return {
        "correlation": statistics.correlation(us, bs) if len(us) > 1 else 0.0,
        "tracking_error_annual": statistics.stdev(gaps) * annualise if len(gaps) > 1 else 0.0,
        "mean_gap_annual": statistics.mean(gaps) * float(PERIODS_PER_YEAR),
        "periods": len(gaps),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_benchmark_fit")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/benchmark-fit-2026-09-06.json"))
    args = parser.parse_args()

    store = BarStore(args.data / "bars.duckdb")
    as_of = store.latest_knowledge_time()
    if as_of is None:
        print("the bar store is empty")
        return 1
    series_by_name: dict[str, BarSeries] = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= LOOKBACK + HORIZON + STEP + 1:
            series_by_name[name] = series
    store.close()

    missing = [c for c in CANDIDATES if c not in series_by_name]
    if missing:
        raise SystemExit(f"not in the store with enough history: {', '.join(missing)}")

    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    calendar = [b.session_date for b in series_by_name["SPY"].bars]
    rebalances = calendar[LOOKBACK::STEP]
    admitted = {n: _admitted_dates(s, RULE, rebalances) for n, s in series_by_name.items()}
    print(f"as_of {as_of.isoformat()}   instruments {len(series_by_name)}   "
          f"rebalance dates {len(rebalances)}")

    # The universe's own return, and the card's, over each 21-session period. One pass.
    universe: list[Decimal] = []
    card: list[Decimal] = []
    by_candidate: dict[str, list[Decimal]] = {c: [] for c in CANDIDATES}
    k = max(1, round(HORIZON / STEP))
    picks: dict[date, list[str]] = {}
    for i, session in enumerate(rebalances[:-1]):
        nxt = rebalances[i + 1]
        held = [
            Candidate(n, positions[session], session)
            for n, positions in index_of.items()
            if session in positions and session in admitted[n]
        ]
        if len(held) < MIN_NAMES_PER_DATE:
            continue
        ranker = ByMarketPathStrength(
            series=series_by_name, benchmark=series_by_name["SPY"], lookback=LOOKBACK
        )
        picks[session] = select(ranker, held, DECILE)[0]

        names = [c.instrument_id for c in held]
        pool = book_return(names, series_by_name, index_of, session, nxt)
        legs = [rebalances[i - j] for j in range(k) if i - j >= 0 and rebalances[i - j] in picks]
        if pool is None or len(legs) < k:
            continue
        held_returns = [
            r for r in (book_return(picks[f], series_by_name, index_of, session, nxt) for f in legs)
            if r is not None
        ]
        marks = {}
        for candidate in CANDIDATES:
            value = period_return(
                series_by_name[candidate],
                index_of[candidate][session], index_of[candidate][nxt],
            ) if session in index_of[candidate] and nxt in index_of[candidate] else None
            if value is None:
                break
            marks[candidate] = value
        if len(marks) != len(CANDIDATES) or not held_returns:
            continue
        universe.append(pool)
        card.append(sum(held_returns, Decimal(0)) / len(held_returns))
        for candidate, value in marks.items():
            by_candidate[candidate].append(value)

    if len(universe) < 2:
        print("too few complete periods to compare")
        return 1

    rows = []
    for candidate in CANDIDATES:
        fit = tracking(universe, by_candidate[candidate])
        excess = [c - b for c, b in zip(card, by_candidate[candidate], strict=True)]
        fit["card_excess_annual"] = float(
            Decimal(str(statistics.mean([float(v) for v in excess]))) * PERIODS_PER_YEAR
        )
        fit["benchmark"] = candidate
        fit["incumbent"] = candidate == "SPY"
        rows.append(fit)

    ordered = sorted(rows, key=lambda r: r["tracking_error_annual"])
    print(f"\nWHAT THE UNIVERSE ACTUALLY TRACKS - {len(universe)} periods of {STEP} sessions")
    print("  the DECIDING columns are correlation and tracking error; the card is not in them\n")
    print(f"  {'index':<8}{'corr':>8}{'tracking err':>15}{'universe gap':>15}   {'| card excess':>14}")
    for row in ordered:
        mark = "  <- rs.benchmark today" if row["incumbent"] else ""
        print(f"  {row['benchmark']:<8}{row['correlation']:>8.3f}"
              f"{row['tracking_error_annual'] * 100:>14.2f}%"
              f"{row['mean_gap_annual'] * 100:>+14.2f}%"
              f"   | {row['card_excess_annual'] * 100:>+11.2f}%{mark}")

    best = ordered[0]
    print(f"\n  CLOSEST PASSIVE ALTERNATIVE: {best['benchmark']} "
          f"(tracking error {best['tracking_error_annual'] * 100:.2f}% a year)")
    print("  The card-excess column is a CONSEQUENCE of the choice and must not decide it:")
    print("  picking the index a strategy beats is choosing the answer.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "as_of": as_of.isoformat(),
        "step": STEP, "horizon": HORIZON, "lookback": LOOKBACK,
        "periods": len(universe),
        "incumbent": "SPY",
        "selection_criterion": "lowest annualised tracking error against the equal-weighted "
                               "admitted universe. Card excess is reported and is NOT an input",
        "rows": ordered,
        "exploratory": True,
        "not_measured": [
            "an index's fees and tracking of its own benchmark",
            "survivorship - the directory is today's",
            "whether an equal-weighted book is what the owner wants to hold at all, which is a "
            "different question than which index it resembles",
        ],
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
