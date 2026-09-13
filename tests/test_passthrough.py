"""Operational scripts as `swingdesk` subcommands: the same script, the same interpreter, the
arguments untouched. Two lists must never drift - the mapping and the parsers README can see."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from swingdesk.presentation import cli, passthrough


def test_every_tool_command_reaches_its_script_with_arguments_untouched(monkeypatch) -> None:
    seen: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(cli, "run_tool", lambda name, rest: seen.append((name, list(rest))) or 0)
    for name in passthrough.TOOL_COMMANDS:
        assert cli.main([name, "--help", "--budget", "5"]) == 0
    assert seen == [(name, ["--help", "--budget", "5"]) for name in passthrough.TOOL_COMMANDS]


def test_every_tool_command_is_listed_in_the_readme_reference() -> None:
    """The goal, checked where it lives: README.md's generated reference names each command.

    The first version of this test searched `cli.py` for `add_parser("name"` and passed while
    README.md listed none of the six - `tools/build_commands.py` recognises only an ASSIGNED
    `add_parser` call, and the first cut used bare ones. A test of the source was green for a
    reason that had nothing to do with what it was named for.
    """
    readme = (passthrough.REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for name in passthrough.TOOL_COMMANDS:
        assert f"`swingdesk {name}`" in readme, name


def test_every_mapped_script_exists_in_the_checkout() -> None:
    for script in passthrough.TOOL_COMMANDS.values():
        assert (passthrough.REPO_ROOT / "tools" / script).is_file(), script


def test_a_missing_script_is_unavailable_not_a_crash(tmp_path, capsys) -> None:
    assert passthrough.run_tool("budget", [], repo_root=tmp_path) == 2
    assert "UNAVAILABLE" in capsys.readouterr().err


def test_the_script_runs_with_this_interpreter_from_the_checkout(tmp_path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "trial_budget.py").write_text("", encoding="utf-8")
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=7)

    assert passthrough.run_tool("budget", ["--budget", "5"], repo_root=tmp_path,
                                runner=runner) == 7
    command, kwargs = calls[0]
    assert command == [sys.executable, "-X", "utf8",
                       str(tmp_path / "tools" / "trial_budget.py"), "--budget", "5"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["env"]["PYTHONPATH"] == str(tmp_path / "src")
