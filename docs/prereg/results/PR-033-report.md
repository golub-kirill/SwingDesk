# PR-033 RESULT: the night pays and the session barely does — but the night does not beat holding the fund, and a whole cent a share takes it to zero

```
prereg:        PR-033
ran:           2026-09-20
verdict:       INCONCLUSIVE, branch COST_FRAGILE. The basket's overnight arm +0.0325% a day
               [+0.0045, +0.0602] - wholly above zero at half a cent a share a side, and
               +0.0263% [-0.0017, +0.0542] at a whole cent, which touches it
status:        final. Run once from the registration commit's snapshot at the pinned instants
tool:          tools/run_pr033.py
evidence:      PR-033.json; five funds' minutes 2016-01-04 .. 2026-09-18 and their cash dividends
trials:        10, declared before the run (two arms x five funds)
```

---

## Read this first

**The night carries the return and the session does not.** Over 2,692 sessions on an equally
weighted basket of `SPY`, `QQQ`, `IWM`, `DIA` and `EFA`, holding only overnight earned **+8.2% a
year** net of two trades a day; holding only through the session earned **+3.4%**. The claim
published since 2008 reproduces here, and §3 predicted the size of it before the run: +0.035% a day
predicted, +0.0325% measured.

**It does not beat holding the fund per unit of risk, which is this project's bar.** The night's
Sharpe ratio is **0.67** against **0.81** for holding the same basket with its dividends. The night
earns a bit over half the return at two thirds of the volatility, and its worst drawdown, −30.1%, is
not much better than holding's −34.4%. On four of the five funds the same is true.

**`IWM` is the exception, and it is the strongest thing in this study.** Small caps' whole return is
overnight: the night earned **+13.1% a year at a Sharpe ratio of 0.91**, the session **−3.3% at
−0.18**, and holding `IWM` earned 12.8% at 0.56. It is a secondary reading, counted and never read,
and it was not picked in advance.

**A whole cent a share a side takes the verdict to zero.** That is what `COST_FRAGILE` means here:
two trades every day is 500 round trips a year, and the strategy's whole edge is about 1.6 bps a
day. The cost assumption is not a detail of this study — it is the study.

## §9, as registered, shown first

| check | registered | realised |
|---|---|---|
| the two arms compounded must equal holding, on sessions with no dividend | a rounding error | **3e-16** on every fund — the identity holds to machine precision |
| sessions unread, any fund | under a tenth | **0**, except 3 thin `QQQ` sessions |
| realised half-width against §3's 0.028 | half to twice | **0.0278**, 0.99× |
| each fund's dividends against its published yield | within a tenth | `SPY` $64.36, `QQQ` $20.45, `IWM` $24.14, `DIA` $64.28, `EFA` $23.23 over the window — each within a tenth of its yield times its average price |

## The readings

| mean daily net return | estimate | 95% interval | a year | Sharpe |
|---|---|---|---|---|
| **the basket, overnight** (the verdict) | **+0.0325%** | **[+0.0045, +0.0602]** | +8.2% | 0.67 |
| at a whole cent a share a side | +0.0263% | [−0.0017, +0.0542] | +6.6% | 0.54 |
| at the paper's $0.0045 | +0.0331% | [+0.0051, +0.0608] | +8.3% | 0.68 |
| gross, no cost | +0.0386% | [+0.0106, +0.0663] | +9.7% | 0.79 |
| the basket, the session (counted, never read) | +0.0133% | [−0.0086, +0.0371] | +3.4% | 0.25 |
| the basket, night less session (counted, never read) | +0.0191% | [−0.0215, +0.0588] | +4.8% | 0.27 |
| **holding the basket** with dividends (benchmark) | +0.0581% | [+0.0285, +0.0905] | +14.6% | **0.81** |
| the basket's night, last 590 sessions (the gate) | +0.0506% | [−0.0036, +0.0939] | +12.8% | **1.16** |

**The recent window is the best part of it.** Over the 590 sessions since 2024-05-13 the night
earned 12.8% a year at a Sharpe ratio of 1.16 and a −15.2% worst drawdown. The gate asked only for
a positive estimate and got one; the interval touches zero, as a window this short must.

## Every fund, both halves of the day

| | night, a year | night Sharpe | session, a year | session Sharpe | holding, a year | holding Sharpe |
|---|---|---|---|---|---|---|
| `SPY` | +9.3% | 0.80 | +4.9% | 0.37 | +15.7% | 0.88 |
| `QQQ` | +11.9% | 0.87 | +6.8% | 0.39 | +20.9% | 0.94 |
| **`IWM`** | **+13.1%** | **0.91** | **−3.3%** | **−0.18** | +12.8% | 0.56 |
| `DIA` | +8.3% | 0.73 | +3.8% | 0.30 | +13.8% | 0.80 |
| `EFA` | −1.7% | −0.12 | +4.6% | 0.44 | +10.1% | 0.58 |

`EFA` is the mirror: a fund whose companies trade while New York sleeps has its news in the price
before the open, and its New York session is where its return appears. That is the shape the
hypothesis predicts for it, and §3 said so before the run.

## What this establishes, and what it does not

**Established:** over 2016-2026, on five index funds, holding overnight earned more than nothing at
half a cent a share a side — and not at a cent. The session earned little. The two arms are exactly
the halves of holding the fund, so this is a decomposition and not a model: nothing is fitted here.

**Not established:**

* **that the night beats holding.** It does not, on the basket: 0.67 against 0.81. This study was
  registered to ask whether the night earns, and it does; the bar `EVIDENCE_SUMMARY` §20-§23 sets is
  a different question and the answer to it here is no.
* **that `IWM`'s night is an edge.** It is one of ten arms, read after the fact. Asking it properly
  is a new registration on funds this study did not read.
* **that these prices are tradeable.** The night arm needs the closing auction and the opening
  auction every day — `cls` and `opg` orders, neither of which `DR-027` §3.3's `day`
  time-in-force places, and `PR-025` and `PR-030` are the only things here that have ever priced an
  auction fill.
* **what it costs to do daily.** Half a cent a share on `SPY` is 1 bp; on `IWM`, at a fifth of
  `SPY`'s price, it is 2.3 bps a side. The cost-adverse reading is the honest bound and it contains
  zero.

## What it changes

* **The overnight decomposition is now measured in this repository**, and it is the first thing
  here whose recent two years are stronger than its ten-year average.
* **A candidate worth one more question, and only one:** small caps' night, asked on funds this
  study never read, at a cost model that survives a cent. If that reads clear of zero, it is the
  first thing in this project with both an edge and a reason to expect one.
* **Nothing is built.** The auctions it would trade in are not the prices measured here, and the
  owner decides whether a specification is worth writing.

## What the study cost

No fetch beyond the five funds' dividends (5 requests); one run of fifteen minutes. Ten trials,
149 to 159.
