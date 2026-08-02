# OBSERVABILITY SPEC

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

---

## 1. What this system needs to observe

Not uptime — there is none to observe (`NFR.md` §5). The questions that matter here are different:

| Question | Answered by |
|---|---|
| Did the run complete, and is its output trustworthy? | run manifest + `output_hash` |
| Why was this instrument skipped? | coded refusal with its failing input |
| Where did this number come from? | trace with component ids and versions |
| Is the data getting worse over time? | revision volume, refusal rates, conflict counts |
| Am I actually following the process? | `Process compliance` (`STATISTICS_SPEC.md`) |

The last two are the ones a conventional monitoring setup would miss, and they are the ones that
predict trouble.

## 2. Structured logs, one schema

Every log line is structured, with a fixed core:

| Field | Always present |
|---|---|
| `run_id` | yes — ties every line to its manifest |
| `level` | yes |
| `context` | the bounded context emitting it |
| `component` + `version` | when a component is involved |
| `instrument` | when instrument-scoped |
| `event` | a stable, greppable identifier — not a prose message |
| `code` | for any refusal: the skip or error code |
| `as_of` | the `knowledge_time` in play |

`event` being a **stable identifier** is what makes logs queryable a year later. Prose messages
change; identifiers do not.

## 3. Every refusal is a log line

`criteria.yml` `a.no_uncoded_failures` requires zero uncoded failures, which is only checkable if
every refusal is emitted with:

- its code (`CODES.md`)
- the input that failed
- the check that rejected it
- the `as_of` of the data involved

A refusal logged without a code is itself a defect, and the audit that verifies `a.no_uncoded_failures`
is a query over these lines.

## 4. Run manifest

Specified in `DETERMINISM_SPEC.md` §5 — ten fields, written before any work. It is not a log; it is
the run's identity, and every other record references it.

## 5. The daily health report

Produced by every run, and read before its results are trusted:

| Section | Contents |
|---|---|
| **completion** | did every stage finish, and how long each took against its `NFR.md` budget |
| **data** | instruments fetched, revisions written, sessions rejected, conflicts found |
| **funnel** | universe size → screened → candidates → decisions by type, with skip codes ranked |
| **refusals** | every code raised, with counts |
| **parameters** | how many `assumed` values influenced this run |
| **staleness** | instruments behind, and by how many sessions |

The funnel is the one Appendix H explicitly requires reviewing weekly
(`Watchlist funnel и Skip quality проверены`), so producing it daily costs nothing extra and makes
the weekly review a read rather than a computation.

## 6. Trends worth watching

Single-run numbers say little; the derivatives say a lot:

| Signal | What a change means |
|---|---|
| revision volume spiking | vendor re-adjusted history — visible only because storage is delta-based |
| `DATA` refusal rate rising | data quality degrading, or a vendor changing behaviour |
| conflict rate rising | the two sources diverging — one of them changed |
| one instrument repeatedly refused | a candidate for universe eviction |
| `assumed` parameter count not falling | the validation programme is not progressing |

That last one is a project-health metric rather than a system metric, and it is the honest measure
of whether this is going anywhere.

## 7. What not to build

- **No metrics server, no dashboards, no alerting stack.** One user, one daily run, one machine.
  A time-series database here would be infrastructure with no reader.
- **No log shipping.** Logs stay local, like everything else (`PRODUCT_SURFACES.md` §3.4).
- **No sampling.** Volume is low enough to keep everything, and the interesting events are rare by
  definition.

## 8. Secrets

Vendor keys and tokens are masked at the log handler, not at each call site — a masking rule that
depends on every caller remembering it will fail. See `SECURITY.md`.

## 9. Open items

- [ ] Log format: JSON lines is queryable and unreadable; plain text is the reverse. Likely JSON to
      file plus a human-readable console renderer.
- [ ] Retention. Logs are not the audit trail — the journal is — so they can be pruned, unlike the
      records in `AUDIT_AND_IMMUTABILITY.md` §7.
- [ ] Whether the health report is part of the main report or a separate artifact. Separate keeps
      the trading output clean; combined means it actually gets read.
