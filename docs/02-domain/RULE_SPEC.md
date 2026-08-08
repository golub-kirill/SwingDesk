# RULE SPEC — the Rule object

**Status:** drafting · **Tier:** 2 (domain) · **Content:** authored, audited against the tree

Master ТЗ v1.0 §15. `SPEC_GAP_ANALYSIS.md` §4 ranks it first of the nine absent sections because
§16–§20 all reference it: an Event, a State, a Setup and a Constraint are each defined in terms of a
Rule, so specifying them before this one means specifying them against nothing.

**Seed.** `11_Rule_Specification.md`, preserved verbatim in commit `dee8f37`, restated in English per
owner decision D7. That draft defined the form and did not check which parts of it this tree already
satisfies — the same omission that produced `SPEC_GAP_ANALYSIS.md`. §7 is that check, and it is the
reason this document is longer than the seed in the audit and shorter in the schema.

**What this document does not do.** It authors no rule. The course names the rule concepts and
quantifies none of them (`AGENTS.md` §8), so a rule invented here would be scope wearing a
specification's clothes. This freezes the *shape* a rule must have; filling the shape is
transcription where the course supplies content and a pre-registration where it does not.

---

## 1. Rule and Component are different objects

Name collisions are the failure mode this tree has already hit once: `EVENT_SPEC.md` holds the
course's market-event catalogue while the ТЗ's §16 Event is a formal transition object, and two
different things now share one name (`SPEC_GAP_ANALYSIS.md` §4.2). So the boundary comes first.

| | Component (`COMPONENT_REGISTRY_SPEC.md`) | Rule (this document) |
|---|---|---|
| Produces | a **value** — a number, a series, a label | a **verdict** — one that changes what happens to a candidate |
| Fails by | computing the wrong number | firing when it should not, or never firing at all |
| Verified by | golden vectors against a derivation | a pair of inputs whose verdicts differ (§6) |
| Example | ATR `M18-T0280` | the trend filter `M33-T0485` |

The course draws the same line and puts the two in **different layers**: measuring structure is
`Derived Observations`, selecting on it is `Decision Logic`. That is why
`swingdesk.decision_logic.trend` is a separate module from `swingdesk.derived_observations.moving_average`
rather than a flag on it, and the split is the course's, not an engineering preference.

**Measured, from `registry/components.yml`.** Of 465 rows, **173 carry claim type
`Operational Course Rule`** — 89 in `Decision Logic`, 51 in `Trade Management`, 31 in
`Derived Observations`, 2 in `Source Facts`. The rule population is registered already; what is
missing is the contract each of those rows must satisfy before it can decide anything.

### 1.1 A Rule is not a new registry

`registry/rules.yml` is deliberately **not** proposed. Master ТЗ §8 forbids maintaining one logic in
two places, and this repository spent a day doing exactly that. A rule that comes from the course is
a component row and gains the fields in §2 there; a rule authored here lives where it already lives —
the liquidity rule in `decisions/DR-003-liquidity-rule.md`, the kill criteria in
`registry/criteria.yml`. The form is a contract on the object, satisfied in place.

Ids follow the same principle. A course-derived rule is identified by its course component id
(`M33-T0485-v5.0`); an authored one keeps its `DR-NNN` or criterion id. The seed's third scheme
(`RULE.TREND.PRICE_ABOVE_EMA.001`) is dropped — a fresh id space for objects that already have ids
is how two names for one thing get created.

## 2. The eleven mandatory parts

An object missing any of these is not a rule in this system's sense and may not advance past
`registered`.

| # | Part | What its absence permits | Held today in |
|---|---|---|---|
| 1 | `semantic_claim` — what it is asserting, in one sentence | a gate nobody can argue with because nobody knows what it claims | docstrings |
| 2 | `expression` — the machine form, the sole source of the verdict | prose and code disagreeing, with the prose reviewed | code |
| 3 | `inputs` — components and parameters by id | a rule reading something nobody knows it reads | `parameters:` on the component row |
| 4 | `preconditions` — warm-up, data quality, eligibility | a verdict from an unwarmed input | code |
| 5 | `output` — type and the meaning of each value (§4) | `signal = good` | code |
| 6 | `evaluation` — when it runs and what it may see | look-ahead | `POINT_IN_TIME_SPEC.md` |
| 7 | `missing_data_policy` — what a missing or stale input yields (§4) | the silent substitution `REQ-DATA-002` forbids | code |
| 8 | `scope` — markets, instruments, timeframes, regimes, direction | a US rule silently applied to TSX | **nowhere** |
| 9 | `effect` + `consumed_by` — what it changes and who reads it (§5) | a rule that prints and decides nothing | `consumers:` on the component row |
| 10 | `evidence_status` — hypothesis until an evidence record says otherwise | a hypothesis quoted as a finding | parameter provenance only |
| 11 | `tests` — including the discriminating pair (§6) | an inert gate | unit tests, unlinked |

Two rows have no home in this tree at all. **`scope` exists nowhere as a field** — applicability is
prose in every document that carries it, and `CONSTRAINTS.md` keeps USA and Canada separate by
policy rather than by a field any object declares. **`evidence_status` exists for parameters and not
for rules**: `regime.classifier_rule` carries `validated:PR-002` in `registry/parameters.yml`, but
that is the provenance of a *value*, not the standing of the rule that consumes it.

## 3. The record

Fields only; no invented values. `screen.trend_definition` is `unset` and closed by evidence
(PR-001, PR-005), so the definition slot below stays empty on purpose — this is what a correctly
blocked rule looks like, not a template waiting to be filled in.

```yaml
- rule: M33-T0485-v5.0          # the course id; a rule is not given a second identity
  name: Trend filter
  layer: Decision Logic
  claim_type: Operational Course Rule

  semantic_claim: >
    An instrument whose price structure qualifies as an uptrend on this bar is admissible to the
    breakout playbook. Admissibility is a filter, not a forecast.

  scope:
    markets: [US, CA]           # separate calendars and currencies; never merged (AGENTS 3)
    instrument_types: [stock, ETF]
    timeframes: [1D]
    regimes: []                 # empty = unrestricted; narrowed only by evidence
    direction: LONG

  inputs:
    components: [M25-T0382-v5.0, M12-T0201-v5.0, M12-T0202-v5.0]
    parameters: [screen.trend_definition, screen.trend_pivot_count]

  preconditions:
    warm_up: inherited from the inputs; an unwarmed input yields UNKNOWN, never FALSE
    data_quality: session completeness passed for the decision bar

  expression: swingdesk.decision_logic.trend:is_uptrend   # the verdict comes from here and nowhere else

  evaluation:
    at: BAR_CLOSE
    reads: bars[:i+1] and observation values at i          # POINT_IN_TIME_SPEC
    frequency: EACH_DAILY_BAR

  output:
    type: BOOLEAN
    true_meaning: admissible to the playbook
    false_meaning: not admissible on this bar
    unknown_allowed: true

  missing_data_policy:
    on_missing_input: UNKNOWN
    on_stale_input: UNKNOWN
    on_unset_parameter: REFUSE                             # coded, naming the parameter
    on_calculation_failure: UNKNOWN

  effect:
    class: HARD_GATE                                       # §5
    on_false: Skip
    skip_code: null                                        # see §7 open item
  consumed_by: []                                          # measured, and the finding is in §7

  evidence_status: HYPOTHESIS
  evidence_refs: [PR-001, PR-005]                          # both REFUTED; see CLOSED BY EVIDENCE
  blocked_by: [screen.trend_definition]

  tests:
    discriminating_pair: tests/test_trend.py::test_definition_a_b_c_on_the_same_inputs
    missing_data: tests/test_trend.py::test_definitions_answer_none_when_inputs_have_not_warmed_up
    boundary: null
    stale_data: null
```

## 4. Three-valued output, and what UNKNOWN becomes

`TRUE` · `FALSE` · `UNKNOWN`. `UNKNOWN` never becomes `TRUE` or `FALSE` on its own —
`REQUIREMENTS.md` `REQ-DATA-002`, and the reason it is a requirement rather than a style note is that
its violation is invisible: a neutral substitute produces a plausible number exactly where the
missing input mattered.

Causes of `UNKNOWN`, each distinguishable from a `FALSE`: missing input · insufficient history ·
stale input · unset parameter · unsupported market · calculation failure · sources in conflict.

The tree already implements this three times, in three shapes, and the shapes are not
interchangeable:

| Shape | Where | Reads as |
|---|---|---|
| `bool \| None` | `swingdesk.decision_logic.trend:is_uptrend` | the verdict itself is unknown |
| `ItemState.UNAVAILABLE` | `swingdesk.application.checklist` | the *system* cannot answer, and says what is missing |
| `Refusal(code, reason, parameter_id)` | `swingdesk.trade_management.sizing` | evaluation stopped, with the failing input named |

`CHECKLIST_SPEC.md`'s rule — an unanswerable item is not a pass and not a human question — is this
same distinction at the checklist level, and `HANDOFF.md` §7 states the general form: **`unavailable`
is not `fail`.** A gap in the system and a fact about the trade are different claims.

**Propagation.** A rule reading an `UNKNOWN` input yields `UNKNOWN` unless its expression can decide
without that input. On the decision path an `UNKNOWN` from a `HARD_GATE` or a `VETO` produces
`Skip` or `Pause` with a code from `CODES.md`, never `Trade` and never a silent `Watch`:

| Verdict | Class | Candidate decision | Code |
|---|---|---|---|
| `FALSE` | `HARD_GATE` | `Skip` | the rule's own code |
| `TRUE` | `VETO` | `Skip` | the veto's code |
| `UNKNOWN` | `HARD_GATE` / `VETO` | `Skip`, or `Pause` when the cause is account-wide | `DATA`, `TECH` |
| `UNKNOWN` | `SOFT_FACTOR` | unchanged, contribution withheld | — |
| any | `WARNING` | unchanged | — |

`Pause` is account-wide, not per-candidate (`DECISION_STATE_MACHINE.md` §1), so only a rule whose
failing input is account-wide may raise it.

## 5. Effect classes

The ТЗ names four; the course names three condition kinds in M71 (`STRATEGY_CARD_SPEC.md` §2). They
agree everywhere it matters:

| Class | Course kind | Behaviour |
|---|---|---|
| `HARD_GATE` | обязательный (required) | must hold; failure means the setup does not exist |
| `VETO` | запрещающий (prohibiting) | blocks regardless of any score |
| `SOFT_FACTOR` | подтверждающий (confirming) | adds support; may be absent |
| `WARNING` | — | informs; changes no verdict |

Plus `STATE_TRANSITION` and `EVENT_EMISSION` for rules that move an object rather than judge one —
`swingdesk.trade_management.exits:ExitPolicy.evaluate` is the tree's only example today.

**Binding, and architecturally load-bearing.** `HARD_GATE` and `VETO` are evaluated **outside** any
scoring path and their result cannot be outvoted — `FAIL_CLOSED_POLICY.md` §3, which transcribes the
course stating it as an absolute. Any design in which a composite score clears a critical gate is
wrong by construction regardless of the weights. Weighting applies **within** `SOFT_FACTOR` and
never across classes.

**One class per rule.** A rule that is a gate *and* contributes to a score is two rules, and its
mixed form is how a gate acquires a weight nobody voted for.

**`WARNING` may never be the stated reason a decision changed.** If it was, it was a soft factor
wearing a warning's label, and the record now says something false about how the decision was made.

## 6. Tests — and the mechanism this tree already has

### 6.1 The discriminating pair

`REQ-VALIDATION-001`: every gate, veto or eligibility filter must exhibit two input sets whose
verdicts differ. Absent that pair, the verdict is invariant across all inputs — the rule is
decoration, and decoration in a decision path is worse than nothing because it looks like a control.

The rationale is not hypothetical. `REQUIREMENTS.md` §2 records the TradAlert case: an R:R gate
implemented as `if is_long: return True` passed **seven audits**, because it is a valid function with
valid references. Prose review cannot catch that class of defect; only an executable pair can.

### 6.2 The mechanism exists, and is not yet pointed at rules

`golden/components/` holds **25 vectors across 6 components**, each a JSON case with its inputs, its
pinned parameters, the expected output series, and a `derivation` field stating why that output is
correct. `tools/golden.py` runs them as a merge gate. `M18-T0280-v5.0/warm_up_refusal.json` is
already a missing-data case in exactly the form §2 row 11 requires — it asserts that a
partially-warmed average emits nothing rather than something plausible.

What is missing is the link, not the machinery:

- **The one implemented `Decision Logic` component has `verification: null`.** `M33-T0485-v5.0` is
  the trend filter; the six components with vectors are all `Derived Observations`. The rule layer
  has no vector at all.
- **Its discriminating pair nonetheless exists**, as a unit test:
  `tests/test_trend.py::test_definition_a_b_c_on_the_same_inputs` holds close, short MA and long MA
  fixed and gets `TRUE` from definition A and `FALSE` from definition C on the identical inputs.
  `test_definitions_answer_none_when_inputs_have_not_warmed_up` is the missing-data case.
- **Seven of the eight rules in §7 have a pair; one does not.** Checked test by test, not assumed.
  It was six of eight when this document was written; the eighth gained one when row 2 was fixed.
- **Nothing asserts that a rule has one.** The requirement is met by care, which is the detection
  method `REQ-VALIDATION-001` exists to say does not scale — and the rule still without a pair is
  the ratified kill criterion, which cannot have one until its parameter is set.

### 6.3 The required sets

| Set | Asserts |
|---|---|
| `discriminating_pair` | the verdict depends on the inputs |
| `positive` / `negative` | it fires, and it declines |
| `boundary` | behaviour at equality — strict versus non-strict is a **specified property** |
| `missing_data` | a missing input yields `UNKNOWN`, not a default |
| `stale_data` | a stale input yields `UNKNOWN` |

The boundary row has a precedent worth copying: pivot detection is strict on the left and non-strict
on the right, and `golden/components/M12-T0201-v5.0/plateau_keeps_first_bar.json` pins it. Both sides
strict and a flat double top vanishes; both sides loose and every bar of a plateau registers. The
asymmetry is a decision, and it is recorded as one.

### 6.4 The mutation invariant

The system-level form of the same requirement: forcing a rule's verdict to its inverse **must**
change at least one outcome in the test corpus. A rule whose inversion changes nothing is inert, and
the build should fail.

`REQUIREMENTS.md` §5 records `mutation_test` as the one verification method that **does not exist**
here. §9 below states the cheap subset that would have caught the live instance.

## 7. Audit — what is a rule in this tree today

Eight decision points produce verdicts. Measured against §2, not against intent.

| # | Rule | Where | Class | 3-valued | Discriminating pair | Gap |
|---|---|---|---|---|---|---|
| 1 | Trend filter (5 candidate definitions) | `swingdesk.decision_logic.trend` | `HARD_GATE` | yes | `test_trend.py::test_definition_a_b_c_on_the_same_inputs` | no vectors; `consumed_by` empty; no `scope` |
| 2 | Breakout trigger | `validation/backtest/engine.py` | `HARD_GATE` | **yes, since 2026-08-08** | `test_backtest.py::test_a_bar_with_no_lookback_window_is_not_a_rejected_signal` | no `scope`; the live path has no trigger at all |
| 3 | Exit policy (protective, gap, time) | `swingdesk.trade_management.exits` | `STATE_TRANSITION` | n/a | `test_backtest.py`, `test_positions.py` | two of four course slots implemented (`EXIT_MODEL_SPEC.md`) |
| 4 | Sizing refusals | `swingdesk.trade_management.sizing` | `HARD_GATE` | yes | `test_invariants.py::test_stop_at_or_above_entry_always_refuses` | — |
| 5 | Liquidity / universe rule | `swingdesk.application.universe`, `DR-003` | `HARD_GATE` | yes | `test_universe_selection.py::test_a_symbol_the_store_has_never_seen_is_not_measured_and_not_admitted` | plateau re-check pending full coverage |
| 6 | Session completeness | `swingdesk.market_data.completeness` | `HARD_GATE` | yes | `test_pipeline.py::test_missing_session_raises_data` vs `::test_half_day_does_not_raise_data` | — |
| 7 | Pre-trade checklist items | `swingdesk.application.checklist` | mixed | yes | partial — `test_checklist.py` | 5 of 18 answerable, by design and stated |
| 8 | Success and kill criteria | `registry/criteria.yml` | `HARD_GATE` | no | **none** | `k.drawdown_pause` was inert until 2026-08-08 — §9 |

Row 6 is the model the others should be read against. A missing session raises `DATA`; a half-day
and a US/Canada calendar divergence do not. Three tests, one pair of verdicts, and the rule's meaning
is pinned by the cases that must *not* fire as much as by the one that must.

Four of the eleven parts are absent across **every** row: `scope`, `evidence_status`, a declared
`effect.class`, and a link from the rule to its tests. Those are the four fields a rule contract
would add, and none of them requires new logic.

**Row 2 carried a real defect, and it is the reason this document exists in this form.** In
`run_arm`, a bar with no trigger window and a bar that genuinely failed the trigger took the same
branch: `if threshold is None or bar.close <= threshold: continue`. Two consequences, both about the
record rather than the trades:

1. `UNKNOWN` was collapsed into `FALSE` — the exact substitution `REQ-DATA-002` forbids. Harmless
   *there* because both cases correctly produce no entry, and not harmless as a habit.
2. Neither case incremented `signals` or any counter, so the first `lookback` bars of every
   instrument left the denominator silently.

**Fixed 2026-08-08**: the two cases are separate branches and the unanswerable one increments
`ArmResult.unevaluable_bars`, which is deliberately not a `Skipped` reason —
`EXECUTION_MODEL.md` §5 has the full account and the reason for the separate field.

The general form is what to take from it: a rule that cannot answer and a rule that answers "no"
must be distinguishable **in the record**, not only in the code path. Nothing downstream
distinguished them here, which is exactly why nobody noticed.

**Row 8 was the inert gate this project already owned.** `k.drawdown_pause` is ratified and its
trigger references `validation.max_allowable_drawdown`, which was `unset` along with all fifteen
`validation.*` parameters — so its verdict was invariant across every input the system could produce,
a `HARD_GATE` that could not fail. Found by hand on 2026-08-03.

`DR-005-validation-thresholds.md` proposes values for all fifteen (2026-08-08), which makes the
criterion able to evaluate. **It still has no discriminating pair**, because nothing exercises it —
there is no realised drawdown to test against, and the threshold itself is the weakest value in that
record. The gate went from unable to fail to untested, which is progress and is not the same as
working.

## 8. Weights, scoring and double counting

**Measured: this tree has no scoring path.** Nothing sums signals, nothing weights them, and the
decision path is a sequence of gates from the universe rule through completeness, warm-up and sizing
to `Watch`. So the correlated-factor failure is not reachable today, and the form's job is to keep it
unreachable by accident.

If a score is ever introduced:

1. **A weight is a registry parameter**, `unset` until calibrated — never a literal in a rule body.
   `PARAMETER_REGISTRY.md` §4 already makes an unset parameter a refusal, so a rule whose weight is
   unset cannot reach runtime. That is the whole enforcement mechanism, and it is already built.
2. **Rules measuring one factor form a group with a capped total contribution.** Price above a
   short MA, price above a long MA, the stack, and MA slope are four expressions of one measurement,
   and summing them is counting one fact four times.
3. **Marginal contribution is established by ablation**, per rule, before the rule earns a weight —
   `PREREG_TEMPLATE.md`, and PR-001/PR-005 are the precedent for what "establish" costs.
4. **A gap bar is the named failure mode.** One number enters ATR, the range, and any momentum
   measure simultaneously, so formally independent rules reading a gap bar are near-perfectly
   correlated on exactly the bar where the position is largest and the stop widest. This belongs in
   every affected rule's `failure_modes` rather than in one place.

## 9. Invariants that can be checked, ranked by cost

| Check | Extends | Cost | Would have caught |
|---|---|---|---|
| ~~every ratified criterion's referenced parameters are set~~ | **landed 2026-08-08 as gate 3g**, `tools/verify_criteria.py` | done | `k.drawdown_pause` |
| every rule with a verdict names a discriminating-pair test that exists | `tools/verify_components.py` (gate 11) | hours | rows 2 and 8 above |
| `consumed_by` non-empty for any rule on the decision path | gate 11 | hours | a decorative rule |
| one `effect.class` per rule; no rule both gates and scores | gate 11 | hours | a weighted gate |
| forcing a rule's inverse changes ≥1 verdict in the corpus | new gate, needs a corpus | days | an inert gate with a live test |

The first row is done. It cost about eighty lines, and the join between the two registries was
indeed four of them — the rest is naming *which* criterion and *which* parameter, because a gate that
says only "failed" sends the reader back to do the work it just did. It also grew a check the
requirement implies rather than states: a criterion's `status` must be on the declared ladder, since
a typo there would exempt the row from the parameter check and make the gate quietly weaker rather
than loudly wrong.

`CI_POLICY.md`'s standing rule applies to all of them — a gate that is wrong gets fixed or removed,
never skipped.

## 10. Open items

- [ ] **Skip code per gate.** §3's record leaves `effect.skip_code` null for the trend filter because
      `CODES.md`'s twelve are the course's and none of them means "failed the trend filter". Either a
      gate maps to an existing code or the mapping is `REGIME`/`SECTOR`-shaped and needs stating.
      Adding a thirteenth code is a course-version change and is not the answer.
- [ ] **`scope` as a field, not prose.** Cheapest place is the component row. Blocked on nothing;
      listed here so it is a decision rather than an omission.
- [x] ~~**Row 2's collapsed `UNKNOWN`**~~ — **done 2026-08-08** (§7). Two branches plus a counter and
      a test; no trade moved and the reported denominator is now stated rather than implied.
- [ ] **`M33-T0485-v5.0` has `verification: null`.** Its tests exist; the vector form for a rule —
      inputs, verdict, derivation — is not yet defined. Defining it is what turns §6.2 from a
      description into a gate.
- [ ] **Whether `evidence_status` on a rule may exceed the status of the parameters it consumes.** It
      should not, and the tree has no instance yet. Decide before the first one.
