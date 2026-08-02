# CONCURRENCY MODEL

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

---

## 1. Three tiers, three different rules

| Tier | Work | Model | Determinism |
|---|---|---|---|
| **Fetch** | vendor I/O | async or thread pool, rate-limited per vendor | not required |
| **Compute** | backtests, sweeps, feature builds over independent units | process pool | per-unit only |
| **Decide** | observations → conditions → decisions → sizing | **single-threaded** | **required, byte-identical** |

The tiers are separated by the snapshot (`DETERMINISM_SPEC.md` §4). Concurrency above it; none
below.

**The decision path is not a place to optimise.** `NFR.md` budgets it at ≤5 minutes for ~1,500
instruments, which single-threaded Python comfortably meets. Making it concurrent would buy nothing
and cost the one property the system is built around.

## 2. Fetch tier

### Rate limiting

Per **vendor**, not global — the limits differ and one vendor's backoff must not throttle another.

| Vendor | Constraint |
|---|---|
| Yahoo (`yfinance`) | undocumented and unofficial; treat as fragile, back off aggressively on any 4xx/5xx |
| Questrade | documented limits, HTTP 429 on breach; second-source use only |

A limiter is per (vendor, endpoint-class) with a token bucket. Concurrency is bounded by the
limiter, never by the size of the work queue.

### Backpressure

The fetch queue is bounded. When full, producers block rather than accumulate — an unbounded queue
converts a slow vendor into memory exhaustion, an hour later, with no obvious cause.

### Retries

- Exponential backoff **with jitter** — un-jittered retries from a batch re-synchronise and hammer
  the vendor in waves.
- A bounded retry count, then a coded failure. Retrying forever is how a run silently never finishes.
- Retries are safe because fetches are **idempotent reads**. Nothing in the fetch tier mutates
  vendor state.

### Circuit breaker

Consecutive failures against one vendor open the breaker: stop calling it, serve the last valid
snapshot, and raise the condition. This is the fail-closed table's row 1 in code —
*"использовать второй источник и последний валидный snapshot"*.

### Cancellation

`Ctrl-C` and shutdown cancel in-flight fetches and **leave the store consistent**. Because writes are
append-only with a `knowledge_time`, a partial fetch is a partial set of new facts — never a
corrupted series. A run that was cancelled is marked incomplete in its manifest and is not usable as
a decision input.

## 3. Compute tier

Parallel over **independent units**: one instrument, one walk-forward window, one backtest arm.

Two hard rules, both from `DETERMINISM_SPEC.md` §3.3:

1. **Aggregation is single-threaded and canonically ordered.** Floating-point addition is not
   associative, so a result combined in completion order is not reproducible.
2. **Worker count never changes results.** `--workers 4` and `--workers 16` must produce identical
   output. If they do not, aggregation is order-dependent and it is a bug, not a tuning artifact.

That second rule is the practical test, and it is cheap: run the same backtest at two worker counts
and diff. It belongs in CI (`CI_POLICY.md` gate 9).

Workers must not share mutable state. Each receives its inputs and returns its outputs; the parent
merges.

## 4. Thread-safety classes

Every module declares one, recorded in the component registry:

| Class | Meaning |
|---|---|
| `immutable` | no mutable state; safe everywhere |
| `thread-safe` | internally synchronised |
| `confined` | single-threaded use only; not shared across tiers |
| `not-safe` | explicitly single-owner |

Domain packages are `immutable` by construction — they are pure functions
(`ARCHITECTURE.md` §3). If a domain module needs another class, the purity boundary has been broken.

## 5. Forbidden

- Shared mutable global state.
- `datetime.now()` in domain packages (`DETERMINISM_SPEC.md` §3.1).
- Unordered iteration feeding output.
- Concurrency inside the decision path.
- Unbounded queues.
- Silent retry loops with no ceiling.
- Aggregating floats in completion order.

## 6. Open items

- [ ] Async vs thread pool for fetch. `yfinance` is synchronous, which argues for threads; a future
      direct HTTP client would argue for async. Decide when the fetcher is written, not before.
- [ ] Default worker count. `NFR.md` budgets a 2-hour backtest without pinning it; it should default
      to something safe and be overridable.
- [ ] Whether the breaker is per vendor or per (vendor, instrument). Per vendor is simpler and
      probably right, since the failures observed so far are vendor-wide.
