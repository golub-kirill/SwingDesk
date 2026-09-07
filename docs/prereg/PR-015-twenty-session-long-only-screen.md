# PREREG: at a twenty-session hold, does ANY long-only selection signal earn a net excess over `SPY` whose interval excludes zero and replicates out of sample?

```
id:            PR-015
date:          2026-09-07
author:        Claude, at the owner's instruction 2026-09-06 — "research a good strategy for
               14-20 days of holding, longs"
status:        reported   (2026-09-07 - results/PR-015-report.md)
verdict:       INCONCLUSIVE. The only arm whose interval excludes zero is LOWVOL_126, and
               it LOSES - so section 6's both-negative branch fires. The finding that is
               not the verdict: the four-position book's four cells disagree by up to 96.6
               points where the decile it selects from disagrees by 7.5
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

Held for twenty sessions in a **four-position long-only book** — the ratified
`risk.max_concurrent_positions` — does any of five selection signals earn an annualised net excess
over `rs.benchmark` whose bootstrap interval excludes zero on the primary window **and** excludes
zero on both holdouts without re-selection?

It can come out "no": if no arm's primary interval excludes zero, the family is rejected at this
horizon.

## 2. Hypothesis

**H1.** At least one of `REVERSAL_21`, `HIGH_52W`, `LOWVOL_126`, `MOM_252_21` and the ratified
`PATH_126`, traded as a four-position book at a twenty-session hold, produces an annualised net
excess over `SPY` that excludes zero on the primary window and on both holdouts.

**H0.** None does — a four-position twenty-session long-only book earns nothing separable from zero
on this universe, whatever it ranks on.

Concerns the BOOK as well as the signal, and A-2 is why: `risk.max_concurrent_positions` binds long
before the decile does, so a result here is about what this system can hold and not about a
portfolio of a hundred and thirty names.

Concerns `decision_logic.ranking` (the `PATH_126` arm calls the live `ByMarketPathStrength`; the
other four have no component and are implemented in the study tool, declared in §5) and
`trade_management.portfolio` (the cap).

## 3. Prediction, stated numerically before the run

**If H1 is true**, the winning arm shows an annualised net excess of at least **+8%** on the primary
window with a lower bound above zero, and lower bounds above zero on both holdouts.

**If H0 is true**, every arm's primary interval contains zero, and the point estimates sit in the
band `PR-014` measured for the incumbent long-only book: **−1.5% to +2%** annualised.

**THIS STUDY CANNOT RESOLVE A SMALL EDGE, AND THAT IS REGISTERED HERE RATHER THAN DISCOVERED
AFTERWARDS.** `PR-014`'s long-only cells returned bootstrap intervals about **±8 percentage points**
wide at this horizon on a book of ~260 names. **This book holds FOUR** (A-2), so its idiosyncratic
variance is far higher and its interval will be wider by an amount nobody can state in advance.
`PR-012` measured a four-position book and **refused a verdict for want of sample**.

**So §8 registers a POWER FLOOR rather than a prediction dressed as one.** If the selected arm's
primary interval is wider than **±25 percentage points**, the study reports the measurement and
declines to read a null as evidence of absence — the instrument would not have detected an edge
worth trading. That threshold is fixed now, before any number exists, and it is deliberately loose:
its job is to catch the case where the answer is "this cannot be measured on four positions", which
is a finding about the construction and not about the signal.

**A null result therefore refutes only a LARGE edge.** `PREREG_TEMPLATE` §3 asks whether the true
and false cases look different; on the capped book they do, but only well above 8%.

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
book:           at most FOUR concurrent positions - `risk.max_concurrent_positions`, value 4,
                status `owner` - equal-weighted, long only. See A-2: the decile is the
                ELIGIBILITY screen and the ratified cap picks who is taken
rebalance:      every 5 sessions = 20 / 4, OVERLAPPING. One slot frees each rebalance because the
                position opened 20 sessions earlier reaches the cap and closes; it is refilled
                with the highest-ranked eligible name NOT already held. Positions therefore
                overlap four deep, each held its full 20 sessions, and a slot stays EMPTY when no
                eligible name is available rather than being filled with something worse
eligible:       the top DECILE of the admitted cross-section under that arm's signal
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
diagnostic:     the whole eligible DECILE's return, equal-weighted, reported beside the capped
                book and NEVER read by section 6. It is what separates "the signal is weak" from
                "four positions is too few to express it", and that distinction is the first
                thing a reader will ask for
caps NOT applied, and why, because a cap left unmentioned reads as a cap enforced:
                `risk.max_open_risk` (4 R) constrains RISK rather than count, and pricing it needs
                a stop, a position size and an equity curve - none of which this study models.
                `risk.max_sector_risk` (2 R) needs a point-in-time sector and
                `data/classifications.duckdb` holds fourteen days of knowledge times; the module
                refuses to answer a 2016 question with today's classification and it is right to.
                `risk.correlation_threshold` (0.70) is computable from bars alone and is left out
                on purpose: it is a risk guard whose bite `correlation-cap-calibration-2026-08-23`
                already measured, and applying it here would confound a comparison BETWEEN signals
                with a guard that fires at different rates for each
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
                because the book overlaps FOUR deep BY CONSTRUCTION (A-2): consecutive 5-session
                returns share three of their four positions, so the dependence spans four
                rebalances and is a property of the design rather than an empirical guess. Six
                covers it with a margin. An i.i.d. resample would report an interval several
                times too narrow, which is the flattering direction
```

## 6. Decision rule

```
accept if:      the arm chosen by section 5a's selection rule has a net interval excluding zero
                on the primary window at 1x costs, a point estimate still positive at 3x, AND
                net intervals excluding zero on BOTH holdouts
reject if:      no arm's primary-window net interval excludes zero at 1x costs AND at least one
                arm's primary interval is inside the §8 power floor. A grid where NOTHING was
                measurable is not a refutation and must not be recorded as one
underpowered:   if the arm §5a selects has a primary interval wider than the §8 power floor, or
                if no arm qualifies and no arm's interval is inside the floor, the verdict is
                `inconclusive` and the report says the instrument, not the signal, is what
                failed. Fixed before any number exists
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

**What it costs.** The programme has spent **90** and the hurdle stands at **2.49 sd(SR)**. Five
more takes it to **95**, and the hurdle to **2.51**. Derive both with `tools/trial_budget.py`
(`AGENTS.md` §10.5); the figures are here because a pre-registration has to name its own price
before it runs, not because this page owns them.

**Those numbers were 81 and 2.46 when this file was first drafted on 2026-09-07, and they were
wrong.** Fourteen committed measurements carried no counting rule, and two of them were searches —
nine configurations the programme had tried and never counted. Corrected the same day, before this
study ran. That the marginal cost of five more is small is not an argument for spending freely — it
is `trial_budget.py`'s own finding that the expensive trials are the first ones — but it is the
honest accounting: this study is cheap because the programme has already paid for the expensive
part of the search.

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
power floor:    the SELECTED arm's primary-window net interval must be no wider than 50
                percentage points end to end (±25). Registered in §3 and fixed before any
                number exists. A wider interval means the instrument could not have detected an
                edge worth trading, and a null read off it would be evidence of nothing
if not met:     either failure - too few rebalances, or an interval wider than the floor - and
                the study reports the measurement and REFUSES to treat the window as evidence,
                the way PR-012 did. A window that cannot support an interval, or supports one
                too wide to inform, is a finding about the instrument and saying so is the point
```

Expected, from the calendar: with a 5-session step (A-2) there are roughly **500 rebalance dates**
over the store's span, about 270 before 2022 and 230 after. **The unit of observation is a
5-session return of the four-position book, not a trade** — which is why this study has a sample
where `PR-012`, counting trades against a minimum of 200, did not. The name split does not reduce
the number of rebalances, only the width of each cross-section they select from.

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

### A-1 · 2026-09-07 · BEFORE THE RUN — the fourth cell of the 2×2 exists, and it is reported

**No data has been seen.** Found while building the tool, before it ran.

§5a registers three windows over a 2×2 of time and names, which leaves a fourth cell: **formations
after 2021-12-31, names in half B.** The tool computes it, because refusing to compute a number that
falls out of the same loop is not restraint — it is a gap in the record that nobody could audit.

**It is written to the result as `diagnostic_both`, and §6 must never read it.** The decision
rule consults `primary`, `holdout_time` and `holdout_names` and nothing else. **This registers a
requirement on the tool**: it must carry a test that fails if the rule ever grows a branch reading
the fourth cell, because a study that selected on four windows while registering three would be
spending a holdout it never declared, and nothing else would notice.

**Why it is worth having.** If the selected arm passes both registered holdouts and fails the
fourth, that is a fact about the arm the report must carry — not a fourth chance to find one that
passes.

### A-2 · 2026-09-07 · BEFORE THE RUN — the book this system trades holds FOUR names, not a decile

**No data has been seen. Owner instruction, 2026-09-07**, and the registry had already said it.

§5 registered *"every 20 sessions, NON-OVERLAPPING… the top DECILE of the admitted cross-section"*.
That is not a book this system can hold. `risk.max_concurrent_positions` is **4**, `status: owner`,
read by `trade_management.portfolio:limits` — and `screen.relative_strength_rule`'s own registry
note has said the consequence since `DR-030`:

> *"At ~1,100 admitted names the top decile is ~110 and `risk.max_concurrent_positions` (4) binds
> LONG before it does, so this value picks who is ELIGIBLE and the ratified caps pick who is
> TAKEN."*

**The decile is the eligibility screen. The cap is the book.** A study measuring the whole decile
measures a portfolio of ~130 names that this system would never hold, and its result would be about
a construction rather than about a strategy.

**What replaces it.** At most four concurrent positions, each held its full 20 sessions, entered
**5 sessions apart** — `20 / 4`, so exactly one slot frees per rebalance and the positions overlap
four deep. The freed slot takes the highest-ranked eligible name **not already held**; if no
eligible name is available the slot stays **empty** rather than being filled with something worse.
Non-overlapping was never a property worth having here — it was an artefact of measuring a decile.

**What it costs, and it is not small.** A four-name book has far higher idiosyncratic variance than
a 260-name one, and `PR-012` refused a verdict on a four-position book for want of sample. §3 and §8
now register a **power floor** in response, fixed before any number exists. What this study has that
`PR-012` did not is a different unit of observation: **a 5-session book return, of which there are
about 500, rather than a completed trade, of which there were 181 against a minimum of 200.**

**And it changes the cost question rather than settling it.** `decile-persistence-2026-09-07`
measured 63.6% of the top DECILE surviving a 20-session gap. The top *one* name is a different
question and the answer is not derivable from that figure, so turnover is measured inside this study
from the book it actually holds — which is what `PR-014` amendment A-3 was about.

**"No good place" is a rule, and under this eligibility screen it will almost never fire.** The
owner's instruction was *"or non-overlapping if there is no good place"*, and the tool implements
it: a freed slot stays empty when no eligible name is unheld. But eligibility here is the **top
decile**, which is about 130 names against a book of four — so the slot is fillable at essentially
every rebalance, and the branch is defensive rather than expected. **It is not left as an
assumption**: the tool counts `rebalances_with_an_empty_slot` per arm and window, and the report
states the number even when it is zero. A quality bar that would make the branch bite — enter only
above some score — is a THRESHOLD, and `AGENTS.md` §8 says a threshold needs a pre-registration
rather than a guess made while building the tool. If the owner wants one, it is its own study.

**The 5-session entry grid is an APPROXIMATION and is declared as one.** The live pipeline scans
every session and would enter whenever a slot happened to be free, so real entries would stagger
unevenly rather than landing exactly 5 sessions apart. Even spacing is the standard
overlapping-portfolio construction (Jegadeesh & Titman 1993, and `PR-014` amendment A-1 by the
owner's ruling), it makes each of the four sub-books an equal share of the capital, and it is what
this study can compute: ranking a cross-section of ~1,300 names took twenty minutes at 313 dates,
and a daily grid is 2,500. **What it costs is realism about ENTRY TIMING, not about the cap** — the
book still holds at most four names for at most twenty sessions each. If an arm survives, the entry
grid is the first thing a follow-up should relax.

**The whole eligible decile's return is still computed**, reported beside the capped book and never
read by §6. It is what separates *"the signal is weak"* from *"four positions cannot express it"*.

### Anything after the run

Appended, dated, and it downgrades this study to exploratory (`PREREG_TEMPLATE` rule 3) — which is
exactly what happened to `PR-014` on 2026-09-07, and the reason that rule is quoted here rather
than assumed.
