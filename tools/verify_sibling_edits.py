"""Gate 33 (advisory): another live branch is editing the same lines you are.

`POSTMORTEM-2026-08-09.md` root cause A: three worktrees branched from one commit, none knew about
the others, and one re-ran a study another had already finished and reached the opposite conclusion.
**Gate 16 was the answer, and gate 16 is not enough.** It checks that every worktree is NAMED in
`HANDOFF.md` - which tells a session that a sibling exists, not that the sibling is rewriting the
paragraph it is about to rewrite.

**It happened again on 2026-08-25 with gate 16 green.** Two trees independently found that four
governed documents still asserted an impossibility this repository had refuted, and both corrected
`RISK_REGISTER.md` D-3 and the Canadian row of `UX_TASK_FLOWS.md`. The commits are two hours apart.
Reading the sibling's commit SUBJECTS at the start of the session - which is what gate 16 makes
possible - did not reveal it, because the subjects named the sibling's other work. Reading its DIFF
would have, in one command, and nothing asked for that.

**What it reports.** For every branch that is checked out in a worktree or unmerged into `master`,
the files this branch and that one have both changed since their shared merge-base, and the
overlapping line ranges **expressed in merge-base coordinates** - so an overlap means both trees
changed the same original text, not merely the same file. Two sessions appending to different parts
of `TODO.md` do not collide and are not reported; two sessions rewriting one table row are.

**ADVISORY BY DESIGN: it prints and returns 0.** Parallel work is this repository's normal mode
(`HANDOFF.md` §2) and an overlap is often legitimate - the same shared log, the same registry.
Vetoing it would block ordinary work, and a gate that blocks ordinary work gets bypassed
(`CI_POLICY.md` §3). Visibility, not veto.

**In CI there are no siblings.** A shallow clone has no other branches, so it says it did not run
rather than reporting a clean result for a check it never made - the same handling as gate 29's
cross-branch half.

Stdlib only.

    python tools/verify_sibling_edits.py
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: `@@ -a,b +c,d @@` - only the base side is read. A hunk's base range is the text that existed
#: before either branch touched it, which is the only coordinate system the two diffs share.
HUNK = re.compile(r"^@@ -(?P<start>\d+)(?:,(?P<count>\d+))? ")

#: The trunk. Branches already merged into it are history rather than live efforts.
TRUNK = "master"


def _git(*args: str) -> str | None:
    """Git output, or None when git cannot answer - a shallow clone is not a failure."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=False,
            # The diffs carry section signs, em dashes and the course's Cyrillic. Windows decodes a
            # pipe as cp1252 by default, which raises inside a reader thread and leaves this tool
            # reporting "0 overlaps" over output it never read - a gate manufacturing confidence.
            encoding="utf-8", errors="replace",
        )
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def _live_branches() -> list[str] | None:
    """Every branch worth comparing against: checked out somewhere, or not yet merged to trunk.

    Both sources, because neither alone is right. A worktree's branch may already be merged and
    still be actively worked; an unmerged branch may have no worktree on this machine and still be
    the thing a pull request is about.
    """
    listed = _git("branch", "--no-merged", TRUNK, "--format=%(refname:short)")
    worktrees = _git("worktree", "list", "--porcelain")
    if listed is None and worktrees is None:
        return None
    names: list[str] = [line.strip() for line in (listed or "").splitlines() if line.strip()]
    for line in (worktrees or "").splitlines():
        if line.startswith("branch "):
            names.append(line.removeprefix("branch ").strip().removeprefix("refs/heads/"))
    here = (_git("rev-parse", "--abbrev-ref", "HEAD") or "").strip()
    seen: dict[str, None] = {}
    for name in names:
        if name and name != here and name != TRUNK:
            seen.setdefault(name, None)
    return list(seen)


def _touched(base: str, ref: str) -> dict[str, list[tuple[int, int]]]:
    """path -> base-side line ranges changed between `base` and `ref`.

    A pure insertion has a zero-length base range; it is widened to a single line so that two
    branches appending at the same anchor - the end of one file, the same table - are seen to
    collide. Without that, the commonest real overlap is invisible.
    """
    diff = _git("diff", "--unified=0", "--no-color", f"{base}..{ref}")
    ranges: dict[str, list[tuple[int, int]]] = {}
    path = ""
    for line in (diff or "").splitlines():
        if line.startswith("+++ b/"):
            path = line.removeprefix("+++ b/").strip()
        elif line.startswith("+++ /dev/null"):
            path = ""
        elif path and (match := HUNK.match(line)):
            start = int(match.group("start"))
            count = int(match.group("count") or 1)
            ranges.setdefault(path, []).append((start, start + max(count, 1) - 1))
    return ranges


def _overlaps(
    mine: list[tuple[int, int]], theirs: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    found = []
    for a_start, a_end in mine:
        for b_start, b_end in theirs:
            low, high = max(a_start, b_start), min(a_end, b_end)
            if low <= high:
                found.append((low, high))
    return sorted(set(found))


def main() -> int:
    branches = _live_branches()
    if branches is None:
        print("  sibling check DID NOT RUN: git could not list branches (a shallow CI clone has "
              "none). This is not a clean result.")
        print("\nsibling edits: not run")
        return 0

    reports: list[str] = []
    compared = 0
    for branch in sorted(branches):
        base = (_git("merge-base", "HEAD", branch) or "").strip()
        if not base:
            continue
        mine, theirs = _touched(base, "HEAD"), _touched(base, branch)
        if not mine:
            continue
        compared += 1
        for path in sorted(set(mine) & set(theirs)):
            hits = _overlaps(mine[path], theirs[path])
            if not hits:
                continue
            where = ", ".join(
                f"{low}" if low == high else f"{low}-{high}" for low, high in hits[:6]
            )
            more = f" (+{len(hits) - 6} more)" if len(hits) > 6 else ""
            reports.append(
                f"{path}: both this branch and `{branch}` changed base line(s) {where}{more}"
            )

    for report in sorted(set(reports)):
        print(f"  {report}")
    if reports:
        print(
            "\n  Advisory. Line numbers are in the shared merge-base, so both trees rewrote the"
            "\n  same original text. Read the sibling's diff before continuing - `git diff"
            "\n  master...<branch> -- <path>` - and decide which version survives NOW rather than"
            "\n  at merge time (AGENTS.md 10.1, 10.2)."
        )
    print(
        f"\nsibling edits: {compared} live branch(es) compared, {len(set(reports))} overlap(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
