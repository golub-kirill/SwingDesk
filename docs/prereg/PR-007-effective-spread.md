# PREREG: Is the assumed 5bp slippage an understatement of the spread this universe actually pays?

```
id:      PR-007
date:    2026-08-09
author:  owner
status:  registered
blocked: nothing - runs offline against data/bars.duckdb
```

`PR-006` is **not** this study. `DR-004` reserves that id for measured live slippage against
modelled, which needs a forward test that does not exist. This study estimates a historical spread
from data already in hand and does not replace it.

## 0. Refutation-family check

- **searched:** `docs/prereg/` for any cost study; `DR-004`'s alternatives table; `ROADMAP.md`
  and `RISK_REGISTER.md` for cost work items; `registry/parameters.yml` for `costs.*`.
- **found:** no study of costs has ever been run here. `DR-004` is a decision record, not a study,
  and it fixed both cost parameters by assumption. `PR-005` consumed those assumptions and reported
  under them. The refuted family in this project is the **trend-definition** family (`PR-001`,
  `PR-005`); nothing in it concerns costs.
- **distinct because:** `DR-004`'s alternatives table rejected *"spread-derived slippage from quoted
  bid/ask"* on the grounds that no free source serves historical intraday spreads point-in-time.
  That is correct and it is about **quoted bid/ask**. It did not consider estimators that recover
  the effective spread from **daily OHLC**, which need no data this project lacks. So this is not a
  rejected option being retried — it is an option the decision record did not evaluate.

This study also does not tune a parameter or add a filter. It measures an input that sits underneath
every R the project has ever reported, including the three refutations.

## 1. Question

Is the effective bid-ask spread paid by the `DR-003`-eligible universe larger than the 5 basis
points per side that `DR-004` assumes?

## 2. Hypothesis

`costs.slippage_model` at 5bp per side **understates** the spread component of transaction cost for
the instruments this system would actually trade.

The null is the assumption's own claim: 5bp per side is at or above the effective half-spread.

## 3. Prediction

**If TRUE:** the median per-side effective half-spread across eligible instrument-months exceeds
5.0bp, on both estimators independently.

**If FALSE:** the median is at or below 5.0bp on both, meaning the assumption is not optimistic
about spread — and, per §9, still says nothing about impact or timing.

### The asymmetry, registered before the run

**This study can show the assumption is too optimistic. It cannot show it is adequate.** A spread
estimate is a lower bound on the cost of crossing: it excludes market impact, timing slippage, and
the cost of a stop that fills through the level. So a measured half-spread below 5bp is *consistent
with* the assumption and is not evidence for it, and §6 is written to say exactly that rather than
to convert a weak result into a strong one.

## 4. Data

```
universe:      DR-003 liquidity rule - min_price 5.00, min_adtv 5,000,000, adtv_window 20,
               min_history 250 - applied to every instrument in data/bars.duckdb
window:        the store's full extent, 2024-08-05 to 2026-08-03, 500 sessions.
               Chosen because it is the whole measured population; no sub-window is selected.
snapshot:      the bars store as committed, knowledge_time per row. Offline; no fetch.
costs:         none charged - this study measures a cost, it does not simulate trades
survivorship:  ABSENT and, unusually, close to harmless here. A spread level is a
               cross-sectional property of surviving liquid names; delisted names would
               widen the estimate, so the bias runs AGAINST the hypothesis and a positive
               result is conservative. Recorded rather than waved away.
```

## 5. Method

Two estimators, chosen because they are independent in construction and both take only daily bars:

```
CS   Corwin & Schultz (2012), from consecutive two-day high/low ratios, with the paper's
     overnight-gap adjustment and its negative-estimate rule
AR   Abdi & Ranaldo (2017), the close-high-low estimator, from the gap between the close
     and the mid-range of adjacent days
```

```
aggregation:    per instrument-month, then cross-sectional across instrument-months.
                Monthly because both estimators are averages over a window and a single
                two-day pair is noise.
statistic:      MEDIAN per-side effective half-spread in basis points, over eligible
                instrument-months, reported per estimator. Half-spread = S/2, because a
                single crossing pays half the round-trip spread and DR-004's 5bp is
                per side.
reported also:  ADTV-weighted mean, and the distribution by ADTV decile and price decile,
                because a universe median hides the thin end and the liquidity rule is
                exactly what decides which end is in scope
negatives:      both estimators produce negative values on some windows. CS sets them to
                zero per the paper; AR takes max(0, .) inside the root. Both are reported
                as a COUNT as well, because a high negative rate is evidence the estimator
                is out of its regime, not evidence of a zero spread.
```

### Secondary, and registered now so it cannot be chosen later

`PR-005` reported the ungated base strategy at two cost levels: **+0.02795R** at 1× and
**−0.12344R** at 3×. Mean R is linear in the cost multiplier, so those two points determine both
terms:

```
cost per trade   C = (R₁ - R₃)/2 = 0.075695 R
gross per trade  G = R₁ + C      = 0.103642 R
break-even       k* = G/C        = 1.3692
```

The base strategy's positive result therefore survives only while true costs stay below **1.369×**
what `DR-004` assumes.

The measured spread does not convert into a verdict on `PR-005` directly, because scaling the
slippage term alone is not the same as scaling total cost, and `PR-005.json` records only the total.
But the split is bounded. Writing `m` for the measured half-spread as a multiple of 5bp, the
strategy stays positive under **every** possible commission/slippage split when `m < k*`, and the
required `m` only rises as the commission share rises. So:

```
m < 1.369  (half-spread < 6.85bp)  -> PR-005's +0.028R survives the spread correction
                                      under every split. A clean one-sided conclusion.
m >= 1.369 (half-spread >= 6.85bp) -> the sign of PR-005's headline is no longer
                                      determined by what is on record, and recovering it
                                      needs PR-005 re-run with cost components logged
                                      separately.
```

**Two caveats on `k*`, both registered before the run.** The linearity is approximate: `PR-005`
recorded 2,629 trades at 1× and 2,672 at 3×, so the trade population is itself cost-dependent and
the two points do not describe one fixed sample. And `k*` inherits every other `PR-005` assumption
unchanged. It is a sensitivity, not a new measurement.

## 6. Decision rule

```
accept:        median half-spread > 5.0bp on BOTH estimators
               -> costs.slippage_model is optimistic; DR-004 is revisited
reject:        median half-spread <= 5.0bp on BOTH estimators
               -> the spread component alone does not exceed the assumption. This does NOT
                  ratify the 5bp value and may NOT be used to advance costs.slippage_model
                  from `assumed`, for the reason in section 3.
inconclusive:  the estimators fall on opposite sides of 5.0bp, or either produces negative
               estimates on more than 25% of instrument-months
```

The 25% negative-rate branch is a refusal to report a number the estimator is not entitled to
produce, and it is fixed here rather than judged after seeing the rate.

## 7. Stopping rule

One pass over the store as it stands on the run date. No re-running with a different window,
aggregation period, or liquidity rule after seeing the result. If the store later grows, that is a
new study with a new id, not a re-run of this one.

## 8. Sample

```
minimum:     200 eligible instruments, each with >= 12 monthly estimates
if not met:  report the coverage achieved and refuse the verdict
```

200 mirrors `validation.backtest_min_trades`'s order of magnitude without borrowing it — that
parameter counts trades and this counts instruments, and reusing the number would imply a
correspondence that does not exist.

## 9. What would refute this

A median half-spread at or below 5bp on both estimators across the eligible universe.

It would **not** show that `DR-004` is right. Spread is the floor of transaction cost, not the whole
of it, and the gap between the two is exactly what `M74-T1110` (`Проверка реального
проскальзывания`) asks a forward test to measure. A refutation here narrows the open question to
impact and timing; it does not close it.

## 10. Amendments

None.
