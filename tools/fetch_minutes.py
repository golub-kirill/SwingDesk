"""Fetch the one-minute bars of named sessions into a `MinuteStore`. GET only. `DR-042` §9.

**What it is for.** `validation.backtest.intraday.MinuteTieBreak` answers an ambiguous daily bar from
stored minutes, and a backtest never calls a vendor while it runs. This tool is the one place the
minutes come from: it reads a list of (instrument, session) pairs - by default the 132 ambiguous
bars `run_pr016.py` recorded - and stores each session's minutes with the instant they were learned.

**Two choices made on purpose, each one a way the answer could be wrong without any error:**

* **`adjustment=split`.** The bar store holds Yahoo's daily bars, whose prices are split-adjusted to
  the day they were fetched, and a study's stop and target are computed from those prices. Alpaca's
  default is `raw`; on any session before a later split, raw minutes are in different units from
  the stop they are compared with. `probe_ambiguous_bar.py` used the default - `tools/
  measure_first_touch.py` measures what that changed.
* **The whole UTC day is stored**, pre-market through after-hours. Which part of it a question
  reads is the reader's decision (`intraday.regular_hours`), and it can only be revisited if the
  store did not make it first.

**A failed request is not a fetch.** Nothing is written for it, so the session reads as never
fetched (`None`) and a later run tries again. A session the feed served empty IS written, as a fetch
of zero minutes - that is an answer.

**Two ways to name what to fetch.** A file of (instrument, session) pairs, which is what `DR-042`
needed; or an instrument and a date range, which is what a study of the intraday ladder needs
(`DR-045`). The range comes from the exchange calendar, so a date the exchange was shut is never
requested - a fact no amount of bar data could establish.

    PYTHONPATH=$PWD/src python tools/fetch_minutes.py --store <path>
    PYTHONPATH=$PWD/src python tools/fetch_minutes.py --store <path> --adjustment raw
    PYTHONPATH=$PWD/src python tools/fetch_minutes.py --store <path> --instrument SPY \
        --from 2016-01-04 --to 2026-09-15

Needs `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`; reports UNAVAILABLE and exits 2 without them.
Network tool, never run in CI (`CI_POLICY` §4).
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from swingdesk.market_data.minutes import Minute, MinuteStore
from swingdesk.reference_data import calendar as cal

REPO = Path(__file__).resolve().parents[1]

BARS = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
AMBIGUOUS_BARS = REPO / "docs" / "prereg" / "results" / "PR-016-ambiguous-bars.jsonl"

#: `probe_ambiguous_bar.py` measured on 2026-09-08 that `sip` serves minutes from 2016-01-04 and
#: `iex` serves none of that history.
FEED = "sip"
ADJUSTMENT = "split"

#: One GET: status and decoded body, or status and a short reason. Injected so a test never touches
#: the network.
Getter = Callable[[str], tuple[int, object]]


def get(url: str) -> tuple[int, object]:
    """One GET with the credentials from the environment. A non-200 is returned, never raised."""
    headers = {
        "APCA-API-KEY-ID": os.environ.get("APCA_API_KEY_ID", ""),
        "APCA-API-SECRET-KEY": os.environ.get("APCA_API_SECRET_KEY", ""),
        "User-Agent": "SwingDesk-fetch-minutes/1.0",
    }
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")[:300]
    except Exception as error:  # noqa: BLE001 - the message is the point
        return -1, f"{type(error).__name__}: {error}"


def symbol_for(instrument_id: str) -> str:
    """Alpaca spells a share class with a dot where Yahoo uses a dash: `BRK-B` is `BRK.B`."""
    return instrument_id.replace("-", ".")


def parse(bar: dict[str, Any]) -> Minute:
    """One Alpaca bar. Prices go through `str` so a float's binary tail never becomes a price."""
    return Minute(
        at=datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00")),
        open=Decimal(str(bar["o"])), high=Decimal(str(bar["h"])),
        low=Decimal(str(bar["l"])), close=Decimal(str(bar["c"])),
    )


def fetch(instrument_id: str, session: date, getter: Getter = get, feed: str = FEED,
          adjustment: str = ADJUSTMENT) -> list[Minute] | str:
    """Every minute of the session's UTC day, following `next_page_token`, or why not."""
    minutes: list[Minute] = []
    token: str | None = None
    while True:
        query = {"timeframe": "1Min", "start": f"{session.isoformat()}T00:00:00Z",
                 "end": f"{session.isoformat()}T23:59:59Z", "limit": "10000", "feed": feed,
                 "adjustment": adjustment}
        if token:
            query["page_token"] = token
        url = f"{BARS.format(symbol=symbol_for(instrument_id))}?{urllib.parse.urlencode(query)}"
        status, body = getter(url)
        if status != 200 or not isinstance(body, dict):
            return f"HTTP {status}: {str(body)[:80]}"
        minutes.extend(parse(bar) for bar in body.get("bars") or [])
        token = body.get("next_page_token")
        if not token:
            return minutes


def sessions_from(path: Path) -> list[tuple[str, date]]:
    """The distinct (instrument, session) pairs a JSON-lines file names, in a fixed order."""
    pairs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            pairs.add((row["instrument_id"], date.fromisoformat(row["session_date"])))
    return sorted(pairs)


def range_sessions(instruments: list[str], start: date, end: date) -> list[tuple[str, date]]:
    """Every (instrument, session) pair in `[start, end]`, from each instrument's own calendar.

    **The calendar decides, never the date arithmetic.** A weekend is obvious; a holiday, a
    half day and an exchange that keeps a different one are not, and requesting a session that
    never happened would store an empty fetch as though the market had printed nothing.
    """
    pairs: list[tuple[str, date]] = []
    for instrument in instruments:
        exchange = cal.exchange_for(instrument)
        pairs += [(instrument, session.session_date)
                  for session in cal.sessions(exchange, start, end)]
    return sorted(set(pairs))


def main(argv: list[str] | None = None, getter: Getter = get,
         now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, required=True, help="the minute store to write")
    parser.add_argument("--sessions", type=Path, default=AMBIGUOUS_BARS,
                        help="JSON lines naming instrument_id and session_date")
    parser.add_argument("--instrument", action="append", default=[],
                        help="fetch a DATE RANGE for this instrument instead of --sessions; "
                             "repeatable")
    parser.add_argument("--from", dest="start", type=date.fromisoformat,
                        help="first session of the range, inclusive (with --instrument)")
    parser.add_argument("--to", dest="end", type=date.fromisoformat,
                        help="last session of the range, inclusive (with --instrument)")
    parser.add_argument("--feed", default=FEED)
    parser.add_argument("--adjustment", default=ADJUSTMENT, choices=["raw", "split"])
    parser.add_argument("--refetch", action="store_true",
                        help="fetch sessions the store already holds, as a new version")
    args = parser.parse_args(argv)

    if getter is get and not (os.environ.get("APCA_API_KEY_ID")
                              and os.environ.get("APCA_API_SECRET_KEY")):
        print("fetch minutes: UNAVAILABLE - APCA_API_KEY_ID/SECRET are not in the environment")
        return 2
    if args.instrument:
        if not (args.start and args.end):
            print("fetch minutes: REFUSED - --instrument needs --from and --to")
            return 2
        if args.start > args.end:
            print(f"fetch minutes: REFUSED - --from {args.start} is after --to {args.end}")
            return 2
        pairs = range_sessions(args.instrument, args.start, args.end)
    elif not args.sessions.exists():
        print(f"fetch minutes: UNAVAILABLE - {args.sessions} does not exist")
        return 2
    else:
        pairs = sessions_from(args.sessions)
    source = f"alpaca:{args.feed}:{args.adjustment}"
    fetched = held = empty = 0
    failures: list[str] = []
    with MinuteStore(args.store) as store:
        for instrument_id, session in pairs:
            if not args.refetch and store.session(instrument_id, session, now()) is not None:
                held += 1
                continue
            got = fetch(instrument_id, session, getter, args.feed, args.adjustment)
            if isinstance(got, str):
                failures.append(f"{instrument_id} {session}: {got}")
                continue
            store.write(instrument_id, session, got, now(), source)
            fetched += 1
            empty += not got

    print(f"sessions named {len(pairs)}   source {source}   store {args.store}")
    print(f"  fetched now            {fetched}   (served empty: {empty})")
    print(f"  already held           {held}")
    print(f"  failed, nothing kept   {len(failures)}")
    for failure in failures[:20]:
        print(f"    {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
