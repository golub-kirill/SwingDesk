# The trade flow: from a name on a screen to a closed position

**Status:** drafting · **Tier:** 8 (PM) · **Owner instruction, 2026-08-24**

> *"Нам нужен конкретный план. Это программа, которая должна полностью провести меня за руку от
> нахождения сделки до её закрытия, но не просто как учитель — это строгий исследовательский
> инструмент."*

This plan does not invent a strategy. It closes a gap that three separate artefacts describe from
three directions, and shows they are one gap.

---

## 1. The three views of one hole

**The course already specifies the flow.** `DECISION_STATE_MACHINE.md` §3, verbatim from
`M32-T0467-v5.0`, gives nine watchlist states:

```
Research · Developing · Watch · Ready · Triggered · Trade · Late · Invalid · Skip
```

**The transitions between them were never written.** That document's §6 has carried it as open
authored work since 2026-08-01: *"The nine states exist; the legal transitions do not."*

**And the code cannot reach `Trade`.** Measured 2026-08-24 across the live application layer: the
decision token `Skip` appears in seventeen places, `Watch` in one, and `Trade` in none. The journal
agrees — every decision ever recorded is `Watch` or `Skip`. The nightly report prints `Trade 0`
because no code can construct it, not because no candidate qualified.

*(`Pause` is absent from the candidate path CORRECTLY: §1 models it as account-wide, suppressing the
whole scan, not as a per-candidate state.)*

**These are the same hole.** The course defines `Watch` as *"контекст есть, но trigger, цена или
подтверждение ещё отсутствуют"*, and the pipeline's own terminal line reads *"sized; awaiting a
trigger"* — quoting the definition of the state it is stuck in.

## 2. What actually blocks it, measured rather than reasoned

Appendix E is the course's own pre-trade checklist, and it is already wired. On a healthy sized
candidate it returns **`Research`**, never `Ready`: five items pass, none fail, five are for the
human, and eight cannot be answered by machine.

`application/checklist.py` already records why each of the eight cannot be answered. Both reasons
this plan suspected of being stale were re-checked on 2026-08-24 and **both stand**: `DR-016` fetches
corporate actions for HELD names only, so a candidate has none; `DR-018` chose one benchmark, while
`E05` needs one per sector.

| Item | What it asks | Why it cannot answer | Already built? |
|---|---|---|---|
| `E03` | data fresh, corporate actions accounted for | actions are fetched for held names only | **half** — `DR-015` freshness yes, actions no |
| `E04` | market regime recorded | classifier exists, is not wired, `regime.breadth_cutoffs` unset | code yes, wiring no |
| `E05` | sector/industry and benchmark checked | needs a benchmark series **per sector**; no sector→index map | classification yes, mapping no |
| **`E08`** | **trigger measurable and not yet `Late`** | **there is no trigger and no maximum entry** | **no** |
| **`E09`** | **entry zone and maximum entry recorded** | **entry is recorded, maximum entry is not** | **no** |
| `E11` | earnings and events checked | no event calendar, and no buffer value to apply | no |
| `E12` | spread, dollar volume, expected slippage acceptable | volume yes; spread and slippage are not observable on free data | partial, and capped by evidence |
| `E14` | open risk, sector, currency, event exposure | risk/correlation/sector enforced; currency and event buckets are not | **mostly** — `DR-006` |

**`E08` and `E09` are different in kind from the other six.** The rest gate *quality* — they make a
trade better checked. These two gate *existence*: without a trigger and a maximum entry there is no
`Triggered`, no `Late`, and therefore no `Trade`. They are also exactly two of the nine states.

**Five of the eight are largely built and not connected.** That is the shape `AGENTS.md` §7 exists
to catch — specified, implemented, wired to nothing — appearing here one layer up, at the checklist.

## 3. The order of work, and why this order

**Stage 1 — author the transition graph.** For each of the nine states: what enters it, what leaves
it, and on which observable. Structure only, no thresholds. Recorded as a decision record and
written into `DECISION_STATE_MACHINE.md` §3, which §6 already instructs. This is allowed authored
work: a graph is a definition, not a threshold (`AGENTS.md` §8 governs the thresholds, not the
shape).

**Stage 2 — derive the observables from the graph, not from taste.** Every edge names what must be
computable to cross it. Intersect that list with the registry and the result is a **demand-driven**
activation list — which is what `HANDOFF.md` §4 requires: *name the strategy card that consumes it*.
Five components are implemented and sitting at `registered`/`specified` (pivots, moving average,
regime, breadth, trend); this stage decides which of them the flow actually needs, rather than
activating them because they exist.

**Stage 3 — the trigger and the maximum entry.** These carry numbers, so they are not free. The
course names breakout, pullback and contraction and quantifies none of them — `AGENTS.md` §8 lists
that among the four authored, load-bearing things. So `E08`/`E09` need a decision record with a
citation, or a pre-registration. **Not a guess, and not this plan's to pick.**

**Stage 4 — wire what is already built**, re-checking each `_unavailable` reason first, since two
were suspected stale and a third may be by the time this is worked. Then `Trade` becomes reachable.

~~and a reachability gate over every controlled vocabulary stops the class of defect rather than the
instance.~~ **Withdrawn 2026-08-25, having been measured.** The gate is not buildable without noise,
and `CI_POLICY.md` §3 records what happens to a noisy gate.

Two things kill it. **First, "reachable" is ambiguous and a naive check gets it backwards**: a
text search for `"Trade"` across the live layers finds `funnel.py`'s `by_decision.get("Trade", 0)`
and reports the token reachable — that is a READ of a decision, not a construction of one. The
sharper measurement, counting `DecisionRecord` constructions in `pipeline.py`, is what found the
gap, and it is specific to how decisions are made rather than generic over vocabularies.
**Second, most of `CODES.md` is not the pipeline's to emit at all.** Twenty of its twenty-four
tokens are absent from the live path, and they should be: `REVENGE`, `HINDSIGHT`, `PSYCH`, `CHASE`
and `AVG_DOWN` are journal codes describing a HUMAN's discipline, recorded by the person reviewing
their own trading. A gate flagging those would fire on correct design every run.

**What survives the idea** is much narrower and worth stating for whoever revisits it: the four
CANDIDATE decision states have exactly one construction site, `pipeline.py`, and three of them
should be constructible there (`Pause` is account-wide by the state machine's §1). That is a check
about one file, not a rule about vocabularies — and the gap it would find is already recorded, so it
would ship green and prove nothing until something regresses.

## 4. The sample constraint this must be designed against

**Entries per year = concurrent positions × 252 ÷ holding sessions.** At the ratified values, four
and twenty, that is roughly fifty a year. The ratified evidence floor is **100 closed trades**, and
six months is 126 sessions — so about twenty-five live trades against a floor of a hundred.

**Live evidence inside the owner's horizon is arithmetically impossible without moving a ratified
value.** Only two levers reach 100 in 126 sessions: holding five sessions instead of twenty, or
sixteen concurrent positions instead of four. `DR-006` set four on a measured argument — a gap exit
costs −1.692R, so a full book in a bad session loses about 10R.

**`PR-013` took the third route: measure the SIGNAL rather than the book.** Formation every five
sessions gives independent formation dates rather than trades, and it satisfied the sample rule
where `PR-012` could not. **What it then measured was empty** — every gross interval spans zero, in
both periods, across all three arms. The method for obtaining a sample works; the first pair of
lookback and horizon it was pointed at contains nothing.

**Consequence for this plan, and it is a constraint rather than a note.** The flow must be
expressible at *more than one* holding horizon, because the horizon is the open variable. A flow
that hard-codes twenty sessions bakes in the value that makes live evidence unreachable.

**This arithmetic existed only in conversation until 2026-08-24.** It is the reasoning the whole
evidence programme rests on and no artefact held it, which is why it is written here.

## 5. What this plan deliberately does not do

- **It does not add an asset class.** Gold is reachable inside the charter as a US-listed ETF and
  needs no amendment; crypto and physical commodities are `CHARTER.md` §3 non-goals. But neither
  addresses the actual problem: no signal has shown an edge, and a new asset class spends trials
  from `b.deflated_sharpe`'s budget without testing that. **Stay in the admitted universe.**
- **It does not assume the flow differs by instrument type.** The nine states are
  instrument-agnostic. Whether the *thresholds* on the edges differ between an ETF and a single name
  is a question a study answers. Build one graph; split it only when a measurement demands it.
- **It does not create edge.** A complete flow makes the system exercisable end to end and makes
  exits expressible — and exits are the one lever never varied, which is why the 2026-08-11 council
  funded exactly that card. The flow is machinery. `HANDOFF.md` §3 still governs what the evidence
  supports.

## 6. Stage 2 delivered: what the graph demands, measured against the registry

`DR-020` authored the graph, so its edges can now be intersected with what exists. Derived
2026-08-24 from `registry/components.yml` and `registry/parameters.yml` — every implemented
component, its activation, and what blocks it:

| Component | What | Activation | Blocked by | Demanded by the graph? |
|---|---|---|---|---|
| `M18-T0280` | ATR | **active** | — | yes — sizing, the stop, and `entry.maximum_entry_atr`'s unit |
| `M12-T0201/0202` | swing high / low | `specified` | `pivot.left`, `pivot.right` | **yes — the trigger breaks a prior swing high** |
| `M30-T0450` | regime | `registered` | `regime.breadth_cutoffs` | **yes — `E04` gates `Watch → Ready`** |
| `M31-T0459` | breadth | `specified` | `regime.pct_above_ma_period` | transitively, via regime's `BREADTH_MEDIAN` rule |
| `M25-T0382` | moving average | `specified` | **nothing** | **no** |
| `M31-T0464` | relative strength | `specified` | **nothing** | **no** |
| `M33-T0485` | trend | `registered` | `screen.trend_definition` (refuted family) | **no** |

**The result is the opposite of what availability suggests.** The two components that could activate
today — moving average and relative strength — are exactly the two nothing in the flow demands.
`HANDOFF.md` §4 already rules on that case: no card consumes it, so it stays `registered`, which
costs nothing. Activating them because they are ready would be supply-driven, and this plan is
demand-driven by construction.

**Trend stays out on evidence, not on convenience.** `PR-001` and `PR-005` both refuted the
trend-definition family, `screen.trend_definition` stays `unset`, and the graph needs no trend
filter to reach `Trade`.

**So the demanded set is two families, and both are blocked by `unset` parameters:**

1. **Pivots** — `pivot.left` and `pivot.right`. The course marks a pivot as *"зона или структура"*
   and never says how wide the neighbourhood is.
2. **Regime** — `regime.breadth_cutoffs`, and behind it `regime.pct_above_ma_period`. The course
   defines eleven regimes and names the inputs, and **no rule produces the label**;
   `regime.classifier_rule` is `assumed:PR-002`, whose verdict was corrected to `inconclusive`.

### `pivot.right` is a look-ahead lag, and that makes it the sharpest of the four

The registry states it plainly: a pivot is emitted at `P + right`, **never at `P`**. So `right` is
not a smoothing knob — it decides how late the structure a trigger breaks becomes known. Raising it
makes structure more reliable and later; lowering it makes the trigger earlier and the level less
certain.

**That trade-off is measurable on stored bars and nobody had measured it**, which made it the
cheapest real progress available on the flow: no vendor call, no new data, and no owner ruling to
*measure* — only to decide afterwards.

**MEASURED 2026-08-24, and the reasoning above was wrong where it mattered.** This paragraph argued
that confirmation spends the entry budget, so a small `entry.maximum_entry_atr` would leave the
trigger permanently `Late`. It does not: the drift is **negative** at every setting, because a swing
high is confirmed precisely by the following bars failing to exceed it. `DR-020` §7 carries the
table and what the measurement does and does not establish. Left standing rather than rewritten,
because a claim that read as a fact and was not is exactly what `AGENTS.md` §15 asks to be visible.

**Regime is the harder of the two and should not be rushed.** Its classifier rests on a study whose
verdict was withdrawn, so setting `regime.breadth_cutoffs` would put a number on top of an
inconclusive result. `AGENTS.md` §3: *nothing looks more validated than it is.*
