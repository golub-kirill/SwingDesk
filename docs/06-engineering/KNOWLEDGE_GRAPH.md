# KNOWLEDGE GRAPH

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored, measured against the tree

Master ТЗ v1.0 §46, the last absent section. The gap analysis called it *"a projection of registries
that already exist"* and ranked it last, and writing it confirms the ranking: **the edges are already
here and most of them are already enforced.** What is missing is a view.

This document specifies the projection, not a new store. Building one would put the dependency
structure in two places, which is the thing §8 of the specification forbids and this repository has
already paid for once.

---

## 1. The nodes already exist

Every node type is an existing record with a stable id. Nothing has to be invented for the graph to
exist:

| Node | Id | Source | Count |
|---|---|---|---|
| Component | `M##-T####-v#.#` | `registry/components.yml` | 465 |
| Parameter | `group.name` | `registry/parameters.yml` | 96 |
| Course topic | `M##-T####` | `registry/course_index.yml` | 1379 |
| Criterion | `a.* · b.* · k.*` | `registry/criteria.yml` | 19 |
| Checklist item | `E##` and siblings | `registry/checklists.yml` | 84 |
| Document | filename | `docs/` | 87 |
| Decision record | `DR-NNN` | `docs/decisions/` | 6 |
| Study | `PR-NNN` | `docs/prereg/` | `python tools/verify_study_summary.py` |
| Golden vector | path | `golden/` | 25 |
| Test | `file::name` | `tests/` | 253 |

## 2. The edges already exist, and nine are gate-enforced

This is the finding. A knowledge graph usually has to be built because the relationships are implicit;
here they are explicit, typed, and most of them fail the build when they dangle.

| Edge | From → to | Enforced by |
|---|---|---|
| `implements` | component → code symbol | gate 11, and it is **injective** |
| `parameters` | component → parameter | gate 11 |
| `consumers` | component → component | gate 11 |
| `spec` | component → document anchor | gate 11 for `active` |
| provenance | parameter → decision record | gate 1 |
| provenance | parameter → study | gate 1, gate 3f (verdict must be ACCEPT) |
| cites | document → document, parameter, component | gate 3e |
| trigger references | criterion → parameter, criterion | gate 3g |
| generated-from | document → registry | gates 3b, 3c, 3d, 3ci |
| verifies | golden vector → component | gate 7b |
| covers | test → component | **not enforced** — this is CI gate 10, still unwired |

**Ten of eleven edge types are already checked.** The eleventh is traceability, and `CI_POLICY.md` §7
records why it is unwired: its strongest check is *every `active` component has a test*, and there
are zero `active` components, so it would pass vacuously.

## 3. What the projection is for

Two questions nothing can answer today, both of which the edges above already contain:

**"What breaks if I change this?"** — the transitive closure of `consumers` and `parameters` from a
component, plus the studies whose evidence pinned its version. `COMPONENT_REGISTRY_SPEC.md` §1 calls
the consumer list *"a visible list"* and says without it you cannot answer this question. The list
exists per row; the closure does not.

**"What supports this number?"** — from a displayed value back through `ParameterUse` to the
parameter, its provenance, the decision record or study behind it, and that study's disclosures.
`REQ-OUTPUT-001` requires every displayed number to carry its source; the graph is what makes the
*chain* legible rather than the immediate link.

A third, cheaper than both: **"what is orphaned?"** — a parameter no component reads, a document
nothing cites, a golden vector for a component that no longer exists. Each is a small rot detector
and all three are one query over the same edges.

## 4. The projection, specified

1. **Derived, never authored.** The graph is regenerated from the registries like the FRD and the
   coverage matrix. A hand-maintained node is a second source of truth.
2. **No new ids.** Every node keeps the id its registry already gives it. A graph that mints its own
   identifiers becomes a thing to reconcile.
3. **Edges are typed and directional**, and the type is the field name that produced it —
   `implements`, `consumers`, `provenance`. An untyped edge cannot answer either question in §3.
4. **A dangling edge is a build failure, not a null node.** Every edge type in §2 except `covers`
   already fails a gate when it does not resolve; the projection inherits that rather than tolerating
   holes.
5. **Output is a file, not a service.** The same shape as `COVERAGE_MATRIX.md`: generated, committed,
   gated on being current. A graph nobody can read in a diff is a graph nobody checks.

## 5. Why it is last, and honestly so

Every question in §3 is answerable today by reading two YAML files, and the tree is small enough that
this is not painful: 465 components of which 7 are implemented, and 96 parameters of which 33 have
values. The graph pays for itself when the numbers grow, and both grow only in phase 3.

Recorded plainly so it is not mistaken for neglect: **§46 is specified and deliberately not built.**
The specification exists so that when it is built it is a projection rather than a second registry,
which is the only decision about it that is expensive to reverse.

## 6. Open items

- [ ] **Format.** Mermaid renders in a diff and does not scale past a few hundred nodes; a JSON
      adjacency file scales and reads badly. Probably both — JSON as the artefact, Mermaid for a
      named subgraph on demand.
- [ ] **Gate 10 lands here.** Traceability is the missing eleventh edge, and building the projection
      is most of the work of wiring it. They should be done together, when the first component is
      `active`.
- [ ] **Whether the course index belongs in the graph.** 1379 topics against 465 components is most
      of the node count for one edge type. Likely a separate subgraph, loaded on demand.
