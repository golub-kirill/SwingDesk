# SCREENER SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim` + derived from `registry/`

<!-- verbatim-sources: Module_33_Skrinery_v5.0.pdf, Module_32_Watchlist_v5.0.pdf -->

**Sources:** `Module_33_Skrinery_v5.0.pdf` (screener), `Module_32_Watchlist_v5.0.pdf` (watchlist).
Filter names are generated from `registry/course_index.yml`; normative text is verified by
`tools/verify_transcription.py`. Verified 2026-08-01.

---

## 1. What a screener is, and is not

> "Скринер фильтрует торговую вселенную по измеримым признакам и создаёт кандидатов, а не готовые
> ордера. Любой результат затем проходит market, sector, 1Y, 3M, 30D и risk review."

And the prohibition:

> "Запрещён бесконечный список без trigger/stop или автоматический ордер из результата скринера.
> Доказательство: Screener query/version, candidate card, rank/status history и причины Skip."

**Binding:** a screener produces candidates only. Two artifacts are mandatory alongside every run —
the **query and its version**, and the **skip reasons**. A screener result that cannot be reproduced
from its recorded query version is a defect.

## 2. The sixteen filters (M33, topics 479–494)

| Topic | Filter | Threshold in course |
|---|---|---|
| 479 | Фильтр по цене | none |
| 480 | Фильтр по капитализации | none |
| 481 | Фильтр по среднему объёму | none |
| 482 | Фильтр по относительному объёму | none |
| 483 | Фильтр по волатильности | none |
| 484 | Фильтр по ATR | none |
| 485 | Фильтр по тренду | none |
| 486 | Фильтр по близости к максимуму | none |
| 487 | Фильтр по относительной силе | none |
| 488 | Фильтр по пробою | none |
| 489 | Фильтр по откату | none |
| 490 | Фильтр по сжатию | none |
| 491 | Фильтр по гэпу | none |
| 492 | Фильтр по отчётности | none |
| 493 | Фильтр для short-selling | none |
| 494 | Ручная проверка результатов скринера | — |

**All sixteen thresholds are unspecified.** M33 contains no numeric values and its own verification
record reports zero recovered decision tables. Every one becomes a parameter-registry entry with
provenance `assumed`; an unset filter returns `SKIP`, never a pass-through.

Topic 494 is not a filter — it mandates **manual review of screener output**. The funnel is
`screen → human review → candidate`, never `screen → candidate`.

### Filter standards worth encoding

Volume filters (481, 482):
> "Нормализовать показатель по истории и времени, проверить dollar volume, spread, depth и
> совместимость с размером."

> "Запрещён вывод по абсолютному объёму или одной котировке без ценовой структуры. Доказательство:
> Relative volume/ATR%, spread snapshot, dollar volume и сравнение с типичными значениями."

**Absolute volume alone is prohibited** — volume must be normalised against its own history and time
of day, and checked for compatibility with the intended position size. This is the same
normalisation the one genuinely specified unit in the course uses: `RVOL: x 20D median` (M34-T513).

Volatility, ATR and gap filters (483, 484, 491):
> "Измерить масштаб в %, ATR и относительно ключевой структуры; адаптировать stop, size и способ
> исполнения."

Short filter (493):
> "Проверить borrow/fee/recall, ограничить размер, задать squeeze/gap scenario и отдельные exit
> rules."

**Shorts require borrow data**, which has no confirmed source (`VENDOR_COMPARISON.md`). Skip code
`BORROW` is `Automatic Skip`, so until a borrow source exists the honest behaviour is that short
candidates are automatically skipped — not that borrow is assumed available.

## 3. The nine-step pipeline

Identical in M32 and M33, and this is the screening runtime:

> Определить market regime USA/Canada.

> Оценить сектор, отрасль и relative strength.

> Подтвердить 1Y и 3M контекст.

> На 30D классифицировать setup.

> Записать trigger, entry zone и maximum entry.

> Определить stop, target и time stop.

> Рассчитать размер и portfolio overlap.

> Присвоить Trade/Watch/Skip и установить alerts.

> После исхода обновить статистику стратегии.

Steps run **in order**. Regime is determined first and gates everything downstream — consistent with
Appendix L's regime→strategy matrix. Size is computed only after stop and target exist (step 6
before step 7), matching the ordering law in `RISK_SPEC.md` §3.

## 4. The operational standard

| Элемент | Обязательное требование | Проверка / запрет |
|---|---|---|
| Контекст | Определены market regime, sector status и 1Y/3M структура | Контекст записан до trigger |
| Сетап | Условия потенциальной сделки формализованы | Два наблюдателя дают одинаковый статус |
| Trigger | Вход разрешает измеримое событие, а не впечатление | Точная цена/close/condition указана заранее |
| Invalidation | Stop связан с отменой идеи | Stop существует до расчёта размера |
| Trade/Watch/Skip | Каждый кандидат получает статус и причину | Нет кандидатов без следующего действия |

**`Два наблюдателя дают одинаковый статус`** is a testable property, not a platitude: setup
classification must be deterministic enough that two evaluations agree. It is the acceptance
criterion for every setup detector, and it belongs in `INVARIANTS.md` as a property test — the same
inputs must always produce the same classification.

**`Нет кандидатов без следующего действия`** means every screened instrument leaves the run with a
status and a reason. A screener that returns a list and stops is non-compliant.

## 5. Required candidate-card fields

Repeated across M32/M33/M34 definitions:

> "нужны market filter, sector filter, дневной setup, измеримый trigger, invalidation, maximum entry,
> ожидаемый путь и причины Skip. Без одного из критических полей сделка остаётся Watch."

Eight required fields, and the failure mode is specified: a missing critical field leaves the
candidate at **`Watch`**, not `Trade` and not an error. This maps onto `Candidate` and `Trade Plan`
in `JOURNAL_SCHEMA.md`.

## 6. The watchlist (M32, topics 467–478)

Twelve topics: Назначение watchlist · Основной список · Список потенциальных пробоев · Список
откатов · Список событийных акций · Список коротких позиций · Список активных позиций · Размер
watchlist · Ежедневное обновление · Удаление слабых кандидатов · Приоритизация сетапов · Создание
торгового плана на неделю.

**Six partitions**, which are views over one candidate set rather than six separate lists: main,
potential breakouts, pullbacks, event names, shorts, active positions.

The purpose statement is a constraint on the UI:

> "Он должен уменьшать неопределённость, а не хранить бесконечный список тикеров."

`Размер watchlist` (474) gives **no number** — parameter registry. `Удаление слабых кандидатов`
(476) requires an eviction rule, also unspecified.

The nine watchlist statuses and the caution about their overlap with the decision enum are in
`DECISION_STATE_MACHINE.md` §3.

## 7. Open items

- [ ] All sixteen filter thresholds, watchlist size, and the eviction rule — parameter registry,
      provenance `assumed`.
- [ ] `Фильтр по тренду`, `по пробою`, `по откату`, `по сжатию` require quantitative definitions of
      trend, breakout, pullback and contraction. These are the hardest authored items in the project
      and each needs a pre-registration before it is activated.
- [ ] Borrow source for filter 493, or ship with short candidates auto-skipped and say so.
- [ ] Whether the six watchlist partitions are stored as tags on one candidate or as separate
      collections. Tags fit the data better; confirm against the weekly-review funnel report.
