# ARCHITECTURE

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored, constrained by tier 2

This document does **not** invent a model. `docs/02-domain/LIFECYCLE_AND_LAYERS.md` is the
architecture; this maps it onto packages and states what each owns.

---

## 1. Contexts

Nine packages under `src/swingdesk/`. The four middle ones are the course's four layers, one to one.

| Package | Course layer | Owns |
|---|---|---|
| `platform` | — | config, clock injection, logging, storage, scheduling, run manifests |
| `market_data` | Source Facts | vendor adapters, bitemporal bar storage, freshness and conflict checks |
| `reference_data` | Source Facts | symbology, exchange calendars, corporate actions, sector/industry, event calendars |
| `derived_observations` | **Derived Observations** | indicators, structure, levels, patterns, regime, relative strength — **pure functions** |
| `decision_logic` | **Decision Logic** | gates, conditions, screeners, strategy evaluation, candidate decisions |
| `trade_management` | **Trade Management** | sizing, stop, target, partial, trailing, time-exit, portfolio constraints |
| `journal_evidence` | — | append-only journal, audit trail, evidence records, checklists |
| `validation` | — | backtest, walk-forward, robustness, forward-test harnesses |
| `presentation` | — | CLI, reports, web API, Telegram, push |

`platform` and `journal_evidence` have no course layer because they are infrastructure: the course
describes *what must be recorded and reproduced*, not where the code lives.

## 2. Dependency direction

```
presentation
    ↓
validation
    ↓
trade_management
    ↓
decision_logic
    ↓
derived_observations
    ↓
reference_data
    ↓
market_data
    ↓
platform
```

`journal_evidence` sits **outside** this chain. It is a persistence service: `trade_management`,
`validation` and `presentation` write to it; `derived_observations` and `decision_logic` must not
touch it, because they are pure. Expressing that needs `forbidden` contracts, not layers — see
`DEPENDENCY_LAW.md`.

## 3. Purity boundary

This is the one architectural rule that everything else leans on.

**`derived_observations` and `decision_logic` are pure.** No I/O, no network, no database, no
journal, no wall clock. They take data in and return values. Everything they need is passed to them.

Three separate course requirements force this, and none of them is a software-taste argument:

| Requirement | Source |
|---|---|
| "Deterministic calculations or classifications derived from source facts" | §3.6 layer 2 |
| "strategies do not fetch or normalize their own private version of shared facts" | §3.8 |
| a re-run must reproduce a control run — `повторный run совпал с контрольным` | fail-closed row 3 |

The third is the sharpest: the course states determinism as an **operating procedure** for returning
from a screener failure. A decision path that reads the clock or the network cannot satisfy it.

Consequence: time is injected. `datetime.now()` never appears in a domain package, and CI enforces
that (`CI_POLICY.md`).

## 4. Where the mandatory trace is materialised

The course requires (`LIFECYCLE_AND_LAYERS.md` §3):

```
Source Facts → Derived Observations → Evaluated Conditions → Strategy Decision
             → Management Policy → Outcome → Review
```

Each arrow crosses a package boundary, and each crossing is a **recorded** step, not just a call:

| Trace step | Produced by | Recorded in |
|---|---|---|
| Source Facts | `market_data`, `reference_data` | bar/fact rows with as-of and knowledge time |
| Derived Observations | `derived_observations` | observation values with component id + version |
| Evaluated Conditions | `decision_logic` | per-condition result, including which failed |
| Strategy Decision | `decision_logic` | `Trade/Watch/Skip/Pause` + reason code |
| Management Policy | `trade_management` | action, rule, timestamp |
| Outcome | `journal_evidence` | fills, exit, R |
| Review | `journal_evidence` | MFE, MAE, process score, errors |

*"A conclusion that cannot be reproduced from its recorded inputs and versions is a production
defect."* — so the trace is the primary output of a run, and the report is a view over it. Not the
other way round.

## 5. Run shape

One daily run, following the course's own nine-step pipeline (`SCREENER_SPEC.md` §3), with open
positions processed first (`CHECKLIST_SPEC.md` §4, `Открытые позиции и gaps проверены первыми`):

```
platform: open run, write manifest (code hash, config hash, data snapshot, spec versions)
  market_data + reference_data: refresh, freshness/conflict gates
  journal_evidence: load open positions
  trade_management: evaluate exits on open positions        <- before any new candidate
  decision_logic: regime -> sector/RS -> context -> setup -> trigger
  trade_management: stop -> size -> portfolio overlap
  decision_logic: assign Trade/Watch/Skip + reason
  journal_evidence: persist trace, candidates, decisions
  presentation: report, alerts, approval prompts
```

A failure at any gate degrades per `FAIL_CLOSED_POLICY.md` rather than aborting silently: data
failures fail open into a cached snapshot, **decisions** fail closed.

## 6. Concurrency, briefly

Detail lives in `CONCURRENCY_MODEL.md`. The architectural constraint:

- `market_data` fetching is concurrent (async or thread pool), rate-limited per vendor.
- `validation` backtests are process-parallel.
- **The decision path is single-threaded and deterministic.** Parallelism is permitted only where
  results are order-independent, and every merge point re-imposes a canonical sort.

## 7. Open items

- [ ] Whether `reference_data` and `market_data` should be one context. They are separate because
      their revision behaviour differs — bars get back-adjusted, calendars do not — but that may not
      justify a boundary. Revisit after the walking skeleton.
- [ ] Where the Telegram approval loop lives. It spans `presentation` (the prompt) and
      `trade_management` (the proposed action) and `journal_evidence` (the record). Likely an
      application service in `presentation`; confirm when `PRODUCT_SURFACES.md` is written.
- [ ] Storage engine choice (owner decision: local DB, Firebase for push only). Parquet + DuckDB is
      the leading candidate for bars; the journal wants transactional integrity, which points
      elsewhere. Needs its own ADR.
