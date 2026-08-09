# HANDOFF — start here in a fresh session

Written 2026-08-04; rewritten **2026-08-08** at the end of a session that ran 08-05 → 08-08. Read
this, then `AGENTS.md`, then `docs/README.md`. Everything below is measured from the tree, not
remembered — and where a gate derives a number, the gate is named.

**Everything is committed and pushed.** `master` carries the 2026-08-09 reconciliation; one branch remains unmerged.
remote `github.com/golub-kirill/SwingDesk` (public). `master` is the default branch and sits at the
state before this session; nothing has been merged.

---

## 1. What this is

Decision-support software for swing trading Canadian and US equities and ETFs, specified from the
owner's 116-PDF swing-trading course. **It never places orders** — owner decision D1. **The final
trading decision is human-only** — charter amendment A-001. The system prepares, checks and records;
the human decides.

The founding premise: previous attempts failed *upstream of code* — goals, limits and the algorithm
were never frozen first. So documentation is the deliverable, and the code exists to prove the
documentation is implementable.

## 2. State, measured

| | |
|---|---|
| Merge gates | **20**, one command, all green |
| Tests | **298**, fully offline |
| Docs | 86 files, Tier 0–8 · indexed by `registry/project_manifest.yml` |
| Components | 465 catalogued · 458 registered · 7 `specified` · **0 `active`** |
| Parameters | 96 — 83 `unset`, 9 `assumed`, 3 `owner`, **1 `validated`** |
| Golden vectors | 25 across 6 components |
| Studies | 5 registered · **4 reported — 2 refuted**, 1 inconclusive, 1 accepted and quantifiably fragile |
| Universe | 1,133 members · 3,687 of 13,043 measured · **28.3% coverage** |
| Directory | 3 pulls (08-03, 08-05, 08-08) · 14 departures observed · **unscheduled** |
| Costs | slippage **measured** — 25bps per side (`DR-005`); commission still assumed |
| Criteria | `criteria.yml` **v1.1.0**, amended 2026-08-08; v1.0.0 on record |
| ТЗ coverage | FULL 29 · PARTIAL 19 · ABSENT 5 · DEFERRED 3 (`SPEC_GAP_ANALYSIS.md`) |
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
| `claude/swingdesk-handoff-continue-f479bd` | 2026-08-09 | **yes** | PR-008, the v7.0 delta, `AGENTS.md` §9 |
| `claude/swingdesk-handoff-continue-1feb49` | 2026-08-08 | **yes**, merged 2026-08-09 | `DR-005` slippage at 25bp, `RULE_SPEC`/`SYSTEM_MODES`/`EXECUTION_MODEL`, four gates, `validation.max_allowable_drawdown` = 20% |
| `claude/swingdesk-documentation-321418` | 2026-08-09 | **no**, 26 commits | a HANDOFF rewrite, a count audit, a phase plan, `DR-006`, `DR-007` — unreviewed |

**One branch is still out, and `master` contradicts parts of it.** `criteria.yml` is still v1.0.0 here while `321418` carries a v1.1.0 that **sets** the Track A time box — the version the owner chose. The file-by-file plan is `docs/08-pm/RECONCILIATION_PLAN.md`; steps 1 and 2 are done, 3 to 8 are not. **Merge nothing without it.**
— two `DR-005`s, two `PR-008`s, three incompatible `criteria.yml` v1.1.0. The file-by-file plan is
`docs/08-pm/RECONCILIATION_PLAN.md`. **Merge nothing without it.**

## 3. The uncomfortable summary

**The machinery is real and honest. The strategy is not known to work, and what is known is mostly
negative.**

- The base strategy measured **+0.028R per trade** at 1× costs and **−0.123R under 3× cost stress**
  (PR-005). Both are **net** — gross is never reported (`DR-004` consequence 1), so "before costs" is
  the one description that is wrong. **The second number is the operative one:** `DR-005` measures
  slippage at ~**25bps per side** against DR-004's assumed 5, and the two PR-005 points put
  break-even at only **1.369×** the assumption. The 1× column was never the applicable one.
- **The direction is settled and the level is not.** `PR-008` reached the opposite conclusion — that
  the estimators cannot resolve the spread — and that explanation was **withdrawn on 2026-08-09**
  after a calibration-free sign test refuted it. But neither effort settled the magnitude:
  Abdi-Ranaldo correlates **+0.46** with volatility and **−0.02** with liquidity, which is backwards
  for a spread, and the published literature documents exactly that bias. Treat 25bp as
  "materially more than 5", not as a measurement of 25. `POSTMORTEM-2026-08-09.md` §2.
- The one positive finding (PR-002: breadth separates breakout outcomes) is erased by **1.6–2.3% of
  trades missing at −2R**, and Yahoo serves no delisted history, so that exposure can never be
  confirmed on the free tier.
- **There is no legal source of probability in this system today.** No expectation estimate exists,
  no calibrated model exists (`EXPECTATION_SPEC.md` §6). Any probability displayed would be
  manufactured.
- **Two ratified criteria are inert.** `k.strategy_rejected` cannot fire — Track B evaluates on
  journalled trades only, and its benchmark comparison is not commensurable. See §5.
- `CHARTER.md` §4's v1 finish line is a **machinery** target and was reached 2026-08-02. Reaching v1
  and reporting no validated edge is a **success** against the ratified criteria, not a failure.

Do not write anything implying more confidence than that. `UX_COPY.md` §3 carries the standing
warning verbatim.

## 4. What happened, and what it settled

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

### The documentation was audited against itself and did not hold (2026-08-08)

A master requirements document (ТЗ §§1–54) asked for the documentation to be **verified and updated,
not rewritten**. Its §53 gives the order; **steps 1–4 are done**, and step 8 is in progress.

Its §4 listed seven suspected inconsistencies in `docs/README.md`. **All seven were confirmed**, and
the audit found more: a study census overstated in fourteen places, three written specifications
marked `planned`, two specifications indexed nowhere, and `RISK_REGISTER.md` claiming the gates were
tested for their ability to fail when nothing tested them.

**The census error claimed *more* negative evidence than existed**, which is the direction nobody
checks. Its cause: `PR-002-survivorship-bound.json` carries no `prereg` id and no `verdict`, so it is
a supporting analysis, and counting it inflated every summary that quoted it.

**Four gates now cover the class**, because a defect found by hand will be found by hand again:

| | |
|---|---|
| 12 `verify_criteria.py` | a committed criterion that cannot fire |
| 13 `verify_study_summary.py` | a stated study count the result files do not support |
| 14 `verify_counts.py` | any hard-coded count drifted from the registries |
| 15 `verify_project_manifest.py` | the index drifting from the tree or a document's own header |

`registry/project_manifest.yml` is the machine source of truth for the document set, and
`docs/README.md` is checked against it both ways. Gates 13 and 15 have **failure tests**
(`tests/test_gates.py`); the other seventeen do not, and `RISK_REGISTER.md` says so.

### Costs measured, the clock started (2026-08-05)

`DR-005` supersedes DR-004's slippage: **25bps per side**, from Corwin-Schultz (2012) and
Abdi-Ranaldo (2017) over the A-tier instruments already in `data/bars.duckdb`. **No network** —
DR-004 had rejected spread-derived slippage as "correct and unavailable" because no free source
serves historical *quotes*, and these estimators never needed quotes. Evidence in
`docs/decisions/measurements/spread-sample.json`, reproducible byte-identically.

The survivorship clock: `directory.duckdb` had **one** pull, so `departures()` could not answer at
all. Three pulls now exist and **14 departures** are recorded across two windows.

### Owner decisions, all 2026-08-08

| Decision | Where it lives |
|---|---|
| An AI agent is **in scope**, to subsume context and present a global picture; it **may never decide** | `CHARTER.md` **A-001**, the charter's first amendment |
| The synthesis/recommendation boundary, including *any ordering must name a deterministic key* | `AI_AUTHORITY_MODEL.md` §3, **ratified as written** |
| AI provider: local Ollama model — keeps `$0/month` | `AI_AUTHORITY_MODEL.md` §10 |
| `k.timebox_review` actioned by **removing** the Track A time box, not setting one | `criteria.yml` v1.1.0 |
| Track B evaluates on **journalled trades only** | `criteria.yml` v1.1.0 |
| §16's collision resolves by naming the **new** object differently | this file, §5 |
| §31 is specified with its five portfolio caps left `unset` | this file, §5 |
| `validation.max_allowable_drawdown` = **20% of equity** | `parameters.yml`, `status: owner` |

**A-001 carries a standing condition**: nothing AI is implemented before the authority model is
written and gated. The model is written; nothing is gated yet.

**Removing the Track A time box removed a guard.** What remains against scope drift is the activation
gate — components sit at `registered` at no cost and reach `active` only deliberately, and none is
`active`.

### Two efforts reconciled (2026-08-04)

A second track built ten numbered documents at root to ТЗ §47 — Russian, "documentation only" —
having never opened `docs/`, `src/` or `registry/`. Its build plan scheduled ~10 specification
sections as future work already done here.

`docs/` is canonical (owner). That track is preserved verbatim in commit **`dee8f37`**, its genuinely
new material folded in, duplicates gone. **Do not rebuild the numbered tree** — ТЗ §8 forbids
maintaining one logic in two places, and for a day this repo was doing exactly that.

## 5. What to do next, ranked

### Owner decisions — three remain

1. **Set the remaining 14 `validation.*` parameters**, `go_live_criteria` first — `GO_LIVE_GATES.md`
   cannot be evaluated without it.
2. **`UDR-004`: which regime ontology is canonical** — the ТЗ's eight or the course's eleven? Only
   the course list has evidence behind it (`REGIME_SPEC.md`).
3. **Does `PR-007` run?** It is registered and blocked on a re-fetch — its window is
   2016-08-01 → 2026-07-31 and the store holds two years. DR-005 already settles the *direction*;
   the study buys a confidence interval at the measured cost vector. Registering cost nothing;
   running is the decision.

**Deliberately not owner decisions:** the five portfolio caps stay `unset` (2026-08-08) — that is the
fail-closed design working, and §31 is specified around it. Setting them is what would make
`k.strategy_rejected` evaluable, so they are listed here as leverage, not as debt.

### Work, highest leverage first

4. **Run `tools/fetch_directory.py` by hand, often.** The only irreversible clock, and still
   unscheduled — the pulls that exist happened because someone remembered, which is not a mechanism.
   It accumulates *forward only*: a symbol that left and was replaced inside a gap is invisible
   forever. Owner decision 2026-08-09: **keep it manual for now**, no scheduled task.

   The rate is measurable and not small: **14 departures across two windows** (7 in 2 days, 7 in 3)
   against ~13,100 names. Whatever fraction are genuine delistings is the survivorship exposure
   `PR-002` cannot bound and D10 makes unbuyable. **~5 seconds a day.**

   ```bash
   python tools/fetch_directory.py --data C:/PycharmProjects/SwingDesk/data
   ```

   Run from the main repo, not a worktree: `data/` is gitignored and exists only there, and the
   tool's `--data` default would create a fresh empty store that accumulates nothing.
5. **Finish the reconciliation.** `RECONCILIATION_PLAN.md` steps 3–8 are outstanding: the duplicated
   specs, merging `claude/…-321418`, the single `criteria.yml` amendment, gate renumbering, and
   recomputing every R at 25bp. Step 7 changes the headline, so it is not cosmetic.
6. **§31 Capital Allocation** — the top absent section, specified with caps `unset`. It is the layer
   the commensurability rule needs, so it unblocks a ratified criterion as well as filling a gap.
7. **§16's transition object**, under a name that is not `EVENT_SPEC.md` — that stays with the
   market-event catalogue (M34, verbatim). The ТЗ's Event is a formal discrete-transition object.
8. **Unify the trigger before the live path gets one.** `validation/backtest/engine.py` owns
   `breakout_high` and the entry decision; `application/pipeline.py` has none. No divergence yet
   *only* because live implements no strategy (`REQUIREMENTS.md` §3). **Top code task.**
8. **Build the AI claim reviewer.** Plan and rationale are settled — retrieve deterministically, ask
   the model only whether evidence supports a claim. It **can never be a merge gate**: `CI_POLICY.md`
   §4 bars network in CI and `a.reproducible` is ratified. Its success metric is how many gates it
   causes, not how many findings it repeats. A four-case trial scored 4/4 on a known defect.
9. **Wire the regime classifier into the daily run.** PR-002 is the only validated finding and it is
   not used; checklist item E04 reports `unavailable`.
10. **Finish universe coverage** — ~5 more `tools/refresh_universe.py` passes to 100%, then re-check
    DR-003's liquidity plateau and re-run DR-005's measurement over the full population.
11. **The mutation half of `REQ-VALIDATION-001`.** Gate 12 checks a criterion's inputs exist; nothing
    checks that a verdict ever changes. `if is_long: return True` with every parameter set still
    passes — the failure the requirement leads with.
12. **Failure tests for the other seventeen gates.** The pattern is in `tests/test_gates.py`: point a
    verifier at a fixture tree with `SWINGDESK_ROOT` and assert it reports *that* defect. Nothing
    mutates the real tree.

## 6. Closed by evidence — do not re-open

| | Why |
|---|---|
| Trend-definition family | PR-001 (definitions select different instruments) and PR-005 (those populations then behave the same) both refuted. `screen.trend_definition` stays `unset` |
| Paid market data | Owner decision D10, taken with the survivorship cost known |
| Tuning the current parameters | PR-005 measured the strategy flat at assumed costs and negative under stress — both net |
| New entry filters | Same family, same evidence |
| ~~Spread estimation from free daily data~~ | **Removed 2026-08-09 — this row was wrong.** It rested on PR-008's withdrawn explanation. The sign test shows the estimators do detect a spread; see `POSTMORTEM-2026-08-09.md` §2. Kept struck through because a "closed by evidence" row that quietly disappears is worse than one that was wrong |
| Order placement, automation, multi-user | `CHARTER.md` §3 non-goals — reopening needs a charter amendment |
| An AI that decides, sizes, or ranks by desirability | `CHARTER.md` A-001 and `AI_AUTHORITY_MODEL.md` §3, ratified |

## 7. The habits that matter here

- **Verify before asserting.** Every documentation defect this project has had read as correct to its
  author. A careful read did not catch them; gates did. **When you find that class of defect, add a
  gate rather than fixing the instance.**
- **A count is not a fact until something derives it.** Counts were reconciled by hand three times
  and every pass left stale numbers behind — gate 14 found eight more the moment it existed. Before
  typing a number that describes this repository, check whether a gate derives it.
- **History is not drift.** A roadmap line reading `DONE 2026-08-03, 14 gates` is correct *about that
  date*. Gate 14 skips struck-through and dated-completion lines for this reason; do not "fix" them
  and do not remove that exclusion.
- **`unavailable` is not `fail`.** A gap in the *system* and a fact about the *trade* are different
  claims. Collapsing them is the most damaging error this product can make.
- **An `UNSET` parameter is the design working**, not a backlog item. Components refuse rather than
  default.
- **Records are append-only.** A pre-registration gets a dated amendment, never an edit; `criteria.yml`
  gets a version; a decision record gets superseded. `PR-007` and A-001 are the worked examples.
- **Never hand-edit** a `verbatim` block or a generated registry field. Gates 2, 3b–3e catch it.
- **Check the clock against the data.** This session ran 08-05 → 08-08; the directory pull is stamped
  with machine time, not the day the work felt like. Dates from a conversation are not measurements;
  the ones in `directory.duckdb` and `spread-sample.json` are.
- **Run the gates with the project venv, and mind worktrees.** Under a bare interpreter **14 of the
  20 gates fail** for missing PyYAML, ruff, mypy and import-linter — environment, not regression.
  Worse in a worktree: the editable install resolves `swingdesk` to `C:/PycharmProjects/SwingDesk/src`,
  so a worktree's tests silently exercise the **main** tree unless `PYTHONPATH` points at the
  worktree's `src`. Both were hit on 2026-08-05.

## 8. Where things live

```
docs/00-charter      charter (+ amendment A-001), kill criteria, constraints, glossary
docs/01-requirements BRD, user stories, NFR, surfaces, REQ registry
docs/02-domain       the course transcribed and specified; RULE, EXECUTION_MODEL, EXPECTATION
docs/03-data         point-in-time, calendar, vendors, quality
docs/04-journal      audit, checklists, journal schema, evidence records
docs/05-validation   backtest protocol, walk-forward, prereg template, go-live gates
docs/06-engineering  architecture, dependency law, determinism, CI policy, SYSTEM_MODES,
                     AI_AUTHORITY_MODEL, invariants
docs/07-ux           task flows, controlled vocabulary
docs/08-pm           roadmap, risk register, gap analysis, COVERAGE_AUDIT, the postmortem and
                     the reconciliation plan, definition of done
docs/prereg          five pre-registrations, four of them reported
docs/decisions       five decision records and the measurements behind them
registry/            parameters, components, course index, checklists, criteria (v1.1.0),
                     project_manifest — the document set's machine source of truth
src/swingdesk/       the reference implementation — the vertical slice ТЗ §50 requires
tools/               the 20 gates, plus network tools that never run in CI
tests/test_gates.py  the gates' own failure tests — gates 13 and 15 only, so far
```

## 9. If you are here to apply the master ТЗ

Read `docs/08-pm/COVERAGE_AUDIT.md` **before writing any new document** — that is what it is for
(ТЗ §49). It licensed three of the seven documents the ТЗ proposes and refused four as already-housed,
charter-excluded, or dependent on something unwritten. Then `SPEC_GAP_ANALYSIS.md` for the §56
section-by-section view.

Four findings that will save you the same discovery:

1. **Much of the ТЗ is already law here under other names.** `RULE_SPEC.md` §9 is the worked example
   — eleven of §15's requirements were already met, several more strictly than asked. Check first.
2. **Nothing may be called missing because its name is not in an index** (§8.2). Inspection reversed
   three verdicts in the coverage audit, in both directions.
3. **Its stated numbers go stale.** The version received on 2026-08-08 quoted the parameter census and
   golden-vector count as they were days earlier. Verify its claims too — its own §1 requires it.
4. **Do not adopt its status vocabulary.** This tree's ladder is `planned | drafting | owner-pending |
   frozen | generated`, enforced by gate 3e on every document header. ТЗ §6.1 proposes a richer set;
   adopting it would mean two vocabularies in one repository, which §8 of that same document forbids.
   Recorded in the manifest as an extension point, not a gap.
