"""`tools/wait_for_first_pass.py`: the second pass waits for the first, and never suppresses itself
on a scheduler it could not read. Owner ruling 2026-09-14."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]


def _tool() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location("_wait_for_first_pass",
                                                  REPO / "tools" / "wait_for_first_pass.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _states(*answers):  # type: ignore[no-untyped-def]
    queue = list(answers)
    return lambda task: queue.pop(0)


def test_a_finished_run_lets_the_pass_go_at_once() -> None:
    tool = _tool()
    slept: list[float] = []
    assert tool.wait(probe=_states(False), sleep=slept.append, say=lambda _: None) == tool.FREE
    assert slept == []


def test_a_running_first_pass_is_waited_for() -> None:
    tool = _tool()
    slept: list[float] = []
    said: list[str] = []
    code = tool.wait(limit_minutes=5, poll_seconds=60, probe=_states(True, True, False),
                     sleep=slept.append, say=said.append)
    assert code == tool.FREE
    assert slept == [60, 60]
    assert "still running" in said[0] and "finished" in said[-1]


def test_a_run_still_going_at_the_limit_skips_the_pass() -> None:
    tool = _tool()
    slept: list[float] = []
    said: list[str] = []
    code = tool.wait(limit_minutes=3, poll_seconds=60, probe=lambda task: True, sleep=slept.append,
                     say=said.append)
    assert code == tool.STILL_RUNNING
    assert slept == [60, 60, 60], "three minutes, asked four times, never a sleep past the limit"
    assert "skipped" in said[-1]


def test_an_unreadable_scheduler_runs_the_pass() -> None:
    """Unavailable is not a reason to skip: an unmeasured condition must not suppress a pass."""
    tool = _tool()
    assert tool.wait(probe=lambda task: None, sleep=lambda _: None, say=lambda _: None) == tool.UNAVAILABLE


@pytest.mark.parametrize(("record", "expected"), [
    ({"Status": "Running", "Scheduled Task State": "Enabled"}, True),
    ({"Status": "Ready", "Scheduled Task State": "Enabled"}, False),
    ({"Status": "", "Scheduled Task State": "Enabled"}, False),
    (None, None),
])
def test_running_reads_the_status_field_not_the_enabled_state(record, expected,  # type: ignore[no-untyped-def]
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool()
    monkeypatch.setattr(tool.schedule, "query_task", lambda task: record)
    assert tool.running("SwingDesk daily run") is expected


def test_the_wrapper_waits_before_it_reads_the_journal() -> None:
    """Order in `daily_run.cmd`: the wait sits in the second-pass branch, before `retry_needed.py`,
    which reads the store the first pass may still hold."""
    text = (REPO / "tools" / "daily_run.cmd").read_text(encoding="utf-8")
    branch = text.index('if not "%SECOND%"=="1" goto :attempt')
    waits = text.index("wait_for_first_pass.py")
    reads = text.index("retry_needed.py\" --data")
    assert branch < waits < reads
    assert "goto :first_still_running" in text and ":first_still_running" in text
