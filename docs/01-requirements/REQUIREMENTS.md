# REQUIREMENTS

**Status:** drafting · **Tier:** 1 (requirements) · **Content:** authored, audited against the tree

Nine normative requirements with stable ids, each carrying a verification method that can be
executed rather than asserted. Master ТЗ v1.0 §0 requires this form; this tree had Gherkin user
stories in `USER_STORIES.md` and no requirement registry, and a requirement registry is what CI
gate 10 (traceability) has been waiting for.

**Provenance.** Six of the nine were derived from the post-mortem of a previous system, TradAlert,
and each names the specific failure it exists to make inexpressible. That is why they read
oddly specific — they are not general good practice, they are scar tissue. They arrived via the
parallel documentation track (`01_Normative_Requirements_and_Conventions.md`, preserved in
`dee8f37`) and are restated here in English per owner decision D7.

Normative words follow the ТЗ: **MUST** / **MUST NOT** are unconditional, **SHOULD** admits a
justified deviation, **MAY** is an option.

---

## 1. The register

| id | Requirement | Status in this tree |
|---|---|---|
| `REQ-DATA-001` | The event calendar MUST be a point-in-time dataset with the same bitemporal semantics as market data. **No event date may appear as a literal in executable code.** Every record carries `source_id`, `known_from`, `checksum`. | **partially met** — no date literals in `src/` (verified); no event calendar exists at all (`EVENT_SPEC.md` §4) |
| `REQ-DATA-002` | A missing or stale critical input MUST NOT silently become zero or a neutral value. It MUST produce `UNKNOWN`; on a live path a critical `UNKNOWN` MUST produce `NO_TRADE`. | **met** — components refuse rather than default (`INVARIANTS.md` #9); ATR emits `None` before warm-up |
| `REQ-VALIDATION-001` | Every gate, veto or eligibility filter MUST have a pair of inputs producing different verdicts. An object whose verdict is invariant across all inputs MUST NOT reach runtime. | **NOT met** — no mutation testing. See §2 |
| `REQ-VALIDATION-002` | For an identical bar and an identical versioned config, the backtest path and the live path MUST produce an identical `Decision`. Divergence MUST fail the build. | **NOT met, and structurally so** — see §3 |
| `REQ-OUTPUT-001` | Every numeric value in a decision output MUST carry its source identifier — estimate version, cohort key, or model reference. A value without provenance MUST NOT be displayed. | **largely met** — `ParameterUse` travels with every computed value; the report marks `assumed` inputs adjacent to the number |
| `REQ-EVIDENCE-001` | Assigning a validation stage MUST reference a validation run that actually executed in an automated pipeline. An implemented-but-uncalled validation function MUST NOT justify a stage. | **met in practice, unchecked** — `regime.classifier_rule` is `validated:PR-002` and PR-002 has a report with real figures; nothing enforces the link |
| `REQ-RISK-001` | Any risk control in `enabled: false` MUST carry a dated ADR with an owner and a review date. Expiry without renewal MUST fail the build. | **not applicable yet** — this tree has no disabled controls; its risk parameters are `unset`, which fails closed rather than silently passing. See §4 |
| `REQ-AI-001` | AI output MUST NOT bypass an independent risk engine, and a risk veto MUST NOT be overridable by the agent. | **deferred** — `CHARTER.md` §3 makes an AI agent a v1 non-goal |
| `REQ-AI-002` | An AI agent MUST NOT generate numeric quantities (win rate, probability, expectancy, score, stop, target, position size, weights, slippage, edge) from text. These MUST come from deterministic engines or a validated expectation estimate. | **deferred** — as above |

## 2. `REQ-VALIDATION-001` — the inert-gate requirement, and one this tree already has

The rationale is worth quoting because it is not hypothetical: in TradAlert an R:R gate was
`if is_long: return True` and **passed seven audits**, because it is a valid function with valid
references. Prose review cannot catch that. Only an executable test on a pair of inputs can.

**This tree already contains one instance of the failure.** `registry/criteria.yml` ratifies
`k.drawdown_pause`, whose trigger references `validation.max_allowable_drawdown` — which is `unset`,
along with all fifteen `validation.*` parameters. A ratified kill criterion that cannot evaluate is
a gate whose verdict is invariant across all inputs. It was found by hand on 2026-08-03, which is
exactly the detection method this requirement says does not scale.

The check is mechanical and belongs in CI: for every ratified criterion and every veto, assert that
the parameters its trigger references are set, and that forcing the gate's inverse changes at least
one verdict in the test corpus.

## 3. `REQ-VALIDATION-002` — backtest and live are two code paths today

`validation/backtest/engine.py` owns `breakout_high` and the entry decision. `application/pipeline.py`
owns the live path and reaches `"sized; awaiting a trigger"` — **it has no trigger at all.**

So there is no divergence *yet*, and only because the live path implements no strategy. The moment
it does, this repository will hold two independently written implementations of one strategy —
precisely what master ТЗ §8 forbids ("Backtest и live trading не должны использовать две независимо
написанные версии одной стратегии") and what this requirement exists to prevent.

TradAlert's version of the failure: "current date" came from the system clock on live and from the
bar date in backtest, so the two paths selected different trade populations, and the measured edge
described a program that could not have taken the trade it claimed.

**This is cheap to fix now and expensive later.** The trigger should be written once, in a layer both
paths call, before the live path acquires one. Recorded here rather than in a backlog because the
window in which it is cheap is open now and closes on the next feature.

## 4. `REQ-RISK-001` — why `unset` is not the same as `enabled: false`

The requirement targets a control that is written, correct and switched off — TradAlert had six.
`UNSET` does not cover that case: the control is specified but dead.

This tree uses a different mechanism. A risk parameter with no value makes its component **refuse**
(`FAIL_CLOSED_POLICY.md`), so an unset control blocks rather than silently permits. That is stronger
than the requirement asks for, and it is why the requirement is marked not-applicable rather than
unmet.

It becomes applicable the moment any control gains an `enabled` flag. If that happens, the ADR with
`owner` / `reason` / `review_by` is required in the same commit.

## 5. Verification methods

The ТЗ's vocabulary, mapped to what runs here:

| Method | Runs as |
|---|---|
| `inspection` | review; the weakest, used only where nothing else applies |
| `schema_test` | Pydantic contracts in `src/swingdesk/contracts/`, gate 8 |
| `static_validation` | gates 1, 3e, 6, 7, 11 — registries, references, layers, wall clock |
| `unit_test` / `integration_test` | gate 8, 249 tests |
| `replay_test` | gate 9 — a stored manifest must reproduce its `output_hash` |
| `mutation_test` | **does not exist** — the gap `REQ-VALIDATION-001` names |

## 6. Open items

- [ ] `REQ-VALIDATION-001` needs a gate. The narrow version — every ratified criterion's referenced
      parameters are set — is cheap and would have caught `k.drawdown_pause`.
- [ ] `REQ-VALIDATION-002` needs the trigger to exist once rather than twice, **before** the live
      path gets one.
- [ ] `REQ-EVIDENCE-001` is met by practice and not by a check. Gate 11 already verifies that an
      `active` component has `verification`; the analogous check for `validated` parameters does not
      exist.
- [ ] These nine are not yet linked to `USER_STORIES.md` or to tests. That linkage is CI gate 10
      (traceability), still unwired — it would pass vacuously today with zero `active` components.
