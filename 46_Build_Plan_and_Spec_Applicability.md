# 46 — План построения и применимость мастер-ТЗ

```yaml
document_metadata:
  document_id: DOC-PLAN-046
  title: План построения и применимость мастер-ТЗ (логический разбор 56 разделов)
  version: 1.0.0
  status: DRAFT
  owner: null
  reviewers: []
  source_documents: [master_specification/v1.0]
  dependency_documents: [DOC-CHARTER-000, DOC-REQ-001, DOC-ONTOLOGY-003, DOC-UDR-045]
  created_at: null
  updated_at: null
```

Мастер-ТЗ содержит 56 нормативных разделов (плюс §0 — инструкция агенту). Не все применимы к текущему состоянию проекта в равной мере. Этот документ логически сортирует каждый раздел и выводит порядок построения. Он же служит рабочим планом.

---

## 1. Классы применимости

| Класс | Значение |
| --- | --- |
| **DONE** | уже зафиксировано в документах 00/01/03/45 |
| **FOUNDATION-NOW** | source-independent, строится сейчас (форма/мета/политика, не зависит от содержания уроков) |
| **LESSON-GATED** | форма строится сейчас, наполнение ждёт полных уроков (`UDR-001`) |
| **SCOPE-DEFERRED** | вне текущего контура (ручное исполнение; нет live-автоматизации) — место в онтологии фиксируется, работа откладывается |
| **CROSS-CUTTING** | сквозная политика/качество, действует везде, поглощается в 00/01 |

---

## 2. Разбор 56 разделов

| § | Раздел | Класс | Целевой документ | Статус |
| ---: | --- | --- | --- | --- |
| 0 | Инструкция агенту | CROSS-CUTTING | 00 / 01 | DONE |
| 1 | Смысл проекта | DONE | 00 | ✅ |
| 2 | Главный принцип успеха | DONE | 00 | ✅ |
| 3 | Главные цели документации (25 вопросов) | FOUNDATION-NOW | 47 (DoD checklist) | later |
| 4 | Предметная область (рынки, направление, TF) | FOUNDATION-NOW | 02 | **next** |
| 5 | Полнота курса / Coverage Matrix | LESSON-GATED | 02 (форма) | форма→next |
| 6 | Основная архитектурная модель (слои) | DONE | 03 | ✅ |
| 7 | Определения сущностей | DONE | 03 | ✅ |
| 8 | Канонический источник истины | FOUNDATION-NOW | 32 + ADR-001 | Tier 4 |
| 9 | Общая модель метаданных | FOUNDATION-NOW | schema (common_metadata) | **now** |
| 10 | Извлечение знаний из курса | FOUNDATION-NOW | 05 | **now** |
| 11 | Терминология | LESSON-GATED | 04 (форма) | форма→Tier 2 |
| 12 | Требования к данным (time semantics) | FOUNDATION-NOW | 06 | **now** |
| 13 | Feature / Indicator Spec | LESSON-GATED | 09 (форма) | форма→Tier 2 |
| 14 | Parameter Registry | FOUNDATION-NOW | 10 (реестр+дисциплина) | Tier 2 |
| 15 | Rule Specification | LESSON-GATED | 11 (форма) | форма→Tier 2 |
| 16 | Event Specification | LESSON-GATED | 12 (форма) | форма→Tier 2 |
| 17 | State / State Machine | LESSON-GATED | 13 (форма) | форма→Tier 2 |
| 18 | Market Regime | LESSON-GATED (`UDR-004`) | 14 | book |
| 19 | Setup / Trigger / Strategy | LESSON-GATED | 15 / 16 (форма) | форма→Tier 2 |
| 20 | Constraint Model | FOUNDATION-NOW | 17 | Tier 2 |
| 21 | Outcome Definition | FOUNDATION-NOW | 18 | Tier 3 |
| 22 | Метрики стратегии | FOUNDATION-NOW | 18 | Tier 3 |
| 23 | Expectation Model | LESSON-GATED | 19 (форма) | форма→Tier 3 |
| 24 | Evidence Framework | FOUNDATION-NOW | 20 | Tier 3 |
| 25 | Research Governance | FOUNDATION-NOW | 21 | Tier 3 |
| 26 | Validation Protocol | FOUNDATION-NOW | 22 | Tier 3 |
| 27 | Backtest Simulation Semantics | FOUNDATION-NOW | 23 + ADR-004 | Tier 3 |
| 28 | Execution Model | FOUNDATION-NOW (частично) | 24 | Tier 3 (частично) |
| 29 | Order Management State Machine | SCOPE-DEFERRED (`UDR-003`) | 27 | deferred |
| 30 | Risk Engine | FOUNDATION-NOW | 25 | Tier 4 |
| 31 | Capital Allocation / Ranking | FOUNDATION-NOW | 26 | Tier 4 |
| 32 | AI Decision Agent | FOUNDATION-NOW | 28 | Tier 4 |
| 33 | LLM / Model Governance | FOUNDATION-NOW | 30 | Tier 4 |
| 34 | Decision Record / Explainability | FOUNDATION-NOW | 29 | Tier 4 |
| 35 | System Modes | FOUNDATION-NOW | 02 | **next** |
| 36 | System Architecture | FOUNDATION-NOW | 31 | Tier 4 |
| 37 | Non-Functional Requirements | FOUNDATION-NOW | 33 | Tier 4 |
| 38 | Testing Strategy | FOUNDATION-NOW | 34 | Tier 5 |
| 39 | Golden Datasets | LESSON-GATED (форма now) | 35 | форма→Tier 5 |
| 40 | Observability / Audit | FOUNDATION-NOW | 36 | Tier 5 |
| 41 | Security | FOUNDATION-NOW | 37 | Tier 5 |
| 42 | Operations / Incident Response | SCOPE-DEFERRED (частично) | 38 | deferred |
| 43 | Change Management | FOUNDATION-NOW | 39 | Tier 5 |
| 44 | Learning Engine | FOUNDATION-NOW | 40 | Tier 5 |
| 45 | Drift Monitoring | FOUNDATION-NOW (пороги LESSON) | 41 | Tier 5 |
| 46 | Knowledge Graph | FOUNDATION-NOW (СУБД `UDR-002`) | 42 | Tier 5 |
| 47 | Документационный комплект | FOUNDATION-NOW | этот план | ✅ учтено |
| 48 | Формат документации | DONE | 00 + doc_metadata | ✅ |
| 49 | Рабочий процесс агента (Этапы 1–9) | FOUNDATION-NOW (Этап 1–2 LESSON) | 05 | now/book |
| 50 | MVP / вертикальный срез | LESSON-GATED (`UDR-005`) | 46 (скелет) | скелет→book |
| 51 | Переходные ворота | FOUNDATION-NOW | 47 | Tier 5 |
| 52 | Definition of Done | FOUNDATION-NOW | 47 | Tier 5 |
| 53 | Количественные критерии QA | FOUNDATION-NOW | 47 | Tier 5 |
| 54 | Запрещённые действия агента | CROSS-CUTTING | 01 | ✅ поглощено |
| 55 | Итоговая архитектурная формула | DONE | 00 | ✅ |
| 56 | Финальная задача агенту (gap-analysis) | CROSS-CUTTING | этот план | ✅ метод |

**Сводка по классам:** DONE — 7; FOUNDATION-NOW — 29; LESSON-GATED — 12; SCOPE-DEFERRED — 3; CROSS-CUTTING — 5.

Ключевой вывод: **~52% разделов (29 из 56) строятся прямо сейчас, не дожидаясь уроков**, потому что определяют форму, а не содержание. 12 разделов дают форму сейчас и ждут наполнения. Только 3 отложены по scope.

---

## 3. Порядок построения (tiers)

Порядок следует зависимостям и собственной последовательности мастер-ТЗ (Этап 4 онтология → Этап 5 схемы → Этап 6 каталоги; Gate 1→2→…).

**Tier 0 — Конституция (готово):** 00, 01, 03, 45.

**Tier 1 — Несущая мета (source-independent, разблокирует всё):**
- `schemas/common_metadata.schema.json` (§9) — на неё ссылается каждый объект
- `06_Data_and_Time_Semantics.md` (§12) — PIT и защита от look-ahead; дом `REQ-DATA-001/002`
- `05_Course_Knowledge_Extraction_Model.md` (§10, §49) — мост к урокам: делает извлечение turnkey к моменту готовности книги
- `02_Product_Scope_and_System_Modes.md` (§4, §35, §5-форма) — границы всего

**Tier 2 — Формы объектов (структура без содержания):**
- `07_Data_Pipeline_and_Data_Contracts.md` (§12.6-8), `09_Feature_and_Indicator_Specification.md` (§13)
- `10_Parameter_Registry_and_Calibration.md` (§14), `11_Rule_Specification.md` (§15)
- `12_Event_Catalog.md` (§16), `13_State_Machines.md` (§17)
- `15_Setup_and_Trigger_Model.md` + `16_Strategy_Composition.md` (§19), `17_Constraint_and_Veto_Model.md` (§20)
- `04_Glossary_and_Canonical_Terms.md` (§11, форма)
- соответствующие `schemas/*.schema.json`

**Tier 3 — Исход, исследование, валидация, backtest (source-independent):**
- `18_Outcome_and_Performance_Metrics.md` (§21-22), `19_Expectation_Model.md` (§23, форма)
- `20_Evidence_and_Provenance_Framework.md` (§24), `21_Research_Governance.md` (§25)
- `22_Time_Series_Validation_Protocol.md` (§26), `23_Backtest_Simulation_Semantics.md` (§27)
- `24_Execution_and_Fill_Model.md` (§28, часть) + ADR-004

**Tier 4 — Система, AI, риск (source-independent):**
- `25_Portfolio_and_Risk_Engine.md` (§30), `26_Capital_Allocation_and_Ranking.md` (§31)
- `28_AI_Decision_Agent.md` (§32), `29_Decision_Context_and_Output_Contracts.md` (§34)
- `30_AI_Model_Governance_and_Evaluation.md` (§33), `31_System_Architecture_and_Bounded_Contexts.md` (§36)
- `32_Canonical_Source_and_Runtime_Compilation.md` (§8) + ADR-001, `33_Non_Functional_Requirements.md` (§37)

**Tier 5 — Качество, наблюдаемость, governance (source-independent):**
- `34_Test_Strategy.md` (§38 — сюда ложатся `REQ-VALIDATION-001/002` как типы тестов)
- `35_Golden_Datasets.md` (§39, форма), `36_Observability_and_Audit.md` (§40)
- `37_Security_and_Threat_Model.md` (§41), `39_Change_Release_and_Rollback_Governance.md` (§43)
- `40_Offline_Learning_and_Knowledge_Promotion.md` (§44), `41_Drift_Monitoring.md` (§45)
- `42_Knowledge_Graph_Schema.md` (§46), `47_Acceptance_Gates_and_Definition_of_Done.md` (§51-53)

**Tier 6 — Наполнение из уроков (когда книга готова, `UDR-001`):**
- Этап 1–2 (Source Inventory → извлечение), затем наполнение: `04` глоссарий, `09` features, `10` значения параметров, `11` rules, `12` events, `13` states, `14` regimes (`UDR-004`), `15/16` setups/strategies, `19` expectation estimates, `05`-каталоги, Coverage Matrix, golden-сценарии, конкретика reference slice (`UDR-005`).

**Отложено по scope (`UDR-003`):** `27` OMS (§29), брокерская часть `24` (§28), ops-runbooks `38` (§42) — до появления автоисполнения/live.

---

## 4. Логические замечания к плану

1. **Форма отделена от содержания везде, где возможно.** Rule/Event/State/Feature/Strategy получают полную схему объекта сейчас (Tier 2), а конкретные экземпляры — из уроков (Tier 6). Это позволяет строить ~52% ТЗ немедленно и делает наполнение книгой механическим, а не творческим.
2. **`05` (извлечение) — критический мост.** Он строится в Tier 1 именно потому, что уроки неполны: когда книга придёт, Этап 1–2 должны быть turnkey, а не проектироваться заново.
3. **Шесть сквозных REQ уже размещены** (в 01) и получают исполняемые проверки в Tier 5 (`34` Testing): `REQ-VALIDATION-001` (mutation), `REQ-VALIDATION-002` (parity/replay), остальные — по своим `verification_method`.
4. **Scope-DEFERRED — не выброс.** OMS/broker/runbooks фиксируются в онтологии со статусом `DEFERRED`, чтобы место было определено, а труд не тратился на контур, которого пока нет (ручное исполнение).
5. **Reference slice (§50) — скелет сейчас, тело из уроков.** По собственному порядку ТЗ (Gate 2 → Gate 4) срез идёт после онтологии и схем; его конкретика (какой setup/trigger) — `LESSON-GATED`.
6. **Метод §56 (gap-analysis) применён здесь:** этот документ и есть проверка существующего материала на соответствие мастер-ТЗ и определение, что покрыто, что частично, что отсутствует.
