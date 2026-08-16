"""Gate 23 (advisory): the Track A streak, computed from the log rather than kept by hand.

`a.run_completes` (`registry/criteria.yml`) needs 20 CONSECUTIVE trading days of the scheduled run
completing. `HANDOFF.md` §2 has carried that number since 2026-08-09, updated by a human reading
`tail -40 data/daily_run.log` and `schtasks /Query` - the exact manual check this gate automates,
because "a silent failure resets it without announcing itself" (`HANDOFF.md` §5) describes a number
nobody is watching between sessions.

Computed from `data/daily_run.log`, not from a second hand-kept counter - the same reason
`SPEC_GAP_ANALYSIS.md`'s summary is recounted by gate 3e rather than trusted. The log is the
`daily_run.cmd` wrapper's own record, distinct from `data/journal.duckdb`'s `runs` table: the
Journal records every pipeline invocation regardless of how it was started (manual testing included),
while the log's `daily run starting`/`finished` pair exists only when the WRAPPER ran.

**A run counts as "the scheduled attempt" only within a tolerance window of the documented 18:30
local trigger.** This machine's local clock is validated - not assumed - as its own timezone by
running `date` directly, since the project's other timezone mistake (the withdrawn `gaps()`, and the
directory trailer question this rebuilt) was exactly this kind of unchecked assumption. Evening runs
never sit near a date boundary in any plausible zone, so the log's own calendar date is used directly
- no zone conversion needed here, unlike the vendor trailer.

The window matters because a scheduled run and a human's manual catch-up look identical in the log
except for when they started. Calibrated against a real case: the 2026-08-10 battery failure has no
log entry near 18:30 - the automatic attempt crashed before writing a line - and a hand re-run
finished at 20:46, 131 minutes late. `HANDOFF.md` §5 explicitly does not count that day toward the
streak ("treat the clock as starting with the first CLEAN SCHEDULED run"), and a +-30 minute window
reproduces that judgment exactly: the 20:41 start falls outside it, so 2026-08-10 correctly reads as
a missing scheduled attempt despite its logged exit 0.

**Exit code rule, from `HANDOFF.md` §5, not re-derived here:**
"Exit 0 is a completed run. Exit 2 is a refusal, which is a real outcome and not a failure. A crash
is exit 3 or a missing log entry, and that is what resets the counter." `src/swingdesk/presentation/
cli.py` shows exit 3 is a coded empty-universe outcome, not a literal crash - HANDOFF's classification
is followed as already-decided rather than second-guessed, because it is the ratified reading, not an
implementation detail this gate gets to reinterpret.

ADVISORY BY DESIGN, matching gate 21's reasoning: a scheduling failure has nothing to do with whether
today's code change is correct, so this never blocks a merge. It prints on every gate run instead,
which is the property that makes a silent reset impossible to miss for long - not a hard veto.

**Advisory is not the same as silent, and this gate confused the two until 2026-08-15.** `data/` is
gitignored operational state and exists only in the main checkout, so from a worktree there is no
log to read. This printed "nothing scheduled has run" and returned 0 - a false negative wearing a
PASS. HANDOFF section 2's Track A row was hand-kept at 3 while the main checkout measured 4, and
nothing contradicted it because the gate reported success from every tree that could not see the
subject. That is the shape of gate 16's own fixed bug, "green from a worktree, red from the main
checkout".

So a checkout with no log now returns `UNAVAILABLE` (exit 4), not 0. A LOW streak is still a PASS -
being behind on the clock is a fact about the schedule, not about today's change - but a streak this
gate could not measure is not reported as one it did (`AGENTS.md` §10.6).

Stdlib only.

    python tools/track_a_streak.py
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal

_ROOT_OVERRIDE = os.environ.get("SWINGDESK_ROOT")
REPO = Path(_ROOT_OVERRIDE or Path(__file__).resolve().parents[1])

#: `data/` is gitignored operational state and exists only in the main checkout. `SWINGDESK_DATA`
#: lets a worktree read it - several worktrees at once is this project's normal mode, and a gate
#: that is structurally blind from most of them is how the hand-kept counter went unchallenged.
#:
#: **Ignored when `SWINGDESK_ROOT` is pinned, and that ordering is load-bearing.** A caller that
#: pins the root is describing a COMPLETE tree - every test does - so letting a looser variable
#: reach outside it would make the suite read the developer's real stores instead of its fixture.
#: Written the other way round first, and three tests caught it within the minute.
DATA = Path(
    os.environ["SWINGDESK_DATA"]
    if os.environ.get("SWINGDESK_DATA") and not _ROOT_OVERRIDE
    else REPO / "data"
)
LOG = DATA / "daily_run.log"

#: This machine's own local zone, read once. `DTZ` is a deliberate repo-wide rule with no
#: exemption for `tools/` ("every stored time is tz-aware") - this module compares wall-clock
#: times (the schedule, the log's own naive timestamps) against each other, never against UTC, so
#: every value here is tagged with THIS zone rather than left naive or mixed with UTC.
LOCAL_ZONE = datetime.now().astimezone().tzinfo


def _now() -> datetime:
    """Wall clock, overridable by `SWINGDESK_NOW` (ISO datetime, naive - interpreted as local) so a
    test can pin it - the same pattern `SWINGDESK_ROOT` already uses for the filesystem root. Never
    set in normal use; a gate that only ever runs against the real clock cannot be tested against a
    chosen "today" without every fixture aging out as real time passes. Not a `src/` wall-clock
    read (gate 7 does not apply here): the decision path never touches this file."""
    override = os.environ.get("SWINGDESK_NOW")
    if override:
        return datetime.fromisoformat(override).replace(tzinfo=LOCAL_ZONE)
    return datetime.now().astimezone()


#: The documented trigger (`HANDOFF.md` §1, "weekdays 18:30 local") - this machine's OWN local
#: clock, matching what Windows Task Scheduler and `daily_run.cmd`'s `%TIME%` both use.
SCHEDULE = time(18, 30)

#: Calibrated against the 2026-08-10 case (see module docstring): wide enough for ordinary
#: scheduler jitter, narrow enough to exclude an hours-later manual catch-up.
TOLERANCE = timedelta(minutes=30)

#: `a.run_completes`, `registry/criteria.yml`.
TARGET_STREAK = 20

#: Exit code meaning "my subject is not present in this environment" (`check_gates.py`).
UNAVAILABLE_EXIT = 4

#: First scheduled day (`HANDOFF.md` §2: "SCHEDULED 2026-08-09").
SCHEDULING_STARTED = date(2026, 8, 9)

#: Codes that continue the streak. Every other code - and a session with no qualifying entry at
#: all - resets it (`HANDOFF.md` §5, quoted above).
CLEAN_EXIT_CODES = (0, 2)

_STARTING = re.compile(
    r"^===== \[\w+ (\d{2})/(\d{2})/(\d{4})\s+(\d{1,2}):(\d{2}):\d{2}\.\d+\] daily run starting"
)
_FINISHED = re.compile(
    r"^===== \[\w+ \d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\.\d+\] daily run finished, exit (-?\d+)"
)


@dataclass(frozen=True, slots=True)
class Attempt:
    session_date: date
    started_at: time
    exit_code: int | None  # None: a "starting" line with no matching "finished" - incomplete


def _parse_attempts(text: str) -> list[Attempt]:
    """Every wrapper invocation the log recorded, paired starting-to-finished in file order."""
    attempts: list[Attempt] = []
    pending: tuple[date, time] | None = None
    for line in text.splitlines():
        start = _STARTING.match(line)
        if start:
            if pending is not None:
                attempts.append(Attempt(pending[0], pending[1], None))
            month, day, year, hour, minute = (int(g) for g in start.groups())
            pending = (date(year, month, day), time(hour, minute))
            continue
        finish = _FINISHED.match(line)
        if finish and pending is not None:
            attempts.append(Attempt(pending[0], pending[1], int(finish.group(1))))
            pending = None
    if pending is not None:
        attempts.append(Attempt(pending[0], pending[1], None))
    return attempts


def _within_schedule(started_at: time) -> bool:
    """Time-of-day comparison only - the reference date is arbitrary and identical on both sides,
    so it never participates in the result. Tagged with `LOCAL_ZONE` to satisfy `DTZ`, not because
    either side crosses a zone boundary."""
    reference = date(2000, 1, 1)
    scheduled = datetime.combine(reference, SCHEDULE, tzinfo=LOCAL_ZONE)
    actual = datetime.combine(reference, started_at, tzinfo=LOCAL_ZONE)
    return abs(actual - scheduled) <= TOLERANCE


def _scheduled_outcome(attempts: list[Attempt], session_date: date) -> int | None:
    """The exit code of THE scheduled attempt for `session_date`, or None if none qualifies.

    An in-window "starting" with no "finished" (`exit_code is None`) is an incomplete run and
    reports as `None` here too - indistinguishable from never having started, which is correct:
    both mean no evidence this session's run completed.
    """
    for attempt in attempts:
        if attempt.session_date == session_date and _within_schedule(attempt.started_at):
            return attempt.exit_code
    return None


def _evaluable_sessions(as_of: datetime) -> tuple[date, ...]:
    """NYSE sessions from `SCHEDULING_STARTED` through the most recent one whose scheduled window
    has already closed. Today is excluded while its own run may still be in progress."""
    last_evaluable = as_of.date()
    if datetime.combine(last_evaluable, SCHEDULE, tzinfo=LOCAL_ZONE) + TOLERANCE > as_of:
        last_evaluable -= timedelta(days=1)
    return tuple(
        s.session_date
        for s in cal.sessions(Exchange.NYSE, SCHEDULING_STARTED, last_evaluable)
        if s.session_date <= last_evaluable
    )


def streak(attempts: list[Attempt], as_of: datetime) -> tuple[int, date | None, date | None]:
    """The current consecutive-clean-session count, its start date, and the date that broke the
    PRIOR streak (the most recent missing-or-non-clean session before the current run), if any.

    Walks backward from the most recent evaluable session, stopping at the first missing or
    non-clean outcome.
    """
    sessions = _evaluable_sessions(as_of)
    count = 0
    start: date | None = None
    broke_at: date | None = None
    for session_date in reversed(sessions):
        outcome = _scheduled_outcome(attempts, session_date)
        if outcome in CLEAN_EXIT_CODES:
            count += 1
            start = session_date
        else:
            broke_at = session_date
            break
    return count, start, broke_at


@dataclass(frozen=True, slots=True)
class Reading:
    """One measurement of the streak, so callers share this gate's arithmetic instead of redoing it.

    `end` is the most recent evaluable session, which is what `count` is counted back from.
    """

    count: int
    start: date | None
    end: date | None
    broke_at: date | None
    break_reason: str | None


def measure(as_of: datetime | None = None) -> Reading | None:
    """The current streak, or `None` when this checkout holds no log.

    `None` is the third state and it is deliberately not zero. Zero is a measurement - the schedule
    ran and nothing qualified. `None` means the subject is absent from this tree, and the two must
    never render the same way (`AGENTS.md` §10.6).
    """
    if not LOG.is_file():
        return None
    attempts = _parse_attempts(LOG.read_text(encoding="utf-8", errors="replace"))
    now = as_of or _now()
    count, start, broke_at = streak(attempts, now)
    sessions = _evaluable_sessions(now)

    reason: str | None = None
    if broke_at is not None:
        outcome = _scheduled_outcome(attempts, broke_at)
        reason = "no qualifying scheduled-window entry" if outcome is None else f"exit {outcome}"

    return Reading(
        count=count,
        start=start,
        end=sessions[-1] if sessions else None,
        broke_at=broke_at,
        break_reason=reason,
    )


def main() -> int:
    reading = measure()
    if reading is None:
        print("track A: UNAVAILABLE - no data/daily_run.log in this checkout.")
        print("  `data/` is gitignored operational state and lives only in the main checkout.")
        print("  This is not a streak of zero. Run it there to measure one.")
        return UNAVAILABLE_EXIT

    if reading.count == 0:
        print("track A streak: 0")
    else:
        print(f"track A streak: {reading.count}/{TARGET_STREAK} consecutive clean sessions "
              f"({reading.start} to {reading.end})")
    if reading.broke_at is not None:
        print(f"  most recent break: {reading.broke_at} ({reading.break_reason})")
    if reading.count >= TARGET_STREAK:
        print(f"  a.run_completes is MET as of {reading.start}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
