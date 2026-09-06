# PREREG: at what holding period, if any, does the ratified selection rule earn a net excess that excludes zero — and is the shortest such period longer than the twenty sessions now assumed?

```
id:            PR-014
date:          2026-09-06
author:        Claude, at the owner's instruction 2026-09-06
status:        registered
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md` §§8, 8a, 10, 11, 12, and `TODO.md` §5. The
censuses live in `HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-012` | does a four-position book beat a control? | **refused** a verdict — structural sample ceiling, 181–203 trades against its own 200 |
| `PR-013` | does the ORDERING carry information at 5 sessions? | **exploratory** — all six gross intervals include zero |
| `measure_momentum_horizon` | the decile SPREAD at 5/20/63/126 | exploratory; excludes zero only at 126 |
| `measure_long_only_horizon` | the same, converted to long-only | exploratory; +4.805% [−0.009, +10.125] at 126 — misses |
| `measure_short_leg` | does the spread survive a borrowable short leg? | exploratory; +7.705% [+2.515, +12.863] net at 126 |
| `measure_banding` | does a wider sell band pay? | exploratory; every interval includes zero |

**distinct because — and there are two reasons, of which the second is the whole study.**

**First, the question is the HORIZON itself.** Every study above fixed a holding period and asked
about the signal. This fixes the signal — `CARD-001`'s ratified selection rule, unchanged — and asks
which holding period it should be run at. `exit.max_holding_period` is **20 sessions,
`assumed:DR-012`**, and no study has ever tested it.

**Second, and this is why a new study can say something the sweeps could not: every measurement
above used NON-OVERLAPPING windows, and that is what made the answer unreachable.** Ten years of
daily bars contain seventeen non-overlapping 126-session windows. Seventeen observations cannot
resolve anything, and `EVIDENCE_SUMMARY` §8a named the consequence exactly — *"a longer hold buys a
bigger effect and fewer chances to see it"*. That is a property of the **estimator**, not of the
market. The standard construction in this literature holds `K` overlapping sub-portfolios formed one
period apart, so every formation date contributes and the book turns over `1/K` of itself per
period. §5 registers it, and §5b registers the inference it requires.

**The constraint was an owner rule and the owner lifted it on 2026-09-06 — see §10, amendment A-1,
made before the tool existed.** This paragraph is left as written.

---

## 1. Question

**Over what holding period does the ratified selection rule produce an annualised net excess whose
95% interval excludes zero, and what is the SHORTEST such period?**

It can come out "no": no horizon in the grid qualifies.

## 2. Hypothesis

**H1.** For `CARD-001` v1's selection rule — top decile by `rs.lookback` = 126-session relative
strength against `SPY`, `rs.benchmark_form` = path, ratified by `DR-030` — the annualised net excess
over the benchmark rises with holding period across the registered grid, and excludes zero at some
horizon **longer than 20 sessions**.

**H0.** No horizon in the grid produces an annualised net excess whose interval excludes zero.

Components: `relative_strength` `M31-T0464-v5.0` v1, unchanged. This study changes no component.

## 3. Prediction, stated numerically before the run

**If H1 is TRUE:** annualised net excess is monotone or single-peaked in horizon, and at least one
horizon ≥ 42 sessions has a 95% interval strictly above zero. Extrapolating the exploratory
figures — +0.562% per 20 sessions and +4.805% per 126 — the annualised gross is roughly **+7%** and
**+9.6%** respectively, so the prediction is a net figure between **+4% and +10% a year** at the
qualifying horizon.

**If H0 is TRUE:** every horizon's interval straddles zero, and the point estimates show no trend in
horizon beyond what the widening intervals allow.

**These look different.** Under H1 at least one interval clears zero; under H0 none does.

## 4. Data

```
universe:      DR-003's rule - close >= $5.00, 20-session ADTV >= $5,000,000, >= 250 bars -
               re-evaluated at EVERY formation date, never once at the end
window:        2016-08-22 to the store's knowledge horizon. The start is not chosen: it is the
               first session on which >= 100 instruments carry enough history to be admitted, and
               MIN_NAMES_PER_DATE refuses every date before it
snapshot:      the bar store's latest knowledge_time at run time, recorded in the result
costs:         DR-005, 25 bps per side, ratified. TWO sides per rebalance for the long-only arm and
               FOUR for the long-short arm, because both legs turn (EVIDENCE_SUMMARY section 11)
               Commission: DR-039 sets it to ZERO at this venue. Regulatory fees are ~0.9% of the
               slippage term and are EXCLUDED - a known bias, in the pessimistic direction for H1
survivorship:  ABSENT. The directory is today's, so a name that delisted is missing. For the
               LONG-ONLY arm this biases the result UPWARD and the arm is therefore reported as an
               upper bound. For the LONG-SHORT arm it biases DOWNWARD, because a delisted loser
               would have been the sample's most profitable short
```

## 5. Method

```
split:          PRIMARY 2016-08-22 to 2021-12-31; HOLDOUT 2022-01-01 onward
split buys:     protection against picking the maximum of a twelve-cell sweep. The decision rule in
                section 6 selects a horizon FROM THE PRIMARY WINDOW ONLY and then reports it on the
                holdout without re-selecting. Without the split, "the best horizon" is a statement
                about noise; this is the one thing a horizon sweep must not do and the whole reason
                this study is registered rather than swept
selection rule: the SHORTEST horizon in the grid whose primary-window net interval excludes zero.
                NOT the largest point estimate - a rule that picks the maximum is the data-snooping
                the course prohibits, and shortest-that-qualifies is decidable in advance
perturbations:  WALKFORWARD_SPEC 4, numbers 3 and 4 - cost stress at 1x and 3x DR-005
statistic:      ANNUALISED net excess over rs.benchmark, equal-weighted across held names.
                Annualised because the grid spans 20 to 252 sessions and +0.5% per 20 sessions is
                not comparable to +8.7% per 126 without it: annual = per-period x (252 / horizon)
```

**The construction, registered because it is the point of the study:**

```
formation:      252 sessions of relative strength, rs.benchmark_form = path (DR-030)
rebalance:      every 21 sessions, at EVERY such date - not every `horizon` sessions
book:           K = round(horizon / 21) overlapping sub-portfolios. On each rebalance date the
                oldest sub-portfolio is closed and one new one opened, so a name is held for
                `horizon` sessions and 1/K of the book turns over each rebalance
turnover:       1/K per 21 sessions BY CONSTRUCTION, which is what makes the cost fall with
                horizon rather than staying flat
horizons:       20, 42, 63, 126, 189, 252 sessions  (1, 2, 3, 6, 9, 12 months)
arms:           long-only vs rs.benchmark; long-short with the short leg drawn from the
                most-traded quartile (EVIDENCE_SUMMARY section 11's construction, unchanged)
```

## 5b. Inference, registered separately because overlapping windows demand it

**A moving-block bootstrap over the rebalance-date series**, block length `max(K, 6)` rebalances,
10,000 resamples, seed `20260906`. Percentile interval.

**Why not the plain bootstrap every other study here uses:** overlapping sub-portfolios share
holdings, so successive rebalance returns are autocorrelated by construction, and an i.i.d.
resample would report an interval several times too narrow. The block length is tied to `K` because
that is exactly how many rebalances two overlapping books can share a position across.

**This is an authored import** (`AGENTS.md` §10.3) and marked as one: Künsch (1989), the moving-block
bootstrap. The course supplies no method for dependent data.

**The overlapping construction does NOT create information.** It uses every formation date instead
of one in `K`, which lowers the variance of the estimate; it does not add independent years. A
result that needs 2016–2026 to clear zero is still a result about one decade, and §9 says so.

## 6. Decision rule

```
accept if:     in the PRIMARY window, the shortest qualifying horizon's annualised net interval
               excludes zero at 1x costs AND its point estimate remains positive at 3x;
               AND on the HOLDOUT, that same horizon's interval also excludes zero
reject if:     no horizon's primary-window interval excludes zero at 1x costs
both negative: if the selected horizon's net excess AND the buy-and-hold control are both below
               zero, the verdict is `inconclusive` regardless of which loses less. Comparing two
               losers on which loses less is not a finding (PREREG_TEMPLATE rule 8)
inconclusive:  a horizon qualifies on the primary window and fails on the holdout; or the sample
               rule in section 8 is not met; or any other outcome
```

**The control is buy-and-hold on the admitted universe over the same window**, not zero.
`DR-029` §7 measured that a 20-session hold of everything returns **+0.140R gross / −0.030R net**,
and a selection rule that merely matches the universe has selected nothing.

## 6a. Trials

**Twelve configurations**: 6 horizons × 2 arms. The 1x/3x cost stress is a restatement of the same
arm and multiplies nothing; the primary/holdout split is a data split, not a search.

Declared in the result as `trials: 12` and read by `tools/trial_budget.py`. **The programme stands
at 61 and this takes it to 73**, moving the hurdle from 2.35 to about 2.40 sd(SR) — the marginal
trial is cheap and the first ones were not, which is the shape that tool exists to print.

## 7. Stopping rule

**One run over the declared grid.** The study ends when the twelve cells are reported. It does not
end when a horizon qualifies, and the grid is not extended if none does — an extension after seeing
the result is a new pre-registration, not this one.

## 8. Sample

```
minimum:       >= 100 admitted names per formation date (MIN_NAMES_PER_DATE, the convention
               PR-013 set) AND >= 24 rebalance dates in each of the primary and holdout windows
if not met:    the study reports the measurement and REFUSES a verdict for that cell, the way
               PR-012 refused rather than concluding from 181 trades
```

**24 rebalances is two years of 21-session periods** and is the floor at which a block bootstrap
with block length 6 has four independent blocks. At `horizon = 252` the holdout window is close to
that floor, and the cell will say so rather than quietly reporting a number.

## 9. What would refute this

**H1 is refuted** if no horizon's primary-window net interval excludes zero at 1x costs. That is a
real possibility and the exploratory figures point at it: the long-only arm at 126 sessions is
+4.805% **[−0.009, +10.125]** and misses by three decimals on 17 non-overlapping observations. The
overlapping construction lowers the variance of the estimate — it does not move the mean, and if
the mean is where the exploratory work put it, the long-only arm may clear zero by a hair or not at
all.

**And a result this study CANNOT produce:** it cannot validate `CARD-001`. `b.expectancy` and
`b.min_sample` are `measured_by: journal` (`criteria.yml` v1.1.0) and the journal holds one closed
trade. What it can do is give `exit.max_holding_period` a provenance better than `assumed:DR-012`,
and tell the owner whether the two-year clock should be started on a 20-session hold or a longer
one — which is the question that prompted it.

## 10. Amendments

### A-1 · 2026-09-06 · BEFORE THE RUN — the non-overlapping constraint was an owner rule, and the owner has lifted it

**No data has been seen.** The tool this study describes does not exist at the time of this
amendment, so `PREREG_TEMPLATE` rule 3 does not apply and the study is not downgraded.

**What changes is the provenance of §5's construction, not the construction.** §0 attributed the
non-overlapping windows to the studies that used them and presented overlapping portfolios as this
study's methodological proposal. The owner ruled on 2026-09-06, verbatim: *"my mistake, thay could
intersect"* — the constraint was theirs, and it is withdrawn.

**Why that matters enough to record.** A method an agent proposes and a method the owner rules are
different objects in this repository. Under the first, §5's construction is a claim this study has
to defend; under the second it is a ratified premise, and the seventeen-observation ceiling in every
prior result becomes a **known artefact of a withdrawn rule** rather than a limit of the data.

**What it does NOT change.** The rest of §5b stands unaltered and is still load-bearing: overlapping
sub-portfolios share holdings, so the moving-block bootstrap is required rather than optional, and
**overlapping windows still create no new information.** Ten years remain ten years. A result that
needs 2016–2026 to clear zero is a result about one decade, and §9 says so. Lifting the constraint
lowers the variance of the estimate; it does not lower the risk of being wrong about a decade.

**And the prior results are not retroactively repaired by it.** `EVIDENCE_SUMMARY` §§8a and 11 were
measured non-overlapping and stand as measured; this study is where the overlapping construction is
tested, and the 126-session long-short cell is the one that will say whether the ceiling was the
data or the estimator.

### A-2 · 2026-09-06 · BEFORE THE RUN — §5's formation was wrong, and finding out why is a result on its own

**No data has been seen.** Found while building the tool, before it ran.

**§5 said `formation: 252 sessions` and §2 said `rs.lookback = 126`. Those contradict, and the
252 was copied from `measure_momentum_horizon.py` rather than read from the registry.** The
ratified value is **126**, `status: owner`, `read_by: swingdesk.application.pipeline:_selection_rule`.

**Chasing that turned up a second and larger mismatch.** `rs.benchmark_form` is **`path`**, ruled by
the owner via `DR-030`, and the live pipeline implements it as
`decision_logic.ranking.ByMarketPathStrength` — *"share of sessions the name beat `rs.benchmark`"*.
Every exploratory measurement of this family instead ranked on
`measure_momentum_horizon._formation_return`, a **point-to-point return over 252 sessions**.

**Those are not the same signal and the repository already says so.** `ByMarketPathStrength`'s own
docstring: *"Measured at Spearman ~0.6 against a raw-return ranking, so it is a genuinely different
signal... It is not proposed; a pre-registration picks it or does not."* And `rs.benchmark_form`'s
registry note records that the point-to-point form *"is measured to be a lie about the card's own
name"*.

**So `EVIDENCE_SUMMARY` §§8, 8a and 11 do not measure the ratified selection rule.** They measure
252-session point-to-point momentum. The card ranks on 126-session path strength, and **no study has
ever measured what the card actually does.** That is not a defect in those results — each is correct
about what it computed — and it is exactly the `AGENTS.md` §17 granularity error this project keeps
paying for, found here before it was paid for again.

**What changes in this study:** the score is `ranking.ByMarketPathStrength` at `rs.lookback` = 126,
called through the live implementation rather than reimplemented, so the study and the system cannot
drift apart. §5's `formation: 252` is void.

**What that costs §3.** The numeric prediction was extrapolated from figures measured on the OTHER
signal, so its anchor is gone. The qualitative prediction stands unchanged and is what the decision
rule reads: under H1 at least one horizon ≥ 42 sessions has an interval strictly above zero; under
H0 none does. **A weaker prediction registered before the run is worth more than a precise one
borrowed from a different measurement**, and §6's thresholds were never expressed in those numbers.

**And it adds a reading this study did not set out to produce:** if the path form at 126 behaves
unlike the point-to-point form at 252, the difference is a fact about `DR-030`'s ruling that nothing
else in the repository has measured.

Any amendment after the run is appended, dated, and downgrades this study to exploratory
(`PREREG_TEMPLATE` rule 3).
