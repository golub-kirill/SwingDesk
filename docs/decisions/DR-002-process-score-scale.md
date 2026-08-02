# DR-002: Process score scale

```
date:       2026-08-02
status:     proposed
parameters: stats.process_score_scale, stats.quality_grade_scale
components: none yet
```

`process score` appears in the journal `Review` record, in the checklist close-out
(`Error code и process score записаны`), in the weekly review's required evidence, and as one of the
five go-live conditions (`GO_LIVE_GATES.md` §4). M68-T1017 names a "standard scale" and defines none.

It blocks more gates than any other unset parameter in tier 5, and it is the one the course most
insists on: Appendix S gates size increases on **process**, not profit.

---

## Decision

Process score is a **deduction from 100, per trade, computed from recorded facts** — never entered
by hand.

```
score = 100 - Σ (severity weight of each error code recorded on the trade)
```

| Error severity (`CODES.md`) | Deduction |
|---|---|
| `Moderate` | 10 |
| `Moderate/Major` | 20 |
| `Major` | 35 |
| `Critical` | 100 |

Floor at 0. A single `Critical` therefore scores 0 regardless of everything else — the
non-compensatory rule (`FAIL_CLOSED_POLICY.md` §3) applied to self-assessment.

Two derived figures, both over a rolling window (`stats.rolling_window`):

- **process compliance** — mean score
- **clean rate** — fraction of trades scoring 100

`quality grade` (on the Setup, before the outcome is known) is a **separate 4-value ordinal** —
`A` / `B` / `C` / `D` — and is explicitly *not* the process score. Setup quality is a judgement about
the opportunity; process score is a measurement of execution. Collapsing them would let a good setup
excuse a sloppy execution, which is the exact substitution the course's error catalogue exists to
prevent.

## Why this one

**Deduction from 100, not addition toward it.** An additive score rewards doing the minimum and
stopping. A deduction scale makes the default state *correct* and every deviation visible, which
matches how the course frames it: the twelve error codes are the vocabulary, and a trade with no
errors is a clean trade.

**Computed, not self-reported.** The go-live gate reads "стабильный process score". A self-reported
number is a measure of the operator's mood after a losing trade, and it will drift with P&L — which
is the third prohibition in `VALIDATION_PROGRAM.md` §3, arriving through a side door. Deriving it
from error codes already in the journal makes it a fact about the record rather than an opinion
about the trade.

**Critical = 0, not −100.** A floor at zero keeps the scale readable; the point of a critical
violation is that it cannot be averaged away, and zeroing that trade achieves it without letting one
disaster make a whole month arithmetically unrecoverable in a way that hides subsequent behaviour.

**The weights are the weakest part of this, and are marked so.** The severities are the course's;
their numeric spacing is not. 10/20/35/100 is ordinal-preserving and otherwise arbitrary. What the
weights must not do is let three `Moderate` errors outweigh one `Major`, and this spacing satisfies
that.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| 1–5 stars, hand-entered | self-reported; drifts with P&L; not reproducible from the record |
| pass/fail per trade | loses the gradient the go-live gate needs ("stable", not "perfect") |
| weight by error frequency | circular — frequent errors would become cheap exactly as they became a problem |
| one score covering setup quality and execution | lets a good setup excuse poor execution; the course separates them and so does this |
| deduct by count only, ignoring severity | makes `Critical` and `Moderate` interchangeable, contradicting `CODES.md` |

## What would overturn this

- Evidence that the weights change any decision. If process compliance ranks the same trades in the
  same order under 10/20/35/100 and under any other ordinal-preserving spacing, the weights are
  cosmetic and should be documented as such rather than defended. **PR-004**, once there are enough
  journalled trades to rank.
- A measured correlation between process score and forward outcome strong enough that the score is
  acting as a performance predictor rather than a discipline measure. That would mean it is
  measuring the wrong thing, not that it is working.

## Consequences

1. Every error code recorded on a trade must carry its severity — already true (`CODES.md`
   transcribes all twelve with severity).
2. The score is recomputed from the journal, never stored as a number that could drift from its
   inputs. Storing it would make it correctable independently of the errors it came from, and the
   journal is append-only precisely so that cannot happen.
3. `GO_LIVE_GATES.md` §4's second condition becomes computable, taking that gate from one of five
   measurable to two of five.
4. `quality_grade_scale` gets an A–D ordinal here, which is a smaller decision riding along; if it
   needs its own reasoning later it gets its own DR and this one is superseded.
