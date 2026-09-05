# HANDOFF — start here in a fresh session

Written 2026-08-04; **brought current 2026-09-02**. Read this, then **`AGENTS.md`'s rule index** —
every rule in one line, and the column saying which ones nothing will catch — then §12's traps, then
`docs/README.md`.

## 0. The first thing, and it is not code

~~**Everything is merged.**~~ **Do not read that from here — it was true on the morning of
2026-08-25 and stopped being true by mid-day.** Ask the tree instead, which is the only answer that
cannot rot:

```bash
python tools/verify_branches.py          # every live branch, and whether it is merged
python tools/verify_sibling_edits.py     # what another live branch is editing, before you edit it
```

~~**`claude/swingdesk-open-tasks-2001c8` is unmerged and holds real work**~~ — **merged
2026-08-29** into `claude/swingdesk-open-tasks-f2773d`, with the two `CI_POLICY.md` rows gate 36
required and that neither branch could write alone. It carried the directory collector, the AI
guard's vocabulary half, gates 22 and 31, and the EDGAR departure classifier; §5 below now
summarises it alongside `claude/inspiring-colden-2e8e16`. **Do not read that from here either** —
the two commands above are the only answer that cannot rot, and this line is struck rather than
deleted for the same reason §0 opens the way it does.

**Run the second command before editing anything another branch might be editing.** On 2026-08-25
two trees rewrote the same two table rows two hours apart with gate 16 green, because gate 16's
subject is whether a worktree is *declared* and both were. `AGENTS.md` §10.1 now carries the rule
that came out of it.

**Read these four before touching the flow, the registry or the criteria. Each changes what you
would otherwise assume, and each was measured rather than argued.**

1. **`Trade` is unreachable in code, and that is now explained rather than merely observed.**
   Across the live application layer the decision token `Skip` appears in seventeen places, `Watch`
   in one, **`Trade` in none**, and every decision in `journal.duckdb` is `Watch` or `Skip`. The
   nightly `Trade 0` is a property of the code. The cause is one gap seen from three sides: the
   course specifies nine watchlist states, the transitions between them were never authored
   (`DECISION_STATE_MACHINE.md` §6, open since 2026-08-01), and Appendix E cannot return `Ready`
   because eight of its items are unanswerable. **`DR-020` authors the graph and decides no number;
   `docs/08-pm/plans/2026-08-24-the-trade-flow.md` is the plan.**
   *(`Pause` is absent from the candidate path CORRECTLY — the state machine models it as
   account-wide.)*
2. **The only ratified criterion with scope `live` cannot fire.** `k.drawdown_pause`'s threshold is
   owner-set at 20% and **nothing in `src/` computes realised drawdown**; its prescribed action
   names `risk.risk_off_ladder`, which is `unset`. Every gate passed over it for a defensible
   reason — 3g checks that inputs EXIST, 1 accepts `none` as honest — and neither asks whether a
   ratified criterion can FIRE. Gate 1 now prints that subset on every run.
3. **"Canada cannot be enumerated" is false, and the research record narrowed itself on it.**
   `DR-003` wrote *"no free symbol directory in hand … cannot presently enumerate"*. TMX serves the
   directory free, no account: `python tools/probe_canada.py --full`, re-verified 2026-08-25.
   **It repairs no study** — the endpoint is today's membership, and applying it to old data is
   survivorship bias with extra steps.
   **Counted 2026-08-25, and this line said "a study" until then.** `PR-001`, `PR-002`, `PR-005`
   and `PR-008` all narrowed to a US-only universe on that record, citing it eight times. Five keep
   `DR-003`'s *"in hand"* qualifier; **three turn it into an unqualified "cannot"** — `PR-002`'s
   report twice and `PR-001`'s own registration once, where the qualifier survives the first clause
   of a sentence and dies in the second. `PR-001` §10's third amendment counts them and names the
   command that re-derives the split.
   **The citations were swept and live documents were stale** — `ROADMAP.md` §5 is corrected here;
   `RISK_REGISTER.md` D-3 and `UX_TASK_FLOWS.md` were corrected on
   `claude/swingdesk-open-tasks-2001c8` two hours before this tree reached them, **and both trees
   found it independently**, which is `POSTMORTEM-2026-08-09.md` root cause A repeating with gate 16
   green. Those two rows are deliberately left at `master`'s text on this branch so the sibling's
   version merges without a conflict; `tools/verify_sibling_edits.py` is the check that would have
   said so at the start.
   **What blocks Canada now is a fetch nobody has run**, and §2's `Canada` row owns the number: the
   directory holds zero `.TO` symbols and the bar store holds one `.TO` instrument, fetched once on
   2026-08-02 and never refreshed.
4. **"No free source serves delisted history" is half false.** SEC EDGAR serves the FACT and DATE of
   a delisting, free and official, back to 1993 (`tools/probe_edgar.py`). Prices for a delisted name
   are still unobtainable, so the bound's RETURN half stands untouched.

**The rules are not listed here any more, and that is the point.** `AGENTS.md` opens with an index
— one line per rule, with the gate that catches you or the word **honour** when nothing does — and
gate 37 keeps it from drifting from the rules it lists. Enumerating them here would be the second
copy §10.5 forbids. **Owner instruction, 2026-08-25: that file governs, and it is to be followed
strictly.**

**The evening of 2026-08-24, which matters because it is the first clean one since 08-18:** both
passes ran `exit 0` and decided **identically** — same `output_hash` an hour apart on the real
universe, the first live observation of a property `DR-015` §3 only asserted. `DR-019` makes the
second pass conditional, because it has never changed an outcome and the failure it insures against
has never occurred here.

**`master` is protected** on `github.com/golub-kirill/SwingDesk` (public) and requires the `gates`
check, so it only ever advances to a commit CI has already passed.

Everything below is measured from the tree, not remembered. **§2 is the only place a measured count
lives** (`AGENTS.md` §10.5); a figure here that disagrees with `python tools/check_gates.py` is this
document being wrong, not the gate.

That rule has one hole worth knowing: gate 14 matches digits, so a count spelled in words is
invisible to it. This paragraph replaced *"Twenty-two gates"*, which had been wrong since the gate
count reached 24 and no gate could see it.

---

## 1. What this is

Decision-support software for swing trading Canadian and US equities and ETFs, specified from the
owner's 116-PDF swing-trading course. **It never places orders** — owner decision D1. **The final
trading decision is human-only** — charter amendment A-001. The system prepares, checks and records;
the human decides.

The founding premise: previous attempts failed *upstream of code* — goals, limits and the algorithm
were never frozen first. So documentation is the deliverable, and the code exists to prove the
documentation is implementable.

## 2. State, measured

**Nothing in the generated blocks below is typed by hand** — here, or in the worktree census further
down. They were, and they went stale while saying they had not — see `AGENTS.md` §10.6 for the
numbers that paid for this. Regenerate with `python tools/build_state.py`; gate 24 fails if they
drift, and reports `UNAVAILABLE` rather than guessing for the blocks a given checkout cannot see.

### Derived from the tree

<!-- BEGIN GENERATED: state:repo -->

*Generated by `tools/build_state.py` (gate 24). Do not edit between the markers - an edit here is overwritten and fails the gate.*

| | |
|---|---|
| Merge gates | **49**, one command: `python tools/check_gates.py` |
| Tests | **1347**, fully offline |
| Docs | 147 files, Tier 0-8 · indexed by `registry/project_manifest.yml` |
| Components | 465 catalogued · 459 registered · 4 `specified` · **2 `active`** |
| Parameters | 108 - 57 `unset`, 34 `assumed`, 17 `owner`, **0 `validated`** |
| Golden vectors | 25 vectors across 6 components |
| Studies | 10 registered · 8 reported |
| Criteria | `registry/criteria.yml` **v1.1.2** |

<!-- END GENERATED: state:repo -->

### Derived from `data/` — main checkout only

<!-- BEGIN GENERATED: state:runtime -->

| | |
|---|---|
| Journal | 59 runs, 8 incomplete · **22 run(s) recorded against a dirty tree** and therefore not replayable from their SHA |
| Decisions | 56753 recorded · 0 uncoded refusals (`a.no_uncoded_failures` requires 0) |
| Bar store | 7,479,252 rows across 13,008 instruments |
| PIT integrity | **CLEAN** - bars whose `event_time` postdates their `knowledge_time`: 0 |
| Directory | **26 pulls** · **16 confirmed** against the response's own `Last-Modified` (`source_session_date`); of the rest, **7** predate the field and stay permanently unattributed (`DR-008` c3); **3** do NOT - they were taken after the field existed and the vendor file had not regenerated, so `DirectoryStore.record`'s monotonicity check dropped the claim. Each of those is a re-pull of an already-recorded session, which `DR-008` says should make **zero requests** |
| Universe coverage | bars stored for 13,008 of 13,188 listed symbols - **98.6%** |
| Canada | **1 instrument** with bars, 252 bars over one fetch, last 2026-08-02 · **0** `.TO` symbol(s) listed in `directory.duckdb`. `BR-9`'s per-country requirement is unmet in every reported study. Since `DR-003` gap 1 was refuted (2026-08-25) a FORWARD result is blocked by this row rather than by a missing source; a HISTORICAL one also needs point-in-time membership, which the TMX endpoint cannot supply at any price |
| Classifications | 3,984 instrument(s) carry a sector · 3,560 (**89.4%**) report at least one non-zero weight. The stricter `look_through` count, which also drops a degenerate ETF look-through (`DR-006` §8.7), is lower - derive it with `python tools/measure_sector_cap.py --wide --classifications data/classifications.duckdb` |
| Track A clock | **4/20** consecutive clean sessions (2026-09-01 to 2026-09-04) · counting from a **deliberate restart on 2026-08-31**, not an outage - `python tools/track_a_streak.py` prints why · `a.run_completes`, computed by `tools/track_a_streak.py` |

*Measured from `data/` on 2026-09-05.*

<!-- END GENERATED: state:runtime -->

### Not derivable — hand-kept, each with its date

| | As of | |
|---|---|---|
| `master` | 2026-08-10 | **protected** — required check `gates`, admins included, no force-push. A new merge commit is refused until its check reports; fast-forward a green commit, or use a PR |
| CI | 2026-08-24 | `gates`, windows-latest. **Five** `UNAVAILABLE`, verified against run `32757431015`: gates 2 and 3 need the course PDFs, which are not in the repo; gates 23, 24 and **26** need `data/` or the scheduling machine. Everything else must be green. ~~Exactly **four** … verified against run `32093559374`~~ — that row was written 2026-08-17 and gate 26 landed on the 18th, so it asserted four for six days while CI reported five. Gates 28 and 29 were added after this run and both execute in CI; **29's cross-branch half cannot**, and prints that it did not run rather than passing for a check it never made. **Gates 32-36, added 2026-08-25, all run in CI and none is `UNAVAILABLE`** — but **33 is a second case of 29's shape**: a shallow clone has no sibling branches, so it prints `DID NOT RUN` and returns 0, which the summary shows as `PASS`. It is advisory by design and vetoing was never on the table; the honest reading is that a green 33 on GitHub says nothing about overlaps. ~~**The count of five is unverified since that run** and needs a CI pass to confirm~~ - **confirmed, see above** | **RE-VERIFIED 2026-08-30 against run `33293707486`**, the first CI pass carrying gates 22 and 31: still **Five** and still the same five - 2, 3, 23, 24 and 26 - with 22 and 31 both green there. So the row's own open question is closed, and the two gates the sibling branch added are proven to run off this machine. **One thing that pass exposed:** gate 24 reported `UNAVAILABLE` for the right reason and printed the WRONG one - it said the scheduled run was holding the stores, in an environment that has no scheduled run and no store, over a duckdb error reading *database does not exist*. Fixed the same day and pinned by a test; the verdict was never wrong, the explanation was.
| Daily run | 2026-08-24 | **SCHEDULED** — Windows Task Scheduler, `SwingDesk daily run`, weekdays 18:30 local, wrapper `tools/daily_run.cmd`, log `data/daily_run.log`. **~6 min per pass** over 1,141 members, of which **160 s** is compute and ~3 min is 1,141 sequential vendor fetches — measured 2026-08-24 by `tools/verify_reproducible.py`, which ran two full passes in 11m40s. It was ~24 min that morning; the row read ~5 min and had been right on 2026-08-09 |
| Costs | 2026-08-09 | slippage **measured** — 25bps per side (`DR-005`); commission still assumed |
| ТЗ coverage | 2026-08-24 | FULL 29 · PARTIAL 26 · ABSENT 0 · DEFERRED 2 — recounted from `SPEC_GAP_ANALYSIS.md` §3 by gate 3e. Two rows moved: §32 out of DEFERRED because charter amendment A-001 put the AI contour in scope, and §18 out of FULL because `PR-002`'s verdict — its only stated evidence — was corrected to `inconclusive` |
| Project gates | 2026-08-10 | G0, G4, G5 closed · G1, G2, G3, G6, G7 open |

```bash
PYTHONPATH=$PWD/src python tools/check_gates.py
```

Must stay green. A gate that is wrong gets **fixed or removed, never skipped**.

### You are not the only effort. Check this before starting work.

This repository's normal mode is **several worktrees at once**. On 2026-08-09 three efforts branched
from `9a07fab`, none knew about the others, and one re-ran a study another had already finished and
reached the opposite conclusion — `docs/08-pm/POSTMORTEM-2026-08-09.md`, root cause A. Gate 16 fails
if a worktree below is missing — but the list itself is never hand-typed: it comes from `git worktree
list`, the same source gate 16 reads, so the two can never disagree and no session has to remember to
add its own row. History of what each past effort held lives in `git log` and `POSTMORTEM-2026-08-09.md`,
not here — a document read in a session's first minute does not need to carry it twice
(`AGENTS.md` §10.6, extended 2026-08-16 to this table after it grew the same way a hand-typed count
once did).

<!-- BEGIN GENERATED: state:worktrees -->

*Generated by `tools/build_state.py` (gate 24). Do not edit between the markers - an edit here is overwritten and fails the gate.*

- `claude/a-handoff-for-the-blocked-claims`
- `claude/the-audit-overturned-my-own-finding`

*Tip and merge state deliberately absent - both move under this document's own feet. `python tools/verify_branches.py` prints them.*

<!-- END GENERATED: state:worktrees -->

## 3. The uncomfortable summary

**The machinery is real and honest. The strategy is not known to work, and what is known is mostly
negative.** The standing account of what the reported studies support moved to
[`docs/08-pm/EVIDENCE_SUMMARY.md`](docs/08-pm/EVIDENCE_SUMMARY.md) on 2026-08-15 — it outlives any
one session, and `AGENTS.md` §10.7 keeps this file to what does not.

Four things a fresh session must not get wrong, each argued there:

- the base strategy is **negative at measured costs** across the whole admissible universe, and no
  price an eligible instrument can have makes it positive;
- the spread **level is not obtainable from daily OHLC** — treat 25bp as "materially more than 5",
  never as a measurement of 25;
- the one positive finding (`PR-002`) is **erased by 1.6–2.3% of trades missing at −2R**, which the
  free tier ~~can never rule out~~ **could not rule out until 2026-09-05**, when Alpaca was
  asked for the first time and served complete daily paths for delisted names — 19,188 inactive
  US equities enumerated, `EIO` 767 bars to its delisting, `BHBK` 815. `feed=sip` only; the free
  IEX feed serves none of it, coverage starts 2016-01-04, and whether SIP historical is
  free-tier or this account's is unestablished. `python tools/probe_alpaca_delisted.py`, and
  `EVIDENCE_SUMMARY.md` §3 carries what it does and does not license;
- **there is no legal source of probability in this system today.** Any probability displayed would
  be manufactured.

**And a fifth — WHICH CHANGED ON 2026-09-01, and the change is the single most important thing in
this file.** ~~Every decision this system has ever taken is a `Watch` or a `Skip`. Not one is a
`Trade`. `pipeline.py`'s terminal state for a candidate that passes every check is the literal
`"Watch"` with the reason "sized; awaiting a trigger" — and there is no trigger in the live path,
so `"Trade"` is in the decision vocabulary and is emitted by nothing in `src/`.~~

**`CARD-001` SELECTS, and the system emits `Trade`.** `DR-030` ruled its four selection inputs by
owner preference on 2026-09-01; `decision_logic/selection.py` is the cross-sectional screen and
`pipeline._select` runs it after the candidate loop, because a rank is a property of the
cross-section and the loop decides one name at a time. That is *why* the terminal state was `Watch`
for the card's whole life: the trigger is membership of the selection set, and nothing computed it.

**Read what that does and does not mean, because the distance between them is the whole project.**

| | |
|---|---|
| does mean | the run ranks its survivors, takes the top decile, and every loser carries its rank and the cutoff in its `Watch` reason |
| does **not** mean | anything is validated. `CARD-001` is still `Untested`, its `evidence` is still null, and `DR-030` §3.1 **registers in advance that it is expected to FAIL** `b.expectancy` |

**The provenance is `owner`, never `validated:`,** and that is not a technicality — it is the whole
claim. `ALLOCATION_SPEC` §3's pre-registration route was followed to its **end** and closed:
`PR-012` refused on a structural sample ceiling, `PR-013` ran the per-date design and returned six
intervals all including zero. And `b.min_sample` is `measured_by: journal`, so **no backtest could
ever have marked the card `Validated` whatever it measured** — which is what turned the study's job
from a verdict into defensible provenance. `screen.trend_definition`'s registry note is the
precedent and it prescribes exactly this mechanism for a closed family.

No position has still ever been opened, no fill recorded, no management proposal made. The tallies
move every evening and §2 owns them — derive the split with `python tools/build_state.py`, and the
per-verdict breakdown from `data/journal.duckdb` directly. (This paragraph carried three counts for
six hours until the 18:30 run moved all three, which is the drift `AGENTS.md` §10.5 exists to stop
and it happened inside the document that states the rule.)

**The absence of an AI is a ratified decision, not a gap.** Charter amendment A-001: the final
trading decision is human-only, and an AI may never decide, size, override a veto or originate a
number. Nobody should go looking for the missing recommender.

Do not write anything implying more confidence than that. `UX_COPY.md` §3 carries the standing
warning verbatim.

## 4. The plan — adopted 2026-08-08

**`ROADMAP.md` §9 is the plan of record.** It governs the roadmap's Now/Next/Later; where they
disagree, it wins. The phase table that used to sit here is a second copy of it and has been removed
(`AGENTS.md` §10.5).

Two adopted adjustments survive here because they are decisions, not state:

- **The MVP is behind us.** What looks like one from here is **activation**; §2 has the standing.
- **Coverage is demand-driven.** "Maximum coverage" is `k.project_timebox`'s own named kill risk.
  The test before implementing anything: **name the strategy card that consumes it.** No card → it
  stays `registered`, which costs nothing.
- **Scheduling was reversed 2026-08-09** and the daily run is scheduled, so phase 3′ runs in
  parallel with phase 2. `k.track_a_timebox`'s 120-day branch is the live one.

## 5. Next — the plan of record is a document now

### 5.0c THE NEXT SESSION'S JOB, and it is one job — audit the BLOCKED claims

**Owner instruction, 2026-09-04:** *"lets keep working on pending questions, ratifications, etc.
All questions where you declaring that you can not reseach."*

**What to do.** `TODO.md` is full of sentences saying something is blocked, missing, unwired, has no
source, or needs the owner. **Test them.** Not re-read — tested, against the tree, the stores or the
source.

`tools/blocked_claims.py` is the worklist, built 2026-09-04 for this job: it prints the open items
whose text asserts something is blocked, missing or impossible, with their line numbers. **It finds
SENTENCES, not truth** — whether each is still true is what the session then answers, one command at
a time. Derive the population from it rather than trusting a number written here:

```bash
python tools/blocked_claims.py --list
```

**Why this is the highest-value work available, and it is measured rather than argued.** Every
sweep of this kind made in the last two weeks found the claims wrong at a rate nothing else in this
repository comes close to:

| when | what was tested | how many were false |
|---|---|---|
| 2026-08-25 | the impossibility audit's ranked claims | four of seven |
| 2026-09-04 (evening) | blockers on entries opened the night before | three of the eight opened |
| 2026-09-04 (this session) | five blocked entries picked at random | three, all the same shape |

**The shapes to expect, because all three keep recurring:**

1. **The blocker EXPIRED and the entry did not.** *"The scheduled pass never reconciles"*, *"a fill
   is never recorded without a person"*, *"blocked on a missing symbol directory"* — each correct on
   its own date, each false within days, none marked. `[v]` does not protect against this: it
   records that an item was verified WHEN WRITTEN.
2. **The TITLE asserts what the entry's own BODY has already struck.** Three found in one pass —
   *"`a.reproducible` has never been measured"* over a paragraph reporting the measurement,
   *"almost every recorded `Skip` is …"* over *"no such skip since the parameter was set"*. **This
   one needs no measurement at all**: the contradiction is inside the entry.
3. **The claim is an IMPOSSIBILITY nobody tested** (`AGENTS.md` §15). *"Canada cannot be
   enumerated"*, *"no free source serves delisted history"*, and on 2026-09-04 *"bond and
   foreign-market ETFs cannot be identified from what we hold"* — that last one was about to be
   written into a pre-registration when the vendor turned out to serve both fields, in a response
   this project already makes and discards.

**The method, and it is the whole of the instruction.** For each claim: name the command or the
query that would show it had changed, run it, and write the answer. If it is still true, say so with
today's date and the command beside it — that is what makes the next re-read cheap. If it is false,
correct the entry AND its title, and check what CITED it (`AGENTS.md` §12: a citation rots when the
fact moves, not when it is written).

**Do not open new research to answer one.** `PR-011b` was drafted and stopped on 2026-09-04 for
exactly that reason, on the owner's instruction: *"That's bad ... we have a very big debt already."*
A study is not how you find out whether last week's sentence is still true.

**Two things this session got wrong, both recorded rather than tidied away, because they are the
failure mode to avoid while doing this work:**

- an argument was made that closing a book position on the venue's silence was unsafe *because an
  empty response cannot be told from a failed read*. **False** — the adapter raises on any non-200,
  on bad credentials and on a non-JSON body. `DR-038` §4 carries the correction;
- `sync-fills` was seen not to close a position, the cause was declared to be the fills feed's
  default window, and a fix was written before the claim was tested. Measured afterwards: **the feed
  returns the same rows with and without the window**, and the real reason was that the position had
  already been closed. The branch was discarded unpushed. **Declaring a cause is a claim, and it is
  the same claim §15 is about.**

### 5.0a What changed on 2026-09-03 and 2026-09-04 — the machine protects itself now

**Read this before touching the submission path.** Sixteen pull requests landed across those two
days and the shape of the system changed: it went from *placing orders and stopping* to *placing
orders, protecting them, and continuing*. A fresh session that re-derives any of the below will
duplicate a day of work.

**1. A position's protection now outlives the session that opened it (`DR-037`).** The entry keeps
`time_in_force: day`; a separate `gtc` OCO goes on once the position is recorded. This exists
because `DR-036` measured every bracket leg dead at the first close — three holdings, no protection
at the venue, and a book still recording one.

Three things about it were wrong on the first armed evening and each was corrected by the venue or
by a measurement rather than by reading:

- **the payload carried no `type`** and came back `422 invalid order type`. The evidence that
  settled it was this system's own accepted entry, which sends `type` beside `order_class`;
- **the confirmation was our own write's echo.** An `oco` answers with its *parent* — `type: limit`,
  `stop_price: null` — and the stop is a nested leg, so re-checking against what we believed we had
  placed proved nothing. The run re-reads the venue now;
- **`status=open` does not return the stop at all.** A leg rests as `held`, and `held` is not
  `open`; `nested=true` is the only request shape that returns it. Measured three ways in
  `DR-037` §5.3.

**2. A protective SELL is not exposure (`DR-032` §3.1).** It was priced as committed risk and three
of them held more than the whole 4R cap, so the pass refused every candidate for as long as the
protection stood. `PlacedOrder` carries `side` now and the caps skip a sell.

**3. `TODO.md`'s blockers are not self-expiring, and three of them had expired.** *"The scheduled
pass never reconciles"* (built by `DR-035`), *"a fill is never recorded without a person"* (built by
`DR-031`, and `daily_run.cmd` runs `sync-fills` before the scan), and *"blocked on a missing symbol
directory"* (the directory is populated). All three were correct on their own dates. §6 carries the
general entry and the proposed convention: **a sentence saying something is blocked names the
command that would show it had changed**, which is §10.5's move aimed at a blocker instead of a
count.

**4. The coverage tier was specified and never scheduled — ~~and this is the one still open~~,
and it was REGISTERED on 2026-09-04.**
`refresh_universe.py` describes tiered work: a periodic pass widens coverage, the daily pass reads
what is stored. The daily tier was registered on 2026-08-12; **the periodic tier was never
registered at all**, and every evening's report has printed `PARTIAL UNIVERSE` over it. `CARD-001`
ranks relative strength across the admitted universe, so *strongest* meant strongest of whatever
had been fetched. Derive the current coverage rather than quoting one:

```bash
PYTHONPATH=$PWD/src python tools/verify_counts.py
```

`tools/widen_universe.cmd` is built and `docs/runbooks/README.md` §8 carries the one command that
registers it. ~~**Gate 26 names the task and is therefore RED until somebody runs that command**~~
— deliberately, because a tier nothing watches is how this went unnoticed for three weeks. A
catch-up pass was run by hand on 2026-09-04 so the subset is not left where it was while the
registration waits.

**IT IS REGISTERED, and gate 26 is GREEN — confirmed against the scheduler 2026-09-04.**
`SwingDesk coverage pass` is registered weekly, Sunday 11:00, `Ready`, next run 2026-09-06 — the
day and hour the runbook prescribes. Who ran the command is not established here and is not
asserted; the task exists and matches the runbook, and that is what a scheduler can be asked.

The gate reports it as named and adds *"has not run yet - this check says nothing about that
run"* rather than judging an exit code it does not have, which is `unavailable` ≠ `pass`
behaving correctly in a task's first week. Ask the machine rather than reading either sentence:

```bash
SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data PYTHONPATH=$PWD/src python tools/verify_schedule.py
```

~~What is left is an observation and not an action: nothing yet shows `widen_universe.cmd`
survives a real Sunday~~ — **it was run by hand on 2026-09-04 on the owner's instruction,
through the registered task rather than the wrapper, and returned `exit 0`** in ten minutes:
`fetched 3784, failed 216` of a 4,000 budget, the failures being the warrants, units and
rights that map to no vendor symbol. Gate 26 now judges a real exit code. §2's coverage row
is regenerated and owns the figure.

**5. Four gates and one policy were added or hardened.** Gate 20 refused a decision record whose
token appeared only in a comment or a docstring — one record was living on that. Gate 33 stopped
reporting phantom overlaps against a branch already merged under a different SHA. Gate 41 is new:
the price vendor's limits live in `registry/vendor_policy.yml` and the adapter reads them, which is
`DR-008`'s argument applied at last to the dependency this project asks the most of. The policy
**authors no number** — every value in it was already in force.

**6. `executemany` was DuckDB's slow path and it was in four places.** Profiling one bar write put
it at 97% of the time. The fix is one statement per chunk, in `platform/bulk.py`; the directory
pull went from tens of seconds to under one. The daily pass barely notices, and saying so is the
honest half: the cost is per NEW row, so it lands on backfills.

**What a fresh session should check first**, in this order:

```bash
PYTHONPATH=$PWD/src SWINGDESK_DATA=$PWD/data python tools/verify_submission_guards.py --data data
PYTHONPATH=$PWD/src SWINGDESK_DATA=$PWD/data python tools/check_gates.py
python tools/vendor_integrity.py
```

The first runs every guard the evening pass runs, against the live account, and sends nothing. The
third answers *has the vendor served an impossible bar before* as a tool call rather than as a
memory — it found hundreds on its first run, every one of them buried in a line nobody could see.

**AND WIDENING THE UNIVERSE MOVED SOMETHING ELSE, measured 2026-09-05 — read this before reasoning
about the sector cap.** The coverage catch-up tripled the admitted universe on 2026-09-04, and
`tools/refresh_classifications.py` is scheduled **nowhere**, so the classification store did not
widen with it. The share of candidates the sector cap admits **unchecked** went from about a tenth
to nearly two thirds in one evening — `DR-006` §3's fail-open now applies to the majority rather
than the margin, which inverts the cost side of a ruling the owner has not yet made. `TODO.md` §2
carries the funnel figures and the command that re-derives them; the report has been printing the
`UNAVAILABLE` line in the funnel every evening since.

**Standing, and not defects:** ~~gate 26 is red until the coverage task is registered (above)~~
— registered 2026-09-04 and the gate is green, see above — and gate 24 is red on any morning the
evening pass has moved `data/`, regenerate rather than investigate, which §8 of this file already
says.

### 5.0 What changed on 2026-09-01 and 2026-09-02, and what it left open

**Three things landed that a fresh session must not re-derive.**

**1. The paper venue is wired, read AND write, and it has been exercised against the live
endpoint.** `swingdesk broker` reads an Alpaca paper account and reconciles it against the book,
reporting disagreement in the course's own `TECH` code. `scan --submit` sends this run's `Trade`
decisions as brackets. `ADR-0005` places the package, `DR-026` reads `D1`'s *"order"* as one that
moves real money, `CHARTER` A-002 is the owner's ruling that a paper venue is outside it, `DR-027`
says what may be sent and lists four independent guards.

> **The paper/live boundary is a committed host allowlist and NOTHING ELSE, because nothing else
> exists.** A brokerage account object carries no field saying whether it is paper or live. Gate 39
> is what holds it. A-002 §3 says so in the charter, where anyone weakening the allowlist will see
> what they are weakening.

**Submission is stopped by default.** The kill switch is a file in `data/`, absent, and absent is
its value. Arming it is the owner's act. `DR-027` §9 records two defects a single real order found
that nothing else could: a bracket needs three legs, and the idempotency key must come from the
exchange calendar rather than a clock — at 19:57 New York the UTC date has already rolled, so the
18:30 pass and `DR-015`'s 19:30 retry would have submitted every entry twice.

**2. `CARD-001` selects.** See §3, which is where the consequence is argued.

**3. Gate 40, and it is worth reading before trusting any registry note.** Two `note:` keys on one
parameter means YAML keeps the last and drops the other **without a word**. It had happened twice,
and both dropped notes were load-bearing.

**What is open and is the owner's**, not a gap somebody should fill:

- **Arming the switch.** Nothing has been submitted by a run. The probe placed one deliberately
  unfillable order to prove the path; it was disarmed immediately.

  **Read `DR-027` §10 AND §11 before arming, and do not arm a checkout that carries neither.** On
  2026-09-02 an armed `--submit` would have sent **114 bracket orders, 103.5R, $153,040 of
  notional** against ratified caps of **4 positions and 4R** — and the venue would have accepted
  every one, because the paper account is ten times the size of the `account.equity` the risk model
  uses, so nothing bounces. `DR-027` §4's four guards are boundary guards and none of them counts;
  `pipeline` prices the book once and judges every candidate against that same empty book, so no
  candidate was ever compared with any other. `portfolio.allocate` now applies the three ratified
  caps across one run's own output, in `CARD-001`'s ranked order, and the same run submits **4**.
  **`data/` is shared by the main checkout and every worktree, so the switch is shared too** — an
  armed switch is only as safe as the code the checkout beside it is running.

  **§11 is the second half and it compounds.** The caps are measured against `positions.duckdb`,
  which only `open-position` and `respond` ever write — so an evening whose fills nobody recorded
  leaves the book reading empty and the caps take four MORE names, every night, for ever. The
  submission path now asks the venue what it already holds (positions **and** live orders) and
  stops with `TECH` — *pause new entries* — on anything the book does not carry. **So a fill that
  is not recorded stops the next run**, which is the guard working. §6 of `TODO.md` carries the
  migration that would make it automatic.
- **`DR-029` §5's three levers**, which is the research the owner asked for: a tighter stop (the
  strongest candidate and never measured — it halves R, so 2R becomes as reachable as 1R is now), a
  longer hold (already scheduled, bounded at ~40 sessions), and selection. **They do not belong together**: the first two are exit thresholds and belong to decision records, the third is an
  ordering and belongs to a pre-registration.
- **`DR-006` §3's admit-on-unavailable**, unchanged and still the deepest open item: a cap that
  fails open is not a cap, and `TODO.md` prices the migration.


**`docs/08-pm/plans/2026-08-11-evidence-foundation.md`** is that plan, and **its block is now
delivered**: gates 19 (secret hygiene), 20 (an accepted decision names what proves it happened) and
21 (uncommitted work, advisory) are all in the suite, `DR-008`'s collector runs on every scheduled
evening, and the first trade log this project has ever had is published at
`docs/prereg/results/PR-005-trades.csv` — 26,351 trades, with its provenance beside it.

Work deferred there with entry criteria rather than dates — EDGAR delisting backfill, the exit card,
the parked breadth card, vector memory, and nine smaller debts — is still deferred, and `TODO.md`
is where any of it becomes an open item.

**A five-advisor council reviewed the strategy question on 2026-08-11 and returned fewer cards than
it was asked for.** Its verdict: build **no** strategy card first. Persist the trade log, then fund
exactly one card — **exits** — because `PR-007` fixes the stop at 2.0 × ATR(14) with no trailing, so
exits have never been varied and cannot be the refuted entry family re-parameterised. **Breadth is
parked, not killed**: `PR-002`'s own survivorship bound puts it on its kill line at the observed
1.6–2.3% missing rate, and it is revivable only as a portfolio participation gate — never a
per-signal entry filter, which is closed by evidence (§7).

### What it carried — `claude/swingdesk-tasks-cl-perf-707e67`, merged 2026-08-24 as #49

**The daily run was breaching a ratified NFR budget by 4x and nothing measured it.**
`NFR.md` §3 budgets the **decision path at ≤ 5 minutes**; measured on 2026-08-24 before any
change it was **20.2 minutes** — 19.0 of pipeline compute plus 71.9 s of universe selection —
and it is **2.7 minutes** now. The breach was invisible because the same table's end-to-end
budget (≤ 45 min) was comfortably met at ~24 min, and nothing in this tree measured any of
those budgets — the run log gives a total and no split, and **the requirement lives in the
split**. `tools/measure_latency.py` measures the decision path now and reads its threshold
out of `NFR.md` rather than carrying a copy; the refresh and report-generation budgets are
still unmeasured and neither is close to binding. Three hot spots and a
quadratic: `completeness.check` was O(bars x sessions) over each instrument's whole stored extent,
`application/universe.py`'s selection read 3.57 million bars to answer a count, a last close and a
twenty-session average, `calendar.sessions` read a pandas frame with `iterrows` against a cache running at a 2%
hit rate, and `checklist` re-parsed its registry per candidate.

**Byte-identity is the reason to trust it, and it was measured five times**, most usefully by
`tools/verify_reproducible.py` reproducing `50e1646b933a4a9d` over the full 1,141-instrument
universe — the hash recorded on `master` before the change — and by `tools/run_pr005_replay.py`
reproducing all 20 of PR-005's cells through the backtest engine instead of the pipeline. So it
moves no decision output and spends no `a.run_completes` counter, and none of it touches a frozen
file.

*(The 20-cell reproduction is true of the store as it stood. Run the same command today and it
reports a mean-R drift in the ten holdout cells, caused by a vendor revision to one instrument
on 2026-08-27 that moved `high` and `low` and never touched `close`; `TODO.md` §6 carries the
measurement. It says nothing about the change this paragraph is about, which is why the sentence
stands and this note sits beside it.)*

**Two gates came with it**, 28 (a document may not state a parameter status the registry
contradicts) and 29 (a pre-registration id is reserved once, including across unmerged branches).
`TODO.md` §3 is empty for the first time.

**Two owner rulings landed on it late in the day and both are live work, not notes.**

**The AI may advise on an OPEN position** — `AI_AUTHORITY_MODEL.md` §3a, amended and ratified
2026-08-24. §3 is untouched; entry stays closed; the decision vocabulary, the MANAGEMENT vocabulary
(`HOLD`/`MOVE_STOP`/`PARTIAL_EXIT`/`EXIT_NOW`/`PAUSE`) and originating a number all stay forbidden.
Checked against the charter first: A-001 asks for "synthesis, not authority", advice is not
authority, and none of its six prohibitions is engaged — so this is not a charter amendment. **A-001's
standing condition is NOT discharged**: nothing may be implemented until the two vocabularies are
mechanically guarded, and they are still prose.

**`PR-013` measures the signal instead of the book** — registered, runner built, exploratory by
declaration. The owner's constraint is what drove it: four positions held twenty sessions is ~50
entries a year, the ratified sample floor is 100 closed trades, and the horizon is six months — so
**25 live trades**, and live evidence inside the horizon is arithmetically impossible without moving
a ratified value. The 2026-08-16 research suspension was overridden by the owner for this study and no
other, and `TODO.md` §2 records both the override and the fact that the suspension's own exit
condition can never be met.

**One thing on it needs the owner and is not an agent's to take:** PR-005's published trade log no
longer matches a fresh replay, because seven bars arrived three hours after it was published.
`TODO.md` §5 states the three options; `docs/prereg/results/` was not touched.

**The code graph was re-indexed once it merged** — `src/` and `tools/` both changed (`AGENTS.md`
§9 rule 3). It is named `swingdesk`, rooted at the main checkout, and now describes `master`.

### What `claude/inspiring-colden-2e8e16` carries — landed on `master` 2026-08-25 and 08-29

**Read this section first if you are a fresh session.** It is the whole of two working days.

**Six new gates (32-37), one extracted into a tool it can be tested through, and a run of
corrections.**
**None of it moves a decision output, sets a value, or touches a frozen file** — the one source edit
inside the freeze is a comment — so it spends no `a.run_completes` counter, and gate 9's determinism
replay confirms the output is unmoved.

**The finding to read first: a superseded threshold was the arithmetic under a wired risk cap for
thirteen days.** `DR-007` §3.7 proposed `validation.max_allowable_drawdown` = −15R; the owner set
20 percent of equity and the 2026-08-09 reconciliation superseded §3.7. The registry has never held
−15R — git settles it. But `DR-006` §1 anchors the book cap on a ratio against −15R, and §9 moved
that cap from 6R to 4R to restore the ratio; `ALLOCATION_SPEC.md` quoted it forward; `PR-009` is
*titled* after it. **The ratified 4R does not move and the error ran conservative** — 1R is exactly
1 percent of equity today, so the pause is 20R and the ratified anchor is 3.0 gap-sessions away
rather than the 2.2 recorded, against a design target of 2.5. `DR-006` §18 carries the working.

- **Gate 32 — a checklist item's stated blocker must still be blocking.** The eight `UNAVAILABLE`
  pre-trade items each carry a sentence saying what the system waits on, and re-reading them was a
  manual chore the trade-flow plan asks for by name. Each now declares the registry statuses its
  reason rests on. Written for `entry.maximum_entry_atr`: `DR-020` created it `unset`, `E08` and
  `E09` wait on it, and **neither sentence even named it**.
- **Gate 33 — a live branch is rewriting the lines you are rewriting.** Advisory. Gate 16 makes a
  sibling worktree visible; it does not say the sibling is editing your paragraph, and on this day
  two trees corrected the same two table rows two hours apart with gate 16 green.
- **Gate 34 — an enforcement the tree CLAIMS must be able to fail.** 15 mutants and 0 survivors
  **as it landed on 2026-08-25**; two more were added on 08-29 and the tool prints the current
  figure. Over `INVARIANTS.md` §1 and `REQ-VALIDATION-001`'s five live vetoes. It exists because the test
  `INVARIANTS.md` named for invariant 1 asserted `(net / x) * x == net` and could not fail; that
  test is rewritten and pinned to a value.
- **Gate 35 — a document naming a test must name one that exists.** `INVARIANTS.md` §1 and
  `REQUIREMENTS.md` §7 both argue enforcement by naming a test and a reader takes the name as proof.
  23 cited, 0 unresolved; renaming a test is ordinary work no other gate would notice.
- **Gate 7 moved out of `check_gates.py` into a tool**, because while it was an inline function it
  could not be pointed at a fixture — so it was the one gate of this repository's own making with no
  failure test, **and the audit that closed that class could not see it**: that audit's own
  derivation was *"grep `tests/` for each `tools/verify_*.py`"*. It now also enforces
  `REQ-DATA-001`'s *"no event date as a literal in executable code"*, a MUST whose status cell read
  "verified", once, by hand.
- **`REQUIREMENTS.md` §7** — each requirement paired with the test or gate that would go red, or the
  honest statement that nothing would. Six of nine have something; three have nothing, correctly.
  It is the artefact gate 10 has been waiting for, and the table says what gate 10 should *not*
  check.
- **The Canada row in §2**, and the `TODO.md` §6 item that was blocked on `DR-003` gap 1 and is
  not any more.
- **`PR-001` §10, `PR-002`'s report, `PR-009` §10 and `DR-006` §18** are corrected forward. No
  verdict, sample or number moves, and each says so in the file.
- **Nine fail-closed refusals had never been executed by the suite** — five of them in the frozen
  `trade_management/sizing.py`. All 45 refusal and decision sites in `src/` are now accounted for,
  and `tools/measure_refusal_coverage.py` is the command that says so. **No source changed**: they
  were missing tests, not missing guards.
- **`k.drawdown_pause` is one owner question, not three** (§0 finding 3 above), and `TODO.md` §4
  carries the pattern this session kept finding: **§10.5 gives every COUNT an owner and nothing does
  that for a STATUS** — twenty-odd stale ones across fifteen governed documents in a day, none of
  them wrong when written.
- **Gate 37 and the rule index, on owner instruction 2026-08-25** — *"AGENTS это твоя библия… раздели
  список правил и прозу"*. `AGENTS.md` now opens by saying it governs, and carries a one-line-per-rule
  index whose third column names the gate that catches you, or **honour** when nothing does. The
  measurement behind it: **about a dozen rules are honour-only**, including §1, §13, §14 and §5's
  *"say the name, not the code"*. Gate 37 keeps the index from drifting from the rules.
  **What paid for it:** this session read §5 and §13 — both owner instructions — and broke both for
  a whole day while building five gates that catch other things.

**The code graph describes `master`, not this branch** — `AGENTS.md` §9 rule 3 says to re-index
after a MERGE, and this is not merged, so that is correct rather than an oversight. It does not know
the six tools or the tests added here. Two of its answers were checked against the files this
session and **one was wrong**: `freshness.assess` reports zero fan-in and is called twice in
`pipeline.py` under an alias, while `transitive_loop_depth` is not populated at all — a query on it
looks clean because the property is absent. §9's *"a null result is evidence only once a positive
control shows the query works"* is not a formality.

**~~One thing to do at merge time~~ — DONE 2026-08-29, and the prediction was exact.** The merge
of `claude/swingdesk-open-tasks-2001c8` went red on gate 36 and on nothing else of its own making,
because that branch registers **22** (`verify_directory_policy.py`) and **31**
(`verify_commands.py`) in `check_gates.py` and added no rows to `CI_POLICY.md` §1, while neither
branch could add them alone — a row for a gate the other side registers fails gate 36 from the
other direction. **The gate working on its first real merge, not a defect in either branch.** Both
rows are written, from the two tools rather than from the runner's one-line labels.

**And the merge repaired something nobody predicted.** The sibling had taught `tools/build_state.py`
to emit the classification command with the flag it actually requires; this side's generated §2 row
still carried the form that exits 2. Regenerating §2 fixed it — so gate 31 arrived on the same
merge as a live instance of the defect it was built for, in the block whose whole promise is that a
reader can derive the number instead of trusting the row.

### The session of 2026-08-30: three claims tested, and every one of them was already false

**Read this if you are wondering what to test next.** The pattern is the session, not the findings:
every item below came from re-running a check somebody had already written down the answer to.

- **Three mutants recorded as surviving the suite were all dead**, and had been for up to twelve
  days. `TODO.md` §6 carried it `[v]` and it steered a build order; §1 of the same file had recorded
  the opposite six days earlier. Two of the three are now gate 34 mutants, so the kills stop being
  incidental. **The control is the transferable part**: the first attempt produced a false kill,
  because `src/` alone in a scratch tree makes `test_checklist.py` fail on a registry it resolves
  through the package, and that looks exactly like a dead mutant.
- **Gate 24 named the wrong cause on every CI run it has ever made.** `data/` exists in GitHub
  Actions and holds no store; the tool reported *"a store is open in another process — the scheduled
  run holds them"*, over a duckdb error reading *database does not exist*. Verdict right every time,
  reason wrong every time — `AGENTS.md` §10.6 rule 2 aimed at confidence rather than alarm. The two
  states are told apart from the filesystem now.
- **"The `E11` event calendar has no source" was three claims of different strength and only the
  weakest was true.** The code said *not wired* (true), `TODO.md` said *no source*, `REQUIREMENTS.md`
  said *does not exist*. `tools/probe_events.py` asks the source: Nasdaq serves the forward schedule
  with a session bucket, free and keyless. It settles the SOURCE and not the RULE —
  `screen.earnings_buffer_days` stays `unset`, and the literature recorded with it cuts against the
  obvious framing, because the earnings announcement premium is positive and peer-reviewed.
- **The degeneracy guard refuses five of the eleven sector ETFs, and its stated reason is false for
  them.** `tools/probe_sector_benchmarks.py`. `DR-006` §12.1 argued the guard is exact so a genuine
  sector ETF clears it; five report exactly one sector at exactly 100%. The behaviour is right —
  the candidate is admitted and the reason travels — and the sentence *"a fund holding no equity at
  all"* is not, for a fund holding 99.7% equity. A measured discriminator exists in the same vendor
  response. **Not changed: that is a `DR-006` amendment and the owner's.**
- **Gate 14 now reads `TODO.md`**, for the parameter statuses and component activation states only.
  The 2026-08-24 rejection of the whole pattern set stands and a test pins it; what reopened the
  narrow half is that the rejection bounded its cost on stale counts sitting in CLOSED items, and
  the instance was in an open one.

- **The layer contract made the backtest/live duplication MANDATORY, and both documents describing
  that risk were pointing at the wrong cause.** `REQUIREMENTS.md` §3 reads as a discipline problem -
  write the trigger once before the live path acquires one. But `validation` sits ABOVE
  `application` in the layered contract, so `pipeline.py` could not import the backtest's trigger at
  all: gate 6 refuses it. The live path's only legal options were a second implementation or a
  broken contract. `EntryTrigger` and its three implementations now live in
  `decision_logic/triggers.py`, below both, moved unchanged and confirmed by gate 9's replay.
  **It does not meet `REQ-VALIDATION-002`** - nothing asserts the two paths agree, because the live
  path still has no trigger to compare against.
- **Twelve decision records are `proposed`, and §5 said five were "the whole of what is blocked on a
  human".** Gate 20 prints the list on every run now, as a standing measurement rather than a
  failure. That is `TODO.md` §4's open question answered for one instance: §10.5 gives every COUNT an
  owner and nothing did that for a STATUS.
- **Gate 38** - a gate number cited in prose must be one the inventory knows. Row 12's shape, one
  layer out from gate 36. Measured first: 363 citations, 0 unresolved. It also settles what is left
  of gate 10, which is two checks rather than three, because §7's recommended narrow check turned
  out to be gate 35, built the same day §7 was.

- **One shape turned up three times, and it is worth holding in mind before the findings are.**
  Gate 24 said the scheduled run held the stores when no scheduled run existed. `DR-006` §8.7 says
  a refused sector ETF is *"a fund holding no equity at all"* when it holds 99.7% equity.
  `pipeline.py` computes `code_dirty` from the whole working tree while being named for the code.
  **In all three the verdict is defensible and the stated subject is wrong or wider than the name**
  — and a stated subject is a claim (§15 rule 1, §10.4). None of the three is findable by review;
  each came from measuring the sentence against the thing it describes.

- **A zero-byte file was hiding a fail-open in the reproducibility check, and it is the best thing
  found today.** `src/swingdesk/py.typed` did not exist, so mypy treated this project's own
  fully-typed package as UNTYPED the moment a tool imported it — every script in `tools/` got `Any`
  for every `swingdesk` symbol. **142 of 247 errors were that one fact**, and the count is the least
  of it: the checker was blind at the one boundary where a tool meets the system. Adding the marker
  raised `arg-type` from 7 to 16, and one of the nine was `verify_reproducible.py` comparing two
  `str | None` hashes declared `list[str]` — **two passes that produced NOTHING compare equal and
  print byte-identical output as evidence for `a.reproducible`.** Latent, not live, and written up
  as latent. Gate 5 now covers every `verify_*`, every `build_*`, `check_gates.py` and
  `track_a_streak.py`; the research runners stay out and `CI_POLICY.md` §7 names the command
  instead of the count that has drifted five times.
- **CI was one slow runner away from a red `master`.** A run was cancelled at 20m05s against
  `timeout-minutes: 20` while its twin on the same commit passed at 15m10s — inside **gate 34**, the
  mutation gate. Cumulative growth, not one change: the cap dates from a suite half this size.
  Raised to 35, and §7 names the next lever without taking it.
- **The nine argument errors, split rather than rounded off:** two real and fixed, five files
  checked and cleared as inference, **four named as NOT checked**. `TODO.md` §6 carries the split,
  because "they look like the cleared ones" is a prior and not a check.

**What none of it touched:** no parameter gained a value, no ratified record was amended, no frozen
file changed, and gate 9 confirms decision output is unmoved.

### Five questions waiting on the owner — restated 2026-08-29 with names, not codes

**`AGENTS.md` §5: say the name, not the code.** These five are the **sharpest** things blocked on a
human — each is one decision, each is already built or authored, and each unblocks something
downstream. ~~These five are the whole of what is blocked on a human~~ — **that was false when it
was written and measurably so, corrected 2026-08-30**: `docs/decisions/` holds twelve records still
`proposed`, and a curated five read as an enumeration. Derive the full list, never from here:

```bash
PYTHONPATH=$PWD/src python tools/verify_decisions.py
```

Gate 20 prints it on every run now, as a standing measurement rather than a failure — ratifying is
the owner's act and no gate has an opinion about when. **`AGENTS.md` §10.5 gives every measured
COUNT one owner and nothing did that for a STATUS** (`TODO.md` §4's open question); this is that
answer for this one, and the hand-typed list is what it replaces.

1. **The conditional second evening pass** (`DR-019`) — the 19:30 run fires every evening
   unconditionally; the record proposes firing it only when the first pass refused something a retry
   could fix. Built and running. **Ratify or reject.** *(And see the third live risk below: on a
   catch-up day it does not run at all.)*
2. **The nine watchlist states and the transitions between them** (`DR-020`) — the course names the
   states, nobody ever wrote the edges, and that is why `Trade` is unreachable in code. The record
   draws the graph and **decides no number**. **Ratify or reject.**
3. **The maximum entry distance** (`entry.maximum_entry_atr`) — how far past a fired trigger an entry
   may still be taken, in ATR units. Inside it a plan becomes `Trade`, beyond it `Late`. The unit is
   decided; **the value is not, and without it two pre-trade checklist items cannot answer.** A
   ruling with a reason, or permission to register a study.
4. **One word in the drawdown kill switch** (`k.drawdown_pause`) — it reads *"Realised drawdown"*.
   Closed trades only, or the drawdown that actually happened including open positions? The drawdown
   study uses the word in the second sense. **This is all that is left of what were three questions.**
5. **The published trade log of the base-strategy study** (`PR-005`) — 26,351 trades that no longer
   reproduce, because seven bars arrived three hours after publication. Leave it and date it,
   republish it, or publish the new one alongside. `TODO.md` §5 has the three.
### The session of 2026-08-25 (afternoon): a ratified record was half unimplemented

**`DR-008` was ratified 2026-08-10 and roughly half of it had never been built. Every clause reaches
code now**, and `TODO.md` §2 carries the audit clause by clause — see §5 for the full list of what
landed. One item in that audit turned out to be a misreading of the record rather than a gap: *"it
**may** retry one failed attempt"* is a ceiling, not an obligation, so retrying zero times is
compliant.

**Gate 20 exists BECAUSE of `DR-008` — its own docstring says so — and passed the whole time.** It
checks that a record NAMES an implementer, not that the implementer implements the record. That is
`AGENTS.md` §17 in one example and the sharpest one here.

**How it was found matters more than the finding.** Not by reading the record: by **gate 31**, new
this session, which checks that a command a document tells you to run accepts the arguments given.
`DR-008`'s emergency block named two flags argparse had never had — the only mechanically checkable
sentence in an otherwise prose record. The same gate caught `HANDOFF.md` §2's own **generated**
census naming a command that exits 2, which is the one promise §2 makes.

**The guard has a measured cost behind it:** 3 of 18 directory pulls were same-session duplicates,
each spending two requests and storing a ~13,000-row snapshot that was then stripped of its session
date. `DR-008` says zero requests. It fires today.

**Four already-REFUTED claims were still standing unqualified in live documents** and are corrected:
`RISK_REGISTER.md` D-3 and `UX_TASK_FLOWS.md` both still said Canada cannot be enumerated a day
after that was refuted; `UX_TASK_FLOWS.md` said no free point-in-time sector source is in hand,
false since 2026-08-23; and `REGIME_SPEC.md` carried the exact sentence `EVIDENCE_SUMMARY.md` §3
struck on 08-24. Both refutations were **re-verified from the source** before anything was edited.
The mechanism is one sentence: a correction lands in the document that owns the claim and the copies
elsewhere keep the refuted wording — §10.5's disease applied to claims instead of counts.

### What to pick up, ranked — 2026-08-25

**Everything below needs the owner except items 5 and 6.** The session that produced them
deliberately built no value into a threshold and took no decision that was the owner's.

1. **Ratify or reject `DR-019` and `DR-020`.** Both are `proposed` and both are already built or
   authored — the conditional second pass runs today, and the transition graph is what makes `Trade`
   reachable in principle. `DECISION_STATE_MACHINE.md` §6 stays open until `DR-020` is ratified,
   because a proposed record constrains nothing.
2. **`entry.maximum_entry_atr` and the trigger definitions need values.** A value is a study or a
   ruling, never a guess (`AGENTS.md` §8). `DR-020` §7 measured what the pivot parameters cost and
   **refuted the hypothesis it was built to test** — confirmation does not spend the entry budget,
   the drift is negative at every setting — so one argument that would have been made from a false
   premise is gone. No value moved.
3. **`k.drawdown_pause` needs a measurement, and the measurement needs ONE owner ruling — not
   three.** ~~Starting capital, mark-to-market versus realised-only, and per-account versus
   per-strategy are definitions, not implementation details.~~ **Narrowed 2026-08-25 by testing each
   rather than accepting the list.** Peak-relative comes from `GLOSSARY.md`, transcribed from the
   course; starting capital is `account.equity`, owner-set, with `DR-014` ruling paper-only;
   per-account versus per-strategy has no subject while the position store holds zero positions.
   **What is left is one question and it is sharp:** `k.drawdown_pause` says *"Realised drawdown"*,
   which reads as closed-trades-only — and `PR-009` uses *realised* throughout to mean the drawdown
   that actually occurred rather than a permuted one. The same word does different work in a
   ratified criterion and a registered study. `TODO.md` §1 states what becomes computable the day it
   is ruled, and why it is not urgent: the store is empty, so either reading reports 0.00% today.
4. **The `PR-005` trade log** — the published CSV no longer matches a fresh replay because seven
   bars arrived three hours after publication. Three options in `TODO.md`; `docs/prereg/results/`
   was deliberately not touched.
5. ~~**`SWINGDESK_EDGAR_CONTACT` is one line and unblocks a real measurement.**~~ **DONE
   2026-08-25, and it needed no owner action: the blocker was false.** `www.sec.gov` requires a
   `User-Agent` **and an `Accept` header** — the original comparison sent `Accept` to one host and
   not the other, attributed the difference to the host, and parked a measurement behind an owner
   action nobody needed. `python tools/classify_departures.py` classifies the 87 departures: **26
   confirmed delistings**, 11 structured symbols, 1 rename, 40 unresolved. The methodological
   finding outranks the count — the filer's TICKER LIST lags the vendor by more than the window
   (34 of 36) while the **Form 25 date does not**, landing on the same pull the symbol vanished at.
   `tools/probe_edgar.py` re-derives the host table on every run now instead of carrying it as
   prose. Setting the contact is still good citizenship and no longer blocks anything.
6. **The AI guard exists and is half of what A-001 requires.** `application/ai_guard.py` refuses
   both controlled vocabularies and any numeral the deterministic path did not produce, reading the
   vocabularies from their enums so they cannot drift. **It cannot see paraphrase**, two tests
   assert that hole, and `AI_AUTHORITY_MODEL.md` §11 stays open because of it. A-001's standing
   condition is **not** discharged.
7. **Everything owner-pending is in `TODO.md` §4**, and the impossibility audit's long tail is in
   §2 — four ranked claims are closed, the rest are a command away.

### The clock, and the freeze that protects it

`a.run_completes` counts **consecutive** trading days, and a silent failure resets it without
announcing itself:

```bash
schtasks /Query /TN "SwingDesk daily run" /FO LIST     # Last Result, Next Run Time
tail -40 data/daily_run.log                            # what it actually did
```

Exit 0 is a completed run. **Exit 2 is a refusal, which is a real outcome and not a failure.** A
crash is exit 3 or a missing log entry, and that is what resets the counter. `tools/preflight.py`
runs before the pipeline and exits 3 naming any missing dependency, so an environment fault costs a
log line at 18:30 instead of a day.

**The freeze that ran 2026-08-11 → 2026-08-17 is LIFTED.** Owner rule: nothing landed that changed
the daily-run code path until the counter had five clean days. It reached five on 2026-08-17, PR #9
merged that evening, and the counter reset by design. Recorded here rather than deleted because the
frozen-file list below is still live and still governs what resets the counter.

**Frozen files:** `tools/daily_run.cmd`, `application/pipeline.py`, `trade_management/sizing.py`.
Registries, documents, decision records and new `tools/` scripts are all safe.

**Amendment, 2026-08-16, council-reviewed (5 advisors + peer review, unanimous on both points):** a
merge to a frozen file that changes decision output resets the counter to zero, **effective the merge
date and not the next scheduled run** — which would just reopen the question every cycle. Cosmetic
changes (logging, comments) do not reset it.

**First trigger, and it exposed that the rule had no mechanism.** PR #9 merged 2026-08-17 (FX
refusal, cost-inclusive R denominator, one exit policy read from the registry, `output_hash` widened
to cover trade terms and open positions, a held position's vendor-ticker lookup). The 4 days banked
08-11→08-14 ran under a pipeline with five now-fixed correctness defects, and splicing them onto a
corrected system's streak would report confidence in a system that had existed for one day.

**It went on reporting 5/20 anyway.** The amendment lived only in this paragraph, so nothing applied
it. Implemented the same evening as `STREAK_RESTARTS` in `tools/track_a_streak.py`: a dated list with
a reason per row, sessions on or before the most recent restart outside the countable window. Adding
a row is now the only way to apply this rule. The counter reads `0` and prints why — a bare zero
after a deliberate reset is indistinguishable from an outage.

**Second trigger, 2026-08-18, and this time the mechanism was already there.** `DR-015` built: two
frozen files changed — `application/pipeline.py` (the freshness gate at both decision reads) and
`tools/daily_run.cmd` (the 19:30 second pass) — and the change moves decision output, which is what
the amendment turns on. Measured against the 2026-08-17 run: **67 of 1152 candidates were one
session behind and were sized and left on `Watch`; they now leave with a `DATA` skip.** A row was
added to `STREAK_RESTARTS` and the counter reports the reason with the number.

**Deliberately taken while the counter was at 0.** The reset cost nothing on 2026-08-18 and would
have cost two weeks in two weeks — the reasoning is `DR-015` §3's, not this session's, and it is
the whole argument for building the second pass now rather than later.

**Third trigger, 2026-08-22: `DR-006`'s book cap.** `application/pipeline.py` changed and the change
moves decision output — a candidate that would push the book past `risk.max_open_risk` (4R) or
`risk.max_concurrent_positions` (4) now leaves with a `Skip` / `RISK` where it reached `Watch`
before. `trade_management/sizing.py` changed cosmetically in the same commit: two private helpers
made public so the cap reuses the one FX rule and the one definition of 1R instead of copying
either. A row is in `STREAK_RESTARTS` with the reason. Taken while the counter read 0 again, for the
same reason as 08-18.

**The council's sharper finding about idle days — the premise is gone, the diagnostic remains.** It
warned that with `exit.atr_stop_multiple` / `exit.max_holding_period` unset post-merge, every
candidate would Skip and every position Pause, while `CLEAN_EXIT_CODES = (0, 2)` counted a coded
refusal as a clean run. **`DR-012` ratified both parameters on 2026-08-17, so that window never
opened** — verified on real bars the same day: candidates size and reach `Watch` rather than
refusing. The idle-day line in `tools/track_a_streak.py` stays, because the gap it measures is
permanent: a day on which every candidate refused identically and a day that evaluated something are
different facts, and the exit code alone cannot tell them apart. **It does not change what
`a.run_completes` measures**, which stays exactly its ratified text — the run completes and produces
a report.

### The schema repair held, and the outage is closed — measured 2026-08-24 after the run

**`exit 0`.** The 18:30 pass ran 18:30:00.82 → 18:49:59.38 — **19 min 59 s** — and completed. The
fault that killed every evening from 2026-08-18 was `positions.open_as_of` binding a column the
table on disk did not have; `positions.duckdb` carries it again and the run proves it in production.

**That outage is also what §2's `incomplete` runs are, and nothing said so** — checked 2026-08-25
against `journal.duckdb` rather than inferred. Every run with no `completed_at` started between
2026-08-18 18:30 and 2026-08-21 19:30, which is the outage window exactly. They are journalled
starts that never finished, they are immutable, and there is nothing to investigate. The same query
independently confirms the sleep finding two sections down: **2026-08-20 has a 19:30 run and no
18:30 run at all.**

**The 19:30 second pass then ran, 19:30:00.77 → 19:49:56.92, `exit 0`, and gate 26 is green.**
`tools/track_a_streak.py` reads **1/20** — it had read 0 straight after the 18:30 pass because it
does not count a session until its 18:30 ± 30 min window has closed, which is the tool declining to
answer early rather than a fault.

**Gate 26 called that healthy pass a crash while it was mid-run, and that is now fixed.** At 19:39
it reported *"last run 7:30:00 PM exited 267009"*. `267009` is `SCHED_S_TASK_RUNNING` — the Task
Scheduler puts its own STATUS in `Last Result` while a run is in flight, and the gate was reading
that column as an exit code unconditionally. `267011` (has not run yet) was already special-cased;
this is the same kind of value. A task with no completed run to judge is now reported and **not**
judged, and the summary line names how many tasks it could not judge instead of printing a bare
`PASS` over both.

**The two passes agreed exactly**, which is the first live observation of a property `DR-015` §3
only asserted: same `output_hash` (`0b104d2cb42e3100`), same `code_hash`, both `code_dirty` false,
an hour apart on the real universe. **The second pass rescued nothing** — `changed 0`, and the log
records no fetch failure for it to retry, so it did its job correctly and moved nothing. One evening
is not a verdict about whether it earns its twenty minutes; it is the first data point.

**87 of 1,141 admitted candidates left with `Skip`/`DATA`, one session behind** — last bar Friday
2026-08-21 against a last completed session of Monday 08-24, and neither refetch brought them
current. That is 7.6%, against `DR-015`'s own 2026-08-17 measurement of 67 of 1,152 (5.8%). Before
that gate existed every one of them would have been sized and left on `Watch` against a Friday
close.

**Twenty minutes is what `master` costs, and it breaches a ratified budget.** `NFR.md` §3 budgets
the decision path at ≤ 5 minutes; measured this morning `master` needs 20.2 (19.0 of compute plus
71.9 s of universe selection) before the vendor. This was the **first full pass since the store was
deepened to ten years** — the last one to complete was 2026-08-17 at 11m45s against a median of 510
bars rather than 2,512, and every evening between died in 45 seconds. The branch in §0 takes it to
about six minutes a pass; on `master` the margin to the 19:30 second pass is forty minutes and
shrinks as coverage grows, and both passes hold the same single-writer stores.

### The estimate that preceded it, kept because it was right

Both facts above were established **before** the pass ran, against a copy of the live store rather
than by waiting: `open_as_of` was shown to bind again, and `master`'s decision path was measured at
20.2 minutes. The run then took **19m59s** and exited 0. Recorded because the habit is the
transferable part — the alternative was to wait four hours and learn the same two things afterwards.

### Long jobs, and the one rule about them

Three jobs take longer than a session wants to wait, and **all three hold the bar store**, which is
single-writer (`ADR-0004`). A job still running at 18:30 or 19:30 takes that evening's pass down.

| | |
|---|---|
| `tools/refresh_universe.py`, ten-year deepening | **~2¼ hours** |
| `tools/run_pr012.py` | **13m37s** |
| `tools/verify_reproducible.py` | **11m40s** for both passes |

**Run them in the background and against a COPY where the tool allows it** — several take `--data`
for exactly this, and a copy of `bars.duckdb` takes under a second. Every long job this session ran
used a copy, which is why the 18:30 pass was never at risk from them.

### Three live risks

**The catch-up fires BOTH tasks at once, and the second pass dies — measured 2026-08-29.** Both
scheduled tasks report the same `last run 8/29/2026 6:50:57 PM`: `StartWhenAvailable` caught up the
missed triggers together, the 18:30 pass started, and the 19:30 pass exited **`-2147020576`** —
`0x80070420`, `ERROR_SERVICE_ALREADY_RUNNING`. ~~Gate 26 reports it and is red on this machine for
that reason~~; CI reports the gate `UNAVAILABLE` and cannot see it.

**Gate 26 is GREEN today, and that is not the risk going away — it is the gate reading a
different day.** Measured 2026-09-04: the 18:30 pass and the 19:30 pass each report their own
trigger and `exit 0`, an hour apart. The gate judges the LAST run, so it is red on a catch-up
morning and green on every ordinary one, which is why a green here is not evidence about the
risk. **The last measured collision is still 2026-08-29's** and what would settle this is a day
the machine misses its trigger, not another clean evening.

**If you are a fresh session and gate 26 is your first red, it now says this itself** — since
2026-08-30 the gate names `0x80070420` rather than printing the bare negative number, so the
failure explains itself at the point you meet it. Naming a cause is not fixing one, and the fix
below is a scheduling decision.

**Why it matters more than it looks.** The second pass exists to retry the instruments a data
failure dropped. A catch-up happens exactly on the days the machine was asleep or logged out — the
days most likely to have stale data — and those are precisely the days the retry does not run. The
two are not independent: the condition that creates the need also removes the remedy.

**Not fixed here, and it is a scheduling decision rather than a code one.** The options are a delay
or a start-boundary on the second task, or making it conditional on the first having finished, which
is `DR-019`'s subject. Recorded rather than acted on; `DR-019` is still `proposed`.

**And the run makes the NEXT run unreproducible — found the same evening.** `daily_run.cmd`'s last
step regenerates §2 and its own comment records the cost: *"this leaves `HANDOFF.md` modified and
uncommitted in the main checkout most evenings."* `code_dirty` is stamped while the pipeline runs,
**before** that regeneration, so each evening's flag records the previous evening's leftover. The
journal shows the chain starting 2026-08-25 19:30 ~~and unbroken since~~ — **it ran to 2026-08-27
19:30 and stopped there; every scheduled pass since 2026-08-31 is clean, measured 2026-09-04 from
`runs`, and why it stopped is conjecture (`AGENTS.md` §10.4) because the leftover is a property of
what the main checkout carries at 18:30 rather than of the code.** The comment weighs an advisory
gate-21 note against a red gate 24 and picks the note; **it does not mention that the leftover spends
`a.reproducible`**, one of the four Track A criteria, and those manifests are immutable. `TODO.md`
§6 carries it. `daily_run.cmd` is frozen, so the fix is the owner's.

**`Logon Mode: Interactive only`** — the task runs only while the user is logged on, and changing
that needs stored credentials. Whether `StartWhenAvailable` makes a logged-out 18:30 *late* rather
than *lost* is **still untested and still conjecture** (`AGENTS.md` §10.4) — a logout and a sleep
are different mechanisms. One evening settles it: log out before 18:30, log back in, and read
`Last Run Time` against the trigger time.

**The SLEEP case is no longer conjecture, and the answer is *lost*.** Measured 2026-08-24 from the
Windows event log, not argued: on **2026-08-20** the machine slept from 2026-08-19T20:01 local
through **2026-08-20T19:01 local** — straight over that day's 18:30 trigger — and
`data/daily_run.log` has **no 18:30 entry for 08-20 at all**, while the 19:30 pass ran normally at
19:30:01. The 18:30 task carries `<StartWhenAvailable>true</StartWhenAvailable>`, so it *should*
have run late on the 19:01 wake, and it did not. **A missed pass is not deferred, it is dropped —
and it leaves no trace anywhere except an absence.**

`tools/track_a_streak.py` already reads that absence correctly: its window is 18:30 ± 30 min, so a
day on which only the 19:30 pass ran is `None` — missing — and breaks the streak. Nothing needed
fixing there. What is worth knowing is the failure MODE: **`a.run_completes` can be reset by the
machine being asleep at 18:30**, and the log will say nothing rather than something wrong.
(Only one such day exists in the 08-10 → 08-21 window; every other wake landed before 18:30 local.)

~~**The directory pull still does not run, and it is the most time-sensitive item in the project.**
`DR-008` was ratified 2026-08-10 and its collector was never built — `tools/fetch_directory.py` has
none of the gating, calendar eligibility, response cap or audit the record specifies, and the
wrapper line is still commented out.~~

**Struck 2026-08-17: this was false, and it had been false for days.** Measured, not argued —
`tools/daily_run.cmd:59` calls `fetch_directory.py --scheduled` and is **not** commented out;
`directory.duckdb` holds a pull for every scheduled evening through 2026-08-14, the last one 13,144
rows with `source_session_date` confirmed against the response's own `Last-Modified`. The census in
§2 has been reporting 10 pulls / 2 confirmed the whole time, three paragraphs above a sentence saying
the collector does not exist.

Kept struck through rather than deleted, per §10.5's own convention: a paragraph that ranked itself
**the most time-sensitive item in the project** and was wrong is worth more visible than absent. It is
also the exact failure §2 exists to prevent, surviving in the one part of this file §2 does not
generate — hand-written prose next to a generated table that already contradicted it.

**What remains true:** 2026-08-10's departures are lost permanently, and 2026-08-11 was captured by
hand (six departures).

~~Whether every clause of `DR-008` (gating, calendar eligibility, response cap, audit) is implemented
has **not** been re-verified here — only that the collector runs and records. That check is open.~~

**CLOSED 2026-08-25, and the answer was that roughly half of it had never been built.** The audit is
in `TODO.md` §2, clause by clause against the code. Built the same day: the per-invocation audit
row, `--emergency-repull --reason`, the already-recorded-session guard, the append-only supersession
record, response checksums, exact header validation, gap recording with its `WARNING`/`ERROR`
severities, the committed network policy (`registry/directory_pull_policy.yml` + **gate 22**), the
process lock, and eligibility *after the latest session has completed* rather than merely on a
trading date. **Every clause now reaches code.**

**Gate 20 exists BECAUSE of `DR-008` — its own docstring says so — and passed the whole time**, because
it checks that a record NAMES an implementer, not that the implementer implements the record
(`AGENTS.md` §17). What finally found it was **gate 31**, from a completely different direction: the
record's emergency command named two argparse flags that had never existed, and a command block was
the one mechanically checkable sentence in an otherwise prose record.

**One measured cost, so the guard is not taken on faith:** 3 of the 18 stored pulls were same-session
duplicates — 2026-08-13 22:09 and the 19:30 second passes of 08-18 and 08-19 — each spending two
requests and storing a ~13,000-row snapshot that was then stripped of its session date. `DR-008` says
zero requests. **Coverage measured at the same time: zero gaps inside the attributed window** (8
sessions, 08-13 to 08-24), and coverage starts at the first ATTRIBUTED pull rather than the first
pull, so the 8 NYSE sessions between 08-03 and 08-13 stay uncountable — c3 forbids backfilling them.

## 6. Open — the owner's, not mine

**Moved to [`TODO.md`](TODO.md) §4 on 2026-08-15.** Open decisions, unratified records and pending
owner rulings live there with everything else that is open — one list, not five (`AGENTS.md` §10.7).

## 7. Closed by evidence — do not re-open

| | Why |
|---|---|
| Trend-definition family | PR-001 (definitions select different instruments) and PR-005 (those populations then behave the same) both refuted. `screen.trend_definition` stays `unset` |
| **The spread LEVEL from daily OHLC** | Three estimators — Corwin-Schultz 2012, Abdi-Ranaldo 2017, EDGE 2024 — cannot resolve it here. `PR-010` reports 25.65bp per side against its own 41.87bp zero-spread floor at this universe's measured volatility; Abdi-Ranaldo's 25.44bp sits under a 33.85bp floor. They agree to 0.21bp **inside their shared noise**, and neither declines with liquidity. `PR-006` — real fills — is the only route left. **A fourth estimator is the same family, and the reason is a mechanism rather than a tally** (audited 2026-08-25 under `AGENTS.md` §15 rule 3, which forbids a prediction standing as a closure): each floor is calibrated at THIS universe's measured volatility, so it is a property of the INPUT and not of the estimator's construction — any method inferring a spread from daily OHLC infers it from price variation, and here the variation from volatility swamps the variation from the spread. That is why both read LESS on the real universe than on a spreadless series. Concrete rather than hypothetical: `bidask` also ships Roll 1984 and the generalized OHL/OHLC/CHL/CHLO variants, and the mechanism covers them |
| Paid market data | Owner decision D10, taken with the survivorship cost known |
| Tuning the current parameters | PR-005 measured the strategy flat at assumed costs and negative under stress — both net |
| New entry filters | Same family, same evidence |
| ~~Spread estimation from free daily data~~ | **Removed 2026-08-09 — this row was wrong.** It rested on PR-008's withdrawn explanation. The sign test shows the estimators do detect a spread; see `POSTMORTEM-2026-08-09.md` §2. Kept struck through because a "closed by evidence" row that quietly disappears is worse than one that was wrong |
| Order placement with REAL money, multi-user | `CHARTER.md` §3 non-goals. **This row was "order placement, automation, multi-user" until 2026-09-01, and the amendment it named as the price was paid**: `CHARTER` A-002 scopes the human-only rule to real money, so the system may submit to a PAPER venue without per-order approval. On anything that can move the owner's money A-001 stands unweakened, and the two are kept apart by a committed host allowlist and gate 39 — nothing else can keep them apart, because a brokerage account object carries no paper/live field. Multi-user is untouched and is `ADR-0001`'s data licence, not a preference |
| An AI that decides, sizes, or ranks by desirability | `CHARTER.md` A-001 and `AI_AUTHORITY_MODEL.md` §3, ratified |

## 8. Traps, and the habits that catch them

**Moved to [`AGENTS.md`](AGENTS.md) §12 on 2026-08-15.** §10.7 makes that file the habit guide and
this one session memory; habits outlive a session, so they belong there.

## 9. Where things live

**See [`AGENTS.md`](AGENTS.md) §4.** This section was a second copy of it, under the same name, and
the two had already drifted apart on which directories exist.

## 10. History, condensed

Full history is `git log`. Two conclusions from it are load-bearing and are kept here because a
fresh session can act wrongly without them:

- **Do not rebuild the numbered tree.** A second effort once built ten numbered Russian documents at
  the repo root, having never opened `docs/`, `src/` or `registry/`. `docs/` is canonical (owner
  decision, 2026-08-04); that work is preserved verbatim in commit **`dee8f37`** and its new material
  is folded in. §8 of the specification forbids maintaining one logic in two places, and for a day
  this repo was doing exactly that.
- **The master specification is not in this repository**, which is why §3 and §53 of the gap analysis
  are blocked rather than written — see `ENTITY_MAP.md` §0 for what that cost.
