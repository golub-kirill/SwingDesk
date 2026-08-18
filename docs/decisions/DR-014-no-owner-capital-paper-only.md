# DR-014: No owner capital in the observable state of this project — paper only, and Canada is deferred rather than blocked

```
date:            2026-08-17
status:          accepted — ruled by the owner 2026-08-17
parameters:      none directly. Changes the STANDING of six risk.* parameters (DR-006) and closes
                 PR-006's precondition; the CAD FX rate PR #9 introduces stays unset by decision, not omission
components:      none
supersedes:      nothing. Resolves the standing ambiguity every item below inherited
implementation:  none
why_none:        a scope ruling, not a code change. Consequences are carried by TODO.md section 4
                 and by section 3 below.
```

## 1. What was asked

The council's grilling put one question ahead of every other pending decision: **is the owner going to
trade this system with their own money?** Six open items — `DR-006`, `PR-006`, the paid-data decision
`D10`, the TSX directory, the CAD FX rate, and the whole "resume research" question — were each
being carried as independently open while all six actually hung on that one answer.

## 2. The ruling

> *"In current or observable for me state of project, I won't trade my money. I can imitate, we can use
> a paper trading, etc. But now I would not risk so much. This project goal — by many possible ways to
> find the edge. Research is a secondary, we just need a proof/evidence of our assuming."*
> — owner, 2026-08-17

Three separable decisions in that:

1. **No owner capital**, in the current or foreseeable state of the project.
2. **Paper / simulated positions are authorised** as the vehicle instead.
3. **The goal is finding an edge by whatever route works. Formal studies are secondary to having
   evidence for what the system already assumes.**

And the same day, on Canada:

> *"No, keep it closed for now, but not throw out forever. Once we will build a solid working trade
> strategy, we will try to do the same on Canadian market."*

## 3. What this decides that was previously open

| Item | Was | Is now |
|---|---|---|
| `DR-006` — six `risk.*` caps | "proposed — **binds a real account**", urgent, and `TODO.md` warned it must not be rubber-stamped | **Deferred, and no longer urgent.** There is no real account to bind. The warning stands for whenever it *is* ratified; the pressure to ratify it now is gone |
| `PR-006` — real fills | "the only route left" to the spread level | **Precondition withdrawn by decision.** It needs the owner to trade and report real fills. That is not happening, so the spread LEVEL is now a **permanent** known limitation, not a to-do |
| `D10` — paid market data | closed by owner decision, with the survivorship cost known | **Unchanged, and now consistent.** No capital at risk means the survivorship bound costs evidence, not money |
| TSX directory / Canada | "blocked", carried as a debt in several documents | **Deferred by owner decision, with a named re-entry condition** — see §4 |
| The CAD FX rate (introduced by PR #9, not yet on `master`) | `unset`, blocking every CAD instrument | **Stays unset deliberately.** Sizing refuses `.TO` instruments, which is now the intended behaviour rather than a gap |
| Resuming research | suspended by the 2026-08-16 council until one end-to-end cycle ran; it ran 2026-08-17 | **Reordered, not resumed.** See §5 |

**The single most valuable thing this ruling buys is the removal of a false urgency.** `DR-006` has
been described as the blocker on portfolio caps since 2026-08-02. It was never a blocker on anything
that could happen without capital.

## 4. Canada: deferred, not blocked, and the difference is not cosmetic

**Re-entry condition, in the owner's words: once a solid working trade strategy exists, try the same on
the Canadian market.**

`blocked` and `deferred` cost differently, which is the whole reason to write this down. A blocked item
appears in every audit, every handoff and every open-work list as debt somebody must eventually pay. A
deferred one with a stated condition costs nothing until the condition fires.

What stays true while it is deferred:

- `size_long` **refuses** any CAD instrument, naming the missing rate. Correct, already built,
  and now intentional.
- `DR-003` gap 1 (no TSX symbol directory) stays open but stops being ranked as time-sensitive.
- `AGENTS.md` §3's "USA and Canada are never merged" is untouched and still binding — deferring Canada
  is not permission to merge the two later out of convenience.
- The `risk.costs_bp_cad` / `risk.costs_floor_cad` parameters stay set. They cost nothing, and
  `DR-010` set them precisely so sizing would not silently merge currencies the day Canada opens.

## 5. Consequence for research, and it is not "resume"

The 2026-08-16 council suspended new pre-registrations until one end-to-end cycle ran. It ran on
2026-08-17. On the letter of that decision, research resumes.

**The owner's ruling reorders it instead:** *"Research is a secondary, we just need a proof/evidence of
our assuming."* Read against the same day's measurement, that is the correct order and not merely a
preference —

- `planned_risk`, the denominator every research output is expressed in, could be replaced with the
  constant `Decimal('42')` and the **entire** suite stayed green — count from `HANDOFF.md` §2,
  never restated here (`AGENTS.md` §10.5);
- a widened sample put the base rate of unasserted computed quantities at **3 of 11** mutants surviving
  the whole suite, with 2 of the 3 on the live sizing path.

A study run now emits numbers denominated in a quantity nothing verifies. So: **evidence for what is
already assumed comes before new assumptions.** That is a stronger statement of the same instinct the
council reached from the other direction.

## 6. What this does NOT decide

- **It is not a kill.** The owner said "not throw out forever" about Canada and "in current or
  observable state" about capital. Both are reversible, and this record is what a future session
  amends rather than re-deriving.
- **It does not make paper positions equivalent to real ones.** A paper fill has no slippage
  measurement in it. `record-fill` already refuses to manufacture slippage where the plan named no
  reference price, and a simulated fill price is a reference the reporter chose — the same defect
  `US-011` closed from the other side. **Anything built on paper positions must mark them as such in
  the store**, or the trade log becomes a mixture of measured and invented fills with nothing
  distinguishing them. That is the first design constraint on the paper-trading work, and it is not
  yet built.
- **It does not change `CHARTER.md`.** No orders, human-only decisions, and the non-goals are all
  untouched. Paper trading is a recording change, not an execution one.

## 7. What would overturn this

The owner deciding to fund the account. That is the only thing. It is a single sentence from them and
it re-opens `DR-006` as urgent, `PR-006` as reachable, and the paid-data question `D10` as a live
trade-off rather than a settled one.
