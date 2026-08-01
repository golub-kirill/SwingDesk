# LIFECYCLE AND LAYERS

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim`

<!-- verbatim-sources: Course_Production_Rules_v3.8.md, Module_33_Skrinery_v5.0.pdf -->

**Source of truth:** `C:\Users\User\Desktop\swing-trading setup\Course_Production_Rules_v3.8.md`,
§3.6 *Decision-engine and methodology architecture* and §3.8 *Component reuse, strategy
independence, and traceability*. Confirmed present in every module PDF as the `REQUIRED TRACE`
block and the per-topic `STAGE` / `LAYER` metadata strip.

This document is the architecture. `docs/06-engineering/ARCHITECTURE.md` maps bounded contexts onto
it; it does not invent a second model.

---

## 1. The lifecycle

Every operational topic in the course declares where it sits in one common sequence:

```
Context → Candidate → Setup → Trigger → Entry → Risk → Management → Exit → Review → Validation
```

Verbatim rule: *"Any operational topic that cannot be located in the common lifecycle, assigned to a
layer, or distinguished from a trading decision is a production defect."*

Stage populations in the registry (`registry/course_index.yml`, all 1379 topics):

| Stage | Topics | Stage | Topics |
|---|---|---|---|
| `Setup` | 398 | `Entry` | 105 |
| `Context` | 236 | `Validation` | 82 |
| `Risk` | 127 | `Candidate` | 74 |
| `Review` | 124 | `Trigger` | 74 |
| `Exit` | 122 | `Management` | 37 |

`Stage` is a required field on every component. It is not decoration: it determines when in a run a
component may be evaluated, and a component evaluated out of stage order is a defect.

## 2. The four layers

Verbatim from §3.6, condensed to the normative clauses only.

### Layer 1 — Source Facts (107 topics)

> "Direct market observations and externally verified records, such as OHLCV, quotes, corporate
> actions, earnings dates, filings, classifications, and broker-provided borrow status."

> "A source fact is not assumed immutable. It records provider, field definition, instrument
> identity, session, timezone, currency, adjustment policy, as-of time, retrieval time, and revision
> status wherever those properties affect interpretation."

> "Conflicting providers, later corrections, back-adjustments, and missing or stale values remain
> visible. They are not silently reconciled into false certainty."

**Binding on this system:** the ten recorded properties are the mandatory column set for
`POINT_IN_TIME_SPEC.md`. "Not silently reconciled" forbids a fallback that quietly substitutes one
provider for another — a conflict is a `DATA` skip, not a repair.

### Layer 2 — Derived Observations (491 topics)

> "Deterministic calculations or classifications derived from source facts, such as ATR, RSI,
> relative strength, market regime, swing structure, volume contraction, or distance from an anchored
> VWAP."

> "Every derived observation defines inputs, formula or algorithm, parameters, units, timeframe,
> sampling and session rules, warm-up, missing-data behavior, time alignment, output range, and
> version."

> "A classification such as "healthy trend" is an output of a stated rule, not a raw fact and not
> proof of future direction."

**Binding:** that eleven-field list is exactly the required record shape in `ALGORITHM_SPEC.md`.
`Deterministic` is load-bearing — see `DETERMINISM_SPEC.md`.

### Layer 3 — Decision Logic (416 topics)

> "Explicit logical conditions that combine source facts and derived observations into a candidate,
> permission, rejection, or other decision."

> "Conditions use visible gates, branches, thresholds, precedence, and fail-closed behavior. Terms
> such as "smart", "strong", "quality", or "confirmed" are prohibited unless reduced to observable
> rules or explicitly reserved for documented human review."

> "Indicators, chart patterns, and derived observations are informational components. None is a
> standalone strategy or proof of edge."

> "Different strategies may interpret the same observations differently and may produce different
> decisions for the same instrument without creating a course contradiction."

**Binding:** the banned-adjective rule is enforceable in review — any decision field named
`quality`, `strength` or `confirmed` must resolve to a stated rule or be explicitly flagged as human
review. Two strategies disagreeing on one instrument is **not** a bug and must not be "fixed".

### Layer 4 — Trade Management (365 topics)

> "Independently defined policies for position size, order selection, entry timing, stops, targets,
> scale-in, scale-out, trailing, breakeven, event handling, time exits, early exits, and review."

> "Management policies may be reused across strategies but remain separately versioned and
> validated. A favorable management result does not retroactively prove the entry logic had edge."

**Binding:** management and entry are validated separately. Attributing a management-driven result
to entry logic is a specific, named error.

## 3. The mandatory trace

Present in every module as `REQUIRED TRACE`:

```
Source Facts → Derived Observations → Evaluated Conditions → Strategy Decision
             → Management Policy → Outcome → Review
```

> "Каждая запись хранит as-of данные, версии компонентов, результат условий, причину отказа, human
> override и следующее действие."
> *(Every record stores as-of data, component versions, condition results, the refusal reason, human
> override, and the next action.)*

> "A conclusion that cannot be reproduced from its recorded inputs and versions is a production
> defect."

**Binding:** this defines the minimum journal record. It is why `JOURNAL_SCHEMA.md` carries an
`Audit` entity and why `run_manifest` exists in `DETERMINISM_SPEC.md`.

## 4. What a strategy must specify

§3.6 lists what every strategy or playbook declares. Transcribed as the required field set for
`STRATEGY_CARD_SPEC.md`:

strategy ID and version · applicable markets, instruments, timeframes, regimes, holding horizon ·
required source facts and derived observations · prerequisite context and candidate-selection rules ·
setup, trigger, entry method, maximum acceptable entry · invalidation, initial stop, sizing method,
portfolio constraints · management and exit policies · incompatible conditions and automatic
Skip/Pause/Error gates · expected data latency and behaviour when data is missing, stale, revised or
contradictory · evidence classification and validation status.

> "Reference topics may teach components that are not yet used by a validated strategy. They still
> identify their layer, operational role, limitations, and evidence status. All techniques being
> available for research does not authorize combining all of them inside one rule set without a
> documented hypothesis and validation."

**Binding:** this is the course's own statement of the activation gate in `docs/README.md`. A
component may be registered and specified without being active in any strategy.

## 5. Component independence

§3.8 lists the reusable component classes: source and normalization adapters · formulas and
indicators · derived-observation classifiers · candle, structure, level, zone, pattern and event
detectors · screeners and candidate filters · decision gates and strategy definitions · execution
and fill models · sizing, risk, management and exit policies · portfolio constraints · journals,
analytics and validation procedures.

> "Each component has one canonical definition, explicit inputs and outputs, an owner, a version,
> tests or verification method appropriate to its role, and a visible list of known consumers.
> Strategies reference components rather than copying their formulas or silently reimplementing
> them."

The independence rules, verbatim, each mapped to how this repo enforces it:

| Rule | Enforcement |
|---|---|
| "indicators do not own strategy decisions" | layer contract, `pyproject.toml` |
| "patterns and classifiers produce observations, not orders" | layer contract |
| "strategies do not fetch or normalize their own private version of shared facts" | `forbidden` contract: `decision_logic` ✗→ `market_data` |
| "management and exit policies may be attached to multiple strategies without duplicating logic" | one implementation per decision, `EXIT_MODEL_SPEC.md` |
| "modifying one strategy does not modify another unless a shared dependency is deliberately versioned and both consumers explicitly adopt the new version" | component versioning + consumer list |
| "changing a shared component never silently rewrites historical evidence. Affected strategy versions are re-tested or remain linked to the earlier component version" | evidence records pin component versions, `EVIDENCE_RECORD_SPEC.md` |
| "critical gates remain non-compensatory … A score or agreement among several weak indicators cannot override missing data, invalid risk, unavailable borrow, incompatible execution, or another critical failure" | `FAIL_CLOSED_POLICY.md` |
| "component combinations require a stated hypothesis. Redundant indicators, correlated observations, parameter searches, and interaction terms are counted as research degrees of freedom rather than free confirmation" | `PREREG_TEMPLATE.md`, multiple-testing accounting |

## 6. Human judgment

> "Human judgment is permitted where the course explicitly requires it. The record must identify the
> observation shown to the reviewer, the bounded choice available, the decision made, and the reason.
> Human review may not be presented as deterministic calculation, and an undocumented override may
> not be presented as rule-compliant."

**Binding:** this is the specification for the Telegram approval flow. Every prompt sent to the user
must carry: the observation, the bounded set of choices, and a required reason on the response. A
free-text action with no bounded choice set is non-compliant.
