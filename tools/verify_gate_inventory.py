"""Gate 36: the gate inventory and the gate runner name the same gates.

`CI_POLICY.md` section 1 calls itself the inventory, and section 1's own text says so: *"the table
above is the inventory, and the count belongs to `HANDOFF.md` section 2"*. A reader learning what
this project checks reads that table; `check_gates.py` is what actually runs.

**They disagreed for seventeen days and nothing could see it.** Row 12 pointed at
`verify_criteria.py` and read **exists**; `check_gates.py` has never registered a 12. The 2026-08-09
reconciliation had already found *three* things claiming that number, resolved it to 3e and 3g, and
corrected both tool docstrings - and left the policy row, which then went on asserting a gate that
does not run. Three sites of four, and the one missed was the inventory.

**Three checks, and each is exact** - a gate number is a token, not a judgement:

1. Every gate registered in `check_gates.py` has a row.
2. Every row that claims to exist is registered. A row marked `to build`, or struck through, claims
   nothing and is left alone - which is how row 10 has been honest about itself all along.
3. No number is claimed by two rows.

**What it deliberately does not check:** whether the row DESCRIBES the gate correctly. That is prose
against behaviour and no gate can read it; what this closes is the case where the two disagree about
a gate's existence, which is a token comparison and was the actual failure.

    python tools/verify_gate_inventory.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

POLICY = REPO / "docs" / "06-engineering" / "CI_POLICY.md"
RUNNER = REPO / "tools" / "check_gates.py"

#: A row of the inventory table. The number may be struck through, which is how a retired row says
#: so. `3ci` and `7b` are gate numbers here, so the token is not just digits.
ROW = re.compile(r"^\|\s*(?P<strike>~~)?(?P<number>[0-9]+[a-z]*)~*\s*\|(?P<rest>.*)$")

#: A gate registered in the runner: the dict key opens with its number.
ENTRY = re.compile(r'^\s*"(?P<number>[0-9]+[a-z]*) [^"]*":', re.MULTILINE)

#: A row that claims nothing. `to build` is the honest form and predates this gate.
UNCLAIMED = re.compile(r"\bto build\b|RETIRED|~~exists~~", re.IGNORECASE)


def _inventory() -> tuple[dict[str, bool], list[str]]:
    """number -> claims-to-exist, plus any number claimed twice."""
    rows: dict[str, bool] = {}
    duplicates: list[str] = []
    inside = False
    for line in POLICY.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 1."):
            inside = True
            continue
        if inside and line.startswith("## ") and not line.startswith("## 1."):
            break
        if not inside:
            continue
        match = ROW.match(line)
        if not match or match.group("number") in {"", "#"}:
            continue
        number = match.group("number")
        claims = not (match.group("strike") or UNCLAIMED.search(match.group("rest")))
        if number in rows:
            duplicates.append(number)
        rows[number] = claims
    return rows, duplicates


def main() -> int:
    if not POLICY.is_file() or not RUNNER.is_file():
        print(f"  gate inventory: {POLICY.name} or {RUNNER.name} is not in this tree")
        return 1

    rows, duplicates = _inventory()
    registered = set(ENTRY.findall(RUNNER.read_text(encoding="utf-8")))

    failures: list[str] = []
    for number in sorted(registered - set(rows)):
        failures.append(
            f"gate {number} runs and has no row in CI_POLICY section 1. The inventory is what a "
            f"reader counts gates from."
        )
    for number, claims in sorted(rows.items()):
        if claims and number not in registered:
            failures.append(
                f"gate {number} is listed as existing and `check_gates.py` does not register it. "
                f"Register it, or mark the row `to build` the way row 10 does."
            )
    for number in sorted(set(duplicates)):
        failures.append(f"gate {number} is claimed by two rows of the inventory.")

    for failure in failures:
        print(f"  {failure}")
    print(
        f"\ngate inventory: {len(rows)} row(s), {len(registered)} registered, "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
