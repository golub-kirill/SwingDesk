# PREREG: does the published intraday momentum rule make money on SPY, long only - and still, since it was published?

```
id:            PR-031
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19 - asked what to research after the
               order types, the owner picked "Внутридневной моментум" (the published intraday
               momentum rule on SPY/QQQ), long only (their standing preference, same day)
status:        registered, not run
verdict:       -
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, `EVIDENCE_SUMMARY.md` §20-§27, `CHARTER.md`
A-003, `DR-040`, `DR-045`, `DR-046`.

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-021`..`PR-023` | reversal, an index with a trend exit, five asset classes - daily | none beats holding `SPY` per unit of risk |
| `PR-024`, `PR-025`, `PR-030` | when and how `CARD-001`'s stock entries should execute | the card breaks even; the saving is execution, not edge |
| `CHARTER` A-003 | whether intraday decisions may be studied | allowed 2026-09-16, and it names this rule: *"the one published family where this project's cost model stops being fatal"*, with two standing cautions - test the period since publication separately, and use no more timeframes than the question needs |

**distinct because nothing here has traded inside a session.** Every study so far held overnight
and paid a stock's spread; this holds `SPY` for part of one session and pays about a cent a share.

**What is known in advance, stated first.** The authors report the rule on `SPY` over 2007 to early
2024 at a **Sharpe ratio of 1.33 and 19.6% a year net**, long and short together, trading at the
bar they read. An independent replication on `ES` futures from 2010 with realistic slippage found it
weaker - **Sharpe 0.91, 8.1% a year** - and alive. The author has read both and nothing else of the
rule's performance; no minute of `SPY` or `QQQ` has been read by any tool here before this
registration except by the power estimate below, which let only widths out.

## 1. Question

Over 2016-01-04 .. 2026-09-18, does the published intraday momentum rule, traded LONG ONLY on
`SPY` with no look-ahead at the decision, earn a positive mean daily return net of costs - and does
it still earn it after 2024-05-10, the day the paper appeared?

## 2. Hypothesis

**H1.** The mean daily net return of `SPY-long` has a 95% interval wholly above zero, and its
estimate after publication is above zero.

**H0.** It does not.

**Two more readings, counted and never read:** `QQQ-long`, the same rule on `QQQ`; and `SPY-both`,
the paper's own long-and-short rule on `SPY`.

## 3. Prediction, stated numerically before the run

```
primary quantity:  the mean over sessions of SPY-long's net return on equity, a session's return
                   the leverage times each trade's move less two sides' cost, over the open;
                   month-clustered bootstrap
predicted:         SPY-long about +0.02% a day net (about +5% a year), between 0.00 and +0.04. The
                   paper's 19.6% a year was long AND short, filled at the bar it read, on a window
                   that holds 2008; an independent replication on ES futures found 8.1% a year; and
                   published work finds most of SPY's long-run gain overnight, when the rule is
                   flat - not measured here, and the author has not looked. The
                   predicted width is 0.036 points a day (results/PR-031-power.json), so a
                   zero-containing interval is NULL, not INCONCLUSIVE: ACCEPT needs the estimate
                   above about +0.018, and the author puts ACCEPT and NULL near even. After
                   publication (590 sessions, 0.052 wide) the estimate's sign is a coin the
                   author cannot call, which makes PUBLICATION_FRAGILE the likeliest of the rest.
                   QQQ-long: the same, a little larger. SPY-both: higher in the crashes, about the
                   same Sharpe ratio, twice as wide
if H1 were TRUE:   an interval wholly above zero, and a positive estimate after publication
minimum detectable effect:  0.026 points a day (0.00026, about 6.5% a year) - the difference the whole
                   window detects with 80% power: the predicted half-width, 0.018, x (1.96 + 0.84)
                   / 1.96. After publication alone, 0.037 a day (about 9.3% a year). From
                   `run_pr031.py --power` - the verdict estimator's own interval on the registered
                   window and store, widths only under `power_pr019.assert_no_effect_leaked`
power floor:       0.08 points a day end to end (0.0008) - a zero-containing interval narrower than
                   that, within +-0.04% a day or about +-10% a year, is NULL; it gates NULL only
```

## 4. Data

```
store:         SPY and QQQ one-minute bars from Alpaca's sip feed, adjustment=split, fetched by
               tools/fetch_minutes.py --instrument SPY --instrument QQQ --from 2016-01-04
               --to 2026-09-18 into a scratchpad MinuteStore; the knowledge instant is recorded
               with the result
as_of:         2026-09-19T20:57:13.362351+00:00 - the fetch's last knowledge_time; 2,693
               sessions of each fund fetched, none empty
window:        2016-01-04, the first session the sip feed serves minutes for, to 2026-09-18, the
               last completed session before registration: 10.71 years, 129 months. After
               publication: 2024-05-13 .. 2026-09-18
window rationale: the study is a REPLICATION of a published result whose window the original fixed -
               2007 to early 2024, AGENTS.md 19.4's third reason - and the minute store cannot go
               further back than 2016-01-04. The part of that window after publication is read
               apart and gates ACCEPT, as CHARTER A-003's first caution requires
country:       USA
survivorship:  none - two index funds trading throughout
a session:     regular hours only (intraday.regular_hours), read when its minutes cover 90% of the
               session; gaps carry the last close forward. The first 15 sessions are warm-up
costs:         per share per side: $0.005, half the one-cent quoted spread (net); the paper's
               $0.0035 commission plus $0.001 slippage, $0.0045; a whole cent (cost_adverse).
               Alpaca charges no commission (DR-039). No quote of SPY is stored, so the spread is
               the tick, not a measurement. Regulatory fees on sales are left out - about 0.3 bps
               of a sale, inside the cost-adverse cent
dividends:     not in the minutes. The rule is flat overnight and never holds through an ex-date,
               so its returns lose nothing. The prior close that widens the upper bound is not
               adjusted for them either: on about four ex-dates a year the bound starts a dividend
               high, which the paper adjusts and this does not
```

## 5. Method

* **The noise area, the paper's.** For each minute of the session, `sigma` is the mean over the
  last 14 read sessions of the absolute move from the open to that minute's close. The upper bound is
  `max(open, prior close) x (1 + sigma)`, the lower `min(open, prior close) x (1 - sigma)`.
* **The decision, at every HH:00 and HH:30 from 10:00 to the last half hour of the session**, reads
  the close of the minute that ENDS there and fills at the open of the next minute: LONG if that
  close is above both the upper bound and the session's VWAP so far, else flat (`SPY-both`: short
  if below both the lower bound and the VWAP). **The paper trades at the bar it reads; this does not**,
  and the difference is a minute of adverse drift at every trade. Everything is flat at the last
  minute's close.
* **The session's VWAP** is each minute's own VWAP weighted by its volume, cumulative from the bell
  (the typical price where a minute has no VWAP).
* **Size**: equity times `min(4, 0.02 / sigma_daily)`, `sigma_daily` the sample standard deviation
  of the last 14 close-to-close returns. The paper's constants, none chosen here.
* **The statistic.** The mean daily net return; a 95% moving-block bootstrap over calendar months,
  block 3, 10,000 resamples, seed 20260921. Before and after publication, each the same way.

### 5a. The split, and what it buys

```
split:           none - a published rule with every constant fixed by its authors
split buys:      nothing a split could buy: nothing is selected here. The period since
                 publication is read apart and gates ACCEPT (section 6)
perturbations:   paper - the paper's $0.0045 a share a side
                 cost_adverse - a whole cent a share a side. Section 6 reads it on an ACCEPT
                 gross - no cost
```

**Diagnostics, printed and never read by §6:** annualised mean, volatility, Sharpe ratio, CAGR and
worst drawdown, whole and after publication; the sessions traded and the mean leverage; every
excluded session by reason; and **holding the same fund close to close on the same sessions**, price
only, with its Sharpe ratio and its correlation with the rule. Holding leaves out about 1.3% a year
of `SPY`'s dividends, and the report says so beside the number.

## 6. Decision rule

**For `SPY-long`, in this order:** `REFUSED` under 1,000 sessions, 24 months, or 90% of the window's
sessions after warm-up read; `COST_FRAGILE` if the interval is wholly above zero and the
cost-adverse reading's is not; `PUBLICATION_FRAGILE` if wholly above zero and the estimate after
publication is not above zero; `ACCEPT` wholly above; `REJECT` wholly below; `INCONCLUSIVE`
containing zero and wider than 0.08 points a day; `NULL` containing zero inside it. **The study's
`verdict:` is `SPY-long`'s**; `QQQ-long` and `SPY-both` are reported and never replace it.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *the rule, long only on `SPY`, made money net of a half-cent a share over 2016-2026,
  and was still making it after publication*: worth a specification for a live paper trial.
* `PUBLICATION_FRAGILE` — *it made money in the years the paper read and not since*.
* `COST_FRAGILE` — *it made money at half a cent and not at a cent*.
* `REJECT` — *it lost money*.
* `INCONCLUSIVE` / `NULL` — *not established at this width* / *within about ±10% a year of zero*.

**Nothing is built on any branch.** An intraday loop does not exist (`CHARTER` A-003 §4); running
the rule, even on paper, is specification-first work after this, and it is the owner's call.

## 6a. Trials

**Three** — `SPY-long`, `QQQ-long`, `SPY-both`. The tool reads **143** with `PR-030`; three more take
it to **146** and the hurdle from **2.654 to 2.661** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** any other lookback, band multiplier, decision interval, volatility target
or leverage cap; any other fund; a stop inside the half hour; the paper's same-bar fill.

## 7. Stopping rule

One fetch of the minutes, repeated only to fill sessions that failed. One run at the pinned knowledge
instant. No constant, fund, costing or window tried after the first result is seen.

## 8. Sample

```
minimum:       1,000 read sessions across at least 24 months, and 90% of the window's sessions
               after warm-up read
power floor:   0.08 points a day end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by `REJECT`, `NULL`, `INCONCLUSIVE`, `COST_FRAGILE` or `PUBLICATION_FRAGILE`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* more than a tenth of the window's sessions unread;
* a realised half-width outside half to twice §3's predicted 0.018;
* a mean leverage outside 1 to 4 - `SPY`'s daily volatility near 1% puts it near 2, and a mean
  at either end means the volatility is read wrong.

**What would NOT settle anything:** an `ACCEPT` read as *a working strategy*. It would say a
published rule, long only, made money in a backtest at a tick's cost; a live paper trial is what
the specification after it would have to show.

## 10. Amendments

None.
