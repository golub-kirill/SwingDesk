"""`cli.py`: the command-line surface, and what it wires into a run.

No end-to-end `scan` test here - `run()` has no fetcher-injection point on this path and defaults
to the real Yahoo fetcher, and CI must never touch the network (`CI_POLICY` 4). What is tested
instead is the one thing `cli.py` is actually responsible for: opening the right stores and passing
the right arguments into `run()` - the WIRING, not the pipeline it wires to, which is
`test_pipeline.py`'s and `test_positions.py`'s job.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from swingdesk.application.pipeline import RunResult
from swingdesk.contracts.run import RunManifest
from swingdesk.presentation import cli, notify


@pytest.fixture(autouse=True)
def _never_raise_a_real_toast(monkeypatch):
    """No test in this file may pop a desktop notification.

    `scan` notifies by default - that is the point of `DR-011` - so without this, every run of the
    suite would spray toasts across the screen and spawn a PowerShell process per test. Autouse
    rather than per-test: forgetting it is invisible in CI and merely annoying locally, which is
    exactly the kind of defect that never gets fixed.
    """
    monkeypatch.setattr(
        cli.notify, "notify",
        lambda run_id, outcome: notify.NotifyResult(True, "stubbed in tests"),
    )


def _fake_run(captured: dict):
    """A stand-in for `pipeline.run` that records what it was called with and returns a minimal,
    valid `RunResult` - enough for `report.render()` to print without touching a real store.

    The store must be queried HERE, inside the fake, not after `main()` returns: `main()`'s own
    `with` block closes every store it opened on the way out, `PositionStore` included, so a query
    made after `main()` returns is a query against a closed connection - which is exactly what the
    first draft of this fixture got wrong.
    """
    from datetime import UTC, datetime

    def run(instruments, clock, registry, store, journal, *, mode, lookback,
            universe=None, positions=None, exits=None):
        captured["positions"] = positions
        captured["instruments"] = instruments
        # Kept so a test can prove they are SHUT by the time the notice is raised.
        captured["bar_store"] = store
        captured["position_store"] = positions
        captured["open_positions"] = (
            positions.open_as_of(datetime.now(UTC)) if positions is not None else None
        )
        return RunResult(manifest=RunManifest(
            run_id="r", started_at=clock.now(), mode=mode, code_hash="a", config_hash="b",
            snapshot_id="s", calendar_version="c", platform="p",
        ))

    return run


def test_scan_opens_a_position_store_and_passes_it_to_run(tmp_path: Path, monkeypatch) -> None:
    """Until 2026-08-16, `scan` never opened a `PositionStore` at all - Appendix T's "positions run
    first" was proven only in tests, never in the scheduled job (`TODO.md` 6b item 2). This is the
    wiring, not the pipeline: it does not need a real position recorded to prove the store reaches
    `run()`, and a store with nothing in it is the correct, safe state before item 1 (position
    entry) exists.
    """
    captured: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run(captured))

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    assert code == 0
    assert captured["positions"] is not None, "run() must not be called with positions=None"
    assert (tmp_path / "positions.duckdb").exists()


def test_scan_still_works_with_an_empty_position_store(tmp_path: Path, monkeypatch) -> None:
    """The store existing and being empty are different things - the wiring must not require a
    position to already be recorded, or landing this stays gated on item 1 landing first."""
    captured: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run(captured))

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    assert code == 0
    assert captured["open_positions"] == []


# ------------------------------------------------------ the dated report file (TODO.md 6b item 3)
#
# Until 2026-08-16 the report existed only as stdout, which `daily_run.cmd` redirected into an
# append-only log that rotates at 50MB. US-001 requires "a dated report is produced"; ROADMAP
# recorded that row as done on the strength of the run rendering something.


def test_scan_writes_a_report_file_named_for_the_run(tmp_path: Path, monkeypatch) -> None:
    """One file per run, named by run_id - which already carries the run's start instant, so the
    filename sorts chronologically and traces to the journal's `runs` row without a second copy
    of the date being formatted anywhere (AGENTS.md 10.5)."""
    monkeypatch.setattr(cli, "run", _fake_run({}))

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    written = tmp_path / "reports" / "r.txt"
    assert code == 0
    assert written.is_file(), "the run must leave a durable artifact, not only stdout"
    assert "SwingDesk run r" in written.read_text(encoding="utf-8")


def test_the_report_file_matches_what_was_printed(tmp_path: Path, monkeypatch, capsys) -> None:
    """The file and the console must be the same report. Two renderings that could drift is the
    defect this project keeps finding under other names."""
    monkeypatch.setattr(cli, "run", _fake_run({}))

    cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    printed = capsys.readouterr().out
    written = (tmp_path / "reports" / "r.txt").read_text(encoding="utf-8")
    assert written in printed


def test_report_dir_is_overridable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "run", _fake_run({}))
    elsewhere = tmp_path / "somewhere" / "else"

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path), "--report-dir", str(elsewhere)])

    assert code == 0
    assert (elsewhere / "r.txt").is_file(), "a nested directory must be created, not refused"


def test_an_unwritable_report_dir_is_loud_but_not_fatal(tmp_path: Path, monkeypatch, capsys) -> None:
    """The report was still PRODUCED - it is on stdout - so `a.run_completes` is satisfied and the
    run must not fail. But a delivery channel that fails quietly is the defect being closed here,
    so the failure has to reach stderr.
    """
    monkeypatch.setattr(cli, "run", _fake_run({}))

    def refuse(result, directory):
        raise OSError("disk is full")

    monkeypatch.setattr(cli.report, "write", refuse)

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 0, "a disk error must not reset the Track A counter"
    assert "report NOT persisted" in captured.err
    assert "disk is full" in captured.err
    assert "SwingDesk run r" in captured.out, "the report itself must still be printed"


# ------------------------------------------------- the local run notice (DR-011, TODO.md 6b 3b)


def test_scan_notifies_with_the_run_id_and_nothing_else(tmp_path: Path, monkeypatch) -> None:
    """The notice carries a terminal status and the run id. `DR-011` bans anything else, and this
    asserts the CLI honours that rather than assembling its own richer message."""
    seen: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run({}))
    monkeypatch.setattr(
        cli.notify, "notify",
        lambda run_id, outcome: seen.update(run_id=run_id, outcome=outcome)
        or notify.NotifyResult(True, "delivered"),
    )

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    assert code == 0
    assert seen["run_id"] == "r"
    assert seen["outcome"] is notify.Outcome.COMPLETE


def test_no_notify_suppresses_the_notice_but_not_the_report(tmp_path: Path, monkeypatch) -> None:
    called: list = []
    monkeypatch.setattr(cli, "run", _fake_run({}))
    monkeypatch.setattr(cli.notify, "notify", lambda *a: called.append(a))

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path), "--no-notify"])

    assert code == 0
    assert called == [], "--no-notify must not reach the notifier at all"
    assert (tmp_path / "reports" / "r.txt").is_file(), "the report is written either way"


def test_an_undelivered_notice_is_loud_but_not_fatal(tmp_path: Path, monkeypatch, capsys) -> None:
    """Same rule as the report write: the run completed and produced a report, so `a.run_completes`
    is satisfied and a failed pop-up must not reset a 20-day counter. But unnoticed non-delivery is
    the defect this feature exists to close, so it never fails in silence.
    """
    monkeypatch.setattr(cli, "run", _fake_run({}))
    monkeypatch.setattr(
        cli.notify, "notify",
        lambda run_id, outcome: notify.NotifyResult(False, "powershell.exe not found"),
    )

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 0, "a failed notice must not change the run's exit code"
    assert "notice NOT delivered" in captured.err
    assert "powershell.exe not found" in captured.err


def test_a_failed_report_write_changes_what_the_notice_says(tmp_path, monkeypatch) -> None:
    """Found by review 2026-08-16. `COMPLETE` was sent unconditionally, so after a failed write
    the toast still read "Report on disk." - telling the owner to go and read a file that is not
    there, while the only word of the failure sat on stderr in the log this feature exists to
    stop them having to read.
    """
    seen: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run({}))
    monkeypatch.setattr(cli.report, "write", _raise_oserror)
    monkeypatch.setattr(
        cli.notify, "notify",
        lambda run_id, outcome: seen.update(outcome=outcome) or notify.NotifyResult(True, "ok"),
    )

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    assert code == 0
    assert seen["outcome"] is notify.Outcome.COMPLETE_NO_REPORT
    assert "Report on disk." not in notify.body("r", seen["outcome"])


def _raise_oserror(result, directory):
    raise OSError("disk is full")


def test_a_refused_universe_still_notifies(tmp_path, monkeypatch) -> None:
    """Both refusal paths used to `return` from inside the store block, before the notifier - so a
    refused run said nothing at all. Silence then meant either "the system refused" or "the
    scheduler never fired", and `track_a_streak` counts exit 2 as a clean day, so nothing else
    surfaced it either. Silence must mean exactly one thing.
    """
    from swingdesk.trade_management.sizing import Refusal

    seen: dict = {}
    monkeypatch.setattr(
        cli.universe_builder, "rule_from_registry",
        lambda registry: Refusal("RISK", "universe.min_price is unset"),
    )
    monkeypatch.setattr(
        cli.notify, "notify",
        lambda run_id, outcome: seen.update(run_id=run_id, outcome=outcome)
        or notify.NotifyResult(True, "ok"),
    )

    code = cli.main(["scan", "--universe", "--data", str(tmp_path)])

    assert code == 2, "the refusal's exit code is unchanged"
    assert seen["outcome"] is notify.Outcome.REFUSED
    assert seen["run_id"] is None, "no run was journalled, so there is no id to reference"


def test_the_notice_is_raised_after_every_store_is_closed(tmp_path, monkeypatch) -> None:
    """It used to run inside the `with`, holding three DuckDB locks open for up to the notifier's
    full 15s timeout just to display a pop-up.

    Asserted by querying the store objects the run itself was handed: a closed DuckDB connection
    raises on use, so this can only pass once `main` has left the `with` suite. The FIRST draft
    of this test opened the same database files a second time instead - and passed against the
    unfixed code, because DuckDB permits multiple connections from one process. A test that
    cannot fail is the defect this whole session keeps finding, so it is recorded here rather
    than quietly replaced.
    """
    captured: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run(captured))

    def check_the_stores_are_shut(run_id, outcome):
        for name in ("bar_store", "position_store"):
            with pytest.raises(Exception, match=r"[Cc]losed"):
                captured[name]._connection.execute("SELECT 1")
        captured["checked"] = True
        return notify.NotifyResult(True, "ok")

    monkeypatch.setattr(cli.notify, "notify", check_the_stores_are_shut)

    assert cli.main(["scan", "AAPL", "--data", str(tmp_path)]) == 0
    assert captured.get("checked"), "the notifier must actually have run"
