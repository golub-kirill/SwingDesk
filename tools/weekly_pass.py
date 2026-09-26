"""Is a weekly pass due? The question a daily trigger asks so that a killed or missed pass retries.

**What paid for it, 2026-09-26.** The coverage pass of 2026-09-20 was killed four minutes in by a
clean restart (`0xC000013A`), and its next attempt was its next weekly trigger - a week of coverage
lost to one reboot. Task Scheduler's own *"if the task fails, restart every"* does not cover it: it
retries a task that failed to START, and a process that started and died counts as a successful
launch. So each weekly task now fires DAILY, and its wrapper asks this first:

    python tools/weekly_pass.py due coverage --data data     exit 0: due, run it
                                                             exit 10: done this week, skip
    python tools/weekly_pass.py done coverage --data data    after a clean finish

**The week starts on Sunday at 00:00, local time**, because every weekly pass is scheduled on a
Sunday. That anchor is what keeps the cadence: a pass killed on Sunday runs on Monday, and the next
one still runs on Sunday, because Monday's run belongs to the week that began the day before. A
threshold in days would drift the schedule to whichever weekday the retry landed on.

**Done means the pass FINISHED with a clean code** - 0, or 2, the coded refusal gate 26 also counts
as clean. A refusal is a real answer and re-asking tomorrow is not a retry, and for
`remeasure.py` a second point in one week would be the re-run-until-it-flips search `AGENTS.md`
§19.7 forbids. A crash writes nothing, so tomorrow's trigger runs it again.

The stamp is runtime state in `data/weekly/<name>.done`, holding the instant of the last clean
finish. It is not a record: the pass's own log and output are.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

#: Exit code for "already done this week". Above every code a Python crash or `argparse` produces,
#: so a wrapper's `if errorlevel 10` cannot mistake a broken check for a finished pass - and a
#: broken check then RUNS the pass, which costs minutes, where skipping it would cost a week.
NOT_DUE = 10

#: Monday is 0 in `datetime.weekday()`; every weekly pass is scheduled on a Sunday.
WEEK_STARTS = 6


def week_start(now: datetime) -> datetime:
    """Midnight of the most recent Sunday at or before `now`, in `now`'s own timezone."""
    back = (now.weekday() - WEEK_STARTS) % 7
    return (now - timedelta(days=back)).replace(hour=0, minute=0, second=0, microsecond=0)


def stamp_path(data: Path, name: str) -> Path:
    return data / "weekly" / f"{name}.done"


def last_clean_finish(data: Path, name: str) -> datetime | None:
    """When the pass last finished cleanly, or `None` if never, or if the stamp cannot be read.

    An unreadable stamp is treated as no stamp: the pass then runs, which is the cheap mistake.
    """
    try:
        return datetime.fromisoformat(stamp_path(data, name).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_due(data: Path, name: str, now: datetime) -> bool:
    finished = last_clean_finish(data, name)
    return finished is None or finished < week_start(now)


def record_done(data: Path, name: str, now: datetime) -> None:
    path = stamp_path(data, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(now.isoformat(), encoding="utf-8")


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("due", "done"))
    parser.add_argument("name", help="the pass, e.g. coverage, classification, remeasure-PR-016")
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args(argv)
    # The machine's local time, aware, because the Sunday the schedule means is the local one.
    moment = now if now is not None else datetime.now().astimezone()

    if args.action == "done":
        record_done(args.data, args.name, moment)
        print(f"{args.name}: finished cleanly at {moment:%Y-%m-%d %H:%M %Z}; next due from "
              f"{week_start(moment) + timedelta(days=7):%Y-%m-%d}")
        return 0
    if is_due(args.data, args.name, moment):
        return 0
    finished = last_clean_finish(args.data, args.name)
    print(f"{args.name}: already finished this week ({finished:%Y-%m-%d %H:%M}); nothing to do")
    return NOT_DUE


if __name__ == "__main__":
    raise SystemExit(main())
