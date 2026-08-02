# TEST STRATEGY

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

---

## 1. Layers

| Layer | Proves | Runs |
|---|---|---|
| **unit** | a function does what its spec says on chosen cases | every commit |
| **property** | an invariant holds for *any* input | every commit |
| **golden vector** | behaviour has not changed since it was frozen | every commit |
| **contract** | a cross-context record matches its schema | every commit |
| **integration (recorded)** | adapters work against real vendor responses, replayed from fixtures | every commit |
| **replay** | a stored manifest reproduces its `output_hash` | every commit (fixture) · nightly (real run) |
| **chaos** | the fail-closed paths actually fire | nightly |

No layer touches the network (`CI_POLICY.md` §4).

## 2. Property tests carry the invariants

`INVARIANTS.md` is not prose to be read — each entry is a property test. The ones already identified:

| Invariant | Source |
|---|---|
| R denominator is always the **initial planned** risk, across stop moves and partials | `RISK_SPEC.md` §2 |
| open risk is recomputed, never decremented | `RISK_SPEC.md` §2 |
| shares always round **down** | Appendix C |
| stop is set before size | `RISK_SPEC.md` §3 |
| a stop change increasing risk is rejected | `CODES.md` `WIDE_STOP` |
| no decision uses data whose `knowledge_time` exceeds the decision time | `POINT_IN_TIME_SPEC.md` §2 |
| identical inputs always yield an identical classification | M32/M33 — `Два наблюдателя дают одинаковый статус` |
| shuffled input order yields identical output | `DETERMINISM_SPEC.md` §7 |
| an unset parameter yields a coded refusal, never a value | `PARAMETER_REGISTRY.md` §4 |

That seventh is the course's own acceptance criterion for a setup detector, restated as a testable
property. It is stronger than it looks: it forbids any classifier whose output depends on anything
not in its declared inputs.

## 3. Golden vectors are the immutability mechanism

A golden vector is a frozen input → frozen output pair, checked in, with a hash manifest.

They are what make `COMPONENT_REGISTRY_SPEC.md` §6 enforceable rather than aspirational: changing
behaviour requires bumping the component version, regenerating the vectors, writing a decision
record, and resetting validation status. **A silent behaviour change is impossible** because the
diff shows up in CI as a blocking failure.

Rules:

- Every `active` component has golden vectors. That is part of what `active` means.
- Vectors use `TEST.1`, `TEST.2` … synthetic instruments, never real tickers — a vector referencing
  a real name invites someone to "fix" it against current market data.
- A changed vector blocks the merge unless the same commit carries the decision record.

## 4. Fixtures, and where they come from

| Fixture | Source |
|---|---|
| vendor responses | recorded once from a real call, then replayed forever |
| bar data | a small pinned snapshot — a handful of instruments, spanning a half-day, a holiday divergence and a known vendor gap |
| calendar | pinned `pandas_market_calendars` version (`ADR-0002`) |

The bar fixture deliberately includes the three pathologies already measured: a US half-day, a
session where one exchange is closed, and a confirmed vendor gap. Those are the cases that break
things, so they belong in the fixture rather than in a "known issues" list.

## 5. Coverage targets by stability tier

Uniform coverage targets are noise. Targets by what the code is:

| Tier | Target |
|---|---|
| immutable core — risk formulas, statistics, exits, point-in-time queries | **100% branch**, plus properties and golden vectors |
| stable — screener, regime, journal | high, with properties on the invariants |
| volatile — presentation, reports, CLI wiring | smoke tests; do not chase coverage in code that is mostly formatting |

Appendix C and D arithmetic sits in the first row. They are eleven formulas each, they are the whole
computational basis of the system, and they are cheap to cover exhaustively.

## 6. Chaos scenarios

The fail-closed paths must be *tested*, not assumed. One scenario per row of the degradation table
(`FAIL_CLOSED_POLICY.md` §2):

| Scenario | Expected |
|---|---|
| vendor returns nothing | last valid snapshot served, new decisions stopped |
| vendor returns a truncated session | `DATA` skip for that session |
| two sources disagree beyond tolerance | conflict surfaced, `DATA` skip, **no averaging** |
| a required parameter is unset | coded refusal naming the parameter |
| screener crashes mid-run | automated signals invalid; manual universe path available |
| stale data on an open position | new entries blocked, position management still reachable |

The last one matters disproportionately: a data failure must never lock the owner *out* of managing
risk on positions already open.

## 7. What is deliberately not tested

- Vendor availability. Not ours, and testing it makes the suite flaky.
- That a strategy is profitable. That is Track B evidence, not a test
  (`SUCCESS_AND_KILL_CRITERIA.md`).
- UI appearance.

## 8. Open items

- [ ] Property-test library — Hypothesis is the obvious choice and is not yet a dependency.
- [ ] Where golden vectors live: alongside the component or centrally. Alongside keeps them visible
      in review, which is where they do their work.
- [ ] Whether the nightly replay uses the previous real run or a rolling fixture. Real is stronger;
      it also means a genuine vendor revision looks like a failure until triaged.
