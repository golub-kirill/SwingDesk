"""Gate 14: every hard-coded count in the documentation matches what the tree actually holds.

`HANDOFF.md` §7 states the habit this implements: *when you find that class of defect, add a gate
rather than fixing the instance.* Hard-coded counts have now been reconciled by hand three times -
commit `0bd503f`, then twice on 2026-08-05 - and each pass found stale numbers the previous careful
read had left behind. A number that is right on the day it is written and wrong a week later does
not look like a defect, which is exactly why a person does not catch it.

Counts are derived from the registries, the filesystem and the gate list, never from another
document. Where a count cannot be derived cheaply it is not checked, and that is stated rather than
guessed at: the test total comes from pytest collection because parametrised cases mean the number
of `def test_` lines (228) is not the number of tests (260).

Needs PyYAML and pytest, so it runs with the project venv like most of the suite.

    python tools/verify_counts.py
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

#: Root of the tree being checked. Overridable so a test can point the gate at a fixture and
#: assert it goes red - a gate nobody has seen fail is a gate nobody has tested. Never set in
#: normal use; `check_gates.py` does not set it.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
DOCS = REPO / "docs"
ROOT_DOCS = ("README.md", "AGENTS.md", "HANDOFF.md")


def _load_yaml(path: Path):
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _gate_count() -> int:
    """Entries in `check_gates.py`'s results mapping - the gates that actually run.

    Parsed rather than imported, because importing it would execute the suite.
    """
    tree = ast.parse((REPO / "tools" / "check_gates.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and node.keys and all(
            isinstance(k, ast.Constant) and isinstance(k.value, str) for k in node.keys
        ):
            return len(node.keys)
    raise LookupError("could not find the results mapping in check_gates.py")


def _test_count() -> int | None:
    """Collected tests, or None when pytest is unavailable. Parametrised cases make the
    `def test_` line count wrong, so nothing cheaper is correct."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--collect-only"],
        cwd=REPO, capture_output=True, text=True,
    )
    match = re.search(r"(\d+) tests? collected", result.stdout)
    return int(match.group(1)) if match else None


def measure() -> dict[str, int]:
    """Everything this gate knows how to derive."""
    parameters = _load_yaml(REPO / "registry" / "parameters.yml")["parameters"]
    components = _load_yaml(REPO / "registry" / "components.yml")["components"]

    counts: dict[str, int] = {
        "parameters": len(parameters),
        "components": len(components),
        "documents": len(list(DOCS.rglob("*.md"))),
        "gates": _gate_count(),
        "golden vectors": len(list((REPO / "golden" / "components").rglob("*/*.json"))),
        "golden components": len([p for p in (REPO / "golden" / "components").iterdir()
                                  if p.is_dir()]),
    }
    for status in ("unset", "assumed", "owner", "validated"):
        counts[f"parameters:{status}"] = sum(1 for p in parameters if p.get("status") == status)
    for state in ("registered", "specified", "active"):
        counts[f"components:{state}"] = sum(1 for c in components if c.get("activation") == state)

    tests = _test_count()
    if tests is not None:
        counts["tests"] = tests
    return counts


#: (pattern, count key, guard). The guard is a word that must appear on the same line for the match
#: to be about that quantity - "465 registered" is a component census only where components are
#: under discussion. Patterns are deliberately narrow; a noisy gate gets bypassed (CI_POLICY 3).
#: `§` and `~` are in the lookbehind for real reasons found on the first run: "§4 tests whether"
#: parsed as a test count, and "~460 registered components" is an approximation the author meant.
_LEAD = r"(?<![-\w.§~])"

CHECKS: tuple[tuple[str, str, str | None], ...] = (
    # The bare "N parameters" form is deliberately NOT checked: "9 parameters carry assumed values"
    # is a true statement about the assumed subset, and a pattern that cannot tell it from a total
    # produces exactly the noise that gets a gate bypassed. The backticked status forms below are
    # unambiguous, and a census line carries them anyway.
    (_LEAD + r"(\d+)\s+`unset`", "parameters:unset", None),
    (_LEAD + r"(\d+)\s+`assumed`", "parameters:assumed", None),
    (_LEAD + r"(\d+)\s+`owner`", "parameters:owner", None),
    (_LEAD + r"(\d+)\s+`validated`", "parameters:validated", None),
    (_LEAD + r"(\d+)\s+registered\b", "components:registered", "component"),
    (_LEAD + r"(\d+)\s+`specified`", "components:specified", None),
    (_LEAD + r"(\d+)\s+`active`", "components:active", None),
    (_LEAD + r"(\d+)\s+(?:merge\s+)?gates\b", "gates", None),
    (_LEAD + r"(\d+)\s+tests\b", "tests", None),
    (_LEAD + r"(\d+)\s+vectors\b", "golden vectors", None),
    # The state tables in HANDOFF.md put the label first: "| Merge gates | **16**, one command".
    # Missed on the first run, which is why the form is covered explicitly.
    (r"Merge gates\s*\|\s*\*\*(\d+)\*\*", "gates", None),
    (r"Tests\s*\|\s*\*\*(\d+)\*\*", "tests", None),
    (r"\|\s*Docs\s*\|\s*(\d+)\s+files", "documents", None),
)

#: A line recording what was true on a date, or a struck-through completed item. These are history
#: and must NOT be rewritten to match today - a roadmap entry saying "DONE 2026-08-03, 14 gates" is
#: a correct statement about 2026-08-03. Updating it would falsify the record.
HISTORICAL = re.compile(r"~~|\b(DONE|CLOSED|REACHED)\s+20\d\d-\d\d-\d\d")

#: Statements that legitimately use one of these numbers for something else. Each is a decision.
ALLOWED: set[tuple[str, str]] = set()

#: The single owner of a measured count, and the section of it that owns them (owner decision,
#: 2026-08-10). Every other document names the source instead of the number.
#:
#: The rule exists because correctness was never the problem. These counts have been *correct* in
#: five documents and wrong in a sixth, repeatedly - the drift is a property of keeping six copies,
#: not of anyone being careless. ROADMAP section 1 was a second dashboard that reached "18 merge
#: gates" and "253 tests" against a tree carrying 24 and 320, and most of it was invisible to this
#: gate because the phrasings did not match the ones above. Deleting the copies removes the failure
#: mode; scanning them harder does not.
OWNER = "HANDOFF.md"
OWNER_SECTION = "## 2."

#: Generated documents. Their numbers are recomputed from the registries on every build and cannot
#: drift, so the ownership rule does not apply - `--check-only` is already their gate.
GENERATED = frozenset({"docs/08-pm/COVERAGE_MATRIX.md", "docs/01-requirements/FRD.md"})

OWNERSHIP_HINT = (
    "measured counts live in HANDOFF.md section 2. Name the source instead of the number, or mark "
    "the line historical (strike it through, or write DONE/CLOSED/REACHED with a date)"
)


def main() -> int:
    counts = measure()
    markdown = sorted(DOCS.rglob("*.md")) + [REPO / name for name in ROOT_DOCS]

    failures: list[str] = []
    for path in markdown:
        rel = path.relative_to(REPO).as_posix()
        section = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                section = line
            if HISTORICAL.search(line):
                continue

            # Ownership is checked before value: a measured count in the wrong document is a defect
            # even when it is right today, because being right today is exactly how every previous
            # drift looked on the day it was written.
            if not (rel in GENERATED or (rel == OWNER and section.startswith(OWNER_SECTION))):
                for pattern, key, guard in CHECKS:
                    if key not in counts or (guard and guard not in line.lower()):
                        continue
                    for match in re.finditer(pattern, line, re.IGNORECASE):
                        phrase = re.sub(r"\s+", " ", match.group(0)).strip().replace("`", "")
                        if (rel, phrase) not in ALLOWED:
                            failures.append(f"{rel}: {phrase!r} - {OWNERSHIP_HINT}")
                continue

            for pattern, key, guard in CHECKS:
                if key not in counts:
                    continue
                if guard and guard not in line.lower():
                    continue
                for match in re.finditer(pattern, line, re.IGNORECASE):
                    phrase = re.sub(r"\s+", " ", match.group(0)).strip().replace("`", "")
                    if (rel, phrase) in ALLOWED:
                        continue
                    if int(match.group(1)) != counts[key]:
                        failures.append(
                            f"{rel}: says {phrase!r}, but {key} is {counts[key]}"
                        )

    for failure in failures:
        print(f"  {failure}")
    derived = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"\ncounts: {derived}")
    print(f"{len(markdown)} documents checked, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
