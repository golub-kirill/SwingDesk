"""Do the scheduled tasks exist, and did they last succeed? Asked of the machine, not of a document.

**What paid for this, 2026-08-23.** `TODO.md` §4 and two session handoffs carried *"Register the
19:30 task — until it exists the retry inside the run is live and the second pass is not"* as an
open item. The task had been registered on **2026-08-18**, five days earlier. `AGENTS.md` §12 knew —
it says the run died every evening *"both passes, once the 19:30 task was registered"* — so two
documents in this repository contradicted each other about a fact neither could check, and the
stale one was the one being acted on. The owner was handed a `schtasks /Create` line for a task that
already existed, and only answered `N` to the replace prompt by luck.

`AGENTS.md` §12's habit is explicit about the response: when you find a stale claim, **add a gate
rather than fixing the instance.** No gate can see the Windows Task Scheduler from CI, which is
exactly why nothing did.

**Advisory, and `UNAVAILABLE` off the scheduling machine** — the same shape as gates 23 and 24,
which read `data/`. A check that answered differently depending on where it ran and did not say so
would manufacture confidence, which `AGENTS.md` §10.6 rule 2 names as worse than no check at all.

**Read-only. It queries and never creates, replaces or deletes a task.** Registering one is the
owner's step (`docs/runbooks/README.md` §1a) and stays that way.

    python tools/verify_schedule.py
"""

from __future__ import annotations

import csv
import subprocess
import sys

#: The two tasks `docs/runbooks/README.md` §1 and §1a describe. Named here rather than discovered,
#: so a task RENAMED out from under the runbook reads as missing instead of silently passing.
TASKS = ("SwingDesk daily run", "SwingDesk second pass")

UNAVAILABLE_EXIT = 4

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

#: Settings that make a task silently not run, and that only the verbose query shows. Neither is a
#: fault this can fix - both are the owner's environment - but both explain an evening with no log
#: line, which is otherwise indistinguishable from a run that did nothing.
HAZARDS = {
    "Logon Mode": ("Interactive only", "runs only while the user is logged on"),
    "Power Management": ("No Start On Batteries", "does not start on battery power"),
}


def _query(task: str) -> dict[str, str] | None:
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
    return "crash", f"exited {code}"


def main() -> int:
    if sys.platform != "win32":
        print("schedule: UNAVAILABLE - the Task Scheduler exists only on the scheduling machine.")
        return UNAVAILABLE_EXIT

    seen = [(task, _query(task)) for task in TASKS]
    if all(record is None for _, record in seen):
        # Not a failure. A worktree, a CI runner and a laptop that does not run the schedule all
        # look like this, and calling it red would train the operator to ignore the check.
        print("schedule: UNAVAILABLE - neither task is registered on this machine.")
        return UNAVAILABLE_EXIT

    failures: list[str] = []
    pending = 0
    for task, record in seen:
        if record is None:
            failures.append(f"{task}: NOT REGISTERED. docs/runbooks/README.md has the command.")
            continue
        last_result = (record.get("Last Result") or "").strip()
        last_run = (record.get("Last Run Time") or "").strip()
        state = (record.get("Scheduled Task State") or "").strip()
        print(f"  {task}")
        print(f"      state       {state} · next {record.get('Next Run Time', '?').strip()}")
        print(f"      last run    {last_run} · exit {last_result or '?'}")
        for field, (needle, consequence) in HAZARDS.items():
            if needle in (record.get(field) or ""):
                print(f"      NOTE        {consequence} ({field}: {needle})")
        if state.lower() != "enabled":
            failures.append(f"{task}: scheduled state is {state!r}, not Enabled")
        judgement, phrase = verdict(last_result)
        if judgement == "pending":
            pending += 1
            print(f"      NOTE        {phrase} - this check says nothing about that run")
        elif judgement == "crash":
            failures.append(
                f"{task}: last run {last_run} exited {last_result} - see data/daily_run.log"
            )

    for failure in failures:
        print(f"  {failure}")
    # The summary names what was JUDGED, not what was queried. A task mid-run leaves this check with
    # nothing to say about it, and a bare PASS over two tasks when only one was judged is the same
    # overclaim in the other direction.
    counted = f"{len(seen)} task(s) named"
    if pending:
        counted += f", {pending} with no result to judge"
    print(f"--- schedule: {'PASS' if not failures else 'FAIL'} ({counted})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
