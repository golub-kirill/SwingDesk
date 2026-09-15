"""Which leg a session reached first, read from its one-minute bars. `DR-042` §9, owner ruling 2026-09-14.

**Why now, in the owner's words:** it can matter to a future study, and nobody can prove the
daily-bar assumption is right. `DR-042` §4c had already measured the stop-first convention wrong on
56% of the bars it touches. This makes a backtest READ the answer wherever the session's minutes are
stored, and keep the convention only where they cannot say.

**Four rules, each a place the answer could quietly go wrong:**

* **Regular hours only.** The bar being resolved is the regular session's daily bar, and a stop
  resting at the venue triggers only in regular hours - a pre-market print beyond the session's
  range belongs to neither. The window is the session's own open and close from the exchange
  calendar (`reference_data.calendar`), so an early close ends it where it ended the day. Measured
  2026-09-14: the whole-day window the probe used decided 7 of 132 bars on a print outside it.
* **The minutes must BE the bar.** Their high and low must reproduce the daily bar's, or they are
  a different series: measured 2026-09-14, 4 of 132 were not - two where the vendors adjusted the
  history by different factors (x1.30, x1.33) and two daily lows no consolidated minute contains.
  All four read `target`, all four wrongly or unknowably. They are `MISMATCH` now.
* **Time order, never storage order.** Minutes are sorted by their start before they are walked.
* **Say what cannot be said.** One minute that reached both legs is the same ambiguity one level
  down (`WITHIN_A_MINUTE`); a session never fetched or served empty is `UNAVAILABLE`. These, and a
  mismatch, leave the stop-first convention in place, and every answer is counted by the caller.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from swingdesk.contracts.reference import ExchangeSession
from swingdesk.contracts.trade import ExitReason
from swingdesk.market_data.minutes import Minute, MinuteStore
from swingdesk.reference_data import calendar as cal
from swingdesk.trade_management.exits import ExitDecision


class Touch(StrEnum):
    STOP = "stop"
    TARGET = "target"
    WITHIN_A_MINUTE = "within_a_minute"
    NEITHER = "neither"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"


class DailyRange(Protocol):
    """What the tie-break needs of the bar it resolves. `contracts.market.Bar` is one."""

    @property
    def session_date(self) -> date: ...

    @property
    def high(self) -> Decimal: ...

    @property
    def low(self) -> Decimal: ...


#: What the engine asks: instrument, the bar, its stop and target -> which one printed first.
TieBreak = Callable[[str, DailyRange, Decimal, Decimal], Touch]

#: How far the regular-hours minutes' high and low may sit from the daily bar's and still be that
#: bar. Measured 2026-09-14 on PR-016's 132 ambiguous bars (`docs/decisions/measurements/
#: first-touch-2026-09-14.json`): the 128 that agree are all within 0.035% - two tapes differing by
#: a print at the extremes - and the four that do not are 7.5%, 25%, 30% and 33% out. Half a percent
#: sits more than ten times from each.
RANGE_TOLERANCE = Decimal("0.005")


def regular_hours(minutes: Sequence[Minute], session: ExchangeSession) -> list[Minute]:
    """The minutes that START inside the session: at or after its open, before its close."""
    return [minute for minute in minutes if session.open_time <= minute.at < session.close_time]


def reproduces(minutes: Sequence[Minute], bar: DailyRange) -> bool:
    """Whether the minutes' high and low are the bar's, to `RANGE_TOLERANCE`. None never is."""
    if not minutes:
        return False
    high = max(minute.high for minute in minutes)
    low = min(minute.low for minute in minutes)
    return (abs(high / bar.high - 1) <= RANGE_TOLERANCE
            and abs(low / bar.low - 1) <= RANGE_TOLERANCE)


def first_touch(minutes: Sequence[Minute], stop: Decimal, target: Decimal) -> Touch:
    """Walk the minutes in time order and name the leg reached first."""
    for minute in sorted(minutes, key=lambda m: m.at):
        hit_stop, hit_target = minute.low <= stop, minute.high >= target
        if hit_stop and hit_target:
            return Touch.WITHIN_A_MINUTE
        if hit_stop:
            return Touch.STOP
        if hit_target:
            return Touch.TARGET
    return Touch.NEITHER


def session_for(instrument_id: str, on: date) -> ExchangeSession | None:
    """The session the instrument's exchange held on `on`, or None if it was shut."""
    return cal.session(cal.exchange_for(instrument_id), on)


class MinuteTieBreak:
    """The tie-break a study hands the engine: the stored minutes, as they were known at `as_of`.

    `as_of` is the MINUTES' knowledge instant and is the study's to declare, next to the one its
    bars are read at - minutes are fetched after the fact, for the few sessions that need them.
    """

    def __init__(self, store: MinuteStore, as_of: datetime,
                 sessions: Callable[[str, date], ExchangeSession | None] = session_for) -> None:
        self._store = store
        self._as_of = as_of
        self._sessions = sessions

    def __call__(self, instrument_id: str, bar: DailyRange, stop: Decimal,
                 target: Decimal) -> Touch:
        minutes = self._store.session(instrument_id, bar.session_date, self._as_of)
        session = self._sessions(instrument_id, bar.session_date)
        regular = regular_hours(minutes, session) if minutes and session is not None else []
        if not regular:
            return Touch.UNAVAILABLE
        if not reproduces(regular, bar):
            return Touch.MISMATCH
        return first_touch(regular, stop, target)


def break_tie(decision: ExitDecision, tie_break: TieBreak | None, instrument_id: str,
              bar: DailyRange, stop: Decimal, target: Decimal | None,
              counts: Counter[str]) -> ExitDecision:
    """An ambiguous exit resolved by the session's minutes where they can say, unchanged otherwise.

    Only the TARGET is resolved. When the profit leg is a partial rather than a target the position
    is not closed by it, and what the stop does after a partial in the same session is a second
    unknown this does not pretend to answer - so that case keeps the convention and is not counted.
    The decision stays flagged `ambiguous` either way: the count is the size of the question, and
    `counts` says how each one was answered.
    """
    if not decision.ambiguous or tie_break is None or target is None:
        return decision
    touch = tie_break(instrument_id, bar, stop, target)
    counts[touch.value] += 1
    if touch is Touch.TARGET:
        return ExitDecision(True, target, ExitReason.TARGET, ambiguous=True)
    return decision
