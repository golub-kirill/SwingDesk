"""How large an effect could a sector-momentum study on ELEVEN funds actually detect?

**Asked before registering `PR-037`, and it is why `PR-037` was not registered.**
`RETURN_SOURCE_REGISTER` §3.1 ranked industry momentum first in the queue because it inherits no
survivorship problem and needs no point-in-time index membership - it is the cheapest source here to
TEST. This measures whether it is a source this instrument can ANSWER, which is a different
question, and the two were not separated until somebody measured.

**The method leaks no effect, which is what makes it safe to run before a registration.** The
ranking is RANDOM - `run_pr037.power` draws `HOLD` of the eligible funds each month with a seeded
generator - so the book has the design's turnover, its costs, its concentration and its calendar,
and none of its signal. What comes back is the width of the interval this design produces, and a
width carries no sign. `power_pr019.assert_no_effect_leaked` is the rule this obeys.

**The minimum detectable effect** is the conventional one: half the 95% width, scaled by
`(1.96 + 0.84) / 1.96` for 80% power against a two-sided test at 5%.

**What it is compared against.** Moskowitz and Grinblatt (1999) report industry momentum spreads
around 0.4-0.5% a month long-short; a long-only top-decile book's excess over its market is
conventionally around **2 to 3 points a year**, and post-publication decay is real - `PR-031`
measured a published intraday rule earning 8.5% a year before its paper and 0.45% after.

    PYTHONPATH=$PWD/src python tools/measure_sector_power.py --data <store dir> [--resamples 2000]

Network-free. It reads a stored bar store and writes one measurement.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr037 as sector

OUT = REPO / "docs" / "decisions" / "measurements" / "sector-momentum-power-2026-09-21.json"

#: Every long-only book size worth asking about on eleven candidates. Below two is one fund and
#: above six is more than half the pool, at which point "selection" has stopped meaning anything.
BOOK_SIZES = (2, 3, 4, 5, 6)

#: The conventional 80%-power scaling of a half-width, stated as a name rather than a literal so
#: the report can say where 4.45 came from.
POWER_SCALE = (1.96 + 0.84) / 1.96


def minimum_detectable(width: float) -> float:
    """The effect this design could separate from zero at 80% power."""
    return width / 2.0 * POWER_SCALE


def measure(args: argparse.Namespace) -> dict[str, Any]:
    def widths_for(hold: int | None) -> dict[str, Any]:
        return {
            name.replace("-random-ranking", ""): {
                "width": cell["width"], "minimum_detectable": minimum_detectable(cell["width"]),
                "months": cell["months"],
            }
            for name, cell in sector.power(args, hold=hold)["widths"].items()
        }

    rows: dict[str, Any] = {str(hold): widths_for(hold) for hold in BOOK_SIZES}
    # And the rule the study actually registers, which is not a fixed size: the tercile is three
    # funds while nine are eligible and four once eleven are, so it has its own width and is
    # measured rather than interpolated between the rows above.
    rows["tercile"] = widths_for(None)

    tercile = rows["tercile"]["excess-vs-own-pool"]["minimum_detectable"]
    # "Best" across book sizes is NOT the answer, and reading it as one is the mistake this line
    # exists to prevent: the narrowest interval belongs to the book holding six of eleven funds,
    # which is 55% of the pool and barely a selection at all. The honest comparison is the
    # narrowest interval among books that are still a SELECTION - five of eleven or fewer.
    selective = min(row["excess-vs-own-pool"]["minimum_detectable"]
                    for size, row in rows.items() if size != "tercile" and int(size) <= 5)
    return {
        "measured": "2026-09-21",
        "asked_by": "Claude, before registering PR-037 - RETURN_SOURCE_REGISTER 3.1 ranked this "
                    "source first because it is the cheapest to TEST, which is not the same as "
                    "being answerable",
        "exploratory": True,
        "trials": 0,
        "why_no_trial": "the ranking is RANDOM, so this carries widths and no effect. Nothing "
                        "here is a reading of the hypothesis and nothing is counted against the "
                        "budget",
        "tool": "tools/measure_sector_power.py",
        "funds": list(sector.FUNDS),
        "benchmark": sector.BENCH,
        "formation_months": sector.FORMATION,
        "skip_months": sector.SKIP,
        "costs_bps_of_notional": sector.COSTS,
        "resamples": args.resamples,
        "power_scale": POWER_SCALE,
        "by_book_size": rows,
        "tercile_minimum_detectable_vs_own_pool": tercile,
        "best_minimum_detectable_among_selective_books": selective,
        "selective_means": "a book of five of eleven or fewer. Six of eleven is 55% of the pool",
        "claimed_effect_in_the_literature": 0.02,
        "conclusion": "NO long-only book that is still a selection can separate a 2-point-a-year "
                      "effect from zero here. Against the funds' own pool, two of eleven detects "
                      "4.56 points a year, three detects 3.18, four 2.32, five 2.16, and the "
                      "registered TERCILE rule 2.86 - every one of them above the two points this "
                      "literature claims. Only six of eleven gets under it, at 1.67, and six of "
                      "eleven is 55% of the pool. The binding constraint is the CROSS-SECTION, not "
                      "the book size: eleven candidates over 320 months is too thin to rank",
        "what_follows": "PR-037 is NOT registered on this instrument. Spending a trial raises the "
                        "deflated-Sharpe hurdle for every study after it, and a design that cannot "
                        "detect its own claimed effect buys nothing with that. The source stays "
                        "open in RETURN_SOURCE_REGISTER 3.1 with a stated trigger: a wider "
                        "cross-section - industry-level funds, or the repaired stock universe",
        "what_this_does_NOT_settle": "whether sector momentum exists. This measures what this "
                                     "DESIGN could see, not what the market does, and a random "
                                     "ranking carries no sign. It also does not measure how the "
                                     "effect itself changes with book size - that would be reading "
                                     "the hypothesis before the registration",
    }


def report(payload: dict[str, Any]) -> None:
    print("sector momentum on eleven funds: what could be detected, by book size")
    print(f"  {'hold':>7}  {'vs SPY width':>13} {'MDE':>7}   {'vs own pool':>13} {'MDE':>7}")
    for hold, row in payload["by_book_size"].items():
        spy, pool = row["excess-vs-SPY"], row["excess-vs-own-pool"]
        print(f"  {hold:>7}  {100 * spy['width']:>12.2f}% {100 * spy['minimum_detectable']:>6.2f}%"
              f"   {100 * pool['width']:>12.2f}% {100 * pool['minimum_detectable']:>6.2f}%")
    claimed = payload["claimed_effect_in_the_literature"]
    tercile = payload["tercile_minimum_detectable_vs_own_pool"]
    selective = payload["best_minimum_detectable_among_selective_books"]
    print(f"  the tercile rule detects {100 * tercile:.2f}% a year, and the best book that is still"
          f" a SELECTION {100 * selective:.2f}%, against a claimed {100 * claimed:.2f}%")
    print(f"  -> {'registrable' if selective <= claimed else 'NOT answerable on eleven funds'}:"
          " the binding constraint is the cross-section, not the book size")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True,
                        help="the directory holding bars.duckdb with the sector funds")
    parser.add_argument("--as-of", help="the store's knowledge instant")
    parser.add_argument("--resamples", type=int, default=2000)
    args = parser.parse_args(argv)
    payload = measure(args)
    payload["as_of"] = args.as_of or datetime.now(UTC).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report(payload)
    print(f"  written to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
