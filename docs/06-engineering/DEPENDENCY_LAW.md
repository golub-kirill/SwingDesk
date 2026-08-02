# DEPENDENCY LAW

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored, enforcing tier 2

**Enforced by:** `[tool.importlinter]` contracts in `pyproject.toml`, run in CI.

An architecture rule that is not executed is decoration. Every rule here maps to a contract that
fails the build.

---

## 1. The rules and where they come from

Production rules §3.8 states five independence rules. Each is transcribed in
`LIFECYCLE_AND_LAYERS.md` §5; here is how each is *enforced*.

| Course rule | Contract | Type |
|---|---|---|
| "indicators do not own strategy decisions" | layered architecture — `derived_observations` sits below `decision_logic` and cannot import it | `layers` |
| "patterns and classifiers produce observations, not orders" | same layer contract; `trade_management` is above `decision_logic` | `layers` |
| "strategies do not fetch or normalize their own private version of shared facts" | `derived_observations` and `decision_logic` may not import `market_data` | `forbidden` |
| "management and exit policies may be attached to multiple strategies without duplicating logic" | one implementation per decision — review rule, not yet mechanised (§4) | — |
| "changing a shared component never silently rewrites historical evidence" | evidence records pin component versions (`EVIDENCE_RECORD_SPEC.md`) | — |

Plus two rules this project adds, both derived from the purity boundary in `ARCHITECTURE.md` §3:

| Rule | Contract | Type |
|---|---|---|
| pure layers do not journal | `derived_observations`, `decision_logic` ✗→ `journal_evidence` | `forbidden` |
| the journal depends only on `platform` | `journal_evidence` ✗→ every other context | `forbidden` |

## 2. The layer chain

```
presentation → validation → trade_management → decision_logic
    → derived_observations → market_data → reference_data → platform
```

A package may import anything **below** it and nothing above. `import-linter`'s `layers` contract
enforces the whole chain in one rule.

`journal_evidence` is deliberately absent from the chain. Placing it anywhere would permit an import
we forbid: put it low and `decision_logic` could journal (breaking purity); put it high and
`trade_management` could not journal (breaking the trace). Two `forbidden` contracts express the
real shape.

## 3. Adding a package

1. Decide which layer it belongs to, or that it is a service outside the chain.
2. Add it to the `layers` list, or add its `forbidden` contracts.
3. If it is a service, state explicitly what may import it and what it may import.
4. If neither fits, that is a signal the context map is wrong — fix `ARCHITECTURE.md` first.

A package that cannot be placed is not a packaging problem. It usually means it does two things.

## 4. Not yet mechanised

Honest list — these are review rules today, and each is a candidate for a check:

- **One implementation per decision.** The course requires a component have "one canonical
  definition" and that strategies "reference components rather than copying their formulas". Two
  functions computing the same thing pass import-linter cheerfully. Detecting it needs the component
  registry to record which module implements which component id, then asserting the mapping is
  injective. Worth doing before the catalogue grows.
- **No wall clock in domain packages.** A grep-level CI check (`datetime.now`, `date.today`,
  `time.time` under `derived_observations` and `decision_logic`). Cheap; schedule with `CI_POLICY.md`.
- **No unordered iteration feeding output.** Harder to detect statically; covered instead by the
  determinism check — same inputs must produce byte-identical output across two runs.
- **Non-compensatory gates.** The rule that a score may never clear a critical gate
  (`FAIL_CLOSED_POLICY.md` §3) is a property of the decision engine's shape. Best enforced by
  construction — critical gates evaluated outside the scoring path entirely — plus a property test,
  not by import analysis.

## 5. Running it

```bash
lint-imports
```

Contracts live in `pyproject.toml` under `[tool.importlinter]` so there is one config file, not two.
