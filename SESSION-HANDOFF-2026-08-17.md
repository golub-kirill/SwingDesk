# Session handoff — 2026-08-17

**Read `HANDOFF.md` first, then `TODO.md`.** This file covers only what changed today and what the
next session must decide. Delete it once §1 is actioned.

Replaces `SESSION-HANDOFF-2026-08-16.md`, whose own §1 asked for exactly that once a decision record
existed for the exit parameters. It does now (`DR-012`), so the file went. Everything in it that
outlives a session was already in `TODO.md` (the PR-005 replay, §2) or `AGENTS.md` §12 (the
stash-and-watch-it-go-red habit).

---

## 1. RATIFIED — the gate is open

**`DR-012` was ratified by the owner on 2026-08-17** and the values are in the registry with
`assumed:DR-012`: `exit.atr_stop_multiple = 2.0`, `exit.max_holding_period = 20`.
([PR #18](https://github.com/golub-kirill/SwingDesk/pull/18))

Yesterday this was "a decision record is missing". It now exists, is `accepted`, argues its own
provenance, and carries a measured before/after.

Three things in it a fresh session should not re-derive:

- **Provenance is `assumed:DR-012`, not `assumed:PR-005`** — yesterday's handoff suggested PR-005 and
  that would have been false. PR-005 held 2.0/20 as study *conditions*, never findings, and PR-005
  was **refuted**. §4 argues this at length so it cannot be re-litigated from memory.
- **The course quantifies nothing here.** Checked, not assumed — `EXIT_MODEL_SPEC.md` §4 audits all 92
  topics in M52–M58: *"Not one exit carries a parameter."* So no transcription outranks the decision.
- **§9 measures both halves** on a copy of the real store: unset → 3 Skips coded
  `RISK [exit.atr_stop_multiple]`; set → 3 Watches at `entry − 2.0 × ATR` with a cost-inclusive R
  denominator. The owner ratifies against a measurement.

**§8.6 ruled: ONE reset, attached to PR #9's merge date.** And gate 20 then proved the argument
without being asked — it refused DR-012's claim to be implemented by `_exit_policy`, because that
function does not exist on `master`. Which is the same fact from the other side: **on `master` these
values are ratified and INERT**, since `pipeline.py` still carries the literal and never opens the
registry. The record now reads `implementation: none` with `arrives_with: PR #9`.

## 2. What is open

| PR | State |
|---|---|
| [#18](https://github.com/golub-kirill/SwingDesk/pull/18) | `DR-012` + `AGENTS.md` §13. **MERGEABLE, CI green, not frozen — mergeable now.** |
| [#9](https://github.com/golub-kirill/SwingDesk/pull/9) | **MERGEABLE and CI green** (was CONFLICTING). Still DRAFT and still behind the freeze. |
| [#19](https://github.com/golub-kirill/SwingDesk/pull/19) | `open-position`. **Stacked on #9's branch** — retarget to `master` after #9 merges. |

**Suggested order:** merge #18 → tonight's 18:30 run makes streak 5 and lifts the freeze → ratify
DR-012 → merge #9 (counter resets, deliberately, once) → retarget and merge #19.

**Freeze status:** Track A was **4/20** at the start of today, last clean 2026-08-14. Do not trust
that number from here — `python tools/track_a_streak.py` from the **main** checkout is the only owner.

## 3. What was built

**PR #9 was CONFLICTING and is not any more**, and getting it there found two more defects. Only
`HANDOFF.md`'s *generated* block conflicted (resolved by running the generator, never by hand), but
the auto-merge left a semantic collision git could not see: #9 makes
`Position.initial_costs_per_share` required and master's newer `tests/test_cli.py` constructs
`Position` without it. Fixed by supplying the field, **not** by defaulting it.

Choosing the fixture value found the rest:

- **`size_long` sized against a zero or negative stop.** `stop >= entry` was the only stop check, so
  `size_long(1.00, 0.00)` returned **98 shares** against a risk-per-share larger than the entry
  price, and −5.00 was accepted too. `Position.initial_stop` is `gt=0`, so the run would size and
  propose a trade the store could never record. **Reachable:** the stop is `entry − multiple × atr`,
  so any instrument whose ATR exceeds half its price at 2.0 crosses zero, and `universe.min_price` of
  5.00 does not exclude those. Now a coded `STOP` refusal.
- **Nothing asserted that sizing and `Position` agree on the R denominator** — #9's whole subject.
  Both sides looked separately correct and the disagreement lived in the gap between two modules. The
  new property test asserts the *equality*, not either value, and **it found the stop defect on its
  first run**.
- **A fixture disagreed with DR-010 at its own entry price** — `0.25` called "DR-010's USD floor",
  but DR-010 charges `max(0.25, 50bp × entry)` and at that fixture's 100 entry the bp term (0.50)
  binds. The floor governs only below a 50 entry.

**Both extra fixes went into PR #9 rather than their own PR on purpose:** both touch `sizing.py`, and
the amendment resets the counter per *merge* to a frozen file. Two PRs would have cost two resets.

**`open-position` was unreachable after its merge, and that is the finding to remember.** Master's
#14/#15 pulled scan out of `main()` into `_scan()`; this branch was written against the older inline
`main()`, so the textual merge dropped the whole handler **inside `_scan()`, after that function's own
`return`**. ruff clean, mypy clean, 30 gates green, and every invocation fell through to `return 1`
printing nothing at all. **Six tests caught it; no gate would have**, and no review of a diff whose
only conflict markers were imports.

## 4. The chain closed — §1's condition for resuming research is met

`open-position` → `scan` → `pending` → `respond --approve` → `record-fill`, all five steps, on a
**copy** of the real bar store with DR-012's values set locally and reverted after. Live stores never
opened for write. `TODO.md` §6b carries the table.

`record-fill` is the row to read twice: it **refused to manufacture a slippage number** for a
maximum-holding-period exit, printed why, and recomputed open risk across the book instead of
decrementing it. The design held under a real run rather than a fixture.

**It is not a trade.** No owner capital, a store copy, a pinned clock. It is the chain proving it
closes, which is what the 2026-08-16 council asked for — nothing more.

## 5. A defect that stopped being theoretical

**The `LIVE_AS_OF` look-ahead has now been observed, and it changed a decision.** `TODO.md` §8 had it
as real in code and never fired.

Still **0** violations on the real store — re-measured, unchanged. But one
`scan --as-of 2026-08-14T21:00:00Z` against the copy produced **1** immediately: AAPL's `2026-08-17`
session written with `knowledge_time` `2026-08-14 16:00:00-05:00`, because `--as-of` pins the clock
and still fetches live while `store.write(refreshed.bars, started)` stamps the pinned instant. That
bar passed `as_of`'s `knowledge_time <= ?` filter, became `held.bars[-1]`, and the run justified its
exit with *"maximum holding period reached at 2026-08-17"* — from a run pinned three days earlier.

`pipeline.py` calls `store.as_of(...)` with **no `end`**, though the method accepts one and bounds
`event_time` with it. **One line closes it**, and the reproduction above is the test §8's own third
bullet records as missing. Not fixed today: `pipeline.py` is frozen and #19 is already stacked on the
only PR touching it. **This is the next code task after the freeze lifts.**

## 6. Owner decisions — four answered 2026-08-17, and one answer moved everything

**`DR-014` is the one to read.** The owner will **not trade this system with their own money** in its
current or observable state; paper / simulated positions are the authorised vehicle. Six items that
were each carried as independently open turned out to hang on that single answer:

| Was | Is now |
|---|---|
| `DR-006` — urgent, "binds a real account" | **Deferred.** There is no account to bind. Ranked a blocker since 2026-08-02; never blocked anything reachable without capital |
| `PR-006` — "the only route left" to the spread level | **Precondition withdrawn by choice.** The spread LEVEL is a permanent limitation now, not a to-do |
| `D10` paid data | Unchanged, and now consistent — no capital at risk means survivorship costs evidence, not money |
| Canada / TSX directory | **Deferred with a re-entry condition**, not blocked. Re-opens when a solid working strategy exists |
| The CAD FX rate | Stays unset **deliberately**. `size_long` refusing `.TO` is intended behaviour, not a gap |
| Resuming research | **Reordered, not resumed** — see §7 |

**`DR-013` — proposal expiry, ruled.** Non-critical (`MOVE_STOP`, `PARTIAL_EXIT`) expires after **3
trading days**; critical (`EXIT_NOW`) **never expires and never auto-applies**. `TODO.md` §6b item 5b
is unblocked and is now **the only unbuilt item in §6b**. `management.proposal_expiry_days = 3` is in
the registry; the code is not written.

**`AGENTS.md` §14 — force the answer.** Owner instruction: do not proceed on an assumption when a
decision is theirs, and do not accept a casual go-ahead as the answer to a specific proposal. `D6`
stops the *system* acting unasked; this stops an *agent* treating ambient approval as a specific one.

Still waiting: **`DR-011`** (proposed; mechanism was the owner's choice, record unratified),
**four ADRs**, **UDR-001/002/004**, **course v7.0 adoption**.

## 7. The test suite does not prove what it appears to — measured, then counciled

`planned_risk`, the R denominator the whole validation programme is expressed in, was replaced with
the constant `Decimal('42')`. **The entire suite stayed green**, including the test `INVARIANTS.md`
§1 names as enforcing that invariant — which asserts `(net/x)*x == net`, an identity that cannot fail
for any `x`.

**Base rate, measured 2026-08-17: 3 of 11 mutants survive the whole suite.** Two are in `sizing.py`
(`planned_risk`, `risk_per_share`). The third is `sessions_behind` in `calendar.py`, and it survived
for a **different reason** — the function has no caller anywhere in `src/`, while
`DATA_QUALITY_SPEC.md`:40 defines staleness through it. A spec rule implemented in dead code. Full
detail in `TODO.md` §6.

**A five-advisor council reviewed this and was unanimous on the form of the answer: do not write a
test-architecture ruleset.** This project already has a documentation surplus and a falsifiability
deficit; `INVARIANTS.md` was a careful audit that was *wrong about invariant #1* while claiming a
test enforced it. Its recommendation was two gates — a hand-authored mutant list over a declared
critical surface, and a `check:` line requiring every "closed by verification" block to carry a
runnable command.

**The owner's steer sharpens it: a stored list is regression, not detection.** It only re-checks
defects someone already thought of; `Decimal('42')` came from a human hypothesis no machine would
have scheduled. **So: seam properties first (detection), mutant list second (cheap insurance).** The
detector that actually worked this session was a cross-module property test asserting the *equality*
of two implementations rather than either value — it found the zero-stop sizing defect nobody had
hypothesised, on its first run.

Three non-negotiables if the list is built, from the council's peer review: a patch that fails to
apply is **FAIL** never skip (an exact-string mutant rots on the next rename, and a gate that mutated
nothing is `(net/x)*x == net` one layer up); it ships with one planted survivor proving it can go
red; output is named survivors with diffs, never a score.

**One trap, verified:** `git stash push -- src/` **cannot** census a committed suite. It reverts
*uncommitted* work, so on a clean tree it stashes nothing and the suite runs unchanged — which is
exactly why `AGENTS.md` §12's ritual has only ever applied to newly written tests. Auditing the
existing suite needs real mutants against committed source.

## 8. New in `AGENTS.md`

**§13 — how to talk to the owner**, on owner instruction: brief, direct, Russian, friendly profanity
aimed at situations and never at people. **Chat replies only.** §5 stands unchanged for every artifact
in the tree — documents, code, comments, commits, CLI output and reports stay English, and the rules
are kept in the owner's own words as the second marked exception to that rule, for the same reason the
first exists.

**§14 — force the answer**, on owner instruction: *"Do not process before my answer for action even if
I'm asking you to. Force me to answer."* When a decision is the owner's, do the parts that do not
depend on it, then ask — never pick a default and proceed. A critical proposal is answered by
`swingdesk respond POS-N SEQ --approve|--reject --reason "…"` and by nothing else, because that is
what puts the owner's reason and the moment they answered into the append-only response table.
A sentence in chat cannot do that.
