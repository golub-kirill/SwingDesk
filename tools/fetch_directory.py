"""Download the NASDAQ Trader symbol directory and record it as one dated pull.

The two files cover every US venue in scope. There is no equivalent for Canada, which is why the
`.TO` universe is still a list rather than a rule (DR-003 gap 1).

Run this before the universe can be built, and periodically after - each run adds a snapshot, and
consecutive snapshots are the only free survivorship evidence available to this project. Skipping
runs does not lose accuracy today; it loses the departure record permanently.

Network tool. Never imported by anything in src/, never run in CI (CI_POLICY 4).

**Three modes, and `DR-008` ratified all three.** `SCHEDULED` honours the local switch, the NYSE
calendar and the already-recorded-session guard. `MANUAL` — the bare form — honours none of them,
because a human asked. `FORCED` is the emergency re-pull: it honours the switch and the calendar
like the scheduled form and bypasses **only** the already-recorded guard, which is the whole reason
it exists.

**The already-recorded guard and the forced pull are one change, built together 2026-08-25.**
Neither works alone: a guard with no override strands an operator whose first pull was malformed,
and an override with nothing to override is decoration. Until they existed the collector re-pulled
a session it already held — measured on the live store, 3 of 18 pulls were same-session duplicates
that `DirectoryStore.record` then stripped of their session date, and `DR-008` says those should
have made **zero requests**.

**Every invocation writes one audit row**, including the ones that make no request. A refusal that
recorded nothing left the store unable to tell "declined" from "never ran".

    python tools/fetch_directory.py
    python tools/fetch_directory.py --scheduled
    python tools/fetch_directory.py --emergency-repull --reason "first pull returned a truncated file"
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
import urllib.request
from collections.abc import Sequence
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


def digest(*bodies: str) -> str:
    """A `DR-008` checksum over the response bodies, in the order they were fetched.

    **One digest over both files, not one each.** A pull is a complete snapshot - the record's own
    framing, and the reason `DirectoryStore.as_of` reads the latest pull rather than unioning - so
    the thing worth identifying is the pair. Two files whose contents swapped between them would be
    a different snapshot and must not collide, which is what the length prefix prevents.
    """
    hasher = hashlib.sha256()
    for body in bodies:
        encoded = body.encode("utf-8")
        hasher.update(str(len(encoded)).encode("ascii"))
        hasher.update(b":")
        hasher.update(encoded)
    return hasher.hexdigest()


def gap_severity(gaps: Sequence[date]) -> str | None:
    """`DR-008`: one consecutive miss is a `WARNING`; two or more are an `ERROR`.

    **Consecutive is the word that matters** and it is about a RUN, not a total. Eight isolated
    single misses over two months are eight recoverable evenings; two in a row means whatever
    stopped the collector was still stopping it the next day, and the departure record has a hole no
    later run can fill. Returns `None` when there is nothing to say, because a collector that
    announced "0 gaps" every evening would train its reader to skip the line.
    """
    if not gaps:
        return None
    ordered = sorted(gaps)
    longest = run = 1
    for earlier, later in itertools.pairwise(ordered):
        # Consecutive SESSIONS, not consecutive dates - a Friday and the Monday after it are
        # adjacent here, and treating the weekend as a gap would report one every week.
        run = run + 1 if _adjacent_sessions(earlier, later) else 1
        longest = max(longest, run)
    return "ERROR" if longest >= 2 else "WARNING"


def _adjacent_sessions(earlier: date, later: date) -> bool:
    """True when no NYSE session sits strictly between the two."""
    between = cal.sessions(Exchange.NYSE, earlier, later)
    return len(between) == 2


def main() -> int:
    parser = argparse.ArgumentParser(prog="fetch_directory")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="honour the local switch and the exchange calendar; the manual form ignores both, "
             "because a human asked for it",
    )
    parser.add_argument(
        "--emergency-repull",
        action="store_true",
        help="DR-008's forced pull: one two-file attempt, no internal retry, recorded as FORCED. "
             "Bypasses ONLY the already-recorded-session guard and the retry budget - never the "
             "local switch, the NYSE calendar, the response cap, validation or the audit row. "
             "Requires --reason, and a reason that differs from the last forced pull's",
    )
    parser.add_argument(
        "--reason",
        default=None,
        help="why this forced pull is being made. Required by --emergency-repull, non-empty, and "
             "must not repeat the previous forced pull's reason",
    )
    args = parser.parse_args()

    started_at = datetime.now(UTC)
    forced = args.emergency_repull
    mode = "FORCED" if forced else ("SCHEDULED" if args.scheduled else "MANUAL")
    reason = (args.reason or "").strip() or None
    store_path = args.data / "directory.duckdb"

    # Usage errors, not policy refusals, and they write no audit row on purpose: argparse rejects an
    # unknown flag with exit 2 and no record either, and these are the same class of mistake. A
    # refusal the COLLECTOR makes - disabled, closed, already recorded, reason repeated - is a fact
    # about the evening and is audited below.
    if args.reason is not None and not forced:
        print("--reason is only meaningful with --emergency-repull")
        return 2
    if forced and reason is None:
        print("--emergency-repull requires a non-empty --reason (DR-008)")
        return 2

    # An invocation that makes zero requests still writes its audit row, so `_finish` is the single
    # exit for every branch below. A refusal that recorded nothing would leave the store unable to
    # distinguish "declined" from "never ran" - which is the state this table was added to end.
    enabled = collection_enabled(REPO)

    def _finish(result: str, *, requests: int = 0, attempts: int = 0,
                received: int = 0, snapshot: datetime | None = None, code: int = 0) -> int:
        with DirectoryStore(store_path) as audit_store:
            audit_store.record_audit(
                started_at=started_at, finished_at=datetime.now(UTC), mode=mode, reason=reason,
                enabled=enabled, attempts=attempts, requests=requests, received_bytes=received,
                result=result, snapshot=snapshot,
            )
        return code

    # `DR-008`: the forced form "does not bypass local disablement, the NYSE calendar, source
    # allowlist, response cap, validation, process lock or audit". So these two gates bind it as
    # tightly as they bind the scheduled form; only the already-recorded guard below is bypassed.
    if args.scheduled or forced:
        if not enabled:
            print(f"directory pull disabled - no {LOCAL_CONFIG} with directory_pull_enabled: true")
            return _finish("DISABLED")
        if not cal.is_open(Exchange.NYSE, started_at.date()):
            print("not an NYSE session - nothing to collect")
            return _finish("NOT_A_SESSION")

    if forced:
        with DirectoryStore(store_path) as guard_store:
            previous_reason = guard_store.last_forced_reason()
        if previous_reason is not None and previous_reason == reason:
            print("--reason repeats the previous forced pull's reason; DR-008 requires a new one")
            return _finish("REASON_REPEATED", code=2)

    # `DR-008`: "A successful session is not fetched again automatically ... an already-recorded
    # session makes zero requests." Decided from the CALENDAR against what is already attributed,
    # because the vendor's own session date does not arrive until the file does.
    #
    # **The guard keys on the ATTRIBUTED session, so it fails OPEN, and that is the right
    # direction.** A pull whose trailer and `Last-Modified` did not corroborate stores a NULL date,
    # so this guard does not see it and the next pass fetches again - which is correct, because an
    # unattributed pull is precisely the case where we do not know whether we hold that session.
    # The failure mode is therefore today's behaviour, never something worse.
    superseded: datetime | None = None
    target_session = cal.last_completed_session(Exchange.NYSE, started_at).session_date
    with DirectoryStore(store_path) as guard_store:
        already = guard_store.pull_for_session(target_session)
    if already is not None:
        if not forced:
            if args.scheduled:
                print(f"session {target_session} is already recorded - no requests made "
                      f"(DR-008). Use --emergency-repull --reason ... to override")
                return _finish("ALREADY_RECORDED")
        else:
            superseded = already

    nasdaq_text, nasdaq_modified = _download(FILES["nasdaqlisted.txt"])
    other_text, other_modified = _download(FILES["otherlisted.txt"])
    received = len(nasdaq_text.encode("utf-8")) + len(other_text.encode("utf-8"))
    checksum = digest(nasdaq_text, other_text)
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

    with DirectoryStore(store_path) as store:
        previous = store.latest_pull(knowledge_time)
        # The digest is compared BEFORE the pull is recorded, or the pull just written would be
        # the latest one and every evening would report "identical to itself".
        previous_checksum = store.latest_checksum()
        stored_date = store.record(
            entries, knowledge_time, SOURCE, claimed_date,
            supersedes=superseded, checksum=checksum,
        )
        print(f"recorded {len(entries)} rows ({len(eligible)} eligible) at {knowledge_time:%Y-%m-%d %H:%M}Z")
        if superseded is not None:
            # Appended, never overwritten: the superseded pull stays in `directory` and in
            # `directory_pulls`, and this row is the only thing that says it is no longer the
            # answer. `DR-008`: "The previous snapshot remains stored but is no longer canonical."
            store.record_supersession(
                recorded_at=knowledge_time, superseded=superseded,
                replacement=knowledge_time, reason=reason or "",
            )
            print(f"FORCED: replaces the pull of {superseded:%Y-%m-%d %H:%M}Z for session "
                  f"{target_session}; that snapshot remains stored and is no longer canonical")
        if claimed_date is not None and stored_date is None:
            print(f"source_session_date {claimed_date} rejected - not strictly after the last "
                  "stored session date; the vendor file may not have regenerated")
        if previous_checksum is not None:
            # Says which of the two an unattributed pull was, instead of leaving it ambiguous.
            if previous_checksum == checksum:
                print("checksum: byte-identical to the previous pull - the vendor served the same "
                      "files, so this adds no observation the store did not already hold")
            else:
                print("checksum: differs from the previous pull")
        elif stored_date is not None:
            print(f"source_session_date confirmed: {stored_date}")

        if previous is None:
            print("first pull - no departures to report, and none are recoverable for earlier dates")
        else:
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

        # `DR-008`: gaps are recorded, never backdated, and research claiming continuous coverage
        # must disclose them. Reported over the ATTRIBUTED window only - before the first attributed
        # pull there is no session to be missing from, and calling that a gap would report ten
        # phantom ones.
        attributed = store.attributed_sessions()
        if attributed:
            window = [s.session_date for s in cal.sessions(Exchange.NYSE, attributed[0], attributed[-1])]
            gaps = store.gaps(window)
            severity = gap_severity(gaps)
            if severity is None:
                print(f"coverage: {len(attributed)} attributed session(s), "
                      f"{attributed[0]} to {attributed[-1]}, no gaps")
            else:
                print(f"{severity}: {len(gaps)} session(s) with no attributed pull inside "
                      f"{attributed[0]}..{attributed[-1]}: "
                      + ", ".join(str(g) for g in gaps[:10])
                      + (f" and {len(gaps) - 10} more" if len(gaps) > 10 else ""))
                print("A gap is permanent - the vendor publishes current state, not an archive.")

    return _finish(
        "RECORDED", requests=2, attempts=1, received=received, snapshot=knowledge_time,
    )


if __name__ == "__main__":
    raise SystemExit(main())
