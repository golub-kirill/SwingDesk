# DECISION STATE MACHINE

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim`

<!-- verbatim-sources: Module_33_Skrinery_v5.0.pdf, Module_32_Watchlist_v5.0.pdf, Module_69_Statistika_strategii_v4.0.pdf -->

**Sources**

| Enum | File | Section | Verified |
|---|---|---|---|
| Candidate decision | `Module_33_Skrinery_v5.0.pdf` | `DECISION TABLES` | 2026-08-01 |
| Module gate | `Module_33_Skrinery_v5.0.pdf` | `MODULE GATE` | 2026-08-01 |
| Watchlist status | `Module_32_Watchlist_v5.0.pdf` | topic 467, `M32-T0467-v5.0` | 2026-08-01 |
| Acceptance | `Module_69_Statistika_strategii_v4.0.pdf` | `DECISION TABLES` | 2026-08-01 |
| Checklist terminal states | module footers + Appendices E, H, P, T | `Итог:` line | 2026-08-01 |

The course defines **five separate enums** for five different objects. They are not variants of one
another and must not be collapsed into a single status column.

---

## 1. Candidate decision — 4 states

The decision attached to a candidate. Verbatim, including the `Следующее действие` column, which is
normative and not advice:

| Статус | Критерий | Следующее действие |
|---|---|---|
| `Trade / Выполнить` | Все обязательные условия выполнены; данные свежие; риск и исполнение допустимы. | Действовать только по записанному плану. |
| `Watch / Подготовить` | Контекст есть, но trigger, цена или подтверждение ещё отсутствуют. | Установить alert; ордер не отправлять. |
| `Skip / Отказ` | Критический фильтр нарушен, entry Late, stop неясен или portfolio risk превышен. | Записать причину; не искать оправдание. |
| `Pause / Блокировка` | Ошибка данных, брокера, дисциплины или превышение loss limit. | Новые сделки запрещены до устранения причины. |

**Binding on this system**

- `Watch` **must** create an alert and **must not** create an order or an order-equivalent action.
- `Skip` **requires** a reason — one of the twelve codes in `CODES.md`. A `Skip` with no code is a
  defect, and "нет кандидатов без следующего действия" (`ОПЕРАЦИОННЫЙ СТАНДАРТ`, M32/M33) makes a
  candidate with no decision a defect too.
- `Pause` is **not** a per-candidate state despite living in this table. Its criteria (data, broker,
  discipline, loss limit) are account-wide, and its action — "новые сделки запрещены до устранения
  причины" — blocks every candidate. Model it as a system state that suppresses the whole scan, and
  record which condition raised it.

## 2. Module gate — 3 states

Applied to a *range of components*, not to a candidate. Verbatim:

| Gate | Критерий |
|---|---|
| `PASS` | Все required inputs свежие; gate/invalidation/risk записаны |
| `PAUSE` | Источник неясен, данные конфликтуют или требуется ручная проверка |
| `SKIP` | Нет обязательного поля, допустимого риска или воспроизводимого критерия |

Accompanying rule, verbatim: *"Критический отказ не компенсируется баллом или дополнительным
индикатором."* See `FAIL_CLOSED_POLICY.md` §3.

## 3. Watchlist status — 9 states

Verbatim from `M32-T0467-v5.0`:

> "Watchlist — очередь подготовленных решений со статусами Research, Developing, Watch, Ready,
> Triggered, Trade, Late, Invalid и Skip. Он должен уменьшать неопределённость, а не хранить
> бесконечный список тикеров."

```
Research · Developing · Watch · Ready · Triggered · Trade · Late · Invalid · Skip
```

**Note the overlap and the trap.** `Watch`, `Trade` and `Skip` appear in *both* this enum and the
candidate-decision enum, and `Late` appears here and as a skip code (`CODES.md` → `LATE`). They are
the same words for different objects. The schema keeps them in **separate columns**
(`watchlist_status` vs `decision`); it does not merge them, and code must not compare across them.

The course states no transition rules between these nine. Transitions are therefore **authored**,
recorded in this document once designed, and any transition not listed is rejected — the enum is
closed but the graph is currently unspecified. *(Open item, see §6.)*

## 4. Acceptance — 4 states

Applied to a *rule or strategy* under evaluation, not to a candidate. Verbatim from M69:

| Статус | Критерий | Следующее действие |
|---|---|---|
| `Принять` | Правило подтверждено данными, версией и проверяемым артефактом. | Использовать в пределах доказанной области. |
| `Продолжить сбор` | Выборка мала или результат нестабилен. | Не менять систему; собрать новые наблюдения. |
| `Исправить процесс` | Выявлено повторяющееся управляемое нарушение. | Добавить checklist/техническую блокировку. |
| `Остановить` | Критический риск, leakage или техническая ошибка. | Приостановить применение и провести аудит. |

**Binding:** `Продолжить сбор` explicitly forbids changing the system while collecting — this is the
course's own anti-tinkering rule and it maps directly to the pre-registration stopping rule in
`PREREG_TEMPLATE.md`. `Использовать в пределах доказанной области` means an accepted rule carries
its applicability limits with it; acceptance is never global.

## 5. Checklist terminal states — two distinct sets

Measured across all appendices and the module set on 2026-08-01 by extracting every `Итог:` line:

| Set | Occurrences | Where |
|---|---|---|
| `Ready · Research · Watch · Skip · Pause · Error` | 28 | module reusable checklists |
| `Complete · Research · Pause · Skip · Error` | 10 | **exclusively** Appendices E, H, P, T |

This is **not** a contradiction. The four appendices are worksheets that are *completed*; the module
checklists gate a *decision*, so they carry `Ready` and `Watch` instead of `Complete`. The split is
clean — no file mixes them.

Two enums, two object types:

- `ChecklistOutcome` (worksheet): `Complete | Research | Pause | Skip | Error`
- `DecisionChecklistOutcome` (module gate): `Ready | Research | Watch | Skip | Pause | Error`

## 6. Open items

- [ ] **Watchlist transition graph — AUTHORED 2026-08-24 in `DR-020`, awaiting ratification** (§3).
      The nine states exist; the legal transitions did not, and that gap is why `Trade` is
      unreachable in code — measured across the live application layer, the decision token `Skip`
      appears in seventeen places, `Watch` in one, and `Trade` in none.
      `DR-020` authors the graph and decides no number: `Trade` is reachable only through
      `Ready → Triggered → Trade`, `Skip` from every pre-position state, and `Late`/`Invalid`/`Skip`
      end the CYCLE rather than the instrument. **It stays open here until the record is ratified**,
      at which point the graph is transcribed into §3 and enforced — an unconstrained status field
      still degrades into free text, and a proposed record does not constrain anything yet.
- [ ] **`Pause` scope** (§1). Modelled here as account-wide, which follows from its criteria and its
      action, but the course does not say so explicitly. Confirm with the owner before implementing.
- [ ] Confirm no sixth enum exists in the modules not yet swept (M45–58, M88–93 were sampled for
      other purposes and showed the same four-state decision table).

## 7. Implementation constraint

Five enums, five columns, no merging. The verification script asserts each enum's membership and
cardinality against this document: 4 · 3 · 9 · 4 · (5 and 6). Adding a state is a course-version
change and requires a dated amendment here first.
