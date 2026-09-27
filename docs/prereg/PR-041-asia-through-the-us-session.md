# PREREG: do Asia-Pacific funds earn while their home markets are shut — through the US session?

```
id:            PR-041
date:          2026-09-27
author:        Claude, on the owner's choice of 2026-09-27 (DR-055 section 1.4): the third leg to try
               is foreign equity held through the US session. The owner asked for the three-leg
               book's last three years and chose to register first rather than look first
status:        reported   (2026-09-27 - results/PR-041-report.md)
verdict:       INCONCLUSIVE, branch COST_FRAGILE - the basket's US session earned +0.0253% a day
               [+0.0079, +0.0451] after the fees, 6.05% a year, and at half a cent a share a side
               [-0.0228, +0.0147]. Its Sharpe ratio, 0.63, is not above holding's 0.64. Secondary:
               the three-leg book returned 24.3% a year over the last three years against the
               two-leg book's 23.7% and SPY's 22.9%, and no interval tells them apart
```

---

## 0. Refutation-family check

**searched:** `PR-033`..`PR-036`, `PR-040`, `EVIDENCE_SUMMARY` §31-§35, `RETURN_SOURCE_REGISTER` §2.3.

**found:** `PR-033` split five US-listed funds' days into night and session; on `EFA` - developed
markets outside North America - the night was negative and the session positive, **read after the
fact** and never registered. `PR-034` and `PR-036` established the night on US small caps.

**distinct because no study here has split a fund whose home market is shut through the whole US
session.** For Japan, China, Hong Kong, India, Korea, Taiwan, Australia and Singapore the US session
is the home market's night; the mechanism `RETURN_SOURCE_REGISTER` §2.3 records predicts the return
lives there. `EFA` is excluded: it was read, and Europe overlaps New York by two hours.

**What is known in advance:** `PR-033`'s `EFA` reading, and that Asia-Pacific markets returned
modestly over 2016-2026 against the US. The funds' daily bars were fetched on 2026-09-27; nothing
from them has been computed but the power estimate's width. The overnight effect's literature is
outside knowledge (Cliff, Cooper and Gulen 2008; Lou, Polk and Skouras 2019).

## 1. Question

Over 2016-01-04 .. 2026-09-25, does an equally weighted basket of `EWJ`, `FXI`, `EWH`, `INDA`,
`EWY`, `EWT`, `EWA` and `EWS`, held only from each US opening auction to that session's closing
auction, earn a positive mean daily return after the venue's fees - and more per unit of risk than
holding the same basket?

## 2. Hypothesis

**H1.** The basket's session arm has a 95% interval wholly above zero after the fees, and above zero
with half a cent a share a side added; its mean over the last 48 months is above zero; and its
Sharpe ratio exceeds holding the basket's.

**H0.** Any of those fails.

**A registered secondary, counted and never read by §6:** the three-leg book - `IJR`+`VB` by night,
the day split equally between `SPY` and this basket - against `SPY` held and against `PR-035`'s
two-leg book, over the window and over the last three years (from 2026-09-26 back to 2023-09-26),
by `DR-047` §3.5's geometric excess.

## 3. Prediction, stated numerically before the run

```
primary quantity:  the mean over sessions of the basket's session-arm net return, month-clustered
                   moving-block bootstrap (block 3, 10,000 resamples, seed 20260927)
predicted:         about +0.030% a day (+7.6% a year), between 0.00 and +0.06. If the premium lives
                   in the home market's night, the session arm carries the basket's whole return and
                   the night gives some back, as the session did for small caps. The Sharpe gate is
                   expected to pass; the cost gate at half a cent is the risk - these funds trade near
                   $20-70, where half a cent is 1-2.5 basis points a side
if H1 were TRUE:   the interval above zero at the fees and at half a cent, the last 48 months above
                   zero, and a Sharpe ratio above holding's
minimum detectable effect:  0.000266 a day (about 6.7% a year) - the width with bars and fees,
                   0.000373 end to end (results/PR-041-power.json), x (1.96 + 0.84) / 1.96 / 2.
                   The prediction sits a little above it; the author puts ACCEPT near even odds
power floor:       0.0008 a day end to end, PR-031's..PR-036's; it gates NULL only
```

## 4. Data

```
funds:         EWJ, FXI, EWH, INDA, EWY, EWT, EWA, EWS - the eight largest Asia-Pacific equity
               markets with a US-listed single-country fund, equal weight. Fixed before any bar
               was fetched. For the secondary: IJR, VB and SPY
prices:        DAILY bars, open and close, tools/fetch_history.py, with cash dividends by ex-date;
               the bars stand in for the auction crosses, checked against a sample of crosses (9)
as_of:         bars 2026-09-27T17:23:09.819950+00:00
window:        2016-01-04 .. 2026-09-25, 2,697 sessions
window rationale: the leg would join PR-035's book, whose window this is, and DR-055's proof reads
               the last 48 months as a gate of its own, so the current market is not averaged away
               (AGENTS.md 19.4's replication reason; 19.3's cost is paid in the stated width)
holdout:       2004-01-01 .. 2015-12-31 is NOT read (DR-049 section 4.2); reading it later is its
               own registration
country:       USA-listed; the underlying markets are Asia-Pacific
survivorship:  none - eight index funds trading throughout the window
costs:         the venue's fees at the 2026-09-01 schedule (PR-040's): SEC 0.0000206 of value sold,
               TAF $0.000195 a share sold, CAT $0.000003 a share either side
```

## 5. Method

**`PR-033`'s arms on daily bars, `PR-036`'s way:** the session is `close / open − 1` less its two
sides; the night is `(next open + dividend) / close − 1` less its two sides, the dividend paid to the
night because it detaches at the ex-date's open; holding is close to close with the dividend and no
cost. The basket is equal capital across the funds that trade that session.

### 5a. The split, and what it buys

```
split:           none - one basket, one arm, one window
split buys:      nothing a split could buy: no constant is chosen here
perturbations:   half_cent - $0.005 a share a side on top of the fees; its interval is a gate (6)
                 cent - $0.01 a share a side on top of the fees
                 gross - no cost
```

**Diagnostics, printed and never read by §6:** each arm's annual return, volatility, Sharpe ratio and
worst drawdown; the night arm; the identity check; the secondary book.

## 6. Decision rule

**In this order:** `REFUSED` when §9's basis check fails, or under 1,000 sessions or 24 months;
`COST_FRAGILE` when the interval is wholly above zero and the half-cent one is not; `RECENT_FRAGILE`
when the last 48 months' mean is not above zero; `NOT_BETTER_HELD` when the session arm's Sharpe ratio
is not above holding the basket's; `ACCEPT` past all three; `REJECT` wholly below zero;
`INCONCLUSIVE` containing zero and wider than 0.0008 a day; `NULL` containing zero inside it.

**What each licenses:**

* `ACCEPT` — *the Asia-Pacific basket pays through the US session*: a third leg worth registering
  INSIDE the book, priced at its crosses, before any paper order.
* `COST_FRAGILE` / `RECENT_FRAGILE` / `NOT_BETTER_HELD` — *it pays, and not robustly enough to add*.
* `REJECT` / `NULL` / `INCONCLUSIVE` — *no third leg here at this width*.

## 6a. Trials

**Two:** the session arm, and the three-leg book as a registered secondary - a configuration is
evaluated even when it carries no verdict. The count moves from 168 to 170.

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** Europe; any other fund, weight or day split; the 2004-2015 holdout; any
conditioning on regime or volatility.

## 7. Stopping rule

One run at the pinned instants. Nothing is tried after the result is seen.

## 8. Sample

```
minimum:       1,000 sessions across at least 24 months
power floor:   0.0008 a day end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by any branch other than `ACCEPT`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* **the basis check failing** - thirty seeded sessions a fund are read from the SIP tape
  (`run_pr041.py --sample-out`, then `tools/fetch_auction_prints.py`); a median gap between the
  crosses and the bars above 5 basis points on any fund means the bars are not the auction's prices,
  and the study refuses;
* the identity check failing: at zero cost, night and session must compound to holding on every
  session with no dividend;
* a realised half-width outside half to twice the power estimate's 0.000187.

## 10. Amendments

None.
