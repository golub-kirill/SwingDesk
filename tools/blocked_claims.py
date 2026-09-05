"""The open items in `TODO.md` that assert something is blocked, and therefore need testing.

**Not a gate. A worklist**, and it exists because the claims it lists are wrong at a rate nothing
else in this repository comes close to: four of seven impossibility claims on 2026-08-25, three of
the eight entries opened on the evening of 2026-09-04, three of five picked at random the day after.
`AGENTS.md` §15 is the rule those measurements produced - an impossibility is a claim, and the one
kind this repository does not check.

**It finds sentences, not truth**, and that is the whole of what it promises. A hit is an item whose
text says something is blocked, missing, unwired or impossible; whether it still IS is the question
the reader then has to answer with a command. A miss is not evidence of anything - the vocabulary is
open and prose is not parseable, which is why this is a worklist rather than a gate
(`CI_POLICY.md` §3: a gate over prose needs an exact token or it becomes noise).

    python tools/blocked_claims.py            # the census
    python tools/blocked_claims.py --list     # with each item's first line, to work through

Stdlib only.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: An open checklist item. Closed ones are history and are not re-tested.
OPEN_ITEM = re.compile(r"^- \[ \] ")

#: The vocabulary a blocking claim is written in here, gathered from the entries that turned out to
#: be false rather than invented. Deliberately broad: this is a worklist, so a false positive costs
#: one re-read and a miss costs a stale claim nobody looks at again.
BLOCKING = re.compile(
    r"blocked on|blocked behind|not wired|no source|does not exist|cannot |can never|never been|"
    r"read by nothing|reaches no code|unwired|no free|is missing|needs the owner|awaiting the owner|"
    r"impossible|not available|no way to",
    re.IGNORECASE,
)


def items(text: str) -> list[tuple[int, str, bool]]:
    """Every open item as (line number, first line, carries a blocking claim)."""
    lines = text.splitlines()
    starts = [n for n, line in enumerate(lines) if OPEN_ITEM.match(line)]
    found: list[tuple[int, str, bool]] = []
    for index, start in enumerate(starts):
        # An item runs to the next item or the next heading, whichever comes first - so a claim in
        # the item BELOW is never counted against this one.
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        for cursor in range(start + 1, end):
            if lines[cursor].startswith("#"):
                end = cursor
                break
        body = "\n".join(lines[start:end])
        headline = re.sub(r"[*`~]", "", lines[start][6:]).strip()
        found.append((start + 1, headline, bool(BLOCKING.search(body))))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(prog="blocked_claims")
    parser.add_argument("--list", action="store_true",
                        help="print each item's line number and first line, to work through")
    parser.add_argument("--todo", type=Path, default=REPO / "TODO.md")
    args = parser.parse_args()

    try:
        text = args.todo.read_text(encoding="utf-8")
    except OSError as unreadable:
        print(f"blocked claims: could not read {args.todo}: {unreadable}", file=sys.stderr)
        return 2

    found = items(text)
    blocking = [(number, headline) for number, headline, is_blocking in found if is_blocking]

    if args.list:
        for number, headline in blocking:
            print(f"  TODO.md:{number}  {headline[:104]}")

    print(f"\nblocked claims: {len(blocking)} of {len(found)} open item(s) assert something is "
          f"blocked, missing or impossible")
    print("  Each is a SENTENCE, not a verdict. Test it against the tree, the stores or the source "
          "before believing it (AGENTS.md 15).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
