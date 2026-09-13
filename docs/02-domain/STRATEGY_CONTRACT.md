# STRATEGY CONTRACT

**What a combination of parameters must declare before it is allowed to be called a strategy.**

`STRATEGY_CARD_SPEC.md` says what a card LOOKS LIKE — a merged field list imported from Appendix I,
Module 71 and Production Rules §3.6. This document says what a card must be TRUE OF. The two are
complementary and neither substitutes for the other: a card can satisfy every field in the spec and
still be an assembly nobody has ever evaluated as an assembly, which is precisely the state
`CARD-001` is in.

**This document sets no parameter value and ratifies nothing.** Every clause below is a requirement
to DECLARE something, never a requirement to declare a particular number. `AGENTS.md` §8 sends
numbers to a pre-registration and §14 sends the rest to the owner, and nothing here is an exception.

---

## 0. The defect this exists to close

Every parameter in this system is ratified, or assumed, or unset **individually**. The registry has
an owner for each one. **Nobody owns the combination.**

`CARD-001` §4 states the position in its own words and does not flinch from it:

> *"Deliberately almost everything"* is inherited, and *"Only the selection rule is this card's own,
> and it is exactly the part that is `unset`."*

That arrangement is defensible if and only if the pieces are **separable** — if the value of a
selection rule is a property of the selection rule. **On 2026-09-08 `PR-018` measured that they are
not:**

| the SAME screen, on the SAME entries | worth |
|---|---|
| under the ratified exit (`PR-016`, out of sample) | **+0.088R** |
| under holding to the clock (`PR-018`, out of sample) | **+0.158R** |

The screen did not change. The exit decided how much of the screen's contribution survived to be
measured, because a stop truncates the right tail of a name that was going to run and names that run
are the whole of what the screen contributes. **The interaction is larger than the effect.**

So the object that can carry evidence is not a parameter and not a component. It is a **combination**,
and a combination that no document owns is a combination no verdict can attach to.

---

## 1. The ten clauses

Each clause states the demand, the measurement that forced it, and how it is checked. A clause with
no check is an intention, and this repository has a rule about those (`AGENTS.md` §16).

### C-1 — The mechanism comes before any number

A strategy states, in prose, **why the money is there**: whose behaviour creates the return, and why
it is not arbitraged away. One paragraph, before any parameter.

**Why.** `PREREG_TEMPLATE.md` §0 already refuses a study without one. A strategy is a standing bet
and deserves at least the same test as a single question. Without it, every later clause is
satisfiable by search: a combination that survives ten filters and explains nothing is what a trial
budget exists to price.

**Check.** Non-empty, and it may not be a restatement of the rules. *"We buy the strongest decile"*
describes the rule; *"we buy the strongest decile because slow institutional rebalancing supplies a
persistent bid we can front"* is a mechanism, and it is falsifiable.

### C-2 — The combination is the unit of evidence

A validation status attaches to the **whole tuple**: universe, admission rules, selection, entry
trigger, entry time, stop, target, holding period, sizing, portfolio caps, cost model. **No strategy
inherits a validation status from the validation of its parts**, and `LIFECYCLE_AND_LAYERS.md` §2's
separation of entry from management is the floor of this rule, not the ceiling.

**Why.** `PR-018`'s +0.088R against +0.158R. Also `PR-016`'s `ACCEPT`, whose §6 reads the paired
difference and never asks whether either arm is profitable — a true statement about a part that says
nothing about the whole.

**Check.** Gate 27 already refuses a card that claims more than it has. The version rule in C-10
makes the claim mechanical rather than editorial.

### C-3 — The null it must beat is a first-class field

A strategy names the **specific cheaper alternative** it claims to beat, and that alternative must be
the cheapest thing that could produce approximately the same trades. Two nulls are mandatory and a
strategy may add more:

- **the no-management null** — the same entries held to a fixed clock, no stop and no target
  (`PR-018`'s `hold_only`);
- **the no-selection null** — the same rules applied to every admitted name (`PR-016`'s control).

**Why.** The nulls are not decoration; each one has already changed a verdict here. The no-selection
null is what made `PR-016`'s `ACCEPT` readable as *"loses less"* rather than *"works"*. The
no-management null is what `PR-018` found the ratified exit losing to.

**Check.** Both nulls named by id, both measured in the same run as the strategy, on the same
entries wherever the construction permits it — and where it does not, **the card says so and says by
how much the entry sets differ**, which is the amendment `PR-018` §A-1 had to make and the reason its
minimum detectable effect was wrong.

### C-4 — The declared number is NET, with an interval, at a named cost model

A strategy declares **expected net R per trade** as a number with a confidence interval and the id of
the cost model that produced it. A gross figure may appear in the body; it may never be the headline
and it may never be the number a decision is taken on.

**Why.** The measured position: the ratified cell's gross is **+0.042R** against a round trip
costing about **0.17R** at `DR-005`'s 25.44 bps a side. **Costs are four times the edge.** A
programme that reports gross is reporting the smaller of the two numbers it is made of.

And a cost model is not a footnote: `PR-014` published an `ACCEPT` that its own cost error created,
and the error was a **monotone function of the axis the study varied** — 2.69× overcharge at twenty
sessions, 1.02× at a year. It taxed short holds and waved long ones through, and the decision rule
selected the shortest qualifying horizon. **A cost mistake aligned with the axis under study is
indistinguishable from a finding.**

**Check.** The cost model id resolves in the registry, and the interval is produced by the study, not
by the card.

### C-5 — Cost is an ADMISSION rule, not a subtraction

A strategy declares a **cost-in-R admission threshold** and refuses candidates below it at selection
time. The quantity is `round_trip_cost / (stop_multiple × ATR / price)` — the fraction of one R the
round trip consumes before the trade has an opinion about anything.

**Why.** Cost in R is not a property of the strategy; it is a property of **each candidate**. At
`DR-005`'s 25 bps a side and the ratified two-ATR stop, a name whose `ATR/price` is below 0.005 pays
**more than 1R** to open and close. Such a name cannot be profitable at any win rate the selection
rule could plausibly deliver, and no amount of signal repairs it. **Refusing those candidates is a
filter that beats every parameter this project has tuned**, and it is the one lever that is
arithmetic rather than a bet.

The threshold is **not set here.** It is the fraction of the risk budget the owner is willing to
spend on execution, it is registered in `TODO.md` §4 as theirs, and `tools/measure_gap_cost.py`
prints a floor table with the universe cost of each candidate value.

**Check.** The card names the threshold parameter id; the parameter is `owner` or `validated`, never
`assumed`, because an assumed value here silently admits the population that cannot work.

### C-6 — Execution time is a strategy field, and the gross belongs to it

A strategy declares **when in the session it transacts**, and the gross it declares must have been
measured at that time.

**Why.** Median per-side spread, measured across five years and a growing universe: **26.5 bps at the
09:30 open, 5.8 bps at 11:00, 4.0 bps at the close.** `CARD-001`'s entry method is *next session's
open* — the single most expensive moment of the day, at **6.6×** the close.

**And the limit is the whole of the clause.** A later entry is not the same trade at a better price:
it changes the gross as well as the cost. Subtracting a smaller cost from an unchanged gross is
exactly the error `DR-029` §5 made when it read a lever off a table labelled *"Gross of costs"*, and
`EVIDENCE_SUMMARY.md` §10 records that this project's published results *"are all computed at the top
of a curve nobody knew was a curve"*.

**What has been measured since, and why it still does not move a card.** `measure_execution_time`
answered `DR-040` §6 directly: paired over 6,176 entries, moving off the open changes the gross by
**−0.0010 [±0.0025]**, which contains zero, while the net difference, **+0.0031, excludes it** —
about 0.13R a trade of recovered cost, more than the ratified screen is worth. It is 60
instruments, unselected entries, and exploratory. The registered study on the live selection does
not exist; the store holds no intraday bars, and `probe_ambiguous_bar.py` established that the venue
serves minute bars from 2016-01-05 on `feed=sip`, so what blocks it is work, not data.

**Check.** Execution time is a declared field; the study that produced the net figure records the
same value; a card whose entry time differs from its evidence's entry time is a version change under
C-10.

### C-7 — The holding period is the strategy's OWN, and it is researched

**No strategy may inherit `exit.max_holding_period` as a global constant.** Each strategy registers
its own value, with its own provenance, from its own pre-registration, measured **inside its own
combination** — its selection, its stop, its execution time.

**Why, and this is the clause with the most arithmetic behind it.** The holding period is not one
parameter among several; it is the quantity that decides what the others can be.

1. **It fixes what target is reachable at all.** The registry's own note on
   `exit.target_r_multiple`: R is two ATR, and these names travel about three ATR in twenty sessions,
   so *"the reachable range is structurally about 1.5R"*. Measured over 1,505 instruments and 91,572
   non-overlapping windows, 3R resolves in 54% of them and 2R carries a negative expectancy. **Change
   the hold and every one of those numbers moves.** A target chosen against the wrong hold is a
   target that cannot fire.
2. **It fixes how many round trips the gross has to pay for.** Cost is per trade and roughly constant
   in bps; gross accumulates with time in the position. The ratio of the two IS the holding period,
   which is why `PR-014`'s corrected table shows net turnover falling from 39.0% per rebalance at
   twenty sessions to 8.2% at a year.
3. **It is where a cost error does the most damage.** `PR-014` again: the overcharge was 2.69× at
   twenty sessions and 1.02× at a year, and the verdict flipped on that gradient alone.
4. **It interacts with the stop, which is the thing that actually costs money.** `PR-018`:
   `ratified_no_target` (stop and clock, no target) reads −0.0261R and −0.0650R against the full
   policy's −0.0797R and −0.1144R, at a tail of 3.0% below −2R against 2.3%. **The target costs about
   0.05R and buys nothing on the tail; the stop costs the rest and buys all of it.** How long you are
   willing to hold decides how wide that stop can be, and a wide stop with a short clock is a
   different instrument from a wide stop with a long one.

**What the value inherits from today is not evidence.** `exit.max_holding_period` is 20 trading days,
status `assumed`, provenance `assumed:DR-012`. The registry note says the rest out loud: it was
*"held as a study condition by `PR-005`/`PR-007` rather than found by them, and unquantified by the
course."* **Twenty sessions is a constant wearing a parameter's clothes.** `PR-014` varied a
different quantity — the rebalance horizon of a book — and its verdict is `INCONCLUSIVE` and
`EXPLORATORY`; **no study in this repository has ever varied the per-trade hold on entries anyone
would trade.**

**Check.** The card's `exit.max_holding_period` reference must resolve to a parameter whose
provenance is this strategy's own study. A card citing `assumed:DR-012` for its hold is refused, and
the refusal is the point: it makes the missing research visible instead of letting a default stand in
for it.

### C-8 — The tail is a declared budget, printed beside the mean

A strategy declares, as fields, the **maximum adverse excursion** it is willing to accept: the share
of trades permitted below −2R, below −3R, and the worst single excursion it would tolerate before it
stops. Every report on the strategy prints those beside the mean, **in the same paragraph**.

**Why.** `PR-018`, both prices on the same trade:

| | mean, OOS | below −2R | below −3R | worst |
|---|---|---|---|---|
| the ratified exit | −0.1144R | 2.3% | 0.4% | −7.74R |
| holding to the clock | **+0.0404R** | **21.7%** | **7.9%** | **−23.81R** |

**The only positive combination this project has ever measured is the one with the tail that would
end it.** One trade in five below −2R is not a drawdown; it is a way to stop trading. A report that
gave the mean and put the tail three sections later would answer half the question in the voice of
having answered all of it.

**And the choice between those two columns is not a measurement.** It is a decision about ruin,
`CHARTER` A-001 says whose it is, and a strategy that does not carry the answer as a field has left
its most consequential parameter implicit.

**Check.** The fields exist and the study reports against them. A strategy whose measured tail
exceeds its declared budget is refuted by its own card, without argument.

### C-9 — The trial bill is carried on the card

A strategy declares the **cumulative trial count at the moment its evidence was produced** and the
deflated-Sharpe hurdle that count implies. Both are derived, never typed: `python tools/trial_budget.py`.

**Why.** This project has spent a three-figure number of trials on a universe of one strategy family.
A result read against a hurdle from fifty trials ago is a result read against the wrong hurdle, and
the count only goes up. `parameters:validated` is **0**, and every clause above is written on the
assumption that it will stay 0 until something clears the bar that is actually in force.

**Check.** Gate 28 refuses a document that states a parameter status the registry contradicts; the
trial figure is regenerated by the tool and compared.

### C-10 — Retirement is a predicate, and the version is computed

Two halves of one rule, because each is unenforceable alone.

**Retirement.** The conditions that would kill the strategy are written as **measurable predicates**
over quantities the daily run already produces — not prose, not *"if performance deteriorates"*. Each
predicate names its statistic, its window and its threshold.

**Version.** The strategy's version is **computed from its field values**, not chosen by an author.
Changing any field — including an inherited one, including a cost model, including the execution
time — produces a new version and **resets the validation status of the combination to `Untested`**.

**Why.** `STRATEGY_CARD_SPEC.md` §5 rule 2 already states this in prose: *"Editing a threshold after
seeing results creates a new rule version and resets any validation claim."* **Nothing enforced it,
and prose does not survive contact with a session that is trying to ship.** A computed version makes
the reset automatic and makes "we only changed one inherited number" impossible to say.

**Check.** A tool hashes the resolved field values and compares against the card's declared version.
The mechanism does not exist yet and is registered in §5 below as work, not as a claim.

---

## 2. What the contract adds to the card record

Every field below is **new relative to `STRATEGY_CARD_SPEC.md` §4's merged record.** The spec's
fields all remain required.

| field | clause | kind |
|---|---|---|
| `mechanism` | C-1 | prose, non-empty, not a restatement of the rules |
| `combination_version` | C-10 | computed from the resolved field values |
| `validation_status` | C-2 | of the COMBINATION, from the nine-value enum |
| `null.no_management` | C-3 | id of the held-to-clock arm |
| `null.no_selection` | C-3 | id of the every-admitted-name arm |
| `null.entry_overlap` | C-3 | how far the nulls' realised entries differ from the strategy's |
| `expected_net_r` | C-4 | number **with interval**, per trade |
| `cost_model` | C-4 | registry id |
| `admission.cost_in_r_max` | C-5 | parameter id, provenance `owner` or `validated` |
| `execution.time_of_session` | C-6 | and the evidence must share it |
| `exit.max_holding_period` | C-7 | **this strategy's own parameter**, never `assumed:DR-012` |
| `tail_budget.below_2r` · `below_3r` · `worst` | C-8 | declared before the study, not after |
| `trials_at_evidence` · `hurdle` | C-9 | derived by `tools/trial_budget.py` |
| `retire_when[]` | C-10 | predicates over daily-run statistics |

---

## 3. Where `CARD-001` stands against this contract

Stated plainly because a contract whose only example passes it is a contract that has not been
tested.

| clause | `CARD-001` | |
|---|---|---|
| C-1 mechanism | §1 gives one, and it is genuinely a mechanism | **holds** |
| C-2 combination is the unit | §4 inherits almost everything and the card evaluates none of it as a whole | **fails** |
| C-3 nulls as fields | neither null is a field; both exist only inside `PR-016`/`PR-018` | **fails** |
| C-4 net with interval | the card declares no number at all | **fails** |
| C-5 cost admission | no cost-in-R rule; the threshold is unset and owner-pending | **fails** |
| C-6 execution time | declared (`next session's open`) — the most expensive moment measured | **holds, badly** |
| C-7 own researched hold | inherits `assumed:DR-012`, 20 sessions, never varied on selected entries | **fails** |
| C-8 tail budget | none declared | **fails** |
| C-9 trial bill | not carried | **fails** |
| C-10 predicate retirement, computed version | §6 gives three conditions and two of them are already predicates | **partly** |

**Two and a half of ten.** `CARD-001` is not a bad card — it is an honest one, and §2 of it argues at
length for why it must stay `Untested`. What the table says is that **the honesty was about the
parts**, and the contract is about the thing the parts add up to.

---

## 4. The research this contract makes visible

Each of these is a study that does not exist, and each one is now attributable to a clause rather
than to somebody's judgement about what to do next.

| owed by | question | status |
|---|---|---|
| **C-7** | what holding period does this combination want, measured on selected entries, with the stop width varied beside it | **`PR-019`**, sized by `tools/power_pr019.py` before it was registered |
| C-5 | what does each candidate cost-in-R floor cost in universe and buy in net R | tool exists (`measure_gap_cost.py`, its floor table); needs the owner's fraction |
| C-6 | does the gross survive a later entry — the question `DR-040` §6 registers | blocked on intraday bars |
| C-4 | a cost model whose error cannot align with the axis under study | `PR-014`'s lesson, unimplemented |
| C-10 | the tool that computes a combination version and resets the status | not built |
| C-3 | the QA reconstruction for a no-stop arm | `verify_pr016_qa.py` is specific to `PR-016` |

**C-7 is first, and not only because the owner asked for it.** It is the clause whose missing answer
makes the other clauses unanswerable: the reachable target, the number of round trips the gross must
carry, and the width the stop can afford are all downstream of the hold, and all three are currently
resting on a constant that was a study condition rather than a finding.

---

## 5. What this document does not do

It does not create a strategy. It does not ratify a parameter, choose a threshold, or advance any
validation status; every clause is a requirement to declare, and `AGENTS.md` §8 and §14 still own
what gets declared.

It does not claim the combination it makes visible is profitable. **The measured position is that it
is not**: the ratified combination loses on both windows, the one arm that earns carries a tail in
which more than a fifth of trades run below −2R, and `EVIDENCE_SUMMARY.md` §1 remains the standing
counterweight.

It does not change `DR-014`: **no owner capital, paper only.**

And it does not retroactively invalidate anything. Studies reported before this document stand as
reported; what changes is that a **strategy** may no longer be assembled out of them without
declaring the assembly.
