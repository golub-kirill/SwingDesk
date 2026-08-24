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
        if last_result and last_result not in CLEAN_RESULTS and last_result != "267011":
            # 267011 is "has not run yet", which a freshly registered task reports and which is not
            # a failure. Every other non-clean code is the wrapper crashing.
            failures.append(
                f"{task}: last run {last_run} exited {last_result} - see data/daily_run.log"
            )

    for failure in failures:
        print(f"  {failure}")
    print(f"--- schedule: {'PASS' if not failures else 'FAIL'} ({len(seen)} task(s) named)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
