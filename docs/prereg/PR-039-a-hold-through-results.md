# PREREG: does a hold that spans a results announcement jump the stop more often — and what would avoiding it cost?

```
id:            PR-039
date:          2026-09-26
author:        Claude, on the owner's instruction of 2026-09-26: "начнем с C" - option (c) of
               three offered: measure how much of CARD-001's losses fell on results
               announcements, and decide about a filter. TODO.md carried the question since
               2026-08-30 ("the buffer needs a ruling or a study") and named this check
status:        registered, not run
verdict:       -
```

---

## 0. Refutation-family check

**searched:** `docs/prereg/` and `docs/decisions/` on every branch (only `master` exists since
2026-09-26); `RETURN_SOURCE_REGISTER.md`; `EVENT_SPEC.md`; `EVIDENCE_SUMMARY` §17; `TODO.md` §2's
earnings-buffer item and its literature.

**found:**

| prior work | what it found |
|---|---|
| `EVIDENCE_SUMMARY` §17.2 (`PR-005`'s 26,351 trades) | gaps through the stop are 18.8% of losing trades and **28.1% of all loss**, at −1.56R each against −1.03R for an ordinary stop |
| `EVENT_SPEC` (course modules 34 and 40) | the course names the catalyst check and quantifies nothing; `screen.earnings_buffer_days` is `unset` |
| `TODO.md` §2, searched 2026-08-30 under `AGENTS.md` §16 | the literature points AGAINST avoiding announcements on RETURN grounds: an announcement premium of roughly 7-10% a year (Frazzini & Lamont 2007; Savor & Wilson, *JF* 2016; Barber et al., *JFE* 2013). What it does not touch is the STOP: a gap opens through it, so the realised loss is not 1R |

**distinct because** no study here has ever dated an announcement. Every trade log in this
repository is silent on whether a hold spanned one, so neither half of the question - the tail or
the cost - has been measured on this system's trades.

**Where it sits in `DR-047`'s order, said out loud.** `DR-047` §3.2 puts management research after
a source has passed its own test, and `CARD-001`'s source has not (`RETURN_SOURCE_REGISTER` §2.1).
This is not a search for return: its primary question is the **1R denominator** that the running
paper book's caps and kill switch are expressed in. The owner chose it on 2026-09-26 knowing the
alternatives, which is theirs to do.

**What is known in advance:** the sample's pooled exit mix (`stop_gap` is 201 of 2,400 trades,
8.4%); the bucket sizes below, counted with no outcome read (`run_pr039.py --count`); and the
widths, from permuted labels (`results/PR-039-power.json`). Nothing split by exposure has been read.

## 1. Question

Among `PR-016`'s one-times-cost trades on companies whose results announcements are dated, does a
hold that spans an announcement **exit through a gap** (`stop_gap`: the session opened through the
stop) more often than a hold that does not - and does leaving those holds out change the mean net R?

## 2. Hypothesis

**H1.** The `stop_gap` rate of exposed holds minus that of unexposed holds has a 95% interval
wholly above zero.

**H0.** It does not.

**Read, and it decides only which branch an `ACCEPT` is:** the mean net R of exposed holds minus
that of unexposed ones - the cost side, where the announcement premium would show.

**Counted and never read by §6:** the same two differences on `CARD-001`'s own arm alone
(`ranked_top4`, 28 exposed trades - far too few to decide anything); every bucket's share of the
arm's trades and of its total loss (the owner's question, answered descriptively); the book's mean
net R with the exposed holds left out.

## 3. Prediction, stated numerically before the run

```
primary quantity:  stop_gap rate (exposed) - stop_gap rate (unexposed), pooled one-times-cost
                   arms, moving-block bootstrap over entry months
predicted:         exposed about 20%, unexposed about 7%: +13 points. An announcement moves a
                   typical US stock several percent in a session, and a stop two ATRs below the
                   entry is a few percent of price - so a fair share of adverse announcements open
                   through it. The predicted half-width is 0.040 (results/PR-039-power.json), so
                   ACCEPT needs the estimate above about +0.040.
                   The mean net R difference: about -0.10R (the gap costs half an R more than a
                   stop, section 0) against the announcement premium, which a 1R target mostly
                   caps. That is inside the cost side's +/-0.19R half-width, so the author
                   expects the branch RISK_ONLY
if H1 were TRUE:   an interval wholly above zero
minimum detectable effect:  0.057 (5.7 points of gap rate) - the permuted-label half-width 0.0398 x
                   (1.96 + 0.84) / 1.96, results/PR-039-power.json
power floor:       the cost side's minimum detectable effect is 0.28R a trade; a smaller cost of
                   the filter cannot be seen by this sample, and the report says so
```

## 4. Data

```
trades:        docs/prereg/results/PR-016-trades-sample.csv, committed with PR-016 on
               2026-09-08: a seeded random sample of 400 trades per arm. The pool is the four
               one-times-cost arms (ranked, ranked_top4, unselected, unselected_two_slot), each
               distinct trade once - 1,591 trades. The _3x arms are the same entries costed three
               times and are left out
calendar:      docs/prereg/results/PR-039-announcements.csv - every Form 8-K carrying Item 2.02
               ("Results of Operations and Financial Condition") that SEC EDGAR accepted since
               2015 for the sample's names, with EDGAR's acceptance instant; fetched 2026-09-26 by
               tools/fetch_earnings_dates.py. 985 companies, 44,427 announcements
coverage:      docs/prereg/results/PR-039-coverage.csv, with each name's is_etf from the
               project's symbol directory. Buckets, fixed before any outcome was read: a company
               with dated results -> exposed or unexposed; an ETF -> fund; everything else ->
               unknown (a foreign issuer reporting on Form 6-K, which carries no item codes, has
               results that exist and cannot be dated here)
sizes:         pool - exposed 144, unexposed 903, fund 389, unknown 155; 90.3% classified.
               CARD-001's arm - exposed 28, unexposed 234, fund 113, unknown 25
window:        the sample's entries, 2017-09-07 .. 2026-08-07, 105 months
window rationale: the event is rare (AGENTS.md 19.4's fourth reason): 144 exposed holds in the
               whole sample, and the last 48 months hold about half of its entries - roughly 75
               exposed holds, under section 8's minimum of 100. The trades are also not chosen
               here: they are PR-016's committed sample, whose window PR-016 argued
country:       USA
survivorship:  PR-016's, inherited: the store's names are today's listings (BACKTEST_PROTOCOL 6c)
costs:         PR-016's, as recorded in each trade's net_r
```

## 5. Method

**Exposure.** The impact session comes from the acceptance instant in New York time: before the
open of a session day, that session's **open**; during the session, that session **intraday**;
after the close or on a closed day, the **next session's open**. A trade enters at its entry day's
open. An open impact on the entry day is already in the entry price, so it does not expose the
trade; an open impact on any later day through the exit day does. An intraday impact exposes any
day of the hold, the entry day included. (`run_pr039.impact`, `run_pr039.exposed`; tested on eight
instants and six holds in `tests/test_run_pr039.py`.)

**The statistic.** A difference in proportions of `exit_reason == "stop_gap"`; a 95% moving-block
bootstrap over entry months, block 3, 10,000 resamples, seed 20260927. The cost side is the same
bootstrap on `net_r`.

### 5a. The split, and what it buys

```
split:           none - exposed against unexposed holds of one committed sample
split buys:      nothing a split could buy: no constant is chosen here
perturbations:   none registered
```

**Diagnostics, printed and never read by §6:** each bucket's trades, gap exits and share of total
loss, for the pool and for `CARD-001`'s arm; the book's mean net R with and without exposed holds.

## 6. Decision rule

**In this order:** `REFUSED` below §8's minimums; then on the primary interval -

* **wholly above zero** - `ACCEPT`, and the cost side names the branch: `FILTER_HELPS` if the
  mean-R difference is wholly below zero (exposed holds earn less, so leaving them out raises the
  mean); `FILTER_COSTS` if wholly above zero (the announcement premium: leaving them out lowers
  it); `RISK_ONLY` if it contains zero;
* **wholly below zero** - `REJECT`;
* **containing zero** - `NULL` if its upper end is below the minimum detectable effect (0.057),
  otherwise `INCONCLUSIVE`.

**What each licenses - one sentence, and no parameter:**

* `ACCEPT` / `RISK_ONLY` or `FILTER_HELPS` - *an announcement inside the hold is a measured source
  of losses beyond 1R*: the owner may set `screen.earnings_buffer_days` as `assumed`, citing this
  study, as tail control. Using it live needs a FORWARD calendar, which EDGAR does not publish, and
  that is a separate build.
* `ACCEPT` / `FILTER_COSTS` - *the tail is real and avoiding it gives up measured return*: the
  owner's trade-off, with both numbers.
* `REJECT` / `NULL` - *announcements add no measurable gap risk here*: no filter; the parameter
  stays `unset`.
* `INCONCLUSIVE` - *not established at this width*.

## 6a. Trials

**One.** The filter - leave out every hold that spans an announcement - is a configuration
evaluated on the data, whatever the primary says. The count moves from **166 to 167**.

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** a buffer of N sessions before an announcement (this reads the hold, not a
window before it); any conditioning on company size, volatility, sector or the direction of the
surprise; the `_3x` arms; any other sample.

## 7. Stopping rule

One run over the committed files. No bucket rule, exposure rule, arm or window is changed after
the first result is seen.

## 8. Sample

```
minimum:       600 company trades in the pool, 100 of them exposed, and 80% of the pool classified
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by any branch other than `ACCEPT`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* **the acceptance instant not tracking the release** - results are released outside the session
  almost always, so intraday impacts should be a small minority. If more than **20%** of the
  calendar's announcements since 2017 land intraday, the exposure rule is reading the wrong clock
  and the study says so instead of reporting;
* **a thin calendar** - a median below **3 announcements a company a year** means the filings are
  missing results, and unexposed holds would be contaminated with exposed ones;
* a realised half-width outside half to twice §3's predicted 0.040.

**What would NOT settle anything:** an `ACCEPT` read as *the card should avoid announcements*.
`CARD-001`'s own source has not passed its test (§0), and a filter on a strategy with no measured
edge controls its tail and nothing more.

## 10. Amendments

None.
