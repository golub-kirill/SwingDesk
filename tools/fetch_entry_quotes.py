"""Fetch quoted bid/ask windows at named moments of named sessions into a `QuoteStore`. GET only.

**What it is for.** `PR-024` charges every entry the spread its own name was quoted at, at the moment
it was entered, where `DR-040` §9 charged every entry the median spread of a whole universe. That
needs the quotes of the names the card actually buys, kept so the run can be replayed: this is the
one place they come from.

**Three moments, resolved from the exchange calendar, never from wall-clock arithmetic:**

* `open` - five seconds after the session opens, `DR-040`'s own convention for *the next
  session's open*;
* `eleven` - 11:00 exchange time;
* `close` - five minutes before the session closes, which is 15:55 on a full day and 12:55 on a
  half day. A fixed 15:55 would ask a half day for quotes three hours after it ended.

**A failed request is not a fetch.** `measure_quoted_spread.fetch_quotes` returns the same empty list
for a request that failed and a window the vendor served empty; a store fed from it could not tell a
gap from a quiet tape. Here a failure writes nothing, so the window reads as never fetched and a
later run tries again, while a served-empty window IS written, as a fetch of zero quotes.

**Quotes are stored as served.** A crossed, locked or one-sided quote is a real state of the tape;
which ones a spread may be computed from is the study's rule (`run_pr024.half_spread_bps`), and it
can only be revisited if the store did not decide it first.

    PYTHONPATH=$PWD/src python tools/fetch_entry_quotes.py --store <path> --sessions <jsonl>

Needs `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`; reports UNAVAILABLE and exits 2 without them.
Network tool, never run in CI (`CI_POLICY` §4). Paced at 0.32 s a request - the free tier documents
200 a minute - and a 429 is retried with a growing pause before it counts as a failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# A TOOL MUST IMPORT THE CHECKOUT IT LIVES IN. `swingdesk` is installed editable and the .pth
# carries the MAIN checkout's `src` as an absolute path, so without this line a tool run from a
# git worktree measures another tree's code. Found 2026-09-21, by the same defect in the suite.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_minutes import Getter, get, symbol_for
from swingdesk.contracts.reference import ExchangeSession
from swingdesk.market_data.quotes import CLOSE, ELEVEN, MOMENTS, OPEN, Quote, QuoteStore
from swingdesk.reference_data import calendar as cal

QUOTES = "https://data.alpaca.markets/v2/stocks/{symbol}/quotes"
FEED = "sip"
SOURCE = f"alpaca:{FEED}"

#: How many quotes a window holds. `DR-040` read 25 and took their median; the same count keeps the
#: two measurements comparable, and the request count - not the response size - is the binding cost.
QUOTES_PER_WINDOW = 25

#: The free tier documents 200 requests a minute. Sleeping between calls is cheaper than discovering
#: the limit, and `measure_quoted_spread.py` measured this pacing as sufficient.
PACE_SECONDS = 0.32

#: Attempts on a 429 before the window counts as failed, and the base of the growing pause.
RETRIES = 4
BACKOFF_SECONDS = 2.0

OPEN_OFFSET = timedelta(seconds=5)
CLOSE_OFFSET = timedelta(minutes=5)

Sessions = Callable[[Any, date], ExchangeSession | None]


def instant_for(instrument_id: str, session_date: date, moment: str,
                sessions: Sessions = cal.session) -> datetime | None:
    """The UTC instant a moment of the session falls on, or `None` when the exchange was shut."""
    session = sessions(cal.exchange_for(instrument_id), session_date)
    if session is None:
        return None
    if moment == OPEN:
        local = session.open_time + OPEN_OFFSET
    elif moment == ELEVEN:
        local = session.open_time.replace(hour=11, minute=0, second=0, microsecond=0)
    elif moment == CLOSE:
        local = session.close_time - CLOSE_OFFSET
    else:
        raise ValueError(f"{moment!r} is not one of {MOMENTS}")
    return local.astimezone(UTC)


def parse(row: dict[str, Any]) -> Quote | None:
    """One Alpaca quote, prices through `str`. `None` for a row with no usable timestamp or price."""
    try:
        return Quote(
            at=datetime.fromisoformat(str(row["t"]).replace("Z", "+00:00")),
            bid=Decimal(str(row.get("bp", 0))),
            ask=Decimal(str(row.get("ap", 0))),
        )
    except (KeyError, ValueError, InvalidOperation):
        return None


def fetch(instrument_id: str, at: datetime, getter: Getter = get,
          limit: int = QUOTES_PER_WINDOW, feed: str = FEED) -> list[Quote] | str:
    """The first `limit` quotes at or after `at`, or why not. One request, no paging."""
    query = {"start": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": str(limit), "feed": feed}
    url = f"{QUOTES.format(symbol=symbol_for(instrument_id))}?{urllib.parse.urlencode(query)}"
    status, body = getter(url)
    if status != 200 or not isinstance(body, dict):
        return f"HTTP {status}: {str(body)[:80]}"
    parsed = [parse(row) for row in body.get("quotes") or [] if isinstance(row, dict)]
    return [quote for quote in parsed if quote is not None]


def fetch_with_retry(instrument_id: str, at: datetime, getter: Getter,
                     pause: Callable[[float], None]) -> list[Quote] | str:
    """`fetch`, retried on 429 only. Any other refusal is final for this run."""
    got: list[Quote] | str = "never attempted"
    for attempt in range(RETRIES):
        got = fetch(instrument_id, at, getter)
        if not (isinstance(got, str) and got.startswith("HTTP 429")):
            return got
        pause(BACKOFF_SECONDS * (attempt + 1))
    return got


def sessions_from(path: Path) -> list[tuple[str, date]]:
    """The distinct (instrument, session) pairs a JSON-lines file names, in a fixed order."""
    pairs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            pairs.add((row["instrument_id"], date.fromisoformat(row["session_date"])))
    return sorted(pairs)


def main(argv: Sequence[str] | None = None, getter: Getter = get,
         now: Callable[[], datetime] = lambda: datetime.now(UTC),
         pause: Callable[[float], None] = time.sleep,
         sessions: Sessions = cal.session) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, required=True, help="the quote store to write")
    parser.add_argument("--sessions", type=Path, required=True,
                        help="JSON lines naming instrument_id and session_date")
    parser.add_argument("--moment", action="append", choices=MOMENTS, default=[],
                        help="fetch only this moment; repeatable. Default: all three")
    parser.add_argument("--refetch", action="store_true",
                        help="fetch windows the store already holds, as a new version")
    args = parser.parse_args(argv)

    if getter is get and not (os.environ.get("APCA_API_KEY_ID")
                              and os.environ.get("APCA_API_SECRET_KEY")):
        print("fetch quotes: UNAVAILABLE - APCA_API_KEY_ID/SECRET are not in the environment")
        return 2
    if not args.sessions.exists():
        print(f"fetch quotes: UNAVAILABLE - {args.sessions} does not exist")
        return 2

    moments = tuple(args.moment) or MOMENTS
    pairs = sessions_from(args.sessions)
    fetched = held = empty = 0
    failures: list[str] = []
    with QuoteStore(args.store) as store:
        for instrument_id, session_date in pairs:
            for moment in moments:
                if not args.refetch and store.fetched(instrument_id, session_date, moment, now()):
                    held += 1
                    continue
                at = instant_for(instrument_id, session_date, moment, sessions)
                if at is None:
                    failures.append(f"{instrument_id} {session_date} {moment}: not a session")
                    continue
                got = fetch_with_retry(instrument_id, at, getter, pause)
                pause(PACE_SECONDS)
                if isinstance(got, str):
                    failures.append(f"{instrument_id} {session_date} {moment}: {got}")
                    continue
                store.write(instrument_id, session_date, moment, at, got, now(), SOURCE)
                fetched += 1
                empty += not got

    print(f"sessions named {len(pairs)}   moments {', '.join(moments)}   store {args.store}")
    print(f"  windows fetched now    {fetched}   (served empty: {empty})")
    print(f"  already held           {held}")
    print(f"  failed, nothing kept   {len(failures)}")
    for failure in failures[:20]:
        print(f"    {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
