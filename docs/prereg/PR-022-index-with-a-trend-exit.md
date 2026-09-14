# PREREG: held while above its ten-month average and in T-bills otherwise, does SPY earn more per unit of risk than holding SPY?

```
id:            PR-022
date:          2026-09-14
author:        Claude, on the owner's ruling of 2026-09-14 - "lets try this one" - choosing the
               index with drawdown control, after PR-021 closed short-term reversal and holding
               SPY had beaten every active construction this project measured
status:        registered
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md`, `REGIME_SPEC.md`, the course index for
`M77`. The censuses live in `HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-002` | whether a breadth regime label separates breakout outcomes | `INCONCLUSIVE`, corrected from `ACCEPT` — a label conditioning single-stock setups, never the index held or left |
| `PR-019b`, `EVIDENCE_SUMMARY` §20.6–§20.9 | the relative-strength family against `SPY` over the same days | the index won, per dollar, by every sizing |
| `PR-021` | short-term reversal against `SPY` | `REJECT` — the index won again |
| `M77-T1145` | the course names time-series momentum | an untested hypothesis; the index gives no rule |

**distinct because every study above traded single stocks and used `SPY` only as the thing to
beat.** None held the index itself and stepped out of it. `PR-002`'s classifier conditioned setups
on breadth; this conditions the whole book on the index's own trend. The family is empty here.

**What is known in advance, stated first — this is the most public study in the programme.** The
rule is published (Faber, *A Quantitative Approach to Tactical Asset Allocation*, 2006–2007) and the
window's history — 2008, 2020, 2022, 2025 — is known to everyone, the author included. What no file
here holds is the rule's measured return, drawdown and Sharpe on this store's total-return series at
`DR-005`'s cost. **The study cannot be blind.** Its protection is that the rule, the window, the
costs and the decision rule are fixed here before the run and none was chosen to fit that known
path: the rule is Faber's as published, the window starts where the cash fund's history does, and
the cost is the registry's.

## 1. Question

From June 2007 to September 2026, does holding `SPY` only while its month-end close is above the
mean of its last ten month-end closes — and a T-bill fund otherwise, switched at the next open and
charged `DR-005` — earn a higher Sharpe ratio, by `stats.sharpe_convention`, than holding `SPY`
throughout?

## 2. Hypothesis

**H1.** The Sharpe difference, timed minus held, has a 95% interval wholly above zero: stepping out
below the trend buys more than it costs, per unit of risk.

**H0.** It does not.

No parameter is concerned and no card exists for this. If H1 survives, the next step is a
component and a card, not a parameter.

## 3. Prediction, stated numerically before the run

```
primary quantity:  Sharpe(timed, net) - Sharpe(held), stats.sharpe_convention - daily total
                   returns, net of costs, rf = 0, x sqrt(252) - over 2007-06-01 .. 2026-09-11
predicted:         INCONCLUSIVE. The power estimate puts the interval's width at 0.759, so ACCEPT
                   needs a difference above about +0.38 and REJECT one below about -0.38. The
                   published record of trend rules on US equities puts the improvement near +0.1
                   to +0.3 in Sharpe, concentrated in one or two bear markets, 2008 above all -
                   the author's reading of published work (Faber 2007 and its updates; Hurst, Ooi
                   & Pedersen 2017, a century across many markets), not of this store. Centre of
                   the prediction: +0.05 to +0.25
if H1 were TRUE:   an interval wholly above zero - a difference above about +0.38, larger than
                   the published record for this rule on one index
minimum detectable effect:  0.38 in Sharpe - the predicted half-width, from tools/power_pr022.py
                   (PR-022-power.json): the verdict estimator's own bootstrap on 4,851 sessions.
                   Widths only; the study holds nothing out, so the estimate ran on the window
                   the verdict reads
power floor:       0.40 end to end, fixed in tools/run_pr022.py before the power estimate ran.
                   It gates NULL only, in PR-021's order
```

```bash
PYTHONPATH=$PWD/src python tools/power_pr022.py --report
```

| window | sessions | Sharpe difference width | return difference width, points a year |
|---|---|---|---|
| registered, 2007-06-01 .. 2026-09-11 | 4,851 | **0.759** | 10.95 |
| last 48 months, diagnostic | 1,002 | 1.191 | 16.80 |

Over the registered window the rule is invested **78.0%** of sessions and switches **32 times, 1.66 a
year**, which `DR-005` charges **0.83 points a year**.

**No width is readable at the floor, and that is written down before the data.** One index over
nineteen years cannot resolve a Sharpe difference the size the literature reports; the evidence that
does is a century and dozens of markets wide. So `NULL` is unreachable and the study reads only a
large effect's sign. **What it measures precisely is the PATH** — the rule's CAGR, its worst
drawdown, and what it did in every fall of the index deeper than 15% — reported beside the verdict
and never read by §6. They are one path, not a distribution: they carry no interval and are not a
forecast.

**Why not reach further back.** The store now holds `SPY` from 1993, but no cash fund before May
2007, and the years before the rule was published are the years it was designed on. The window
starts where both legs exist and the rule's design ends.

## 4. Data

```
store:         SPY and BIL daily bars and corporate actions, fetched by tools/fetch_history.py
               (period max) into a store of their own - SPY 8,462 bars from 1993-01-29 and 135
               dividends; BIL 4,853 bars from 2007-05-30, 127 dividends and one split
               (2017-11-30) the vendor had already applied to its prices and dividends, so it
               is not applied again
as_of:         2026-09-14T11:31:09.113665+00:00 - that pull's knowledge_time
window:        2007-06-01, the first session after the first month-end whose next month BIL
               covers, to 2026-09-11, the store's last session: 19.28 years, 232 months
window rationale: the question is about DRAWDOWNS, and the last 48 months hold one fall of the
               index deeper than 15%, early 2025. The registered window holds every such fall
               since the rule was published - AGENTS.md 19.4's first and fourth reasons, a regime
               the recent window lacks and an event rare enough that four years hold too few.
               The report counts them; the last 48 months are read beside it as a diagnostic
country:       USA
survivorship:  none - one index fund and one T-bill fund, both trading throughout. The first
               study here without that bias
adjustment:    total return on both legs: split-adjusted prices, and cash dividends added on
               their ex-dates to whoever held at the prior close
costs:         DR-005, 25 bps a fill (costs.slippage_model), and a switch is two fills. About
               twenty-five times SPY's own quoted spread and the registry's number, so it leans
               against H1 - by 0.83 points a year at the measured switching rate. Commission
               zero; regulatory fees excluded, which favours H1 negligibly
```

## 5. Method

* **The rule** (Faber 2007). At each month's last session, `SPY`'s close against the mean of its
  last ten month-end closes, the current one included. Above: hold `SPY` next month. At or below:
  hold `BIL`. Nothing after that close is read.
* **Execution.** A change of holding happens at the next session's open. That session, the old asset
  earns its overnight move and the dividend of an ex-date that day; the new one earns open to close;
  each side of the switch pays one `DR-005` fill.
* **Both books** bought at the open of 2007-06-01, neither charged for it: the question is how they
  differ from there.
* **The statistic.** Each book's Sharpe ratio on its daily total returns net of cost, the difference
  timed minus held; a 95% moving-block bootstrap of the PAIRED daily returns, block 63 sessions (a
  quarter: a monthly rule's exposure persists for months), 10,000 resamples, seed 20260914,
  percentile interval.

### 5a. The split, and what it buys

```
split:           none
split buys:      nothing is selected - one published rule, fixed here - so a split would halve
                 nineteen years and their handful of drawdowns for a protection there is nothing
                 to protect (PREREG_TEMPLATE 7)
perturbations:   cost_stress_3x - the timed book at three times DR-005. Section 6 reads its
                 point estimate on an ACCEPT only
```

**Diagnostics, printed and never read by §6:** the difference at zero cost; the arithmetic return
difference with its interval; each book's CAGR, volatility and worst drawdown with its dates; the
share of sessions invested and the switches; the break-even cost a fill; every fall of the held
index deeper than 15%, with the timed book's return through the fall and through the recovery and
its own worst drawdown inside; each year's return; the same readings over the last 48 months.

## 6. Decision rule

**Read on the registered window by `run_pr022.branch_for`, in this order:**

```
REFUSED        fewer than 120 months.
BOTH_NEGATIVE  the difference's interval lies wholly above zero AND the timed book's own Sharpe
               interval lies wholly below zero. PREREG_TEMPLATE rule 8.
COST_FRAGILE   the difference's interval lies wholly above zero and its point estimate at three
               times DR-005 is not above zero.
ACCEPT         the difference's interval lies wholly ABOVE zero.
REJECT         the difference's interval lies wholly BELOW zero.
INCONCLUSIVE   it contains zero and is wider than the 0.40 floor - the predicted outcome.
NULL           it contains zero, inside the floor. Rule 10. Unreachable at the predicted width.
```

**The floor gates `NULL` and not the sign**, as `PR-021` registered and for `PR-019b`'s reason: an
interval that excludes zero answers the sign whatever its width.

**The report's `verdict:` token** is `ACCEPT`, `REJECT`, `INCONCLUSIVE` or `REFUSED`; `NULL`,
`BOTH_NEGATIVE` and `COST_FRAGILE` are reported under `INCONCLUSIVE` with the branch named first.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *on `SPY` since the rule was published, stepping into T-bills below the ten-month
  average earned more per unit of risk than holding the index, net of costs.* The next step is a
  card and paper trading; one path is not a forecast.
* `REJECT` — *the trend exit cost more return than the risk it removed.*
* `INCONCLUSIVE` — *the risk-adjusted difference is not established at a 0.38 half-width.* The path
  diagnostics — how deep each book fell, and what each earned — are what is left to decide on, and
  they are one path.
* `NULL` — *any Sharpe difference is smaller than about 0.2.*

## 6a. Trials

**One.** The cumulative figure and the hurdle are the tool's, never typed here:

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

It read **120** before this registration; one more takes it to **121** and the hurdle from **2.594**
to **2.597** sd(SR).

**Registered as NOT run, each with its reason**, because each is another configuration:

* **the 200-session daily average** (Siegel's rule) — faster out of a crash and more switches;
* **twelve-month time-series momentum** — the form `M77` points at (Moskowitz, Ooi & Pedersen 2012);
* **a band around the average**, which trades whipsaws for lag;
* **other indices, or Faber's five asset classes**, which is where the published evidence is wide;
* **leverage while above the average**, which is a different claim altogether.

## 7. Stopping rule

One pass, one pinned `--as-of`. No interim look, no second rule, window, cost or cash fund tried
after the first result is seen.

## 8. Sample

```
minimum:       120 months
power floor:   0.40 end to end on the Sharpe difference, gating NULL
if not met:    report the measurement and REFUSE to read the window as evidence
```

The window holds **232 months and 4,851 sessions**.

## 9. What would refute this

**H1 is refuted** by `REJECT` or `NULL`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* any session the timed book held `BIL` without a price for it — the cash leg must be priced
  throughout;
* a switch count other than the power estimate's **32**, or a Sharpe-difference width other than its
  **0.759** — the same rule on the same series under the same seed must reproduce both to the digit;
* a split applied twice: `BIL`'s price must read about 91.5 in 2007 and in 2026.

**What would NOT settle anything:** an `ACCEPT` read as *this will protect the next crash*. Nineteen
years hold a handful of falls, each different, and the rule met each one at a month-end.

## 10. Amendments

None.
