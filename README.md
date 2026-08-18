# SwingDesk

Decision-support software for swing trading Canadian and US equities and ETFs. It computes the
charts, indicators, market structure, setups, risk figures, journal and statistics defined by the
owner's 116-file swing-trading course, and records every decision with an audit trail.

**It does not place orders.** No broker integration, no automated execution, no advice to third
parties. The human makes every trading decision; this system prepares and records them.

## Status

**The operational loop is closed and gated; the strategy is not known to work.** Those are two
different claims and this project keeps them apart deliberately.

*Closed* means a position can be recorded, evaluated before candidates on every scheduled run,
proposed on, approved by the owner, applied, and settled against what the broker actually did —
end to end, on real bars, first demonstrated 2026-08-17. *Not known to work* means the base
strategy is negative at measured costs across the whole admissible universe and **no parameter in
this system has ever reached `validated`**. See `docs/08-pm/EVIDENCE_SUMMARY.md`, which outlives
any one session.

Everything that keeps those two claims from blurring runs from a single command:

```bash
python tools/check_gates.py
```

The current inventory covers provenance, transcription, generated registries, document and study
consistency, architecture, static analysis, golden vectors, tests, determinism and the parallel
worktree census. See `docs/06-engineering/CI_POLICY.md` for the derived inventory and a record of
what each gate has caught.

## Source of truth

The requirements source is the course at
`C:\Users\User\Desktop\swing-trading setup\Swing_Trading_Course_Fixed\Swing_Trading_Course_Charts_Layout_Fixed_Verified\`
(116 PDFs plus `VERIFICATION_MANIFEST.json`), governed by
`C:\Users\User\Desktop\swing-trading setup\Course_Production_Rules_v3.8.md`.

Measured facts about that source, established by full text extraction — not assumed:

| | |
|---|---|
| Topics | **1379**, each with a stable component ID (`M26-T0393-v5.0`) |
| Claim types | Definition 916 · Operational Course Rule 173 · Untested Hypothesis 124 · Derived Observation 121 · Inference 45 |
| Computable components | **~460** (everything that is not a Definition) |
| Validation status | `Not Applicable` 1209 · `Untested` 170 · **tested: 0** |
| Numeric thresholds supplied by the course | **effectively none** — across 276 audited topic definitions, the count containing a parameter not already in their own title is 0 |
| Arithmetic supplied by the course | Appendix C (11 risk formulas) and Appendix D (11 statistics formulas) only |
| Schema supplied by the course | Appendix G — a 12-entity ER model with column lists |

**The consequence, stated plainly:** the course is a complete *governance and taxonomy*
specification and an empty *parameter* specification. Every threshold in this system is authored,
not inherited. Every parameter therefore carries a provenance and a status, and no component is
ever displayed as more validated than it is.

## Scope

- Markets: Canada + US equities and ETFs
- Timeframes: context `1Y` / `3M` (windows over daily bars) → decision `1D` → confirmation/trigger
  `1H` → execution `30m`. Lower frames refine a setup; they never invent one. Each resolution is
  fetched and stored independently — deriving `1H` from `30m` would cap hourly history at 60
  trading days when ~725 are available (`ADR-0001`).
- Storage: local databases for bars, the directory, positions and the journal. Nothing leaves the
  machine.
- Notification: a **local desktop notice** (`DR-011`, 2026-08-16). Firebase is specified in
  `PRODUCT_SURFACES` §3.4 and **unbuilt**; the record explains why local is stronger on §3.4's own
  terms — "no data leaves the machine" is satisfied by construction rather than by a third party's
  policy.
- Surfaces: **CLI + reports, built.** The owner's approval of open-position actions runs through
  `swingdesk pending` / `respond` on the CLI, not Telegram — `DR-011` established the owner is at
  the machine when the run fires, and a Telegram approval surface would re-open every question that
  record settled. A web admin panel and Telegram remain specified and unbuilt.

## Layout

```
docs/        the document set, by tier (see docs/README.md)
registry/    generated data: course index, component registry, parameter registry
golden/      frozen fixtures: component vectors and replay cases
src/         bounded contexts, one package each
tools/       generators, verification scripts, and the gate runner
tests/
```

## Language

English throughout — documents, code, and UI. The course's controlled vocabulary
(`STAGE`, `LAYER`, `CLAIM TYPE`, `VALIDATION`, `Trade/Watch/Skip/Pause`, the skip and error codes)
is used verbatim and is never translated or paraphrased.

**This governs artifacts, not conversation.** `AGENTS.md` §13 records an owner instruction about the
language an agent replies in, which changes nothing that lands in the repository. If the two ever
appear to disagree, this rule wins for anything committed.
