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

**The idle-day line, added 2026-08-16, council-reviewed.** `CLEAN_EXIT_CODES = (0, 2)` is correct
and unchanged: a coded refusal is a real, non-crash outcome, and `a.run_completes`'s ratified text
only ever claimed the run completes and produces a report. What it does not claim, and what people
read into the number anyway, is that the run did anything - and once `exit.atr_stop_multiple` /
`exit.max_holding_period` merge unset, every candidate Skips and every position Pauses for the
identical reason, and every one of those days still counts as clean. `idle_days()` answers that
separately, from `data/journal.duckdb` rather than the log (which has no decision-level detail): of
the streak's counted sessions, how many had a run where nothing distinguished one candidate's
outcome from another's. It changes nothing about the count above it - only makes the gap visible.

Reads `data/journal.duckdb` in addition to the log, so no longer stdlib-only.

    python tools/track_a_streak.py
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.reference import Exchange
from swingdesk.journal_evidence.journal import DecisionRecord, Journal
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
JOURNAL = DATA / "journal.duckdb"

#: This machine's own local zone, read once. `DTZ` is a deliberate repo-wide rule with no
#: exemption for `tools/` ("every stored time is tz-aware") - this module compares wall-clock
#: times (the schedule, the log's own naive timestamps) against each other, never against UTC, so
#: every value here is tagged with THIS zone rather than left naive or mixed with UTC.
LOCAL_ZONE = datetime.now().astimezone().tzinfo


def clock_now() -> datetime:
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

#: DELIBERATE restarts: a merge to a frozen file that changed decision output, which the 2026-08-16
#: amendment (`HANDOFF.md` §5, council-reviewed, unanimous) resets the counter to zero from.
#:
#: THIS EXISTED ONLY AS PROSE UNTIL 2026-08-17, and the rule fired that day with nothing to enforce
#: it. PR #9 merged - five correctness fixes to `pipeline.py` and `sizing.py`, every one of which
#: changes what the run decides - and this tool went on reporting 5/20, counting four days
#: (2026-08-11 to 08-14) that ran under the defective pipeline. That is the exact number the
#: amendment was written to forbid: "splicing them onto a corrected system's streak would report
#: confidence in a system that only existed for one day."
#:
#: A date here is a claim that the system evaluating candidates changed on that date. Adding one is
#: how the rule is applied; there is no other mechanism, and prose was already shown not to be one.
#: Sessions on or before a restart date never count toward the current streak, even if their runs
#: exited cleanly - they measured a different system.
STREAK_RESTARTS: tuple[tuple[date, str], ...] = (
    (date(2026, 8, 17),
     "PR #9 - FX refusal, cost-inclusive R denominator, one exit policy read from the registry, "
     "output_hash widened to cover trade terms and open positions, a held position's vendor-ticker "
     "lookup. Merged with DR-012's ratification as ONE transition costing ONE reset (DR-012 section 8.6)"),
    (date(2026, 8, 18),
     "DR-015 built - the staleness gate reached the decision path. Two frozen files changed "
     "(pipeline.py, daily_run.cmd) and the change moves decision output: measured against the "
     "2026-08-17 run, 67 of 1152 candidates were one session behind and were sized and left on "
     "Watch; they now leave with a DATA skip. A streak spanning that boundary would count days "
     "spent deciding on stale data toward a system that refuses to"),
    (date(2026, 8, 22),
     "DR-006's book cap reached the decision path. One frozen file changed (pipeline.py) and the "
     "change moves decision output: a candidate that would push the book past risk.max_open_risk "
     "(4R) or risk.max_concurrent_positions (4) now leaves with a Skip/RISK where it used to reach "
     "Watch. Also sizing.py, cosmetically - two private helpers made public so the cap reuses the "
     "one FX rule and the one definition of 1R rather than copying either. Taken while the counter "
     "already read 0, which is DR-015 section 3's argument reused: the reset costs nothing today "
     "and would cost weeks in two weeks"),
    (date(2026, 8, 30),
     "DR-017 and DR-023 built and ratified together. Two frozen files changed (daily_run.cmd, "
     "pipeline.py) and both changes move decision output. DR-017: the 20-session ADTV window now "
     "ends 3 sessions before the run, so admission is decided on volume the vendor has never been "
     "observed to revise; universe_hash widens to cover the lag. DR-023: the symbol directory is "
     "pulled BEFORE the pipeline rather than after it, so the 18:30 pass stops building its "
     "universe from the previous evening's list - 3 to 18 already-delisted instruments reached it "
     "each night. Measured, and it is why the two merged: of the 7 instruments that left the "
     "universe between the 18:30 and 19:30 passes over 08-25/26/27, 5 left because volume was "
     "rewritten across the $5M floor within that hour and hold their side of it under the lag, 1 "
     "left on a late bar, and 1 on the directory. ONE reset for both, taken while the counter "
     "already read 0 - DR-015 section 3's argument for the third time, and here the two halves fix "
     "one symptom between them, so neither could have been verified alone"),
    (date(2026, 8, 30),
     "DR-024 - CARD-001's own measure reaches the run. The RS line (M31-T0464) is computed for "
     "every candidate against rs.benchmark and printed with its validation status, which is what "
     "COMPONENT_REGISTRY_SPEC 3 needs before the component can be `active`; it is now the second "
     "active component and the first a live strategy card names. It DECIDES nothing - all four of "
     "CARD-001's selection parameters are unset - but output_hash gains the RS field, so no earlier "
     "run replays to the same hash and this moves decision output by that route. "
     "SECOND ROW ON THE SAME DATE, DELIBERATELY, and it costs nothing: `streak` counts sessions "
     "STRICTLY AFTER the restart date, 2026-08-30 is a Sunday, and the countable sessions after the "
     "row above measured ZERO when this landed. Two rows dated one day truncate the identical "
     "window. That is a fact about this day and not a licence - from 2026-08-31 the one-reset rule "
     "applies again in full"),
    (date(2026, 8, 31),
     "DR-025 - the sector guard stops reading the look-through's SHAPE. DR-006 8.7 refused a fund "
     "reporting one sector at exactly 100%, inferring it holds no equity. Measured over 35 funds: "
     "the vendor's sector weights sum to 1.0000 for EVERY fund regardless of holdings, including "
     "the ten that report 0% equity - they are normalised over what the vendor could classify, not "
     "over the fund's assets, so the shape never carried the information. It refused 23 admitted "
     "universe members including five SPDR Select Sector funds at 99.7%+ equity, and a refusal "
     "reports unavailable, which DR-006 3 ADMITS UNCHECKED - so the guard was maximally permissive "
     "on the most concentrated instruments it had. Now only a vendor-declared 0% equity refuses. "
     "Moves decision output: sector-spendable universe members go 1018 -> 1041, every one of them "
     "in the conservative direction. NOT scaled by the equity share - stockPosition is physical "
     "equity, not economic exposure, and AAPU reads 0.074 while being 2x Apple. Taken on the "
     "owner's grant of a restart for this date"),
)


def restarted_at(as_of: datetime) -> tuple[date, str] | None:
    """The most recent deliberate restart at or before `as_of`, if any."""
    past = [r for r in STREAK_RESTARTS if r[0] <= as_of.date()]
    return max(past, key=lambda r: r[0]) if past else None

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

    # A deliberate restart truncates the countable window. Not a "break" - `broke_at` reports a
    # FAILURE, and a restart is the opposite: a correctness fix landing on purpose. Reporting one as
    # the other would make an intentional reset read as an outage in every later summary.
    restart = restarted_at(as_of)
    if restart is not None:
        sessions = tuple(s for s in sessions if s > restart[0])

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
    now = as_of or clock_now()
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


def _idle(decisions: list[DecisionRecord]) -> bool:
    """True when nothing on this run distinguished one candidate from another.

    Every decision carries the identical `(decision, reason_code, parameter_id)` - the shape a run
    takes when every candidate is refused for the same unset parameter, or the run evaluated
    nothing at all. An empty run counts as idle too: no decisions is not a weaker form of variety.

    Council finding, 2026-08-16: `CLEAN_EXIT_CODES` counts a run like this the same as a run that
    actually sized and proposed something, because a coded refusal (exit 2) is a legitimate,
    non-crash outcome and correctly so - Skip is a first-class decision, not a lesser one. This
    function does not relitigate that; it answers a different question the exit code cannot: did
    the run see more than one shape of outcome, or was every candidate turned away identically.
    """
    if not decisions:
        return True
    first = (decisions[0].decision, decisions[0].reason_code, decisions[0].parameter_id)
    return all((d.decision, d.reason_code, d.parameter_id) == first for d in decisions)


@dataclass(frozen=True, slots=True)
class IdleReading:
    """How much of the current streak had no substance, alongside how much could even be checked."""

    idle: int
    examined: int
    unmatched: int


def idle_days(reading: Reading, journal_path: Path = JOURNAL) -> IdleReading | None:
    """Of the streak's counted sessions, how many were idle. `None` when there is nothing to check.

    A SEPARATE measurement from `measure()`, deliberately - it does not change what
    `a.run_completes` counts as clean, which stays exactly its ratified text ("the daily run
    completes and produces a report"). This answers the question people actually read into that
    number and the exit code alone cannot: how many of the counted days had a run that evaluated
    anything, versus one that skipped every candidate for the identical reason.

    Matches a session date to its run the way the log does - the documented 18:30 local trigger
    +- `TOLERANCE` - but against `runs.started_at` in the Journal, because the log carries no
    decision-level detail (this module's own docstring: "distinct from the Journal").
    `unmatched` counts streak sessions with no run found in that window: not assumed clean, not
    assumed idle - genuinely unmeasured, the same three-state discipline `measure()` itself uses.
    """
    if reading.start is None or reading.end is None or not journal_path.is_file():
        return None

    window_start = datetime.combine(reading.start, time.min, tzinfo=LOCAL_ZONE).astimezone(UTC)
    window_end = datetime.combine(reading.end, time.max, tzinfo=LOCAL_ZONE).astimezone(UTC)
    sessions = {
        s.session_date
        for s in cal.sessions(Exchange.NYSE, reading.start, reading.end)
    }

    with Journal(journal_path) as journal:
        runs = journal.runs_starting_between(window_start, window_end)
        matched: set[date] = set()
        idle = 0
        for run_id, started_at in runs:
            local_start = started_at.astimezone(LOCAL_ZONE)
            if not _within_schedule(local_start.time()):
                continue
            session_date = local_start.date()
            # Only the scheduled attempt counts for a date, same rule the log follows - a manual
            # re-run later the same day is not what the streak is measuring.
            if session_date not in sessions or session_date in matched:
                continue
            matched.add(session_date)
            if _idle(journal.decisions_for(run_id)):
                idle += 1

    return IdleReading(idle=idle, examined=len(matched), unmatched=len(sessions) - len(matched))


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

    # Printed whenever one applies, because a small number after a restart means something entirely
    # different from a small number after an outage, and the reader cannot tell them apart otherwise.
    #
    # `clock_now()`, not `datetime.now()`. This line read the wall clock while the COUNT above was
    # measured against `SWINGDESK_NOW`, so with the two pinned apart the tool would name a restart it
    # had not counted from - and on any day after a new restart row lands, name one that had not
    # happened yet at the pinned instant. Found 2026-08-22 by the row added that day: a test pinned
    # to 2026-08-18 went on passing because the printed line was reading today's date rather than
    # the one it had pinned. Same shape as the fixture trap in `AGENTS.md` §12.
    restart = restarted_at(clock_now())
    if restart is not None:
        print(f"  counting from a deliberate restart on {restart[0]}: {restart[1]}")
    if reading.count >= TARGET_STREAK:
        print(f"  a.run_completes is MET as of {reading.start}")

    # Advisory, additional to the count above - never changes it (2026-08-16, council-reviewed).
    #
    # `idle_days` returns None for TWO reasons and they are not the same claim: the journal is absent
    # (a fact about this checkout) or the streak has no counted sessions (a fact about the streak).
    # Printing the first message for the second case asserts something false about the environment,
    # which is the `unavailable`-is-not-`zero` conflation `AGENTS.md` 12 calls the most damaging
    # error this product can make. Latent until 2026-08-17, when the deliberate restart made a zero
    # streak the normal state and the tool immediately claimed a database that exists does not.
    idle = idle_days(reading)
    if idle is None and not JOURNAL.is_file():
        print("  idle-day check: UNAVAILABLE - no data/journal.duckdb in this checkout.")
    elif idle is None:
        print("  idle-day check: nothing to check - the streak has no counted sessions yet.")
    elif idle.examined:
        print(
            f"  {idle.idle}/{idle.examined} counted day(s) were idle (every candidate refused "
            f"identically)"
            + (f", {idle.unmatched} unmatched" if idle.unmatched else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
