"""Fetch sector classifications for instruments the store already holds bars for.

The pass that makes `risk.max_sector_risk` measurable. `DR-006` §2 requires an ETF to consume its
constituents' sector budget rather than sitting outside it, §3 recorded the whole constraint as
unevaluable for want of a source, and §8.4 found the source was there all along - the bar vendor
serves sector and industry directly and serves a fund's composition through `funds_data`.

**Why this is a separate pass rather than part of the daily run**, for exactly the reason
`refresh_universe.py` gives: one classification is one more vendor round trip per instrument, and
the universe was 1152 members on 2026-08-17. Doing it inside the evening run would double its
vendor traffic against a 45-minute budget (`NFR.md`) on a rate-limited free tier, to refresh a fact
that changes a few times a year.

So the cadence is tiered the same way:

  * this tool, run occasionally, widens sector coverage
  * `swingdesk scan`, run daily, reads what is already stored and never blocks on a fetch

**Until it has run, every candidate is admitted UNCHECKED and the report says so.** That is
`DR-006` §3 being obeyed rather than a gap: a sector cap that refused every unclassified name would
refuse the whole universe on the day the store was created, which stops the system while looking
like risk discipline.

**What this cannot fix: the classification is TODAY's, not the one in force on an older date.**
The store is bitemporal and read as-of, so a replay before the first pull correctly finds nothing.
It does not, and must not, answer a 2016 question with a 2026 answer. That restricts a backtest and
not live admission (`DR-006` §8.4 d).

Network tool. Never imported by anything in src/, never run in CI (CI_POLICY 4).

    python tools/refresh_classifications.py --universe --budget 1200
    python tools/refresh_classifications.py --budget 200
    python tools/refresh_classifications.py --symbols AAPL SPY --data data
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.application import universe as universe_builder
from swingdesk.contracts.reference import Instrument
from swingdesk.market_data import BarStore, VendorUnavailable, vendor_yahoo
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import universe
from swingdesk.reference_data.classification import ClassificationStore, look_through
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.trade_management.sizing import Refusal

#: Seconds between vendor calls. The same courtesy `refresh_universe.py` extends to a free tier
#: this project has no contract with, and the reason a budget exists at all.
PAUSE = 0.5


def _queue(
    bars: BarStore,
    classifications: ClassificationStore,
    directory: DirectoryStore,
    as_of: datetime,
    budget: int,
    admitted: set[str] | None = None,
) -> list[Instrument]:
    """Instruments with bars but no classification, oldest gap first, up to `budget`.

    **Only names the store already holds bars for.** A classification for an instrument that has no
    price history buys nothing: it can never be sized, so it can never reach the sector check. The
    universe converges on the rule's answer through `refresh_universe.py`, and this follows it.

    `admitted` narrows it further to the names the liquidity rule actually admits - the ones a run
    can nominate today. Without it the queue is every symbol with bars in symbol order, which
    classifies thousands of names no candidate path will ever reach before it finishes the ones it
    will. Roughly a third of what has bars is admitted, so the difference is most of the work.

    Unclassified first, then everything else in symbol order so a re-run is deterministic and the
    coverage gap closes rather than being resampled.
    """
    by_symbol = {entry.symbol: entry for entry in directory.as_of(as_of)}
    have_bars = [
        s
        for s in bars.instrument_ids(as_of)
        if s in by_symbol and (admitted is None or s in admitted)
    ]
    classified = set(classifications.instrument_ids(as_of))

    missing = sorted(s for s in have_bars if s not in classified)
    known = sorted(s for s in have_bars if s in classified)
    return [universe.to_instrument(by_symbol[s]) for s in (missing + known)[:budget]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="refresh_classifications")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--budget", type=int, default=100,
                        help="how many instruments to classify this pass")
    parser.add_argument("--symbols", nargs="*", default=None,
                        help="classify exactly these symbols, ignoring the queue")
    parser.add_argument("--universe", action="store_true",
                        help="queue only the names the liquidity rule admits, not every symbol "
                             "with bars - the ones a run can actually nominate")
    args = parser.parse_args(argv)

    as_of = datetime.now(UTC)
    with (
        BarStore(args.data / "bars.duckdb") as bars,
        ClassificationStore(args.data / "classifications.duckdb") as classifications,
        DirectoryStore(args.data / "directory.duckdb") as directory,
    ):
        admitted: set[str] | None = None
        if args.universe:
            built = universe_builder.rule_from_registry(ParameterRegistry.load())
            if isinstance(built, Refusal):
                # Fail closed and name the parameter, exactly as `scan --universe` does. A pass
                # that silently classified everything because the rule had no value would be
                # doing different work under the same flag.
                print(f"universe REFUSED  {built}")
                return 2
            rule, parameters = built
            selection = universe_builder.select(directory, bars, rule, as_of,
                                                parameters=parameters)
            # `.instrument.id`, not the Membership itself. A set of dataclasses tests nothing
            # against a string id, so the first run of this flag queued NOTHING and reported
            # "every instrument already has a classification" - a false clean bill of health,
            # and exactly the shape of silence AGENTS.md 1 says to check rather than trust.
            admitted = {member.instrument.id for member in selection.members}
            print(f"universe: {len(admitted)} admitted of {selection.measured} measured "
                  f"({selection.coverage:.1%} of {selection.eligible} eligible)")

        if args.symbols:
            by_symbol = {entry.symbol: entry for entry in directory.as_of(as_of)}
            queue = [
                universe.to_instrument(by_symbol[s]) for s in args.symbols if s in by_symbol
            ]
            unresolved = [s for s in args.symbols if s not in by_symbol]
            if unresolved:
                print(f"  not in the directory, skipped: {', '.join(unresolved)}")
        else:
            queue = _queue(bars, classifications, directory, as_of, args.budget, admitted)

        if not queue:
            # Says what it MEASURED, not what it assumes the reason was. This line read "every
            # instrument with bars already has a classification" and printed exactly that over an
            # empty store, because a bug upstream had emptied the queue - a false clean bill of
            # health, from a message asserting a cause it had never checked.
            print(
                f"queue is empty: {len(classifications.instrument_ids(as_of))} instrument(s) "
                f"already classified, {len(bars.instrument_ids(as_of))} have bars"
                + (f", {len(admitted)} admitted by the rule" if admitted is not None else "")
            )
            return 0

        stored = failed = degenerate = 0
        for index, instrument in enumerate(queue):
            if index:
                time.sleep(PAUSE)
            try:
                classification = vendor_yahoo.fetch_classification(instrument, as_of)
            except VendorUnavailable as unavailable:
                # Fail-open at this layer, exactly as the bar path is: a vendor failure leaves the
                # previous classification standing and the next pass tries again. What must never
                # happen is a fabricated sector written to close a gap.
                print(f"  {instrument.id}: {unavailable}")
                failed += 1
                continue
            classifications.record([classification])
            stored += 1
            # Reported at write time, because a look-through this project refuses is the one
            # outcome an operator would otherwise never see - it is stored, then declined on the
            # way out, and the daily report only counts it (`DR-006` §8.7).
            if not look_through(classification, instrument.id).is_available:
                degenerate += 1

        covered = len(classifications.instrument_ids(as_of))
        measured = len(bars.instrument_ids(as_of))
        print(
            f"classified {stored} of {len(queue)} attempted · {failed} vendor failure(s) · "
            f"{degenerate} unusable (no sector, or a degenerate look-through)"
        )
        print(f"coverage: {covered} of {measured} instruments with bars now carry a sector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
