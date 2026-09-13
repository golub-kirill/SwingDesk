"""The Task Scheduler, read once. Gate 26 and `swingdesk status` must agree on what a result means,
so they share one parser - a second copy is how `267009` (still running) was once called a crash."""

from __future__ import annotations

import pytest

from swingdesk.platform import schedule

RECORD = {
    "Scheduled Task State": "Enabled",
    "Next Run Time": "9/14/2026 6:30:00 PM",
    "Last Run Time": "9/11/2026 6:30:00 PM",
    "Last Result": "0",
}


def test_off_windows_nothing_is_read(monkeypatch) -> None:
    monkeypatch.setattr(schedule.sys, "platform", "linux")
    assert schedule.read("SwingDesk daily run") is None


def test_a_task_that_is_not_registered_reads_none(monkeypatch) -> None:
    monkeypatch.setattr(schedule.sys, "platform", "win32")
    monkeypatch.setattr(schedule, "query_task", lambda task: None)
    assert schedule.read("SwingDesk daily run") is None


def test_one_task_is_summarised(monkeypatch) -> None:
    monkeypatch.setattr(schedule.sys, "platform", "win32")
    monkeypatch.setattr(schedule, "query_task", lambda task: dict(RECORD))
    assert schedule.read("SwingDesk daily run") == schedule.TaskReading(
        task="SwingDesk daily run", state="Enabled", next_run="9/14/2026 6:30:00 PM",
        last_run="9/11/2026 6:30:00 PM", judgement="clean", phrase="exit 0")


@pytest.mark.parametrize(("code", "judgement"),
                         [("267009", "pending"), ("-1", "crash"), ("2", "clean")])
def test_the_result_is_judged_by_the_shared_verdict(monkeypatch, code, judgement) -> None:
    monkeypatch.setattr(schedule.sys, "platform", "win32")
    monkeypatch.setattr(schedule, "query_task", lambda task: {**RECORD, "Last Result": code})
    reading = schedule.read("SwingDesk daily run")
    assert reading is not None and reading.judgement == judgement


def test_the_run_tasks_lead_the_task_list() -> None:
    assert schedule.TASKS[: len(schedule.RUN_TASKS)] == schedule.RUN_TASKS
