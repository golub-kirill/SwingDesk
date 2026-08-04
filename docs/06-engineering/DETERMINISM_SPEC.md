# DETERMINISM SPEC

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

---

## 1. Why this is a requirement, not a preference

Three independent parts of the system already depend on it:

| Source | Requirement |
|---|---|
| `criteria.yml` `a.reproducible` | a re-run from a manifest reproduces the control run **byte-identically** — a ratified Track A criterion |
| `FAIL_CLOSED_POLICY.md` row 3 | the return condition after a screener failure is `повторный run совпал с контрольным` — **the course states determinism as an operating procedure** |
| `ARCHITECTURE.md` §3 | the purity boundary exists to make it achievable |

And §3.8 of the production rules makes it the definition of a valid conclusion:

> "A conclusion that cannot be reproduced from its recorded inputs and versions is a production
> defect."

## 2. Scope — what must be deterministic

**The decision path**: `derived_observations` → `decision_logic` → `trade_management`.

Given the same snapshot, the same config and the same component versions, these must produce
byte-identical output on every run, on this machine, forever.

**Not in scope:** how long a fetch took, which vendor responded first, the order network requests
completed in, log timestamps. Those are *observations about the run*, not inputs to the decision —
and the boundary between the two is §4.

## 3. The rules

### 3.1 No wall clock in domain code

Time is **injected**. A domain function that needs "now" receives it as an argument.

Forbidden in `derived_observations`, `decision_logic`, `trade_management`:
`datetime.now()` · `date.today()` · `time.time()` · `datetime.utcnow()`

Enforced by a CI grep (`CI_POLICY.md`). This is cheap to check and impossible to enforce by review
alone — it takes one hurried commit to break reproducibility invisibly.

### 3.2 Stable ordering everywhere

Unordered iteration feeding output is the most common source of silent non-determinism.

- Every collection that reaches output is **canonically sorted** before it does.
- `set` iteration never feeds a result directly.
- `dict` ordering is insertion-ordered in Python and therefore stable — but only if insertion order
  is itself deterministic, which pushes the problem up one level rather than solving it. Sort at the
  boundary.
- Every merge point after parallel work **re-imposes a canonical sort** (`ARCHITECTURE.md` §6).

### 3.3 Floating-point addition is not associative

This is the trap specific to parallel backtests, and it is easy to miss because the code looks
correct.

`(a + b) + c != a + (b + c)` in floating point. So a sum computed across N processes and combined
depends on **how the work was split** — and if the split depends on timing or core count, the result
is not reproducible even though every process is individually deterministic.

Rules:

- Parallelism is permitted for **independent** units (one instrument, one window, one backtest arm).
- Aggregation across those units happens in **one place, in canonical order**, single-threaded.
- Money is integer minor units or `Decimal` — exact, and the question does not arise.
- Where floats must be aggregated, the order is fixed by sort key, never by completion order.

### 3.4 Seeded randomness

Any stochastic procedure — bootstrap CIs, Monte Carlo robustness, sampling — takes an explicit seed,
and the seed is recorded in the run manifest. There is no unseeded RNG anywhere.

### 3.5 Pinned inputs

| Input | Pinned by |
|---|---|
| data | snapshot id — a named `knowledge_time` (`POINT_IN_TIME_SPEC.md` §5) |
| code | commit hash |
| config | config hash |
| component behaviour | component versions |
| dependencies | lockfile |
| platform | this machine — see §6 |

## 4. The determinism boundary

Fetching is concurrent, rate-limited and timing-dependent. That is fine, because **fetching writes
facts, it does not make decisions**.

```
market_data (concurrent, non-deterministic timing)
        │
        ▼   writes facts with knowledge_time
   ┌────────────────┐
   │  THE BOUNDARY  │   snapshot: a named knowledge_time
   └────────────────┘
        │
        ▼   reads a pinned snapshot
decision path (single-threaded, deterministic)
```

The snapshot **is** the boundary. Above it, order and timing vary. Below it, nothing does.

This is why the decision path never fetches — not merely to keep layers tidy, but because a fetch
inside a decision would put non-determinism on the wrong side of the line.

## 5. The run manifest

Written by every run, before any work:

| Field | Purpose |
|---|---|
| `run_id`, `started_at` | identity (not an input) |
| `code_hash` | git commit, plus a dirty flag |
| `config_hash` | full resolved config |
| `snapshot_id` | the pinned `knowledge_time` |
| `component_versions` | every component that participated |
| `parameter_values` + provenance | what the thresholds were, and where they came from |
| `seed` | for any stochastic step |
| `calendar_version` | `pandas_market_calendars` version (`ADR-0002`) |
| `platform` | OS, Python, key library versions |
| `output_hash` | hash of the produced result |

A replay takes a manifest and reproduces `output_hash`. If it does not match, **the run is a defect**
— either something is non-deterministic or something was not pinned. Both are bugs, and the manifest
narrows which.

## 6. Honest scope limits

- **Reproducibility is guaranteed on this machine, this platform.** Cross-platform float behaviour
  and library-version differences can change last-bit results. Single-user on one machine
  (`CONSTRAINTS.md` §7) makes that acceptable — but it is a stated assumption, not a property.
- **Reproducibility of a *past* run requires its snapshot to still exist.** Retention is indefinite
  for exactly this reason (`POINT_IN_TIME_SPEC.md` §8).
- **A vendor changing history does not break determinism** — it creates a new `knowledge_time`. The
  old snapshot still reproduces. That is the whole point of the bitemporal store.

## 7. Verification

| Check | When | Status |
|---|---|---|
| no wall clock in domain packages | every CI run | **runs** — AST-parsed |
| replay a stored manifest, compare `output_hash` | every CI run, on a small fixture | **runs** — `tools/replay.py` |
| replay the previous real run | nightly / before any release | to build |
| property test: shuffled input order → identical output | every CI run | **runs — on `breadth`** |

That last one is the strongest of the four: it catches ordering dependence directly, rather than
waiting for it to surface as an unreproducible result. Its scope needs stating, because "runs"
on its own reads as general coverage and it is not: `breadth` is the **only** component whose
input is an unordered collection. Every other one takes a `BarSeries`, which rejects unordered
input at the boundary, so there is no shuffle for them to be invariant to. `INVARIANTS.md` §3
carries the audit and names the one thing this does not cover — nothing forces a *future*
unordered-input component to bring its own invariance test.

### 7.1 What a replay case must pin

A case is a directory under `golden/replay/`: recorded bars, the inputs that select them, and the
manifest the run produced. Three things it must get right, each learned by getting it wrong:

1. **The case pins its own inputs.** `inputs_digest` covers the recorded bars, instruments,
   parameters and as-of. Without it, editing the fixture produces a different output and the gate
   blames the decision path — a false accusation, and the fastest way to make a gate distrusted.
2. **`config_hash` covers parameter *values*, not just which ids are set.** The first version hashed
   set-ness alone, so changing a threshold left it unmoved and the mismatch looked like
   non-determinism.
3. **The fixture's data must be sensitive to the parameters.** The first recorded case walked its
   closes upward with fixed high/low offsets, which made every true range identical at 2.00 — so the
   ATR was the same for any period, and the case was blind to the parameter it claimed to pin. Bars
   now vary their range on coprime cycles.

The current case covers all four decision branches: a candidate that sizes, a second exchange whose
calendar diverges, a warm-up refusal, and a vendor that returned nothing. A fixture that exercises
only the happy path pins the least interesting third of the run.

## 8. Open items

- [ ] Whether `output_hash` covers the full trace or just the decisions. It covers decisions,
      bar counts and the latest observation today. Full trace is stricter and catches more, but will
      churn on cosmetic changes — which trains people to ignore it.
- [ ] Whether a dirty working tree is allowed to produce a journalled run at all, or only a
      scratch one. The manifest records `code_dirty` and the replay diagnosis reports it, but
      nothing refuses.
