# SPEC GAP ANALYSIS — master ТЗ v1.0 against what exists

**Status:** drafting · **Tier:** 8 (project management) · **Content:** authored, measured against the tree

Master ТЗ v1.0 (2026-08-04) §56 asks for exactly one thing first: *"проверить существующую
техническую документацию; построить gap analysis"*. This is that check.

**Why it exists separately from `46_Build_Plan_and_Spec_Applicability.md`.** That document performed
the same analysis and reached a different answer, because it was written without sight of this tree
— verified: it contains zero references to `docs/`, `src/`, `registry/`, or any study id. Its
line 154 states the §56 method was applied; it was applied to a greenfield baseline. Its
classification framework is sound and is reused below. Its schedule is not, because roughly ten
sections it placed in Tier 3–5 are already done here.

Every coverage claim below names a path. Gate 3e (`tools/verify_docs.py`) fails the build if one
does not resolve, so this table cannot rot quietly.

---

## 1. Applicability classes

Taken from `46_Build_Plan_and_Spec_Applicability.md` §1 — the one part of the parallel track worth
keeping wholesale.

| Class | Meaning |
|---|---|
| **FULL** | the ТЗ requirement is met by an existing artefact |
| **PARTIAL** | substantially covered, with a named shortfall |
| **ABSENT** | nothing in the tree addresses it |
| **DEFERRED** | out of the current contour by owner decision, place in the ontology fixed |

## 2. The 56 sections

| § | Section | Coverage | Where it lives / what is missing |
|---:|---|---|---|
| 0 | Инструкция агенту | FULL | `AGENTS.md`, `CI_POLICY.md` |
| 1 | Смысл проекта | FULL | `CHARTER.md` |
| 2 | Главный принцип успеха | FULL | `CHARTER.md`, `SUCCESS_AND_KILL_CRITERIA.md` (frozen v1.0.0) |
| 3 | 25 вопросов документации | PARTIAL | `DEFINITION_OF_READY_DONE.md` answers most; no document walks all 25 |
| 4 | Предметная область | FULL | `CONSTRAINTS.md` — markets, timeframes, D1–D10 |
| 5 | Coverage Matrix | FULL | `COVERAGE_MATRIX.md` (2026-08-08) — **generated** from the registries by `tools/build_coverage.py`, gate 3ci. Authoring it by hand would have been the one document whose only content is counts, maintained by hand |
| 6 | Архитектурная модель (слои) | FULL | `LIFECYCLE_AND_LAYERS.md`, `DEPENDENCY_LAW.md` — **and enforced**: 4 import contracts, gate 6 |
| 7 | Определения сущностей | PARTIAL | `GLOSSARY.md` (35 terms), `src/swingdesk/contracts/`; the ТЗ's 22-entity table is not mapped one-to-one |
| 8 | Канонический источник истины | PARTIAL | no ADR. **Live violation**: `schemas/*.json` and `contracts/*.py` are two hand-maintained copies |
| 9 | Общая модель метаданных | PARTIAL | `registry/*.yml` rows carry metadata; no unified `common_metadata` applied across object types |
| 10 | Извлечение знаний из курса | FULL | `tools/build_course_index.py`, `registry/course_index.yml` — 1379 topics classified, gate 3 |
| 11 | Терминология | PARTIAL | `GLOSSARY.md` — no `synonyms_discouraged` / `ambiguous_terms` fields |
| 12 | Требования к данным, время | **PARTIAL** | `POINT_IN_TIME_SPEC.md`, `DATA_QUALITY_SPEC.md`, `CALENDAR_SPEC.md`. **2 of 8 time types** |
| 13 | Feature / Indicator Spec | FULL | `COMPONENT_REGISTRY_SPEC.md`, `registry/components.yml` (465), 25 golden vectors, gates 3c/7b/11 |
| 14 | Parameter Registry | FULL | `PARAMETER_REGISTRY.md`, `registry/parameters.yml` (96), gate 1 |
| 15 | Rule Specification | PARTIAL | `RULE_SPEC.md` (2026-08-08) freezes the form and audits the eight rules that exist. **No object carries `scope`, `evidence_status` or a declared effect class**, and no rule links to its own tests |
| 16 | Event Specification | PARTIAL | `TRANSITION_SPEC.md` (2026-08-08) — the object, renamed to end the collision with the market-event catalogue in `EVENT_SPEC.md`. `from_state` now recorded on decisions; **no common envelope across the four shapes**, and six kinds of transition are still not recorded at all, two of them irrecoverably |
| 17 | State / State Machine | PARTIAL | `DECISION_STATE_MACHINE.md` covers candidate decisions; no instrument state machine, no hysteresis policy |
| 18 | Market Regime | FULL | `REGIME_SPEC.md`, `derived_observations/regime.py`, **PR-002 validated** |
| 19 | Setup / Trigger / Strategy | PARTIAL | `STRATEGY_CARD_SPEC.md`, `SCREENER_SPEC.md`; no separate Setup and Trigger objects with expiration |
| 20 | Constraint Model | PARTIAL | `CODES.md` (12 skip + 12 error codes), `FAIL_CLOSED_POLICY.md`; no constraint object with `priority` / `override_policy` |
| 21 | Outcome Definition | PARTIAL | `contracts/trade.py`, `BACKTEST_PROTOCOL.md`; the intrabar ambiguity policy is now stated (`EXECUTION_MODEL.md` §4) and **`Trade` carries no ambiguity flag to record it** |
| 22 | Метрики стратегии | PARTIAL | `STATISTICS_SPEC.md`; no capacity estimate, no exposure/turnover |
| 23 | Expectation Model | PARTIAL | `EXPECTATION_MODEL.md` (2026-08-08) — the estimate/definition split, the cohort key, the status ladder. **No estimate is addressable yet**: aggregate results live in study JSON and no runtime object could cite one |
| 24 | Evidence Framework | FULL | `EVIDENCE_RECORD_SPEC.md`, `contracts/evidence.py`, three reported studies |
| 25 | Research Governance | FULL | `PREREG_TEMPLATE.md` + **three executed pre-registrations**, plus one post-hoc bound labelled as such |
| 26 | Validation Protocol | FULL | `VALIDATION_PROGRAM.md`, `WALKFORWARD_SPEC.md` |
| 27 | Backtest Semantics | PARTIAL | `BACKTEST_PROTOCOL.md`, `validation/backtest/engine.py`; intrabar policy specified in `EXECUTION_MODEL.md` §4 and not yet enforceable — nothing can violate it while no target exists |
| 28 | Execution Model | PARTIAL | `EXECUTION_MODEL.md` (2026-08-08) — fills, gaps, the intrabar policy and the costs. **No target exists, so the policy is stated ahead of its first use**; the live path sizes from a different price than the backtest fills at |
| 29 | Order Management SM | DEFERRED | D1 — the system never places orders |
| 30 | Risk Engine | PARTIAL | `RISK_SPEC.md`, `trade_management/sizing.py`; **no portfolio layer** — correlation, sector and open-risk caps all `unset` |
| 31 | Capital Allocation / Ranking | PARTIAL | `ALLOCATION_SPEC.md` (2026-08-08) — admissibility vs preference, the allocation record, the id-order trap. `DR-006` proposes the six portfolio constraints; **two of them cannot be evaluated** (no sector source, no correlation matrix) and `rs.ranking_method` is `unset`, so nothing ranks yet |
| 32 | AI Decision Agent | DEFERRED | `CHARTER.md` §3 non-goal for v1 |
| 33 | LLM / Model Governance | DEFERRED | follows §32 |
| 34 | Decision Record | FULL | `JOURNAL_SCHEMA.md`, `AUDIT_AND_IMMUTABILITY.md`, `journal_evidence/journal.py` |
| 35 | System Modes | PARTIAL | `SYSTEM_MODES.md` (2026-08-08) — six modes, four running, `mode` required on `RunManifest` and on `pipeline.run` since 2026-08-08. **`PAPER` and `SHADOW` do not exist**, so two of the six are definitions without a runtime |
| 36 | System Architecture | FULL | `ARCHITECTURE.md`, `DEPENDENCY_LAW.md`, `CONCURRENCY_MODEL.md` |
| 37 | Non-Functional Requirements | FULL | `NFR.md` |
| 38 | Testing Strategy | FULL | `TEST_STRATEGY.md`, `INVARIANTS.md`, 253 tests, 18 gates |
| 39 | Golden Datasets | PARTIAL | `golden/` holds 25 component **vectors**; the ТЗ's 25 named end-to-end **scenarios** do not exist |
| 40 | Observability / Audit | FULL | `OBSERVABILITY_SPEC.md`, `docs/runbooks/` |
| 41 | Security | FULL | `SECURITY.md`, `BACKUP_AND_DR.md` |
| 42 | Operations / Incident Response | FULL | `docs/runbooks/` — five runbooks with verbatim return conditions |
| 43 | Change Management | PARTIAL | `COMPONENT_REGISTRY_SPEC.md` §6 covers component versioning; no change-type taxonomy or rollback policy |
| 44 | Learning Engine | **ABSENT** | offline-learning promotion path undefined |
| 45 | Drift Monitoring | **ABSENT** | nothing monitors feature, regime, slippage or expectation drift |
| 46 | Knowledge Graph | **ABSENT** | dependencies exist in registries; no graph projection |
| 47 | Документационный комплект | FULL | `docs/README.md` — 61-document plan, different structure, same function |
| 48 | Формат документации | FULL | `docs/README.md`; enforced by gates 2 and 3e |
| 49 | Рабочий процесс агента | FULL | `AGENTS.md`, `tools/build_*.py` |
| 50 | MVP / вертикальный срез | **FULL** | **G5 closed 2026-08-02** — walking skeleton green, replay is a merge gate |
| 51 | Переходные ворота | FULL | `GO_LIVE_GATES.md`, `docs/README.md` gates G0–G7 |
| 52 | Definition of Done | FULL | `DEFINITION_OF_READY_DONE.md` |
| 53 | Количественные критерии QA | PARTIAL | gate 3e enforces broken-reference = 0; no single QA scorecard against the ТЗ's 13 counters |
| 54 | Запрещённые действия агента | PARTIAL | `AGENTS.md` non-negotiables cover most of the 30 |
| 55 | Итоговая формула | FULL | `CHARTER.md` |
| 56 | Финальная задача (gap analysis) | FULL | this document |

## 3. Summary

| Coverage | Count |
|---|---|
| FULL | **29** |
| PARTIAL | 22 |
| ABSENT | **2** |
| DEFERRED | 3 |

**Half the specification is already met.** That is the finding the parallel analysis could not
reach, and it changes the plan: the work is filling two holes and closing twenty-two shortfalls,
not building 48 documents.

**Movement since the first pass (2026-08-04 → 2026-08-08).** §15, §28, §35 and §16 — the top four of
the nine — moved from ABSENT to PARTIAL when `RULE_SPEC.md`, `EXECUTION_MODEL.md`,
`SYSTEM_MODES.md` and `TRANSITION_SPEC.md` were written. They are PARTIAL and not FULL on purpose:
each specifies a form that no object in the tree yet carries, and grading the document rather than
the discharge is how a coverage matrix starts lying. Each names its own remaining shortfall in the
row above.

## 4. The two absent sections, and why they are not simply next

What is left is not the top of a queue. These three are **blocked on something other than writing
time**, which is why they outlasted the six that went first.

1. **§45 Drift Monitoring** and **§44 Learning Engine** — blocked on `EXPECTATION_MODEL.md` having a
   stored estimate to measure against, and then on a live record. Drift **is** the difference between
   two expectations for one cohort at two as-of dates; with zero stored expectations there is nothing
   to difference. `UX_TASK_FLOWS.md` §3 measures the post-trade phase at 0 of 6 — the same gap from
   the operator's side.
2. **§46 Knowledge Graph** — a projection of registries that already exist. Lowest urgency, and the
   one section where specifying before projecting would be pure ceremony.

**§5 was one of these and is now FULL** — built as a generator rather than written, for the reason
that kept it on this list: a hand-maintained matrix of counts is the most rot-prone document a
project can own, and this tree had already shipped five documents quoting a study count that was
wrong. `tools/build_coverage.py` counts every cell from the registries and gate 3ci fails if the
committed copy drifts.

### What the written documents found

Each was written by auditing the tree rather than by transcribing the seed, and each returned a
defect that no gate could see:

| Document | Found |
|---|---|
| `RULE_SPEC.md` | the backtest trigger collapsed "no lookback window" into "did not trigger" and counted neither — the first `lookback` bars of every instrument left the signal denominator silently. **Fixed 2026-08-08** |
| `EXECUTION_MODEL.md` | `Skipped` declared five reasons and incremented three; `POSITION_OPEN` removed signals from the denominator without recording how many. **Fixed 2026-08-08.** Still open: the live path sizes from the last close while the backtest fills at the next open plus slippage |
| `SYSTEM_MODES.md` | `RunManifest` has no `mode` field, so a journalled run cannot say whether it was real |
| `EXPECTATION_MODEL.md` | this tree carries provenance for the numbers a human chose and none for the numbers it measured. `REQ-OUTPUT-001` requires an "estimate version, cohort key, or model reference" and all three name parts of an object that does not exist |
| `ALLOCATION_SPEC.md` | the course's only two statements about how to order candidates are **both labelled `Untested Hypothesis` by the course itself**, so adopting either is a pre-registration rather than a transcription |
| `TRANSITION_SPEC.md` | nothing records `from_state`, so a status that changed is indistinguishable from one that was always there. Appendix G requires `Candidate.status history` and there is no watchlist store to hold it; the owner's approval of a proposal — the only transition with a human actor — is written nowhere |

## 5. The two shortfalls that are defects rather than gaps

**§12 — two of eight time types.** The store distinguishes `event_time` and `knowledge_time`. The
ТЗ requires eight, and names `available_time` as the one that decides admissibility: a decision at
`decision_time = T` may use only values with `available_time ≤ T`. Bars make this collapse safely
(a daily bar is available at session close), which is why it has cost nothing so far. It stops being
safe the moment any non-bar source arrives — earnings dates, filings, news — because for those,
publication and availability genuinely differ.

**§8 — two hand-maintained schema copies. Resolved by removal, pending a generator.**
`schemas/common_metadata.schema.json` and `schemas/parameter.schema.json` overlapped
`src/swingdesk/contracts/*.py`. The specification's own §8 forbids maintaining one logic in two
places, so the hand-written copies were removed rather than left to drift; both are preserved
verbatim in `dee8f37`.

The requirement itself stands and is unmet: **JSON Schema should be generated from the Pydantic
models** (`model_json_schema()`), with a `--check-only` gate like every other registry here. The
contracts win because they are already enforced at runtime and by 253 tests, so a divergence between
them and a hand-written schema would always be the schema's fault.

## 6. What the parallel track contributed

Recorded so the effort is not written off:

- **The applicability taxonomy** (§1 above) — reused wholesale.
- **The eight time types** — a real gap this tree had not identified.
- **`REQ-*` objects** with `verification_method` and `acceptance_criteria`. This tree has Gherkin
  user stories and no requirement registry, and a requirement registry is what CI gate 10
  (traceability) has been waiting for.
- **The calendar-as-point-in-time-dataset framing** and `REQ-DATA-001` (zero date literals in
  executable code). Checked: `src/` already satisfies it. Worth keeping as an enforceable rule.

Two of its requirements were verified as **already met** — no date literals in `src/`, and
`Series.RAW` / `Series.ADJUSTED` stored separately by contract. Good requirements, written without
checking whether they were already satisfied.

## 7. Open items

- [ ] `01_Normative_Requirements_and_Conventions.md` declares **nine** `REQ-*` ids; the working
      note describing it says six. Reconcile before the registry is folded in.
- [ ] The ten numbered documents at repo root are outside gate 3e's scan (`docs/` only), so their
      own cross-references are unverified while they remain there.
- [ ] `k.timebox_review` fired when G5 closed on 2026-08-02 and `registry/criteria.yml` is still
      v1.0.0. Owner amendment, tracked here because it is a governance gap the ТЗ would also flag.
