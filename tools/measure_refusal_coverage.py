"""Which refusals and decisions has the test suite never seen the system produce?

**Not a merge gate, and the reason is runtime rather than principle.** It runs the whole suite under
a tracer - about three minutes - and gate 8 already runs the suite once. Doubling that at the front
of every merge buys a number that changes rarely, and `CI_POLICY.md` section 1 orders the gates
fastest-first for a reason. It is a deliberate check, the same standing as
`tools/verify_reproducible.py`, and it exits non-zero on an unexecuted site so it could become a
gate later without changing meaning.

**What it measures.** Every `Refusal(...)` and `DecisionRecord(...)` CONSTRUCTION in `src/` - found
by parsing, so a type annotation, an `isinstance` check or a docstring mention is not one - and
whether the suite ever executes it.

**Why it is worth measuring.** A fail-closed refusal nobody has seen fire is a refusal nobody knows
fires, which is the whole subject of `FAIL_CLOSED_POLICY.md`, and `REQ-VALIDATION-001` asks the same
question about every gate, veto and filter. Measured 2026-08-25 on its first run: **18 of 27 refusal
sites executed, and 15 of 17 decision sites.** The nine unexecuted refusals were missing tests rather
than missing guards - five of them in `trade_management/sizing.py`, the most safety-critical file in
the tree - and the two unexecuted decisions were defensive branches, one of which said so and one of
which did not.

**What it does NOT establish.** That a site is exercised for the right REASON. A line executed is not
a branch asserted, and those are the same distance apart as gate 8 and gate 34.

**No new dependency.** `coverage` is not declared here and adding one to answer this would be the
wrong trade against gates 17 and 18; `sys.settrace`, scoped to the files that have sites, is enough
and is stdlib.

    PYTHONPATH=$PWD/src python tools/measure_refusal_coverage.py
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from types import FrameType
from typing import Any

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: The constructions worth counting. Both are how this system says no - one to a candidate, one to
#: an operation - and both are supposed to be unreachable-until-they-are-not.
CONSTRUCTORS = ("Refusal", "DecisionRecord")


#: How far above a site a comment may sit and still be about it.
DECLARATION_WINDOW = 14


def _declared_unreachable(lines: list[str], first: int) -> bool:
    """Does a comment just above this site say the branch cannot be reached?

    The tool's own message asks for exactly this - *"record beside it why it cannot be reached"* -
    so honouring the declaration is what stops the check being permanently red over branches that
    are defensive by design. It is deliberately a COMMENT rather than a registry: the reason has to
    be readable by whoever next wonders why the branch is there, and a file that says
    *"unreachable while `size_long` refuses the same instrument for the same reason"* has already
    said the useful part.
    """
    start = max(0, first - 1 - DECLARATION_WINDOW)
    for line in lines[start:first - 1]:
        stripped = line.strip()
        if stripped.startswith("#") and "unreachable" in stripped.lower():
            return True
    return False


def _sites(path: Path) -> dict[int, tuple[int, str, bool]]:
    """First line -> (last line, source, declared-unreachable) for every construction here."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    found: dict[int, tuple[int, str, bool]] = {}
    for node in ast.walk(ast.parse(text, filename=str(path))):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else ""
        if name not in CONSTRUCTORS:
            continue
        end = node.end_lineno or node.lineno
        found[node.lineno] = (
            end, lines[node.lineno - 1].strip(), _declared_unreachable(lines, node.lineno)
        )
    return found


def main() -> int:
    src = REPO / "src"
    targets: dict[str, dict[int, tuple[int, str, bool]]] = {}
    for path in sorted(src.rglob("*.py")):
        sites = _sites(path)
        if sites:
            targets[str(path.resolve())] = sites
    if not targets:
        print("  no refusal or decision construction found under src/")
        return 0

    executed: dict[str, set[int]] = {name: set() for name in targets}

    def local_trace(frame: FrameType, event: str, _arg: Any) -> Any:
        if event == "line":
            executed[frame.f_code.co_filename].add(frame.f_lineno)
        return local_trace

    def global_trace(frame: FrameType, event: str, _arg: Any) -> Any:
        if event == "call" and frame.f_code.co_filename in executed:
            return local_trace
        return None

    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(src))
    os.chdir(REPO)
    import pytest

    sys.settrace(global_trace)
    try:
        outcome = pytest.main(["tests/", "-q", "-p", "no:cacheprovider", "--no-header"])
    finally:
        sys.settrace(None)
    if outcome != 0:
        print(f"\n  the suite did not pass (pytest exit {outcome}); coverage below is not a claim")
        return 1

    total = missed = declared = 0
    print("")
    for name, sites in sorted(targets.items()):
        hit = executed[name]
        never = sorted(
            first for first, (last, _source, _declared) in sites.items()
            if not any(line in hit for line in range(first, last + 1))
        )
        total += len(sites)
        label = Path(name).relative_to(src).as_posix()
        print(f"  {len(sites) - len(never):>3}/{len(sites):<3} {label}")
        for first in never:
            _last, source, is_declared = sites[first]
            if is_declared:
                declared += 1
                print(f"        declared unreachable  {label}:{first}: {source[:80]}")
            else:
                missed += 1
                print(f"        NEVER  {label}:{first}: {source[:96]}")

    print(
        f"\nrefusal coverage: {total} site(s), {total - missed - declared} executed, "
        f"{declared} declared unreachable, {missed} never"
    )
    if missed:
        print(
            "\n  A refusal nobody has seen fire is a refusal nobody knows fires. Either write the"
            "\n  test that reaches it, or put a comment above it saying why it cannot be reached -"
            "\n  a defensive branch that says so is not the same as a gap, and this check reads"
            "\n  that comment."
        )
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
