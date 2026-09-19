# PREREG: does an entry that joins the opening auction earn what the 15:55 entry earns?

```
id:            PR-025
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19. Asked what to do with CARD-001's
               entry after PR-024, the owner answered "Сначала аукцион" - measure the opening
               auction before deciding. PR-024's report named it as the question left open
status:        registered
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, `EVIDENCE_SUMMARY.md` §25, `DR-040` §10.

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-024` | the same entries bought at the 09:30 continuous open, 11:00 and 15:55, each paying its own quoted half-spread | `ACCEPT` — 15:55 beats the open by **+0.311%** a trade [+0.228, +0.418], all of it the spread: 37.8 bps a side at the open on average, 5.0 at 15:55; gross −0.016% |
| `DR-040` §10 | what `PR-024` adds to the spread record | the open it measured is the continuous book after the cross; the auctions are unmeasured |

**distinct because no study here has priced an auction.** `PR-024`'s open is the print of the
09:30 minute plus the half-spread quoted at 09:30:05 — an order that arrives after the cross. An
order in the opening auction pays the cross's single price and nothing else. Moving an order into
the auction is a routing change (Alpaca's `opg`); moving it to 15:55 needs a pass during the
session that does not exist. This is the owner's question: which of the two the saving is.

**What is known in advance, stated first, and it predicts most of the answer.** The author knows
every number in `PR-024`. And a probe of twelve `PR-024` entries on 2026-09-19 read the SIP trade
tape at each bell (a scratch probe, not committed; the run's `crosses` diagnostic measures the
same on every entry): the stored daily close equalled the listing market's closing cross, to half a
cent, in 12 of 12; the stored daily open equalled the opening cross in 10 of 12; **the 09:30
minute's open — `PR-024`'s price for `O` — equalled it in 9 of 12**, missing by up to 0.31%. So the auction arm is, to a first
approximation, `PR-024`'s open without its spread, and arithmetic on `PR-024` puts `A − C` near
+0.05% to +0.10%. **What the arithmetic cannot say is what this measures**: the cross per entry, and
whether where it differs from the minute's first print it differs against the buyer. No file here
holds any entry's cross price; the probe read twelve and they are not in the sample's scoring.

## 1. Question

For the entries `CARD-001` selected over the last 48 months, does buying in the **opening auction**
of the entry session earn as much per dollar as buying at **15:55** — each net of what it pays to
enter, under the ratified exit?

## 2. Hypothesis

**H1.** The per-entry difference `A − C` in net return per dollar has a 95% interval wholly above
zero: the opening auction beats 15:55.

**H0.** It does not.

**The branch the author expects is `NULL`** — the auction and 15:55 equal within the floor — and
it is the branch that matters most: it would mean the whole of `PR-024`'s saving is available by
routing, without a pass during the session.

**A second arm, counted and never read:** `X`, the closing auction of the entry session, reported as
`X − C`. **And `A − O`**, the auction against `PR-024`'s continuous open — not a new configuration —
says what the routing change alone saves.

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean over entries of [net per dollar (A) - net per dollar (C)], same entry,
                   same ratified exit, month-clustered bootstrap, PR-024's draw and window
predicted:         NULL - a difference of +0.05% to +0.10%, inside the floor. A pays no spread
                   where C pays about 5 bps; the price from the open to 15:55 moved nothing on these
                   names in PR-024 (-0.016% [-0.105, +0.090]); and the cross is the minute's first
                   print on most entries. X - C: near zero, the closing cross five minutes after C
                   with no spread. A - O: about +0.3%, PR-024's saving
if H1 were TRUE:   A's interval wholly above zero - a difference above about +0.10 points
minimum detectable effect:  0.14 points per dollar (0.0014) - the difference the registered sample
                   detects with 80% power at the lowest complete share section 8 admits.
                   From PR-024's REALISED half-width of the same contrast shape - C - O, 0.095
                   points on 8,878 pairs (PR-024.json) - because A walks O's path at a different
                   price: 0.095 / sqrt(0.90) x (1.96 + 0.84) / 1.96. A prior study's interval, which
                   PREREG_TEMPLATE rule 9 allows; widths only
power floor:       0.30 points end to end on the difference (0.0030 per dollar), PR-024's; it gates
                   NULL only
```

## 4. Data

```
sample:        PR-024's committed draw, results/PR-024-sample.jsonl - 982 sessions x 10 names,
               9,820 entries, 2022-09-19 .. 2026-08-18. Not redrawn
bars, minutes, quotes: PR-024's stores at PR-024's instants - bars
               2026-09-16T19:30:10.930516-05:00, minutes and quotes
               2026-09-17T08:16:22.839207+00:00
auctions:      the SIP trade tape at each entry session's open and close, fetched by
               tools/fetch_auction_prints.py into a scratchpad AuctionStore: every print flagged O,
               Q, 6 or M from the bell until the tape runs 60 s past the first cross, at most 5
               minutes. The fetch instant is recorded with the result
the cross:     the largest print flagged O (opening) or 6 (closing), earliest on a tie
               (run_pr025.cross_price)
window:        PR-024's - the last 48 months (AGENTS.md 19's default), so no window rationale is
               owed
country:       USA
survivorship:  present, as in PR-024
costs:         commission 0 (DR-039). A and X: the cross price, nothing added. O and C: as in
               PR-024, the minute's open plus the moment's own half-spread. Exits: PR-024's rule,
               the entry session's half-spread at the exit's moment, the same for every arm
```

## 5. Method

* **The arms.** Signal on session T, entry on T+1. `A` fills at the opening cross and reads its
  entry session from the regular-hours minute holding the cross — so a NYSE opening delayed for news
  starts where it printed. `C` and `O` are `PR-024`'s arms, unchanged. `X` fills at the closing cross
  and sees nothing of its entry session after the fill.
* **The walk** is `run_pr024.walk_entry`, which `PR-024`'s `--parity` proved equals the engine on
  9,820 entries: stop at the fill less 2 × ATR(14) at T, target 1R above, 20 sessions, `DR-042`'s
  minute tie-break.
* **Each reading on its own entries.** A pair enters a reading when both of its arms are priced
  under that reading's costing. `PR-024` dropped an entry from its verdict when an unread arm or a
  perturbation failed; this does not.
* **The statistic.** Per entry, `A`'s net per dollar minus `C`'s; the mean; a 95% moving-block
  bootstrap over entry months, block 3, 10,000 resamples, seed 20260919.

### 5a. The split, and what it buys

```
split:           none
split buys:      nothing is selected - two routings of one decision, fixed here, each read - and
                 the entries were drawn and split-tested before (PR-024, PR-016)
perturbations:   cost_adverse - A and X charged the 15:55 half-spread, as if an auction fill cost
                   what the continuous close costs; C and O at their own; every exit at its own
                   session's opening spread. Section 6 reads it on an ACCEPT
                 exits_at_registry - every exit at DR-005's 25 bps
                 anchored_stop - legs from the signal close, as the live bracket places them
                 instrument_clustered - an iid bootstrap over names
                 date_weighted - each date's mean, then months
```

**Diagnostics, printed and never read by §6:** each arm's exits and what it paid; how often the
cross equals the stored bar's open or close and the 09:30 minute's first print, and by how much it
differs where it does not; how late the opening crosses printed; every exclusion by arm and reason;
and **whether `O` and `C` reproduce `PR-024`'s own QA rows to the digit** (`PR-024-qa-sample.csv`).

## 6. Decision rule

**For `A − C`, by `run_pr024.branch_for`, in `PR-024`'s order:** `REFUSED` under 90% complete, 1,000
pairs or 24 months; `BOTH_NEGATIVE` if wholly above zero and `A`'s own net wholly below;
`COST_FRAGILE` if wholly above and the cost-adverse reading not above zero; `ACCEPT` wholly above;
`REJECT` wholly below; `INCONCLUSIVE` containing zero and wider than 0.30; `NULL` containing zero
inside it. **The study's `verdict:` is `A − C`'s**; `X − C` and `A − O` are reported and never
replace it.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *an order in the opening auction earned more than one at 15:55*: routing, not the
  clock, is the better change.
* `NULL` — *the opening auction earned what 15:55 did, within ±0.15 points*: `PR-024`'s saving is
  available by routing alone.
* `REJECT` — *15:55 earned more than the opening auction*: the clock is worth more than the routing.
* `INCONCLUSIVE` — *not established at this width.*

Changing `CARD-001`'s order is the owner's call whatever the branch.

## 6a. Trials

**Two** — `A` and `X`. `O` and `C` are `PR-024`'s. The tool reads **125** before this registration;
two more take it to **127** and the hurdle from **2.608 to 2.614** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** a limit-on-open at the sizing price (the live order is a limit, `DR-027`
§3.1, and an `opg` limit does not fill above it); a limit-on-close; the auction of the SIGNAL
session's close; any other moment. Each is another configuration.

## 7. Stopping rule

One fetch of the auction prints, repeated only to fill windows that failed. One run at pinned
knowledge instants for all four stores. No arm, costing, cross rule or window tried after the first
result is seen.

## 8. Sample

```
minimum:       1,000 complete A - C pairs across at least 24 entry months, and 90% of the drawn
               entries complete for that pair
power floor:   0.30 points end to end on the difference, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by `REJECT` or `NULL`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* `O` or `C` failing to reproduce any of `PR-024`'s QA rows — they are the same walk on the same
  stores, so a difference is a defect;
* a realised half-width outside half to twice the predicted 0.10 points;
* the closing cross differing from the stored daily close by more than half a cent on more than a
  tenth of entries — the probe found them equal in 12 of 12, so a large miss means the cross rule
  picks the wrong print;
* more than a tenth of drawn entries with no opening cross flagged.

**What would NOT settle anything:** a `NULL` or `ACCEPT` read as *the card makes money*. `PR-024`
found it breaks even at 15:55; this asks only which route gets there.

## 10. Amendments

None.
