"""Hold the 19:30 second pass until the 18:30 daily run has finished - owner ruling 2026-09-14.

**Why.** Both passes write the same stores and DuckDB refuses a second writer, so a second pass that
starts while the first is still running fails on a lock and loses the evening it exists to save.
The evening run took 41 minutes on 2026-09-08 against 17.7 three sessions earlier, which left the
one-hour gap looking thin. Of the three options put to the owner - move the second pass later, make
it wait, or cap the candidate set - the owner chose waiting (`TODO.md`, "THE EVENING RUN TOOK 41
MINUTES").

**It asks the Task Scheduler, not a lock file.** The scheduler already knows whether the daily run
is running, and a lock file a crashed run left behind would hold every later evening hostage. The
field is `Status` - `Running` or `Ready` - and not `Scheduled Task State`, which says only whether
the task is enabled.

Exit codes, read by `tools/daily_run.cmd`:

    0  the daily run is not running - the second pass goes ahead
    1  it was still running when the wait ran out - the second pass is skipped, and says so
    4  the scheduler could not be read - UNAVAILABLE, and the pass runs anyway: an unmeasured
       condition must not suppress a pass (`AGENTS.md` §12), which is `retry_needed.py`'s rule too

    python tools/wait_for_first_pass.py
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.platform import schedule

TASK = "SwingDesk daily run"

#: How often to ask, and how long to wait in all. An hour takes the second pass to 20:30 at the
#: latest - still the same evening, and still before anything reads tomorrow's session.
POLL_SECONDS = 60
LIMIT_MINUTES = 60

FREE = 0
STILL_RUNNING = 1
UNAVAILABLE = 4


def running(task: str) -> bool | None:
    """Whether the scheduler reports `task` running now; None when it cannot be read."""
    record = schedule.query_task(task)
    if record is None:
        return None
    return (record.get("Status") or "").strip().lower() == "running"


def wait(task: str = TASK, limit_minutes: int = LIMIT_MINUTES, poll_seconds: int = POLL_SECONDS,
         probe: Callable[[str], bool | None] = running,
         sleep: Callable[[float], None] = time.sleep,
         say: Callable[[str], None] = print) -> int:
    """Ask until the task is not running or the limit passes. Never sleeps when it need not."""
    polls = max(1, math.ceil(limit_minutes * 60 / poll_seconds))
    for attempt in range(polls + 1):
        state = probe(task)
        if state is None:
            say(f"second pass: {task!r} could not be read from the Task Scheduler - UNAVAILABLE, "
                f"so the pass runs")
            return UNAVAILABLE
        if not state:
            if attempt:
                say(f"second pass: {task!r} has finished; waited {attempt * poll_seconds} seconds")
            return FREE
        if attempt == 0:
            say(f"second pass: {task!r} is still running; waiting up to {limit_minutes} minutes")
        if attempt < polls:
            sleep(poll_seconds)
    say(f"second pass: {task!r} was still running after {limit_minutes} minutes - skipped, so the "
        f"two passes never write the stores at once")
    return STILL_RUNNING


def main() -> int:
    parser = argparse.ArgumentParser(prog="wait_for_first_pass")
    parser.add_argument("--task", default=TASK, help="the scheduled task to wait for")
    parser.add_argument("--limit-minutes", type=int, default=LIMIT_MINUTES,
                        help="how long to wait in all before skipping the second pass")
    parser.add_argument("--poll-seconds", type=int, default=POLL_SECONDS,
                        help="how often to ask the scheduler")
    args = parser.parse_args()
    return wait(args.task, args.limit_minutes, args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
