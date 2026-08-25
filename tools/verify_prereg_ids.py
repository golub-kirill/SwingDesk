"""Gate 29: a pre-registration id is reserved once, and reserving it makes the debt visible.

`docs/prereg/README.md` §"`PR-006` was reserved on 2026-08-02 and went unlisted here until
2026-08-05" states the rule and then states that nothing enforces it: *"an id reserved by reference
only, with no file behind it, leaves nothing for a gate to find. Worth fixing if a third one
appears."* A third has appeared, and `TODO.md` §5 has carried it since.

**Three checks, and the third is `AGENTS.md` §10.2 turned into a machine.**

1. **Every id with a file is in the index.** A study document that exists and is not listed is a
   study nobody browsing the index will find.
2. **Every id REFERENCED anywhere in `docs/` is in the index.** This is the `PR-006` case exactly:
   an id reserved inside a decision record, with no file behind it, is invisible to every other
   check in this tree. Reserving an id is how a debt becomes visible, and an unlisted reservation
   is the debt going quiet.
3. **No two UNMERGED branches claim one id for different studies.** `POSTMORTEM-2026-08-09.md` root
   cause A is two efforts answering the same question without looking sideways, and
   `RECONCILIATION_PLAN.md` records the collisions it produced - two `PR-007`s and two `DR-005`s.
   Measured 2026-08-24: `PR-006` and `PR-007` each carry two different slugs across this
   repository's branches, and **both colliding branches are merged**, so the numbering was
   reconciled and what survives is history. Restricting the check to `--no-merged` is therefore not
   a convenience - a merged branch's old filename is a correct statement about a commit, the same
   way a struck-through count is.

**What it cannot do, said out loud rather than passed over.** The cross-branch half needs the other
branches to be present, and a shallow CI clone has none of them. It reports that it could not run
instead of quietly returning green for a check it never made - `AGENTS.md` §10.6 rule 2 is about
exactly this, and a gate answering differently depending on where it runs manufactures confidence.

    python tools/verify_prereg_ids.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

#: Root of the tree being checked. Overridable so a test can point the gate at a fixture.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
PREREG = REPO / "docs" / "prereg"
INDEX = PREREG / "README.md"

#: `PR-012-cross-sectional-relative-strength.md` -> id `PR-012`, slug the rest.
DOCUMENT = re.compile(r"^(?P<id>PR-\d{3})-(?P<slug>[a-z0-9-]+)\.md$")

#: A reference to an id in prose. Backticked or bare; both are used across the tree.
REFERENCE = re.compile(r"\bPR-(\d{3})\b")

#: Directories whose ids are records of past numbering rather than live reservations. A report in
#: `results/` belongs to a study already in the index by construction.
NOT_A_RESERVATION = ("docs/prereg/results/",)


def _indexed() -> set[str]:
    """Ids the prereg index lists."""
    if not INDEX.is_file():
        return set()
    return {f"PR-{n}" for n in REFERENCE.findall(INDEX.read_text(encoding="utf-8"))}


def _documents() -> dict[str, str]:
    """id -> slug, for every pre-registration document in this tree."""
    found: dict[str, str] = {}
    if not PREREG.is_dir():
        return found
    for path in sorted(PREREG.glob("PR-*.md")):
        if match := DOCUMENT.match(path.name):
            found[match.group("id")] = match.group("slug")
    return found


def _git(*args: str) -> str | None:
    """Git output, or None when git cannot answer - a shallow clone is not a failure."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def _branch_documents() -> dict[str, dict[str, str]] | None:
    """branch -> {id: slug} for every branch not yet merged into master, or None if git cannot."""
    listed = _git("branch", "--no-merged", "master", "--format=%(refname:short)")
    if listed is None:
        return None
    branches = [line.strip() for line in listed.splitlines() if line.strip()]
    per_branch: dict[str, dict[str, str]] = {}
    for branch in branches:
        tree = _git("ls-tree", "-r", "--name-only", branch, "--", "docs/prereg")
        if tree is None:
            continue
        found: dict[str, str] = {}
        for line in tree.splitlines():
            path = line.strip()
            # Directly under `docs/prereg/` only. `results/` holds `PR-001-report.md` and friends,
            # which are outputs of a study already indexed by its registration - reading them as
            # reservations makes every reported study collide with itself.
            if path.count("/") != 2:
                continue
            if match := DOCUMENT.match(Path(path).name):
                found[match.group("id")] = match.group("slug")
        per_branch[branch] = found
    return per_branch


def main() -> int:
    indexed = _indexed()
    documents = _documents()
    failures: list[str] = []

    for study_id in sorted(documents):
        if study_id not in indexed:
            failures.append(
                f"{study_id} has a document in docs/prereg/ and no row in docs/prereg/README.md"
            )

    referenced: dict[str, str] = {}
    for path in sorted(REPO.glob("docs/**/*.md")):
        relative = path.relative_to(REPO).as_posix()
        if relative.startswith(NOT_A_RESERVATION) or path == INDEX:
            continue
        for number in REFERENCE.findall(path.read_text(encoding="utf-8")):
            referenced.setdefault(f"PR-{number}", relative)
    for study_id, where in sorted(referenced.items()):
        if study_id not in indexed:
            failures.append(
                f"{study_id} is reserved by reference in {where} and is not listed in "
                f"docs/prereg/README.md - an unlisted reservation is a debt that stopped being "
                f"visible"
            )

    per_branch = _branch_documents()
    if per_branch is None:
        print("  cross-branch check DID NOT RUN: git could not list branches (a shallow clone "
              "has none). The two in-tree checks above did run.")
    else:
        slugs: dict[str, dict[str, list[str]]] = {}
        here = _git("rev-parse", "--abbrev-ref", "HEAD")
        for branch, found in [(here.strip() if here else "HEAD", documents), *per_branch.items()]:
            for study_id, slug in found.items():
                slugs.setdefault(study_id, {}).setdefault(slug, []).append(branch)
        for study_id, by_slug in sorted(slugs.items()):
            if len(by_slug) > 1:
                detail = "; ".join(
                    f"{slug} on {', '.join(sorted(set(where)))}" for slug, where in sorted(by_slug.items())
                )
                failures.append(f"{study_id} names two different studies across live branches: {detail}")
        print(f"  cross-branch check ran over {len(per_branch)} unmerged branch(es)")

    for failure in failures:
        print(f"  {failure}")
    print(f"\nprereg ids: {len(documents)} document(s), {len(indexed)} indexed, "
          f"{len(referenced)} referenced, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
