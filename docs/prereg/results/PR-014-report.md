# PR-014 RESULT: the ratified twenty sessions is the WORST cell of twelve, and the horizon that works is six months

```
prereg:        PR-014
ran:           2026-09-06
verdict:       ACCEPT - H1, at 126 sessions, LONG-SHORT
tool:          tools/run_pr014.py
evidence:      PR-014.json
trials:        12, declared before the run
```

---

## Read this first

**The verdict follows the registered rule and the rule was written before the data.** It is still
weaker than the headline number, and one diagnostic is the reason: **the holdout window's exclusion
of zero survives at the registered block length and does not survive a doubled one.** That is
stated here, before the numbers, because a reader who takes +11.00% and stops has taken the part of
this result that is least robust.

## What ran

**9,544 instruments, 115 rebalance dates, 109 with a full cross-section.** Formation is the RATIFIED
selection rule and this is the first study in the repository to use it: `rs.lookback` **126**,
`rs.benchmark_form` **path**, scored by calling `decision_logic.ranking.ByMarketPathStrength` — the
live class — rather than reimplementing it (amendment A-2).

**Windows overlap** (amendment A-1, the owner's ruling). `K = horizon / 21` sub-portfolios formed 21
sessions apart, so every formation date contributes and `1/K` of the book turns per rebalance.
Inference is a moving-block bootstrap, block `max(K, 6)`, 10,000 resamples, seed `20260906`.

**Overlapping did not make turnover cheaper** and the tool asserts it: cost is `252 / horizon` full
turns a year whatever `K` is, two sides for a long-only book and four for a spread.

## The numbers

Annualised **net** excess over `rs.benchmark`, after `DR-005`'s 25 bps a side:

| horizon | K | arm | cost/yr | PRIMARY net | HOLDOUT net |
|---|---|---|---|---|---|
| **20** | 1 | long-only | 6.30% | **−3.41%** [−10.23, +9.23] | **−3.63%** [−11.40, +5.37] |
| **20** | 1 | long-short | 12.60% | **−6.94%** [−16.67, +9.24] | **−6.90%** [−25.38, +9.26] |
| 42 | 2 | long-only | 3.00% | +1.15% [−5.47, +14.06] | −1.12% [−7.65, +6.48] |
| 42 | 2 | long-short | 6.00% | +8.05% [−2.57, +23.62] | +3.35% [−11.42, +15.91] |
| 63 | 3 | long-only | 2.00% | +1.98% [−5.03, +15.48] | +0.33% [−6.21, +7.67] |
| 63 | 3 | long-short | 4.00% | +10.97% [−0.35, +28.10] | +9.24% [−2.71, +20.17] |
| 126 | 6 | long-only | 1.00% | +3.12% [−3.82, +14.74] | +1.39% [−5.18, +7.45] |
| **126** | **6** | **long-short** | **2.00%** | **+13.82% [+3.96, +27.11]** ✗ | **+11.00% [+0.24, +19.74]** ✗ |
| 189 | 9 | long-only | 0.67% | +2.07% [−3.39, +14.32] | +1.69% [−4.83, +6.83] |
| 189 | 9 | long-short | 1.33% | +9.62% [+1.87, +22.83] ✗ | +11.79% [−1.20, +21.24] |
| 252 | 12 | long-only | 0.50% | +1.14% [−2.22, +14.05] | +0.82% [−5.00, +4.72] |
| 252 | 12 | long-short | 1.00% | +7.44% [+4.99, +21.05] ✗ | +8.60% [−5.53, +18.62] |

✗ marks an interval excluding zero with the sample rule met.

## The verdict, arrived at by the registered rule

§6: *"the SHORTEST horizon whose primary-window net interval excludes zero"*, then read on the
holdout without re-selecting.

1. **Primary window, qualifying cells:** 126, 189 and 252 sessions, all long-short. No long-only
   cell qualifies at any horizon.
2. **Shortest of those: 126 sessions.**
3. **The 3× cost check.** Gross 15.82% against a stressed cost of 6.00% leaves **+9.82%**, positive
   as §6 requires.
4. **Holdout, same cell, not re-selected:** **+11.00% [+0.24, +19.74]**, excludes zero.
5. **The both-negative branch does not fire.** The registered control — buy-and-hold the whole
   admitted universe — is **−1.58%** on the primary window and **−4.27%** on the holdout, so the
   control is negative and the arm is not.

**ACCEPT.** The holding period that works is **126 sessions, about six months**, long-short.

## And the ratified twenty sessions is the worst cell in the grid

**−3.41% a year long-only and −6.94% long-short**, on both windows independently.
`exit.max_holding_period` = 20 is `assumed:DR-012` and has never been tested; at that horizon the
book turns 12.6 times a year and the cost — 6.30% or 12.60% — takes everything the signal produces
and more. The effect appears at 42–63 sessions and is significant at 126. It does not keep growing:
189 and 252 give lower point estimates and their holdout intervals include zero.

## The fragility, in full

**The holdout's lower bound is +0.24%.** Doubling the block length — a diagnostic, computed and
reported beside the registered figure rather than instead of it — moves it:

| window | registered block 6 | diagnostic block 12 |
|---|---|---|
| primary | [+3.96%, +27.11%] | **[+5.61%, +28.02%]** — still excludes zero |
| holdout | [+0.24%, +19.74%] | **[−1.15%, +18.61%]** — includes zero |

**The primary window is robust to it and the holdout is not.** The registered statistic is block
`max(K, 6)`, fixed before the run, and the verdict follows it — changing the statistic after seeing
the result would be the data snooping this study exists to avoid. But `max(K, 6)` at `K = 6` is
exactly one holding period, the shortest length that spans the dependence, and a longer block is
defensible. **The honest reading is that the primary window establishes the horizon and the holdout
confirms it weakly.**

## What the control changed, which was not what it was registered for

§6 put the control there for the both-negative branch. It answered a different question too.

**The equal-weighted admitted universe LOSES to `SPY`** — by 1.58% a year on the primary window and
4.27% on the holdout. So at 126 sessions the long-only arm's +3.12% against `SPY` is
**+4.70% against the universe it selects from**. The selection rule works; `SPY` over 2016–2026 is
what is hard to beat, and the long-only arm's interval against it still includes zero.

## What a LONG-ONLY system takes from this, which is the reading that matters here

**This system trades long only, and the headline above needs a short book it does not have.** The
long-only rows are the ones it can act on, and they say something smaller and usable.

**No long-only cell's interval excludes zero at any horizon.** The signal is not shown to beat
`SPY`, and this report does not claim it does.

**But the COST is arithmetic, not an estimate, and it is the whole difference between the rows:**

| horizon | long-only cost/yr | primary net | holdout net |
|---|---|---|---|
| **20 (ratified)** | **6.30%** | −3.41% | −3.63% |
| 63 | 2.00% | +1.98% | +0.33% |
| **126** | **1.00%** | **+3.12%** | **+1.39%** |
| 252 | 0.50% | +1.14% | +0.82% |

**A long-only book at 126 sessions pays 5.30 percentage points a year less than at 20**, for a gross
signal that no cell distinguishes from another. The point estimate goes from negative on both
windows to positive on both. That is not a proof the strategy works; it is a measured reason the
current setting is the most expensive of six, by a factor of six.

**And the control says the selection itself is not the problem.** The equal-weighted admitted
universe loses to `SPY` by 1.58% a year (primary) and 4.27% (holdout). At 126 sessions the top
decile's +3.12% against `SPY` is **+4.70% against the universe it selects from**. The ranking picks
better names than the pool it draws from; `SPY` over 2016–2026 is what neither beats.

**So the smallest complete thing available to a long-only system is the holding period**, and it
needs no new capability, no short book and no new data. `exit.max_holding_period` is 20,
`assumed:DR-012`, and it is the worst of the six tested. That is a parameter ruling and it is the
owner's.

## What this does NOT establish

**It does not validate `CARD-001`, and cannot.** `b.expectancy` and `b.min_sample` are
`measured_by: journal` (`criteria.yml` v1.1.0) and the journal holds one closed trade. §9 said this
before the run.

**Everything that works here needs a SHORT LEG the system does not have.** No long-only cell clears
zero at any horizon in the grid. `trade_management/portfolio.py` states the system is long-only,
`CARD-001` requires a stop below the entry, and `registry/broker_policy.yml` sends `side: buy`.

**Borrow is unpriced.** Fees, hard-to-borrow rates, Regulation SHO locates and the uptick rule are
all costs of the short leg and none is measured, so every net figure in the spread rows is a
**floor on the cost**. For a liquid quartile at six-month holds the fee is plausibly 0.3–1% a year,
which does not overturn +11% — but plausibly is not measured.

**Regulatory fees are excluded**, about 0.9% of the slippage term (`DR-039`), a bias against H1.

**Survivorship is absent and cuts BOTH ways here.** The directory is today's, so a loser that
delisted at a loss is missing — it would have been the sample's best short — and a winner acquired
at a premium is missing too. Both understate the spread. The long-only arm is biased the usual
flattering way and is reported as an upper bound.

**Ten years is ten years.** Overlapping windows lowered the variance of the estimate; they added no
independent decades, and §5b said so before the run.

## What would refute this

A horizon whose primary-window interval excludes zero and whose holdout does not, taken as
confirmation anyway. That is the failure this study's split exists to prevent, and the holdout
result above is one doubled block away from being that case.

## The verdict is applied by the tool, not by this page

`run_pr014.py` executes §6 and writes the outcome into `PR-014.json`. The rule is mechanical and was
fixed before the data, so a reader's judgement has no step to enter through — and the tool's
tie-break is deliberately **fail-closed**: §6 names a horizon and not an arm, so two arms qualifying
at the same shortest horizon returns `inconclusive` rather than a choice made after the run. Only
one arm qualifies here, so that branch does not fire.

The machine and this page agree: **ACCEPT, 126 sessions, long-short, +9.82% at 3× costs.**

## What it costs the programme

**12 trials, declared before the run.** `tools/trial_budget.py` reads them from this result's
`trials` field.

**`PR-014` §6a forecast "61 to 73" and both numbers were stale when it was written** — the
`short-leg` measurement's 8 trials had landed between the reading and the drafting. The actual move
is **69 to 81**, and the hurdle from 2.40 to **2.46 sd(SR)**. The pre-registration is not edited:
§6a was a forecast, and this is where the measured figure belongs.

## Reproducing

```bash
PYTHONPATH=$PWD/src python tools/run_pr014.py --data <store>
```

Every per-period series is committed in `PR-014.json` so the interval can be re-tested at another
block length without a thirty-five-minute re-run.
