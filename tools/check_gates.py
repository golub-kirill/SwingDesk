"""Run every merge gate, fastest first (CI_POLICY 1).

One command, and the CI definition calls this same script - if a local run and CI can disagree, the
local run stops being trusted and the feedback loop lengthens to a push.

A gate that is wrong gets fixed or removed, never skipped. There is deliberately no --skip flag.

**Three states, not two** (added 2026-08-10, when CI was first wired). Gates 2 and 3 read the
owner's 116 course PDFs, which are not in the repository and cannot be: they are the requirements
source, not an artefact. Those two gates therefore cannot run in GitHub Actions, and the choice was
between a permanently red CI, a --skip flag, or naming the state honestly.

`UNAVAILABLE` is the state, and the vocabulary is the project's own: HANDOFF section 8, "a gap in
the *system* and a fact about the *trade* are different claims, and collapsing them is the most
damaging error this product can make". A gate whose subject is absent has not passed. It is
reported separately, it is counted separately, and the summary never says "all gates pass" when one
did not run.

Two things keep it from becoming a skip flag by another name. Only the gates in
`MAY_BE_UNAVAILABLE` are allowed the state - any other gate exiting 4 is a FAIL, because a gate
inventing a reason not to run is the failure this guard exists for. And the owner's machine has
everything, so locally every gate still runs: the weaker environment is the one that says so,
rather than the two quietly diverging.

**A second legitimate cause was added 2026-08-15: `data/`.** The local DuckDB stores and the
scheduler log are gitignored operational state - they cannot be in the repository for the same
reason the PDFs cannot, and they exist only in the main checkout. Gates 23 and 24 read them.
Gate 23 previously returned 0 from a worktree while printing "nothing scheduled has run", so a
hand-kept counter in `HANDOFF.md` sat wrong for days with every gate green. That is what the third
state is for, and extending it here is the alternative to a gate that lies quietly.
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

PASS, FAIL, UNAVAILABLE = "PASS", "FAIL", "UNAVAILABLE"

#: Exit code a gate uses to say "my subject is not present in this environment".
UNAVAILABLE_EXIT = 4

#: The only gates permitted to report UNAVAILABLE, and the three legitimate reasons. Gates 2 and 3
#: read the 116 course PDFs, the requirements source, which are not in the repository. Gates 23 and
#: 24 read `data/`, gitignored operational state present only in the main checkout. Gate 26 reads
#: the Windows Task Scheduler, which exists only on the machine that runs the schedule. Any other
#: gate exiting 4 is a FAIL - see the module docstring.
MAY_BE_UNAVAILABLE = frozenset({
    "2 transcription", "3 course index", "23 track A streak", "24 state block", "26 schedule",
})


def _run(name: str, argv: list[str], key: str = "") -> str:
    print(f"\n=== {name}")
    result = subprocess.run(argv, cwd=REPO)
    if result.returncode == 0:
        status = PASS
    elif result.returncode == UNAVAILABLE_EXIT and key in MAY_BE_UNAVAILABLE:
        status = UNAVAILABLE
    else:
        status = FAIL
    print(f"--- {name}: {status}")
    return status


def check_no_wall_clock() -> str:
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
    status = FAIL if offenders else PASS
    print(f"--- no wall clock: {status} ({len(PURE_PACKAGES)} packages checked)")
    return status


def main() -> int:
    python = sys.executable
    results = {
        "1 parameters": _run("parameter registry contract",
                           [python, "tools/verify_parameters.py"]),
        "2 transcription": _run("verbatim transcription + enums",
                              [python, "tools/verify_transcription.py"], "2 transcription"),
        "3e doc references": _run("documentation cross-references",
                               [python, "tools/verify_docs.py"]),
        "3f study record": _run("study record and the counts quoted from it",
                             [python, "tools/verify_studies.py"]),
        "3 course index": _run("course index shape",
                             [python, "tools/build_course_index.py", "--check-only"],
                             "3 course index"),
        "3b frd": _run("FRD current", [python, "tools/build_frd.py", "--check-only"]),
        "3c checklists current": _run("checklist registry current",
                                   [python, "tools/build_checklists.py", "--check-only"]),
        "3d components current": _run("component registry current",
                                   [python, "tools/build_components.py", "--check-only"]),
        "3ci coverage matrix": _run("coverage matrix current",
                                [python, "tools/build_coverage.py", "--check-only"]),
        "11 component contract": _run("component registry contract",
                                   [python, "tools/verify_components.py"]),
        "3g criteria evaluable": _run("committed criteria can fire",
                                   [python, "tools/verify_criteria.py"]),
        "13 study summary": _run("stated study counts match the record",
                              [python, "tools/verify_study_summary.py"]),
        "25 prereg conformance": _run("a reported verdict conforms to its pre-registration",
                                   [python, "tools/verify_prereg_conformance.py"]),
        "14 counts current": _run("hard-coded counts match the registries",
                               [python, "tools/verify_counts.py"]),
        "15 project manifest": _run("document index matches the tree",
                                 [python, "tools/verify_project_manifest.py"]),
        "4 ruff": _run("ruff", [python, "-m", "ruff", "check", "."]),
        "5 mypy": _run("mypy --strict", [python, "-m", "mypy"]),
        "6 import contracts": _run("import-linter architecture contracts",
                                 [python, "-m", "importlinter.cli", "lint-imports"]),
        "7 no wall clock": check_no_wall_clock(),
        "7b golden vectors": _run("golden vectors", [python, "tools/golden.py"]),
        "8 tests": _run("pytest", [python, "-m", "pytest", "tests/", "-q"]),
        "9 determinism replay": _run("determinism replay", [python, "tools/replay.py"]),
        "16 branch census": _run("parallel worktrees declared in HANDOFF",
                              [python, "tools/verify_branches.py"]),
        "17 declared dependencies": _run("every third-party import in src is declared",
                                      [python, "tools/verify_dependencies.py"]),
        "18 lock current": _run("requirements lock matches the declarations",
                             [python, "tools/build_lock.py", "--check-only"]),
        "19 secret hygiene": _run("no tracked secrets, no false ignore claims",
                               [python, "tools/verify_secrets.py"]),
        "20 decisions implemented": _run("accepted decisions declare what proves them",
                                      [python, "tools/verify_decisions.py"]),
        "21 worktree clean": _run("no finished work left uncommitted (advisory)",
                               [python, "tools/verify_worktree_clean.py"]),
        "23 track A streak": _run("the a.run_completes streak, computed not hand-kept (advisory)",
                               [python, "tools/track_a_streak.py"], "23 track A streak"),
        "24 state block": _run("HANDOFF section 2 is generated, not typed",
                            [python, "tools/build_state.py", "--check-only"], "24 state block"),
        "26 schedule": _run("the scheduled tasks exist and last succeeded (advisory)",
                            [python, "tools/verify_schedule.py"], "26 schedule"),
        "27 strategy cards": _run("a card's references resolve and it claims no more than it has",
                                  [python, "tools/verify_cards.py"]),
        "28 parameter claims": _run("no document states a parameter status the registry contradicts",
                                    [python, "tools/verify_parameter_claims.py"]),
        "29 prereg ids": _run("a pre-registration id is reserved once and listed where it is owed",
                              [python, "tools/verify_prereg_ids.py"]),
    }

    print("\n" + "=" * 62)
    for name, status in results.items():
        print(f"  {status:11s}  {name}")
    failed = [name for name, status in results.items() if status == FAIL]
    unavailable = [name for name, status in results.items() if status == UNAVAILABLE]
    print("=" * 62)

    if failed:
        print(f"{len(failed)} gate(s) failed: {', '.join(failed)}")
        return 1

    if unavailable:
        # Never "all gates pass". The count that matters to a reader is how many actually ran, and
        # a summary that hides a gate which did not run is the thing this state exists to prevent.
        ran = len(results) - len(unavailable)
        print(f"{ran} of {len(results)} gates pass; "
              f"{len(unavailable)} could not run here: {', '.join(unavailable)}")
        # Naming the cause generically, because there are now two and the message used to assert
        # the wrong one. A summary that misreports why a gate did not run is the same defect class
        # as a gate that does not report it at all.
        print("Their subjects are absent from this environment - the course PDFs, or `data/` in a "
              f"worktree. Run on the owner's main checkout for all {len(results)}.")
        return 0

    print("all gates pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
