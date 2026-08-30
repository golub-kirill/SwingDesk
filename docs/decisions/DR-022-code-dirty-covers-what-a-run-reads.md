# DR-022: `code_dirty` asks whether the run's own inputs were uncommitted, not whether anything was

```
date:            2026-08-30
status:          accepted — ratified by the owner 2026-08-30
parameters:      none — a definition, not a threshold
components:      none — no decision component reads this field
supersedes:      nothing. It NARROWS a check that has never had a record of its own
implemented_by:  src/swingdesk/application/pipeline.py :: DECIDING_PATHS
built:           2026-08-30. It moves no decision output — §5 — so it does NOT reset Track A
```

## 1. What the field claims, and what it was measuring

`RunManifest.code_dirty` exists to answer one question: **can this run be reproduced from its
`code_hash`?** `is_reproducible` is `is_complete and not code_dirty`, and `a.reproducible` — one of
Track A's four exit criteria — is built on it.

It was computed as `git status --porcelain` over the **whole working tree**. `code_hash` is
`rev-parse --short HEAD` and says nothing about which files moved, so a modified `HANDOFF.md` marked
a run unreplayable by exactly the same mechanism a modified `sizing.py` does.

**The verdict was defensible and the subject was wider than the name.** A document the decision path
never opens cannot change what the run decided, and cannot stop the run being rebuilt from its SHA.

## 2. What it cost, measured

Of **31 journalled runs, 18 carry `code_dirty`**. Six are complete and clean.

The recent ones are not a person's uncommitted work. `tools/daily_run.cmd`'s last step regenerates
`HANDOFF.md` §2 — the wrapper's own comment says so — and `code_dirty` is stamped while the pipeline
runs, **before** that regeneration. So each evening's flag records the *previous* evening's leftover
paperwork:

| Date | Passes | Dirty |
|---|---|---|
| 2026-08-24 | 2 | 0 |
| 2026-08-25 | 2 | **1** — the 19:30 pass, the first to see the 18:30 leftover |
| 2026-08-26 | 2 | **2** |
| 2026-08-27 | 2 | **2** |
| 2026-08-29 | 1 | **1** |

Six consecutive scheduled passes spent `a.reproducible` on a modified `HANDOFF.md`. The wrapper's
comment weighed two costs — an advisory gate-21 note against gate 24 red every morning — and picked
the note. **It never mentioned the third**, because nobody had connected the regeneration to the
Track A criterion. `TODO.md` records the finding and the wrong first attribution that preceded it.

## 3. The decision

`code_dirty` is computed over **`src/`, `tools/`, `registry/`, `golden/`** and nothing else.

Those four are what a run reads: `src/` is the decision path, `tools/` the wrapper and the runners,
`registry/` every parameter and criterion, `golden/` the vectors components are checked against. A
dirty tree in any of them genuinely breaks replay. `docs/` and the root documents feed no run — and
the root documents are the only thing the wrapper dirties.

The list lives in one named constant, `pipeline.DECIDING_PATHS`, so it is a fact stated once rather
than an argument spread across a git invocation.

## 4. The 18 already-flagged runs keep their flag

They are immutable and this applies **forward only**. The journal is not rewritten, and no run's
`code_dirty` is re-derived.

**That leaves a discontinuity on the record and it is the honest cost of this change.** A future
reader comparing a run from 2026-08-26 against one from 2026-09-02 is comparing two different
questions, both called `code_dirty`. The alternative — recomputing the flag for past runs — would
require reconstructing each evening's working tree, which is not recoverable, and would edit a
record whose entire value is being immutable. `AGENTS.md` §11 rule 2 forbids it outright.

So the discontinuity stays, dated, and this record is where a reader finds out about it. The field's
own description in `contracts/run.py` names the date for the same reason.

## 5. Why this does NOT reset the Track A counter

`code_dirty` **is not in `output_hash`.** It is manifest identity, like `run_id` and `started_at`:
the decision path never reads it, no candidate's outcome depends on it, and narrowing it cannot
change what any run decides. Measured before the change rather than argued.

What it does change is whether a *future* clean evening is counted as reproducible — which is the
point, and which is not a decision output.

## 6. Alternatives rejected

**Commit the regenerated `HANDOFF.md` from the wrapper.** It makes the scheduled task a committer to
the repository, which is a much larger grant than the one being asked for, and it would have to
handle a conflicted or diverged main checkout at 18:36 with nobody watching.

**Move the regeneration out of the wrapper.** That returns gate 24 to red every morning with a
person needed to clear it — the exact defect the regeneration was added to remove, and the wrapper's
comment already weighed and rejected it.

**Leave it, and read `code_dirty` with a caveat.** A criterion that everybody knows to discount is
not a criterion. `a.reproducible` either means something or should be withdrawn.

**Drop `tools/` from the list.** Tempting, because the wrapper lives there and a wrapper edit does
not change a decision. Rejected: `tools/` also holds the study runners and `replay.py` itself, and
the whole point of this record is that the field should cover what a run reads rather than what is
convenient to exclude.

## 7. What would overturn this

A run reading something outside the four paths. `data/` is deliberately absent — it is not source,
it is the store the run is *supposed* to move, and `snapshot_id` is what pins it. If a decision ever
starts reading a checked-in file under `docs/`, that is either a defect or a fifth path, and this
record is the place to settle which.

## 8. Consequences

The daily run stops marking itself unreplayable over its own paperwork, so `a.reproducible` starts
measuring what its name says from 2026-08-30 forward. `TODO.md`'s open item is answered by this
record and closed against it.
