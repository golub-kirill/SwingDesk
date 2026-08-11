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
    """(branch, tip sha) for every worktree except the main one, in listing order.

    The main working tree is always `git worktree list`'s FIRST entry, which is how it is
    identified here.

    **This used to skip whichever tree the gate was running in, not the main one** (fixed
    2026-08-10). The two coincide only when the gate runs from the main checkout, so the gate
    returned different verdicts on one commit depending on where it was invoked: from a worktree it
    exempted the running effort and counted the main checkout as a sibling - whose branch is
    `master`, a string that appears in `HANDOFF.md` many times over, so it could never fail. On
    664e84a it was green from `swingdesk-documentation-321418` and red from the main checkout.

    A gate that exempts the effort running it is exempting the one effort a fresh session is
    guaranteed not to know about yet, which inverts what `POSTMORTEM-2026-08-09.md` root cause A
    asks for. Declaring your own worktree in `HANDOFF.md` section 2 before your gates go green is
    the discipline, and it costs one table row.
    """
    entries: list[tuple[str, str]] = []
    records: list[tuple[str, str, str]] = []
    path = head = branch = ""
    for line in _git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ").strip()
        elif line.startswith("HEAD "):
            head = line.removeprefix("HEAD ").strip()
        elif line.startswith("branch "):
            branch = line.removeprefix("branch ").strip().removeprefix("refs/heads/")
        elif not line.strip():
            if path and branch:
                records.append((path, branch, head[:7]))
            path = head = branch = ""
    if path and branch:
        records.append((path, branch, head[:7]))

    for _path, branch_name, sha in records[1:]:  # [0] is the main working tree
        entries.append((branch_name, sha))
    return entries


def merged_branches() -> set[str] | None:
    """Branches merged into master, or None when no `master` ref resolves here.

    A GitHub Actions checkout creates only the branch being built, so `git branch --merged master`
    exits 128 on the runner even with full history fetched. That crashed this gate on CI's first
    run - and only CI could have caught it, because on any developer machine `master` is simply
    always there.

    Merge state is *commentary* here: the gate's actual question is whether each worktree is named
    in HANDOFF, which needs no master ref at all. So a missing ref degrades the annotation and must
    never fail the check. `unavailable` is not `fail` (HANDOFF section 8) applies to a gate's own
    inputs too.
    """
    for ref in ("master", "origin/master"):
        try:
            return set(_git("branch", "--merged", ref, "--format=%(refname:short)").split())
        except subprocess.CalledProcessError:
            continue
    return None


def _merge_state(branch: str, merged: set[str] | None, *, suffix: str = "") -> str:
    if merged is None:
        return "merge state unknown - no master ref in this clone"
    return ("merged" if branch in merged else "NOT merged") + suffix


def main() -> int:
    if not HANDOFF.exists():
        print("HANDOFF.md is missing; it is the declared entry point", file=sys.stderr)
        return 1

    body = HANDOFF.read_text(encoding="utf-8")
    branches = worktree_branches()

    merged = merged_branches()

    failures: list[str] = []
    for branch, sha in branches:
        if branch not in body:
            state = _merge_state(branch, merged, suffix=" into master")
            failures.append(
                f"worktree branch {branch!r} ({sha}, {state}) is not named in HANDOFF.md. "
                f"A fresh session reading HANDOFF would not know it exists."
            )

    for failure in failures:
        print(f"  {failure}")

    # The census is printed even when the gate is green, because the check is only that each branch
    # is NAMED - a row can still describe a tip or a merge state that has since moved. On 2026-08-10
    # HANDOFF said the council worktree sat "at master's tip"; it was six commits behind.
    #
    # Asserting the tip SHA against the document was considered and REJECTED: a branch tip moves
    # with every commit, so the gate would demand a HANDOFF edit per commit and be bypassed within a
    # day. Printing ground truth next to the claim costs nothing and leaves the comparison to a
    # reader, which is the right split for prose that no parser should be interpreting.
    for branch, sha in branches:
        print(f"  {branch}  tip {sha}  {_merge_state(branch, merged, suffix=' into master')}")

    print(f"\nworktrees: {len(branches)} parallel, {len(failures)} undeclared")
    if failures:
        print("\nAdd them to HANDOFF.md section 2 with tip date and one line on what they hold.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
