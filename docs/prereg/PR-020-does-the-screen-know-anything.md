# PREREG: with the exit's cost out of the way, does the ratified screen know anything?

```
id:            PR-020
date:          2026-09-13
author:        Claude, owed by measure_universe_null (EVIDENCE_SUMMARY 20.7), which found the
               exit the largest cost of PR-019b's loss and the screen's own contribution not
               distinguishable from zero. Registered on the owner's ruling of 2026-09-13 that the
               question be answered rather than shelved, with the hold the power estimate can read
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
| `PR-015` | the net excess over `SPY` of a four-position book, five signals | `INCONCLUSIVE` — nothing separates from zero |
| `PR-016` | the ratified exit: ranked decile minus every liquid name, paired by month | `ACCEPT`, PRELIMINARY — +0.088R out of sample; both arms lose |
| `PR-018` | hold-only against the ratified exit on selected entries, 20 sessions | `INCONCLUSIVE` — beside it, hold-only on the selected decile +0.0404R against −0.1174R on every admitted name out of sample, unpaired and never read |
| `PR-019` | the hold and the stop on selected entries, twelve cells incl. no-stop at 10–60 | `INCONCLUSIVE` |
| `PR-019b` | `PR-019`'s candidate against `SPY` over each trade's own sessions | `INCONCLUSIVE` for precision — −0.1543R, wholly below zero |
| `measure_universe_null` | `PR-019b`'s loss decomposed against the admitted universe | exploratory — the exit loses to holding the universe; the screen ~+0.06R inside it |

**distinct because:** no study has read the selected decile HELD, with no stop, against **its own
admitted universe over the same sessions, paying the same slippage**. Every null so far was another
exit (`PR-016`..`PR-019`) or `SPY` (`PR-015`, `PR-019b`), and `PR-016`'s paired difference ran
both arms through the ratified stop and target, so the exit shaped both.

**What is known in advance, stated first.** The out-of-sample window is not fresh: `PR-019` read
its no-stop cells' LEVELS there at 10 to 60 sessions, and `measure_universe_null` read the
unselected pool gap there. **No file in this tree holds the 5-session no-stop cell's level, and
none holds the selected decile minus its universe at any hold** — the power estimate reports
dispersion only. So the trade leg at this hold is unread, and the difference is unread at any hold.

## 1. Question

On `PR-019`'s out-of-sample common entries — the top decile by the live `ByMarketPathStrength`,
spaced at 60 sessions, entered after 2021-12-31 — held **5 sessions with no protective stop**, does
the mean per-trade difference between the trade's net R and the equal-weighted admitted universe
over exactly that trade's sessions, charged the same slippage, in the trade's own R, lie above zero?

## 2. Hypothesis

**H1.** The out-of-sample mean of `trade net R − pool R` has an interval inside the power floor and
wholly above zero: over a week, the names the screen selects beat the universe they were selected
from.

**H0.** They do not.

No parameter is concerned. `screen.relative_strength_rule` and every `exit.*` stay where they are.
**No verdict moves anything**; what one licenses is in §6.

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean over trades of (trade net R - pool R over the trade's own sessions, the
                   pool charged DR-005's slippage on both fills), OUT OF SAMPLE only
predicted:         NULL - an interval containing zero, inside the floor. The nearest prior is
                   PR-018's unpaired +0.158R between the selected decile and every admitted name,
                   held 20 sessions with no stop; if that accrues evenly it is about +0.04R over 5,
                   below this study's minimum detectable effect. measure_universe_null's ~+0.06R at
                   60 sessions under a stop points the same way. Centre of the prediction: +0.00R
                   to +0.05R. These are the author's readings of other studies, not this store's.
if H1 were TRUE:   an interval wholly above zero, around +0.10R - a screen whose edge is front-
                   loaded into the first week, which a 20- or 60-session hold would dilute.
minimum detectable effect:  0.0704R - the predicted out-of-sample half-width of trade minus pool at
                   5 sessions, from tools/power_pr020.py (PR-020-power.json), in sample only, on a
                   25% instrument subsample, variance-components corrected, overlap-aware. A
                   normal approximation to the moving-block bootstrap, so a LOWER bound.
power floor:       0.15 R end to end on the out-of-sample difference interval - PR-017..PR-019b's
                   standard, unchanged.
```

```bash
PYTHONPATH=$PWD/src python tools/power_pr020.py --report
```

| no-stop hold, trade − pool | overlap lags | factor | predicted OOS half-width | readable at 0.075 |
|---|---|---|---|---|
| **5 sessions** | 0 | 1.000 | **0.0704** | **yes, by 0.0046** |
| 10 sessions | 0 | 1.000 | 0.0781 | no |
| 20 sessions | 0 | 1.000 | 0.1005 | no |
| 40 sessions | 1 | 1.163 | 0.1092 | no |
| 60 sessions | 2 | 3.911 | 0.1828 | no |

**The hold was chosen by that column and nothing else.** No level exists in the estimate
(`power_pr019.assert_no_effect_leaked`), so the choice could not have been made on the answer.
The first estimate sized `PR-019`'s four no-stop holds and none was readable; the half-width falls
with the hold, so the only direction that could reach the floor was shorter, and 5 was added.

**Two approximations, stated.** The estimate sized trade minus a ZERO-cost pool; the primary charges
the pool the trade's slippage, which shifts each trade's difference by its own round trip — a term
that varies with entry over risk and is not in the estimate. And at 5 sessions a 0.15R effect asks
the screen for a larger edge PER DAY than the same floor at 20: the floor is per trade, and a
shorter hold is easier to read and harder to pass.

**Calibration.** `PR-019`'s two points ran 6–8% wide; `PR-019b`'s miss was overlap, and at 5
sessions there is none to correct. **Readable, by 6%**: if the realised width exceeds 0.15R, §6
says `INCONCLUSIVE` and the report says it was a precision miss.

## 4. Data

```
store:         data/bars.duckdb, daily bars, series RAW
as_of:         2026-09-06T22:36:49.635786-05:00 - PR-019's instant, so section 9 reproduces it
window:        asked from 2016-01-04, as PR-016..PR-019b. MEASURED span reported beside it
country:       USA
universe:      DR-003's liquidity rule at each formation date's own bar
entries:       PR-019's common entry set exactly - the top decile by the LIVE ByMarketPathStrength
               at rs.lookback 126, formations every 20 sessions, SPACED at 60 sessions per name,
               restricted to the entries PR-019's binding cell realised (section 5)
survivorship:  ABSENT and material - but on BOTH legs: the pool is the same survivor universe the
               names are drawn from, so it inflates the difference far less than it did SPY's
adjustment:    split-adjusted, NOT dividend-adjusted - on both legs, which share a universe
costs:         the trade: 25 bps a side and $0.005 a share, DR-005. The pool: 25 bps a side, no
               commission - a basket has no single price to charge per share on, stated
split:         PR-019's - in sample = entries on or before 2021-12-31, printed and NEVER read;
               out of sample = after, the verdict
```

window rationale: the verdict is read only on entries after 2021-12-31 — about the most recent 56
months, `AGENTS.md` §19's current market to within two months. The window is `PR-019`'s because §9
reproduces `PR-019` before anything is read — §19.4's third reason, a replication of a committed
study. **It does not rest on "the intervals are too wide otherwise"**, which §19.4 refuses.

## 5. Method

* **The trade leg.** `h5_stopnone` — no protective stop, no target, 5 sessions; R denominated at
  `2.0 × ATR(14)` exactly as `PR-019`'s no-stop cells, so the difference is in the same units as
  every cell before it — under the ratified constant-risk sizing, net of `DR-005`. **No stop and no
  target, so no bar is ambiguous and `DR-042`'s unruled tie-break does not touch this study**: it is
  not PRELIMINARY for that reason.
* **The common entry set.** `PR-019` restricted every cell to the entries every cell realised; the
  4 ATR cells refused 5 that every other cell took, and dropped nothing. So the candidate is
  simulated beside `h60_stop4.0` and the intersection taken (`run_pr019.common_entries`).
* **The pool leg** (`measure_universe_null.pool_r`). Every name admitted at the trade's formation
  date, equal-weighted, over the trade's own sessions: bought at the entry session's OPEN — that
  session contributes its open-to-close return — then close to close, sold at the exit session's
  CLOSE, in the trade's own R: `(pool growth − 1) × entry price / initial risk per share`, charged
  25 bps on both fills (`run_pr020.pool_slipped`). A trade whose legs cannot both be priced is
  counted and reported, never dropped silently.
* **The statistic.** Per trade, `trade net R − pool R`; the mean over the window's trades; a 95%
  moving-block bootstrap over entry months, block 3, 10,000 resamples, seed 20260908 — `PR-016`'s.
  Formed before resampling, so the pairing is exact.
* **Nothing is selected**, so the split buys one thing: the entries were `PR-019`'s, whose cell was
  selected in sample, and reading only out of sample keeps any of that off the verdict.

**Perturbations**, each moving ONE thing against the primary:

* `pool_zero_cost` — the pool leg at zero cost, the trade unchanged: what the round trip alone costs
  the selected names against a free universe;
* `cost_stress_3x` — the TRADE at three times `DR-005`, the pool at the primary's 1×.

**Diagnostics, printed and never read by §6:** `SPY` over the same sessions, `PR-019b`'s question at
this hold; the tail — share below −2R and −3R and the worst excursion — beside the mean, because
`C-8`'s tail budget is unruled; and **the null's own check**: every admitted name held the same way
against the same pool, which should read close to zero (§9).

## 6. Decision rule

**Read on `h5_stopnone`, out of sample, primary null**, by `run_pr019b.verdict_for`, in this order:

```
REFUSED        fewer than 200 trades or 24 entry months out of sample (section 8).
INCONCLUSIVE   the difference interval is wider than the 0.15R power floor.
BOTH_NEGATIVE  the trade's own interval AND the pool leg's interval both lie wholly below zero.
               PREREG_TEMPLATE rule 8.
ACCEPT         the difference interval lies wholly ABOVE zero.
REJECT         the difference interval lies wholly BELOW zero.
NULL           the difference interval contains zero, inside the floor. Rule 10: the instrument was
               sharp enough and, at this precision, the screen's week is its universe's.
```

**The report's `verdict:` token** is `ACCEPT`, `REJECT`, `INCONCLUSIVE` or `REFUSED` — gate 3f's
vocabulary — and `NULL` and `BOTH_NEGATIVE` are reported under `INCONCLUSIVE` with the branch named
first in the same line, as `PR-017`'s powered null was.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *over a week, the names the ratified screen selects beat the universe they come from,
  net of the same slippage.* The screen knows something the exit has been giving away; the next
  study is the exit built around that week. **Not** that any strategy is profitable.
* `REJECT` — *over a week the selected names LOSE to their universe*: at this horizon the screen is
  anti-informative, the short-term reversal the literature documents.
* `NULL` — *any edge the screen has over a week is smaller than about 0.07R a trade.* Not a lever
  worth building on at this horizon; the research line moves to a different signal.

## 6a. Trials

**One** — `h5_stopnone`, chosen by the power estimate's precision alone. The partner cell and the
null's check re-evaluate configurations `PR-019` already counted and are not read by §6. The
cumulative figure and the hurdle are the tool's, never typed here:

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

## 7. Stopping rule

One pass, one pinned `--as-of`. No interim look, no early stop, no second hold or null tried after
the first is seen.

## 8. Sample

```
minimum:       200 trades AND 24 entry months out of sample
power floor:   0.15 R end to end on the out-of-sample difference interval
if not met:    report the measurement and REFUSE to read the window as evidence
```

`PR-019`'s no-stop cells realised **7,236 trades over 54 entry months** out of sample on this entry
set. Months bind, and §3's table is what they bind.

## 9. What would refute this

**H1 is refuted** by `REJECT` or `NULL`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* `h60_stop4.0` failing to reproduce `PR-019`'s committed cell on both windows — trades, mean net R
  and its interval, every digit. `run_pr020.reproduction` reads the committed file, so there is no
  second copy to drift. Same store instant, same construction; anything else is a defect here;
* **the null's own check** reading an observed mean further than **0.05R** from zero on either
  window. Every admitted name held the same way against the universe it makes up, charged the same
  slippage, can differ from it only by commission and weighting; a pool leg that failed this is
  wrong, and the verdict is not read;
* any trade without a pool price that the report cannot explain.

**What would NOT settle anything:** an `ACCEPT` read as *it works*. It says the screen selects;
whether a strategy can be built on a week is the next registration's question.

## 10. Amendments

None.
