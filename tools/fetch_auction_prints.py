"""Fetch the opening and closing auction prints of named sessions into an `AuctionStore`. GET only.

**What it is for.** `PR-025` prices an entry that joins the opening or the closing auction, which
pays the cross's single price and no quoted spread. The price is read from the SIP trade tape,
where the listing market's cross carries the condition `O` (opening) or `6` (closing) and every
market center stamps its own official open `Q` and close `M`. Every flagged print in the window is
kept; which one is the cross is the study's rule (`run_pr025.cross_price`).

**How far it reads.** From the session's open, or its close - 13:00 on a half day, from the
calendar - pages of 1,000 trades, until the tape has run 60 seconds past the first print carrying
the cross's condition, or five minutes have passed. A cross is usually in the first second; a NYSE
opening delayed for news can be minutes late, and a first flagged print from another venue can come
before the listing market's own - the minute after it is what lets the larger print arrive.

**A failed request is not a fetch.** A failure writes nothing, so the window reads as never fetched
and a later run tries again; a window whose tape flagged nothing IS written, as a fetch of no prints.

    PYTHONPATH=$PWD/src python tools/fetch_auction_prints.py --store <path> --sessions <jsonl>

Needs `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`; reports UNAVAILABLE and exits 2 without them.
Network tool, never run in CI (`CI_POLICY` §4). Paced like `fetch_entry_quotes.py`.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.parse
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_entry_quotes import (
    BACKOFF_SECONDS,
    PACE_SECONDS,
    RETRIES,
    Sessions,
    sessions_from,
)
from fetch_minutes import Getter, get, symbol_for
from swingdesk.market_data.auctions import CLOSING, FLAGS, OPENING, SIDES, AuctionStore, Print
from swingdesk.reference_data import calendar as cal

TRADES = "https://data.alpaca.markets/v2/stocks/{symbol}/trades"
FEED = "sip"
SOURCE = f"alpaca:{FEED}:trades"

#: The condition the listing market's cross carries, per side.
CROSS = {OPENING: "O", CLOSING: "6"}

PAGE = 1000
WINDOW = timedelta(minutes=5)
PAST_THE_CROSS = timedelta(seconds=60)


def instant_for(instrument_id: str, session_date: date, side: str,
                sessions: Sessions = cal.session) -> datetime | None:
    """The UTC instant the auction window starts: the session's open or close. `None` when shut."""
    if side not in SIDES:
        raise ValueError(f"{side!r} is not one of {SIDES}")
    session = sessions(cal.exchange_for(instrument_id), session_date)
    if session is None:
        return None
    return (session.open_time if side == OPENING else session.close_time).astimezone(UTC)


def parse(row: dict[str, Any]) -> Print | None:
    """One trade, kept only when it carries a flag this store records."""
    conditions = tuple(str(c) for c in row.get("c") or [])
    if not FLAGS.intersection(conditions):
        return None
    try:
        return Print(at=datetime.fromisoformat(str(row["t"]).replace("Z", "+00:00")),
                     price=Decimal(str(row["p"])), size=int(row.get("s", 0)),
                     exchange=str(row.get("x", "")), conditions=conditions)
    except (KeyError, ValueError, InvalidOperation):
        return None


def _page(instrument_id: str, start: datetime, end: datetime, token: str | None,
          getter: Getter) -> tuple[list[dict[str, Any]], str | None] | str:
    query = {"start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": str(PAGE), "feed": FEED}
    if token:
        query["page_token"] = token
    url = f"{TRADES.format(symbol=symbol_for(instrument_id))}?{urllib.parse.urlencode(query)}"
    status, body = getter(url)
    if status != 200 or not isinstance(body, dict):
        return f"HTTP {status}: {str(body)[:80]}"
    rows = [row for row in body.get("trades") or [] if isinstance(row, dict)]
    return rows, body.get("next_page_token")


def fetch(instrument_id: str, at: datetime, side: str, getter: Getter,
          pause: Callable[[float], None]) -> tuple[list[Print], int] | str:
    """Every flagged print from `at` until the tape is a minute past the first cross, or why not."""
    end = at + WINDOW
    prints: list[Print] = []
    scanned = 0
    token: str | None = None
    first_cross: datetime | None = None
    while True:
        got: tuple[list[dict[str, Any]], str | None] | str = "never attempted"
        for attempt in range(RETRIES):
            got = _page(instrument_id, at, end, token, getter)
            pause(PACE_SECONDS)
            if not (isinstance(got, str) and got.startswith("HTTP 429")):
                break
            pause(BACKOFF_SECONDS * (attempt + 1))
        if isinstance(got, str):
            return got
        rows, token = got
        scanned += len(rows)
        for row in rows:
            flagged = parse(row)
            if flagged is None:
                continue
            prints.append(flagged)
            if first_cross is None and CROSS[side] in flagged.conditions:
                first_cross = flagged.at
        last = rows[-1].get("t") if rows else None
        reached = (datetime.fromisoformat(str(last).replace("Z", "+00:00")) if last else None)
        if not token:
            return prints, scanned
        if first_cross is not None and reached is not None and reached - first_cross >= PAST_THE_CROSS:
            return prints, scanned


def main(argv: Sequence[str] | None = None, getter: Getter = get,
         now: Callable[[], datetime] = lambda: datetime.now(UTC),
         pause: Callable[[float], None] = time.sleep,
         sessions: Sessions = cal.session) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, required=True, help="the auction store to write")
    parser.add_argument("--sessions", type=Path, required=True,
                        help="JSON lines naming instrument_id and session_date")
    parser.add_argument("--side", action="append", choices=SIDES, default=[],
                        help="fetch only this auction; repeatable. Default: both")
    parser.add_argument("--refetch", action="store_true",
                        help="fetch windows the store already holds, as a new version")
    args = parser.parse_args(argv)

    if getter is get and not (os.environ.get("APCA_API_KEY_ID")
                              and os.environ.get("APCA_API_SECRET_KEY")):
        print("fetch auction prints: UNAVAILABLE - APCA_API_KEY_ID/SECRET are not in the environment")
        return 2
    if not args.sessions.exists():
        print(f"fetch auction prints: UNAVAILABLE - {args.sessions} does not exist")
        return 2

    sides = tuple(args.side) or SIDES
    pairs = sessions_from(args.sessions)
    fetched = held = empty = 0
    failures: list[str] = []
    with AuctionStore(args.store) as store:
        for instrument_id, session_date in pairs:
            for side in sides:
                if not args.refetch and store.fetched(instrument_id, session_date, side, now()):
                    held += 1
                    continue
                at = instant_for(instrument_id, session_date, side, sessions)
                if at is None:
                    failures.append(f"{instrument_id} {session_date} {side}: not a session")
                    continue
                got = fetch(instrument_id, at, side, getter, pause)
                if isinstance(got, str):
                    failures.append(f"{instrument_id} {session_date} {side}: {got}")
                    continue
                prints, scanned = got
                store.write(instrument_id, session_date, side, at, prints, scanned, now(), SOURCE)
                fetched += 1
                empty += not any(CROSS[side] in p.conditions for p in prints)

    print(f"sessions named {len(pairs)}   auctions {', '.join(sides)}   store {args.store}")
    print(f"  windows fetched now    {fetched}   (no cross flagged: {empty})")
    print(f"  already held           {held}")
    print(f"  failed, nothing kept   {len(failures)}")
    for failure in failures[:20]:
        print(f"    {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
