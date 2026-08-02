# ADR-0003 — Contract schema language

- **Status:** Proposed
- **Date:** 2026-08-02

## Context

Records crossing a bounded-context boundary need one canonical definition, and §3.8 requires that
components "reference components rather than copying their formulas or silently reimplementing
them". The same argument applies to data shapes: a `Bar` defined once in `market_data` and again in
`derived_observations` will diverge.

`docs/README.md` #25 requires that **code is generated from the schemas**, not written twice.

Constraints that narrow the field:
- single language (Python), single user, single machine
- no network services between contexts — these are in-process boundaries
- a web API arrives later (`PRODUCT_SURFACES.md` §3.2)
- `NFR.md` budgets the decision path at ≤5 min for ~1,500 instruments, so per-record validation
  overhead matters at the margin

## Decision

Use **Pydantic v2 models** as the contract definition, in `src/swingdesk/contracts/`.

The model class **is** the schema. JSON Schema is exported from it for documentation and for any
future non-Python consumer, rather than being the source.

## Alternatives considered

- **JSON Schema as source, with codegen.** Language-neutral and the "purest" reading of
  "generate code from schemas". Rejected: the neutrality buys nothing in a single-language project,
  and it adds a build step between editing a contract and using it — friction that gets skipped
  under time pressure, which is exactly when contracts matter.
- **Protobuf / Avro.** Built for cross-process, cross-language, schema-registry environments. These
  boundaries are in-process function calls. Rejected as overhead without a matching problem.
- **Dataclasses.** No validation, no serialisation, no constraint expression. Would leave the
  contract as a naming convention.
- **Nothing — pass DataFrames across boundaries.** The path of least resistance and the reason
  boundaries erode: a DataFrame has no declared shape, so every consumer invents its own assumptions
  about columns and dtypes. Rejected explicitly, because it is what will happen by default if this
  ADR does not exist.

## Consequences

- Positive: validation, serialisation, JSON Schema export and static types from one definition; no
  codegen step; FastAPI integration is free when the web panel arrives.
- Negative: Python-only. Acceptable, and revisitable — JSON Schema export means a future consumer is
  not locked out.
- **Watch:** validation cost on hot paths. Bars are the high-volume record (~20M rows). Bars are
  therefore carried in **columnar form** inside `market_data`, and the `Bar` contract governs the
  boundary crossing, not every row in a series. Validating 20M rows individually would be pointless
  and slow.

## Rules

1. One canonical definition per record, in `contracts/`. No context redefines a shared record.
2. Contracts are **versioned**; additive changes within a major, breaking changes bump it.
3. A contract change requires a decision record when it alters meaning rather than adding a field.
4. Contracts are frozen (`model_config = ConfigDict(frozen=True)`) — records are values, and
   immutability at the boundary supports the append-only rules elsewhere.
5. Money fields are `Decimal` or integer minor units, never `float` (`DETERMINISM_SPEC.md` §3.3).
6. Every fact-bearing record carries `knowledge_time` (`POINT_IN_TIME_SPEC.md` §2).

## Revisit when

- A non-Python consumer appears.
- Boundary validation shows up in a profile of the decision path.
