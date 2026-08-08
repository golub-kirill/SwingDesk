# RULE SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** authored, measured against the tree

Master ТЗ §15. The Rule is the specification's central object — §16 through §20 all reference it —
and `SPEC_GAP_ANALYSIS.md` §4 ranked it first for exactly that reason.

**A rule is a formal function, not a written recommendation.** This document defines the *form* a
rule takes. The form is source-independent: individual rules are extracted from the course and
populate a rule registry against this schema.

A 276-line seed draft exists in commit `dee8f37` (`11_Rule_Specification.md`, Russian, from the
parallel documentation track). Its structure is sound and is kept. What is added here is the part
that draft could not do, because it was written without sight of this tree: **for each requirement of
the form, what already satisfies it, and what does not.** That reconciliation is §9, and it is the
reason this document is shorter than it looks — much of §15 is already law here under other names.

---

## 1. What the form exists to make inexpressible

Three specific failure modes, each taken from the TradAlert post-mortem rather than from general
principle:

| Failure | How the form forbids it |
|---|---|
| **the constant gate** — a rule whose verdict is invariant across all inputs | §4 requires a discriminating pair and a mutation check |
| **the silent `missing → value`** | §5's three-valued logic and a mandatory `missing_data_policy` |
| **the decorative output** — a rule that is computed and consumed by nothing | mandatory `consumed_by` and `effect` |

The first is not hypothetical. TradAlert's R:R gate was `if is_long: return True` and **passed seven
audits**, because it is a valid function with valid references. Prose review cannot catch it; only an
executable test on a pair of inputs can (`REQUIREMENTS.md` §2).

## 2. The eleven mandatory parts

Every rule carries:

1. a human-readable claim — `semantic_claim`
2. a machine expression — `expression`
3. inputs — `inputs`
4. preconditions — `preconditions`
5. an output and its meaning — `output`
6. temporal semantics — `evaluation`
7. a missing-data policy — `missing_data_policy`
8. a scope — `scope`
9. a downstream effect — `effect`, `consumed_by`
10. an evidence status — `expected_relationship.evidence_status`
11. tests — `tests`

**A object missing any of these is not a rule in this system** and may not hold a status above
`draft`.

## 3. The form

Identifiers follow **this tree's existing namespaces**, not the seed draft's. The seed invented
`DATA.PRICE.CLOSE.001` and `PARAMETER.EMA.PERIOD.001`; this repository already has two id schemes —
course components as `M18-T0280-v5.0` (`registry/course_index.yml`) and parameters as `atr.period`
(`registry/parameters.yml`). Adopting a third would be the §8 violation the specification itself
forbids, and it is the same mistake that produced two copies of the schema layer.

```yaml
rule:
  id: rule.trend.price_above_ma
  version: 1                       # ours, independent of the course's document version
  status: draft                    # draft | specified | active - COMPONENT_REGISTRY_SPEC 3
  title: Price above the long moving average

  semantic_claim: >
    Close above the long moving average MAY indicate positive medium-term structure.
    This is a claim about meaning, NOT a demonstrated edge. It carries no evidence
    until expected_relationship.evidence_status says so.

  scope:
    markets: [US, CA]              # never merged - AGENTS 3
    instrument_types: [stock, etf]
    timeframes: [1D]
    regimes: []                    # empty = unrestricted
    direction: null                # null = undirected

  inputs:
    - component: M18-T0280-v5.0    # must resolve in registry/course_index.yml
    - parameter: null              # the MA period is NOT yet a registry parameter - see below

  preconditions:
    minimum_history_bars: null     # unset; warm-up plus margin
    data_quality_requirements: []
    eligibility_rules: []

  expression:                      # the ONLY source of the verdict
    operator: gt
    left:  { component: M18-T0280-v5.0, field: close }
    right: { component: M18-T0280-v5.0, field: value }

  evaluation:
    evaluation_time: bar_close
    available_time_policy: after_bar_finalisation
    frequency: each_daily_bar
    persistence_policy: null
    confirmation_policy: null
    cooldown_policy: null

  output:
    type: boolean                  # see 4
    true_meaning: condition_confirmed
    false_meaning: condition_not_confirmed
    unknown_allowed: true          # three-valued logic is mandatory - see 6

  missing_data_policy:             # REQ-DATA-002. Substituting a value is forbidden.
    on_missing_input: unknown
    on_stale_input: unknown
    on_calculation_failure: unknown

  effect:
    effect_type: feature_contribution
    target: state.instrument.trend
    weight_parameter: null         # unset until calibrated - see 8

  consumed_by: []                  # mandatory and non-empty for a deciding rule
  vetoed_by: []
  conflicts_with: []
  depends_on: []

  expected_relationship:
    direction: positive
    evidence_status: hypothesis    # hypothesis by default, never fact

  failure_modes: []
  assumptions: []
  limitations: []

  tests:
    positive_cases: []
    negative_cases: []
    boundary_cases: []
    missing_data_cases: []
    stale_data_cases: []
    discriminating_pair: null      # REQ-VALIDATION-001 - mandatory for a verdict rule
```

The metadata block deliberately does **not** reference a JSON schema. The seed pointed at
`common_metadata.schema.json`, which was removed on 2026-08-04 because it duplicated
`src/swingdesk/contracts/` by hand (`SPEC_GAP_ANALYSIS.md` §5). The contracts are authoritative; a
rule schema should be generated from them, not written alongside them.

**Writing that example surfaced a real gap: the moving-average period is not a registry parameter.**
`registry/parameters.yml` has `atr.period` but nothing for the moving-average lengths — PR-005 pinned
50 and 200 as *study constants*, recorded in its own pre-registration, which is correct for a study
and insufficient for a rule. A rule cannot cite what the registry does not hold, so the first real
rule of this shape needs the parameter added first, `unset`, with `named_in` citing where the course
names the concept (`AGENTS.md` §7). This is the form doing its job before a single rule exists.

## 4. Output types and effect classes

**Output types.** `boolean` · `numeric` · `category` · `score_contribution` · `veto` · `warning` ·
`state_transition` · `event_emission` · `eligibility_result`.

Outputs without precise semantics are forbidden: no `signal = good`, no `trend = strong`, no
`setup = beautiful`. Every value carries a stated meaning. This is the same prohibition
`ALGORITHM_SPEC.md` enforces as banned vocabulary.

**Effect classes**, which may not be mixed:

| Class | Meaning |
|---|---|
| `hard_gate` | mandatory condition; unmet means the object does not advance |
| `veto` | independent cancellation, **regardless of any score** |
| `soft_factor` | changes a score, does not forbid the action |
| `warning` | informs about risk without changing the verdict |

Plus `feature_contribution`, `state_transition` and `event_emission` for contributing and emitting
rules.

**A `hard_gate` or `veto` rule must be capable of rejecting.** §5 is what guarantees it.

## 5. Tests, which are the core of the form

### 5.1 The discriminating pair

Every rule with a verdict — `boolean`, `veto`, `eligibility_result`, `hard_gate` — **must** exhibit a
pair of input sets on which its result differs:

```yaml
discriminating_pair:
  case_a:
    inputs:   { close: 105.0, ma: 100.0 }
    expected: true
  case_b:
    inputs:   { close:  95.0, ma: 100.0 }
    expected: false
```

If no such pair exists, the rule's verdict is invariant across all inputs, the rule is decoration,
and **it must not reach runtime.** A static check rejects a verdict rule without one.

### 5.2 The mutation invariant

At system level, forcibly inverting a rule's result **must** change at least one final verdict in the
test corpus. A rule whose inversion changes nothing is decoration and fails the build.

This is the check that would have caught `if is_long: return True` on its first run.

### 5.3 The remaining mandatory sets

`positive_cases` · `negative_cases` · `boundary_cases` (behaviour at equality, with strict versus
non-strict comparison fixed) · `missing_data_cases` (a missing input yields `unknown`, **never** a
default) · `stale_data_cases`.

## 6. Three-valued logic

A rule's result is `true`, `false`, or `unknown`.

**`unknown` must never become `true` or `false` automatically** (`REQ-DATA-002`). Its causes are
enumerable: missing data, insufficient history, stale data, an unresolved parameter, an unsupported
market, a calculation failure, or conflicting source values.

Propagation upward is declared explicitly. On a live path, a critical `unknown` yields `NO_TRADE`.

The form forbids the "safe" conversion `unknown → false`. In TradAlert that appeared as an indicator
defaulting to its mean and a risk score defaulting to its midpoint — both of which removed the
safety catch at precisely the moment it was needed. This is the same distinction `AGENTS.md` and
`HANDOFF.md` §7 state as a standing habit: **`unavailable` is not `fail`.** A gap in the *system* and
a fact about the *trade* are different claims, and collapsing them is the most damaging error this
product can make.

## 7. Correlated factors and double counting

`price above MA20`, `price above MA50`, `MA20 slope`, `MA50 slope` and `MACD above zero` may all be
measuring one trend factor. The form records the risk; the mechanisms belong to the strategy and
ranking specifications:

- **signal groups** — rules measuring one factor are grouped
- **correlation warnings** — raised when a correlated rule is added
- **contribution caps** — a group's total contribution is bounded
- **ablation** — marginal contribution is checked separately
- **no mechanical summation** of weights without calibration

**The gap bar is the worked example.** One number — the gap — feeds ATR, RSI, MACD and any
volatility-normalised measure at once, so formally independent rules reading those indicators have
correlation near 1 on that bar. This is recorded as a `failure_mode` on every rule reading them.

This tree already treats gaps as a first-class hazard on the execution side: `ExitReason.STOP_GAP`
is distinct from `STOP`, and a gap through a stop records the **actual** loss rather than `−1R`
(`EXECUTION_MODEL.md` §3). The indicator-side correlation has no equivalent handling and no
quarantine mechanism — see §10.

## 8. Weights are `unset` until calibrated

A rule's contribution weight is a **parameter in the registry**, never a number in the rule body.
Until calibrated it is `unset`, and a rule whose critical weight is unset does not reach runtime.

Forbidden: `Trend +18 / Volume +12 / Momentum +15` without a calibration method, out-of-sample
validation, correlation control, sensitivity analysis, a versioned parameter set and ablation.

This is already the strongest-held law in this repository, and it is stated more strictly here than
the ТЗ asks: `registry/parameters.yml` has **no `default:` field, deliberately**, and 83 of its 96
parameters are `unset`. An unset parameter makes its component refuse.

## 9. What this tree already satisfies

The reconciliation. Measured 2026-08-05, and the reason this document is a specification of a gap
rather than of a greenfield.

| Form requirement | Already here as | Verdict |
|---|---|---|
| three-valued output, no silent default | `ItemState.UNAVAILABLE` (checklists), `Observation.value: Decimal \| None`, `REQ-DATA-002` **met** | **substance met, contract not unified** — two shapes, no single named type |
| `missing_data_policy` | components refuse rather than default (`INVARIANTS.md` #9); ATR emits `None` before warm-up | met |
| `veto` / `hard_gate` non-compensatory | `AGENTS.md` §3 non-negotiable: *"no score, and no quantity of weak positives, clears one"* | met as law, **unmodelled as a field** |
| coded refusal rather than a guess | `CODES.md` — 12 skip codes with actions, 12 error codes with severity; `FAIL_CLOSED_POLICY.md` | met |
| weights `unset` before calibration | the registry's whole discipline; no `default:` field | met, and stricter than asked |
| `evidence_status` defaults to hypothesis | the provenance ladder `unset` / `assumed` / `owner` / `validated`; only `regime.classifier_rule` is `validated`, from PR-002 | met |
| `validated` only with an evidence record | `verify_parameters.py` requires `validated:<evidence-id>`; a decision record may never yield it | met and **gated** |
| `consumed_by` / output provenance | `REQ-OUTPUT-001`; `ParameterUse` travels with every computed value | largely met |
| `scope.markets` | US and CA are never merged — separate calendars, indexes, currencies | met |
| versioning and behavioural freeze | `COMPONENT_REGISTRY_SPEC.md` §6, 25 golden vectors, gate 7b | met |
| **discriminating pair** | `REQ-VALIDATION-001`. Gate 12 checks a committed criterion's *inputs* are set — not that a verdict ever changes | **NOT met** |
| **mutation invariant** | nothing | **NOT met** |
| **the Rule object itself** | no rule registry, no expression tree | **absent** |
| **`vetoed_by` on a verdict** | nothing records which rule cancelled a decision | **absent** |
| signal groups, correlation caps, ablation | nothing | **absent** |

**The headline:** eleven of the form's requirements are already satisfied here, several by mechanisms
stricter than the specification asks for. What is genuinely missing is the Rule object as a
first-class thing — the expression tree, the registry, the veto provenance — and the two halves of
`REQ-VALIDATION-001` that make a verdict rule prove it can discriminate.

## 10. Static form invariants

Checkable without running a rule, and the natural content of a future gate:

1. a verdict rule has a discriminating pair, or it is rejected (`REQ-VALIDATION-001`)
2. `missing_data_policy` never substitutes a value for `unknown` (`REQ-DATA-002`)
3. `consumed_by` is non-empty for a deciding rule (`REQ-OUTPUT-001`)
4. `scope` is set
5. `effect_type` belongs to exactly one class; mixing is forbidden
6. `evidence_status` is `hypothesis` unless an evidence record is referenced
7. an unset critical weight blocks the rule from runtime

## 11. Open items

- [ ] **No rule registry exists.** `registry/` holds parameters, components, checklists, criteria and
      the course index; there is no `rules.yml`. Until there is, this document specifies a form with
      no population — which is the correct order, and worth stating so it is not mistaken for
      completeness.
- [ ] **The expression tree is unspecified beyond the example.** Operator set, nesting, type rules
      and how an expression references a component field all need fixing before a rule can be written.
- [ ] **`vetoed_by` needs a carrier.** Recording which rule cancelled a decision is a journal and
      decision-record concern as much as a rule-form one.
- [ ] **The three-valued contract is not unified.** `ItemState.UNAVAILABLE` and
      `Observation.value: None` express the same discipline in two shapes. A named type would make
      §6 checkable rather than conventional.
- [ ] **Gap-bar correlation has no mechanism.** §7 names the hazard; no quarantine, property test or
      grouping exists on the indicator side.
- [ ] **`UDR-004` blocks `scope.regimes`.** Which regime ontology is canonical — the ТЗ's eight or
      the course's eleven — is an open owner decision, and a rule scoped to a regime cannot name one
      until it is taken.
