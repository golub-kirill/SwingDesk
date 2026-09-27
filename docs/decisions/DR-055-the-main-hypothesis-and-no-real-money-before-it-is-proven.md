# DR-055: the project's main hypothesis is `PR-035`'s book against `SPY` after real costs — and no real money moves before it is proven

```
date:            2026-09-27
status:          accepted — ruled by the owner 2026-09-27: "da, delay etu svyazku osnovnoy
                 gipotezoy, no nikakih realnih deneg do dokazatelstva", then, asked, what counts
                 as proof, which third leg to try first, and whether SPY may be held through a
                 paper session without a stop
parameters:      none
components:      none new
implementation: none
binds:           the research order (TODO), CARD-002 section 7, runbook section 11, and the
                 exception in section 4, which the paper day leg's own record will implement
```

## 1. What was ruled

1. **The main hypothesis.** `PR-035`'s book — `IJR` and `VB` from each close to the next open,
   `SPY` from that open to that close, the same dollar twice — beats holding `SPY` after the costs
   it would really pay. Research serves this question first.
2. **No real money before it is proven.** The twenty real sessions at one share a fund, resumed
   on 2026-09-26 (`CARD-002` §7.5), are **cancelled before the first one**. Paper continues.
3. **What "proven" means — both, and neither alone:**
   1. a registered study prices the book at the listing markets' **official auction prices** and
      the venue's regulatory fees, and the book's geometric excess over `SPY` held has a 95%
      interval wholly above zero over `PR-035`'s window, **and** a positive excess over the last
      48 months;
   2. **60 paper sessions of the full book with no machinery defect** — `CARD-002` §5's list: a
      position held with no exit order, a position still open after the auction meant to close
      it, or a rejected or unfilled order the passes did not handle.

   Meeting both moves no money by itself. It puts the question of real money back to the owner,
   which is `CHARTER` A-001.
4. **The third leg, next.** Foreign equity funds held through the US session, when their home
   markets are closed — the same mechanism as the night, seen from the other side of the world.
5. **`SPY` may be held through a PAPER session without a stop**, narrowly (§4).

## 2. Why, and the number that made the question sharp

The owner asked whether any of this beats simply holding `SPY`. `PR-035` had already measured it
over 2016-2026: the book returned 18.9% a year at a Sharpe ratio of 1.01 against the index's 15.7%
at 0.89. **Its excess is +3.25% a year at half a cent a share a side, and +0.35% at a whole cent.
Gross, the margin is 6.1% a year: the edge and four fills a day are the same size**
(`EVIDENCE_SUMMARY` §33). An exploratory three-year reading shown in conversation the same day
said the same thing more starkly and is not relied on here.

**So the decisive unknown is the price the fills pay, and it does not need real money.** Every
backtest here priced an auction fill as a bar's open or close plus a modelled half cent. An order
that joins an auction is filled at the auction's single price. `tools/fetch_auction_prints.py`
reads that price from the SIP tape, where the listing market's cross carries condition `O` or `6`,
GET only. Comparing it with the bar price the backtests used, plus the fee schedule
(`docs/decisions/measurements/venue-fees-2026-09-05.json`), measures the cost directly.

**The residual assumption, stated rather than hidden:** that the broker routes a `cls` or `opg`
order into the listing market's auction. That is the broker's documented behaviour and has never
been observed here, because the paper venue's fills are simulated. Proof (1) removes the modelled
cost; it cannot remove this.

## 3. What this changes

* **`CARD-002` §7.5**: the real sessions are cancelled; runbook §11's owner steps are not to be run.
* **`CARD-002` becomes the night leg of the book.** Its paper passes keep running (`DR-054`).
* **Three build items, in this order** (`TODO.md`): the auction-priced study of the book; the paper
  day leg that makes the paper account carry the whole book, under §4; and the third leg's
  registration on funds nothing here has read.

## 4. The narrow exception to `DR-027` §3.2

`DR-027` §3.2 requires a stop at the venue whenever the market is open, and `DR-048` §5 excepted
only a position held while the exchange is shut. **The book's day leg is held while it is open.**
The owner ruled on 2026-09-27 that on the PAPER account it may be, on these terms and no others:

* the symbol is `SPY`;
* it is bought in the opening auction and sold in the closing auction of the same session;
* a market-on-close sell for the whole position is lodged as soon as the buy has filled, so the
  exit rests at the venue for the whole holding period.

Any other symbol, any longer hold, and any account that can move the owner's money keeps the stop.
This record carries no code; the paper day leg's own record implements the exception and cites
this section.
