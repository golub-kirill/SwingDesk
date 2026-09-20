# PREREG: is the money in the night? The overnight return against the session's own, on five index funds

```
id:            PR-033
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19. Shown that PR-031's ACCEPT did not
               survive PR-032's test on funds the rule was never fitted to, the owner picked
               "Ночь против дня" - the overnight effect - as the next candidate
status:        registered, not run
verdict:       -
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, `EVIDENCE_SUMMARY` §20-§30, `CHARTER` A-003,
`DR-040`, `DR-045`.

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-021`..`PR-023` | reversal, an index with a trend exit, five asset classes — all held overnight AND through the session | none beats holding `SPY` per unit of risk |
| `PR-031`, `PR-032` | the published intraday momentum rule, which is flat overnight by construction | `ACCEPT` on `SPY`, and nothing on three funds it was never fitted to |
| `PR-024`, `PR-025`, `PR-030` | what the card's entries pay at the open and the close | the open costs 37.8 bps a side on stocks; a fund's auction is a different market and none of these priced one |

**distinct because no study here has separated a session from the night before it.** Every earlier
holding spans both. This splits the calendar day in two and prices each half with its own trades.

**What is known in advance, stated first.** The claim is published and old: since Cliff, Cooper and
Gulen (2008) and repeatedly since, US index funds' gains are reported to accrue between the close
and the next open, with the session adding little. The author has read those claims and no number
from this project's own funds: the power estimate below let only widths out, and no level of any
arm has been printed.

## 1. Question

Over 2016-01-04 .. 2026-09-18, does holding an equally weighted basket of `SPY`, `QQQ`, `IWM`, `DIA`
and `EFA` **only overnight** — bought in the closing auction, sold at the next open — earn a
positive mean daily return net of two trades a day, and does it still earn one over the last 590
sessions?

## 2. Hypothesis

**H1.** The basket's overnight arm has a 95% interval wholly above zero, its cost-adverse reading
too, and a positive estimate over the last 590 sessions.

**H0.** It does not.

**Counted and never read:** each fund's overnight arm; the session arm `D` (open to close) for the
basket and each fund; the difference `N − D`; and holding each fund close to close with its
dividends, which is the benchmark and spends no trial.

## 3. Prediction, stated numerically before the run

```
primary quantity:  the mean over sessions of the equally weighted basket's overnight net return -
                   (next open + dividend) / close - 1, less two sides at $0.005 a share;
                   month-clustered bootstrap
predicted:         +0.035% a day, about +9% a year, between +0.01 and +0.06. The funds themselves
                   returned roughly 12-15% a year over this window, and the published claim is that
                   the night carries nearly all of it; two sides a day at half a cent take about
                   0.5% a year off. The predicted width is 0.056 points a day
                   (results/PR-033-power.json), so ACCEPT needs the estimate above about +0.028 and
                   a zero-containing interval is NULL rather than INCONCLUSIVE. The author expects
                   ACCEPT or RECENT_FRAGILE, and rates RECENT_FRAGILE the larger risk: the last two
                   years' sessions have been strong intraday
                   N - D: positive, +0.05 to +0.08 a day. Per fund the same shape, EFA weakest
                   because its market trades while New York sleeps
if H1 were TRUE:   an interval wholly above zero, cost-adverse too, and a positive recent estimate
minimum detectable effect:  0.040 points a day (0.00040, about 10% a year) - the difference this
                   window detects with 80% power: the predicted half-width, 0.028, x (1.96 + 0.84)
                   / 1.96. The recent window alone is twice as wide (0.096), which is why it gates
                   rather than carries the verdict
power floor:       0.08 points a day end to end (0.0008), PR-031's; it gates NULL only
```

## 4. Data

```
funds:         SPY, QQQ, IWM, DIA, EFA - every fund whose minutes this project holds. No fund is
               chosen here and none is left out
minutes:       Alpaca sip, adjustment=split, the scratchpad MinuteStore PR-031 and PR-032 used;
               2,693 sessions of each fund, none served empty
dividends:     Yahoo's cash dividends by EX-DATE, fetched with tools/fetch_history.py into a
               scratchpad store of its own (SPY 136 actions, QQQ 90, IWM 108, DIA 340, EFA 48)
as_of:         minutes 2026-09-19T21:38:38.502579-05:00; bars and actions
               2026-09-20T04:28:27.411162+00:00
window:        2016-01-04 to 2026-09-18, 2,692 sessions after the first, 129 months. The recent
               window is the last 590 sessions, from 2024-05-13
window rationale: the claim is about a PERSISTENT market-structure regularity published in 2008 and
               re-tested repeatedly since - AGENTS.md 19.4's third reason, a replication whose
               window the original fixes - and 2016-01-04 is the first session the minute feed
               serves. The recent window is read apart, as CHARTER A-003's caution asks of any
               published rule
country:       USA and developed markets
survivorship:  none - five index funds trading throughout
costs:         two sides a day for each arm, over the price that arm bought at: $0.005 a share
               (net), $0.0045 (the paper's convention from PR-031), $0.01 (cost_adverse). A cent on
               a $500 fund is 0.2 bps a side. Commission 0 (DR-039). Holding pays two sides in ten
               years, which rounds to nothing a session, and is reported as paying none
```

## 5. Method

* **The night** is `(next open + dividend on that date) / close − 1`, less two sides. A cash
  dividend detaches at the ex-date's OPEN, so the holder at the previous close receives it: every
  dividend goes to `N` and none to `D`. That is ownership, not a convention.
* **The session** is `close / open − 1`, less two sides.
* **Both prices come from the stored minutes** — the first regular minute's open and the last
  regular minute's close — so the two arms and the benchmark read one source. A session whose
  minutes cover under 90% of it is left out, and its neighbours lose the night that touches it.
* **The basket** is equal capital: each session's mean over the funds that read it.
* **The statistic.** The mean daily net return; a 95% moving-block bootstrap over calendar months,
  block 3, 10,000 resamples, seed 20260923.

### 5a. The split, and what it buys

```
split:           none - two halves of the same calendar day, both read, on every fund the store has
split buys:      nothing a split could buy: nothing is selected or tuned here
perturbations:   paper - $0.0045 a share a side
                 cost_adverse - a whole cent a share a side. Section 6 reads it
                 gross - no cost
```

**Diagnostics, printed and never read by §6:** each arm's and each fund's annualised return,
volatility, Sharpe ratio, CAGR and worst drawdown; holding each fund with its dividends beside them;
the dividends each fund paid over the window; and every excluded session by fund and reason.

## 6. Decision rule

**For the basket's overnight arm, in this order:** `REFUSED` under 1,000 sessions, 24 months or 90%
of the window read; `COST_FRAGILE` if the interval is wholly above zero and the cost-adverse
reading's is not; `RECENT_FRAGILE` if wholly above zero and the last 590 sessions' estimate is not
above zero; `ACCEPT` wholly above; `REJECT` wholly below; `INCONCLUSIVE` containing zero and wider
than 0.08 a day; `NULL` containing zero inside it.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *holding these funds only overnight earned more than nothing, net of two trades a day,
  and still does*: the first candidate whose return per unit of risk is worth putting beside
  holding the index, and worth a specification for a paper trial.
* `RECENT_FRAGILE` — *it earned over ten years and not over the last two*.
* `COST_FRAGILE` — *it earns at half a cent a share and not at a cent*.
* `REJECT` — *the night lost money net of costs*.
* `NULL` / `INCONCLUSIVE` — *within about ±10% a year of nothing* / *not established at this width*.

**Nothing is built on any branch.** A paper trial of it needs orders in the closing and opening
auctions, which `DR-027` §3.3's `day` time-in-force does not place; that is a specification and the
owner's call.

## 6a. Trials

**Ten** — two arms on each of five funds. Holding a fund is the benchmark and spends none, as
`PR-019b` and `PR-021` treated `SPY`. The tool reads **149** with `PR-032`; ten more take it to
**159** and the hurdle from **2.668 to 2.690** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** any other fund; any split of the session other than open-to-close; a
night held only on some weekdays or some regimes; the short side of either arm; any leverage.

## 7. Stopping rule

One run at the pinned knowledge instants. No fund, arm, costing or window tried after the first
result is seen.

## 8. Sample

```
minimum:       1,000 sessions across at least 24 months, and 90% of the window's sessions read
power floor:   0.08 points a day end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by `REJECT`, `NULL`, `INCONCLUSIVE`, `COST_FRAGILE` or `RECENT_FRAGILE`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* the two arms and the benchmark failing to add up — `N` and `D` compounded over a session must
  equal holding it to within a rounding error on any fund, because they are the same two prices and
  the same dividend;
* more than a tenth of any fund's sessions unread;
* a realised half-width outside half to twice §3's predicted 0.028;
* a fund's dividends over the window standing more than a tenth away from its published yield —
  a missing dividend would be money handed to neither arm.

**What would NOT settle anything:** an `ACCEPT` read as *a strategy to run tomorrow*. It would say
the night paid better than the day on five funds over ten years, at a cost model this project chose;
what it licenses is a specification, and the auctions it would trade in are not the prices measured
here.

## 10. Amendments

None.
