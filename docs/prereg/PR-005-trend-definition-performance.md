# PREREG: Do the trend definitions' populations behave differently, net of costs?

```
id:      PR-005
date:    2026-08-02
author:  owner
status:  registered
blocked: backtest harness (being built to this specification)
```

## 0. Refutation-family check

- **searched:** `docs/prereg/` (PR-001, PR-002), `docs/decisions/`, `registry/parameters.yml` for
  prior trend work.
- **found:** **PR-001, reported 2026-08-02, REJECT.** The four runnable definitions select
  substantially different populations — no pair cleared the accept bar, four of six cleared the
  reject bar, and `STRUCTURE` overlaps the moving-average definitions by roughly a third.
- **distinct because:** PR-001 asked *whether* the populations differ and answered yes. This asks
  *whether the difference matters to outcomes*. It is the study PR-001's reject branch explicitly
  requires before `screen.trend_definition` may be set, and it could not have been run first —
  without PR-001 the honest move would have been to pick a definition on convenience.

This is the second study in the trend family. If it also fails to separate the definitions, the
family is closed and `screen.trend_definition` becomes an owner preference recorded as such, not a
validated choice.

## 1. Question

Holding everything else identical, does gating the same entry trigger on a different trend
definition change the distribution of trade outcomes?

## 2. Hypothesis

At least one definition's gated population produces a mean R per trade, net of costs, that differs
from the ungated population by more than sampling noise — and the ordering among definitions is
stable across a cost stress and a held-out period.

The null is not "trend filters do nothing". It is the more likely and more useful failure: **the
definitions differ in *which* instruments they select (PR-001 established that) and not in *what
those instruments then do*.** Under the null, PR-001's finding is real and irrelevant.

## 3. Prediction

Five arms over the same universe, same trigger, same exits, same sizing, same costs. **Only the
gate differs.**

| Arm | Gate |
|---|---|
| `NONE` | trigger only, no trend filter — the reference |
| `A` | `ABOVE_LONG_MA` |
| `B` | `MA_STACK` |
| `C` | `PRICE_AND_STACK` |
| `D` | `STRUCTURE` |

**If TRUE:** at least one gated arm's mean R differs from `NONE` beyond the bootstrap interval, and
the arm ordering by mean R is the same under 1× and 3× costs and in the holdout period.

**If FALSE:** all arms sit within the interval of `NONE`, or the ordering reshuffles between cost
regimes or between periods — which would mean the ordering is noise wearing a rank.

`NONE` is the load-bearing arm. Comparing four filters only to each other can rank them without
establishing that any of them beats not filtering at all, and a ranking of four things that are all
worse than nothing is not a finding worth adopting.

## 4. Data

```
universe:      DR-003 liquidity rule (price >= 5.00, 20d ADTV >= 5,000,000, history >= 250),
               applied per session, point-in-time
sample:        seeded random draw from the NASDAQ Trader directory, seed recorded
window:        the sessions common to the admitted universe; minimum 2000
split:         first 70% of sessions = primary, last 30% = holdout. Nothing is FITTED on
               either - see section 5 - so the holdout exists to test the STABILITY of a
               conclusion, not to validate a fitted parameter.
costs:         commission and slippage, values in section 5, stressed at 3x
survivorship:  ABSENT. Material here in a way it was not for PR-001: this study measures
               outcomes, and instruments that delisted are missing from the outcome
               distribution. Delisting is not independent of trend. Recorded on the
               evidence record; the result may not be reported without it.
```

## 5. Method

Everything below is fixed now, before the harness exists.

```
trigger:       close > the highest high of the prior 20 sessions (M35-T0527,
               "Пробой 20-дневного максимума"). Course-sourced, and identical in every
               arm.
gate:          the arm's trend definition, evaluated on the SAME session as the trigger
entry:         next session's open. Never the signal bar's close - a decision made on
               bar T executes at T+1 or it is look-ahead.
stop:          entry - 2.0 x ATR(14) at the signal bar. Fixed at entry; no trailing.
               Trailing is a separate unregistered choice and adding it here would
               compare five gates through six exit rules.
time exit:     close of session 20 after entry, if the stop has not been hit
gap handling:  a gap through the stop fills at the open, and the loss recorded is the
               ACTUAL loss, not -1R. Assuming -1R on gaps is the single most common way
               a backtest flatters itself.
sizing:        fixed 1R risk per trade; outcomes are R-multiples. No portfolio
               constraints, no position cap, no correlation limit - each signal is an
               independent trade. This is a deliberate simplification and it means the
               result says nothing about a portfolio.
costs:         commission 0.005 USD/share both sides; slippage 5 bps of price both
               sides; stress arm at 3x both
statistic:     mean R per trade, net. Reported with median R, hit rate, mean MFE, mean
               MAE and holding period, per arm.
comparison:    difference in mean R between each gated arm and NONE, against a seeded
               bootstrap (10,000 resamples) of that difference under the null
```

**Nothing is fitted.** No parameter is chosen by looking at outcomes: the trigger is course-sourced,
the exits and costs are declared here, and the gates come from PR-001. That is why there is no
train/validation split — there is nothing to hold out from. The holdout in §4 tests whether a
*conclusion* survives a period it was not drawn from, which is a weaker and different claim, and it
is labelled as such.

**Multiple comparisons.** Four arms against `NONE`, plus a six-way ordering. With four comparisons
at a conventional threshold, one spurious result is roughly a coin flip. This study does not correct
for that; it requires the effect to reproduce under cost stress **and** in the holdout, which is a
stricter and more interpretable filter than an adjusted p-value on a single pass.

## 6. Decision rule

```
accept:        at least one arm's mean-R difference from NONE lies outside the 95%
               bootstrap interval, AND that arm keeps its rank under 3x costs, AND it
               keeps its rank in the holdout
reject:        every arm sits inside the interval of NONE under 1x costs
inconclusive:  an effect appears at 1x costs but vanishes under stress or reverses in
               the holdout - report it as unstable, adopt nothing
```

An `accept` licenses setting `screen.trend_definition` to that arm with provenance
`validated:<evidence-id>`. Nothing weaker does.

## 7. Stopping rule

One run per cost regime over the fixed window. No re-running with different exits, a different
trigger, or a different holding period after seeing the result — each of those is a new study
needing its own registration, and running them and reporting the best is the data snooping the
course prohibits.

## 8. Sample

```
minimum:     200 trades per arm in the primary period, and 60 in the holdout
if not met:  report the trade counts and refuse the verdict for the arms that fall
             short. An arm with 40 trades is not a quiet failure, it is a reported one.
```

## 9. What would refute this

Every arm's mean R inside `NONE`'s bootstrap interval. That would mean the trend filters partition
the universe (PR-001) without changing what the selected instruments subsequently do — the
definitions differ, and the difference is decorative.

It would **not** mean trend is meaningless. It would mean these four definitions, gating this
trigger, with these exits, on this universe, do not separate outcomes. Every clause in that sentence
is a limitation of the study, not a fact about markets.

## 10. Amendments

None.
