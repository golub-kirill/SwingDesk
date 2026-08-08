# EXPECTATION SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** authored, reconciled against the studies

Master ТЗ §22 and §23. `SPEC_GAP_ANALYSIS.md` recorded §23 as **ABSENT** and ranked it second of the
remaining gaps; `COVERAGE_AUDIT.md` licensed a document for it, with the instruction to try
extending `STATISTICS_SPEC.md` first.

**It does not graft.** `STATISTICS_SPEC.md` is a transcription document — fourteen verbatim quotes
from M69 and Appendix D, specifying how a metric is computed and reported. An Expectation is not a
metric. It is a **conditional claim** that metrics estimate, and it is authored throughout. Putting a
large authored object inside a verbatim-checked document blurs the boundary gate 2 exists to hold,
and this tree already gives each domain object its own specification — Rule, Event, Regime, Exit.
Expectation follows that pattern.

---

## 1. The split that the whole document exists to make

**An Expectation Definition and an Expectation Estimate are different objects with different
lifetimes, and conflating them is how a measurement acquires authority it never earned.**

| | Definition | Estimate |
|---|---|---|
| what it is | a conditional claim, stated before any data | the result of one validation run |
| when it is fixed | before the run — it is part of the pre-registration | after the run |
| lifetime | stable across runs; changing it creates a new version | superseded by the next run |
| what it may not do | reference a result | change the conditions it was measured under |

The failure this prevents is specific and this project has already brushed against it. PR-005
reported the base strategy at 1× and 3× costs. When `DR-005` measured slippage, the question
"what does the strategy expect?" turned out to have no fixed answer — because no Definition existed
saying *under which cost model* the expectation was claimed. The estimate moved, and nothing recorded
what it was an estimate **of**.

## 2. The Definition

Fixed before the run, and carried in the pre-registration:

```yaml
expectation:
  id: expectation.breakout.base
  version: 1

  conditions:                 # what must be true for this expectation to apply
    universe: DR-003 liquidity rule
    regime: null              # null = unrestricted; a regime id restricts it
    markets: [US, CA]
    setup: 20-session breakout
  strategy_ref: null          # the strategy card and version this belongs to
  cohort: null                # the population the claim is about, if narrower than the universe

  outcome:                    # WHAT is being predicted - not "does it work"
    measure: mean R per trade
    net_of: [commission, slippage]
    cost_model_ref: DR-005    # WITHOUT this the claim has no fixed meaning
  horizon:
    holding_limit: 20 sessions
    exit_policy_ref: null

  baseline_ref: null          # mandatory - see 4
  intended_use: >
    what a reader is licensed to conclude, and what they are not
  evidence_status: hypothesis # hypothesis until an estimate with a baseline says otherwise
```

**`cost_model_ref` is not a detail.** It is the field whose absence made PR-005's headline number
ambiguous for three days. An outcome measured net of costs has no meaning without naming which cost
model, and this tree's cost model changed by a factor of five on 2026-08-05.

## 3. The Estimate

The result of one run against one Definition. Never edited; a new run creates a new estimate.

```yaml
estimate:
  expectation_ref: expectation.breakout.base
  expectation_version: 1
  run_manifest_ref: null      # commit, config hash, snapshot id, component versions
  prereg_ref: null            # absent = exploratory, and it says so

  sample:
    trades: null
    effective_sample_size: null   # NOT the trade count - see below
    period: null

  result:
    mean: null
    median: null
    quantiles: {}
    probability_positive: null
    confidence_interval: null
    mae: null
    mfe: null
    holding_period: null

  breakdowns: {}              # the axes STATISTICS_SPEC 4 requires
  calibration_error: null     # null until a predictive model exists
  limitations: []             # survivorship, window ceiling, PIT coverage - mandatory
```

**Effective sample size, not trade count.** Overlapping trades, correlated signals and one market
regime dominating a window all mean *n* trades carry fewer than *n* independent observations.
Reporting the raw count where the effective count is smaller overstates precision, and it is the
easiest number in this system to quote innocently. Where the effective size cannot be computed, it
is reported as unknown — never silently replaced by the raw count.

## 4. A baseline is mandatory

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

## 5. Commensurability — the rule that makes a comparison legal

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

## 6. Probability has exactly three legal sources

Restating `AI_AUTHORITY_MODEL.md` §5 in the domain, because the constraint is not about AI:

A probability may come only from **a validated expectation estimate, a calibrated statistical model,
or a matched historical cohort.** Nothing else may be rendered as one — not a setup score, not a
component's confidence, not a count of satisfied conditions, and not a model's own stated certainty.

**This system currently has no legal source of probability.** One parameter is `validated`, no
expectation estimate exists, and no calibrated model exists. Any probability displayed today would be
manufactured, and the honest output is a refusal.

## 7. What this tree already has

| §22 requirement | Already here as | Verdict |
|---|---|---|
| metric list for an estimate | `STATISTICS_SPEC.md` §3 — the fifteen M69 metrics | **met** |
| breakdown axes | `STATISTICS_SPEC.md` §4 | **met** |
| net-of-costs rule | `STATISTICS_SPEC.md` §5, verbatim from M69 | **met, and binding** |
| run manifest for reproducibility | `DETERMINISM_SPEC.md`, gate 9 | **met** |
| evidence artefacts | `EVIDENCE_RECORD_SPEC.md`, three reported studies | **met** |
| sample-size discipline | `stats.min_sample_for_verdict` (`unset`), `b.min_sample` (100, ratified) | **partially** — the parameter is unset, so the system reports the count and refuses the verdict |
| baselines in practice | PR-002 and PR-005 both used one | **met in practice, unnamed** |
| the Definition object | — | **absent — this document** |
| definition/estimate split | — | **absent — this document** |
| effective sample size | — | **absent**; no study reports one |
| commensurability rule | — | **absent**, and a ratified criterion depends on it (§5) |

## 8. Open items

- [ ] **No expectation has been defined for any strategy.** This specifies the form; the population
      is separate work and belongs with the strategy card.
- [ ] **`stats.min_sample_for_verdict` is `unset`.** Until it is set, every estimate reports its
      count and refuses a verdict, which is the design working rather than a gap.
- [ ] **Effective sample size has no method here.** Overlapping-trade correction is a choice
      (block bootstrap, cluster-robust, trade-level de-overlapping) and it needs a decision record.
- [ ] **`k.strategy_rejected` is inert** until §5's conversion exists, which needs the portfolio
      layer. Recorded in `COVERAGE_AUDIT.md` and `PR-007` §6 as well, so it cannot be missed from
      any of the three directions.
