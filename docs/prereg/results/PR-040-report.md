# PR-040 RESULT: at the prices an auction order gets, the book beat holding SPY by 4.4% a year — and by 0.7% over the last four years

```
prereg:        PR-040
ran:           2026-09-27
verdict:       ACCEPT. PR-035's book - IJR and VB from each closing cross to the next opening cross,
               SPY from that opening cross to that closing cross - every fill at the listing
               market's official cross and charged the venue's regulatory fees, beat holding SPY by
               a geometric +4.39% a year [+0.95%, +8.30%] over 2016-01-04 .. 2026-09-18, and by
               +0.73% a year over the last 48 months (2022-10 .. 2026-09). Both of DR-055's
               conditions for proof (1) are met
status:        final. Run once, at the registered bar instant and the auction store's recorded one,
               with tools/run_pr040.py unchanged since the registration commit bff98f0
tool:          tools/run_pr040.py (run_pr025's cross rule and basis factor, run_pr033's arms,
               run_pr035's book, run_pr037's excess and bootstrap - all imported unchanged)
evidence:      PR-040.json; PR-040-power.json. Bars and dividends as_of
               2026-09-27T16:22:36.363912+00:00 (tools/fetch_history.py); 16,158 cross windows
               from the SIP tape as_of 2026-09-27T21:12:04+00:00 (tools/fetch_auction_prints.py).
               Both stores are scratch copies, not committed; the two fetch tools rebuild them
trials:        1, as registered. 167 -> 168
```

---

## Read this first

**Proof (1) of `DR-055` is met, and it is met narrowly where it matters most.** Over the whole
decade the book beat `SPY` by 4.4 points a year at the prices its orders would actually get. Over
the last four years it beat `SPY` by 0.7 points a year. Both are above zero, and that is exactly
what the registration asked; the second one is small.

| at the crosses, with the fees | book | holding `SPY` |
|---|---|---|
| compound annual return | **20.2%** | **15.1%** |
| annual volatility | 18.7% | 17.7% |
| Sharpe ratio | **1.08** | 0.88 |
| worst drawdown | −36.2% | −33.7% |
| geometric excess, whole window | **+4.39% [+0.95%, +8.30%]** | |
| geometric excess, last 48 months | **+0.73%** | |

**In money, on the paper account's $100,000:** the decade's margin is roughly $4,400 a year more
than holding the index; the last four years' is roughly $730 a year. The first is the effect the
registration was built to detect. The second is what the current market has paid, and it is the
number to carry into the paper run.

**Proof (2) is still owed**: sixty clean paper sessions of the whole book (`DR-056`), counting from
the first whole book journalled. **No real money moves** — meeting both proofs returns the question
to the owner (`DR-055`, `CHARTER` A-001).

## §9, as registered, shown first

| check | registered | measured | |
|---|---|---|---|
| sessions, months | at least 1,000 and 24 | **2,693 sessions, 129 months** | pass |
| sessions carrying all six crosses | at least 95% | **2,688 of 2,693, 99.8%** | pass |
| median gap, cross against its own bar, every fund and side | at most 5 basis points | **0.78 bp** at worst (`SPY`'s open); every other fund and side under 0.001 bp | pass |
| reproduction: `PR-035`'s costing on the bars through this code | within 2 points a year of +3.25% | **+2.73%**, 0.52 points away | pass |
| identity: at zero cost, each fund's night and session compound to holding | on every session with no dividend | worst gap **3.1 × 10⁻¹⁶** on all three | pass |
| realised half-width against the power estimate's 0.0384 | between half and twice | **0.0367**, 0.96 times | pass |

**The median cannot see a single bad cross, and a single bad cross is exactly what this book is
exposed to**: it holds `IJR` and `VB` only through the night, so an opening cross on the wrong scale
is a night return nothing offsets. The priced sessions were therefore read one by one after the
run, through `run_pr040.load` in a scratch script that is not committed. Every fund's opening and
closing gaps were sorted, and the extreme nights on the crosses were compared with the same nights on
the bars. **No cross is on the wrong scale.** `IJR`'s 2-for-1 split, which the smoke read found on
the tape, is undone on every session. The worst closing gap on any fund is 0.11%. At most two opening
gaps a fund exceed 0.5%, and the largest is `SPY`'s on 2016-11-07, at 1.40%. On `SPY` 2016-11-07,
`SPY` 2017-05-17 and `VB` 2016-10-10 - and on several smaller ones - the bar's night is exactly zero, which reads as the bar vendor
carrying the previous close as the open — *conjecture, not checked* (`AGENTS.md` §10.4). Compounded
gross, the night on the crosses and on the bars agree: `IJR` 3.58 against 3.62, `VB` 6.63 against
6.42.

**Five sessions lacked a cross** on at least one fund — 2019-08-12, 2023-06-05 and 2025-09-05 on
all three, and `VB` on 2017-03-20 and 2025-08-29. As registered, each was priced at its bar and
charged a whole cent a share on that side.

**The book has 2,692 days here and 2,691 in `PR-035`**, whose prices were the first and last stored
minute. The cause of the one-session difference was not checked; the reproduction check above is
what bounds it.

## The registered reading and its perturbations

| costing | geometric excess | 95% interval | last 48 months | book CAGR | `SPY` CAGR |
|---|---|---|---|---|---|
| **crosses and fees** (primary) | **+4.39%** | **[+0.95%, +8.30%]** | **+0.73%** | **20.23%** | 15.14% |
| crosses, fees and half a cent a share a side | +1.54% | [−1.82%, +5.34%] | −1.41% | 16.92% | 15.14% |
| crosses, no fee | +5.54% | [+2.07%, +9.49%] | +1.81% | 21.56% | 15.14% |
| `PR-035`'s costing on the bars | +2.55% | [−0.84%, +6.55%] | −0.31% | 18.10% | 15.14% |

**§3 predicted +4.3% a year, interval about [+0.5%, +8.1%], and the last 48 months around +1.5%.**
The whole-window estimate and interval landed where predicted. The last 48 months came in at half
the prediction.

**The fees cost 1.14 points of excess a year** (gross +5.54% against +4.39%). That is under §3's
1.5-point estimate, which was built on the SEC fee being charged on the book's whole equity twice a
session.

**Half a cent a share a side costs 2.86 points**, and it removes both conditions. So the whole
difference between this study and `PR-035`'s `COST_FRAGILE` is the price source. An auction order
pays the cross and no spread, and that is the only reason the modelled half cent does not apply.

## Each leg, at the crosses with the fees

| | CAGR | volatility | Sharpe | worst drawdown |
|---|---|---|---|---|
| the night, `IJR`+`VB` | 15.34% | 13.0% | **1.16** | −32.1% |
| the day, `SPY` | 4.24% | 13.4% | 0.38 | −25.2% |
| the book, both compounded | 20.23% | 18.7% | 1.08 | −36.2% |
| holding `SPY` | 15.14% | 17.7% | 0.88 | −33.7% |

**The night carries the book.** Small caps held only while the market is shut earned as much as
holding `SPY` all the time, at three quarters of the volatility, and the day leg adds 4.2% a year on
top by using the same dollar during the session.

**Six-factor attribution (`DR-049`), a diagnostic §6 does not read:** alpha **+4.62% a year,
t = 3.31**. The market beta is 1.00 and every other loading is under 0.09 in size; R² is 0.95, over
2,658 days to 2026-07-31, where the factor file ends. The margin is not a size or value tilt in
disguise.

## What this does not settle

* **That the broker routes a `cls` or `opg` order into the listing auction.** The paper venue
  simulates its fills, so this is not observable there (§9). If a real fill lands half a cent a side
  worse than the cross, the last four years' margin is gone: the half-cent row above is that case.
* **The current margin is thin.** The last four years' +0.73% a year is a point estimate with no
  interval, and the registration gated on its sign alone.
* **The drawdown is an equity drawdown.** The book fell 36.2% at its worst, 2.5 points more than the
  index.
* **Three things are out of the study's scope and none is measured here.** Taxes: every gain the
  book realises is held for under a day. The day leg's round trip in `SPY` is a same-day buy and
  sell, which FINRA's pattern-day-trader margin rule governs; its current thresholds were not
  checked here. And the fee schedule is 2026-09-01's, charged on every session of the decade as
  registered.

## What happens next

1. **Proof (2)**: the paper passes carry the whole book from Monday 2026-09-28 (`DR-056`); sixty
   clean sessions are counted from the first whole book journalled.
2. **`PR-041`**, the third leg, is registered and waiting on its basis sample. Its registered
   secondary is the three-leg book over the window and over the last three years.
3. **Nothing else is run on this question.** One run at the recorded instants (§7).
