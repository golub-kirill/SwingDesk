# TRIAL BUDGET — what the programme may spend against `b.deflated_sharpe`

**Status:** owner-pending · **Tier:** 8 (PM) · **Written:** 2026-08-24

Step 3 of [`plans/2026-08-24-from-machinery-to-evidence.md`](plans/2026-08-24-from-machinery-to-evidence.md).
That plan's §2c says the conflict between rigour and search is *"unpriced"*. This prices it, and
the price is not what the plan assumed.

**No number here is typed.** Derive every figure with:

```bash
python tools/trial_budget.py
```

---

## 0. Three things measured before anything is proposed

### 0a. The criterion is ratified and nothing computes it

`registry/criteria.yml`:

> `b.deflated_sharpe` — Deflated Sharpe computed on the CUMULATIVE trial count across the whole
> programme · `> 0` · **ratified**

Checked 2026-08-24, against the code graph and by text search across `src/`, `tools/` and `tests/`:
**no module computes a deflated Sharpe.** That much was expected — it is a reporting statistic and
no study has needed it yet.

**What was not expected: nothing counts the trials.** Not a parameter, not a registry field, not a
line of code. The criterion's only input did not exist anywhere, so a criterion ratified on
2026-08-08 could not have fired on any day since. This is the shape `AGENTS.md` §7 was written for,
and it is not the first this repository has found - `AGENTS.md` §7 names the family and
`DR-016` §8.5 is the most recent, an empty `corporate_actions` table discovered inside the
record that closed the previous one. Counting the instances in prose is the trap §12 names,
so this one is named rather than numbered.

`tools/trial_budget.py`, added with this document, supplies the input. It deliberately does **not**
compute the deflated Sharpe — see §4.

### 0b. Two documents disagree, and one of them is ratified

`PREREG_TEMPLATE.md` §6 carries these as **open items**:

> - Multiple-testing correction. … Candidate approaches from the literature: White's Reality Check,
>   the deflated Sharpe ratio (Bailey & López de Prado), and the multiple-testing adjustments argued
>   for in Harvey & Liu. **None is adopted yet** …
> - Whether the trial count for such a correction is per component, per strategy, or project-wide.

`criteria.yml` **ratified both** on 2026-08-08: the method is the deflated Sharpe, and the
denominator is cumulative across the programme. `EVIDENCE_RECORD_SPEC.md` §1 then states it as
settled fact.

**`criteria.yml` wins and the template is stale.** A ratified criterion is a commitment; a template's
open-items list is a working note. The template should be corrected forward — that is an open item
in `TODO.md`, not a change made here, because `PREREG_TEMPLATE.md` governs how studies are written
and editing it inside a budget document is the wrong blast radius.

### 0c. Thirteen trials are already spent, not five

**A trial is a CONFIGURATION EVALUATED, not a pre-registration filed.** The deflated Sharpe deflates
by the number of shots taken at the data; a study that fits four regime variants and keeps one has
taken four shots, not one.

| study | trials | what |
|---|---|---|
| `PR-001` | 4 | one per trend definition tested |
| `PR-002` | 4 | one per regime-classifier variant fitted — one selected, three still tried |
| `PR-005` | 5 | one per gate arm. `1x`/`3x` is a cost stress on the same arm and primary/holdout is a data split, so neither multiplies the search |
| `PR-008` | 0 | measures a spread ESTIMATOR, not a return — no Sharpe to deflate |
| `PR-010` | 0 | same |

**The plan's §2c reads the census as the budget** — *"5 reported studies in 23 calendar days. The
trial budget is therefore small."* The census is 5 and the spend is **13**. Counting filings instead
of configurations understates the search by about a factor of three, in the flattering direction.

The counting rule is printed per study by the tool rather than hidden inside a total, so a reader
can disagree with the rule instead of having to trust the number.

## 1. The arithmetic, and it inverts the plan's assumption

Under the null, the expected best of `N` independent trials rises with `N`. In units of the
dispersion of the trials' own Sharpes (Bailey & López de Prado 2014 — an **authored import**,
marked as one per `AGENTS.md` §10.3):

| N trials | hurdle, sd(SR) | marginal |
|---|---|---|
| 1 | 0.00 | — |
| 5 | 1.19 | +1.19 |
| 10 | 1.57 | +0.38 |
| **13 — spent today** | **1.70** | +0.13 |
| 20 | 1.90 | +0.13 |
| 30 | 2.07 | +0.17 |
| 50 | 2.28 | +0.20 |
| 100 | 2.53 | +0.25 |

**The growth is logarithmic, and that is the whole finding.** Going from 1 trial to 5 costs
**1.19** sd(SR). Going from 5 all the way to **50** — a tenfold expansion — costs only **1.08**
more.

Three consequences, and each contradicts something a reasonable person would assume:

1. **The expensive trials are the first ones, and they are already spent.** The programme paid its
   steepest increment before this question was ever asked.
2. **Rationing trials late buys very little.** Cutting a budget from 30 to 20 recovers 0.17 sd(SR).
   That is not a research strategy; it is a rounding error bought with the option to test anything.
3. **What buys the control is DECLARING and COUNTING trials, not having few of them.** An undeclared
   trial is not free — it inflates the true `N` while the reported `N` stays flat, which is exactly
   the direction that manufactures significance. A counted trial costs 0.13 sd(SR); an uncounted one
   costs the criterion's integrity.

**So `b.deflated_sharpe` is not the trap §2c takes it for.** It is a cheap and well-behaved control
that this project has simply never operated. The trap was never the arithmetic — it was that nobody
could say what `N` was.

## 2. What is proposed

**A budget of 25 configurations across the whole programme**, of which 13 are spent and **12
remain**. At 25 the hurdle is 2.00 sd(SR), against 1.70 today — the entire remaining budget costs
**+0.29 sd(SR)**.

Allocation, as an intent rather than a reservation — an unspent line is not a licence to spend it:

| family | trials | why |
|---|---|---|
| cross-sectional ranking | 4 | a genuinely different family on the same data; the universe machinery exists and the engine can now express it |
| short-horizon mean reversion | 4 | the family where the cost model *decides* the answer, which is why `DR-005` and `DR-010` were built |
| the excluded liquidity corner | 2 | only if a card asks for it; `DR-003`'s floor is ratified and moving it is a strategy argument |
| reserve | 2 | for the thing nobody has thought of. A budget with no slack gets exceeded silently |

**Three rules that matter more than the number:**

1. **A configuration counts when it is RUN, not when it is reported.** A variant fitted and
   discarded is a shot taken. `PR-002` fitted four and reported one; all four count here.
2. **A re-run of an unchanged configuration on unchanged data costs nothing.** Reproduction is not
   search. A re-run on *more* data, or with any parameter moved, is a new trial.
3. **The count only ever goes up.** There is no expiry and no reset. A refuted family does not
   return its trials — that is what "cumulative across the programme" means, and it is the sentence
   `criteria.yml` already ratified.

## 3. What this does not settle, and the owner's call

**The number is the owner's**, and the arithmetic above is deliberately not an argument for a large
budget or a small one — it shows the choice matters less than either intuition suggests. What it is
an argument for is *counting*.

Also unsettled and named rather than glossed:

- **The trials are not independent**, and the formula assumes they are. Five gate arms over one
  universe and one window share almost all their data. Dependence makes the true hurdle *lower* than
  the table, so the table is conservative — which is the safe direction, and it is an approximation
  rather than a measurement.
- **`sd(SR)` across trials is not known**, so the hurdle is in units of it rather than in Sharpe.
  Converting needs each trial's Sharpe, and Track B evaluates on **journalled trades only**
  (`criteria.yml` v1.1.0) — of which there are none. Until a card is live and journalling, the
  absolute hurdle is not computable and this document does not pretend otherwise.
- **Whether a backtest arm and a journalled strategy count against the same N.** They do here,
  because the search happens either way and the criterion says *programme*. That reading is not
  written anywhere else and is worth a ruling.

## 4. Why the deflated Sharpe itself is not implemented here

Because it cannot be evaluated and building it would create the appearance that it can. Its inputs
are each trial's Sharpe and their dispersion; both need journalled trades, and `b.min_sample` wants
100 closed ones per strategy and version. `PR-007` §9 already records this — an `accept` there
*"licenses nothing on its own"* precisely because `b.deflated_sharpe` is unevaluated.

**What was missing was never the statistic. It was the count**, and that is what this document and
its tool supply. The statistic lands when there is something to deflate.

## 5. What would show this is wrong

- **Trials turn out to be near-independent** — then the hurdle is the table rather than an upper
  bound, and a tighter budget starts to earn its cost.
- **Throughput reaches several honest studies a week.** The plan's §6 names this as the test of
  whether §2c's conflict exists at all. At that rate 12 remaining trials is weeks, not the
  programme, and the budget needs re-opening rather than defending.
- **A counting rule above is judged wrong** — most likely `PR-005`'s, where a reader could argue the
  `1x`/`3x` cost stress is a second shot. It is printed per study so that argument can be had
  against the rule instead of against the total.
