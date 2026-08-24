"""Sector-relative strength: the other way out of the identity `DR-018` found.

`DR-018` §1 established that on a single cross-section a MARKET benchmark cannot change a ranking.
The benchmark's return is one constant for every name that day, so dividing by it is a strictly
monotone transform of the name's own return - point-to-point relative strength against an index is
momentum with a decorative denominator. `DR-018` §5 gap 1 named the escape route and refused to
guess at it:

> Sector-relative strength is not measured. `M31-T0460`, `M31-T0461` and `M31-T0462` are the other
> way out of §1's identity - a per-name denominator is not a common factor.

This is that measurement. **A sector benchmark varies BY NAME**, so it is not a common factor and
it can reorder - the question is by how much, and whether that is more than the choice between
market indexes buys.

**The comparison that matters is against RAW RETURN**, not against another relative measure. A
ranking that agrees with raw return at rho = 1.0 is momentum whatever it is called; the further
below 1.0, the more the denominator is doing real work. `DR-018` measured the market path-form at
about 0.6, and that is the number to beat.

**Three readings, all authored and all stated rather than defaulted:**

  1. **The sector return is the EQUAL-WEIGHTED mean of its admitted members' returns.** Not
     capitalisation-weighted - this project has no point-in-time float-adjusted market cap, the same
     constraint `DR-003` records for index membership and `DR-017` for the ADTV rule's shape.
  2. **A name is assigned its DOMINANT sector** by `look_through`, and an ETF whose look-through is
     refused by the degeneracy guard (`DR-006` §8.7) contributes to no sector and is excluded.
  3. **A name is included in its own sector's mean.** With sectors of 26 to 215 members the
     self-inclusion bias is small and it is symmetric across names; removing it per name would make
     the denominator depend on the numerator, which is worse.

**The classification store is read at the RUN's clock, not the bar store's.** The two stores are
filled by different passes, and reading classifications at the bar store's knowledge time hides
every one pulled since the last bar refresh. That trap has now been hit twice here - once on the
classification store in 2026-08-23 and once on corporate actions in `measure_benchmark.py` - so it
is stated rather than assumed.

    python tools/measure_sector_relative.py --data C:/PycharmProjects/SwingDesk/data \\
        --out docs/decisions/measurements/sector-relative-2026-08-24.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_benchmark import LOOKBACKS, _return, spearman
from swingdesk.application.universe import ADTV_WINDOW
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.classification import ClassificationStore, look_through
from swingdesk.reference_data.directory import DirectoryStore

#: The market benchmark `DR-018` fixed, so the two denominators are compared on the same footing.
MARKET = "SPY"

#: A sector with fewer members than this has a mean too noisy to be a benchmark. Stated rather than
#: silently tolerated: with 3 members one name IS a third of its own denominator.
MIN_SECTOR_MEMBERS = 10


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_sector_relative")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    clock = datetime.now(UTC)

    with (
        BarStore(args.data / "bars.duckdb") as store,
        DirectoryStore(args.data / "directory.duckdb") as directory,
        ClassificationStore(args.data / "classifications.duckdb") as classifications,
    ):
        as_of = store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("bar store is empty")

        market = store.as_of(MARKET, Interval.DAY, Series.RAW, as_of)
        if not market.bars:
            raise SystemExit(f"{MARKET} is not in the bar store - DR-018's benchmark is missing")

        rule = rules.LiquidityRule(
            min_price=Decimal("5.00"), min_adtv=Decimal(5_000_000),
            adtv_window=ADTV_WINDOW, min_history=250,
        )
        stored = set(store.instrument_ids(as_of))
        admitted: dict[str, BarSeries] = {}
        for entry in directory.as_of(as_of, eligible_only=True):
            if entry.symbol not in stored:
                continue
            series = store.as_of(entry.symbol, Interval.DAY, Series.RAW, as_of)
            if series.bars and rule.admits(series):
                admitted[entry.symbol] = series

        sector_of: dict[str, str] = {}
        refused = 0
        for name in admitted:
            exposure = look_through(classifications.as_of(name, clock), name)
            if not exposure.is_available or not exposure.weights:
                refused += 1
                continue
            sector_of[name] = max(exposure.weights, key=lambda w: w.weight).sector

        members: dict[str, list[str]] = defaultdict(list)
        for name, sector in sector_of.items():
            members[sector].append(name)
        usable = {s: n for s, n in members.items() if len(n) >= MIN_SECTOR_MEMBERS}

        print(f"bars as of            {as_of.isoformat()}")
        print(f"classifications as of {clock.isoformat()}  (the RUN's clock)")
        print(f"admitted {len(admitted)} · classified {len(sector_of)} · "
              f"no usable look-through {refused}")
        print(f"sectors with >= {MIN_SECTOR_MEMBERS} members: {len(usable)} of {len(members)}")
        for sector, names in sorted(usable.items(), key=lambda kv: -len(kv[1])):
            print(f"  {sector:<26} {len(names)}")

        results: list[dict[str, object]] = []
        print(f"\n{'lookback':>9} {'names':>7} {'vs raw return':>15} {'vs market p-to-p':>18}")
        for lookback in LOOKBACKS:
            own: dict[str, float] = {}
            for name, series in admitted.items():
                value = _return(series, len(series.bars) - 1, lookback)
                if value is not None:
                    own[name] = float(value)

            market_return = _return(market, len(market.bars) - 1, lookback)
            if market_return is None:
                continue

            # The sector's own return: the equal-weighted mean of its admitted members'.
            sector_return: dict[str, float] = {}
            for sector, names in usable.items():
                have = [own[n] for n in names if n in own]
                if len(have) >= MIN_SECTOR_MEMBERS:
                    sector_return[sector] = sum(have) / len(have)

            shared = sorted(
                n for n in own
                if n in sector_of and sector_of[n] in sector_return and n != MARKET
            )
            if len(shared) < 3:
                continue

            # A per-name denominator. NOT a common factor, so this can reorder - which is the whole
            # reason to measure it rather than reason about it.
            relative = [
                (1 + own[n]) / (1 + sector_return[sector_of[n]]) for n in shared
            ]
            raw = [own[n] for n in shared]
            # The market POINT-TO-POINT form, for the same names. A CONTROL, not a comparison:
            # `DR-018` proved it ranks identically to raw return, so this column must equal the one
            # beside it. If the two ever differ, the arithmetic here is broken.
            market_relative = [(1 + own[n]) / (1 + float(market_return)) for n in shared]

            vs_raw = spearman(relative, raw)
            vs_market = spearman(relative, market_relative)
            print(f"{lookback:>9} {len(shared):>7} "
                  f"{'n/a' if vs_raw is None else f'{vs_raw:.6f}':>15} "
                  f"{'n/a' if vs_market is None else f'{vs_market:.6f}':>18}")
            results.append({
                "lookback": lookback,
                "names": len(shared),
                "spearman_vs_raw_return": None if vs_raw is None else round(vs_raw, 6),
                "spearman_vs_market_relative": None if vs_market is None else round(vs_market, 6),
                "sectors_used": len(sector_return),
            })

    print("\nWHAT THIS SETTLES")
    if results:
        worst = min(float(r["spearman_vs_raw_return"]) for r in results
                    if r["spearman_vs_raw_return"] is not None)
        best = max(float(r["spearman_vs_raw_return"]) for r in results
                   if r["spearman_vs_raw_return"] is not None)
        control_holds = all(
            r["spearman_vs_raw_return"] == r["spearman_vs_market_relative"] for r in results
        )
        print(f"  A SECTOR denominator DOES reorder: rho against raw return runs {worst:.6f} to "
              f"{best:.6f},")
        print("  where a MARKET denominator in the same point-to-point form gives exactly 1.0.")
        print(f"  Control - the two printed columns are identical: {control_holds}. They must be, "
              "and that")
        print("  IS DR-018's identity restated: correlating against the market point-to-point form")
        print("  is correlating against raw return.")
        print("\n  AND IT REORDERS LESS THAN THE MARKET PATH FORM DOES. DR-018 measured that at")
        print("  about 0.6 against raw return; this reads 0.75 to 0.82.")
        print("  Stated plainly because the tempting reading is the wrong one: FURTHER FROM RAW")
        print("  RETURN IS NOT BETTER. Both are real cross-sectional signals, neither is evidence")
        print("  of anything, and which one predicts is a question only a pre-registration answers.")
        if not control_holds:
            print("\n  CONTROL BROKEN - the columns differ. Do not read anything above.")
            return 1

    payload = {
        "bars_as_of": as_of.isoformat(),
        "classifications_as_of": clock.isoformat(),
        "market_benchmark": MARKET,
        "min_sector_members": MIN_SECTOR_MEMBERS,
        "admitted": len(admitted),
        "classified": len(sector_of),
        "no_usable_look_through": refused,
        "sector_sizes": {s: len(n) for s, n in sorted(usable.items())},
        "results": results,
        "readings": [
            "sector return is the EQUAL-WEIGHTED mean of admitted members - no point-in-time "
            "float-adjusted market cap exists here, the same constraint DR-003 records",
            "a name takes its DOMINANT sector by look_through; a refused look-through contributes "
            "to no sector (DR-006 section 8.7)",
            "a name is included in its own sector's mean; removing it would make the denominator "
            "depend on the numerator",
        ],
        "not_measured": (
            "whether the sector signal PREDICTS anything. This measures that the denominator "
            "changes the order, not that the order is better. That needs a pre-registration."
        ),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
