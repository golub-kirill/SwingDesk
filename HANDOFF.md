# HANDOFF — start here in a fresh session

Written 2026-08-04; **brought current 2026-08-24**. Read this, then `AGENTS.md` — especially §10,
rules that were each paid for, and §12, traps that each cost real time — then `docs/README.md`.

## 0. The first thing, and it is not code

**Everything is merged.** The 2026-08-24/25 session landed as a pull request onto `master`; the main
checkout is fast-forwarded and the code graph re-indexed against it (`AGENTS.md` §9 rule 3). Nothing
is held in a branch waiting for a decision.

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

**Three new rules and one new gate**, owner instructions of 2026-08-24: `AGENTS.md` **§15** an
impossibility is a claim, **§16** the course is a requirements source and not an evidence source,
**§17** verify at the right granularity. **Gate 30** makes a second rulebook impossible. The
`AGENTS.md` cut of the same day removed roughly a third of it with every heading byte-identical and
all its section references still resolving.

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
| Merge gates | **38**, one command: `python tools/check_gates.py` |
| Tests | **905**, fully offline |
| Docs | 122 files, Tier 0-8 · indexed by `registry/project_manifest.yml` |
| Components | 465 catalogued · 459 registered · 5 `specified` · **1 `active`** |
| Parameters | 106 - 61 `unset`, 34 `assumed`, 11 `owner`, **0 `validated`** |
| Golden vectors | 25 vectors across 6 components |
| Studies | 9 registered · 7 reported |
| Criteria | `registry/criteria.yml` **v1.1.1** |

<!-- END GENERATED: state:repo -->

### Derived from `data/` — main checkout only

<!-- BEGIN GENERATED: state:runtime -->

| | |
|---|---|
| Journal | 24 runs, 7 incomplete · **12 run(s) recorded against a dirty tree** and therefore not replayable from their SHA |
| Decisions | 13522 recorded · 0 uncoded refusals (`a.no_uncoded_failures` requires 0) |
| Bar store | 3,597,267 rows across 3,743 instruments |
| PIT integrity | **CLEAN** - bars whose `event_time` postdates their `knowledge_time`: 0 |
| Directory | **18 pulls** · **8 confirmed** against the response's own `Last-Modified` (`source_session_date`); the rest predate the field and stay permanently unattributed (`DR-008` c3) |
| Universe coverage | bars stored for 3,743 of 13,169 listed symbols - **28.4%** |
| Canada | **1 instrument** with bars, 252 bars over one fetch, last 2026-08-02 · **0** `.TO` symbol(s) listed in `directory.duckdb`. `BR-9`'s per-country requirement is unmet in every reported study. Since `DR-003` gap 1 was refuted (2026-08-25) a FORWARD result is blocked by this row rather than by a missing source; a HISTORICAL one also needs point-in-time membership, which the TMX endpoint cannot supply at any price |
| Classifications | 1,148 instrument(s) carry a sector · 1,046 (**91.1%**) report at least one non-zero weight. The stricter `look_through` count, which also drops a degenerate ETF look-through (`DR-006` §8.7), is lower - derive it with `python tools/measure_sector_cap.py --wide` |
| Track A clock | **1/20** consecutive clean sessions (2026-08-24 to 2026-08-24) · counting from a **deliberate restart on 2026-08-22**, not an outage - `python tools/track_a_streak.py` prints why · `a.run_completes`, computed by `tools/track_a_streak.py` |

*Measured from `data/` on 2026-08-25.*

<!-- END GENERATED: state:runtime -->

### Not derivable — hand-kept, each with its date

| | As of | |
|---|---|---|
| `master` | 2026-08-10 | **protected** — required check `gates`, admins included, no force-push. A new merge commit is refused until its check reports; fast-forward a green commit, or use a PR |
| CI | 2026-08-24 | `gates`, windows-latest. **Five** `UNAVAILABLE`, verified against run `32757431015`: gates 2 and 3 need the course PDFs, which are not in the repo; gates 23, 24 and **26** need `data/` or the scheduling machine. Everything else must be green. ~~Exactly **four** … verified against run `32093559374`~~ — that row was written 2026-08-17 and gate 26 landed on the 18th, so it asserted four for six days while CI reported five. Gates 28 and 29 were added after this run and both execute in CI; **29's cross-branch half cannot**, and prints that it did not run rather than passing for a check it never made |
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

- `claude/inspiring-colden-2e8e16`
- `claude/swingdesk-open-tasks-2001c8`
- `claude/state-block-from-the-run`
- `claude/swingdesk-tasks-cl-perf-707e67`

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
  free tier can never rule out;
- **there is no legal source of probability in this system today.** Any probability displayed would
  be manufactured.

**And a fifth, added 2026-08-24 because a session summary got it wrong out loud.** *"The first
strategy card exists"* is true and reads like *"a strategy runs"*, which is false in a way the
record settles: **every decision this system has ever taken is a `Watch` or a `Skip`. Not one is a
`Trade`.** No `Pause` either, no position ever opened, no fill, no management proposal. The tallies
move every evening and §2 owns them — derive the split with
`python tools/build_state.py`, and the per-verdict breakdown from `data/journal.duckdb` directly.
(This paragraph carried three counts for six hours until the 18:30 run moved all three, which is
the drift `AGENTS.md` §10.5 exists to stop and it happened inside the document that states the
rule.) `pipeline.py`'s terminal state for a candidate that passes every check is the
literal `"Watch"` with the reason *"sized; awaiting a trigger"* — and **there is no trigger in the
live path**, so `"Trade"` is in the decision vocabulary and is emitted by nothing in `src/`.
`REQUIREMENTS.md` `REQ-VALIDATION-002`, `ALLOCATION_SPEC.md` §7, `EXECUTION_MODEL.md` §7 and
`SYSTEM_MODES.md` §4 all say so; what was missing was saying it here, in the file a session reads
first.

**`CARD-001` is `Untested` and REFUSES**, which is the card doing its job: four selection inputs are
`unset`, the study that would have set them refused a verdict for want of sample, and all four of
its components are `registered`. A card is a list of what blocks a strategy, not a strategy.

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

### What `claude/inspiring-colden-2e8e16` carries — unmerged, 2026-08-25

Three gates and two corrections. **None of it moves a decision output, sets a value, or touches a
frozen file**, so it spends no `a.run_completes` counter.

- **Gate 32 — a checklist item's stated blocker must still be blocking.** The eight `UNAVAILABLE`
  pre-trade items each carry a sentence saying what the system waits on, and re-reading them was a
  manual chore the trade-flow plan asks for by name. Each now declares the registry statuses its
  reason rests on. Written for `entry.maximum_entry_atr`: `DR-020` created it `unset`, `E08` and
  `E09` wait on it, and **neither sentence even named it**.
- **Gate 33 — a live branch is rewriting the lines you are rewriting.** Advisory. Gate 16 makes a
  sibling worktree visible; it does not say the sibling is editing your paragraph, and on this day
  two trees corrected the same two table rows two hours apart with gate 16 green.
- **Gate 34 — an enforcement the tree CLAIMS must be able to fail.** 15 mutants, 20 s, 0 survivors,
  over `INVARIANTS.md` §1 and `REQ-VALIDATION-001`'s five live vetoes. It exists because the test
  `INVARIANTS.md` named for invariant 1 asserted `(net / x) * x == net` and could not fail; that
  test is rewritten and pinned to a value.
- **The Canada row in §2**, and the `TODO.md` §6 item that was blocked on `DR-003` gap 1 and is
  not any more.
- **`PR-001` §10 and `PR-002`'s report** are corrected forward for the refuted enumeration claim.
  No verdict, sample or number moves, and both say so in the file.

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
3. **`k.drawdown_pause` needs a measurement, and the measurement needs owner decisions.** Realised
   drawdown requires an account-equity concept the store does not hold: fills are recorded per
   position and nothing aggregates them. Starting capital, mark-to-market versus realised-only, and
   per-account versus per-strategy are definitions, not implementation details. `TODO.md` §1 states
   why inventing one to green a gate would be the wrong move.
4. **The `PR-005` trade log** — the published CSV no longer matches a fresh replay because seven
   bars arrived three hours after publication. Three options in `TODO.md`; `docs/prereg/results/`
   was deliberately not touched.
5. **`SWINGDESK_EDGAR_CONTACT` is one line and unblocks a real measurement.** `data.sec.gov` answers
   a descriptive `User-Agent` and `www.sec.gov` does not, so lookup by CIK works and lookup by
   TICKER needs the contact the SEC asks for. With it, the **87 symbols that left the directory in
   three weeks** can be classified into delistings and renames — which `DR-008` c3 records as
   currently indistinguishable, and which is the first empirical purchase anyone has had on the
   survivorship question.
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

### Two live risks

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
hand (six departures). Whether every clause of `DR-008` (gating, calendar eligibility, response cap,
audit) is implemented has **not** been re-verified here — only that the collector runs and records.
That check is open, and it is a different claim from the one struck above.

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
| Order placement, automation, multi-user | `CHARTER.md` §3 non-goals — reopening needs a charter amendment |
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
