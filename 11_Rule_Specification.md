# 11 — Спецификация правил

```yaml
document_metadata:
  document_id: DOC-RULE-011
  title: Спецификация правил SwingDesk
  version: 1.0.0
  status: DRAFT
  owner: null
  reviewers: []
  source_documents: [master_specification/v1.0, tradalert_postmortem/TRADALERT_REVIEW]
  dependency_documents: [DOC-ONTOLOGY-003, DOC-REQ-001, DOC-DATA-006]
  requirement_refs: [REQ-VALIDATION-001, REQ-DATA-002, REQ-OUTPUT-001]
  unresolved_issue_refs: []
  created_at: null
  updated_at: null
```

`Rule` — **формальная функция, а не текстовая рекомендация.** Этот документ определяет форму правила. Форма — source-independent: конкретные правила извлекаются из уроков (`UDR-001`) и наполняют `rules.yaml` по этой схеме.

Форма спроектирована так, чтобы **три конкретных режима отказа были невыразимы**:

- **Константный гейт** (правило, чей результат инвариантен ко входам) — не проходит `REQ-VALIDATION-001`, потому что форма требует пары различающих тестов и mutation-проверки.
- **Молчаливое `missing → значение`** — запрещено трёхзначной логикой (раздел 5) и обязательной `missing_data_policy`.
- **Декоративный вывод** (правило, которое печатается, но не потребляется) — ловится обязательными полями `consumed_by` и `effect`.

---

## 1. Обязательные части правила

Каждое правило имеет:

1. человекочитаемое определение (`semantic_claim`);
2. машинное выражение (`expression`);
3. входы (`inputs`);
4. предусловия (`preconditions`);
5. выход и его семантику (`output`);
6. временну́ю семантику (`evaluation`);
7. политику отсутствующих данных (`missing_data_policy`);
8. область действия (`scope`);
9. нисходящий эффект (`effect`, `consumed_by`);
10. статус доказательности (`expected_relationship.evidence_status`);
11. тесты (`tests`).

Отсутствие любой из этих частей означает, что объект не является правилом в смысле SwingDesk и не может получить статус выше `DRAFT`.

---

## 2. Полная форма

```yaml
rule:
  metadata:                                  # общий блок, см. common_metadata.schema.json
    id: RULE.TREND.PRICE_ABOVE_EMA.001
    object_type: rule
    version: 1.0.0
    schema_version: 1.0.0
    status: SPECIFIED
    title_ru: Цена выше EMA
    title_en: Price Above EMA
    summary: >
      Положение цены закрытия относительно EMA заданного периода.
    owner: null
    source_refs: []
    course_module_refs: []
    requirement_refs: []
    test_refs: []

  purpose: >
    Определение положения цены закрытия относительно EMA.

  semantic_claim: >
    Цена выше заданной EMA МОЖЕТ быть признаком положительной среднесрочной
    структуры. Это утверждение НЕ считается доказанным edge без validation record.
    # semantic_claim описывает предполагаемый смысл, а не доказанный факт.

  scope:                                     # §4; правило без scope запрещено
    markets: [US, CA]
    instrument_types: [stock, ETF]
    timeframes: [1D]
    regimes: []                              # пусто = не ограничено; заполняется при валидации по режимам
    direction: null                          # null = ненаправленное; LONG/SHORT если применимо

  inputs:
    - feature_ref: DATA.PRICE.CLOSE.001
    - feature_ref: FEATURE.TREND.EMA.001
    - parameter_ref: PARAMETER.EMA.PERIOD.001

  preconditions:
    minimum_history_bars: null               # UNSET; warm-up EMA + запас
    data_quality_requirements: []
    eligibility_rule_refs: []

  expression:                                # машинное выражение; единственный источник вердикта
    operator: GT
    left:  { feature_ref: DATA.PRICE.CLOSE.001 }
    right: { feature_ref: FEATURE.TREND.EMA.001 }

  evaluation:                                # временна́я семантика, см. 06
    evaluation_time: BAR_CLOSE
    available_time_policy: AFTER_BAR_FINALIZATION
    frequency: EACH_DAILY_BAR
    persistence_policy: null                 # сохраняется ли результат между барами
    confirmation_policy: null                # нужно ли подтверждение (N баров)
    cooldown_policy: null

  output:
    type: BOOLEAN                            # см. раздел 3 — допустимые типы
    true_meaning: CONDITION_CONFIRMED
    false_meaning: CONDITION_NOT_CONFIRMED
    unknown_allowed: true                    # трёхзначная логика обязательна, см. раздел 5

  missing_data_policy:                       # REQ-DATA-002; НЕ ДОЛЖНО быть "подставить значение"
    on_missing_input: UNKNOWN
    on_stale_input: UNKNOWN
    on_calculation_failure: UNKNOWN

  effect:                                    # нисходящий эффект; правило без эффекта — декорация
    effect_type: FEATURE_CONTRIBUTION        # см. раздел 3
    target_ref: STATE.INSTRUMENT.TREND.001
    weight_parameter_ref: null               # UNSET до калибровки; см. 10 и раздел 6

  consumed_by: []                            # обязательно: кто потребляет результат (REQ-OUTPUT-001)
  invalid_when: []
  vetoed_by: []
  conflicts_with: []
  depends_on: []

  expected_relationship:
    target_outcome_ref: null
    direction: POSITIVE
    evidence_status: HYPOTHESIS               # по умолчанию гипотеза, не факт

  failure_modes: []
  assumptions: []
  limitations: []

  validation_plan_ref: null
  evidence_refs: []

  tests:                                     # обязательны; см. раздел 4
    positive_cases: []
    negative_cases: []
    boundary_cases: []
    missing_data_cases: []
    stale_data_cases: []
    discriminating_pair_ref: null            # REQ-VALIDATION-001: пара входов с разным вердиктом
```

---

## 3. Типы результата и типы эффекта

### 3.1. Типы результата (`output.type`)

```text
BOOLEAN            — TRUE / FALSE / UNKNOWN
NUMERIC            — число с единицей
CATEGORY           — значение из перечня
SCORE_CONTRIBUTION — вклад в оценку
VETO               — независимая отмена действия
WARNING            — информирование о риске
STATE_TRANSITION   — переход состояния
EVENT_EMISSION     — эмиссия события
ELIGIBILITY_RESULT — допуск/недопуск на следующий этап
```

Запрещены результаты без точной семантики: `signal = good`, `trend = strong`, `setup = beautiful`. Каждое значение имеет определённый смысл (`true_meaning` / `false_meaning` / перечень категорий).

### 3.2. Класс правила-ограничения (`effect_type`)

Четыре класса, которые **нельзя смешивать между собой**:

| Класс | Семантика |
| --- | --- |
| `HARD_GATE` | Обязательное условие. Не выполнено → объект не проходит на следующий этап. |
| `VETO` | Независимое условие, отменяющее действие **независимо от score**. |
| `SOFT_FACTOR` | Изменяет оценку, но не запрещает действие. |
| `WARNING` | Информирует о риске/неопределённости, не меняя вердикт. |

Плюс `FEATURE_CONTRIBUTION` (вклад в состояние/оценку) и `STATE_TRANSITION`/`EVENT_EMISSION` для правил-переходов и правил-эмиттеров.

**Правило класса `HARD_GATE` или `VETO` обязано быть способно отклонить.** Форма это гарантирует через раздел 4.

---

## 4. Тесты обязательны — и почему это ядро формы

Это раздел, который делает `_rr_ok = return True` невыразимым.

### 4.1. Discriminating pair (`REQ-VALIDATION-001`)

Каждое правило с вердиктом (`BOOLEAN`, `VETO`, `ELIGIBILITY_RESULT`, `HARD_GATE`) **обязано** предъявить пару входных наборов `(A, B)`, на которых его результат **различается**:

```yaml
discriminating_pair:
  id: TEST.RULE.PRICE_ABOVE_EMA.DISCRIMINATING.001
  case_a:
    inputs: { "DATA.PRICE.CLOSE.001": 105.0, "FEATURE.TREND.EMA.001": 100.0 }
    expected: TRUE
  case_b:
    inputs: { "DATA.PRICE.CLOSE.001":  95.0, "FEATURE.TREND.EMA.001": 100.0 }
    expected: FALSE
```

Если такой пары не существует — результат правила инвариантен ко входам, правило является декорацией и **НЕ ДОЛЖНО допускаться в runtime**. Статическая проверка каталога отклоняет правило с вердиктом без `discriminating_pair_ref`.

### 4.2. Mutation-инвариант

На уровне системы (`34_Test_Strategy`) действует mutation-проверка: принудительная инверсия результата правила ОБЯЗАНА изменить ≥1 итоговый вердикт в тестовом корпусе. Правило, инверсия которого ничего не меняет, — декорация, и сборка падает.

> Это прямой перенос находки TradAlert: R:R-гейт `if is_long: return True` проходил семь аудитов логики, потому что был валидной функцией. Mutation-проверка отклонила бы его в первый же прогон: инверсия ничего не меняет.

### 4.3. Остальные обязательные наборы

- `positive_cases` — вход даёт `TRUE`/срабатывание;
- `negative_cases` — вход даёт `FALSE`/несрабатывание;
- `boundary_cases` — поведение на равенстве и у порога (строгое/нестрогое сравнение зафиксировано);
- `missing_data_cases` — отсутствующий вход даёт `UNKNOWN`, **не** значение по умолчанию;
- `stale_data_cases` — устаревший вход даёт `UNKNOWN`.

---

## 5. Трёхзначная логика

Результат правила может быть:

```text
TRUE   FALSE   UNKNOWN
```

`UNKNOWN` **НЕ ДОЛЖЕН** автоматически превращаться в `TRUE` или `FALSE` (`REQ-DATA-002`). Причины `UNKNOWN`: missing data; insufficient history; stale data; unresolved parameter; unsupported market; calculation failure; conflicting source values.

Распространение `UNKNOWN` вверх по цепочке определяется явно; для критического правила на live-входе `UNKNOWN` обычно приводит к `NO_TRADE`. Форма запрещает «безопасное» превращение `UNKNOWN → FALSE`, которое в TradAlert проявилось как `bb_z → 0.0` («идеально у среднего») и `risk_on_score → 0.5` («средний размер позиции») — оба сняли предохранитель именно там, где он был нужен.

---

## 6. Двойной учёт коррелирующих факторов

Форма фиксирует риск двойного счёта. Пример: `price above EMA20`, `price above EMA50`, `EMA20 slope`, `EMA50 slope`, `MACD above zero` могут частично измерять **один** trend-фактор.

Обязательные механизмы (детально — в спецификации стратегий и ранжирования):

- **signal groups** — правила, измеряющие один фактор, объединяются в группу;
- **correlation warnings** — предупреждение при добавлении коррелирующего правила;
- **contribution caps** — ограничение суммарного вклада группы;
- **ablation requirements** — маржинальный вклад проверяется отдельно (`22`, `26.2`);
- **запрет механического суммирования** весов без калибровки.

Особый случай — **бар с гэпом**: одно число (гэп) одновременно входит в ATR, RSI, MACD и bb_z, поэтому «независимые» правила на гэп-баре имеют корреляцию ≈1. Это фиксируется как `failure_mode` каждого правила, читающего эти индикаторы, и как property-тест на уровне системы (инъекция синтетического гэпа → правило либо помещает бар в карантин, либо трасса фиксирует потребление `gap_quarantine`).

> В TradAlert это была причина, по которой +9% гэп-бар «подтверждался» шестью формально независимыми гейтами и заодно раздувал собственный target через ATR.

---

## 7. Веса — до калибровки `UNSET`

Вес вклада правила (`effect.weight_parameter_ref`) — это параметр в реестре (`10`), а не число в теле правила. До калибровки:

```yaml
weight_parameter_ref: PARAMETER.WEIGHT.PRICE_ABOVE_EMA.001   # value: null, status: UNSET
```

Запрещено `Trend +18 / Volume +12 / Momentum +15` без формального метода калибровки, out-of-sample валидации, корреляционного контроля, sensitivity-анализа, версионированного набора параметров и ablation. Вес без этого — `UNSET`, и правило не переходит в runtime, пока критический вес не разрешён.

---

## 8. Инварианты формы (проверяются статически)

- правило с вердиктом имеет `discriminating_pair_ref`, иначе отклоняется (`REQ-VALIDATION-001`);
- `missing_data_policy` не содержит подстановки значения вместо `UNKNOWN` (`REQ-DATA-002`);
- `consumed_by` непусто для правила, участвующего в решении (иначе — декорация, `REQ-OUTPUT-001`);
- `scope` задан;
- `effect_type` принадлежит одному классу; смешение `HARD_GATE`/`VETO`/`SOFT_FACTOR`/`WARNING` запрещено;
- `evidence_status` по умолчанию `HYPOTHESIS`; `VALIDATED` — только со ссылкой на evidence record;
- критический `weight_parameter_ref` в статусе `UNSET` блокирует переход правила в runtime.
