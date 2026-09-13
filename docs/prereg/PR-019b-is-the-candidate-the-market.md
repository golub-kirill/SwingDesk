# PREREG: does `PR-019`'s candidate exit earn more than the index over exactly the same days — or is it the market's drift?

```
id:            PR-019b
date:          2026-09-13
author:        Claude, owed by STRATEGY_CONTRACT.md C-3 - §4's row "does the 4 ATR long-hold exit
               beat the MARKET over the same days, or is it drift" - and by PR-019's own report,
               which names the missing market null as the reason its +0.0202R no-selection
               reading cannot be interpreted. Written under the owner's standing instruction of
               2026-09-13 to work the open list end to end
status:        registered
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md`, `TODO.md` §§4–5, `STRATEGY_CONTRACT.md` §4.
The censuses live in `HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-013` | whether relative strength separates forward returns at all | `INCONCLUSIVE` — every gross interval contains zero |
| `PR-014` | the net excess over `SPY` of a rebalanced book, 20 to 252 sessions | `INCONCLUSIVE`, `EXPLORATORY` after A-3 |
| `PR-015` | the net excess over `SPY` of a four-position book held 20 sessions, five signals | `INCONCLUSIVE` — nothing separates from zero |
| `PR-019` | the hold and stop width on selected entries; selected `h60_stop4.0` in sample | `INCONCLUSIVE` — +0.0528R [−0.1106, +0.2234] out of sample; the same exit on every admitted name +0.0202R |

**distinct because:** every comparison with the index so far was a BOOK's periodic return against
the index's, at a fixed clock and with no stop. **No study has compared a TRADE, under a stop, with
the index over that trade's own sessions**, and none has done it for the one exit `PR-019` left
standing. The unit here is one trade in its own R, and the null is formed per trade.

**The out-of-sample window is not fresh, and that is stated before anything else.** `PR-019` read
this cell's LEVEL there. What it did not compute — and what no file in this tree contains — is the
index's return over the same trades, in their R. So half of this study's difference is known in
advance and half is not. Two consequences are fixed here rather than discovered:

* **`both_negative` cannot fire.** It needs the trade's own interval wholly below zero, and
  `PR-019` measured it containing zero.
* **An `ACCEPT` cannot say the candidate is profitable** — only that it is not the index. The
  trade's own interval stays `PR-019`'s, and the report prints it beside the verdict.

## 1. Question

On `PR-019`'s out-of-sample entries — the top decile by the live `ByMarketPathStrength`, spaced at
60 sessions, entered after 2021-12-31 — does the mean per-trade difference between the trade's net R
under `h60_stop4.0` and the same notional held in `SPY` over exactly that trade's sessions, in the
trade's own R, lie above zero?

## 2. Hypothesis

**H1.** The out-of-sample mean of `trade net R − market R` has an interval inside the power floor
and wholly above zero: the candidate earns more than the index over the days it is exposed.

**H0.** It does not — the index over the same days earned as much or more.

No parameter is concerned. `exit.atr_stop_multiple`, `exit.max_holding_period` and
`exit.target_r_multiple` stay the owner's, and the candidate stays a candidate (`STRATEGY_CONTRACT`
§4, row C-7). **No verdict moves anything.**

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean over trades of (trade net R - SPY R over the trade's own sessions, at zero
                   cost on the SPY leg), OUT OF SAMPLE only
predicted:         AT OR BELOW ZERO - H1 fails, and the verdict is NULL or REJECT. The trade leg
                   is PR-019's +0.0528R. The index leg is SPY's return over each holding, scaled
                   by entry / risk. A 4 ATR stop on a top-decile name sits roughly 10-15% below
                   the entry, so a 1% move in the index is 0.07R to 0.10R; by public record SPY
                   rose on the order of 5% a year over 2022-2025 after a 2022 drawdown, which puts
                   a ~60-session holding near +1% to +2% and the index leg near +0.07R to +0.20R.
                   Centre of the prediction: -0.05R to -0.10R. The multiples and the index path
                   are the author's estimates, not the store's - the power estimate reports no
                   level and the out-of-sample SPY leg has not been computed.
if H1 were TRUE:   an interval wholly above zero, around +0.10R - the selection and the exit
                   together out-earning the index's drift over the same exposure.
minimum detectable effect:  0.0743R - the predicted out-of-sample half-width of trade minus
                   benchmark, from tools/power_pr019b.py (PR-019b-power.json), in sample only, on
                   a 25% instrument subsample, variance-components corrected. A normal
                   approximation to the moving-block bootstrap, so a LOWER bound.
power floor:       0.15 R end to end on the out-of-sample difference interval - PR-017..PR-019's
                   standard, unchanged.
```

```bash
PYTHONPATH=$PWD/src python tools/power_pr019b.py --report --out docs/prereg/results/PR-019b-power.json
```

| series, `h60_stop4.0`, 1,220 in-sample trades over 50 months | in-sample half-width, corrected | out of sample, predicted | readable at the floor |
|---|---|---|---|
| trade − benchmark | 0.0772 | **0.0743** | **yes, by 0.0007** |
| trade alone | 0.1884 | 0.1813 | no |
| benchmark alone | 0.1497 | 0.1440 | no |

**Pairing with the market does what `PR-019` §3 said pairing two exits could not.** There, the
month-to-month variance of a difference between two exits was the market path acting differently on
each, and no pairing cancelled it. Here the market IS the thing subtracted: the between-month
variance of the difference is **0.078 against 0.462 for the trade alone**, a six-fold cut. That is a
statement about dispersion, not level, and it already says something: **most of what moves this
candidate from month to month is the index.**

**Calibration, both points from `PR-019`.** Its selected contrast was predicted at 0.137 and
realised 0.129; the trade alone, predicted here at 0.181, realised 0.167 on the same trades out of
sample. The estimator ran about 6–8% wide at both points. **Readable, narrowly**: if the realised
width exceeds 0.15R, §6 says `INCONCLUSIVE` and the report says it was a precision miss.

## 4. Data

```
store:         data/bars.duckdb, daily bars, series RAW
as_of:         2026-09-06T22:36:49.635786-05:00 - PR-018's and PR-019's instant, so §9's
               reproduction runs on the identical store state
window:        asked from 2016-01-04, as PR-016..PR-019. MEASURED span reported beside it
country:       USA
universe:      DR-003's liquidity rule at each formation date's own bar
entries:       PR-019's exactly - the top decile by the LIVE ByMarketPathStrength at rs.lookback
               126, through `select`, formations every 20 sessions, SPACED at 60 sessions per name
survivorship:  ABSENT and material. It inflates the TRADE leg and not the index leg, so it biases
               the difference UPWARD - toward H1
adjustment:    split-adjusted, NOT dividend-adjusted - on both legs. SPY's dividend (~1.3% a year)
               is missing from the null, which also favours H1
costs:         the trade: 25 bps a side and $0.005 a share, DR-005. The SPY leg: ZERO in the
               primary, DR-005 symmetric as a perturbation (§5)
split:         PR-019's - in sample = entries on or before 2021-12-31, printed and NEVER read;
               out of sample = after, the verdict
```

window rationale: the VERDICT is read only on entries after 2021-12-31 — about the most recent 56
months, `AGENTS.md` §19's current market to within two months — and the older window is printed and
never read. The window is `PR-019`'s because §9 reproduces `PR-019`'s committed cells to every digit
before anything else is read, and the candidate was selected on that window's older half — §19.4's
third reason, a replication of a committed study. **It does not rest on "the intervals are too wide
otherwise"**, which §19.4 refuses.

## 5. Method

**One entry set, one exit, one null.**

* **The trade leg.** `h60_stop4.0` — `4.0 × ATR(14)` stop, no target, 60 sessions, stop checked
  first (`DR-042`) — on `PR-019`'s spaced entries, under the ratified constant-risk sizing (`RISK_SPEC`
  2, $1,000 a trade). Net of `DR-005`'s costs. Restricted to the entries the 1× and 3× books both
  realised (`run_pr019.common_entries`), and the loss reported.
* **The index leg** (`power_pr019b.market_r`, committed with the power estimate). The same notional
  in `rs.benchmark` = `SPY`, bought at `SPY`'s OPEN on the trade's entry session — the trade fills at
  that session's open — and sold at `SPY`'s CLOSE on the trade's exit session, expressed in the
  trade's own R: `(close / open − 1) × entry price / initial risk per share`. A trade whose legs
  cannot both be priced is counted and reported, never dropped silently.
* **The statistic.** Per trade, `trade net R − market R`; the mean over the window's trades; a 95%
  moving-block bootstrap over entry months, block 3, 10,000 resamples, seed 20260908 — `PR-016`'s.
  The difference is formed before resampling, so the pairing is exact by construction.
* **Nothing is selected**, so the split buys one thing: the cell was selected in `PR-019`'s
  in-sample window, and reading only the out-of-sample window keeps that selection off the verdict.
  The in-sample difference is biased upward by the selection and is printed, never read.

**Perturbations** — of `WALKFORWARD_SPEC` §4's six, cost is the one run, twice, each moving ONE thing
against the primary (`run_pr016.control_arm_for` records what happens otherwise):

* `benchmark_costed_1x` — the `SPY` leg charged `DR-005` symmetric with the trade: bought at
  `open × (1 + 25 bps)`, sold at `close × (1 − 25 bps)`, $0.005 a share on both sides;
* `cost_stress_3x` — the TRADE at three times `DR-005`, the `SPY` leg at the primary's zero.

**Registered diagnostic, printed and never read by §6:** the same exit on every admitted name
(`STRATEGY_CONTRACT` C-3's no-selection null) against the index — whether the EXIT alone is the
market, separately from the selection.

**What is not measured, said here rather than found later:**

* **beta.** The null holds the same NOTIONAL, not a beta-matched position. Top-decile momentum names
  plausibly run a beta above one, and in a rising market that excess reads as H1. With survivorship
  and the missing dividend, **three known biases point toward `ACCEPT` and none away from it** — so a
  `REJECT` or `NULL` is robust to them and an `ACCEPT` is the weakest of the outcomes;
* **the stop-out day.** The trade leaves at its stop intraday and the null at that session's close:
  a few hours' more index exposure on those days, stated rather than modelled;
* **the book.** One trade at a time, no cap and no capacity, as `PR-016`..`PR-019`.

## 6. Decision rule

**Read on `h60_stop4.0`, out of sample, primary null**, by `run_pr019b.verdict_for`, in this order:

```
REFUSED        fewer than 200 trades or 24 entry months out of sample (§8). The measurement is
               reported and not read.
INCONCLUSIVE   the difference interval is wider than the 0.15R power floor.
BOTH_NEGATIVE  the trade's own interval AND the index leg's interval both lie wholly below zero.
               PREREG_TEMPLATE rule 8. Unreachable here (§0), registered anyway.
ACCEPT         the difference interval lies wholly ABOVE zero.
REJECT         the difference interval lies wholly BELOW zero: the index over the same days
               earned more.
NULL           the difference interval contains zero, inside the floor. Rule 10: the instrument
               was sharp enough and, at this precision, the candidate IS the index.
```

The tests in `tests/test_run_pr019b.py` pin every branch and its boundaries. **The report's
`verdict:` token** is `ACCEPT`, `REJECT`, `INCONCLUSIVE` or `REFUSED` — gate 3f's vocabulary — and
`NULL` and `BOTH_NEGATIVE` are reported under `INCONCLUSIVE` with the branch named first in the same
line, as `PR-017`'s powered null was.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *on the current market, this candidate earned more a trade than the same notional in
  `SPY` over the same days.* **Not** that it is profitable: `PR-019`'s own interval contains zero and
  still does. **Not** beta-adjusted, and §5 says which way that cuts.
* `REJECT` — *the index over the same days earned more.* Under `STRATEGY_CONTRACT` C-3 a strategy
  that cannot beat its cheapest alternative is retired, and the candidate is.
* `NULL` — *at this precision the candidate is the index's drift.* Retired under C-3 as beta.

## 6a. Trials

**One** — `h60_stop4.0`, fixed before this study by `PR-019`'s in-sample rule. The no-selection
diagnostic re-evaluates a configuration `PR-019` already counted, against a new null, and is not
read by §6; it is not counted, as `PR-019`'s own no-selection arm was not. A reader who counts it
gets two. The cumulative figure and the hurdle are the tool's, never typed here:

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

## 7. Stopping rule

One pass, one pinned `--as-of`. No interim look, no early stop, no second null tried after the
first is seen.

## 8. Sample

```
minimum:       200 trades AND 24 entry months out of sample
power floor:   0.15 R end to end on the out-of-sample difference interval
if not met:    report the measurement and REFUSE to read the window as evidence
```

`PR-019` realised **7,236 trades over 54 entry months** out of sample for this cell. Months bind, and
§3's table is what they bind.

## 9. What would refute this

**H1 is refuted** by `REJECT` or `NULL`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* the trade leg failing to reproduce `PR-019`'s committed `h60_stop4.0` — **4,935 trades at +0.108R
  in sample, 7,236 at +0.0528R [−0.1106, +0.2234] out** — or the no-selection diagnostic failing to
  reproduce `PR-019`'s **31,320 at +0.102R and 46,687 at +0.0202R**. Same store instant, same
  construction; anything but every digit is a defect in this runner. `run_pr019b.reproduction` reads
  the committed file rather than these numbers, so there is no second copy to drift;
* any trade without a benchmark price that the report cannot explain. The power estimate found none
  in 1,220.

**What would NOT settle anything:** an `ACCEPT` read as *it works*. §0 says why it cannot mean that.

## 10. Amendments

None.
