# PREREG: Does a cross-sectional ranking beat plain momentum on a capacity-constrained book?

```
id:            PR-012
date:          2026-08-24
author:        Claude (agent), for the owner
status:        reported
card:          CARD-001
trials:        3 configurations (see §5)
```

**This is `CARD-001`'s selection rule.** `ALLOCATION_SPEC.md` §3 forbids setting it by decision
record — *"an ordering adopted from the course is not a transcription and does not inherit the
course's authority"* — so `rs.benchmark_form`, `rs.lookback` and `rs.ranking_method` get their values
here or not at all.

---

## 0. Refutation-family check

- **searched:** every file in `docs/prereg/`, `docs/08-pm/EVIDENCE_SUMMARY.md`,
  `HANDOFF.md` §7 *"Closed by evidence — do not re-open"*, and `git ls-tree` across every branch for
  `docs/prereg` and `docs/decisions`. Terms: relative strength, cross-sectional, ranking, momentum,
  trend definition.
- **found:**
  - `PR-001` — **REJECT**. Trend *definitions* select different populations? No.
  - `PR-005` — **REJECT**. Those populations behave differently net of costs? No.
  - `PR-002` — **INCONCLUSIVE** (corrected from ACCEPT). A regime classifier improves decisions? Not shown.
  - `PR-007` — registered, unreported. Base strategy expectancy at measured costs.
- **distinct because:** every one of those is **time-series**. `PR-001` and `PR-005` ask whether a
  per-instrument trend filter selects or improves; `PR-007` asks whether that same breakout family
  pays. This asks a **cross-sectional** question — *which of these*, not *is this one ready* — and
  it is expressible only since `run_book` gained a date axis and a capacity cap on 2026-08-24.
  `HANDOFF.md` §7's closed rows are *"the trend-definition family"* and *"new entry filters"*; a
  ranking is neither. **The refuted family is the one this deliberately avoids**, which is why the
  owner chose it for the first card.

## 1. Question

Does ranking the admitted universe by a cross-sectional relative-strength measure, and holding the
top names under `DR-006`'s capacity caps, produce a higher mean net R per trade than ranking the
same universe by plain momentum on the same book?

It can come out "no" in two ways: the ranking arms can fail to beat the momentum control, or every
arm including the control can be negative net of costs — which is what `EVIDENCE_SUMMARY.md` §1
leads one to expect.

## 2. Hypothesis

At least one of the two relative-strength forms `DR-018` characterised — `ByMarketPathStrength` or
`BySectorRelativeStrength`, components `M31-T0464-v5.0` and `M31-T0465-v5.0` — produces a mean net R
per trade whose bootstrap interval lies **entirely above zero and entirely above the momentum
control's mean**, on the holdout window.

**The control is not optional and this is why.** `DR-018` §1 proved that a market *point-to-point*
relative strength ranks identically to raw return — the benchmark's return is one constant per day,
so dividing by it is a strictly monotone transform. Without `ByRawReturn` as an arm, an edge from
either ranking form could not be distinguished from momentum.

## 3. Prediction

**If TRUE:** on the holdout, at least one ranking arm shows mean net R > 0 with a 95% bootstrap
interval excluding 0, and its lower bound exceeds the control's point estimate.

**If FALSE:** every arm's interval straddles or lies below 0, or the ranking arms' intervals overlap
the control's point estimate — a ranking that merely reproduces momentum.

These are different observable outcomes, so the study can inform.

## 4. Data

```
universe:      DR-003's liquidity rule as ratified - min_price 5.00, min_adtv_20d 5,000,000
               (owner), min_bar_history 250 - applied at the snapshot. A rule, never a ticker list.
window:        starts at the first session on which at least 200 admitted names have a full
               rs.lookback window; ends at the latest session the store holds. Both are FUNCTIONS
               of the data and fixed by this rule rather than by a chosen date, so neither can be
               tuned after a result is seen. The realised dates are recorded in the result.
snapshot:      the bar store's own latest knowledge_time at the run, recorded in the result.
costs:         DR-010's price-aware model at DR-005's measured slippage - risk.costs_bp_usd = 50bp
               round trip. A 3x stress is reported as SENSITIVITY on the same configurations, not
               as separate arms: a cost stress is not a new shot at the data (TRIAL_BUDGET.md).
benchmark:     rs.benchmark = SPY (DR-018), for the market path arm only.
sectors:       the classification store, read at the RUN's clock. 1,023 of 1,153 admitted names
               carry a dominant sector; the rest are UNSCORED by the sector arm and rank last.
survivorship:  ABSENT. The universe is today's directory, so delisted names are missing and every
               figure is biased UPWARD. This bounds the whole study and no arm escapes it.
```

**Two data limits that are not survivorship and matter as much.**

1. **Today's sectors, not point-in-time ones** (`DR-006` §14.5). A name that changed sector is
   misfiled for its whole history, which biases the sector arm specifically and in an unknown
   direction.
2. **Raw prices, so a dividend payer looks weaker** by roughly its yield over the lookback
   (`DR-018` §3). The store holds no adjusted series. This biases *every* arm identically in
   direction but not in size, since yields differ across names.

## 5. Method

```
split:          the last 30% of sessions in the window is the HOLDOUT and is not looked at until
                the arms are run. The remaining 70% is the primary window. Both are reported.
selection rule: NOTHING is selected from the data. All three arms and the single lookback are fixed
                here, before the run. There is no parameter search, which is why this study spends
                three trials and not thirty.
arms:           MOMENTUM  - ByRawReturn(126)                    [the control]
                MARKET    - ByMarketPathStrength(SPY, 126)
                SECTOR    - BySectorRelativeStrength(126)
lookback:       126 sessions, about six months, fixed now.
capacity:       risk.max_concurrent_positions = 4, risk.max_open_risk = 4R (DR-006, ratified owner).
entry:          AlwaysEligible(126). A cross-sectional family SELECTS rather than times, so there
                is no price trigger; the ranking and the capacity cap do the selecting. CARD-001 §1.
exits:          exit.atr_stop_multiple = 2.0, exit.max_holding_period = 20 (DR-012, ratified).
perturbations:  cost stress 3x (run). Lookback and capacity sweeps are NOT run - each would be a
                new trial and this study does not spend them.
statistic:      mean net R per trade, and a 95% percentile bootstrap interval over 10,000
                resamples of the trade list, seeded and recorded. Net R is cost-inclusive, per
                DR-010, with the R denominator PR #9 corrected.
```

**Why 126 and why only one lookback.** `DR-018` measured rank agreement at 63, 126 and 252 sessions —
**agreement between rankings, never returns**, so no outcome information reached this choice. 126 is
the middle of that range and roughly six months against a 20-session holding period. Choosing it
after seeing those measurements is the same acceptable case `DR-003` Consequence 3 records: a
quantity that involves no forward returns cannot leak the answer. Sweeping lookbacks would multiply
trials, and `TRIAL_BUDGET.md` §1 shows the hurdle rises with every one.

**Trial accounting.** This study evaluates **3 configurations**. Derive the programme's cumulative
count with `python tools/trial_budget.py`; `b.deflated_sharpe` is computed on that total and this
declaration is what the template's §6 now requires.

## 6. Decision rule

```
accept if:      on the HOLDOUT, a ranking arm's 95% bootstrap interval for mean net R lies entirely
                above 0 AND its lower bound exceeds the MOMENTUM arm's point estimate.
reject if:      every arm's interval lies entirely below 0 at the measured cost vector.
inconclusive:   everything else - including a ranking arm that is positive but indistinguishable
                from the control, which is the outcome DR-018 section 1 makes most likely.
```

**An `accept` licenses nothing on its own.** `b.deflated_sharpe`, `b.benchmark_relative` and
`b.era_stability` are ratified and none is evaluated here, and `criteria.yml` v1.1.0 evaluates
Track B on **journalled trades only** — so no verdict here can move `CARD-001` past `Untested`.

## 7. Stopping rule

The study ends when all three arms have run over the full window once. **There is no re-run on a
disappointing result**, and no arm is added after seeing one — an arm added later is a new
pre-registration with its own trial cost.

## 8. Sample

```
minimum:        200 closed trades per arm on the holdout. Derived from b.min_sample = 100 closed
                trades, doubled because three arms are compared and a comparison needs more than
                either side alone.
if not met:     the study reports the trade counts and REFUSES a verdict. A thin arm is reported as
                thin, never as inconclusive-by-statistic.
```

**The capacity cap makes this a real risk rather than a formality.** Four concurrent positions over
a 20-session holding period is at most about 12 entries a year per arm, so the window must be long
for the sample to exist at all. If the deepened universe does not supply it, that is the finding and
§8's refusal is the correct outcome.

## 9. What would refute this

A holdout in which the ranking arms' intervals sit at or below the momentum control's point estimate.
That is the specific observation that says a cross-sectional relative-strength ordering is momentum
with extra steps — which is exactly what `DR-018` §1 proved for the *point-to-point* market form and
what this study asks about the two forms that escape that proof.

## 10. Amendments

None. Appended, dated, never edited in place; an amendment after data is seen downgrades this to
exploratory.

## 11. Reported 2026-08-24 — REFUSED for want of sample

`results/PR-012-report.md`. §8's minimum of 200 holdout trades per arm is not met on two of three,
and one of the two is the **control** — so §8's *"reports the measurement and refuses a verdict"*
fires, and it is a refusal rather than an `inconclusive` because a comparison whose control is
under-sampled is not a comparison.

**§8 named this failure mode before the run**, and the arithmetic under it is now measured: four
concurrent positions held at most 20 sessions is a ceiling of about 50 entries a year, so a
2.9-year holdout can produce roughly 145 trades at best. The observed 181–203 is **at** that
ceiling. No amount of universe deepening fixes it — the binding constraint is the capacity cap
against the holding period, and both are ratified.

The three trials are spent. A refused study still spends them: `b.deflated_sharpe` deflates by
shots taken at the data, not by shots that produced an answer.
