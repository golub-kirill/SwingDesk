"""`cli.py`: the command-line surface, and what it wires into a run.

No end-to-end `scan` test here - `run()` has no fetcher-injection point on this path and defaults
to the real Yahoo fetcher, and CI must never touch the network (`CI_POLICY` 4). What is tested
instead is the one thing `cli.py` is actually responsible for: opening the right stores and passing
the right arguments into `run()` - the WIRING, not the pipeline it wires to, which is
`test_pipeline.py`'s and `test_positions.py`'s job.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.application.pipeline import RunResult
from swingdesk.contracts.position import ActionKind as _ActionKind
from swingdesk.contracts.run import RunManifest
from swingdesk.market_data.retry import RetryingFetcher
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
            universe=None, positions=None, exits=None, fetcher=None):
        captured["positions"] = positions
        captured["instruments"] = instruments
        captured["fetcher"] = fetcher
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


def test_scan_wraps_the_fetcher_in_the_retry_dr_015_ruled(tmp_path: Path, monkeypatch) -> None:
    """`DR-015` §3 puts the retry around the injected fetcher, and `run()` falls back to the bare
    `vendor_yahoo.fetch` when nothing is passed - so a retry that exists and is never injected is
    the exact "decided, but wired to nothing" shape `AGENTS.md` §7 was written for. This asserts
    the wiring, which is the half that cannot be proven by testing the wrapper.
    """
    captured: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run(captured))

    assert cli.main(["scan", "AAPL", "--data", str(tmp_path)]) == 0

    fetcher = captured["fetcher"]
    assert isinstance(fetcher, RetryingFetcher), "the scheduled run must not get the bare fetcher"
    assert fetcher.slept == 0.0, "a run that fetched nothing cannot have waited"


def test_scan_still_works_with_an_empty_position_store(tmp_path: Path, monkeypatch) -> None:
    """The store existing and being empty are different things - the wiring must not require a
    position to already be recorded, or landing this stays gated on item 1 landing first."""
    captured: dict = {}
    monkeypatch.setattr(cli, "run", _fake_run(captured))

    code = cli.main(["scan", "AAPL", "--data", str(tmp_path)])

    assert code == 0
    assert captured["open_positions"] == []


# --------------------------------------------------------------- open-position (TODO.md 6b item 1)
#
# `PositionStore.record()` had no caller anywhere outside tests until this command. Every case
# below runs the REAL command against a REAL PositionStore - no fetcher to fake, no network
# involved, so unlike `scan` this path can be exercised end to end.


def _open(tmp_path: Path, *args: str) -> tuple[int, list]:
    """Run `open-position` and return its exit code plus what actually landed in the store."""
    from datetime import UTC, datetime

    from swingdesk.journal_evidence.positions import PositionStore

    code = cli.main(["open-position", *args, "--data", str(tmp_path)])
    with PositionStore(tmp_path / "positions.duckdb") as store:
        recorded = store.open_as_of(datetime.now(UTC))
    return code, recorded


def test_open_position_records_a_usd_fill_with_dr010_costs(tmp_path: Path) -> None:
    """The default path: no --costs-per-share override, so the DR-010 formula prices it - the same
    formula sizing uses, not a second implementation of the same number (AGENTS.md 10.5)."""
    code, recorded = _open(
        tmp_path, "AAPL", "--entry", "100", "--shares", "50", "--stop", "96",
        "--opened-on", "2026-08-10",
    )
    assert code == 0
    assert len(recorded) == 1
    position = recorded[0]
    assert position.position_id == "POS-AAPL-2026-08-10"
    assert position.instrument_id == "AAPL"
    assert position.shares == 50
    assert position.entry_price == Decimal(100)
    assert position.initial_stop == Decimal(96)
    assert position.current_stop == Decimal(96), "a fresh position starts unmoved"
    # DR-010: max(0.25 floor, 50bp * 100) = max(0.25, 0.50) = 0.50
    assert position.initial_costs_per_share == Decimal("0.50")
    assert position.initial_risk_per_share == Decimal("4.50"), "entry - stop + costs, RISK_SPEC 2"


def test_open_position_accepts_a_real_broker_cost_override(tmp_path: Path) -> None:
    """Once a broker confirmation names the real round-trip cost, it should win over the DR-010
    estimate - the estimate is what sizing planned against, not a fact about this specific fill."""
    code, recorded = _open(
        tmp_path, "AAPL", "--entry", "100", "--shares", "50", "--stop", "96",
        "--opened-on", "2026-08-10", "--costs-per-share", "1.23",
    )
    assert code == 0
    assert recorded[0].initial_costs_per_share == Decimal("1.23")


def test_open_position_prices_cad_through_the_cad_parameters(tmp_path: Path) -> None:
    """`.TO` resolves to CAD, and CAD costs are a SEPARATE registry entry (AGENTS.md 3: USA and
    Canada are never merged) - this proves the command reads the right one, not just A currency."""
    code, recorded = _open(
        tmp_path, "SHOP.TO", "--entry", "80", "--shares", "10", "--stop", "76",
        "--opened-on", "2026-08-10",
    )
    assert code == 0
    assert recorded[0].instrument_id == "SHOP.TO"
    # max(0.25, 50bp * 80) = max(0.25, 0.40) = 0.40
    assert recorded[0].initial_costs_per_share == Decimal("0.40")


def test_open_position_refuses_an_invalid_stop_cleanly(tmp_path: Path) -> None:
    """A stop at or above entry is not an invalidation level - Position's own validator catches
    this, and the CLI must turn that into a coded refusal, not an uncaught traceback."""
    code, recorded = _open(
        tmp_path, "AAPL", "--entry", "100", "--shares", "50", "--stop", "105",
        "--opened-on", "2026-08-10",
    )
    assert code == 2
    assert recorded == [], "a refused position must not reach the store"


def test_open_position_refuses_a_same_day_duplicate(tmp_path: Path) -> None:
    """The store's own append-only guard, surfaced as a clean refusal rather than a stack trace -
    and the right behaviour: a second `open-position` for the same instrument on the same date is
    far more likely to be an accidental re-run than a real second entry."""
    first_code, _ = _open(
        tmp_path, "AAPL", "--entry", "100", "--shares", "50", "--stop", "96",
        "--opened-on", "2026-08-10",
    )
    second_code, recorded = _open(
        tmp_path, "AAPL", "--entry", "101", "--shares", "40", "--stop", "97",
        "--opened-on", "2026-08-10",
    )
    assert first_code == 0
    assert second_code == 2
    assert len(recorded) == 1, "the second attempt must not have landed"
    assert recorded[0].entry_price == Decimal(100), "the first record is untouched"


def test_open_position_id_is_overridable(tmp_path: Path) -> None:
    code, recorded = _open(
        tmp_path, "AAPL", "--entry", "100", "--shares", "50", "--stop", "96",
        "--opened-on", "2026-08-10", "--position-id", "POS-CUSTOM-1",
    )
    assert code == 0
    assert recorded[0].position_id == "POS-CUSTOM-1"
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


# ------------------------------------- pending / respond: the loop closes (US-010, TODO 6b 4+5)


def _seeded(tmp_path, **action_kw):
    """A position with one unanswered MOVE_STOP proposal on it."""
    from datetime import UTC, date, datetime
    from decimal import Decimal

    from swingdesk.contracts.position import ActionKind, ManagementAction, Position
    from swingdesk.journal_evidence.positions import PositionStore

    fields = dict(kind=ActionKind.MOVE_STOP, reason="2xATR trail cleared the current stop",
                  old_stop=Decimal(290), new_stop=Decimal(298))
    fields.update(action_kw)
    with PositionStore(tmp_path / "positions.duckdb") as store:
        store.record(Position(
            position_id="POS-1", version=1, instrument_id="AAPL", opened_on=date(2026, 8, 10),
            entry_price=Decimal(300), shares=8, initial_stop=Decimal(290),
            current_stop=Decimal(290),
            # What DR-010 actually charges at a 300 entry: max(floor 0.25, 50bp x 300) = 1.50, so
            # the bp term binds and the floor does not. Picking the floor here would have made the
            # fixture disagree with `size_long` on the same instrument, which is the very defect
            # the cost-inclusive denominator exists to close.
            initial_costs_per_share=Decimal("1.50"),
            knowledge_time=datetime(2026, 8, 10, tzinfo=UTC),
        ))
        store.propose(ManagementAction(
            position_id="POS-1", proposed_at=datetime(2026, 8, 16, 22, 30, tzinfo=UTC), **fields))
    return tmp_path


def _history(tmp_path):
    from swingdesk.journal_evidence.positions import PositionStore

    with PositionStore(tmp_path / "positions.duckdb") as store:
        return store.history("POS-1")


def test_pending_states_what_is_needed_to_answer(tmp_path, capsys) -> None:
    """US-010: the proposal states the observation, the rule that produced it, and the bounded set
    of choices - which is exactly two."""
    assert cli.main(["pending", "--data", str(_seeded(tmp_path))]) == 0

    out = capsys.readouterr().out
    assert "POS-1" in out and "#1" in out and "MOVE_STOP" in out
    assert "2xATR trail cleared the current stop" in out, "the rule that produced it"
    assert "290" in out and "298" in out, "the observation it acted on"
    assert "--approve|--reject" in out, "the bounded choices"


def test_pending_is_quiet_when_nothing_awaits_an_answer(tmp_path, capsys) -> None:
    assert cli.main(["pending", "--data", str(tmp_path)]) == 0
    assert "no proposals" in capsys.readouterr().out


def test_an_approval_is_recorded_and_applied(tmp_path, capsys) -> None:
    """`manage.apply_approved` was built, unit tested, and called from nowhere but tests, so no
    decision the owner made could ever reach the store. This is that wiring."""
    root = _seeded(tmp_path)

    code = cli.main(["respond", "POS-1", "1", "--approve", "--reason", "trend intact",
                     "--data", str(root)])

    assert code == 0
    versions = _history(root)
    assert [p.version for p in versions] == [1, 2], "an approval writes a NEW version"
    assert versions[1].current_stop == Decimal(298)
    assert versions[0].current_stop == Decimal(290), "the earlier version stays readable"
    assert "applied" in capsys.readouterr().out


def test_a_rejection_is_recorded_and_changes_nothing(tmp_path, capsys) -> None:
    root = _seeded(tmp_path)

    code = cli.main(["respond", "POS-1", "1", "--reject", "--reason", "too early",
                     "--data", str(root)])

    assert code == 0
    assert [p.version for p in _history(root)] == [1], "a rejection applies nothing"
    assert "nothing applied" in capsys.readouterr().out


def test_nothing_is_applied_without_a_recorded_response(tmp_path) -> None:
    """US-010's third clause, asserted on the store rather than on the CLI's word for it."""
    from swingdesk.journal_evidence.positions import PositionStore

    root = _seeded(tmp_path)
    with PositionStore(root / "positions.duckdb") as store:
        assert store.response_for("POS-1", 1) is None
    assert [p.version for p in _history(root)] == [1], "unanswered means unapplied"


def test_a_response_without_a_reason_is_refused_by_the_parser(tmp_path, capsys) -> None:
    """Production rule 3.8. `--reason` is `required=True`, so this never reaches the store.

    The message is asserted, not merely the `SystemExit`: argparse exits the same way for an
    unknown command, so a bare `pytest.raises(SystemExit)` passed even when `respond` did not
    exist at all - a test that could not fail, which is the defect this session keeps finding.
    """
    with pytest.raises(SystemExit):
        cli.main(["respond", "POS-1", "1", "--approve", "--data", str(_seeded(tmp_path))])
    assert "--reason" in capsys.readouterr().err


def test_approve_and_reject_are_mutually_exclusive(tmp_path, capsys) -> None:
    """A response is one choice. Same reasoning as above for asserting the message."""
    with pytest.raises(SystemExit):
        cli.main(["respond", "POS-1", "1", "--approve", "--reject", "--reason", "x",
                  "--data", str(_seeded(tmp_path))])
    assert "not allowed with" in capsys.readouterr().err


def test_answering_twice_is_refused_at_the_cli(tmp_path, capsys) -> None:
    root = _seeded(tmp_path)
    cli.main(["respond", "POS-1", "1", "--approve", "--reason", "yes", "--data", str(root)])
    capsys.readouterr()

    code = cli.main(["respond", "POS-1", "1", "--reject", "--reason", "no", "--data", str(root)])

    assert code == 2
    assert "already answered" in capsys.readouterr().err
    assert [p.version for p in _history(root)] == [1, 2], "the second answer applied nothing"


# ---------------------------------------------------- record-fill (US-011, TODO.md 6b item 6)


def _approved(tmp_path, *, reason_code="STOP"):
    """A position with one APPROVED EXIT_NOW, ready to be filled."""
    root = _seeded(tmp_path, kind=_ActionKind.EXIT_NOW, reason_code=reason_code,
                   reason="stop 290 touched", old_stop=Decimal(290), new_stop=None)
    cli.main(["respond", "POS-1", "1", "--approve", "--reason", "out", "--data", str(root)])
    return root


def _fills(tmp_path):
    from swingdesk.journal_evidence.positions import PositionStore

    with PositionStore(tmp_path / "positions.duckdb") as store:
        return store.fills_for("POS-1")


def test_a_stop_exit_fill_reports_slippage_in_r(tmp_path, capsys) -> None:
    """The planned price comes from the ACTION, never from the reporter - a reference supplied
    after seeing the fill is one that can always be made to look acceptable."""
    root = _approved(tmp_path)
    capsys.readouterr()

    code = cli.main(["record-fill", "POS-1", "1", "--price", "289.40", "--shares", "8",
                     "--commission", "1.25", "--data", str(root)])

    assert code == 0
    recorded = _fills(root)[0]
    assert recorded.planned_price == Decimal(290)
    assert recorded.slippage_per_share == Decimal("0.60")
    out = capsys.readouterr().out
    assert "R against the ORIGINAL denominator" in out
    assert "open risk" in out, "US-011 wants the book, recomputed"


def test_a_time_exit_fill_refuses_to_invent_slippage(tmp_path, capsys) -> None:
    """A maximum-holding-period exit is at market. 0.00 would be a manufactured measurement, and
    it would flatter the strategy: unknown slippage is not absent slippage."""
    root = _approved(tmp_path, reason_code="TIME")
    capsys.readouterr()

    code = cli.main(["record-fill", "POS-1", "1", "--price", "311.20", "--shares", "8",
                     "--commission", "1.00", "--data", str(root)])

    assert code == 0
    assert _fills(root)[0].planned_price is None
    assert _fills(root)[0].slippage_per_share is None
    assert "UNAVAILABLE" in capsys.readouterr().out


def test_a_fill_for_an_unapproved_action_is_refused(tmp_path, capsys) -> None:
    """D6 from the far side of the trade."""
    root = _seeded(tmp_path, kind=_ActionKind.EXIT_NOW, reason_code="STOP",
                   reason="stop touched", old_stop=Decimal(290), new_stop=None)

    code = cli.main(["record-fill", "POS-1", "1", "--price", "289", "--shares", "8",
                     "--commission", "1", "--data", str(root)])

    assert code == 2
    assert "no recorded response" in capsys.readouterr().err
    assert _fills(root) == [], "nothing may be recorded against an unapproved action"


def test_a_fill_for_an_action_that_does_not_exist_is_refused(tmp_path, capsys) -> None:
    code = cli.main(["record-fill", "POS-1", "99", "--price", "1", "--shares", "1",
                     "--commission", "0", "--data", str(_approved(tmp_path))])
    assert code == 2
    assert "no action" in capsys.readouterr().err


# ---------------------------------- proposal expiry (DR-013, TODO.md 6b item 5b) - 2026-08-18
#
# `ActionStatus.EXPIRED` was defined on the contract and written by nothing, so a MOVE_STOP computed
# on week-old bars stayed answerable forever. DR-013 ruled the window: non-critical expires after 3
# TRADING days, critical never does.


def _answer(root, seq=1, at="2026-08-21T22:00:00", approve=True):
    flag = "--approve" if approve else "--reject"
    return cli.main(["respond", "POS-1", str(seq), flag, "--reason", "ok",
                     "--as-of", at, "--data", str(root)])


def test_a_stale_stop_move_can_no_longer_be_answered(tmp_path, capsys) -> None:
    """The defect itself. Proposed Sunday 2026-08-16; by Friday 08-21 four sessions have elapsed,
    one past the window, and approving would move a real stop on a four-day-old observation."""
    root = _seeded(tmp_path)
    capsys.readouterr()

    code = _answer(root)

    assert code == 2
    err = capsys.readouterr().err
    assert "expired" in err and "DR-013" in err
    assert [p.version for p in _history(root)] == [1], "nothing may be applied to the position"


def test_a_stop_move_inside_the_window_is_still_answerable(tmp_path, capsys) -> None:
    """The boundary matters as much as the rule. Three elapsed sessions is INSIDE - proposals must
    not expire a day early, which is the off-by-one an inclusive session count would produce."""
    root = _seeded(tmp_path)
    capsys.readouterr()

    code = _answer(root, at="2026-08-20T22:00:00")

    assert code == 0
    assert [p.version for p in _history(root)] == [1, 2], "the approval must apply"


def test_a_critical_exit_never_expires(tmp_path, capsys) -> None:
    """DR-013 2.1: expiring an EXIT_NOW converts the system's loudest statement into silence, and
    silence reads as "nothing to do". Same date that expires a MOVE_STOP above."""
    root = _seeded(tmp_path, kind=_ActionKind.EXIT_NOW, reason_code="STOP",
                   reason="stop 290 touched", old_stop=Decimal(290), new_stop=None)
    capsys.readouterr()

    code = _answer(root, at="2026-09-30T22:00:00")

    assert code == 0, "a critical proposal is answerable however long it has waited"
    assert [p.version for p in _history(root)] == [1, 2]


def test_pending_shows_an_expired_proposal_rather_than_hiding_it(tmp_path, capsys) -> None:
    """An owner who cannot tell "nothing pending" from "something aged out while I was away" has
    been told less than the truth, and the second is the case they most need to know about."""
    root = _seeded(tmp_path)
    capsys.readouterr()

    assert cli.main(["pending", "--data", str(root), "--as-of", "2026-08-21T22:00:00"]) == 0

    out = capsys.readouterr().out
    assert "no proposals awaiting your answer" in out, "it is not answerable"
    assert "EXPIRED" in out and "POS-1" in out, "but it is still reported"


def test_pending_still_lists_a_live_proposal(tmp_path, capsys) -> None:
    root = _seeded(tmp_path)
    capsys.readouterr()

    assert cli.main(["pending", "--data", str(root), "--as-of", "2026-08-18T22:00:00"]) == 0

    out = capsys.readouterr().out
    assert "1 proposal(s) awaiting your answer" in out
    assert "EXPIRED" not in out
