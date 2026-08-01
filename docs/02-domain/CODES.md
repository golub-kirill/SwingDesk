# CODES — skip reasons and error codes

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim`

<!-- verbatim-sources: Appendix_N_Prichiny_propuska_sdelki_v2.0.pdf, Appendix_O_Tipichnye_oshibki_v2.0.pdf -->

**Source of truth**

| Table | File | Page | Extraction |
|---|---|---|---|
| Skip reasons | `Appendix_N_Prichiny_propuska_sdelki_v2.0.pdf` | 2 | `pdftotext -enc UTF-8 -f 2 -l 2 <file> -` |
| Error codes | `Appendix_O_Tipichnye_oshibki_v2.0.pdf` | 2 | `pdftotext -enc UTF-8 -f 2 -l 2 <file> -` |

Both tables are transcribed unchanged. The `Причина` / `Описание` / `Действие` / `Контроль` columns
are the course's own wording; where the source is Russian, an English gloss is given in a separate
column and is clearly **not** part of the source. Column alignment was reconstructed from the PDF
text layer, which emits table columns as separate blocks — the ordering of all four columns was
checked position-by-position against the rendered table.

Changing any row here is a course-version change, not an edit. See
`docs/04-journal/AUDIT_AND_IMMUTABILITY.md`.

---

## 1. Skip reasons (Appendix N)

Twelve codes with stable primary keys. Every candidate that does not become a trade records exactly
one of these, plus free-text detail. A candidate with no next action is a defect
(`SCREENER_SPEC.md`).

| Код | Причина (source) | Действие (source) | Gloss (not source) |
|---|---|---|---|
| `DATA` | Stale/missing data, wrong split/currency. | Automatic Skip until corrected. | — |
| `LIQ` | Spread/dollar volume/depth incompatible. | Skip or smaller universe category. | — |
| `EVENT` | Unknown/near earnings or binary event. | Skip or separate event strategy. | — |
| `REGIME` | Strategy incompatible with market regime. | Watch/Skip. | — |
| `SECTOR` | Sector/industry contradicts thesis. | Lower rank or Skip. | — |
| `LATE` | Price beyond maximum entry. | No chase; wait new setup. | — |
| `STOP` | No logical invalidation or stop too wide. | Skip. | — |
| `RISK` | Open/sector/currency/event limit exceeded. | Skip or choose better candidate. | — |
| `CORR` | Duplicate economic exposure. | Choose one or reduce. | — |
| `BORROW` | Short borrow unavailable/unstable/expensive. | Automatic Skip. | — |
| `TECH` | Broker/platform/journal mismatch. | Pause new entries. | — |
| `PSYCH` | Risk state or discipline threshold violated. | Reduced/Pause. | — |

**Automatic codes.** `DATA` and `BORROW` state `Automatic Skip` — the system raises them without a
human decision. `TECH` states `Pause new entries`, which is a system-wide state change, not a
per-candidate one.

**Unquantified terms.** `stop too wide` (`STOP`), `limit exceeded` (`RISK`), and
`discipline threshold violated` (`PSYCH`) have **no threshold in the course**. Each becomes a
required parameter in `PARAMETER_REGISTRY.md` with provenance `assumed`, and a component whose
parameter is unset returns the corresponding skip code rather than a guess.

---

## 2. Error codes (Appendix O)

Twelve codes. The `Контроль` column is not advice — it is a list of software controls this system
must implement, and each maps to a requirement in `FRD.md`.

| Код | Описание (source) | Тяжесть | Контроль (source) | Gloss of the Russian description |
|---|---|---|---|---|
| `NO_PLAN` | Вход без Trade Plan | `Major` | Блокировать ордер без Ready/Trade card. | Entry without a Trade Plan |
| `CHASE` | Entry beyond maximum | `Moderate/Major` | Late status and order guard. | — |
| `NO_TRIGGER` | Сетап без измеримого события | `Major` | Trigger field required. | Setup without a measurable event |
| `WIDE_STOP` | Расширение stop | `Critical` | Hard violation protocol. | Widening the stop |
| `AVG_DOWN` | Добавление к невалидной позиции | `Critical` | Separate setup and total-risk gate. | Adding to an invalidated position |
| `OVERSIZE` | Risk above plan | `Critical` | Independent position-size calculator. | — |
| `CORRISK` | Скрытая концентрация | `Major` | Risk buckets/stress test. | Hidden concentration |
| `EARLY_EXIT` | Страх до exit rule | `Moderate` | Tested exit + lower size. | Fear ahead of the exit rule |
| `LATE_EXIT` | Игнорирование exit rule | `Major` | Alerts/bracket/manual fallback. | Ignoring the exit rule |
| `REVENGE` | Сделка для возврата убытка | `Critical` | Pause after threshold. | A trade taken to win back a loss |
| `HINDSIGHT` | Переписывание плана | `Major` | Immutable pre-trade snapshot. | Rewriting the plan after the fact |
| `DATA_ERR` | Торговля при ошибке данных | `Critical` | Fail-closed gate. | Trading on erroneous data |

### Severity enum

`Moderate` · `Moderate/Major` · `Major` · `Critical` — exactly four values, in that order.
`Moderate/Major` is a single value in the source, not a range to be resolved at runtime.

### Controls this system owes

Six of the twelve controls are structural and constrain the architecture, not just a screen:

| Code | Control | Where it is discharged |
|---|---|---|
| `NO_PLAN` | order/action blocked without a `Ready`/`Trade` card | `DECISION_STATE_MACHINE.md` |
| `OVERSIZE` | position size computed by an **independent** calculator | `RISK_SPEC.md` — one implementation, no re-inlining |
| `HINDSIGHT` | immutable pre-trade snapshot | `AUDIT_AND_IMMUTABILITY.md` |
| `DATA_ERR` | fail-closed gate | `FAIL_CLOSED_POLICY.md` |
| `WIDE_STOP` | hard violation protocol | `RISK_SPEC.md` + `AUDIT_AND_IMMUTABILITY.md` |
| `CORRISK` | risk buckets / stress test | `RISK_SPEC.md` (`Sector risk = Σ risk одной темы/сектора`) |

**Unquantified term.** `REVENGE` → `Pause after threshold` gives no threshold. Parameter registry
entry required; until it has a value, the control cannot be enforced automatically and that fact is
displayed rather than hidden.

---

## 3. Implementation constraint

These two lists are enums with stable keys. The verification script asserts that the code enums
equal these tables exactly — 12 skip codes and 12 error codes, same spelling, same order. Adding a
thirteenth code of either kind is a course-version change and requires a dated amendment here first.
