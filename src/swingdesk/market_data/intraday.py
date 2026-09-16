"""Intraday resolutions above a minute, rolled up from the minutes that are stored. `DR-045`.

**One stored intraday resolution, and the rest derived from it.** `contracts.market.Interval` says
each resolution is fetched independently and never derived from another, and that rule was written
for Yahoo: its hourly history reaches 730 days and its 30-minute history 60, so a 30-minute series
derived from hourly bars would have had a different past than the one the vendor serves. Alpaca's
minutes have no such ceiling - the free tier's SIP feed serves them from 2016 - so a three-minute
bar built from three stored minutes has exactly the history the minutes do, from one source, with
one adjustment and one knowledge time. `DR-045` §3 records the change, and why it leaves the rule
standing for the daily path.

**A rolled-up bar is not a fetched bar, and this never pretends otherwise.** It returns bars built
here, from minutes read as-of, so a study replays identically; nothing is written back to a store
under a resolution nobody fetched.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from swingdesk.market_data.minutes import Minute

#: The resolutions this rolls up to, in minutes. `1` is absent deliberately: a one-minute bar is
#: what is stored, and asking this module for one would be asking it to copy.
SUPPORTED = (3, 5, 15, 30, 60)


class NotDivisible(ValueError):
    """The minutes do not fill the window the caller asked for.

    Raised rather than rounded. A 60-minute roll-up of a half day would otherwise end with a bar
    covering a different span than every other bar in the same series - a bar whose high and low
    mean something else - and a study would never see that it had happened.
    """


@dataclass(frozen=True, slots=True)
class Bar:
    """One rolled-up intraday bar: when it starts, its four prices, and the minutes it holds.

    `minutes` is carried rather than assumed. A bar built from fewer minutes than its span is a
    fact about the session - a halt, a half day, a thin name - and a study that wants to exclude
    those has to be able to see them.
    """

    at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    minutes: int


def roll_up(
    minutes: Sequence[Minute], span: int, *, allow_partial: bool = False,
    anchor: datetime | None = None,
) -> tuple[Bar, ...]:
    """Group `minutes` into bars of `span` minutes each, in time order.

    **Bucketed by the clock, not by position in the list.** A session with a missing minute - a
    halt, or a thin name that printed nothing - must not shift every later bar by one: the bucket a
    minute belongs to comes from its own timestamp, measured from `anchor`.

    **Pass `anchor`, and pass regular-hours minutes.** `MinuteStore` holds the whole UTC day,
    pre-market included, so measuring from the first minute present would start a 30-minute series
    at 04:03 rather than at the open, and every bar would straddle the boundaries a trader reads.
    `anchor` is the instant the buckets are measured from - the session's open for a regular-hours
    series - and minutes before it are refused rather than bucketed backwards. Without it the first
    minute present is used, which is right only for minutes already cut to the session.

    `allow_partial` admits a final bucket the session ended inside, which a half day produces and a
    halt can too. It defaults to False so a caller gets the refusal rather than a short bar it did
    not ask about.
    """
    if span not in SUPPORTED:
        raise NotDivisible(
            f"{span} is not one of {SUPPORTED}. A window this cannot build is one a study must not "
            f"silently receive"
        )
    if not minutes:
        return ()

    ordered = sorted(minutes, key=lambda minute: minute.at)
    start = ordered[0].at if anchor is None else anchor
    if ordered[0].at < start:
        raise NotDivisible(
            f"a minute at {ordered[0].at:%H:%M} is earlier than the anchor {start:%H:%M}. Cut the "
            f"session to its hours first; a bucket counted backwards from the open is not a bar"
        )
    buckets: dict[int, list[Minute]] = {}
    for minute in ordered:
        index = int((minute.at - start).total_seconds() // 60) // span
        buckets.setdefault(index, []).append(minute)

    built: list[Bar] = []
    for index in sorted(buckets):
        group = buckets[index]
        if len(group) < span and not allow_partial:
            raise NotDivisible(
                f"the bar starting {start + timedelta(minutes=index * span):%H:%M} holds "
                f"{len(group)} of {span} minutes. A short bar's high and low cover a different span "
                f"than its neighbours'; pass allow_partial to accept it deliberately"
            )
        built.append(Bar(
            at=start + timedelta(minutes=index * span),
            open=group[0].open,
            high=max(minute.high for minute in group),
            low=min(minute.low for minute in group),
            close=group[-1].close,
            minutes=len(group),
        ))
    return tuple(built)
