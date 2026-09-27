# PR-041 RESULT: Asia-Pacific funds do earn through the US session — 6% a year after the fees, gone at half a cent, and no better than holding them

```
prereg:        PR-041
ran:           2026-09-27
verdict:       INCONCLUSIVE, branch COST_FRAGILE. The equally weighted basket of EWJ, FXI, EWH,
               INDA, EWY, EWT, EWA and EWS, held from each US opening auction to that session's
               close, earned +0.0253% a day [+0.0079%, +0.0451%] after the venue's fees over
               2016-01-04 .. 2026-09-25 - 6.05% a year - and at half a cent a share a side its
               interval is [-0.0228%, +0.0147%], which contains zero. The first gate the rule
               checks fails, so the branch is COST_FRAGILE
status:        final. Run once, at the registered bar instant and the auction sample's recorded one,
               with tools/run_pr041.py unchanged since the registration commit
tool:          tools/run_pr041.py (PR-033's arms, PR-036's bars, PR-040's fees, PR-037's excess -
               imported unchanged)
evidence:      PR-041.json; PR-041-power.json. Daily bars and dividends as_of
               2026-09-27T17:23:09.819950+00:00 (tools/fetch_history.py); 480 cross windows - thirty
               seeded sessions a fund, both auctions - from the SIP tape as_of
               2026-09-27T21:19:27+00:00 (tools/fetch_auction_prints.py). Both stores are scratch
               copies; the two fetch tools and `--sample-out` rebuild them
trials:        2, as registered - the session arm and the three-leg book. 168 -> 170
```

---

## Read this first

**The mechanism showed up, and it is not a leg worth adding.** Asia-Pacific funds earned more
through the US session, when their home markets are shut, than overnight: 6.05% a year against
2.75%. But the edge is thin enough that half a cent a share a side erases it. Per unit of risk it
is also no better than simply holding the same funds (Sharpe ratio 0.63 against 0.64).

**The owner's question — the three-leg book over the last three years — is the registered
secondary, and here it is:**

| 2023-09-26 .. 2026-09-25, on bars with the fees | CAGR | volatility | Sharpe | worst drawdown |
|---|---|---|---|---|
| **three legs**: `IJR`+`VB` by night, the day half `SPY` and half the Asia basket | **24.3%** | 16.1% | **1.43** | −20.0% |
| **two legs** (`PR-035`'s book) | 23.7% | 17.0% | 1.33 | −21.2% |
| **holding `SPY`** | 22.9% | 15.3% | 1.42 | −18.8% |
| three legs over `SPY`, geometric | **+1.10%** [−7.04%, +8.83%] | | | |
| three legs over two legs, geometric | +0.49% [−2.74%, +4.49%] | | | |

**Over the last three years all three returned about the same**, and neither interval can tell
them apart; they are sixteen and seven points wide. The three-leg book was a little ahead of both
and a little smoother than the two-leg one, and neither is distinguishable from luck at this
length.

| 2016-01-04 .. 2026-09-25, the same construction | CAGR | volatility | Sharpe | worst drawdown |
|---|---|---|---|---|
| three legs | 21.4% | 17.3% | 1.21 | −36.3% |
| two legs | 20.4% | 18.7% | 1.09 | −36.2% |
| holding `SPY` | 15.3% | 17.7% | 0.89 | −33.7% |
| three legs over `SPY` | **+5.35%** [+1.27%, +9.88%] | | | |
| three legs over two legs | +0.83% [−1.21%, +2.96%] | | | |

**Over the decade the book beats the index and the third leg adds nothing distinguishable.** The
two-leg book on these bars (20.4%) lands next to `PR-040`'s reading on the crosses (20.2%, a week
shorter), which is the cross-check the two studies give each other.

## §9, as registered, shown first

| check | registered | measured | |
|---|---|---|---|
| sessions, months | at least 1,000 and 24 | **2,697 sessions, 129 months** | pass |
| median gap between a sampled cross and its own bar, each fund | at most 5 basis points | **0.0004 bp at worst** — the bars ARE the crosses on the median session | pass |
| identity: at zero cost, night and session compound to holding | on every session with no dividend | worst gap **3.2 × 10⁻¹⁶**, all eight | pass |
| realised half-width against the power estimate's 0.000187 | between half and twice | **0.000187**, 1.00 times | pass |

**The median can hide a stale open, and a stale open would inflate exactly this arm.** A bar whose
open repeats the previous close moves that night's return into the session. So after the run, a
scratch script that is not committed counted every session whose bar open equals the previous close
exactly. It found 0.8% to 3.7% of sessions a fund, with `EWS` the highest. On the five such sessions
the seeded sample happened to draw, the real opening cross sat within 5.5 basis points of the bar:
those were genuine opens that matched the prior close, not stale data. **`FXI` has the noisiest
opens**: a median gap of 1.2 basis points, with 8 of its 30 opening crosses more than 5 basis points
from the bar and the worst at 0.76%. It passes the registered tolerance. Its direction was not
measured.

## The registered reading

| the basket's session arm | mean a day | 95% interval | a year | Sharpe | worst drawdown |
|---|---|---|---|---|---|
| **the venue's fees** (primary) | **+0.0253%** | **[+0.0079%, +0.0451%]** | **6.05%** | **0.63** | −12.6% |
| fees and half a cent a share a side (a gate) | −0.0053% | [−0.0228%, +0.0147%] | −1.83% | −0.13 | −37.9% |
| fees and a cent a share a side | −0.0359% | [−0.0533%, −0.0159%] | −9.11% | −0.89 | −67.1% |
| gross | +0.0280% | [+0.0105%, +0.0478%] | 6.76% | 0.70 | −11.9% |

**The gates, in the registered order**:

1. **Cost: FAILS.** The fees interval is wholly above zero; the half-cent one is not.
2. **The last 48 months: passes.** The mean is +0.0333% a day, above the whole window's.
3. **Sharpe above holding: would have FAILED.** 0.631 against 0.639.

The branch is the first failure, `COST_FRAGILE`. §6 licenses one sentence: *it pays, and not
robustly enough to add*.

**§3 predicted +0.030% a day, between 0.00 and +0.06, and named the cost gate as the risk.** Both
held: +0.025%, and the cost gate is where it failed. The prediction also said the Sharpe gate would
pass, and it would not have, by a hair.

## Each arm, at the fees

| the Asia basket | CAGR | volatility | Sharpe | worst drawdown |
|---|---|---|---|---|
| the US session (their night) | 6.05% | 10.1% | 0.63 | −12.6% |
| the US night (their day) | 2.75% | 14.8% | 0.26 | −34.6% |
| holding, no cost | 10.47% | 18.2% | 0.64 | −35.2% |

**The session carries more than the night, as the mechanism predicts, but the night does not give
it back.** For US small caps, `PR-034` found the session LOSING 5.4% a year while the night earned 13.8%. Here both
halves are positive, so timing the basket saves drawdown (−12.6% against −35.2%) and costs return,
at about the same return per unit of risk. That is a smoother holding, not a source of excess.

## What this does not settle

* **Whether real auction fills land on the cross.** The same residual as `PR-040`, and here it
  decides the verdict. At the fees the leg pays; at half a cent it does not.
* **The three-leg secondary is on bars, not crosses.** The basis sample says the bars match the
  crosses at the median, and `PR-040` says the same for the two-leg funds. The book was not re-priced
  on crosses.
* **2004-2015 was not read**, as registered.

## What happens next

**No third leg.** The paper account keeps carrying the two-leg book (`DR-056`), which is what
`DR-055`'s proof (2) counts. A third leg returns only with a new registration and a new reason.
Re-reading this basket until it passes is not a reason.
