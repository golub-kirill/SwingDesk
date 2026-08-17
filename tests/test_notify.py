"""The run notice (`DR-011`): what it may say, and that it can never break a run.

Nothing here raises a real desktop notification. `subprocess.run` is replaced in every case that
reaches it, so the suite stays offline, silent and fast - and, more to the point, so the failure
paths can be exercised at all. A notifier is mostly failure paths.
"""

from __future__ import annotations

import inspect
import re
import subprocess

import pytest

from swingdesk.presentation import notify

#: The whole permitted shape. `DR-011` fixes the notice at a terminal status, an optional
#: reference, and a fixed trailer chosen from a table - this pattern is the mechanical form of
#: that rule, and if it needs relaxing the decision record has to change first.
BODY = re.compile(
    r"^run (complete|complete, report NOT written|REFUSED)"
    r"( - run-[A-Za-z0-9-]+)?\. "
    r"(Report on disk|Nothing on disk - see the log|No run was recorded - see the log)\.$"
)


def test_the_body_is_a_status_and_a_reference_and_nothing_else() -> None:
    for outcome in notify.Outcome:
        assert BODY.match(notify.body("run-20260817T183001Z-a1b2c3d4", outcome))


def test_a_refusal_renders_without_a_fabricated_reference() -> None:
    """A refusal can happen before any run is journalled, so there is no id. `None` must render as
    no reference at all - "run REFUSED - unknown" would be a manufactured identifier."""
    rendered = notify.body(None, notify.Outcome.REFUSED)
    assert BODY.match(rendered)
    assert "None" not in rendered
    # The status is followed straight by its period - no dangling reference separator. Asserted
    # this way rather than as `" - " not in rendered`, which was the first draft and was wrong:
    # the trailer legitimately contains a dash ("No run was recorded - see the log").
    assert rendered.startswith("run REFUSED. ")


def test_the_trailer_never_promises_a_report_that_was_not_written() -> None:
    """Found by review 2026-08-16: the trailer was the fixed string "Report on disk." and was sent
    even when `report.write` had just raised, telling the owner to go read a file that is not
    there while the only word of the failure sat on stderr in the log.
    """
    assert "Report on disk." in notify.body("run-1", notify.Outcome.COMPLETE)
    for silent in (notify.Outcome.COMPLETE_NO_REPORT, notify.Outcome.REFUSED):
        assert "Report on disk." not in notify.body("run-1", silent)
        assert "see the log" in notify.body("run-1", silent)


def test_the_body_cannot_be_given_anything_to_leak() -> None:
    """The content rule is enforced by the SIGNATURE, not by review.

    `DR-011` bans candidate counts, tickers and decision words from the notice - not for privacy
    (a local toast sends nothing anywhere) but because a glanceable summary is one the owner can
    act on without the report's provenance, validation status and Untested banner. Two parameters
    means there is no `RunResult` in scope to interpolate. Adding a third is a visible act in
    review rather than a quiet f-string somewhere in the caller.
    """
    assert list(inspect.signature(notify.body).parameters) == ["run_id", "outcome"]


@pytest.mark.parametrize("banned", ["Trade", "Watch", "Skip", "Pause", "candidate"])
def test_the_decision_vocabulary_never_reaches_the_notice(banned: str) -> None:
    for outcome in notify.Outcome:
        assert banned not in notify.body("run-20260817T183001Z-a1b2c3d4", outcome)


def _completed(returncode: int, stderr: str = "", stdout: str = ""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_a_delivered_notice_reports_delivered(monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(0))
    assert notify.notify("run-1", notify.Outcome.COMPLETE) == notify.NotifyResult(True, "delivered")


def test_a_missing_powershell_is_reported_not_raised(monkeypatch) -> None:
    """Not Windows, or PowerShell absent. A fact about the machine, not a fault in the run - and
    it must arrive as a value the caller can print, never as an exception escaping into a run that
    has already finished and already written its report."""
    def absent(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", absent)
    result = notify.notify("run-1", notify.Outcome.COMPLETE)
    assert not result.delivered
    assert "powershell.exe not found" in result.detail


def test_a_hung_notifier_times_out_instead_of_stalling_the_run(monkeypatch) -> None:
    """The scheduled run must not be held open by the act of announcing itself."""
    def hang(*a, **k):
        raise subprocess.TimeoutExpired(cmd="powershell.exe", timeout=notify.TIMEOUT_SECONDS)

    monkeypatch.setattr(subprocess, "run", hang)
    result = notify.notify("run-1", notify.Outcome.COMPLETE)
    assert not result.delivered
    assert str(notify.TIMEOUT_SECONDS) in result.detail


def test_a_failure_reports_the_diagnosis_not_just_the_position(monkeypatch) -> None:
    """PowerShell's first stderr line is often a bare position marker. Reporting only that says a
    failure happened and nothing about what - measured during development, where `At line:3
    char:77` was the entire diagnostic for a broken script.
    """
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _completed(1, stderr="At line:3 char:77\n+ ... bad\nUnexpected token."),
    )
    result = notify.notify("run-1", notify.Outcome.COMPLETE)
    assert not result.delivered
    assert "Unexpected token." in result.detail, "the cause must survive, not only the position"


def test_a_silent_failure_still_reports_something(monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(1))
    result = notify.notify("run-1", notify.Outcome.COMPLETE)
    assert not result.delivered
    assert result.detail, "a failure with no output must not produce an empty explanation"


def test_the_notice_text_is_passed_by_environment_never_interpolated(monkeypatch) -> None:
    """A run id is generated by this codebase and is not attacker-controlled, but building a shell
    command by string substitution is a habit that is wrong exactly once. The script must be a
    constant; the text must arrive in the environment."""
    seen: dict = {}

    def capture(command, **kwargs):
        seen["command"] = command
        seen["env"] = kwargs.get("env", {})
        return _completed(0)

    monkeypatch.setattr(subprocess, "run", capture)
    notify.notify("run-INJECTED", notify.Outcome.COMPLETE)

    assert "run-INJECTED" not in " ".join(seen["command"]), "the run id must not reach the command"
    assert "run-INJECTED" in seen["env"]["SWINGDESK_NOTIFY_BODY"]


def test_the_notifier_decodes_leniently(monkeypatch) -> None:
    """`text=True` alone decodes STRICTLY, and that destroyed the diagnosis this module works to
    preserve.

    Measured 2026-08-16: `daily_run.cmd` runs the CLI under `-X utf8`, so Python decodes as UTF-8
    while PowerShell 5.1 writes stderr in the console's OEM codepage. One non-ASCII byte raised
    `UnicodeDecodeError` inside subprocess's reader thread, `completed.stderr` came back `None`,
    and the failure reported as "no output" - with a traceback in the daily log for company.
    """
    seen: dict = {}

    def capture(command, **kwargs):
        seen.update(kwargs)
        return _completed(1, stderr="boom")

    monkeypatch.setattr(subprocess, "run", capture)
    notify.notify("run-1", notify.Outcome.COMPLETE)

    assert seen.get("errors") == "replace", (
        "a strict decode loses the error text on any non-UTF-8 PowerShell message"
    )
