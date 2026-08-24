"""`a.reproducible`, measured against the real universe instead of three synthetic instruments.

`criteria.yml` ratifies **a.reproducible - "A re-run from a stored manifest reproduces the control
run byte-identically"** - and gate 9 checks it on `golden/replay/daily-three-instruments`. That case
is real and it is three instruments. **Determinism defects live where iteration order, set
membership and dictionary insertion have room to differ**, and three names give them almost none.

**And no journalled production run has ever been replayed.** Measured 2026-08-24 against
`journal.duckdb`: of 22 runs, 12 carry `code_dirty` and are not replayable from their SHA at all,
and **not one of the clean ones was recorded at the code this repository now runs**. So a replay of
any stored manifest today would mismatch on `code_hash` - correctly, and uninformatively.
`HANDOFF.md` framed the dirty runs as what holds this criterion short; the sharper statement is that
even a clean one could not demonstrate it, because the criterion is about a re-run at the SAME code.

**So this runs the pipeline twice, now, at one pinned clock over the stored universe, and compares
the two output hashes.** Same code, same snapshot, same parameters - the only thing that can differ
is the thing the criterion is about.

**Both runs journal into a THROWAWAY database.** A determinism check that wrote to
`data/journal.duckdb` would add two runs to the evidence record for every time anyone asked the
question, and `a.run_completes` counts journalled runs.

**A mismatch is not automatically a defect, and the manifest says which it is** (`DETERMINISM_SPEC`
§5): a pinned input that changed is expected and explainable, and only an unexplained difference is
non-determinism. Since both runs happen within seconds at one snapshot, nothing pinned CAN change
here - which is what makes a mismatch here a stronger signal than one in gate 9.

    python tools/verify_reproducible.py --data C:/PycharmProjects/SwingDesk/data
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.application import universe as universe_builder
from swingdesk.application.pipeline import run
from swingdesk.contracts.run import RunManifest, RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data.classification import ClassificationStore
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.trade_management.sizing import Refusal

#: Exit code for "this checkout cannot see the stores". The same contract gates 23, 24 and 26 use:
#: a gate that cannot measure says so rather than exiting 0 as though it had (`AGENTS.md` §10.6).
UNAVAILABLE = 4


def _differences(first: RunManifest, second: RunManifest) -> list[str]:
    """Every pinned field the two manifests disagree on. Empty means only the output differed."""
    fields = (
        "code_hash", "code_dirty", "config_hash", "calendar_version",
        "seed", "platform", "universe_hash",
    )
    notes: list[str] = []
    for field in fields:
        left, right = getattr(first, field, None), getattr(second, field, None)
        if left != right:
            notes.append(f"{field}: {left!r} -> {right!r}")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(prog="verify_reproducible")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--limit", type=int, default=None,
                        help="cap the universe. Useful for a fast check; a PASS on a capped "
                             "universe is a weaker claim and the output says so")
    args = parser.parse_args()

    bars_path = args.data / "bars.duckdb"
    if not bars_path.is_file():
        print(f"reproducible: UNAVAILABLE - no bar store at {bars_path}. `data/` is gitignored "
              f"operational state and lives only in the main checkout.")
        return UNAVAILABLE

    registry = ParameterRegistry.load()
    try:
        stores = (
            BarStore(bars_path),
            DirectoryStore(args.data / "directory.duckdb"),
            ClassificationStore(args.data / "classifications.duckdb"),
        )
    except duckdb.IOException as error:
        # ADR-0004 makes the stores single-writer, so a refresh pass holding one is the design
        # working rather than a fault. UNAVAILABLE, never a traceback and never a silent 0.
        print(f"reproducible: UNAVAILABLE - a store is open in another process. {error}")
        return UNAVAILABLE

    store, directory, classifications = stores
    with store, directory, classifications:
        snapshot = store.latest_knowledge_time()
        if snapshot is None:
            print("reproducible: UNAVAILABLE - the bar store holds nothing")
            return UNAVAILABLE

        built = universe_builder.rule_from_registry(registry)
        if isinstance(built, Refusal):
            print(f"reproducible: UNAVAILABLE - the universe rule refuses: {built.reason} "
                  f"({built.parameter_id})")
            return UNAVAILABLE
        rule, parameters = built
        selection = universe_builder.select(
            directory, store, rule, snapshot, parameters=parameters, limit=args.limit
        )
        print(f"snapshot {snapshot.isoformat()}")
        print(f"universe {len(selection.members)} member(s)"
              + (f", capped from {selection.capped_from}" if selection.capped_from else ""))
        if args.limit:
            print("  NOTE: a capped universe is a WEAKER claim - the defect this looks for lives "
                  "in iteration order, which a cap changes")

        # One clock for both runs. A wall-clock read between them would make the two runs answer
        # different questions and the difference would look like non-determinism.
        clock = FixedClock(snapshot)

        hashes: list[str] = []
        manifests: list[RunManifest] = []
        for pass_number in (1, 2):
            with tempfile.TemporaryDirectory() as scratch:
                journal = Journal(Path(scratch) / "journal.duckdb")
                try:
                    result = run(
                        [], clock, registry, store, journal,
                        mode=RunMode.LIVE, universe=selection,
                        classifications=classifications,
                    )
                finally:
                    journal.close()
            manifests.append(result.manifest)
            hashes.append(result.manifest.output_hash)
            print(f"  pass {pass_number}: output_hash {result.manifest.output_hash}")

    if hashes[0] == hashes[1]:
        scope = "capped" if args.limit else "full"
        print(f"\n--- reproducible: PASS ({scope} universe, {len(selection.members)} instruments)")
        print("    Two passes at one snapshot produced byte-identical output. That is what")
        print("    a.reproducible asserts, measured here on the real universe rather than on")
        print("    gate 9's three-instrument case.")
        return 0

    print("\n--- reproducible: FAIL")
    print(f"    pass 1 {hashes[0]}")
    print(f"    pass 2 {hashes[1]}")
    notes = _differences(manifests[0], manifests[1])
    if notes:
        print("    A PINNED input differs between the two passes, which should be impossible at one")
        print("    snapshot. Read this as a defect in the harness before reading it as one in the")
        print("    decision path:")
        for note in notes:
            print(f"      {note}")
    else:
        print("    NOTHING PINNED DIFFERS. Same code, same config, same calendar, same universe,")
        print("    same snapshot - and a different answer. That is non-determinism in the decision")
        print("    path, and it is the case this check exists to catch (DETERMINISM_SPEC section 5).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
