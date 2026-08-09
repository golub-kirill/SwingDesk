# DRIFT AND LEARNING

**Status:** drafting · **Tier:** 5 (validation) · **Content:** authored, audited against the tree

Master ТЗ v1.0 **§45** (drift monitoring) and **§44** (learning engine), the last two absent sections
that were blocked on substance rather than on writing time.

**Why one document.** Drift without a response is a dashboard; a response without measurement is
tinkering. The ТЗ separates them and this tree cannot: every threshold that would trigger a response
is a drift measurement, and every drift measurement that leads nowhere is a number nobody acts on.
They are written together so the second half cannot be forgotten.

**Why tier 5.** The measuring half looks like observability, but what it feeds is the validation
ladder — a component's status changing because the world changed is the same machinery as a status
changing because a study reported.

---

## 1. The course already specifies the learning engine, and it forbids the naive one

This is the finding, and it inverts the ТЗ's framing. §44 asks for an "offline-learning promotion
path" as though nothing existed. Module 69's **acceptance enum** is exactly that path, it is
transcribed in `DECISION_STATE_MACHINE.md` §4, and it is connected to nothing:

| State | Criterion | Next action |
|---|---|---|
| `Принять` | the rule is confirmed by data, version and a checkable artefact | use it **within the proven area** |
| `Продолжить сбор` | the sample is small or the result unstable | **do not change the system**; collect more observations |
| `Исправить процесс` | a repeated, controllable violation was found | add a checklist item or a technical block |
| `Остановить` | critical risk, leakage or a technical error | suspend use and audit |

**`Продолжить сбор` is the whole design.** *Не менять систему* — do not change the system while
collecting. That single clause forbids the loop most "learning engines" implement: observe a
degradation, adjust a parameter, observe again. The course's own anti-tinkering rule says the
adjustment is not permitted while the evidence is still accumulating, and the reason is that a system
changed mid-sample has no sample.

So the learning engine's output set is **not** a parameter update. It is one of four verdicts, three
of which change nothing about the rules:

- `Принять` narrows or confirms scope. It does not retune.
- `Продолжить сбор` explicitly changes nothing.
- `Исправить процесс` changes the **checklist**, not the strategy — the operator's process is what
  failed, not the rule.
- `Остановить` suspends. Also not a retune.

**Nothing in the course authorises automatic parameter adjustment from observed outcomes.** A
learning engine here promotes, demotes, narrows or halts; it does not fit.

## 2. What drift is measured against

An expectation (`EXPECTATION_MODEL.md`). Drift is the difference between two estimates for one
cohort at two as-of dates, so both terms must be addressable before anything can be differenced.

**Zero expectations are stored today**, which is why §45 outranked nothing and why this document
could not have been written first. What follows is therefore specified against the object rather
than against data.

## 3. The five drift families, and which this project can see

The split that matters is not conceptual — it is whether free data plus D1 permits the measurement
at all.

| # | Family | What moves | Computable today? |
|---|---|---|---|
| 1 | **Data drift** | completeness, revisions, vendor gaps, session shape | **yes** — `market_data.completeness` already computes findings per run |
| 2 | **Universe drift** | membership churn, departures, liquidity migration | **yes** — the directory store's `departures()`, and `UniverseSelection` records `eligible`/`measured` per run |
| 3 | **Feature drift** | the distribution of a derived observation over the universe | **yes** — ATR, breadth and the moving averages are computed from bars alone |
| 4 | **Regime drift** | label distribution and **flip rate** | **yes**, and the metric already exists — PR-002 selected `BREADTH_MEDIAN` on *stability*, measured as label flips per 100 sessions |
| 5 | **Expectation drift** | realised outcomes against a stored estimate; slippage against the model | **no** — needs executed fills |

**Four of five are computable and none is computed.** That is the actionable half of this document:
the machinery for families 1–4 exists and produces numbers every run, and nothing compares those
numbers to yesterday's.

**Family 5 is the one that matters for the strategy, and it is structurally blocked.**
`UX_TASK_FLOWS.md` §1 counts the post-trade phase at **0 of 6**, §2 itemises it and §3 explains
why: every item needs executed fills, D1 means this system never executes, the trades happen in the owner's broker, and
nothing imports them back. Expectation drift and slippage drift are not hard here — they are
unreachable without an import path the charter does not scope.

**PR-002's stability metric is the template for the other three.** It is worth naming because it was
invented for a different purpose and generalises exactly: *count how often the label changes per 100
sessions, and prefer the variant that changes less.* A drift monitor is the same measurement applied
over time instead of across variants.

## 4. Cadence and thresholds

Every threshold below is `unset`, and that is the honest state rather than an oversight — a drift
alarm with a guessed threshold cries wolf until it is disabled.

| Family | Natural cadence | Threshold parameter | Status |
|---|---|---|---|
| Data | per run | `data.max_missing_sessions_per_instrument`, `data.source_conflict_tolerance` | `unset` |
| Universe | per refresh pass | — none exists | not registered |
| Feature | weekly, over the universe | — none exists | not registered |
| Regime | per run | — none exists; PR-002's flips/100 is the measure | not registered |
| Expectation | per closed trade, rolling | `stats.rolling_window` | `unset`, and required by M69 |

**Three of the five have no parameter at all.** Registering them is cheap and belongs with the first
implementation rather than ahead of it — `AGENTS.md` §7 requires a `named_in` citation, and inventing
five entries the course never mentions would be scope wearing a registry's clothes.

## 5. The response ladder

Drift is an observation. It becomes an action only through the acceptance enum in §1:

| Observation | Verdict | What changes |
|---|---|---|
| A metric moved and the sample is still small | `Продолжить сбор` | **nothing.** Record and keep collecting |
| A metric moved past a threshold, sample sufficient | `Принять` with narrowed scope | the component's *applicability*, not its parameters |
| The operator repeatedly did something the rules forbid | `Исправить процесс` | a checklist item, or a technical block |
| Leakage, a technical error, or risk that cannot be bounded | `Остановить` | the component is suspended and audited |

**A drift alarm never edits a parameter.** If a value should change, that is a decision record or a
pre-registration — the same instruments as any other threshold change — and it carries the
consequence `COMPONENT_REGISTRY_SPEC.md` §6 attaches: a parameter change bumps the component version
and **resets its validation status**. Learning that silently retunes would erase the evidence it
claims to be responding to.

`PREREG_TEMPLATE.md` §3 states the other half: amending after seeing the data downgrades a study to
exploratory. A loop that re-fits on drift is that amendment, applied continuously.

## 6. What must never be built here

Recorded as prohibitions because each is a plausible next feature that would quietly break something
already ratified:

1. **Automatic parameter adjustment from observed outcomes.** §1 — the course forbids it, and
   `REQ-EVIDENCE-001` requires a validation stage to reference a run that actually executed.
2. **Refitting a classifier on a rolling window without a new pre-registration.** PR-002 fitted
   thresholds on train only and selected on validation by stability; a rolling refit discards that
   discipline while keeping its reported result.
3. **A drift score that aggregates families.** Data, universe, feature, regime and expectation drift
   fail for different reasons and demand different responses; one number hides which. This is the
   non-compensation rule (`FAIL_CLOSED_POLICY.md` §3) applied to monitoring.
4. **Alarming on family 5 with modelled costs.** `costs.slippage_model` is `assumed:DR-004`, so
   "slippage drifted" would frequently mean "the assumption was wrong from the start", which is a
   different finding and is `EXECUTION_MODEL.md` §6's open item rather than a drift event.

## 7. What can be built today, ranked

Only the first is worth doing before a live record exists:

1. **Record what the run already computes.** Completeness findings, universe `eligible`/`measured`,
   and the regime label are produced every run and kept only in the run's own result. Storing them
   per run is the substrate for families 1, 2 and 4, and it costs one table.
2. Feature-distribution snapshots over the universe — cheap, and pointless until something consumes
   them.
3. Everything in family 5 — blocked on a post-trade loop that D1 places outside this system.

## 8. Open items

- [ ] **The drift record has no home.** It is the third object in three documents asking the same
      question — `TRANSITION_SPEC.md` §11 (one table or four shapes) and `EXPECTATION_MODEL.md` §10
      (where an estimate is stored) are the other two. They should be answered together, once.
- [ ] **Three families have no threshold parameter** (§4). They want registering with the first
      implementation, not before it.
- [ ] **Whether `Исправить процесс` can be raised automatically.** It is the one verdict whose
      trigger — a repeated operator violation — is computable from the journal's error codes without
      any new data. It may be the only part of the learning engine reachable before a post-trade
      loop exists.
- [ ] **Nothing here is enforceable until family 5 exists**, and family 5 needs the broker import
      the charter does not scope. That is a charter question, not an engineering one, and
      `UX_TASK_FLOWS.md` §3 and §4 already state it plainly.
