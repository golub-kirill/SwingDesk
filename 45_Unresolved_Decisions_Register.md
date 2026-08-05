# 45 — Реестр нерешённых вопросов

```yaml
document_metadata:
  document_id: DOC-UDR-045
  title: Реестр нерешённых вопросов SwingDesk
  version: 1.0.0
  status: DRAFT
  owner: null
  reviewers: []
  source_documents: [master_specification/v1.0]
  dependency_documents: [DOC-CHARTER-000]
  created_at: null
  updated_at: null
```

Открытые вопросы фиксируются здесь явно, а не скрываются за предположениями. Наличие записи в этом реестре — нормальное состояние; она не блокирует работу над остальной документацией, если объект можно корректно оставить `UNSET`. Вопрос владельцу проекта задаётся только тогда, когда без решения невозможно корректно определить смысл объекта или фундаментальное поведение системы.

Формат записи:

```yaml
unresolved_decision:
  id: UDR-NNN
  question: >
    Что именно требует решения.
  blocks: []          # какие объекты/документы это блокирует; пусто — не блокирует
  options: []         # рассматриваемые варианты, если есть
  owner_input_required: true|false
  status: OPEN
```

---

## Открытые записи

```yaml
unresolved_decision:
  id: UDR-001
  question: >
    Полные версии уроков свинг-трейдинга ещё не готовы. Доменное извлечение
    (конкретные rules, strategies, features, значения параметров) невозможно
    завершить до их готовности.
  blocks:
    - каталоги rules.yaml / strategies.yaml / features.yaml (наполнение)
    - доменные требования REQ-RULE-*, доменные REQ-DATA-*
    - reference vertical slice (§50) — конкретика setup/trigger
  options:
    - строить онтологию и требования вперёд, с UNSET на местах доменного материала (принято на этой фазе)
  owner_input_required: false
  status: OPEN
  note: >
    Не блокирует фундамент. По мере поступления уроков запускается Этап 1–2
    (Source Inventory → извлечение), и каркас наполняется реальными терминами
    пользователя, а не догадками.

unresolved_decision:
  id: UDR-002
  question: >
    Выбор графовой базы данных для проекции Knowledge Graph. Мастер-ТЗ прямо
    относит это к отдельному архитектурному решению и запрещает автоматически
    считать граф основной runtime-базой.
  blocks:
    - физическая реализация knowledge graph (не его логическая схема)
  options: []
  owner_input_required: true
  status: OPEN
  note: >
    Логическая схема графа (типы узлов и связей) определяется независимо от
    выбора СУБД и не заблокирована этой записью.

unresolved_decision:
  id: UDR-003
  question: >
    Область (scope) исполнительного и брокерского слоя. Текущий контур —
    ручное исполнение; полноценные OMS, fill-модели, broker adapter и
    reconciliation не требуются на текущей фазе.
  blocks: []
  options:
    - пометить объекты §27–§29 (Order Management, Execution, Broker) как scope=DEFERRED до появления автоисполнения (предложено)
  owner_input_required: true
  status: OPEN
  note: >
    Не выбрасывается — фиксируется в онтологии со статусом DEFERRED, чтобы
    место в модели было определено, а работа не тратилась вхолостую.

unresolved_decision:
  id: UDR-004
  question: >
    Канонический набор рыночных режимов (Regime ontology). Мастер-ТЗ приводит
    примерный список (BULL / WEAK_BULL / NEUTRAL / DISTRIBUTION / BEAR / PANIC /
    RECOVERY / UNKNOWN), но требует не считать его окончательным до формальной
    спецификации.
  blocks:
    - 14_Market_Regime_Model.md (наполнение)
    - validated domain стратегий по режимам
  options: []
  owner_input_required: true
  status: OPEN
  note: >
    Зависит от уроков (UDR-001): режимы должны выводиться из материала, а не
    назначаться заранее.

unresolved_decision:
  id: UDR-005
  question: >
    Порядок работы после фундамента: подтвердить, что первым идёт reference
    vertical slice (§50) до массового наполнения 48 документов, как того
    требует сам мастер-ТЗ (Gate 2 → Gate 4).
  blocks: []
  options:
    - reference slice первым, до широкого наполнения каталогов (соответствует §50 и §5)
  owner_input_required: true
  status: OPEN
```
