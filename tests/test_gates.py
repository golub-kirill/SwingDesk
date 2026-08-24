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


# ------------------------------------------------------------- gate 23: idle-day diagnostic
#
# Council finding, 2026-08-16: CLEAN_EXIT_CODES counts a run that skipped every candidate
# identically the same as one that actually evaluated something. These tests prove idle_days() can
# tell the two apart - and, per RISK_REGISTER B-1's own rule for this file, that it can fail.


def _within_schedule_start(date_str: str) -> str:
    """A `started_at` inside the 18:30 local tolerance, tagged with the TOOL's own LOCAL_ZONE -
    not a hardcoded UTC offset. `idle_days()` matches sessions against the real machine's local
    zone the same way the log-based tests do, so the fixture has to agree with it rather than
    assume a zone, or this test would be true only on a machine that happens to sit near UTC."""
    from datetime import datetime as _dt

    import track_a_streak

    day, month, year = date_str.split("/")[1], date_str.split("/")[0], date_str.split("/")[2]
    return _dt(
        int(year), int(month), int(day), 18, 15, tzinfo=track_a_streak.LOCAL_ZONE
    ).isoformat()


def _record_run(
    journal_path: Path, run_id: str, started_at_iso: str, decisions: list[tuple],
) -> None:
    """Write one run and its decisions with the real classes, not hand-rolled SQL."""
    from datetime import datetime

    from swingdesk.contracts.run import RunManifest, RunMode
    from swingdesk.journal_evidence.journal import DecisionRecord, Journal

    manifest = RunManifest(
        run_id=run_id, started_at=datetime.fromisoformat(started_at_iso),
        mode=RunMode.LIVE, code_hash="a", config_hash="b", snapshot_id="s",
        calendar_version="c", platform="p",
    )
    with Journal(journal_path) as journal:
        journal.start_run(manifest)
        journal.record_decisions(
            run_id, datetime.fromisoformat(started_at_iso),
            [DecisionRecord(instrument_id=iid, decision=d, reason_code=rc, parameter_id=pid)
             for iid, d, rc, pid in decisions],
        )
        journal.complete_run(run_id, "hash", datetime.fromisoformat(started_at_iso))


def test_idle_day_line_is_absent_without_a_journal(tmp_path: Path) -> None:
    """No `journal.duckdb` means the check could not run - reported as UNAVAILABLE, not silence."""
    log = _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 0")
    root = _streak_tree(tmp_path, log)
    code, out = _run_streak_gate(root, "2026-08-11T22:00:00")
    assert code == 0
    assert "idle-day check: UNAVAILABLE" in out


def test_idle_day_line_counts_a_uniformly_refused_day_as_idle(tmp_path: Path) -> None:
    """Every candidate Skipped for the same unset parameter - the exact shape PR #9 produces with
    exit.atr_stop_multiple / exit.max_holding_period unset."""
    log = _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 0")
    root = _streak_tree(tmp_path, log)
    _record_run(
        root / "data" / "journal.duckdb", "run-idle", _within_schedule_start(_TUE),
        [
            ("AAA", "Skip", "RISK", "exit.atr_stop_multiple"),
            ("BBB", "Skip", "RISK", "exit.atr_stop_multiple"),
        ],
    )
    code, out = _run_streak_gate(root, "2026-08-11T22:00:00")
    assert code == 0
    assert "1/1 counted day(s) were idle" in out


def test_idle_day_line_does_not_count_a_substantive_day_as_idle(tmp_path: Path) -> None:
    """This is the fail-first case: without idle_days() distinguishing outcomes, this would read
    identically to the uniformly-refused test above. A Watch alongside a Skip is real variety."""
    log = _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 0")
    root = _streak_tree(tmp_path, log)
    _record_run(
        root / "data" / "journal.duckdb", "run-substantive", _within_schedule_start(_TUE),
        [
            ("AAA", "Watch", None, None),
            ("BBB", "Skip", "DATA", None),
        ],
    )
    code, out = _run_streak_gate(root, "2026-08-11T22:00:00")
    assert code == 0
    assert "0/1 counted day(s) were idle" in out


def test_idle_day_line_treats_an_empty_run_as_idle(tmp_path: Path) -> None:
    """No candidates at all - a positions-only run, or a refused universe - has no variety either."""
    log = _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 0")
    root = _streak_tree(tmp_path, log)
    _record_run(root / "data" / "journal.duckdb", "run-empty", _within_schedule_start(_TUE), [])
    code, out = _run_streak_gate(root, "2026-08-11T22:00:00")
    assert code == 0
    assert "1/1 counted day(s) were idle" in out


def test_idle_day_line_reports_unmatched_days_separately(tmp_path: Path) -> None:
    """A counted-clean day with no matching journal run is UNMATCHED, not assumed idle or clean -
    the same three-state discipline `measure()` itself uses for a missing log."""
    log = "".join(
        _log_line(d, e)
        for day in (_TUE, _WED)
        for d, e in ((day, "starting"), (day, "finished, exit 0"))
    )
    root = _streak_tree(tmp_path, log)
    _record_run(
        root / "data" / "journal.duckdb", "run-tue", _within_schedule_start(_TUE),
        [("AAA", "Skip", "RISK", "exit.atr_stop_multiple")],
    )
    # Wednesday has a scheduled-window log entry but no matching journal run at all.
    code, out = _run_streak_gate(root, "2026-08-12T22:00:00")
    assert code == 0
    assert "1/1 counted day(s) were idle (every candidate refused identically), 1 unmatched" in out


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

    rows = state.worktree_rows()
    if not rows:
        pytest.skip("no sibling worktrees visible from this checkout")
    rendered = state.render_worktrees(rows)
    for branch, _sha in worktree_branches():
        assert branch in rendered, f"{branch!r} is checked out but missing from the generated block"


def test_the_census_records_nothing_that_moves_when_you_commit() -> None:
    """A worktree lists its OWN branch, so any fact about that branch which changes on commit leaves
    the census stale against itself the instant it is written - gate 24 red on every commit, forever.

    Tips move every commit. Merge state moves on the first commit (the branch stops equalling
    `master`) and again whenever a sibling merges. Both were tried here; both did exactly that. Only
    the branch NAME is stable, and it changes precisely when a worktree is added or removed - the
    event gate 16 exists to catch.
    """
    state = _build_state()
    from verify_branches import worktree_branches

    rows = state.worktree_rows()
    if not rows:
        pytest.skip("no sibling worktrees visible from this checkout")
    rendered = state.render_worktrees(rows)
    for _branch, sha in worktree_branches():
        assert sha not in rendered, (
            f"tip {sha!r} is in the census; it is stale one commit from now"
        )
    for volatile in ("merged into", "NOT merged"):
        assert volatile not in rendered, (
            f"{volatile!r} is in the census; merge state moves without this file being edited"
        )


def test_a_checkout_with_no_sibling_worktrees_leaves_the_block_alone(tmp_path: Path) -> None:
    """The CI regression, pinned. A runner sees zero sibling worktrees; that is blindness, not a
    measurement of nothing, and rewriting the block from it would overwrite another machine's true
    list and then fail the very gate that just wrote it.

    Shipped without this test on 2026-08-16 and CI caught it within the hour: the generator produced
    an empty list, compared it against five committed rows, and called the file stale - correctly.
    """
    state = _build_state()
    committed = (
        f"{state.WORKTREES_BEGIN}\n\n| Branch | State |\n|---|---|\n"
        f"| `claude/somebody-elses-worktree` | tip `abc1234` · **NOT merged** |\n\n"
        f"{state.WORKTREES_END}"
    )
    # An empty measurement must leave that text exactly as it stands.
    assert state._replace(committed, state.WORKTREES_BEGIN, state.WORKTREES_END, committed) == committed
    with pytest.raises(TypeError):
        state.render_worktrees()  # type: ignore[call-arg]


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


# ------------------------------------------------ gate 25: prereg conformance


def _conformance_tree(tmp_path: Path, record: dict) -> Path:
    (tmp_path / "docs" / "prereg" / "results").mkdir(parents=True)
    (tmp_path / "docs" / "prereg" / "results" / "PR-999.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    return tmp_path


def test_conformance_gate_catches_an_accept_over_a_declared_shortfall(tmp_path: Path) -> None:
    """PR-002's exact shape, and the case this gate was built for.

    It reported `single_market: true` beside a verdict of `accept`, on a prereg whose §6 permitted
    accept only in both countries. The flag was recorded and no gate read it as part of the verdict.
    """
    root = _conformance_tree(
        tmp_path,
        {"prereg": "PR-999", "verdict": "accept", "country": "US", "single_market": True,
         "perturbations": {"registered": [], "run": []}},
    )
    code, out = run_gate("verify_prereg_conformance.py", root)
    assert code == 1
    assert "single_market" in out
    assert "inconclusive branch" in out


def test_conformance_gate_catches_an_accept_missing_a_registered_perturbation(
        tmp_path: Path) -> None:
    """PR-002's second, quieter defect: §5 registered three perturbations and one was run."""
    root = _conformance_tree(tmp_path, {
        "prereg": "PR-999", "verdict": "accept", "country": "US",
        "perturbations": {"registered": ["cost_stress", "threshold_20pct"],
                          "run": ["cost_stress"]},
    })
    code, out = run_gate("verify_prereg_conformance.py", root)
    assert code == 1
    assert "threshold_20pct" in out


def test_conformance_gate_requires_a_reported_study_to_state_its_scope(tmp_path: Path) -> None:
    root = _conformance_tree(tmp_path, {"prereg": "PR-999", "verdict": "reject"})
    code, out = run_gate("verify_prereg_conformance.py", root)
    assert code == 1
    assert "country" in out


def test_conformance_gate_requires_a_perturbations_declaration(tmp_path: Path) -> None:
    """The condition that makes this gate bite on the present tree rather than on a hypothetical
    future study. An empty `registered` is a legitimate declaration; an ABSENT block is not,
    because it cannot be told apart from nobody having looked.

    The first cut of this gate only REPORTED this, and every study was in that state - so the gate
    was green because the tree was silent, which is not a gate."""
    root = _conformance_tree(
        tmp_path, {"prereg": "PR-999", "verdict": "reject", "country": "US"}
    )
    code, out = run_gate("verify_prereg_conformance.py", root)
    assert code == 1
    assert "perturbations" in out


def test_conformance_gate_accepts_an_empty_perturbation_registration(tmp_path: Path) -> None:
    """PR-008 and PR-010 register none. Saying so explicitly is a declaration, not a gap."""
    root = _conformance_tree(tmp_path, {
        "prereg": "PR-999", "verdict": "reject", "country": "US",
        "perturbations": {"registered": [], "run": []},
    })
    code, out = run_gate("verify_prereg_conformance.py", root)
    assert code == 0, out


def test_conformance_gate_allows_a_shortfall_on_a_non_affirmative_verdict(tmp_path: Path) -> None:
    """A study may always conclude LESS than it registered. `inconclusive` over a single market is
    precisely the correct handling - it is what PR-002 should have said - so it must not fail."""
    root = _conformance_tree(tmp_path, {
        "prereg": "PR-999", "verdict": "inconclusive", "country": "US", "single_market": True,
        "perturbations": {"registered": [], "run": []},
    })
    code, out = run_gate("verify_prereg_conformance.py", root)
    assert code == 0, out


def test_conformance_gate_ignores_a_supporting_analysis(tmp_path: Path) -> None:
    """A file without a prereg id and a verdict is not a study - `PR-002-survivorship-bound.json`
    is one, and counting it as a study once inflated every summary that quoted it (gate 13)."""
    root = _conformance_tree(tmp_path, {"note": "supporting analysis", "bound": "2.3%"})
    code, out = run_gate("verify_prereg_conformance.py", root)
    assert code == 0, out
    assert "0 study(ies) checked" in out


# ------------------------------------- the deliberate restart (2026-08-17), and what it exposed
#
# The 2026-08-16 amendment - a merge to a frozen file that changes decision output resets the
# counter from the merge date - existed ONLY AS PROSE until 2026-08-17, and fired that day with
# nothing enforcing it. PR #9 merged and the tool went on reporting 5/20, four of those days having
# run under the pipeline the merge corrected. These pin the mechanism that replaced the prose.


def test_a_restart_truncates_the_streak_to_sessions_after_it() -> None:
    """Sessions on or before a restart date never count, however cleanly they ran - they measured a
    different system. This is the whole point of the amendment, and it is asserted on the pure
    function rather than through the CLI so the restart date can be varied."""
    from datetime import date, datetime

    import track_a_streak

    attempts = [
        track_a_streak.Attempt(
            session_date=date(2026, 8, d),
            started_at=datetime(2026, 8, d, 18, 30, tzinfo=track_a_streak.LOCAL_ZONE),
            exit_code=0,
        )
        for d in (11, 12, 13, 14, 17)
    ]
    # `as_of` is the restart evening itself, NOT a later day, and that choice is the test.
    # At 2026-08-18 the un-truncated tool also returns zero - because 08-18 has no run - so the
    # assertion would have passed against the unfixed code, for the wrong reason. Caught by the
    # stash ritual (`AGENTS.md` 12) and fixed here. At 2026-08-17 the two answers differ: five
    # clean sessions without the restart, zero with it.
    as_of = datetime(2026, 8, 17, 22, 0, tzinfo=track_a_streak.LOCAL_ZONE)

    count, start, _ = track_a_streak.streak(attempts, as_of)
    assert count == 0, (
        "every counted session is on or before the 2026-08-17 restart, so the streak is zero - "
        f"got {count} starting {start}"
    )


def test_the_restart_is_reported_rather_than_leaving_a_bare_zero(tmp_path: Path) -> None:
    """A zero after a deliberate restart and a zero after an outage are different facts. Printing
    the number alone makes an intentional reset read as a failure."""
    log = "".join(
        _log_line(d, e)
        for day in (_TUE, _WED, _THU)
        for d, e in ((day, "starting"), (day, "finished, exit 0"))
    )
    code, out = _run_streak_gate(_streak_tree(tmp_path, log), "2026-08-18T22:00:00")

    # Read from STREAK_RESTARTS, never restated here. This assertion named 2026-08-17 and "PR #9"
    # as literals until 2026-08-18, when adding the second restart row broke a test that was
    # measuring nothing about the behaviour it names - the same one-owner rule AGENTS.md 10.5
    # applies to counts, applied to a date.
    #
    # And `restarted_at(<the pinned now>)`, not `STREAK_RESTARTS[-1]`: the gate is run above with
    # SWINGDESK_NOW pinned to 2026-08-18, so the restart it must name is the one in force THEN, not
    # whichever row happens to be last today. Taking the last row made this test pass for the wrong
    # reason on 2026-08-22 - it agreed with a wall-clock read in the tool that was itself the bug.
    from datetime import datetime

    sys.path.insert(0, str(TOOLS))
    import track_a_streak

    latest_date, latest_reason = track_a_streak.restarted_at(
        datetime(2026, 8, 18, 22, 0, tzinfo=track_a_streak.LOCAL_ZONE)
    )

    assert code == 0, "advisory - a restart must never fail the gate"
    assert "track A streak: 0" in out
    assert f"deliberate restart on {latest_date}" in out
    assert latest_reason[:40] in out, "the reason travels with the number (CHARTER 4)"


def test_the_restart_date_itself_is_never_reported_as_a_break() -> None:
    """`broke_at` reports a FAILURE; a restart is a correctness fix landing on purpose. Sessions
    at or before the restart are outside the window entirely, so the restart date can never surface
    as the thing that broke a streak.

    Asserted as that invariant rather than "no break is ever printed", which would be a stronger
    claim than is true: a genuinely missing run AFTER the restart is a real break and must still be
    reported. The first draft of this test asserted the stronger thing and failed correctly.
    """
    from datetime import date, datetime

    import track_a_streak

    attempts = [
        track_a_streak.Attempt(
            session_date=date(2026, 8, d),
            started_at=datetime(2026, 8, d, 18, 30, tzinfo=track_a_streak.LOCAL_ZONE),
            exit_code=0,
        )
        for d in (11, 12, 13, 14, 17)
    ]
    as_of = datetime(2026, 8, 21, 22, 0, tzinfo=track_a_streak.LOCAL_ZONE)

    # The restart IN FORCE at `as_of`, which is what `streak()` itself uses - not the newest row in
    # the tuple. Taking the last row asserted against a restart dated after this fixture's own
    # `as_of` the moment a later one was added, and failed for a reason that said nothing about the
    # invariant. A test that pins a date must pin every date it compares to (`AGENTS.md` §12).
    restart = track_a_streak.restarted_at(as_of)[0]

    _, _, broke_at = track_a_streak.streak(attempts, as_of)
    assert broke_at != restart, "an intentional reset must never read as an outage"
    assert broke_at is None or broke_at > restart


def test_a_zero_streak_does_not_claim_the_journal_is_missing(tmp_path: Path) -> None:
    """The conflation `AGENTS.md` 12 calls the most damaging error this product can make.

    `idle_days()` returns None for two unrelated reasons - no journal, or no counted sessions - and
    the caller printed the environment message for both. Latent until the restart made a zero
    streak normal, at which point the tool asserted that a database sitting right there did not
    exist.
    """
    log = "".join(
        _log_line(d, e)
        for day in (_TUE, _WED)
        for d, e in ((day, "starting"), (day, "finished, exit 0"))
    )
    root = _streak_tree(tmp_path, log)
    _record_run(root / "data" / "journal.duckdb", "r1", _within_schedule_start(_TUE),
                [("TEST.1", "Skip", "RISK", "risk.per_trade_pct")])

    _, out = _run_streak_gate(root, "2026-08-18T22:00:00")

    assert "track A streak: 0" in out
    assert "UNAVAILABLE" not in out, "the journal exists; saying otherwise is a false claim"
    assert "nothing to check" in out


# ------------------------------- gate 11: `spec` is resolved, not measured for length (2026-08-18)
#
# The check existed and passed for months while every one of the seven implemented components
# pointed at a heading that did not exist. `implements` was resolved for real - import the module,
# find the symbol - and `spec` was checked for non-emptiness. A pointer only checked for length is
# not a pointer; it is a claim nobody has read.


def _spec_failure(component: str, spec: str):
    import sys
    sys.path.insert(0, str(TOOLS))
    from verify_components import spec_failure

    return spec_failure(component, spec)


def test_a_dangling_document_anchor_is_a_failure() -> None:
    """The defect itself. `ALGORITHM_SPEC.md` exists and has numbered headings only, so every one
    of `#atr`, `#sma`, `#swing-high`, `#classifier`, `#breadth`, `#trend-filter` named a section
    that was never written."""
    failure = _spec_failure("TEST-1", "docs/02-domain/ALGORITHM_SPEC.md#atr")
    assert failure is not None
    assert "no such heading" in failure


def test_a_real_document_anchor_passes() -> None:
    """A positive control. Without one, the test above passes for any string at all and proves
    nothing about anchors (`AGENTS.md` 12)."""
    assert _spec_failure("TEST-1", "docs/02-domain/ALGORITHM_SPEC.md#1-the-required-fields") is None


def test_a_module_carrying_its_record_passes() -> None:
    """`ALGORITHM_SPEC.md` 7 asked whether specs live in that document or beside the code. Five
    components had already answered by carrying the eleven-field record in their module docstring,
    so the `.py` form is where these specifications actually are."""
    assert _spec_failure("TEST-1", "src/swingdesk/derived_observations/atr.py") is None


def test_a_module_without_the_record_is_a_failure() -> None:
    """The `.py` form must check CONTENT, not existence — otherwise it is the original defect one
    file type over. `regime.py` is real code and carries no record, which is why its component was
    demoted rather than pointed at it."""
    failure = _spec_failure("TEST-1", "src/swingdesk/derived_observations/regime.py")
    assert failure is not None
    assert "carries no" in failure


def test_a_missing_file_is_a_failure() -> None:
    assert "does not exist" in (_spec_failure("TEST-1", "docs/nope.md#x") or "")


# ------------- gate 1: `read_by` resolves the CONSUMER of a value, added 2026-08-18
#
# The registry recorded where the course MENTIONS a concept (`named_in`) and where the value CAME
# FROM (`provenance`), and nothing about whether anything consumed it. Measured that day: 23
# parameters carried a value no line of code read, fourteen from `DR-007` alone. Three findings in
# one week — the exit policy, the staleness gate, the corporate-actions gate — were all that shape.


def _reader_failure(**entry):
    import sys
    sys.path.insert(0, str(TOOLS))
    from verify_parameters import reader_failure

    return reader_failure({"id": "test.param", **entry})


def test_a_named_reader_that_resolves_passes() -> None:
    """Positive control. Without it the failures below pass for any string at all."""
    assert _reader_failure(read_by="swingdesk.trade_management.sizing:size_long") is None


def test_an_explicit_none_passes() -> None:
    """`none` is the honest alternative, not a loophole: many parameters legitimately precede the
    code that will read them. It is counted and printed rather than hidden."""
    assert _reader_failure(read_by="none") is None


def test_a_missing_read_by_is_a_failure() -> None:
    assert "no `read_by`" in (_reader_failure() or "")


def test_a_reader_naming_a_module_that_does_not_exist_is_a_failure() -> None:
    failure = _reader_failure(read_by="swingdesk.nowhere:whatever")
    assert failure is not None
    assert "cannot import" in failure


def test_a_reader_naming_a_symbol_that_does_not_exist_is_a_failure() -> None:
    """The half a presence check cannot see. `sizing` imports fine; `no_such_function` does not
    exist in it, and that is exactly the shape of a pointer nobody has read."""
    failure = _reader_failure(read_by="swingdesk.trade_management.sizing:no_such_function")
    assert failure is not None
    assert "no_such_function" in failure


def test_a_malformed_reader_is_a_failure() -> None:
    assert "module:symbol" in (_reader_failure(read_by="sizing.size_long") or "")


# ------------------------------------------------------- the 19:30 second pass (DR-015 section 3)
#
# The second pass writes to the same log as the 18:30 run. `a.run_completes` counts the SCHEDULED
# attempt and nothing else, so the question these ask is not "does the second pass work" but "can
# the second pass be mistaken for the run Track A is measuring". It must not be, and the reason it
# is not must be a property of the words rather than of two numbers happening to differ by more
# than the tolerance.


def _second_pass_line(date_str: str, event: str, at: str = "19:30:01.00") -> str:
    return f"===== [Day {date_str} {at}] second pass {event} \n"


def test_a_second_pass_is_not_parsed_as_a_scheduled_attempt(tmp_path: Path) -> None:
    """A session whose 18:30 run crashed is a break, and a clean 19:30 pass must not paper over it.

    This is the failure mode that matters. If the second pass counted, every crashed evening would
    be rescued by its own retry and the counter would report a system that never fails - which is
    the opposite of what `a.run_completes` exists to measure.
    """
    log = (
        _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 0")
        + _second_pass_line(_WED, "starting") + _second_pass_line(_WED, "finished, exit 0")
    )
    code, out = _run_streak_gate(_streak_tree(tmp_path, log), "2026-08-12T22:00:00")

    assert code == 0
    assert "track A streak: 0" in out
    assert "most recent break: 2026-08-12 (no qualifying scheduled-window entry)" in out


def test_the_same_lines_worded_as_a_daily_run_would_have_counted(tmp_path: Path) -> None:
    """The positive control, and this pair is the whole point of the two tests.

    Identical timing, identical exit code, only the marker words differ - and at 19:30 the +-30
    minute window would exclude it anyway. So without this control the test above would pass for
    the wrong reason and go on passing if someone widened the tolerance. Written at 18:30 to hold
    the window constant, leaving the WORDS as the only variable.
    """
    counted = (
        _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 0")
        + _log_line(_WED, "starting") + _log_line(_WED, "finished, exit 0")
    )
    ignored = (
        _log_line(_TUE, "starting") + _log_line(_TUE, "finished, exit 0")
        + _second_pass_line(_WED, "starting", at="18:30:01.00")
        + _second_pass_line(_WED, "finished, exit 0", at="18:30:01.00")
    )

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _, counted_out = _run_streak_gate(_streak_tree(tmp_path / "a", counted), "2026-08-12T22:00:00")
    _, ignored_out = _run_streak_gate(_streak_tree(tmp_path / "b", ignored), "2026-08-12T22:00:00")

    assert "track A streak: 2/20" in counted_out, "the wording the parser knows"
    # Zero, not one: the streak walks BACKWARD from the most recent evaluable session, so a
    # Wednesday the parser cannot see breaks it before Tuesday is ever reached.
    assert "track A streak: 0" in ignored_out, "the same run, wearing the second pass's words"
    assert "most recent break: 2026-08-12" in ignored_out


def test_a_second_pass_never_displaces_the_scheduled_attempt(tmp_path: Path) -> None:
    """Both passes on the same evening: the streak still counts one session, not two, and it is the
    18:30 run's exit code that decides it."""
    log = "".join(
        _log_line(day, "starting") + _log_line(day, "finished, exit 0")
        + _second_pass_line(day, "starting") + _second_pass_line(day, "finished, exit 0")
        for day in (_TUE, _WED)
    )
    code, out = _run_streak_gate(_streak_tree(tmp_path, log), "2026-08-12T22:00:00")

    assert code == 0
    assert "track A streak: 2/20" in out
    assert "2026-08-11 to 2026-08-12" in out


def test_the_wrapper_and_the_parser_agree_on_the_marker_words() -> None:
    """Read from the two files rather than restated here, so this cannot drift into agreeing with
    itself. `daily_run.cmd` is the only thing that writes these lines and `track_a_streak.py` the
    only thing that reads them; a rename on one side is invisible until the counter is wrong.
    """
    import re

    wrapper = (TOOLS / "daily_run.cmd").read_text(encoding="utf-8")
    assert 'set PASS=daily run' in wrapper
    assert 'set PASS=second pass' in wrapper
    assert 'if /I "%~1"=="second-pass"' in wrapper, "the argument the scheduled task passes"

    sys.path.insert(0, str(TOOLS))
    import track_a_streak

    scheduled = "===== [Day 08/11/2026 18:30:01.00] daily run starting "
    second = "===== [Day 08/11/2026 19:30:01.00] second pass starting "
    assert track_a_streak._STARTING.match(scheduled), "the run Track A measures"
    assert not track_a_streak._STARTING.match(second), "and the pass it must never measure"
    assert re.search(r"second pass", wrapper), "the wrapper writes what the parser refuses"


def test_the_second_pass_does_not_pull_the_directory_again() -> None:
    """`DR-008` c3 attributes a pull to the session date the vendor's own `Last-Modified` reports.
    A second pull an hour later can only add a duplicate row or a refusal, on the one record whose
    entire value is being auditable."""
    wrapper = (TOOLS / "daily_run.cmd").read_text(encoding="utf-8")
    guard = wrapper.index('if "%SECOND%"=="0"')
    fetch = wrapper.index("fetch_directory.py")
    assert guard < fetch, "the directory pull must sit inside the first-pass guard"


def test_the_track_a_row_never_renders_a_bare_zero_after_a_restart() -> None:
    """`HANDOFF.md` section 5: "a bare zero after a deliberate reset is indistinguishable from an
    outage". `track_a_streak.py` follows that rule on its own console; this row did not.

    It went unnoticed because every zero so far also carried a break date, which gave the reader a
    cause. The 2026-08-22 restart truncated the countable window to sessions that have not happened
    yet, so `broke_at` became None and the row rendered `**0/20** consecutive clean sessions` and
    nothing else - in section 2, which `AGENTS.md` 10.5 makes the single owner of that number.
    """
    import sys as _sys

    _sys.path.insert(0, str(TOOLS))
    import track_a_streak

    state = _build_state()
    if not track_a_streak.LOG.is_file():
        pytest.skip("no data/daily_run.log in this checkout - the row reports UNAVAILABLE")

    _label, body = state._track_a_row()
    restart = track_a_streak.restarted_at(track_a_streak.clock_now())
    if restart is None:
        return  # no restart in force; the row has nothing to disclose

    assert str(restart[0]) in body, "the row must name the restart date"
    assert "deliberate restart" in body
    assert "not an outage" in body


def test_the_track_a_row_reads_the_same_clock_the_streak_counts_against(monkeypatch) -> None:
    """Two clocks in one measurement is how the restart line came to name a reset that had not
    happened yet at the instant the count was taken.

    Asserted by MOVING the clock rather than by scanning the source: a text search for
    `datetime.now(` trips on the comment explaining why it is not used, which is a test measuring
    its own prose.
    """
    import sys as _sys

    _sys.path.insert(0, str(TOOLS))
    import track_a_streak

    state = _build_state()
    if not track_a_streak.LOG.is_file():
        pytest.skip("no data/daily_run.log in this checkout - the row reports UNAVAILABLE")

    from datetime import timedelta

    # The DAY BEFORE the first restart. `restarted_at` compares dates, so a restart is in force
    # from midnight of its own date - an earlier hour on the same day is not "before" it.
    first_restart = min(d for d, _ in track_a_streak.STREAK_RESTARTS) - timedelta(days=1)

    monkeypatch.setenv("SWINGDESK_NOW", f"{first_restart}T09:00:00")
    _label, before = state._track_a_row()
    assert "deliberate restart" not in before, (
        "at an instant before the first restart there is nothing to disclose, and claiming one "
        "would be the row reading a clock the streak did not"
    )

    latest = max(d for d, _ in track_a_streak.STREAK_RESTARTS)
    monkeypatch.setenv("SWINGDESK_NOW", f"{latest}T23:00:00")
    _label, after = state._track_a_row()
    assert str(latest) in after and "deliberate restart" in after


# ------------------------------------------------------------------- gate 27: strategy cards


def _cards_tree(tmp_path: Path, card: str, name: str = "cards") -> Path:
    """A tree holding one card, the two registries it references, and its document.

    `name` exists so one test can build two trees - the both-directions cases below need a
    clean tree per assertion, and reusing the path silently tests the first one twice.
    """
    root = tmp_path / name
    (root / "registry").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "CARD.md").write_text("# card\n", encoding="utf-8")
    (root / "registry" / "cards.yml").write_text(card, encoding="utf-8")
    (root / "registry" / "components.yml").write_text(
        "components:\n"
        "  - component: M01-T0001-v1.0\n"
        "    activation: registered\n",
        encoding="utf-8",
    )
    (root / "registry" / "parameters.yml").write_text(
        "parameters:\n"
        "  - id: rs.lookback\n"
        "    status: unset\n"
        "  - id: exit.max_holding_period\n"
        "    status: assumed\n",
        encoding="utf-8",
    )
    return root


_MINIMAL = """cards:
  - card: CARD-001
    version: 1
    status: Untested
    document: docs/CARD.md
    scope:
      holding_horizon: exit.max_holding_period
    components: [M01-T0001-v1.0]
    evidence: null
"""


def test_a_card_whose_references_resolve_passes(tmp_path: Path) -> None:
    code, out = run_gate("verify_cards.py", _cards_tree(tmp_path, _MINIMAL))
    assert code == 0, out


def test_a_card_naming_a_component_that_does_not_exist_fails(tmp_path: Path) -> None:
    """`STRATEGY_CARD_SPEC` §5 rule 1: a card REFERENCES components. A reference nobody can follow
    is the failure gate 1 catches for `read_by` and gate 20 for `implemented_by`."""
    card = _MINIMAL.replace("[M01-T0001-v1.0]", "[M99-T9999-v1.0]")
    code, out = run_gate("verify_cards.py", _cards_tree(tmp_path, card))
    assert code == 1
    assert "does not resolve in components.yml" in out


def test_a_card_citing_an_unset_input_must_declare_it_blocked(tmp_path: Path) -> None:
    """The rule that matters most. An unset parameter makes its component refuse - that is the
    design working - but a card depending on one while claiming to be runnable is the
    'specified, wired to nothing' shape one layer up."""
    card = _MINIMAL.replace(
        "    components:", "    selection:\n      lookback: rs.lookback\n    components:")
    code, out = run_gate("verify_cards.py", _cards_tree(tmp_path, card))
    assert code == 1
    assert "declares no `blocked_by`" in out

    declared = card.replace(
        "    evidence: null", "    blocked_by:\n      - id: unset-selection\n        what: it is\n"
                              "    evidence: null")
    code, out = run_gate("verify_cards.py", _cards_tree(tmp_path, declared, "declared"))
    assert code == 0, out


def test_a_card_cannot_carry_evidence_without_being_validated(tmp_path: Path) -> None:
    """And cannot be `Validated` without evidence. Both directions, because a status and its
    warrant drifting apart is how something looks more validated than it is."""
    claimed = _MINIMAL.replace("    evidence: null", "    evidence: PR-999")
    code, out = run_gate("verify_cards.py", _cards_tree(tmp_path, claimed))
    assert code == 1
    assert "carries evidence" in out

    bare = _MINIMAL.replace("status: Untested", "status: Validated")
    code, out = run_gate("verify_cards.py", _cards_tree(tmp_path, bare, "bare"))
    assert code == 1
    assert "requires an evidence id" in out


def test_a_card_whose_document_is_missing_fails(tmp_path: Path) -> None:
    """A card is a reviewable artefact. Half of it living nowhere is not reviewable."""
    card = _MINIMAL.replace("docs/CARD.md", "docs/NOT_THERE.md")
    code, out = run_gate("verify_cards.py", _cards_tree(tmp_path, card))
    assert code == 1
    assert "is not a file" in out


def test_no_cards_file_is_not_a_failure(tmp_path: Path) -> None:
    """A tree with no cards is a tree before P5, not a broken one."""
    root = tmp_path / "empty"
    (root / "registry").mkdir(parents=True)
    code, out = run_gate("verify_cards.py", root)
    assert code == 0, out
