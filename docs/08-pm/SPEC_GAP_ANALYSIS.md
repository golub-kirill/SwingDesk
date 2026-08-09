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
| 5 | Coverage Matrix | **ABSENT** | no matrix of area × documented/specified/implemented/validated/runtime |
| 6 | Архитектурная модель (слои) | FULL | `LIFECYCLE_AND_LAYERS.md`, `DEPENDENCY_LAW.md` — **and enforced**: 4 import contracts, gate 6 |
| 7 | Определения сущностей | PARTIAL | `GLOSSARY.md` (35 terms), `src/swingdesk/contracts/`; the ТЗ's 22-entity table is not mapped one-to-one |
| 8 | Канонический источник истины | PARTIAL | no ADR. **Live violation**: `schemas/*.json` and `contracts/*.py` are two hand-maintained copies |
| 9 | Общая модель метаданных | PARTIAL | `registry/*.yml` rows carry metadata; no unified `common_metadata` applied across object types |
| 10 | Извлечение знаний из курса | FULL | `tools/build_course_index.py`, `registry/course_index.yml` — 1379 topics classified, gate 3 |
| 11 | Терминология | PARTIAL | `GLOSSARY.md` — no `synonyms_discouraged` / `ambiguous_terms` fields |
| 12 | Требования к данным, время | **PARTIAL** | `POINT_IN_TIME_SPEC.md`, `DATA_QUALITY_SPEC.md`, `CALENDAR_SPEC.md`. **2 of 8 time types** |
| 13 | Feature / Indicator Spec | FULL | `COMPONENT_REGISTRY_SPEC.md`, `registry/components.yml` (465), 25 golden vectors, gates 3c/7b/11 |
| 14 | Parameter Registry | FULL | `PARAMETER_REGISTRY.md`, `registry/parameters.yml` (96), gate 1 |
| 15 | Rule Specification | **ABSENT** | no formal Rule object: no expression tree, no three-valued output contract, no `vetoed_by` |
| 16 | Event Specification | **ABSENT** | `EVENT_SPEC.md` is the *market-event catalogue* (M34/M40), not the formal Event object. Name collision — see §4 |
| 17 | State / State Machine | PARTIAL | `DECISION_STATE_MACHINE.md` covers candidate decisions; no instrument state machine, no hysteresis policy |
| 18 | Market Regime | FULL | `REGIME_SPEC.md`, `derived_observations/regime.py`, **PR-002 validated** |
| 19 | Setup / Trigger / Strategy | PARTIAL | `STRATEGY_CARD_SPEC.md`, `SCREENER_SPEC.md`; no separate Setup and Trigger objects with expiration |
| 20 | Constraint Model | PARTIAL | `CODES.md` (12 skip + 12 error codes), `FAIL_CLOSED_POLICY.md`; no constraint object with `priority` / `override_policy` |
| 21 | Outcome Definition | PARTIAL | `contracts/trade.py`, `BACKTEST_PROTOCOL.md`; intrabar ambiguity policy undefined |
| 22 | Метрики стратегии | PARTIAL | `STATISTICS_SPEC.md`; no capacity estimate, no exposure/turnover |
| 23 | Expectation Model | **ABSENT** | the four studies carry baselines; no Expectation object, no estimate/definition split |
| 24 | Evidence Framework | FULL | `EVIDENCE_RECORD_SPEC.md`, `contracts/evidence.py`, three reported studies |
| 25 | Research Governance | FULL | `PREREG_TEMPLATE.md` + **four executed pre-registrations** |
| 26 | Validation Protocol | FULL | `VALIDATION_PROGRAM.md`, `WALKFORWARD_SPEC.md` |
| 27 | Backtest Semantics | PARTIAL | `BACKTEST_PROTOCOL.md`, `validation/backtest/engine.py`; intrabar policy absent |
| 28 | Execution Model | **ABSENT** | `validation/backtest/costs.py` models commission and slippage only |
| 29 | Order Management SM | DEFERRED | D1 — the system never places orders |
| 30 | Risk Engine | PARTIAL | `RISK_SPEC.md`, `trade_management/sizing.py`; **no portfolio layer** — correlation, sector and open-risk caps all `unset` |
| 31 | Capital Allocation / Ranking | **ABSENT** | no deterministic ranking when candidates exceed capital |
| 32 | AI Decision Agent | DEFERRED | `CHARTER.md` §3 non-goal for v1 |
| 33 | LLM / Model Governance | DEFERRED | follows §32 |
| 34 | Decision Record | FULL | `JOURNAL_SCHEMA.md`, `AUDIT_AND_IMMUTABILITY.md`, `journal_evidence/journal.py` |
| 35 | System Modes | **ABSENT** | no RESEARCH / BACKTEST / REPLAY / PAPER / SHADOW / LIVE definition |
| 36 | System Architecture | FULL | `ARCHITECTURE.md`, `DEPENDENCY_LAW.md`, `CONCURRENCY_MODEL.md` |
| 37 | Non-Functional Requirements | FULL | `NFR.md` |
| 38 | Testing Strategy | FULL | `TEST_STRATEGY.md`, `INVARIANTS.md`, 275 tests, 16 gates |
| 39 | Golden Datasets | PARTIAL | `golden/` holds 25 component **vectors**; the ТЗ's 25 named end-to-end **scenarios** do not exist |
| 40 | Observability / Audit | FULL | `OBSERVABILITY_SPEC.md`, `docs/runbooks/` |
| 41 | Security | FULL | `SECURITY.md`, `BACKUP_AND_DR.md` |
| 42 | Operations / Incident Response | FULL | `docs/runbooks/` — five runbooks with verbatim return conditions |
| 43 | Change Management | PARTIAL | `COMPONENT_REGISTRY_SPEC.md` §6 covers component versioning; no change-type taxonomy or rollback policy |
| 44 | Learning Engine | **ABSENT** | offline-learning promotion path undefined |
| 45 | Drift Monitoring | **ABSENT** | nothing monitors feature, regime, slippage or expectation drift |
| 46 | Knowledge Graph | **ABSENT** | dependencies exist in registries; no graph projection |
| 47 | Документационный комплект | FULL | `docs/README.md` — 57-document plan, different structure, same function |
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
| FULL | **28** |
| PARTIAL | 16 |
| ABSENT | **9** |
| DEFERRED | 3 |

**Half the specification is already met.** That is the finding the parallel analysis could not
reach, and it changes the plan: the work is filling nine holes and closing sixteen shortfalls, not
building 48 documents.

## 4. The nine absent sections, ranked

Ranked by what unblocks the most, not by ТЗ order.

1. **§15 Rule Specification** — the ТЗ's central object. Everything from §16 to §20 references it.
   A 276-line draft exists in the parallel track's `11_Rule_Specification.md`, preserved in commit
   `dee8f37`. It is the seed for `docs/02-domain/RULE_SPEC.md`, not a substitute: it is in Russian,
   and it specifies the object without checking which parts this tree's components already satisfy —
   the same omission that produced the rest of this analysis.
2. **§16 Event Specification.** Note the collision: `EVENT_SPEC.md` here means the *market-event
   catalogue*. The ТЗ's Event is the formal discrete-transition object. Two different things share
   one name, which is precisely the §11 terminology failure the specification warns about. The new
   document needs a different name.
3. **§35 System Modes** — cheap, and every other section references the mode it applies in.
4. **§28 Execution Model** — currently latent rather than harmful: the engine has a protective stop
   and a time stop and no target, so stop-and-target-in-one-bar cannot arise. It becomes a
   correctness defect the day a target exists.
5. **§23 Expectation Model** — the studies have baselines; the object that would make them
   comparable does not exist.
6. **§31 Capital Allocation** — needed the moment candidates exceed capital. With 1,133 universe
   members that day is close.
7. **§5 Coverage Matrix** — the ТЗ forbids claiming coverage without formal basis.
8. **§45 Drift Monitoring** and **§44 Learning Engine** — both need a live record first, and
   `UX_TASK_FLOWS.md` §3 measures the post-trade phase at 0 of 6.
9. **§46 Knowledge Graph** — a projection of registries that already exist. Lowest urgency.

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
contracts win because they are already enforced at runtime and by 249 tests, so a divergence between
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
