"""The forward-record report, and the one distinction it must never collapse.

**A store another process is holding and a store with nothing in it produce the same silence.**
Reporting "0 positions, 0 submissions" for a book that is merely locked is the error `AGENTS.md`
§12 calls the most damaging this product can make, and it is the exact error this tool was written
to stop me repeating by hand.

Everything here builds its own DuckDB files in a temporary directory. No live store, no venue.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

REPO = Path(__file__).resolve().parents[1]

POSITIONS = """
CREATE TABLE positions (
    position_id VARCHAR, version INTEGER, instrument_id VARCHAR, opened_on DATE,
    closed_on DATE, entry_price DECIMAL(18,6), shares INTEGER, initial_stop DECIMAL(18,6)
);
"""
SUBMISSIONS = """
CREATE TABLE submissions (
    session_date DATE, outcome VARCHAR, venue_status VARCHAR, instrument_id VARCHAR
);
"""


@pytest.fixture(scope="module")
def report():
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "_forward_record", REPO / "tools" / "forward_record.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def data(tmp_path):
    with duckdb.connect(str(tmp_path / "positions.duckdb")) as book:
        book.execute(POSITIONS)
        book.execute(
            "INSERT INTO positions VALUES "
            "('POS-AIS', 2, 'AIS', DATE '2026-09-03', DATE '2026-09-04', 65.70, 17, 61.70),"
            "('POS-BTSG', 1, 'BTSG', DATE '2026-09-03', NULL, 60.21, 18, 55.08),"
            "('POS-DINO', 1, 'DINO', DATE '2026-09-03', NULL, 105.46, 12, 98.59)"
        )
    with duckdb.connect(str(tmp_path / "journal.duckdb")) as journal:
        journal.execute(SUBMISSIONS)
        journal.execute(
            "INSERT INTO submissions VALUES "
            "(DATE '2026-09-02', 'sent', 'accepted', 'AIS'),"
            "(DATE '2026-09-02', 'sent', 'accepted', 'DINO'),"
            "(DATE '2026-09-02', 'stopped', NULL, 'CM'),"
            "(DATE '2026-09-02', 'stopped', NULL, 'KO'),"
            "(DATE '2026-09-03', 'rejected', NULL, 'SPY')"
        )
    return tmp_path


def test_a_locked_store_is_UNAVAILABLE_and_never_an_empty_record(report, data, capsys, monkeypatch):
    """The distinction the whole file exists for.

    A book nobody can read is not a book with nothing in it. If this ever returns 0 and prints a
    census, the report becomes a machine for saying the forward record is empty every evening the
    daily pass happens to be running - which is every evening.
    """
    def refuse(*_args, **_kwargs):
        raise duckdb.IOException("held by another process")

    monkeypatch.setattr(report.duckdb, "connect", refuse)
    monkeypatch.setattr(sys, "argv", ["forward_record", "--data", str(data)])
    assert report.main() == 2
    printed = capsys.readouterr()
    assert "UNAVAILABLE" in printed.err
    assert "positions.duckdb" in printed.err
    assert "position(s) ever" not in printed.out


def test_read_returns_rows_when_the_store_is_free(report, data):
    rows = report.read(data / "positions.duckdb", "SELECT instrument_id FROM positions")
    assert sorted(r[0] for r in rows) == ["AIS", "BTSG", "DINO"]


def test_open_and_closed_are_told_apart_by_closed_on(report, data, capsys, monkeypatch):
    """`closed_on` is written in one place and is what every count of a completed trade reads.
    Counting a closed position as open would hold a slot in the cap that nothing holds."""
    monkeypatch.setattr(sys, "argv", ["forward_record", "--data", str(data)])
    assert report.main() == 0
    printed = capsys.readouterr().out
    assert "3 position(s) ever, 2 open, 1 closed" in printed
    assert "closed 2026-09-04" in printed


def test_the_accepted_orders_are_counted_apart_from_what_the_guards_refused(
    report, data, capsys, monkeypatch
):
    """Two numbers that a single "submissions" count would merge, and they mean opposite things:
    one is what reached the venue, the other is the caps doing their job."""
    monkeypatch.setattr(sys, "argv", ["forward_record", "--data", str(data)])
    report.main()
    printed = capsys.readouterr().out
    assert "2 order(s) accepted by the venue" in printed
    assert "2 not sent - stopped" in printed
    assert "1 not sent - rejected" in printed


def test_the_switch_reports_STOPPED_when_the_file_is_absent(report, data, capsys, monkeypatch):
    """`DR-027` §4.2 defaults to stopped, and a report that stayed silent about a disarmed switch
    would describe a record that is not being collected as one that is."""
    monkeypatch.setattr(sys, "argv", ["forward_record", "--data", str(data)])
    report.main()
    assert "STOPPED" in capsys.readouterr().out


def test_the_switch_reports_ARMED_and_since_when(report, data, capsys, monkeypatch):
    (data / report.ARMED).write_text("armed", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["forward_record", "--data", str(data)])
    report.main()
    printed = capsys.readouterr().out
    assert "ARMED since" in printed


def test_risk_at_entry_is_the_stop_distance_and_not_the_notional(report, data, capsys, monkeypatch):
    """`RISK_SPEC` 2: R is `entry - stop`, per share, times shares. Printing the notional instead
    would make a 17-share position look like a thousand-dollar risk."""
    monkeypatch.setattr(sys, "argv", ["forward_record", "--data", str(data)])
    report.main()
    printed = capsys.readouterr().out
    # AIS: (65.70 - 61.70) * 17 = 68.00, not 65.70 * 17 = 1116.90
    assert "68.00" in printed
    assert "1116" not in printed


def test_an_absent_store_says_ABSENT_and_not_held_by_another_process(
    report, tmp_path, capsys, monkeypatch
):
    """DuckDB raises the same IOException for both, and the first version of this tool told an
    operator to wait for a daily pass that had already finished. A message that sends somebody
    looking for the wrong thing is worse than no message."""
    monkeypatch.setattr(sys, "argv", ["forward_record", "--data", str(tmp_path)])
    assert report.main() == 2
    printed = capsys.readouterr().err
    assert "UNAVAILABLE" in printed
    assert "does not exist" in printed
    assert "held by another process" not in printed
