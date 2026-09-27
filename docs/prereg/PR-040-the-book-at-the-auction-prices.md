# PREREG: does `PR-035`'s book beat holding `SPY` at the prices an auction order actually gets?

```
id:            PR-040
date:          2026-09-27
author:        Claude, on the owner's ruling of 2026-09-27 (DR-055): PR-035's book is the
               project's main hypothesis, no real money moves before it is proven, and proof (1)
               is this study - the book priced at the official auction prints and the venue's fees
status:        reported   (2026-09-27 - results/PR-040-report.md)
verdict:       ACCEPT - the book beat holding SPY by a geometric +4.39% a year [+0.95%, +8.30%] at
               the official crosses with the venue's fees, and by +0.73% a year over the last 48
               months. DR-055's proof (1) is met; at half a cent a share a side neither condition
               holds
```

---

## 0. Refutation-family check

**searched:** `PR-033`..`PR-036` and their reports, `EVIDENCE_SUMMARY` §31-§35, `DR-048`, `DR-055`.

**found:**

| prior work | prices | what it found |
|---|---|---|
| `PR-034` | first and last stored minute | small caps' night +13.8% a year at Sharpe 1.06 |
| `PR-035` | the same | this book: 18.9% a year against `SPY`'s 15.7%; the contrast +3.25% a year at half a cent a share a side, **+0.35% at a cent**, 6.1% gross - `COST_FRAGILE` |
| `PR-036` | daily bars, 2004-2015 | the night paid before 2016 too; `COST_FRAGILE` again at a cent |

**distinct because every one of them priced a fill as a stored price plus a modelled cost.** None
read the price an auction order is filled at. This study changes only that, on `PR-035`'s own window
and rule.

**What is known in advance, and it is a lot.** `PR-035`'s every number; and a smoke read of three
2016 sessions on 2026-09-27, which established the UNITS and nothing about returns: the tape flags
both crosses on all three funds, `VB`'s crosses equal its bars' open and close to the cent, `SPY`'s
sit within two basis points, and `IJR`'s are exactly twice its bars - a 2-for-1 split the bars carry
and the tape does not. An exploratory three-year reading on daily bars was shown to the owner the same
day (book +94.7% gross, +83.2% at half a cent, against `SPY`'s +85.0%) and is not relied on. **No
cross has been priced into a return.**

## 1. Question

Over `PR-035`'s window, 2016-01-04 .. 2026-09-18, does `PR-035`'s book - `IJR` and `VB` in equal
halves from each closing cross to the next opening cross, `SPY` from that opening cross to that
closing cross - earn a higher geometric return than holding `SPY`, when every fill is priced at the
listing market's official cross and charged the venue's regulatory fees?

## 2. Hypothesis

**H1.** The book's geometric excess over `SPY` held has a 95% interval wholly above zero over the
window, and its point estimate over the last forty-eight months of the window is above zero -
`DR-055` §1.3's proof (1), exactly.

**H0.** Either fails.

**Counted and never read by §6:** the costings in §5a; the night, the day leg and holding, each
described; each fund's crossed share and basis gap; and the six-factor alpha `DR-049` requires.

## 3. Prediction, stated numerically before the run

```
primary quantity:  (1 + CAGR_book) / (1 + CAGR_SPY) - 1, monthly, 95% paired moving-block bootstrap
                   over calendar months (block 3, 10,000 resamples, seed 20260927) -
                   run_pr037.geometric_excess and paired_bootstrap, imported unchanged
predicted:         about +4.3% a year, interval roughly [+0.5, +8.1]. PR-035's gross margin was
                   6.1% a year and its half-cent costing charged about 2.6% a year; auction pricing
                   replaces that with the fees, about 1.5% a year - the SEC fee alone is ~1.0%,
                   because the book sells its whole equity twice a session - and the crosses are
                   expected to sit on the stored prices within a basis point or two, as the smoke
                   read found. The last 48 months: positive, smaller, around +1.5% a year.
                   The author puts ACCEPT at a little better than even
if H1 were TRUE:   the interval's lower end above zero and the last 48 months above zero
minimum detectable effect:  0.0548 a year - the realised width with bars standing in for the
                   crosses, 0.0768 end to end (results/PR-040-power.json), x (1.96 + 0.84) / 1.96 / 2.
                   The prediction sits BELOW it: a true +4.3% is detected somewhat under half the
                   time at 80%-power terms, and the author says so rather than widening anything
power floor:       0.04 a year end to end; it gates NULL only
```

## 4. Data

```
funds:         IJR and VB (the night, equal halves) and SPY (the day, and the benchmark held)
prices:        the listing market's opening cross (condition O) and closing cross (condition 6)
               from the SIP tape, tools/fetch_auction_prints.py, chosen by run_pr025.cross_price
               and brought onto the bars' basis by run_pr025.adjustment_factor, both unchanged.
               Daily bars and dividends from tools/fetch_history.py for the basis, the fallback
               and the dividends
as_of:         bars 2026-09-27T16:22:36.363912+00:00; the auction store's instant is recorded by
               the run
window:        2016-01-04 .. 2026-09-18, PR-035's measured span, 2,691 sessions, 129 months
window rationale: this re-prices a registered result, and the window is fixed by that original
               (AGENTS.md 19.4's replication reason); DR-055's proof reads the last 48 months as
               its own condition, so the current market is not averaged away. No window is held
               out (DR-049 section 4.2): the tape's history begins in 2016, and 2004-2015 has no
               cross to read
country:       USA
survivorship:  none - three index funds trading throughout
costs:         the venue's regulatory fees at the 2026-09-01 schedule for every session
               (docs/decisions/measurements/venue-fees-2026-09-05.json): SEC 0.0000206 of value
               sold, FINRA TAF $0.000195 a share sold, CAT $0.000003 a share either side; no
               commission. A session missing a fund's cross is priced at that bar and charged a
               whole cent a share on that side
```

## 5. Method

**`PR-033`'s arms and `PR-035`'s book, with only the price changed.** The night is `(opening cross +
dividend) / previous closing cross − 1`, less the buy's and the sell's fees; `SPY`'s session is
`closing cross / opening cross − 1` less its two sides; holding `SPY` is closing cross to closing
cross with its dividend and no cost. The book compounds the night basket and `SPY`'s session, session
by session (`run_pr035.compounded`). Daily returns compound into calendar months, and the months
carry the statistic.

**Fees are charged on the TAPE's price**, the price the shares traded at, because a per-share fee
is levied on shares; returns are computed on the bars' basis, where every split is already undone.

### 5a. The split, and what it buys

```
split:           none - one book, one benchmark, a re-pricing of a registered rule
split buys:      nothing a split could buy: no constant is chosen here
perturbations:   auction_plus_half_cent - the crosses and fees plus $0.005 a share a side
                 gross - the crosses, no fee
                 bars_pr035 - PR-035's own costing on bar prices, the reproduction check (section 9)
```

## 6. Decision rule

**In this order:** `REFUSED` under 1,000 sessions or 24 months, when fewer than 95% of sessions
carry all six crosses, when a fund's median gap between its cross and its own bar exceeds 5 basis
points on either side, or when the reproduction check fails (§9); `ACCEPT` when the interval is
wholly above zero AND the last 48 months' estimate is above zero; `RECENT_FRAGILE` when the interval
is wholly above zero and the last 48 months' is not; `REJECT` when the interval is wholly below zero;
`INCONCLUSIVE` when it contains zero and is wider than 0.04 a year; `NULL` when it contains zero
inside it.

**What each licenses — one sentence, and no money:**

* `ACCEPT` — *proof (1) is met*: the book beat `SPY` at the prices its orders get. Proof (2), sixty
  clean paper sessions of the whole book, is still required, and meeting both returns the question
  to the owner (`DR-055`, `CHARTER` A-001).
* `RECENT_FRAGILE` — *it beat `SPY` over the decade and not in the market of the last four years*.
* `INCONCLUSIVE` / `NULL` — *not established at this width* / *no margin to find*.
* `REJECT` — *the book loses to `SPY` at its real prices*, and the main hypothesis falls.

## 6a. Trials

**One.** The rule is `PR-035`'s, but a new price source with a verdict of its own is a new look at
the data, and counting it is the conservative reading. The count moves from 167 to 168.

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** any fund, weight or window other than `PR-035`'s; any other cross rule;
any conditioning on regime, year or volatility; the third leg (`DR-055` §1.4), which is its own
registration.

## 7. Stopping rule

One run at the recorded instants. No costing, fund, window or rule tried after the result is seen.

## 8. Sample

```
minimum:       1,000 sessions across at least 24 months; 95% of sessions fully crossed
power floor:   0.04 a year end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by any branch other than `ACCEPT`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* **the reproduction check failing** — `PR-035`'s own costing on the bars, run through this code,
  must land within 2 points a year of `PR-035`'s registered +3.25%: further apart and this code does
  not build the book `PR-035` built;
* **the basis check failing** — a median cross-to-bar gap above 5 basis points is two prices
  measuring different things, which is how `PR-025`'s first run became a unit error;
* the identity check failing: at zero cost, each fund's night and session must compound to holding
  on every session with no dividend;
* a realised half-width outside half to twice the power estimate's 0.0384.

**What would NOT settle anything:** an `ACCEPT` read as *real money is now safe*. The residual
assumption - that the broker routes a `cls` or `opg` order into the listing auction - is not
observable on a paper account, and the book's worst drawdown is an equity drawdown.

## 10. Amendments

None.
