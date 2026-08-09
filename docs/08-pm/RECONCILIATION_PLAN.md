# RECONCILIATION PLAN — three branches, one master

**Status:** owner-pending · **Tier:** 8 (project management) · **Content:** authored, measured against the tree

Three efforts branched from `9a07fab` (2026-08-05) and none knew about the others. They do not only
conflict with `master`; **they conflict with each other.** Two independent `DR-005` records, two
independent `PR-007` studies, three incompatible `criteria.yml` v1.1.0 amendments, and four
specification documents written twice.

**Approved 2026-08-09. Steps 1–5 are done; 6–8 remain.** All three branches are merged into `master`.

Owner decisions taken 2026-08-09 are recorded in §3 and are the basis of every call below.

---

## 1. The three branches

| Branch | Tip | Commits vs master | Size | State |
|---|---|---|---|---|
| `claude/swingdesk-handoff-continue-f479bd` | 2026-08-09 11:22 | — | 14 files | **merged into `master`** |
| `claude/swingdesk-handoff-continue-1feb49` | 2026-08-08 16:07 | 9 | 38 files, +43,424 | **merged, step 2** |
| `claude/swingdesk-documentation-321418` | 2026-08-09 09:06 | 26 | 63 files, +4,181 | **merged, step 4** |

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
`EXPECTATION_SPEC.md` — `1feb49` only. **`EXECUTION_MODEL.md` was on BOTH, at different paths —
this line was wrong; see §7.**
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
2. ~~**Merge `1feb49`.**~~ **DONE 2026-08-09.** Seven conflicts, all resolved by §3 rather than by
   merge order: `AGENTS.md`, `HANDOFF.md`, `CI_POLICY.md`, `ROADMAP.md`, `SPEC_GAP_ANALYSIS.md`,
   `docs/README.md`, `docs/prereg/README.md`. `check_gates.py` and `verify_docs.py` auto-merged
   correctly — both sides' gates survived, 20 in total. Its four new gates then caught 30 stale
   figures across nine documents, including counts this session had itself introduced. D-R3 was
   applied against the branch: its "Track A time box removed" row was dropped, because the owner
   chose `321418`'s version that sets one.
3. ~~**Reconcile the duplicated specs** (D-R2).~~ **DONE 2026-08-09.** Both went to `321418`'s
   version, and both kept something from `1feb49`'s. Reasoning in §6.
4. ~~**Merge `321418`.**~~ **DONE 2026-08-09.** 19 conflicts. Its code was reviewed rather than
   waved through: `RunMode`, the required `mode` argument, `from_state` read as of the run start,
   and the engine's `unevaluable_bars` counter kept out of `Skipped` so an unanswerable bar is not
   reported as a rejected signal. **Three collisions §2 did not predict** — see §7.
5. ~~**Amend `criteria.yml` once, to v1.1.0**.~~ **DONE** — it arrived with step 4 by taking
   `321418`'s file per D-R3. `k.track_a_timebox` is ratified at *120 calendar days from the first
   scheduled daily run, or 180 from ratification if none is scheduled*, and `k.timebox_review` is
   `met`. One amendment, not three.
6. **Re-assign gate numbers** across the union, and reconcile `check_gates.py` into one registry.
7. **Recompute every R at 25bp** (D-R5), and re-check `PR-005`'s reported figures. Its two points
   put break-even at 1.369× the assumed cost; at 5× the assumption the base strategy is negative,
   so the headline changes and every document quoting +0.028R must change with it.
8. **Rebuild `HANDOFF.md` §2** from the merged tree, and re-run the branch census.

## 6. Step 3: which version of each duplicated spec won, and why

D-R2 requires the reasoning, not just the outcome. Both documents went to `321418`, but neither
wholesale — each carried one thing the winning version did not have.

### `RULE_SPEC.md` → `321418`, plus §0 from `1feb49`

`321418`'s is the better document on three counts that are not stylistic:

1. **It draws the Rule / Component boundary first** (§1) and grounds it in the course's own layer
   split — measuring structure is `Derived Observations`, selecting on it is `Decision Logic`. It
   then measures the population: of 465 component rows, **173 carry claim type
   `Operational Course Rule`**. `1feb49`'s version does not draw the boundary at all.
2. **It refuses `registry/rules.yml` explicitly** (§1.1), citing ТЗ §8 and this repository's own
   2026-08-04 incident, and drops the seed's third id scheme with a reason. That is a design decision
   the other version leaves open.
3. **Its audit is per-rule and checked** (§7): eight decision points, each with its class, its
   three-valued status, the named test that is its discriminating pair, and its gap — with "checked
   test by test, not assumed" stated, and one row corrected mid-writing.

**What `1feb49` had that `321418` did not:** a compact table naming the three failure modes the form
exists to forbid — the constant gate, the silent `missing → value`, the decorative output. `321418`
covers all three but scattered across §4, §6 and §9. The table is ported as **§0**, because it is the
paragraph that tells a reader why the other four hundred lines exist.

### `SYSTEM_MODES.md` → `321418`, plus §6a from `1feb49`

`321418` discriminates the six modes by **what their output authorises**, which is the sharper axis:
`REPLAY` authorises nothing, `BACKTEST` authorises nothing on its own, `LIVE` authorises an owner
decision *and nothing else*. `1feb49` discriminates by network and determinism, which are
consequences rather than the distinction. `321418` also records what actually runs, with entry
points, and its mode rules are enforced — `pipeline.run` takes `mode` as a required keyword-only
argument since 2026-08-08.

**The two documents genuinely disagreed**, and this is the one case in step 3 where they did.
`1feb49` §4 argues mode is **not** a runtime flag and that separation is structural, enforced by the
import contracts; `321418` makes mode a declared argument. Read carelessly, one contradicts the
other.

They do not, and the resolution is now §6a: the mechanisms operate at **different scopes**. Across
the research / backtest / live boundary separation is structural, because those are different
packages and a crossing is a build failure. *Within* the live path, `LIVE` / `PAPER` / `SHADOW` share
one code path and differ only in what the output authorises — so there the mode is a declared field,
required at the call site. Both statements are true and neither survives alone.

### `EXECUTION_MODEL.md` — no contest

`1feb49` only; `321418` does not have it. Already on `master`, unchanged.

### What the imported files still got wrong

`321418`'s `SYSTEM_MODES` understated the reported-study count by one and listed one runner too few.
Caught by `verify_study_summary` — **their own gate, applied to their own document, inside the step
that imported it.**

Worth noting how it was fixed here: the sentence above deliberately does not quote the wrong figure,
because the gate reads a quoted count as a claim and cannot tell the difference. Rewording is the
right answer rather than an allowlist entry — `321418`'s own commit records that they stripped
false-positive patterns rather than exempting them, on the grounds that a noisy gate gets bypassed.

## 7. Three collisions §2 did not predict

**§2 was measured and still incomplete.** All three surfaced during step 4, and all three were found
by a gate rather than by reading.

1. **`PR-006` was claimed twice.** `DR-004` reserved it for live slippage on 2026-08-02, before any
   file existed; `321418` later wrote a drawdown study under it. D-R4 applies — earliest commit
   keeps the id — so the drawdown study became **`PR-009`**. `docs/prereg/README.md` had predicted
   exactly this and asked someone to fix it "if a third one appears". A third appeared.

2. **`EXECUTION_MODEL.md` existed twice, at different paths.** `1feb49` put it in `02-domain`,
   `321418` in `05-validation`. Git saw no conflict because the paths differ, and §2.3 recorded it as
   "`1feb49` only" because it was checked at one path on both branches. **A same-name check is not a
   same-document check.** Resolved to `321418`'s (it carries the exclusions audit and the finding
   that the live path has a different execution model), with `1feb49`'s profit-slot section ported as
   §8a. Caught by `verify_project_manifest`.

3. **`validation.max_allowable_drawdown` was set twice, differently.** The owner set it directly to
   20% of equity on 2026-08-05; `DR-007` §3.7 authored −15R on 2026-08-08 without seeing that. No
   §3 rule covers it, so the registry's own provenance ladder does: **`owner` outranks
   `assumed:DR-007`**, the owner's value stands, and `DR-007` §3.7 is superseded — which `DR-007`
   itself half-anticipated by calling that value the weakest of its fifteen. **This one is worth
   overturning if the owner disagrees**, because it is the only step-4 call that changes a live
   threshold rather than a label.

Also merged: the README carried duplicate rows for both duplicated specs, `321418`'s and `1feb49`'s,
because only one of each pair was in a git conflict. The superseded pair was removed.

## 5. What this plan does not decide

- **`UDR-004`, the regime ontology.** Now three candidates: the ТЗ's eight, the course v5.0's
  eleven, and v7.0's seven. Untouched here.
- **Course v7.0 adoption.** Deferred by owner ruling; `COURSE_V7_DELTA.md` §4 holds the order.
- **Which of `321418`'s 26 commits are sound.** Step 4 is a review, and this plan does not
  pre-approve its content.
- **Whether `EDGE` replaces both estimators.** That is a new pre-registration, after the merge.
- **`EXPECTATION_SPEC.md` against `EXPECTATION_MODEL.md`.** Both landed, from different branches,
  both claiming ТЗ §23 — one at tier 2, one at tier 5. Not a filename collision, so no gate objects,
  and not covered by D-R2 either. **Left for a step 3b** rather than resolved in passing.

## 6. The risk this plan is carrying

Steps 2 and 4 put roughly 35 commits of two other efforts' reasoning behind decisions made in one
session. The mitigation is that nothing is decided by merge order: every contested item in §2 has an
explicit rule in §3, chosen before any conflict was opened. Where a conflict is not covered by §3, it
stops and comes back here rather than being resolved in the moment — which is the failure this whole
document exists to answer.
