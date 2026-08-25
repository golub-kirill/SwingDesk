"""`NFR.md` §3's latency budgets, measured — because until 2026-08-24 nothing measured any of them.

That table has budgeted the **decision path at ≤ 5 minutes** since it was written. Measured that
morning over the 1,141-member universe it was **20.2 minutes** — 19.0 of pipeline compute plus
71.9 s of universe selection, four times the budget. Nobody saw it, and the reason is instructive:
the same table budgets the END-TO-END run at ≤ 45 min, end-to-end was ~24 min, and end-to-end is
the only number `data/daily_run.log` records. **The requirement lives in the split and the log has
no split.**

**What this measures, and what it deliberately does not.**

The decision path is the single-threaded deterministic work `ARCHITECTURE.md` §3 describes — the
part the NFR says is "not a place to optimise with concurrency". So the vendor is taken OUT: the
fetcher replays what the store already holds, which is also what makes two runs comparable. The
incremental refresh has its own budget (≤ 20 min, I/O-bound, explicitly a place concurrency
applies) and is a different measurement; this tool does not make it and does not report on it.

**The budget is read from `NFR.md`, never restated here.** A second copy of a ratified number is
the drift `AGENTS.md` §10.5 exists to stop, and a tool asserting its own threshold would be exactly
that. If the row cannot be parsed the tool refuses rather than assuming five minutes.

**It writes nothing.** The journal is a throwaway, for the same reason `verify_reproducible.py`
uses one: a latency measurement that added a run to the evidence record every time anyone asked
would make `a.run_completes` a function of curiosity.

    python tools/measure_latency.py --data C:/PycharmProjects/SwingDesk/data
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import time
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.application import universe as universe_builder
from swingdesk.application.pipeline import run
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import BarStore, VendorUnavailable
from swingdesk.platform.clock import FixedClock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data.classification import ClassificationStore
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.trade_management.sizing import Refusal

#: The same contract gates 23, 24 and 26 use: a check that cannot measure says so.
UNAVAILABLE = 4

#: What `period="1y"` returns, and therefore what the daily run hands the write path.
BARS_PER_FETCH = 251

NFR = REPO / "docs" / "01-requirements" / "NFR.md"

#: `| Decision path | **≤ 5 min** | ... |` - the row, not the number. The number is NFR.md's.
BUDGET_ROW = re.compile(
    r"^\|\s*\*{0,2}Decision path\*{0,2}\s*\|\s*\*{0,2}[≤<=]+\s*(?P<minutes>\d+)\s*min",
    re.MULTILINE,
)


def _budget_minutes() -> int | None:
    """`NFR.md` §3's decision-path budget in minutes, or None when the row cannot be read."""
    if not NFR.is_file():
        return None
    found = BUDGET_ROW.search(NFR.read_text(encoding="utf-8"))
    return int(found.group("minutes")) if found else None


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_latency")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--limit", type=int, default=None,
                        help="cap the universe. A capped measurement is not the budget's subject "
                             "and the output says so")
    args = parser.parse_args()

    budget = _budget_minutes()
    if budget is None:
        print("latency: REFUSING - could not read the decision-path budget from NFR.md section 3. "
              "The threshold is that document's and this tool does not carry a copy.")
        return 1

    bars_path = args.data / "bars.duckdb"
    if not bars_path.is_file():
        print(f"latency: UNAVAILABLE - no bar store at {bars_path}. `data/` is gitignored "
              f"operational state and lives only in the main checkout.")
        return UNAVAILABLE

    registry = ParameterRegistry.load()
    try:
        store = BarStore(bars_path)
        directory = DirectoryStore(args.data / "directory.duckdb")
        classifications = ClassificationStore(args.data / "classifications.duckdb")
    except duckdb.IOException as error:
        # ADR-0004 makes the stores single-writer, so a refresh pass holding one is the design
        # working rather than a fault.
        print(f"latency: UNAVAILABLE - a store is open in another process. {error}")
        return UNAVAILABLE

    with store, directory, classifications:
        snapshot = store.latest_knowledge_time()
        if snapshot is None:
            print("latency: UNAVAILABLE - the bar store holds nothing")
            return UNAVAILABLE
        built = universe_builder.rule_from_registry(registry)
        if isinstance(built, Refusal):
            print(f"latency: UNAVAILABLE - the universe rule refuses: {built.reason} "
                  f"({built.parameter_id})")
            return UNAVAILABLE
        rule, parameters = built

        started_select = time.perf_counter()
        selection = universe_builder.select(
            directory, store, rule, snapshot, parameters=parameters, limit=args.limit
        )
        select_seconds = time.perf_counter() - started_select

        clock = FixedClock(snapshot)
        started = clock.now()

        # The vendor, replayed from the store. Outside the timed section on purpose: the refresh
        # has its own NFR budget and is explicitly a place concurrency applies, which the decision
        # path is not.
        payload: dict[str, BarSeries] = {}
        for instrument in selection.instruments:
            held = store.as_of(instrument.id, Interval.DAY, Series.RAW, snapshot)
            payload[instrument.id] = BarSeries(
                instrument_id=instrument.id, interval=Interval.DAY, series=Series.RAW,
                knowledge_time=started, bars=held.bars[-BARS_PER_FETCH:],
            )

        def replay(instrument, _interval, _knowledge_time, period=None):  # type: ignore[no-untyped-def]  # noqa: ARG001
            """The `Fetcher` protocol's shape; only the instrument is read off it here."""
            series = payload.get(instrument.id)
            if series is None:
                raise VendorUnavailable(f"{instrument.vendor_symbol}: not in the store")
            return series

        with tempfile.TemporaryDirectory() as scratch:
            journal = Journal(Path(scratch) / "journal.duckdb")
            started_run = time.perf_counter()
            try:
                run([], clock, registry, store, journal, mode=RunMode.LIVE,
                    universe=selection, classifications=classifications, fetcher=replay)
            finally:
                journal.close()
            run_seconds = time.perf_counter() - started_run

    total = select_seconds + run_seconds
    members = len(selection.members)
    print(f"snapshot {snapshot.isoformat()}  ·  {members} instrument(s)"
          + (f", capped from {selection.capped_from}" if selection.capped_from else ""))
    print(f"  universe selection  {select_seconds:8.1f} s")
    each = run_seconds / max(members, 1) * 1000
    print(f"  pipeline            {run_seconds:8.1f} s   ({each:.0f} ms each)")
    print(f"  decision path       {total:8.1f} s   = {total / 60:.1f} min")
    print(f"  NFR section 3 budget{budget * 60:8d} s   = {budget} min")

    if args.limit:
        print("\n  NOTE: a capped universe is NOT the budget's subject. The requirement is about "
              "the run the owner gets, and that run evaluates every admitted member.")

    print("\n  NOT measured here: the incremental vendor refresh (its own budget, I/O-bound and "
          "\n  explicitly a place concurrency applies), report generation, and end-to-end.")

    if total > budget * 60:
        print(f"\n--- latency: OVER BUDGET by {total - budget * 60:.0f} s")
        return 1
    print(f"\n--- latency: within budget, {budget * 60 - total:.0f} s to spare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
