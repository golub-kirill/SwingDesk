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
- **Expected values are authored from the source arithmetic, not recorded from the implementation.**
  Each vector carries a `derivation` field stating how its numbers follow from the formula. A vector
  that only records what the code printed cannot tell you the code was ever right — it can only tell
  you the code has not changed.

They live in `golden/components/<component-id>/`, with a `manifest.json` holding a SHA-256 per
vector. Central rather than beside the source, because two different gates read them and one of
them is not `pytest`. The hash is the load-bearing part: without it, the cheapest way past a failing
vector is to paste in whatever the code now prints, which converts the gate into a formality.

`tools/golden.py --regenerate` exists for a deliberate version bump. It is not a way to fix a red
build.

### What a golden vector cannot do

Freeze behaviour, yes. Prove correctness, no. If a hand-derivation and an implementation share the
same misreading of the definition, they agree and the vector passes — so a component with no
external oracle needs two more layers, both free:

| Layer | Catches | Example |
|---|---|---|
| **differential** | an implementation bug the authored cases did not reach | breadth recomputed in pandas over randomised panels — different code, same definition |
| **metamorphic** | a shared misreading, by constraining how the answer must *change* rather than what it is | scale every price and breadth is unchanged; shift every reading and the regime labels are unchanged, because percentile thresholds are equivariant |

Metamorphic relations are the technique for a component nothing can be checked against. You cannot
say what the right answer is; you can say that scaling the inputs must not change it, and a
component failing that is wrong regardless of what any expected value claims.

**Six components have vectors, 25 in total.** ATR was first — Wilder's seed, the smoothing
recursion, all three true-range branches, the zero-range boundary, warm-up refusal, and a
non-default period to prove the parameter is read rather than hard-coded.

Not every component takes one instrument's bars, so the vector format carries a `kind`:

| `kind` | Shape | Components |
|---|---|---|
| `series` | one `BarSeries` in, one value per bar out | ATR, SMA, swing high, swing low |
| `panel` | many members in, one value per session out | breadth |
| `fit_apply` | a training window in, thresholds plus point answers out | regime |

Forcing the last two through a bar-series loader would have meant either no vectors for them — which
is exactly how `breadth` and `regime` came to be used by a reported study with none — or a loader
that lies about its inputs.

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

## 8. Proving a gate can fail

A gate that cannot be made to fail is theatre, so the gates guarding *change over time* have tests
that break something on a copy of the fixtures and assert the breakage is reported — and reported
with the right cause:

| Broken deliberately | Must be reported as |
|---|---|
| a vector edited without rehashing | content changed |
| a vector's input changed, then rehashed | a value mismatch at a named index |
| a new vector left out of the manifest | unregistered |
| a component version moved without its vectors | version bump required |
| the recorded replay snapshot edited | fixture edited — **not** non-determinism |
| a parameter value changed | `config_hash` changed — **not** non-determinism |

The last two matter more than they look. A gate that reports every mismatch as non-determinism will
fire on the first config edit, and the operator will learn to disbelieve it.

## 9. Open items

- [x] ~~Property-test library~~ — Hypothesis, declared in the `dev` extra.
- [x] ~~Where golden vectors live~~ — `golden/components/`, centrally (§3).
- [ ] Whether the nightly replay uses the previous real run or a rolling fixture. Real is stronger;
      it also means a genuine vendor revision looks like a failure until triaged.
