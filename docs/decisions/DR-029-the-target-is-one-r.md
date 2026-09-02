# DR-029: The take-profit target is 1R, because it is the only one of the course's three the ratified hold can deliver

```
date:            2026-09-01
status:          accepted — ruled by the owner 2026-09-01: "1R is Ok, for sure, as a default"
parameters:      exit.target_r_multiple = 1.0, provenance `owner`
components:      none. broker.submit:target_price already reads it
implemented_by:  src/swingdesk/broker/submit.py :: def target_price
built:           2026-09-01
```

## 1. Why this is a decision record and not a pre-registration

`ALLOCATION_SPEC.md` §3 requires a **pre-registration** for an ordering adopted from the course,
because the course flags both of its ordering statements `Untested Hypothesis` and an ordering that
inherited that authority would be a hypothesis wearing a threshold's clothes.

**A target is not an ordering.** It is an exit threshold, the same family as
`exit.atr_stop_multiple` — which `DR-012` set at 2.0 by owner ruling, with no study, and correctly
so. The course names the form and three candidate values here (`M53-T0807`, `T0808`, `T0809`:
*exit at 1R*, *2R*, *3R*, all `Definition`), rules between none of them, and this project's standing
answer to that shape is a decision record carrying `assumed` or `owner`.

**What a decision record cannot do is make the value right**, and §5 says what would.

## 2. The decision

**`exit.target_r_multiple` = 1.0.** The take-profit leg sits one R above the entry, where R is the
position's own denominator — `entry - stop + costs`, frozen at entry (`RISK_SPEC.md` §2), so the
target is volatility-normalised by construction and comparable across instruments in a way
`exit.percentage_target` would not be.

Provenance `owner`, not `assumed:DR-029`. The owner ruled the value; this record carries the
reasoning and the measurement it rests on.

## 3. What the measurement said, and what it did not

Measured 2026-09-01 over the whole admitted universe — **1,505 instruments, 91,572 non-overlapping
20-session windows**, entry at the next session's open, stop 1R below, classified by **first touch**,
a bar containing both levels counted as a **stop** because that is how `manage.evaluate` resolves
the same ambiguity:

| target | hit | stopped | timed out | expectancy over resolved |
|---|---|---|---|---|
| 0.5R | 67.0% | 30.4% | 2.6% | +0.032R |
| **1.0R** | **46.8%** | **41.7%** | **11.4%** | **+0.057R** |
| 1.5R | 31.3% | 45.6% | 23.1% | +0.017R |
| 2.0R | 19.6% | 46.7% | 33.6% | −0.113R |
| 3.0R | 7.1% | 47.2% | 45.7% | −0.479R |

**3R is excluded by the data rather than by preference.** Nearly half its windows never resolve, so
the course's own third candidate and this project's ratified 20-session hold are simply
incompatible — a target that is reached 7% of the time is a target the exit policy is not really
using. 2R is already negative and unresolved a third of the time.

**And the half that must travel with those numbers.** Entries here carry **no selection at all** —
every 20th session on every admitted name — so a near-zero expectancy at every target is exactly
what an efficient market should produce, and it is not evidence of anything about a strategy. This
measurement answers *how far do these instruments travel in twenty sessions*, which is the input to
choosing a target. It does not answer whether an edge exists, and choosing a target by maximising
expectancy on unselected entries would be fitting noise. Gross of costs. Expectancy is over
resolved windows only, because a time exit is worth whatever the position was on session 20 and the
tool does not price it.

## 4. What 1R against a 1R stop actually means

**A reward-to-risk ratio of 1:1, which is worse than most practitioner convention recommends.**
That is stated plainly here rather than left for someone to notice, because it is the most obvious
objection and it has a real answer:

**the constraint is not the target, it is the pair of ratified numbers around it.** The stop is
`2.0 x ATR(14)`, so one R is about two ATR; the measurement says these names travel roughly three
ATR in twenty sessions. A 2R target therefore asks for six ATR, which the hold cannot deliver. The
reachable range is structurally about 1.5R, and 1R sits inside it with room.

So a wider target is not available by wanting one. It is available by moving the stop or the hold —
and both are ratified, and both are `DR-012`'s.

## 5. What would overturn this, and it is the research the owner asked for

Three levers, none of them the target itself, and each is a measurement nobody here has made:

1. **A tighter stop.** At `1.0 x ATR` one R halves, so 2R becomes as reachable as 1R is now — at the
   cost of a higher stop-out rate. That trade is measurable on the same store with the same tool and
   has never been run. **This is the strongest candidate for opening the range.**
2. **A longer hold.** The owner ruled 20 sessions on 2026-08-31 and scheduled a separate bounded
   study at about 40. The horizon measurement and this one now say the same thing from two
   directions: *twenty sessions is the binding constraint*, once as a null in the momentum studies
   and once as an unreachable target here.
3. **Selection.** Every number above is on unselected entries. A card that raises the hit rate moves
   the whole table, and only then does the choice between 1R and 1.5R mean anything.

**A study of the target alone would be the wrong study**, which is why this record sets the value
and defers the research to those three. `TODO.md` carries them.

## 6. Alternatives rejected

- **0.5R**, whose expectancy is comparable and which resolves 97% of the time. Rejected: it is not
  one of the course's three, it would need its own authorship, and a target inside the noise of a
  single session is an exit that fires on nothing in particular.
- **2R or 3R.** Rejected on §3 — the hold cannot deliver them, and a target the exit policy reaches
  7% of the time is decoration.
- **A percentage target** (`exit.percentage_target`, `M53-T0816`, also unset). Rejected: it is not
  volatility-normalised, so the same 5% is 0.5R on one name and 3R on another, and every R this
  system reports would mean something different per instrument.
- **Leaving it unset and running without a target.** Not available any more, and for two independent
  reasons: the owner ruled a target mandatory so that research data comes from a **completed** trade
  rather than one that timed out, and the venue refuses a bracket missing a leg (`DR-027` §9.1).
