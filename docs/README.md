# Document set

57 documents in 8 tiers. Each row states what the document **freezes** and where its content comes
from. `verbatim` means the content is transcribed from the course without rewriting, and is checked
by `tools/verify_transcription.py` against freshly extracted PDF text.

Status values: `planned` · `drafting` · `owner-pending` (blocked on an owner decision) · `frozen`.

## Tier 0 — Charter · `00-charter/`

Frozen first. Amendments are dated records appended to the file, never edits in place.

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 01 | `CHARTER.md` | Purpose, 8 non-goals, the v1 finish line, 5 standing properties | Owner | **finish line ratified 2026-08-01** |
| 02 | `SUCCESS_AND_KILL_CRITERIA.md` | 18 criteria: 7 Track A (system), 6 Track B (edge), 5 kill. Data in `registry/criteria.yml` v1.0.0 | Owner | **frozen 2026-08-02** |
| 03 | `CONSTRAINTS.md` | Markets, timeframes, 9 owner decisions, measured data depths | `verbatim` appendix covers + owner | drafting — budget owner-pending |
| 04 | `GLOSSARY.md` | 35 terms, verbatim | `verbatim` Appendix A + Production Rules §3.9 | drafting |

## Tier 1 — Requirements · `01-requirements/`

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 05 | `BRD.md` | 16 capabilities, 12 non-negotiable business rules, priority ordering | Owner + course | drafting |
| 06 | `USER_STORIES.md` | 21 stories with Gherkin criteria, grouped by the course's four playbooks; covers Track A completely | Course playbooks (M80–83, M32/M33, M71–76, M67/M68) | drafting |
| 07 | `FRD.md` | The ~460 computable topics as requirement rows, keyed by course ID | Generated from `registry/course_index.yml` | planned |
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
| 15 | `ALGORITHM_SPEC.md` | Per component: inputs, formula, parameters, units, warm-up, missing-data behaviour, version | Field list `verbatim` §3.6; content authored | planned |
| 16 | `PARAMETER_REGISTRY.md` | Every threshold with value, unit, provenance, status, UI-editable flag. **74 catalogued, all `unset`** — data in `registry/parameters.yml` | Authored — **no course source exists** | drafting |
| 17 | `RISK_SPEC.md` | 11 risk formulas + control clauses + the sizing ordering law | `verbatim` Appendix C, M48, M49 | drafting |
| 18 | `STATISTICS_SPEC.md` | 11 statistics formulas, 15 M69 metrics, net-of-costs rule, 9 breakdown axes | `verbatim` Appendix D, H, M69 | drafting |
| 19 | `STRATEGY_CARD_SPEC.md` | The strategy definition record + the three condition kinds (required / confirming / prohibiting) | `verbatim` Appendix I (21 fields) + M71 (17) + §3.6 | drafting |
| 20 | `EXIT_MODEL_SPEC.md` | 4-slot exit model (protective/profit/contextual/time + quantity + order) over 92 M52–M58 topics | `verbatim` M52–M58 + `registry/` | drafting |
| 21 | `SCREENER_SPEC.md` | 16 filters, 8 candidate-card fields, 9-step pipeline, 6 watchlist partitions | `verbatim` M32, M33 + `registry/` | drafting |
| 22 | `REGIME_SPEC.md` | 11 regimes, classifier inputs, regime→strategy→risk matrix | `verbatim` M30/M31/Appendix L; **classifier authored** | planned |
| 23 | `EVENT_SPEC.md` | 20 event types with per-type field schemas | `verbatim` M34 decision tables | planned |
| 24 | `CHART_SPEC.md` | Every chart to render: panels, overlays, levels, units | `verbatim` chart metadata (867 chart topics) | planned |

## Tier 3 — Data · `03-data/`, `contracts/`, `adr/`

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 25 | `contracts/` | One schema per cross-context record; code is generated from these | Engineering | planned |
| 26 | `POINT_IN_TIME_SPEC.md` | Bitemporal `event_time`+`knowledge_time`, revision deltas, raw/adjusted separate, membership as PIT fact | Required by Appendix A, J and M72 | drafting |
| 27 | `CALENDAR_SPEC.md` | Separate NYSE/TSX calendars (16-session divergence measured), 13/7 bar sessions, trailing stub, bar finality, UTC storage | Course + measured | drafting |
| 28 | `VENDOR_COMPARISON.md` + `adr/ADR-0001-market-data.md` | Vendor decision | Evidence gathered 2026-08-01 | drafting — ADR **Proposed**, awaiting ratification |
| 29 | `DATA_QUALITY_SPEC.md` | Freshness, conflict, staleness gates and their fail-closed mapping | Course + engineering | planned |

## Tier 4 — Journal, evidence, audit · `04-journal/`

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 30 | `JOURNAL_SCHEMA.md` | 12-entity ER model + M67 fields + implied fields | `verbatim` Appendix G + M67 | drafting |
| 31 | `AUDIT_AND_IMMUTABILITY.md` | Append-only; the original plan is never rewritten | `verbatim` (every appendix page 1) | planned |
| 32 | `EVIDENCE_RECORD_SPEC.md` | Evidence panel fields; 9-value validation status enum | `verbatim` Production Rules §3.7 | planned |
| 33 | `CHECKLIST_SPEC.md` | 84 checklist items as gated forms (E 18 · H 13 · P 19 · T 34) | `verbatim` Appendices E, H, P, T | drafting |

## Tier 5 — Validation · `05-validation/`

| # | File | Freezes | Source | Status |
|---|---|---|---|---|
| 34 | `VALIDATION_PROGRAM.md` | The 9-step pipeline and the 5-row acceptance gate | `verbatim` M71–M76 | planned |
| 35 | `PREREG_TEMPLATE.md` | Pre-registration before any parameter is chosen or changed | Engineering practice (deliberate import) | planned |
| 36 | `BACKTEST_PROTOCOL.md` | 9 stages and their mandatory records | `verbatim` Appendix J | planned |
| 37 | `WALKFORWARD_SPEC.md` | 12-field window record; `keep/revise/retire` | `verbatim` Appendix K | planned |
| 38 | `GO_LIVE_GATES.md` | Staged plans and their gates | `verbatim` Appendices Q, R, S | planned |

## Tier 6 — Architecture & engineering · `06-engineering/`, `adr/`, `runbooks/`

| # | File | Freezes | Status |
|---|---|---|---|
| 39 | `ARCHITECTURE.md` | 9 contexts, the purity boundary, where the mandatory trace is materialised, run shape | drafting |
| 40 | `DEPENDENCY_LAW.md` | Independence rules as 4 import-linter contracts in `pyproject.toml` | drafting |
| 41 | `CONCURRENCY_MODEL.md` | Async fetching, process pools, single-threaded deterministic decision path | planned |
| 42 | `DETERMINISM_SPEC.md` | No wall clock in domain code; run manifests | planned |
| 43 | `adr/` | Append-only decisions with evidence pointers | planned |
| 44 | `TEST_STRATEGY.md` | Unit → property → golden vectors → contract → replay → chaos | planned |
| 45 | `OBSERVABILITY_SPEC.md` + `runbooks/` | Log schema; one runbook per fail-closed row | planned |
| 46 | `SECURITY.md` + `BACKUP_AND_DR.md` | Credentials, masking, tested restore | planned |
| 47 | `CI_POLICY.md` | Merge gates | planned |
| 48 | `AGENTS.md` (repo root) + per-package `CONTEXT.md` | How agents work here | planned |

## Tier 7 — UI/UX · `07-ux/`

| # | File | Freezes | Status |
|---|---|---|---|
| 49 | `UX_TASK_FLOWS.md` | Weekend prep, daily prep, evening process, weekly review | planned |
| 50 | `DESIGN_SYSTEM.md` | Tokens, components, states, density | planned |
| 51 | `CHART_VISUAL_STANDARD.md` | Panel rules, annotation placement, colour semantics, light/dark | planned |
| 52 | `UX_COPY.md` | English microcopy; controlled vocabulary never paraphrased | planned |
| 53 | `ACCESSIBILITY.md` | WCAG 2.1 AA | planned |
| 54 | `DESIGN_HANDOFF.md` | Build specs | planned |

## Tier 8 — Project management · `08-pm/`

| # | File | Freezes | Status |
|---|---|---|---|
| 55 | `ROADMAP.md` | Now / Next / Later against the gates | planned |
| 56 | `RISK_REGISTER.md` | Project risks, incl. parameter-invention and vendor risk | planned |
| 57 | `DEFINITION_OF_READY_DONE.md` | Entry/exit criteria per work item | planned |

---

## Gates

| Gate | Deliverables | Exit condition |
|---|---|---|
| ~~G0 Charter~~ | 01–04 | **CLOSED 2026-08-02** — finish line ratified, criteria frozen at v1.0.0 |
| G1 Requirements | 05–09 | Every capability has a Gherkin acceptance criterion |
| G2 Transcription | 10–13, 17–21, 30–33 + `registry/course_index.yml` | Every `verbatim` block diffs clean against the PDF text |
| G3 Data | 25–29 | Vendor decided by ADR; point-in-time model settled |
| G4 Architecture | 39–43, 47 | Import contracts compile; determinism check runs |
| G5 Walking skeleton | one end-to-end vertical slice | Green in CI. **No second component starts before this.** |
| G6 Catalog build-out | 14–16, 22–24, 34–38 | Components registered in bulk; activation gated per component |
| G7 Web + Telegram + push | 49–54 | A UI parameter edit versions the component and resets its validation |

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
