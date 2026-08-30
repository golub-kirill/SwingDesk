"""Gate 24: `HANDOFF.md` section 2's state block, generated rather than typed.

`AGENTS.md` §10.5 gave every measured count exactly one owner and gate 14 enforces it. That removed
the duplicate copies; it did not make the survivor true, because the survivor was typed by hand.

MEASURED 2026-08-15, which is what paid for this tool. HANDOFF §2's Track A row read *"counter at
3"* while `tools/track_a_streak.py` computed 4 - and the row described itself as *"computed by
`tools/track_a_streak.py` ... not hand-kept"*. The same table's directory row read *9 pulls, 1
confirmed* against a store holding 10 and 2. Both numbers sat in their single owner, both were
wrong, and nothing in the tree contradicted them. Concentrating a fact makes it findable, not true.

So section 2 is now generated between markers and `--check-only` is its gate - the same shape as
`build_frd.py`, `build_components.py`, `build_checklists.py`, `build_coverage.py` and
`build_lock.py`, none of which has ever gone stale.

**Three blocks, and only ONE of them is a fact about the repository.** Repo facts derive from the
tree: same answer in every checkout, on every machine, forever. Runtime facts derive from `data/`,
gitignored operational state present only in the main checkout. Worktree facts derive from
`git worktree list`, which is machine-local and changes minute to minute.

Splitting them is what lets `--check-only` verify the parts it can see and report the rest as
`UNAVAILABLE` rather than either failing everywhere or - the gate 23 mistake this tool exists to stop
repeating - exiting 0 as though it had checked.

**The worktree block was written as a repo fact on 2026-08-16 and CI rejected it within the hour.**
The generator ran on a runner with no sibling worktrees, produced an empty list, compared it against
five committed rows and called the file stale - correctly. Worktree state is not a property of the
repository; it is a property of the machine holding this copy of it, and no committed list can be
true on two machines at once. That is exactly the `data/` case, and it is handled the same way:
measured where measurable, `UNAVAILABLE` where not, never silently either way.

**The worktree block replaced a hand-typed table on 2026-08-16, for the same reason section 2 did.**
That table grew one row per effort, forever, with "what it holds" prose no tool could check - and it
required every session to remember to add its own row before its gates would pass. `git worktree
list` already knows which worktrees exist without being told. History belongs in `git log` and
`docs/08-pm/POSTMORTEM-2026-08-09.md`, which already carry it; a document a fresh session reads in
its first minute does not need to carry it twice.

Nothing here re-derives a number another tool already owns. The census comes from
`verify_counts.measure()`, the streak from `track_a_streak.measure()`, and the worktree list from
`verify_branches.worktree_branches()` - so gate 14, gate 16, gate 23 and this gate cannot disagree:
there is one implementation per fact.

Facts that no tool can derive - `master`'s branch protection, the Task Scheduler trigger, the G0-G7
project gates - stay hand-written BELOW the generated blocks, each carrying its own `as of` date.
That boundary is the honest one: generate what is derivable, date what is not, and never let the
second kind look like the first.

Needs PyYAML, pytest and duckdb, so it runs with the project venv.

    python tools/build_state.py                # rewrite the blocks in place
    python tools/build_state.py --check-only   # gate 24
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_ROOT_OVERRIDE = os.environ.get("SWINGDESK_ROOT")
REPO = Path(_ROOT_OVERRIDE or Path(__file__).resolve().parents[1])
HANDOFF = REPO / "HANDOFF.md"

#: The runtime stores. Overridable because several worktrees at once is this project's normal mode
#: (`HANDOFF.md` §2) and `data/` exists only in the main checkout - so a worktree that wants to
#: regenerate the runtime block points here rather than copying 228MB or hand-typing the result,
#: which is the failure this whole tool exists to end. There is one machine and one set of stores,
#: so pointing at them from a sibling tree reads the same facts, not different ones.
#:
#: Ignored when `SWINGDESK_ROOT` is pinned - a pinned root describes a complete tree, and a looser
#: variable must not reach outside it. Same ordering as `track_a_streak.py`, for the same reason.
DATA = Path(
    os.environ["SWINGDESK_DATA"]
    if os.environ.get("SWINGDESK_DATA") and not _ROOT_OVERRIDE
    else REPO / "data"
)

REPO_BEGIN = "<!-- BEGIN GENERATED: state:repo -->"
REPO_END = "<!-- END GENERATED: state:repo -->"
RUNTIME_BEGIN = "<!-- BEGIN GENERATED: state:runtime -->"
RUNTIME_END = "<!-- END GENERATED: state:runtime -->"
WORKTREES_BEGIN = "<!-- BEGIN GENERATED: state:worktrees -->"
WORKTREES_END = "<!-- END GENERATED: state:worktrees -->"

#: Exit code meaning "my subject is not present in this environment" (`check_gates.py`).
UNAVAILABLE_EXIT = 4

GENERATED_NOTE = (
    "*Generated by `tools/build_state.py` (gate 24). Do not edit between the markers - "
    "an edit here is overwritten and fails the gate.*"
)


# --------------------------------------------------------------------------- repo facts


def _studies() -> tuple[int, int]:
    """(registered, reported). A pre-registration is a `PR-*.md`; a report is its result page."""
    prereg = REPO / "docs" / "prereg"
    registered = len([p for p in prereg.glob("PR-*.md") if p.is_file()])
    reported = len(list((prereg / "results").glob("PR-*-report.md")))
    return registered, reported


def _criteria_version() -> str:
    import yaml

    document = yaml.safe_load((REPO / "registry" / "criteria.yml").read_text(encoding="utf-8"))
    return str(document.get("version", "unknown"))


def repo_rows() -> list[tuple[str, str]]:
    """Every fact derivable from the tree alone, in the order section 2 has always listed them."""
    from verify_counts import measure

    counts = measure()
    registered, reported = _studies()
    tests = counts.get("tests")

    return [
        ("Merge gates", f"**{counts['gates']}**, one command: `python tools/check_gates.py`"),
        ("Tests", f"**{tests}**, fully offline" if tests is not None
         else "UNAVAILABLE - pytest could not collect"),
        ("Docs", f"{counts['documents']} files, Tier 0-8 · indexed by `registry/project_manifest.yml`"),
        ("Components", f"{counts['components']} catalogued · {counts['components:registered']} "
                       f"registered · {counts['components:specified']} `specified` · "
                       f"**{counts['components:active']} `active`**"),
        ("Parameters", f"{counts['parameters']} - {counts['parameters:unset']} `unset`, "
                       f"{counts['parameters:assumed']} `assumed`, {counts['parameters:owner']} "
                       f"`owner`, **{counts['parameters:validated']} `validated`**"),
        ("Golden vectors", f"{counts['golden vectors']} vectors across "
                           f"{counts['golden components']} components"),
        ("Studies", f"{registered} registered · {reported} reported"),
        ("Criteria", f"`registry/criteria.yml` **v{_criteria_version()}**"),
    ]


def worktree_rows() -> list[tuple[str, str]]:
    """Every worktree currently checked out beside this one - not history, never typed by hand.

    An EMPTY list means this checkout has no siblings: a CI runner, a fresh clone, or the main
    checkout on a machine that happens to have none. That is not "zero worktrees exist anywhere",
    it is "none are visible from here", and the caller treats it as unmeasurable rather than as a
    measurement of nothing. Getting that distinction wrong is what broke CI the first time this
    block shipped.

    **Branch NAMES only - no tip, no merge state.** Both were tried and both self-reference: a
    worktree lists its own branch, so anything about that branch which moves when you commit leaves
    the census stale against itself the instant it is written. Tips move every commit. Merge state
    moves on the first commit (the branch stops equalling `master`) and again whenever any sibling
    merges. Gate 24 would have gone red on every commit, forever.

    `verify_branches.py` had already reasoned this out for tips - "a branch tip moves with every
    commit, so the gate would demand a HANDOFF edit per commit and be bypassed within a day" - and
    this block put them in a GATE-ENFORCED table anyway, which is strictly worse than the case that
    comment rejected. Merge state was then kept on the argument that it "flips once per lifecycle",
    which was wrong for the same reason one step removed.

    What remains changes only when a worktree is ADDED OR REMOVED, which is exactly the event a
    fresh session needs to know about and exactly what gate 16 exists to catch. Gate 16 still prints
    tip and merge state on every run, where a reader compares them and no parser depends on them.

    Reuses `verify_branches.py`'s own detection, so gate 16 (which checks that each branch name
    appears somewhere in this file) and this block can never disagree about what "currently checked
    out" means. A worktree whose directory now holds a different branch, or whose branch merged and
    was cleaned up, simply stops appearing - which is the point. There is no "what it holds" column:
    that was prose no tool could check, and it lived in the one document a fresh session reads before
    it has any of its own context to check it against. The commit history that produced each branch
    already says what it held, in more detail than a table cell ever could.
    """
    from verify_branches import worktree_branches

    return [(f"`{branch}`", "") for branch, _sha in worktree_branches()]


# ------------------------------------------------------------------------ runtime facts


#: The stores the runtime block reads. Named here so the failure path can tell "not here" from
#: "held by the evening run" out of the filesystem, rather than out of duckdb's error text.
STORES: tuple[str, ...] = ("journal.duckdb", "bars.duckdb", "directory.duckdb")


def _connect(name: str):
    """Read-only handle. Never opened for write: this tool reports state, it never changes it."""
    import duckdb

    return duckdb.connect(str(DATA / name), read_only=True)


def _journal_facts() -> list[tuple[str, str]]:
    connection = _connect("journal.duckdb")
    try:
        runs = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        dirty = connection.execute("SELECT COUNT(*) FROM runs WHERE code_dirty").fetchone()[0]
        open_runs = connection.execute(
            "SELECT COUNT(*) FROM runs WHERE completed_at IS NULL"
        ).fetchone()[0]
        decisions = connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        uncoded = connection.execute(
            "SELECT COUNT(*) FROM decisions "
            "WHERE decision = 'Skip' AND (reason_code IS NULL OR reason_code = '')"
        ).fetchone()[0]
    finally:
        connection.close()
    return [
        ("Journal", f"{runs} runs, {open_runs} incomplete · **{dirty} run(s) recorded against a "
                    f"dirty tree** and therefore not replayable from their SHA"),
        ("Decisions", f"{decisions} recorded · {uncoded} uncoded refusals "
                      f"(`a.no_uncoded_failures` requires 0)"),
    ]


def _bar_facts() -> tuple[list[tuple[str, str]], int]:
    """Store size and the point-in-time integrity check, plus the instrument count for coverage.

    The integrity row is the one to read first. `scan --as-of` pins the clock and still fetches
    fresh, so it can write a bar whose `event_time` postdates the `knowledge_time` it was stored
    under - a fact from the future, readable by a decision dated before it. The query is cheap and
    the answer must be 0 forever; carrying it here turns a one-off forensic check into a standing
    measurement.
    """
    connection = _connect("bars.duckdb")
    try:
        rows = connection.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        instruments = connection.execute(
            "SELECT COUNT(DISTINCT instrument_id) FROM bars"
        ).fetchone()[0]
        violations = connection.execute(
            "SELECT COUNT(*) FROM bars WHERE event_time > knowledge_time"
        ).fetchone()[0]
    finally:
        connection.close()
    verdict = "**CLEAN**" if violations == 0 else f"**{violations} VIOLATION(S)**"
    return [
        ("Bar store", f"{rows:,} rows across {instruments:,} instruments"),
        ("PIT integrity", f"{verdict} - bars whose `event_time` postdates their `knowledge_time`: "
                          f"{violations}"),
    ], instruments


def _canada_facts() -> list[tuple[str, str]]:
    """What the never-merge non-negotiable costs, as a number rather than as a phrase.

    Every reported study narrows to a US-only universe and cites `DR-003` for it, and `BR-9`'s
    per-country requirement has been unmet since the first one. `DR-003` gap 1 - *"no free symbol
    directory in hand"* - was refuted on 2026-08-25, so the question a fresh session needs answered
    stopped being *"is there a source?"* and became *"has anyone fetched anything?"*.

    That question had no owner. `DR-003`'s own addendum answers it in prose as *"the Canadian half
    of the store is empty today"*, which is a hand-written claim about `data/` sitting in an
    append-only record - the exact shape §10.6 exists to end. It is also not quite true: the store
    holds one `.TO` instrument, and a row that says *one, fetched once, never refreshed* is a
    different fact from *none*.

    Both halves are counted, because they fail independently: a symbol can be listed in the
    directory with no bars, and - as `CNQ.TO` demonstrates - can hold bars while absent from the
    directory, which is the identity defect `TODO.md` §6 records rather than a coverage figure.
    """
    bars = _connect("bars.duckdb")
    try:
        instruments = bars.execute(
            "SELECT COUNT(DISTINCT instrument_id) FROM bars WHERE instrument_id LIKE '%.TO'"
        ).fetchone()[0]
        rows, fetches, last = bars.execute(
            "SELECT COUNT(*), COUNT(DISTINCT knowledge_time), MAX(knowledge_time) FROM bars "
            "WHERE instrument_id LIKE '%.TO'"
        ).fetchone()
    finally:
        bars.close()
    directory = _connect("directory.duckdb")
    try:
        listed = directory.execute(
            "SELECT COUNT(DISTINCT symbol) FROM directory WHERE symbol LIKE '%.TO'"
        ).fetchone()[0]
    finally:
        directory.close()

    if not instruments and not listed:
        detail = "**nothing stored and nothing listed**"
    else:
        stamp = last.date().isoformat() if last is not None else "n/a"
        plural = "" if instruments == 1 else "s"
        fetched = "one fetch" if fetches == 1 else f"{fetches} distinct fetch times"
        detail = (f"**{instruments} instrument{plural}** with bars, {rows:,} bars over {fetched}, "
                  f"last {stamp} · **{listed}** `.TO` symbol(s) listed in `directory.duckdb`")
    return [
        ("Canada", f"{detail}. `BR-9`'s per-country requirement is unmet in every reported study. "
                   f"Since `DR-003` gap 1 was refuted (2026-08-25) a FORWARD result is blocked by "
                   f"this row rather than by a missing source; a HISTORICAL one also needs "
                   f"point-in-time membership, which the TMX endpoint cannot supply at any price"),
    ]


def _directory_facts(measured_instruments: int) -> list[tuple[str, str]]:
    connection = _connect("directory.duckdb")
    try:
        pulls = connection.execute(
            "SELECT COUNT(DISTINCT knowledge_time) FROM directory_pulls"
        ).fetchone()[0]
        confirmed = connection.execute(
            "SELECT COUNT(DISTINCT knowledge_time) FROM directory_pulls "
            "WHERE source_session_date IS NOT NULL"
        ).fetchone()[0]
        latest = connection.execute(
            "SELECT rows FROM directory_pulls ORDER BY knowledge_time DESC LIMIT 1"
        ).fetchone()
        # The two reasons a pull carries no session date are DIFFERENT facts and this row asserted
        # one of them for both until 2026-08-25. A pull taken BEFORE the field existed is
        # permanently unattributable (`DR-008` c3). A pull taken AFTER it and still null was
        # REJECTED by the monotonicity check in `DirectoryStore.record` - the vendor file had not
        # regenerated, so it is a re-pull of a session already recorded. Three of the ten were the
        # second kind while the row said all ten were the first, which is the drift §10.6 exists to
        # stop, living inside the generator that exists to stop it.
        boundary = connection.execute(
            "SELECT MIN(knowledge_time) FROM directory_pulls WHERE source_session_date IS NOT NULL"
        ).fetchone()[0]
        if boundary is None:
            predating, rejected = pulls - confirmed, 0
        else:
            predating = connection.execute(
                "SELECT COUNT(*) FROM directory_pulls "
                "WHERE source_session_date IS NULL AND knowledge_time < ?", [boundary]
            ).fetchone()[0]
            rejected = connection.execute(
                "SELECT COUNT(*) FROM directory_pulls "
                "WHERE source_session_date IS NULL AND knowledge_time > ?", [boundary]
            ).fetchone()[0]
    finally:
        connection.close()
    listed = int(latest[0]) if latest else 0
    coverage = f"{measured_instruments / listed:.1%}" if listed else "n/a"
    unattributed = (
        f"**{predating}** predate the field and stay permanently unattributed (`DR-008` c3)"
        if predating else "none predate the field"
    )
    if rejected:
        unattributed += (
            f"; **{rejected}** do NOT - they were taken after the field existed and the vendor "
            f"file had not regenerated, so `DirectoryStore.record`'s monotonicity check dropped "
            f"the claim. Each of those is a re-pull of an already-recorded session, which "
            f"`DR-008` says should make **zero requests**"
        )
    return [
        ("Directory", f"**{pulls} pulls** · **{confirmed} confirmed** against the response's own "
                      f"`Last-Modified` (`source_session_date`); of the rest, {unattributed}"),
        ("Universe coverage", f"bars stored for {measured_instruments:,} of {listed:,} listed "
                              f"symbols - **{coverage}**"),
    ]


def _classification_facts() -> list[tuple[str, str]]:
    """How much of the universe the sector cap can actually see (`DR-006` §12).

    **A coverage number, not a census, and the difference is the point.** The cap admits an
    unclassifiable candidate UNCHECKED and says so, because §3 forbids a check the system could not
    perform from refusing everything - so an empty store does not fail anything, it just means the
    cap protects nothing. That is invisible from the report of any single run and exactly the shape
    of fact `AGENTS.md` §10.6 says a tool must derive rather than a person remember.

    Two figures because they answer different questions: how many instruments carry a
    classification at all, and how many survive §8.7's degeneracy guard. A bond fund the vendor
    describes as healthcare 100% is classified and unusable, and collapsing the two would report
    coverage the cap does not have.

    Returns nothing at all when the store has never been created - the pass has not been run, which
    is a different state from a store holding zero and worth not inventing a row for.
    """
    if not (DATA / "classifications.duckdb").is_file():
        return []
    connection = _connect("classifications.duckdb")
    try:
        classified = connection.execute(
            "SELECT COUNT(DISTINCT instrument_id) FROM classifications"
        ).fetchone()[0]
        # Usable is computed HERE in SQL rather than by importing `look_through`, and that is a
        # deliberate limitation rather than a shortcut: this counts instruments with at least one
        # non-zero weight, which catches the empty and all-zero answers but NOT the degenerate
        # look-through. The row says so, so a reader does not take it for the stricter number.
        with_sectors = connection.execute(
            "SELECT COUNT(DISTINCT instrument_id) FROM classification_weights WHERE weight > 0"
        ).fetchone()[0]
    finally:
        connection.close()
    share = f"{with_sectors / classified:.1%}" if classified else "n/a"
    return [
        ("Classifications", f"{classified:,} instrument(s) carry a sector · {with_sectors:,} "
                            f"(**{share}**) report at least one non-zero weight. The stricter "
                            f"`look_through` count, which also drops a degenerate ETF "
                            f"look-through (`DR-006` §8.7), is lower - derive it with "
                            f"`python tools/measure_sector_cap.py --wide "
                            f"--classifications data/classifications.duckdb`"),
    ]


def _track_a_row() -> tuple[str, str]:
    """The streak, taken from gate 23's own measurement rather than recomputed.

    Two implementations of one number is how the number this tool exists to fix went wrong in the
    first place.

    **The restart is carried, and it has to be.** `HANDOFF.md` §5 states the rule the tool already
    follows on its own console - *"a bare zero after a deliberate reset is indistinguishable from an
    outage"* - and until 2026-08-22 this row did not follow it. It went unnoticed because a break
    date happened to be present in every zero so far, which gave the reader a cause. The restart on
    2026-08-22 truncated the countable window to sessions that have not happened yet, so `broke_at`
    became `None` and the row rendered a bare **0/20** with no explanation at all: the exact failure
    §5 describes, in the one document §10.5 makes the owner of the number.

    The DATE only. The reason is a paragraph and belongs where `track_a_streak.py` already prints
    it in full; a row that carried it would be a second copy going stale on its own schedule.
    """
    # `clock_now` rather than this module's own `datetime.now()`: the restart in force is a
    # function of the instant, and reading a different clock from the one gate 23 counts against is
    # how the two come to disagree. It was `_now` until 2026-08-22 and is public for this caller.
    from track_a_streak import TARGET_STREAK, clock_now, measure, restarted_at

    reading = measure()
    if reading is None:
        return ("Track A clock", "UNAVAILABLE - no `data/daily_run.log` in this checkout")
    body = f"**{reading.count}/{TARGET_STREAK}** consecutive clean sessions"
    if reading.count and reading.start and reading.end:
        body += f" ({reading.start} to {reading.end})"
    if reading.broke_at is not None:
        body += f" · most recent break {reading.broke_at}"
    restart = restarted_at(clock_now())
    if restart is not None:
        body += (f" · counting from a **deliberate restart on {restart[0]}**, not an outage - "
                 f"`python tools/track_a_streak.py` prints why")
    return ("Track A clock", body + " · `a.run_completes`, computed by `tools/track_a_streak.py`")


def runtime_rows() -> list[tuple[str, str]] | None:
    """Facts from `data/`, or None when this checkout has no local store.

    None is not an error and not an empty result. It is the third state: the subject of the
    measurement is absent here, so no claim about it can be made from this tree.
    """
    import duckdb

    if not DATA.is_dir():
        return None
    try:
        bar_rows, instruments = _bar_facts()
        return [
            *_journal_facts(),
            *bar_rows,
            *_directory_facts(instruments),
            *_canada_facts(),
            *_classification_facts(),
            _track_a_row(),
        ]
    except duckdb.IOException as error:
        # A store that cannot be opened is the SAME third state as one that is not here: this
        # checkout cannot measure the runtime block, so it must not rewrite it. `ADR-0004` makes the
        # stores single-writer, so the evening run holding `bars.duckdb` is the design working - and
        # `AGENTS.md` §12 names the right response: "UNAVAILABLE, never a traceback". This tool
        # raised one instead, caught 2026-08-24 at 18:31 while the scheduled 18:30 pass was mid-run.
        #
        # **Which of the two it is must be MEASURED, not assumed**, and until 2026-08-30 it was
        # assumed. The message said the scheduled run held the stores, and in GitHub Actions - where
        # `data/` exists but holds no store at all, and no scheduled run has ever existed - it said
        # so on every run, over a duckdb error reading `database does not exist`. The verdict was
        # right and the explanation was false, which is `AGENTS.md` §10.6 rule 2 in the direction of
        # confidence rather than alarm, and §15's rule that an explanation is itself a claim.
        # Decided from the filesystem rather than by parsing a vendor's error text.
        absent = [name for name in STORES if not (DATA / name).is_file()]
        if absent:
            print(f"state: {DATA} holds no {', '.join(absent)}. The runtime block is UNAVAILABLE "
                  f"from here and is left alone.")
        else:
            print(f"state: a store in {DATA} is open in another process - the scheduled run holds "
                  f"them while it works. The runtime block is UNAVAILABLE from here and is left "
                  f"alone.")
        print(f"       {error}")
        return None


# ----------------------------------------------------------------------------- rendering


def _table(rows: list[tuple[str, str]]) -> str:
    body = "\n".join(f"| {label} | {value} |" for label, value in rows)
    return f"| | |\n|---|---|\n{body}"


def render_repo() -> str:
    return f"{REPO_BEGIN}\n\n{GENERATED_NOTE}\n\n{_table(repo_rows())}\n\n{REPO_END}"


def render_worktrees(rows: list[tuple[str, str]]) -> str:
    """Render a NON-EMPTY worktree list. Callers must not render an empty one.

    An empty list is unmeasurable-from-here, not a measurement (see `worktree_rows`), and rendering
    it would overwrite another machine's true list with this machine's blindness.
    """
    listed = "\n".join(f"- {label}" for label, _ in rows)
    body = (
        f"{listed}\n\n"
        "*Tip and merge state deliberately absent - both move under this document's own feet. "
        "`python tools/verify_branches.py` prints them.*"
    )
    return f"{WORKTREES_BEGIN}\n\n{GENERATED_NOTE}\n\n{body}\n\n{WORKTREES_END}"


def render_runtime(rows: list[tuple[str, str]] | None) -> str:
    if rows is None:
        body = (
            "> **UNAVAILABLE in this checkout.** These figures derive from `data/`, which is "
            "gitignored operational state and exists only in the main checkout. Regenerate there:\n"
            "> `python tools/build_state.py`"
        )
    else:
        stamp = datetime.now(UTC).strftime("%Y-%m-%d")
        body = f"{_table(rows)}\n\n*Measured from `data/` on {stamp}.*"
    return f"{RUNTIME_BEGIN}\n\n{body}\n\n{RUNTIME_END}"


def _replace(text: str, begin: str, end: str, body: str) -> str:
    start = text.find(begin)
    stop = text.find(end)
    if start == -1 or stop == -1 or stop < start:
        raise LookupError(f"{HANDOFF.name} is missing the {begin!r} / {end!r} markers")
    return text[:start] + body + text[stop + len(end):]


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_state")
    parser.add_argument("--check-only", action="store_true",
                        help="fail if the committed blocks differ from what the tree measures")
    args = parser.parse_args()

    original = HANDOFF.read_text(encoding="utf-8")
    runtime = runtime_rows()
    worktrees = worktree_rows()

    # Each block is rewritten only when THIS checkout can measure its subject. A block left alone
    # keeps whatever the last machine that could measure it wrote, which is the only honest option:
    # overwriting it here would replace another environment's true answer with this one's blindness.
    updated = _replace(original, REPO_BEGIN, REPO_END, render_repo())
    if worktrees:
        updated = _replace(updated, WORKTREES_BEGIN, WORKTREES_END, render_worktrees(worktrees))
    if runtime is not None:
        updated = _replace(updated, RUNTIME_BEGIN, RUNTIME_END, render_runtime(runtime))

    unmeasurable = [
        name for name, measurable in
        (("worktrees", bool(worktrees)), ("runtime", runtime is not None))
        if not measurable
    ]

    if not args.check_only:
        HANDOFF.write_text(updated, encoding="utf-8")
        scope = "repo" + "".join(f" + {n}" for n in ("worktrees", "runtime") if n not in unmeasurable)
        skipped = f"; left alone: {', '.join(unmeasurable)}" if unmeasurable else ""
        print(f"state: wrote {HANDOFF.name} section 2 ({scope}{skipped})")
        return 0

    if updated != original:
        print(f"state: {HANDOFF.name} section 2 is stale. Regenerate:")
        print("  python tools/build_state.py")
        return 1

    if unmeasurable:
        # What could be checked here was checked. Naming what could not is the whole point - gate 23
        # returned 0 in exactly this situation and a hand-kept counter went uncontradicted for days
        # (`AGENTS.md` §10.6). Exit 4 is UNAVAILABLE, counted separately by `check_gates.py`, which
        # then refuses to print "all gates pass".
        print(f"state: repo block current; {' and '.join(unmeasurable)} "
              f"UNAVAILABLE (not visible from this checkout)")
        return UNAVAILABLE_EXIT

    print("state: section 2 current (repo + worktrees + runtime)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
