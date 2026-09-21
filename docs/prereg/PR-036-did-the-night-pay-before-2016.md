# PREREG: did the night pay before 2016? The same two arms, on daily bars, back to 2004

```
id:            PR-036
date:          2026-09-20
author:        Claude, after an advisory council reviewed PR-030..PR-035 on 2026-09-20. Its
               sharpest unanswered objection: 2016-2026 is an exceptional decade for the index,
               so the overnight result may be a wrapper around an epoch rather than an effect.
               Nobody had asked what the book does in a decade where the index returns nothing
status:        reported   (2026-09-20 - results/PR-036-report.md)
verdict:       INCONCLUSIVE, branch COST_FRAGILE - the IJR+VB basket's night over 2004-2015 earned
               +0.0434% a day [+0.0225, +0.0635], 10.94% a year at a Sharpe ratio of 0.84 against
               holding the same funds' 0.48, and compounded at 10.6% where holding compounded at
               8.8% and fell 58.8%. At a WHOLE CENT a share a side the interval is [-0.0003,
               +0.0408] and touches zero, which is the branch. The epoch objection is answered:
               the effect is not a wrapper around 2016-2026. All three section 9 checks passed -
               the overlap landed 0.57 points a year from PR-034's minute-based reading
```

---

## 0. Refutation-family check

**searched:** `PR-033`, `PR-034`, `PR-035` and their reports, `EVIDENCE_SUMMARY` §31-§33.

**found:**

| prior work | window | what it found |
|---|---|---|
| `PR-034` | 2016-01 .. 2026-09, minute prices | small caps' night +13.8% a year at Sharpe 1.06; holding them 12.9% at 0.59 |
| `PR-033` | the same | the night pays on five funds; the session barely does |
| `PR-035` | the same | a book that adds a day leg returns 18.9% against holding `SPY`'s 15.7%, its margin `COST_FRAGILE` |

**distinct because every one of them reads the same eleven years.** Those years held a 15.7%-a-year
index. This study reads **2004-01-30 .. 2015-12-31** — a window no tool in this repository has
touched, which holds the 2008 collapse and a stretch in which the index went almost nowhere.

**Why it can run at all:** the two prices the arms need — the open and the close — are in the DAILY
bars, and those reach back to 2000 for `IJR` and 2004 for `VB`. Nothing is fetched.

**What is known in advance:** every number in `PR-033`..`PR-035`. Nothing has been read from the
pre-2016 window, and the power estimate below lets only widths out. The overnight effect is
published (outside knowledge: Cliff, Cooper and Gulen 2008, and later work), and that literature
used data from the 1990s and 2000s — which is a reason to expect the effect to be present here,
stated before the run rather than after.

## 1. Question

Over 2004-01-30 .. 2015-12-31, did holding `IJR` and `VB` **only overnight** earn a positive mean
daily return net of two trades a day — still positive at a whole cent a share, and at a higher
Sharpe ratio than holding the same two funds?

## 2. Hypothesis

**H1.** The basket's overnight arm over that window has a 95% interval wholly above zero, its
cost-adverse reading too, and a Sharpe ratio above holding the same basket's.

**H0.** Any one of those fails.

**Counted and never read:** the session arm; holding the basket; each fund's night alone; and the
same three readings over the 2016-2026 overlap, which exist to validate the method (§5).

## 3. Prediction, stated numerically before the run

```
primary quantity:  the mean over sessions of the equally weighted IJR+VB basket's overnight net
                   return, net of $0.005 a share a side, month-clustered bootstrap
predicted:         +0.045% a day, about +11% a year, between +0.02 and +0.07. The 2016-2026
                   reading was +0.0549% and the published literature found the effect in the 1990s
                   and 2000s, so the author expects it PRESENT and somewhat smaller - 2008 is in
                   this window and a crash is an overnight event. The predicted width is 0.040
                   points a day (results/PR-036-power.json), so ACCEPT needs the estimate above
                   about +0.020.
                   The session arm: negative, as it is in 2016-2026. Holding: around +8% a year,
                   which is what small caps did over these twelve years, with a 2008 drawdown near
                   -55%. The author therefore expects the Sharpe gate to PASS comfortably: the
                   night misses most of a crash that happened in daylight
if H1 were TRUE:   all three readings above zero or above the benchmark, as section 6 orders them
minimum detectable effect:  0.029 points a day (0.00029, about 7.3% a year) - the predicted
                   half-width, 0.0202, x (1.96 + 0.84) / 1.96
power floor:       0.08 points a day end to end (0.0008), PR-031's..PR-035'; it gates NULL only
```

## 4. Data

```
funds:         IJR and VB, PR-034's verdict basket, equally weighted. No fund is added
prices:        DAILY bars, open and close, from the scratchpad history store fetched by
               tools/fetch_history.py on 2026-09-20 (IJR 6,617 bars from 2000-05-26; VB 5,695 from
               2004-01-30), with their cash dividends by ex-date
as_of:         2026-09-20T06:28:46.070772+00:00
window:        2004-01-30, the first session VB trades, to 2015-12-31, the day before the minute
               feed and every prior study begin. About 3,000 sessions, 143 months
window rationale: the question IS the earlier window - AGENTS.md 19.4's first reason, a regime the
               recent window does not contain. 2016-2026 held a 15.7%-a-year index; 2004-2015 held
               the 2008 collapse and a decade that went nowhere, and no study here has read it
country:       USA
survivorship:  none - two index funds trading throughout
costs:         PR-033's and PR-034's, unchanged: $0.005 a share a side (net), $0.0045 (the
               paper's), $0.01 (cost_adverse, which the decision rule gates on)
```

## 5. Method

**`PR-033`'s arms, imported unchanged**: the night is `(next open + dividend) / close − 1` less two
sides, the session is `close / open − 1` less two sides, the dividend is paid to the night because
it detaches at the ex-date's open, and the basket is equal capital across the two funds. The only
change is the price source: a daily bar's open and close instead of the session's first and last
stored minute.

**And that change must prove itself before the answer is believed.** A daily bar's open and close
are the vendor's consolidated prices, not the auction prints the minute feed carries. So the runner
also reads **2016-2026 from the same daily bars** and compares it with `PR-034`'s minute-based
night (`run_pr036.reproduces_pr034`). **That comparison is printed first, and §9 makes it the
study's own refutation.**

**The statistic.** The mean daily net return; a 95% moving-block bootstrap over calendar months,
block 3, 10,000 resamples, seed 20260926.

### 5a. The split, and what it buys

```
split:           none - one rule, one basket, one untouched window
split buys:      nothing a split could buy: no constant is chosen here
perturbations:   paper - $0.0045 a share a side
                 cost_adverse - a whole cent a share a side, which the decision rule gates on
                 gross - no cost
```

**Diagnostics, printed and never read by §6:** each fund's night alone; the session arm and holding
over both windows; the annualised return, volatility, Sharpe ratio and worst drawdown of each; and
the identity check — the two arms compounded must equal holding on any session with no dividend.

## 6. Decision rule

**For the basket's night over 2004-2015, in this order:** `REFUSED` under 1,000 sessions, 24 months
or 90% of the window's stored bars read; `COST_FRAGILE` if the interval is wholly above zero and
the cost-adverse reading's is not; `NOT_BETTER_HELD` if wholly above zero and the night's Sharpe
ratio is not above holding the basket's; `ACCEPT` wholly above and past both gates; `REJECT` wholly
below; `INCONCLUSIVE` containing zero and wider than 0.08 a day; `NULL` containing zero inside it.

**There is no recency gate**: this window IS the old one, which is the point.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *the night paid in a decade the index did not*: the effect is not a wrapper around
  2016-2026, and `CARD-002` keeps its evidence.
* `NOT_BETTER_HELD` — *it paid, and holding was still better per unit of risk there*.
* `REJECT` / `NULL` — *the effect is absent before 2016*: `PR-034`'s `ACCEPT` belongs to one decade
  and `CARD-002` should not be built.
* `COST_FRAGILE` / `INCONCLUSIVE` — *it paid at half a cent only* / *not established at this width*.

## 6a. Trials

**Zero.** No configuration is evaluated that `PR-034` did not already declare: the same rule, the
same two funds, the same weighting and the same costs. Only the window and the price source change,
which makes this a replication on an untouched sample rather than a search. The count stays at
**166** and the hurdle at **2.704** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** any other fund; `IJR` alone over its longer history from 2000 (a second
window is a second look); any weighting other than equal; any conditioning on regime, year or
volatility.

## 7. Stopping rule

One run at the pinned knowledge instant. No fund, costing or window tried after the first result is
seen.

## 8. Sample

```
minimum:       1,000 sessions across at least 24 months
power floor:   0.08 points a day end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by any branch other than `ACCEPT`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* **the overlap check failing** — the 2016-2026 night read from daily bars must land within **2
  percentage points a year** of `PR-034`'s minute-based +13.83%. Further apart than that and the
  price source is not measuring the same thing, so the pre-2016 number cannot be trusted and the
  study says so instead of reporting it;
* the identity check failing on either fund;
* a realised half-width outside half to twice §3's predicted 0.0202.

**What would NOT settle anything:** an `ACCEPT` read as *the strategy is safe*. This window contains
a −55% drawdown in the funds themselves, and the night's own drawdown in it is a diagnostic the
report prints.

## 10. Amendments

None.
