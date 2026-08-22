"""`tools/remove_unclosed_bars.py`: proof that it removes the bad bars and ONLY the bad bars.

This script deletes from an append-only store, which `CHANGE_MANAGEMENT.md` §3 otherwise forbids and
which the owner authorised for one specific backlog on 2026-08-18. A deletion cannot be undone by
superseding it, so the question these tests answer is not "does it work" but **"can it take anything
it should not"**.

Every case runs the REAL script against a REAL store built here, with bars whose correctness is
known by construction - a closed session and an unclosed one, on the same day, for the same
instrument where possible. Nothing is mocked, so a defect in the predicate shows up as a deleted row
rather than as a passing assertion about an intention.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from tests.conftest import TEST_CA, TEST_US

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.contracts.reference import Exchange
from swingdesk.market_data import BarStore
from swingdesk.reference_data import calendar as cal

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import remove_unclosed_bars as tool  # noqa: E402

#: A real NYSE session and a real TSX session, so the calendar - not a fixture - decides.
NYSE_SESSION = date(2026, 1, 15)
TSX_SESSION = date(2026, 1, 15)


def _close_time(instrument_id: str, session_date: date) -> datetime:
    session = cal.session(cal.exchange_for(instrument_id), session_date)
    assert session is not None, "the fixture assumes a real trading session"
    return session.close_time


def _bar(instrument_id: str, session_date: date, knowledge_time: datetime,
         close: str = "100.00") -> Bar:
    return Bar(
        instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
        event_time=datetime(session_date.year, session_date.month, session_date.day, tzinfo=UTC),
        session_date=session_date, open=Decimal(close), high=Decimal(close),
        low=Decimal(close), close=Decimal(close), volume=1_000, knowledge_time=knowledge_time,
    )


def _write_bypassing_the_guard(store: BarStore, bar: Bar, knowledge_time: datetime) -> None:
    """Insert a row the way the 2026-08-03 fetch did - before `BarStore.write` had a guard.

    The guard now refuses exactly these, so the backlog they represent cannot be recreated through
    the public API. Writing directly is the only way to reproduce the state this script exists to
    clean up, and reaching into the connection is what makes that honest rather than impossible.
    """
    store._connection.execute(
        "INSERT OR REPLACE INTO bars (instrument_id, interval, series, event_time, session_date, "
        "knowledge_time, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [bar.instrument_id, bar.interval.value, bar.series.value, bar.event_time, bar.session_date,
         knowledge_time, bar.open, bar.high, bar.low, bar.close, bar.volume],
    )


@pytest.fixture
def store_path(tmp_path):
    """A store holding one unclosed bar and several bars that must survive it."""
    path = tmp_path / "bars.duckdb"
    with BarStore(path) as store:
        after = _close_time(TEST_US.id, NYSE_SESSION)
        during = after - timedelta(hours=2)

        # THE BAD ONE: captured mid-session.
        _write_bypassing_the_guard(store, _bar(TEST_US.id, NYSE_SESSION, during, "95.70"), during)

        # Must survive: the same instrument and session, captured after the close.
        store.write([_bar(TEST_US.id, NYSE_SESSION, after, "100.00")], after)
        # Must survive: an EARLIER session captured by that same mid-session fetch. This is the
        # 2026-07-27..07-31 case - the fetch was early for today, not for last week.
        earlier = date(2026, 1, 14)
        assert cal.is_open(Exchange.NYSE, earlier)
        store.write([_bar(TEST_US.id, earlier, during, "90.00")], during)
        # Must survive: a different exchange, whose calendar the script must consult separately.
        store.write([_bar(TEST_CA.id, TSX_SESSION, _close_time(TEST_CA.id, TSX_SESSION))],
                    _close_time(TEST_CA.id, TSX_SESSION))
    return path


def _rows(path: Path) -> set[tuple]:
    with BarStore(path) as store:
        return set(store._connection.execute(
            "SELECT instrument_id, session_date, knowledge_time, close FROM bars"
        ).fetchall())


def test_it_reports_without_deleting_by_default(store_path, capsys) -> None:
    """The default must be inert. A destructive tool whose no-argument form destroys is one keystroke
    from an accident, and this one cannot be undone by superseding."""
    before = _rows(store_path)

    assert tool.main(["--data", str(store_path.parent)]) == 0

    assert _rows(store_path) == before, "the report-only run changed the store"
    assert "report only" in capsys.readouterr().out


def test_apply_removes_the_unclosed_bar(store_path) -> None:
    before = _rows(store_path)

    assert tool.main(["--data", str(store_path.parent), "--apply"]) == 0

    removed = before - _rows(store_path)
    assert len(removed) == 1
    (instrument, session_date, _, close) = next(iter(removed))
    assert (instrument, session_date, close) == (TEST_US.id, NYSE_SESSION, Decimal("95.70"))


def test_the_settled_version_of_the_same_bar_survives(store_path) -> None:
    """The bad row and the good row share an instrument AND a session date. A predicate written on
    either alone would take both, and the store would lose the session entirely."""
    tool.main(["--data", str(store_path.parent), "--apply"])

    survivors = _rows(store_path)
    same_session = [r for r in survivors if r[0] == TEST_US.id and r[1] == NYSE_SESSION]
    assert len(same_session) == 1
    assert same_session[0][3] == Decimal("100.00"), "the post-close bar is the one that survived"


def test_an_earlier_session_caught_by_the_same_fetch_survives(store_path) -> None:
    """The real case this protects: the 13:25 fetch on 2026-08-03 also wrote ~350 bars per session
    for 07-27 through 07-31. Those sessions HAD closed, so those bars are correct. A predicate keyed
    on `knowledge_time` alone - "delete everything that fetch wrote" - would have taken 1,765 good
    bars with the 296 bad ones."""
    tool.main(["--data", str(store_path.parent), "--apply"])

    survivors = _rows(store_path)
    assert any(r[0] == TEST_US.id and r[1] == date(2026, 1, 14) for r in survivors)


def test_a_second_exchange_is_judged_on_its_own_calendar(store_path) -> None:
    tool.main(["--data", str(store_path.parent), "--apply"])
    assert any(r[0] == TEST_CA.id for r in _rows(store_path))


def test_running_it_twice_removes_nothing_the_second_time(store_path) -> None:
    """Idempotent, so a repeat run after an interruption cannot cascade."""
    tool.main(["--data", str(store_path.parent), "--apply"])
    after_first = _rows(store_path)

    assert tool.main(["--data", str(store_path.parent), "--apply"]) == 0
    assert _rows(store_path) == after_first


def test_it_backs_the_store_up_before_deleting(store_path) -> None:
    tool.main(["--data", str(store_path.parent), "--apply"])
    backups = list(store_path.parent.glob("*.backup-before-unclosed-delete"))
    assert len(backups) == 1
    assert _rows(backups[0]) > _rows(store_path), "the backup holds the row that was removed"


def test_a_clean_store_is_left_alone(tmp_path) -> None:
    """The positive control for the whole file. Without it every test above would pass against a
    script that deletes on some other rule entirely, or on none."""
    path = tmp_path / "bars.duckdb"
    with BarStore(path) as store:
        after = _close_time(TEST_US.id, NYSE_SESSION)
        store.write([_bar(TEST_US.id, NYSE_SESSION, after)], after)
    before = _rows(path)

    assert tool.main(["--data", str(tmp_path), "--apply"]) == 0

    assert _rows(path) == before
    assert not list(tmp_path.glob("*.backup-before-unclosed-delete")), "nothing to back up"


def test_a_bar_on_a_day_the_calendar_does_not_know_is_never_touched() -> None:
    """`unclosed_rows` must not delete on ignorance. A holiday, a bad date or an unknown venue is
    `unavailable`, and treating that as `bad` is the error `AGENTS.md` §12 calls the most damaging
    one this product can make."""
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "bars.duckdb"
        holiday = date(2026, 1, 1)
        assert cal.session(Exchange.NYSE, holiday) is None
        with BarStore(path) as store:
            noon = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
            _write_bypassing_the_guard(store, _bar(TEST_US.id, holiday, noon), noon)
        before = _rows(path)

        assert tool.main(["--data", scratch, "--apply"]) == 0
        assert _rows(path) == before
