# PREREG: Does a regime classifier improve decisions, or only partition them?

<!-- verbatim-sources: Module_30_Rynochnye_rezhimy_v5.0.pdf -->

```
id:      PR-002
date:    2026-08-02
author:  owner
status:  registered
blocked: backtest harness; PR-001 (a trend definition is an input to any classifier)
```

## 0. Refutation-family check

- **searched:** `registry/course_index.yml` M30/M31 regime topics and Appendix L
  (`Стратегии и рыночные режимы`); `docs/prereg/` for prior regime studies.
- **found:** none run. The course names eleven regimes and supplies no classifier
  (`REGIME_SPEC.md` is planned, and its classifier is marked authored).
- **distinct because:** first study of this family.

## 1. Question

Does conditioning on a market regime change what the system should *do*, or does it only relabel
outcomes after the fact?

## 2. Hypothesis

A regime label carries decision-relevant information: the distribution of forward outcomes for the
same setup differs materially across regimes, measured **out of sample**.

The null this is tested against is not "regimes do not exist". It is the sharper and more likely
failure: **regimes are identifiable in hindsight and not in advance**, so a classifier that fits
history beautifully has no edge at the moment a decision is made.

## 3. Prediction

**If TRUE:** the same setup, partitioned by the regime label assigned *using only data available at
the decision bar*, shows forward-outcome distributions that differ by more than the difference
between random partitions of the same size.

**If FALSE:** the difference across regime partitions is within the range produced by random
partitions of equal size — the label is decoration.

**The random-partition baseline is the point of this design.** Any partition of a noisy series into
subsets produces subsets with different means. Comparing regime partitions against *nothing* would
find a difference every time. The comparison must be against equal-sized random partitions of the
same data, and that baseline is fixed here, before any classifier exists.

## 4. Data

```
universe:      as PR-001
window:        10 years daily, both exchanges, reported separately per BR-9
snapshot:      pinned at run time, recorded in the manifest
costs:         costs.commission_model and costs.slippage_model must be SET before this
               runs - a regime effect smaller than the cost spread is not a finding
survivorship:  ABSENT (BACKTEST_PROTOCOL 6). This study measures forward outcomes, so the
               bias is material here in a way it was not for PR-001: instruments that
               delisted are missing from the outcome distribution, and delisting is not
               regime-independent. Recorded on the evidence record, and the result may not
               be reported without it.
```

That last point is the honest limitation of this study on free data, and it is stated at
registration rather than discovered in the discussion section.

## 5. Method

```
split:          train / validation / test by date, three-way (WALKFORWARD_SPEC 2).
                Classifier parameters fitted on train, classifier VARIANT selected on
                validation, outcome distributions measured on test only.
selection rule: among classifier variants, choose the one with the most stable regime
                assignment on validation - fewest label changes per unit time - NOT the
                one with the largest outcome difference. Selecting on the outcome
                difference is the study answering its own question.
perturbations:  parameter stability (thresholds +/- 20%); execution delay of 1 bar;
                cost stress at validation.stress_cost_multiplier
statistic:      difference in mean forward R across regime partitions, compared against
                the distribution of the same statistic over 1000 equal-sized random
                partitions with a recorded seed
```

The selection rule is the part most likely to be quietly violated later, so it is stated as a
prohibition: **variant selection may not look at the outcome difference.**

## 6. Decision rule

```
accept:        observed cross-regime difference exceeds the 95th percentile of the random
               partition distribution, on TEST data, in BOTH countries independently
reject:        below the 80th percentile in either country
inconclusive:  between; or significant in one country only -> report as a
               single-market finding and do not generalise
```

## 7. Stopping rule

One run over the fixed window. No re-running with a different classifier family after seeing the
test result — that would be a new study needing a new PR, and it would inherit the multiple-testing
debt recorded in `PREREG_TEMPLATE.md` §6.

## 8. Sample

```
minimum:     validation.backtest_min_trades per regime cell, per country
if not met:  report per-cell coverage and refuse the verdict. Regime breakdowns shatter a
             sample into cells; a verdict on a thin cell is noise with a label
             (WALKFORWARD_SPEC 7).
```

## 9. What would refute this

A cross-regime difference indistinguishable from the random-partition baseline on test data. That
would mean the classifier partitions outcomes without predicting them, and `regime.classifier_rule`
would stay unset with a recorded refutation rather than a pending decision.

It would **not** mean regimes are unreal. It would mean this system cannot identify them in advance
from this data, which is the only claim that matters for a decision at the bar.

## 10. Amendments

**2026-08-02 — before any data was seen, before the study ran.** The random-partition baseline in §3
was registered as an authored design choice. It is not: the course requires it.

Topic M30-T0450, `Определение текущего режима`:

> "Инструмент используется как измеритель, а не как источник уверенности. Параметры фиксируются
> версией стратегии, а добавленная ценность проверяется против простой базовой модели."
>
> *(The instrument is used as a gauge, not as a source of confidence. Parameters are fixed by the
> strategy version, and the added value is checked against a simple baseline model.)*

`добавленная ценность проверяется против простой базовой модели` — added value is checked against a
simple baseline model. That is the requirement this study's design already satisfies, and it is
stronger for being the course's own standard rather than an import. §3 and §6 are unchanged; only
their provenance is corrected.

The first sentence is worth keeping in view too: a classifier is a gauge, not a source of confidence.
A regime label that raises conviction rather than constraining the strategy set is being used the way
the topic prohibits.

---

**2026-08-02, second amendment — before any data was seen, before the study ran.** §5 said "among
classifier variants" without saying which, and "difference in mean forward R" without saying how a
multi-cell difference becomes one number. Both are decisions that could be made after seeing results
if they are not made now.

**1. The variants, enumerated.**

The course defines a regime as `сочетание направления, breadth и volatility` (M30-T0446) and names
no indicator. All three components are computable from this project's own bars — breadth especially,
via M31-T0459 `Доля акций выше средних`, which needs no index data and no vendor beyond what the
universe already fetches.

| Variant | Regimes | Built from |
|---|---|---|
| `BREADTH_TERCILE` | 3 | share of universe above its own 200-day SMA, split at train terciles |
| `BREADTH_MEDIAN` | 2 | the same measure, split at the train median |
| `VOL_TERCILE` | 3 | cross-sectional median 20-day realised volatility, split at train terciles |
| `BREADTH_X_VOL` | 4 | breadth above/below train median × volatility above/below train median |

**Thresholds are fitted on the training window only and then frozen.** A tercile boundary computed
over the full sample is a label that used the future, and this study's null is precisely that
regimes are identifiable in hindsight and not in advance. Freezing train-fitted thresholds is what
makes the test-window labels honest.

**2. The statistic, defined.**

For a variant with *k* regimes, the observed statistic is the **range of mean net R across the
regime cells** — highest cell mean minus lowest. One number, comparable across variants with
different *k*, and it is the quantity a trader would actually act on: how much better is the best
regime than the worst.

The baseline is 1000 random partitions of the same trades into cells **of the same sizes**, with a
recorded seed, and the same range statistic computed on each. §6's thresholds apply to the observed
range's percentile within that distribution.

**3. Canada is unavailable.**

§6 requires significance "in BOTH countries independently". `DR-003` records that no free Canadian
symbol directory is in hand, so the universe is US-only, exactly as in PR-001 and PR-005. The
two-country requirement cannot be met and is **not** quietly dropped: a single-market result is
reported as a single-market result, which §6's own inconclusive branch already describes as the
right handling.

**4. Costs are now set.** `DR-004` fixes `costs.commission_model` and `costs.slippage_model`, which
§4 named as a precondition. The study runs at 1× and 3×.
