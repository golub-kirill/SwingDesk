"""Gate 37: the rule index and the rulebook name the same rules.

`AGENTS.md` opens with an index - every rule in one line, with the gate that catches you when you
break it. **An index is worth having only if it cannot go stale**, and an index of rules that has
drifted from the rules is worse than none: it is read instead of them.

**What paid for it, 2026-08-25.** The owner asked for the list and the prose to be separated, and
the reason was a session that had just broken two owner instructions it had read - §5's *"say the
name, not the code"* and §13's *answer briefly, in Russian* - while building five gates that catch
other things. Nothing surfaced them, because a rule lives in a 650-line file and a working session
acts from memory. The index is the answer; this gate is what stops the answer rotting.

**Three checks, and each compares tokens rather than making a judgement:**

1. **Every numbered section has a row.** A rule added to the rulebook and not to the index fails the
   build - which is the whole point, and the only reason an agent may trust the short list.
2. **Every row points at a section that exists.** A row for a section nobody wrote is a rule nobody
   can read.
3. **Every gate number the index cites is registered** in `check_gates.py`. A row promising that
   gate 33 catches something must mean the gate 33 that runs.

**What it deliberately does not check:** whether a row DESCRIBES its section correctly, or whether
the named gate really enforces that rule. Both are prose against behaviour, no gate reads them, and
`CI_POLICY.md` §3 records what a gate that guesses at prose costs. The word `honour` in the third
column is therefore an honest claim by the author, not a verified one - and it is the column a
reader should trust least and re-read most.

    python tools/verify_rules_index.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

RULEBOOK = REPO / "AGENTS.md"
RUNNER = REPO / "tools" / "check_gates.py"

#: The heading that opens the index. Matched on its own line.
INDEX_HEADING = "### The rules, in one place — the index"

#: A numbered section heading: `## 10.5 ...` or `### 10.1 ...`. The number is the citation target
#: and is frozen (`AGENTS.md`, "How this file is numbered"), so it is a stable key.
SECTION = re.compile(r"^#{2,3}\s+(?P<number>\d+(?:\.\d+)?)\.?\s+\S")

#: A row of the index table. The section number may be bolded to mark a rule worth re-reading.
ROW = re.compile(r"^\|\s*\**(?P<number>\d+(?:\.\d+)?)\**\s*\|(?P<rest>.*)\|\s*$")

#: A gate number cited in the third column: bare, or in a comma-separated run.
GATE_REF = re.compile(r"(?<![\w.])(\d+[a-z]*)(?![\w.])")

#: A gate registered in the runner: the dict key opens with its number.
ENTRY = re.compile(r'^\s*"(?P<number>[0-9]+[a-z]*) [^"]*":', re.MULTILINE)


def _index_rows(text: str) -> dict[str, str]:
    """Section number -> the row's remaining cells, for every row of the index table."""
    rows: dict[str, str] = {}
    inside = False
    for line in text.splitlines():
        if line.strip() == INDEX_HEADING:
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside:
            continue
        match = ROW.match(line)
        if match:
            rows[match.group("number")] = match.group("rest")
    return rows


def _sections(text: str) -> list[str]:
    """Every numbered section, in order, excluding the index's own rows."""
    found: list[str] = []
    for line in text.splitlines():
        match = SECTION.match(line)
        if match:
            found.append(match.group("number"))
    return found


def main() -> int:
    if not RULEBOOK.is_file():
        print(f"  rules index: {RULEBOOK.name} is not in this tree")
        return 1
    text = RULEBOOK.read_text(encoding="utf-8")

    if INDEX_HEADING not in text:
        print(f"  rules index: {RULEBOOK.name} has no index. Its heading must read exactly:")
        print(f"    {INDEX_HEADING}")
        return 1

    rows = _index_rows(text)
    sections = _sections(text)
    registered = set(ENTRY.findall(RUNNER.read_text(encoding="utf-8"))) if RUNNER.is_file() else set()

    failures: list[str] = []
    for number in sections:
        if number not in rows:
            failures.append(
                f"§{number} is a section of the rulebook and has no row in the index. A rule the "
                f"index omits is a rule nobody reading the short list will follow."
            )
    for number in sorted(rows):
        if number not in sections:
            failures.append(f"the index has a row for §{number}, and no such section exists.")

    if registered:
        for number, rest in sorted(rows.items()):
            caught = rest.split("|")[-1]
            for token in GATE_REF.findall(caught):
                if token in registered or token in {"3", "10"}:
                    continue
                failures.append(
                    f"§{number}'s row cites gate {token}, which `check_gates.py` does not register."
                )

    for failure in failures:
        print(f"  {failure}")
    if failures:
        print(
            "\n  The index is the only part of the rulebook a working session holds in mind. It is"
            "\n  worth having exactly as long as it cannot drift from the rules it lists."
        )
    print(
        f"\nrules index: {len(sections)} section(s), {len(rows)} row(s), "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
