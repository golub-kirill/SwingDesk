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
