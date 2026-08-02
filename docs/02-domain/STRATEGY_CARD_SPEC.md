# STRATEGY CARD SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim`

<!-- verbatim-sources: Appendix_I_Opisanie_strategii_v2.0.pdf, Module_71_Formalizatsiya_strategii_v4.0.pdf, Course_Production_Rules_v3.8.md -->

**Sources:** `Appendix_I_Opisanie_strategii_v2.0.pdf` page 2 (21 fields),
`Module_71_Formalizatsiya_strategii_v4.0.pdf` topics 1054–1070 (17 formalization fields),
`Course_Production_Rules_v3.8.md` §3.6 (the strategy declaration list). Verified 2026-08-01.

A strategy card is the unit that gets versioned, tested and accepted. Three independent lists in the
course describe it; this document merges them and notes where they disagree.

---

## 1. Appendix I — the worksheet fields (21)

```verbatim
Название/версия
Цель и экономическая логика
Допустимые рынки/инструменты
Market regimes
Sector/RS filters
1Y/3M context
30D setup
Trigger
Entry methods
Maximum entry
Initial stop
Position sizing
Targets/partials
Trailing/failure/time exits
Skip conditions
Known event rules
Data requirements
Backtest protocol
Out-of-sample/robustness
Paper/live gates
Monitoring/kill criteria
```

The `Правило` column of this appendix is **blank by design** — it is a worksheet. The course supplies
the field list and nothing else.

## 2. Module 71 — the formalization fields (17)

Topics 1054–1070, titles taken from `registry/course_index.yml`:

| Topic | Field | Claim type |
|---|---|---|
| 1054 | Торгуемые инструменты | Definition |
| 1055 | Рабочие таймфреймы | Definition |
| 1056 | Допустимые рыночные режимы | Operational Course Rule |
| 1057 | Условия тренда | Operational Course Rule |
| 1058 | Условия сетапа | Operational Course Rule |
| 1059 | Условия входа | Operational Course Rule |
| 1060 | Условия подтверждения | Operational Course Rule |
| 1061 | Условия отмены | Operational Course Rule |
| 1062 | Правило stop-loss | Operational Course Rule |
| 1063 | Правило размера позиции | Operational Course Rule |
| 1064 | Правило цели | Operational Course Rule |
| 1065 | Правило trailing exit | Operational Course Rule |
| 1066 | Правило частичной фиксации | Operational Course Rule |
| 1067 | Максимальный срок удержания | Operational Course Rule |
| 1068 | Правила пропуска сделки | Operational Course Rule |
| 1069 | Правила портфельного риска | Operational Course Rule |
| 1070 | Полный чек-лист стратегии | Operational Course Rule |

M71's condition semantics, verbatim:

> "Условия делятся на обязательные, подтверждающие и запрещающие; критический запрет не
> компенсируется большим количеством слабых положительных признаков."

**This is the condition type system, and it is load-bearing.** Three kinds:

| Kind | Behaviour |
|---|---|
| `обязательный` (required) | Must hold. Failure → the setup does not exist. |
| `подтверждающий` (confirming) | Adds support. May be absent without invalidating. |
| `запрещающий` (prohibiting) | **Non-compensatory.** Presence blocks regardless of how many confirming conditions hold. |

A prohibiting condition can never be outvoted by confirming ones — the same rule as
`FAIL_CLOSED_POLICY.md` §3, restated at strategy level. Any scoring or weighting scheme applies
**only** to confirming conditions, never across the three kinds.

## 3. Production Rules §3.6 — the declaration list

Every strategy or playbook must specify, verbatim:

```verbatim
strategy ID and version;
applicable markets, instruments, timeframes, regimes, and holding horizon;
required source facts and derived observations;
prerequisite context and candidate-selection rules;
setup, trigger, entry method, and maximum acceptable entry;
invalidation, initial stop, sizing method, and portfolio constraints;
management and exit policies;
incompatible conditions and automatic Skip/Pause/Error gates;
expected data latency and behavior when required data are missing, stale, revised,
evidence classification and validation status under amendment 3.7.
```

## 4. The merged record

Union of all three, deduplicated. Fields present in only one source are marked.

| Group | Field | From |
|---|---|---|
| Identity | strategy id · name · version | I, §3.6 |
| Identity | economic rationale (`Цель и экономическая логика`) | I |
| Scope | markets · instruments · timeframes · **holding horizon** | I, M71, §3.6 |
| Scope | allowed market regimes | I, M71, §3.6 |
| Scope | sector / relative-strength filters | I |
| Dependencies | **required source facts and derived observations** | §3.6 only |
| Context | 1Y/3M context rules · 30D setup rules · trend conditions | I, M71 |
| Entry | candidate-selection rules · setup conditions · trigger · confirmation conditions · entry methods · maximum entry | I, M71, §3.6 |
| Invalidation | cancellation conditions · initial stop rule | I, M71, §3.6 |
| Sizing | position-sizing rule · portfolio constraints | I, M71, §3.6 |
| Exits | targets/partials · trailing · failure exit · time exit · **maximum holding period** | I, M71 |
| Gates | skip conditions · **incompatible conditions and automatic Skip/Pause/Error gates** | I, M71, §3.6 |
| Events | known event rules | I |
| Data | data requirements · **expected latency and behaviour on missing/stale/revised/contradictory data** | I, §3.6 |
| Validation | backtest protocol · out-of-sample & robustness · paper/live gates | I |
| Validation | **evidence classification and validation status** | §3.6 |
| Monitoring | monitoring and kill criteria | I |
| Process | full strategy checklist | M71 |

**Fields only §3.6 supplies** — and they are the ones a naive implementation would omit:
the explicit dependency list (which components this strategy consumes, enabling the "known consumers"
requirement in `LIFECYCLE_AND_LAYERS.md` §5), the data-latency and degradation behaviour, and the
evidence/validation status. All three are mandatory.

## 5. Binding rules

1. **A strategy references components; it does not restate their formulas.** From §3.8:
   *"Strategies reference components rather than copying their formulas or silently reimplementing
   them."* The card holds component IDs and versions, not duplicated logic.
2. **A card is versioned as a whole.** Changing any field creates a new version and resets
   validation status — §3.7: *"Editing a threshold after seeing results creates a new rule version
   and resets any validation claim that depended on the earlier frozen definition."*
3. **Every card carries its validation status honestly**, from the nine-value enum
   (`EVIDENCE_RECORD_SPEC.md`). Every strategy in the course is `Untested`; a card imported from the
   course starts there and may not start anywhere else.
4. **Management and entry are validated separately** (`LIFECYCLE_AND_LAYERS.md` §2, layer 4). A card
   may pin a shared exit policy by ID and version; a good result from that policy does not validate
   the entry logic.

## 6. The six course playbooks are not strategy cards

Modules 88–93 present six playbooks — beginner base system, trend pullback, breakout, false
breakout, event-driven momentum, final risk system. **They are slot lists, not specifications.**
Measured: steps 1–9 of the `PLAYBOOK` page are byte-identical across all six modules, only steps 10
and 11 differ, and no playbook step carries a numeric parameter.

They are therefore useful as **the field skeleton of a card**, and useless as its content. Importing
them creates six cards with every rule field empty, each of which must be authored and each
parameter registered with provenance `assumed` before the card can be activated.

Recording this explicitly so nobody re-reads M88–M93 expecting to find entry rules.

## 7. Open items

- [ ] `Цель и экономическая логика` should be required non-empty — a strategy without a stated
      mechanism is exactly what `PREREG_TEMPLATE.md` §0 exists to reject. Confirm as a hard
      constraint.
- [ ] Whether `Sector/RS filters` (Appendix I) and `Условия тренда` (M71) are separate fields or one.
      They are listed separately; keep separate until proven redundant.
- [ ] Card storage format: the registry rows are YAML, and a strategy card is a natural fit for the
      same treatment. Decide once `COMPONENT_REGISTRY_SPEC.md` is written.
