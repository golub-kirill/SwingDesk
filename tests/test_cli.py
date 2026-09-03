"""`cli.py`: the command-line surface, and what it wires into a run.

No end-to-end `scan` test here - `run()` has no fetcher-injection point on this path and defaults
to the real Yahoo fetcher, and CI must never touch the network (`CI_POLICY` 4). What is tested
instead is the one thing `cli.py` is actually responsible for: opening the right stores and passing
the right arguments into `run()` - the WIRING, not the pipeline it wires to, which is
`test_pipeline.py`'s and `test_positions.py`'s job.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.application.pipeline import RunResult
from swingdesk.contracts.position import ActionKind as _ActionKind
from swingdesk.contracts.run import RunManifest
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
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
            universe=None, positions=None, classifications=None, exits=None, fetcher=None,
            actions_fetcher=None):
        captured["positions"] = positions
        captured["classifications"] = classifications
        captured["actions_fetcher"] = actions_fetcher
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

    # Same wiring, same argument, `DR-006` §2's sector cap (2026-08-23). A cap that no command
    # opens a store for is the "decided, but wired to nothing" shape `AGENTS.md` §7 counts - and
    # an EMPTY store is the correct state before `tools/refresh_classifications.py` has run: every
    # candidate reports `unavailable` and is admitted unchecked, which is the truth.
    assert captured["classifications"] is not None, "the sector cap must reach run()"
    assert (tmp_path / "classifications.duckdb").exists()

    # And the corporate-actions source, `DR-016` §7. `run()` defaults it to None - which does not
    # fetch and reads only what is stored - so a `scan` that never passed one would leave the split
    # guard permanently `unavailable` and the actions table permanently empty. That is exactly the
    # state §8.5 found it in.
    from swingdesk.market_data import vendor_yahoo

    assert captured["actions_fetcher"] is vendor_yahoo.fetch_actions, (
        "the scheduled run must feed the actions series, or the split guard never has an input"
    )


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


def _overrides(tmp_path: Path) -> list:
    """Every acknowledged cap breach in the store under `tmp_path`."""
    from swingdesk.journal_evidence.positions import PositionStore

    with PositionStore(tmp_path / "positions.duckdb") as store:
        return store.cap_overrides()


def _tiny(tmp_path: Path, ticker: str) -> tuple[int, list]:
    """One position worth 0.01R, so the count cap binds long before the R cap can."""
    return _open(tmp_path, ticker, "--entry", "100", "--shares", "10", "--stop", "99.9",
                 "--opened-on", "2026-08-10")


def test_open_position_refuses_a_cad_fill_while_the_rate_is_unset(tmp_path: Path) -> None:
    """The book cap is denominated in R and R is base currency, so a CAD position's risk cannot be
    expressed at all while `account.fx_rate_cad` is unset - and once such a position is in the
    book, no later run can total the book either, which would refuse every candidate.

    Owner ruling 2026-08-22: refuse, and let `--acknowledge-over-cap` record it anyway. This is the
    same fail-closed answer `size_long` already gives a CAD candidate, reached from a command that
    sizes nothing.
    """
    code, recorded = _open(
        tmp_path, "TEST2.TO", "--entry", "80", "--shares", "10", "--stop", "76",
        "--opened-on", "2026-08-10",
    )
    assert code == 2
    assert recorded == [], "a refused position must not reach the store"


def test_an_acknowledged_cad_fill_is_recorded_with_its_reason(tmp_path: Path) -> None:
    """The escape hatch, and the CAD cost pricing it must not disturb. `.TO` resolves to CAD and
    CAD costs are a SEPARATE registry entry (AGENTS.md 3: USA and Canada are never merged), so this
    still proves the command reads the right one - it just has to say so out loud first."""
    code, recorded = _open(
        tmp_path, "TEST2.TO", "--entry", "80", "--shares", "10", "--stop", "76",
        "--opened-on", "2026-08-10",
        "--acknowledge-over-cap", "paper position, CAD rate not set yet",
    )
    assert code == 0
    assert recorded[0].instrument_id == "TEST2.TO"
    # max(0.25, 50bp * 80) = max(0.25, 0.40) = 0.40
    assert recorded[0].initial_costs_per_share == Decimal("0.40")

    overrides = _overrides(tmp_path)
    assert len(overrides) == 1
    assert overrides[0].position_id == recorded[0].position_id
    assert overrides[0].binding == "account.fx_rate_cad"
    assert overrides[0].reason == "paper position, CAD rate not set yet"


def test_a_fifth_position_is_refused_on_the_concurrency_cap(tmp_path: Path) -> None:
    """`risk.max_concurrent_positions` is 4 (DR-006 8.3, owner). Four tiny positions leave the R
    cap nowhere near binding, so the count is the only thing that can refuse the fifth."""
    for ticker in ("TEST1", "TEST2", "TEST3", "TEST4"):
        code, _ = _tiny(tmp_path, ticker)
        assert code == 0, f"{ticker} is inside the cap and must be recorded"

    code, recorded = _tiny(tmp_path, "TEST5")
    assert code == 2
    assert len(recorded) == 4, "the fifth must not reach the store"
    assert _overrides(tmp_path) == [], "a refusal is not an override"


def test_a_fifth_position_is_recorded_when_the_breach_is_acknowledged(tmp_path: Path) -> None:
    for ticker in ("TEST1", "TEST2", "TEST3", "TEST4"):
        _tiny(tmp_path, ticker)

    code = cli.main([
        "open-position", "TEST5", "--entry", "100", "--shares", "10", "--stop", "99.9",
        "--opened-on", "2026-08-10", "--data", str(tmp_path),
        "--acknowledge-over-cap", "scaling in on a plan agreed with myself",
    ])
    assert code == 0

    overrides = _overrides(tmp_path)
    assert len(overrides) == 1
    assert overrides[0].binding == "risk.max_concurrent_positions"
    assert overrides[0].positions_open == 4, "the book AS IT STOOD, not including the new one"
    assert overrides[0].reason == "scaling in on a plan agreed with myself"


def test_a_blank_reason_is_not_an_acknowledgement(tmp_path: Path) -> None:
    """Production Rule 3.8's shape: an approval with no stated reason is an unlogged judgment, and
    whitespace is what a hurried operator types to get past a prompt."""
    for ticker in ("TEST1", "TEST2", "TEST3", "TEST4"):
        _tiny(tmp_path, ticker)

    code = cli.main([
        "open-position", "TEST5", "--entry", "100", "--shares", "10", "--stop", "99.9",
        "--opened-on", "2026-08-10", "--data", str(tmp_path), "--acknowledge-over-cap", "   ",
    ])
    assert code == 2


def test_the_flag_records_no_override_when_nothing_was_breached(tmp_path: Path) -> None:
    """A flag that excused nothing must leave no trace saying it did. An audit table that collects
    overrides for positions inside the cap is an audit table nobody can read."""
    code = cli.main([
        "open-position", "TEST1", "--entry", "100", "--shares", "10", "--stop", "99.9",
        "--opened-on", "2026-08-10", "--data", str(tmp_path),
        "--acknowledge-over-cap", "belt and braces",
    ])
    assert code == 0
    assert _overrides(tmp_path) == []


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


#: An instant INSIDE `DR-013`'s expiry window for the proposal `_seeded` creates.
#:
#: **Why every test touching a live proposal has to pin the clock.** `_seeded` dates its proposal
#: 2026-08-16 and `management.proposal_expiry_days` is 3 SESSIONS, so a test that lets `pending` or
#: `respond` read the wall clock passes only while real time is still inside that window. Four of
#: them did. They passed when written on 2026-08-17, and on 2026-08-20 the window closed and
#: `master` went red with nobody having touched it - the failure surfacing in tests about approval,
#: rejection and double-answering, none of which is about expiry at all.
#:
#: The tests that are ABOUT expiry were never affected: they pin `--as-of` on both sides of the
#: boundary, which is what this constant makes the default habit rather than a detail those tests
#: happened to get right.
LIVE = "2026-08-18T22:00:00"


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
    assert cli.main(["pending", "--data", str(_seeded(tmp_path)), "--as-of", LIVE]) == 0

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
                     "--data", str(root), "--as-of", LIVE])

    assert code == 0
    versions = _history(root)
    assert [p.version for p in versions] == [1, 2], "an approval writes a NEW version"
    assert versions[1].current_stop == Decimal(298)
    assert versions[0].current_stop == Decimal(290), "the earlier version stays readable"
    assert "applied" in capsys.readouterr().out


def test_a_rejection_is_recorded_and_changes_nothing(tmp_path, capsys) -> None:
    root = _seeded(tmp_path)

    code = cli.main(["respond", "POS-1", "1", "--reject", "--reason", "too early",
                     "--data", str(root), "--as-of", LIVE])

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
    cli.main(["respond", "POS-1", "1", "--approve", "--reason", "yes", "--data", str(root),
              "--as-of", LIVE])
    capsys.readouterr()

    code = cli.main(["respond", "POS-1", "1", "--reject", "--reason", "no", "--data", str(root),
                     "--as-of", LIVE])

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


# ------------------------------------------- the refusals `record-fill` can raise and nobody saw
#
# Measured 2026-08-25 by tracing `cli.py` while the suite ran: four of its five `Refusal`
# constructions had never been executed. These are the three that need no monkeypatch - all three
# block the recording of a fill that has ALREADY happened at the broker, which is why each says
# plainly what is missing rather than failing quietly.


def _caps_registry(**overrides: object):
    """The parameters `_capacity_for` reads, and nothing else.

    Built here rather than shared: a `None` value means UNSET and a MISSING key means the code and
    the registry disagree, and these tests are precisely about telling those two apart.
    """
    from swingdesk.platform.parameters import ParameterRegistry

    base: dict[str, object] = {
        "risk.max_open_risk": 4,
        "risk.max_concurrent_positions": 4,
        "account.equity": 10000,
        "account.base_currency": "USD",
        "risk.per_trade_pct": "1.0",
    }
    base.update(overrides)
    return ParameterRegistry({
        key: {
            "id": key, "value": value,
            "provenance": "assumed:test" if value is not None else None,
            "status": "assumed" if value is not None else "unset",
            "unit": "", "named_in": ["test"], "read_by": "none", "ui_editable": False,
        }
        for key, value in base.items()
    })


def _held_position():
    from datetime import UTC, date, datetime

    from swingdesk.contracts.position import Position

    return Position(
        position_id="POS-1", version=1, instrument_id="TEST.1",
        opened_on=date(2025, 12, 1), entry_price=Decimal(100), shares=50,
        initial_stop=Decimal(96), current_stop=Decimal(96),
        initial_costs_per_share=Decimal("0.50"),
        knowledge_time=datetime(2025, 12, 1, tzinfo=UTC),
    )


def test_recording_a_fill_refuses_when_a_cap_has_no_value(tmp_path: Path) -> None:
    """`unset` is not `no limit`. The book cannot be judged against a cap nobody set."""
    from datetime import UTC, datetime

    from swingdesk.journal_evidence.positions import PositionStore
    from swingdesk.trade_management.sizing import Refusal

    with PositionStore(tmp_path / "positions.duckdb") as store:
        result = cli._capacity_for(
            store, _held_position(), _caps_registry(**{"risk.max_open_risk": None}),
            datetime(2026, 1, 5, tzinfo=UTC),
        )
    assert isinstance(result, Refusal)
    assert result.code == "RISK"
    assert result.parameter_id == "risk.max_open_risk"


def test_recording_a_fill_refuses_when_one_R_cannot_be_valued(tmp_path: Path) -> None:
    """The cap is denominated in R, so an unset equity blocks judging the book at all.

    Worth its own case because it WIDENS what can stop a fill being recorded: before the cap
    existed this command needed only the `DR-010` cost parameters.
    """
    from datetime import UTC, datetime

    from swingdesk.journal_evidence.positions import PositionStore
    from swingdesk.trade_management.sizing import Refusal

    with PositionStore(tmp_path / "positions.duckdb") as store:
        result = cli._capacity_for(
            store, _held_position(), _caps_registry(**{"account.equity": None}),
            datetime(2026, 1, 5, tzinfo=UTC),
        )
    assert isinstance(result, Refusal)
    assert result.code == "RISK"
    assert "one R cannot be valued" in result.reason
    assert result.parameter_id == "account.equity"


def test_expiry_refuses_for_a_proposal_whose_position_is_not_in_the_store(tmp_path: Path) -> None:
    """The exchange comes from the POSITION, so no position means no calendar to date against.

    Refusing beats guessing: `DR-013`'s window is in SESSIONS, and picking the wrong calendar is
    the worst way for a date rule to be wrong.
    """
    from datetime import UTC, datetime

    from swingdesk.contracts.position import ManagementAction
    from swingdesk.journal_evidence.positions import PositionStore
    from swingdesk.trade_management.sizing import Refusal

    action = ManagementAction(
        action_id="ACT-1", position_id="POS-MISSING", kind=_ActionKind.MOVE_STOP,
        proposed_at=datetime(2026, 1, 2, tzinfo=UTC), run_id="R1",
        reason="stop moved to breakeven", old_stop=Decimal(96), new_stop=Decimal(98),
    )
    with PositionStore(tmp_path / "positions.duckdb") as store:
        result = cli._expiry(store, action, datetime(2026, 1, 5, tzinfo=UTC))
    assert isinstance(result, Refusal)
    assert result.code == "DATA"
    assert "POS-MISSING" in result.reason


def test_expiry_refuses_when_the_window_itself_is_unset(tmp_path: Path, monkeypatch) -> None:
    """The last of `cli.py`'s five refusals, and the only one needing a monkeypatch.

    `_expiry` reads `ParameterRegistry.load()` itself rather than taking a registry the way
    `_capacity_for` does, so there is no injection point and the guard is unreachable from a
    fixture. What it asserts is still real and is the fail-closed rule: an unset window becomes a
    CODED refusal naming the parameter, never a default number of sessions.
    """
    from datetime import UTC, datetime

    from swingdesk.contracts.position import ManagementAction
    from swingdesk.journal_evidence.positions import PositionStore
    from swingdesk.platform.parameters import ParameterUnset
    from swingdesk.trade_management.sizing import Refusal

    def _refuse_to_load():
        raise ParameterUnset("management.proposal_expiry_days")

    monkeypatch.setattr(cli.ParameterRegistry, "load", staticmethod(_refuse_to_load))

    action = ManagementAction(
        action_id="ACT-1", position_id="POS-1", kind=_ActionKind.MOVE_STOP,
        proposed_at=datetime(2026, 1, 2, tzinfo=UTC), run_id="R1",
        reason="stop moved to breakeven", old_stop=Decimal(96), new_stop=Decimal(98),
    )
    with PositionStore(tmp_path / "positions.duckdb") as store:
        result = cli._expiry(store, action, datetime(2026, 1, 5, tzinfo=UTC))
    assert isinstance(result, Refusal)
    assert result.code == "RISK"
    assert result.parameter_id == "management.proposal_expiry_days"


# --- `swingdesk broker`: the wiring, and the three exit codes ---------------------------------
#
# The reconciliation itself is `test_broker.py`'s subject. What is checked here is the thing
# `cli.py` owns: that a venue it could not read, a venue that disagrees with the book, and a venue
# that agrees produce three DIFFERENT exit codes. Collapsing any two of them is the error
# `AGENTS.md` 12 calls the most damaging this product can make - `unavailable` is not `fail` and it
# is not `pass` - and an exit code is the only part of this surface a script can read.


def _stub_broker(monkeypatch, held, *, raises=None):
    """Point `cli._broker` at a client that serves fixtures instead of a socket."""
    from datetime import UTC, datetime

    from swingdesk import broker as broker_pkg
    from swingdesk.contracts.broker import BrokerAccount

    observed = datetime(2026, 8, 31, 21, 0, tzinfo=UTC)
    policy = broker_pkg.load_policy()

    class _Client:
        def account(self, at):
            if raises is not None:
                raise raises
            return BrokerAccount(
                venue=policy.venue, base_url=policy.base_url, fingerprint="0123456789ab",
                status="ACTIVE", currency="USD", cash=Decimal(100000),
                equity=Decimal(100000), buying_power=Decimal(200000),
                trading_blocked=False, account_blocked=False, observed_at=at or observed,
            )

        def positions(self, at):
            return tuple(held)

        def fills(self, at, after=None):
            return ()

    monkeypatch.setattr(broker_pkg, "open_client", lambda policy=None, transport=None: _Client())
    return policy


def test_broker_agrees_with_an_empty_book(tmp_path: Path, monkeypatch, capsys) -> None:
    _stub_broker(monkeypatch, [])
    assert cli.main(["broker", "--data", str(tmp_path)]) == 0
    assert "describe the same positions" in capsys.readouterr().out


def test_broker_reports_tech_and_exits_3_when_the_venue_holds_what_the_book_does_not(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from datetime import UTC, datetime

    from swingdesk.contracts.broker import BrokerPosition, PositionSide

    _stub_broker(monkeypatch, [BrokerPosition(
        symbol="TEST.1", asset_class="us_equity", exchange="NYSE", side=PositionSide.LONG,
        shares=Decimal(100), average_entry_price=Decimal("50.25"),
        observed_at=datetime(2026, 8, 31, 21, 0, tzinfo=UTC),
    )])
    # 3, not 2: the venue WAS read. A divergence and an unreadable venue are different claims.
    assert cli.main(["broker", "--data", str(tmp_path)]) == 3
    printed = capsys.readouterr()
    assert "TECH" in printed.out
    assert "pause new entries" in printed.err


def test_broker_exits_2_when_the_venue_cannot_be_read(tmp_path: Path, monkeypatch, capsys) -> None:
    from swingdesk.broker import BrokerUnavailable

    _stub_broker(monkeypatch, [], raises=BrokerUnavailable("the venue is down"))
    assert cli.main(["broker", "--data", str(tmp_path)]) == 2
    assert "UNAVAILABLE" in capsys.readouterr().err


# --- `scan --submit`: the machine placing an order, and the switch that stops it ---------------
#
# `CHARTER` A-002 authorises submission with no per-order approval. What `cli.py` owns on that path
# is narrow and worth pinning: it must read the switch, print what it WOULD have submitted whether
# or not it is armed, and never reach the wire when it is stopped. The order's shape is
# `test_submit.py`'s subject.


#: An empty open book, priced with 1R = $100. Every submit fixture starts from one because that is
#: the state the live account is in, and because `_submit` now REFUSES a run whose book was never
#: priced - a cap that cannot be measured stops submission rather than admitting everything.
def _empty_book():
    from swingdesk.trade_management import portfolio

    return portfolio.Book(count=0, open_risk_base=Decimal(0), r_unit=Decimal(100))


def _empty_sector_book():
    from swingdesk.trade_management import portfolio

    return portfolio.SectorBook(
        by_sector={}, unclassified_r=Decimal(0), unmeasured=(), unmeasured_r=Decimal(0),
        total_r=Decimal(0),
    )


def _exposure(instrument_id: str, sector: str = "technology"):
    from swingdesk.contracts.reference import SectorWeight
    from swingdesk.reference_data.classification import Exposure

    return Exposure(
        instrument_id=instrument_id,
        weights=(SectorWeight(sector=sector, weight=Decimal(1)),),
    )


def _trade_outcome(instrument_id: str = "TEST.1", sector: str = "technology"):
    from swingdesk.application.pipeline import InstrumentOutcome
    from swingdesk.contracts.reference import Exchange, Instrument
    from swingdesk.journal_evidence.journal import DecisionRecord
    from swingdesk.trade_management import portfolio
    from swingdesk.trade_management.sizing import RiskSnapshot

    return InstrumentOutcome(
        instrument=Instrument(
            id=instrument_id, ticker=instrument_id, exchange=Exchange.NYSE, currency="USD",
        ),
        decision=DecisionRecord(instrument_id=instrument_id, decision="Trade"),
        risk=RiskSnapshot(
            equity=Decimal(10000), risk_pct=Decimal("1.0"), allowed_risk=Decimal(100),
            entry=Decimal("50.25"), stop=Decimal("45.00"), costs_per_share=Decimal("0.02"),
            risk_per_share=Decimal("5.27"), shares=18, position_value=Decimal("904.50"),
            planned_risk=Decimal("94.86"), parameters=(),
        ),
        # The candidate loop's own sector verdict. `_submit` reads `requested_r` and the exposure
        # off it rather than recomputing either, so a fixture without one is a run that reached a
        # `Trade` with no sector verdict - which `_submit` refuses, deliberately.
        sector=portfolio.assess_sector(
            _empty_sector_book(), Decimal(2), _exposure(instrument_id, sector), Decimal(1),
        ),
    )


def _target_registry():
    """A registry carrying a take-profit multiple, because the real one has none.

    `exit.target_r_multiple` is UNSET in production and these tests are about the WIRING, not about
    the value. `test_submit.py` asserts the unset case, which is what a run does today.
    """
    from swingdesk.platform.parameters import ParameterRegistry

    return ParameterRegistry({
        "exit.target_r_multiple": {
            "id": "exit.target_r_multiple", "value": "2.0", "provenance": "assumed:test fixture",
            "status": "assumed", "unit": "R", "named_in": ["M53-T0808"],
        },
        # `DR-032` §3 prices what a resting order of ours is holding, and `DR-010`'s cost model is
        # inside that R. Carried at the committed values, so a fixture cannot flatter the cap.
        "risk.costs_bp_usd": {
            "id": "risk.costs_bp_usd", "value": "50", "provenance": "assumed:DR-010",
            "status": "assumed", "unit": "basis points", "named_in": [],
        },
        "risk.costs_floor_usd": {
            "id": "risk.costs_floor_usd", "value": "0.25", "provenance": "assumed:DR-010",
            "status": "assumed", "unit": "currency per share", "named_in": [],
        },
        # `k.drawdown_pause` is evaluated on every armed submission (`DR-034`): the baseline the
        # equity curve starts from, and the threshold it is compared against.
        "account.equity": {
            "id": "account.equity", "value": "10000", "provenance": "owner",
            "status": "owner", "unit": "USD", "named_in": [],
        },
        "validation.max_allowable_drawdown": {
            "id": "validation.max_allowable_drawdown", "value": "20", "provenance": "owner",
            "status": "owner", "unit": "percent of equity", "named_in": [],
        },
    })


def _result_with_trades(*outcomes, caps=None):
    """A run carrying `Trade` decisions AND everything the ratified caps are measured against.

    The four extra fields are not fixture ceremony: `_submit` applies `risk.max_concurrent_positions`,
    `risk.max_open_risk` and `risk.max_sector_risk` across the run's own output (`DR-027` §10), and
    each of them stops submission when it cannot be measured. A `RunResult` that carries decisions
    and no book is a run that decided without knowing what was already at risk.
    """
    from swingdesk.application.pipeline import RunResult
    from swingdesk.contracts.run import RunManifest, RunMode
    from swingdesk.decision_logic.selection import Selection
    from swingdesk.trade_management import portfolio

    chosen = outcomes or (_trade_outcome(),)
    ordered = tuple(outcome.instrument.id for outcome in chosen)
    return RunResult(
        manifest=RunManifest(
            run_id="RUN-TEST", started_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
            mode=RunMode.LIVE, code_hash="0" * 12, config_hash="1" * 12, snapshot_id="2" * 12,
            calendar_version="c", platform="p",
        ),
        outcomes=list(chosen),
        capacity=portfolio.assess(
            _empty_book(),
            caps or portfolio.Caps(max_open_risk=Decimal(4), max_concurrent=4),
            Decimal(1),
        ),
        sector_book=_empty_sector_book(),
        sector_limit=Decimal(2),
        # The order the names are OFFERED in, which is `CARD-001`'s ranking and never id order.
        selection=Selection(
            selected=frozenset(ordered), ordered=ordered, cutoff=len(ordered), rule="top_decile",
        ),
    )


def _result_with_one_trade():
    return _result_with_trades()


def _stub_submit_client(monkeypatch, sent: list, held=(), live_orders=(), unavailable=None):
    """A venue stub. `held` and `live_orders` are what it already holds - empty by default.

    `DR-027` §11: submission reads the venue before it adds to it, because `positions.duckdb` is
    only ever written by a human and would otherwise read empty on every evening. A stub that
    answered nothing here would test a path production does not take.
    """
    from swingdesk import broker as broker_pkg

    class _Client:
        def __init__(self, arming):
            self.arming = arming

        def positions(self, now):
            if unavailable:
                raise broker_pkg.BrokerUnavailable(unavailable)
            return tuple(held)

        def open_orders(self, now):
            if unavailable:
                raise broker_pkg.BrokerUnavailable(unavailable)
            return tuple(live_orders)

        def submit(self, order, now):
            from swingdesk.contracts.broker import PlacedOrder

            if self.arming.stopped:
                raise broker_pkg.SubmissionStopped(self.arming.reason)
            sent.append(order)
            return PlacedOrder(
                order_id="o-1", client_order_id=order.client_order_id, symbol=order.symbol,
                status="accepted", submitted_at=now, observed_at=now,
            )

    monkeypatch.setattr(
        broker_pkg, "open_client",
        lambda policy=None, transport=None, arming=broker_pkg.STOPPED: _Client(arming),
    )


def test_submit_is_stopped_by_default_and_says_what_it_would_have_sent(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The count prints even when stopped.

    A line that appeared only once the switch was armed would hide the difference between a run
    that had nothing to submit and a run that was stopped from submitting something.
    """
    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)

    printed = capsys.readouterr().out
    assert "1 Trade decision(s) sized and eligible" in printed
    assert "STOPPED" in printed
    assert sent == [], "nothing may reach the venue while the switch is stopped"


def test_an_armed_switch_submits_the_run_s_trade_decisions(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from swingdesk.broker import policy as policy_module

    write = policy_module.load().write
    assert write is not None
    (tmp_path / write.kill_switch_file).write_text(write.armed_marker, encoding="utf-8")

    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)

    printed = capsys.readouterr().out
    assert "armed" in printed
    assert "SENT" in printed
    assert len(sent) == 1
    # The limit is the sizing price and the stop is the sized stop - nothing was re-derived here.
    assert sent[0].limit_price == Decimal("50.25")
    assert sent[0].stop_price == Decimal("45.00")
    assert sent[0].shares == 18
    assert sent[0].client_order_id == "swingdesk-2026-09-01-TEST.1"


def test_a_watch_decision_is_never_submitted(tmp_path: Path, monkeypatch, capsys) -> None:
    from swingdesk.application.pipeline import RunResult
    from swingdesk.broker import policy as policy_module
    from swingdesk.contracts.run import RunManifest, RunMode
    from swingdesk.journal_evidence.journal import DecisionRecord

    write = policy_module.load().write
    assert write is not None
    (tmp_path / write.kill_switch_file).write_text(write.armed_marker, encoding="utf-8")

    outcome = _trade_outcome()
    outcome.decision = DecisionRecord(instrument_id="TEST.1", decision="Watch")
    result = RunResult(
        manifest=RunManifest(
            run_id="RUN-TEST", started_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
            mode=RunMode.LIVE, code_hash="0" * 12, config_hash="1" * 12, snapshot_id="2" * 12,
            calendar_version="c", platform="p",
        ),
        outcomes=[outcome],
    )

    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(result, tmp_path, datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal,
                    _target_registry(), book, bars)
        rows = journal.submissions_for('RUN-TEST')
    assert "0 Trade decision(s)" in capsys.readouterr().out
    assert sent == []
    # Nothing eligible means nothing attempted, so nothing to record. A row here would be the
    # journal asserting an attempt that never happened.
    assert rows == []


def test_every_stopped_attempt_is_journalled(tmp_path: Path, monkeypatch) -> None:
    """`DR-027` 6, and it is most of the record's value.

    Afterwards, a session on which the machine would have entered a name and was stopped is
    otherwise indistinguishable from a session on which it found nothing. Only the row can tell
    them apart, and the reason it carries is the guard's own.
    """
    from swingdesk.journal_evidence.journal import Journal

    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    with Journal(tmp_path / "journal.duckdb") as journal, \
            PositionStore(tmp_path / "positions.duckdb") as book, \
            BarStore(tmp_path / "bars.duckdb") as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = journal.submissions_for("RUN-TEST")

    assert len(rows) == 1
    assert rows[0].outcome == "stopped"
    assert rows[0].instrument_id == "TEST.1"
    assert rows[0].shares == 18
    assert rows[0].limit_price == Decimal("50.25")
    assert rows[0].detail, "a stopped row must say which guard stopped it"
    assert rows[0].venue_order_id is None


def test_a_sent_order_is_journalled_with_the_venue_s_id(tmp_path: Path, monkeypatch) -> None:
    from swingdesk.broker import policy as policy_module
    from swingdesk.journal_evidence.journal import Journal

    write = policy_module.load().write
    assert write is not None
    (tmp_path / write.kill_switch_file).write_text(write.armed_marker, encoding="utf-8")

    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    with Journal(tmp_path / "journal.duckdb") as journal, \
            PositionStore(tmp_path / "positions.duckdb") as book, \
            BarStore(tmp_path / "bars.duckdb") as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = journal.submissions_for("RUN-TEST")

    assert len(rows) == 1
    assert rows[0].outcome == "sent"
    assert rows[0].venue_order_id == "o-1"
    assert rows[0].venue_status == "accepted"
    assert rows[0].client_order_id == "swingdesk-2026-09-01-TEST.1"


def test_a_journal_that_cannot_be_written_does_not_take_the_run_down(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The record matters and the run matters more.

    `a.run_completes` measures decisions and a report, both of which happened before this point.
    A traceback here would lose them over a store write.
    """
    from swingdesk.journal_evidence.journal import Journal

    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    with Journal(tmp_path / "journal.duckdb") as journal, \
            PositionStore(tmp_path / "positions.duckdb") as book, \
            BarStore(tmp_path / "bars.duckdb") as bars:
        monkeypatch.setattr(
            journal, "record_submission",
            lambda submission: (_ for _ in ()).throw(RuntimeError("disk full")),
        )
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)

    assert "NOT JOURNALLED" in capsys.readouterr().err


# --------------------------------------------------------------------------------------------
# The ratified caps, applied across ONE RUN's own output (`DR-027` §10).
#
# Nothing in this file caught the defect these pin, and the reason is worth stating: every submit
# test above carries ONE `Trade`, so the question "do they fit together" could not be asked. On
# 2026-09-02 a real run produced 114 of them, 103.5R against a ratified 4R, and every one was
# admitted because `pipeline` prices the book once and measures each candidate against it alone.
# A fixture with one candidate is not a small version of a fixture with many; it is a different
# thing - the same lesson `daily_run.cmd`'s log-rotation comment records paying for once already.


def test_the_book_cap_binds_across_one_run_s_own_trade_decisions(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Six eligible names, four slots, and only four may reach the venue.

    THE REGRESSION. Before `_submit` allocated, all six went - the book was priced once from an
    empty store and each candidate was judged against that same empty book, so no candidate was
    ever compared with any other.
    """
    from swingdesk.broker import policy as policy_module

    write = policy_module.load().write
    assert write is not None
    (tmp_path / write.kill_switch_file).write_text(write.armed_marker, encoding="utf-8")

    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    # Six different sectors, so the SECTOR cap cannot be what binds and the count cap is isolated.
    sectors = ["technology", "healthcare", "energy", "industrials", "utilities", "real estate"]
    outcomes = [_trade_outcome(f"NAME{n}", sector) for n, sector in enumerate(sectors)]
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_trades(*outcomes), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = {row.instrument_id: row for row in journal.submissions_for("RUN-TEST")}

    assert len(sent) == 4, "risk.max_concurrent_positions is 4 and six names were eligible"
    assert [order.symbol for order in sent] == ["NAME0", "NAME1", "NAME2", "NAME3"], \
        "the four taken are the four the ranking put first, never the first four alphabetically"

    printed = capsys.readouterr().out
    assert "6 Trade decision(s) sized and eligible" in printed
    assert "2 passed over by the ratified caps" in printed

    # EVERY eligible candidate gets a row, including the ones no order was built for. A session on
    # which the machine would have entered six names and took four is otherwise indistinguishable
    # from one on which it found four.
    assert len(rows) == 6
    assert [rows[f"NAME{n}"].outcome for n in range(6)] == \
        ["sent", "sent", "sent", "sent", "stopped", "stopped"]
    assert "risk.max_concurrent_positions" in (rows["NAME4"].detail or "")


def test_the_sector_cap_binds_across_one_run_s_own_trade_decisions(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Four slots free, four names, all one sector - and 2R is what stops the third.

    The count cap is deliberately not the binding one here: `risk.max_sector_risk` has to bind on
    its own, or a run that concentrated its whole book in one theme would clear every check by
    being small enough.
    """
    from swingdesk.broker import policy as policy_module

    write = policy_module.load().write
    assert write is not None
    (tmp_path / write.kill_switch_file).write_text(write.armed_marker, encoding="utf-8")

    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    outcomes = [_trade_outcome(f"TECH{n}", "technology") for n in range(4)]
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_trades(*outcomes), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = {row.instrument_id: row for row in journal.submissions_for("RUN-TEST")}

    assert len(sent) == 2, "each name is 1R and risk.max_sector_risk allows 2R in one sector"
    assert rows["TECH2"].outcome == "stopped"
    assert "technology" in (rows["TECH2"].detail or "")
    assert "risk.max_sector_risk" in (rows["TECH2"].detail or "")


def test_a_candidate_the_caps_pass_over_does_not_stop_the_ones_behind_it(
    tmp_path: Path, monkeypatch
) -> None:
    """A full sector passes over one name; a name in a different sector still goes.

    `requested_r` varies per candidate because the share count rounds down, so a walk that halted
    on the first refusal would leave capacity unused for a reason that is not a cap - the same
    reasoning `pipeline` applies to `result.capacity` not being overwritten by a later admission.
    """
    from swingdesk.broker import policy as policy_module

    write = policy_module.load().write
    assert write is not None
    (tmp_path / write.kill_switch_file).write_text(write.armed_marker, encoding="utf-8")

    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    outcomes = [
        _trade_outcome("TECH0", "technology"),
        _trade_outcome("TECH1", "technology"),
        _trade_outcome("TECH2", "technology"),   # third in technology - passed over at 2R
        _trade_outcome("ENERGY0", "energy"),     # behind it, and its own sector is empty
    ]
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_trades(*outcomes), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)

    assert [order.symbol for order in sent] == ["TECH0", "TECH1", "ENERGY0"]


def test_submission_stops_when_a_cap_could_not_be_measured(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """UNAVAILABLE is STOPPED here, and the polarity is the whole point.

    `DR-025` §2.1 records this project shipping a guard whose refusal ADMITTED the candidate, so
    "fail closed" read correct and behaved backwards. At a venue that inversion is paid for in
    orders, so every un-measurable cap is asserted separately rather than trusted to one branch.
    """
    from swingdesk.broker import policy as policy_module

    write = policy_module.load().write
    assert write is not None
    (tmp_path / write.kill_switch_file).write_text(write.armed_marker, encoding="utf-8")

    for field in ("capacity", "sector_book", "sector_limit", "selection"):
        sent: list = []
        _stub_submit_client(monkeypatch, sent)
        result = _result_with_trades()
        setattr(result, field, None)
        with Journal(tmp_path / f'journal-{field}.duckdb') as journal, \
                PositionStore(tmp_path / f'positions-{field}.duckdb') as book, \
                BarStore(tmp_path / f'bars-{field}.duckdb') as bars:
            cli._submit(result, tmp_path, datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
                        journal, _target_registry(), book, bars)
            rows = journal.submissions_for("RUN-TEST")

        assert sent == [], f"an armed switch must not submit while {field} is unmeasured"
        assert [row.outcome for row in rows] == ["stopped"], \
            f"the attempt is still recorded when {field} stopped it"
        assert "STOPPED" in capsys.readouterr().err


# --------------------------------------------------------------------------------------------
# The venue is asked what it already holds, before anything is added (`DR-027` §11).
#
# §10's caps are measured against `positions.duckdb`, which NOTHING writes automatically -
# `open-position` and `respond` are both commands a person runs. Four fills tonight that nobody
# records leave the book reading empty tomorrow, and the caps then take four MORE names. §10
# bounded a run against itself; these bound it against every run before it.


def _venue_position(symbol: str, shares: str = "10", entry: str = "50.00"):
    """A holding at the venue. `shares` and `entry` are arguments because `reconcile` compares both.

    `DR-035` runs the full reconciliation before anything is added, so a fixture whose book and
    venue disagree about a share count stops the run - correctly, and it would otherwise look like
    the test's own subject failing.
    """
    from swingdesk.contracts.broker import BrokerPosition, PositionSide

    return BrokerPosition(
        symbol=symbol, asset_class="us_equity", exchange="NYSE", side=PositionSide.LONG,
        shares=Decimal(shares), average_entry_price=Decimal(entry),
        observed_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
    )


def _venue_order(symbol: str):
    from swingdesk.contracts.broker import PlacedOrder

    return PlacedOrder(
        order_id=f"o-{symbol}", client_order_id=f"swingdesk-2026-09-01-{symbol}", symbol=symbol,
        status="new", submitted_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
        observed_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
    )


def _armed(tmp_path: Path) -> None:
    from swingdesk.broker import policy as policy_module

    write = policy_module.load().write
    assert write is not None
    (tmp_path / write.kill_switch_file).write_text(write.armed_marker, encoding="utf-8")


def test_a_position_the_venue_holds_and_the_book_does_not_stops_submission(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """THE REGRESSION. Last night's fill, unrecorded, must stop tonight's entries.

    Without this the book reads empty every evening and the ratified caps take four more names on
    each of them - four tonight, four tomorrow, against a cap of four in total.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent, held=[_venue_position("LEFTOVER")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = journal.submissions_for("RUN-TEST")

    assert sent == [], "nothing may be added to a book the venue and this system disagree about"
    printed = capsys.readouterr().err
    assert "TECH" in printed, "the course's own code for the two disagreeing"
    assert "LEFTOVER" in printed
    assert [row.outcome for row in rows] == ["stopped"]
    assert "TECH" in (rows[0].detail or "")


def test_an_unfilled_order_at_the_venue_also_stops_submission(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A resting bracket is committed exposure even though it is not a position.

    Counting only FILLED positions is what would let the same name be entered on two consecutive
    evenings: last night's order had not filled yet, so the book had nothing to record.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent, live_orders=[_venue_order("RESTING")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)

    assert sent == []
    assert "RESTING" in capsys.readouterr().err


def test_a_venue_that_cannot_be_read_stops_submission(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """UNAVAILABLE is STOPPED. A venue whose holdings are unknown is not a venue to add to."""
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent, unavailable="connection reset")
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = journal.submissions_for("RUN-TEST")

    assert sent == []
    assert "connection reset" in capsys.readouterr().err
    assert [row.outcome for row in rows] == ["stopped"]


def test_the_venue_is_not_read_at_all_while_the_switch_is_stopped(
    tmp_path: Path, monkeypatch
) -> None:
    """Arming is checked FIRST, which is `AlpacaClient.guards`' own ordering and reason.

    A refusal reporting *the venue is unreachable* when the truth is *the owner never armed it*
    sends somebody to debug a network at 18:31. The switch is absent here, so a venue that raises
    on every read must never be touched.
    """
    sent: list = []
    _stub_submit_client(monkeypatch, sent, unavailable="this must never be reached")
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = journal.submissions_for("RUN-TEST")

    assert sent == []
    # Stopped by the SWITCH, never by the venue - the reason names the file, not the network.
    assert [row.outcome for row in rows] == ["stopped"]
    assert "arms it" in (rows[0].detail or "")


def test_a_position_both_sides_carry_does_not_stop_submission(
    tmp_path: Path, monkeypatch
) -> None:
    """Recording the fill is what clears the way, and the caps then do the rest.

    The guard must not be a permanent halt once anything is ever held: a book that agrees with the
    venue is exactly the state submission is designed for.
    """
    from swingdesk.contracts.position import Position

    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent, held=[_venue_position("KNOWN")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        book.record(Position(
            position_id="POS-KNOWN-2026-09-01", version=1, instrument_id="KNOWN",
            opened_on=date(2026, 9, 1), entry_price=Decimal(50), shares=10,
            initial_stop=Decimal(45), current_stop=Decimal(45),
            initial_costs_per_share=Decimal("0.25"),
            knowledge_time=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
        ))
        # A recorded position needs a bar to be valued on, or `k.drawdown_pause` reports
        # UNAVAILABLE and stops the run (`DR-034`) - which is the guard being right about a
        # fixture that held something nobody could price.
        _bars_for(bars, "KNOWN", ((date(2026, 9, 1), "50.00"),),
                  knowledge=datetime(2026, 9, 1, 20, 30, tzinfo=UTC))
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 1, 21, 0, tzinfo=UTC), journal, _target_registry(), book, bars)

    assert len(sent) == 1, "the venue and the book agree, so the caps alone decide"


def test_uncommitted_exposure_ignores_a_book_position_this_venue_cannot_hold() -> None:
    """A `.TO` holding is not something a US venue failed to report (`AGENTS.md` §3).

    Scope-symmetric with `reconcile`: an out-of-scope BOOK position is not a finding, while a venue
    symbol matching no book position always is.
    """
    from swingdesk.broker import uncommitted_exposure
    from swingdesk.contracts.position import Position

    canadian = Position(
        position_id="POS-CNQ.TO-2026-09-01", version=1, instrument_id="CNQ.TO",
        opened_on=date(2026, 9, 1), entry_price=Decimal(50), shares=10,
        initial_stop=Decimal(45), current_stop=Decimal(45),
        initial_costs_per_share=Decimal("0.25"),
        knowledge_time=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
    )
    assert uncommitted_exposure([canadian], [], [], "NYSE") == ()
    assert uncommitted_exposure([canadian], [_venue_position("AAPL")], [], "NYSE") == ("AAPL",)


# --------------------------------------------------------------------------------------------
# `sync-fills`: the step that was a person (`DR-031`).
#
# DR-027 section 11 stops submission whenever the venue holds something the book does not carry.
# That was correct and it made the machine one that ran once, because `positions.duckdb` was
# written only by hand. This closes the loop - and the tests that matter are the ones asserting
# what it will NOT adopt.


def _sync_args(tmp_path: Path, dry_run: bool = False):
    import argparse

    return argparse.Namespace(
        data=tmp_path, as_of="2026-09-03T22:30:00", dry_run=dry_run,
    )


def _fill(symbol: str, order_id: str = "o-1", when: str = "2026-09-02T14:31:00+00:00"):
    from swingdesk.contracts.broker import BrokerFill, FillKind, Side

    return BrokerFill(
        activity_id=f"a-{symbol}", order_id=order_id, symbol=symbol, side=Side.BUY,
        kind=FillKind.FILL, transaction_time=datetime.fromisoformat(when),
        price=Decimal("66.46"), shares=Decimal(17),
        observed_at=datetime(2026, 9, 3, 22, 30, tzinfo=UTC),
    )


def _stub_read_client(monkeypatch, held=(), fills=()):
    from swingdesk import broker as broker_pkg

    class _Client:
        def positions(self, now):
            return tuple(held)

        def fills(self, now, after=None):
            return tuple(fills)

    monkeypatch.setattr(
        broker_pkg, "open_client",
        lambda policy=None, transport=None, arming=broker_pkg.STOPPED: _Client(),
    )


def _sent_submission(instrument_id: str, stop: str = "45.00"):
    from swingdesk.journal_evidence.journal import Submission

    return Submission(
        run_id="RUN-SENT", client_order_id=f"swingdesk-2026-09-02-{instrument_id}",
        attempted_at=datetime(2026, 9, 2, 22, 31, tzinfo=UTC), session_date=date(2026, 9, 1),
        instrument_id=instrument_id, shares=17, limit_price=Decimal("50.00"),
        stop_price=Decimal(stop), outcome="sent", venue_order_id="o-1", venue_status="accepted",
    )


def test_sync_records_a_position_for_an_entry_this_system_placed(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """THE LOOP CLOSING. The stop comes from our journal, the price from the venue."""
    _stub_read_client(monkeypatch, held=[_venue_position("AIS")], fills=[_fill("AIS")])
    with Journal(tmp_path / "journal.duckdb") as journal:
        journal.record_submission(_sent_submission("AIS"))

    assert cli._sync_fills(_sync_args(tmp_path)) == 0

    with PositionStore(tmp_path / "positions.duckdb") as store:
        book = store.open_as_of(datetime(2026, 9, 3, 22, 30, tzinfo=UTC))
    assert [p.instrument_id for p in book] == ["AIS"]
    position = book[0]
    assert position.entry_price == Decimal("50.00"), "the VENUE's average entry price"
    assert position.initial_stop == Decimal("45.00"), "OUR stop, from the journal"
    assert position.current_stop == position.initial_stop
    assert position.opened_on == date(2026, 9, 2), "the session the FILL happened in"
    assert position.strategy == "CARD-001"
    assert "RECORDED" in capsys.readouterr().out


def test_sync_refuses_a_holding_that_traces_to_no_order_this_system_sent(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Somebody traded by hand. Adopting it would be this command deciding that anything at the
    venue must have been ours - the assumption most likely to be wrong on the day it matters.

    Exit 3, and DR-027 section 11's guard goes on pausing new entries.
    """
    _stub_read_client(monkeypatch, held=[_venue_position("MYSTERY")], fills=[_fill("MYSTERY")])
    with Journal(tmp_path / "journal.duckdb") as journal:
        journal.record_submission(_sent_submission("SOMETHINGELSE"))

    assert cli._sync_fills(_sync_args(tmp_path)) == 3

    with PositionStore(tmp_path / "positions.duckdb") as store:
        assert store.open_as_of(datetime(2026, 9, 3, 22, 30, tzinfo=UTC)) == []
    printed = capsys.readouterr().err
    assert "TECH" in printed
    assert "MYSTERY" in printed


def test_sync_will_not_adopt_against_an_attempt_that_never_reached_the_venue(
    tmp_path: Path, monkeypatch
) -> None:
    """A `stopped` row is an attempt a guard refused, so no holding can have come from one.

    Adopting against it would credit this system with an order it did not place and - worse - write
    that attempt's stop into the book as though it were live at the venue.
    """
    from swingdesk.journal_evidence.journal import Submission

    _stub_read_client(monkeypatch, held=[_venue_position("AIS")], fills=[_fill("AIS")])
    with Journal(tmp_path / "journal.duckdb") as journal:
        journal.record_submission(Submission(
            run_id="RUN-STOPPED", client_order_id="swingdesk-2026-09-02-AIS",
            attempted_at=datetime(2026, 9, 2, 22, 31, tzinfo=UTC), session_date=date(2026, 9, 1),
            instrument_id="AIS", shares=17, limit_price=Decimal("50.00"),
            stop_price=Decimal("45.00"), outcome="stopped", detail="the switch was absent",
        ))

    assert cli._sync_fills(_sync_args(tmp_path)) == 3

    with PositionStore(tmp_path / "positions.duckdb") as store:
        assert store.open_as_of(datetime(2026, 9, 3, 22, 30, tzinfo=UTC)) == []


def test_sync_is_idempotent_and_leaves_a_holding_the_book_already_carries_alone(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """It runs before every evening pass, so running twice must not write twice."""
    _stub_read_client(monkeypatch, held=[_venue_position("AIS")], fills=[_fill("AIS")])
    with Journal(tmp_path / "journal.duckdb") as journal:
        journal.record_submission(_sent_submission("AIS"))

    assert cli._sync_fills(_sync_args(tmp_path)) == 0
    capsys.readouterr()
    assert cli._sync_fills(_sync_args(tmp_path)) == 0

    with PositionStore(tmp_path / "positions.duckdb") as store:
        assert len(store.open_as_of(datetime(2026, 9, 3, 22, 30, tzinfo=UTC))) == 1
    assert "nothing to record" in capsys.readouterr().out


def test_sync_dry_run_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    _stub_read_client(monkeypatch, held=[_venue_position("AIS")], fills=[_fill("AIS")])
    with Journal(tmp_path / "journal.duckdb") as journal:
        journal.record_submission(_sent_submission("AIS"))

    assert cli._sync_fills(_sync_args(tmp_path, dry_run=True)) == 0

    with PositionStore(tmp_path / "positions.duckdb") as store:
        assert store.open_as_of(datetime(2026, 9, 3, 22, 30, tzinfo=UTC)) == []
    assert "WOULD RECORD" in capsys.readouterr().out


def test_sync_refuses_a_holding_it_cannot_date(tmp_path: Path, monkeypatch, capsys) -> None:
    """`opened_on` is what every holding-period rule counts from, so it is never taken from a clock."""
    _stub_read_client(monkeypatch, held=[_venue_position("AIS")], fills=[])
    with Journal(tmp_path / "journal.duckdb") as journal:
        journal.record_submission(_sent_submission("AIS"))

    assert cli._sync_fills(_sync_args(tmp_path)) == 2

    with PositionStore(tmp_path / "positions.duckdb") as store:
        assert store.open_as_of(datetime(2026, 9, 3, 22, 30, tzinfo=UTC)) == []
    assert "activities feed" in capsys.readouterr().err


def test_the_journal_returns_only_a_sent_submission(tmp_path: Path) -> None:
    """`latest_sent_submission` is the join `sync-fills` trusts, so its filter is asserted directly."""
    from swingdesk.journal_evidence.journal import Submission

    with Journal(tmp_path / "journal.duckdb") as journal:
        journal.record_submission(Submission(
            run_id="R1", client_order_id="swingdesk-2026-09-01-AIS",
            attempted_at=datetime(2026, 9, 1, 22, 31, tzinfo=UTC), session_date=date(2026, 8, 31),
            instrument_id="AIS", shares=1, limit_price=Decimal(1), stop_price=Decimal("0.5"),
            outcome="stopped", detail="the switch was absent",
        ))
        assert journal.latest_sent_submission("AIS") is None

        journal.record_submission(_sent_submission("AIS", stop="45.00"))
        found = journal.latest_sent_submission("AIS")
        assert found is not None
        assert found.stop_price == Decimal("45.00")
        assert journal.latest_sent_submission("NOTHING") is None


# --------------------------------------------------------------------------------------------
# `DR-032`: our own resting orders stop halting the run, and start consuming capacity.
#
# DR-027 section 11 halted on anything at the venue the book did not carry - INCLUDING the orders
# this system had just sent. That killed DR-015's 19:30 retry: the first pass submitted, the second
# found its own orders resting, called them a mismatch and stopped.
#
# The fix has two halves and only both together are safe. Excluding them from the halt without
# counting them in the caps would let the retry add four more names on top of four already resting.


def _our_order(symbol: str, order_id: str | None = None):
    """A live order carrying an id this system journalled before sending."""
    from swingdesk.contracts.broker import PlacedOrder

    return PlacedOrder(
        order_id=f"venue-{symbol}",
        client_order_id=order_id or f"swingdesk-2026-09-02-{symbol}",
        symbol=symbol, status="new",
        submitted_at=datetime(2026, 9, 2, 22, 31, tzinfo=UTC),
        observed_at=datetime(2026, 9, 2, 23, 31, tzinfo=UTC),
    )


def _sent_for(instrument_id: str, shares: int = 17, limit: str = "50.00", stop: str = "45.00"):
    from swingdesk.journal_evidence.journal import Submission

    return Submission(
        run_id="RUN-FIRST-PASS", client_order_id=f"swingdesk-2026-09-02-{instrument_id}",
        attempted_at=datetime(2026, 9, 2, 22, 31, tzinfo=UTC), session_date=date(2026, 9, 2),
        instrument_id=instrument_id, shares=shares, limit_price=Decimal(limit),
        stop_price=Decimal(stop), outcome="sent", venue_order_id=f"venue-{instrument_id}",
        venue_status="accepted",
    )


def test_our_own_resting_order_no_longer_halts_the_retry_pass(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """THE REGRESSION. The 18:30 pass sent it; the 19:30 pass must not call it a mismatch.

    Before this, the second pass found its own orders at the venue, reported TECH and stopped - so
    a candidate that failed on the first pass was never retried at all.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent, live_orders=[_our_order("OURS")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        journal.record_submission(_sent_for("OURS"))
        cli._submit(_result_with_trades(_trade_outcome("LATER", "energy")), tmp_path,
                    datetime(2026, 9, 2, 23, 31, tzinfo=UTC), journal, _target_registry(), book, bars)

    printed = capsys.readouterr()
    assert "TECH" not in printed.err, "an order we sent and journalled is not a mismatch"
    assert [order.symbol for order in sent] == ["LATER"], \
        "the retry may still submit a name the first pass did not"


def test_a_resting_order_of_ours_still_consumes_a_slot_in_the_caps(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """THE OTHER HALF, and without it the fix is the accumulation bug wearing a disguise.

    Four slots, three already resting from the first pass, four fresh candidates: exactly ONE may go.
    """
    _armed(tmp_path)
    sent: list = []
    resting = ["R1", "R2", "R3"]
    _stub_submit_client(monkeypatch, sent, live_orders=[_our_order(s) for s in resting])
    fresh = [_trade_outcome(f"NEW{n}", s) for n, s in
             enumerate(["energy", "utilities", "industrials", "real estate"])]
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        for symbol in resting:
            journal.record_submission(_sent_for(symbol))
        cli._submit(_result_with_trades(*fresh), tmp_path,
                    datetime(2026, 9, 2, 23, 31, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = {row.instrument_id: row for row in journal.submissions_for("RUN-TEST")}

    assert len(sent) == 1, \
        "three slots are held by resting orders and risk.max_concurrent_positions is 4"
    assert sent[0].symbol == "NEW0", "the one taken is the one the ranking put first"
    assert "3 live order(s) of ours already hold" in capsys.readouterr().out
    assert [rows[f"NEW{n}"].outcome for n in range(4)] == ["sent", "stopped", "stopped", "stopped"]


def test_an_order_we_did_not_send_still_halts_everything(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The exemption is narrow on purpose: it is our JOURNAL that makes an order ours.

    An id shaped like ours but never journalled is somebody typing into the dashboard, and it must
    still stop the run. A prefix test would have adopted it.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(
        monkeypatch, sent,
        live_orders=[_our_order("IMPOSTER", order_id="swingdesk-2026-09-02-IMPOSTER")],
    )
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        # Nothing recorded: the id was never put on the wire by this system.
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 31, tzinfo=UTC), journal, _target_registry(), book, bars)

    assert sent == []
    printed = capsys.readouterr().err
    assert "TECH" in printed
    assert "IMPOSTER" in printed


def test_a_stopped_attempt_does_not_make_an_order_ours(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """`sent` only. An attempt a guard stopped never reached the venue, so no order carries its id."""
    from swingdesk.journal_evidence.journal import Submission

    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent, live_orders=[_our_order("GHOST")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        journal.record_submission(Submission(
            run_id="RUN-STOPPED", client_order_id="swingdesk-2026-09-02-GHOST",
            attempted_at=datetime(2026, 9, 2, 22, 31, tzinfo=UTC), session_date=date(2026, 9, 2),
            instrument_id="GHOST", shares=17, limit_price=Decimal("50.00"),
            stop_price=Decimal("45.00"), outcome="stopped", detail="the switch was absent",
        ))
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 31, tzinfo=UTC), journal, _target_registry(), book, bars)

    assert sent == []
    assert "TECH" in capsys.readouterr().err


def test_a_disarmed_run_still_reports_which_names_the_caps_would_have_taken(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The venue is read only after the arming check, so this path allocates against the book alone.

    It must still say four-of-six rather than collapsing to "stopped", which is DR-027 section 6's
    whole argument: a run that would have entered six names and was stopped has to be
    distinguishable from one that found nothing.
    """
    sent: list = []
    _stub_submit_client(monkeypatch, sent, unavailable="the venue must not be reached here")
    sectors = ["technology", "healthcare", "energy", "industrials", "utilities", "real estate"]
    outcomes = [_trade_outcome(f"N{n}", s) for n, s in enumerate(sectors)]
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_trades(*outcomes), tmp_path,
                    datetime(2026, 9, 2, 23, 31, tzinfo=UTC), journal, _target_registry(), book, bars)
        rows = {row.instrument_id: row for row in journal.submissions_for("RUN-TEST")}

    assert sent == []
    printed = capsys.readouterr().out
    assert "2 passed over by the ratified caps; 4 within them" in printed
    assert "arms it" in (rows["N0"].detail or ""), "the four say the SWITCH stopped them"
    assert "max_concurrent" in (rows["N4"].detail or ""), "the two say the CAP passed them over"


def test_ours_reads_the_journal_and_never_the_shape_of_an_id() -> None:
    """`ours` is asserted directly, because the whole exemption rests on how narrow it is."""
    from swingdesk.broker import ours

    mine = _our_order("MINE")
    theirs = _our_order("THEIRS", order_id="swingdesk-2026-09-02-THEIRS")
    known = frozenset({"swingdesk-2026-09-02-MINE"})

    assert [o.symbol for o in ours([mine, theirs], known)] == ["MINE"]
    assert ours([mine, theirs], frozenset()) == ()


def test_a_partly_filled_order_holds_only_the_part_that_has_not_filled(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """`DR-032` §3.1. A partial fill is otherwise counted twice, against one name.

    `sync-fills` records a position for the shares that filled and the book prices those; counting
    the whole order again on top reads 1.29R against a real 1R on a 17-share order with 5 filled.
    Over-counting refuses a legitimate candidate rather than admitting an illegitimate one - the
    safe direction, and still the wrong number.
    """
    from swingdesk.contracts.broker import PlacedOrder

    _armed(tmp_path)
    sent: list = []
    partly = PlacedOrder(
        order_id="venue-PART", client_order_id="swingdesk-2026-09-02-PART", symbol="PART",
        status="partially_filled", submitted_at=datetime(2026, 9, 2, 22, 31, tzinfo=UTC),
        filled_shares=Decimal(5), observed_at=datetime(2026, 9, 2, 23, 31, tzinfo=UTC),
    )
    _stub_submit_client(monkeypatch, sent, live_orders=[partly])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        journal.record_submission(_sent_for("PART", shares=17))
        cli._submit(_result_with_trades(_trade_outcome("FRESH", "energy")), tmp_path,
                    datetime(2026, 9, 2, 23, 31, tzinfo=UTC), journal, _target_registry(), book, bars)

    printed = capsys.readouterr().out
    # 12 of 17 shares still resting at (50.00 - 45.00 + 0.25) = 5.25/share against a 100 r_unit.
    assert "1 live order(s) of ours already hold 0.63R" in printed, printed
    assert [order.symbol for order in sent] == ["FRESH"]


def test_a_fully_filled_order_still_listed_open_holds_nothing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A filled entry stays visible as a bracket LEG. The position it produced holds the slot.

    Counting the leg as well would charge one name twice over - once as a position the book prices
    and once as an order that no longer has anything left to fill.
    """
    from swingdesk.contracts.broker import PlacedOrder

    _armed(tmp_path)
    sent: list = []
    leg = PlacedOrder(
        order_id="venue-DONE", client_order_id="swingdesk-2026-09-02-DONE", symbol="DONE",
        status="new", submitted_at=datetime(2026, 9, 2, 22, 31, tzinfo=UTC),
        filled_shares=Decimal(17), observed_at=datetime(2026, 9, 2, 23, 31, tzinfo=UTC),
    )
    _stub_submit_client(monkeypatch, sent, live_orders=[leg])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        journal.record_submission(_sent_for("DONE", shares=17))
        cli._submit(_result_with_trades(_trade_outcome("FRESH", "energy")), tmp_path,
                    datetime(2026, 9, 2, 23, 31, tzinfo=UTC), journal, _target_registry(), book, bars)

    assert "already hold" not in capsys.readouterr().out
    assert [order.symbol for order in sent] == ["FRESH"]


# --------------------------------------------------------------------------------------------
# `DR-034`: the only ratified `live` criterion can finally fire.
#
# `k.drawdown_pause` is ratified, scope `live`, threshold owner-set at 20 percent, and NOTHING in
# `src/` ever called the measurement - so the project's own kill switch was decorative. TODO.md
# section 1 says it was harmless "today and only today", and today ended when four orders went to a
# venue on 2026-09-02.


def _bars_for(bars: BarStore, instrument_id: str, prices, knowledge=None) -> None:
    """Daily bars at a flat price per session, so a position can be marked to market.

    Any position in the book needs one, or `k.drawdown_pause` reports UNAVAILABLE and stops the run
    (`DR-034`) - which is correct, and makes an unpriced fixture a test failure rather than a
    silent 0.00%.
    """
    from swingdesk.contracts.market import Bar, Interval, Series

    knowledge = knowledge or datetime(2026, 9, 2, 22, 0, tzinfo=UTC)
    bars.write(
        [
            Bar(
                instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(s.year, s.month, s.day, 20, 0, tzinfo=UTC), session_date=s,
                open=Decimal(price), high=Decimal(price), low=Decimal(price),
                close=Decimal(price), volume=1_000_000, knowledge_time=knowledge,
            )
            for s, price in prices
        ],
        knowledge_time=knowledge,
    )


def _fallen_book(book: PositionStore, bars: BarStore, *, peak: str, trough: str) -> None:
    """A position bought at `peak` and now marked at `trough`, with bars to mark it on.

    100 shares against the 10,000 baseline the fixture registry carries, so the arithmetic is
    readable: at 50.00 the position IS half the account.
    """
    from swingdesk.contracts.position import Position

    book.record(Position(
        position_id="POS-FALLEN-2026-09-01", version=1, instrument_id="FALLEN",
        opened_on=date(2026, 9, 1), entry_price=Decimal(peak), shares=100,
        initial_stop=Decimal("1.00"), current_stop=Decimal("1.00"),
        initial_costs_per_share=Decimal("0.25"),
        knowledge_time=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
    ))
    _bars_for(bars, "FALLEN", ((date(2026, 9, 1), peak), (date(2026, 9, 2), trough)))


def test_a_book_past_the_drawdown_limit_pauses_new_entries(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """THE REGRESSION, and it is the whole point of the finding TODO.md section 1 opens with.

    100 shares bought at 50.00 - half a 10,000 account - marked at 30.00 is a 2,000 unrealised loss
    against a 10,000 peak: 20.00%, which does NOT exceed a 20% limit. At 25.00 it is 25.00% and does.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent,
                        held=[_venue_position("FALLEN", shares="100", entry="50.00")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        _fallen_book(book, bars, peak="50.00", trough="25.00")
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 0, tzinfo=UTC), journal, _target_registry(),
                    book, bars)
        rows = journal.submissions_for("RUN-TEST")

    assert sent == [], "a book this far down may not add to itself"
    printed = capsys.readouterr().err
    assert "k.drawdown_pause" in printed
    assert "PAUSE - not kill" in printed
    assert "risk_off_ladder is unset" in printed, \
        "the size-reduction half is the owner's and must not be quietly approximated"
    assert [r.outcome for r in rows] == ["stopped"]


def test_a_book_inside_the_limit_still_submits(tmp_path: Path, monkeypatch, capsys) -> None:
    """The guard must bind at the ratified number and nowhere else.

    Exactly 20.00% does not EXCEED a 20% limit - `Drawdown.breaches` is a strict comparison, and a
    kill switch that fired one basis point early would be a different threshold than the one ruled.

    THE COSTS ARE IN THE CURVE, which is why the peak is 9,975 rather than 10,000: 100 shares at
    `initial_costs_per_share` 0.25 spends 25 the moment the position exists. So 20.00% is a fall of
    1,995, and 50.00 -> 30.05 is exactly that. A fixture that ignored the costs would be asserting
    against arithmetic the system does not do.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent,
                        held=[_venue_position("FALLEN", shares="100", entry="50.00")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        _fallen_book(book, bars, peak="50.00", trough="30.05")
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 0, tzinfo=UTC), journal, _target_registry(),
                    book, bars)

    printed = capsys.readouterr().out
    assert "drawdown 20.00% of a 20% limit" in printed
    assert len(sent) == 1, "20.00% does not exceed 20%"


def test_an_empty_book_reports_zero_rather_than_refusing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """"No answer" and "0.00%" are very different things to print beside a ratified kill switch."""
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent)
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 0, tzinfo=UTC), journal, _target_registry(),
                    book, bars)

    assert "drawdown 0.00% of a 20% limit" in capsys.readouterr().out
    assert len(sent) == 1


def test_a_drawdown_that_cannot_be_measured_stops_submission(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """UNMEASURABLE IS STOPPED, and the polarity is the point.

    A position with no bar to mark it on cannot be priced, so the curve refuses. A kill switch that
    ADMITTED when it could not read the book is `DR-006` section 3's admit-on-unavailable inversion
    on the highest-consequence surface this project has.
    """
    from swingdesk.contracts.position import Position

    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent,
                        held=[_venue_position("UNPRICED", shares="100", entry="50")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        book.record(Position(
            position_id="POS-UNPRICED-2026-09-01", version=1, instrument_id="UNPRICED",
            opened_on=date(2026, 9, 1), entry_price=Decimal(50), shares=100,
            initial_stop=Decimal(45), current_stop=Decimal(45),
            initial_costs_per_share=Decimal("0.25"),
            knowledge_time=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
        ))
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 0, tzinfo=UTC), journal, _target_registry(),
                    book, bars)
        rows = journal.submissions_for("RUN-TEST")

    assert sent == []
    assert "k.drawdown_pause cannot be evaluated" in capsys.readouterr().err
    assert [r.outcome for r in rows] == ["stopped"]


def test_action_kinds_carry_their_real_sequence(tmp_path: Path) -> None:
    """Sequences are monotonic, not contiguous, and `actions_for` deliberately drops them.

    `drawdown._exit_fills` joins a `Fill.sequence` to the kind that settles it, so pairing actions
    with `enumerate` would book a realised gain against an action that never transacted - straight
    into the equity curve `k.drawdown_pause` is measured on.
    """
    from swingdesk.contracts.position import ActionKind, ManagementAction, Position

    with PositionStore(tmp_path / 'positions.duckdb') as book:
        book.record(Position(
            position_id="POS-SEQ-2026-09-01", version=1, instrument_id="SEQ",
            opened_on=date(2026, 9, 1), entry_price=Decimal(50), shares=100,
            initial_stop=Decimal(45), current_stop=Decimal(45),
            initial_costs_per_share=Decimal("0.25"),
            knowledge_time=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
        ))
        for kind in (ActionKind.MOVE_STOP, ActionKind.EXIT_NOW):
            book.propose(ManagementAction(
                position_id="POS-SEQ-2026-09-01", proposed_at=datetime(2026, 9, 2, tzinfo=UTC),
                kind=kind, reason_code="TEST", reason="fixture",
                old_stop=Decimal(45), new_stop=Decimal(46),
            ))
        kinds = book.action_kinds_for("POS-SEQ-2026-09-01")

    assert set(kinds.values()) == {"move_stop", "exit_now"}
    assert all(isinstance(sequence, int) for sequence in kinds)


# --------------------------------------------------------------------------------------------
# `DR-035`: an exit that happened at the venue is not invisible.
#
# `uncommitted_exposure` looks one way - venue to book. It cannot see a position the BOOK still
# carries and the venue no longer holds, which is what a bracket's stop leg firing overnight looks
# like. Nothing closes a position automatically: `closed_on` is written only by `respond` and
# `record-fill`, and the scheduled wrapper never runs `broker`. So a stopped-out position held its
# slot for ever, and after four stop-outs the machine submitted nothing again, silently.


def _booked_and_priced(book: PositionStore, bars: BarStore, symbol: str = "HELD") -> None:
    from swingdesk.contracts.position import Position

    book.record(Position(
        position_id=f"POS-{symbol}-2026-09-01", version=1, instrument_id=symbol,
        opened_on=date(2026, 9, 1), entry_price=Decimal(50), shares=100,
        initial_stop=Decimal(45), current_stop=Decimal(45),
        initial_costs_per_share=Decimal("0.25"),
        knowledge_time=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
    ))
    _bars_for(bars, symbol, ((date(2026, 9, 1), "50.00"), (date(2026, 9, 2), "50.00")))


def test_a_position_the_book_carries_and_the_venue_has_closed_pauses_new_entries(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """THE REGRESSION. A bracket's stop fired overnight and nothing recorded it.

    Before this the run saw an empty venue, `uncommitted_exposure` found nothing to complain about,
    and the caps counted a position that no longer existed - for ever.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent)          # the venue holds NOTHING
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        _booked_and_priced(book, bars)
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 0, tzinfo=UTC), journal, _target_registry(),
                    book, bars)
        rows = journal.submissions_for("RUN-TEST")

    assert sent == [], "a book that describes a position the venue closed bounds nothing"
    printed = capsys.readouterr().err
    assert "TECH" in printed
    assert "HELD" in printed and "book_only" in printed
    assert [r.outcome for r in rows] == ["stopped"]


def test_a_share_count_the_two_sides_disagree_about_pauses_new_entries(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A partial exit nobody recorded looks exactly like this, and the caps would price the wrong R."""
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent,
                        held=[_venue_position("HELD", shares="60", entry="50")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        _booked_and_priced(book, bars)
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 0, tzinfo=UTC), journal, _target_registry(),
                    book, bars)

    assert sent == []
    assert "shares" in capsys.readouterr().err


def test_an_entry_price_the_two_sides_disagree_about_pauses_new_entries(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """`DR-027` §7 already ruled this a stop-submitting condition rather than a note.

    Every R the position reports is denominated in the book's number, so two sides describing
    different trades is not cosmetic.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent,
                        held=[_venue_position("HELD", shares="100", entry="51.25")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        _booked_and_priced(book, bars)
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 0, tzinfo=UTC), journal, _target_registry(),
                    book, bars)

    assert sent == []
    assert "entry_price" in capsys.readouterr().err


def test_a_book_the_venue_agrees_with_still_submits(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The guard must not be a permanent halt the moment anything is ever held.

    Two sides describing the same position is the state submission is designed for, and the caps
    then decide - here the one slot taken leaves three, so the candidate goes.
    """
    _armed(tmp_path)
    sent: list = []
    _stub_submit_client(monkeypatch, sent,
                        held=[_venue_position("HELD", shares="100", entry="50")])
    with Journal(tmp_path / 'journal.duckdb') as journal, \
            PositionStore(tmp_path / 'positions.duckdb') as book, \
            BarStore(tmp_path / 'bars.duckdb') as bars:
        _booked_and_priced(book, bars)
        cli._submit(_result_with_one_trade(), tmp_path,
                    datetime(2026, 9, 2, 23, 0, tzinfo=UTC), journal, _target_registry(),
                    book, bars)

    assert len(sent) == 1
    assert "TECH" not in capsys.readouterr().err
