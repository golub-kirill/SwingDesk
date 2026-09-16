"""Pull the main checkout when the evening run has left `HANDOFF.md` modified - and nothing else.

`daily_run.cmd` ends with `build_state.py`, which rewrites `HANDOFF.md` section 2's generated blocks
from `data/`. So most mornings the main checkout holds one modified tracked file, and because every
merged change rewrites those same blocks, `git pull --ff-only` aborts on "local changes would be
overwritten". Found 2026-09-13, when the owner's pull failed on exactly that.

**The file is discarded only when every difference lies between generated markers.** Those blocks
are derived: the tool that wrote them writes them again after the pull, so nothing is lost. Anything
else - a hand edit to the prose, a removed marker, another modified tracked file, a staged change - is
somebody's work, and this tool refuses and changes nothing rather than guess which.

**It refuses while a pass is running, and that is not a courtesy.** Measured 2026-09-15: a pull
during the 18:30 pass killed it. `cmd.exe` reads a batch file AS IT RUNS, by byte offset, so a pull
that grew `daily_run.cmd` by sixteen lines made the running pass resume in the middle of a comment
and die on `'approval' is not recognized`. It died before restoring protection, and a position whose
stop had just been cancelled stood naked. The Python half failed the same way from the other side:
the process had the old policy module in memory and read the new `broker_policy.yml`, which it
refused. One instruction, two kinds of mixed version, and the warning that used to live in this
docstring was the only thing between them and the owner.

    python tools/update_checkout.py            # discard generated-only edits, pull, regenerate
    python tools/update_checkout.py --dry-run  # say what it would do, change nothing
    python tools/update_checkout.py --anyway   # skip the schedule check, when you know it is idle

Exit codes: 0 up to date · 1 git refused the pull, and its own message is printed · 2 refused here,
nothing changed.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(REPO / "src"))

# Imported after REPO, which is what puts `src` on the path above.
from swingdesk.platform import schedule

#: The one tracked file the evening run leaves modified.
GENERATED_FILE = "HANDOFF.md"

#: A generated block, markers kept and body dropped. Keeping the markers is what catches a removed
#: or renamed one: the skeleton then differs from the committed file's, as any hand edit does.
_BLOCK = re.compile(
    r"(<!-- BEGIN GENERATED: [^>]+? -->).*?(<!-- END GENERATED: [^>]+? -->)", re.DOTALL
)

PULL_FAILED = 1
REFUSED = 2

#: What the Task Scheduler calls a task that is running right now. `schedule.RUN_TASKS` names the
#: two passes; the coverage, classification and re-measurement passes are deliberately not here -
#: they read and write stores, but no pass of theirs is reading `daily_run.cmd` line by line.
RUNNING = "running"


def running_pass(
    tasks: Sequence[str] = schedule.RUN_TASKS,
    probe: Callable[[str], dict[str, Any] | None] = schedule.query_task,
) -> str | None:
    """The pass the scheduler reports running, `""` when none is, `None` when it cannot be read.

    Three answers rather than two, because "no pass is running" and "nobody could tell me" must not
    arrive as one value here: this tool refuses on both, and an operator needs to know which refusal
    they are reading. `--anyway` is the escape hatch for the second.
    """
    unreadable = False
    for task in tasks:
        record = probe(task)
        if record is None:
            unreadable = True
            continue
        if (record.get("Status") or "").strip().lower() == RUNNING:
            return task
    return None if unreadable else ""


def skeleton(text: str) -> str:
    """The file with every generated block emptied: exactly the part a hand edit would change."""
    return _BLOCK.sub(r"\1\2", text.replace("\r\n", "\n"))


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")


def judge(root: Path, porcelain: str) -> tuple[bool, str | None]:
    """(discard `HANDOFF.md` first?, why not). A reason means somebody's work is in the tree."""
    changes = [(line[:2], line[3:]) for line in porcelain.splitlines() if line.strip()]
    others = [path for _, path in changes if path != GENERATED_FILE]
    if others:
        return False, "other tracked files have local changes: " + ", ".join(others)
    if not changes:
        return False, None
    status = changes[0][0]
    if status != " M":
        return False, f"{GENERATED_FILE} is '{status.strip()}', not modified in the working tree only"
    committed = _git(root, "show", f"HEAD:{GENERATED_FILE}").stdout
    working = (root / GENERATED_FILE).read_text(encoding="utf-8")
    if skeleton(committed) != skeleton(working):
        return False, f"{GENERATED_FILE} differs OUTSIDE its generated blocks, which is a hand edit"
    return True, None


def regenerate(root: Path) -> None:
    """Write the blocks back, as the evening run does. `build_state.py` exiting 4 means a block this
    checkout cannot measure was left alone - its answer, not this tool's failure."""
    subprocess.run([sys.executable, "-X", "utf8", str(root / "tools" / "build_state.py")], cwd=root)


def update(
    root: Path, *, dry_run: bool = False, anyway: bool = False,
    tasks: Sequence[str] = schedule.RUN_TASKS,
    probe: Callable[[str], dict[str, Any] | None] = schedule.query_task,
) -> int:
    # BEFORE `git status`, because the reason to stop has nothing to do with the tree. A pull during
    # a pass breaks the pass whether or not this checkout is clean (2026-09-15, in the docstring).
    # `--dry-run` is checked too: it prints what WOULD happen, and what would happen is a refusal.
    if not anyway:
        busy = running_pass(tasks, probe)
        if busy is None:
            print("update: REFUSED, nothing changed - the Task Scheduler could not be read, so "
                  "whether an evening pass is running is unknown")
            print("  a pull during a pass kills it: cmd.exe reads daily_run.cmd as it runs. Run "
                  "this again when you know both passes are idle, or pass --anyway")
            return REFUSED
        if busy:
            print(f"update: REFUSED, nothing changed - {busy!r} is running now")
            print("  cmd.exe reads daily_run.cmd as it runs, by byte offset, so a pull that changes "
                  "that file makes the running pass resume mid-line and die. Wait for it to finish")
            return REFUSED

    status = _git(root, "status", "--porcelain", "--untracked-files=no")
    if status.returncode != 0:
        print(f"update: REFUSED - git status failed: {status.stderr.strip()}")
        return REFUSED
    discard, refusal = judge(root, status.stdout)
    if refusal:
        print(f"update: REFUSED, nothing changed - {refusal}")
        print("  commit, stash or revert that yourself, then run this again")
        return REFUSED

    if dry_run:
        first = f"discard {GENERATED_FILE}'s generated blocks, " if discard else ""
        print(f"update: would {first}pull --ff-only and regenerate section 2; changed nothing")
        return 0

    if discard:
        checkout = _git(root, "checkout", "--", GENERATED_FILE)
        if checkout.returncode != 0:
            print(f"update: REFUSED - could not discard {GENERATED_FILE}: {checkout.stderr.strip()}")
            return REFUSED
        print(f"update: discarded {GENERATED_FILE}'s generated blocks (derived; rebuilt below)")

    pull = _git(root, "pull", "--ff-only")
    print((pull.stdout + pull.stderr).rstrip())
    # After a discard the blocks go back even when the pull failed: the checkout is left as the
    # evening run leaves it, not one step short of it.
    if discard or pull.returncode == 0:
        regenerate(root)
    return 0 if pull.returncode == 0 else PULL_FAILED


def main() -> int:
    parser = argparse.ArgumentParser(prog="update_checkout")
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would be discarded and pulled, and change nothing")
    parser.add_argument("--anyway", action="store_true",
                        help="skip the schedule check. Only when you know no pass is running: a "
                             "pull during one kills it (2026-09-15)")
    args = parser.parse_args()
    return update(REPO, dry_run=args.dry_run, anyway=args.anyway)


if __name__ == "__main__":
    raise SystemExit(main())
