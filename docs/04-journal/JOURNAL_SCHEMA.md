# JOURNAL SCHEMA

**Status:** drafting · **Tier:** 4 (journal) · **Content:** `verbatim`

<!-- verbatim-sources: Appendix_G_Zhurnal_sdelok_v2.0.pdf -->

**Source of truth:** `Appendix_G_Zhurnal_sdelok_v2.0.pdf` page 2, extracted with
`pdftotext -enc UTF-8 -f 2 -l 2 <file> -`, verified 2026-08-01. Cross-referenced against
`Module_67_Torgovyi_zhurnal_v4.0.pdf` topics 984–1005.

**Appendix G is an entity-relationship model, already written.** It is the most directly
implementable artifact in the entire course: twelve entities with their field lists. This document
transcribes it and records what the modules add on top.

---

## 1. The twelve entities, verbatim

One source cell per line, checked independently:

```verbatim
Ticker, exchange, currency, sector, industry.
Date added, source, status history, rank.
Strategy/version, direction, context, quality grade.
Trigger, entry, max entry, stop, targets, time stop, skip.
Equity, risk $, risk/share, shares, open risk, buckets.
Timestamp, type, limit/stop, TIF, broker.
Timestamp, price, shares, commission, slippage.
Action, reason, old/new stop, risk change, screenshot.
Reason, fills, net P&L, R, holding period.
MFE, MAE, process score, errors, lesson.
1Y/3M/30D/30m screenshots, news/source documents.
Immutable initial plan and all later versions.
```

| Объект | Поля |
|---|---|
| `Instrument` | Ticker, exchange, currency, sector, industry. |
| `Candidate` | Date added, source, status history, rank. |
| `Setup` | Strategy/version, direction, context, quality grade. |
| `Trade Plan` | Trigger, entry, max entry, stop, targets, time stop, skip. |
| `Risk Snapshot` | Equity, risk $, risk/share, shares, open risk, buckets. |
| `Order` | Timestamp, type, limit/stop, TIF, broker. |
| `Fill` | Timestamp, price, shares, commission, slippage. |
| `Management` | Action, reason, old/new stop, risk change, screenshot. |
| `Exit` | Reason, fills, net P&L, R, holding period. |
| `Review` | MFE, MAE, process score, errors, lesson. |
| `Attachments` | 1Y/3M/30D/30m screenshots, news/source documents. |
| `Audit` | Immutable initial plan and all later versions. |

## 2. How the entities bind to the rest of the system

| Entity | Binding |
|---|---|
| `Instrument` | `currency` and `exchange` are mandatory, not derived — USA and Canada are never merged (`FAIL_CLOSED_POLICY.md`). Verified available from the data source. |
| `Candidate` | `status history` is a **history**, not a current value: the nine watchlist statuses (`DECISION_STATE_MACHINE.md` §3) with timestamps. `source` records which screener/version produced it. |
| `Setup` | `quality grade` — M68-T1017 defines a "standard scale" and **never states its range or weights**. Authored; parameter registry. |
| `Trade Plan` | `skip` holds one of the twelve skip codes (`CODES.md`). `max entry` is what makes the `LATE` code computable. |
| `Risk Snapshot` | Exactly the outputs of `RISK_SPEC.md` §1. `buckets` = sector/theme/currency/event exposure. Recomputed after every partial and stop change, never decremented. |
| `Order` | **This system does not place orders (D1).** The entity records orders the user placed manually, reported back. `broker` and `TIF` are recorded, not controlled. |
| `Fill` | Populated via the Telegram confirmation flow (D6). `slippage` feeds `Slippage R` in `STATISTICS_SPEC.md`. |
| `Management` | Every action carries `reason` **and** a timestamp — required by §3.8's human-judgment rule. `old/new stop` makes `WIDE_STOP` detectable. Telegram approves these actions (D6). |
| `Exit` | `Reason` is coded, not free text — see `EXIT_MODEL_SPEC.md`. `R` uses the **originally planned** risk as denominator (`RISK_SPEC.md` §2). |
| `Review` | `process score` feeds `Process compliance`. `errors` holds error codes from `CODES.md` with their severity. |
| `Attachments` | Chart capture at `1Y/3M/30D` and `30m` is a **required decision artifact**, not a convenience (`FAIL_CLOSED_POLICY.md` §5). Constrains `CHART_SPEC.md`. |
| `Audit` | The immutability mechanism. See §4. |

## 3. What Module 67 adds

M67 names 22 journal fields (topics 984–1005), most of which map onto Appendix G directly. Those
that are *not* obviously covered by an Appendix G field:

`Рыночный режим` (988) · `Секторный контекст` (989) · `Катализатор` (990) ·
`Эмоциональное состояние` (1002) · `Соблюдение плана` (1003) · `Выводы` (1005)

Regime, sector context and catalyst belong on `Setup` (its `context` field). Emotional state, plan
compliance and lessons belong on `Review`.

M67's `FAIL-CLOSED` clauses imply further required fields, none of which appear in the Appendix G
column lists but all of which are mandated in prose:

- `Risk snapshot: equity, risk %, risk $, entry, stop, costs, shares, open/bucket exposure.` — note
  **`risk %` and `costs`**, absent from Appendix G's `Risk Snapshot`.
- `Order ticket, timestamp, TIF, fills, commission, slippage и broker reconciliation.` — a
  **reconciliation flag**.
- `Exit plan до входа, management log, MFE/MAE и причина фактического выхода.` — the exit plan must
  exist **before entry**, so it is a `Trade Plan` field, not an `Exit` field.
- `Initial stop, chart level, planned/actual risk и audit всех изменений.` — **initial stop must be
  stored separately from current stop**, and planned risk separately from actual. This is what makes
  the R denominator invariant enforceable rather than aspirational.
- `Timestamped state, error code, process score, стоимость в R и контроль следующей недели.` —
  **cost of a violation, in R**.

## 4. Immutability

Verbatim from M67, and stated on page 1 of every appendix:

> "Скопировать рабочую версию, заполнить source/as-of/version, не переписывать исходную запись задним
> числом. Пустое обязательное поле или конфликт данных приводит к Pause/Research/Skip."

And the `Audit` entity itself: `Immutable initial plan and all later versions.`

**Binding — this is a storage-model constraint, not a policy someone remembers to follow:**

1. The initial `Trade Plan` and initial `Risk Snapshot` are written once and are **immutable**.
2. Every later change is a **new version**, linked to the original; nothing is updated in place.
3. Every record carries `date`, `version`, `owner`, `source/as-of`.
4. A required field left empty, or a data conflict, forces `Pause`/`Research`/`Skip` — the record
   cannot be saved in a half-valid state and then fixed later.
5. Error `HINDSIGHT` (`Переписывание плана`, `Major`) has as its required control
   `Immutable pre-trade snapshot` — so the schema *is* the control. If plans were mutable, the
   control would not exist.

Consequence for storage: append-only tables with `valid_from` / superseded-by links, not
`UPDATE`-in-place rows. This is the same bitemporal discipline as `POINT_IN_TIME_SPEC.md`, applied
to decisions instead of market data.

## 5. Open items

- [ ] `quality grade` (Setup) and `process score` (Review) both need a scale. M68-T1017 names a
      "standard scale" and defines none.
- [ ] Cardinality: `Trade Plan` → `Order` → `Fill` is presumably one-to-many at each step
      (partials), and `Exit.fills` is plural, which confirms it. Not stated by the course; author it.
- [ ] Whether a `Candidate` that is skipped still requires a `Trade Plan`. M32/M33's rule that no
      candidate may lack a next action suggests the `skip` field on `Trade Plan` covers it, meaning
      a plan exists even for skips. Confirm.
- [ ] Where the Telegram approval record lives — `Management.reason` plus timestamp appears
      sufficient, but the human-judgment rule (`LIFECYCLE_AND_LAYERS.md` §6) also requires the
      *observation shown* and the *bounded choice offered* to be recorded. Those have no field yet.
