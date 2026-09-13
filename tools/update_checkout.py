"""Pull the main checkout when the evening run has left `HANDOFF.md` modified - and nothing else.

`daily_run.cmd` ends with `build_state.py`, which rewrites `HANDOFF.md` section 2's generated blocks
from `data/`. So most mornings the main checkout holds one modified tracked file, and because every
merged change rewrites those same blocks, `git pull --ff-only` aborts on "local changes would be
overwritten". Found 2026-09-13, when the owner's pull failed on exactly that.

**The file is discarded only when every difference lies between generated markers.** Those blocks
are derived: the tool that wrote them writes them again after the pull, so nothing is lost. Anything
else - a hand edit to the prose, a removed marker, another modified tracked file, a staged change - is
somebody's work, and this tool refuses and changes nothing rather than guess which.

Not during the evening passes (18:30 and 19:30): a pull moves the code a running pass is reading.

    python tools/update_checkout.py            # discard generated-only edits, pull, regenerate
    python tools/update_checkout.py --dry-run  # say what it would do, change nothing

Exit codes: 0 up to date · 1 git refused the pull, and its own message is printed · 2 refused here,
nothing changed.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: The one tracked file the evening run leaves modified.
GENERATED_FILE = "HANDOFF.md"

#: A generated block, markers kept and body dropped. Keeping the markers is what catches a removed
#: or renamed one: the skeleton then differs from the committed file's, as any hand edit does.
_BLOCK = re.compile(
    r"(<!-- BEGIN GENERATED: [^>]+? -->).*?(<!-- END GENERATED: [^>]+? -->)", re.DOTALL
)

PULL_FAILED = 1
REFUSED = 2


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


def update(root: Path, *, dry_run: bool = False) -> int:
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
    args = parser.parse_args()
    return update(REPO, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
