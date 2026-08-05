# 03 — Доменная онтология

```yaml
document_metadata:
  document_id: DOC-ONTOLOGY-003
  title: Доменная онтология SwingDesk
  version: 1.0.0
  status: DRAFT

  owner: null
  reviewers: []

  source_documents:
    - master_specification/v1.0
  dependency_documents:
    - DOC-CHARTER-000
    - DOC-REQ-001

  requirement_refs: []
  unresolved_issue_refs:
    - UDR-002        # выбор графовой БД — отдельное архитектурное решение
  created_at: null
  updated_at: null
```

Онтология — это меta-модель системы: типы объектов, их идентификаторы, статусы и связи. Она **source-independent**: определяет форму знания, а не его содержание, поэтому строится до готовности уроков. Конкретные экземпляры (реальные rules, strategies, features) наполняют каталоги позже, по мере формализации уроков.

---

## 1. Многоуровневая модель

Обязательное разделение уровней обработки:

```text
Raw Data
  → Normalized Data
  → Observation
  → Feature / Indicator
  → Event
  → State
  → Regime / Context
  → Setup
  → Trigger
  → Strategy Candidate
  → Expectation
  → Decision
  → Risk Approval
  → Order
  → Execution / Fill
  → Position
  → Trade
  → Outcome
  → Evidence
  → Offline Knowledge Update
```

**Правило неслияния уровней.** Объект одного уровня НЕ ДОЛЖЕН подменять объект другого. Наиболее частые нарушения, подлежащие явному запрету:

- `Event` и `State` не объединяются: «пробой произошёл» — событие; «инструмент в состоянии после пробоя» — состояние. Событие МОЖЕТ вызвать переход состояния, но не является состоянием.
- `Setup` и `Decision` не объединяются: setup — потенциальная возможность; decision — зафиксированный вывод.
- `Score` и `Probability` не объединяются (см. раздел о выводах в спецификации ранжирования).
- `Data confidence` и `Edge confidence` не объединяются.

---

## 2. Типы объектов

Каждый тип имеет русское определение и английский canonical name (последний используется в идентификаторах и коде).

| Canonical | Русское определение |
| --- | --- |
| `Raw Data` | Неизменённые данные источника |
| `Normalized Data` | Данные, приведённые к внутреннему стандарту |
| `Observation` | Непосредственно наблюдаемое значение |
| `Feature` | Рассчитанная характеристика данных |
| `Indicator` | Формально определённый тип feature |
| `Rule` | Функция, преобразующая входы в формальный результат |
| `Event` | Дискретное событие в определённый момент |
| `State` | Сохраняющееся состояние на временном интервале |
| `Regime` | Состояние высокого уровня, влияющее на набор допустимых стратегий |
| `Setup` | Совокупность условий, создающая потенциальную возможность |
| `Trigger` | Событие, разрешающее конкретное действие |
| `Constraint` | Ограничение: veto, penalty, warning или eligibility-фильтр |
| `Strategy` | Полный торговый процесс от universe до выхода |
| `Decision` | Зафиксированный вывод системы в конкретный момент |
| `Order` | Инструкция на исполнение |
| `Fill` | Подтверждённое исполнение ордера |
| `Position` | Текущее экономическое воздействие на инструмент |
| `Trade` | Полный или частичный жизненный цикл позиции |
| `Outcome` | Формально измеренный результат |
| `Expectation` | Условное вероятностное описание будущего outcome |
| `Evidence` | Доказательство или результат исследования |
| `Parameter` | Версионируемая величина, используемая формальной логикой |
| `Policy` | Правило управления поведением системы |
| `Decision Agent` | Ограниченный компонент выбора допустимого действия |

---

## 3. Идентификаторы объектов

Формат:

```text
OBJECT_TYPE.DOMAIN.CONCEPT.NUMBER
```

Примеры:

```text
DATA.PRICE.CLOSE.001
FEATURE.VOLATILITY.ATR.001
PARAMETER.ATR.PERIOD.001
RULE.TREND.PRICE_ABOVE_EMA.001
EVENT.PRICE.BREAKOUT.001
STATE.INSTRUMENT.UPTREND.001
REGIME.MARKET.BULL.001
SETUP.PULLBACK.TREND_CONTINUATION.001
STRATEGY.PULLBACK.TREND_CONTINUATION.001
EXPECTATION.PULLBACK.RETURN_R.001
EVIDENCE.PULLBACK.WALK_FORWARD.001
```

Идентификатор: уникален; стабилен; не меняется при переименовании; не зависит от файла; используется в документации, коде, тестах и логах.

---

## 4. Общий блок метаданных

Каждый объект несёт единый блок (полная схема — в `schemas/common_metadata.schema.json`, будет создана на этапе схем):

```yaml
metadata:
  id: RULE.TREND.PRICE_ABOVE_EMA.001
  object_type: rule

  version: 1.0.0
  schema_version: 1.0.0

  status: SPECIFIED

  title_ru: Цена выше EMA
  title_en: Price Above EMA

  summary: >
    Краткое нейтральное описание объекта.

  owner: null
  created_at: null
  updated_at: null
  reviewed_at: null

  source_refs: []
  course_module_refs: []
  requirement_refs: []
  test_refs: []

  tags: []
  supersedes: null
  superseded_by: null
  change_log: []
```

---

## 5. Жизненный цикл статуса объекта

```text
DRAFT
REVIEWED
SPECIFIED
IMPLEMENTABLE
IMPLEMENTED
IMPLEMENTATION_VERIFIED
VALIDATION_PENDING
VALIDATED
MONITORED
REJECTED
DEPRECATED
SUPERSEDED
DISABLED
```

**Правило.** Статус `VALIDATED` НЕ ДОЛЖЕН присваиваться без ссылки на конкретный Validation Record (ср. `REQ-EVIDENCE-001`). Статус — это утверждение о состоянии объекта; утверждение без доказательства недопустимо.

---

## 6. Классы извлечения знаний из уроков

Каждый фрагмент урока при формализации классифицируется одним из классов:

```text
CONCEPT
DEFINITION
OBSERVATION
FEATURE
INDICATOR
RULE_CANDIDATE
EVENT_CANDIDATE
STATE_CANDIDATE
SETUP_CANDIDATE
STRATEGY_CANDIDATE
RISK_POLICY
EXECUTION_POLICY
HYPOTHESIS
EXPECTATION_CLAIM
LIMITATION
WARNING
EDUCATIONAL_EXPLANATION
NON_EXECUTABLE_GUIDANCE
```

**Не всё содержание урока превращается в код.** Например, «после сильного импульса цена часто делает передышку» — это не готовое правило, а:

```yaml
classification: HYPOTHESIS
formalization_status: UNSET
```

При извлечении обязательно: выделить концепт; найти скрытые параметры; определить нужный тип объекта; дать точное определение; сохранить ссылку на модуль урока; указать evidence status; не выдавать утверждение за доказанный факт.

---

## 7. Типы связей

Связи между объектами типизированы, направлены, версионируемы, проверяемы и объяснимы.

```text
DERIVES_FROM        REQUIRES            USES_PARAMETER      USES_DATA
PRODUCES            EMITS               DETECTS             ENTERS_STATE
EXITS_STATE         CAUSES_TRANSITION   SUPPORTS            CONTRADICTS
INVALIDATES         VETOES              COMPOSES            CONSUMED_BY
PREDICTS            MEASURED_BY         VALIDATED_BY        TESTED_BY
DEPENDS_ON          CONFLICTS_WITH      SCOPED_TO           SUPERSEDES
EXPLAINED_BY        DOCUMENTED_IN       IMPLEMENTED_BY      AFFECTED_BY
```

**Правило.** Универсальная связь `RELATED_TO` НЕ ДОЛЖНА использоваться, кроме временного чернового состояния. Нетипизированная связь не несёт проверяемого смысла и разрушает трассируемость.

Проекция графа знаний (выбор конкретной графовой БД — отдельное архитектурное решение, `UDR-002`) должна отвечать в том числе на вопросы: почему сделка была/не была открыта; какие события привели к состоянию; какие правила используют данный параметр; какие стратегии затронет изменение параметра; какие правила не имеют evidence; какие expectations не имеют baseline; какие параметры `UNSET`; какие объекты runtime-enabled, но не полностью validated; какие правила конфликтуют; какие узлы являются orphan nodes.

---

## 8. Три значения истинности и классы ограничений

Онтология фиксирует, что результат правила может быть трёхзначным:

```text
TRUE   FALSE   UNKNOWN
```

`UNKNOWN` НЕ ДОЛЖЕН автоматически превращаться в `FALSE` или `TRUE` (ср. `REQ-DATA-002`). Причины `UNKNOWN`: missing data; insufficient history; stale data; unresolved parameter; unsupported market; calculation failure; conflicting source values.

Классы ограничений (`Constraint`), которые нельзя смешивать между собой (подробная семантика — в спецификации правил, будет создана как `11_Rule_Specification.md`):

```text
ELIGIBILITY_FILTER
HARD_GATE
VETO
SOFT_PENALTY
WARNING
PORTFOLIO_CONSTRAINT
EXECUTION_CONSTRAINT
DATA_QUALITY_CONSTRAINT
BROKER_CONSTRAINT
REGULATORY_CONSTRAINT
```

Каждый экземпляр `Constraint` ОБЯЗАН иметь формальный эффект; формулировка «invalid when» без определённого эффекта недостаточна.
