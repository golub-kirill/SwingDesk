"""Gate 30: a rule lives in `AGENTS.md`, and nowhere else.

**What paid for it, 2026-08-24.** The owner saw rule text being staged through a file outside the
repository and asked the right question: *"мы же записываем все правила в agents, правда? Чтобы
агенты, которые работают с этим кодом, не ошибались."* The answer was yes - checked, and every rule
was where it belongs. But nothing made it so. A second rules store is the same
one-logic-in-two-places failure that master ТЗ §8 forbids and that cost this repository a day on
2026-08-04, and it is worse for rules than for anything else: an agent reads `AGENTS.md` and would
never learn that a contradicting rule existed somewhere else.

**What this checks, and the distinction it rests on.** `AGENTS.md` §10.7 already splits habits from
open work: a rule is a habit and belongs in `AGENTS.md`; the WORK an instruction creates is an item
and belongs in `TODO.md`. So a heading declaring an owner instruction outside `AGENTS.md` is not
automatically wrong - it is wrong only when it does not point back at the rule. `TODO.md`'s audit
item names *"`AGENTS.md` §15 is the rule"* in its own heading, which is exactly the shape that keeps
the work trackable without forking the rulebook.

**Deliberately narrow.** It looks for headings that declare themselves an owner instruction, not for
imperative prose - a gate that tried to recognise "a rule" in English would fire on every
specification in the tree, and `CI_POLICY.md` §3 records what happens to a noisy gate.

    python tools/verify_rules_home.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: The one file rules live in.
HOME = "AGENTS.md"

#: A heading that declares itself an owner instruction. Matched on the heading line only.
DECLARES_RULE = re.compile(r"^#{1,4} .*owner instruction", re.IGNORECASE)

#: A pointer back at the rulebook: `AGENTS.md` §N, or "AGENTS.md section N".
POINTS_HOME = re.compile(r"AGENTS\.md`?\s*(?:§|section\s+)\d+(?:\.\d+)?", re.IGNORECASE)

#: The honest escape hatch, and the reason it exists.
#:
#: Not every owner instruction is a RULE. *"Cut this document in half"* is an editorial request
#: about one artefact: it creates work, it does not create a habit, and there is no section for it
#: to cite. Forcing a citation there would manufacture exactly the vacuous marker `AGENTS.md` §10.4
#: warns about - a marker that can be applied to anything is worse than a convention someone
#: follows.
#:
#: So the alternative is to SAY it is one-off. That cannot be written by accident: it is a claim
#: the author makes, and a wrong one is visible to any reader who knows the instruction recurred.
ONE_OFF = re.compile(r"\bone-off\b", re.IGNORECASE)


def _tracked_markdown() -> list[Path]:
    """Tracked `.md` files. Untracked scratch is not the repository's problem."""
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "*.md"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return sorted(REPO.rglob("*.md"))
    return [REPO / line for line in result.stdout.split() if line]


def check(paths: list[Path]) -> tuple[list[str], int]:
    """Failures, and how many declared instructions were seen in total."""
    failures: list[str] = []
    seen = 0
    for path in paths:
        try:
            body = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(REPO).as_posix()
        lines = body.splitlines()
        for number, line in enumerate(lines, 1):
            if not DECLARES_RULE.match(line):
                continue
            seen += 1
            if relative == HOME:
                continue
            # Outside the rulebook it must cite the section that holds the rule. The heading itself
            # or the paragraph under it - a pointer further away is one a reader will not follow.
            window = "\n".join(lines[number - 1: number + 12])
            if not POINTS_HOME.search(window) and not ONE_OFF.search(window):
                failures.append(
                    f"{relative}:{number}: declares an owner instruction and neither names the "
                    f"{HOME} section that carries the rule nor marks itself `one-off`. A rule lives "
                    f"in {HOME}; the WORK it creates lives in TODO.md and points back."
                )
    return failures, seen


def main() -> int:
    paths = _tracked_markdown()
    failures, seen = check(paths)
    for failure in failures:
        print(f"  {failure}")
    print(f"\nrules: {seen} declared owner instruction(s) across {len(paths)} document(s), "
          f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
