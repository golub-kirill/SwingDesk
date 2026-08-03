"""Run every merge gate, fastest first (CI_POLICY 1).

One command, and the CI definition calls this same script - if a local run and CI can disagree, the
local run stops being trusted and the feedback loop lengthens to a push.

A gate that is wrong gets fixed or removed, never skipped. There is deliberately no --skip flag.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Packages that must stay pure: no I/O, no journal, and above all no wall clock
#: (DETERMINISM_SPEC 3.1, ARCHITECTURE 3).
PURE_PACKAGES = ("derived_observations", "decision_logic", "trade_management")
FORBIDDEN_CALLS = {("datetime", "now"), ("datetime", "utcnow"), ("date", "today"), ("time", "time")}


def _run(name: str, argv: list[str]) -> bool:
    print(f"\n=== {name}")
    result = subprocess.run(argv, cwd=REPO)
    ok = result.returncode == 0
    print(f"--- {name}: {'PASS' if ok else 'FAIL'}")
    return ok


def check_no_wall_clock() -> bool:
    """Grep the pure packages for wall-clock calls.

    Parsed rather than string-matched, so a mention in a docstring or a comment does not trip it -
    a gate with false positives gets bypassed, and a bypassed gate teaches that red is normal.
    """
    print("\n=== no wall clock in pure packages")
    offenders: list[str] = []
    for package in PURE_PACKAGES:
        root = REPO / "src" / "swingdesk" / package
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                owner = node.func.value
                if isinstance(owner, ast.Name) and (owner.id, node.func.attr) in FORBIDDEN_CALLS:
                    offenders.append(
                        f"{path.relative_to(REPO)}:{node.lineno}: {owner.id}.{node.func.attr}()"
                    )
    for offender in offenders:
        print(f"  {offender}")
    ok = not offenders
    print(f"--- no wall clock: {'PASS' if ok else 'FAIL'} "
          f"({len(PURE_PACKAGES)} packages checked)")
    return ok


def main() -> int:
    python = sys.executable
    results = {
        "parameters": _run("parameter registry contract",
                           [python, "tools/verify_parameters.py"]),
        "transcription": _run("verbatim transcription + enums",
                              [python, "tools/verify_transcription.py"]),
        "course index": _run("course index shape",
                             [python, "tools/build_course_index.py", "--check-only"]),
        "frd": _run("FRD current", [python, "tools/build_frd.py", "--check-only"]),
        "checklists current": _run("checklist registry current",
                                   [python, "tools/build_checklists.py", "--check-only"]),
        "components current": _run("component registry current",
                                   [python, "tools/build_components.py", "--check-only"]),
        "component contract": _run("component registry contract",
                                   [python, "tools/verify_components.py"]),
        "import contracts": _run("import-linter architecture contracts",
                                 [python, "-m", "importlinter.cli", "lint-imports"]),
        "no wall clock": check_no_wall_clock(),
        "golden vectors": _run("golden vectors", [python, "tools/golden.py"]),
        "tests": _run("pytest", [python, "-m", "pytest", "tests/", "-q"]),
        "determinism replay": _run("determinism replay", [python, "tools/replay.py"]),
    }

    print("\n" + "=" * 62)
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [name for name, ok in results.items() if not ok]
    print("=" * 62)
    if failed:
        print(f"{len(failed)} gate(s) failed: {', '.join(failed)}")
        return 1
    print("all gates pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
