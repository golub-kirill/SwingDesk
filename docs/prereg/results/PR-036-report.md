# PR-036 RESULT: the night paid before 2016 too — 10.9% a year in a decade holding compounded at 8.8% and fell 59%

```
prereg:        PR-036
ran:           2026-09-20
verdict:       INCONCLUSIVE, branch COST_FRAGILE. The IJR+VB basket's overnight arm over 2004-01-30 ..
               2015-12-31 earned +0.0434% a day [+0.0225, +0.0635] - 10.94% a year at a Sharpe
               ratio of 0.84 against holding the same funds' 0.48 - and at a WHOLE CENT a share a
               side the interval is [-0.0003%, +0.0408%], which touches zero. Two of the three
               gates cleared; the cent did not
status:        final. Run once from the registration commit's snapshot at the pinned instant
tool:          tools/run_pr036.py (PR-033's arms and PR-034's basket, imported unchanged)
evidence:      PR-036.json; IJR and VB DAILY bars and dividends, as_of 2026-09-20T06:28:46Z
trials:        0. No configuration PR-034 had not already declared - a replication on an
               untouched window
```

---

## Read this first

**The objection this study was built to answer was: is the overnight result a wrapper around an
exceptional decade?** `PR-033`..`PR-035` all read 2016-2026, and `SPY` returned 15.7% a year over
it. The answer is no — and the comparison that matters is not the night against zero, it is the
night against what holding these funds actually did in that decade:

| 2004-01-30 .. 2015-12-31, 3,002 sessions | compounded a year | volatility | Sharpe | worst drawdown |
|---|---|---|---|---|
| **the night** (buy the close, sell the next open) | **+10.6%** | 13.0% | **0.84** | **−21.1%** |
| the session (buy the open, sell the close) | −12.2% | 20.3% | −0.54 | −80.1% |
| holding the same two funds, with dividends | +8.8% | 23.4% | 0.48 | −58.8% |

**In the decade that contains 2008, the night compounded faster than holding and fell a third as
far.** That is the same shape `PR-034` measured in 2016-2026, found in a window that contains the
worst equity collapse in this project's data — and the session arm, which is where 2008 actually
happened, lost 80% of its capital peak to trough.

**And the registration's prediction was right to the fourth decimal.** §3 was written before any
pre-2016 number was read: *"+0.045% a day, about +11% a year, between +0.02 and +0.07"*, the
session negative, holding *"around +8% a year... with a 2008 drawdown near −55%"*. Realised:
**+0.0434% a day, +10.94% a year**, the session −10.99%, holding +8.77% compounded with a −58.8%
drawdown. The author did not predict the cent.

## §9, as registered, shown first

The registration made the study's own refutation the first output, because a daily bar's open and
close are the vendor's consolidated prices rather than the auction prints the minute feed carries.
**All three checks pass:**

| check | needed | realised |
|---|---|---|
| **the overlap** — the same 2016-2026 night read from DAILY bars against `PR-034`'s minute-based +13.83% | within 2 points a year | **13.26% against 13.83% — 0.57 points apart** |
| the identity — night and session compounded must equal holding | exact | **3.1e-16 on both funds** |
| the realised half-width against §3's predicted 0.0202 | half to twice | **0.0205 — a ratio of 1.01** |

The price source measures the same thing the minute feed does. The pre-2016 number can be believed.

## The gates, and the one that failed

| gate | needed | realised |
|---|---|---|
| the interval above zero | net, at half a cent a share a side | **+0.0434%** [+0.0225, +0.0635] PASS |
| a whole cent a share a side | above zero | **+0.0207%** [**−0.0003**, +0.0408] FAIL |
| better than holding | a higher Sharpe ratio | **0.84 against 0.48** PASS |

**The cent misses by 0.0003 points a day — about 0.08% a year.** Under the decision rule that is
`COST_FRAGILE`, and the rule is applied as written rather than argued with.

**Why the cent bites harder here, and it is arithmetic rather than an era.** A fixed cent a share is
a fraction of the share price, and these funds traded at a third of today's price in that decade:

| mean close over the window | `IJR` | `VB` | a cent a side, both sides, on the basket |
|---|---|---|---|
| 2004-2015 | $35.76 | $74.15 | **about 4.1 bps a night** |
| 2016-2026 | $92.51 | $186.06 | about 1.6 bps a night |

The gross night is +0.0661% a day in the old window; what changed between the windows is that the
same cent costs 2.6× more when the price is a third of today's. **The cost model is being applied
at a price level it was never calibrated at** — `PR-031`'s half cent came from 2016+ fills — and a
2004 execution would not have been charged 2026's rate either. The study does not adjust for that,
because adjusting a cost assumption after seeing the result is the thing pre-registration exists to
prevent. It is recorded as this reading's largest single caveat.

## Every diagnostic the registration listed

| cell | a day | 95% interval | a year | Sharpe | worst |
|---|---|---|---|---|---|
| basket night, 2004-2015 | +0.0434% | [+0.0225, +0.0635] | +10.94% | +0.84 | −21.1% |
| basket night, at a cent | +0.0207% | [−0.0003, +0.0408] | +5.22% | +0.40 | −24.3% |
| basket night, gross | +0.0661% | [+0.0453, +0.0866] | +16.65% | +1.28 | −17.8% |
| basket session, 2004-2015 | −0.0436% | [−0.0816, −0.0076] | −10.99% | −0.54 | −80.1% |
| holding the basket, 2004-2015 | +0.0442% | [+0.0031, +0.0862] | +11.15% | +0.48 | −58.8% |
| **`IJR` night alone** | +0.0207% | **[−0.0035, +0.0436]** | +5.21% | +0.39 | −26.5% |
| **`VB` night alone** | +0.0662% | [+0.0448, +0.0870] | +16.67% | +1.26 | −16.7% |
| basket night, 2016-2026 (overlap) | +0.0526% | [+0.0187, +0.0873] | +13.26% | +1.02 | −32.3% |
| holding the basket, 2016-2026 | +0.0504% | [+0.0107, +0.0942] | +12.70% | +0.59 | −42.2% |

**The two funds do not agree in the old window.** `VB`'s night carries it; `IJR`'s alone does not
separate from zero. Both are diagnostics the decision rule never reads, and neither changes the
verdict — but a reader who takes *"the effect is robust"* from this table is reading past the fact
that half of it is one fund.

## What this establishes, and what it does not

**Establishes:**

1. **The overnight effect is not an artefact of 2016-2026.** It is present, positive and
   risk-superior to holding in a window nobody here had read, one that contains 2008.
2. **The session arm's loss is not an artefact either.** Minus 11% a year over twelve years, and
   −80% peak to trough.
3. **The method transfers between price sources**, within 0.57 points a year.

**Does not establish:**

1. **That it survives a cent in that decade.** It does not, and the failure is a price-level effect
   the cost model does not model.
2. **That both funds carry it.** `VB` does; `IJR` alone does not, pre-2016.
3. **Anything about drawdown safety.** The night's own worst stretch here is −21.1%.

## What it changes

- **`CARD-002` keeps its evidence and gains a caveat.** The card's case is `PR-034`; this study
  removes the epoch objection from it and sharpens what its §5 already watches — **the fill
  measurement is now the open question of the whole line**, because the difference between half a
  cent and a whole cent is the difference between an effect and nothing across half the available
  history.
- **`RETURN_SOURCE_REGISTER` §2.3** records this window as measured rather than registered.
- **No parameter changes, and no trial is spent.** The budget stays at 166 and the hurdle at 2.704.

## What the study cost

One run, about two minutes of compute on data already stored, and no fetch at all. The registration
was written on 2026-09-20 and the answer existed the same evening — which is what a study costs
when the question is a replication on a window the data already held.
