# HANDOFF — start here in a fresh session

Written 2026-08-04; rewritten 2026-08-08; **brought current 2026-08-09**, after a session that
reconciled three parallel branches into `master` and updated the study record. Read this, then
`AGENTS.md` — especially **§10, four rules that were paid for on 2026-08-09** — then
`docs/README.md`.

Everything below is measured from the tree, not remembered, and where a gate derives a number the
gate is named. **Twenty-two gates now derive most of them**, so a figure here that disagrees with
`python tools/check_gates.py` is this document being wrong, not the gate.

**Everything is committed and pushed.** `master` carries the 2026-08-09 reconciliation — all three
parallel branches merged — on `github.com/golub-kirill/SwingDesk` (public).

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
| Merge gates | **24**, one command, all green · **CI since 2026-08-10** (`gates`, windows-latest); 22 run there, 2 report `UNAVAILABLE` because the course PDFs are not in the repo |
| `master` | **protected** since 2026-08-10 — required check `gates`, admins included, no force-push. A new merge commit is refused until its check reports; fast-forward a green commit, or use a PR |
| Tests | **327**, fully offline |
| Docs | 102 files, Tier 0–8 · indexed by `registry/project_manifest.yml` |
| Components | 465 catalogued · 458 registered · 6 `specified` · **1 `active`** — ATR (`M18-T0280-v5.0`), activated 2026-08-10, the first ever |
| Parameters | 96 — 61 `unset`, 30 `assumed`, 4 `owner`, **1 `validated`** · `risk.per_trade_pct` and `risk.costs_allowance` set 2026-08-11, so sizing no longer refuses |
| Golden vectors | 25 across 6 components |
| Studies | 7 registered · **5 reported — 3 refuted**, 1 inconclusive, 1 accepted and quantifiably fragile |
| Daily run | **SCHEDULED 2026-08-09** — Windows Task Scheduler, `SwingDesk daily run`, weekdays 18:30 local, wrapper `tools/daily_run.cmd`, log `data/daily_run.log`. ~5 min, ~2.4MB of log per run |
| Track A clock | `a.run_completes` needs **20 consecutive** trading days · **counter at 0**. First scheduled run 2026-08-10 **failed on battery** (§5) and was re-run by hand at 20:46; treat the clock as starting with the first clean scheduled run |
| Directory | 3 pulls (08-03, 08-05, 08-08) · 14 departures observed · **still manual, by owner decision** |
| Costs | slippage **measured** — 25bps per side (`DR-005`); commission still assumed |
| Criteria | `criteria.yml` **v1.1.0** — `k.track_a_timebox` ratified, `k.timebox_review` `met`; v1.0.0 on record |
| ТЗ coverage | FULL 29 · PARTIAL 19 · ABSENT 5 · DEFERRED 3 (`SPEC_GAP_ANALYSIS.md`) |
| Project gates | G0, G4, G5 closed · G1, G2, G3, G6, G7 open |
| Universe | 1,133 members · 3,687 of 13,043 measured · **28.3%** — last measured 2026-08-03, not re-checked since |

```bash
PYTHONPATH=$PWD/src python tools/check_gates.py
```

Must stay green. A gate that is wrong gets **fixed or removed, never skipped**.

### You are not the only effort. Check this before starting work.

This repository's normal mode is **several worktrees at once**, and the table above measures only the
one you are standing in. On 2026-08-09 three efforts branched from `9a07fab`, none knew about the
others, and one re-ran a study another had already finished and reached the opposite conclusion —
`docs/08-pm/POSTMORTEM-2026-08-09.md`, root cause A. Gate 16 now fails if a worktree is missing here.

| Branch | Tip | Merged? | What it holds |
|---|---|---|---|
| `claude/swingdesk-handoff-continue-f479bd` | 2026-08-09 | **yes** | PR-008, the v7.0 delta, `AGENTS.md` §9–§10 |
| `claude/swingdesk-handoff-continue-1feb49` | 2026-08-08 | **yes**, merged 2026-08-09 | `DR-005` slippage at 25bp, `EXECUTION_MODEL`, four gates, `validation.max_allowable_drawdown` = 20% |
| `claude/swingdesk-documentation-321418` | 2026-08-09 | **yes**, merged 2026-08-09 | `DR-006`, `DR-007`, ALLOCATION/TRANSITION/ENTITY_MAP/EXPECTATION_MODEL/DRIFT_AND_LEARNING/CHANGE_MANAGEMENT/KNOWLEDGE_GRAPH, five gates, `criteria.yml` v1.1.0 |
| `claude/skills-llm-council-setup-1e1d65` | `63b089d` | no unique commits | **a fourth effort, started mid-reconciliation.** It appeared while the merge was running and gate 16 failed within the minute — which is the whole point of the gate. This row said *"at `master`'s tip"* until 2026-08-10; it is six commits behind and has been since `5a79f00` |
| `claude/swingdesk-handoff-review-e8d9f4` | `664e84a` | **yes** — branched from `master`'s tip | **the fifth effort, 2026-08-10.** Handoff verification, an audit of two external reviews, and the P0/P1 fixes that came out of it |

**Two things this table stopped being able to tell you, both fixed 2026-08-10.**

The **directory names no longer match the branches checked out in them** — `git worktree list` is the
truth, not the folder name. This directory, `swingdesk-documentation-321418`, currently holds
`claude/swingdesk-handoff-review-e8d9f4`; the one named `…-continue-1feb49` holds the council branch.
Reading a path and inferring a branch is now wrong.

And **gate 16 was excluding the tree it ran in rather than the main checkout**, so it returned
different verdicts on one commit depending on where you invoked it: green from a worktree, red from
the main checkout. Because it counted the main checkout as a sibling, and that branch is `master` —
a string this file contains many times over — the case it exempted could never fail. It was
exempting the running effort, which is the one effort a fresh session is guaranteed not to know
about. Run it anywhere now and it answers the same, and it prints each tip and merge state so a
stale row like the council one above is visible without being parsed.

**All three reconciled branches are merged and `RECONCILIATION_PLAN.md` is fully executed** — steps 1–8, of
which the last three were gate renumbering, recomputing the base strategy at measured costs, and
rebuilding this table from the merged tree. `criteria.yml` is **v1.1.0** with `k.track_a_timebox` ratified and `k.timebox_review` `met`.

## 3. The uncomfortable summary

**The machinery is real and honest. The strategy is not known to work, and what is known is mostly
negative.**

- **The base strategy is negative at measured costs, across the whole admissible universe.** PR-005
  reported **+0.028R** at 1× and **−0.123R** at 3×; both are net, because gross is never reported
  (`DR-004` consequence 1), so "before costs" is the one description that is wrong. Those two points
  give gross 0.1036R, cost 0.0757R and break-even at **1.369×** the assumption — and `DR-005`
  measures slippage at **25bp per side** against the assumed 5. Recomputed 2026-08-09
  (`DR-005`, *Consequence for PR-005*): **−0.073R at the $5 universe floor, −0.224R at $50.**
  Break-even would need an average traded price of **$1.02**; `universe.min_price` is **$5.00**.
  **No price an eligible instrument can have makes it positive.** The 1× column was never applicable.
- **The direction is settled and the level is not.** `PR-008` reached the opposite conclusion — that
  the estimators cannot resolve the spread — and that explanation was **withdrawn on 2026-08-09**
  after a calibration-free sign test refuted it. But neither effort settled the magnitude:
  Abdi-Ranaldo correlates **+0.46** with volatility and **−0.02** with liquidity, which is backwards
  for a spread, and the published literature documents exactly that bias. **`PR-010` closed this
  on 2026-08-09**: EDGE — the 2024 estimator built to fix both, and the only one that reads the
  open — reports 25.65bp against its own zero-spread floor of **41.87bp** at this universe's
  measured volatility. Two estimators agree to 0.21bp *inside their shared noise*. **The level is
  not obtainable from daily OHLC**; `PR-006`, real fills, is the only route left. Treat 25bp as
  "materially more than 5", never as a measurement of 25.
- The one positive finding (PR-002: breadth separates breakout outcomes) is erased by **1.6–2.3% of
  trades missing at −2R**, and Yahoo serves no delisted history, so that exposure can never be
  confirmed on the free tier.
- **There is no legal source of probability in this system today.** No expectation estimate exists,
  no calibrated model exists (`EXPECTATION_MODEL.md` §9c). Any probability displayed would be
  manufactured.
- **Two ratified criteria are inert.** `k.strategy_rejected` cannot fire — Track B evaluates on
  journalled trades only, and its benchmark comparison is not commensurable. See §5.
- `CHARTER.md` §4's v1 finish line is a **machinery** target and was reached 2026-08-02. Reaching v1
  and reporting no validated edge is a **success** against the ratified criteria, not a failure.

Do not write anything implying more confidence than that. `UX_COPY.md` §3 carries the standing
warning verbatim.

## 4. The plan — adopted 2026-08-08

**`ROADMAP.md` §9 is the plan of record.** It governs the roadmap's Now/Next/Later; where they
disagree, it wins.

| Phase | What it is | Exit |
|---|---|---|
| ~~1. Describe~~ | **CLOSED 2026-08-08** | `ABSENT` = 0; §3 and §53 blocked on a missing source |
| **2. Activate** ← here | **not "MVP"** — that closed at G5 on 2026-08-02 | first component `active`, status displayed |
| 3. Coverage, demand-driven | built when a strategy card needs it | every component a live card needs is `active` |
| 3′. Paper, in parallel | measures the system, not the edge | Track A's four run-measurable criteria met |
| 4. Research and calibration | costs measured first, ahead of phase 3 | a pre-registered study reports on forward data |

Two adopted adjustments change what happens next:

- **The MVP is behind us.** What looks like one from here is **activation**; §2 has the standing.
  ATR became the first `active` component on 2026-08-10.
- **Coverage is demand-driven.** "Maximum coverage" is `k.project_timebox`'s own named kill risk:
  scope drift into the 460-component catalogue. The test before implementing anything: **name the
  strategy card that consumes it.** No card → it stays `registered`, which costs nothing.

~~And one **dated decision the plan creates rather than settles**: at the start of phase 3 the
scheduling deferral is revisited.~~ **Settled early, 2026-08-09: the deferral is reversed and the
daily run is scheduled.** `a.run_completes` needs 20 consecutive trading days and Track A cannot
close without a scheduled run, so phase 3′ now runs *in parallel with* phase 2 rather than after it.

`k.track_a_timebox`'s 180-day branch — *restate the project as documentation-and-research only* — is
consequently **no longer the likely path**. Its 120-day-from-first-scheduled-run branch is now the
live one, and it starts 2026-08-10.

## 5. Next: the Track A clock is running, and phase 2 in parallel

**The daily run is scheduled and the 20-day counter starts 2026-08-10.** Nothing needs doing to keep
it going; what needs doing is *watching it*, because `a.run_completes` counts **consecutive** days
and a silent failure resets the counter without announcing itself:

```bash
schtasks /Query /TN "SwingDesk daily run" /FO LIST     # Last Result, Next Run Time
tail -40 data/daily_run.log                            # what it actually did
```

Exit 0 is a completed run. **Exit 2 is a refusal, which is a real outcome and not a failure** —
today every decision comes back `Skip [RISK]` because `risk.per_trade_pct` is `unset`, and that is
the system working. A crash is exit 3 or a missing log entry, and that is what resets the counter.

**The first scheduled run failed, and it is worth knowing how.** 2026-08-10 18:30 fired and returned
`0x800710E0` — *refused* — because the task was created with Windows' default
`No Start On Batteries`. Nothing crashed, nothing was logged, and the wrapper never ran: from the
log alone the day simply did not exist. Fixed the same evening with
`AllowStartIfOnBatteries`, `DontStopIfGoingOnBatteries` and **`StartWhenAvailable`**, the last so a
run missed to sleep or shutdown catches up instead of silently breaking a 20-day chain. Verified by
triggering it: exit 0 in ~5 minutes.

**One limitation remains and cannot be fixed without a password.** `Logon Mode: Interactive only` —
the task runs only while the user is logged on. Running otherwise needs stored credentials, which is
not something to hand to a tool. If the machine is commonly logged out at 18:30, that is the next
thing that will break the chain, and the fix is yours to make in Task Scheduler.

**How bad that is depends on `StartWhenAvailable`, and nobody here has tested it.** The expectation
is that a logon-mode miss is *late*, not *lost* — the trigger is missed at 18:30, and the task runs
at the next logon instead. If that holds, a logged-out evening costs a late run rather than a day of
`a.run_completes`, and the exposure is much smaller than the paragraph above implies. **Marked
conjecture** under `AGENTS.md` §10.4: it is Windows behaviour nobody has exercised on this machine,
and the settings state alone does not establish it. The check that would settle it is one evening —
log out before 18:30, log back in, and read `Last Run Time` against the trigger time:

```powershell
Get-ScheduledTaskInfo -TaskName "SwingDesk daily run" | Select LastRunTime, LastTaskResult, NextRunTime
```

Until someone runs it, treat a logged-out 18:30 as an unknown rather than as safe. **Verified
2026-08-10** by direct query, and these are facts rather than conjecture: `Enabled True`,
`DisallowStartIfOnBatteries False`, `StopIfGoingOnBatteries False`, `StartWhenAvailable True`,
`LastTaskResult 0`.

**A dependency fault can no longer eat a day silently.** `tools/daily_run.cmd` now runs
`tools/preflight.py` before the pipeline: it reads the runtime dependencies out of `pyproject.toml`
and exits 3 if any is missing from the interpreter's environment, so the log says which one at
18:30 instead of the run dying at the first fetch. It exists because `yfinance` was imported by the
default fetcher and declared in no dependency list — a clean install *succeeded* and was only wrong
once the network was touched. Stdlib only and it reads nothing from `swingdesk`, because it has to
work in exactly the broken environment it reports on. Four tests in `tests/test_gates.py` hold it to
the same standard as the gates: it has been seen red.

**Merging the 2026-08-10 packaging fixes requires one command, and nothing works until it is run.**
`pyproject.toml` now declares `yfinance` and a `swingdesk` console script; neither exists in an
environment installed before that. The venv is shared — `.venv` lives in the main checkout and every
worktree borrows it (§8) — so this must be run **from the main checkout**, never from a worktree,
where an editable install would silently repoint the shared environment at that worktree's `src`
and take the scheduled run with it:

```bash
cd C:/PycharmProjects/SwingDesk && .venv/Scripts/python.exe -m pip install -e ".[dev]"
```

That one command creates the `swingdesk` command, and refreshes install metadata that had gone
stale enough to omit `duckdb` — a declared dependency since 2026-08-02.

### Phase 2, and it is smaller than it looks

**Verified 2026-08-08: ATR and SMA already satisfy every requirement gate 11 imposes for `active`.**
Both carry `implements`, `verification: golden vectors` and a `spec` anchor, and neither has an unset
parameter — ATR's period is `assumed`, SMA has none of its own. `presentation/report.py` already
prints `validation` beside every observation.

So the mechanical change is two fields in `registry/components.yml`. What is *not* mechanical, and is
the actual work:

1. **Decide that `active` is warranted**, per `COMPONENT_REGISTRY_SPEC.md` §3. `active` asserts the
   component will not have to refuse — nothing more, and specifically not that it is any good.
   `Untested` is a permitted status for an `active` component; hiding it is not.
2. **Check the display obligation end to end.** The status must appear wherever the output appears,
   not only in the one report path that happens to print it.
3. **Watch what flips.** `COVERAGE_MATRIX.md`'s runtime column moves off zero for the first time, and
   gate 10 (traceability) stops passing vacuously — `CI_POLICY.md` §7 says it is unwired precisely
   because there are zero `active` components. Activating one is what makes that gate real.

`ROADMAP.md` §4 carries the rest of the ordered work as **P1–P5**; **P5, the first strategy card, is
load-bearing for phase 3** because demand-driven coverage has no meaning without a card to create the
demand.

## 6. Open — the owner's, not mine

1. **`DR-006` is proposed and unratified.** Six `risk.*` portfolio constraints, all `assumed:DR-006`.
   Unlike `DR-007` these bind a real account. Two of the six (sector, correlation) are **set and
   cannot be evaluated** — no sector source, nothing computes a correlation matrix — and §3 of that
   record says they must report `unavailable` rather than fail closed into a blanket refusal.
   `risk.per_trade_pct` is deliberately **not** set: Appendix C reserves it to the owner.
2. ~~**The daily-run schedule stays deferred.**~~ **Reversed 2026-08-09 — the run is scheduled.**
   What remains deferred is the **directory pull**, and it is the one that matters most:
   `departures()` accumulates forward only and is the sole survivorship evidence a free tier can
   produce, so every unpulled day is unrecoverable at any price. It is **one commented-out line** in
   `tools/daily_run.cmd`, on the same schedule, costing about five seconds. Left commented because
   the owner's 2026-08-09 decision was *keep it manual*; uncommenting it is a decision to reverse,
   not an oversight to fix.
3. **`UDR-004`: which regime ontology is canonical** — the specification's eight or the course's
   eleven? Only the course list has evidence behind it (`REGIME_SPEC.md`).
4. **`PR-009` is registered and blocked** — it was `PR-006` until the 2026-08-09 reconciliation moved
   it (`docs/prereg/README.md` explains which id means what, and when). Its step 1 is to persist a
   trade log by reproducing PR-005 under its recorded seed — **no reported study in this project has
   a trade log**, and Appendix J lists one among the five artefacts a strategy claim requires. If the
   reproduction does not match PR-005's aggregates, that mismatch *is* the result.

## 7. Closed by evidence — do not re-open

| | Why |
|---|---|
| Trend-definition family | PR-001 (definitions select different instruments) and PR-005 (those populations then behave the same) both refuted. `screen.trend_definition` stays `unset` |
| **The spread LEVEL from daily OHLC** | Three estimators — Corwin-Schultz 2012, Abdi-Ranaldo 2017, EDGE 2024 — cannot resolve it here. `PR-010` reports 25.65bp per side against its own 41.87bp zero-spread floor at this universe's measured volatility; Abdi-Ranaldo's 25.44bp sits under a 33.85bp floor. They agree to 0.21bp **inside their shared noise**, and neither declines with liquidity. `PR-006` — real fills — is the only route left. **A fourth estimator is the same family** |
| Paid market data | Owner decision D10, taken with the survivorship cost known |
| Tuning the current parameters | PR-005 measured the strategy flat at assumed costs and negative under stress — both net |
| New entry filters | Same family, same evidence |
| ~~Spread estimation from free daily data~~ | **Removed 2026-08-09 — this row was wrong.** It rested on PR-008's withdrawn explanation. The sign test shows the estimators do detect a spread; see `POSTMORTEM-2026-08-09.md` §2. Kept struck through because a "closed by evidence" row that quietly disappears is worse than one that was wrong |
| Order placement, automation, multi-user | `CHARTER.md` §3 non-goals — reopening needs a charter amendment |
| An AI that decides, sizes, or ranks by desirability | `CHARTER.md` A-001 and `AI_AUTHORITY_MODEL.md` §3, ratified |

## 8. Traps, and the habits that catch them

**Two traps that have cost real time:**

- **The worktree venv points at the main checkout.** `pytest` run from a worktree exercises
  `C:\PycharmProjects\SwingDesk\src`, not the worktree's, unless `PYTHONPATH` says otherwise. The
  documentation gates read files by path and are unaffected; the code gates are not. Always run gates
  with `PYTHONPATH=$PWD/src`.
- **Hand-maintained counts drift, every time.** Four have now been caught: the study verdicts
  (`5 studies, 3 refuted` in five documents), the gate total, the specification coverage summary
  (31/22 against a table saying 30/24), and a component-activation claim in
  `COMPONENT_REGISTRY_SPEC.md`. Each read as correct. **None was reachable by review** — only
  recomputation caught them, which is why gates 3f, 3g, 3ci and the gap-summary check in 3e exist.

**The habits:**

- **Verify before asserting.** When you find a stale claim, **add a gate rather than fixing the
  instance.** That rule has produced four gates and every one has since caught something.
- **`unavailable` is not `fail`.** A gap in the *system* and a fact about the *trade* are different
  claims. Collapsing them is the most damaging error this product can make.
- **An `UNSET` parameter is the design working**, not a backlog item. Components refuse rather than
  default.
- **Never hand-edit** a `verbatim` block or a generated file. Gates 2 and 3b–3ci exist to catch it.
- **No Russian in code** (`AGENTS.md` §5) — one marked exception, the course-index heading pattern,
  which is data rather than prose. Course quotations live in `docs/`, where gate 2 checks them.
- **Rollback is mostly supersede, not revert.** The stores are append-only; `CHANGE_MANAGEMENT.md`
  §3 says what can be undone and what can only be corrected forward.

## 9. Where things live

```
docs/00-charter      what this is, what done means, glossary, kill criteria
docs/01-requirements BRD, user stories, NFR, surfaces, REQ registry
docs/02-domain       the course transcribed and specified; rules, transitions, entities, allocation
docs/03-data         point-in-time, calendar, vendors, quality
docs/04-journal      audit, checklists, journal schema, evidence records
docs/05-validation   backtest protocol, walk-forward, prereg, go-live, execution, expectation, drift
docs/06-engineering  architecture, determinism, CI policy, modes, change management, knowledge graph
docs/07-ux           task flows, controlled vocabulary
docs/08-pm           roadmap (the plan of record), risk register, gap analysis, coverage matrix
docs/decisions       DR-001..DR-006 — choices that are not hypotheses
docs/prereg          PR-001/002/005/006 and their reports
registry/            parameters, components, course index, checklists, criteria
src/swingdesk/       the reference implementation — the vertical slice the specification requires
tools/               the merge gates, plus network tools that never run in CI
```

## 10. History, condensed

**2026-08-04.** Two efforts had been writing into this repo without knowing about each other. A
second track built ten numbered documents at root — Russian, "documentation only" — having never
opened `docs/`, `src/` or `registry/`. Its build plan scheduled ~10 specification sections as future
work that was already done, and its README rewrite dropped the "It does not place orders" line.

Resolved: `docs/` is canonical (owner decision). That track's work is preserved verbatim in commit
**`dee8f37`**, its genuinely new material is folded in, the duplicates are gone, and
`SPEC_GAP_ANALYSIS.md` is the real §56 analysis. It read **FULL 28 · PARTIAL 16 · ABSENT 9** that
day; §2 above has today's.

**Do not rebuild the numbered tree.** §8 of the specification forbids maintaining one logic in two
places, and for a day this repo was doing exactly that.

**2026-08-08.** Phase 1 closed. Six specification sections written (§15 rules, §16 transitions, §23
expectation, §28 execution, §31 allocation, §35 modes, §44/§45 drift and learning, §46 knowledge
graph, §7 entities, §11 terminology, §43 change management, §5 coverage matrix — generated). Four
gates added. `DR-007` ratified, `DR-006` proposed, `criteria.yml` amended to v1.1.0 and ratified.
`mode` and `from_state` landed. The master specification itself is **not in this repository**, which
is why §3 and §53 are blocked rather than written — see `ENTITY_MAP.md` §0 for what that cost.
