# PR-025 RESULT: an order in the opening auction earns what the 15:55 order earns — PR-024's saving is a routing change, not a clock one (EXPLORATORY after amendment A-1)

```
prereg:        PR-025
ran:           2026-09-19
verdict:       INCONCLUSIVE, and EXPLORATORY. The registered run's REJECT is withdrawn: the SIP
               tape's cross prices were never on the bars' split- and spin-off-adjusted basis
               (amendment A-1, made after the data). Corrected, the opening auction less 15:55 is
               +0.007% per dollar a trade [-0.089, +0.084], 0.17 wide - the NULL branch section 3
               predicted. The auction against PR-024's continuous open: +0.375% [+0.316, +0.435]
status:        final, exploratory - PREREG_TEMPLATE rule 3; O and C reproduced PR-024's QA rows to
               the digit
tool:          tools/run_pr025.py (amended), prints by tools/fetch_auction_prints.py
evidence:      PR-025.json, PR-025-qa-sample.csv, PR-025-ambiguous-bars.jsonl; PR-024's sample
trials:        2, declared before the run (A and X)
```

---

## Read this first

**Buying in the opening auction is as good as buying at 15:55.** On `PR-024`'s 9,820 entries, an
order filled at the listing market's opening cross — no spread paid — earned **+0.007%** a trade
against the 15:55 order, an interval from −0.09% to +0.08%. And against the continuous open the card
buys at today, it earned **+0.375%** [+0.316, +0.435]: the whole of `PR-024`'s saving.

**What that means for the card.** `PR-024`'s saving is available by ROUTING — Alpaca's `opg`
time-in-force, sent in the evening pass the card already has — and needs no order placed during the
session. The card itself stays where `PR-024` left it: **+0.007% a trade** against nothing, break-even.

**This is exploratory, and the reason is written first.** The registered run returned `REJECT` —
the auctions 3.9 points a trade worse — because the tape prints what traded while the bars carry
every later split and spin-off (§A-1 below). The fix was made after that result was seen, so the
corrected reading cannot carry a confirmatory verdict, whatever it says.

## §A-1 — the unit error, and how it was found

The registered run's own diagnostics gave it away: the opening cross stood **27%** off the stored open
on average while the median gap was **zero**. On **620** sessions the crosses stood off their bars by
one factor — **2 (161), 4 (86), 10 (70), 5 (59), 3 (48), 6 (30), 1.5 (30)**, reverse splits at 0.1
and 0.05, spin-offs at 1.385 and 2.63 — so an auction entry on a name that later split 2-for-1 was
priced at twice its bar and fell through its stop. §9's check — the closing cross against the bar,
"on more than a tenth of entries" — saw 6.8% and passed: it counted misses and never read their
size. `run_pr025.adjustment_factor` now brings both crosses onto the bar's basis when they stand off
it by one factor beyond half a percent, agreeing to half a percent (`PR-025` §10).

## §9, as registered

| check | registered | realised |
|---|---|---|
| `O` and `C` against `PR-024`'s QA rows | no row may differ | **0 of 800** |
| realised half-width against the predicted 0.10 | half to twice | **0.087**, 0.87× |
| closing cross off the stored close by more than half a cent | under a tenth | 651 of 9,531, 6.8% — **by count; by size it was the defect** |
| entries with no opening cross flagged | under a tenth | **200 of 9,820**, 2.0% |
| `A − C` complete | 90% | **96.0%**, 9,429 pairs, 48 months |

## The readings — corrected, exploratory

| per dollar a trade | estimate | 95% interval |
|---|---|---|
| **opening auction − 15:55 (net)** | **+0.007%** | **[−0.089, +0.084]** |
| gross part | −0.046% | [−0.138, +0.032] |
| cost-adverse (the auction charged 15:55's spread) | −0.039% | [−0.135, +0.039] |
| legs from the signal close | +0.052% | [−0.006, +0.112] |
| date-weighted | +0.010% | [−0.085, +0.086] |
| the auction arm's own net | +0.007% | [−0.404, +0.420] |
| **closing auction − 15:55** (counted, never read) | +0.019% | [−0.031, +0.065] |
| **opening auction − continuous open** | **+0.375%** | **[+0.316, +0.435]** |

`A − C` contains zero inside the 0.30 floor: the `NULL` branch §3 predicted, and a clean one — 0.17
wide. Before costs the auction is 0.05% behind 15:55; the 15:55 order's own spread closes the gap.
**The closing auction** reads the same as 15:55 within ±0.05; its cost-adverse reading, charging it
15:55's own spread, is just below zero — it is 15:55 five minutes later, with the spread removed and
the drift of those minutes added.

## What this establishes, and what it does not

**Established, exploratory:** for the names `CARD-001` picks, over 2022-09..2026-08, an order filled
at the opening cross earned what an order at 15:55 earned, and 0.375% a trade more than one meeting
the continuous book after the open.

**Not established:**

* **that the card's live order gets the cross.** The live order is a day LIMIT at the sizing price
  (`DR-027` §3.1). As an `opg` limit-on-open it fills only if the cross is at or under that price;
  the entries it would miss are in every arm here. Which way that cuts is unmeasured.
* **that the card's `day` orders do not already join the auction.** Alpaca's documentation says only
  that `opg` orders do; a queued `day` order's routing at the open is not documented, and the paper
  account's fills are simulated.
* **that the card makes money.** It breaks even at either moment.

## What it changes

* **`PR-024`'s saving is a routing choice.** Sending entries as `opg` in the existing evening pass
  is the cheaper of the two ways to take it; a pass at 15:55 buys nothing more. **Changing the
  order's time-in-force is the owner's call** and a change to `DR-027` §3.3.
* **A price from the tape and a price from a bar are different units.** Recorded where the next
  study will read it: the auction store's own documentation, and `PR-025` §10.

## What the study cost

21,618 requests to the vendor over three hours for the prints; three runs of eight minutes. Two
trials.
