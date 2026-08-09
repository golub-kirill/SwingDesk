# PREREG: Does the base strategy have positive expectancy net of MEASURED costs?

```
id:      PR-007
date:    2026-08-05
author:  owner
status:  registered
blocked: a re-fetch. The window below is ten years; data/bars.duckdb holds two.
```

## 0. Refutation-family check

- **searched:** `docs/prereg/` (PR-001, PR-002, PR-005 and their reports), `docs/decisions/`
  (DR-003, DR-004, DR-005), `registry/criteria.yml` Track B.
- **found:** **PR-005, reported 2026-08-03, REJECT.** Its `NONE` arm is this exact strategy and it
  was measured: **+0.028R per trade at 1× costs, −0.123R at 3×.** Also **DR-005, 2026-08-05**, which
  measured slippage at 25bps per side against DR-004's assumed 5.
- **distinct because:** PR-005 asked whether four trend gates separate outcomes *from each other and
  from no gate*. It answered no, and the `NONE` arm was its reference rather than its subject. This
  asks a different question about that reference arm — whether it clears `b.expectancy` at the cost
  vector that was actually measured. PR-005 could not answer it, because its costs were assumed and
  its two cost regimes bracket the measured vector without landing on it.

**The uncomfortable part, stated rather than hidden.** The direction is close to known before this
runs: DR-005 established that the 3× column is the operative one, and that column is negative. A
study whose sign is already indicated is worth running only for what it adds, and what it adds is
specific: **a confidence interval at the actual cost vector.** `b.expectancy` is ratified as
`E[R] > 0, CI excludes 0` and `k.strategy_rejected` needs a CI, not a point estimate. Reading a
verdict off a column that was charged at a different cost vector would be inference, not measurement.

This is **not** a new lever, a re-tune, or a variant of a refuted idea. Nothing about the strategy
changes. One input — the cost model — moves from assumed to measured, and it moves because it was
measured, not because the previous answer was unwelcome.

## 1. Question

With every rule identical to PR-005's `NONE` arm and only the cost model replaced by the measured
one, is the base strategy's expectancy net of costs positive?

## 2. Hypothesis

Mean R per trade, net of measured costs, is greater than zero, with a bootstrap confidence interval
excluding zero — the condition `b.expectancy` ratifies.

The null is the live possibility and the one the evidence so far points at: **expectancy is negative
once the spread is charged at what it was measured to be**, and the +0.028R at 1× was an artefact of
a slippage assumption five times too low.

## 3. Prediction

One arm. No gates, no variants — the strategy PR-005 called `NONE`.

**If TRUE:** the 95% bootstrap interval on mean R lies entirely above 0 at the measured cost vector,
and does not sign-flip under the 3× stress of that vector.

**If FALSE:** the interval lies entirely below 0, or straddles it.

Reported at both the measured vector and 3× that vector, the same two-column discipline DR-004
consequence 2 requires, so this study cannot be quoted at whichever level flatters it.

## 4. Data

```
universe:      DR-003 liquidity rule (price >= 5.00, 20d ADTV >= 5,000,000, history >= 250),
               applied per session, point-in-time
sample:        the SAME 68 instruments PR-005 admitted, recorded in
               results/PR-005.json, seed 20260802. Reused deliberately: a new draw would
               change the population and the cost model at the same time, and the study
               would no longer isolate the cost change.
window:        2016-08-01 -> 2026-07-31, identical to PR-005. Comparability is the whole
               point; a shorter window would confound "measured costs" with "different
               period".
snapshot:      a knowledge_time at or after the re-fetch, recorded in the result
costs:         commission 0.005 USD/share both sides (DR-004, still ASSUMED - unchanged
               and not measured by DR-005)
               slippage   25 bps of price both sides (DR-005, MEASURED)
               stress arm at 3x BOTH components, i.e. 0.015/share and 75bps
survivorship:  ABSENT, and material exactly as it was for PR-005 - this measures outcomes,
               and delisted instruments are missing from the outcome distribution.
               `b.survivorship_caveat` is ratified and mandatory: the result may not be
               reported without its marker.
```

**The cost vector is mixed provenance, and that is the study's main limitation.** Slippage is
measured; commission is still an assumed retail rate with no broker chosen. A result here is only as
good as the commission assumption, and `DR-004` should be read alongside it.

## 5. Method

Identical to PR-005 §5 in every respect except costs. Restated in full, because a pre-registration
that says "as before" is not one:

```
trigger:       close > the highest high of the prior 20 sessions (M35-T0527)
gate:          none
entry:         next session's open
stop:          entry - 2.0 x ATR(14) at the signal bar. Fixed at entry; no trailing.
time exit:     close of session 20 after entry, if the stop has not been hit
gap handling:  a gap through the stop fills at the open, and the loss recorded is the
               ACTUAL loss, not -1R
sizing:        fixed 1R risk per trade; outcomes are R-multiples. No portfolio
               constraints - each signal is an independent trade, so the result says
               nothing about a portfolio
statistic:     mean R per trade, net. Reported with median R, hit rate, mean MFE, mean
               MAE and holding period
interval:      seeded bootstrap, 10,000 resamples, 95%, on mean R
```

**Nothing is fitted, and nothing may be tuned.** The one changed input is declared above and was
fixed by a decision record written before this file.

## 6. Decision rule

```
accept:        the 95% bootstrap interval on mean R lies entirely ABOVE 0 at the measured
               cost vector
reject:        the interval lies entirely BELOW 0 at the measured cost vector
inconclusive:  the interval straddles 0
```

An `accept` licenses nothing on its own — `b.deflated_sharpe`, `b.benchmark_relative` and
`b.era_stability` are all ratified and none is evaluated here.

### Two limitations of this rule, both worth recording

**1. This study cannot fire `k.strategy_rejected`, and the criterion is not operationally defined.**
Its trigger reads *"After `b.min_sample`, the expectancy CI lies entirely below the benchmark"*.
Two problems:

- `b.min_sample` is 100 closed trades `measured_by: journal, per strategy and version`. A backtest
  journals nothing, so on a literal reading no backtest ever satisfies it. Whether Track B criteria
  evaluate on backtest trades or only on journalled ones is **not stated anywhere**, and it should
  be — it decides whether this study is evidence about a card or merely about a hypothesis.
- The trigger compares an **expectancy CI** to **the benchmark**, where `b.benchmark_relative`
  defines the benchmark as buy-and-hold on the same universe. Mean R per trade and a buy-and-hold
  return are different units, and no document says how one is made comparable to the other. A
  per-trade R expectancy has no horizon; a buy-and-hold return has nothing else.

Both are flagged for the owner. This study reports its interval against **zero**, which is
`b.expectancy`'s own stated condition and needs no conversion.

**2. `inconclusive` is a real outcome here**, not a courtesy. At 68 instruments the interval may
straddle zero even if the mean is clearly negative, and reporting "negative" from a straddling
interval is the error this rule exists to prevent.

## 7. Stopping rule

One run at the measured vector and one at 3× it, over the fixed window and the fixed sample. **No
re-running at a third cost level after seeing the result** — the cost vector is now measured, and
trying others until one produces a positive expectancy is data snooping with a respectable-looking
input.

If the re-fetch cannot reproduce PR-005's 68 instruments, the study reports which are missing and
proceeds on the intersection, disclosing the count. It does not substitute replacements.

## 8. Sample

```
minimum:     200 trades at the measured cost vector
if not met:  report the trade count and refuse the verdict
```

200 matches PR-005's primary-period minimum, so the two are comparable. `b.min_sample`'s 100 is a
different quantity measured on a different thing — see §6.

## 9. What would refute this

A bootstrap interval on mean R lying entirely above zero at 25bps per side. That would mean the
strategy survives its measured spread, and that DR-005's reading of PR-005 — that the 3× column was
the operative one — understated the strategy.

It would **not** mean the strategy is fit to trade. `b.deflated_sharpe` carries the cumulative trial
count across the whole programme, `b.benchmark_relative` is unevaluated, survivorship is absent and
biases this upward, and the commission half of the cost vector is still assumed.

## 10. Amendments

**2026-08-08 — one of §6's two open questions is answered.** Appended, not edited: §6 stands as
written and this records what changed after it.

`criteria.yml` **v1.1.0** settles the first: **Track B evaluates on journalled trades only.** A
backtest is evidence about a hypothesis, never about a strategy card.

The consequence for this study is that it can report a verdict on its **hypothesis** and cannot
advance or reject a **card**. That is not a weakening — it is what this pre-registration already
said in §6, now backed by a ratified criterion rather than by a literal reading of one field.
`k.strategy_rejected` remains unfirable until real trades exist.

§6's second question — how an expectancy CI in R is made comparable to a buy-and-hold benchmark —
is **not** answered. `EXPECTATION_SPEC.md` §5 shows the conversion needs a horizon and an exposure
assumption, both portfolio quantities, and the portfolio layer does not exist. That criterion stays
inert for a second, independent reason.

**No data has been seen.** This study has not run, so this amendment does not downgrade it to
exploratory (`PREREG_TEMPLATE.md` §3.3).
