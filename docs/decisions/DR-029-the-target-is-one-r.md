# DR-029: The take-profit target is 1R, because it is the only one of the course's three the ratified hold can deliver

```
date:            2026-09-01
status:          accepted — ruled by the owner 2026-09-01: "1R is Ok, for sure, as a default"
evidence:        measurements/exit-surface-2026-09-06.json (section 7 - lever 1 measured and
                 refuted; no cell of the stop x target grid beats buy-and-hold)
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

## 7. Lever 1 measured and REFUTED — 2026-09-06

Appended, never edited above. §5 stands as what was believed and why.

Owner instruction: *"lets test and research"*. `python tools/measure_exit_surface.py --data <store>`,
evidence in `measurements/exit-surface-2026-09-06.json`. **EXPLORATORY; it sets no parameter.**

### 7.1 §5 called a tighter stop "the strongest candidate". It is the worst direction

**5,069 instruments, 123,635 non-overlapping entries, every admitted name every 20 sessions.**
Expectancy in R, **net** of `DR-005`'s 25 bps per side, at the ratified 1R target:

| stop | net expectancy | what the same slippage costs, in R |
|---|---|---|
| **0.5 × ATR** | **−0.776R** | 0.679R |
| 1.0 × ATR | −0.327R | 0.340R |
| 1.5 × ATR | −0.195R | 0.227R |
| **2.0 × ATR** (ratified) | **−0.128R** | 0.170R |
| 3.0 × ATR | **−0.057R** | 0.113R |

Monotone, and the intervals are ±0.004 to ±0.016 — this is not noise.

**§5's mechanism was right and its sign was wrong.** *"At `1.0 x ATR` one R halves, so 2R becomes
as reachable as 1R is now — at the cost of a higher stop-out rate."* True. What §5 could not see is
that **halving R also doubles what the same slippage costs in R**, because `DR-005` charges a
fraction of PRICE and R is a multiple of ATR. The cost column above doubles exactly as the multiple
halves. §3 of this record says of its own table **"Gross of costs"**, and that is precisely the
column in which the lever looked attractive.

**The direction that helps is the opposite of the lever**: widening to 3.0 × ATR more than halves
the loss.

### 7.2 And no cell of the grid beats doing nothing

The surface carries its own null — hold 20 sessions, no stop, no target, priced in the same
ratified R units:

| | null (buy and hold) | best cell in the 25 | ratified cell (2.0 / 1R) |
|---|---|---|---|
| gross | **+0.140R** | +0.084R | +0.042R |
| net | **−0.030R** | −0.036R | −0.128R |

**Not one of the twenty-five beats it, gross or net.** That is not an argument for removing the
stop — a stop is insurance and insurance costs money — but it prices the premium: **the ratified
exit policy gives up about 0.10R per trade** against simply holding.

It also fixes the floor. **Net of costs a random 20-session hold loses 0.030R**, so any strategy
must first earn that back before it earns anything.

**So expectancy cannot come from the exit.** It has to come from §5's lever 3, selection — which is
what the card is.

### 7.3 The confound, reported rather than assumed away

A wider stop produces more TIME exits, and over 2016–2026 a time exit collects the decade's drift.
The mix is published beside every cell for that reason: at 3.0 / 3R **69% of entries end on time**,
at 0.5 / 0.5R **none do**. The null exists to absorb exactly that, which is why every cell is marked
against buy-and-hold rather than against zero.

### 7.4 What this does NOT license

**A change to `exit.atr_stop_multiple`.** These are unselected entries; §5's own lever 3 says the
whole table moves once a card raises the hit rate. And the net column rests entirely on
`assumed:DR-005`'s 25 bps, which was measured from daily OHLC as *"materially more than 5"* rather
than observed. **The gross table is robust; the net table is only as good as that constant.**

What is established is narrower and harder: **the lever §5 nominated is measurably the wrong way
round**, and it was nominated from a table its own record labelled gross.

