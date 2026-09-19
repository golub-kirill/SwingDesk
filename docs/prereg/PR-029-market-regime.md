# PREREG: do CARD-001's picks do differently against SPY when SPY is below its 200-day mean?

```
id:            PR-029
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19 - the fourth of four single changes
               registered together (PR-026 carries the shared design, sections 4 and 5)
status:        reported   (2026-09-19 - results/PR-029-report.md)
verdict:       INCONCLUSIVE, as predicted - dates below SPY's 200-day mean less dates above,
               +0.477% a trade [-0.312, +1.317]
```

---

## 0. Refutation-family check

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-002` | a regime classifier as a gate on decisions | `INCONCLUSIVE`, corrected from `ACCEPT` |
| `PR-022` | `SPY` itself held above its ten-month mean | `INCONCLUSIVE` — a risk dial, not an edge |
| `entry-features-2026-09-19` | `PR-024`'s entries sliced at the signal close — EXPLORATORY | entries signalled with `SPY` below its 200-day mean read far better — 1,456 of them, most in 2022 |

**distinct because it reads the card's own trades by regime, in both directions.** The published
expectation runs one way — momentum suffers after the market turns down — and the exploration saw
the other, on essentially one episode. So this is registered two-sided: it asks whether the regimes
differ, and says which way.

## 1. Question

Over 2018-09..2022-08, do the card's entries signalled while `SPY` closed below its 200-session mean
earn a different excess over `SPY` from those signalled while it closed above?

## 2. Hypothesis

**H1.** Dates below less dates above, per-date mean excess over `SPY`, has a 95% interval that
excludes zero. **H0.** It does not. `ACCEPT` names the below side as better; `REJECT` the above.

## 3. Prediction, stated numerically before the run

```
primary quantity:  [mean over dates signalled with SPY below its 200-day mean] - [mean over dates
                   above], of each date's mean excess over SPY; two groups of months, resampled in
                   moving blocks together
predicted:         INCONCLUSIVE. The window holds three spells below the mean - late 2018, spring
                   2020, 2022 - a handful of months, so the interval is about 0.95 wide whatever
                   the sign, and only an effect beyond about +/-0.48 reads
if H1 were TRUE:   an interval excluding zero
minimum detectable effect:  0.68 points per dollar (half-width 0.476 at 90% complete) - from tools/power_pr026.py
                   (PR-026-power.json). Widths only
power floor:       0.30 points end to end, gating NULL only
```

## 4. Data and 5. Method

`PR-026` §4 and §5. **This study's split:** a date is below when `SPY`'s close on the signal date is
at or under the mean of its last 200 closes, the signal's included (`run_pr026.features`). The
interval resamples months in moving blocks of three and takes the difference of the two groups'
means in each resample (`run_pr026.two_group_interval`); a resample missing either group is
dropped. `level` is the below dates' own mean excess.

```
split:           none - the regime is a property of the date, read on the whole window
split buys:      nothing is selected
perturbations:   cost_adverse, gross - as PR-026
```

## 6. Decision rule

`PR-026` §6's table, with its signs read as named in §2. `ACCEPT` — *the card did better against
`SPY` on dates below the mean*. `REJECT` — *better above*. `NULL` — *no difference the sample could
see*. Not a rule for the card: a gate built on this is a further study.

## 6a. Trials

**One** — the fourth of four (127 → 131, hurdle 2.614 → 2.624).

**Registered as NOT run:** other means (10 months, 100 sessions); volatility regimes; breadth.

## 7. Stopping rule, 8. Sample, 9. Refutation

As `PR-026`. **The sample rule counts dates in both groups**; if either holds fewer than 24 months'
worth of its own dates the study says so in its report beside the branch.

```
minimum detectable effect:  see section 3
power floor:                0.30 points end to end, gating NULL only
```

## 10. Amendments

None.
