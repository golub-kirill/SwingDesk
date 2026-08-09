# CHANGE MANAGEMENT

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored, measured against the tree

Master ТЗ v1.0 §43. The shortfall recorded in `SPEC_GAP_ANALYSIS.md` was precise:
`COMPONENT_REGISTRY_SPEC.md` §6 covers *component* versioning and there is **no change-type taxonomy
and no rollback policy**. This is both.

**The finding, before the taxonomy:** in this project **rollback is mostly not a revert.** The
stores are append-only by design — the journal, the position store, evidence records, decision
records, ratified criteria — so undoing something means *superseding* it with a new version that
names the old one. A change management policy written around "revert to the previous state" would
contradict the storage model on its first line.

---

## 1. The change types

Eight kinds, each with what it obliges and what undoing it means. The distinction that matters is
the last column: **reversible** changes can be undone by returning to the previous state;
**supersedable** ones can only be corrected forward.

| # | Change | Obliges | Undo |
|---|---|---|---|
| 1 | **Parameter value** | provenance and a citation (gate 1); a `validated` value needs an evidence id | supersede — a new decision record naming the old (`decisions/README.md` §3 rule 2) |
| 2 | **Component behaviour** | version bump **and** its golden vectors regenerated in the same commit; validation status **resets** | supersede — earlier evidence stays pinned to the earlier version |
| 3 | **Ratified criterion** | an **amendment**, never an edit; a new `criteria.yml` version with the previous one intact | supersede — v1.0.0 stays on record; see v1.1.0 |
| 4 | **Registry regeneration** | the generator is the only writer; `--check-only` gates catch a hand-edit | reversible — regenerate from source |
| 5 | **Documentation** | references must resolve (gate 3e); counts must match the tree (gates 3f, 3ci) | reversible |
| 6 | **Schema / store migration** | additive only; existing rows must survive (`journal.py`'s `ALTER TABLE ... IF NOT EXISTS`) | **not reversible** — see §3 |
| 7 | **Gate added or changed** | fixed or removed, never skipped (`CI_POLICY.md` §3); mutation-tested before it is trusted | reversible |
| 8 | **Study reported** | pre-registered first; the report is the record | **never undone** — an abandoned study stays in the repository (`prereg/README.md`) |

## 2. What each change must carry

Not a form to fill in — the obligations already exist and are enforced. Collected here because
nowhere else lists them together:

| Change | Enforced by |
|---|---|
| parameter value without provenance | gate 1 |
| parameter read as a number that is not a number | gate 1, since 2026-08-08 |
| `assumed:DR-NNN` citing a record that does not exist | gate 1 |
| component behaviour changed without new vectors | gate 7b |
| generated file hand-edited | gates 3b, 3c, 3d, 3ci |
| a document citing something that does not exist | gate 3e |
| a summary count drifting from the evidence | gate 3f |
| a criterion in force whose parameter is unset | gate 3g |
| a decision path that stopped reproducing | gate 9 |

**Nine of the eighteen gates exist to police change rather than correctness.** That is the shape of
this project: the risk is not that a value is wrong today, it is that it stops being what it says it
is.

## 3. Rollback

### What can be rolled back

Code, documents and generated artefacts. `git revert`, then the gates confirm the tree is consistent
again. Nothing more is needed because none of them is a record of something that happened.

### What cannot

**A store migration.** `journal.py` adds columns with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, and
the rows written after it carry data the previous schema has no room for. Reverting the code leaves a
database the old code cannot read correctly, and *deleting the column deletes the record*. This is
why migrations here are **additive only** and why `mode` is nullable in the journal while being
required on the manifest: rows written before the column existed cannot acquire one, and a `NULL`
that means "this predates the field" is honest where a backfill would be a fabrication.

**Anything the journal, position store or evidence set has recorded.** Append-only is a storage
guarantee, not a convention (`AUDIT_AND_IMMUTABILITY.md`) — error `HINDSIGHT`'s required control is
an immutable pre-trade snapshot, so a system that could roll back a decision record would not have
the control it claims.

**A ratified criterion or an accepted decision record.** Both are frozen by rule. `DR-007` is
accepted and may not be edited; correcting a value in it takes `DR-007` naming it superseded.

### The rule

> **Roll back what has no memory. Supersede what does.**

A correction to a recorded fact is a new version linked to the original, and the original stays
readable forever. That is the same discipline `POINT_IN_TIME_SPEC.md` applies to market data, applied
to the project's own history.

## 4. Emergency change

The one case where the order is different. If a gate is **wrong** — failing on correct input, or
passing on a defect — it is fixed or removed in the same session, never skipped
(`CI_POLICY.md` §3). A bypassed gate teaches the operator that red is normal, which costs more than
the gate was worth.

There is deliberately no `--skip` flag, so "emergency" here means *fix it now*, not *route around
it*.

## 5. What this does not cover yet

- **No release versioning.** The project has no releases; the run manifest pins `code_hash` per run,
  which is what reproduction actually needs.
- **No deprecation path.** Nothing has been removed yet. When something is, `Retired` already exists
  as a validation status for a component withdrawn *because the world changed* rather than because it
  failed — `COMPONENT_REGISTRY_SPEC.md` §4 keeps that distinct from `Rejected`.
- **No change record for the parameter registry itself.** A value's history lives in git and in the
  decision records that set it; whether that is enough is §6's first open item.

## 6. Open items

- [ ] **Whether a parameter needs a change history in the registry**, rather than only in git and its
      decision record. The argument for: `EVIDENCE_RECORD_SPEC.md` pins parameter values at the time
      of a study, and reconstructing "what was this on 2026-08-02" currently means reading commits.
- [ ] **A migration record.** §3 says migrations are additive and irreversible; nothing writes down
      *which* migrations have run. DuckDB's `IF NOT EXISTS` makes it idempotent rather than tracked,
      which is fine until two schemas diverge.
- [ ] **`Retired` has never been used.** The first component withdrawn will show whether the
      distinction from `Rejected` survives contact.
