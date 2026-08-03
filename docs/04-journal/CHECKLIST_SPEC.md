# CHECKLIST SPEC

**Status:** drafting · **Tier:** 4 (journal) · **Content:** `verbatim`

<!-- verbatim-sources: Appendix_E_Predtorgovyi_chek_list_v2.0.pdf, Appendix_H_Ezhenedelnyi_obzor_v2.0.pdf, Appendix_P_Polnyi_zhiznennyi_tsikl_sdelki_v2.0.pdf, Appendix_T_Professionalnyi_chek_list_treidera_v2.0.pdf -->

**Sources:** Appendices E, H, P and T, extracted with `pdftotext -enc UTF-8`, verified 2026-08-01.

**84 checklist items across four checklists**, counted from the extracted text:
E 18 · H 13 · P 19 · T 34. (T additionally carries 6 concluding system constraints, transcribed in
§5, which are statements rather than checkable items.)

These four are the only appendices using the worksheet terminal-state set
`Complete · Research · Pause · Skip · Error` — see `docs/02-domain/DECISION_STATE_MACHINE.md` §5.

Every checklist persists `Дата / время`, `Версия`, `Владелец` and exactly one terminal state.

---

## 1. Appendix E — pre-trade checklist (18 items)

```verbatim
Тикер, биржа и валюта проверены.
Инструмент входит в допустимую торговую вселенную.
Данные свежие; corporate actions учтены.
Market regime USA/Canada записан.
Сектор/отрасль и benchmark проверены.
1Y и 3M поддерживают идею.
30D setup соответствует версии стратегии.
Trigger измерим и ещё не Late.
Entry zone и maximum entry записаны.
Stop связан с invalidation.
Earnings и другие события проверены.
Spread, dollar volume и expected slippage допустимы.
Risk $ и shares рассчитаны заново.
Open risk, sector bucket, currency и event exposure допустимы.
Order type и partial-fill/gap сценарий понятны.
Target, trailing, failure exit и time stop записаны.
No-trade/Skip conditions не выполнены.
Alert и резервный ручной план готовы.
```

**Generated since 2026-08-02** — `registry/checklists.yml` is parsed from the verbatim block above,
so the item text is never hand-copied a third time, and `swingdesk.application.checklist` fills it
per candidate.

**Four of the eighteen are answerable today, not twelve.** The paragraph below says twelve are
machine-checkable *given the data the system already holds*, and the system does not hold all of it
yet. Rather than tick them anyway, each unanswerable item reports `unavailable` and names what is
missing — nine of them do. An `unavailable` item is a gap in the **system**, so it is shown beside
the passes and counted as unanswered; demoting it to a human question would hide the gap behind a
person and make the coverage look better than it is.

| Answerable now | Blocked on |
|---|---|
| E01 identity · E13 risk recomputed · E16 time stop · E17 no skip condition | E02 universe rule not applied · E03 corporate actions · E04 regime not wired · E05 no sector source · E08 no trigger/max entry · E09 no maximum entry · E11 no event calendar · E12 no spread data · E14 no exposure buckets |

Twelve of these are **machine-checkable** given the data the system already holds — ticker/exchange/
currency, universe membership, data freshness, regime recorded, sector/benchmark, trigger
measurability and `Late` status, entry zone and max entry present, stop linked to invalidation,
earnings proximity, spread/dollar-volume/slippage, risk and shares recomputed, exposure limits. The
system should pre-tick those and present them as evidence, not as questions.

`Risk $ и shares рассчитаны заново` is notable: **recomputed**, not carried forward. Consistent
with `RISK_SPEC.md` §2.

## 2. Appendix H — weekly review (13 items)

```verbatim
Broker reconciliation завершён.
Net P&L, R и расходы рассчитаны.
Drawdown и максимальный open risk проверены.
Результаты разделены по strategy/version/regime/country/sector.
Entry, exit, slippage, MFE и MAE проверены.
Outcome и Decision Quality разделены.
Major/critical violations перечислены.
Лучшее решение недели выбрано.
Худшее решение недели выбрано.
Watchlist funnel и Skip quality проверены.
Market regime и sector leadership обновлены.
Risk level следующей недели выбран.
Одна измеримая задача улучшения записана.
```

Item 4 is the source of the mandatory reporting axes in `STATISTICS_SPEC.md` §4.

`Watchlist funnel и Skip quality проверены` requires the system to report the funnel — how many
candidates entered, how many were skipped, and under which codes. Skip *quality* means the skip
reasons themselves are reviewed, so skip codes must be aggregable.

`Outcome и Decision Quality разделены` recurs in E, H, P and T. A good outcome from a bad decision
is a distinct, named category (M68 topics 1006–1009) and the UI must never collapse the two.

## 3. Appendix P — full trade lifecycle (19 items)

```verbatim
Идея появилась из разрешённого процесса поиска.
Market regime и risk level определены.
Sector/industry/commodity context проверен.
1Y/3M/30D screenshots сохранены.
Setup и strategy version записаны.
Trigger, entry zone и maximum entry записаны.
Invalidation, stop, targets и time stop записаны.
Event, liquidity, borrow и currency проверены.
Position size и portfolio fit рассчитаны.
Order type и fail scenarios проверены.
Fills импортированы и actual risk пересчитан.
Management actions соответствуют правилам.
Partials и stop changes записаны.
Final exit имеет код причины.
Net P&L, R, MFE, MAE и holding period рассчитаны.
Outcome и Decision Quality оценены отдельно.
Ошибки и стоимость нарушения классифицированы.
Статистика стратегии/версии обновлена.
Одна применимая корректировка процесса сформулирована.
```

`Final exit имеет код причины` — exit reasons are **coded**, confirming the requirement in
`JOURNAL_SCHEMA.md`. `Ошибки и стоимость нарушения классифицированы` requires the cost of a
violation in R, which is a journal field with no Appendix G column.

## 4. Appendix T — master checklist (34 items, 6 phases)

The phases are the operating cadence: `До недели` (6) · `До сессии` (6) · `Перед ордером` (6) ·
`Во время позиции` (5) · `После сделки` (6) · `Аварийный контроль` (5).

```verbatim
Данные и брокер сверены.
USA/Canada regime определён.
Sector map и commodities/CADUSD проверены.
Открытые позиции и events обновлены.
Weekly watchlist и risk budget созданы.
No-trade scenarios записаны.
Overnight/futures/news проверены.
Открытые позиции и gaps проверены первыми.
Daily Priority 1 ограничен.
Entry/exit plans и sizes пересчитаны.
Alerts установлены.
No-trade condition сохранено.
Тикер/биржа/валюта/направление верны.
Setup/trigger сохранены.
Price не Late.
Stop и risk/share верны.
Shares и portfolio fit подтверждены.
Order type и gap/partial scenario понятны.
Stop не расширяется.
Добавление только по отдельному setup и total-risk check.
No Action допускается.
Management action имеет правило и timestamp.
Event/sector/market changes контролируются.
Fills и costs импортированы.
Screenshots сохранены.
R/MFE/MAE/slippage рассчитаны.
Outcome и Decision Quality разделены.
Error code и process score записаны.
Статистика версии обновлена.
Ручной список позиций/stops/targets доступен.
Broker — источник фактических позиций.
При stale data или mismatch новые сделки блокируются.
После critical violation активируется Pause.
Возврат возможен только по записанным критериям.
```

Four items are architectural rather than procedural:

| Item | Consequence |
|---|---|
| `Открытые позиции и gaps проверены первыми` | Open positions are processed **before** new candidates. This is a run-order constraint on the daily pipeline, not a suggestion. |
| `No Action допускается` | Doing nothing is a valid, recordable management action. The UI must offer it explicitly, or it will be under-recorded. |
| `Broker — источник фактических позиций` | The broker is authoritative for positions, not the journal. Any mismatch is a reconciliation failure, and the journal yields. |
| `Ручной список позиций/stops/targets доступен` | A printable fallback list must exist and work with the system down — `FAIL_CLOSED_POLICY.md` row 2. |

`Daily Priority 1 ограничен` states a limit exists but gives **no number** — parameter registry.

## 5. Appendix T — concluding constraints

Six statements, system-level rather than checkable:

```verbatim
Основной рабочий график — 1D; 1Y и 3M задают контекст, 30D формирует план, 30m только исполняет.
Canada и USA анализируются с учётом различий бирж, валюты, liquidity, sectors, commodities и events.
Каждый модуль имеет standard, playbook, checklist, decision table, error controls и evidence requirements.
Каждая сделка проходит полный жизненный цикл и оставляет audit trail.
Размер растёт только после проверяемых gates, а не после одной прибыльной серии.
```

The first is the authoritative timeframe statement, and it resolves the ambiguity Module 29
introduces: **1D is the working chart, 1Y and 3M are context, 30D forms the plan, 30m only
executes.** Note that this sentence does **not** mention a 1H frame. The owner's decision to store
1H as a confirmation/trigger layer is therefore an extension beyond the course, not a transcription
of it, and is recorded as such in `docs/03-data/VENDOR_COMPARISON.md`.

## 6. Implementation constraints

1. A checklist is a **record**, not a UI convenience: it persists date/time, version, owner and one
   terminal state, and it is immutable once submitted (`AUDIT_AND_IMMUTABILITY.md`).
2. Items the system can verify are **pre-filled with their evidence**, not asked as questions. Items
   requiring judgment stay as bounded human choices per `LIFECYCLE_AND_LAYERS.md` §6.
3. A checklist with an unanswered required item cannot reach `Complete` — it takes
   `Research`/`Pause`/`Skip`, per the appendix cover rule.
4. Checklist completion feeds `Process compliance` in `STATISTICS_SPEC.md`.

## 7. Open items

- [ ] `Daily Priority 1 ограничен` — no number.
- [ ] Which E items the system can genuinely auto-verify at v1 depends on data availability
      (`borrow` in particular has no confirmed source — see `VENDOR_COMPARISON.md`).
- [ ] Whether P and T overlap enough to merge in the UI, or whether both are presented. They are
      separate records in the course; keep both until there is evidence the duplication costs more
      than it catches.
