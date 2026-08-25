"""Gate 7: the pure packages read no wall clock, and executable code holds no date literal.

Two rules with one mechanism, and both are AST-parsed rather than string-matched - a mention in a
docstring or a comment must not trip a gate, because a gate with false positives gets bypassed and a
bypassed gate teaches that red is normal (`CI_POLICY.md` section 3).

**The wall clock.** `AGENTS.md` section 5: *"Time is injected into domain code. `datetime.now()` in
`derived_observations`, `decision_logic` or `trade_management` is a defect."* A pure package that
reads the clock cannot be replayed, and `DETERMINISM_SPEC.md` section 3.1 is what that breaks.

**The date literal.** `REQUIREMENTS.md` `REQ-DATA-001` is unconditional: *"No event date may appear
as a literal in executable code."* Its status cell read *"no date literals in `src/` (verified)"* -
verified once, by hand, on a MUST with no mechanism. Measured 2026-08-25: still zero. This is the
mechanism, and it is prevention rather than repair. A hard-coded earnings date is exactly what
arrives under time pressure, and it would make a point-in-time claim false in a way no test would
notice.

**Why this is a file rather than a function.** It lived inside `check_gates.py` until 2026-08-25,
which made it the one gate of this repository's own making that could not be pointed at a fixture -
so it had no failure test, and `TODO.md`'s audit of gates never proven able to fail could not see
it: that audit derived its list by grepping `tests/` for each `tools/verify_*.py`, and gate 7 had no
tool file to grep for.

    python tools/verify_no_wall_clock.py
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: Packages that must stay pure: no I/O, no journal, and above all no wall clock
#: (`DETERMINISM_SPEC.md` section 3.1, `ARCHITECTURE.md` section 3).
PURE_PACKAGES = ("derived_observations", "decision_logic", "trade_management")

FORBIDDEN_CALLS = {("datetime", "now"), ("datetime", "utcnow"), ("date", "today"), ("time", "time")}

#: Constructors that build a fixed point in time. A call with all-constant arguments is a literal
#: date however it is spelled; one with a name or an expression in it is computed from something.
DATE_CONSTRUCTORS = {"date", "datetime"}

#: `2026-08-25` and `20260825` as string constants. The second form is included because a compact
#: date is still a date, and it is the form a filename or an API parameter takes.
_ISO_LENGTHS = (10, 8)


def _is_date_string(value: str) -> bool:
    if len(value) not in _ISO_LENGTHS:
        return False
    if len(value) == 10:
        return (value[4] == value[7] == "-" and value[:4].isdigit()
                and value[5:7].isdigit() and value[8:].isdigit())
    return value.isdigit() and "1900" <= value[:4] <= "2199"


def _date_literals(tree: ast.AST) -> list[tuple[int, str]]:
    """Every fixed date built or written in this module, with its line."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else ""
            )
            if (name in DATE_CONSTRUCTORS and len(node.args) >= 3
                    and all(isinstance(arg, ast.Constant) for arg in node.args)):
                rendered = ", ".join(
                    str(arg.value) for arg in node.args if isinstance(arg, ast.Constant)
                )
                found.append((node.lineno, f"{name}({rendered})"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _is_date_string(node.value):
                found.append((node.lineno, repr(node.value)))
    return found


def _modules(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py")) if root.is_dir() else []


def main() -> int:
    clock: list[str] = []
    packages = 0
    for package in PURE_PACKAGES:
        root = REPO / "src" / "swingdesk" / package
        if not root.is_dir():
            continue
        packages += 1
        for path in _modules(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                owner = node.func.value
                if isinstance(owner, ast.Name) and (owner.id, node.func.attr) in FORBIDDEN_CALLS:
                    clock.append(
                        f"{path.relative_to(REPO).as_posix()}:{node.lineno}: "
                        f"{owner.id}.{node.func.attr}()"
                    )

    dates: list[str] = []
    modules = 0
    for path in _modules(REPO / "src"):
        modules += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for line, rendered in _date_literals(tree):
            dates.append(f"{path.relative_to(REPO).as_posix()}:{line}: {rendered}")

    for offender in clock:
        print(f"  wall clock: {offender}")
    for offender in dates:
        print(f"  date literal: {offender}")
    if clock:
        print(
            "\n  A pure package that reads the clock cannot be replayed. Inject the time -"
            "\n  AGENTS.md section 5, DETERMINISM_SPEC.md section 3.1."
        )
    if dates:
        print(
            "\n  REQ-DATA-001: no event date may appear as a literal in executable code. A"
            "\n  hard-coded date makes a point-in-time claim false in a way no test notices."
            "\n  Read it from the calendar, the store or a parameter."
        )
    print(
        f"\nno wall clock: {packages} pure package(s), {len(clock)} clock read(s); "
        f"{modules} module(s) under src, {len(dates)} date literal(s)"
    )
    return 1 if clock or dates else 0


if __name__ == "__main__":
    raise SystemExit(main())
