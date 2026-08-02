# AUDIT AND IMMUTABILITY

**Status:** drafting · **Tier:** 4 (journal) · **Content:** `verbatim` + authored

<!-- verbatim-sources: Appendix_G_Zhurnal_sdelok_v2.0.pdf, Module_79_Avtomatizatsiya_rabochego_protsessa_v4.0.pdf, Appendix_O_Tipichnye_oshibki_v2.0.pdf -->

---

## 1. The rule, stated on every appendix

> "Скопировать рабочую версию, заполнить source/as-of/version, не переписывать исходную запись задним
> числом. Пустое обязательное поле или конфликт данных приводит к Pause/Research/Skip."

Three obligations in one sentence: fill `source` / `as-of` / `version`; never rewrite the original
record retroactively; and an empty required field or a data conflict forces
`Pause`/`Research`/`Skip` rather than a partial save.

And the journal rule, which appears **identically in seven modules** — 60, 74, 79, 82, 87, 88 and
96 — making it a system-wide rule rather than one module's opinion:

> "Журнал связывает идею, план, risk snapshot, orders, fills, управление, выход и review. Исходный
> план неизменяем; исправления создают новую версию с audit trail."

The `Audit` entity in Appendix G exists for exactly this: `Immutable initial plan and all later
versions.`

## 2. The schema is the control

Error `HINDSIGHT` (`Переписывание плана`, `Major`) has as its **required control**:
`Immutable pre-trade snapshot`.

That is the important structural point: the course does not ask the operator to refrain from
rewriting plans. It requires that rewriting be **impossible**. If plans were mutable, the control
would not exist — so immutability is a storage guarantee, not a discipline.

## 3. What this means mechanically

| Rule | Consequence |
|---|---|
| No `UPDATE` on a fact or a plan | append-only tables with supersession links |
| The initial `Trade Plan` and initial `Risk Snapshot` are written once | they are what R and every violation are measured against |
| A correction is a **new version** | linked to the original, with date, author and reason |
| Nothing is deleted | including records of rejected, null and harmful results (`EVIDENCE_RECORD_SPEC.md` §2) |
| Every record carries `date`, `version`, `owner`, `source/as-of` | the four fields every appendix worksheet footer requires |
| A record with a missing required field cannot be saved as complete | it takes `Pause`, `Research` or `Skip` |

**Initial stop is stored separately from current stop, and planned risk separately from actual.**
M67's fail-closed clause requires it, and it is what makes two invariants enforceable rather than
aspirational:

- R's denominator is the **originally planned** risk (`RISK_SPEC.md` §2)
- a stop change that increases risk is rejected — `WIDE_STOP`, `Critical`

Neither can be checked if the original values were overwritten.

## 4. This is the same discipline as the data layer

`POINT_IN_TIME_SPEC.md` applies bitemporal storage to market data: facts are never overwritten,
revisions are inserts, and every query is as-of.

This document applies the identical rule to **decisions**. One store holds what the market did and
when we learned it; the other holds what we decided and when we decided it. In both cases the
failure being prevented is the same — a past state being quietly replaced by a present one, so that
history appears to agree with the outcome.

That symmetry is worth preserving in the implementation: the same append-only mechanics should serve
both, rather than two different approaches to the same problem.

## 5. The audit trail

Every mutation-shaped operation produces a record answering:

| Question | Field |
|---|---|
| what changed | old value → new value |
| when | timestamp |
| who | owner |
| why | required reason — free text is acceptable here, absence is not |
| under what rule | the rule or component that proposed it, where one did |
| was it an override | whether a human decision differed from the proposal |

That last field discharges §3.8's requirement that *"an undocumented override may not be presented
as rule-compliant"*. An override is legitimate; an override indistinguishable from rule-following is
not.

## 6. Scope

Immutable: journal entries, trade plans, risk snapshots, decisions, checklists once submitted,
evidence records, run manifests, market-data facts, universe membership.

Mutable: configuration **values** (which produce a new component version and reset validation,
`PARAMETER_REGISTRY.md` §6), watchlist status (which is a status *history*, not a value), and
derived caches that can be recomputed from immutable inputs.

The line: **anything that was an input to a decision, or is a record of one, is immutable.**
Anything recomputable is not.

## 7. Open items

- [ ] Physical mechanism — supersession links versus valid-from/valid-to intervals. The latter makes
      "the plan as of time T" a single query, which is what the audit view needs.
- [ ] Whether a cancelled or aborted run's records are retained. They should be: an aborted run is
      evidence about the system, and `criteria.yml` `a.no_uncoded_failures` counts them.
- [ ] Retention. Indefinite for the same reason as the data store — the history *is* the record.
