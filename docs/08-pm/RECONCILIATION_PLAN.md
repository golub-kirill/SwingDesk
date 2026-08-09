# RECONCILIATION PLAN — three branches, one master

**Status:** owner-pending · **Tier:** 8 (project management) · **Content:** authored, measured against the tree

Three efforts branched from `9a07fab` (2026-08-05) and none knew about the others. They do not only
conflict with `master`; **they conflict with each other.** Two independent `DR-005` records, two
independent `PR-007` studies, three incompatible `criteria.yml` v1.1.0 amendments, and four
specification documents written twice.

**Nothing is merged yet, deliberately.** `master` has one of the three branches in it and the other
two are untouched. This document is the plan; executing it is a separate, approved step.

Owner decisions taken 2026-08-09 are recorded in §3 and are the basis of every call below.

---

## 1. The three branches

| Branch | Tip | Commits vs master | Size | State |
|---|---|---|---|---|
| `claude/swingdesk-handoff-continue-f479bd` | 2026-08-09 11:22 | — | 14 files | **merged into `master`** |
| `claude/swingdesk-handoff-continue-1feb49` | 2026-08-08 16:07 | 9 | 38 files, +43,424 | open |
| `claude/swingdesk-documentation-321418` | 2026-08-09 09:06 | 26 | 63 files, +4,181 | open, unreviewed |

`1feb49`'s line count is dominated by one committed evidence file
(`docs/decisions/measurements/spread-sample.json`, ~39k lines).

## 2. Every collision

### 2.1 Identifier collisions

| Id | `1feb49` | `321418` | `master` |
|---|---|---|---|
| `DR-005` | `DR-005-measured-slippage.md` (2026-08-05) | was DR-005-validation-thresholds, now `DR-007-validation-thresholds.md` **(resolved, step 1)** | — |
| `PR-007` | `PR-007-base-strategy-measured-costs.md` (2026-08-08) | — | was PR-007-effective-spread, now `PR-008-effective-spread.md` **(resolved, step 1)** |
| `DR-006` | — | `DR-006-portfolio-risk-block.md` | — |

### 2.2 `registry/criteria.yml` — three incompatible v1.1.0

| Branch | Intent |
|---|---|
| `1feb49` | **Removes** the Track A time box. Argument: G5 closed inside its box, so the clock was never binding, and `SUCCESS_AND_KILL_CRITERIA` §5 already reasoned that boxing Track A conflates two questions |
| `321418` | **Sets** it — adds `k.track_a_timebox`, drafted from measured throughput, with an explicit firing clause |
| (proposed on `master`, never written) | 12 weeks from the first green daily run |

### 2.3 Documents written twice, independently

`RULE_SPEC.md` · `SYSTEM_MODES.md` — on both branches.
`EXECUTION_MODEL.md` · `EXPECTATION_SPEC.md` — `1feb49` only.
`ALLOCATION_SPEC.md` · `TRANSITION_SPEC.md` · `EXPECTATION_MODEL.md` · `DRIFT_AND_LEARNING.md` ·
`AI_AUTHORITY_MODEL.md` · `COVERAGE_AUDIT.md` — one branch each.

### 2.4 Tools changed on both

`tools/check_gates.py` · `tools/verify_criteria.py` · `tools/verify_docs.py`

Plus, unique to one side each: `verify_counts` · `verify_project_manifest` · `verify_study_summary` ·
`measure_spread` (`1feb49`); `verify_studies` · `build_coverage` (`321418`).

Both branches added gates numbered 12–15 **and `master` has since added a gate 16**. Gate numbering
must be re-assigned once, at the end, rather than per-merge.

### 2.5 Documents modified on both

`SUCCESS_AND_KILL_CRITERIA.md` · `REQUIREMENTS.md` · `PARAMETER_REGISTRY.md` · `CI_POLICY.md` ·
`RISK_REGISTER.md` · `ROADMAP.md` · `SPEC_GAP_ANALYSIS.md` · `docs/README.md` ·
`decisions/README.md` · `prereg/README.md` · `registry/parameters.yml`

## 3. Decisions taken — owner, 2026-08-09

| # | Decision |
|---|---|
| D-R1 | **Plan first, merge nothing.** This document, approved, then execution |
| D-R2 | **Duplicated specs are compared per document**, better version wins, reasoning recorded. Nothing discarded unseen |
| D-R3 | **The Track A time box is SET**, per `321418`'s `k.track_a_timebox` with its firing clause. `1feb49`'s removal and the 12-week proposal are both dropped |
| D-R4 | **Earliest commit timestamp keeps a contested id.** Objective and checkable from git |
| D-R5 | **`costs.slippage_model` becomes 25bp per side, status `assumed`**, with the cross-sectional pathology recorded as the reason it may not advance further. Every R is recomputed at the new level |

### What D-R4 resolves to

| Id | Keeps it | Renumbered to |
|---|---|---|
| `DR-005` | `1feb49` measured-slippage (08-05) | `321418` validation-thresholds → **`DR-007`** |
| `PR-007` | `1feb49` base-strategy-measured-costs (08-08) | `master` effective-spread → **`PR-008`** |

`master`'s study is the one that moves — the newest work pays the cost of the collision, which is the
right way round. Its prereg, report and JSON of record were renamed together with all 47 citations,
and `docs/prereg/README.md` records that the id changed and when: **a `PR-007` citation written
before 2026-08-09 means the effective-spread study, one written after means the base-strategy one.**
The git history under `PR-007` is left unedited, because the registration commit is what proves the
hypothesis predated the run.

### What D-R5 must carry

The direction is settled by a calibration-free sign test (real bars clamp at 19.1% against 45.5% for
spreadless synthetic at matched volatility; 126 of 126 instruments read above their own floor). The
**level is not**, and the literature says why: the documented bias of both estimators is dependence
on realised volatility, and their cross-sectional correlation with the true spread falls from ~70%
in small caps to ~18% in large caps. Our own measurements reproduce this exactly — +0.46 against
volatility, −0.02 against liquidity, most-liquid third reading wider than least.

So `DR-005` should record 25bp as **the best available estimate, biased upward for liquid names by a
known and published mechanism**, and name `EDGE` (Ardia, Guidotti & Kroencke, *JFE* 2024;
`github.com/eguidotti/bidask`) as the estimator that supersedes both and the obvious next step.
That is `AGENTS.md` §10.3 applied to its own founding example.

## 4. Execution order

Each step ends green on `python tools/check_gates.py`, and no step begins before the previous is
committed.

1. ~~**Renumber on the branches, not during the merge.**~~ **DONE 2026-08-09.** `master`'s
   `PR-007` → **`PR-008`** is complete: four artifacts renamed, 47 references updated across 13
   files, and the renumbering recorded in the prereg, the report and `docs/prereg/README.md` — the
   git history under `PR-007` is deliberately unedited, because it is what proves registration
   preceded the run. **`321418`'s `DR-005` → `DR-007` is done too** (commit `515708c`): 46 references across 16
   files, including fifteen `assumed:DR-005` provenance strings in `registry/parameters.yml`. All 20
   gates on that branch stay green. **Step 1 complete.**
2. **Merge `1feb49`.** Smaller, already reviewed here, and it carries the cost decision. Expect
   conflicts in the eleven §2.5 documents and in `check_gates.py`/`verify_docs.py`.
3. **Reconcile the duplicated specs** (D-R2) — `RULE_SPEC.md` and `SYSTEM_MODES.md` first, since
   both branches touch them.
4. **Merge `321418`.** Larger and unreviewed; its 26 commits need reading, not just resolving.
5. **Amend `criteria.yml` once, to v1.1.0**, carrying `321418`'s `k.track_a_timebox` (D-R3) and
   marking `k.timebox_review` `met`. One amendment, not three.
6. **Re-assign gate numbers** across the union, and reconcile `check_gates.py` into one registry.
7. **Recompute every R at 25bp** (D-R5), and re-check `PR-005`'s reported figures. Its two points
   put break-even at 1.369× the assumed cost; at 5× the assumption the base strategy is negative,
   so the headline changes and every document quoting +0.028R must change with it.
8. **Rebuild `HANDOFF.md` §2** from the merged tree, and re-run the branch census.

## 5. What this plan does not decide

- **`UDR-004`, the regime ontology.** Now three candidates: the ТЗ's eight, the course v5.0's
  eleven, and v7.0's seven. Untouched here.
- **Course v7.0 adoption.** Deferred by owner ruling; `COURSE_V7_DELTA.md` §4 holds the order.
- **Which of `321418`'s 26 commits are sound.** Step 4 is a review, and this plan does not
  pre-approve its content.
- **Whether `EDGE` replaces both estimators.** That is a new pre-registration, after the merge.

## 6. The risk this plan is carrying

Steps 2 and 4 put roughly 35 commits of two other efforts' reasoning behind decisions made in one
session. The mitigation is that nothing is decided by merge order: every contested item in §2 has an
explicit rule in §3, chosen before any conflict was opened. Where a conflict is not covered by §3, it
stops and comes back here rather than being resolved in the moment — which is the failure this whole
document exists to answer.
