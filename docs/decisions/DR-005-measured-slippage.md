# DR-005: Slippage measured from daily OHLC, replacing DR-004's assumed 5bps

```
date:       2026-08-05
status:     proposed
parameters: costs.slippage_model
components: none - swingdesk.validation.backtest.costs charges it; this sets its input
supersedes: DR-004, slippage component only. Its commission model stands.
```

DR-004 set slippage at **5bps per side** and said what it was:

> 5bp on a liquid instrument entering at the open is on the optimistic side of plausible

It also rejected the correct alternative as unavailable — *"spread-derived slippage from quoted
bid/ask: correct and unavailable — no free source serves historical intraday spreads
point-in-time."* That is true of **quotes**, and both estimators used here need none. They read daily
high, low and close, which `data/bars.duckdb` has held all along.

This matters because PR-005 reported the base strategy at **+0.028R** per trade at 1× costs and
**−0.123R** at 3×. The sign of the project's headline result therefore sat inside an assumed number
that had never been checked.

---

## Decision

| Parameter | Value |
|---|---|
| `costs.slippage_model` | **25 bps of price, each side**, applied to the fill |

Stress regime unchanged: **3×** (`validation.stress_cost_multiplier`), which now means 75bps per
side rather than 15.

Measured 2026-08-05 by `tools/measure_spread.py` over the stored universe as of
`2026-08-03T22:17:23-05:00`. Evidence: `measurements/spread-sample.json`, committed with this
record. Status stays **`assumed`**, not `validated` — a decision record is not a pre-registered
study (`README.md` rule 5), and a measurement taken without one does not acquire that authority
however carefully it was made.

## Why this one

Two estimators recover the proportional effective spread `S = (ask − bid)/mid` from daily bars:
**Corwin & Schultz (2012)** from the two-day high-low range, **Abdi & Ranaldo (2017)** from the close
against the mid-range. A fill at the touch pays **S/2 per side**, and per-side is what this parameter
holds — the one conversion between what is measured and what a backtest charges, performed in
`spread.per_side_bps` and nowhere else.

Across the 1,131 A-tier instruments with at least 200 usable pairs:

| Aggregate | Median full spread | Per side | vs DR-004's 5bps |
|---|---|---|---|
| Abdi-Ranaldo | 0.005088148 | **25.44 bps** | 5.1× |
| Corwin-Schultz, mean-aggregated | 0.006430505 | 32.15 bps | 6.4× |
| Corwin-Schultz, median-aggregated | 0.002373280 | 11.87 bps | 2.4× |

All three are `summary_a_tier` in the evidence file, at its reported nine-decimal resolution.

**The claim that survives every aggregate: 5bps is too low, by at least a factor of 2.3.** The three
disagree about how much, and the disagreement is reported rather than averaged away. 78% of A-tier
names exceed 5bps per side on Abdi-Ranaldo and 94% on Corwin-Schultz *mean*-aggregated; even the
median-aggregated form, the most conservative of the three, still puts 64% above it. The aggregation
is named because the two differ by thirty points and an unqualified "Corwin-Schultz" would be
quoting the higher one.

**Abdi-Ranaldo is the headline** because `tests/test_spread.py` measures both against a series whose
spread is known by construction, and they are not equally good:

- on a **zero-spread** series Abdi-Ranaldo reads zero; Corwin-Schultz reads a full spread of about
  0.0053 — 27bps per side — because flooring its negative two-day estimates at zero leaves a residue
  no sample size removes;
- on a series that **gaps every session**, Corwin-Schultz loses a real 2% spread entirely even with
  the paper's overnight adjustment applied — the enlarged two-day range drives almost every pair
  negative — while Abdi-Ranaldo reads through it.

Those two biases point in opposite directions, which is why Corwin-Schultz brackets rather than
confirms. The estimator that recovered a known spread cleanly is the one the value comes from.

**25 rather than 25.44.** Rounded to the nearest basis point for legibility; the measured figure is
in the record. The rounding is worth 0.44bps against a value whose own estimators disagree by 20.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| keep 5bps | contradicted by the measurement, on the data the project already had |
| the most conservative aggregate, 11.87bps | Corwin-Schultz median-aggregation is the reading most exposed to the gap collapse this record measures. Choosing the lowest of three numbers because it is the least alarming is how a cost model gets built backwards |
| the highest, 32.15bps | same objection mirrored; it is the aggregate carrying the documented upward floor |
| average the estimators | they disagree for understood and opposite reasons. A mean of a floored estimate and a collapsed one is a number with no property either parent had |
| a per-instrument value | the estimators are noisy per name — 19% of A-tier estimates floor at zero, and the median name has 45% of its pairs negative. Per-name figures are evidence, not parameters |
| defer until a broker is chosen | that was DR-004's position and it left the headline result resting on an unchecked assumption for three days longer than it needed to |

## What would overturn this

**Measured live slippage against modelled** (M74-T1110), which DR-004 already reserved as `PR-006`
when a forward test exists. That remains the intended replacement: these estimators infer a spread,
a forward test observes a fill.

Also: **wider store coverage.** The store holds 3,688 instruments, 3,687 of them among the 13,043
currently eligible — **28.3%** — filled oldest-first rather than sampled at random, so
`UniverseSelection.is_partial` is True and this figure inherits that. (The two counts differ by one
name that has bars and is no longer eligible. Stated because 3,688 is the store's count and 3,687 is
the coverage numerator, and the two are not interchangeable.) The A-tier subset it produced is the A-tier *of the stored subset*, not of the
universe. Completing coverage (`tools/refresh_universe.py`, ~5 more passes) and re-running this —
about twenty minutes of local compute over the full population — needs no new decision.

## Consequences

1. **PR-005's operative column is the stress column.** Two of three aggregates put true cost *beyond*
   3×; the most conservative puts it just under. Under every reading, the relevant published result
   is **−0.123R per trade, not +0.028R**. The 1× column was never the applicable one.
2. **That is a restatement, not a re-run.** PR-005 published both columns, so choosing between them
   on new cost evidence adds no post-hoc cost level to a reported study. It is also not exact: the 3×
   column stressed commission *and* slippage together, while this measures slippage only. Quantifying
   the strategy at measured costs needs a **new pre-registration** — `PR-007`, since `PR-006` is
   spoken for — and a re-fetch, because PR-005's window (2016-08-01 → 2026-07-31) is eight years
   longer than the store holds.
3. **Every R computed under DR-004's 5bps is now known to be optimistic**, including PR-002's
   cost-stressed arms. PR-002's finding was reported as surviving cost stress at 3×, which this
   supports rather than undermines — but the figures in it were charged at the old value and say so.
4. `HANDOFF.md` §3 needs its cost sentence corrected: costs are no longer assumed, and the
   uncomfortable summary gets *more* uncomfortable rather than less.
