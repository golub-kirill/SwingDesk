# DR-013: A non-critical proposal expires after 3 days; a critical one never expires and never proceeds unanswered

```
date:            2026-08-17
status:          accepted — ruled by the owner 2026-08-17
parameters:      management.proposal_expiry_days
components:      none — ActionStatus.EXPIRED already exists on the ManagementAction contract
supersedes:      nothing. TODO.md §6b item 5b, which was unbuildable without this rule
implementation:  none
still_to_build:  TODO.md section 6b item 5b. This record IS the rule that build was waiting on;
                 ActionStatus.EXPIRED exists on the contract and is still written by nothing.
```

## 1. The gap

`ActionStatus.EXPIRED` is defined on the contract and **has never been written by anything**. So a
`MOVE_STOP` computed on Monday's bars stays answerable indefinitely: an owner returning after a week
can approve a trail against week-old observations, and `manage.apply_approved()` will apply it,
because approval is checked and staleness is not.

`TODO.md` §6b item 5b has carried this since 2026-08-16 as unbuildable, for the right reason — the
duration is an owner rule, not an implementation detail, and inventing a number would have been one
more `assumed` parameter nobody could defend.

## 2. Decision

**Two classes, and the split is the substance of this record.**

| | Non-critical | Critical |
|---|---|---|
| Expires? | **Yes — after 3 days** | **Never** |
| May the system proceed unanswered? | No | **No, and it must keep asking** |
| Kinds | `MOVE_STOP`, `PARTIAL_EXIT` | `EXIT_NOW` |
| Surfaced how? | listed by `pending` | listed by `pending` **and** named in the run notice |

`HOLD` is out of scope entirely: it is not actionable and needs no answer, which the contract already
encodes (`is_actionable` is false for it).

**`management.proposal_expiry_days = 3`**, provenance `assumed:DR-013`. Trading days, counted the way
every other duration in this system is counted — a proposal made Friday is answerable Wednesday.

### 2.1 Why the classes split where they do

**A critical proposal is one where not acting leaves risk uncontrolled.** `EXIT_NOW` is proposed for
two reasons — a broken protective stop, or a completed maximum holding period — and in both the
position is being carried past the point the rules say it should end. Expiring that proposal would
convert the system's loudest possible statement into silence, and silence reads as "nothing to do".

**The non-critical kinds only ever reduce risk.** `MOVE_STOP` is refused outright if it widens
(`WIDE_STOP`, `Critical` in `CODES.md`, enforced at write time), so an approvable stop move always
raises the stop. `PARTIAL_EXIT` takes risk off. An unanswered one leaves the position exactly as the
owner last approved it, which is a safe resting state — and a stale one computed on 3-day-old bars is
worse than no proposal at all, because it looks current.

### 2.2 The part that binds the agent, not the code

**Owner instruction, verbatim in effect: do not process a critical action before the owner's answer,
even if the owner appears to authorise it in passing. Force an explicit answer.**

This is stronger than D6 ("a proposal is not permission") and it is aimed at a different actor. D6
stops the *system* from acting unasked. This stops an *agent* from treating a casual "go ahead" as the
answer to a specific proposal. A critical action is answered by `swingdesk respond POS-N SEQ
--approve|--reject --reason "…"` and by nothing else — which is also what puts the owner's reason and
the moment they answered into the append-only response table, as rule 3.8 requires.

Recorded in `AGENTS.md` §14 as a working rule, because it governs sessions and not only this feature.

## 3. Why 3 days

**Weakest part of this record, stated plainly rather than dressed up.** The number is a judgment about
how long an observation on daily bars stays actionable, made by the owner, with no measurement behind
it. It is `assumed:DR-013` and it should read as exactly that.

What can be said for it: the run re-evaluates every open position every scheduled evening, so a
3-day-old proposal has already been superseded by two fresher observations of the same position. The
number therefore sits comfortably inside the interval where a *newer* proposal exists anyway, which
is the property that matters — expiry should never be the first time a stale proposal becomes visible.

## 4. Alternatives rejected

- **Supersession instead of a clock** — a proposal expires when the next run re-evaluates the same
  position. Structurally cleaner, needs no parameter, and was the recommendation put to the owner.
  **Rejected by the owner in favour of the explicit 3 days.** Recorded because the argument is real
  and a future session should not think it was overlooked: supersession ties expiry to the scheduler,
  so a week of missed runs silently extends every proposal's life — the failure mode this record
  exists to close. A wall clock does not care whether the scheduler fired.
- **One rule for all kinds.** Rejected on the split in §2.1: the two classes fail in opposite
  directions. Expiring an `EXIT_NOW` hides live risk; keeping a `MOVE_STOP` alive presents stale
  arithmetic as current.
- **Auto-applying a critical action after N days** — the obvious "safety" feature and the worst
  option here. `CHARTER.md` A-001 makes the final trading decision human-only, and D1 forbids the
  system acting. A timer that exits a position is the system deciding, with a delay.
- **Expiring on calendar days rather than trading days.** Would make a Friday proposal expire over a
  weekend in which no bar existed and no risk changed. Every other duration in this system counts
  sessions (`AGENTS.md` §3: separate calendars, never merged).

## 5. What would overturn this

An owner who finds themselves repeatedly re-approving expired non-critical proposals — that is
evidence 3 days is too short for how they actually work. Conversely, approving a stop move whose
observation they then discover was stale is evidence it is too long. Both are observable from the
`fills` and response tables once enough proposals have been answered; neither is available today,
because the loop has answered exactly one proposal in its history.

Note what would **not** overturn it: an argument. This is a working-habits parameter and the owner is
the only measurement instrument for it.

## 6. Consequences

1. **`registry/parameters.yml`** gains `management.proposal_expiry_days = 3`, `assumed:DR-013`.
2. **`pending` must stop listing expired non-critical proposals** — and must say they expired rather
   than silently omitting them, or the owner cannot tell "nothing pending" from "something aged out".
3. **`respond` must refuse an expired proposal** with a coded refusal, not apply it late.
4. **Expiry is computed at read time, never written by a background job.** There is no daemon here and
   `ActionStatus.EXPIRED` must not become a row somebody has to remember to write. A proposal is
   expired if `as_of - proposed_at > 3 sessions` and no response exists — the same shape `pending`
   already uses, where pending is *the absence of a response* rather than a status column.
5. **The run notice names critical proposals.** `DR-011` §4 restricts the notice to a terminal status
   and the run id, enforced by `body()`'s two-parameter signature. **Extending it is a change to a
   ratified record's binding rule and needs its own amendment to `DR-011`** — it is not authorised
   here. Until then a critical proposal is surfaced by `pending`, and the owner's own answer to Q1
   (they are at the machine at 18:30) is what makes that sufficient.
6. **Nothing auto-applies, ever.** §2.2 and `CHARTER.md` A-001.
