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
| 3 | 25 вопросов документации | PARTIAL | `DEFINITION_OF_READY_DONE.md` answers most. **Blocked: the 25 questions are not in the repository** — the master ТЗ is absent and only its restatements survive (`dee8f37`) |
| 4 | Предметная область | FULL | `CONSTRAINTS.md` — markets, timeframes, D1–D10 |
| 5 | Coverage Matrix | FULL | `COVERAGE_MATRIX.md` (2026-08-08) — **generated** from the registries by `tools/build_coverage.py`, gate 3ci. Authoring it by hand would have been the one document whose only content is counts, maintained by hand |
| 6 | Архитектурная модель (слои) | FULL | `LIFECYCLE_AND_LAYERS.md`, `DEPENDENCY_LAW.md` — **and enforced**: 4 import contracts, gate 6 |
| 7 | Определения сущностей | PARTIAL | `ENTITY_MAP.md` (2026-08-08) maps all 24 object types — **12 built, 2 deferred by decision, 3 specified with zero instances**. Mapped against the *restatement* in `dee8f37`, because the ТЗ is not in the repository; **22 vs 24 is unresolved** |
| 8 | Канонический источник истины | PARTIAL | no ADR. **Live violation**: `schemas/*.json` and `contracts/*.py` are two hand-maintained copies |
| 9 | Общая модель метаданных | PARTIAL | `registry/*.yml` rows carry metadata; no unified `common_metadata` applied across object types |
| 10 | Извлечение знаний из курса | FULL | `tools/build_course_index.py`, `registry/course_index.yml` — 1379 topics classified, gate 3 |
| 11 | Терминология | FULL | `GLOSSARY.md` gained both sections (2026-08-08) — 10 ambiguous terms, each a collision this tree has already hit and paid for, plus the discouraged synonyms |
| 12 | Требования к данным, время | **PARTIAL** | `POINT_IN_TIME_SPEC.md`, `DATA_QUALITY_SPEC.md`, `CALENDAR_SPEC.md`. **2 of 8 time types** |
| 13 | Feature / Indicator Spec | FULL | `COMPONENT_REGISTRY_SPEC.md`, `registry/components.yml` (465), 25 golden vectors, gates 3c/7b/11 |
| 14 | Parameter Registry | FULL | `PARAMETER_REGISTRY.md`, `registry/parameters.yml`, gate 1. How many parameters it holds is `HANDOFF.md` §2's — this row said 96 until 2026-08-24 |
| 15 | Rule Specification | PARTIAL | `RULE_SPEC.md` (2026-08-08) freezes the form and audits the eight rules that exist. **No object carries `scope`, `evidence_status` or a declared effect class**, and no rule links to its own tests |
| 16 | Event Specification | PARTIAL | `TRANSITION_SPEC.md` (2026-08-08) — the object, renamed to end the collision with the market-event catalogue in `EVENT_SPEC.md`. `from_state` now recorded on decisions; **no common envelope across the four shapes**, and six kinds of transition are still not recorded at all, two of them irrecoverably |
| 17 | State / State Machine | PARTIAL | `DECISION_STATE_MACHINE.md` covers candidate decisions; no instrument state machine, no hysteresis policy |
| 18 | Market Regime | **PARTIAL** | `REGIME_SPEC.md`, `derived_observations/regime.py`. ~~**PR-002 validated**~~ — **that verdict was CORRECTED to `inconclusive` on 2026-08-16** and `regime.classifier_rule` is `assumed:PR-002`, so the row's only stated evidence for FULL was withdrawn eight days before anyone noticed. Reclassified 2026-08-24 on this document's own standard — grading the document rather than the discharge is how a coverage matrix starts lying: the classifier's `read_by` is **`none`**, so the regime is specified, implemented and **wired into no decision** |
| 19 | Setup / Trigger / Strategy | PARTIAL | `STRATEGY_CARD_SPEC.md`, `SCREENER_SPEC.md`; no separate Setup and Trigger objects with expiration |
| 20 | Constraint Model | PARTIAL | `CODES.md` (12 skip + 12 error codes), `FAIL_CLOSED_POLICY.md`; no constraint object with `priority` / `override_policy` |
| 21 | Outcome Definition | PARTIAL | `contracts/trade.py`, `BACKTEST_PROTOCOL.md`; the intrabar ambiguity policy is now stated (`EXECUTION_MODEL.md` §4) and **`Trade` carries no ambiguity flag to record it** |
| 22 | Метрики стратегии | PARTIAL | `STATISTICS_SPEC.md`; no capacity estimate, no exposure/turnover |
| 23 | Expectation Model | PARTIAL | `EXPECTATION_MODEL.md` (2026-08-08) — the estimate/definition split, the cohort key, the status ladder. **No estimate is addressable yet**: aggregate results live in study JSON and no runtime object could cite one |
| 24 | Evidence Framework | FULL | `EVIDENCE_RECORD_SPEC.md`, `contracts/evidence.py`, the reported studies |
| 25 | Research Governance | FULL | `PREREG_TEMPLATE.md` + **the executed pre-registrations**, plus one post-hoc bound labelled as such |
| 26 | Validation Protocol | FULL | `VALIDATION_PROGRAM.md`, `WALKFORWARD_SPEC.md` |
| 27 | Backtest Semantics | PARTIAL | `BACKTEST_PROTOCOL.md`, `validation/backtest/engine.py`; intrabar policy specified in `EXECUTION_MODEL.md` §4 and not yet enforceable — nothing can violate it while no target exists |
| 28 | Execution Model | PARTIAL | `EXECUTION_MODEL.md` (2026-08-08) — fills, gaps, the intrabar policy and the costs. **No target exists, so the policy is stated ahead of its first use**; the live path sizes from a different price than the backtest fills at |
| 29 | Order Management SM | DEFERRED | D1 — the system never places orders |
| 30 | Risk Engine | PARTIAL | `RISK_SPEC.md`, `trade_management/sizing.py`, `trade_management/portfolio.py`. ~~**no portfolio layer** — correlation, sector and open-risk caps all `unset`~~ — **the portfolio layer exists since 2026-08-22/23** (`DR-006` §9, §11, §12) and all five caps carry a value and name a consumer. Remaining shortfall: `risk.liquidity_cap_order_to_adtv_pct` is `owner`-set and `read_by` **`none`**, `account.fx_rate_cad` is `unset` so a CAD candidate refuses, and the book's R excludes round-trip costs while 1R includes them (`DR-006` §10) |
| 31 | Capital Allocation / Ranking | PARTIAL | `ALLOCATION_SPEC.md` (2026-08-08) — admissibility vs preference, the allocation record, the id-order trap. ~~`DR-006` proposes the six portfolio constraints; **two of them cannot be evaluated** (no sector source, no correlation matrix)~~ — **`DR-006` is fully ratified and all six reach code** (2026-08-23): the sector source is the bar vendor's own look-through and the full correlation matrix builds from the store. **The shortfall is unchanged and is the ranking**: `rs.ranking_method` is `unset` and `rs.benchmark_form` is `unset` by `DR-018`, so nothing ranks yet |
| 32 | AI Decision Agent | **PARTIAL** | ~~DEFERRED — `CHARTER.md` §3 non-goal for v1~~. **Charter amendment A-001 (2026-08-08) put this contour IN scope** — outside the ratified v1 finish line, which is a different claim — and `AI_AUTHORITY_MODEL.md` was written for it the same day. `COVERAGE_AUDIT.md` §4 states it in as many words: *"The coverage status is `MISSING`, not `OUT_OF_SCOPE`"*, and its §3 row grades the contour `PARTIALLY_COVERED`. Shortfall, quoted from there: the model's §3 boundary is authored and wants owner ratification, and **none of its prohibitions are gated** |
| 33 | LLM / Model Governance | DEFERRED | ~~follows §32~~ — §32 is no longer deferred, so the reason had to move: `COVERAGE_AUDIT.md` §5 rules `AI_MODEL_GOVERNANCE_AND_EVALUATION` **not yet**, because model, prompt and schema versioning matter once an agent exists and *"follows the authority model, does not precede it"*. Place in the ontology fixed |
| 34 | Decision Record | FULL | `JOURNAL_SCHEMA.md`, `AUDIT_AND_IMMUTABILITY.md`, `journal_evidence/journal.py` |
| 35 | System Modes | PARTIAL | `SYSTEM_MODES.md` (2026-08-08) — six modes, four running, `mode` required on `RunManifest` and on `pipeline.run` since 2026-08-08. **`PAPER` and `SHADOW` do not exist**, so two of the six are definitions without a runtime |
| 36 | System Architecture | FULL | `ARCHITECTURE.md`, `DEPENDENCY_LAW.md`, `CONCURRENCY_MODEL.md` |
| 37 | Non-Functional Requirements | FULL | `NFR.md` |
| 38 | Testing Strategy | FULL | `TEST_STRATEGY.md`, `INVARIANTS.md`, the test suite and the merge gates |
| 39 | Golden Datasets | PARTIAL | `golden/` holds 25 component **vectors**; the ТЗ's 25 named end-to-end **scenarios** do not exist |
| 40 | Observability / Audit | FULL | `OBSERVABILITY_SPEC.md`, `docs/runbooks/` |
| 41 | Security | FULL | `SECURITY.md`, `BACKUP_AND_DR.md` |
| 42 | Operations / Incident Response | FULL | `docs/runbooks/` — five runbooks with verbatim return conditions |
| 43 | Change Management | FULL | `CHANGE_MANAGEMENT.md` (2026-08-08) — 8 change types, and the rollback finding: **the stores are append-only, so rollback is mostly supersede rather than revert** |
| 44 | Learning Engine | PARTIAL | `DRIFT_AND_LEARNING.md` (2026-08-08) §1 — the promotion path is **M69's acceptance enum**, transcribed since 2026-08-01 and connected to nothing. **Nothing consumes it**, and the post-trade loop it needs is out of contour under D1 |
| 45 | Drift Monitoring | PARTIAL | `DRIFT_AND_LEARNING.md` (2026-08-08) §3 — five families, **four computable today and none computed**; expectation drift needs executed fills and is structurally blocked |
| 46 | Knowledge Graph | PARTIAL | `KNOWLEDGE_GRAPH.md` (2026-08-08) specifies the projection. **10 of 11 edge types are already gate-enforced**; specified and deliberately not built until phase 3 grows the tree |
| 47 | Документационный комплект | FULL | `docs/README.md`, indexed by `registry/project_manifest.yml` and checked by gate 15 — different structure, same function. The document total is `HANDOFF.md` §2's; this row said 61 until 2026-08-24 |
| 48 | Формат документации | FULL | `docs/README.md`; enforced by gates 2 and 3e |
| 49 | Рабочий процесс агента | FULL | `AGENTS.md`, `tools/build_*.py` |
| 50 | MVP / вертикальный срез | **FULL** | **G5 closed 2026-08-02** — walking skeleton green, replay is a merge gate |
| 51 | Переходные ворота | FULL | `GO_LIVE_GATES.md`, `docs/README.md` gates G0–G7 |
| 52 | Definition of Done | FULL | `DEFINITION_OF_READY_DONE.md` |
| 53 | Количественные критерии QA | PARTIAL | gates 3e/3f/3ci enforce reference, count and coverage integrity. **Blocked: the 13 counters are not in the repository**, same cause as §3 |
| 54 | Запрещённые действия агента | PARTIAL | `AGENTS.md` non-negotiables cover most of the 30 |
| 55 | Итоговая формула | FULL | `CHARTER.md` |
| 56 | Финальная задача (gap analysis) | FULL | this document |

## 3. Summary

| Coverage | Count |
|---|---|
| FULL | **29** |
| PARTIAL | 26 |
| ABSENT | **0** |
| DEFERRED | 2 |

**57 rows, §0 through §56.** These four numbers are **recounted from the table above by gate 3e**,
not maintained by hand. They were maintained by hand until 2026-08-08 and had drifted to 31/22 — the
third count in this repository to drift after the study verdicts and the gate total, which is why it
is now checked rather than corrected.

**Over half the specification is met.** That is the finding the parallel analysis could not reach,
and it changed the plan: the work was never building 48 documents. What is left is twenty-four named
shortfalls, each stated in its own row.

**Movement 2026-08-24, and both directions are represented.** §32 left DEFERRED: charter
amendment A-001 put the AI contour **in scope** on 2026-08-08 — outside the ratified v1 finish line,
which is a different claim — and `AI_AUTHORITY_MODEL.md` was written for it the same day, so the row
had been citing a non-goal that the charter had already amended. §18 left FULL in the other
direction: its only stated evidence was *"PR-002 validated"*, and that verdict was corrected to
`inconclusive` on 2026-08-16 while the row went on asserting the strongest word this project has.
Two more rows kept their class and lost a stale shortfall — §30 and §31 both said the portfolio
constraints could not be evaluated, and all six have reached code since 2026-08-23.

**What that pass says about this table's failure mode.** Nothing here rots by being wrong when
written; it rots when a *cited* fact moves and the citation stays. Gate 3e checks that a cited
document exists and that the summary matches the table — neither of which can see a withdrawn study
verdict or an amended charter. The habit that catches it is `AGENTS.md` §12's: read the artefact
that owns the claim, and this table's rows are dense with claims it does not own.

**Movement since the first pass (2026-08-04 → 2026-08-08).** §15, §28, §35 and §16 — the top four of
the nine — moved from ABSENT to PARTIAL when `RULE_SPEC.md`, `EXECUTION_MODEL.md`,
`SYSTEM_MODES.md` and `TRANSITION_SPEC.md` were written. They are PARTIAL and not FULL on purpose:
each specifies a form that no object in the tree yet carries, and grading the document rather than
the discharge is how a coverage matrix starts lying. Each names its own remaining shortfall in the
row above.

## 4. Nothing is ABSENT, and two sections are blocked on a missing source

**Phase 1 closed 2026-08-08.** All 56 sections are FULL, PARTIAL or DEFERRED; the ranked list of
absences that governed the work since 2026-08-04 is empty.

`§46 Knowledge Graph` was the last, and it is PARTIAL rather than FULL for a reason worth keeping:
the projection is **specified and deliberately not built**. Ten of its eleven edge types are already
gate-enforced, every question it would answer is answerable today by reading two YAML files, and the
tree is small enough that this is not painful. It pays for itself in phase 3.

### Two sections are blocked on a source this repository does not hold

**§3 (the 25 documentation questions) and §53 (the 13 QA counters) need the master ТЗ's literal
content, and the ТЗ is not here.** Only the parallel track's restatements survive, in `dee8f37`.

They are recorded as PARTIAL-blocked rather than written, because a document that walks 25 questions
nobody can read is 25 invented questions. Owner decision 2026-08-08: write what is writable, block
the rest.

**Evidence that second-hand sourcing is the right thing to refuse here:** row 7 of this table said
the ТЗ has a **22-entity** table; the preserved `03_Domain_Ontology.md` lists **24**. One is wrong,
`ENTITY_MAP.md` §0 discloses the discrepancy, and neither document can resolve it. That is a small
disagreement about a table; §3 and §53 would have been the same disagreement about content nobody
could check.

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
contracts win because they are already enforced at runtime and by the test suite, so a divergence between
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
