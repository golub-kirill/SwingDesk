"""How much of the ONE significant result survives a short leg you could actually borrow?

**The result this interrogates.** `measure_momentum_horizon` found the decile spread excluding zero
at 126 sessions - **+7.271% [+1.899, +12.512]** - and it is the only interval-excluding-zero finding
about this family in the store. `EVIDENCE_SUMMARY` §8a then showed the tradeable half does not
survive the conversion: top decile against `SPY` is **+4.805% [-0.009, +10.125]**, which by this
project's own `b.expectancy` standard is not established.

So the significant number needs a SHORT LEG, and this system is long-only by choice rather than by
constraint (`trade_management/portfolio.py`: *"this system is long-only today"*). Before anyone
builds one, the question worth asking is whether the spread survives being restricted to names a
short leg could realistically reach.

**The restriction, and why it is a PROXY and said so.** Borrowability is not in this store and is
not in daily bars. What is in the store is dollar volume, and borrow availability tracks liquidity
closely enough to bound the question: a name in the most-traded quartile of an already
liquidity-screened universe is very likely borrowable, and one at the bottom of that universe is the
first to be hard-to-borrow. **This is a bound, not a borrow list.** The venue publishes
`easy_to_borrow` per asset, that flag is TODAY's, and applying today's flag to a decade of history
would be the population-across-time error `DR-040` already had to correct once.

**Four arms, identical in every other respect** - same formation, same liquidity rule judged at each
date, same non-overlapping dates, same bootstrap seed:

  1. **long-short, unrestricted** - the published number, reproduced as a control
  2. **long-short, short leg from the top HALF by dollar volume**
  3. **long-short, short leg from the top QUARTILE by dollar volume**
  4. **long-only** - the tradeable half today, also reproduced as a control

**EXPLORATORY. It sets no parameter and advances no validation status.** It also does not price a
short: borrow fees, hard-to-borrow rates, Regulation SHO's locate requirement and the uptick rule
are all real costs of the leg and none of them is measured here. **A spread that survives this is
not thereby profitable** - it is merely not refuted by the one constraint that can be checked from
the store.

    python tools/measure_short_leg.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_decile_persistence import one_sided
from measure_momentum_horizon import FORMATION, RULE, _formation_return
from run_pr012 import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, bootstrap_interval
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates, _forward_returns
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data.universe import average_dollar_volume

#: `rs.benchmark`, `assumed:DR-018`.
BENCHMARK = "SPY"

#: `screen.relative_strength_rule` = `top_decile`, owner ruling via `DR-030`.
DECILE = Decimal("0.10")

#: The horizon the significant result lives at, and the one `DR-012` ratified.
HORIZONS = (20, 126)

#: `DR-017`'s window. Same as the liquidity rule's, so a name has one liquidity opinion.
ADTV_WINDOW = 20

#: The short leg's reachable fractions of the admitted universe, by dollar volume. `1.0` is the
#: unrestricted control - the arm the published number was computed on.
SHORT_POOLS = (Decimal("1.0"), Decimal("0.50"), Decimal("0.25"))

#: `DR-005`, ratified: 25 bps per side. `DR-040` measures 26.46 at the open, which is where
#: `CARD-001` trades, so the ratified constant is close to right for this construction.
SLIPPAGE_BPS = Decimal("25")

#: **A long-short rebalance is FOUR sides, not two**, and that is the whole reason this column
#: exists. The long leg is bought and sold and so is the short leg; a spread is the difference
#: between two books, each of which pays its own round trip. Charging one round trip - the habit
#: from every long-only measurement in this repository - would halve the cost of the arm that
#: needs it most.
LEGS = 2
SIDES_PER_LEG = 2


def eligible_shorts(adtv: dict[str, Decimal], fraction: Decimal) -> set[str]:
    """The most-traded `fraction` of the names that have a dollar-volume reading on this date.

    A name with no reading is excluded rather than ranked last: an unmeasured name is not a thin
    one, and sorting it to the bottom would fill the short pool's exclusion with names nobody
    measured - the mistake `run_pr013._spread` documents for scores.
    """
    if fraction >= 1:
        return set(adtv)
    ranked = sorted(adtv.items(), key=lambda pair: (-pair[1], pair[0]))
    size = int(len(ranked) * fraction)
    return {name for name, _ in ranked[:size]}


def _mean(values: list[Decimal]) -> Decimal:
    """The mean turnover, or zero when a leg never traded. A long-only arm has no bottom leg and
    its `bottom_turnover` is zero by construction, not by accident."""
    return sum(values, Decimal(0)) / len(values) if values else Decimal(0)


def selected(
    scores: dict[str, Decimal],
    forward: dict[str, Decimal],
    shortable: set[str] | None,
) -> tuple[list[str], list[str]] | None:
    """`(top, bottom)` instrument ids at the decile cutoff, or None when the cross-section refuses.

    **Extracted for `DR-041`'s sibling correction, and it removes a duplication that was already
    there**: `restricted_spread` and `long_only_excess` each ranked the cross-section themselves,
    so the two could have drifted about where a decile falls. Now one function decides and both
    read it - and the names it returns are what makes TURNOVER measurable at all, which is the
    whole reason this refactor happened.

    The ranking is never restricted; only the short SELECTION is. A name that cannot be borrowed
    still competes for the top decile and still sets where the deciles fall.
    """
    ranked = sorted(
        ((s, n) for n, s in scores.items() if n in forward),
        key=lambda pair: (-pair[0], pair[1]),
    )
    if len(ranked) < MIN_NAMES_PER_DATE:
        return None
    size = int(len(ranked) * DECILE)
    if size < 1:
        return None
    top = [n for _, n in ranked[:size]]
    if shortable is None:
        return top, [n for _, n in ranked[-size:]]
    # Worst first among borrowable names, then the same number of positions as the long leg. A
    # short book smaller than the long one is a different portfolio, not a restricted version.
    borrowable = [n for _, n in reversed(ranked) if n in shortable]
    if len(borrowable) < size:
        return None
    return top, borrowable[:size]


def restricted_spread(
    scores: dict[str, Decimal],
    forward: dict[str, Decimal],
    shortable: set[str] | None,
) -> Decimal | None:
    """Top-decile mean minus bottom-decile mean, with the bottom drawn only from `shortable`.

    **The ranking is never restricted - only the short SELECTION is.** A name that cannot be
    borrowed still competes for the top decile and still sets where the deciles fall; it simply
    cannot be sold short. Restricting the ranking instead would change the long leg too and make the
    arms incomparable, which would answer a different question than the one asked.

    `shortable=None` is the unrestricted control and must reproduce `run_pr013._spread` exactly.
    """
    picked = selected(scores, forward, shortable)
    if picked is None:
        return None
    top, bottom = ([forward[n] for n in side] for side in picked)
    return (sum(top, Decimal(0)) / len(top)) - (sum(bottom, Decimal(0)) / len(bottom))


def rebalance_cost(
    arm: str, per_side_bps: Decimal, top_turnover: Decimal, bottom_turnover: Decimal,
) -> Decimal:
    """What one rebalance of this arm costs, charged on the fraction that actually TRADES.

    **This function charged GROSS turnover until 2026-09-07 and the correction is `PR-014`'s.**
    It returned `legs x 2 x bps` at every formation - the whole book sold and rebought - when a name
    still in the decile at the next formation is HELD. `PR-014` amendment A-3 has the full argument
    and the size of the error there: 2.7x at twenty sessions and nil at a year, so it was not a
    constant, it was a monotone function of the holding period this study varies.

    **Each leg is charged its OWN turnover.** `decile-persistence-2026-09-07` measured the bottom
    decile churning about two points more than the top at every horizon, so doubling the long leg's
    number would be an assumption where a measurement is available - the same class of assumption
    the correction is about.

    **Borrow is still not in here and still cannot be.** A short position pays a borrow rate for
    every day it is held and this project has no source for it, so the figure is a FLOOR on the cost
    of the short arms and an exact charge for the long-only one.
    """
    side = per_side_bps / Decimal(10000)
    if arm == "long_only":
        return top_turnover * Decimal(SIDES_PER_LEG) * side
    return (top_turnover + bottom_turnover) * Decimal(SIDES_PER_LEG) * side


def gross_rebalance_cost(arm: str, per_side_bps: Decimal) -> Decimal:
    """What this tool charged before 2026-09-07, kept so the size of the error stays visible.

    `PR-014` keeps the same figure beside its corrected one for the same reason: a re-run that
    quietly absorbed the difference would leave nothing to check the correction against.
    """
    legs = 1 if arm == "long_only" else LEGS
    return Decimal(legs * SIDES_PER_LEG) * per_side_bps / Decimal(10000)


def long_only_excess(
    scores: dict[str, Decimal], forward: dict[str, Decimal], benchmark: Decimal
) -> Decimal | None:
    """Top-decile mean minus the benchmark - the half a long-only book can hold today."""
    picked = selected(scores, forward, None)
    if picked is None:
        return None
    top = [forward[n] for n in picked[0]]
    return (sum(top, Decimal(0)) / len(top)) - benchmark


def measure(store: BarStore, as_of: datetime) -> list[dict[str, object]]:
    series_by_name = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= FORMATION + max(HORIZONS) + 1:
            series_by_name[name] = series
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to serve as the benchmark")

    closes = {n: [b.close for b in s.bars] for n, s in series_by_name.items()}
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    print(f"  instruments with enough history: {len(series_by_name)}")

    rows: list[dict[str, object]] = []
    for horizon in HORIZONS:
        forward = {n: _forward_returns(s, horizon) for n, s in series_by_name.items()}
        calendar = sorted({d for f in forward.values() for d in f})
        dates = calendar[::horizon]
        admitted = {n: _admitted_dates(s, RULE, dates) for n, s in series_by_name.items()}
        bench = forward[BENCHMARK]

        collected: dict[str, list[Decimal]] = {f"short_pool={p}": [] for p in SHORT_POOLS}
        collected["long_only"] = []
        # Turnover per (arm, leg), and the book each arm last held. Reset per horizon, because a
        # 20-session book and a 126-session one are different books that happen to share a ranking.
        turns: defaultdict[tuple[str, str], list[Decimal]] = defaultdict(list)
        held: dict[tuple[str, str], list[str]] = {}
        for session in dates:
            if session not in bench:
                continue
            scores: dict[str, Decimal] = {}
            adtv: dict[str, Decimal] = {}
            for name, positions in index_of.items():
                end = positions.get(session)
                if end is None or session not in admitted[name]:
                    continue
                value = _formation_return(closes[name], end, 0)
                if value is None:
                    continue
                scores[name] = value
                volume = average_dollar_volume(series_by_name[name], ADTV_WINDOW, end)
                if volume is not None:
                    adtv[name] = volume
            if len(scores) < MIN_NAMES_PER_DATE:
                continue
            observed = {n: forward[n][session] for n in scores if session in forward[n]}

            for pool in SHORT_POOLS:
                arm = f"short_pool={pool}"
                shortable = None if pool >= 1 else eligible_shorts(adtv, pool)
                value = restricted_spread(scores, observed, shortable)
                if value is not None:
                    collected[arm].append(value)
                # The NAMES, so the cost can be charged on what actually trades rather than on a
                # constant. Measured against this arm's OWN previous selection: the arms hold
                # different books and a turnover borrowed from one is an assumption in the other.
                picked = selected(scores, observed, shortable)
                if picked is not None:
                    for side, names in zip(("top", "bottom"), picked, strict=True):
                        turns[(arm, side)].append(one_sided(held.get((arm, side), []), names))
                        held[(arm, side)] = names
            excess = long_only_excess(scores, observed, bench[session])
            if excess is not None:
                collected["long_only"].append(excess)
            picked = selected(scores, observed, None)
            if picked is not None:
                turns[("long_only", "top")].append(one_sided(held.get(("long_only", "top"), []),
                                                             picked[0]))
                held[("long_only", "top")] = picked[0]

        for arm, values in collected.items():
            interval = bootstrap_interval(values, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES)
            row: dict[str, object] = {"horizon": horizon, "arm": arm, "n": len(values)}
            if interval:
                mean, low, high = interval
                top_turn = _mean(turns[(arm, "top")])
                bottom_turn = _mean(turns[(arm, "bottom")])
                cost = float(rebalance_cost(arm, SLIPPAGE_BPS, top_turn, bottom_turn))
                row |= {
                    "mean": round(mean, 6), "low": round(low, 6), "high": round(high, 6),
                    "excludes_zero": low > 0 or high < 0,
                    "top_turnover": float(round(top_turn, 4)),
                    "bottom_turnover": float(round(bottom_turn, 4)),
                    "rebalance_cost": round(cost, 6),
                    "rebalance_cost_as_first_published": float(round(
                        gross_rebalance_cost(arm, SLIPPAGE_BPS), 6)),
                    "net_mean": round(mean - cost, 6),
                    "net_low": round(low - cost, 6), "net_high": round(high - cost, 6),
                    "net_excludes_zero": (low - cost) > 0 or (high - cost) < 0,
                }
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_short_leg")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--as-of", default=None,
                        help="read the store at this knowledge instant instead of the latest. The "
                             "store is bitemporal, so this reconstructs the sample a PAST run saw "
                             "- which is the only way to tell a cost correction apart from the "
                             "2026-09-06 backfill when both land in one re-run (PR-014 A-3)")
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/short-leg-2026-09-06.json"))
    args = parser.parse_args()

    store = BarStore(args.data / "bars.duckdb")
    as_of = (
        datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    )
    if as_of is None:
        print("the bar store is empty")
        return 1
    print(f"as_of {as_of.isoformat()}   formation {FORMATION}   bootstrap "
          f"{BOOTSTRAP_RESAMPLES} resamples, seed {BOOTSTRAP_SEED}")
    rows = measure(store, as_of)
    store.close()

    print("\n  GROSS, non-overlapping dates. The short leg is drawn only from the most-traded")
    print("  fraction named; the RANKING is never restricted.\n")
    print(f"  {'horizon':>8}  {'arm':<18}{'n':>5}{'gross':>10}{'95% interval':>26}"
          f"{'net':>11}{'net interval':>26}")
    for row in rows:
        if "mean" not in row:
            print(f"  {row['horizon']:>8}  {row['arm']:<18}{row['n']:>5}   too few dates")
            continue
        star = " *" if row["excludes_zero"] else "  "
        net_star = " *" if row["net_excludes_zero"] else "  "
        print(f"  {row['horizon']:>8}  {row['arm']:<18}{row['n']:>5}"
              f"{row['mean'] * 100:>+9.3f}%{star}"
              f"  [{row['low'] * 100:+7.3f}%, {row['high'] * 100:+7.3f}%]"
              f"{row['net_mean'] * 100:>+10.3f}%{net_star}"
              f"  [{row['net_low'] * 100:+7.3f}%, {row['net_high'] * 100:+7.3f}%]")
    print("\n  * = the bootstrap interval excludes zero")
    print(f"  Net charges {SLIPPAGE_BPS} bps a side: FOUR sides for a spread (both legs turn) and")
    print("  two for the long-only control. Per REBALANCE, so a longer horizon pays it less often.")
    print("  NOT priced: borrow fees, hard-to-borrow rates, Regulation SHO locates, the uptick")
    print("  rule. Every one of those is a cost of the SHORT leg, so the net column above is a")
    print("  FLOOR on the spread arms' cost and an exact charge on long-only.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "as_of": as_of.isoformat(),
        "formation": FORMATION,
        "decile": str(DECILE),
        "benchmark": BENCHMARK,
        "short_pools": [str(p) for p in SHORT_POOLS],
        "adtv_window": ADTV_WINDOW,
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED},
        "rows": rows,
        "gross_of_costs": True,
        "exploratory": True,
        "not_measured": [
            "borrowability itself - dollar volume is a PROXY and the venue's easy_to_borrow flag "
            "is today's, which cannot be applied to a decade of history",
            "borrow fees, hard-to-borrow rates, Regulation SHO locates, the uptick rule",
            "costs of any kind - every figure here is gross",
            "survivorship - the directory is today's",
        ],
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
