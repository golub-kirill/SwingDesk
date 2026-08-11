"""The gates are tested for their ability to fail.

`RISK_REGISTER.md` B-1 names this as the mitigation for the project's structural risk — a solo
project with no second reviewer, where every finding so far was caught by a machine. That claim was
made before any such test existed, which made it the same class of defect the gates themselves
catch: a statement about the system that reads as true and is not.

A gate that has never been seen red proves nothing. Each case below builds a minimal fixture tree,
introduces one specific defect, and asserts the gate reports **that** defect — not merely that it
exited non-zero, which a crash would also do.

Fixtures live in `tmp_path` and the gates are pointed at them with `SWINGDESK_ROOT`. Nothing here
mutates the real tree: a test that edited the repository and then failed would leave it dirty, and
the suite must never be able to do that.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))


def run_gate(tool: str, root: Path) -> tuple[int, str]:
    """Run a verifier against `root`. Returns its exit code and combined output."""
    result = subprocess.run(
        [sys.executable, str(TOOLS / tool)],
        capture_output=True, text=True,
        env={**os.environ, "SWINGDESK_ROOT": str(root)},
    )
    return result.returncode, result.stdout + result.stderr


# --------------------------------------------------------------------------- fixtures


def _manifest_tree(tmp_path: Path, *, status: str = "drafting", number: str = "01") -> Path:
    """The smallest tree `verify_project_manifest.py` will accept: one tier, one document."""
    (tmp_path / "docs" / "00-charter").mkdir(parents=True)
    (tmp_path / "registry").mkdir()
    (tmp_path / "docs" / "00-charter" / "CHARTER.md").write_text(
        f"# Charter\n\n**Status:** {status}\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "README.md").write_text(
        "# Document set\n\n## Tier 0 — Charter · `00-charter/`\n\n"
        "| # | File | Freezes | Source | Status |\n|---|---|---|---|---|\n"
        f"| {number} | `CHARTER.md` | Purpose | Owner | drafting |\n",
        encoding="utf-8",
    )
    (tmp_path / "registry" / "project_manifest.yml").write_text(
        "project:\n  manifest_version: 1.0.0\n\n"
        "tiers:\n  - id: TIER-0\n    number: 0\n    title: \"Charter\"\n    paths: [00-charter/]\n\n"
        "documents:\n"
        f"  - id: DOC-{number.upper()}\n    display_number: \"{number}\"\n"
        "    tier_ref: TIER-0\n    artifact_class: PRIMARY_DELIVERABLE\n"
        "    path: docs/00-charter/CHARTER.md\n    document_status: drafting\n"
        "    status_source: document\n    readme_status_text: \"drafting\"\n"
        "    generated: false\n    file_expected: true\n",
        encoding="utf-8",
    )
    return tmp_path


def _study_tree(tmp_path: Path, claim: str, *, verdicts: tuple[str, ...] = ("reject",)) -> Path:
    """A tree with `len(verdicts)` reported studies and a document making `claim`."""
    results = tmp_path / "docs" / "prereg" / "results"
    results.mkdir(parents=True)
    for index, verdict in enumerate(verdicts, start=1):
        (tmp_path / "docs" / "prereg" / f"PR-00{index}-probe.md").write_text("# probe\n", "utf-8")
        (results / f"PR-00{index}.json").write_text(
            json.dumps({"prereg": f"PR-00{index}", "verdict": verdict}), encoding="utf-8"
        )
    (tmp_path / "docs" / "SUMMARY.md").write_text(f"# Summary\n\n{claim}\n", encoding="utf-8")
    for name in ("README.md", "AGENTS.md", "HANDOFF.md"):
        (tmp_path / name).write_text("# root\n", encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ gate 15: manifest


def test_manifest_gate_catches_a_status_contradicting_the_document(tmp_path: Path) -> None:
    """The defect this gate was written for: the index said `planned`, the document said otherwise."""
    root = _manifest_tree(tmp_path, status="planned")
    code, out = run_gate("verify_project_manifest.py", root)
    assert code == 1
    assert "declares 'planned' but the manifest says 'drafting'" in out


def test_manifest_gate_catches_a_missing_file(tmp_path: Path) -> None:
    root = _manifest_tree(tmp_path)
    (root / "docs" / "00-charter" / "CHARTER.md").unlink()
    code, out = run_gate("verify_project_manifest.py", root)
    assert code == 1
    assert "does not exist" in out


def test_manifest_gate_catches_a_document_in_no_index(tmp_path: Path) -> None:
    """A new specification must not be able to appear without being listed somewhere."""
    root = _manifest_tree(tmp_path)
    (root / "docs" / "00-charter" / "ORPHAN.md").write_text("# orphan\n", encoding="utf-8")
    code, out = run_gate("verify_project_manifest.py", root)
    assert code == 1
    assert "ORPHAN.md" in out and "no numbered row" in out


def test_manifest_gate_catches_an_index_row_with_no_entry(tmp_path: Path) -> None:
    root = _manifest_tree(tmp_path)
    readme = root / "docs" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") +
                      "| 02 | `GHOST.md` | Nothing | Owner | drafting |\n", encoding="utf-8")
    code, out = run_gate("verify_project_manifest.py", root)
    assert code == 1
    assert "row '02' has no manifest entry" in out


def test_manifest_gate_passes_a_consistent_tree(tmp_path: Path) -> None:
    """The other half of the pair. A gate that only ever fails is not discriminating either."""
    code, out = run_gate("verify_project_manifest.py", _manifest_tree(tmp_path))
    assert code == 0, out
    assert "0 failure(s)" in out


# -------------------------------------------------------------- gate 13: study census


@pytest.mark.parametrize(
    ("claim", "fragment"),
    [
        ("Four studies were run.", "four studies"),
        ("Three refuted hypotheses.", "three refuted"),
        ("Two pre-registrations exist.", "two pre-registrations"),
    ],
)
def test_study_gate_catches_an_overstated_census(tmp_path: Path, claim: str,
                                                 fragment: str) -> None:
    """One study on disk, and three different ways of claiming more than that."""
    code, out = run_gate("verify_study_summary.py", _study_tree(tmp_path, claim))
    assert code == 1
    assert fragment in out.lower()


def test_study_gate_counts_only_results_carrying_a_verdict(tmp_path: Path) -> None:
    """A supporting analysis is not a study — the exact confusion that caused the original defect."""
    root = _study_tree(tmp_path, "One study was run.")
    (root / "docs" / "prereg" / "results" / "PR-001-bound.json").write_text(
        json.dumps({"note": "supporting analysis, no prereg id and no verdict"}), encoding="utf-8"
    )
    code, out = run_gate("verify_study_summary.py", root)
    assert code == 0, out
    assert "reported=1" in out


def test_study_gate_passes_an_accurate_census(tmp_path: Path) -> None:
    root = _study_tree(tmp_path, "Two studies were run, one refuted and one accepted.",
                       verdicts=("reject", "accept"))
    code, out = run_gate("verify_study_summary.py", root)
    assert code == 0, out


# --------------------------------------------------------------------------- preflight


def _preflight_tree(tmp_path: Path, *dependencies: str) -> Path:
    """A tree whose pyproject declares exactly `dependencies`."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'fixture'\nversion = '0'\ndependencies = [\n"
        + "".join(f'    "{item}",\n' for item in dependencies)
        + "]\n",
        encoding="utf-8",
    )
    return tmp_path


def test_preflight_catches_a_declared_dependency_that_is_not_installed(tmp_path: Path) -> None:
    """The 2026-08-10 defect in miniature: declared, absent, and only noticed at the first fetch."""
    code, out = run_gate("preflight.py", _preflight_tree(tmp_path, "swingdesk-not-a-real-dist>=1"))
    assert code == 3, out
    assert "swingdesk-not-a-real-dist" in out
    assert "run was NOT attempted" in out


def test_preflight_passes_when_every_declared_dependency_is_present(tmp_path: Path) -> None:
    """pytest is running, so it is installed - a positive control for the check itself."""
    code, out = run_gate("preflight.py", _preflight_tree(tmp_path, "pytest>=8"))
    assert code == 0, out


def test_preflight_reads_the_version_specifier_off_the_name(tmp_path: Path) -> None:
    """`yfinance>=1` must resolve to `yfinance`, not to the whole requirement string."""
    code, out = run_gate("preflight.py", _preflight_tree(tmp_path, "pytest>=8,<99; python_version>'3'"))
    assert code == 0, out


def test_preflight_refuses_a_pyproject_declaring_nothing(tmp_path: Path) -> None:
    """An empty dependency list is a malformed environment, not a clean bill of health."""
    code, out = run_gate("preflight.py", _preflight_tree(tmp_path))
    assert code == 3, out
    assert "no runtime dependencies" in out


# --------------------------------------------------------------------------- unavailable gates


def _exiting_with(tmp_path: Path, code: int) -> list[str]:
    """A command that does nothing but exit with `code`."""
    script = tmp_path / "exits.py"
    script.write_text(f"raise SystemExit({code})\n", encoding="utf-8")
    return [sys.executable, str(script)]


def test_course_index_reports_unavailable_rather_than_failing(tmp_path: Path) -> None:
    """The 116 PDFs are not in the repository, so CI must be able to tell absent from broken."""
    result = subprocess.run(
        [sys.executable, str(TOOLS / "build_course_index.py"), "--check-only",
         "--course-root", str(tmp_path / "no-such-course")],
        capture_output=True, text=True,
    )
    assert result.returncode == 4
    assert "UNAVAILABLE" in result.stderr


def test_runner_maps_exit_4_to_unavailable_for_a_permitted_gate(tmp_path: Path) -> None:
    import check_gates

    status = check_gates._run("fixture", _exiting_with(tmp_path, 4), "3 course index")
    assert status == check_gates.UNAVAILABLE


def test_runner_treats_exit_4_from_any_other_gate_as_a_failure(tmp_path: Path) -> None:
    """Otherwise UNAVAILABLE becomes the --skip flag this runner deliberately does not have."""
    import check_gates

    status = check_gates._run("fixture", _exiting_with(tmp_path, 4), "8 tests")
    assert status == check_gates.FAIL


def test_runner_treats_an_unkeyed_gate_exiting_4_as_a_failure(tmp_path: Path) -> None:
    """A gate wired without its allowlist key must not inherit the exemption by accident."""
    import check_gates

    assert check_gates._run("fixture", _exiting_with(tmp_path, 4)) == check_gates.FAIL


def test_every_permitted_gate_name_is_a_real_gate() -> None:
    """`MAY_BE_UNAVAILABLE` naming a gate that no longer exists would exempt nothing, silently."""
    import check_gates

    source = (TOOLS / "check_gates.py").read_text(encoding="utf-8")
    for name in check_gates.MAY_BE_UNAVAILABLE:
        assert f'"{name}": _run(' in source, name


# --------------------------------------------------------------------------- declared dependencies


def _dependency_tree(tmp_path: Path, source: str, *dependencies: str) -> Path:
    """A tree with one src module and a pyproject declaring `dependencies`."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'fixture'\nversion = '0'\ndependencies = [\n"
        + "".join(f'    "{item}",\n' for item in dependencies)
        + "]\n",
        encoding="utf-8",
    )
    package = tmp_path / "src" / "swingdesk"
    package.mkdir(parents=True)
    (package / "mod.py").write_text(source, encoding="utf-8")
    return tmp_path


def test_dependency_gate_catches_an_undeclared_module_level_import(tmp_path: Path) -> None:
    code, out = run_gate("verify_dependencies.py",
                         _dependency_tree(tmp_path, "import yfinance\n"))
    assert code == 1
    assert "yfinance" in out


def test_dependency_gate_catches_an_import_nested_inside_a_function(tmp_path: Path) -> None:
    """The yfinance defect exactly: a function-level import no smoke test would reach."""
    source = "def fetch():\n    import yfinance as yf\n    return yf\n"
    code, out = run_gate("verify_dependencies.py", _dependency_tree(tmp_path, source))
    assert code == 1
    assert "yfinance" in out
    assert ":2:" in out


def test_dependency_gate_accepts_a_declared_import(tmp_path: Path) -> None:
    code, out = run_gate("verify_dependencies.py",
                         _dependency_tree(tmp_path, "import pytest\n", "pytest>=8"))
    assert code == 0, out


def test_dependency_gate_maps_a_distribution_to_its_import_name(tmp_path: Path) -> None:
    """`pyyaml` provides `yaml`; comparing the two strings directly would fail a correct tree."""
    code, out = run_gate("verify_dependencies.py",
                         _dependency_tree(tmp_path, "import yaml\n", "pyyaml>=6"))
    assert code == 0, out


def test_dependency_gate_ignores_stdlib_and_relative_imports(tmp_path: Path) -> None:
    source = "import json\nimport sys\nfrom . import sibling\nfrom swingdesk.x import y\n"
    code, out = run_gate("verify_dependencies.py", _dependency_tree(tmp_path, source))
    assert code == 0, out


def test_dependency_gate_ignores_type_checking_only_imports(tmp_path: Path) -> None:
    """Those never execute, so a missing distribution behind one cannot break a run."""
    source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import yfinance\n"
    code, out = run_gate("verify_dependencies.py", _dependency_tree(tmp_path, source))
    assert code == 0, out


# --------------------------------------------------------------------------- lock currency


def test_lock_gate_catches_a_stale_lock(tmp_path: Path) -> None:
    """A dependency added to pyproject and never locked is the drift this gate exists for."""
    lock = tmp_path / "lock.txt"
    result = subprocess.run(
        [sys.executable, str(TOOLS / "build_lock.py"), "--out", str(lock)],
        capture_output=True, text=True, cwd=REPO,
    )
    assert result.returncode == 0, result.stderr
    lock.write_text(lock.read_text(encoding="utf-8").replace("pytest==", "pytest==0.0.0+stale"),
                    encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(TOOLS / "build_lock.py"), "--check-only", "--out", str(lock)],
        capture_output=True, text=True, cwd=REPO,
    )
    assert result.returncode == 1
    assert "version moved" in result.stderr


def test_lock_gate_catches_a_missing_lock(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "build_lock.py"), "--check-only",
         "--out", str(tmp_path / "absent.txt")],
        capture_output=True, text=True, cwd=REPO,
    )
    assert result.returncode == 1
    assert "missing" in result.stderr


def test_lock_round_trips(tmp_path: Path) -> None:
    """Generate then check must agree, or the gate is red the moment it is wired."""
    lock = tmp_path / "lock.txt"
    for args in (["--out", str(lock)], ["--check-only", "--out", str(lock)]):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "build_lock.py"), *args],
            capture_output=True, text=True, cwd=REPO,
        )
        assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------- branch census


def test_branch_census_survives_a_clone_with_no_master_ref(tmp_path: Path) -> None:
    """A GitHub checkout creates only the branch being built, and `--merged master` exits 128.

    This crashed the gate on CI's first run. It cannot reproduce on a developer machine, where
    `master` always exists, so the regression test builds the condition explicitly.
    """
    repo = tmp_path / "clone"
    repo.mkdir()
    (repo / "tools").mkdir()
    (repo / "HANDOFF.md").write_text("no worktrees here\n", encoding="utf-8")
    (repo / "tools" / "verify_branches.py").write_text(
        (TOOLS / "verify_branches.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    for args in (["init", "-b", "feature-only"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "only branch"]):
        subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)

    assert "master" not in subprocess.run(
        ["git", "-C", str(repo), "branch"], capture_output=True, text=True, check=True
    ).stdout

    result = subprocess.run(
        [sys.executable, str(repo / "tools" / "verify_branches.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
