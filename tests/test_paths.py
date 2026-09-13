"""Where `--data` points when nobody said.

`DEFAULT_DATA = Path("data")` was relative to the folder the command was typed in, so `pending` run
from anywhere else read an empty directory and answered "nothing pending" - a confident answer about
the wrong book. Four rules, first match wins, and each is pinned here.
"""

from __future__ import annotations

from pathlib import Path

from swingdesk.presentation import paths
from swingdesk.presentation.paths import ENV, default_data


def test_the_environment_wins(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    chosen = tmp_path / "elsewhere"
    assert default_data(cwd=tmp_path, environ={ENV: str(chosen)}, repo_root=tmp_path) == chosen


def test_an_empty_environment_value_is_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    assert default_data(cwd=tmp_path, environ={ENV: ""}, repo_root=repo) == repo / "data"


def test_a_data_directory_here_wins_over_the_checkout(tmp_path: Path) -> None:
    here, repo = tmp_path / "here", tmp_path / "repo"
    (here / "data").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    assert default_data(cwd=here, environ={}, repo_root=repo) == here / "data"


def test_from_anywhere_else_the_checkouts_data_is_found(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    assert default_data(cwd=tmp_path, environ={}, repo_root=repo) == repo / "data"


def test_with_no_data_anywhere_the_old_relative_default_stands(tmp_path: Path) -> None:
    """A missing directory still fails where it always failed, not somewhere new."""
    assert default_data(cwd=tmp_path, environ={}, repo_root=tmp_path / "repo") == Path("data")


def test_repo_root_is_the_checkout() -> None:
    assert (paths.REPO_ROOT / "pyproject.toml").is_file()


def test_the_fee_schedule_does_not_depend_on_the_folder_the_command_ran_in() -> None:
    from swingdesk.validation.backtest.fees import DEFAULT_SCHEDULE_PATH

    assert DEFAULT_SCHEDULE_PATH.is_absolute()
    assert DEFAULT_SCHEDULE_PATH.is_file()
