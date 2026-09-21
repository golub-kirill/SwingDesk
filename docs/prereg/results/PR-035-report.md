# PR-035 RESULT: the book returns 18.9% a year against holding SPY's 15.7% — and the 3.2 points between them do not survive a cent a share

```
prereg:        PR-035
ran:           2026-09-20
verdict:       INCONCLUSIVE, branch COST_FRAGILE, the branch section 3 rated likeliest. The book
               less holding SPY is +0.0129% a session [+0.0002, +0.0272] - +3.25% a year, clearing
               zero by two ten-thousandths of a point - and at a whole cent a share a side it is
               +0.0014% [-0.0113, +0.0157], which does not
status:        final. Run once from the registration commit's snapshot at the pinned instants
tool:          tools/run_pr035.py (PR-033's and PR-034's arms, imported unchanged)
evidence:      PR-035.json; IJR, VB and SPY minutes 2016-01-04 .. 2026-09-18 and their dividends
trials:        1, declared before the run (the combined book)
```

---

## Read this first

**The book earns more than the index, and the margin is not established.**

| | a year | volatility | Sharpe | worst drawdown |
|---|---|---|---|---|
| **the book** — small caps at night, `SPY` in the session | **+18.9%** | 18.7% | **1.01** | −34.8% |
| holding `SPY` with its dividends | +15.7% | 17.7% | 0.89 | −33.8% |
| the night alone (`PR-034`) | +13.8% | 13.1% | 1.06 | −31.6% |

The difference the study registered — the book less holding `SPY`, paired session by session — is
**+3.25% a year**, and its interval's lower bound is **+0.0002% a session**. It clears zero by a
rounding error.

**Three readings say the same thing from three directions**, and §3 predicted all three:

| reading | a year | interval a session |
|---|---|---|
| at half a cent a share a side (registered) | +3.25% | [+0.0002, +0.0272] |
| **at a whole cent a share a side** | **+0.35%** | **[−0.0113, +0.0157]** |
| the last 590 sessions | +0.56% | [−0.0268, +0.0298] |
| gross, no cost at all | +6.14% | [+0.0116, +0.0386] |

**Four fills a day is what eats it.** Gross the book beats the index by 6.1% a year; at half a cent
that is 3.2%; at a cent it is 0.35% and indistinguishable from nothing. The edge and the trading
cost are the same size.

**§3 predicted +4.2% a year and named `COST_FRAGILE` the likeliest branch before the run.** The
measurement is +3.25%, and the branch is `COST_FRAGILE`.

## §9, as registered, shown first

| check | registered | realised |
|---|---|---|
| each fund's two arms compounded equal holding it | a rounding error | **3e-16** on `IJR`, `VB` and `SPY` |
| the legs reproduce `PR-033`'s and `PR-034`'s readings | more than a rounding error is a defect | `night-small-caps` **+13.83%** a year (PR-034: +13.83%); `day-SPY` **+5.01%** (PR-033: +4.94%); `night-SPY` **+9.19%** (PR-033: +9.25%). The small differences are this study's session rule, which reads the sessions `PR-033`'s 90% coverage rule dropped |
| sessions unread | under a tenth | **0** — 2,691 of 2,692 possible pairs, the one loss being a fund's first session |
| realised half-width against §3's 0.0135 | half to twice | **0.0135**, 1.00× |

## What the arithmetic said, and what the run did with it

§0 wrote the identity before the run: the day legs of book and benchmark are the same asset in the
same hours and cancel, so

```
book − hold SPY  =  small caps' night − SPY's night − SPY's extra trading
                 =  13.83% − 9.19% − about 1.4%  =  +3.25% a year
```

and that is exactly the measurement. **The extra trading came out larger than the 0.4% §0
estimated** — 1.4% a year — because the book pays two more sides every session on a fund whose
shares are cheap relative to the notional, and because a book holding `SPY` only in the session
never receives `SPY`'s dividends. That dividend drag is the single largest term working against the
book and it was named in §4 before the run.

## What this establishes, and what it does not

**Established:** over 2016-2026, the book returned 18.9% a year at a Sharpe ratio of 1.01 against
the index's 15.7% at 0.89. Its advantage over the index is +3.25% a year at half a cent a share and
**is not distinguishable from zero at a cent**, nor over the last two years. The two legs are an
exact decomposition, so nothing is fitted.

**Not established:**

* **that the day leg is worth its two extra fills.** That is what `COST_FRAGILE` says, and it is the
  decision the study was run to inform.
* **that the book beats the index recently.** +0.56% a year over 590 sessions, interval straddling
  zero.
* **what the auctions actually give.** Still the open question, and now it is the decisive one:
  at half a cent the day leg adds 3.2 points a year, at a cent it adds nothing. **The paper week
  `CARD-002` asks for measures precisely this number.**

## What it changes

* **`CARD-002` stays one leg.** The registration said an `ACCEPT` would make it a two-leg card;
  `COST_FRAGILE` does not, and the card is unchanged: small caps overnight, nothing in the session.
* **The fill measurement is now decisive rather than confirmatory.** Before this run it checked a
  cost assumption; now it settles whether a second leg is worth building at all.
* **The honest menu for the owner is three lines**, and each is measured: hold `SPY` (15.7%, 0.89);
  the night alone (13.8%, 1.06, and it is what `CARD-002` specifies); the book (18.9%, 1.01, whose
  margin over the index is fragile).

## What the study cost

No fetch; one run of eight minutes. One trial, 165 to 166.
