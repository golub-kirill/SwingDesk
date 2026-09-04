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

**A DELETION counts as a change to every line the file had**, so one branch removing what another
is rewriting is reported - the collision a textual merge settles silently, in whichever direction
the merge strategy prefers. A file both branches removed is not reported: there is nothing to
choose between.

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

    **A DELETION covers the file's whole base-side extent**, so a branch that removes a file
    collides with a branch editing any line of it. That is arguably the overlap that most needs a
    person: a textual merge settles delete-against-edit silently, in whichever direction the merge
    strategy prefers, and nobody is asked which was meant. Until 2026-09-04 it was invisible here -
    a deleted file's header reads `+++ /dev/null`, the path was dropped on that line, and the file
    never entered the map at all. The base-side path comes from `--- a/` instead, which is the one
    place the diff still names it.
    """
    diff = _git("diff", "--unified=0", "--no-color", f"{base}..{ref}")
    ranges: dict[str, list[tuple[int, int]]] = {}
    path = ""
    removed = ""
    # `---` and `+++` are read only in a file's HEADER, between `diff --git` and the first hunk.
    # Inside a hunk they are content: a removed line reading `-- a/x` is printed as `--- a/x`, and
    # this repository's documents quote diffs. The old code had the same ambiguity on `+++ b/`;
    # bounding it costs one flag and the first `@@` is an exact end marker, since a body line can
    # never begin with one.
    in_header = False
    for line in (diff or "").splitlines():
        if line.startswith("diff --git "):
            path, removed, in_header = "", "", True
        elif in_header and line.startswith("--- a/"):
            removed = line.removeprefix("--- a/").strip()
        elif in_header and line.startswith("+++ b/"):
            path = line.removeprefix("+++ b/").strip()
        elif in_header and line.startswith("+++ /dev/null"):
            path = removed
        elif (match := HUNK.match(line)) is not None:
            in_header = False
            if path:
                start = int(match.group("start"))
                count = int(match.group("count") or 1)
                ranges.setdefault(path, []).append((start, start + max(count, 1) - 1))
    return ranges


def _deleted(base: str, ref: str) -> set[str]:
    """Paths that existed at `base` and are gone at `ref`.

    Asked separately from `_touched` because it answers a different question: that one says which
    original lines a branch changed, this one says which files it removed outright. A path BOTH
    sides removed is not a collision - there is nothing for a merge to choose between, and nothing
    for a person to decide - and it is the one exclusion this gate can make with no judgement at
    all, in the same spirit as `_same_as_trunk` below.
    """
    listing = _git("diff", "--name-only", "--diff-filter=D", f"{base}..{ref}")
    return {line.strip() for line in (listing or "").splitlines() if line.strip()}


def _same_as_trunk(branch: str, path: str) -> bool:
    """Is the sibling's version of this file the same object as trunk's?

    Compared by blob id via `rev-parse`, which asks git what it already knows rather than reading
    two files and hashing them here - the same object id is the strongest possible statement that
    there is nothing to choose between.

    **A path missing from one side is not a match, and that guard is now REACHED rather than
    merely defensive.** `rev-parse` fails for a file absent at that ref and `_git` returns `None`;
    two `None`s compared equal would read as *identical, nothing to decide*. The way to reach it is
    one branch deleting what the other rewrites, which `_touched` above could not record until
    2026-09-04 - the guard was written on the same day against the gap being closed, and closing it
    is what turned the sentence from a prediction into a covered case.
    """
    mine = _git("rev-parse", f"{TRUNK}:{path}")
    theirs = _git("rev-parse", f"{branch}:{path}")
    if mine is None or theirs is None:
        return False
    return mine.strip() == theirs.strip()


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
        gone_mine, gone_theirs = _deleted(base, "HEAD"), _deleted(base, branch)
        for path in sorted(set(mine) & set(theirs)):
            if path in gone_mine and path in gone_theirs:
                # Both sides removed it. Nothing to choose between and nothing to merge - the one
                # deletion case that is not a collision.
                continue
            if _same_as_trunk(branch, path):
                # NOTHING TO DECIDE BETWEEN, so nothing to report. Measured 2026-09-04: this gate
                # named eight overlaps against `claude/a-research-instrument-not-a-broker`, a branch
                # whose `tools/check_gates.py` and `tools/verify_registry_keys.py` are BYTE-IDENTICAL
                # to trunk's - its work reached `master` under a different SHA and left the copy
                # orphaned, so `git branch --merged` cannot see it and it will be listed for ever.
                #
                # §10.1's whole argument is that this gate stops two efforts rewriting one
                # paragraph. A gate reporting the same phantom overlaps every run is one an operator
                # learns to skim, and then it is not there on the evening two efforts really do
                # collide - `AGENTS.md` §12's *a gate that manufactures alarm costs what one that
                # manufactures confidence costs*, arrived at by neglect.
                #
                # The test is EXACT and needs no judgement: if the sibling's blob for this path is
                # the same object as trunk's, there is no version to choose. It deliberately does
                # NOT try to decide which side is newer - that is the fuzzy question, and answering
                # it wrongly would hide a real collision.
                continue
            hits = _overlaps(mine[path], theirs[path])
            if not hits:
                continue
            where = ", ".join(
                f"{low}" if low == high else f"{low}-{high}" for low, high in hits[:6]
            )
            more = f" (+{len(hits) - 6} more)" if len(hits) > 6 else ""
            # The stated subject has to match what happened, or the reader acts on the wrong thing
            # (`AGENTS.md` §12: a defensible verdict under a wrong description). A deletion is not
            # "both changed these lines", and it is the case a merge settles without asking.
            if path in gone_theirs:
                reports.append(
                    f"{path}: `{branch}` DELETES this file; this branch changed base line(s) "
                    f"{where}{more}"
                )
            elif path in gone_mine:
                reports.append(
                    f"{path}: this branch DELETES this file; `{branch}` changed base line(s) "
                    f"{where}{more}"
                )
            else:
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
