"""Fetch bars for eligible symbols, oldest-first, up to a budget.

**Why this is a separate pass rather than part of the daily run.** DR-003 admits roughly a third of
13,048 eligible US symbols - about 4,300 instruments. At Yahoo's throughput that is over an hour,
against the 45-minute daily budget in `NFR.md`. Fetching everything the rule admits, every day, does
not fit and never will on a free tier.

So the work is tiered, which is also the cadence the course itself uses - Appendix T's weekly pass
sets up the week and the pre-session pass runs it:

  * this tool, run periodically, widens coverage - the universe converges on the rule's answer
  * `swingdesk scan --universe`, run daily, reads what is already stored and never blocks on a fetch

The consequence is stated rather than hidden: **until coverage is complete the universe is a subset
of what the rule admits**, `UniverseSelection.is_partial` is True, and every report says so.

Oldest-first, because the alternative - refreshing whatever is most convenient - would quietly bias
the universe toward the symbols this tool happens to reach first.

**`--symbols-from` is a different mode, not a variant of the budget queue.** A study reproduction
(`PR-007`) needs the EXACT sample a prior study admitted - not the current eligibility rule's
answer, which has moved since. Re-filtering by today's eligibility would silently change the sample
being reproduced. So this mode resolves a fixed symbol list against the directory *by identity*,
reports what no longer resolves (a real finding - PR-007 section 0 anticipates this exact case), and
fetches only what remains. It never falls back to the budget queue.

Network tool. Never imported by anything in src/, never run in CI (CI_POLICY 4).

    python tools/refresh_universe.py --budget 500
    python tools/refresh_universe.py --symbols-from docs/prereg/results/PR-005.json --period 10y
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import Interval
from swingdesk.contracts.reference import Instrument
from swingdesk.market_data import BarStore, CloseRevision, VendorUnavailable, vendor_yahoo
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import universe
from swingdesk.reference_data.directory import DirectoryStore


def _fixed_queue(
    symbols_from: Path, directory: DirectoryStore, as_of: datetime
) -> list[Instrument]:
    """Resolve a study's fixed symbol list against the directory by identity.

    Reads any JSON document exposing an `instruments` list of bare symbols - the shape
    `docs/prereg/results/*.json` already uses. Unresolved symbols are reported and skipped rather
    than silently dropped: a delisted instrument missing from the reproduction is itself evidence
    (PR-007 section 0 names this case in advance).
    """
    wanted = json.loads(symbols_from.read_text(encoding="utf-8"))["instruments"]
    by_symbol = {e.symbol: e for e in directory.as_of(as_of)}

    resolved = [universe.to_instrument(by_symbol[s]) for s in wanted if s in by_symbol]
    missing = [s for s in wanted if s not in by_symbol]

    print(f"fixed sample: {len(wanted)} requested, {len(resolved)} resolved, "
          f"{len(missing)} missing from the current directory")
    if missing:
        print(f"  missing: {', '.join(missing)}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(prog="refresh_universe")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--budget", type=int, default=500,
                        help="how many symbols to fetch this pass (ignored with --symbols-from)")
    parser.add_argument("--period", default="2y",
                        help="fetch window; must exceed universe.min_bar_history (250 bars)")
    parser.add_argument("--pause", type=float, default=0.0,
                        help="seconds between fetches, if the vendor starts throttling")
    parser.add_argument("--symbols-from", type=Path, default=None,
                         help="JSON file with an 'instruments' list; fetch exactly these symbols "
                              "instead of budget-queuing eligible ones (PR-007 reproduction)")
    args = parser.parse_args()

    as_of = datetime.now(UTC)

    with (
        DirectoryStore(args.data / "directory.duckdb") as directory,
        BarStore(args.data / "bars.duckdb") as store,
    ):
        fixed_mode = args.symbols_from is not None
        if fixed_mode:
            queue = _fixed_queue(args.symbols_from, directory, as_of)
            if not queue:
                print("nothing resolved - directory is empty or none of the sample survives")
                return 1
        else:
            entries = directory.as_of(as_of, eligible_only=True)
            if not entries:
                print("directory is empty - run tools/fetch_directory.py first")
                return 1

            stored = set(store.instrument_ids(as_of))
            instruments = [universe.to_instrument(e) for e in entries]

            # Never-fetched first, then the stalest. A symbol with no bars can never enter the
            # universe, so widening coverage buys more than re-reading what is already there.
            last_seen = store.last_sessions(as_of)
            never = [i for i in instruments if i.id not in stored]
            known = [i for i in instruments if i.id in stored]
            known.sort(key=lambda i: last_seen.get(i.id, date(1970, 1, 1)))
            queue = (never + known)[: args.budget]

            print(f"eligible {len(entries)} · stored {len(stored)} · "
                  f"never fetched {len(never)} · this pass {len(queue)}")

        # `data.revision_epsilon`, scoped to `close` by the owner ruling of 2026-08-23 (DR-016
        # section 8.4). Unset means the store reports no faults rather than assuming a tolerance -
        # the same fail-closed shape the universe rule uses, applied to a check instead of a filter.
        try:
            epsilon, _ = ParameterRegistry.load().decimal_value("data.revision_epsilon")
        except ParameterUnset:
            epsilon = None
            print("data.revision_epsilon is unset - restated closes are stored but not checked")

        fetched = failed = 0
        faults: list[CloseRevision] = []
        for index, instrument in enumerate(queue, start=1):
            try:
                series = vendor_yahoo.fetch(instrument, Interval.DAY, as_of, period=args.period)
            except (VendorUnavailable, Exception) as error:  # noqa: BLE001 - a research tool
                failed += 1
                if failed <= 10:
                    print(f"  {instrument.id}: {type(error).__name__}")
            else:
                faults.extend(store.write(series.bars, as_of, epsilon).close_revisions)
                fetched += 1
            if args.pause:
                time.sleep(args.pause)
            if index % 100 == 0:
                print(f"  [{index}/{len(queue)}] fetched={fetched} failed={failed}")

        print(f"\nfetched {fetched}, failed {failed}")
        if faults:
            # Printed, not raised. This pass widens coverage; it makes no decision, so a restated
            # close here is evidence for the next run rather than a reason to stop this one.
            print(f"{len(faults)} close(s) restated past data.revision_epsilon:")
            for fault in faults[:20]:
                magnitude = "undefined - stored close was zero" if fault.relative is None \
                    else f"{fault.relative:.4%}"
                print(f"  {fault.instrument_id} {fault.session_date}: "
                      f"{fault.stored} -> {fault.restated} ({magnitude})")
            if len(faults) > 20:
                print(f"  ... and {len(faults) - 20} more")
        if fixed_mode:
            covered = len(set(store.instrument_ids(as_of)) & {i.id for i in queue})
            print(f"coverage of the resolved sample: {covered}/{len(queue)}")
        else:
            covered = len(set(store.instrument_ids(as_of)) & {i.id for i in instruments})
            print(f"coverage now {covered}/{len(entries)} eligible ({covered / len(entries):.1%})")
            if covered < len(entries):
                remaining = -(-(len(entries) - covered) // max(args.budget, 1))
                print(f"{remaining} more pass(es) at this budget to cover the directory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
