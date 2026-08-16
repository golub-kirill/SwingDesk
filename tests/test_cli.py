"""`cli.py`: the command-line surface, and what it wires into a run.

No end-to-end `scan` test here - `run()` has no fetcher-injection point on this path and defaults
to the real Yahoo fetcher, and CI must never touch the network (`CI_POLICY` 4). What is tested
instead is the one thing `cli.py` is actually responsible for: opening the right stores and passing
the right arguments into `run()` - the WIRING, not the pipeline it wires to, which is
`test_pipeline.py`'s and `test_positions.py`'s job.
"""

from __future__ import annotations

from pathlib import Path

from swingdesk.application.pipeline import RunResult
from swingdesk.contracts.run import RunManifest
from swingdesk.presentation import cli


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
