# PREREG: on the entries the ratified screen selects, what holding period and stop width does the combination want — and does the best of them, chosen on the older market, survive the current one?

```
id:            PR-019
date:          2026-09-12
author:        Claude, at the owner's instruction 2026-09-08 - "Seems to me that max hold days
               must be researched and per strategy" - and owed by STRATEGY_CONTRACT.md C-7.
               Design ruled by the owner 2026-09-12: the full twelve-cell grid, the precision
               standard unchanged, and the long holds' predicted inconclusiveness written down
               before the run rather than discovered after it
status:        registered
verdict:       (not yet run)
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md`, `TODO.md` §§4–5. The censuses live in
`HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `measure_exit_surface` | expectancy over a stop × target grid, hold fixed at 20 | exploratory, and on **unselected** entries |
| `PR-014` | the REBALANCE horizon of a book, 20 to 252 sessions | `INCONCLUSIVE`, `EXPLORATORY` after amendment A-3 |
| `PR-016` | the ratified exit, screen against no screen | `ACCEPT`, PRELIMINARY — both arms lose money |
| `PR-017` | a partial exit at 1R | a powered null |
| `PR-018` | the ratified exit against holding to the clock, at 20 sessions | `INCONCLUSIVE` — holding earns +0.0404R out of sample and runs 21.7% of trades below −2R |

**distinct because:** no study has ever varied the **per-trade hold on selected entries**.
`PR-014`'s unit is a book's periodic return and its horizon is how often the book turns, not how long
a trade is held under a stop; `PR-018` held the clock at 20. **And the stop width has never been
varied on selected entries either** — `measure_exit_surface` varied it on every admitted name.

## 1. Question

On the top decile by the live `ByMarketPathStrength`, across holds of **10, 20, 40 and 60 sessions**
and stops of **2.0 ATR, 4.0 ATR and none** — no target in any cell — which cell earns the highest mean
net R **without a fatter left tail than the ratified exit**, chosen on entries up to 2021-12-31; and
does that cell, read **only on entries after it**, earn more than the ratified exit and more than
zero?

## 2. Hypothesis

**H1.** The selected cell's out-of-sample mean net R exceeds the ratified exit's on the same entries
(the paired interval lies above zero), its own out-of-sample mean net R interval lies above zero, and
its out-of-sample share of trades below −2R stays within sampling noise of the ratified exit's.

**H0.** It does not.

The parameters concerned are `exit.max_holding_period` (20, `assumed:DR-012`),
`exit.atr_stop_multiple` (2.0, `DR-012`) and `exit.target_r_multiple` (1R, `DR-029`). **No verdict
moves any of them** (§6).

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean net R, SELECTED CELL minus RATIFIED, paired on entry months, read OUT
                   OF SAMPLE only
predicted:         the in-sample rule selects a LONG hold with a stop - 40 or 60 sessions, 4.0
                   ATR more likely than 2.0 - because gross accumulates with time in the
                   position while the round trip is paid once (PR-014's corrected turnover,
                   PR-018's hold_only), and the no-stop cells fail the tail rule at PR-018's
                   21.7% below -2R. Out of sample the predicted verdict is INCONCLUSIVE - for
                   PRECISION, not for sign. The table says which cells this design can read.
minimum detectable effect:  PER CELL - the predicted out-of-sample half-width of the cell's
                   paired difference against ratified, in the table below. From
                   tools/power_pr019.py, a variance estimate on the in-sample window that
                   reports no level, committed as PR-019-power.json before this registration.
power floor:       0.15 R end to end on the selected cell's out-of-sample difference interval -
                   PR-017's and PR-018's standard, kept by owner ruling 2026-09-12.
also predicted:    every no-stop cell's in-sample share below -2R exceeds ratified's by a factor
                   of five or more, so none is eligible. The curve prints them anyway.
```

```bash
PYTHONPATH=$PWD/src python tools/power_pr019.py --report
```

| cell against `ratified` | in-sample half-width, measured | out-of-sample, predicted | readable at the floor |
|---|---|---|---|
| `h10_stop2.0` | 0.0544 | 0.0512 | **yes** |
| `h10_stop4.0` | 0.0630 | 0.0594 | **yes** |
| `h10_stopnone` | 0.1280 | 0.1207 | no |
| `h20_stop2.0` | 0.0839 | 0.0791 | no, by 0.004 |
| `h20_stop4.0` | 0.0769 | 0.0725 | **yes** |
| `h20_stopnone` | 0.2277 | 0.2146 | no |
| `h40_stop2.0` | 0.1488 | 0.1403 | no |
| `h40_stop4.0` | 0.1239 | 0.1168 | no |
| `h40_stopnone` | 0.4953 | 0.4670 | no |
| `h60_stop2.0` | 0.2081 | 0.1962 | no |
| `h60_stop4.0` | 0.1451 | 0.1368 | no |
| `h60_stopnone` | 0.5876 | 0.5540 | no |

**How the numbers were made, and their direction.** A 25% instrument subsample, the decile taken
within it, in sample only, with the subsampling noise removed by a variance-components correction.
Predicted = measured × `sqrt(48 / 54)`, the out-of-sample window's month count. A normal approximation
to a moving-block bootstrap, so each figure is a **lower bound**. One calibration point exists: the
`h20_stopnone` contrast predicts **0.228** in sample, and `PR-018` realised **0.226** for the nearly
identical ratified-against-hold-only contrast.

**Precision falls with the hold, and that is the finding this section registers.** A month's
outcome for a 60-session position is a function of two or three months of market path; for a
10-session position it is a function of two weeks. The difference between two exits therefore
varies more from month to month the longer they hold, and no pairing cancels it — the correction to
`PR-018`'s report on 2026-09-12 records that pairing removed at most a sixth of that study's width.

**So the verdict's most likely shape is written here, before the data: the cell the in-sample rule
is predicted to select is one this design cannot confirm.** The owner ruled to run the grid anyway,
for the curve. **An `INCONCLUSIVE` on a 40- or 60-session cell does not say a long hold fails. It
says this data cannot tell at this precision**, and this paragraph is the proof that the sentence
was not written after the result.

## 4. Data

```
store:         data/bars.duckdb, daily bars, series RAW
as_of:         2026-09-06T22:36:49.635786-05:00 - PR-018's own instant, so §9's reproductions
               run on the identical store state
window:        asked from 2016-01-04, as PR-016..PR-018. MEASURED span reported beside it
country:       USA
universe:      DR-003's liquidity rule at each formation date's own bar
entries:       the top decile by the LIVE ByMarketPathStrength at rs.lookback 126, through
               `select`, formations every 20 sessions - PR-016's `ranked` arm exactly - then
               SPACED at 60 sessions per name (§5)
survivorship:  ABSENT and material - 2,598 of 2,598 decade-long instruments still trade
adjustment:    split-adjusted, NOT dividend-adjusted
costs:         25 bps a side and $0.005 a share, DR-005
split:         in sample = entries on or before 2021-12-31, out of sample = after. The split
               BUYS SELECTION: §6 chooses one cell of twelve in sample and reads it out
```

window rationale: the VERDICT is read only on entries after 2021-12-31 — about the most recent 56
months, which is `AGENTS.md` §19's current market to within two months — and the older window does one
thing, SELECT a cell, which it must do on data the verdict never sees. That needs a time split, and
§19.6 makes a time split the thing to argue for: a name split's halves share every month, and
`tools/power_pr019.py` measured that between-month variance dominates these contrasts, so a cell
selected on one half of the names would be "confirmed" by the same month shocks on the other. And §9
is a replication of `PR-016`'s and `PR-018`'s committed arms, whose windows are fixed by the
originals — §19.4's third reason. **This does not rest on "the intervals are too wide otherwise"**,
which §19.4 refuses, and the table in §3 shows the intervals are too wide at the long holds anyway.

**What the time split means for the owner's question of 2026-09-08** — *how do we know we are not
counting old numbers?* — is that this design asks it directly. **The in-sample window is the older
market; the out-of-sample window is the current one; the verdict asks whether the old market's best
cell survives the new one.** A cell that was best in 2016–2021 and is not in 2022–2026 is exactly
the stale finding §19 exists to catch.

## 5. Method

**One entry set, twelve exits and the incumbent.** Only the exit differs.

* **Spacing.** Each name's selection dates are thinned so that no two entries fall within 60
  sessions (`power_pr019.spaced`). The engine allows one position per instrument; spaced at the
  longest hold in the grid, no cell ever has a position open when the next entry arrives, so every
  cell trades the same schedule — the coupling `PR-018`'s A-1 found and could only report is
  removed at its source.
* **Then the intersection** (`run_pr019.common_entries`). The engine refuses an entry whose stop is
  not a positive price below it, or whose risk buys zero shares, and a 4 ATR stop hits those
  refusals on names a 2 ATR stop does not — **3 of 1,169 on the power subsample**. Every cell is
  restricted to the trades every cell realised, and the loss per cell and the engine's refusal
  reasons are reported.
* **What spacing costs.** It measures net R **per trade** on a fixed schedule and cannot rank cells
  on trades per year: the schedule it fixes is the one the longest hold would impose on all of them.
  The `free_entry` diagnostic reports each cell's own trade count and level for that reason.
* **The cells.** Holds {10, 20, 40, 60} × stops {2.0 ATR, 4.0 ATR, none}. No target anywhere:
  `PR-018` measured that the 1R target costs about 0.05R and buys nothing on the tail. A no-stop cell
  is `protective=False` with the stop still computed at 2 ATR, because R is `entry − stop` and an
  arm priced in different units cannot be subtracted from another.
* **The incumbent, `ratified`.** `2.0 × ATR(14)`, target `1.0R`, 20 sessions, stop checked first
  (`DR-042`), on the same spaced entries.
* **R is each cell's own risk unit** under the ratified constant-risk sizing (`RISK_SPEC` 2, $1,000 a
  trade as `PR-016`). A 4 ATR stop trades half the shares a 2 ATR stop does; every figure — net R and
  MAE alike — is in units of the risk budget, which is what an account experiences.
* **The risk side**, per cell and per window: worst, p01 and p05 MAE, and the shares below −1R, −2R
  and −3R.
* **Statistics** as `PR-016`: moving-block bootstrap over entry months, block 3, 10,000 resamples,
  seed 20260908.

**Two phases, one process.** Phase 1 simulates every selected arm — spaced at 1× and 3× costs, and
unspaced at 1×. §6's selection is a function of phase 1's in-sample cells. Phase 2 simulates, for the
selected cell and the incumbent only, the **no-selection null** (`STRATEGY_CONTRACT` C-3: every
admitted name, spaced at 60) and **cheap execution** at 5.75 bps a side, `EVIDENCE_SUMMARY` §10's
measured 11:00 median — which re-prices an entry struck at the open and is **not** a claim the
strategy can be executed later.

**Registered diagnostics, reported and never read by §6:** `free_entry`, `unselected`,
`cheap_execution`, and the 3× cost stress for every cell.

## 6. Decision rule

**Selection, in sample only.** A cell is eligible if it meets §8's sample rule in sample and its
in-sample share of trades below −2R does not exceed `ratified`'s in-sample share. Among the eligible,
the highest in-sample mean net R is selected; ties break to the shorter hold, then the tighter stop.
**The out-of-sample window is not an input to the selection** — `run_pr019.select_cell` takes no
argument that could carry it.

**Why the incumbent's tail and not a number.** The owner has not ruled the tail budget (`TODO.md`
§4, `STRATEGY_CONTRACT` C-8). The ratified exit's tail is the one the owner already accepted by
ratifying it. It is a stand-in and is registered as one; a looser ruling would admit cells this rule
excludes, and the curve reports every cell's tail so the ruling can be made on it.

**The verdict, read on the selected cell, out of sample.**

```
NO_ELIGIBLE    no cell meets the in-sample eligibility rule. A finding: nothing on this grid
               keeps the ratified exit's tail without its target.
ACCEPT         the selected cell meets §8's sample rule out of sample; its difference interval
               is within the power floor and lies entirely ABOVE zero; its OWN mean net R
               interval lies entirely above zero; and its share below -2R does not exceed the
               Wilson 95% upper bound of ratified's out-of-sample share.
TAIL_BREACH    both intervals as ACCEPT, the tail condition failed. STRATEGY_CONTRACT C-8 made
               mechanical: it earns, and runs a fatter tail than the incumbent where it counts.
REJECT         qualified and powered, and the difference interval lies entirely BELOW zero.
BOTH_NEGATIVE  qualified and powered, not REJECT, and the cell's OWN interval lies entirely
               below zero. PREREG_TEMPLATE rule 8: losing less than the incumbent licenses
               nothing when the cell loses money.
NULL           qualified and powered, and the difference interval contains zero. Rule 10: the
               instrument was sharp enough and there is nothing there.
INCONCLUSIVE   anything else - including a difference interval wider than the power floor,
               which §3 predicts for every cell at 40 or 60 sessions, and a cell that beats the
               incumbent without being demonstrably profitable, which is PR-016's shape.
```

Evaluated in that order by `run_pr019.verdict_for`; the tests in `tests/test_run_pr019.py` pin every
branch and 28 of 28 mutants of the two tools die against them.

**No verdict moves a parameter.** `exit.max_holding_period`, `exit.atr_stop_multiple` and
`exit.target_r_multiple` are the owner's, every cap in `risk.*` is denominated in the stop, and
`CHARTER` A-001 has the last word on anything that touches risk. **An `ACCEPT` licenses one
sentence** — *on the current market, this hold and stop earn this much net R a trade on this
construction, this much more than the ratified exit, with this tail* — and makes it the evidence a
strategy card under `STRATEGY_CONTRACT` C-7 may cite for its own hold.

## 6a. Trials

**Twelve**, one per grid cell. Two of them re-evaluate configurations `PR-018` already evaluated —
`h20_stop2.0` is its `ratified_no_target` and `h20_stopnone` its `hold_only` — on a different entry
schedule, and are **counted anyway**: counting the flattering way is how a budget gets understated.
The incumbent reproduces a published arm and is not counted; a reader who counts it gets thirteen.
The cumulative figure and the hurdle are the tool's, never typed here:

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

## 7. Stopping rule

One pass, one pinned `--as-of`. No interim look, no early stop. The in-sample selection is computed
inside the same run by the registered function, never by a reader.

## 8. Sample

```
minimum:       200 trades AND 24 entry months in EACH window, per cell
power floor:   0.15 R end to end on the selected cell's out-of-sample difference interval
if not met:    report the measurement and REFUSE to read the window as evidence
```

The power subsample — a quarter of the instruments — realised 1,169 spaced entries in sample over 48
months. The full universe gives several times that. **Months bind, and the table in §3 is what they
bind.**

## 9. What would refute this

**H1 is refuted** by `REJECT`, `BOTH_NEGATIVE` or `NULL`.

**What would refute the STUDY rather than the hypothesis**, and the report shows both first:

* the unspaced `free_ratified` arm failing to reproduce `PR-016`'s `ranked` — **11,019 trades at
  −0.0797R in sample, 16,320 at −0.1144R out** — or `free_h20_stop2.0` failing to reproduce
  `PR-018`'s `ratified_no_target` at **−0.0261R and −0.0650R**. Same store instant, same
  construction; anything but every digit is a defect in this runner;
* the spaced entry sets still differing across cells after the intersection. The runner records it.

**What would NOT settle anything:** an `INCONCLUSIVE` on a 40- or 60-session cell. §3 predicts it and
says why.

## 10. Amendments

None.
