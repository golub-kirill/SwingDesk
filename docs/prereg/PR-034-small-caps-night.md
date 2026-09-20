# PREREG: small caps' night, asked properly — on funds PR-033 never read, at a cent a share, against holding them

```
id:            PR-034
date:          2026-09-20
author:        Claude, on the owner's choice of 2026-09-20. Shown PR-033's COST_FRAGILE and the
               one lead inside it - IWM's night at a Sharpe ratio of 0.91 against holding's 0.56,
               read after the fact - the owner chose "Да, проверяем"
status:        registered, not run
verdict:       -
```

---

## 0. Refutation-family check

**searched:** `PR-033` and its report, `EVIDENCE_SUMMARY` §20-§31, `CHARTER` A-003.

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-033` | the night against the session on `SPY`, `QQQ`, `IWM`, `DIA`, `EFA` | `COST_FRAGILE`: the basket's night +8.2% a year net at half a cent, +6.6% at a cent with the interval touching zero; Sharpe 0.67 against holding's 0.81 |
| `PR-033`, `IWM` (counted, never read) | the same two arms on small caps | night **+13.1% a year at 0.91**, session **−3.3% at −0.18**, holding 12.8% at 0.56 |
| `PR-021`..`PR-023`, `PR-031`, `PR-032` | four daily classes and an intraday rule | none beats holding per unit of risk; the intraday rule did not generalise |

**distinct because `IWM`'s reading was one of ten arms and was chosen after the results were seen.**
This asks it as a hypothesis, on funds no tool in this repository has read, with the two gates
`PR-033` failed written into the decision rule rather than reported beside it.

**What is honestly new here, and what is not — stated before the run.** `IJR`, `VB` and `IWM` hold
overlapping companies: a different wrapper on the same asset class is **not** an independent sample
of small-cap returns. What this can establish is that `IWM`'s number was not its own wrapper's
quirk, and that the effect survives a cent a share and beats holding the same funds. What it cannot
establish is that small-cap night returns are an independent confirmation of the `IWM` reading.

**What is known in advance:** every number in `PR-033`. Nothing here has read a minute of `IJR`,
`VB` or `MDY`; their minutes were fetched after this section was written, and the power estimate
below lets only widths out.

## 1. Question

Over 2016-01-04 .. 2026-09-18, does holding an equally weighted basket of `IJR` and `VB` **only
overnight** earn a positive mean daily return net of two trades a day — still positive at a whole
cent a share a side, still positive over the last 590 sessions, and at a better return per unit of
risk than holding the same two funds?

## 2. Hypothesis

**H1.** The basket's overnight arm has a 95% interval wholly above zero; its cost-adverse reading
too; its estimate over the last 590 sessions is above zero; and its Sharpe ratio is above that of
holding the same basket with dividends.

**H0.** Any one of those fails.

**Counted and never read:** each fund alone; the session arm; the difference `N − D`; holding each
fund; and **`MDY`**, the mid-cap boundary case, on both arms.

## 3. Prediction, stated numerically before the run

```
primary quantity:  the mean over sessions of the equally weighted IJR+VB basket's overnight net
                   return - (next open + dividend) / close - 1, less two sides at $0.005 a share;
                   month-clustered bootstrap
predicted:         +0.048% a day, about +12% a year, between +0.02 and +0.08. IWM's night
                   earned 13.1% a year over the same window and these funds hold overlapping
                   companies, so the arithmetic is IWM's less the extra cost of a cheaper share:
                   half a cent on IJR's ~$110 is 0.45 bps a side, against SPY's 0.1. The predicted
                   width is 0.069 points a day (results/PR-034-power.json), so ACCEPT needs the
                   estimate above about +0.034 and a zero-containing interval is NULL.
                   **The cent is the tightest gate**: a whole cent a side on these funds is about
                   2.2% a year, so the cost-adverse reading sits that far under the net one and its
                   lower bound may not clear zero. The author expects ACCEPT or COST_FRAGILE, and
                   rates the holding gate the likeliest to pass - holding IJR or VB over this
                   window is a Sharpe ratio near 0.5, and a night at 12% a year on two thirds of
                   the volatility is near 0.85
if H1 were TRUE:   an interval wholly above zero, a cost-adverse interval wholly above zero, a
                   positive recent estimate, and a Sharpe ratio above holding's
minimum detectable effect:  0.049 points a day (0.00049, about 12.4% a year) - the difference this
                   window detects with 80% power: the predicted half-width, 0.0344, x (1.96 + 0.84)
                   / 1.96. It sits just under what IWM's night earned, so an effect that size is
                   readable here and a materially smaller one is not. From `run_pr034.py --power`,
                   widths only under `power_pr019.assert_no_effect_leaked`
power floor:       0.08 points a day end to end (0.0008), PR-031's and PR-033's; it gates NULL only
```

## 4. Data

```
funds:         IJR (S&P SmallCap 600) and VB (Vanguard Small-Cap) carry the verdict; MDY (S&P
               MidCap 400) is the boundary case, counted and never read. Chosen for what they are -
               small-cap index funds with minutes back to 2016 - before any of their minutes was
               fetched. IWM is PR-033's and is not in the basket
minutes:       Alpaca sip, adjustment=split, fetched by tools/fetch_minutes.py into the scratchpad
               MinuteStore PR-031..PR-033 used
dividends:     Yahoo's cash dividends by EX-DATE (tools/fetch_history.py): IJR 108 actions, VB 67,
               MDY 126
as_of:         minutes 2026-09-20T02:46:12.550112-05:00; bars and actions
               2026-09-20T06:28:46.070772+00:00. 2,693 sessions of each fund,
               none served empty
window:        2016-01-04 to 2026-09-18, the same as PR-033's, so the two are readable side by
               side. The recent window is the last 590 sessions, from 2024-05-13
window rationale: PR-033's, unchanged - a persistent market-structure regularity published in 2008,
               AGENTS.md 19.4's third reason, and 2016-01-04 is the first session the minute feed
               serves
country:       USA
survivorship:  none - three index funds trading throughout
costs:         PR-033's: $0.005 a share a side (net), $0.0045 (the paper's), $0.01 (cost_adverse).
               These funds cost MORE per share than SPY in relative terms - a cent on IJR's ~$110
               is 0.9 bps a side against SPY's 0.2 - which is why the cent is a gate here and not
               a perturbation
```

## 5. Method

**One rule is NOT `PR-033`'s, and it is written here because it was chosen before any return was
read.** `PR-033` required a session's stored minutes to cover 90% of it, because its rule read every
minute. This study reads TWO prices, the open and the close. Measured on every seventh session of
the window before this registration - a count of bars, never a return - `VB`'s median coverage is
**0.877** and `MDY`'s **0.928**, so `PR-033`'s rule would have discarded 61% of `VB`'s sessions and
36% of `MDY`'s, while **the opening minute and the closing minute are present on 100% of them**: a
less liquid fund simply has minutes in which nothing traded. A session is therefore read here when
its first stored minute sits within 5 minutes of the opening bell and its last within 5 of the
close (`run_pr034.BELL`), and a session failing either is counted by which one.

**Everything else is `PR-033`'s module, imported and unchanged**: the night is `(next open + dividend) / close − 1`
less two sides; the session is `close / open − 1` less two sides; the dividend is paid to the night
because it detaches at the ex-date's open; prices come from the stored minutes; a session under 90%
covered is left out. The basket is equal capital across `IJR` and `VB`. The statistic is the mean
daily net return with a 95% moving-block bootstrap over calendar months, block 3, 10,000 resamples,
seed 20260924.

### 5a. The split, and what it buys

```
split:           none - two halves of the day on three funds, all read, nothing selected
split buys:      nothing a split could buy: no constant is chosen here
perturbations:   paper - $0.0045 a share a side
                 cost_adverse - a whole cent a share a side, which the decision rule gates on
                 gross - no cost
```

**Diagnostics, printed and never read by §6:** each fund's arms and holding, annualised return,
volatility, Sharpe ratio, CAGR and worst drawdown; `MDY` entirely; the dividends each fund paid; the
excluded sessions by fund and reason; and the identity check — the two arms compounded must equal
holding on any session with no dividend.

## 6. Decision rule

**For the `IJR`+`VB` basket's overnight arm, in this order:** `REFUSED` under 1,000 sessions, 24
months or 90% of the window read; `COST_FRAGILE` if the interval is wholly above zero and the
cost-adverse reading's is not; `RECENT_FRAGILE` if wholly above zero and the last 590 sessions'
estimate is not above zero; **`NOT_BETTER_HELD` if wholly above zero and its Sharpe ratio is not
above holding the same basket's**; `ACCEPT` wholly above and past all three gates; `REJECT` wholly
below; `INCONCLUSIVE` containing zero and wider than 0.08 a day; `NULL` containing zero inside it.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *small caps' night earns, at a cent a share, in the recent window, and better per unit
  of risk than holding them*: the first thing in this project to clear that bar, and worth a
  specification for a paper trial.
* `NOT_BETTER_HELD` — *it earns, and holding the same funds is still the better deal per unit of
  risk*: `PR-033`'s reading again, on small caps.
* `COST_FRAGILE` — *it earns at half a cent and not at a cent*: untradeable at this size.
* `RECENT_FRAGILE` — *it earned over ten years and not over the last two*.
* `REJECT` / `NULL` / `INCONCLUSIVE` — *it loses* / *within about ±10% a year of nothing* / *not
  established at this width*.

**Nothing is built on any branch.** The arms trade the closing and opening auctions, which
`DR-027` §3.3's `day` time-in-force does not place; a specification is the owner's call.

## 6a. Trials

**Six** — two arms on each of three funds. Holding is the benchmark and spends none. The tool reads
**159** with `PR-033`; six more take it to **165** and the hurdle from **2.690 to 2.702** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** any other fund; `IWM` at a second look; any split of the session other
than open-to-close; any weighting other than equal; leverage; the short side of either arm.

## 7. Stopping rule

One fetch of the minutes, repeated only to fill sessions that failed. One run at the pinned
knowledge instants. No fund, arm, costing, gate or window tried after the first result is seen.

## 8. Sample

```
minimum:       1,000 sessions across at least 24 months, and 90% of the window's sessions read
power floor:   0.08 points a day end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by any branch other than `ACCEPT`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* the two arms compounded failing to equal holding on a session with no dividend — the same
  identity `PR-033` cleared at 3e-16;
* more than a tenth of any fund's sessions unread;
* a realised half-width outside half to twice §3's predicted 0.0344;
* a fund's dividends over the window standing more than a tenth away from its published yield.

**What would NOT settle anything:** an `ACCEPT` read as *independent confirmation of `IWM`*. §0 says
why: these funds hold overlapping companies. It would establish that the reading is not one
wrapper's, and that it clears the two gates `PR-033` failed.

## 10. Amendments

None.
