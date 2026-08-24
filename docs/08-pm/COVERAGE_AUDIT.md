# COVERAGE AUDIT

**Status:** drafting · **Tier:** 8 (project management) · **Content:** authored, measured against the tree

Master ТЗ §8 and §53 step 4. **This document exists to be consulted before any new document is
written** (§49): a requirement with a correct canonical home does not need a second one, and the
fastest way to violate §8's "one logic in two places" rule is to specify something that already
exists under a different name.

Distinct from `SPEC_GAP_ANALYSIS.md`, which classifies the ТЗ's 56 *sections* against this tree.
This asks the narrower operational question: for each **contour** — a body of concern that spans
several documents — where does it live now, how completely, and what would have to change.

---

## 1. Method, and why it is not optional

§8.2 states the rule: **nothing may be declared missing because its name is not visible in an
index.** Every row below was reached by opening the named documents, not by searching for a heading.

The rule earns its place. `RULE_SPEC.md` §9 is the worked example — eleven of master ТЗ §15's
requirements looked absent from any index and were already law here, several enforced more strictly
than the specification asks. Three-valued logic was `ItemState.UNAVAILABLE` and
`Observation.value: Decimal | None`; the non-compensatory veto was a line in `AGENTS.md` §3; weights
being `unset` until calibrated was the registry's entire design.

Inspection changed three verdicts in this audit that a name search would have got wrong, in **both**
directions. Two contours are better covered than the index suggests. One is not covered at all
despite three documents asserting it was settled.

## 2. Coverage statuses

Taken from §8.1.

| Status | Meaning |
|---|---|
| `COVERED` | a canonical home exists and is adequate |
| `PARTIALLY_COVERED` | substantially addressed, with a named shortfall |
| `CONFLICTING` | two homes disagree, or a document asserts something the source does not support |
| `MISSING` | inspected, and genuinely absent |
| `INTENTIONALLY_DEFERRED` | out of the current contour by a recorded decision |
| `OUT_OF_SCOPE` | excluded by ratified charter; reopening needs an amendment |
| `OWNER_PENDING` | blocked on a decision only the owner can make |
| `UNVERIFIED` | not yet inspected — none remain in this pass |

## 3. The audit

| Contour | Existing home | Coverage | Shortfall / conflict | Action |
|---|---|---|---|---|
| **Research governance** | `PREREG_TEMPLATE.md`, `BACKTEST_PROTOCOL.md`, `WALKFORWARD_SPEC.md`, the pre-registrations in `docs/prereg/` | `COVERED` | ~~multiple-testing correction named as an open item and not adopted~~ **closed 2026-08-24**: `b.deflated_sharpe` had been ratified since 2026-08-08 and only the template had not caught up | none — `PREREG_TEMPLATE.md` §6 now records the adopted correction and what a study owes it |
| **Instrument identity** | `DATA_QUALITY_SPEC.md`, `POINT_IN_TIME_SPEC.md`, `reference_data/directory.py` | `PARTIALLY_COVERED` | the principle is stated and enforced — *"the internal id is the only safe identity and tickers are labels attached to it"* — but §26.2's corporate-action lifecycle (mergers, spin-offs, dual listings, ETF closures) is not enumerated | extend `DATA_QUALITY_SPEC.md`; **do not** create a new document |
| **External service qualification** | `VENDOR_COMPARISON.md`, `ADR-0001` | `PARTIALLY_COVERED` | far stronger than the index suggests: Yahoo's personal-use term is quoted verbatim, Questrade carries an explicit `Unverified` list, TradingView is blocked pending a ToS review. Missing is the *machine* form — no `registry/external_services.yml`, no qualification lifecycle, no per-mode permission | extend, then consider a registry when a second vendor is actually adopted |
| **Portfolio & capital allocation** | `RISK_SPEC.md`, `registry/parameters.yml` | `PARTIALLY_COVERED` | the objects exist and are named: `risk.max_open_risk`, `risk.max_sector_risk`, `risk.correlation_threshold`, `risk.max_concurrent_positions`, `risk.max_position_value` — **all five `unset`**, so the constraints fail closed rather than being absent. What is missing is a portfolio *layer* in code and a deterministic ranking when candidates exceed capital | owner sets the five values; ranking needs ТЗ §31, still `ABSENT` |
| **Expectation, baseline, calibration** | `STATISTICS_SPEC.md`, `VALIDATION_PROGRAM.md` | `PARTIALLY_COVERED` | expectancy is defined and net-of-costs is enforced; the ТЗ's **definition/estimate split** and a first-class baseline object are not there. The studies each carry an ad-hoc baseline instead | extend `STATISTICS_SPEC.md` — this is the strongest candidate for a new document if the split proves too large to graft |
| **Execution & order lifecycle** | `EXECUTION_MODEL.md`, `contracts/`, `EXIT_MODEL_SPEC.md` | `OUT_OF_SCOPE` | order states, fills, broker reconciliation and idempotency are genuinely absent — and **`CHARTER.md` §3 makes "Placing orders" a ratified non-goal** (D1). Fills are *modelled* for backtesting; none are ever requested | none. Reopening requires a charter amendment, not a specification |
| **Drift monitoring** | — | `MISSING` | inspected `OBSERVABILITY_SPEC.md` and `GO_LIVE_GATES.md` directly: **the word "drift" does not appear in either.** Confirms `SPEC_GAP_ANALYSIS.md` §45 rather than contradicting it | needs a live record first; `UX_TASK_FLOWS.md` §3 measures the post-trade phase at 0 of 6 |
| **AI decision agent & authority** | `AI_AUTHORITY_MODEL.md`, `CHARTER.md` A-001 | `PARTIALLY_COVERED` | authority model written 2026-08-08. Shortfall: its §3 boundary is authored and wants owner ratification, and none of its prohibitions are gated | ratify §3; then model governance, never before |
| **Runtime source of truth** | `COMPONENT_REGISTRY_SPEC.md`, `ARCHITECTURE.md`, `DEPENDENCY_LAW.md` | `PARTIALLY_COVERED` | activation states exist and are gated; the ТЗ §7.1 **runtime-permission layer** does not. `active` and `live-authorized` are the same field today, and 0 components are `active` so nothing currently depends on the distinction | extend `COMPONENT_REGISTRY_SPEC.md` before the first component goes `active` |

## 4. The finding that changes a decision

**Three documents defer the entire AI contour on the authority of a charter provision that does not
exist.**

- `SPEC_GAP_ANALYSIS.md` §2 row 32: *"DEFERRED — `CHARTER.md` §3 non-goal for v1"*
- the same, row 33, *"follows §32"*
- `REQUIREMENTS.md` `REQ-AI-001` and `REQ-AI-002`: *"deferred — `CHARTER.md` §3 makes an AI agent a
  v1 non-goal"*

**`CHARTER.md` does not mention AI, LLMs or agents anywhere.** Its §3 lists eight non-goals and none
of them is an AI agent. The nearest is **"Automated trading of any kind"**, and that is a different
claim: it excludes an autonomous trader, and says nothing about an assistant that proposes a decision
a human then approves — which is precisely the shape master ТЗ §37 describes, and precisely the shape
this system's every other component already takes.

Gate 3e verifies that a cited *document* exists. Nothing verifies that a cited *provision* does, so
this survived three documents and an earlier gap analysis.

### Resolved 2026-08-08 — charter amendment A-001

The owner took the decision the moment the gap was surfaced, and it is now recorded where it should
have been all along: `CHARTER.md` §7, the charter's **first amendment**.

| | |
|---|---|
| **Final trading decision** | **human-only**, absolute. Extends D1 from *placing orders* to *deciding* |
| **Automated trading** | excluded, and the §3 non-goal now explicitly covers an AI path |
| **AI's permitted role** | subsume context and present a global picture — synthesis, never authority |
| **AI may never** | decide, size, override a veto, alter a parameter, extend its permissions, or originate a number |
| **Timing** | in scope for the project, **outside the ratified v1 finish line**. §4 unchanged |
| **Standing condition** | specification-first — nothing implemented before the authority model is written and gated |

Two consequences worth stating separately, because they invert what the tree said yesterday:

1. **`REQ-AI-001` and `REQ-AI-002` are applicable requirements, not deferred ones.** They were
   written for precisely this boundary — no bypassing an independent risk engine, no numbers
   generated from text. They are unmet because no agent exists, which is a different and more
   honest status than "deferred".
2. **The coverage status is `MISSING`, not `OUT_OF_SCOPE`.** The contour is in scope and has no
   home. That makes an authority-model document justified under §49 — the only one of the four
   AI-adjacent candidates in §5 that this audit now licenses, and only in that order.

## 5. What this audit licenses

Per §49, a new document is justified only where a requirement has no correct canonical home.

| Proposed document (ТЗ §49 candidate) | Verdict |
|---|---|
| EXPECTATION_BASELINE_AND_CALIBRATION_SPEC | **defensible** — the definition/estimate split has no home. Try extending `STATISTICS_SPEC.md` first |
| PORTFOLIO_AND_CAPITAL_ALLOCATION_SPEC | **not yet** — `RISK_SPEC.md` holds the objects; the gap is five unset values and ТЗ §31 ranking |
| EXECUTION_AND_ORDER_STATE_SPEC | **no** — out of scope by ratified charter |
| AI_DECISION_AGENT_AND_AUTHORITY_MODEL | **written 2026-08-08 as `AI_AUTHORITY_MODEL.md`.** The ТЗ's name presumes a deciding agent; A-001 denies that authority, and a name embedding it is the §11 terminology failure the ТЗ itself warns about |
| AI_MODEL_GOVERNANCE_AND_EVALUATION | **not yet** — model, prompt and schema versioning matter once an agent exists. Follows the authority model, does not precede it |
| EXTERNAL_API_QUALIFICATION_SPEC | **not yet** — `VENDOR_COMPARISON.md` carries the substance; revisit when a second vendor is adopted |
| STRATEGY_VALIDATION_DOSSIER | **defensible** — `VALIDATION_PROGRAM.md` names the artefacts but no template collects them per strategy |

**Three of seven**, after A-001 resolved the AI scope on 2026-08-08 — it was two while that was
undecided. The other four would each have duplicated an existing home, been forbidden by the
charter, or preceded a document they depend on, which is the outcome §8 exists to produce.

## 6. Open items

- [ ] **The AI scope decision** (§4). Blocks two proposed documents and voids two requirement
      justifications until taken.
- [ ] **A gate for cited provisions.** Gate 3e checks that a cited *document* exists; nothing checks
      that a cited *section within it* does, let alone that the section says what the citation
      claims. The AI defect in §4 survived three documents and a gap analysis because of that gap. A
      narrow version — assert that a cited section number is present as a heading in the target
      document — would be cheap and would have caught it.
- [ ] **This audit is hand-maintained.** It has no generator and no checker, so it will go stale the
      way `docs/README.md` did. It should be re-run whenever a contour's home changes.
