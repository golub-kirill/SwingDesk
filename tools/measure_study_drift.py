"""How far has the store moved under each REPORTED study since it ran?

A study's verdict is only as reproducible as the sample under it. The store is bitemporal and
append-only, so nothing is ever lost - but a REPLAY that reads the store's LATEST `knowledge_time`
reads a different sample from the one the study read, and says nothing about it. This measures the
difference, per study, and separates the two populations that turned out to behave differently:

  * REVISIONS - a session the study already had, rewritten. `data.revision_epsilon` watches the
    close alone (`DR-016` section 8.4, owner ruling, measured), so a revision that moves only
    `high`, `low` or `volume` is invisible by design and still moves an ATR-denominated result.
  * NEW SESSIONS - a session the study never had. Inside a closed study window that is a backfill.

**Why this exists, measured 2026-09-05.** `tools/run_pr005_replay.py` stopped reproducing
`PR-005.json` in ten of twenty cells. The cause was one instrument revised on 2026-08-27: `close`
moved in zero of 220 sessions, `high` in 70 and `low` in 81, by half a cent. Every guard was silent
and every guard was right - none of them has a REPLAY as its subject.

**It prints UNAVAILABLE rather than a number it cannot mean**, and the predicate for that is per
STUDY rather than per store: whether THESE instruments had bars here at the moment THIS study read
them. `AGENTS.md` section 10.6 rule 2 - a check that cannot measure says so, and does not report as
though it had.

    python tools/measure_study_drift.py
    python tools/measure_study_drift.py --data C:/PycharmProjects/SwingDesk/data

Read-only. Opens no store for write and reaches no network.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
RESULTS = REPO / "docs" / "prereg" / "results"

#: (result file, key holding the instrument list, key holding the vintage the study read at).
#: A study is listed only if its record carries all three; the rest report why they cannot be read.
STUDIES: list[tuple[str, str, str]] = [
    ("PR-001.json", "admitted", "run_at"),
    ("PR-005.json", "instruments", "run_at"),
    ("PR-013.json", "instruments", "snapshot"),
]


@dataclass(frozen=True)
class Drift:
    """What the store did to one study's sample after the study read it."""

    in_window: int
    available: bool
    reason: str = ""
    revised: int = 0
    new_sessions: int = 0
    worst: tuple[tuple[str, int, int, float | None, float | None], ...] = ()


def measure(con, ids: list[str], start: str, end: str, reference: str) -> Drift:
    """Compare the store now against the store as this study read it.

    `reference` is the study's own recorded vintage. The availability check is the load-bearing
    part and it is per STUDY: the store's earliest `knowledge_time` is NOT the question. The first
    version of this asked the global minimum, which for `PR-005` is nine hours BEFORE its `run_at`
    and hours before the fetch that first brought its 68 names in - so the check passed and the
    study's entire sample was then counted as "written since", which reads as total drift and means
    nothing. `run_pr005_replay.py`'s docstring already carries the fact; this encodes it.
    """
    con.execute("create or replace temp table study(id varchar)")
    con.executemany("insert into study values (?)", [(i,) for i in ids])

    in_window = con.execute(
        "select count(*) from bars b join study s on b.instrument_id = s.id "
        "where b.session_date between ? and ?", [start, end]).fetchone()[0]

    had_any = con.execute(
        "select count(*) from bars b join study s on b.instrument_id = s.id "
        "where b.session_date between ? and ? and b.knowledge_time <= ?::TIMESTAMPTZ",
        [start, end, reference]).fetchone()[0]
    if not had_any:
        return Drift(in_window=in_window, available=False,
                     reason=f"read at {reference[:19]}, before ANY of its bars were stored")

    since = con.execute(
        "select count(*) from bars b join study s on b.instrument_id = s.id "
        "where b.session_date between ? and ? and b.knowledge_time > ?::TIMESTAMPTZ",
        [start, end, reference]).fetchone()[0]
    revised = con.execute(
        "select count(*) from bars late join study s on late.instrument_id = s.id "
        "where late.session_date between ? and ? and late.knowledge_time > ?::TIMESTAMPTZ "
        "and exists (select 1 from bars early where early.instrument_id = late.instrument_id "
        "            and early.session_date = late.session_date "
        "            and early.knowledge_time <= ?::TIMESTAMPTZ)",
        [start, end, reference, reference]).fetchone()[0]

    worst = con.execute(
        "with late as (select b.* from bars b join study s on b.instrument_id = s.id "
        "   where b.session_date between ? and ? and b.knowledge_time > ?::TIMESTAMPTZ), "
        "early as (select b.* from bars b join study s on b.instrument_id = s.id "
        "   where b.session_date between ? and ? and b.knowledge_time <= ?::TIMESTAMPTZ) "
        "select l.instrument_id, count(*) n, "
        "   sum(case when l.close <> e.close then 1 else 0 end) close_moved, "
        "   min(l.close / nullif(e.close, 0)) lo, max(l.close / nullif(e.close, 0)) hi "
        "from late l join early e on l.instrument_id = e.instrument_id "
        "   and l.session_date = e.session_date "
        "group by 1 order by n desc limit 3",
        [start, end, reference, start, end, reference]).fetchall()

    return Drift(in_window=in_window, available=True, revised=revised,
                 new_sessions=since - revised, worst=tuple(worst))


def describe(close_moved: int, lo, hi) -> str:
    """The RATIO, not the difference - a 2:1 split reads x0.5, a 1:125 reverse split reads x125.

    An absolute percentage buries a corporate action; the ratio names it. A tick correction that
    leaves the close alone is the case that matters most here and it says so in words.
    """
    if not close_moved:
        return "close unchanged"
    if lo is None or hi is None:
        return "close moved"
    if abs(float(hi) - float(lo)) < 1e-9:
        return f"close x{float(hi):.6g}"
    return f"close x{float(lo):.6g} to x{float(hi):.6g}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default=str(REPO / "data"),
                        help="directory holding bars.duckdb; a worktree does not have one")
    parser.add_argument("--results", default=str(RESULTS),
                        help="directory holding the study result records")
    args = parser.parse_args(argv)

    bars = Path(args.data) / "bars.duckdb"
    if not bars.exists():
        print(f"UNAVAILABLE - no bar store at {bars}")
        print("  This checkout has no data/. Point --data at the main checkout's store.")
        return 0

    import duckdb

    results = Path(args.results)
    con = duckdb.connect(str(bars), read_only=True)
    print(f"store's earliest knowledge_time: "
          f"{con.execute('select min(knowledge_time) from bars').fetchone()[0]}")
    print()
    print(f"{'study':10} {'names':>6} {'in-window':>12} {'revised':>9} {'new':>7}  note")
    print("-" * 96)

    drifted = 0
    for filename, ids_key, time_key in STUDIES:
        record = json.loads((results / filename).read_text(encoding="utf-8"))
        study = filename[:-5]
        ids = record.get(ids_key)
        if not isinstance(ids, list):
            print(f"{study:10} {'-':>6} {'-':>12} {'-':>9} {'-':>7}  "
                  f"UNAVAILABLE - '{ids_key}' is a count, not a list")
            continue

        start, end = record["window"]
        drift = measure(con, ids, start, end, str(record[time_key]))
        if not drift.available:
            print(f"{study:10} {len(ids):>6} {drift.in_window:>12,} {'-':>9} {'-':>7}  "
                  f"UNAVAILABLE - {drift.reason}")
            continue

        moved = drift.revised + drift.new_sessions
        note = "unchanged since it ran" if not moved else "see below"
        print(f"{study:10} {len(ids):>6} {drift.in_window:>12,} {drift.revised:>9,} "
              f"{drift.new_sessions:>7,}  {note}")
        if moved:
            drifted += 1
        for instrument, n, close_moved, lo, hi in drift.worst:
            print(f"{'':10} {instrument:>8}  {n:>5} revised session(s), close moved in "
                  f"{close_moved} - {describe(close_moved, lo, hi)}")

    con.close()
    print()
    if drifted:
        print(f"{drifted} measurable study(ies) sit on a sample that has moved since they ran.")
        print("  A revision is not a fault - the vendor re-adjusts for splits and corrects ticks,")
        print("  and the store keeps every version. What has no owner is the REPLAY: a runner")
        print("  reading `latest_knowledge_time()` reads today's sample, not the recorded one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
