# HANDOFF — start here in a fresh session

Written 2026-08-04 after reconciling two parallel documentation efforts; updated **2026-08-08** after
a documentation-integrity pass against master ТЗ §53. Read this, then `AGENTS.md`, then
`docs/README.md`. Everything below is measured from the tree, not remembered.

**Nothing in this branch is committed.** The working tree holds the whole of 2026-08-05 → 08-08:
four new gates, a project manifest, three specifications, a decision record and a pre-registration.
19 gates pass on it. Review before committing.

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
| Merge gates | **19**, one command, all green |
| Tests | **270**, fully offline |
| Docs | 79 files across **nine** tiers, Tier 0–8 · indexed by `registry/project_manifest.yml` |
| Components | 465 catalogued · 458 registered · 7 `specified` · **0 `active`** |
| Parameters | 96 — 83 `unset`, 9 `assumed`, 3 `owner`, **1 `validated`** |
| Studies | 4 registered · **3 reported — 2 refuted**, 1 accepted and quantifiably fragile |
| Universe | 1,133 members · 3,687 of 13,043 measured · **28.3% coverage** |
| Directory | 3 pulls (08-03, 08-05, 08-08) · 14 departures observed · **still unscheduled — see §5.5** |
| Costs | slippage **measured** 2026-08-05 — 25bps per side (DR-005); commission still assumed |
| Project gates | G0, G4, G5 closed · G1, G2, G3, G6, G7 open |

```bash
python tools/check_gates.py
```

That must stay green. A gate that is wrong gets **fixed or removed, never skipped**.

## 3. The uncomfortable summary

**The machinery is real and honest. The strategy is not known to work, and what is known is mostly
negative.**

- The base strategy measured **+0.028R per trade** at 1× costs and **−0.123R under 3× cost stress**
  (PR-005). **As of 2026-08-05 the second number is the operative one.** Slippage is no longer
  assumed: it measures ~**25bps per side** across the A-tier universe against DR-004's assumed 5
  (DR-005), and every aggregate tried puts it at 2.3× the assumption or more. The 1× column was
  never the applicable one.
- The one positive finding (PR-002: breadth separates breakout outcomes) is erased by **1.6–2.3% of
  trades missing at −2R**, and Yahoo serves no delisted history, so that exposure can never be
  confirmed on the free tier.
- `CHARTER.md` §4's v1 finish line is a **machinery** target and was reached 2026-08-02. Reaching
  v1 and reporting no validated edge is a **success** against the ratified criteria, not a failure.

Do not write anything that implies more confidence than that. `UX_COPY.md` §3 carries the standing
warning verbatim.

## 4. What just happened

### 2026-08-08 — the documentation was audited against itself, and it did not hold

A master requirements document arrived (master ТЗ, §§1–54) asking for the documentation to be
**verified and updated, not rewritten**. Its §53 gives the order; **steps 1–4 and part of 8 are
done** — the coverage audit is `docs/08-pm/COVERAGE_AUDIT.md`.

Its §4 listed seven suspected inconsistencies in `docs/README.md`. **All seven were confirmed
against the tree**, and the audit found more:

- **The study count was wrong in fourteen places.** Six documents each claimed one more study run
  than exists, and one more refutation. The record holds three studies carrying a verdict — PR-001
  `reject`, PR-002 `accept`, PR-005 `reject`.
  The cause: `PR-002-survivorship-bound.json` has no `prereg` id and no `verdict`, so it is a
  supporting analysis, and counting it inflated every summary quoting it — including
  `RISK_REGISTER.md`'s statement of the project's central risk. **It claimed more negative evidence
  than exists**, which is the direction nobody checks.
- **Three specifications were marked `planned` and were written.** `REGIME_SPEC.md`, `EVENT_SPEC.md`
  and `CHART_SPEC.md`, 118–161 lines each, all declaring `drafting` in their own headers.
- **Two specifications were indexed nowhere.** `REQUIREMENTS.md` and `SPEC_GAP_ANALYSIS.md`.
- **"57 documents in 8 tiers"** — both numbers wrong; the tiers run 0–8, which is nine.
- **`RISK_REGISTER.md` B-1 claimed the gates were tested for their ability to fail.** They were not.
  That row is the mitigation for this project's structural risk, and it was decoration.

**Four gates now cover the class**, because a defect found by hand will be found by hand again:

| | |
|---|---|
| 12 `verify_criteria.py` | a committed criterion that cannot fire |
| 13 `verify_study_summary.py` | a stated study count the result files do not support |
| 14 `verify_counts.py` | any hard-coded count drifted from the registries |
| 15 `verify_project_manifest.py` | the index drifting from the tree or from a document's own header |

`registry/project_manifest.yml` is new and is now the machine source of truth for the document set —
9 tiers, 63 documents. `docs/README.md` is checked against it in both directions. Gates 13 and 15
are themselves tested for the ability to fail (`tests/test_gates.py`); **the other seventeen are
not**, and `RISK_REGISTER.md` now says so.

Also written: `RULE_SPEC.md` (ТЗ §15, the central object — the reconciliation found **eleven of its
requirements already met here**, several more strictly than the ТЗ asks), `SYSTEM_MODES.md` (§35)
and `EXECUTION_MODEL.md` (§28, the intrabar policy written while it is still free to write).

### 2026-08-05 — costs measured, the clock started, the inert gate closed

**Slippage is measured.** `DR-005` supersedes DR-004's slippage component: **25bps per side**, from
Corwin-Schultz (2012) and Abdi-Ranaldo (2017) run over the 1,131 A-tier instruments already in
`data/bars.duckdb`. No network — DR-004 had rejected spread-derived slippage as "correct and
unavailable" because no free source serves historical *quotes*, and these estimators never needed
quotes. Evidence in `docs/decisions/measurements/spread-sample.json`, reproducible byte-identically.

**The survivorship clock is running.** `directory.duckdb` had exactly **one** pull, so
`departures()` could not return anything at all. There are now two, and the first observation is
recorded: **7 symbols gone, 32 new** between 2026-08-03 and 2026-08-05. It is an observation, not a
delisting — a ticker change looks identical from here. **It still is not scheduled**, and every day
without a pull is permanently lost.

**`k.drawdown_pause` can fire.** The owner set `validation.max_allowable_drawdown` to **20% of
equity**, and gate 12 (`verify_criteria.py`) now fails the build if any ratified or owner-set
criterion references an `unset` parameter. `REQ-VALIDATION-001` moves to *partially* met — the
mutation half, which is the half it leads with, is still open.

### 2026-08-04 — two documentation efforts reconciled

Two efforts had been writing into this repo without knowing about each other. A second track built
ten numbered documents at root to master-ТЗ v1.0 §47 — Russian, "documentation only" — having never
opened `docs/`, `src/` or `registry/`. Consequences: its build plan scheduled ~10 specification
sections as future work that was already done, and its README rewrite dropped the "It does not place
orders" line.

Resolved: `docs/` is canonical (owner decision). All of that track's work is preserved verbatim in
commit **`dee8f37`**, its genuinely new material is folded in, and the duplicates are gone.
`docs/08-pm/SPEC_GAP_ANALYSIS.md` is the real §56 analysis: **FULL 29 · PARTIAL 18 · ABSENT 6 ·
DEFERRED 3** (was 28/16/9/3 until §35, §28 and §15 were written on 2026-08-05).

**Do not rebuild the numbered tree.** Master ТЗ §8 forbids maintaining one logic in two places, and
for a day this repo was doing exactly that.

## 5. What to do next, ranked

Four of these are decisions only the owner can make. They are listed first because they are
overdue, not because they are hard.

### Owner decisions

1. **`k.timebox_review` has fired and is unactioned.** `registry/criteria.yml` is ratified and says:
   trigger *"G5 reached"*, action *"set the Track A time box from measured throughput and issue this
   file as v1.1.0"*. G5 closed 2026-08-02; the file is still v1.0.0. This is the guard against scope
   drift that the project was built to have.
2. **Set the remaining 14 `validation.*` parameters**, `go_live_criteria` first.
   `max_allowable_drawdown` was set 2026-08-05 (20% of equity) and gate 12 now enforces that a
   ratified criterion's parameters exist — so this is no longer silent, but it is still unset.
3. **`UDR-004`: which regime ontology is canonical** — the ТЗ's eight or the course's eleven? Only
   the course list has evidence behind it (`REGIME_SPEC.md`).
4. **Does the base strategy survive measured costs?** DR-005 makes PR-005's 3× column the operative
   one without a re-run, which settles the *direction*. Quantifying it needs `PR-007` — now
   registered and blocked on a re-fetch, since its window is 2016-08-01 → 2026-07-31 and the store
   holds two years. **Running it is the decision**; registering it cost nothing.
5. **The §16 name collision.** `EVENT_SPEC.md` here is the *market-event catalogue*; the ТЗ's Event
   is a formal transition object. Two things, one name — the §11 terminology failure the ТЗ warns
   about. Rename the catalogue, or name the new object something else. **This blocks the top
   remaining spec gap.** Recommend the latter: the catalogue is cited from several documents.

6. **Is an AI decision agent in scope?** `COVERAGE_AUDIT.md` §4 found that three documents
   deferred the whole contour citing `CHARTER.md` §3 — **and the charter does not mention AI
   anywhere.** Its nearest non-goal, "Automated trading of any kind", excludes an autonomous trader
   and says nothing about an assistant proposing a decision a human approves. `IN_V1` / `LATER` /
   `OUT_OF_SCOPE`. If the answer is out of scope, the fix is a **charter amendment adding the
   non-goal**, not a citation to a clause nobody wrote.

Two more are recorded in `PR-007` §6 and want a ruling: whether Track B criteria evaluate on
backtest trades or only journalled ones (`b.min_sample` says `measured_by: journal`, so on a literal
reading **no backtest can ever fire `k.strategy_rejected`**), and how an expectancy CI in R is made
comparable to a buy-and-hold benchmark. Both make a ratified criterion un-evaluable as written.

### Work, highest leverage first

5. **Schedule `tools/fetch_directory.py`. This is the only irreversible clock and it is still
   unscheduled** — three pulls exist because someone remembered three times, which is not a
   mechanism. It accumulates *forward only*: a symbol that left and was replaced inside a gap is
   invisible forever, and the gaps so far were 2 and 3 days. ~5 seconds a day.

   The rate is now measurable and it is not small. **14 departures across two windows** — 7 between
   08-03 and 08-05, 7 more between 08-05 and 08-08 — against a directory of ~13,100 names. Whatever
   fraction of those are genuine delistings rather than ticker changes is the survivorship exposure
   `PR-002` cannot bound and D10 makes unbuyable. Every unscheduled day discards a sample of it.

   ```bash
   python tools/fetch_directory.py --data C:/PycharmProjects/SwingDesk/data
   ```

   Run it from the main repo, not a worktree: `data/` is gitignored and exists only there, and the
   tool's `--data` default would create a fresh empty store that accumulates nothing.
6. **Act on `COVERAGE_AUDIT.md`.** It is written and it licensed **two of seven** proposed
   documents — an expectation/baseline specification and a strategy validation dossier — refusing
   the other five as already-housed, charter-excluded or scope-undecided. Read it before writing any
   new document; that is what it is for (§49).

   Its §4 is the finding that matters: **the AI contour was deferred by three documents citing a
   charter clause that does not exist.** Corrected to `OWNER_PENDING` in `SPEC_GAP_ANALYSIS.md` and
   `REQUIREMENTS.md`; the decision itself is owner item 6 above.
7. **Unify the trigger before the live path gets one.** `validation/backtest/engine.py` owns
   `breakout_high` and the entry decision; `application/pipeline.py` has none. No divergence yet
   *only* because live implements no strategy — see `REQUIREMENTS.md` §3. Cheap now, expensive later.
   **This is the top code task.**
8. **Wire the regime classifier into the daily run.** PR-002 is the only validated finding in the
   project and it is not used; checklist item E04 reports `unavailable`.
9. **Finish universe coverage** — ~5 more `tools/refresh_universe.py` passes to 100%, then re-check
   DR-003's liquidity plateau against the full population. It also re-runs DR-005's measurement over
   the full A-tier population in minutes, which is the cheapest way to improve that number.
10. **The mutation half of `REQ-VALIDATION-001`.** Gate 12 checks a criterion's inputs exist; nothing
    checks that a gate's verdict ever changes. `if is_long: return True` with every parameter set
    still passes. That is the failure the requirement leads with.
11. **Failure tests for the other seventeen gates.** Two are covered. The pattern is established in
    `tests/test_gates.py` — point a verifier at a fixture tree with `SWINGDESK_ROOT` and assert it
    reports *that* defect. Nothing mutates the real tree.
12. **The remaining ranked gaps** in `SPEC_GAP_ANALYSIS.md` §4, after the coverage audit says they
    are genuinely absent: §16 (blocked on the naming decision above), then §23 Expectation Model and
    §31 Capital Allocation.

Done 2026-08-05 → 08-08: the directory clock started, costs measured (`DR-005`), `PR-007`
registered, the three top-ranked spec gaps closed (`RULE_SPEC.md`, `SYSTEM_MODES.md`,
`EXECUTION_MODEL.md`), and gates 12–15 built with the project manifest behind them.

## 6. Closed by evidence — do not re-open

| | Why |
|---|---|
| Trend-definition family | PR-001 (definitions select different instruments) and PR-005 (those populations then behave the same) both refuted. `screen.trend_definition` stays `unset` |
| Paid market data | Owner decision D10, taken with the survivorship cost known |
| Tuning the current parameters | PR-005 measured the strategy flat before costs and negative under stress |
| New entry filters | Same family, same evidence |
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
- **A count is not a fact until something derives it.** Counts were reconciled by hand three times
  and every pass left stale numbers behind — gate 14 found eight more the moment it existed. If you
  are about to type a number that describes this repository, check whether a gate derives it first.
- **History is not drift.** A roadmap line reading `DONE 2026-08-03, 14 gates` is a correct statement
  about that date. Gate 14 skips struck-through and dated-completion lines for this reason; do not
  "fix" them, and do not remove that exclusion.
- **Check the clock against the data.** This session ran 2026-08-05 → 08-08 and the directory pull
  is stamped with the machine time, not the day the work felt like. Dates that came from a
  conversation are not measurements; the ones in `directory.duckdb` and `spread-sample.json` are.
- **Run the gates with the project venv, and mind worktrees.** Under a bare interpreter 11 of the
  19 gates fail for missing PyYAML, ruff, mypy and import-linter — that is the environment, not a
  regression. Worse in a worktree: the editable install resolves `swingdesk` to
  `C:/PycharmProjects/SwingDesk/src`, so a worktree's tests silently exercise the **main** tree's
  source unless `PYTHONPATH` points at the worktree's `src`. Both were hit on 2026-08-05.

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
docs/prereg         four pre-registrations, three of them reported
docs/decisions      five decision records and the measurements behind them
registry/           parameters, components, course index, checklists, criteria,
                    project_manifest — the document set's machine source of truth
src/swingdesk/      the reference implementation — the vertical slice ТЗ §50 requires
tools/              the 19 gates, plus network tools that never run in CI
tests/test_gates.py the gates' own failure tests — gates 13 and 15 only, so far
```

## 9. If you are here to apply the master ТЗ

Read `docs/08-pm/SPEC_GAP_ANALYSIS.md` before writing anything. Its §56 method is the one the ТЗ
itself asks for: apply the specification **as a gap analysis against what exists**, not as a second
tree. A previous effort skipped that step and scheduled ten sections as future work that were
already done here (§4, 2026-08-04).

Three findings from applying it that will save the next session the same discovery:

1. **Much of the ТЗ is already law here under other names.** `RULE_SPEC.md` §9 is the worked
   example. Check before specifying.
2. **Its stated numbers go stale.** The version received on 2026-08-08 quoted the parameter census
   and the golden-vector count as they were days earlier. Verify its claims too — §1 requires it.
3. **Do not adopt its status vocabulary.** This tree's ladder is `planned | drafting | owner-pending
   | frozen | generated`, enforced by gate 3e on every document header. The ТЗ §6.1 proposes a
   richer set; adopting it would mean two vocabularies in one repository, which §8 of that same
   document forbids. Recorded in the manifest as an extension point, not a gap.
