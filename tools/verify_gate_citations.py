"""Gate 38: a document citing a gate number cites one the inventory knows about.

**What paid for it.** `CI_POLICY.md` row **12** read `exists` for seventeen days over a number
`check_gates.py` has never registered. Gate 36 was written out of that and closes the two places a
gate is DEFINED - the inventory and the runner. It does not reach the ~130 tracked documents that
CITE a gate number, and those are where a reader actually meets one. A sentence saying *"gate 12
catches this"* is read as protection, and nothing could tell it from a sentence naming a real gate.

**The vocabulary is the inventory, not the runner**, and that distinction is the whole design. A
gate may honestly be cited before it exists: `CI_POLICY.md` row **10** says `to build` and about
twenty documents refer to gate 10 as the linkage that is missing. Every one of those sentences is
true, and a check that reddened on them would be demanding that a document stop naming the thing it
is waiting for. So a citation resolves when the inventory carries the number **in any state** -
registered, `to build`, or struck through as retired. What it may never do is name a number the
inventory has never heard of.

**Measured before it was written, over every tracked `.md`:** 365 gate citations, and after the two
exclusions below **zero** unresolved. So this is prevention, like gate 35, and it costs nothing
while the answer stays zero.

**Two exclusions, each from a real false positive in that measurement.**

1. **A four-digit number is a year, not a gate.** *"FIXED AT THE GATE 2026-08-24"* parsed as gate
   2026. No gate id is that long and none plausibly will be.
2. **A number followed by `-` is a date.** Same instance from the other side, kept because either
   alone would have let it through.

**What it deliberately does not check:** whether the citing sentence DESCRIBES the gate correctly.
That is prose against behaviour, and gate 36's row already records why that line is not crossed.

    python tools/verify_gate_citations.py
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
RUNNER = REPO / "tools" / "check_gates.py"
INVENTORY = REPO / "docs" / "06-engineering" / "CI_POLICY.md"

#: `gate 3g`, `gates 28 and 29`. The id is short by construction - see exclusion 1 - and a trailing
#: `-` is refused so a date cannot be read as one.
CITATION = re.compile(r"\bgates?\s+(\d{1,3}[a-z]{0,2})\b(?!-)", re.IGNORECASE)

#: A row in the inventory table, whatever state it claims. `| 3g | ...` and `| ~~12~~ | ...` both
#: count: the point is that the number is KNOWN, not that its gate runs.
ROW = re.compile(r"^\|\s*~*\s*(\d{1,3}[a-z]{0,2})\s*~*\s*\|")


def registered_ids() -> set[str]:
    """Every gate id `check_gates.py` registers, read from its syntax tree rather than imported."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [key.value for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)]
        # The results mapping is the only large dict whose every key is `<id> <name>`.
        if len(keys) > 5 and all(" " in key for key in keys):
            return {key.split()[0] for key in keys}
    return set()


def inventory_ids() -> set[str]:
    """Every gate number the inventory table carries, in any state."""
    found: set[str] = set()
    for line in INVENTORY.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            found.add(match.group(1))
    return found


def tracked_documents() -> list[Path]:
    """Every tracked markdown file. `git ls-files` rather than a glob, so an untracked scratch note
    cannot fail the build for anyone."""
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "*.md"],
        capture_output=True, encoding="utf-8", errors="replace", check=False,
    )
    return [REPO / name for name in result.stdout.split() if (REPO / name).is_file()]


def main() -> int:
    known = registered_ids() | inventory_ids()
    if not known:
        # A gate that cannot see its subject says so rather than passing (`AGENTS.md` §10.6 rule 2).
        print("gate citations: UNAVAILABLE - neither the runner nor the inventory could be read")
        return 4

    failures: list[str] = []
    citations = 0
    for path in tracked_documents():
        relative = path.relative_to(REPO).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in CITATION.finditer(line):
                identifier = match.group(1)
                citations += 1
                if identifier not in known:
                    failures.append(
                        f"{relative}:{number} cites gate {identifier}, which neither "
                        f"check_gates.py registers nor CI_POLICY.md lists. A gate number a reader "
                        f"meets in prose is read as protection"
                    )

    for failure in failures:
        print(f"  {failure}")
    print(f"\ngate citations: {citations} across {len(tracked_documents())} document(s), "
          f"{len(known)} known gate number(s), {len(failures)} unresolved")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
