"""Is there a free source for the pre-trade event calendar? Asked of the source, not of our code.

**The claim under test, and it is not the one the code makes.** `TODO.md` §2 carries
*"The `E11` event calendar has no source"*, unverified. `application/checklist.py` says something
narrower and true: *"no event calendar is **wired**"*. Those are different statements, and turning
the second into the first is precisely `AGENTS.md` §15 rule 2 - a claim about what a SOURCE holds
must be tested against the source, never inferred from what our code received. It is also the exact
shape that cost `DR-003` gap 1 its qualifier and `PR-002` half its scope.

**The answer: a source exists, free, with no account and no key.** Nasdaq's own calendar is backed
by a JSON endpoint taking one date per call:

    https://api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD

It serves the FORWARD schedule with a session bucket - before the open, after the close, or not
supplied - which is the field a swing system actually needs, because the question at 18:30 is
whether tonight's position carries an event over the next session. It also serves PAST dates with
the realised figure.

**What it does not settle, stated before anyone over-reads it.**

  * **The schedule AS KNOWN on an earlier date is not recoverable.** Querying an old date returns
    what Nasdaq says about that date TODAY. So a historical study can know an announcement happened
    on a session; it cannot know the date was already published five sessions earlier, or that it
    had been revised. E11 asks the forward question at decision time and is unaffected; a backtest
    of any event rule is not, and this is the same survivorship-shaped bound `probe_canada.py`
    records for TMX.
  * **A row mixes an event-dated fact with a current-state one.** `marketCap` does not vary with the
    announcement date, which this probe demonstrates rather than asserts by comparing the same
    symbol across two dates. Reading it as the capitalisation at announcement would be the
    point-in-time violation `INVARIANTS.md` invariant 6 forbids.
  * **Coverage beyond US venues is measured here, not assumed.** `AGENTS.md` §3 never merges the two
    countries, so a US-only calendar leaves the Canadian half needing its own source. The probe
    reports how much of the calendar is outside `directory.duckdb`, which is the US listing.
  * **It settles the SOURCE and not the RULE.** `screen.earnings_buffer_days` stays `unset` and
    nothing here proposes a value: the course gives one criterion for all twenty catalyst types and
    no lead time at all, so the buffer needs a decision record or a study (`AGENTS.md` §8). What
    this removes is the belief that there is no data to apply one to.

**It is an unofficial endpoint on a consumer site**, like the bar source (`ADR-0001`) and the TMX
directory: undocumented, unversioned, free to change without notice.

**Read-only, writes nothing, and paced.** One request per second, and the directory store is opened
read-only or reported unavailable - never with a traceback (`ADR-0004`).

    python tools/probe_events.py
    python tools/probe_events.py --days 10 --data data
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENDPOINT = "https://api.nasdaq.com/api/calendar/earnings?date={day}"

#: The endpoint refuses a bare urllib request. Both headers are needed, and the lesson is
#: `probe_edgar.py`'s: the SEC blocker was believed to be the HOST for fifteen days when it was a
#: missing `Accept`, so a probe that holds one header constant at a time is the only honest kind.
HEADERS = {
    "User-Agent": "SwingDesk research probe (contact: repository owner)",
    "Accept": "application/json, text/plain, */*",
}

DELAY_SECONDS = 1.0
TIMEOUT_SECONDS = 30


def fetch(day: str) -> dict[str, Any] | None:
    """One calendar day, or None with the reason printed. Never raises."""
    request = urllib.request.Request(ENDPOINT.format(day=day), headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except urllib.error.HTTPError as error:
        print(f"  {day}: HTTP {error.code} - {error.reason}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"  {day}: {type(error).__name__}: {error}")
    return None


def rows_of(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The announcement rows, or an empty list. An empty day is a true answer, not a failure."""
    if not payload:
        return []
    data = payload.get("data") or {}
    rows = data.get("rows")
    return rows if isinstance(rows, list) else []


def weekdays_after(start: dt.date, count: int) -> list[dt.date]:
    """Weekdays only.

    The endpoint has no holiday knowledge and this probe needs none: a holiday returns zero rows,
    which is a true statement about that date rather than a gap to explain.
    """
    days: list[dt.date] = []
    cursor = start
    while len(days) < count:
        cursor += dt.timedelta(days=1)
        if cursor.weekday() < 5:
            days.append(cursor)
    return days


def listed_symbols(data: Path) -> set[str] | None:
    """Every symbol in the US directory, or None when the store cannot be read from here.

    None means UNAVAILABLE and is printed as such. A worktree has no `data/` of its own, and the
    evening run holds the stores while it works - both are the design working (`AGENTS.md` §12).
    """
    store = data / "directory.duckdb"
    if not store.is_file():
        print(f"  coverage: UNAVAILABLE - no directory.duckdb under {data}")
        return None
    try:
        import duckdb
    except ImportError:
        print("  coverage: UNAVAILABLE - duckdb is not importable here")
        return None
    try:
        connection = duckdb.connect(str(store), read_only=True)
    except duckdb.IOException as error:
        print(f"  coverage: UNAVAILABLE - {error}")
        return None
    try:
        # The table is found by its COLUMNS rather than by its name. `directory_pulls` is the audit
        # trail and `directory` holds the symbols; a name-substring match picked the wrong one on
        # the first run, and a probe that reports UNAVAILABLE because it looked in the audit table
        # would be a false impossibility of exactly the kind this file exists to test.
        tables = sorted(str(row[0]) for row in connection.execute("SHOW TABLES").fetchall())
        for table in tables:
            columns = [str(row[0]) for row in connection.execute(f"DESCRIBE {table}").fetchall()]
            column = next((name for name in columns if name.lower() == "symbol"), "")
            if not column:
                continue
            query = f"SELECT DISTINCT {column} FROM {table}"
            return {str(row[0]).upper() for row in connection.execute(query).fetchall() if row[0]}
        print(f"  coverage: UNAVAILABLE - no table with a symbol column among {tables}")
        return None
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe_events", description=__doc__)
    parser.add_argument("--days", type=int, default=5,
                        help="how many weekdays ahead to sample (default 5)")
    parser.add_argument("--data", default=os.environ.get("SWINGDESK_DATA", "data"),
                        help="the directory holding directory.duckdb")
    parser.add_argument("--as-of", default=None, metavar="YYYY-MM-DD",
                        help="the date to sample forward from (default: today, local)")
    args = parser.parse_args(argv)

    # One read of the clock, tz-aware, and overridable. `AGENTS.md` §12: a partially pinned clock
    # is worse than an unpinned one, because its tests agree with the bug - so the default is the
    # only place this tool asks what day it is, and `--as-of` replaces it wholesale.
    today = (dt.date.fromisoformat(args.as_of) if args.as_of
             else dt.datetime.now(dt.UTC).astimezone().date())
    print(f"probe_events: {ENDPOINT.format(day='YYYY-MM-DD')}\n")
    print(f"forward schedule, {args.days} weekday(s) from {today}:")

    forward: list[dict[str, Any]] = []
    reachable = False
    for index, day in enumerate(weekdays_after(today, args.days)):
        if index:
            time.sleep(DELAY_SECONDS)
        payload = fetch(day.isoformat())
        if payload is None:
            continue
        reachable = True
        rows = rows_of(payload)
        forward.extend(rows)
        timed = sum(1 for row in rows
                    if str(row.get("time", "")) not in ("", "time-not-supplied"))
        stamp = (payload.get("data") or {}).get("asOf")
        suffix = "" if stamp is None else f" - asOf {stamp}"
        print(f"  {day}: {len(rows):4d} announcement(s), {timed:4d} with a session bucket{suffix}")

    if not reachable:
        print("\nprobe_events: the endpoint could not be reached. That is a fact about this "
              "network, not about the source - re-run before recording anything either way.")
        return 1

    print("\nhistory: does a past date return the realised figure, or only the forecast?")
    past = today - dt.timedelta(days=365)
    while past.weekday() >= 5:
        past -= dt.timedelta(days=1)
    time.sleep(DELAY_SECONDS)
    old_rows = rows_of(fetch(past.isoformat()))
    realised = sum(1 for row in old_rows if str(row.get("eps") or "").strip() not in ("", "N/A"))
    print(f"  {past}: {len(old_rows)} row(s), {realised} carrying a realised figure")

    print("\npoint-in-time: is `marketCap` an event-dated fact or a current-state one?")
    earlier = {str(row.get("symbol")): row for row in old_rows if row.get("symbol")}
    verdict = "UNTESTED - no symbol appeared in both samples, so nothing is claimed here"
    for row in forward:
        symbol = str(row.get("symbol", ""))
        if symbol and symbol in earlier:
            then = earlier[symbol].get("marketCap")
            now = row.get("marketCap")
            if then == now:
                verdict = (f"{symbol}: the {past} row and the forward row both report {now}. "
                           f"IDENTICAL, so this is current state and must never be read as the "
                           f"capitalisation at announcement")
            else:
                verdict = f"{symbol}: {past} reports {then} and the forward row reports {now}"
            break
    print(f"  {verdict}")

    print("\ncoverage: how much of this calendar is outside the US directory we already pull?")
    known = listed_symbols(Path(args.data))
    if known is not None:
        symbols = {str(row.get("symbol", "")).upper() for row in forward if row.get("symbol")}
        outside = sorted(symbols - known)
        print(f"  {len(symbols)} distinct symbol(s) in the forward window, "
              f"{len(symbols) - len(outside)} in directory.duckdb, {len(outside)} absent from it")
        if outside:
            print(f"  absent sample: {', '.join(outside[:12])}")
        # Stated as what was measured. Every symbol falling inside the US directory is CONSISTENT
        # with a US-only calendar and does not establish one - a window that happened to hold no
        # foreign name looks identical. The test that would settle it is a TSX-only symbol, and
        # this probe does not make it. Saying more here would be the qualifier-drift that cost
        # `DR-003` gap 1 its "in hand" and `PR-002` half its scope.
        print("  Every symbol above falling inside the US directory is consistent with a US-only "
              "calendar and does not prove one. Whether a TSX-only name ever appears is UNTESTED, "
              "and AGENTS.md section 3 never merges the two countries.")

    print("\nprobe_events: a free, keyless source for the E11 event calendar EXISTS. It does not "
          "supply the buffer to apply, and it cannot say what the schedule looked like on an "
          "earlier date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
