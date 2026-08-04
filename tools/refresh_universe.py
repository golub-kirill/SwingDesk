"""Fetch bars for eligible symbols, oldest-first, up to a budget.

**Why this is a separate pass rather than part of the daily run.** DR-003 admits roughly a third of
13,048 eligible US symbols - about 4,300 instruments. At Yahoo's throughput that is over an hour,
against the 45-minute daily budget in `NFR.md`. Fetching everything the rule admits, every day, does
not fit and never will on a free tier.

So the work is tiered, which is also the cadence the course itself uses (Appendix T: `До недели`
sets up the week, `До сессии` runs it):

  * this tool, run periodically, widens coverage - the universe converges on the rule's answer
  * `swingdesk scan --universe`, run daily, reads what is already stored and never blocks on a fetch

The consequence is stated rather than hidden: **until coverage is complete the universe is a subset
of what the rule admits**, `UniverseSelection.is_partial` is True, and every report says so.

Oldest-first, because the alternative - refreshing whatever is most convenient - would quietly bias
the universe toward the symbols this tool happens to reach first.

Network tool. Never imported by anything in src/, never run in CI (CI_POLICY 4).

    python tools/refresh_universe.py --budget 500
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import Interval
from swingdesk.market_data import BarStore, VendorUnavailable, vendor_yahoo
from swingdesk.reference_data import universe
from swingdesk.reference_data.directory import DirectoryStore


def main() -> int:
    parser = argparse.ArgumentParser(prog="refresh_universe")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--budget", type=int, default=500,
                        help="how many symbols to fetch this pass")
    parser.add_argument("--period", default="2y",
                        help="fetch window; must exceed universe.min_bar_history (250 bars)")
    parser.add_argument("--pause", type=float, default=0.0,
                        help="seconds between fetches, if the vendor starts throttling")
    args = parser.parse_args()

    as_of = datetime.now(UTC)

    with (
        DirectoryStore(args.data / "directory.duckdb") as directory,
        BarStore(args.data / "bars.duckdb") as store,
    ):
        entries = directory.as_of(as_of, eligible_only=True)
        if not entries:
            print("directory is empty - run tools/fetch_directory.py first")
            return 1

        stored = set(store.instrument_ids(as_of))
        instruments = [universe.to_instrument(e) for e in entries]

        # Never-fetched first, then the stalest. A symbol with no bars can never enter the universe,
        # so widening coverage buys more than re-reading what is already there.
        last_seen = store.last_sessions(as_of)
        never = [i for i in instruments if i.id not in stored]
        known = [i for i in instruments if i.id in stored]
        known.sort(key=lambda i: last_seen.get(i.id, date(1970, 1, 1)))
        queue = (never + known)[: args.budget]

        print(f"eligible {len(entries)} · stored {len(stored)} · "
              f"never fetched {len(never)} · this pass {len(queue)}")

        fetched = failed = 0
        for index, instrument in enumerate(queue, start=1):
            try:
                series = vendor_yahoo.fetch(instrument, Interval.DAY, as_of, period=args.period)
            except (VendorUnavailable, Exception) as error:  # noqa: BLE001 - a research tool
                failed += 1
                if failed <= 10:
                    print(f"  {instrument.id}: {type(error).__name__}")
            else:
                store.write(series.bars, as_of)
                fetched += 1
            if args.pause:
                time.sleep(args.pause)
            if index % 100 == 0:
                print(f"  [{index}/{len(queue)}] fetched={fetched} failed={failed}")

        covered = len(set(store.instrument_ids(as_of)) & {i.id for i in instruments})
        print(f"\nfetched {fetched}, failed {failed}")
        print(f"coverage now {covered}/{len(entries)} eligible ({covered / len(entries):.1%})")
        if covered < len(entries):
            remaining = -(-(len(entries) - covered) // max(args.budget, 1))
            print(f"{remaining} more pass(es) at this budget to cover the directory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
