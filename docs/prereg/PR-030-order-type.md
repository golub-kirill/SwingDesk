# PREREG: which order should carry CARD-001's entries - today's day limit, or a limit-on-open?

```
id:            PR-030
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19. Asked whether to change CARD-001's
               entry after PR-025, the owner answered "Сначала измерить" - measure the order
               types on the card's own entries before deciding
status:        reported   (2026-09-19 - results/PR-030-report.md)
verdict:       INCONCLUSIVE - G - D +0.123% per drawn entry [-0.075, +0.305], 0.38 wide. J - D,
               counted and never read, +0.145% [+0.119, +0.174]. §9's split check FAILED as
               registered; amendment A-1 shows why
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, `EVIDENCE_SUMMARY.md` §25 and §27, `DR-040`
§4, §10 and §11, `DR-027` §3.

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-024` | the same entries bought at the 09:30 continuous open, 11:00 and 15:55, each paying its own quoted half-spread | `ACCEPT` — 15:55 beats the open by **+0.311%** a trade [+0.228, +0.418], all of it the spread |
| `PR-025` | the same entries bought at the opening cross, no spread | EXPLORATORY after amendment A-1 — the auction less 15:55 **+0.007%** [−0.089, +0.084]; less the continuous open **+0.375%** [+0.316, +0.435] |
| `DR-040` §4 | how the live limit at the prior close fills, on daily bars over the admitted universe | 147,712 entries: **50.6% marketable at the open, 32.8% passive at the limit, 16.6% never filled** |
| `DR-027` §3.1 | the live entry order | a DAY LIMIT at the sizing price, the signal session's close, bracketed (§3.2) |

**distinct because every priced arm so far fills every entry.** `PR-024`'s and `PR-025`'s arms are
market orders at a moment; the live order is a limit. A limit marketable at the open pays the
spread, one that is not RESTS and fills at the limit if the price comes back and not at all if it
does not — and `DR-040` §4 counted that split on the whole universe, never priced it. A
limit-on-open (Alpaca's `opg`) takes the cross or nothing. So the switch `PR-025` points at wins the
spread on the marketable entries and gives up the resting ones. **Nothing here has measured the
net of the two on the card's own entries**, and that is the owner's question.

**What is known in advance, and stated first.** The author knows every number above. On `PR-024`'s
arithmetic the spread saved on the marketable half is about 0.19 points a drawn entry
(0.378 × ~0.5). What the resting entries are worth is not known: bought below the open, after a
decline, with no entry spread, but with the exit's spread still paid on a card that breaks even.

## 1. Question

For the entries `CARD-001` selected over the last 48 months, does a **limit-on-open at the signal
close** earn more per drawn entry than **today's day limit at the signal close** — each net of
what it pays, under the ratified exit, an order that never fills earning nothing?

## 2. Hypothesis

**H1.** The per-entry difference `G − D`, in net return per dollar, a missed order counting as 0,
has a 95% interval wholly above zero: the limit-on-open earns more.

**H0.** It does not.

**Two more orders, counted and never read:** `M`, a market-on-open (`PR-025`'s auction arm, which
takes the cross always), read as `M − D`; and `J`, a day limit that JOINS the opening cross when
marketable there and rests at the limit from the cross's minute otherwise, read as `J − D`. How
Alpaca routes a queued `day` order at the open is not documented; `D` and `J` bound it from the two
sides.

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean over DRAWN entries of [net per dollar (G) - net per dollar (D)], a missed
                   order 0, same entry, same ratified exit, month-clustered bootstrap, PR-024's draw
predicted:         G - D about +0.20 points per drawn entry, between +0.10 and +0.30. The spread
                   saved where D is marketable - about 0.378 on about half the entries - is +0.19;
                   where D rests and G misses, D holds a trade on a card that breaks even, bought
                   without an entry spread and still paying its exit's, so abstaining costs little.
                   The predicted width is 0.37 (results/PR-030-power.json), wider than the floor:
                   NULL is out of reach, and between ACCEPT and INCONCLUSIVE this is close to a coin
                   flip - about 55% power at +0.20. Registered as it is rather than enlarged: a
                   larger draw needs new quotes and prints for every added entry.
                   M - D: near zero - the spread won on the marketable half, the resting third
                   bought higher at the cross, the missed sixth traded. J - D: about +0.19 and
                   narrow (0.05 wide) - J is G where the cross is under the limit and D where not
if H1 were TRUE:   G's advantage wholly above zero
minimum detectable effect:  0.26 points per dollar (0.0026) - the difference the registered sample
                   detects with 80% power: the predicted half-width, 0.185, x (1.96 + 0.84) / 1.96.
                   From `run_pr030.py --power` - the verdict estimator's own interval on the
                   registered sample and stores, widths only under
                   `power_pr019.assert_no_effect_leaked` (PR-021..PR-023's precedent)
power floor:       0.30 points end to end on the difference (0.0030 per dollar), PR-024's; it gates
                   NULL only
```

## 4. Data

```
sample:        PR-024's committed draw, results/PR-024-sample.jsonl - 982 sessions x 10 names,
               9,820 entries, 2022-09-19 .. 2026-08-18. Not redrawn
stores:        PR-025's, at PR-025's instants - bars 2026-09-16T19:30:10.930516-05:00, minutes
               2026-09-19T18:13:43.335554+00:00, quotes 2026-09-17T08:16:22.839207+00:00,
               auctions 2026-09-19T18:13:43.335554+00:00. Nothing is fetched
the limit L:   the signal session's close in the stored bars - the sizing price, DR-027 §3.1
the cross:     run_pr025.cross_price, brought onto the bars' basis by run_pr025.adjustment_factor
               (PR-025 amendment A-1)
window:        PR-024's - the last 48 months (AGENTS.md 19's default), so no window rationale is
               owed
country:       USA
survivorship:  present, as in PR-024
costs:         commission 0 (DR-039). D marketable: the 09:30 minute's open plus the quoted
               half-spread at 09:30 (PR-024's O). A resting fill and a crossed fill: the price,
               nothing added. Exits: PR-024's rule, the entry session's half-spread at the exit's
               moment, the same for every order
```

## 5. Method

* **The orders**, signal on session T, entry on T+1, limit `L` the close of T:
  * `D` — today's order. Marketable when the 09:30 minute's open plus the half-spread quoted at
    09:30 is at or under `L`: it fills there. Otherwise it rests at `L` and fills AT `L` in the
    first regular-hours minute whose low reaches `L`, paying no spread. Otherwise missed.
  * `G` — a limit-on-open: the adjusted opening cross if at or under `L`, else missed.
  * `M` — a market-on-open: the adjusted opening cross, always. `PR-025`'s `A`.
  * `J` — `G` when the cross is at or under `L`; otherwise it rests at `L` from the cross's minute,
    as `D` rests.
* **A missed order is a result, not an exclusion.** It earns 0 — cash — under every costing and is
  in the mean. The unit is the drawn entry, so an order that fills less is charged for it.
* **The walk** is `run_pr024.walk_entry` from each order's own fill, as in `PR-024` and `PR-025`:
  stop at the fill less 2 × ATR(14) at T, target 1R above, 20 sessions, `DR-042`'s tie-break.
* **Each reading on its own entries.** A pair enters a reading when both orders are priced or
  missed under that costing; an entry with no opening cross flagged, or no fresh quote at 09:30,
  is out of the readings that need it and counted by arm and reason.
* **The statistic.** Per drawn entry, `G`'s net per dollar minus `D`'s; the mean; a 95%
  moving-block bootstrap over entry months, block 3, 10,000 resamples, seed 20260920.

**A known lean, stated before the run: the resting fill favours `D`.** A minute whose low merely
TOUCHES `L` fills the resting order here; at the venue a touch fills only the orders ahead in the
queue. So `D` is credited with some fills it would not get, and those fills are the ones this study
turns on. An `ACCEPT` is the more conservative for it; a `REJECT` would be overstated by it, and
the report says so.

### 5a. The split, and what it buys

```
split:           none
split buys:      nothing is selected - four orders for one decision, fixed here, each read - and
                 the entries were drawn and split-tested before (PR-024, PR-016)
perturbations:   cost_adverse - a crossed fill charged the 15:55 half-spread, as if an auction fill
                   cost what the continuous close costs; every exit at its session's opening spread.
                   Section 6 reads it on an ACCEPT
                 gross - no spread anywhere; reported
```

**Diagnostics, printed and never read by §6:** how each order fared (marketable, crossed, rested,
missed), beside `DR-040` §4's 50.6 / 32.8 / 16.6; `G − D` taken apart by how `D` fared — each
group's entries, its mean difference and its share of the reading — so the spread saved on the
marketable entries and what abstaining gained or lost on the others are reported apart; every
exclusion by arm and reason; and **whether `M` reproduces `PR-025`'s `A` and a marketable `D`
reproduces `PR-024`'s `O` on their QA rows, to the digit** (`run_pr030.repeats_prior_studies`).

## 6. Decision rule

**For `G − D`, by `run_pr024.branch_for`, in `PR-024`'s order:** `REFUSED` under 90% complete,
1,000 pairs or 24 months; `BOTH_NEGATIVE` if wholly above zero and `G`'s own net wholly below;
`COST_FRAGILE` if wholly above and the cost-adverse reading not above zero; `ACCEPT` wholly above;
`REJECT` wholly below; `INCONCLUSIVE` containing zero and wider than 0.30; `NULL` containing zero
inside it. **The study's `verdict:` is `G − D`'s**; `M − D` and `J − D` are reported and never
replace it.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *a limit-on-open at the signal close earned more per signal than today's day limit*.
* `NULL` — *the two orders earned the same per signal, within ±0.15 points*: the route is not
  worth a change to the order.
* `REJECT` — *today's day limit earned more*: the resting fills are worth more than the spread.
* `INCONCLUSIVE` — *not established at this width.*
* `BOTH_NEGATIVE` — *the limit-on-open lost less, and lost*.

**Changing the card's order is the owner's call whatever the branch**, and it is not only a number:
Alpaca accepts a bracket only as `day` or `gtc`, so an `opg` entry cannot carry its stop and target
the way `DR-027` §3.2 requires, and a limit-on-open is rejected when sent between 09:28 and 19:00
ET. The report states what a switch would change in `DR-027`, and does not decide it.

## 6a. Trials

**Three** — `D`, `G` and `J`. `D` is the card's live order, never priced before: `PR-016` priced
the open with no limit. `M` is `PR-025`'s `A`. The tool reads **140** before this registration;
three more take it to **143** and the hurdle from **2.647 to 2.654** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** any other limit — the prior close plus or minus any amount, the sizing
price with an ATR allowance; a limit-on-close; a resting order that expires before the close; any
fill model other than touch.

## 7. Stopping rule

One run at the pinned instants of all four stores. No order, limit, fill rule or costing tried after
the first result is seen.

## 8. Sample

```
minimum:       1,000 complete G - D pairs across at least 24 entry months, and 90% of the drawn
               entries complete for that pair
power floor:   0.30 points end to end on the difference, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by `REJECT`, `NULL` or `INCONCLUSIVE`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* `M` failing to reproduce any of `PR-025`'s `A` QA rows, or a marketable `D` any of `PR-024`'s
  `O` rows — the same fill on the same stores, so a difference is a defect;
* a realised half-width outside half to twice 0.185 points, §3's;
* `D`'s split more than 15 points off `DR-040` §4's on any of its three parts — a different
  population and a different test (the ask, not the print), so near but not equal; far off means
  the order is simulated wrong;
* more than a tenth of drawn entries with no opening cross flagged.

**What would NOT settle anything:** an `ACCEPT` read as *the card makes money*. `PR-024` and
`PR-025` found it breaks even; this asks only which order loses less of it.

## 10. Amendments

### A-1 — 2026-09-19, AFTER the run: one §9 check that checked nothing, and why another failed

**What happened.** The run returned `INCONCLUSIVE`. Two of §9's checks did not do what they
were registered to do:

* **`M` against `PR-025`'s QA rows checked no row.** `run_pr030.REPRODUCES` asked `M` for the fill
  `"M"`, which is its arm's name. Its fills are `crossed`, so every one of the 400 rows fell under
  `other_fill`. The test covered only `D`. **Corrected:** the tuple now names `CROSSED`, with a
  test that fails if either order's fill is misnamed. Result: 400 of 400 rows checked, none differ.
* **`D`'s split against `DR-040` §4 failed**, at 31.0 / 50.5 / 18.5 against 50.6 / 32.8 / 16.6.
  §5 defines marketable as the ASK at or under the limit, while `DR-040` counted the first PRINT;
  the registered tolerance of 15 points did not allow for that difference. **Added, as a
  diagnostic:** each entry classed by `DR-040`'s own test (`Ordered.by_print`). Result: 47.2 /
  34.3 / 18.4, within 3.4 points on every part.

**What it costs the study.** Nothing in the verdict. Neither change touches a price, a fill, a
walk or a reading. The second run, with both corrections, reproduced the first run's cells,
fills, exclusions, branch and QA file to the digit. The split check stays reported as FAILED;
what explains it was found after the data was seen, and it is marked that way.
