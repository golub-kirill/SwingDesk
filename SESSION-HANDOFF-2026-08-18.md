# Session handoff — 2026-08-18

**Read `HANDOFF.md` first, then `TODO.md`.** This file covers only what changed today and what the
next session must decide. Delete it once §1 is actioned.

Replaces `SESSION-HANDOFF-2026-08-17.md`. Everything in that file which outlives a session is now in
`TODO.md`, `AGENTS.md` or a decision record; nothing was dropped.

**Nothing is in flight. No open PRs, `master` green on all 30 gates, working tree clean.**

---

## 1. The one thing to decide

**Build what `DR-015` ruled.** The record is accepted and its parameter is set; **none of it is
wired.** Three pieces, in this order:

1. **The retry wrapper** — three attempts, 30 seconds apart, around the *injected fetcher*. Not
   inside `pipeline.py`: `run()` takes the fetcher as an argument, so this needs no frozen file and
   keeps the pipeline pure (no sleeping in the decision path).
2. **The freshness check at the decision read** — `calendar.sessions_behind()` already computes it
   and `data.freshness_window = 2` is now set. `sessions_behind > 0` → refetch; still stale → `DATA`
   skip; ≥ 2 → drop the instrument from the run.
3. **The 19:30 second pass** — this one **touches `tools/daily_run.cmd`, a frozen file, and resets
   the Track A counter.** Do it now on purpose: the counter is at **0** after the 2026-08-17
   restart, so the reset costs nothing today and costs two weeks in two weeks.

`DR-015` §3 carries the reasoning for each; do not re-derive it.

## 2. What was decided today, and by whom

Four owner rulings, three of them recorded as decision records.

| | What |
|---|---|
| **`DR-013`** | Proposal expiry. Non-critical (`MOVE_STOP`, `PARTIAL_EXIT`) expires after **3 trading days**; critical (`EXIT_NOW`) **never expires and never auto-applies**. **Built and merged.** |
| **`DR-014`** | **No owner capital, paper trading only.** Canada deferred with a re-entry condition. One answer that six open items were all secretly hanging on. |
| **`DR-015`** | `data.freshness_window = 2` sessions; retry 3×30s then a 19:30 pass. **Ruled, not built** — §1. |
| **`AGENTS.md` §13/§14** | How to talk to the owner, and: do not proceed on an assumption when the decision is theirs. Force an explicit answer. |

**`DR-014` is the one a fresh session must read.** It removed a false urgency that had stood since
2026-08-02: `DR-006` "binds a real account", and there is no account to bind. `PR-006`'s precondition
is withdrawn **by choice**, so the spread level is now a permanent limitation rather than a to-do.

## 3. What was built

- **Proposal expiry** (`DR-013`) — `manage.is_expired()`, read-time only, sessions not calendar days.
  `EXPIRING_KINDS` is a whitelist: `EXIT_NOW` never expires, and `PAUSE` inherits the fail-closed
  side because `DR-013` did not classify it. `pending` **shows** expired proposals rather than
  dropping them; `respond` refuses **before** recording an answer, because the store's primary key
  means a recorded response cannot be taken back.
- **Gate 11 resolves `spec` by content** — see §4.
- **Gate 1 resolves `read_by`** — see §5.
- **Track A's reset rule stopped being prose.** `STREAK_RESTARTS` in `tools/track_a_streak.py`. The
  2026-08-16 amendment fired on 08-17 with nothing enforcing it, and the counter went on reporting
  5/20 while four of those days had run under the pipeline PR #9 corrected.

## 4. Gate 11 measured spec pointers by string length

**All seven implemented components pointed at a heading that does not exist.** The ladder defines
`specified` as "algorithm spec written", so all six `specified` rows stood in a state they had not
earned. It survived because `implements` was resolved for real — import the module, find the symbol
— and `spec` was checked for non-emptiness.

**The specifications were not missing.** Five of the seven carry the full eleven-field
`ALGORITHM_SPEC record` in their own module docstring. `ALGORITHM_SPEC.md` §7 had been asking
whether specs belong in that document or beside the code; the tree had answered long ago and nobody
wrote it down. **§7 item 1 is now closed: beside the code, under the marker.**

`regime` and `trend` carry no record and were demoted to `registered`. **Read the correction in
`TODO.md` §6 before repeating the reason I first gave:** that demotion was justified as "both serve
the entry-filter family closed by evidence", which is true of `trend` and **false of `regime`**.
`regime.classifier_rule` is set (`assumed:PR-002`), and breadth is *parked, not killed* — revivable
as a **portfolio participation gate**, never a per-signal filter.

**Neither is consumed by the live path today.** Zero references to `regime`, `trend` or `breadth` in
`pipeline.py` or `report.py`. Today's Watch/Skip carries no regime input at all.

## 5. The pattern behind three findings in one week, now countable

The exit policy, the staleness gate and the corporate-actions gate were all the same shape:
**specified, sometimes implemented, wired to nothing.** The registry could not see it — it recorded
where the course *mentions* a concept and where a value *came from*, and nothing about whether
anything consumed it.

**Measured: 23 parameters carried a value no line of code reads**, fourteen from `DR-007` alone.

`read_by` is now on all 102 parameters — `module:symbol`, or the explicit `none` — and gate 1
imports and looks it up. `none` is honest and is not a loophole; it is **counted and printed on
every gate run**, grouped by provenance. It caught `data.freshness_window` an hour after `DR-015`
set it, which is the intended behaviour.

Current standing measurement: **27 decided-not-wired** (the number rose by the four `DR-015`/`DR-013`
additions, and it should fall as §1 lands).

## 6. The biggest open risk, and it is not on any list yet

**Corporate actions.** Both the candidate path and the held-position path read `Series.RAW`. Raw bars
are unadjusted, so a split does not restate history — **the next bars arrive at a different price
level**. A 2:1 split over a weekend leaves a stored stop of 290 compared against Monday raw prices
near 145: an instant stop-out that never happened, on a position still held.

`DATA_QUALITY_SPEC.md` §4 specifies the gate in full, including the `DATA_ERR`/`Critical` case for a
changed raw bar. **Nothing is implemented** — no mention of splits or dividends anywhere in `src/` —
and `data.revision_epsilon` is `unset`. It needs its own decision record, same shape as `DR-015`.

**Stale data makes the system decide on old information, which `DR-015` now prevents. An unhandled
split makes it decide on *wrong* information while every freshness check passes.**

## 7. Two corrections a fresh session must not re-inherit

**The R denominator is no longer unasserted.** `TODO.md` said so all week and it was true until PR #9
merged. Re-measured on `master`: the `Decimal('42')` and `risk_per_share` mutants are **both killed**
by `test_sizing_and_position_agree_on_the_denominator`, the cross-module property test #9
introduced. **The base rate is 1 of 11, not 3.**

One attractive conclusion drops with it: *"a wrong R could be why the base strategy is negative"* has
no antecedent. R was never wrong, only unasserted. **The entry-filter family stays closed.**

**The sole surviving mutant is `calendar.sessions_behind`** — dead code, not a weak test. `DR-015`
is what unblocks wiring it.

## 8. State, measured — do not trust these from here

`HANDOFF.md` §2 is generated and owns every count. Run the commands rather than quoting this file.

- **Track A: 0/20**, counting from the deliberate restart on 2026-08-17. That is correct, not an
  outage — `tools/track_a_streak.py` prints the reason with the number.
- **Components 465: 460 registered · 4 specified · 1 active.** Only ATR is `active`.
- **Parameters 102, zero `validated`.** That has never changed and is the honest headline.
- The strategy is **negative at measured costs** across the whole admissible universe
  (`docs/08-pm/EVIDENCE_SUMMARY.md`). Nothing today touched that.

## 9. Habits this session paid for, now in `AGENTS.md`

- **§14 — force the answer.** Do not accept a casual go-ahead as the answer to a specific question.
- **Restore from a file copy, never `git checkout`, when the ritual's subject is uncommitted.**
  `git checkout -- file` reverts from the INDEX; a new function that was never staged is *deleted* by
  the "restore", and the next mutation then fails for entirely the wrong reason. Cost an hour, caught
  only by the full gate suite. `TODO.md` §6b carries it.
- **A positive control is not optional.** Several tests written today assert the *absence* of a
  behaviour and cannot go red against an unbuilt feature. Those were proven against **mutated**
  implementations instead, and the ones that genuinely cannot discriminate are labelled as controls.
