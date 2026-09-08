# PREREG: against a target that already caps every winner, does taking HALF at 1R and carrying the rest beat closing it all — and does either beat no target?

```
id:            PR-017
date:          2026-09-08
author:        Claude. Raised by `EVIDENCE_SUMMARY` §17.4 — the partial is the one exit lever in
               this system that has never been measured, and the only construction whose
               arithmetic on `PR-005`'s log came out positive where both pure alternatives are
               negative
status:        reported   (2026-09-08 - results/PR-017-report.md)   PRELIMINARY
verdict:       INCONCLUSIVE by §6's rule, and the word understates it: this is a POWERED
               null. +0.0015R [-0.0286, +0.0378] in sample and +0.0247R [-0.0162, +0.0780]
               out - both intervals INSIDE §8's 0.15R floor at half-widths of 0.033R and
               0.047R, against a registered minimum detectable effect of 0.05R. Selling half
               at 1R earns the same as closing it all there.
               THE FINDINGS THAT ARE NOT THE VERDICT. (1) The partial reshapes the TAIL for
               nothing: p95 goes +0.970R -> +1.625R, two thirds of the distance to the
               no-target arm's +2.407R, while the mean does not move. Against a capped
               incumbent the partial caps LESS. (2) M54-T0830's "Математические недостатки"
               is real and is NOT the argument the course gives: at 3x costs the partial is
               worse by -0.0356R [-0.0627, -0.0043], because it is a THIRD FILL and pays
               slippage for it. A transaction cost, not a forgone tail. (3) §9's question
               about the stop move is answered against it - leaving the stop where it was is
               worth about +0.010R more and costs 4.5 points of win rate.
               §6 has no branch for a powered null and could not say any of this.
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md` §§8–18, `TODO.md` §5. The censuses live in
`HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-016` | does the ratified screen change the outcome distribution at the ratified exit? | **`ACCEPT`**, and both arms lose. Its `unselected_two_slot` diagnostic is the no-target arm here |
| `measure_exit_surface` | expectancy over the stop × target grid | exploratory. **25 cells, every one all-or-nothing** |
| `measure_target_reachability` | how often is a target reached in 20 sessions? | exploratory; unselected entries |
| `DR-029` | what is the take-profit multiple? | **1R, ruled by the owner**, so a trade completes and can be observed |
| `PR-011` | does a 2 × ATR stop behave as the risk model assumes? | `reject`, in the reverse direction |

**Distinct because every exit this project has ever measured is all-or-nothing.** The 25 cells of
`measure_exit_surface` sweep two prices and close the whole position at whichever is reached first.
`PR-016` runs the ratified pair. **No study, no measurement and no tool has ever sold part of a
position**, and until 2026-09-08 `ExitPolicy` could not express it.

**And the course has an opinion this study exists to test.** `M54-T0830` asserts the partial has
`Математические недостатки`; `M54-T0832` frames partial-against-all-out as the comparison.
**That argument is against letting a winner run, and this system does not let winners run** —
`exit.target_r_multiple` is ratified at 1R and `PR-016` measures p95 at +0.971R in both its arms,
which is the target minus costs. Against *that* incumbent a partial caps LESS, not more.

## 1. Question

Under the ratified stop (`2.0 × ATR(14)`) and the ratified hold (20 sessions), on the same entries,
which of three exits earns the highest mean net R:

  * **`all_out_1r`** — take-profit at 1R, the whole position. `DR-029`, the incumbent.
  * **`partial_half`** — sell **half** at 1R (`M54-T0821` + `T0823`), move the stop to the entry
    fill (`M54-T0827`), carry the rest to the stop or the clock.
  * **`no_target`** — no profit slot at all. What `PR-005` ran.

## 2. Hypothesis

**H1.** `partial_half` beats `all_out_1r`, with the paired bootstrap interval on the difference
excluding zero, on both the in-sample and the out-of-sample window.

**H0.** It does not — the two are indistinguishable, or the course's `Математические недостатки`
holds even against a capped incumbent.

**Why this is not obvious in either direction.** A partial gives up half the runner's upside to
lock half a winner early, which is the course's objection. But the incumbent gives up **all** of it
at the same price. On `PR-005`'s log the arithmetic came out at roughly +263R for the partial where
all-out reads −619R against no target — **and that estimate is not this study**: it assumed the
runner exits flat, which the breakeven stop makes likely and does not guarantee.

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean net R, partial_half minus all_out_1r, paired on entry months
minimum detectable effect:  0.05 R.  From PR-016's OWN dispersion rather than PR-005's, which
                   §7 of that report says to use: the realised 95% half-widths there were
                   0.040 R in sample and 0.070 R out, on the same universe, the same window
                   and the same monthly clustering. This study's arms share ENTRIES exactly -
                   only the exit differs - so its paired differences should be no wider.
power floor:       0.15 R end to end on the difference interval in either window. Tighter than
                   PR-016's 0.20 because the pairing here is exact. If a window's interval is
                   wider, the study reports the measurement and refuses to read the window.
also predicted:    the WIN RATE ordering is all_out_1r > partial_half > no_target, because a
                   trade is a win when its net R exceeds zero and half a position banked at
                   1R with the other half stopped at breakeven is a small win rather than a
                   large one. PR-016 measures the two ends at 48.64% and 40.48%. Registered
                   so that a confirmation cannot later be presented as a finding.
also predicted:    partial_half's SKEW sits between the other two. The 1R target caps every
                   winner (PR-016: skew -2.41) where no target does not (PR-005: +1.61), and
                   a partial caps half of each winner.
```

## 4. Data

```
store:         data/bars.duckdb, daily bars, series RAW, one --as-of instant
window:        as PR-016 - asked from 2016-01-04, and the MEASURED span reported beside it.
               PR-016 obtained 8.91 years of entries; this study will obtain the same, and
               the ten-year instruction is still unmet for the reason TODO section 4 records
country:       USA
universe:      DR-003's liquidity rule at each formation date's own bar
entries:       UNSELECTED - every admitted name, every 20 sessions. The same control set
               PR-016 used, and the reason this study spends what measure_exit_surface spends:
               with no signal there is no edge being claimed, only an exit measured against
               the market
benchmark:     not used. No arm here is compared to an index
survivorship:  ABSENT and material, exactly as PR-016 records it - 2,598 of 2,598 decade-long
               instruments still trade
adjustment:    split-adjusted, NOT dividend-adjusted. Measured 2026-09-07
```

## 5. Method

**One entry set, three exits.** Every arm enters the same names on the same dates at the same fill,
so the arms are exactly paired and every difference is the exit.

**The partial, spelled out.** At the first bar whose high reaches `entry + 1.0 R`, half the shares
are sold at that price less slippage; the working stop moves to the entry **fill**; the remainder
runs to the stop or the clock. Share counts round down, and a fraction that rounds to zero or to
the whole position takes no partial and spends the slot — a position that kept re-trying would sell
itself away on a strong run.

**Bar-order rules, `DR-042` §3, unchanged and extended by one.** A session opening below the stop
fills at the open; a session opening above the profit leg fills at the leg, not the better open;
intraday the **stop is checked before the profit leg**, whether that leg is a target or a partial
trigger, and the bar is flagged `ambiguous`; the clock is last. `DR-042`'s tie-break is unruled and
its measured effect is 0.05% of exits, so this study is `PRELIMINARY` on the same terms.

**Costs.** 25 bps a side and $0.005 a share, on **every** fill — a partial is a third fill and pays
for itself. Commission is unchanged in total, because the shares traded are the same either way;
slippage is not, because it is charged per fill on the price.

**Statistics.** As `PR-016`: win rate, mean and median net R, payoff, break-even win rate, skew,
the p1–p99 ladder, MFE/MAE, exit-reason mix. Intervals by moving-block bootstrap over entry months,
block 3, 10,000 resamples, seed 20260908.

**Registered diagnostics, reported and never read by §6.** `partial_third` (`M54-T0824`), and
`partial_half_no_stop_move` — the same partial with the stop left where it was, which is the other
reading of an unset `exit.stop_move_after_partial` and is what says how much of any effect is the
partial and how much is the moved stop.

**Perturbation.** Cost stress ×3, re-simulated, each arm differenced against its own cost level —
`PR-016` learned that the hard way.

## 6. Decision rule

Read on **`partial_half` minus `all_out_1r`, mean net R**, and nothing else.

```
ACCEPT        both windows meet §8's sample rule, both clear §8's power floor, and BOTH
              paired difference intervals lie entirely above zero.
REJECT        both qualify, both clear the floor, and BOTH lie entirely below zero - the
              course's Математические недостатки, holding even against a capped incumbent.
              PREREG_TEMPLATE rule 8's both-negative branch.
INCONCLUSIVE  anything else.
```

**`ACCEPT` sets no parameter.** `exit.partial_trigger`, `exit.partial_fraction` and
`exit.stop_move_after_partial` are the owner's, and an accept here licenses one sentence: *at the
ratified stop and hold, selling half at 1R earns more per trade than closing the whole position
there.* **It says nothing about profitability** — `PR-016` measures every arm of this family losing
money, and a less-negative exit is not an edge.

## 6a. Trials

**Two**, declared here and entered in `trial_budget.py`: `partial_half` and `no_target` as two exit
configurations against the incumbent. The incumbent itself is the comparison basis and spends
nothing, for `PR-008`'s reason — no signal, no edge claimed.

`partial_third` and `partial_half_no_stop_move` are **readings of the same construction at a
different knob** and §6 never touches them. **A reader may reject that**; if they do the count is
four and the deflated-Sharpe hurdle moves accordingly. Cumulative before this study: 97.

## 7. Stopping rule

One pass, one `--as-of`. No interim look, no early stop.

## 8. Sample

```
minimum:       200 trades AND 24 entry months in EACH window, as PR-016
power floor:   0.15 R end to end on the difference interval, registered in section 3
if not met:    report the measurement and REFUSE to read the window as evidence
```

Expected from `PR-016`'s run: about 119 formation dates, 51 and 54 entry months, and on the order
of 10⁵ trades an arm. **Months bind, not trades**, which is why the bootstrap resamples months.

## 9. What would refute this

**H1 is refuted** if neither window's difference interval excludes zero above the floor, or if both
lie below it.

**H1 is damaged without being refuted** if `partial_half_no_stop_move` carries the whole effect —
that would make this a study about moving a stop rather than about selling half, and the report
must say so in those words.

**What would NOT refute H1:** every arm losing money. That is `PR-016`'s finding and it is the
condition this study runs under, not a result of it.

**What would refute the STUDY rather than the hypothesis:** `all_out_1r` failing to reproduce
`PR-016`'s `unselected` arm, or `no_target` failing to reproduce its `unselected_two_slot`
diagnostic. Both are the same construction on the same entries, so both must match, and the report
must show the comparison.

## 10. Amendments

None.
