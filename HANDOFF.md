# HANDOFF — start here in a fresh session

Written 2026-08-04, after reconciling two parallel documentation efforts. Read this, then
`AGENTS.md`, then `docs/README.md`. Everything below is measured from the tree, not remembered.

---

## 1. What this is

Decision-support software for swing trading Canadian and US equities and ETFs, specified from the
owner's 116-PDF swing-trading course. **It never places orders** — owner decision D1. The human
makes every trading decision; the system prepares, checks and records them.

The project's founding premise: previous attempts failed *upstream of code* — goals, limits and the
algorithm were never frozen first. So documentation is the deliverable and the code exists to prove
the documentation is implementable.

## 2. State, measured

| | |
|---|---|
| Merge gates | **16**, one command, all green |
| Tests | **275**, fully offline |
| Docs | 77 files across 8 tiers |
| Components | 465 registered · 7 `specified` · **0 `active`** |
| Parameters | 96 — 84 `unset`, 9 `assumed`, 2 `owner`, **1 `validated`** |
| Studies | 5 reported — **3 refuted**, 1 inconclusive, 1 accepted and quantifiably fragile |
| Universe | 1,133 members · 3,687 of 13,043 measured · **28.3% coverage** |
| Project gates | G0, G4, G5 closed · G1, G2, G3, G6, G7 open |

```bash
python tools/check_gates.py
```

That must stay green. A gate that is wrong gets **fixed or removed, never skipped**.

### You are not the only effort. Check this before starting work.

This repository's normal mode is **several worktrees at once**, and the table above measures only the
one you are standing in. On 2026-08-09 three efforts branched from `9a07fab`, none knew about the
others, and one re-ran a study another had already finished and reached the opposite conclusion —
`docs/08-pm/POSTMORTEM-2026-08-09.md`, root cause A. Gate 16 now fails if a worktree is missing here.

| Branch | Tip | Merged? | What it holds |
|---|---|---|---|
| `claude/swingdesk-handoff-continue-f479bd` | 2026-08-09 | **yes** | PR-007, the v7.0 delta, `AGENTS.md` §9 |
| `claude/swingdesk-handoff-continue-1feb49` | 2026-08-08 | **no**, 9 commits | `DR-005` slippage at 25bp, `criteria.yml` v1.1.0 **removing** the Track A time box, `RULE_SPEC`/`SYSTEM_MODES`/`EXECUTION_MODEL`, gates 12–15, `validation.max_allowable_drawdown` = 20% |
| `claude/swingdesk-documentation-321418` | 2026-08-09 | **no**, 26 commits | a HANDOFF rewrite, a count audit, a phase plan — unreviewed |

**`master` currently contradicts several items in row 2.** Reconciling them is open work, listed in
the postmortem §5.D. Do not merge either branch without reading it.

## 3. The uncomfortable summary

**The machinery is real and honest. The strategy is not known to work, and what is known is mostly
negative.**

- The base strategy measured **+0.028R per trade at `DR-004`'s assumed costs** and **−0.123R under
  3× cost stress** (PR-005). Both are **net** — gross is never reported (`DR-004` consequence 1), so
  "before costs" is the one description that is wrong. Those two points put the break-even at
  **1.369× assumed costs**. Costs on `master` are still *assumed*. A parallel branch measured them
  at **25bp per side** (`DR-005`), and PR-007's contrary claim — that they cannot be measured from
  free daily data — was **withdrawn on 2026-08-09** after a calibration-free sign test refuted it.
  The direction is settled: 5bp is too low. The level is not. So the sign of the result still sits
  inside an unvalidated number, and now also inside an unreconciled one.
- The one positive finding (PR-002: breadth separates breakout outcomes) is erased by **1.6–2.3% of
  trades missing at −2R**, and Yahoo serves no delisted history, so that exposure can never be
  confirmed on the free tier.
- `CHARTER.md` §4's v1 finish line is a **machinery** target and was reached 2026-08-02. Reaching
  v1 and reporting no validated edge is a **success** against the ratified criteria, not a failure.

Do not write anything that implies more confidence than that. `UX_COPY.md` §3 carries the standing
warning verbatim.

## 4. What just happened

### 2026-08-09 — a rebuilt course appeared, and is deliberately not used

`Swing_Trading_Course_Canada_USA_v7.0_2026-08-08` exists on disk beside the indexed course. Owner
ruling the next day: **v7.0 is still young, work is ongoing** — `v5.0`/`v4.0` stays canonical and
`registry/course_index.yml` is unchanged. Nothing in the tree reads v7.0.

It is not a re-render. Same 1,379 topics with identical ids, but **79% have a different claim type**
and **83% a different validation status**; `Definition` collapses 916 → 70 and `Inference`
disappears. Body text is rewritten, so the 393 `verbatim` quotes would all need re-transcribing, and
v7.0 carries formulas where the indexed course carries none — which makes `AGENTS.md`'s "zero
numeric thresholds" premise a statement about v5.0/v4.0 specifically.

Measured in full in `COURSE_V7_DELTA.md`, including the two findings that will matter most: PR-002's
second amendment quotes a sentence v7.0 does not contain, and v7.0 names a **third** regime list
(seven) against the two `UDR-004` is choosing between. **Do not adopt v7.0 piecemeal** — §4 of that
document is the order the steps have to happen in.

### 2026-08-04 — two parallel documentation efforts, reconciled

Two efforts had been writing into this repo without knowing about each other. A second track built
ten numbered documents at root to master-ТЗ v1.0 §47 — Russian, "documentation only" — having never
opened `docs/`, `src/` or `registry/`. Consequences: its build plan scheduled ~10 specification
sections as future work that was already done, and its README rewrite dropped the "It does not place
orders" line.

Resolved: `docs/` is canonical (owner decision). All of that track's work is preserved verbatim in
commit **`dee8f37`**, its genuinely new material is folded in, and the duplicates are gone.
`docs/08-pm/SPEC_GAP_ANALYSIS.md` is the real §56 analysis: **FULL 28 · PARTIAL 16 · ABSENT 9 ·
DEFERRED 3.**

**Do not rebuild the numbered tree.** Master ТЗ §8 forbids maintaining one logic in two places, and
for a day this repo was doing exactly that.

## 5. What to do next, ranked

Three of these are decisions only the owner can make. They are listed first because they are
overdue, not because they are hard.

### Owner decisions

1. **`k.timebox_review` has fired and is unactioned.** `registry/criteria.yml` is ratified and says:
   trigger *"G5 reached"*, action *"set the Track A time box from measured throughput and issue this
   file as v1.1.0"*. G5 closed 2026-08-02; the file is still v1.0.0. This is the guard against scope
   drift that the project was built to have.
2. **Set the 15 `validation.*` parameters.** All unset, including `go_live_criteria` and
   `max_allowable_drawdown` — which makes the ratified `k.drawdown_pause` inert.
3. **`UDR-004`: which regime ontology is canonical** — the ТЗ's eight or the course's eleven? Only
   the course list has evidence behind it (`REGIME_SPEC.md`).

### Work, highest leverage first

4. **Run `tools/fetch_directory.py`, by hand, often.** The only irreversible clock in the project:
   `departures()` accumulates *forward only*, and it is the sole survivorship evidence a free tier
   can ever produce. Every day without it is permanently lost. ~5 seconds/day.
   Measured 2026-08-09: **three pulls only** — 2026-08-03, 08-05, 08-08 — so it is running by hand
   at irregular 2–3 day gaps, not on a schedule. Owner decision 2026-08-09: **keep it manual for
   now**, no scheduled task.
5. **Reconcile the cost measurement — it was done twice, with opposite answers.** PR-007 on `master`
   returned **inconclusive** on its registered decision rule (negative-estimate rate 53.2%/41.3%
   against a 25% threshold) and then explained that with a claim it has since **withdrawn**. The
   parallel branch's `DR-005` measured **25bp per side** and is right about the direction: a
   clamp-rate sign test gives **19.1%** on real bars against **45.5%** on spreadless synthetic at
   matched volatility, and 126 of 126 instruments read above their own floor. What neither effort
   settled is the **level** — Abdi-Ranaldo correlates +0.46 with volatility and −0.02 with liquidity,
   which is backwards for a spread. Read `POSTMORTEM-2026-08-09.md` §2 before touching this.
6. **Unify the trigger before the live path gets one.** `validation/backtest/engine.py` owns
   `breakout_high` and the entry decision; `application/pipeline.py` has none. No divergence yet
   *only* because live implements no strategy — see `REQUIREMENTS.md` §3. Cheap now, expensive later.
7. **Wire the regime classifier into the daily run.** PR-002 is the only validated finding in the
   project and it is not used; checklist item E04 reports `unavailable`.
8. **A mutation gate for `REQ-VALIDATION-001`.** The narrow version — every ratified criterion's
   referenced parameters are set — is cheap and would have caught `k.drawdown_pause`.
9. **Finish universe coverage** — ~5 more `tools/refresh_universe.py` passes to 100%, then re-check
   DR-003's liquidity plateau against the full population.
10. **Fill the ranked gaps** in `SPEC_GAP_ANALYSIS.md` §4: `RULE_SPEC.md` first (seed draft in
    `dee8f37`), then `SYSTEM_MODES.md`, then `EXECUTION_MODEL.md`.

## 6. Closed by evidence — do not re-open

| | Why |
|---|---|
| Trend-definition family | PR-001 (definitions select different instruments) and PR-005 (those populations then behave the same) both refuted. `screen.trend_definition` stays `unset` |
| Paid market data | Owner decision D10, taken with the survivorship cost known |
| Tuning the current parameters | PR-005 measured the strategy flat at assumed costs and negative under stress — both net |
| New entry filters | Same family, same evidence |
| ~~Spread estimation from free daily data~~ | **Removed 2026-08-09 — this row was wrong.** It rested on PR-007's withdrawn explanation. The sign test shows the estimators do detect a spread; see `POSTMORTEM-2026-08-09.md` §2. Kept struck through because a "closed by evidence" row that quietly disappears is worse than one that was wrong |
| Order placement, automation, multi-user | `CHARTER.md` §3 non-goals — reopening needs a charter amendment |

## 7. The habits that matter here

- **Verify before asserting.** Three documentation defects were found on 2026-08-03, and all three
  read as correct: a stale count, a claim that a transcribed appendix was untranscribed, and a
  framing that made a Berkshire-sized exclusion sound like a rounding error. A careful read did not
  catch them; gates did. When you find that class of defect, add a gate rather than fixing the
  instance.
- **`unavailable` is not `fail`.** A gap in the *system* and a fact about the *trade* are different
  claims. Collapsing them is the most damaging error this product can make.
- **An `UNSET` parameter is the design working**, not a backlog item. Components refuse rather than
  default.
- **Never hand-edit** a `verbatim` block or a generated registry field. Gates 2, 3b–3e exist to
  catch it, which is the point.
- Docs **are** committed here. Every threshold is authored and carries its provenance.

## 8. Where things live

```
docs/00-charter     what this is, what done means, glossary, kill criteria
docs/01-requirements BRD, user stories, NFR, surfaces, REQ registry
docs/02-domain      the course, transcribed and specified
docs/03-data        point-in-time, calendar, vendors, quality
docs/04-journal     audit, checklists, journal schema, evidence records
docs/05-validation  backtest protocol, walk-forward, prereg template, go-live gates
docs/06-engineering architecture, dependency law, determinism, CI policy, invariants
docs/07-ux          task flows, controlled vocabulary
docs/08-pm          roadmap, risk register, gap analysis, definition of done
docs/prereg         four pre-registrations and their reports
registry/           parameters, components, course index, checklists, criteria
src/swingdesk/      the reference implementation — the vertical slice ТЗ §50 requires
tools/              the 16 gates, plus network tools that never run in CI
```
