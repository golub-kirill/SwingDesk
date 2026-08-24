# From machinery to evidence — the plan to answer the profitability question inside the timebox

**Status:** owner-pending · **Written:** 2026-08-24 · **Tier 8**

**Goal:** not profit. **A defensible answer, inside `k.track_a_timebox`, to whether an edge this
project can reach exists at all** — and, if one does, a card that can be run without ceremony.

**Why it exists:** the v1 machinery finish line was reached on **2026-08-02**, and the three weeks
since have produced machinery. The roadmap named the load-bearing next item on the same day and it
is still not done. This plan says so, sequences what follows, and prices three constraints nobody
has written down.

---

## 0. What this plan corrects, before anything is built on it

Three claims were made in the session that produced this document and are **wrong**. A plan resting
on them would be worse than no plan.

1. **"The v1 finish line is close."** It is **reached**. `ROADMAP.md` §2 measures all six of
   `CHARTER.md` §4's capabilities as done, dated 2026-08-02, and `EVIDENCE_SUMMARY.md` §7 says the
   same. The machinery phase is over.
2. **"Component activation at 1 of 465 is the largest gap on the finish line."** It is not a
   finish-line item at all. §4 requires every *displayed* number to carry provenance, which it does
   for the components that exist. Activation belongs to **G6**, and `ROADMAP.md` §3 defines G6 as
   *demand-driven* — "every component **a live strategy card needs** is `active`". 465 was never the
   denominator.
3. **"The backtest engine exists; only a parameterised front end is missing."** Verified in the
   source: `validation/backtest/engine.py:run_arm` **hardcodes the entry trigger** to
   `breakout_high(series, index, config.trigger_lookback)`. The `gate` argument is a per-bar
   *filter* over that trigger, not the trigger itself. The engine is single-instrument, long-only,
   time-series breakout with a boolean regime filter. **That is one strategy family, and it is the
   family `PR-005` refuted.**

Correction 3 is the one that changes the work, and §4 step 4 is built on it.

## 1. The diagnosis, from this repository's own records

**The machinery target was met on day two of the project, and the sessions since have kept building
machinery.** That is not laziness and not waste — the caps, the guards and the gates are real and
several found real defects. It is a *direction* problem: none of it moves Track B, and Track B is
where income lives.

**The roadmap already identified the load-bearing item and it is untouched.** `ROADMAP.md` §4:

> **P5 is the load-bearing one for phase 3.** Demand-driven coverage has no meaning without a card
> to create the demand, so the first card is not one item among several — it is the thing that
> decides which of the 465 components get built at all.

`STRATEGY_CARD_SPEC.md` is written. **No card exists** — there is no `registry/cards.yml`, no card
document, nothing. So phase 3 cannot start, coverage cannot be demand-driven, and G6 has no
definition to be measured against. Everything downstream of P5 has been waiting on P5 since
2026-08-02.

**The consequence, stated plainly:** the project is not blocked on engineering. It is blocked on
having declared, in a reviewable artefact, what it is actually trying to trade.

## 2. Three constraints nobody has priced

These are analysis, not measurements, and each names the check that would settle it.

### 2a. The liquidity floor selects the most efficient corner of the market

`universe.min_adtv_20d = $5,000,000`, `universe.min_price = $5`, `min_bar_history = 250` — all
`assumed`, none measured. They admit **1,148 names of 13,136 eligible**: liquid US mid and large
caps, which is exactly the population every institutional system already trades.

The inefficiency a retail participant can plausibly reach lives in the corners this rule excludes by
construction. **The same rule that protects against slippage removes the population where an edge
would survive.** Both cannot be had at once, and the current setting is chosen, not derived.

*This is the highest-leverage unratified number in the registry: it decides the achievable edge
class before any strategy is chosen.*

**Settles it:** measure the admitted universe and modelled effective spread at $5M / $1M / $500k /
$250k. Computable today from the existing bar store plus `EDGE` (Ardia, Guidotti & Kroencke, *JFE*
2024 — `pip install bidask`), which `AGENTS.md` §10.3 already identifies as the estimator to use
rather than re-deriving Corwin–Schultz.

### 2b. One strategy family is hardcoded into the only engine, and it is the refuted one

§0 correction 3. A cross-sectional ranking rule, a mean-reversion rule or anything not expressible
as "breakout of an N-bar high, optionally gated" **cannot be run** by the current engine. Every
study, every trade log, and the entire cost model calibration describes that one family.

### 2c. Rigor and search are in direct conflict, and the conflict is unpriced

`b.deflated_sharpe` (ratified) requires deflated Sharpe on the **cumulative trial count across the
whole programme**. That is the correct rule. It also means **every hypothesis tested raises the bar
for every other one**.

Measured throughput: 5 reported studies in 23 calendar days. The trial budget is therefore small and
each trial is expensive by construction — and no document says how many trials the programme intends
to spend, or on what. Without that, deflated Sharpe is a trap rather than a control.

## 3. The arithmetic that defines what success can mean

At `account.equity = 10,000` and `risk.per_trade_pct = 1.0`, one R is **$100**.

| edge per trade | 100 trades/year | of equity |
|---|---|---|
| +0.028R (`PR-005`'s base slice at 1×, before `DR-005`'s cost correction) | $280 | 2.8% |
| +0.05R | $500 | 5% |
| +0.10R — already a good systematic edge | **$1,000** | 10% |
| +0.20R — not realistic on daily bars | $2,000 | 20% |

**Research answers the percentage. Capital answers the sum.** These are different questions and only
the first is in this repository's scope. Recorded here so that "стабильный доход" is not silently
read as something the research programme can deliver on its own.

`EVIDENCE_SUMMARY.md` §1 is the counterweight and stands unchanged: at the corrected cost model the
base strategy is **−0.073R at the $5 floor**, and no price an eligible instrument can have makes it
positive.

## 4. The plan

Six steps. Each names its exit condition, so "done" is observable.

### Step 1 — The first strategy card (`ROADMAP.md` P5)

**Exit:** one card exists as a reviewable artefact, declaring its universe filter, entry rule, exit
rule, horizon, and the components it needs. Status `Untested`, which is the only honest status.

This is the roadmap's own load-bearing item and it unblocks G6, coverage, and every step below. It
is authoring, not code.

**It should NOT be the refuted breakout family.** Declaring the card that `PR-005` already tested
would spend the first slot on a known answer.

### Step 2 — The liquidity floor becomes a decision record (§2a)

**Exit:** a `DR-NNN` that states, with the measurement behind it, whether the floor excludes noise
or excludes edge — and either ratifies the current value or moves it.

Cheap, fully computable from what is on disk, and it aims every subsequent study. **If only one
thing from this plan is done, do this one.**

### Step 3 — The trial budget (§2c)

**Exit:** a Tier-8 document naming how many pre-registrations the programme will spend, across which
families, before any are spent — with the deflated-Sharpe accounting stated up front.

One document. It converts a ratified trap into a managed constraint.

### Step 4 — Generalise the engine past breakout (§2b)

**Exit:** `run_arm` takes its entry trigger as an injected rule rather than calling `breakout_high`,
and a second family runs through it end to end with no new module.

Everything else the harness needs already exists — the cost model, the exit policy, the replay, the
prereg conformance gate. This is the smallest change that turns *one* backtest into *a* backtest,
and it is the prerequisite for spending the budget on families rather than on tweaks.

**Guard rail:** the existing `PR-005` trade log must replay byte-identically through the generalised
engine before the change is accepted. A refactor that quietly moves a refuted result is worse than
no refactor.

### Step 5 — Spend the budget on families, not tweaks

**Exit:** each family in the budget has a pre-registration, a run, and a report — accepted or
refuted, both being results.

Candidate families, ordered by prior probability given free daily OHLC and named as research
directions rather than recommendations:

- **cross-sectional ranking** — relative strength within the admitted universe rather than timing
  each name. A different family from the refuted one, on the same data, and the universe machinery
  already exists;
- **short-horizon mean reversion** — the family where the cost model *decides* the answer, which is
  precisely why `DR-005` and `DR-010` were worth building;
- **the excluded liquidity corner** — only if step 2 says it is worth entering.

Running in parallel and requiring no thought: **bar coverage is 28.3%**. `tools/refresh_universe.py`
should run continuously. Every study to date has run on a thin and partly survivorship-limited
sample.

### Step 6 — The verdict, at the timebox

`k.track_a_timebox` is 120 calendar days from the first scheduled daily run (2026-08-09). **15 used,
105 remaining** at the time of writing. `k.programme_exhausted` and `k.strategy_rejected` are
ratified.

**Exit:** a defensible answer, not a hope. That is the only outcome this plan can guarantee.

## 5. What this plan does not promise

It does not promise an edge exists at this data tier. Nobody honest can, and
`EVIDENCE_SUMMARY.md` §1 is the reason to expect the opposite.

It does not promise income. §3 is the arithmetic and it is not a research problem.

It does not change `DR-014`: no owner capital, paper only. Nothing here is a reason to revisit that.

## 6. What would show this diagnosis is wrong

- A pre-registered **cross-sectional** test clears the bar on the current data → the data tier is
  not the ceiling and §2a is overstated.
- Loosening the liquidity floor produces an edge that survives modelled slippage → the rule was the
  bind, and step 2 was the whole plan.
- Throughput reaches several honest studies a week without losing rigor → §2c's conflict does not
  exist and the trial budget is unnecessary.

Each is a cheap test of the claim it attacks, which is the standard this project already holds its
own reports to (`AGENTS.md` §10.4).

## 7. What this plan does not touch, deliberately

The documentation discipline. The gates, the registries, the provenance tracking and the
verbatim-transcription rules are what make a negative result trustworthy, and they cost about a
sixth of the tree while producing every finding this project has. **The problem is not that
documents are too expensive. It is that evidence is not cheap enough** — which is what steps 3, 4
and 5 address, and what step 4 in particular exists to fix.
