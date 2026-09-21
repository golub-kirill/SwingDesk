# PREREG: the same dollar twice — small caps overnight, SPY through the session, against holding SPY

```
id:            PR-035
date:          2026-09-20
author:        Claude, on the owner's choice of 2026-09-20. Shown that PR-034's night earns 13.8%
               a year against holding SPY's 15.7%, the owner said reproducibility is not the goal
               and asked for more RETURN; of the three honest levers offered - occupy the idle day
               slot, use leverage, or add capital - they chose "Занять дневной слот"
status:        registered, not run
verdict:       -
```

---

## 0. Refutation-family check

**searched:** `PR-030`..`PR-034` and their reports, `EVIDENCE_SUMMARY` §20-§32.

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-034` | small caps' night against holding them | `ACCEPT` — +13.83% a year at a Sharpe ratio of 1.06; the funds' own sessions lose 5.4% |
| `PR-033`, `SPY` (counted, never read) | `SPY`'s two halves | night +9.25% a year at 0.80, session **+4.94% at 0.37 with an interval touching zero**, holding +15.68% at 0.88 |
| `PR-031`, `PR-032` | an intraday rule on `SPY` and four other funds | `ACCEPT` on `SPY` then nothing on funds it was never fitted to |

**distinct because no study here has held two different assets in the two halves of one day.**
Every arm so far owned one fund or nothing. This owns small caps while the market is shut and `SPY`
while it is open, so **the same dollar is used twice a day** — and that is a book, not an arm.

**The arithmetic is known in advance and is written here so no result can be claimed as a
surprise.** The session legs of the book and of the benchmark are the same asset in the same hours
and cancel exactly, so

```
combined − hold SPY  =  small caps' night − SPY's night − SPY's extra trading
                     =  13.83% − 9.25% − about 0.4%  ≈  +4.2% a year
```

**What is NOT known, and is the reason to run it:** whether that difference's interval clears zero
once the legs are compounded session by session rather than averaged; whether it survives a whole
cent a share on **four** sides a day instead of two; and whether the book's own Sharpe ratio beats
the index it replaces. The author has read every number above and no number from the combination.

## 1. Question

Over 2016-01-04 .. 2026-09-18, does a book that holds `IJR`+`VB` from each close to the next open
and `SPY` from that open to that close earn **more per session than holding `SPY`** — net of four
auction fills a day, still positive at a whole cent a share a side, still positive over the last
590 sessions, and at a higher Sharpe ratio than holding `SPY`?

## 2. Hypothesis

**H1.** The per-session difference `combined − hold SPY` has a 95% interval wholly above zero; its
cost-adverse reading too; its estimate over the last 590 sessions is above zero; and the book's
Sharpe ratio is above holding `SPY`'s.

**H0.** Any one of those fails.

**Counted and never read:** the book's own level; holding `SPY`; each leg alone — small caps' night,
`SPY`'s night, `SPY`'s session.

## 3. Prediction, stated numerically before the run

```
primary quantity:  the mean over sessions of [(1 + small caps' night)(1 + SPY's session) - 1] less
                   holding SPY that session, both net of $0.005 a share a side; month-clustered
                   bootstrap
predicted:         +0.0166% a day, about +4.2% a year, between +0.02 and +0.07 a day at the
                   extremes. The predicted width is 0.027 points a day
                   (results/PR-035-power.json) - narrow because the day legs cancel and what is
                   left is two highly correlated nights - so ACCEPT needs the estimate above about
                   +0.0135 and the author expects it to clear.
                   **The cent is where this is expected to fail.** Four sides a day at a whole cent
                   costs about 2.6% a year more than the registered half cent, which leaves about
                   +1.6% a year against a half-width of 3.4%: COST_FRAGILE is the branch the author
                   rates likeliest, with ACCEPT second.
                   The book's own Sharpe ratio: about 1.05 against holding SPY's 0.88, so the
                   holding gate should pass. Its worst drawdown will be an equity drawdown, near
                   -35%
if H1 were TRUE:   all four readings above zero or above the benchmark, as section 6 orders them
minimum detectable effect:  0.019 points a day (0.00019, about 4.9% a year) - the predicted
                   half-width, 0.0135, x (1.96 + 0.84) / 1.96. That sits just ABOVE the predicted
                   effect, which is stated plainly: this study can see 4.2% a year only if the
                   estimate lands near or above its prediction
power floor:       0.08 points a day end to end (0.0008), PR-031's..PR-034's; it gates NULL only
```

## 4. Data

```
funds:         the night leg is PR-034's verdict basket, IJR and VB equally weighted; the session
               leg and the benchmark are SPY. No fund is chosen here that a reported study did not
               already carry
minutes:       Alpaca sip, adjustment=split, the scratchpad MinuteStore PR-031..PR-034 used
dividends:     Yahoo's cash dividends by EX-DATE, the same store PR-033 and PR-034 read
as_of:         minutes 2026-09-20T02:46:12.550112-05:00; bars and actions
               2026-09-20T06:28:46.070772+00:00
window:        2016-01-04 to 2026-09-18, PR-033's and PR-034's, so all three are readable side by
               side. The recent window is the last 590 sessions, from 2024-05-13
window rationale: PR-033's, unchanged - a market-structure regularity published in 2008 and
               re-tested since (AGENTS.md 19.4's third reason), and 2016-01-04 is the first
               session the minute feed serves
country:       USA
survivorship:  none - three index funds trading throughout
costs:         $0.005 a share a side (net), $0.0045 (the paper's), $0.01 (cost_adverse), on FOUR
               sides a day: sell the small caps and buy SPY at the opening cross, sell SPY and buy
               the small caps at the closing cross. Holding SPY pays two sides in ten years and is
               reported as paying none
dividends, and the trap: a book holding SPY only through the session NEVER receives SPY's
               dividends - they detach at the ex-date's open and are paid to whoever held
               overnight, which here is the small-cap leg. run_pr033.returns_of already pays every
               dividend to the night arm and none to the session arm, so the drag is inside the
               numbers. It is worth about 1.3% a year and it is the single largest term working
               against H1
```

## 5. Method

**`PR-033`'s and `PR-034`'s modules, imported unchanged**: the night is
`(next open + dividend) / close − 1` less two sides, the session is `close / open − 1` less two
sides, a session is read when its first and last stored minutes sit within five minutes of the
bells, and the night basket is equal capital across `IJR` and `VB`.

**The book compounds rather than adds**: a session's return is `(1 + night)(1 + session) − 1`,
because the second leg is bought with what the first returned. A session where either leg is
unread is not in the book.

**The statistic.** The mean per-session difference against holding `SPY`, paired by session; a 95%
moving-block bootstrap over calendar months, block 3, 10,000 resamples, seed 20260925.

### 5a. The split, and what it buys

```
split:           none - one book, one benchmark, both legs already measured by reported studies
split buys:      nothing a split could buy: no constant is chosen here
perturbations:   paper - $0.0045 a share a side
                 cost_adverse - a whole cent a share a side, which the decision rule gates on
                 gross - no cost
```

**Diagnostics, printed and never read by §6:** the book's and the benchmark's annualised return,
volatility, Sharpe ratio and worst drawdown; each leg alone; and the identity check — each fund's
night and session compounded must equal holding it, which `PR-033` and `PR-034` cleared at 3e-16.

## 6. Decision rule

**For `combined − hold SPY`, in this order:** `REFUSED` under 1,000 sessions, 24 months or 90% of
the window read; `COST_FRAGILE` if the interval is wholly above zero and the cost-adverse reading's
is not; `RECENT_FRAGILE` if wholly above zero and the last 590 sessions' estimate is not above
zero; `NOT_BETTER_HELD` if wholly above zero and the book's Sharpe ratio is not above holding
`SPY`'s; `ACCEPT` wholly above and past all three gates; `REJECT` wholly below; `INCONCLUSIVE`
containing zero and wider than 0.08 a day; `NULL` containing zero inside it.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *the book earns more than the index it replaces, at a cent a share, recently, and per
  unit of risk*: `CARD-002` becomes a two-leg card and the paper trial starts with the day leg in
  it.
* `COST_FRAGILE` — *it earns at half a cent and not at a cent*: the day leg is not worth its four
  fills, and `CARD-002` stays the night alone.
* `NOT_BETTER_HELD` / `RECENT_FRAGILE` — *more return, worse risk* / *it worked and stopped*.
* `REJECT` / `NULL` / `INCONCLUSIVE` — *holding `SPY` is better* / *the same within about ±10% a
  year* / *not established at this width*.

**Nothing is built on any branch**, and the card that would carry it is `CARD-002`, whose size is
the owner's and whose passes do not exist yet.

## 6a. Trials

**One** — the combined book. Its legs are not new: the night basket is `PR-034`'s verdict and
`SPY`'s session is `PR-033`'s `SPY-D`, both already counted. The tool reads **165** with `PR-034`;
one more takes it to **166** and the hurdle from **2.702 to 2.704** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** any other day-leg fund; any weighting other than equal across the night
funds; leverage of any kind; holding the day leg only on some sessions; and the book at any size
other than fully invested, which is a `CARD-002` question rather than a study one.

## 7. Stopping rule

One run at the pinned knowledge instants. No leg, fund, costing or window tried after the first
result is seen.

## 8. Sample

```
minimum:       1,000 sessions across at least 24 months, and 90% of the window's sessions read
power floor:   0.08 points a day end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by any branch other than `ACCEPT`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* the identity check failing on any fund — each fund's two arms compounded must equal holding it;
* `SPY`'s session leg differing from `PR-033`'s `SPY-D` reading, or the night basket from
  `PR-034`'s, by more than a rounding error: they are the same code on the same stores;
* more than a tenth of the window's sessions unread;
* a realised half-width outside half to twice §3's predicted 0.0135.

**What would NOT settle anything:** an `ACCEPT` read as *the book is safe*. It holds equities
around the clock in two different wrappers; its drawdown is an equity drawdown, and §3 predicts
about −35%.

## 10. Amendments

None.
