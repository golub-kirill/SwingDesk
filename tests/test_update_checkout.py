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
