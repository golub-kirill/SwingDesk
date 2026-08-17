# Session handoff — 2026-08-17

**Read `HANDOFF.md` first, then `TODO.md`.** This file covers only what changed today and what the
next session must decide. Delete it once §1 is actioned.

Replaces `SESSION-HANDOFF-2026-08-16.md`, whose own §1 asked for exactly that once a decision record
existed for the exit parameters. It does now (`DR-012`), so the file went. Everything in it that
outlives a session was already in `TODO.md` (the PR-005 replay, §2) or `AGENTS.md` §12 (the
stash-and-watch-it-go-red habit).

---

## 1. The one decision that gates everything — now a document, awaiting a signature

**Ratify `DR-012`** (`docs/decisions/DR-012-exit-policy-parameters.md`, [PR #18](https://github.com/golub-kirill/SwingDesk/pull/18)):
`exit.atr_stop_multiple = 2.0`, `exit.max_holding_period = 20`.

Yesterday this was "a decision record is missing". Today the record exists, argues its own
provenance, and carries a measured before/after. **The values are deliberately NOT written into
`registry/parameters.yml`** — writing them is the ratification, and that is the owner's.

Three things in it a fresh session should not re-derive:

- **Provenance is `assumed:DR-012`, not `assumed:PR-005`** — yesterday's handoff suggested PR-005 and
  that would have been false. PR-005 held 2.0/20 as study *conditions*, never findings, and PR-005
  was **refuted**. §4 argues this at length so it cannot be re-litigated from memory.
- **The course quantifies nothing here.** Checked, not assumed — `EXIT_MODEL_SPEC.md` §4 audits all 92
  topics in M52–M58: *"Not one exit carries a parameter."* So no transcription outranks the decision.
- **§9 measures both halves** on a copy of the real store: unset → 3 Skips coded
  `RISK [exit.atr_stop_multiple]`; set → 3 Watches at `entry − 2.0 × ATR` with a cost-inclusive R
  denominator. The owner ratifies against a measurement.

**§8.6 asks the owner one further question:** `registry/parameters.yml` is not a frozen file, so on
the letter of the 2026-08-16 amendment ratifying does not reset the Track A counter — but it plainly
changes decision output, and PR #9 resets it already. The honest reading is **one transition, one
reset**. Confirm it, or the counter gets reset twice for a single change.

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

## 6. Owner decisions still waiting

Unchanged from yesterday except where noted:

- **`DR-012`** — §1 above. New today.
- **5b — proposal expiry.** `ActionStatus.EXPIRED` exists and is never written; a stop move computed
  on week-old bars stays answerable indefinitely. **Now the only unbuilt item in `TODO.md` §6b.**
  Needs a rule for how long a proposal stands before it can be built — and the mechanism should take
  the duration as an `unset` parameter that fails closed, not a constant.
- **DR-006** — six `risk.*` parameters; every portfolio cap cites `assumed:DR-006`. Must land on
  evaluated values, not a rubber stamp.
- **DR-011** — status `proposed`; the mechanism was the owner's choice, the record is unratified.
- **A TSX symbol directory** — `DR-003` gap 1. Blocks instrument identity and the Canadian half.

## 7. New in `AGENTS.md`

**§13 — how to talk to the owner**, on owner instruction: brief, direct, Russian, friendly profanity
aimed at situations and never at people. **Chat replies only.** §5 stands unchanged for every artifact
in the tree — documents, code, comments, commits, CLI output and reports stay English, and the rules
are kept in the owner's own words as the second marked exception to that rule, for the same reason the
first exists.
