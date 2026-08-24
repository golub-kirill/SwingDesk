# PR-012 RESULT: the sample rule fired, and it fired for the reason §8 named in advance

```
prereg:     PR-012 (registered 2026-08-24)
status:     reported
run:        2026-08-24
verdict:    REFUSED - the minimum sample is not met on two of three arms
data:       PR-012.json
trials:     3 configurations, spent
```

---

## The verdict, and why it is not `inconclusive`

**§8 fixed a minimum of 200 closed trades per arm on the holdout, and said what happens if it is
not met:** *"the study reports the measurement and refuses a verdict."* At the measured cost
vector:

| arm | holdout trades | ≥ 200 |
|---|---|---|
| `MOMENTUM` | 184 | **no** |
| `MARKET` | 203 | yes |
| `SECTOR` | 181 | **no** |

Two of three arms are under the floor, and one of them is the **control**. A comparison whose
control is under-sampled is not a comparison, so this is a refusal rather than an `inconclusive` —
those are different claims and collapsing them would report a missing measurement as a measured
result.

**§8 predicted this exact failure mode before the run:**

> The capacity cap makes this a real risk rather than a formality. Four concurrent positions over a
> 20-session holding period is at most about 12 entries a year per arm, so the window must be long
> for the sample to exist at all. If the deepened universe does not supply it, that is the finding
> and §8's refusal is the correct outcome.

The universe *was* deepened for this study — from a median of 510 bars to 2,512 — and **9.5 years
still does not supply 200 holdout trades on a four-slot book.** That is the finding.

## What ran

```
window        2017-02-22 -> 2026-08-21, 2,388 sessions
holdout from  2023-10-12  (the last 30% of sessions, per §5)
universe      1,140 admitted; 1,013 carry a dominant sector
snapshot      the bar store's own latest knowledge_time
```

The window is what §4's **rule** produced — *the first session on which at least 200 admitted names
have a full 126-session lookback* — not a chosen date. The fast-path score tables agreed with
`ranking.py`'s reference implementations on all 200 sampled scores.

## The numbers, reported because a refusal still reports

At the measured cost vector (`1x`):

| arm | period | n | mean net R | 95% CI |
|---|---|---|---|---|
| `MOMENTUM` | primary | 413 | 0.3886 | [−0.0590, 1.1580] |
| `MOMENTUM` | **holdout** | **184** | 0.1935 | [−0.0362, 0.4350] |
| `MARKET` | primary | 432 | 0.0516 | [−0.0846, 0.1951] |
| `MARKET` | **holdout** | **203** | 0.1060 | [−0.1247, 0.3564] |
| `SECTOR` | primary | 409 | 0.3445 | [−0.3072, 1.2578] |
| `SECTOR` | **holdout** | **181** | 0.1606 | [−0.0539, 0.3803] |

Under the 3× cost stress the `MARKET` arm turns negative on the primary window
(−0.2181, CI [−0.3438, −0.0909]) and the others stay positive with intervals straddling zero.

**Three observations, and none of them is a verdict.**

1. **Every holdout interval straddles zero.** Even at an adequate sample the decision rule's
   `accept` branch could not have fired, because §6 required an interval **entirely above 0**.
2. **Neither ranking arm beat the control.** `MOMENTUM`'s holdout mean is 0.194 against `MARKET`'s
   0.106 and `SECTOR`'s 0.161. §6's `accept` also required a ranking arm's lower bound to exceed
   the control's point estimate; it is not close.
3. **The wide primary intervals are the small-sample shape, not a signal.** `SECTOR`'s primary CI
   spans −0.31 to +1.26 on 409 trades, which is what a heavy-tailed R distribution looks like when
   a handful of trades carry the mean.

**These are observations on a refused study and they are not evidence.** They may inform the next
pre-registration; they may not advance any validation status, and nothing here moves `CARD-001` off
`Untested`.

## What this costs the programme

**Three trials, spent.** Derive the cumulative count with `python tools/trial_budget.py`. A refused
study still spends its trials: the configurations were evaluated, and `b.deflated_sharpe` deflates
by shots taken at the data rather than by shots that produced an answer. That is what *cumulative
across the whole programme* means, and pretending otherwise is the direction that manufactures
significance.

## Why the sample is structurally short, and what would fix it

The book holds **at most 4 positions** (`risk.max_concurrent_positions`, ratified) for **at most 20
sessions** (`exit.max_holding_period`, ratified). That is a hard ceiling of roughly
`4 × 252 / 20 ≈ 50` entries a year, and the holdout is 2.9 years — so about **145 trades is the
structural maximum**, before any session on which fewer than four candidates qualify. The observed
181–203 is at that ceiling, not below it.

**So no amount of universe deepening fixes this.** The binding constraint is the capacity cap
against the holding period, and every route out of it is a change to something ratified or to the
study's shape:

| route | what it changes | cost |
|---|---|---|
| a longer window | more calendar, same rate | pre-2017 data, and survivorship worsens the further back it reaches |
| a shorter holding period | `exit.max_holding_period`, ratified by `DR-012` | a new study; `PR-009` is the one that may move it |
| more concurrent positions | `risk.max_concurrent_positions`, ratified by `DR-006` §8.3 at 4 for a measured reason | an owner ruling against evidence |
| a lower minimum sample | `b.min_sample`, ratified | weakens every Track B claim, not just this one |
| **pooling the primary window** | the study's own split | **the honest one**, and it needs a new pre-registration because §5 fixed the split before the run |

## What would have refuted the hypothesis

Unchanged from §9, and worth restating because the study did not get to test it: a holdout in which
the ranking arms' intervals sat at or below the momentum control's point estimate. **The holdout
looks like that** — but on 181 and 203 trades against a control on 184, which is why it is an
observation and not the refutation.

## Limitations, all of them inherited and none of them fixed here

- **Survivorship is absent.** Today's directory, so delisted names are missing and every figure
  above is biased **upward**.
- **Today's sectors, not point-in-time ones** (`DR-006` §14.5). A name that changed sector is
  misfiled for its whole history; this biases the `SECTOR` arm specifically, in an unknown
  direction.
- **Raw prices**, so a dividend payer looks weaker by roughly its yield over the lookback
  (`DR-018` §3). The store holds no adjusted series.
- **One lookback, one benchmark, one split.** All fixed in advance, which is why this study spends
  three trials and not thirty — and it means the result says nothing about 63 or 252 sessions.

## Reproducing

```bash
python tools/run_pr012.py --data data --verify-sample 200
```

Deterministic given the store: the window comes from a rule, the bootstrap is seeded
(`BOOTSTRAP_SEED = 20260824`), and the runner refuses to start if its pinned constants no longer
match what §5 declared.


---

## Appended 2026-08-24: the split cost the sample and bought nothing, and saying so is now expensive

Appended rather than edited — a reported result is corrected forward (`AGENTS.md` §11 rule 2). No
number above changes.

### The holdout protected against a risk this study did not carry

`WALKFORWARD_SPEC.md` §1 states what a split is for: *"Walk-forward separates tuning from subsequent
checking in time. It fails when the choice saw the data it is later judged on."* §2 makes the
mechanism explicit — parameters are **fitted** on train, **selected** on validation, and **judged**
on test.

**This study fits nothing and selects nothing.** §5 says so in its own words: *"NOTHING is selected
from the data. All three arms and the single lookback are fixed here, before the run. There is no
parameter search."*

So train and validation are empty by construction, and the 70/30 split discarded **70% of the
window from the judged sample in exchange for a protection there was nothing to protect.** Roughly
600 trades per arm became roughly 185, which is the entire reason §8's floor was missed. The routes
listed above — a longer window, a shorter holding period, more positions, a lower `b.min_sample` —
were all answers to the wrong question.

### And the honest fix is not available to whoever notices it

The obvious redesign is the same three arms over the full window with no split. **It cannot be run
as a confirmatory study now**, and the reason is `PREREG_TEMPLATE.md` rule 3: *"An amendment made
after seeing data downgrades the study to exploratory."* The numbers above are seen. A
pre-registration written by someone who has read them is not a pre-registration in the sense that
makes one worth anything, whatever its commit timestamp says.

**This is a real cost and it is recorded rather than worked around.** The choices are:

| | |
|---|---|
| run it and label it **exploratory** | honest, and it cannot advance any validation status or set `rs.benchmark_form` |
| have someone who has not seen these numbers design it | the only route to a confirmatory result on this window |
| register a **different** question | the split's cost does not transfer, but the trials do |

**None of these is free, and the cheapest-looking one is the trap.** Running the pooled version and
quietly treating its verdict as confirmatory is exactly the data-snooping the whole
pre-registration discipline exists to make detectable, and it would be undetectable here because
the file would look correct.

### What this says about the discipline rather than about the study

**A split is a cost, not a virtue, and it should be priced before it is imposed.** This
pre-registration copied a 70/30 holdout from `PR-005`, which had five gate arms and a genuine
selection problem. Carried into a study with no selection at all, the same structure looked like
rigour and behaved like a 70% sample cut.

`PREREG_TEMPLATE.md` §5 asks for a `split` and a `selection rule` as separate fields. It does not
ask what the split is *for* when the selection rule is "nothing". That is the gap this study fell
into, and it is a template question rather than a study one — carried to `TODO.md`.
