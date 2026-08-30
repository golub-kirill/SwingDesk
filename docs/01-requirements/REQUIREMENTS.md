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

**Status is what is true; §7 is what would go red if it stopped being true.** The two are different
claims and this document carried only the first until 2026-08-25.

| id | Requirement | Status in this tree |
|---|---|---|
| `REQ-DATA-001` | The event calendar MUST be a point-in-time dataset with the same bitemporal semantics as market data. **No event date may appear as a literal in executable code.** Every record carries `source_id`, `known_from`, `checksum`. | **partially met** — the date-literal clause is **enforced by gate 7** since 2026-08-25 and reads zero across all 70 modules in `src/`; ~~verified~~ once by hand before that, on a MUST with no mechanism. No event calendar exists at all (`EVENT_SPEC.md` §4) |
| `REQ-DATA-002` | A missing or stale critical input MUST NOT silently become zero or a neutral value. It MUST produce `UNKNOWN`; on a live path a critical `UNKNOWN` MUST produce `NO_TRADE`. | **met** — components refuse rather than default (`INVARIANTS.md` #9); ATR emits `None` before warm-up |
| `REQ-VALIDATION-001` | Every gate, veto or eligibility filter MUST have a pair of inputs producing different verdicts. An object whose verdict is invariant across all inputs MUST NOT reach runtime. | **partially met** — gate 3g enforces the narrow half for criteria (2026-08-08), and **gate 34 mutation-tests the five vetoes that evaluate on the live path** (2026-08-25), each forced to admit everything. Still partial: `k.drawdown_pause` is ratified and cannot fire, so the criteria half has no verdict to flip. See §2 |
| `REQ-VALIDATION-002` | For an identical bar and an identical versioned config, the backtest path and the live path MUST produce an identical `Decision`. Divergence MUST fail the build. | **NOT met, and structurally so** — see §3 |
| `REQ-OUTPUT-001` | Every numeric value in a decision output MUST carry its source identifier — estimate version, cohort key, or model reference. A value without provenance MUST NOT be displayed. | **largely met** — `ParameterUse` travels with every computed value; the report marks `assumed` inputs adjacent to the number |
| `REQ-EVIDENCE-001` | Assigning a validation stage MUST reference a validation run that actually executed in an automated pipeline. An implemented-but-uncalled validation function MUST NOT justify a stage. | **NOT met, and 2026-08-16 proved why it matters.** The single `validated:` assignment in this tree — `regime.classifier_rule` = `validated:PR-002` — referenced a run that executed but whose verdict violated its own pre-registered decision rule; nothing enforced the link and nothing checked the verdict against the branches the prereg registered. The parameter is now `assumed:PR-002` and **no parameter holds a validation stage**. The requirement is unenforced, not satisfied |
| `REQ-RISK-001` | Any risk control in `enabled: false` MUST carry a dated ADR with an owner and a review date. Expiry without renewal MUST fail the build. | **not applicable yet** — this tree has no disabled controls; its risk parameters are `unset`, which fails closed rather than silently passing. See §4 |
| `REQ-AI-001` | AI output MUST NOT bypass an independent risk engine, and a risk veto MUST NOT be overridable by the agent. | **NOT met, and now applicable** — charter amendment **A-001** puts an AI agent in scope as a context layer that may never decide. This requirement was written for that boundary; no agent exists to satisfy it |
| `REQ-AI-002` | An AI agent MUST NOT generate numeric quantities (win rate, probability, expectancy, score, stop, target, position size, weights, slippage, edge) from text. These MUST come from deterministic engines or a validated expectation estimate. | **NOT met, and now applicable** — as above |

## 2. `REQ-VALIDATION-001` — the inert-gate requirement, and the one this tree had

The rationale is worth quoting because it is not hypothetical: in TradAlert an R:R gate was
`if is_long: return True` and **passed seven audits**, because it is a valid function with valid
references. Prose review cannot catch that. Only an executable test on a pair of inputs can.

**This tree contained one instance of the failure.** `registry/criteria.yml` ratifies
`k.drawdown_pause`, whose trigger references `validation.max_allowable_drawdown` — which was `unset`,
along with all fifteen `validation.*` parameters. A ratified kill criterion that cannot evaluate is
a gate whose verdict is invariant across all inputs. It was found by hand on 2026-08-03, which is
exactly the detection method this requirement says does not scale.

**Closed 2026-08-08 by `DR-007-validation-thresholds.md`**, which proposes values for all fifteen.
The criterion can now evaluate. It is still *untested* — nothing exercises it, because there is no
realised drawdown to exercise it against — and `RULE_SPEC.md` §7 keeps those two states apart on
purpose: a gate that went from unable-to-fail to untested has improved without yet working.

The check is mechanical and belongs in CI: for every ratified criterion and every veto, assert that
the parameters its trigger references are set, and that forcing the gate's inverse changes at least
one verdict in the test corpus.

**The first half landed 2026-08-08 as gate 3g** (`tools/verify_criteria.py`), in the same change that
ratified `DR-007`. It also checks two things the requirement implies rather than states: that a
reference resolves at all, and that a criterion's `status` is on the declared ladder — the second
because a typo there would exempt the row from the first check, which would make the gate quietly
weaker rather than loudly wrong. All three were mutation-checked against a deliberately broken
registry before the gate was trusted.

~~**The second half — mutation testing — still does not exist**, and it needs a corpus of evaluated
criteria before it can. Nothing evaluates these yet, so a mutation gate here would have nothing to
flip.~~

**BUILT 2026-08-25 as gate 34, and the premise above had gone stale rather than been wrong.** It was
written when no veto evaluated anything. `DR-006` then wired the concurrent-position, open-risk,
correlation and sector caps into the live path (2026-08-22/23) and `DR-015` wired the staleness gate
(2026-08-18), so a corpus arrived and nobody re-read this paragraph — which is `AGENTS.md` §12's
*"a citation that was correct when written, still standing after the fact it cites moved"*.

Each of those five vetoes is now forced to **admit everything** — the exact shape of TradAlert's
`if is_long: return True` — against a scratch copy of `src/`, and a named test must go red. All five
are caught. Derive it, never quote it from here:

```bash
python tools/verify_invariant_tests.py
```

**What is still not covered, and it is the half this requirement was written about.** The
requirement says *"every gate, veto or eligibility filter"*, and ratified CRITERIA are not vetoes in
code. `k.drawdown_pause` cannot fire at all — nothing computes realised drawdown — so there is no
verdict to flip and no mutant to write. The gate names that omission on every run rather than
counting it as covered, and `TODO.md` §1 carries it as open work. **The status below stays
`partially met` because of it.**

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
| `static_validation` | gates 1, 3e, 3f, 3g, 6, 7, 11 — registries, references, criteria, layers, wall clock |
| `unit_test` / `integration_test` | gate 8 |
| `replay_test` | gate 9 — a stored manifest must reproduce its `output_hash` |
| `mutation_test` | ~~**does not exist** — the gap `REQ-VALIDATION-001` names.~~ **gate 34, built 2026-08-25.** Gate 3g closes the input half; gate 34 closes the verdict half for the five vetoes that evaluate on the live path, each forced to admit everything, plus `INVARIANTS.md` §1's named tests. Ratified CRITERIA are still uncovered — `k.drawdown_pause` has no verdict to flip |

## 6. Open items

- [x] ~~`REQ-VALIDATION-001` needs a gate~~ — **narrow version landed 2026-08-08, gate 3g**, and the
      ~~mutation half remains, and remains blocked on a corpus of evaluated criteria~~ **mutation
      half landed 2026-08-25 as gate 34.** The corpus arrived without anyone noticing: `DR-015`
      wired the staleness gate and `DR-006` the book, correlation and sector caps. **Still open for
      criteria** — `k.drawdown_pause` cannot fire, so it has no verdict to flip; that is `TODO.md`
      §1's item, not a gate's.
- [ ] `REQ-VALIDATION-002` needs the trigger to exist once rather than twice, **before** the live
      path gets one.
- [ ] `REQ-EVIDENCE-001` is met by practice and not by a check. Gate 11 already verifies that an
      `active` component has `verification`; the analogous check for `validated` parameters does not
      exist.
- [x] ~~These nine are not yet linked to `USER_STORIES.md` or to tests.~~ **Half done 2026-08-25:
      §7 links each requirement to the test or gate that would go red if it broke, or states that
      nothing would.** Six of nine have something; three have nothing, correctly, and say why. The
      `USER_STORIES.md` half is untouched.
      **Gate 10 is still not wired, and §7 says what it should and should not check.** The
      "vacuously" clause above rested on zero `active` components; derive the current count from
      `HANDOFF.md` §2 rather than from this line.

## 7. What enforces each — the linkage §6 has been waiting for

**Written 2026-08-25.** §6's last item records that these nine are *"not yet linked to
`USER_STORIES.md` or to tests"*, and names CI gate 10 as the linkage. This is the half that has to
exist first: for each requirement, the executable thing that would go red if it broke, **or the
honest statement that nothing would**. `INVARIANTS.md` §1 is the same artefact for the nine
invariants, and it is the one that found a named test which could not fail.

**Six of nine have something. Three have nothing, and each says why.**

| id | Enforced by | Kind |
|---|---|---|
| `REQ-DATA-001` | **gate 7** (`verify_no_wall_clock.py`) for the date-literal clause — zero across all 70 modules in `src/`. **Nothing for the rest**: no event calendar is **wired**, so its bitemporal semantics and its `source_id` / `known_from` / `checksum` fields have no subject yet (`EVENT_SPEC.md` §4). ~~no event calendar **exists**~~ — **corrected 2026-08-30**, and the correction is the point: one exists, free and keyless, and `python tools/probe_events.py` reaches it. This cell said *exists* where the code says *wired*, which is `AGENTS.md` §15 rule 2 — a claim about the world inferred from what our code received. Not a gap that closed; a sentence that was never tested | gate, partial |
| `REQ-DATA-002` | `test_unset_parameter_refuses_and_names_itself` plus gate 1's registry contract for the *unset* half; `test_a_stale_candidate_is_refused_instead_of_sized` for the *stale* half — a candidate past the freshness window leaves with `Skip` / `DATA` rather than being sized. **Both are mutation-checked by gate 34** | test ×2, mutation-checked |
| `REQ-VALIDATION-001` | **gate 3g** (a criterion's inputs exist) and **gate 34** (a veto's verdict can be flipped, five of them). **Not covered:** ratified criteria — `k.drawdown_pause` has no verdict to flip, which is §2's remaining half | gate ×2, partial |
| `REQ-VALIDATION-002` | **nothing, and structurally so** — §3. Two independently written code paths exist and no divergence test can be written until the live path has a trigger. The cheap window is open now | nothing, by construction |
| `REQ-OUTPUT-001` | `test_atr_carries_provenance_and_status` at the component boundary and `test_an_assumed_parameter_is_flagged_as_not_evidence` at the display boundary. **Neither is mutation-checked**, and the first covers one component | test ×2 |
| `REQ-EVIDENCE-001` | **gate 3f**, in part: a `validated:` parameter may only cite a study that ACCEPTed. **Not covered:** the *"actually executed in an automated pipeline"* clause — nothing distinguishes a validation run that ran from one that was written | gate, partial |
| `REQ-RISK-001` | **nothing, and there is nothing to check** — no control in this tree carries an `enabled` flag (§4). It becomes checkable the moment one does, and the ADR is then required in the same commit | not applicable |
| `REQ-AI-001` | deliberately not stated here — see `AI_AUTHORITY_MODEL.md` §11. `application/ai_guard.py` was changing on a parallel branch on the day this table was written, and two trees answering one question differently is `POSTMORTEM-2026-08-09.md` root cause A | see the model |
| `REQ-AI-002` | as above | see the model |

**What this makes possible, and what it does not.** Gate 10 can now be written against this column
rather than against nothing. It still should not demand a test for every requirement: three of the
nine have none *correctly*, and a gate that reddened on those would be demanding a test for a
capability that does not exist. The check worth having is narrower — **a row here naming a test or a
gate that no longer exists** — which is the failure this table will acquire the moment something is
renamed.

**Two things this table asserts that the register did not.** `REQ-OUTPUT-001` reads *"largely met"*
above and rests on two example tests, one of them over a single component; and `REQ-EVIDENCE-001`'s
§6 open item said the check analogous to gate 11 *"does not exist"* — gate 3f is that check for the
half it covers, and the half it does not is the *"executed in a pipeline"* clause.
