# PR-017 RESULT: a POWERED null — selling half at 1R is indistinguishable from closing it all, and at triple costs it is worse

```
prereg:        PR-017
ran:           2026-09-08
verdict:       INCONCLUSIVE by §6's rule — and that word understates it. Both windows CLEAR
               the power floor and both contain zero: +0.0015 [-0.0286, +0.0378] in sample,
               +0.0247 [-0.0162, +0.0780] out. This is not "the instrument could not tell".
               It is "the instrument could have seen 0.05R and there is no 0.05R"
status:        PRELIMINARY on `DR-042`'s terms, exactly as PR-016 is
tool:          tools/run_pr017.py
evidence:      PR-017.json
trials:        2, declared before the run
```

---

## Read this first

**§6 has no branch for a powered null, and this is one.** The registered rule returns
`INCONCLUSIVE` for anything that is not two intervals on the same side of zero, so it cannot
distinguish *we could not see* from *we looked properly and there is nothing*. §3 registered the
difference in advance — a floor of 0.15R and a minimum detectable effect of 0.05R — and the
realised half-widths are **0.033R and 0.047R**, comfortably inside both.

So the honest sentence is: **selling half the position at 1R earns the same as closing all of it
there, to within a third of the effect this design was built to detect.**

**And the course's objection turns out to be right for a reason it does not give.** `M54-T0830`
asserts `Математические недостатки`, and the classical argument is about cutting a winner that
would have run. That is not what bites here. **At triple costs the partial is measurably worse** —
−0.0356R [−0.0627, −0.0043], excluding zero — because a partial is a **third fill** and pays
slippage for it. The disadvantage is a transaction cost, not a forgone tail.

Derive every figure with `python tools/run_pr017.py --report`, never from these lines.

## What ran

| | |
|---|---|
| store | `bars.duckdb` at `as_of 2026-09-06T22:36:49.635786-05:00` |
| instruments | 10,330 |
| formation dates | 125, every 20th session |
| **measured span** | **2017-03-17 … 2026-08-07 — 9.39 years**, short of the ten instructed |
| entries | unselected, identical across every arm |
| exit, shared | stop `2.0 × ATR(14)`, time exit at session 20 |
| costs | 25 bps a side, $0.005 a share, on **every** fill — a partial pays for its own |

## §9's reproduction check, which had to pass before anything else could be read

§9 registered that `all_out_1r` must reproduce `PR-016`'s `unselected` arm and `no_target` its
`unselected_two_slot` diagnostic — same construction, same entries, two studies.

| | PR-017 | PR-016 |
|---|---|---|
| `all_out_1r` out of sample | 154,846 trades, −0.2028R, 46.21% | **154,846, −0.2028R, 46.21%** |
| `no_target` out of sample | 115,918 trades, −0.1512R, 37.58% | **115,918, −0.1512R, 37.58%** |
| `all_out_1r` in sample | 104,108 trades, −0.1759R | 103,911, −0.1756R |

**Out of sample, identical to every digit.** In sample it differs by 197 trades — 0.19% — and the
reason is known rather than waved at: `PR-016` skips formation dates whose cross-section is too
thin to decile, and this study builds no decile, so it keeps those six dates. They are all early,
which is why only the in-sample window moves.

## The numbers

```
arm                          window           win%    be%    meanR    skew  payoff     p95
all_out_1r                   in_sample       48.64  57.39  -0.1759   -3.34   0.743  +0.970
all_out_1r                   out_of_sample   46.21  56.31  -0.2028   -1.64   0.776  +0.971
partial_half                 in_sample       48.50  56.99  -0.1744   -2.81   0.755  +1.625
partial_half                 out_of_sample   46.44  55.02  -0.1780   -1.05   0.818  +1.745
no_target                    in_sample       40.48  46.63  -0.1495   -1.00   1.145  +2.407
no_target                    out_of_sample   37.58  43.56  -0.1512   +0.41   1.296  +2.638
```

**The quantity §6 reads:**

| window | partial_half − all_out_1r | 95% interval | width | floor |
|---|---|---|---|---|
| in-sample | +0.0015R | [−0.0286, +0.0378] | 0.066 | 0.15 ✓ |
| out-of-sample | +0.0247R | [−0.0162, +0.0780] | 0.094 | 0.15 ✓ |

## What the partial actually changes, and it is not the mean

Look at the columns that are not the mean. The partial does not move expectancy and it moves almost
everything else:

| | all_out_1r | partial_half | no_target |
|---|---|---|---|
| **p95** | **+0.970R** | **+1.625R** | +2.407R |
| payoff ratio | 0.743 | 0.755 | 1.145 |
| break-even win rate | 57.39% | 56.99% | 46.63% |
| skew | −3.34 | −2.81 | −1.00 |
| exits at a target | 42% | **none — the slot is a partial** | none |
| time exits | 11% | 38% | 49% |

**p95 is the whole story.** The all-out arm's 95th percentile is the target minus costs, and there
is nothing above it by construction. The partial's is **+1.625R**, because half of every winner is
still running. It buys back two thirds of the distance to the no-target arm's +2.407R and gives up
nothing measurable in the mean.

**That is a different trade from the one `M54` describes.** The course frames the partial as
psychology bought with expectancy. Measured here against a capped incumbent it is **tail shape
bought with nothing** — and the mean is unchanged because what the runner adds, the extra fill
takes away.

## The cost stress is where the course's objection turns out to be right

| window | partial_half_3x − all_out_1r_3x | 95% interval |
|---|---|---|
| in-sample | **−0.0356R** | **[−0.0627, −0.0043]** — excludes zero |
| out-of-sample | −0.0070R | [−0.0415, +0.0404] |

**A partial is a third fill.** Selling half the position costs half a side's slippage that the
all-out arm never pays: at the median `2 × ATR / price` of 0.0524 that is about **0.024R** at
ratified costs and **0.072R** at triple. At 1× it is inside the noise; at 3× it dominates, and the
in-sample interval excludes zero.

**So `M54-T0830`'s `Математические недостатки` is real in this system and is not the argument the
course gives.** It is not a forgone tail — the incumbent forgoes more of the tail than the partial
does. It is the extra transaction.

## The registered diagnostics, neither read by §6

**`partial_half_no_stop_move` — the stop move costs a little and buys win rate.**

| | mean net R, in sample | win rate | difference vs incumbent |
|---|---|---|---|
| `partial_half` (stop → breakeven) | −0.1744 | 48.50% | +0.0015 [−0.0286, +0.0378] |
| `partial_half_no_stop_move` | **−0.1649** | 44.00% | +0.0110 [−0.0275, +0.0619] |

§9 registered the question: *does the stop move carry the whole effect?* **It does not — it works
against it.** Leaving the stop where it was is worth about **+0.010R** more, and costs 4.5
percentage points of win rate, because the runner can then reach −1R instead of about zero. Both
intervals contain zero, so neither is established; the direction is recorded because §9 asked.

**`partial_third` sits where it should**, between the half and no target on every column —
+0.0041R and +0.0315R against the incumbent, p95 +1.857R. The ordering is monotone in how much is
banked early, which is what a real mechanism looks like and what an artefact usually does not.

## The registered predictions, one right and one wrong

**§3 predicted the win-rate ordering `all_out_1r > partial_half > no_target`.**

* in sample: 48.64 > 48.50 > 40.48 — **right**, by 0.14 percentage points at the top.
* out of sample: 46.21 < **46.44** > 37.58 — **wrong**. The partial wins slightly MORE often.

The reasoning behind the prediction was that half a position banked at 1R with the other half
stopped at breakeven is a small win rather than a large one — true, but it is still a **win**, and
the runner sometimes adds to it. The prediction was registered so that this correction is a
correction and not a discovery.

**§3 predicted `partial_half`'s skew sits between the other two.** In sample −3.34 < **−2.81** <
−1.00; out of sample −1.64 < **−1.05** < +0.41. **Right on both windows.** The mechanism is exactly
the registered one: a 1R target caps every winner and a partial caps half of each.

## What this does NOT establish

* **That anything is profitable.** Every arm loses. `all_out_1r` reads −0.176R and −0.203R, and the
  best arm on this page still loses 0.15R a trade.
* **That the partial is worthless.** It is worthless *for the mean* and it demonstrably reshapes the
  tail. A study measuring the mean cannot value that, and `M54-T0829`'s psychological advantage is
  not a property of a price series.
* **Anything about selection.** Entries are unselected, so no arm claims an edge.
* **Ten years.** 9.39, for the reason `TODO` §4 records.
* **Anything without the survivorship caveat.** 2,598 of 2,598 decade-long instruments still trade.

## What it costs the programme

**2 trials**, declared in §6a before the run. Cumulative: **99**, hurdle 2.52 sd(SR).

## Reproducing

```bash
PYTHONPATH=$PWD/src python tools/run_pr017.py --data data
```

```bash
PYTHONPATH=$PWD/src python tools/run_pr017.py --report
```

The QA stage has not been run for this study. `tools/verify_pr016_qa.py` is specific to `PR-016`'s
sample and constants; a partial's three fills need their own reconstruction, and that is an open
item rather than a done one.
