"""`TODO.md` holds open items, and only open items.

`AGENTS.md` section 10.7 has said so since it was written. On 2026-09-05 the file held **105 closed
items across 2,557 lines** - more than half of it - and nothing could see them, because the rule
was honour and the file is prose.

**Why a gate is defensible here and is not over prose.** `AGENTS.md` section 12's standard for a
check over text is an exact token, or it becomes the noise `CI_POLICY.md` section 3 describes. The
subject here is a five-character literal at the start of a line: `- [x] `. No English is
interpreted, no judgement is made, and the false-positive rate is structurally zero - a line either
starts with that or it does not.

**What paid for it.** `TODO.md` went from 198 lines on 2026-08-15 to 4,653 on 2026-09-05, growing
about 330 lines a day, and 57% of it was finished work. The cost is not disk: it is that a fresh
session's first read of the open-work list is mostly not open work, which is the exact thing
section 10.7 was written to prevent.

**Where a closed item goes** is `docs/08-pm/TODO_CLOSED.md`, and the discipline that comes with it
is that the lesson is promoted first - to section 12's traps, to a decision record, or to a gate -
and only then does the entry move. A lesson that is only "this specific thing was fixed" is not
promoted, because git holds it.

Stdlib only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
TODO = REPO / "TODO.md"

#: The exact token. A checklist line that is ticked.
CLOSED = "- [x] "

#: Where they go, named here so the failure message can say it.
CLOSED_DOC = "docs/08-pm/TODO_CLOSED.md"


def closed_items(text: str) -> list[tuple[int, str]]:
    """Every ticked checklist line, with its line number."""
    return [
        (number, line[len(CLOSED):].strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if line.startswith(CLOSED)
    ]


def main() -> int:
    if not TODO.exists():
        print(f"open work: UNAVAILABLE - no {TODO.name} in this checkout")
        return 0

    text = TODO.read_text(encoding="utf-8")
    found = closed_items(text)
    if not found:
        total = sum(1 for line in text.splitlines() if line.startswith("- [ ] "))
        print(f"open work: PASS - {TODO.name} carries {total} open item(s) and nothing closed")
        return 0

    print(f"{len(found)} closed item(s) in {TODO.name}, which holds open items and only open items "
          f"(AGENTS.md 10.7):")
    for number, title in found[:20]:
        clean = title.replace("**", "").replace("`", "")
        print(f"   {TODO.name}:{number}  {clean[:96]}")
    if len(found) > 20:
        print(f"   ... and {len(found) - 20} more")
    print()
    print("Promote the lesson first - to AGENTS.md section 12, to a decision record, or to a gate -")
    print(f"then move the entry to {CLOSED_DOC}. A lesson that is only \"this specific thing was")
    print("fixed\" is not promoted; git holds it.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
