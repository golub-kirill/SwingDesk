"""Download the NASDAQ Trader symbol directory and record it as one dated pull.

The two files cover every US venue in scope. There is no equivalent for Canada, which is why the
`.TO` universe is still a list rather than a rule (DR-003 gap 1).

Run this before the universe can be built, and periodically after - each run adds a snapshot, and
consecutive snapshots are the only free survivorship evidence available to this project. Skipping
runs does not lose accuracy today; it loses the departure record permanently.

Network tool. Never imported by anything in src/, never run in CI (CI_POLICY 4).

    python tools/fetch_directory.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data import universe
from swingdesk.reference_data.directory import DirectoryStore

SOURCE = "nasdaqtrader.com/SymDir"
USER_AGENT = "swingdesk/0.0"
FILES = {
    "nasdaqlisted.txt": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "otherlisted.txt": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}

#: The vendor's own end-of-day marker, e.g. "File Creation Time: 0813202621:31".
_TRAILER = re.compile(r"File Creation Time:\s*(\d{2})(\d{2})(\d{4})(\d{2}):(\d{2})")

#: Confirmed 2026-08-13 against the live response: trailer "0813202621:31" read as America/New_York
#: (21:31 EDT) equals 2026-08-14 01:31 UTC, matching that same response's own
#: `Last-Modified: Fri, 14 Aug 2026 01:31:44 GMT` to within 44 seconds. Read as UTC it is off by
#: exactly 4 hours - the trailer is Eastern local time, not UTC. Not re-derived on every run; the
#: `Last-Modified` cross-check below is what stays live, because a single confirmation on one day
#: does not prove the vendor's two clocks can never drift apart later.
_TRAILER_ZONE = ZoneInfo("America/New_York")

#: How far trailer-as-ET and Last-Modified may disagree and still corroborate each other. The
#: observed gap was 44 seconds; this leaves headroom for ordinary write latency without accepting a
#: trailer that merely happens to land on the right calendar date for the wrong reason.
_CORROBORATION_TOLERANCE = timedelta(minutes=5)

#: Response cap (DR-008). Applied to Content-Length AND to bytes actually read, so a server that
#: omits or misstates the header cannot bypass it.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

#: Per-machine switch. Ignored by git, never committed, and absent means OFF - the same
#: fail-closed rule the parameter registry uses. There is deliberately no committed default.
LOCAL_CONFIG = ".swingdesk-local.json"
REPO = Path(__file__).resolve().parents[1]


def collection_enabled(root: Path) -> bool:
    """True only for an explicit boolean true; missing, unreadable, malformed, or false refuse."""
    config = root / LOCAL_CONFIG
    if not config.is_file():
        return False
    try:
        loaded = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    value = loaded.get("directory_pull_enabled") if isinstance(loaded, dict) else None
    return value is True


def _download(url: str) -> tuple[str, str | None]:
    """The decoded body, and the response's own `Last-Modified` header (or None if absent)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
            raise ValueError(f"{url}: declared {declared} bytes exceeds the cap")
        body = response.read(MAX_RESPONSE_BYTES + 1)
        last_modified = response.headers.get("Last-Modified")
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"{url}: body exceeds the {MAX_RESPONSE_BYTES} byte cap")
    return body.decode("utf-8"), last_modified


def _trailer_time(text: str) -> datetime | None:
    """The vendor's `File Creation Time`, as America/New_York local time. None if absent or
    malformed - a missing trailer refuses rather than guessing."""
    match = _TRAILER.search(text)
    if match is None:
        return None
    month, day, year, hour, minute = (int(g) for g in match.groups())
    try:
        return datetime(year, month, day, hour, minute, tzinfo=_TRAILER_ZONE)
    except ValueError:
        return None


def _corroborated_session_date(text: str, last_modified: str | None) -> date | None:
    """The trailer's date, only when the response's own `Last-Modified` header confirms it.

    A trailer is a claim inside the file it describes - trusting it alone is exactly what the
    withdrawn capture-instant approach did, just with a different field. `Last-Modified` is an
    independent signal from the same response; agreement between two vendor-supplied clocks is
    corroboration, not a second guess. Refuses (returns None) on a missing or malformed trailer, a
    missing or unparseable header, or disagreement beyond `_CORROBORATION_TOLERANCE`.
    """
    trailer = _trailer_time(text)
    if trailer is None or last_modified is None:
        return None
    try:
        modified = parsedate_to_datetime(last_modified)
    except (TypeError, ValueError):
        return None
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=UTC)
    if abs(trailer.astimezone(UTC) - modified.astimezone(UTC)) > _CORROBORATION_TOLERANCE:
        return None
    return trailer.date()


def main() -> int:
    parser = argparse.ArgumentParser(prog="fetch_directory")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="honour the local switch and the exchange calendar; the manual form ignores both, "
             "because a human asked for it",
    )
    args = parser.parse_args()

    if args.scheduled:
        if not collection_enabled(REPO):
            print(f"directory pull disabled - no {LOCAL_CONFIG} with directory_pull_enabled: true")
            return 0
        if not cal.is_open(Exchange.NYSE, datetime.now(UTC).date()):
            print("not an NYSE session - nothing to collect")
            return 0

    nasdaq_text, nasdaq_modified = _download(FILES["nasdaqlisted.txt"])
    other_text, other_modified = _download(FILES["otherlisted.txt"])
    entries = [
        *universe.parse_nasdaq_listed(nasdaq_text),
        *universe.parse_other_listed(other_text),
    ]
    eligible = [e for e in entries if e.is_eligible]
    knowledge_time = datetime.now(UTC)

    # Both files must independently corroborate the SAME date - two files built on different days
    # is itself a sign something is wrong, not a tiebreaker to resolve.
    nasdaq_date = _corroborated_session_date(nasdaq_text, nasdaq_modified)
    other_date = _corroborated_session_date(other_text, other_modified)
    claimed_date = nasdaq_date if nasdaq_date == other_date else None
    if claimed_date is None:
        print("source_session_date unattributable - trailer/Last-Modified did not corroborate "
              "on one or both files, or the two files disagreed")

    with DirectoryStore(args.data / "directory.duckdb") as store:
        previous = store.latest_pull(knowledge_time)
        stored_date = store.record(entries, knowledge_time, SOURCE, claimed_date)
        print(f"recorded {len(entries)} rows ({len(eligible)} eligible) at {knowledge_time:%Y-%m-%d %H:%M}Z")
        if claimed_date is not None and stored_date is None:
            print(f"source_session_date {claimed_date} rejected - not strictly after the last "
                  "stored session date; the vendor file may not have regenerated")
        elif stored_date is not None:
            print(f"source_session_date confirmed: {stored_date}")

        if previous is None:
            print("first pull - no departures to report, and none are recoverable for earlier dates")
            return 0

        gone = store.departures(previous, knowledge_time)
        arrived = len(
            {e.symbol for e in entries} - {e.symbol for e in store.as_of(previous)}
        )
        print(f"since {previous:%Y-%m-%d}: {len(gone)} symbol(s) gone, {arrived} new")
        for symbol in gone[:20]:
            print(f"    gone: {symbol}")
        if len(gone) > 20:
            print(f"    ... and {len(gone) - 20} more")
        print("\nA departure is an observation, not a delisting - a ticker change looks the same.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
