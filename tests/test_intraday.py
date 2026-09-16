"""Rolling stored minutes up into the intraday ladder (`DR-045`).

Pure arithmetic over a sequence, so every case here is an exact statement about one session. The
ones that matter are the sessions that are NOT tidy: a halt, a half day, a minute the vendor never
printed. A roll-up that silently reindexes those produces bars whose highs and lows cover spans
nobody chose, and a study cannot tell afterwards that it happened.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from swingdesk.market_data.intraday import SUPPORTED, Bar, NotDivisible, roll_up
from swingdesk.market_data.minutes import Minute

OPEN = datetime(2026, 9, 15, 13, 30, tzinfo=UTC)  # 09:30 New York


def _minute(offset: int, open_: str, high: str, low: str, close: str) -> Minute:
    return Minute(at=OPEN + timedelta(minutes=offset), open=Decimal(open_), high=Decimal(high),
                  low=Decimal(low), close=Decimal(close))


def _session(count: int, first: int = 100) -> list[Minute]:
    """`count` minutes climbing by one a minute, each with a one-point range around its close."""
    return [_minute(i, str(first + i), str(first + i + 1), str(first + i - 1), str(first + i + 1))
            for i in range(count)]


def test_three_minutes_become_one_bar_with_the_session_s_own_prices() -> None:
    [bar] = roll_up(_session(3), 3)

    assert bar.at == OPEN, "the bar is stamped when it STARTS"
    assert bar.open == Decimal(100), "the first minute's open"
    assert bar.close == Decimal(103), "the last minute's close"
    assert bar.high == Decimal(103) and bar.low == Decimal(99), "the extremes of all three"
    assert bar.minutes == 3


def test_the_bars_tile_the_session_in_order() -> None:
    bars = roll_up(_session(30), 3)

    assert len(bars) == 10
    assert [bar.at for bar in bars] == [OPEN + timedelta(minutes=3 * i) for i in range(10)]
    assert all(bar.minutes == 3 for bar in bars)
    assert bars[0].open < bars[-1].close, "and they stay in time order"


@pytest.mark.parametrize("span", SUPPORTED)
def test_every_supported_span_tiles_a_session_that_divides_by_it(span: int) -> None:
    bars = roll_up(_session(span * 4), span)
    assert [bar.minutes for bar in bars] == [span] * 4


def test_a_missing_minute_does_not_shift_every_later_bar() -> None:
    """THE CASE THAT MATTERS. A halted or thin minute must not push its neighbours into other bars.

    Position in the list would do exactly that: with minute 4 absent, minute 5 would become the
    last member of the first bar and the whole session would slide by one. The clock says
    otherwise, so bar two holds two minutes and everything after it stays where it belongs.
    """
    minutes = [m for m in _session(9) if m.at != OPEN + timedelta(minutes=4)]

    bars = roll_up(minutes, 3, allow_partial=True)

    assert [bar.at for bar in bars] == [OPEN, OPEN + timedelta(minutes=3),
                                        OPEN + timedelta(minutes=6)]
    assert [bar.minutes for bar in bars] == [3, 2, 3]
    assert bars[2].open == Decimal(106), "the third bar still opens on minute 6"


def test_a_short_bar_is_refused_unless_it_is_asked_for() -> None:
    """A half day ends inside a bucket. Rounding it away would hide that the last bar of the
    series covers a different span than the rest."""
    with pytest.raises(NotDivisible, match="5 of 60"):
        roll_up(_session(65), 60)

    bars = roll_up(_session(65), 60, allow_partial=True)
    assert [bar.minutes for bar in bars] == [60, 5]


def test_an_unsupported_span_is_refused_rather_than_approximated() -> None:
    with pytest.raises(NotDivisible, match="7 is not one of"):
        roll_up(_session(70), 7)


def test_one_minute_is_not_a_roll_up() -> None:
    """It is what is STORED. Asking for it here would be asking this to copy the store."""
    assert 1 not in SUPPORTED
    with pytest.raises(NotDivisible):
        roll_up(_session(10), 1)


def test_an_empty_session_rolls_up_to_nothing() -> None:
    """`MinuteStore.session` distinguishes never-fetched from fetched-and-empty; a fetched-empty
    session is a fact, and the answer to it is no bars rather than a refusal."""
    assert roll_up([], 30) == ()


def test_minutes_out_of_order_are_read_in_time_order() -> None:
    """The store returns them ordered; a caller that concatenated two reads might not."""
    shuffled = list(reversed(_session(6)))
    assert roll_up(shuffled, 3) == roll_up(_session(6), 3)


def test_a_rolled_up_bar_says_how_many_minutes_it_holds() -> None:
    """So a study can exclude short bars instead of discovering them in its results."""
    bars = roll_up(_session(62), 30, allow_partial=True)
    assert isinstance(bars[0], Bar)
    assert [bar.minutes for bar in bars] == [30, 30, 2]


def test_an_anchor_aligns_the_bars_to_the_open_when_the_first_minute_is_late() -> None:
    """The store holds whole UTC days. A series measured from whatever minute printed first starts
    wherever that minute fell; measured from the open, a late first print lands in its own bucket
    and every bar keeps the boundaries a trader reads."""
    late = [m for m in _session(6) if m.at >= OPEN + timedelta(minutes=1)]

    bars = roll_up(late, 3, anchor=OPEN, allow_partial=True)

    assert [bar.at for bar in bars] == [OPEN, OPEN + timedelta(minutes=3)]
    assert [bar.minutes for bar in bars] == [2, 3]


def test_a_minute_before_the_anchor_is_refused_not_bucketed_backwards() -> None:
    """Pre-market minutes must be cut before rolling up; a negative bucket is not a bar."""
    early = [_minute(-5, "99", "100", "98", "99"), *_session(3)]
    with pytest.raises(NotDivisible, match="earlier than the anchor"):
        roll_up(early, 3, anchor=OPEN)


def test_without_an_anchor_the_first_minute_is_the_origin() -> None:
    """Right only for minutes already cut to the session, which is what the docstring says."""
    late = [m for m in _session(7) if m.at >= OPEN + timedelta(minutes=1)]
    bars = roll_up(late, 3)
    assert bars[0].at == OPEN + timedelta(minutes=1)
