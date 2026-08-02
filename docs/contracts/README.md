# CONTRACTS

**Status:** drafting · **Tier:** 3 (data) · **Implementation:** `src/swingdesk/contracts/`
**Language:** Pydantic v2 (`ADR-0003`)

The records that cross a bounded-context boundary. One canonical definition each; no context
redefines a shared record.

---

## 1. The boundaries that need contracts

From `ARCHITECTURE.md` §2, reading down the layer chain:

```
reference_data ─ Instrument, ExchangeSession, UniverseMembership ──┐
market_data ──── Bar ──────────────────────────────────────────────┤
                                                                   ▼
                                                    derived_observations
                                                                   │ Observation
                                                                   ▼
                                                          decision_logic
                                                                   │ Candidate, Decision
                                                                   ▼
                                                        trade_management
                                                                   │ RiskSnapshot, ExitProposal
                                                                   ▼
                                              journal_evidence · presentation
platform ─────── RunManifest ──────────────────────────────────── (all)
```

## 2. The records

| Record | Produced by | Consumed by | Carries |
|---|---|---|---|
| `Instrument` | `reference_data` | all | id, ticker, exchange, **currency**, sector, industry |
| `ExchangeSession` | `reference_data` | `market_data`, `derived_observations` | exchange, date, open, close, `is_early_close`, `expected_bars(interval)` |
| `UniverseMembership` | `reference_data` | `decision_logic` | instrument id, date, eligible, failing rule |
| `Bar` | `market_data` | `derived_observations` | instrument, interval, `event_time`, OHLCV, `series` (raw/adjusted), `knowledge_time` |
| `Observation` | `derived_observations` | `decision_logic` | component id + version, instrument, `event_time`, value, units, parameters used |
| `Candidate` | `decision_logic` | `trade_management` | instrument, strategy card id + version, condition results, rank |
| `Decision` | `decision_logic` | `journal_evidence`, `presentation` | candidate, one of `Trade`/`Watch`/`Skip`/`Pause`, reason code, trace |
| `RiskSnapshot` | `trade_management` | `journal_evidence` | equity, risk %, risk $, entry, stop, costs, shares, open risk, buckets, **FX rate used** |
| `ExitProposal` | `trade_management` | `presentation` | position, slot, rule, proposed action, quantity, execution order |
| `RunManifest` | `platform` | all | the 10 fields in `DETERMINISM_SPEC.md` §5 |

## 3. Rules every record follows

1. **Immutable.** `frozen=True`. Records are values.
2. **Money is exact** — `Decimal` or integer minor units. Never `float`.
3. **Fact-bearing records carry `knowledge_time`.** `Bar`, `Observation`, `UniverseMembership`,
   any vendor-sourced fact.
4. **Instrument identity is the internal id, never the ticker string.** Tickers get reused
   (`DATA_QUALITY_SPEC.md` §3).
5. **Currency is mandatory** on anything priced. USA and Canada are never merged (`BR-9`).
6. **Component id + version travels with every derived value.** That is what makes
   `USER_STORIES.md` US-018 — every number traces — possible at all.
7. **Versioned.** Additive within a major; breaking bumps it, with a decision record when meaning
   changes.

## 4. The one performance exception

`Bar` is the high-volume record — ~20M rows (`NFR.md` §1). Validating each row individually would
cost more than it protects.

**Inside `market_data`, bars are columnar.** The `Bar` contract governs the **boundary crossing**:
a request for a series returns a validated container (instrument, interval, series, window,
`knowledge_time`, and the column block), not 20M validated objects.

This is the only place a contract describes a collection rather than a record, and it is deliberate.

## 5. Open items

- [ ] Whether `Observation` is one record per (component, instrument, bar) or a series per
      (component, instrument). Series is far cheaper; per-bar is easier to trace. Likely series with
      the component/version on the container, mirroring §4.
- [ ] Whether `Decision` embeds the full trace or references it by id. Embedding makes a decision
      self-contained for audit; referencing keeps the record small.
- [ ] JSON Schema export target — needed once the web panel exists, not before.
