# PR-019 RESULT: a 4 ATR stop with no target beats the ratified exit at every hold out of sample, with a thinner tail — and the best of them is still not distinguishable from zero

```
prereg:        PR-019
ran:           2026-09-12
verdict:       INCONCLUSIVE - as §3 predicted before the data, and for the reason it gave.
               §6 selected h60_stop4.0 in sample. Out of sample it beats the ratified exit by
               +0.1888R [+0.0551, +0.3128] with a THINNER tail, but the interval is 0.258 wide
               against the 0.15R floor, and its own mean, +0.0528R [-0.1106, +0.2234], contains
               zero. Predicted half-width 0.137, realised 0.129
status:        PRELIMINARY on DR-042's terms
               AMENDED 2026-09-14: ruled - DR-042 §9. Stop-first with no minutes stored, as
               the ruling prescribes; its 8 ambiguous exits, all resolved to the target, would
               move the ratified arm by at most +0.0013R a trade. No longer PRELIMINARY on
               DR-042's terms
tool:          tools/run_pr019.py, sized by tools/power_pr019.py
evidence:      PR-019.json, PR-019-power.json
trials:        12, declared before the run
```

---

## Read this first

**This is the first verdict in the programme whose shape was written down before the data and came
out that way.** §3 predicted that the in-sample rule would pick a long hold with a stop — 40 or 60
sessions, 4 ATR likelier than 2 — that no no-stop cell would be eligible, and that the selected
cell's out-of-sample interval would be too wide to read. All three held. The power estimate
predicted a half-width of **0.137** for the selected contrast; the study realised **0.129**.

**And the verdict is not the finding.** Across the grid, a 4 ATR stop with no target beats the
ratified exit out of sample at **every** hold, with a thinner tail at every hold. §6 reads one cell,
so that is an observation on registered diagnostics and not a validation — but it is four intervals
out of four, and it is the most consistent thing this project has measured about an exit.

**What it does not show is money.** The selected cell's own interval contains zero, its median trade
loses 0.37R, and without the screen the same exit still reads **+0.0202R** out of sample — so most
of what moved is the EXIT, not the selection, and on a long-only book held sixty sessions through
2022–2026 part of it may be the market's drift. **This study has no market null.** §"What this does
NOT establish" is not boilerplate here.

Derive every figure with `python tools/run_pr019.py --report`, never from these lines.

## §9's reproductions, which had to pass before anything else could be read

| free-entry arm | window | this run | committed |
|---|---|---|---|
| `free_ratified` = `PR-016`'s `ranked` | in-sample | 11,019 trades, −0.0797R | **11,019, −0.0797R** |
| | out-of-sample | 16,320, −0.1144R | **16,320, −0.1144R** |
| `free_h20_stop2.0` = `PR-018`'s `ratified_no_target` | in-sample | −0.0261R | **−0.0261R** |
| | out-of-sample | −0.0650R | **−0.0650R** |

**Identical to every digit**, and one more that §9 did not ask for: `free_h20_stopnone` is `PR-018`'s
`hold_only` and reproduces it exactly — 7,305 at +0.0645R and 10,774 at +0.0404R.

**The entry sets.** 29,031 selected signals, 12,189 entries after spacing at 60 sessions, and after
the intersection **4,935 in sample and 7,236 out in every cell**. The engine refused 13 entries in
every cell for buying zero shares at $1,000 of risk, and the 4 ATR cells refused 5 more — 4 whose
stop was not a positive price and one more zero-share. Those 5 were removed from every cell, as §5
registered.

## The selection, in sample

Eligible: a cell meeting the sample rule whose share of trades below −2R does not exceed the ratified
exit's **1.76%**.

| eligible | in-sample mean net R | below −2R |
|---|---|---|
| `h10_stop2.0` | −0.0912 | 1.66% |
| `h10_stop4.0` | −0.0368 | 0.32% |
| `h20_stop4.0` | −0.0066 | 0.45% |
| `h40_stop4.0` | +0.0504 | 0.67% |
| **`h60_stop4.0`** | **+0.1080** | 0.91% |

**Every no-stop cell failed**, at 11.6% to 45.1% below −2R. **So did every 2 ATR cell held longer than
ten sessions** — 2.35% at 20, 3.53% at 40, 3.93% at 60 — which is a finding of its own, below.

## The verdict cell, out of sample

| | `h60_stop4.0` | `ratified` |
|---|---|---|
| trades / months | 7,236 / 54 | 7,236 / 54 |
| mean net R | **+0.0528** [−0.1106, +0.2234] | −0.1360 [−0.2368, −0.0170] |
| difference | **+0.1888** [+0.0551, +0.3128] — width 0.258, floor 0.15 | — |
| win rate / median | 42.87% / **−0.3704R** | 47.29% / −0.4063R |
| p95 | **+2.658R** | +0.970R |
| below −2R / −3R | **0.81% / 0.10%** | 2.56% / 0.44% |
| worst MAE | **−4.67R** | −7.25R |
| median hold | 85 calendar days | 8 |
| exits | time 3,632 · stop 2,630 · gap 581 · end of data 393 | target 3,146 · stop 2,812 · gap 654 · time 573 |

**Read the mean and the tail together, as §6 requires.** The selected cell earns more than the
incumbent and loses less at the bottom, both at once — the first cell here that does not trade one
for the other. **Its shape is the opposite of the incumbent's:** the ratified exit caps every winner
at 1R and so its p95 is the target minus costs; this one loses a little most of the time and is paid
by a right tail that reaches +2.66R at p95.

## The curve, out of sample

| cell | mean net R | difference vs `ratified` | below −2R | worst |
|---|---|---|---|---|
| `h10_stop2.0` | −0.0997 | +0.0363 [−0.0141, +0.0824] | 2.40% | −8.92 |
| `h10_stop4.0` | −0.0235 | **+0.1125 [+0.0405, +0.1655]** | 0.39% | −4.46 |
| `h10_stopnone` | −0.0303 | +0.1057 [+0.0113, +0.1843] | 11.90% | −10.52 |
| `h20_stop2.0` | −0.1050 | +0.0310 [−0.0413, +0.1050] | 3.47% | −8.92 |
| `h20_stop4.0` | −0.0250 | **+0.1110 [+0.0321, +0.1745]** | 0.48% | −4.46 |
| `h20_stopnone` | +0.0075 | +0.1435 [−0.0189, +0.2724] | 22.17% | −14.19 |
| `h40_stop2.0` | −0.1010 | +0.0350 [−0.0856, +0.1503] | 4.20% | −8.92 |
| `h40_stop4.0` | +0.0151 | **+0.1511 [+0.0368, +0.2443]** | 0.73% | −4.67 |
| `h40_stopnone` | +0.1619 | +0.2979 [+0.0127, +0.5455] | 36.66% | −14.19 |
| `h60_stop2.0` | −0.0865 | +0.0495 [−0.0992, +0.2088] | 4.69% | −8.92 |
| **`h60_stop4.0`** | **+0.0528** | **+0.1888 [+0.0551, +0.3128]** | **0.81%** | **−4.67** |
| `h60_stopnone` | +0.3994 | +0.5354 [+0.1837, +0.8946] | 44.38% | −15.50 |
| `ratified` | −0.1360 | — | 2.56% | −7.25 |

**Three readings, none of which §6 makes, all of which a strategy has to live with.**

1. **The 4 ATR stop beats the ratified exit at every hold**, the four intervals all excluding zero,
   and its tail is the thinnest in the grid at every hold. `h10_stop4.0` is even readable at the
   floor — width 0.125 — and it LOSES money in level, −0.0235R. **Beating the incumbent is not
   earning.**
2. **A 2 ATR stop held longer fattens the tail**: 3.47% to 4.69% below −2R against the incumbent's
   2.56%, and the worst trade at −8.92R in every one of them. The ratified target takes the winner
   off early and with it the days a gap can go through the stop; take the target away and hold
   longer, and the tight stop is gapped more. **The hold and the stop width are one decision**,
   which is `STRATEGY_CONTRACT` C-7's argument measured rather than asserted.
3. **Level rises with the hold under a 4 ATR stop**: −0.0235, −0.0250, +0.0151, +0.0528R. Monotone,
   and the precision falls in exactly that direction, which is why §3 said the long end could not
   be confirmed.

**Holding with no stop earns the most and is not a strategy.** `h60_stopnone` reads +0.3994R with
**44% of trades below −2R and a quarter below −3R**. That is the market's drift bought with an
unbounded left tail, and no reading of this study licenses it.

## The perturbations

**Triple costs.** `h60_stop4.0` −0.0042R and −0.0826R [−0.2462, +0.0834]; `ratified` −0.3203R and
−0.3906R. **The advantage GROWS under costs** — +0.3161R and +0.3080R [+0.1694, +0.4387] — because the
4 ATR cell trades half the shares at the same risk and pays the round trip on half the notional,
while its LEVEL turns negative. Cost-robust in relative terms, cost-fragile in absolute ones.

**Cheap execution** at 5.75 bps a side, a re-pricing of an entry struck at the open and not a claim
it can be executed later: `h60_stop4.0` +0.1534R and **+0.1005R**, `ratified` −0.0049R and −0.0440R.

**The no-selection null** (`STRATEGY_CONTRACT` C-3), every admitted name spaced at 60 sessions:

| | in-sample | out-of-sample |
|---|---|---|
| `h60_stop4.0`, selected | +0.1080R | **+0.0528R** |
| `h60_stop4.0`, every admitted name | +0.1020R | **+0.0202R** |
| `ratified`, every admitted name | −0.0749R | −0.1952R |

**Under this exit the screen is worth +0.006R in sample and +0.033R out** — small, where under
holding to the clock `PR-018` measured it at +0.158R. **Almost all of the improvement over the
incumbent is the exit**, and it survives on names nobody selected.

## Per trade, and what it costs per year

Spacing fixes one schedule for every cell, so the table above ranks cells per TRADE. The free-entry
diagnostic lets each cell take its own trades, out of sample:

| | trades | mean net R |
|---|---|---|
| `free_h60_stop4.0` | 8,438 | +0.0441 |
| `free_ratified` | 16,320 | −0.1144 |

Half the trades, each earning a little instead of losing a tenth of an R. **No book is modelled** —
concurrency, caps and capital are not in this study — so this is a direction, not a return.

## What this does NOT establish

* **A verdict.** Both intervals §6 reads are wider than it will accept, and the cell's own level
  contains zero. Nothing is validated and no parameter moves.
* **An edge over the market.** Every arm is long-only; the selected one holds a median 85 days
  through 2022–2026. **This study never compares a trade to the index over the same days**, and the
  no-selection null earning +0.0202R out of sample is exactly what a market drift would look like.
  `PR-014` and `PR-015` measured against `SPY`; this one did not. That is the next question, and it
  has to be registered before anyone reads this table as a strategy.
* **Anything about a book.** One trade at a time; no concurrency, no caps, no capacity.
* **A clean end.** 393 of the selected cell's 7,236 out-of-sample trades — 5.4% — were closed at the
  last stored close because the data ended, which a 60-session hold makes more likely than a
  20-session one. Counted, never dropped (`engine.py`'s `END_OF_DATA` branch).
* **Ten years**, or survivorship. 8.91 years of entries, and 2,598 of 2,598 decade-long instruments
  still trade.
* **Anything free of `DR-042`.** Its tie-break bit on 8 of the ratified arm's exits and on no 4 ATR
  or no-stop cell.

## What it means for the strategy

`STRATEGY_CONTRACT` C-7 asked for the hold to be the combination's own and researched. **It now has
evidence, and the evidence says the hold cannot be chosen alone:** at a 2 ATR stop a longer hold
fattens the tail, at a 4 ATR stop it raises the level. The combination the data points at is

```
selection:   the ratified decile (worth little under this exit - measured, not assumed)
stop:        4 x ATR(14), no target
hold:        40 to 60 sessions
net R:       +0.015R to +0.053R a trade out of sample, neither distinguishable from zero
tail:        0.7% to 0.8% of trades below -2R, worst -4.7R - better than the ratified exit
validation:  Untested. INCONCLUSIVE here, and no market null exists yet
```

**It is a candidate, not a strategy.** Contract C-4 requires a net number with an interval that
excludes zero, and C-3 a null it must beat; this has neither yet.

## What it costs the programme

**12 trials**, declared before the run. The cumulative count and the hurdle are the tool's:

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

## Reproducing

```bash
PYTHONPATH=$PWD/src python tools/run_pr019.py --data data --as-of 2026-09-06T22:36:49.635786-05:00
```

```bash
PYTHONPATH=$PWD/src python tools/run_pr019.py --report
```
