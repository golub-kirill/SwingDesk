"""`tools/update_checkout.py`: the morning pull that the evening run's `HANDOFF.md` used to block.

Exercised against real repositories - an upstream that moves on, and a clone the evening run has
dirtied - because the thing that could silently be wrong is git's behaviour, not the Python.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"

COMMITTED = """# HANDOFF

Prose a person wrote.

<!-- BEGIN GENERATED: state:repo -->
| studies | 20 |
<!-- END GENERATED: state:repo -->

Prose between the blocks.

<!-- BEGIN GENERATED: state:runtime -->
| Track A | 0/20 |
<!-- END GENERATED: state:runtime -->
"""

#: What a merged PR does to the file: its generated repo block moves, and so may the prose.
MERGED = COMMITTED.replace("| studies | 20 |", "| studies | 21 |").replace(
    "Prose a person wrote.", "Prose a person wrote, amended by a merged PR."
)

#: What the evening run does to it: only a block derived from `data/` moves.
EVENING = COMMITTED.replace("| Track A | 0/20 |", "| Track A | 1/20 |")


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("update_checkout", TOOLS / "update_checkout.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def _identify(root: Path) -> None:
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")


def _head(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    """(upstream, local): the clone is one merged PR behind, and that PR rewrote `HANDOFF.md`."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(upstream, "init", "-q", "-b", "master")
    _identify(upstream)
    (upstream / "HANDOFF.md").write_text(COMMITTED, encoding="utf-8")
    (upstream / "thing.py").write_text("x = 1\n", encoding="utf-8")
    _git(upstream, "add", "-A")
    _git(upstream, "commit", "-q", "-m", "base")

    local = tmp_path / "local"
    assert _git(tmp_path, "clone", "-q", str(upstream), str(local)).returncode == 0
    _identify(local)

    (upstream / "HANDOFF.md").write_text(MERGED, encoding="utf-8")
    _git(upstream, "commit", "-q", "-am", "a merged PR")
    return upstream, local


@pytest.fixture
def regenerated(monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, list[Path]]:
    """The tool, with `build_state.py` replaced by a recorder - the fixture repo has none."""
    tool = _tool()
    calls: list[Path] = []
    monkeypatch.setattr(tool, "regenerate", calls.append)
    # And an idle schedule. These cases are about the pull; the guard has its own below, and CI has
    # no Task Scheduler at all - left real, every one of them would refuse instead of pulling.
    monkeypatch.setattr(tool, "running_pass", lambda *args, **kwargs: "")
    return tool, calls


def test_the_fixture_reproduces_the_pull_that_failed(repos: tuple[Path, Path]) -> None:
    """Without the tool, the evening run's leftover blocks the pull - the 2026-09-13 failure."""
    _, local = repos
    (local / "HANDOFF.md").write_text(EVENING, encoding="utf-8")
    pull = _git(local, "pull", "--ff-only")
    assert pull.returncode != 0
    assert "HANDOFF.md" in pull.stderr


def test_the_evening_runs_blocks_are_discarded_and_the_pull_lands(
    repos: tuple[Path, Path], regenerated: tuple[ModuleType, list[Path]]
) -> None:
    upstream, local = repos
    tool, calls = regenerated
    (local / "HANDOFF.md").write_text(EVENING, encoding="utf-8")

    assert tool.update(local) == 0
    assert _head(local) == _head(upstream)
    assert (local / "HANDOFF.md").read_text(encoding="utf-8") == MERGED
    assert calls == [local], "and the blocks are written back afterwards"


def test_a_clean_checkout_pulls_and_regenerates(
    repos: tuple[Path, Path], regenerated: tuple[ModuleType, list[Path]]
) -> None:
    """Nothing to discard is not a reason to skip the rebuild: the pulled runtime block is stale."""
    upstream, local = repos
    tool, calls = regenerated
    assert tool.update(local) == 0
    assert _head(local) == _head(upstream)
    assert calls == [local]


def test_a_hand_edit_outside_the_blocks_is_refused_and_nothing_moves(
    repos: tuple[Path, Path], regenerated: tuple[ModuleType, list[Path]]
) -> None:
    _, local = repos
    tool, calls = regenerated
    before = _head(local)
    edited = EVENING.replace("Prose between the blocks.", "A note the owner typed.")
    (local / "HANDOFF.md").write_text(edited, encoding="utf-8")

    assert tool.update(local) == tool.REFUSED
    assert _head(local) == before
    assert (local / "HANDOFF.md").read_text(encoding="utf-8") == edited
    assert calls == []


def test_a_removed_marker_counts_as_a_hand_edit(
    repos: tuple[Path, Path], regenerated: tuple[ModuleType, list[Path]]
) -> None:
    """A block without its END marker is no longer a block, so its body is text somebody changed."""
    _, local = repos
    tool, _ = regenerated
    broken = COMMITTED.replace("<!-- END GENERATED: state:runtime -->\n", "")
    (local / "HANDOFF.md").write_text(broken, encoding="utf-8")

    assert tool.update(local) == tool.REFUSED
    assert (local / "HANDOFF.md").read_text(encoding="utf-8") == broken


def test_another_modified_tracked_file_is_refused(
    repos: tuple[Path, Path], regenerated: tuple[ModuleType, list[Path]]
) -> None:
    """Even alongside a discardable `HANDOFF.md`: one refusal leaves the whole tree as it was."""
    _, local = repos
    tool, calls = regenerated
    (local / "HANDOFF.md").write_text(EVENING, encoding="utf-8")
    (local / "thing.py").write_text("x = 2\n", encoding="utf-8")

    assert tool.update(local) == tool.REFUSED
    assert (local / "HANDOFF.md").read_text(encoding="utf-8") == EVENING
    assert (local / "thing.py").read_text(encoding="utf-8") == "x = 2\n"
    assert calls == []


def test_a_staged_handoff_is_refused(
    repos: tuple[Path, Path], regenerated: tuple[ModuleType, list[Path]]
) -> None:
    """The evening run never stages anything, so a staged file is a person's."""
    _, local = repos
    tool, _ = regenerated
    (local / "HANDOFF.md").write_text(EVENING, encoding="utf-8")
    _git(local, "add", "HANDOFF.md")

    assert tool.update(local) == tool.REFUSED
    assert "HANDOFF.md" in _git(local, "diff", "--cached", "--name-only").stdout


def test_a_dry_run_changes_nothing(
    repos: tuple[Path, Path], regenerated: tuple[ModuleType, list[Path]]
) -> None:
    _, local = repos
    tool, calls = regenerated
    before = _head(local)
    (local / "HANDOFF.md").write_text(EVENING, encoding="utf-8")

    assert tool.update(local, dry_run=True) == 0
    assert _head(local) == before
    assert (local / "HANDOFF.md").read_text(encoding="utf-8") == EVENING
    assert calls == []


def test_a_failed_pull_still_puts_the_blocks_back(
    repos: tuple[Path, Path], regenerated: tuple[ModuleType, list[Path]]
) -> None:
    """A local commit makes `--ff-only` refuse. The discard already happened, so the rebuild must."""
    _, local = repos
    tool, calls = regenerated
    (local / "thing.py").write_text("x = 3\n", encoding="utf-8")
    _git(local, "commit", "-q", "-am", "a local commit")
    before = _head(local)
    (local / "HANDOFF.md").write_text(EVENING, encoding="utf-8")

    assert tool.update(local) == tool.PULL_FAILED
    assert _head(local) == before
    assert calls == [local]


def test_the_skeleton_keeps_the_markers_and_drops_only_the_bodies() -> None:
    tool = _tool()
    crlf = EVENING.replace("\n", "\r\n")
    assert tool.skeleton(crlf) == tool.skeleton(COMMITTED)
    assert "| Track A |" not in tool.skeleton(EVENING)
    assert tool.skeleton(EVENING).count("GENERATED: state:runtime") == 2
    assert "Prose between the blocks." in tool.skeleton(EVENING)


# ------------------------------------------- the schedule guard, measured the hard way 2026-09-15


@pytest.fixture
def with_schedule(monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, list[Path]]:
    """The tool with its REAL guard - these cases ARE the guard, so nothing stands in for it."""
    tool = _tool()
    calls: list[Path] = []
    monkeypatch.setattr(tool, "regenerate", calls.append)
    return tool, calls


def _scheduler(running: str | None = None, unreadable: tuple[str, ...] = ()):
    """A Task Scheduler that reports `running` as running, and cannot read `unreadable`."""
    def _probe(task: str) -> dict[str, str] | None:
        if task in unreadable:
            return None
        return {"Status": "Running" if task == running else "Ready"}
    return _probe


def test_a_running_pass_stops_the_pull(
    repos: tuple[Path, Path], with_schedule: tuple[ModuleType, list[Path]], capsys
) -> None:
    """THE REGRESSION, measured 2026-09-15 on the owner's machine.

    The pull landed while the 18:30 pass was running. `cmd.exe` reads a batch file AS IT RUNS, by
    byte offset, so the pass resumed inside a comment of the sixteen-lines-longer `daily_run.cmd`
    and died on `'approval' is not recognized` - before restoring protection, on an evening a stop
    had just been cancelled. Nothing in the tool stopped it; a line in a docstring asked.
    """
    _, local = repos
    tool, calls = with_schedule
    before = _head(local)
    (local / "HANDOFF.md").write_text(EVENING, encoding="utf-8")

    assert tool.update(local, probe=_scheduler(running="SwingDesk daily run")) == tool.REFUSED

    assert _head(local) == before, "the code a running pass is reading did not move"
    assert (local / "HANDOFF.md").read_text(encoding="utf-8") == EVENING
    assert calls == []
    assert "SwingDesk daily run" in capsys.readouterr().out


def test_the_second_pass_counts_too(
    repos: tuple[Path, Path], with_schedule: tuple[ModuleType, list[Path]]
) -> None:
    """Both passes run the same wrapper, so both are broken by the same pull."""
    _, local = repos
    tool, _ = with_schedule
    before = _head(local)

    assert tool.update(local, probe=_scheduler(running="SwingDesk second pass")) == tool.REFUSED
    assert _head(local) == before


def test_an_idle_schedule_lets_the_pull_through(
    repos: tuple[Path, Path], with_schedule: tuple[ModuleType, list[Path]]
) -> None:
    """The guard costs nothing on every other evening of the week."""
    upstream, local = repos
    tool, calls = with_schedule

    assert tool.update(local, probe=_scheduler()) == 0
    assert _head(local) == _head(upstream)
    assert calls == [local]


def test_an_unreadable_scheduler_refuses_and_names_the_way_past(
    repos: tuple[Path, Path], with_schedule: tuple[ModuleType, list[Path]], capsys
) -> None:
    """Not knowing is not knowing it is idle, and the permissive reading is what cost an evening.
    The refusal names `--anyway`, so an operator is never stuck behind it."""
    _, local = repos
    tool, calls = with_schedule
    before = _head(local)

    assert tool.update(local, probe=_scheduler(unreadable=("SwingDesk daily run",))) == tool.REFUSED

    assert _head(local) == before
    assert calls == []
    printed = capsys.readouterr().out
    assert "could not be read" in printed and "--anyway" in printed


def test_anyway_skips_the_check_entirely(
    repos: tuple[Path, Path], with_schedule: tuple[ModuleType, list[Path]]
) -> None:
    """The escape hatch asks the scheduler nothing - a probe that would fail proves it."""
    upstream, local = repos
    tool, calls = with_schedule

    def _explode(task: str):
        raise AssertionError(f"the scheduler was asked about {task}")

    assert tool.update(local, anyway=True, probe=_explode) == 0
    assert _head(local) == _head(upstream)
    assert calls == [local]


def test_a_dry_run_is_refused_while_a_pass_runs(
    repos: tuple[Path, Path], with_schedule: tuple[ModuleType, list[Path]]
) -> None:
    """`--dry-run` says what would happen, and what would happen is this refusal."""
    _, local = repos
    tool, _ = with_schedule

    assert tool.update(
        local, dry_run=True, probe=_scheduler(running="SwingDesk daily run")) == tool.REFUSED


def test_running_pass_separates_idle_from_unreadable() -> None:
    tool = _tool()
    tasks = ("SwingDesk daily run", "SwingDesk second pass")

    assert tool.running_pass(tasks, _scheduler()) == "", "idle is an empty name, never None"
    assert tool.running_pass(tasks, _scheduler(running=tasks[1])) == tasks[1]
    assert tool.running_pass(tasks, _scheduler(unreadable=tasks)) is None
    assert tool.running_pass(
        tasks, _scheduler(running=tasks[1], unreadable=(tasks[0],))) == tasks[1], (
        "a pass the scheduler CAN see running outranks one it could not read"
    )


def test_running_pass_reads_status_and_not_the_enabled_state() -> None:
    """`Scheduled Task State` says whether a task is enabled, which is true all day. The field that
    moves is `Status` - the distinction `wait_for_first_pass.py` was written around."""
    tool = _tool()

    def _enabled_only(task: str) -> dict[str, str]:
        return {"Scheduled Task State": "Enabled", "Status": "Ready"}

    assert tool.running_pass(("SwingDesk daily run",), _enabled_only) == ""


def test_the_defaults_ask_the_real_scheduler_about_both_passes() -> None:
    """Every case above injects a probe, so the WIRING is what nothing else would catch: a default
    that named one task, or a probe that asked nothing, would pass all of them and protect neither
    pass on the owner's machine."""
    import inspect

    tool = _tool()
    for function in (tool.update, tool.running_pass):
        defaults = inspect.signature(function).parameters
        assert tuple(defaults["tasks"].default) == tuple(tool.schedule.RUN_TASKS)
        assert defaults["probe"].default is tool.schedule.query_task
    assert tool.schedule.RUN_TASKS == ("SwingDesk daily run", "SwingDesk second pass")
