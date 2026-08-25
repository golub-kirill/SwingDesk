# DR-020: The nine watchlist states get their transitions, and `Trade` becomes reachable in principle

```
date:            2026-08-24
status:          proposed — owner ratification required
parameters:      entry.maximum_entry_atr (NEW, unset) · screen.breakout_definition ·
                 screen.pullback_definition · screen.contraction_definition ·
                 watchlist.max_size · watchlist.eviction_rule (all already unset)
components:      none yet. Section 6 names what each edge would consume
supersedes:      nothing. Closes DECISION_STATE_MACHINE section 6 open item 1, open since 2026-08-01
implemented_by:  none — this record authors the GRAPH; no code changes with it
```

## 1. Why this record exists

`DECISION_STATE_MACHINE.md` §3 carries nine watchlist states verbatim from `M32-T0467-v5.0`:

```
Research · Developing · Watch · Ready · Triggered · Trade · Late · Invalid · Skip
```

and then states the gap plainly: *"The course states no transition rules between these nine.
Transitions are therefore authored, recorded in this document once designed, and any transition not
listed is rejected — the enum is closed but the graph is currently unspecified."*

**Nobody authored them, and the consequence is measurable.** Across the live application layer the
decision token `Skip` appears in seventeen places, `Watch` in one, and **`Trade` in none**. Every
decision ever recorded in `journal.duckdb` is `Watch` or `Skip`. The nightly report prints `Trade 0`
because no code can construct it.

**A graph is a definition, not a threshold**, so authoring it is allowed work (`AGENTS.md` §8
governs the numbers on the edges, not the shape). This record authors the shape and **decides no
number**.

## 2. The graph

`Pause` is deliberately absent: §1 of the state machine models it as account-wide — it suppresses
the whole scan and is not a per-candidate state.

```
                (admitted to the universe)
                            │
                            ▼
                       ┌──────────┐
                       │ Research │◀────────────── (a new cycle may begin here)
                       └────┬─────┘
                            │ a setup pattern is recognised
                            ▼
                     ┌────────────┐
                     │ Developing │
                     └─────┬──────┘
                           │ the setup completes and context holds
                           ▼
                       ┌───────┐
                       │ Watch │   ← every candidate sits here today
                       └───┬───┘
                           │ the pre-trade checklist returns Ready
                           ▼
                       ┌───────┐
                       │ Ready │   alert set; NO order (state machine §1, binding)
                       └───┬───┘
                           │ the trigger fires
                           ▼
                     ┌───────────┐
                     │ Triggered │
                     └─┬───────┬─┘
       within the entry│       │ beyond maximum entry
              zone     ▼       ▼
                  ┌───────┐ ┌──────┐
                  │ Trade │ │ Late │
                  └───────┘ └──────┘

  Invalid ◀── from Developing, Watch, Ready: the setup broke, or the plan expired
  Skip    ◀── from Research, Developing, Watch, Ready: a critical filter fired (CODES.md)
```

**Every transition, and what it needs**

| From | To | Condition | Needs |
|---|---|---|---|
| — | `Research` | admitted to the universe | `universe.*` (all set) |
| `Research` | `Developing` | a setup pattern is recognised | `screen.breakout_definition` / `pullback` / `contraction` |
| `Developing` | `Watch` | the setup completes and context holds | the same, plus the context checks |
| `Watch` | `Ready` | the pre-trade checklist returns `Ready` | the eight `E` items (`plans/2026-08-24-the-trade-flow.md` §2) |
| `Ready` | `Triggered` | the trigger condition is met | the trigger definition, evaluated on the new bar |
| `Triggered` | `Trade` | entry is available inside the entry zone | **`entry.maximum_entry_atr`** |
| `Triggered` | `Late` | price is beyond maximum entry | **`entry.maximum_entry_atr`** |
| `Developing`/`Watch`/`Ready` | `Invalid` | the setup broke, or the plan expired unfired | `watchlist.eviction_rule` |
| any pre-position state | `Skip` | a critical filter fired | `CODES.md`, already enforced |
| `Trade` | (leaves the watchlist) | position opened | `DR-012` manages it from here |

**Four properties this graph asserts, and they are the substance of it.**

1. **`Trade` is reachable ONLY through `Ready → Triggered → Trade`.** No edge skips the checklist.
   That is what makes Appendix E load-bearing rather than decorative, and it is why `Trade` being
   unreachable today is a *correct* consequence of an incomplete checklist rather than a separate
   defect.
2. **`Skip` is reachable from every pre-position state.** Fail-closed: a critical filter ends the
   cycle wherever it fires.
3. **`Late` is a state, not a skip code — and it is also both.** `CODES.md` has `LATE`; the state
   machine warns that the words overlap across enums and must live in separate columns. The state
   records *what happened to this plan*; the code records *why this candidate was refused*.
4. **The terminal states are terminal for the CYCLE, not the instrument.** `Late`, `Invalid` and
   `Skip` all return to `Research` on a new setup, which is what stops the watchlist becoming the
   *"бесконечный список тикеров"* `M32-T0467` warns against.

## 3. The one new parameter, and why only one

`entry.maximum_entry_atr` — how far past the trigger an entry may still be taken, in ATR units.
Below it, `Trade`; beyond it, `Late`.

**`unset`, and it must stay unset until a decision or a study supplies it.** Appendix E item `E09`
names the concept — *"Entry zone и maximum entry записаны"* — and the course quantifies nothing,
which is `AGENTS.md` §8's central fact rather than an oversight.

**ATR units rather than a percentage, and that choice IS made here.** A fixed percentage means
something different for an instrument with a 1% daily range than for one with 6%, so a percentage
would silently apply a different rule to every name. `DR-012` already expresses the stop in ATR for
the same reason, and expressing the entry ceiling in the same unit keeps the entry-to-stop distance
comparable across the universe. The UNIT is a definition; the VALUE is not, and only the unit is
decided here.

**Everything else the graph needs already exists in the registry as `unset`:**
`screen.breakout_definition`, `screen.pullback_definition`, `screen.contraction_definition`,
`watchlist.max_size`, `watchlist.eviction_rule`. No parameter is invented to fit the graph.

## 4. What the literature says, and what it does not

Searched 2026-08-24 under `AGENTS.md` §16, which requires this before a course rule becomes a design
constraint.

**Supports the SHAPE.** A published, precisely specified breakout system — the Donchian-channel
"Turtle" rules — defines exactly the three things this graph needs and this project lacks: a trigger
(price exceeding an N-session high), an entry, and a stop. Its stop is **2N where N is a 20-session
ATR**, which is within rounding of `DR-012`'s ratified 2.0 × ATR(14). That is independent
corroboration that a ratified value sits on a known convention rather than on nothing. It is
**rank 2** — practitioner rules with a documented history, not peer-reviewed.

**Does NOT support any particular maximum-entry distance.** No rank-1 evidence was found that a
specific distance past the trigger improves expectancy on daily equities. The closest study found is
a systematic falsification of intraday opening-range breakouts in MNQ futures, which reports pullback
entries failing badly — **a different market and a different horizon**, so under §16 rule 3 it is a
known limitation of a method, not evidence here.

**And the standing caution from §10.3 applies to all of it.** Sullivan, Timmermann & White (1999,
*Journal of Finance*) applied White's Reality Check to the full universe of rules a study draws from
and found the apparent performance of technical rules did not survive the correction out of sample.
This project already carries that lesson as `b.deflated_sharpe` and the trial budget. **Any trigger
adopted here spends trials, and this record spends none because it decides no value.**

## 5. Why this changes no code today

Nothing is implemented with this record, deliberately.

**The flow stalls exactly where the graph predicts it should.** `Watch → Ready` requires the
checklist to return `Ready`; the checklist cannot, because eight items are unanswerable — one of
them `E09`, which needs the very parameter §3 leaves `unset`. So every candidate sits at `Watch`,
which is what the journal shows and what the report prints.

**That is the graph earning its place before any code is written:** it explains the observed state
of the system from its own structure, rather than describing an aspiration.

## 6. Open, and each names who it belongs to

- **The trigger definition** (`screen.breakout_definition` and its siblings). A value needs a
  pre-registration, not a ruling — `AGENTS.md` §8 lists the breakout/pullback/contraction
  definitions among the four authored, load-bearing things.
- **`entry.maximum_entry_atr`'s value.** Same: no external evidence supports a number, so it is a
  study or an owner ruling recorded as `assumed` with its citation.
- **`watchlist.eviction_rule`** — what expires a `Ready` plan that never fires. The course names the
  concept (`M32-T0476`) and quantifies nothing.
- **Whether the thresholds differ by instrument type.** The nine states are instrument-agnostic and
  this graph does not split them. Whether an ETF and a single name need different edge values is a
  question for a study, not an assumption (`plans/2026-08-24-the-trade-flow.md` §5).

## 7. Measured 2026-08-24, and it refuted the hypothesis this record was built around

`tools/measure_pivots.py`, 400 instruments with at least 300 stored sessions,
`docs/decisions/measurements/pivots-2026-08-24.json`. Descriptive only: it evaluates no strategy,
compares no arms and reports no return, so it spends no trial.

| left | right | pivots / 252 sessions | confirmation drift, ATR (p50) | broke within 5 | within 20 |
|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 34.1 | −1.08 | 0.44 | 0.69 |
| 3 | 2 | 28.7 | −1.10 | 0.44 | 0.69 |
| 3 | 3 | 24.0 | −1.31 | 0.37 | 0.64 |
| 5 | 3 | 19.1 | −1.34 | 0.37 | 0.63 |
| 5 | 5 | 15.1 | −1.72 | 0.29 | 0.56 |
| 10 | 5 | 11.0 | −1.77 | 0.29 | 0.55 |
| 10 | 10 | 7.8 | −2.44 | 0.19 | 0.43 |

**THE HYPOTHESIS THIS WAS BUILT TO TEST WAS WRONG, and wrong by construction.** The plan reasoned
that confirmation would *spend the entry budget* — that by the time a level is knowable, price has
already run past it, so a small `entry.maximum_entry_atr` would leave the trigger permanently
`Late`. **The drift is negative at every setting.** At confirmation the close sits 1.1 to 2.4 ATR
**below** the level, and it must: a swing high is confirmed precisely because the following `right`
bars failed to exceed it. The two parameters do not compete for the same budget.

That is recorded rather than quietly dropped because the reasoning was stated as *"the sharpest of
the four"* before it was checked, which is the shape `AGENTS.md` §15 exists to catch — an assertion
about the world that reads as a fact.

**What the measurement does establish.**

- **Density is not the binding constraint.** Even the widest neighbourhood yields about eight
  confirmed highs per instrument-year, and the admitted universe is over a thousand names. There is
  no setting on this grid at which the flow starves for levels.
- **The real trade-off is level significance against how often it is tested.** Widening the
  neighbourhood roughly halves the number of levels and roughly halves how often they break —
  0.69 → 0.43 within twenty sessions. A wider pivot is a rarer, stronger level that is exceeded less.
- **The estimates are stable.** A 40-instrument run and a 400-instrument run agree to about 0.01 on
  every column, so sample SIZE is not what limits this. The alphabetical-prefix bias
  (`AGENTS.md` §12) is untouched by that and still stands.

**What it emphatically does NOT establish, and the number most likely to be misread.** *"Broke
within 20 sessions: 0.69"* is **not an edge and not a win rate.** It says only that price exceeded a
recent high at some point in the following month. It says nothing about what happened next, nothing
about the stop, and nothing about costs — and `HANDOFF.md` §3 records that the base strategy is
negative at measured costs. A trigger's firing rate and a trigger's profitability are different
quantities, and this measures the first.

**Consequence for the graph.** `entry.maximum_entry_atr` is not constrained from below by
confirmation drift, so it is free to be small. Which value it takes remains a study or a ruling, and
this section moves it no closer to either — it only removes an argument that would have been made
from a false premise.
