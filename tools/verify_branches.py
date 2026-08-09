"""Gate 16: every parallel worktree is declared in HANDOFF.md.

The defect this exists for is recorded in `docs/08-pm/POSTMORTEM-2026-08-09.md`, root cause A. Three
efforts branched from the same commit and none of them knew about the others. One re-ran a study
another had already finished, reached the opposite conclusion, and merged first. Nothing was
corrupted and every other gate was green throughout, because no other gate looks outside the
checked-out tree.

`HANDOFF.md` opens by saying it is measured from the tree, and it is. That is the problem: a sibling
worktree is not in the tree, so an accurate document can be silently incomplete about the one thing
most likely to waste a session.

Scoped to WORKTREES rather than to all unmerged branches on purpose. A stale local branch is
somebody's abandoned idea and costs nothing; a checked-out worktree is an effort someone is running
right now, and that is what a fresh session needs to know about before it starts work.

Stdlib only.

    python tools/verify_branches.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HANDOFF = REPO / "HANDOFF.md"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout


def worktree_branches() -> list[tuple[str, str]]:
    """(branch, tip sha) for every worktree except the main one, in listing order."""
    entries: list[tuple[str, str]] = []
    path = head = branch = ""
    for line in _git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ").strip()
        elif line.startswith("HEAD "):
            head = line.removeprefix("HEAD ").strip()
        elif line.startswith("branch "):
            branch = line.removeprefix("branch ").strip().removeprefix("refs/heads/")
        elif not line.strip():
            if path and branch and Path(path).resolve() != REPO.resolve():
                entries.append((branch, head[:7]))
            path = head = branch = ""
    if path and branch and Path(path).resolve() != REPO.resolve():
        entries.append((branch, head[:7]))
    return entries


def main() -> int:
    if not HANDOFF.exists():
        print("HANDOFF.md is missing; it is the declared entry point", file=sys.stderr)
        return 1

    body = HANDOFF.read_text(encoding="utf-8")
    branches = worktree_branches()

    failures: list[str] = []
    for branch, sha in branches:
        if branch not in body:
            merged = _git("branch", "--merged", "master", "--format=%(refname:short)").split()
            state = "merged into master" if branch in merged else "NOT merged into master"
            failures.append(
                f"worktree branch {branch!r} ({sha}, {state}) is not named in HANDOFF.md. "
                f"A fresh session reading HANDOFF would not know it exists."
            )

    for failure in failures:
        print(f"  {failure}")
    print(f"\nworktrees: {len(branches)} parallel, {len(failures)} undeclared")
    if failures:
        print("\nAdd them to HANDOFF.md section 2 with tip date and one line on what they hold.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
