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
| Merge gates | **18**, one command, all green |
| Tests | **253**, fully offline |
| Docs | 87 files across 8 tiers |
| Components | 465 registered · 7 `specified` · **0 `active`** |
| Parameters | 96 — 63 `unset`, 30 `assumed`, 2 `owner`, **1 `validated`** |
| Studies | 3 reported — **2 refuted**, 1 accepted and quantifiably fragile; plus one post-hoc bound |
| Universe | 1,133 members · 3,687 of 13,043 measured · **28.3% coverage** |
| Project gates | G0, G4, G5 closed · G1, G2, G3, G6, G7 open |

```bash
python tools/check_gates.py
```

That must stay green. A gate that is wrong gets **fixed or removed, never skipped**.

## 3. The uncomfortable summary

**The machinery is real and honest. The strategy is not known to work, and what is known is mostly
negative.**

- The base strategy measured **+0.028R per trade before costs** and **−0.123R under 3× cost stress**
  (PR-005). Costs are *assumed*, not measured — so the sign of the result sits inside an
  unvalidated number.
- The one positive finding (PR-002: breadth separates breakout outcomes) is erased by **1.6–2.3% of
  trades missing at −2R**, and Yahoo serves no delisted history, so that exposure can never be
  confirmed on the free tier.
- `CHARTER.md` §4's v1 finish line is a **machinery** target and was reached 2026-08-02. Reaching
  v1 and reporting no validated edge is a **success** against the ratified criteria, not a failure.

Do not write anything that implies more confidence than that. `UX_COPY.md` §3 carries the standing
warning verbatim.

## 4. What just happened (2026-08-04)

Two efforts had been writing into this repo without knowing about each other. A second track built
ten numbered documents at root to master-ТЗ v1.0 §47 — Russian, "documentation only" — having never
opened `docs/`, `src/` or `registry/`. Consequences: its build plan scheduled ~10 specification
sections as future work that was already done, and its README rewrite dropped the "It does not place
orders" line.

Resolved: `docs/` is canonical (owner decision). All of that track's work is preserved verbatim in
commit **`dee8f37`**, its genuinely new material is folded in, and the duplicates are gone.
`docs/08-pm/SPEC_GAP_ANALYSIS.md` is the real §56 analysis: **FULL 28 · PARTIAL 20 · ABSENT 5 ·
DEFERRED 3.**

**Do not rebuild the numbered tree.** Master ТЗ §8 forbids maintaining one logic in two places, and
for a day this repo was doing exactly that.

## 4a. What happened after that (2026-08-08)

The top four absent sections are written, each by auditing the tree rather than transcribing the
seed, and each returned a defect no gate could see:

- `docs/02-domain/RULE_SPEC.md` (§15) — the Rule form, and an audit of the eight decision points that
  are rules today. Found: the backtest trigger collapsed "no lookback window" into "did not trigger"
  and counted neither. **Fixed.**
- `docs/05-validation/EXECUTION_MODEL.md` (§28) — fills, gaps, costs, and the intrabar
  stop-before-target policy stated *before* a target exists. Found: `Skipped` declared five reasons
  and incremented three (**fixed**), and the live path sizes from the last close while the backtest
  fills at the next open plus slippage (**open** — it is `REQ-VALIDATION-002`).
- `docs/06-engineering/SYSTEM_MODES.md` (§35) — six modes, four running. Found: `RunManifest` has no
  `mode` field, so a journalled run cannot say whether it was real.
- `docs/02-domain/TRANSITION_SPEC.md` (§16) — the discrete-change object, **renamed** to end the
  collision: *event* means the market's events (`EVENT_SPEC.md`), *transition* means the system's.
  Found: no shape records `from_state`, so a status that changed reads exactly like one that never
  did; Appendix G's required `Candidate.status history` has no store; and the owner's approval of a
  proposal — the one transition with a human actor — is written nowhere.

Also corrected: **five documents said `4 studies, 3 refuted`.** Three pre-registrations are reported
and two of them REJECT; the fourth "study" is the post-hoc survivorship bound inside PR-002, which
carries no verdict. The evidence was right and every summary of it was wrong. Gate 3f
(`tools/verify_studies.py`) now recomputes those counts from the reports, and it was mutation-checked
against the original claim rather than trusted.

**One trap worth knowing about in a worktree.** The venv's editable install points at
`C:\PycharmProjects\SwingDesk\src` — the main checkout — so `pytest` run from a worktree exercises
the *main* tree's source unless `PYTHONPATH` names the worktree's `src`. The documentation gates read
files by path and are unaffected; the code gates are not. Set it before trusting a green run:

```bash
PYTHONPATH=$PWD/src python tools/check_gates.py
```

## 4b. The phase plan — adopted 2026-08-08

**Read `ROADMAP.md` §9 before planning anything.** It governs the roadmap's Now/Next/Later, and where
they disagree it wins.

| Phase | What it is | Exit |
|---|---|---|
| ~~1. Describe~~ | **CLOSED 2026-08-08** | ТЗ `ABSENT` = **0**; §3 and §53 blocked on a missing source |
| 2. Activate | **not "MVP"** — that closed at G5 on 2026-08-02 | first component `active`, status displayed |
| 3. Coverage, demand-driven | built when a strategy card needs it | every component a live card needs is `active` |
| 3′. Paper, in parallel | measures the system, not the edge | Track A's four run-measurable criteria met |
| 4. Research and calibration | costs measured first, ahead of phase 3 | a pre-registered study reports on forward data |

Four adjustments were adopted with it, and two change what happens next:

- **The MVP is behind us.** What looks like one from here is **activation** — 465 registered, 7
  implemented, **0 `active`**.
- **Coverage is demand-driven.** "Maximum coverage" is `k.project_timebox`'s own named kill risk —
  scope drift into the 460-component catalogue. The test before implementing a component: **name the
  strategy card that consumes it.** If there is none, it stays `registered`, which costs nothing.

And one dated decision the plan creates rather than settles: **at the start of phase 3 the scheduling
deferral is revisited** (item 4 below). `a.run_completes` needs 20 consecutive trading days of the run
completing, so Track A cannot close without a scheduled run and phase 4 is unreachable without Track
A. Either it is reversed then, or `k.track_a_timebox` fires at 180 days into *restate the project as
documentation-and-research only* — a legitimate end state, reached deliberately rather than by
default.

## 5. What to do next, ranked

**The ranking below predates §4b's phase plan and is kept for its detail, not for its order.** Where
the two disagree, the phases win. The mapping:

| Phase | Items here |
|---|---|
| 1 — describe | 3 (`UDR-004`), 10 (the remaining gaps) |
| 2 — activate | *not in this list* — see `ROADMAP.md` §4 **P2**, the first `active` component |
| 3 — coverage, demand-driven | 6 (unify the trigger), 7 (wire the regime classifier), 8 (the mutation gate), 9 (universe coverage) |
| 3′ — paper | 4, as the dated decision point: revisit the scheduling deferral |
| 4 — research, moved ahead | 5 (measure costs) |

Two of these change character under the plan. **6 and 7 are no longer "cheap now, expensive later"
items to be done opportunistically** — they are phase 3 work, and under demand-driven coverage they
happen when the first strategy card needs them. **5 moves ahead of its phase** for the reason in
`ROADMAP.md` §9 D: everything built in phase 3 inherits the cost number.

Three of the items below are decisions only the owner can make. They are listed first because they
are overdue, not because they are hard.

### Owner decisions

1. ~~**Ratify the Track A time box.**~~ **Done 2026-08-08.** `criteria.yml` v1.1.0 ratified with
   `k.track_a_timebox`: 120 days from the first scheduled daily run, **or 180 days from ratification
   if no run is ever scheduled**. The second clause was added at ratification because the first
   alone could never have fired — see §5a of `SUCCESS_AND_KILL_CRITERIA.md`. `k.timebox_review` is
   now `met`, six days after it fired.

2. ~~**Set the 15 `validation.*` parameters.**~~ **Done — `DR-005-validation-thresholds.md`
   ratified by the owner 2026-08-08.** All fifteen carry `assumed:DR-005`; four ratify what PR-002
   and PR-005 already used, eight are authored, and `max_allowable_drawdown` at **−15R** is the
   weakest — it names the permutation study that should replace it, and that study is the next
   thing this decision needs. Nothing here is `validated` and nothing pretends to be.
3. **`UDR-004`: which regime ontology is canonical** — the ТЗ's eight or the course's eleven? Only
   the course list has evidence behind it (`REGIME_SPEC.md`).

### Work, highest leverage first

4. ~~**Schedule `tools/fetch_directory.py`.**~~ **Deferred by the owner 2026-08-08, with the loss
   accepted.** Recorded rather than dropped, because the cost is real and permanent: `departures()`
   accumulates forward only and is the sole survivorship evidence a free tier can ever produce, so
   every unscheduled day is unrecoverable at any price. Do not re-raise it as a suggestion — it is
   a decision. It is also what makes the 180-day clause in `k.track_a_timebox` load-bearing.

5. **Measure costs instead of assuming them.** Corwin–Schultz (2012) and Abdi–Ranaldo (2017)
   estimate effective spread from daily OHLC — no new data needed. This is the highest-value study
   available, because the base-strategy verdict currently flips on an assumed 5bps.
6. **Unify the trigger before the live path gets one.** `validation/backtest/engine.py` owns
   `breakout_high` and the entry decision; `application/pipeline.py` has none. No divergence yet
   *only* because live implements no strategy — see `REQUIREMENTS.md` §3. Cheap now, expensive later.
7. **Wire the regime classifier into the daily run.** PR-002 is the only validated finding in the
   project and it is not used; checklist item E04 reports `unavailable`.
8. **A mutation gate for `REQ-VALIDATION-001`.** The narrow half landed 2026-08-08 as gate 3g. What
   remains is the hard half — forcing a gate's inverse must change a verdict — and it is blocked on
   a corpus of evaluated criteria, because nothing evaluates these yet.
9. **Finish universe coverage** — ~5 more `tools/refresh_universe.py` passes to 100%, then re-check
   DR-003's liquidity plateau against the full population.
10. **Fill the ranked gaps** in `SPEC_GAP_ANALYSIS.md` §4. **Six of the nine are written.** The three
    left are blocked on something other than writing time: §5 Coverage Matrix wants to be generated
    rather than authored, §44/§45 need a stored expectation to difference against, and §46 is a
    projection of registries that already exist. §4 says so in each case.

Three cheap items fell out of §4a and are worth doing before they get expensive:

11. ~~**`mode` on `RunManifest`**, required, no default.~~ **Done 2026-08-08**, with `from_state` on
    `DecisionRecord` alongside it. Both were the "gets permanently more expensive" kind: a run
    journalled without a mode, or a decision written without its predecessor, can never acquire one.
    The replay fixture was re-recorded and its `output_hash` is unchanged, which is the evidence
    that two fields were added and no decision moved.
12. ~~**Count `POSITION_OPEN`**, and split the trigger's "no window" from its "did not trigger".~~
    **Done 2026-08-08** — two counters, one test, no trade moved. `EXECUTION_MODEL.md` §5 records
    what changed and the one caveat: PR-005's stored skip counts predate the counters.
13. ~~**The narrow `REQ-VALIDATION-001` gate**~~ **Done 2026-08-08 — gate 3g,
    `tools/verify_criteria.py`.** Three checks, all mutation-tested against a deliberately broken
    registry: a criterion in force whose parameter is unset, a reference that does not resolve, and
    a `status` off the ladder. The third matters most — a typo there would exempt the row from the
    first check, making the gate quietly weaker instead of loudly wrong.

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

## 8. Where things live

```
docs/00-charter     what this is, what done means, glossary, kill criteria
docs/01-requirements BRD, user stories, NFR, surfaces, REQ registry
docs/02-domain      the course, transcribed and specified
docs/03-data        point-in-time, calendar, vendors, quality
docs/04-journal     audit, checklists, journal schema, evidence records
docs/05-validation  backtest protocol, walk-forward, prereg template, go-live gates, execution model
docs/06-engineering architecture, dependency law, determinism, CI policy, invariants
docs/07-ux          task flows, controlled vocabulary
docs/08-pm          roadmap, risk register, gap analysis, definition of done
docs/prereg         four pre-registrations and their reports
registry/           parameters, components, course index, checklists, criteria
src/swingdesk/      the reference implementation — the vertical slice ТЗ §50 requires
tools/              the 18 gates, plus network tools that never run in CI
```
