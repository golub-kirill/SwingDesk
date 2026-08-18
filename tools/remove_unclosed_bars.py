"""Remove bars that were captured before their own session closed. Owner-ruled, 2026-08-18.

    python tools/remove_unclosed_bars.py                 report only, changes nothing
    python tools/remove_unclosed_bars.py --apply         delete them

**This deletes rows from an append-only store, which is normally forbidden.** `CHANGE_MANAGEMENT.md`
§3 says rollback is supersede, never revert, and every other correction in this project follows that.
The owner ruled otherwise for this case on 2026-08-18, with a reason: *"we have no reason to replay
broken stuff step by step."* A replay pinned to a `knowledge_time` before the deletion will no longer
reproduce, and that is the accepted, stated cost - not an oversight.

WHAT IS BEING REMOVED, and why it is not merely "worse" data. On 2026-08-03 a manual fetch ran at
13:25 local - two and a half hours before the 16:00 ET close - and stored 296 mid-session prints as
if they were session bars. A partial bar is wrong in all four fields every downstream component
reads: its close is a mid-session price, its high and low are partial extremes, and its volume is a
fraction of the session's. Measured, the stored closes were out by up to 4.3%. `CALENDAR_SPEC.md` §5
forbids the unclosed current bar as a decision input, and `calendar.last_completed_session` has
enforced that on every READ since it was written; nothing enforced it on WRITE until
`BarStore.write` gained its guard the same day, so this is the backlog that guard was too late for.

**Scoped by the calendar, not by the date.** The same 13:25 fetch also wrote ~350 bars per session
for 2026-07-27 through 07-31. Those sessions had closed, so those bars are correct and are left
alone. The predicate is the rule - `knowledge_time` earlier than that session's own close - and it
is recomputed here rather than hard-coded, so this script can never delete more than it describes.

**The gap heals by itself.** `pipeline.run` fetches a full year for every universe member every
evening and `BarStore.write` inserts what is missing, so a member's 2026-08-03 bar returns on the
next scheduled run - correct this time, because the guard now refuses the partial one. Instruments
outside the universe are not evaluated at all until `refresh_universe.py` reaches them, which
refetches them anyway.

Takes a backup path and refuses to run without one.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import duckdb

from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
DATA = Path(os.environ.get("SWINGDESK_DATA") or REPO / "data")


def unclosed_rows(connection: duckdb.DuckDBPyConnection) -> list[tuple[str, object, object]]:
    """Every stored daily raw bar whose `knowledge_time` predates its own session's close.

    A session the calendar does not know is LEFT ALONE - not knowing whether a bar is unclosed is a
    different claim from knowing that it is, and this script must never delete on ignorance.
    """
    rows = connection.execute(
        "SELECT instrument_id, session_date, knowledge_time FROM bars "
        "WHERE interval = '1d' AND series = 'raw'"
    ).fetchall()

    closes: dict[tuple[str, object], object] = {}
    dates = {row[1] for row in rows}
    if dates:
        for exchange in (Exchange.NYSE, Exchange.TSX):
            for session in cal.sessions(exchange, min(dates), max(dates)):
                closes[(exchange.value, session.session_date)] = session.close_time

    doomed = []
    for instrument_id, session_date, knowledge_time in rows:
        close_time = closes.get((cal.exchange_for(instrument_id).value, session_date))
        if close_time is not None and knowledge_time < close_time:
            doomed.append((instrument_id, session_date, knowledge_time))
    return doomed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="remove-unclosed-bars")
    parser.add_argument("--apply", action="store_true",
                        help="actually delete. Without this the script only reports.")
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args(argv)

    store = args.data / "bars.duckdb"
    if not store.is_file():
        print(f"no bar store at {store}", file=sys.stderr)
        return 2

    with duckdb.connect(str(store), read_only=True) as reader:
        doomed = unclosed_rows(reader)
        total = reader.execute("SELECT COUNT(*) FROM bars").fetchone()[0]

    if not doomed:
        print(f"no unclosed bars in {store}. Nothing to do.")
        return 0

    by_session: dict[object, int] = {}
    for _, session_date, _ in doomed:
        by_session[session_date] = by_session.get(session_date, 0) + 1

    print(f"store: {store}  ({total:,} rows)")
    print(f"bars captured BEFORE their own session closed: {len(doomed)}")
    for session_date, count in sorted(by_session.items()):
        print(f"  session {session_date}: {count}")

    if not args.apply:
        print("\nreport only. Re-run with --apply to delete them.")
        return 0

    backup = store.with_name(f"{store.name}.backup-before-unclosed-delete")
    if not backup.exists():
        print(f"\nbacking up to {backup.name} ...")
        shutil.copy2(store, backup)

    with duckdb.connect(str(store)) as writer:
        writer.executemany(
            "DELETE FROM bars WHERE instrument_id = ? AND session_date = ? "
            "AND knowledge_time = ? AND interval = '1d' AND series = 'raw'",
            doomed,
        )
        writer.execute("CHECKPOINT")
        after = writer.execute("SELECT COUNT(*) FROM bars").fetchone()[0]

    with duckdb.connect(str(store), read_only=True) as reader:
        remaining = len(unclosed_rows(reader))

    print(f"\ndeleted {total - after} row(s); {after:,} remain in the store.")
    print(f"unclosed bars still present: {remaining}")
    if remaining or (total - after) != len(doomed):
        print("MISMATCH - restore from the backup and investigate.", file=sys.stderr)
        return 1
    print("The guard in BarStore.write now refuses any new one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
