# 17 — Модель ограничений и veto

```yaml
document_metadata:
  document_id: DOC-CONSTRAINT-017
  title: Модель ограничений и veto SwingDesk
  version: 1.0.0
  status: DRAFT
  owner: null
  reviewers: []
  source_documents: [master_specification/v1.0, tradalert_postmortem/TRADALERT_REVIEW]
  dependency_documents: [DOC-ONTOLOGY-003, DOC-REQ-001, DOC-RULE-011, DOC-DATA-006]
  requirement_refs: [REQ-AI-001, REQ-RISK-001, REQ-DATA-001]
  unresolved_issue_refs: []
  created_at: null
  updated_at: null
```

`Constraint` — ограничение, отменяющее или изменяющее действие. Мастер-ТЗ формулирует ядро этого документа одной фразой: **формулировка «invalid when» без формального эффекта недостаточна.** Форма source-independent: конкретные ограничения приходят из уроков (`UDR-001`); здесь определяется, как ограничение выражается и как исполняется.

Форма несёт три урока TradAlert:

- **Vetos, которые не могут отклонить.** Ограничение с классом `VETO`/`HARD_GATE` обязано проходить discriminating-pair и mutation-проверку из `11` — иначе это декоративный запрет (как R:R-гейт, который «проверял» reward:risk и всегда пропускал).
- **Пустой/устаревший veto как живой контроль.** Ограничение на основе даты (blackout, earnings window) обязано быть point-in-time (`REQ-DATA-001`) и fail-closed — иначе оно молча перестаёт блокировать (как blackout-календарь TradAlert, пустой два месяца).
- **AI, обходящий Risk-вето.** `VETO` риск-класса не может быть отменён AI-агентом (`REQ-AI-001`).

---

## 1. Классы ограничений

Класс определяет **природу** ограничения. Классы нельзя смешивать (см. `11`, раздел 3).

```text
ELIGIBILITY_FILTER       — допуск на этап (universe/pre-screen)
HARD_GATE                — обязательное условие прохождения
VETO                     — независимая отмена, вне зависимости от score
SOFT_PENALTY             — изменение оценки без запрета
WARNING                  — информирование без изменения вердикта
PORTFOLIO_CONSTRAINT     — ограничение на уровне портфеля
EXECUTION_CONSTRAINT     — ограничение исполнения
DATA_QUALITY_CONSTRAINT  — ограничение по качеству данных
BROKER_CONSTRAINT        — ограничение брокера
REGULATORY_CONSTRAINT    — регуляторное ограничение
```

Разница `HARD_GATE` и `VETO`: gate — часть последовательного прохождения (не прошёл — не идёшь дальше); veto — независимая отмена, применимая даже к объекту с высоким score. Их семантика исполнения различна, поэтому смешение запрещено.

---

## 2. Полная форма ограничения

```yaml
constraint:
  metadata:
    id: CONSTRAINT.EVENT.EARNINGS_WINDOW.001
    object_type: constraint
    version: 1.0.0
    schema_version: 1.0.0
    status: SPECIFIED
    title_ru: Окно отчётности (veto)
    title_en: Earnings Window Veto
    owner: null
    source_refs: []
    course_module_refs: []

  class: VETO                                # один из раздела 1
  scope: ENTRY                               # ENTRY | EXIT | SIZING | PORTFOLIO | EXECUTION

  condition_ref: RULE.EVENT.EARNINGS_PROXIMITY.001    # правило-условие (форма из 11)

  effect:                                    # ОБЯЗАТЕЛЕН; «invalid when» без него недостаточно
    action: REJECT_ENTRY                     # см. раздел 3
    reason_code: EARNINGS_WINDOW_VETO        # обязателен для объяснимости

  priority: null                             # порядок применения при конфликте (раздел 4)

  override_allowed: false                    # риск-класс: всегда false для AI (REQ-AI-001)
  override_policy_ref: null

  temporal:                                  # для ограничений на основе времени/даты
    point_in_time: true                      # REQ-DATA-001: only as-of-knowable
    fail_mode: FAIL_CLOSED                   # раздел 5
    staleness_policy: null                   # сверх какого возраста данные считаются устаревшими

  valid_from: null                           # версионирование внешних ограничений (broker/regulatory)
  valid_until: null

  applies_to:                                # к чему применяется
    strategies: []
    markets: [US, CA]
    instrument_types: [stock, ETF]

  tests:                                     # наследует требования из 11
    triggering_cases: []                     # вход, при котором ограничение срабатывает
    non_triggering_cases: []                 # вход, при котором не срабатывает
    discriminating_pair_ref: null            # REQ-VALIDATION-001 для HARD_GATE/VETO/ELIGIBILITY

  evidence_refs: []
```

---

## 3. Формальные эффекты

Эффект ограничения выбирается из перечня действий; свободного текста недостаточно.

```text
REJECT_ENTRY            — отклонить вход
BLOCK_UNTIL            — блокировать до условия/срока
REDUCE_SIZE            — уменьшить размер (для SOFT_PENALTY/риск-класса)
APPLY_PENALTY          — изменить score (для SOFT_PENALTY)
EMIT_WARNING           — выдать предупреждение (для WARNING)
FORCE_NO_TRADE         — принудить NO_TRADE
REQUIRE_ESCALATION     — потребовать ручного review
CANCEL_WORKING_ORDER   — отменить рабочий ордер (риск/execution)
```

Каждый эффект несёт `reason_code` — машиночитаемый код причины, обязательный для decision record и объяснимости (`REQ-OUTPUT-001`). Ограничение без `reason_code` не проходит валидацию.

---

## 4. Приоритет и разрешение конфликтов

Когда к одному действию применимо несколько ограничений, порядок детерминирован:

1. `DATA_QUALITY_CONSTRAINT` и `REGULATORY_CONSTRAINT` — высший приоритет (нельзя торговать на плохих данных или против регулятора);
2. `VETO` риск-класса (`REQ-AI-001`, неотменяемо);
3. `HARD_GATE`;
4. `BROKER_CONSTRAINT` / `EXECUTION_CONSTRAINT`;
5. `PORTFOLIO_CONSTRAINT`;
6. `SOFT_PENALTY` (влияет на оценку, не на допустимость);
7. `WARNING` (не меняет вердикт).

Результат НЕ ДОЛЖЕН зависеть от случайного порядка обработки. `priority` разрешает конфликты внутри одного класса и фиксируется явно.

---

## 5. Fail-closed для ограничений на основе данных (`REQ-DATA-001`)

Ограничение, зависящее от внешних данных (календарь событий, отчётность, качество данных), обязано вести себя fail-closed:

| Условие | Поведение |
| --- | --- |
| Данные недоступны | Вход блокируется. Выход из позиции — проходит. |
| Данные устарели сверх `staleness_policy` | Вход блокируется. |
| Источники противоречат | Вход блокируется для затронутого окна. Громкий алерт. |
| Покрытие календаря кончается близко к горизонту | Вход блокируется. **Не** логовое предупреждение. |

`point_in_time: true` обязателен: ограничение видит только то, что было известно на момент решения (`known_from ≤ decision_time`).

> В TradAlert blackout-veto сверял точную строку одной даты и был пуст два месяца — то есть всё это время возвращал «не блокировать» на каждом тикере. Отдельно календарь событий давал три разных даты из трёх источников без указания, какая использована, и при сбое фетча «падал открытым», а весь его сигнал тревоги был одной строкой в лог. Форма делает такое состояние недопустимым: пустой/сбойный календарь блокирует входы, а не пропускает их.

**Горизонт ограничения — это горизонт сделки.** Veto по событию проверяет все события в окне `[decision_time, decision_time + max_hold]`, а не «ближайшее в пределах фиксированных N дней». Иначе событие внутри окна удержания (например, заседание регулятора на 14-й день при удержании 3–14 дней) остаётся невидимым.

---

## 6. Независимость Risk-вето от AI (`REQ-AI-001`)

Ограничение риск-класса (`VETO`/`HARD_GATE`, порождённое Risk Engine) имеет `override_allowed: false` для AI-агента **всегда**. Вето Risk Engine не может быть отменено выводом агента. Архитектурно: не существует пути, которым решение агента достигает исполнения, минуя Risk Gate. Это проверяется интеграционным тестом (сценарий: veto Risk Engine отменяет действие агента) и инспекцией графа зависимостей (отсутствие ребра agent→broker в обход risk).

Risk Engine имеет абсолютное право на действия `REDUCE`, `REJECT`, `CANCEL`, `HALT`, `LIQUIDATE` независимо от Strategy Engine и AI Decision Agent (детально — в `25_Portfolio_and_Risk_Engine`).

---

## 7. Инварианты формы (проверяются статически)

- каждое ограничение имеет `class`, `scope`, `condition_ref`, `effect` с `reason_code`;
- `effect.action` принадлежит перечню раздела 3; свободный текст запрещён;
- ограничение класса `VETO`/`HARD_GATE`/`ELIGIBILITY_FILTER` имеет `discriminating_pair_ref` (`REQ-VALIDATION-001`);
- ограничение на основе данных имеет `point_in_time: true` и `fail_mode: FAIL_CLOSED` (`REQ-DATA-001`);
- риск-класс имеет `override_allowed: false` для AI (`REQ-AI-001`);
- `priority` задан для ограничений, способных конфликтовать внутри класса;
- внешнее ограничение (`BROKER_CONSTRAINT`/`REGULATORY_CONSTRAINT`) несёт `valid_from`/`valid_until` (версионирование по времени);
- риск-контроль в `enabled: false` несёт датированную ADR со сроком (`REQ-RISK-001`).
```
