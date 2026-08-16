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


# -------------------------------------------------------------------- gate 21: worktree clean


def _git_init(root: Path) -> None:
    for args in (
        ["init", "-b", "main"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "--allow-empty", "-m", "base"],
    ):
        subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)


def test_worktree_gate_reports_untracked_governed_files(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "orphan.md").write_text("finished, uncommitted\n", encoding="utf-8")
    _git_init(tmp_path)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert code == 0, "advisory only - it must never fail the build"
    assert "docs/orphan.md" in out


def test_worktree_gate_is_quiet_on_a_clean_tree(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "kept.md").write_text("committed\n", encoding="utf-8")
    for args in (
        ["init", "-b", "main"],
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "base"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, check=True)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert code == 0
    assert "0 stray" in out


def test_worktree_gate_ignores_ungoverned_paths(tmp_path: Path) -> None:
    (tmp_path / "scratch.txt").write_text("not governed\n", encoding="utf-8")
    _git_init(tmp_path)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert code == 0
    assert "0 stray" in out


# --------------------------------------------------------------------------- gate 20: decisions


def _decisions_tree(tmp_path: Path, header: str, *, marker_file: str = "",
                    marker_body: str = "") -> Path:
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / "docs" / "decisions" / "DR-001-fixture.md").write_text(
        f"# DR-001: fixture\n\n```\n{header}\n```\n\nBody.\n", encoding="utf-8"
    )
    if marker_file:
        target = tmp_path / marker_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(marker_body, encoding="utf-8")
    return tmp_path


def test_decision_gate_catches_an_accepted_record_with_no_implementation_field(
        tmp_path: Path) -> None:
    root = _decisions_tree(tmp_path, "date: 2026-08-01\nstatus: accepted\nparameters: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 1
    assert "implemented_by" in out


def test_decision_gate_catches_an_absent_marker(tmp_path: Path) -> None:
    root = _decisions_tree(
        tmp_path,
        "date: 2026-08-01\nstatus: accepted\n"
        "implemented_by: tools/run.cmd :: fetch_directory.py",
        marker_file="tools/run.cmd", marker_body="echo nothing\n",
    )
    code, out = run_gate("verify_decisions.py", root)
    assert code == 1
    assert "fetch_directory.py" in out


def test_decision_gate_accepts_a_present_marker(tmp_path: Path) -> None:
    root = _decisions_tree(
        tmp_path,
        "date: 2026-08-01\nstatus: accepted\n"
        "implemented_by: tools/run.cmd :: fetch_directory.py",
        marker_file="tools/run.cmd",
        marker_body="python tools/fetch_directory.py --scheduled\n",
    )
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out


def test_decision_gate_accepts_an_explicit_none(tmp_path: Path) -> None:
    """A convention decision changes no code. Saying so out loud is the point."""
    root = _decisions_tree(tmp_path, "date: 2026-08-01\nstatus: accepted\nimplementation: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out


def test_decision_gate_ignores_a_proposal(tmp_path: Path) -> None:
    """Only accepted records promise anything. A proposal is still a question."""
    root = _decisions_tree(tmp_path, "date: 2026-08-01\nstatus: proposed\nparameters: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out


# --------------------------------------------------------------------------- fixtures


def _secrets_tree(tmp_path: Path, gitignore: str, doc: str = "") -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / ".gitignore").write_text(gitignore, encoding="utf-8")
    if doc:
        (tmp_path / "docs" / "NOTES.md").write_text(doc, encoding="utf-8")
    for args in (["init", "-b", "main"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "fixture"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, check=True)
    return tmp_path


# ------------------------------------------------------------------------- gate 19: secrets


def test_secret_gate_catches_a_false_ignore_claim(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, "docs/build/\n",
                         "The collector reads the ignored local file `.swingdesk-local.json`.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 1
    assert ".swingdesk-local.json" in out


@pytest.mark.parametrize(
    "claim",
    [
        "`.swingdesk-local.json` is ignored.\n",
        "`.swingdesk-local.json` is the local config.\n",
    ],
)
def test_secret_gate_catches_a_path_before_the_ignore_claim(tmp_path: Path, claim: str) -> None:
    root = _secrets_tree(tmp_path, "docs/build/\n", claim)
    code, out = run_gate("verify_secrets.py", root)
    assert code == 1
    assert ".swingdesk-local.json" in out


@pytest.mark.parametrize(
    "claim",
    [
        "The local config: `.swingdesk-local.json`.\n",
        "The ignored file, `.swingdesk-local.json`, stays off Git.\n",
        "The local config; `.swingdesk-local.json`.\n",
        "The ignored file (`.swingdesk-local.json`) is machine-specific.\n",
    ],
)
def test_secret_gate_catches_an_ignore_claim_with_punctuation(tmp_path: Path, claim: str) -> None:
    root = _secrets_tree(tmp_path, "docs/build/\n", claim)
    code, out = run_gate("verify_secrets.py", root)
    assert code == 1
    assert ".swingdesk-local.json" in out


def test_secret_gate_accepts_a_true_ignore_claim(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, ".swingdesk-local.json\n",
                         "The collector reads the ignored local file `.swingdesk-local.json`.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 0, out


def test_secret_gate_catches_a_tracked_secret_shaped_file(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, "docs/build/\n")
    (root / ".env").write_text("BROKER_TOKEN=abc\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-f", ".env"], capture_output=True, check=True)
    code, out = run_gate("verify_secrets.py", root)
    assert code == 1
    assert ".env" in out


def test_secret_gate_does_not_flag_ordinary_prose(tmp_path: Path) -> None:
    """A noisy gate gets bypassed. 'ignored' in prose must not trip it."""
    root = _secrets_tree(tmp_path, "docs/build/\n",
                         "Whitespace is ignored by the parser, and the header is ignored too.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 0, out


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


# --------------------------------------------------------------------------- count ownership


def _counts_tree(tmp_path: Path, doc: str, body: str) -> Path:
    """The smallest tree `verify_counts.py` can measure: two registries and a golden directory."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "registry").mkdir()
    (tmp_path / "registry" / "parameters.yml").write_text(
        "parameters:\n  - id: a.b\n    status: unset\n", encoding="utf-8")
    (tmp_path / "registry" / "components.yml").write_text(
        "components:\n  - component: X-1\n    activation: registered\n", encoding="utf-8")
    (tmp_path / "golden" / "components" / "one").mkdir(parents=True)
    (tmp_path / "tools").mkdir()
    # `_gate_count` parses the first all-string-keyed dict literal it finds, so the stub needs one.
    (tmp_path / "tools" / "check_gates.py").write_text(
        '"""stub"""\nresults = {"1 a": True, "2 b": True}\n', encoding="utf-8")
    for name in ("README.md", "AGENTS.md", "HANDOFF.md"):  # ROOT_DOCS; the gate reads all three
        (tmp_path / name).write_text("# stub\n", encoding="utf-8")
    (tmp_path / doc).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / doc).write_text(body, encoding="utf-8")
    return tmp_path


def test_ownership_rule_rejects_a_measured_count_outside_handoff(tmp_path: Path) -> None:
    """Correct today is how every previous drift looked on the day it was written."""
    # The count is CORRECT - the fixture holds exactly one `unset` parameter. It fails on
    # ownership alone, which is the whole point of the rule.
    root = _counts_tree(tmp_path, "docs/NOTES.md", "The registry carries 1 `unset` parameter.\n")
    code, out = run_gate("verify_counts.py", root)
    assert code == 1
    assert "HANDOFF.md section 2" in out
    assert "docs/NOTES.md" in out


def test_ownership_rule_allows_a_historical_line(tmp_path: Path) -> None:
    """`DONE <date>` and strikethrough are records, and rewriting them would falsify history."""
    root = _counts_tree(tmp_path, "docs/NOTES.md", "DONE 2026-08-03, 14 gates in that tree.\n")
    (root / "HANDOFF.md").write_text("# H\n\n## 2. State\n", encoding="utf-8")
    code, out = run_gate("verify_counts.py", root)
    assert code == 0, out


def test_ownership_rule_allows_the_owner_section(tmp_path: Path) -> None:
    root = _counts_tree(tmp_path, "docs/NOTES.md", "no counts here\n")
    (root / "HANDOFF.md").write_text("# H\n\n## 2. State\n\n| Tests | **0** |\n", encoding="utf-8")
    code, out = run_gate("verify_counts.py", root)
    assert code == 0, out


# ------------------------------------------------------------- gate 23: track A streak

#: A real, verified NYSE trading week (Mon-Fri, no holiday) - the calendar itself is not
#: fixture-mockable, so tests use dates independently confirmed to be sessions.
_MON, _TUE, _WED, _THU, _FRI = (
    "08/10/2026", "08/11/2026", "08/12/2026", "08/13/2026", "08/14/2026",
)


def _log_line(date_str: str, event: str) -> str:
    return f"===== [Day {date_str} 18:30:01.00] daily run {event} \n"


def _run_streak_gate(root: Path, now: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "track_a_streak.py")],
        capture_output=True, text=True,
        env={**os.environ, "SWINGDESK_ROOT": str(root), "SWINGDESK_NOW": now},
    )
    return result.returncode, result.stdout + result.stderr


def _streak_tree(tmp_path: Path, log_text: str) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "daily_run.log").write_text(log_text, encoding="utf-8")
    return tmp_path


def test_track_a_gate_reports_a_clean_streak(tmp_path: Path) -> None:
    log = "".join(
        _log_line(d, e)
        for day in (_TUE, _WED, _THU)
        for d, e in ((day, "starting"), (day, "finished, exit 0"))
    )
    root = _streak_tree(tmp_path, log)
    code, out = _run_streak_gate(root, "2026-08-13T22:00:00")
    assert code == 0
    assert "track A streak: 3/20" in out
    assert "2026-08-11 to 2026-08-13" in out


def test_track_a_gate_excludes_an_out_of_window_entry(tmp_path: Path) -> None:
    """The calibration case: a run starting 20:41 - 131 minutes past the 18:30 schedule - does not
    count as the scheduled attempt, even though it exited 0."""
    log = (
        f"===== [Day {_MON} 20:41:19.00] daily run starting \n"
        f"===== [Day {_MON} 20:46:30.00] daily run finished, exit 0 \n"
        + "".join(
            _log_line(d, e)
            for day in (_TUE, _WED)
            for d, e in ((day, "starting"), (day, "finished, exit 0"))
        )
    )
    root = _streak_tree(tmp_path, log)
    code, out = _run_streak_gate(root, "2026-08-12T22:00:00")
    assert code == 0
    assert "track A streak: 2/20" in out
    assert "2026-08-11 to 2026-08-12" in out
    assert "most recent break: 2026-08-10 (no qualifying scheduled-window entry)" in out


def test_track_a_gate_counts_exit_2_as_clean(tmp_path: Path) -> None:
    """`HANDOFF.md` §5: exit 2 is a refusal, a real outcome, not a failure."""
    log = _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 2")
    root = _streak_tree(tmp_path, log)
    code, out = _run_streak_gate(root, "2026-08-11T22:00:00")
    assert code == 0
    assert "track A streak: 1/20" in out


def test_track_a_gate_treats_exit_3_as_a_break(tmp_path: Path) -> None:
    """`HANDOFF.md` §5: exit 3 resets the counter, even though it is a coded outcome (empty
    universe) rather than a literal crash - the ratified reading is followed as given."""
    log = _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 3")
    root = _streak_tree(tmp_path, log)
    code, out = _run_streak_gate(root, "2026-08-11T22:00:00")
    assert code == 0
    assert "track A streak: 0" in out
    assert "most recent break: 2026-08-11 (exit 3)" in out


def test_track_a_gate_is_advisory_even_with_a_broken_streak(tmp_path: Path) -> None:
    log = _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 1")
    root = _streak_tree(tmp_path, log)
    code, _out = _run_streak_gate(root, "2026-08-11T22:00:00")
    assert code == 0, "advisory only - it must never fail the build"


def test_track_a_gate_reports_a_missing_run_as_a_break(tmp_path: Path) -> None:
    """A `starting` line with no matching `finished` - the crash case - reads the same as no entry
    at all: no evidence the run completed."""
    log = _log_line(_TUE, "starting")
    root = _streak_tree(tmp_path, log)
    code, out = _run_streak_gate(root, "2026-08-11T22:00:00")
    assert code == 0
    assert "track A streak: 0" in out


def test_track_a_gate_reports_a_missing_log_as_unavailable_not_as_zero(tmp_path: Path) -> None:
    """A checkout with no log has not measured a streak of zero. It has measured nothing.

    Contract changed 2026-08-15. This returned 0 and printed "nothing scheduled has run", so from a
    worktree - where `data/` never exists - the gate reported success while blind, and `HANDOFF.md`
    §2's hand-kept counter sat wrong at 3 against a measured 4 with every gate green. Exit 4 is
    `check_gates.py`'s UNAVAILABLE, which is counted separately and stops the suite saying "all
    gates pass" (`AGENTS.md` §10.6).
    """
    tmp_path.joinpath("data").mkdir()
    code, out = _run_streak_gate(tmp_path, "2026-08-13T22:00:00")
    assert code == 4, "a gate that cannot see its subject must not report PASS"
    assert "UNAVAILABLE" in out
    assert "streak: 0" not in out, "absent evidence must never render as a measured zero"


def test_track_a_gate_excludes_todays_session_while_its_window_is_still_open(tmp_path: Path) -> None:
    """A run in progress must not read as a break - "now" sits inside the schedule window, so
    today is not yet evaluable."""
    log = _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 0")
    root = _streak_tree(tmp_path, log)
    code, out = _run_streak_gate(root, "2026-08-12T18:45:00")  # inside the 30-minute tolerance
    assert code == 0
    assert "track A streak: 1/20" in out
    assert "2026-08-11 to 2026-08-11" in out


# ------------------------------------------------------------------ gate 24: the state block


def _build_state():
    """Import the gate 24 tool by path. It lives in `tools/`, which is not an installed package."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_state", TOOLS / "build_state.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_handoff_still_carries_all_generated_markers() -> None:
    """Delete a marker pair and gate 24 stops checking that section in silence.

    `_replace` raises rather than skipping, so a removed marker is a hard failure instead of a block
    that quietly stops being regenerated - which is how a generated section decays back into a typed
    one.
    """
    state = _build_state()
    text = (REPO / "HANDOFF.md").read_text(encoding="utf-8")
    for marker in (
        state.REPO_BEGIN, state.REPO_END,
        state.WORKTREES_BEGIN, state.WORKTREES_END,
        state.RUNTIME_BEGIN, state.RUNTIME_END,
    ):
        assert marker in text, f"HANDOFF.md lost {marker!r}"


def test_worktree_rows_reflect_git_worktree_list() -> None:
    """The worktree block and gate 16 read the same function, so they cannot disagree about what
    "currently checked out" means."""
    state = _build_state()
    from verify_branches import worktree_branches

    rendered = state.render_worktrees()
    for branch, sha in worktree_branches():
        assert branch in rendered, f"{branch!r} is checked out but missing from the generated block"
        assert sha in rendered, f"{branch!r}'s tip {sha!r} is missing from the generated block"


def test_missing_markers_fail_loudly_rather_than_no_op() -> None:
    state = _build_state()
    with pytest.raises(LookupError):
        state._replace("no markers here", state.REPO_BEGIN, state.REPO_END, "body")


def test_an_unmeasurable_runtime_block_does_not_render_as_a_measurement() -> None:
    """`None` is not zero and must not look like it.

    The whole defect this gate was built for was an absent measurement reading as a present one
    (`AGENTS.md` §10.6), so the rendered form has to be unmistakable.
    """
    state = _build_state()
    body = state.render_runtime(None)
    assert "UNAVAILABLE" in body
    assert "|---|---|" not in body, "an unmeasured block must not render as a table of figures"
