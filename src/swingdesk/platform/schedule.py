"""The Windows Task Scheduler, read - one parser, shared by gate 26 and `swingdesk status`.

Moved out of `tools/verify_schedule.py` on 2026-09-12 so that the status screen does not grow a
second opinion about what `267009` means. Every constant below moved byte for byte, comments and
all; `tools/verify_schedule.py` imports them back. Stdlib only - `platform` is the bottom layer and
imports nothing above it. Read-only: it queries and never creates, replaces or deletes a task.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from dataclasses import dataclass

#: The two passes that produce a run. `swingdesk status` shows these; gate 26 checks every task in
#: `TASKS`, which begins with them.
RUN_TASKS = ("SwingDesk daily run", "SwingDesk second pass")

#: The tasks `docs/runbooks/README.md` §1, §1a and §8 describe. Named here rather than discovered,
#: so a task RENAMED out from under the runbook reads as missing instead of silently passing.
#:
#: **The third one was added 2026-09-04 and is expected to be RED until somebody registers it**,
#: which is the whole point of adding it. `refresh_universe.py` describes tiered work - a periodic
#: pass widens coverage, a daily pass reads what is stored - and the periodic tier was specified on
#: 2026-08-12 and never scheduled at all. Nothing noticed for three weeks, while every evening's
#: report printed `PARTIAL UNIVERSE` over a universe that was 28% of what the rule admits, and
#: `CARD-001` ranked relative strength across that 28% as though it were the market.
#:
#: A task this file does not name is a task that can stop running and be missed, which is the
#: failure this gate exists for aimed at the schedule instead of at one run. The message names the
#: runbook section that carries the one command; it stops being red the moment it is registered.
TASKS = (
    *RUN_TASKS,
    "SwingDesk coverage pass",
    # Added 2026-09-05, and RED until the owner registers it - deliberately, on the coverage pass's
    # own precedent. A tier nothing watches is how `refresh_universe.py` went unscheduled for three
    # weeks; `refresh_classifications.py` is the second of that pair and went unscheduled longer.
    # What it cost: the coverage catch-up tripled the admitted universe on 2026-09-04 and the
    # classification store did not move with it, so candidates admitted UNCHECKED by the sector cap
    # went from 110 to 2,396 in one evening. `docs/runbooks/README.md` carries the one command.
    "SwingDesk classification pass",
    # Added 2026-09-13, RED until the owner registers it, on the same precedent. `AGENTS.md` §19.7:
    # a re-observation of a registered question spends no trial only because it is SCHEDULED and
    # every point is recorded - an unscheduled `tools/remeasure.py` is exactly the on-demand re-run
    # that ruling's guard forbids. `docs/runbooks/README.md` §8 carries the one command.
    "SwingDesk re-measurement pass",
)

#: `schtasks` reports the wrapper's exit code. `daily_run.cmd` exits 0 on a clean run and 2 on a
#: coded refusal, which `track_a_streak.py` also treats as clean - anything else is a crash.
CLEAN_RESULTS = ("0", "2")

#: ...except that `Last Result` holds an exit code only once a run has produced one. Between those
#: moments the Task Scheduler puts its own STATUS there instead, and a status is not a crash. Both
#: values below are `SCHED_S_*` HRESULTs from the scheduler's own header, and neither is a number
#: `daily_run.cmd` can return - which is what makes them safe to name rather than guess at.
#:
#: **What paid for the first row, 2026-08-24.** This gate reported *"SwingDesk second pass: last run
#: 7:30:00 PM exited 267009"* at 19:39, nine minutes into a pass that had started at 19:30 and was
#: working normally - the first clean evening after the schema drift that had killed every run since
#: 08-18. `267011` was already special-cased and `267009` is the same KIND of value, so the check
#: called a healthy run a crash on the one evening it had something to say. A gate that manufactures
#: alarm trains its operator to ignore it, which costs exactly what `AGENTS.md` section 10.6 rule 2
#: says a gate that manufactures confidence costs.
NO_RESULT_YET = {
    "267009": "still running",     # SCHED_S_TASK_RUNNING,     0x00041301
    "267011": "has not run yet",   # SCHED_S_TASK_HAS_NOT_RUN, 0x00041303
}

#: Failure codes this gate can NAME. The verdict stays `crash` - these are real failures and the
#: gate is right to be red - but a raw negative HRESULT tells an operator nothing, and this gate's
#: own history is that an unexplained number is how it lost credibility once already (see the note
#: above). Naming a cause is not the same act as fixing one: the scheduling decision stays the
#: owner's, and `TODO.md` section 6 holds it.
#:
#: **What paid for the first row, 2026-08-29.** Both tasks reported the same last run time, and the
#: second pass carried this code. `StartWhenAvailable` catches missed triggers up TOGETHER, so on a
#: day the machine was asleep the 18:30 pass starts and the 19:30 pass cannot start at all - and
#: those are exactly the days whose stale data the second pass exists to repair. The two failures
#: are not independent, which is the whole finding, and it was reachable only because somebody read
#: the number.
DIAGNOSED = {
    "-2147020576": (
        "the other pass was already running (0x80070420, ERROR_SERVICE_ALREADY_RUNNING). A "
        "catch-up fires both triggers together, so this is the day the retry was most needed and "
        "least able to run - TODO.md section 6"
    ),
}

#: Settings that make a task silently not run, and that only the verbose query shows. Neither is a
#: fault this can fix - both are the owner's environment - but both explain an evening with no log
#: line, which is otherwise indistinguishable from a run that did nothing.
HAZARDS = {
    "Logon Mode": ("Interactive only", "runs only while the user is logged on"),
    "Power Management": ("No Start On Batteries", "does not start on battery power"),
}


def query_task(task: str) -> dict[str, str] | None:
    """One task's verbose record, or `None` when it does not exist."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task, "/V", "/FO", "CSV"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    rows = list(csv.DictReader(result.stdout.splitlines()))
    return rows[0] if rows else None


def verdict(last_result: str) -> tuple[str, str]:
    """What `Last Result` says about the run that produced it: `clean`, `pending` or `crash`.

    Pure, and separate from `main`, because the interesting cases cannot be summoned on demand: a
    task is mid-run for a few minutes an evening, which is precisely when nobody is reading a gate.
    Tested directly in `tests/test_gates.py` instead of waiting for the calendar to reproduce it.
    """
    code = last_result.strip()
    if not code:
        return "pending", "no result reported"
    if code in CLEAN_RESULTS:
        return "clean", f"exit {code}"
    if code in NO_RESULT_YET:
        return "pending", NO_RESULT_YET[code]
    if code in DIAGNOSED:
        # Still a crash. Still red. It just says what happened.
        return "crash", DIAGNOSED[code]
    return "crash", f"exited {code}"


@dataclass(frozen=True)
class TaskReading:
    """One task as `swingdesk status` shows it."""

    task: str
    state: str
    next_run: str
    last_run: str
    judgement: str
    phrase: str


def read(task: str) -> TaskReading | None:
    """One task, summarised; None off Windows or when the task is not registered.

    None rather than a refusal because both are ordinary: a worktree, a CI runner and a laptop that
    does not run the schedule all look like this, and the status screen says so in words.
    """
    if sys.platform != "win32":
        return None
    record = query_task(task)
    if record is None:
        return None
    judgement, phrase = verdict((record.get("Last Result") or "").strip())
    return TaskReading(
        task=task,
        state=(record.get("Scheduled Task State") or "").strip(),
        next_run=(record.get("Next Run Time") or "?").strip(),
        last_run=(record.get("Last Run Time") or "").strip(),
        judgement=judgement,
        phrase=phrase,
    )
