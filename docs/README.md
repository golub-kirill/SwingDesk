# Document set

63 documents in 8 tiers. Each row states what the document **freezes** and where its content comes
from. `verbatim` means the content is transcribed from the course without rewriting, and is checked
by `tools/verify_transcription.py` against freshly extracted PDF text.

Status values: `planned` · `drafting` · `owner-pending` (blocked on an owner decision) · `frozen`.

## Tier 0 — Charter · `00-charter/`

Frozen first. Amendments are dated records appended to the file, never edits in place.

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 01 | `CHARTER.md` | Purpose, 8 non-goals, the v1 finish line, 5 standing properties | Owner | **finish line ratified 2026-08-01** |
| 02 | `SUCCESS_AND_KILL_CRITERIA.md` | 19 criteria: 7 Track A (system), 6 Track B (edge), 6 kill. Data in `registry/criteria.yml` v1.1.0 | Owner | **frozen 2026-08-02**; v1.1.0 Track A time box proposed 2026-08-08 |
| 03 | `CONSTRAINTS.md` | Markets, timeframes, 9 owner decisions, measured data depths | `verbatim` appendix covers + owner | drafting — budget owner-pending |
| 04 | `GLOSSARY.md` | 35 terms, verbatim | `verbatim` Appendix A + Production Rules §3.9 | drafting |

## Tier 1 — Requirements · `01-requirements/`

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 05 | `BRD.md` | 16 capabilities, 12 non-negotiable business rules, priority ordering | Owner + course | drafting |
| 06 | `USER_STORIES.md` | 21 stories with Gherkin criteria, grouped by the course's four playbooks; covers Track A completely | Course playbooks (M80–83, M32/M33, M71–76, M67/M68) | drafting |
| 07 | `FRD.md` | **463 requirements** keyed by course component id, grouped by layer and module | **Generated** by `tools/build_frd.py` | generated |
| 08 | `NFR.md` | ~20M bar rows, ≤45 min daily run, byte-identical re-runs, $0/mo, revision-delta storage | Engineering + owner | drafting |
| 09 | `PRODUCT_SURFACES.md` | 4 surfaces, what each owns, notification matrix, what none may do | Owner decisions D3/D6 | drafting |

## Tier 2 — Domain specification · `02-domain/`

Mostly transcription. This is the cheapest, highest-value tier — do it early.

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 10 | `LIFECYCLE_AND_LAYERS.md` | 10-stage lifecycle, 4 layers, the mandatory trace | `verbatim` Production Rules §3.6, §3.8 | drafting |
| 11 | `DECISION_STATE_MACHINE.md` | **Five separate enums**: candidate decision (4), module gate (3), watchlist status (9), acceptance (4), checklist outcome (5 worksheet / 6 decision) | `verbatim` M32/M33/M69 + appendix footers | drafting |
| 12 | `FAIL_CLOSED_POLICY.md` | The 5-row degradation table with return conditions; critical fail is never compensated | `verbatim` (identical across all sampled modules) | drafting |
| 13 | `CODES.md` | 12 skip codes with actions; 12 error codes with severity and required control | `verbatim` Appendix N, O | drafting |
| 14 | `COMPONENT_REGISTRY_SPEC.md` | Record shape, 3 activation states, 9 validation statuses, 8 claim types, 6 unlocked checks | `verbatim` §3.7, §3.8 | drafting |
| 15 | `ALGORITHM_SPEC.md` | 11-field record template, 7 rules, banned vocabulary, order of work | Field list `verbatim` §3.6; content authored | drafting |
| 15a | `RULE_SPEC.md` | The Rule object: 11 mandatory parts, three-valued output, 4 effect classes, the discriminating pair. **173 registered rows carry claim type `Operational Course Rule`**; 8 decision points audited against the form | ТЗ §15, seeded from `dee8f37`; audited against the tree | drafting |
| 16 | `PARAMETER_REGISTRY.md` | Every threshold with value, unit, provenance, status, UI-editable flag. **96 catalogued: 69 `unset`, 24 `assumed`, 2 `owner`, 1 `validated`** — data in `registry/parameters.yml` | Authored — **no course source exists** | drafting |
| 17 | `RISK_SPEC.md` | 11 risk formulas + control clauses + the sizing ordering law | `verbatim` Appendix C, M48, M49 | drafting |
| 18 | `STATISTICS_SPEC.md` | 11 statistics formulas, 15 M69 metrics, net-of-costs rule, 9 breakdown axes | `verbatim` Appendix D, H, M69 | drafting |
| 19 | `STRATEGY_CARD_SPEC.md` | The strategy definition record + the three condition kinds (required / confirming / prohibiting) | `verbatim` Appendix I (21 fields) + M71 (17) + §3.6 | drafting |
| 20 | `EXIT_MODEL_SPEC.md` | 4-slot exit model (protective/profit/contextual/time + quantity + order) over 92 M52–M58 topics | `verbatim` M52–M58 + `registry/` | drafting |
| 21 | `SCREENER_SPEC.md` | 16 filters, 8 candidate-card fields, 9-step pipeline, 6 watchlist partitions | `verbatim` M32, M33 + `registry/` | drafting |
| 22 | `REGIME_SPEC.md` | 11 regimes, classifier inputs, regime→strategy→risk matrix | `verbatim` M30/M31/Appendix L; **classifier authored** | planned |
| 23 | `EVENT_SPEC.md` | 20 event types with per-type field schemas | `verbatim` M34 decision tables | planned |
| 22a | `ALLOCATION_SPEC.md` | Ranking when candidates exceed capacity: admissibility vs preference, what binds first (open risk, not cash), the allocation record, and the alphabetical-bias trap in truncating an id-sorted list | ТЗ §31; the course's two ordering topics are **both `Untested Hypothesis`** | drafting |
| 23a | `TRANSITION_SPEC.md` | The discrete-change object (ТЗ §16, renamed to end the collision with 23): one envelope, the three-part test, observed vs inferred, who may emit. **6 kinds of transition are not recorded at all**, two irrecoverably | ТЗ §16; audited against the journal and stores | drafting |
| 24 | `CHART_SPEC.md` | Every chart to render: panels, overlays, levels, units | `verbatim` chart metadata (867 chart topics) | planned |

## Tier 3 — Data · `03-data/`, `contracts/`, `adr/`

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 25 | `contracts/` | 10 cross-context records, 7 rules, columnar exception for `Bar` — Pydantic v2 per `ADR-0003` | Engineering | drafting |
| 26 | `POINT_IN_TIME_SPEC.md` | Bitemporal `event_time`+`knowledge_time`, revision deltas, raw/adjusted separate, membership as PIT fact | Required by Appendix A, J and M72 | drafting |
| 27 | `CALENDAR_SPEC.md` | Separate NYSE/TSX calendars (**30-session** divergence measured over ~2.9 years), 13/7 bar sessions, trailing stub, bar finality, session date stored not derived | Course + measured | drafting |
| 28 | `VENDOR_COMPARISON.md` + `adr/ADR-0001-market-data.md` | Vendor decision | Evidence gathered 2026-08-01 | drafting — ADR **Proposed**, awaiting ratification |
| 29 | `DATA_QUALITY_SPEC.md` | 4 course gates, session-completeness check, measured negative results, code mapping | Course + measured | drafting |

## Tier 4 — Journal, evidence, audit · `04-journal/`

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 30 | `JOURNAL_SCHEMA.md` | 12-entity ER model + M67 fields + implied fields | `verbatim` Appendix G + M67 | drafting |
| 31 | `AUDIT_AND_IMMUTABILITY.md` | Append-only; the schema IS the HINDSIGHT control; same discipline as the data layer | `verbatim` Appendix G/O + 7 modules | drafting |
| 32 | `EVIDENCE_RECORD_SPEC.md` | 11 evidence-panel field groups + 3 project-mandatory fields (survivorship, window ceiling, PIT coverage) | `verbatim` Production Rules §3.7 | drafting |
| 33 | `CHECKLIST_SPEC.md` | 84 checklist items as gated forms (E 18 · H 13 · P 19 · T 34) | `verbatim` Appendices E, H, P, T | drafting |

## Tier 5 — Validation · `05-validation/`

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 34 | `VALIDATION_PROGRAM.md` | The status ladder and what earns each transition; what a forward test measures that a backtest cannot; the 5 required evidence artefacts | `verbatim` M74 + M72 | drafting |
| 35 | `PREREG_TEMPLATE.md` | 11-section pre-registration; amendment-after-data downgrades to exploratory; `inconclusive` is first-class | Required by Appendix J/K + the data-snooping prohibition; statistics authored | drafting |
| 36 | `BACKTEST_PROTOCOL.md` | 9 stages and their mandatory records; the 4 prohibitions; **survivorship stated as unmeetable on free data** | `verbatim` Appendix J + M72 | drafting |
| 36a | `EXECUTION_MODEL.md` | Fill timing, slippage on the fill, gap handling, the **intrabar stop-before-target policy** stated before a target exists, and the two silent exclusions from the signal ledger | ТЗ §28 + `DR-004`; measured against the engine | drafting |
| 36b | `EXPECTATION_MODEL.md` | The estimate/definition split, the cohort key (the course's own mandatory GROUP BY), three sample floors and what each governs, the usability ladder. **An expectation may never size, gate or override** | ТЗ §23; audited against the studies | drafting |
| 37 | `WALKFORWARD_SPEC.md` | 12-field window record with a **three-way** train/validation/test split; `keep/revise/retire`; the 6 perturbations | `verbatim` Appendix K + M73 | drafting |
| 38 | `GO_LIVE_GATES.md` | Staged plans, the 5-condition size gate, drawdown as an actuator; calendar time authorises nothing | `verbatim` Appendices Q, R, S + M75 | drafting |

Two working directories serve this tier and are not numbered documents:

| Directory | Holds | Rule |
|---|---|---|
| `decisions/` | `DR-NNN` — a **choice that is not a hypothesis** (a convention, a definition) | written before use; leaves a parameter at `assumed:DR-NNN`, **never** `validated` |
| `prereg/` | `PR-NNN` — a **claim that could be false** | committed before the study runs; only its evidence can reach `validated` |

That split is the point. A convention dressed as a hypothesis produces a study that cannot fail, and
a hypothesis settled by decree produces a value with the authority of a measurement it never had.
`tools/verify_parameters.py` checks that every `DR-NNN` a parameter cites actually exists.

Tier 5's finding, stated once: topics literally titled *minimum number of trades* (twice),
*minimum forward-test duration*, *maximum allowable drawdown* and *first 100 real trades* contain
**no numbers at all**. This is the tier where the source was most likely to quantify something, and
it does not. Appendix S's `100% plan/stop/journal; no critical violations` is the only hard,
checkable gate in the course.

## Tier 6 — Architecture & engineering · `06-engineering/`, `adr/`, `runbooks/`

| # | File | Freezes | Status |
|---|---|---|---|
| 39 | `ARCHITECTURE.md` | 10 contexts, the purity boundary, where the mandatory trace is materialised, run shape | drafting |
| 40 | `DEPENDENCY_LAW.md` | Independence rules as 4 import-linter contracts in `pyproject.toml` | drafting |
| 41 | `CONCURRENCY_MODEL.md` | 3 tiers, per-vendor limits, breaker, thread-safety classes, worker-count invariance | drafting |
| 42 | `DETERMINISM_SPEC.md` | The snapshot as determinism boundary, float-associativity trap, 10-field run manifest, stated scope limits | drafting |
| 42a | `SYSTEM_MODES.md` | RESEARCH · BACKTEST · REPLAY · PAPER · SHADOW · LIVE, discriminated by time, facts, writes and **what the output authorises**; the mode↔validation-status mapping; 4 of 6 running | drafting |
| 43 | `adr/` | ADR-0001 market data · 0002 calendar · 0003 schema language · 0004 storage engine (all Proposed) | drafting |
| 44a | `INVARIANTS.md` | The 9 invariants audited against the tests that enforce them: 7 by test, 1 by a function signature, 1 partial | drafting |
| 44 | `TEST_STRATEGY.md` | 7 layers, 9 invariants as property tests, golden vectors as the immutability mechanism, 6 chaos scenarios | drafting |
| 45 | `OBSERVABILITY_SPEC.md` + `runbooks/` | Structured-log schema, daily health report, trend signals; 5 runbooks with verbatim return conditions | drafting |
| 46 | `SECURITY.md` + `BACKUP_AND_DR.md` | Threat model, secret rules, Telegram as a control surface; what cannot be re-fetched, restore verified by output hash | drafting |
| 47 | `CI_POLICY.md` | 18 gates (**17 running**), what each prevents and what each has caught, what CI must never do, local equivalence | drafting |
| 48 | `AGENTS.md` (repo root) | Trust discipline, 7 non-negotiables, how to add a verbatim doc or a parameter | drafting — per-package `CONTEXT.md` still planned |

## Tier 7 — UI/UX · `07-ux/`

| # | File | Freezes | Status |
|---|---|---|---|
| 49 | `UX_TASK_FLOWS.md` | Appendix T's six phases mapped to what the system does today — **11 of 34 items served** | drafting |
| 50 | `DESIGN_SYSTEM.md` | Tokens, components, states, density | **deferred — no surface** |
| 51 | `CHART_VISUAL_STANDARD.md` | Panel rules, annotation placement, colour semantics, light/dark | **deferred — no surface** |
| 52 | `UX_COPY.md` | Controlled vocabulary that is never paraphrased, tone, Russian-in-English rules | drafting |
| 53 | `ACCESSIBILITY.md` | WCAG 2.1 AA | **deferred — no surface** |
| 54 | `DESIGN_HANDOFF.md` | Build specs | **deferred — no surface** |

**Four of the six are deferred deliberately, not overlooked.** They specify a visual surface
that does not exist: `PRODUCT_SURFACES.md` §3.1 names the CLI as the complete v1 surface, and
colour semantics, density tokens and WCAG criteria for a UI nobody has designed would be
invention dressed as specification. `CHART_SPEC.md` declined the same thing for the same reason.
They unblock at G7, with the web admin (D3).

The two that were written are surface-independent: the operator's cadence comes from Appendix T
and holds whatever renders it, and the controlled vocabulary is already enum members in
`contracts/` that gate 2 checks — freezing "never paraphrased" costs nothing now and prevents a
second surface inventing synonyms later.

## Tier 8 — Project management · `08-pm/`

| # | File | Freezes | Status |
|---|---|---|---|
| 55 | `ROADMAP.md` | Now / Next / Later, built on the reported studies rather than before them. Two concrete gaps remain to the ratified finish line | drafting |
| 56 | `RISK_REGISTER.md` | 8 **realised** risks with what caught each, plus 18 open. Every realised one was found by a gate or a test, none by review | drafting |
| 57 | `DEFINITION_OF_READY_DONE.md` | Entry/exit criteria for 5 kinds of work item: component, parameter, study, document, surface | drafting |

---

## Gates

| Gate | Deliverables | Exit condition |
|---|---|---|
| ~~G0 Charter~~ | 01–04 | **CLOSED 2026-08-02** — finish line ratified, criteria frozen at v1.0.0 |
| G1 Requirements | 05–09 | Every capability has a Gherkin acceptance criterion |
| G2 Transcription | 10–13, 17–21, 30–33 + `registry/course_index.yml` | Every `verbatim` block diffs clean against the PDF text |
| G3 Data | 25–29 | Vendor decided by ADR; point-in-time model settled |
| ~~G4 Architecture~~ | 39–43, 47 | **CLOSED** — 4 import contracts compile; determinism replay runs as a gate |
| ~~G5 Walking skeleton~~ | one end-to-end vertical slice | **CLOSED 2026-08-02** — 9 gates green from `python tools/check_gates.py`; ATR active with golden vectors |
| G6 Catalog build-out | 14–16, 22–24, 34–38 | Components registered in bulk; activation gated per component. **34–38 written 2026-08-02**; 7 components implemented, 4 with golden vectors |
| G7 Web + Telegram + push | 49–54 | A UI parameter edit versions the component and resets its validation |

## Studies

Pre-registrations in `prereg/`, results in `prereg/results/`, decision records in `decisions/`.

| | Question | Verdict |
|---|---|---|
| `PR-001` | Do the trend definitions select the same instruments? | **REJECT** — overlaps as low as 0.30 |
| `PR-005` | Do their different populations then behave differently? | **REJECT** — every arm inside the ungated interval |
| `PR-002` | Does a regime label carry decision-relevant information? | **ACCEPT** — and ~2% of trades missing at −2R would erase it |

Two refuted hypotheses and one fragile positive, from three pre-registrations. A fourth analysis —
the survivorship bound in `results/PR-002-report.md` — is **post-hoc and carries no verdict**; it is
counted as a study run and never as a hypothesis tested. `screen.trend_definition` is closed by evidence;
`regime.classifier_rule` is the first `validated` parameter and carries its bound in the registry
note. Planning follows in `08-pm/ROADMAP.md`.

## Verification

Every `verbatim` document declares its sources in a machine-readable comment:

```
<!-- verbatim-sources: Appendix_N_Prichiny_propuska_sdelki_v2.0.pdf, Appendix_O_Tipichnye_oshibki_v2.0.pdf -->
```

`tools/verify_transcription.py` re-extracts those sources with `pdftotext` and asserts that every
markdown blockquote in the document appears in them, plus the membership of all load-bearing enums.
`tools/build_course_index.py --check-only` asserts the registry still extracts to the known shape.
Both are stdlib-only and run on system Python.

```bash
python tools/verify_transcription.py && python tools/build_course_index.py --check-only
```

`tools/verify_parameters.py` enforces the parameter contract: no value without provenance, no
`assumed` without a citation, no parameter without a course reference. It needs PyYAML; the two
checks above are stdlib-only by design so they run anywhere.

```bash
python tools/verify_parameters.py
```

Quotes containing an elision marker are reported as skipped, never silently passed. Translation
glosses are excluded from checking — they are ours, not the course's.

## Component activation states

1. `registered` — course ID, name, layer, stage recorded. All ~460 reach this.
2. `specified` — algorithm spec written, parameters declared with provenance.
3. `active` — usable in a decision: parameters have values with provenance, golden vectors exist,
   and the validation status is displayed wherever the component's output appears.

`Untested` is a permitted status for an active component. Hiding it is not.
