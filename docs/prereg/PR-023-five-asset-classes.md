# PREREG: five asset classes, each held above its ten-month average and in T-bills below — more per unit of risk than SPY?

```
id:            PR-023
date:          2026-09-14
author:        Claude, choosing what to measure next under the owner's "продолжай" of
               2026-09-14 (AGENTS.md 14: what to measure is the agent's, a ratification is the
               owner's). Owed by PR-022, whose one index could not read +/-0.38 of Sharpe and
               whose own not-run list named Faber's five asset classes as where the evidence is
status:        registered
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md`. The censuses live in `HANDOFF.md` §2 and are
not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-013`..`PR-021`, `EVIDENCE_SUMMARY` §20–§21 | selection, exit, sizing and reversal on US stocks against `SPY` | the index won |
| `PR-022` | Faber's ten-month rule on `SPY` alone, cash in `BIL` | `INCONCLUSIVE` — Sharpe 0.625 against 0.615 at rf = 0, **−0.027 [−0.401, +0.343]** on the excess over `BIL` (its addendum); worst drawdown −26.9% against −55.2% |

**distinct because every study above held one asset class.** Twenty-two studies bought US equities
and nothing else; `PR-022` timed the one index. This holds five classes that do not move together —
US and foreign stocks, Treasuries, real estate, commodities — which is where the published evidence
for trend rules lives (Faber 2007's headline test; Hurst, Ooi & Pedersen 2017, a century across many
markets). The rule is `PR-022`'s, so the family is the same; the question is the one its §6a named
as not run, and `PR-022` was not refuted — it could not see.

**What is known in advance, stated first.** The window's history is public and known to the author:
over 2007–2026 US stocks beat foreign stocks, real estate and above all commodities by wide margins,
and 2022 took stocks and bonds down together. **That history biases against both books here**, and
the study cannot be blind to it. What no file here holds is either book's measured return,
drawdown or Sharpe; the power estimate read widths and construction only.

## 1. Question

From June 2007 to September 2026, does a book holding a fifth each of `SPY`, `EFA`, `IEF`, `VNQ` and
`DBC` — each fifth in `BIL` while that asset's month-end close is at or below the mean of its last
ten, rebalanced at each month's first open and charged `DR-005` — earn a higher Sharpe ratio on its
excess return over `BIL` than holding `SPY`?

## 2. Hypothesis

**H1.** `TIMED_5`'s excess-Sharpe difference against `SPY` has a 95% interval wholly above zero.

**H0.** It does not.

**A second arm, registered and counted, never carrying the verdict:** `HOLD_5`, the same five a fifth
each, rebalanced monthly and never timed. It says what diversification does without the rule, so
that a result for `TIMED_5` can be told apart from one for the mix.

No parameter is concerned and no card exists.

## 3. Prediction, stated numerically before the run

```
primary quantity:  Sharpe(TIMED_5 - BIL) - Sharpe(SPY - BIL), daily, net of DR-005, x sqrt(252),
                   2007-06-01 .. 2026-09-11
predicted:         INCONCLUSIVE for TIMED_5: the power estimate puts its interval at 0.755 wide,
                   so the sign reads only beyond about +/-0.38, and the published improvement of a
                   trend rule on a diversified book is of that order in the long samples and
                   smaller in this one. Centre of the prediction: -0.10 to +0.20. For HOLD_5, whose
                   interval is 0.353 wide: REJECT or NULL - the known history of these five against
                   US stocks since 2007 points below SPY. Centre: -0.30 to 0.00. Both centres are
                   the author's reading of public history, not of this store
if H1 were TRUE:   TIMED_5's interval wholly above zero - a difference above about +0.38
minimum detectable effect:  0.38 in Sharpe for TIMED_5 and 0.18 for HOLD_5 - the predicted
                   half-widths, from tools/power_pr023.py (PR-023-power.json): the verdict
                   estimator's own bootstrap on 4,851 sessions. Widths only; nothing is held out
power floor:       0.40 end to end, the value PR-022 fixed; it gates NULL only
```

```bash
PYTHONPATH=$PWD/src python tools/power_pr023.py --report
```

| arm | in risk assets | traded a year | `DR-005` cost, points a year | asset switches a year | width, registered window | width, last 48 months |
|---|---|---|---|---|---|---|
| `TIMED_5` | 60.2% | 3.73 | 0.93 | 9.87 | **0.755** | 1.430 |
| `HOLD_5` | 100% | 0.30 | 0.08 | — | **0.353** | 1.212 |

**`HOLD_5` is readable at the floor and `TIMED_5` is not.** The held mix moves with its parts every
day, so its difference from `SPY` is steady; the timed book is in cash 40% of the time on average
and differs from `SPY` in bursts. So `NULL` is reachable for the mix and not for the rule, and a
`TIMED_5` verdict reads only a large effect's sign.

**Why the excess over `BIL` and not `stats.sharpe_convention`'s rf = 0.** `PREREG_TEMPLATE` §5 allows a
study its own convention if it says so and why. A book holding T-bills 40% of the time is paid their
yield, and rf = 0 counts that yield as reward for risk; `PR-022`'s difference turned from +0.011 to
−0.027 when it was removed. The rf = 0 reading is reported beside the primary.

## 4. Data

```
store:         SPY, EFA, IEF, VNQ, DBC and BIL daily bars and corporate actions in one pull by
               tools/fetch_history.py (period max) - SPY from 1993, EFA 2001, IEF 2002, VNQ 2004,
               DBC 2006-02, BIL 2007-05-30. Two splits, EFA 2005-06-09 and BIL 2017-11-30, both
               already applied by the vendor to prices and dividends, so neither is applied again
as_of:         2026-09-14T13:10:56.533619+00:00 - that pull's knowledge_time
window:        2007-06-01 - the first session after the first month-end at which all five have
               ten month-ends behind them and BIL prices the next open - to 2026-09-11: 19.28
               years, 232 months
window rationale: the question is about what diversification and a trend exit do through regimes,
               and the last 48 months hold neither a slow bear market nor a crisis in which the
               asset classes parted - 2008 is the case the rule is known for and 2022 the case
               where stocks and bonds fell together. AGENTS.md 19.4's first reason. The last 48
               months are read beside it as a diagnostic
country:       USA - US-listed funds; EFA holds developed markets outside the US
survivorship:  none - six funds, all trading throughout
adjustment:    total return: split-adjusted prices, dividends added on their ex-dates to whoever
               held at the prior close
costs:         DR-005, 25 bps a fill (costs.slippage_model) on every unit sold or bought at a
               rebalance. Many times these funds' own spreads, so it leans against both arms;
               commission zero, regulatory fees excluded
```

## 5. Method

* **Signals.** Each asset, at each month's last session: its close against the mean of its own last
  ten month-end closes. A month with no close decides nothing for that asset.
* **Targets.** `TIMED_5`: a fifth in each asset above its average, the fifth of each asset at or
  below it in `BIL`. `HOLD_5`: a fifth in each, always.
* **Execution.** On the first session after each month-end the book earns the night with the weights
  it drifted to — a dividend whose ex-date is that session belongs to the prior close's holder —
  trades to the targets at the open, paying one `DR-005` fill on every unit bought or sold, and earns
  open to close with the targets. Other sessions are close to close with drifting weights. Both arms
  and `SPY` are bought at the open of 2007-06-01 for nothing.
* **The statistic.** Each book's daily return minus `BIL`'s daily total return; the Sharpe ratio of
  that excess, ×√252; the difference, arm minus `SPY`; a 95% moving-block bootstrap of the paired
  excess returns, block 63, 10,000 resamples, seed 20260915.

### 5a. The split, and what it buys

```
split:           none
split buys:      nothing is selected - two arms fixed here, both read, neither chosen - so a split
                 would halve nineteen years for a protection there is nothing to protect
                 (PREREG_TEMPLATE 7)
perturbations:   cost_stress_3x - each arm at three times DR-005, read by section 6 on an ACCEPT
```

**Diagnostics, printed and never read by §6:** the rf = 0 difference; the difference at zero cost;
the arithmetic return difference with its interval; each book's CAGR, volatility and worst drawdown
with its dates; its share in risk assets, what it traded and the switches; every fall of `SPY`
deeper than 15% with each book's return through it and its recovery; each year's returns; each
asset's own CAGR and the months it sat above its average; everything again on the last 48 months.

## 6. Decision rule

**For each arm, by `run_pr022.branch_for`, in `PR-021`'s order**: `REFUSED` under 120 months;
`BOTH_NEGATIVE` if the interval is wholly above zero and the arm's own excess-Sharpe interval wholly
below; `COST_FRAGILE` if wholly above and the point at 3× `DR-005` is not above zero; `ACCEPT` wholly
above; `REJECT` wholly below; `INCONCLUSIVE` containing zero and wider than 0.40; `NULL` containing
zero inside it. **The study's `verdict:` is `TIMED_5`'s**; `HOLD_5`'s branch is reported beside it
and never replaces it. `NULL`, `BOTH_NEGATIVE` and `COST_FRAGILE` are reported under `INCONCLUSIVE`
with the branch named.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` (`TIMED_5`) — *five asset classes timed by their own trend earned more per unit of risk
  than `SPY`, net of costs, since 2007.* The next step is a card and paper trading.
* `REJECT` — *timing five classes by their trend earned less per unit of risk than holding `SPY`.*
* `INCONCLUSIVE` — *not established at a 0.38 half-width*; the path diagnostics are what is left.
* `NULL` (reachable for `HOLD_5` only) — *the mix earned what `SPY` did per unit of risk, within
  about 0.2.*

## 6a. Trials

**Two** — one per arm. The tool derives the cumulative figure: it read **121** before this
registration; two more take it to **123** and the hurdle from **2.597 to 2.603** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** risk-parity or volatility weights instead of fifths; bonds (`IEF`) as the
cash leg; other lookbacks or a band; Antonacci's dual momentum; leverage. Each is another
configuration.

## 7. Stopping rule

One pass, one pinned `--as-of`. No third arm, asset, weight, window or cost tried after the first
result is seen.

## 8. Sample

```
minimum:       120 months
power floor:   0.40 end to end on each arm's difference, gating NULL
if not met:    report the measurement and REFUSE to read the window as evidence
```

The window holds **232 months and 4,851 sessions**.

## 9. What would refute this

**H1 is refuted** by `TIMED_5`'s `REJECT` — or `NULL`, which the width makes unreachable.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* any unpriced holding — every fund must price every session it is held;
* either arm's width other than the power estimate's (0.755 and 0.353), or `TIMED_5`'s traded units a
  year other than 3.73 — the same books on the same series under the same seed must reproduce them;
* `HOLD_5` recording a switch, or a share outside risk assets.

**What would NOT settle anything:** a `TIMED_5` `ACCEPT` read as *diversified trend following works in
the future*. Nineteen years, a handful of regimes, five funds.

## 10. Amendments

None.
