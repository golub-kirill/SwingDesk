# PREREG: at a twenty-session hold, does ANY long-only selection signal earn a net excess over `SPY` whose interval excludes zero and replicates out of sample?

```
id:            PR-015
date:          2026-09-07
author:        Claude, at the owner's instruction 2026-09-06 — "research a good strategy for
               14-20 days of holding, longs"
status:        registered
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md` §§8, 8a, 10–14, `TODO.md` §5. The censuses
live in `HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-013` | does relative strength separate forward returns at all? | **`inconclusive`**, and worse than that reads: **all six GROSS intervals include zero** |
| `PR-014` | at what holding period does the RATIFIED rule earn a net excess? | **`inconclusive`**, corrected 2026-09-07 and downgraded to exploratory. No horizon from 20 to 252 sessions replicates on the holdout |
| `EVIDENCE_SUMMARY` §11 | does a decile SPREAD survive costs? | exploratory; the only construction with a net interval excluding zero, and it needs a short leg this system does not have |
| `EVIDENCE_SUMMARY` §14 | what does a rebalance actually cost? | measured; the cost model that suppressed short horizons was wrong |

**distinct because this changes the SIGNAL, and every study above holds the signal fixed.**
`PR-013`, `PR-014` and §§8, 8a, 11 all rank on one family — relative strength, in one form or
another — and ask about horizon, construction, universe or cost. **None has ever asked whether a
different signal works.** `PR-014` is the reason the question is now worth asking rather than
speculative: it established that the incumbent rule earns nothing that replicates at ANY holding
period between one month and a year, which removes horizon as the explanation and leaves the signal.

**And one prior result points at a specific candidate.** `README.md` records, citing Jegadeesh (1990)
and Lehmann (1990), that holds of a month or less sit inside the window where the literature
documents the **opposite** sign to momentum. Every measurement in this repository has ranked in the
momentum direction. The reversal arm below is that observation turned into a testable arm, and it
has never been run here.

## 1. Question

Held for twenty sessions, long-only, does any of five selection signals earn an annualised net
excess over `rs.benchmark` whose bootstrap interval excludes zero on the primary window **and**
excludes zero on both holdouts without re-selection?

It can come out "no": if no arm's primary interval excludes zero, the family is rejected at this
horizon.

## 2. Hypothesis

**H1.** At least one of `REVERSAL_21`, `HIGH_52W`, `LOWVOL_126`, `MOM_252_21` and the ratified
`PATH_126` produces a long-only top-decile book whose annualised net excess over `SPY` excludes zero
on the primary window and on both holdouts.

**H0.** None does — twenty-session long-only selection earns nothing separable from zero on this
universe, whatever it ranks on.

Concerns `decision_logic.ranking` (the `PATH_126` arm calls the live `ByMarketPathStrength`; the
other four have no component and are implemented in the study tool, declared in §5).

## 3. Prediction, stated numerically before the run

**If H1 is true**, the winning arm shows an annualised net excess of at least **+8%** on the primary
window with a lower bound above zero, and lower bounds above zero on both holdouts.

**If H0 is true**, every arm's primary interval contains zero, and the point estimates sit in the
band `PR-014` measured for the incumbent long-only book: **−1.5% to +2%** annualised.

**THIS STUDY CANNOT RESOLVE A SMALL EDGE, AND THAT IS REGISTERED HERE RATHER THAN DISCOVERED
AFTERWARDS.** `PR-014`'s long-only cells returned bootstrap intervals about **±8 percentage points**
wide at this horizon and sample. A true edge of 3% a year — which would be a good long-only
strategy — is invisible to this instrument. **So a null result refutes only a LARGE edge**, and the
study's honest ceiling is: it can find a big effect, and it can rule one out. `PREREG_TEMPLATE` §3
asks whether the true and false cases look different; they do, but only above roughly 8%.

## 4. Data

```
universe:      every instrument the store can price, admitted at each formation date by
               reference_data's LiquidityRule judged AT THAT DATE (tools/run_pr013.py
               _admitted_dates)
window:        the store's full span, to its knowledge horizon. The START IS DERIVED, not
               written here: the first formation date on which EACH HALF of the split carries
               at least 100 admitted names (section 8). It is recorded in the result rather
               than asserted now, because the 2026-09-06 backfill moved it and a date fixed
               from memory would be a guess dressed as a registration. PR-014's 2016-08-22 was
               measured on the pre-backfill store and on the WHOLE universe, so it is neither
               this study's population nor its threshold
snapshot:      the bar store's latest knowledge_time at run time, recorded in the result.
               The 2026-09-06 backfill applies: 72.1% of the admitted universe now carries a
               decade, against 20.3% before it
costs:         DR-005, 25 bps per side, ratified. TWO sides, charged on MEASURED net turnover
               between consecutive books - not on gross turnover, which is the error that
               withdrew PR-014's ACCEPT (its amendment A-3, EVIDENCE_SUMMARY section 14).
               Measured 2026-09-07 for the incumbent rule at this horizon: 37.2% of the book
               bought per rebalance, 2.35% a year
               Commission: DR-039 sets it to ZERO at this venue. Regulatory fees are ~0.9% of
               the slippage term and are EXCLUDED - a known bias, pessimistic for H1
survivorship:  ABSENT. The directory is today's, so a name that delisted is missing. For a
               LONG-ONLY book this biases the result UPWARD, and every arm is therefore an
               UPPER BOUND. This is the same caveat PR-014 carries and it is not smaller here
```

## 5. Method

```
horizon:        20 sessions, fixed. The ratified exit.max_holding_period (assumed:DR-012), the
                top of the owner's 14-20 band, and the value the system would actually trade
rebalance:      every 20 sessions, NON-OVERLAPPING. The book is rebuilt at each formation and
                held to the next
book:           the top DECILE of the admitted cross-section, equal-weighted, long only
arms:           five, one per signal. Every other choice is identical across them
signals:        PATH_126     ByMarketPathStrength, lookback 126 - the RATIFIED rule, called
                             through the live class (PR-014 amendment A-2). The control arm
                REVERSAL_21  minus the trailing 21-session close-to-close return
                HIGH_52W     close divided by the highest high of the trailing 252 sessions
                LOWVOL_126   minus the standard deviation of trailing 126 daily returns
                MOM_252_21   the return from t-252 to t-21 - the standard skip-a-month form,
                             which this repository has never run
                The four non-ratified signals have NO component and are implemented in the
                study tool. That is a reimplementation risk and it is declared: if one wins,
                the next step is a component and a card version, not a parameter change
band:           NONE, deliberately. A buy/hold band is the strongest cost mitigation in the
                literature (Novy-Marx & Velikov 2016) and measure_banding.py has already
                measured it here - but a band makes the holding period EMERGENT, and the
                holding period is the thing this study holds fixed at the owner's request.
                Registered as not-run, with the reason, rather than left unmentioned
benchmark:      SPY (rs.benchmark, assumed:DR-018). Excess is the book's return minus the
                benchmark's over the same 20 sessions
control:        the EQUAL-WEIGHTED admitted universe OF THE SAME HALF, so section 6's
                both-negative branch compares the book to the pool it actually selected from
                rather than to a different population. Not an arm and never selected
statistic:      annualised net excess = mean per-rebalance excess x 252/20, minus the annual
                cost computed from measured turnover
```

### 5a. The split, and what it buys

```
split:          TWO splits at once, over the SAME five arms. No extra configuration is
                evaluated: these are readings, not shots
                  PRIMARY    formations on or before 2021-12-31, names in half A
                  HOLDOUT-T  formations after 2021-12-31, names in half A   (a TIME holdout)
                  HOLDOUT-N  formations on or before 2021-12-31, names in half B (a NAME holdout)
names:          half A is every instrument whose id satisfies
                  `sha256(instrument_id.encode()).digest()[0] % 2 == 0`
                and half B the rest. Written out in full because "hash it" is not a
                registered choice: SHA-256 is stable across Python builds where the builtin
                `hash()` is not, and a split that moved between runs would not be a split.
                Fixed before the run and independent of any return
selection rule: the arm with the LARGEST primary-window net excess whose interval excludes
                zero at 1x costs. Then both holdouts are read WITHOUT re-selecting
split buys:     PR-014's holdout was a time split that turned out to be a population split as
                well, because 94% of the store held only two years of bars. The backfill fixed
                the population and left a second problem it cannot fix: EVERY time window in
                this store has now been spent by a prior study, so a time holdout is no longer
                unspent data. The NAME holdout is - no study here has ever split the universe -
                and it guards a different failure: a signal that works on a handful of names.
                Requiring BOTH is strictly harder than requiring either, and neither is free:
                the name split halves each cross-section, so a decile book holds about 130
                names rather than 260
perturbations:  WALKFORWARD_SPEC 4, numbers 3 and 4 - cost stress at 1x and 3x DR-005, run on
                EVERY arm and not only on the selected one
inference:      moving-block bootstrap over the rebalance-date series, block 6 rebalances,
                10,000 resamples, seed 20260907, percentile interval. Block 6 rather than 1
                because consecutive books share names - measured 2026-09-07, 63.6% of the top
                decile survives a 20-session rebalance - so an i.i.d. resample would report an
                interval too narrow, which is the flattering direction
```

## 6. Decision rule

```
accept if:      the arm chosen by section 5a's selection rule has a net interval excluding zero
                on the primary window at 1x costs, a point estimate still positive at 3x, AND
                net intervals excluding zero on BOTH holdouts
reject if:      no arm's primary-window net interval excludes zero at 1x costs
both negative:  if the selected arm's net excess AND the equal-weighted universe control are
                both below zero, the verdict is `inconclusive` regardless of which loses less.
                Comparing two losers on which loses less is not a finding
inconclusive:   everything else, including: the arm qualifies on the primary window and fails
                either holdout; more than one arm ties for the largest qualifying primary
                estimate (fail-closed - choosing between them after the run is not registered)
```

The rule is applied by the tool, not by a reader, and the tool prints the branch it took.

## 6a. Trials

**Five configurations**, declared before the run: one per signal. `tools/trial_budget.py` reads the
number from this study's `trials` field.

**Why five and not ten.** The band doubles the grid and is registered as not-run in §5, for a reason
that is about the question rather than about the budget. The 1x/3x cost stress is a restatement of
each arm and the three windows are readings of one fit, so neither multiplies the search.

**What it costs.** The programme has spent **81** and the hurdle stands at **2.46 sd(SR)**. Five more
takes it to **86**, and the hurdle to about **2.48**. That the marginal cost is small is not an
argument for spending freely — it is `trial_budget.py`'s own finding that the expensive trials are
the first ones — but it is the honest accounting: this study is cheap because the programme has
already paid for the expensive part of the search.

## 7. Stopping rule

The study ends when all five arms have been evaluated on all three windows. It does not stop early
on a favourable arm and does not continue on an unfavourable one. No arm is added after the run
begins; an arm that cannot be computed is REPORTED as not computed rather than silently dropped.

## 8. Sample

```
minimum:        24 rebalances in each window, the same minimum PR-014 §8 uses, and 100 names
                in EACH HALF's cross-section at every formation date (MIN_NAMES_PER_DATE,
                applied per half rather than to the whole). Applying it to the whole would let
                a half fall to fifty names and still pass, which is the granularity error
                AGENTS.md §17 names
if not met:     the study reports the measurement and REFUSES a verdict for that window, the
                way PR-012 did. A window below the minimum cannot support an interval and
                saying so is the finding
```

Expected, from the calendar: about 126 non-overlapping 20-session formations over the store's span,
roughly 65 before 2022 and 61 after. The name split does not reduce the number of formations, only
the width of each cross-section.

## 9. What would refute this

**H1 is refuted** if no arm's primary-window net interval excludes zero at 1x costs. That is a
concrete, reachable observation and `PR-013` and `PR-014` both produced its analogue.

**H1 is also damaged, without being refuted, if the winning arm is `PATH_126`** — the incumbent —
because `PR-014` has already measured that arm at this horizon and found nothing that replicates. An
arm that wins here having failed there would be evidence about the split rather than about the
signal, and the report must say so.

**What would NOT refute H1:** a small point estimate. §3 registers that this instrument cannot
resolve an edge below roughly 8% a year, so "no interval excluded zero" is compatible with a real
edge of 3% and the report may not claim otherwise.

## 10. Amendments

None. Any amendment after the run is appended, dated, and downgrades this study to exploratory
(`PREREG_TEMPLATE` rule 3) — which is exactly what happened to `PR-014` on 2026-09-07, and the
reason that rule is quoted here rather than assumed.
