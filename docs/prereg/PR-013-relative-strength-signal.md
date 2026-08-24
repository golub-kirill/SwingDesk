# PREREG: does relative strength separate forward returns at all, measured on names rather than on a four-position book?

```
id:            PR-013
date:          2026-08-24
author:        owner (direction), agent (drafting)
status:        registered
```

**Read §0b before anything else. This study is EXPLORATORY by declaration**, not by accident, and
the reason is stated there rather than discovered later.

## 0. Refutation-family check

```
searched:     docs/prereg/ across every local branch (AGENTS.md 10.2), and docs/decisions/ for
              rulings that already settle a piece of this. Terms: relative strength, cross-
              sectional, momentum, ranking, benchmark.
found:        PR-001  trend definitions select different instruments        REFUTED
              PR-005  those populations then behave the same                REFUTED
              PR-012  a ranked four-position book beats a momentum book      REFUSED (sample)
              DR-018  benchmark chosen; point-to-point relative strength measured
distinct because:
              PR-001 and PR-005 refuted the TIME-SERIES trend family - each name judged against its
              own history. This is cross-sectional: names judged against each other. DR-018 is a
              decision record that fixed the benchmark and does not test whether the measure
              predicts.
              PR-012 is the closest and is genuinely a different question. It asked whether a
              CAPACITY-CONSTRAINED BOOK ranked this way outperforms one ranked by momentum, and it
              refused a verdict because four concurrent positions held at most twenty sessions
              cannot produce enough trades. This study removes the book entirely and asks whether
              the ORDERING carries information about forward returns. A negative answer here would
              make PR-012's question moot; a positive one would not settle it.
```

## 0b. Why this is exploratory, declared before the run

`PREREG_TEMPLATE.md` rule 3 downgrades a study to exploratory when an amendment is made after data
was seen. This is a new study rather than an amendment, so the rule does not fire mechanically — and
the honest reading fires anyway.

**The drafter has read `PR-012`'s results**, which observed that neither ranking arm's holdout
interval excluded zero and neither beat the momentum control. That is information about this same
signal, obtained before this design existed. A study designed with that knowledge and reported as
confirmatory would be undetectable data snooping, which is the trap `PR-012`'s own report names.

**So: exploratory. It may generate the next pre-registration and it may not advance a validation
status** (rule 3). Its purpose is to decide whether a confirmatory trial is worth spending at all,
and that is what exploratory results are for.

**Two things are inherited rather than chosen, to remove the remaining degrees of freedom:**

- the **holdout boundary** is `PR-012`'s (2023-10-12), not one picked to suit this study;
- the **lookback** is `PR-012`'s (126 sessions), so no lookback is searched here.

## 1. Question

Over the admitted US universe, does ranking names by relative strength — in a form that is **not** a
monotone transform of the name's own return — separate the forward return of the top decile from the
bottom decile by more than ranking on raw return alone does?

## 2. Hypothesis

`M31-T0465-v5.0` (*long strongest / short weakest*, which the course itself records as an **Untested
Hypothesis**) carries information at the cross-section: names in the top decile of relative strength
outperform names in the bottom decile over the following 5 sessions, and by more than the same
decile split on raw return produces.

`M31-T0464-v5.0` supplies the measure and is `specified`. `rs.benchmark` = `SPY` (`assumed:DR-018`).

## 3. Prediction

Stated numerically before the run. The statistic is defined in §5.

| | TRUE | FALSE |
|---|---|---|
| Arm's mean decile spread | positive, 95% CI excludes zero | CI includes zero |
| Against the control | arm's CI lower bound above the control's point estimate | at or below it |

**If both look the same, the study cannot inform.** They do not: the control is the whole point.
`DR-018` measured that the usual point-to-point relative-strength ratio ranks a cross-section
**identically** to raw return — Spearman 1.000000 across 15 benchmark × lookback pairs over 1,148
names — so a study without a raw-return control would measure momentum and report it as relative
strength. That is why the point-to-point form is **excluded as an arm by construction**: it is the
control.

## 4. Data

```
universe:      the DR-003 liquidity rule as of each formation date, read as-of - never today's
               admitted set applied to an older window
window:        2017-02-22 -> 2026-08-21, inherited from PR-012, which chose the start as the first
               session on which at least 200 admitted names carried a full lookback
snapshot:      the bar store's latest knowledge_time at run time, pinned and recorded
benchmark:     SPY (rs.benchmark), and the sector arm uses the classification store read as-of
costs:         slippage 25 bps per side (DR-005, measured), commission 0.005 per share
               (assumed:DR-010). Applied as stated in section 5 - and the gross figure is reported
               beside the net one, because a decile-spread portfolio's cost depends on turnover
               rather than on a per-trade rule
survivorship:  ABSENT. The directory is today's, so every figure is biased UPWARD. PR-002's own
               bound puts the erasure at 1.6-2.3% of trades missing at -2R; this study cannot
               correct it and reports it
```

## 5. Method

```
unit:          one FORMATION DATE, not one name and not one trade. On each formation date every
               admitted name is ranked; the statistic is a property of the date.
formation:     every 5th session, NON-OVERLAPPING. Overlapping windows would inflate the count
               without adding information - names ranked on consecutive days share almost all of
               their history and their forward window.
horizon:       5 sessions forward, close to close.
split:         train  - none. NOTHING IS FITTED, so a train window would be empty by construction.
               PR-012's report established that a split protecting against a fitting risk the study
               does not carry costs sample and buys nothing.
               primary  2017-02-22 -> 2023-10-11
               holdout  2023-10-12 -> 2026-08-21   (boundary inherited from PR-012)
selection rule: NONE. No parameter is chosen from any window. Every value is fixed above.
arms:          3, and each is a trial (see section 6a)
               A  MARKET PATH   share of the last 126 sessions on which the name's daily return
                                exceeded SPY's. DR-018 measured this at rho ~ 0.6 against raw
                                return, so it is a genuinely different ordering.
               B  SECTOR        the name's return over 126 sessions relative to its own sector's,
                                through the classification store's look-through. DR-018 section 7
                                measured rho 0.750-0.819 against raw return.
               C  CONTROL       raw return over the same 126 sessions. Plain momentum.
statistic:     per formation date, the mean forward return of the top decile minus the mean forward
               return of the bottom decile. The reported figure is the mean of that spread over
               formation dates, with a 95% bootstrap CI resampling FORMATION DATES (10,000
               resamples, seed 20260824).
               Deciles require at least 100 ranked names on the date; a date with fewer is dropped
               and the count of dropped dates is reported.
costs:         a decile-spread portfolio turns over both legs at each rebalance, so the net figure
               subtracts 4 x 25 bps per formation date - two sides on each of two legs - plus the
               commission model. Reported beside the gross figure.
perturbations: WALKFORWARD_SPEC section 4, run: cost stress at 3x (a sensitivity on the same
               configurations, not a new arm - it costs no additional trial).
               NOT run, and named rather than omitted: lookback sweep, horizon sweep, decile-width
               sweep, execution delay. Each would be a further shot at the data.
```

**Why the effective sample is the number of DATES and not the number of names.** Every name ranked
on one date shares that date's market move, so the cross-section is one observation, not a thousand.
This is the correction that makes the study worth running at a different unit than `PR-012` used —
not that names are numerous, but that a 5-session horizon admits **five times as many independent
formation dates as the ratified 20-session holding period allows trades to be opened.**

## 6. Decision rule

```
accept if:     the arm's 95% CI on the mean net decile spread excludes zero AND its lower bound
               exceeds the control's point estimate
reject if:     the arm's CI includes zero, OR its point estimate is at or below the control's
inconclusive:  everything else - a legitimate and expected outcome
```

**No verdict advances a validation status**, because §0b makes this exploratory. `accept` here means
*worth spending a confirmatory trial on*, and nothing more.

## 6a. Trials

**3 trials**, one per arm, declared before the run as `PREREG_TEMPLATE.md` §6 requires. The cost
stress is a sensitivity on the same three configurations and costs no additional trial
(`TRIAL_BUDGET.md`: a cost stress is not a new shot at the data). Derive what remains with
`python tools/trial_budget.py`.

## 7. Stopping rule

The study ends when the three arms have been evaluated over the full window at the pinned snapshot.
There is no early stop and no extension: the window is fixed in §4 and is **not** contingent on the
result.

## 8. Sample

```
minimum:       100 formation dates in the holdout.
               DERIVED BY ANALOGY, and the analogy is declared rather than hidden: b.min_sample is
               100 CLOSED TRADES and a formation date is not a trade. What the criterion protects
               against is an expectancy CI too wide to act on, and the same argument applies to a
               mean of date-spreads. The number is not doubled the way PR-012 doubled it: PR-012
               compared three arms' TRADE populations against each other, while here every arm is
               measured on the SAME dates, so the comparison is paired and does not need more than
               either side alone.
if not met:    the study reports the measurement and REFUSES a verdict, exactly as PR-012 did.
expected:      the holdout spans roughly 717 sessions, so about 143 non-overlapping formation
               dates. This is expected to be met and is fixed here so that it is not adjusted after
               the fact.
```

## 9. What would refute this

A holdout in which arm A's and arm B's decile-spread CIs both include zero, or in which neither
point estimate exceeds the raw-return control's. Either observation makes the hypothesis wrong at
this horizon and this lookback, and would mean the cross-sectional ranking `CARD-001` is built on
carries no information the control does not already have.

**It would not refute the FAMILY.** A different horizon or a different lookback could still carry
information, and this study deliberately searches neither — which is the cost of not spending trials
on a sweep, stated here rather than discovered in the report.

## 10. Amendments

None. Appended, dated, never edited in place. An amendment after data is seen is recorded as such —
and this study is already exploratory by §0b, so an amendment cannot downgrade it further and must
still be recorded.
