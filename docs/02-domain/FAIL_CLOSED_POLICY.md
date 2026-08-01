# FAIL-CLOSED POLICY

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim`

<!-- verbatim-sources: Module_33_Skrinery_v5.0.pdf, Course_Production_Rules_v3.8.md -->

**Source of truth:** the `FAIL-CLOSED · резервный процесс`, `MODULE GATE`, `GATE МОДУЛЯ` and
`AUTOMATIC FAIL` blocks that appear in every module. Transcribed from
`Module_33_Skrinery_v5.0.pdf` (pages 30–31), verified 2026-08-01 with
`pdftotext -enc UTF-8 <file> -`. The block is byte-identical across the modules sampled, which is
why it is a system-wide policy rather than a screener detail.

This is the single most important document in tier 2. It is the reason the system may say "no" to
itself, and it is stated by the course as an absolute, not a preference.

---

## 1. The cover rule

Printed on the cover of all 116 files:

> `Fail-closed: missing/stale/conflicting data → no new trade`

## 2. The degradation table

Five failure modes, each with a mandated manual process and an explicit **return condition**.
Verbatim:

| Отказ / неопределённость | Ручной безопасный процесс | Условие возврата |
|---|---|---|
| Нет/сомнительны данные | Остановить новые решения; использовать второй источник и последний валидный snapshot. | Freshness, symbol/currency, corporate actions и event time подтверждены. |
| Сбой брокера/платформы | Открыть ручной список positions/shares/stops/targets/events; управлять через доступный резервный канал. | Позиции и ордера reconciled; protective orders подтверждены. |
| Сбой скринера/автоматизации | Использовать ограниченный ручной universe и checklist; автоматические сигналы считать недействительными. | Logs проверены, причина устранена, повторный run совпал с контрольным. |
| Неясен риск или правило | Статус Watch/Skip; новый ордер запрещён. | Полная карточка и risk snapshot заполнены без предположений. |
| Нарушение/эмоциональная потеря контроля | Pause или reduced risk по risk-off ladder. | Review завершён и выполнены формальные критерии возврата. |

**What each row obliges this system to build**

| Row | Obligation | Where |
|---|---|---|
| 1 | Last-valid snapshot must exist and be reachable — you cannot "use the last valid snapshot" without a bitemporal store. Freshness, symbol/currency, corporate-action and event-time checks are the four named return gates. | `POINT_IN_TIME_SPEC.md`, `DATA_QUALITY_SPEC.md` |
| 2 | A manual position/stop/target/event list must be printable **without the platform running**. Return requires reconciliation. | `runbooks/`, `RECONCILIATION_SPEC.md` |
| 3 | Automated signals are **invalid**, not merely suspect, during a screener failure. Return requires a **repeat run matching a control** — so a reproducible control run must exist. | `DETERMINISM_SPEC.md`, `runbooks/` |
| 4 | Unclear risk forces `Watch`/`Skip`. Return requires a complete card and risk snapshot **filled without assumptions** — i.e. no defaults substituted for missing values. | `DECISION_STATE_MACHINE.md`, `PARAMETER_REGISTRY.md` |
| 5 | A risk-off ladder must exist as a named, pre-set mechanism. **The course names it and never quantifies it** — parameter registry entry, provenance `assumed`. | `RISK_SPEC.md`, `PARAMETER_REGISTRY.md` |

Row 3's return condition is the strictest thing in the course: *"повторный run совпал с
контрольным"* — a re-run must match a control run. That is a determinism requirement stated as an
operating procedure, and it is why `DETERMINISM_SPEC.md` is not optional engineering taste.

## 3. Non-compensation

Verbatim, `AUTOMATIC FAIL`:

> "Модуль 33: если required data отсутствуют, устарели, противоречат друг другу или риск невозможно
> ограничить, новое действие запрещено. Нужны Pause/Research и запись причины; **балл или
> дополнительный индикатор не компенсируют critical fail.**"

And from `MODULE GATE`:

> "Критический отказ не компенсируется баллом или дополнительным индикатором."

And from §3.8 of the production rules:

> "critical gates remain non-compensatory … A score or agreement among several weak indicators cannot
> override missing data, invalid risk, unavailable borrow, incompatible execution, or another
> critical failure."

**Binding, and architecturally load-bearing:** critical gates are evaluated **outside** any scoring
or ranking path and their result cannot be outvoted. Any design in which a composite score can clear
a critical gate is wrong by construction, no matter how the weights are set. This forbids the whole
"weighted signal score decides" pattern for anything gate-related.

## 4. The module gate

Verbatim:

> "Для тем 479–494 решение разрешено только при свежих данных, явном lifecycle stage, измеримом
> критерии, заранее записанном invalidation и допустимом риске. Missing, stale, incomplete или
> contradictory required data означают Research/Watch/Skip/Pause, а не догадку."

Five preconditions for **any** decision:

1. fresh data
2. an explicit lifecycle stage
3. a measurable criterion
4. an invalidation **recorded in advance**
5. acceptable risk

Absent any one → `Research` / `Watch` / `Skip` / `Pause`. Verbatim: *"а не догадку"* — **not a
guess**. This is the sentence that turns an unset parameter into a `Skip` rather than a default.

## 5. Required evidence

Verbatim, `Обязательные доказательства`:

> Дата и версия материала/правил. Краткое собственное определение и главный вывод. Пример
> правильного и неправильного применения. Screenshots 1Y, 3M и 30D; 30m только при исполнении.
> Market/sector context и использованный benchmark. Trigger/условие, invalidation и причины
> Trade/Watch/Skip.

Note `Screenshots 1Y, 3M и 30D; 30m только при исполнении` — chart capture is a *required artifact*
of a decision, not a UI nicety. It constrains `CHART_SPEC.md` and the journal's `Attachments`
entity.

## 6. How this maps to skip and error codes

| Failure | Code | Action |
|---|---|---|
| Stale/missing data, wrong split/currency | `DATA` | `Automatic Skip until corrected` |
| Broker/platform/journal mismatch | `TECH` | `Pause new entries` |
| Risk state or discipline threshold violated | `PSYCH` | `Reduced/Pause` |
| Trading on erroneous data | `DATA_ERR` (`Critical`) | `Fail-closed gate` |

See `CODES.md` for the full twelve of each.

## 7. Implementation constraints

1. **Fail-closed is the default for the decision path.** A component that cannot evaluate returns a
   coded refusal. It never returns a neutral or optimistic value.
2. **Data fetching is fail-open; decisions are fail-closed.** A fetch may degrade to a cached
   snapshot; a *decision* on degraded data may not proceed. These are different layers and the
   distinction is deliberate — conflating them is how "fail-open everywhere" quietly becomes
   "traded on stale data".
3. **An unset parameter is a refusal, not a default.** From §4, *"а не догадку"*.
4. **No silent reconciliation.** From §3.6 layer 1: conflicting providers stay visible.
5. **Every refusal is recorded** with its code, the failing input, and its as-of time — the trace in
   `LIFECYCLE_AND_LAYERS.md` §3 requires `причину отказа` as a stored field.

## 8. Open items

- [ ] The **risk-off ladder** (row 5) is named but never quantified anywhere in the course. Needs
      levels and triggers — owner input, recorded as `assumed` until validated.
- [ ] `DATA_QUALITY_SPEC.md` must define the four row-1 return gates concretely (freshness window,
      symbol/currency check, corporate-action check, event-time check). None carries a number in the
      course.
