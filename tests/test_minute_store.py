"""`MinuteStore`: volume and the vendor's VWAP, stored when served and never invented.

A store written before the two columns existed must open, keep its minutes, and read them back
with `None` - a zero would be a volume nobody measured.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb

from swingdesk.market_data.minutes import Minute, MinuteStore

SESSION = date(2026, 9, 15)
OPENED = datetime(2026, 9, 15, 13, 30, tzinfo=UTC)
KNOWN = datetime(2026, 9, 16, 1, 0, tzinfo=UTC)


def _minute(i: int, volume: int | None = None, vwap: str | None = None) -> Minute:
    price = Decimal("100") + i
    return Minute(at=OPENED + timedelta(minutes=i), open=price, high=price, low=price, close=price,
                  volume=volume, vwap=None if vwap is None else Decimal(vwap))


def _point_read(store: MinuteStore, instrument_id: str, session_date, knowledge_time):
    """What `session()` returned before 2026-09-26, run directly: the reference the window must equal."""
    fetched = store._connection.execute(
        "SELECT count(*) FROM minute_fetches "
        "WHERE instrument_id = ? AND session_date = ? AND knowledge_time <= ?",
        [instrument_id, session_date, knowledge_time]).fetchone()
    if fetched is None or fetched[0] == 0:
        return None
    rows = store._connection.execute(
        """
        SELECT minute, open, high, low, close, volume, vwap FROM minute_bars
        WHERE instrument_id = ? AND session_date = ? AND knowledge_time <= ?
        QUALIFY ROW_NUMBER() OVER (PARTITION BY minute ORDER BY knowledge_time DESC) = 1
        ORDER BY minute
        """,
        [instrument_id, session_date, knowledge_time]).fetchall()
    return tuple(Minute(at=r[0], open=r[1], high=r[2], low=r[3], close=r[4],
                        volume=None if r[5] is None else int(r[5]), vwap=r[6]) for r in rows)


def _history(tmp_path: Path) -> tuple[MinuteStore, list, list]:
    """Two instruments over sixty weekdays, with the cases a window could get wrong.

    Most sessions fetched once; every fourth REVISED later with changed prices and an added minute;
    every seventh fetched and EMPTY; every ninth never fetched. The second instrument shares the dates
    and prices differently, so a window keyed on the wrong instrument would be visible.
    """
    first_known = datetime(2026, 1, 1, tzinfo=UTC)
    revised = datetime(2026, 6, 1, tzinfo=UTC)
    store = MinuteStore(tmp_path / "m.duckdb")
    days, day = [], date(2026, 1, 5)
    while len(days) < 60:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    for symbol, offset in (("TEST.1", 0), ("TEST.2", 500)):
        for n, session in enumerate(days):
            if n % 9 == 8:
                continue                                            # never fetched: None
            opened = datetime(session.year, session.month, session.day, 14, 30, tzinfo=UTC)

            def bar(i: int, bump: int = 0, _o=opened, _off=offset, _n=n) -> Minute:
                price = Decimal(100 + _off + _n + i + bump)
                return Minute(at=_o + timedelta(minutes=i), open=price, high=price, low=price,
                              close=price, volume=1000 + i, vwap=None)

            served = [] if n % 7 == 6 else [bar(i) for i in range(3)]   # empty: ()
            store.write(symbol, session, served, first_known, "alpaca:sip:split")
            if n % 4 == 3 and served:
                store.write(symbol, session, [bar(0, 50), bar(3, 50)], revised, "alpaca:sip:split")
    instants = [datetime(2025, 12, 1, tzinfo=UTC), datetime(2026, 3, 1, tzinfo=UTC),
                datetime(2026, 9, 1, tzinfo=UTC)]
    return store, days, instants


def test_a_scan_reads_exactly_what_point_reads_read(tmp_path: Path) -> None:
    """Every date, every instant, both instruments - ascending, which is what the runners do.

    Until 2026-09-26 `session()` ran two queries per call; it now reads a window ahead when it is
    scanned. The window partitions by `(session_date, minute)`, the set the point query filtered to
    before ranking versions, and this is the check that the two are the same set.
    """
    store, days, instants = _history(tmp_path)
    with store:
        for knowledge_time in instants:
            for symbol in ("TEST.1", "TEST.2"):
                for session in days:
                    assert store.session(symbol, session, knowledge_time) == \
                        _point_read(store, symbol, session, knowledge_time), (symbol, session)


def test_any_order_of_access_reads_the_same(tmp_path: Path) -> None:
    """Descending, shuffled and interleaved access must agree too - a window must never leak."""
    import random

    store, days, instants = _history(tmp_path)
    requests = [(s, d, k) for k in instants for s in ("TEST.1", "TEST.2") for d in days]
    orders = {
        "descending": list(reversed(requests)),
        "shuffled": random.Random(20260926).sample(requests, len(requests)),
        # Session-major, fund-minor: both instruments on one date before the next date. The first
        # version of this order alternated DATES of one instrument, and a mutant ignoring which
        # instrument a window holds survived it.
        "by session then fund": [(s, d, k) for k in instants for d in days
                                 for s in ("TEST.1", "TEST.2")],
    }
    with store:
        for name, order in orders.items():
            for symbol, session, knowledge_time in order:
                assert store.session(symbol, session, knowledge_time) == \
                    _point_read(store, symbol, session, knowledge_time), (name, symbol, session)


def test_a_scan_asks_the_database_a_handful_of_times_not_twice_a_session(tmp_path: Path) -> None:
    """The point of the change, pinned: 60 sessions scanned in order is a few windows, not 120 queries."""
    store, days, instants = _history(tmp_path)

    class Counting:
        def __init__(self, inner):
            self.inner, self.calls = inner, 0

        def execute(self, *args, **kwargs):
            self.calls += 1
            return self.inner.execute(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.inner, name)

    with store:
        counting = Counting(store._connection)
        store._connection = counting
        for session in days:
            store.session("TEST.1", session, instants[-1])
        store._connection = counting.inner
    assert counting.calls <= 8, f"{counting.calls} queries for {len(days)} sessions"


def test_a_write_is_seen_by_the_next_read(tmp_path: Path) -> None:
    """A window read ahead must not outlive a write that changes what it holds.

    The read after the write asks at the SAME instant the window was read at, and the write is known
    before that instant. The first version of this test read at a later instant, so the window no
    longer matched and was re-read for that reason - and a mutant that never invalidated survived.
    """
    far = datetime(2027, 1, 1, tzinfo=UTC)
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "alpaca:sip:split")
        store.write("SPY", SESSION + timedelta(days=1), [_minute(1)], KNOWN, "alpaca:sip:split")
        store.session("SPY", SESSION, far)
        store.session("SPY", SESSION + timedelta(days=1), far)     # a scan: the window is warm
        store.write("SPY", SESSION + timedelta(days=1), [_minute(1, 9999)],
                    KNOWN + timedelta(hours=1), "alpaca:sip:split")
        assert store.session("SPY", SESSION + timedelta(days=1), far)[0].volume == 9999


def test_a_second_price_basis_is_refused(tmp_path: Path) -> None:
    """Two adjustments in one instrument's minutes make an overnight ratio cross a split wrong.

    `minute_fetches` has recorded the basis since it was written and NOTHING read it: `minute_bars`
    carries none, `session()` never joined to the fetch table, and `write()` took any source. A
    `--adjustment raw` probe into a `split` store left a series whose sessions sit on two price
    scales, silently, on exactly the sessions a split makes interesting. `PR-025` is what an
    unchecked price basis costs - a REJECT that was a unit error.
    """
    import pytest

    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "alpaca:sip:split")
        with pytest.raises(ValueError, match=r"[Tt]wo price bases"):
            store.write("SPY", SESSION + timedelta(days=1), [_minute(1)], KNOWN, "alpaca:sip:raw")


def test_the_same_basis_from_another_feed_is_allowed(tmp_path: Path) -> None:
    """A feed difference is a data-quality question, not two price scales.

    `alpaca:iex:split` and `alpaca:sip:split` are the same numbers from different tapes. Refusing
    that would be guarding the wrong field, and a guard that fires on the wrong thing gets removed.
    """
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "alpaca:sip:split")
        store.write("SPY", SESSION + timedelta(days=1), [_minute(1)], KNOWN, "alpaca:iex:split")
        assert store.sources("SPY", KNOWN) == ("alpaca:iex:split", "alpaca:sip:split")


def test_a_source_that_claims_no_basis_is_not_accused(tmp_path: Path) -> None:
    """A store written before the convention carries `old`, and re-sourcing it is legitimate.

    The first cut refused any source that differed at all and broke the migration test. Accusing on
    a shape the check cannot read is the mistake it exists to prevent.
    """
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "old")
        store.write("SPY", SESSION + timedelta(days=1), [_minute(1)], KNOWN, "new")
        assert store.sources("SPY", KNOWN) == ("new", "old")


def test_another_instrument_is_its_own_question(tmp_path: Path) -> None:
    """One store may hold two instruments on two bases; a RATIO is only ever within one."""
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "alpaca:sip:split")
        store.write("QQQ", SESSION, [_minute(1)], KNOWN, "alpaca:sip:raw")
        assert store.sources("SPY", KNOWN) == ("alpaca:sip:split",)
        assert store.sources("QQQ", KNOWN) == ("alpaca:sip:raw",)


def test_sources_are_read_as_of_a_knowledge_time(tmp_path: Path) -> None:
    """A study asks what it is reading AT its pinned instant, like every other read here."""
    later = KNOWN + timedelta(days=1)
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], later, "alpaca:sip:split")
        assert store.sources("SPY", KNOWN) == ()
        assert store.sources("SPY", later) == ("alpaca:sip:split",)


def test_volume_and_vwap_round_trip(tmp_path: Path) -> None:
    served = [_minute(0, 5000, "100.02"), _minute(1, 7000, "101.01")]
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, served, KNOWN, "test")
        assert store.session("SPY", SESSION, KNOWN) == tuple(served)


def test_a_minute_served_without_volume_reads_back_without_it(tmp_path: Path) -> None:
    with MinuteStore(tmp_path / "m.duckdb") as store:
        store.write("SPY", SESSION, [_minute(0)], KNOWN, "test")
        [got] = store.session("SPY", SESSION, KNOWN)
    assert got.volume is None and got.vwap is None


def test_a_store_written_before_the_columns_opens_and_keeps_its_minutes(tmp_path: Path) -> None:
    """THE MIGRATION. The old four-price table gains two empty columns; nothing is invented."""
    path = tmp_path / "old.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("""
        CREATE TABLE minute_bars (
            instrument_id VARCHAR NOT NULL, session_date DATE NOT NULL,
            minute TIMESTAMPTZ NOT NULL, knowledge_time TIMESTAMPTZ NOT NULL,
            open DECIMAL(18,6) NOT NULL, high DECIMAL(18,6) NOT NULL,
            low DECIMAL(18,6) NOT NULL, close DECIMAL(18,6) NOT NULL,
            PRIMARY KEY (instrument_id, minute, knowledge_time));
        CREATE TABLE minute_fetches (
            instrument_id VARCHAR NOT NULL, session_date DATE NOT NULL,
            knowledge_time TIMESTAMPTZ NOT NULL, source VARCHAR NOT NULL,
            minutes INTEGER NOT NULL, PRIMARY KEY (instrument_id, session_date, knowledge_time));
    """)
    connection.execute("INSERT INTO minute_bars VALUES ('SPY', ?, ?, ?, 100, 101, 99, 100.5)",
                       [SESSION, OPENED, KNOWN])
    connection.execute("INSERT INTO minute_fetches VALUES ('SPY', ?, ?, 'old', 1)", [SESSION, KNOWN])
    connection.close()

    with MinuteStore(path) as store:
        [old] = store.session("SPY", SESSION, KNOWN)
        assert old.close == Decimal("100.5") and old.volume is None and old.vwap is None
        store.write("SPY", date(2026, 9, 16), [_minute(0, 900, "100.4")], KNOWN, "new")
        [new] = store.session("SPY", date(2026, 9, 16), KNOWN)
        assert new.volume == 900 and new.vwap == Decimal("100.4")
