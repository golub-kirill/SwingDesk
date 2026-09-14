# PR-023 RESULT: five asset classes timed never fell more than 13% in nineteen years — and earned 4% a year; neither they nor the five held beat SPY per unit of risk

```
prereg:        PR-023
ran:           2026-09-14
verdict:       INCONCLUSIVE, as section 3 predicted. TIMED_5's Sharpe on its excess over BIL is
               0.380 against SPY's 0.543 - a difference of -0.163 [-0.566, +0.190], 0.755 wide
               against the 0.40 floor. Beside it and never read: a worst drawdown in nineteen years
               of -13.1% against SPY's -55.2%, and 4.01% a year against 10.70%. HOLD_5, the same
               five never timed, reads NULL: -0.169 [-0.345, +0.007], inside the floor
status:        final - two arms fixed before the run, no selection, no split; section 9 reproduced
               both power widths and the traded units to the digit
tool:          tools/run_pr023.py, sized by tools/power_pr023.py, data by tools/fetch_history.py
evidence:      PR-023.json, PR-023-power.json
trials:        2, declared before the run
```

---

## Read this first

**The timed five-asset book is the calmest thing this programme has measured, and it is not better
than the index per unit of risk.** Holding a fifth each of US stocks, foreign stocks, Treasuries,
real estate and commodities — each fifth in T-bills while its own trend is broken — lost no more
than **13.1%** from any peak in nineteen years. Through 2008 it **gained 2.5%** while `SPY` fell
55.2%. And it compounded at **4.01% a year** against `SPY`'s 10.70%, and T-bills' 1.39%.

**Per unit of risk it trails.** On the excess over T-bills its Sharpe ratio is 0.380 to `SPY`'s
0.543. The interval — −0.566 to +0.190 — contains zero, so the verdict is `INCONCLUSIVE` as §3
predicted; the point estimate is negative.

**Diversification alone did not help on this window, and that one the study CAN say.** The same five
held, never timed, read `NULL` at −0.169 [−0.345, +0.007]: within about 0.18 of `SPY`'s risk-adjusted
return, and on the side below it. The reason is the window: the other four funds compounded at 2.5%
to 5.2% a year while `SPY` did 10.7%.

**Why the yardstick matters, stated first because it decides how to read everything below.** A fixed
mix of `SPY` and T-bills has EXACTLY `SPY`'s Sharpe on the excess — the T-bill share adds nothing and
removes risk in proportion. So "beats `SPY` per unit of risk" here means "beats every fixed `SPY` and
T-bill mix at the same risk". The timed book does not: a fixed 38% `SPY` at its volatility earned
5.29% a year to its 4.01% — and fell 23.0% in 2008 where the timed book did not fall at all.

## §9, which had to hold before anything else could be read

| check | registered | realised |
|---|---|---|
| `TIMED_5`'s width, against the power estimate | the same, to the digit | **0.755 and 0.755** |
| `HOLD_5`'s width, against the power estimate | the same, to the digit | **0.353 and 0.353** |
| `TIMED_5`'s units traded a year | 3.73 | **3.73** |
| unpriced holdings | none | **none**, both arms |
| `HOLD_5` switches, and its share outside risk assets | none, and none | **0, and 100% in risk assets** |

**All hold.** The run reproduced its own sizing; the two readings are of the series the estimate
sized.

## The verdict, as §6 reads it

```
TIMED_5  excess Sharpe, book - SPY:  -0.163  [-0.566, +0.190]   width 0.755   INCONCLUSIVE
HOLD_5   excess Sharpe, book - SPY:  -0.169  [-0.345, +0.007]   width 0.353   NULL
```

| | `TIMED_5` | `HOLD_5` | `SPY` |
|---|---|---|---|
| Sharpe on the excess over `BIL` | **0.380** [0.013, 0.768] | **0.373** [−0.028, 0.838] | **0.543** [0.180, 0.999] |
| Sharpe at rf = 0 (the convention), difference to `SPY` | −0.049 | −0.144 | — |
| compound return a year | 4.01% | 5.91% | 10.70% |
| volatility | 7.4% | 14.4% | 19.7% |
| worst drawdown | **−13.1%**, 2011-04-29 → 2012-06-04 | −47.1%, 2008-05 → 2009-03 | −55.2%, 2007-10 → 2009-03 |
| arithmetic return difference to `SPY`, points a year | −7.91 [−13.71, −2.20] | −5.32 [−8.48, −2.20] | |
| share in risk assets | 60.2% | 100% | 100% |
| traded a year, `DR-005` cost | 3.73 units, 0.93 points | 0.30 units, 0.08 points | |

**The study's verdict is `TIMED_5`'s: `INCONCLUSIVE`.** `HOLD_5`'s `NULL` is reported beside it and
does not replace it.

## §3's prediction, graded

| | predicted | realised |
|---|---|---|
| `TIMED_5` branch | `INCONCLUSIVE` | **`INCONCLUSIVE`** |
| `TIMED_5` centre | −0.10 to +0.20 | **−0.163** — below the band |
| `HOLD_5` branch | `REJECT` or `NULL` | **`NULL`** |
| `HOLD_5` centre | −0.30 to 0.00 | **−0.169** — in the band |
| widths | 0.755 and 0.353 | **0.755 and 0.353** |

**Both branches were right, and the rule's centre was too kind for the fourth study running.** At
zero cost `TIMED_5`'s difference is −0.037, so costs took about 0.13 of Sharpe; at three times
`DR-005` it is −0.415.

## Diagnostics — registered, printed, never read by §6

**Each asset over the window** — the reason both books trail:

| | `SPY` | `EFA` | `IEF` | `VNQ` | `DBC` |
|---|---|---|---|---|---|
| compound return a year | 10.70% | 4.53% | 3.15% | 5.23% | 2.49% |
| months above its average, of 232 | 181 | 143 | 121 | 132 | 120 |

**Every fall of `SPY` deeper than 15%:**

| `SPY`'s fall | `SPY` | `TIMED_5` | `HOLD_5` | the recovery: `SPY` / `TIMED_5` / `HOLD_5` |
|---|---|---|---|---|
| 2007-10-09 → 2009-03-09 | −55.2% | **+2.5%** | −43.6% | +124.2% / +14.0% / +98.7% |
| 2018-09-20 → 2018-12-24 | −19.3% | −8.2% | −12.0% | +24.4% / +3.9% / +15.8% |
| 2020-02-19 → 2020-03-23 | −33.7% | −5.5% | −26.2% | +51.2% / +2.4% / +29.9% |
| 2022-01-03 → 2022-10-12 | −24.5% | −3.5% | −16.9% | +34.1% / +2.5% / +15.9% |
| 2025-02-19 → 2025-04-08 | −18.8% | −6.5% | −10.4% | +23.6% / +5.8% / +13.5% |

**The timed book lost less than half of `SPY`'s fall in every one — under a sixth of it in 2020 and
2022, and gained through 2008 — and recovered between a twentieth and a quarter as much.** It holds
so little risk that it neither falls nor rises with the market.

**The last 48 months**, `AGENTS.md` §19's current market: `TIMED_5` −0.625 [−1.512, −0.083] —
wholly below zero, 6.34% a year to `SPY`'s 19.81%; `HOLD_5` −0.283 [−0.896, +0.316], 11.22% a year.

## Exploratory, after the run — against a fixed mix of `SPY` and T-bills at the same risk

*Not registered, chosen after the result was seen (`PREREG_TEMPLATE` rule 3), read by nothing.* A
fixed mix has `SPY`'s excess Sharpe exactly, so this is the comparison the primary already implies —
laid out in the units the owner would feel:

| | the book | a fixed mix at its volatility | |
|---|---|---|---|
| `TIMED_5` | 4.01% a year, worst −13.1% | **37.7% `SPY`: 5.29% a year**, worst −23.0% | last 48 months 6.34% against **10.33%** |
| `HOLD_5` | 5.91% a year, worst −47.1% | **73.3% `SPY`: 8.54% a year**, worst −42.9% | last 48 months 11.22% against **15.78%** |

**At the same volatility, a fixed `SPY`-and-T-bill mix out-earned both books.** The timed book's one
advantage is the depth of the worst fall — −13.1% against −23.0%, and that difference is 2008.

## What this establishes, and what it does not

**Established, at the registered design:**

* **The five asset classes held did not beat `SPY` per unit of risk on 2007–2026**, to within about
  0.18 of Sharpe — `HOLD_5`'s `NULL`.
* **Timing them by their own trend built a book whose worst fall in nineteen years was 13.1%**, at a
  compound return of 4.01% a year — measured on one path, not estimated.
* **Its risk-adjusted return is not shown to differ from `SPY`'s** — the interval is ±0.38 wide, and
  its point estimate is below.

**Not established:**

* **That diversification fails in general.** One window, dominated by US stocks and by a decade of
  near-zero rates and a commodity bust; the published evidence spans a century.
* **That the next crash will look like these five.** The timed book met each at a month-end.
* **The exploratory mixes as findings.** They were chosen after the run.

## What this licenses

> *On 2007–2026, five asset classes — timed by their own trend or held — did not earn more per unit
> of risk than `SPY`; timed, they built a book that barely fell and barely grew.*

No parameter moves and no card exists.

## What it changes

**Four classes have now been measured on this window, and none beats holding `SPY` per unit of
risk**: the relative-strength family (`EVIDENCE_SUMMARY` §20), short-term reversal (§21), the index
with a trend exit (§22), and five asset classes timed or held (§23). What they differ in is how much
risk they carry, and on the excess-Sharpe yardstick every fixed `SPY`-and-T-bill mix sits on the same
line. **So what is left is not a search for an edge but a choice of where on that line to sit — how
deep a fall the owner's capital can take — and a choice about the one thing the timed books buy:
a shallower worst fall in a slow bear market.** That choice is the owner's and it is not investment
advice.

## What the study cost

**Two trials.** The programme's count moves from **121 to 123** and the hurdle from **2.597 to 2.603**
sd(SR) — derive both with `python tools/trial_budget.py`. The run took ten seconds from the
registration commit's own snapshot.
