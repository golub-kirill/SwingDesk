# PREREG: on the entries the ratified screen actually selects, does the ratified exit policy earn more than holding to the clock — and what does it buy on the risk side if it does not?

```
id:            PR-018
date:          2026-09-08
author:        Claude, at the owner's instruction 2026-09-08 — "proceed on 2 as a solid step",
               where 2 is the comparison EVIDENCE_SUMMARY §10 and the exit surface imply and
               nothing has ever run on selected entries
status:        registered
verdict:       (not yet run)
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md` §§8–19, `TODO.md` §§4–5. The censuses live in
`HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `measure_exit_surface` | expectancy over the stop × target grid, against a buy-and-hold null | exploratory. **Unselected entries**, and it is the only thing here that has ever compared an exit to no exit |
| `PR-016` | does the ratified screen change the outcome distribution at the ratified exit? | `ACCEPT`; both arms lose. **Never compared the exit to no exit** |
| `PR-017` | does a partial beat all-out at 1R? | a powered null. **Three exits compared to each other, never to none** |
| `PR-011` | does a 2 × ATR stop behave as the risk model assumes? | `reject`, in the reverse direction. Measures the stop's INTEGRITY, not its worth |
| `DR-012` | what are the stop multiple and the holding period? | ratified `assumed`, and its own §8.3 notes the values were held as study CONDITIONS, never found |

**Distinct because the comparison has never been made on entries anyone would trade.** Everything
above either compares exits to each other or compares an exit to no exit on **unselected** names.
The selected decile is where the system's money would go, and the exit surface's own caveat is that
its entries carry no signal.

**And the numbers that make it worth asking, from `EVIDENCE_SUMMARY` §10 and the exit surface** —
the same entries, one round trip each, therefore the same cost:

| | gross | net at 50 bps |
|---|---|---|
| buy and hold, 20 sessions | **+0.140R** | −0.031R |
| the ratified `2.0 × 1R` cell | **+0.042R** | −0.128R |

Decomposed: the 1R target costs about **0.04R** of gross (at a 3R target the cell reads +0.084R),
and the 2 ATR stop about **0.056R** more. **If that survives on selected entries it is the largest
effect measured in this project** — larger than the screen is worth, larger than the clock.

## 1. Question

On the top decile by the live `ByMarketPathStrength` — the entries the running system selects —
does the ratified exit (`2.0 × ATR(14)` stop, `1.0R` target, time exit at session 20) earn a higher
mean net R than holding the same names for the same 20 sessions with **no stop and no target**?

**And if it does not: what does it buy?** §5 registers the risk side, and §6 refuses to read the
mean alone.

## 2. Hypothesis

**H1.** The ratified exit's mean net R exceeds the hold-only arm's, with the paired bootstrap
interval on the difference excluding zero on both windows.

**H0.** It does not — the exit policy costs return, and the question becomes what it buys.

**This hypothesis is expected to fail, and that is why it is registered this way round.** The
incumbent is on trial and the null is doing nothing. Registering it the other way — *does holding
beat the exit* — would let a rejection read as a defence of the exit, and §6 would inherit the
asymmetry. **A study should put the thing that costs something on the side that has to prove
itself.**

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean net R, ratified minus hold_only, paired on entry months
predicted sign:    NEGATIVE. The exit surface reads +0.042R gross against +0.140R on
                   unselected entries at the same cost, so the difference there is about
                   -0.098R. On selected entries it could be smaller - the screen's names
                   trend more, so a target caps more of a real move - or larger. The sign is
                   predicted; the magnitude is not.
minimum detectable effect:  0.05 R.  From PR-017, which paired the same way on the same
                   universe and realised half-widths of 0.033R and 0.047R. The arms here
                   share entries exactly, as PR-017's did.
power floor:       0.15 R end to end on the difference interval in either window, PR-017's
                   floor and for its reason.
also predicted:    hold_only's MAE distribution has a materially fatter left tail. The stop
                   exists to bound it and PR-011 measured that it does - overshoot 0.03R to
                   0.10R by band. If the tails are indistinguishable, the exit policy is
                   costing return and buying nothing, which is a stronger finding than H0
                   and is registered here so it cannot be presented as a discovery.
```

## 4. Data

```
store:         data/bars.duckdb, daily bars, series RAW, one --as-of instant
window:        as PR-016 and PR-017 - asked from 2016-01-04, MEASURED span reported beside it
country:       USA
universe:      DR-003's liquidity rule at each formation date's own bar
entries:       the top decile by the LIVE ByMarketPathStrength at rs.lookback 126, through
               `select` - the same code path the running system uses, and the same arm PR-016
               calls `ranked`
benchmark:     not used. Neither arm is compared to an index
survivorship:  ABSENT and material - 2,598 of 2,598 decade-long instruments still trade
adjustment:    split-adjusted, NOT dividend-adjusted
costs:         25 bps a side and $0.005 a share, DR-005. BOTH ARMS PAY ONE ROUND TRIP, so the
               comparison is nearly cost-invariant by construction - which is the point.
               EVIDENCE_SUMMARY §10 measures that 25 bps describes 09:30 and is 4x to 14x too
               high later; §5 registers what a cheaper execution would do to each arm, and it
               is NOT a free improvement to either
```

## 5. Method

**One entry set, two exits.** Same names, same dates, same fills; only the exit policy differs.

* **`ratified`** — stop `2.0 × ATR(14)` fixed at entry, target `1.0R`, time exit at session 20,
  stop checked first (`DR-042`).
* **`hold_only`** — `protective=False`, no target, exit at the close of session 20. **The stop is
  still computed**, because R is `entry − stop` (`RISK_SPEC` 2) and a null arm priced in different
  units cannot be subtracted from anything.

**The risk side, and §6 reads it.** For each arm: the MAE distribution in R — mean, p5, p1, the
worst, and the share of trades whose MAE went below −1R, −2R and −3R. **The exit policy's job is to
bound the left tail**, and a study that reported only the mean would answer half the question and
sound like it had answered all of it.

**Registered diagnostics, reported and never read by §6.**

  * `unselected` — the same pair on every admitted name, which connects this to
    `measure_exit_surface` and says whether selection changes the answer.
  * `ratified_no_target` — stop and clock, no take-profit. It splits the 0.098R into the target's
    share and the stop's share on selected entries, which the exit surface only did unselected.

**Perturbation.** Cost stress ×3, re-simulated, each arm against its own cost level. **And a cheaper
execution is registered as a second perturbation**: both arms re-simulated at 5.75 bps a side,
`EVIDENCE_SUMMARY` §10's measured 11:00 median. **This is NOT a claim that the strategy can be
executed there** — `DR-040` §4 and `measure_execution_time` both record that a later entry changes
the gross as well as the cost, and this re-prices an entry struck at the open. It is registered to
show which arm the cost level favours, because the answer is not obvious and the two arms pay the
same round trip.

**Statistics.** As `PR-016` and `PR-017`: win rate, mean and median net R, payoff, break-even win
rate, skew, the p1–p99 ladder, MFE/MAE, exit-reason mix. Moving-block bootstrap over entry months,
block 3, 10,000 resamples, seed 20260908.

## 6. Decision rule

Read on **`ratified` minus `hold_only`, mean net R**, and on the MAE comparison beside it.

```
ACCEPT        both windows meet §8's sample rule, both clear §8's power floor, and BOTH
              paired difference intervals lie entirely ABOVE zero. The exit policy earns
              more than doing nothing.
REJECT        both qualify, both clear the floor, and BOTH lie entirely BELOW zero. The exit
              policy costs return, and §6 then REQUIRES the report to state what it buys:
              the MAE comparison is reported in the same paragraph as the verdict, never
              after it.
NULL          both qualify, both intervals are INSIDE the power floor, and both contain
              zero. PREREG_TEMPLATE rule 10's branch, and PR-018 is the first study to
              carry it. The exit policy neither earns nor costs a detectable amount, and
              the MAE comparison decides whether it is worth keeping.
INCONCLUSIVE  anything else.
```

**No verdict moves a parameter.** `exit.atr_stop_multiple` and `exit.target_r_multiple` are the
owner's, every cap in `risk.*` is denominated in the stop, and `CHARTER` A-001 has the last word on
anything that touches risk. **A `REJECT` here licenses one sentence** — *the ratified exit earns
less than holding to the clock, by this much, and bounds the left tail by this much* — and the
trade between those two numbers is a decision, not a measurement.

## 6a. Trials

**Two**: `ratified` and `hold_only` are two exit configurations evaluated on one entry set. The
diagnostics are readings of the same two at a different knob and §6 never touches them; a reader who
rejects that counts four. Cumulative before this study: **99**, hurdle 2.52 sd(SR).

## 7. Stopping rule

One pass, one `--as-of`. No interim look, no early stop.

## 8. Sample

```
minimum:       200 trades AND 24 entry months in EACH window
power floor:   0.15 R end to end on the difference interval
if not met:    report the measurement and REFUSE to read the window as evidence
```

Expected from `PR-016`: about 27,000 selected trades, 51 and 54 entry months. **Months bind.**

## 9. What would refute this

**H1 is refuted** by a `REJECT`, which §3 predicts. That is the point of the study and it is not a
failure of it.

**What would refute the STUDY rather than the hypothesis:** `ratified` failing to reproduce
`PR-016`'s `ranked` arm — same construction, same entries, same exit — to the tolerance `PR-017`
achieved, which was every digit out of sample. The report must show that comparison first.

**What would NOT settle anything either way:** the mean alone. §6 requires the MAE comparison in the
verdict's own paragraph, because an exit policy that costs 0.1R and removes a −47R tail is a
different object from one that costs 0.1R and removes nothing.

## 10. Amendments

### A-1 — the arms share signal DATES, not realised entries, and the gap is wider here than in `PR-017`

**2026-09-08, before this study's own data produced any result.** Found while smoke-testing the
runner on a synthetic store of random prices.

§5 says *"Same names, same dates, same fills; only the exit policy differs."* **The first clause is
right and the entries are not identical.** `hold_only` never stops out, so its positions run the
full 20 sessions every time; the engine allows one position per instrument, so a name still held on
the next formation date records `POSITION_OPEN` and that entry never happens. `ratified` closes
early whenever the stop or the target fires, and its name is free again.

On the synthetic store: **263 `ratified` entries against 182 `hold_only`** from the same dates — a
31% gap, where `PR-017`'s A-1 measured 26% between its exits.

**This is a property of the exit being compared and it cuts BOTH ways, which is why it is
registered rather than corrected.** An exit that frees capital sooner takes more trades; an exit
that never frees it takes fewer and each is held longer. A study that forced the entry counts equal
would be measuring a different pair of policies from the ones anyone would run.

**What it changes about the reading**, and §6 is unaffected because the difference is in mean net R
*per trade* rather than in a total:

* both entry counts are reported for every window;
* the report states the **capital-efficiency** difference explicitly — `hold_only` earning more per
  trade while taking fewer trades is a different claim from earning more per year, and this study
  measures only the first.

Registered under rule 3's clock as `PR-017`'s A-1 was: it comes from the harness's behaviour on
random prices, not from this study's data.
