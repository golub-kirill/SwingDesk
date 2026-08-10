# EXPECTATION MODEL

**Status:** drafting · **Tier:** 5 (validation) · **Content:** authored, audited against the tree

Master ТЗ v1.0 §23, and after the top four it is first of the five remaining in
`SPEC_GAP_ANALYSIS.md` §4. The ТЗ's complaint is precise: *no Expectation object, no
estimate/definition split.*

**Why tier 5 rather than tier 2.** `STATISTICS_SPEC.md` already holds the *definitions* — expectancy,
profit factor, MFE capture, transcribed from Appendix D. What is missing is the object that carries
an **estimate** of one of those quantities: a number measured from a sample, in a window, for a
cohort, with a staleness. Every rule about such a number is a validation-programme rule, so it
belongs beside the programme that produces them.

---

## 1. The split, and why it is not pedantry

| | Definition | Estimate |
|---|---|---|
| What it is | `WinRate×AvgWin − LossRate×AvgLoss` | `+0.0279R` |
| Where it comes from | the course, transcribed | a sample, measured |
| Can it be wrong? | it can be the *wrong definition*; it cannot be inaccurate | it can be accurate, stale, or drawn from a sample too small to mean anything |
| What it needs | a version | a version **and** a sample, a window, a cohort, a method and a status |
| Where it lives today | `STATISTICS_SPEC.md` | **nowhere addressable** — §2 |

Collapsing them produces a specific failure: a number quoted with the authority of a formula. *"The
expectancy is +0.028R"* reads like arithmetic and is in fact an estimate from 2,629 trades, in one
window, on survivorship-incomplete data, before an assumed cost model. Every one of those
qualifications changes what the number licenses, and none of them is in the sentence.

## 2. What the tree has, and the gap in one line

| Kind of number | Provenance carrier | Status |
|---|---|---|
| A parameter someone chose | `ParameterUse` — id, value, provenance, `is_assumed` | **exists**, travels with every computed value |
| A derived observation | `ObservationSeries` — component, version, parameters, validation status | **exists** |
| A validation claim | `EvidenceRecord` — sample, window, survivorship, window ceiling, PIT coverage | **exists**, three disclosures required |
| **An estimate a decision would consume** | — | **absent** |

**So the tree carries provenance for the numbers a human chose and none for the numbers it
measured.** Aggregate results live in `docs/prereg/results/*.json` and in the prose of three reports.
Nothing addresses them, nothing versions them, and no runtime object could cite one if it wanted to.

That gap is exactly what `REQ-OUTPUT-001` presupposes. The requirement says every numeric value in a
decision output must carry its source identifier — *"estimate version, cohort key, or model
reference"*. Three phrases, and all three name parts of an object that does not exist. The
requirement is marked **largely met** in `REQUIREMENTS.md` on the strength of `ParameterUse`, and
that assessment is right about parameters and silent about estimates, because there are none to
display yet.

`EvidenceRecord` is the near miss, and the difference is worth being exact about: it records **what a
study claimed about a component's validation status**. An Expectation records **what a decision may
assume about an outcome**. The first is about the past of a rule; the second is an input to a future
trade. They share most fields and are not the same object, and building the second out of the first
would put a validation-status ladder on a number that needs a staleness clock instead.

## 3. The record

```yaml
- expectation_id: exp-2026-08-08-breakout-ungated-001
  quantity: expectancy               # a name from STATISTICS_SPEC, never a new formula here
  definition_ref: STATISTICS_SPEC#expectancy
  definition_version: 1

  estimate:
    value: "+0.0279"
    unit: R per trade
    interval: { method: permutation, low: "-0.0939", high: "+0.0916", level: 0.90 }

  cohort:                            # §4 - the key is the course's, not ours
    strategy: breakout
    strategy_version: 1
    regime: null                     # null = pooled across, and pooled is a claim of its own
    country: US
    sector: null
    setup: null
    entry_type: next_open
    exit_type: protective_or_time

  sample:
    trades: 2629
    window_start: 2016-08-01
    window_end: 2026-07-31
    holdout_from: 2023-07-28

  method:
    run_id: null                     # the run whose manifest pins code, config and snapshot
    prereg_id: PR-005
    evidence_id: null                # the EvidenceRecord this was computed alongside
    cost_model: assumed:DR-004       # every R here is net, at 1x - EXECUTION_MODEL 6
    stress: { multiplier: 3, value: "-0.123" }

  qualifications:                    # inherited from the evidence, never dropped in transit
    survivorship: absent
    point_in_time_from: null
    exploratory: false

  validity:
    as_of: 2026-08-02
    stale_after: null                # UNSET - stats.rolling_window has no value; see 6
  status: MEASURED                   # §7
```

Nothing here is a new number. Every field is either already recorded somewhere in this tree or
explicitly `null` because the thing it names does not exist yet — which is the point of writing the
shape before the first estimate is published.

## 4. The cohort key is already specified

This is the part the course settles, so it is not authored. `STATISTICS_SPEC.md` §4 makes six
breakdowns mandatory (M69) and Appendix H adds the weekly-review grouping; their union is the
mandatory `GROUP BY` set:

```
strategy · version · regime · country · sector · setup · weekday · entry type · exit type
```

**That set is the cohort key.** An expectation is an estimate *for a cohort*, and the course already
says which axes a result must be separable along. Two consequences:

1. **A pooled estimate is a claim, not a default.** `regime: null` above says "pooled across
   regimes", and PR-002 is the study showing that pooling across regimes can hide a real difference.
   A null axis must be legible as pooling rather than as absence.
2. **`country` is never pooled.** USA and Canada are separate calendars, currencies and indexes, and
   merging them is a non-negotiable in `AGENTS.md` §3.

## 5. Three sample floors, three different jobs

They are easy to conflate and they govern different refusals. Stated once, here:

| Threshold | Value | Governs |
|---|---|---|
| `validation.backtest_min_trades` | 200 primary / 60 holdout, per arm (`DR-007`) | whether a **backtest** may produce a verdict |
| `b.min_sample` | 100 closed trades, ratified | whether a **strategy card** may be judged at all |
| `stats.min_sample_for_verdict` | **`unset`** | whether a **statistic** may be displayed with a verdict rather than as a bare count |

The third is the one an Expectation needs and it has no value, so the honest behaviour is the one
`VALIDATION_PROGRAM.md` §3 already states: **report the measurement and refuse the verdict.** An
expectation below the floor is publishable as a number with its `n`; it is not publishable as an
expectation a decision may lean on.

## 6. Staleness, and the clock that does not exist

An estimate has a shelf life. A parameter does not, which is why this object cannot be modelled on
`ParameterUse`.

M69 requires a **rolling window** for expectancy and never quantifies it; `stats.rolling_window` is
`unset`. So `stale_after` above is null, and until it has a value **an expectation carries an
as-of date and no expiry**. That is not a design choice, it is a disclosed gap, and it is the
cheapest of the open items in §10 because the course already demands the field.

Two rules that hold regardless of the number:

1. **An expectation older than its source data is stale by construction.** If the underlying study's
   window ends before the current session, say so; a 2023 estimate quoted in 2026 is not wrong, it is
   old, and the reader must be able to tell.
2. **A re-measurement is a new expectation, not an edit.** Same discipline as every other record here
   (`AUDIT_AND_IMMUTABILITY.md`); the previous estimate stays addressable, because drift is the
   difference between two of them (§8).

## 7. Status — what an expectation may be used for

Deliberately **not** the nine validation statuses. Those describe a rule's standing; these describe
an estimate's usability:

| Status | Means | May be used to |
|---|---|---|
| `HYPOTHETICAL` | assumed or asserted, not measured | nothing. Display only, labelled |
| `MEASURED` | computed from a sample below the floor | display with its `n`; no verdict |
| `SUPPORTED` | above the floor, from a pre-registered study | inform ranking and reporting |
| `FORWARD_CONFIRMED` | reproduced on the real schedule (`PAPER`) | the above, plus go-live evidence |
| `RETIRED` | superseded, or its cohort no longer exists | nothing; kept for the audit trail |

**Every estimate this project currently owns is `MEASURED` or `SUPPORTED` at best**, and the base
strategy's is negative under stress. Nothing is `FORWARD_CONFIRMED`, because no forward test has run.

**What an expectation may never do**, and this is the load-bearing clause: it may not size a
position, clear a gate, or override a refusal. Sizing is `RISK_SPEC.md`'s ordering law — invalidation
to stop to risk to shares — and an expectancy estimate appears nowhere in it. A gate is
non-compensatory (`FAIL_CLOSED_POLICY.md` §3) and no score, including a favourable expectation,
clears one. An expectation informs *which* of several admissible candidates to prefer (§31's
territory) and never *whether* a candidate is admissible.

## 8. Drift is the difference between two expectations

ТЗ §45 (drift monitoring) is ABSENT and ranked below this one for a structural reason: **drift is
measured against an expectation, so there is nothing to monitor until this object exists.** Realised
outcomes drifting from a stored estimate is the whole of it, and both terms have to be addressable.

Same for §44 (learning). A promotion path needs a before and an after, and those are two
expectations for one cohort at two as-of dates.

## 9. Invariants that can be checked

| Check | Cost |
|---|---|
| every expectation names a `definition_ref` that resolves to a quantity in `STATISTICS_SPEC.md` | hours |
| `SUPPORTED` or better requires a `prereg_id` — an exploratory estimate cannot be leaned on | hours |
| the qualifications of the evidence it came from are present and unmodified | hours |
| no expectation is referenced by the sizing path | static check, minutes — and it passes vacuously today, which is worth saying out loud |
| a cohort's axes are all from §4's set; an invented axis is rejected | hours |

The fourth row is the one to wire first *and* the one that proves nothing today. That combination is
why `CI_POLICY.md` §7 leaves gate 10 unwired: a green check that asserts nothing teaches the operator
to trust it. It becomes real the day an expectation exists.

> **Merged 2026-08-09.** EXPECTATION_SPEC covered the same ТЗ §23 from another branch, written
> without sight of this one. Both made the same Definition/Estimate split; §9a–§9c below are what it
> had and this did not — the mandatory baseline, the commensurability rule a ratified kill criterion
> turns out to need, and the three legal sources of probability. `RECONCILIATION_PLAN.md` §6 records
> why this document was the base: seven documents cite it, three cited the other.

## 9a. A baseline is mandatory

**Without a baseline, no estimate may claim that anything adds edge.** An estimate with no baseline
is a description of a sample, not evidence about a strategy.

The permitted baselines, in rough order of strength:

| Baseline | Answers |
|---|---|
| the same strategy without factor X | does this factor contribute anything? |
| matched cohort | is the effect the instruments, or the rule? |
| random eligible entry | does the selection beat drawing from the same universe? |
| eligible-universe return | does trading beat holding what was eligible? |
| previous strategy version | is this change an improvement? |
| simpler deterministic benchmark | is the complexity earning its place? |

This tree already does it, without having named the object. PR-005's `NONE` arm — the trigger with no
trend gate — is a *strategy without factor X* baseline, and its pre-registration says why: comparing
four filters only to each other can rank them without establishing that any beats not filtering at
all. PR-002 compared against random partitions of the same trades. **Both chose correctly and
neither recorded which kind of baseline it was**, which is what this section fixes.

## 9b. Commensurability — the rule that makes a comparison legal

An estimate and its baseline must be expressed in the **same unit, over the same horizon, on the
same population, under the same cost model.** A comparison violating any of the four is void.

This is not pedantry. `registry/criteria.yml` ratifies `k.strategy_rejected`, whose trigger is *"the
expectancy CI lies entirely below the benchmark"* — and `b.benchmark_relative` defines the benchmark
as buy-and-hold on the same universe. **Mean R per trade and a buy-and-hold return are not
commensurable.** R has no horizon; buy-and-hold has nothing else. `PR-007` §6 records the same
problem from the study side.

So a ratified kill criterion cannot currently be evaluated, and the fix belongs here:

> **Where a Definition names a baseline in different units from its outcome measure, the Definition
> must state the conversion, or the pair is not a legal comparison.**

For a per-trade R expectancy against a buy-and-hold return, the conversion requires a horizon and an
exposure assumption — how many such trades over what period, at what fraction of capital. Those are
portfolio quantities, and `COVERAGE_AUDIT.md` records the portfolio layer as absent with all five
`risk.*` caps `unset`. **The comparison is therefore not merely unspecified but unavailable**, and
`k.strategy_rejected` should be read as inert until it is.

**It is now inert for two independent reasons.** `criteria.yml` v1.1.0 (2026-08-08) settles that
Track B evaluates on **journalled trades only**, so no backtest can fire the criterion regardless of
whether the comparison is legal. Both blockers must clear before it can ever trigger: real trades
must exist, *and* the units must be made commensurable.

## 9c. Probability has exactly three legal sources

Restating `AI_AUTHORITY_MODEL.md` §5 in the domain, because the constraint is not about AI:

A probability may come only from **a validated expectation estimate, a calibrated statistical model,
or a matched historical cohort.** Nothing else may be rendered as one — not a setup score, not a
component's confidence, not a count of satisfied conditions, and not a model's own stated certainty.

**This system currently has no legal source of probability.** One parameter is `validated`, no
expectation estimate exists, and no calibrated model exists. Any probability displayed today would be
manufactured, and the honest output is a refusal.

## 10. Open items

- [ ] **`stats.rolling_window` is `unset`** (§6), and it is required by M69 rather than optional.
      Until it has a value no expectation can expire.
- [ ] **`stats.min_sample_for_verdict` is `unset`** (§5). `DR-007` set fifteen `validation.*`
      thresholds and deliberately did not touch the `stats.*` family; this is the one that most
      obviously belongs with them, and it wants its own record.
- [ ] **Where an expectation is stored.** The study JSONs already hold the numbers; a `registry/`
      file would make them addressable, and a fifth registry is not obviously right. Decide with the
      transitions question in `TRANSITION_SPEC.md` §11 — both are asking whether this project wants
      one more table or one more projection.
- [ ] **Whether `FORWARD_CONFIRMED` needs a second sample floor.** `validation.forward_test_min_trades`
      is 20 (`DR-007`) and that is a *process* threshold; confirming an expectation is a statistical
      claim and 20 trades will not support one. Likely a separate value, and it should be set before
      a forward test starts rather than after it reports.
