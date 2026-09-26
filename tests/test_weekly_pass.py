"""A weekly pass fired daily: it runs once a week, and a killed or missed one runs the next day."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import weekly_pass  # noqa: E402

CDT = timezone(timedelta(hours=-5))
SUNDAY = datetime(2026, 9, 20, 11, 0, tzinfo=CDT)


def test_the_week_starts_at_the_most_recent_sunday_midnight() -> None:
    assert weekly_pass.week_start(SUNDAY) == datetime(2026, 9, 20, tzinfo=CDT)
    assert weekly_pass.week_start(SUNDAY + timedelta(days=6, hours=12)) == \
        datetime(2026, 9, 20, tzinfo=CDT), "Saturday night is still the same week"
    assert weekly_pass.week_start(SUNDAY + timedelta(days=7)) == datetime(2026, 9, 27, tzinfo=CDT)


def test_a_pass_killed_on_sunday_runs_on_monday_and_again_the_next_sunday(tmp_path: Path) -> None:
    """The cadence the anchor keeps: a threshold in days would move the schedule to Monday."""
    assert weekly_pass.is_due(tmp_path, "coverage", SUNDAY), "never run"
    # Sunday's run is killed: nothing is recorded. Monday's trigger finds it still due.
    monday = SUNDAY + timedelta(days=1)
    assert weekly_pass.is_due(tmp_path, "coverage", monday)
    weekly_pass.record_done(tmp_path, "coverage", monday + timedelta(minutes=30))
    for later in range(1, 6):          # Tuesday to Saturday
        assert not weekly_pass.is_due(tmp_path, "coverage", monday + timedelta(days=later))
    assert weekly_pass.is_due(tmp_path, "coverage", SUNDAY + timedelta(days=7)), \
        "back on Sunday, not drifted to Monday"


def test_names_are_independent_and_a_bad_stamp_means_run(tmp_path: Path) -> None:
    weekly_pass.record_done(tmp_path, "remeasure-PR-019b", SUNDAY)
    assert not weekly_pass.is_due(tmp_path, "remeasure-PR-019b", SUNDAY + timedelta(hours=1))
    assert weekly_pass.is_due(tmp_path, "remeasure-PR-016", SUNDAY + timedelta(hours=1))
    weekly_pass.stamp_path(tmp_path, "coverage").parent.mkdir(parents=True, exist_ok=True)
    weekly_pass.stamp_path(tmp_path, "coverage").write_text("not a time", encoding="utf-8")
    assert weekly_pass.is_due(tmp_path, "coverage", SUNDAY), "an unreadable stamp runs the pass"


def test_main_answers_in_exit_codes(tmp_path: Path, capsys) -> None:
    args = ["due", "coverage", "--data", str(tmp_path)]
    assert weekly_pass.main(args, now=SUNDAY) == 0
    assert weekly_pass.main(["done", "coverage", "--data", str(tmp_path)], now=SUNDAY) == 0
    assert weekly_pass.main(args, now=SUNDAY + timedelta(days=2)) == weekly_pass.NOT_DUE
    assert "already finished this week" in capsys.readouterr().out


# ------------------------------------------------------------------ the wrappers themselves
#
# The logic that matters lives in batch files - `goto`, `errorlevel`, exit codes - and a text search
# cannot tell whether they run. So each wrapper is copied into a scratch tree with a real
# interpreter, the real `weekly_pass.py`, and fake passes whose exit code the test chooses, and run.

pytestmark_windows = pytest.mark.skipif(sys.platform != "win32", reason="batch wrappers")

FAKE_PASS = '''import os, sys
from pathlib import Path
study = sys.argv[1] if sys.argv[1:2] and not sys.argv[1].startswith("-") else ""
name = Path(sys.argv[0]).stem + ("-" + study if study else "")
Path(os.environ["RAN"]).open("a").write(name + "\\n")
raise SystemExit(int(os.environ.get("RC_" + name.replace("-", "_"), "0")))
'''


@pytest.fixture(scope="module")
def scratch_python(tmp_path_factory) -> Path:
    """A throwaway virtual environment: the wrappers insist on `.venv\\Scripts\\python.exe`."""
    root = tmp_path_factory.mktemp("venv")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")],
                   check=True, capture_output=True)
    return root / ".venv"


def _tree(tmp_path: Path, venv: Path, wrapper: str, fakes: tuple[str, ...]) -> Path:
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    (root / "data").mkdir()
    shutil.copytree(venv, root / ".venv")
    shutil.copy(REPO / "tools" / wrapper, root / "tools" / wrapper)
    shutil.copy(REPO / "tools" / "weekly_pass.py", root / "tools" / "weekly_pass.py")
    for fake in fakes:
        (root / "tools" / fake).write_text(FAKE_PASS, encoding="utf-8")
    return root


def _run(root: Path, wrapper: str, **codes: str) -> tuple[int, list[str]]:
    ran = root / "ran.txt"
    ran.unlink(missing_ok=True)
    env = {**os.environ, "RAN": str(ran), **codes}
    code = subprocess.run(["cmd", "/c", str(root / "tools" / wrapper)], env=env,
                          capture_output=True).returncode
    return code, ran.read_text().split() if ran.exists() else []


@pytestmark_windows
@pytest.mark.parametrize(("wrapper", "name", "fake"), [
    ("widen_universe.cmd", "coverage", "refresh_universe.py"),
    ("widen_classifications.cmd", "classification", "refresh_classifications.py"),
])
def test_a_weekly_wrapper_runs_once_a_week_and_retries_a_crash(
        tmp_path: Path, scratch_python: Path, wrapper: str, name: str, fake: str) -> None:
    root = _tree(tmp_path, scratch_python, wrapper, ("preflight.py", fake, "build_state.py"))
    step = fake.removesuffix(".py")

    assert _run(root, wrapper, **{f"RC_{step}": "1"}) == (1, ["preflight", step, "build_state"])
    assert not weekly_pass.stamp_path(root / "data", name).exists(), "a crash records nothing"

    assert _run(root, wrapper, **{f"RC_{step}": "2"})[0] == 2, "the retry runs; a refusal is clean"
    assert weekly_pass.stamp_path(root / "data", name).exists()

    assert _run(root, wrapper) == (0, []), "done this week: nothing runs, not even preflight"

    weekly_pass.stamp_path(root / "data", name).unlink()
    assert _run(root, wrapper)[0] == 0
    assert weekly_pass.stamp_path(root / "data", name).exists(), "a clean 0 is done too"


@pytestmark_windows
def test_the_remeasure_wrapper_retries_only_the_study_that_did_not_finish(
        tmp_path: Path, scratch_python: Path) -> None:
    """A second PR-019b point in one week is the search AGENTS.md 19.7 forbids."""
    root = _tree(tmp_path, scratch_python, "remeasure.cmd", ("remeasure.py",))

    code, ran = _run(root, "remeasure.cmd", RC_remeasure_PR_016="1")
    assert (code, ran) == (1, ["remeasure-PR-019b", "remeasure-PR-016"]), \
        "PR-016 runs whatever PR-019b returned, and its failure is the exit code"

    assert _run(root, "remeasure.cmd") == (0, ["remeasure-PR-016"]), "PR-019b is not re-drawn"
    assert _run(root, "remeasure.cmd") == (0, []), "both done: nothing runs"

    (root / "data" / "weekly" / "remeasure-PR-019b.done").unlink()
    (root / "data" / "weekly" / "remeasure-PR-016.done").unlink()
    code, ran = _run(root, "remeasure.cmd", RC_remeasure_PR_019b="1")
    assert (code, ran) == (1, ["remeasure-PR-019b", "remeasure-PR-016"]), \
        "the FIRST failure is the exit code, and a clean PR-016 does not overwrite it"
