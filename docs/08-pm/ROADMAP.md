# ROADMAP

**Status:** drafting · **Tier:** 8 (project management) · **Content:** authored

**Written 2026-08-02, after the studies rather than before them.** A roadmap drafted at G0 would
have planned a trend-filter programme that the evidence has since closed. This one is built on what
was measured.

The finish line it serves is `CHARTER.md` §4, ratified 2026-08-01 and unchanged.

---

## 1. Where the project actually is

| | |
|---|---|
| Gates closed | G0 charter · G4 architecture · **G5 walking skeleton** |
| Gates open | G1 requirements · G2 transcription · G3 data · G6 catalogue · G7 surfaces |
| Merge gates running | 17, from one command |
| Tests | 253 |
| Components implemented | 7 · 6 with golden vectors (25) · **0 `active`** — five blocked by an unset parameter, which is the fail-closed design working |
| Parameters | 96 — 63 `unset`, 30 `assumed`, 2 `owner`, **1 `validated`** |
| Studies | 4 pre-registered, 3 reported — **2 refuted, 1 accepted and quantifiably fragile**; plus one post-hoc bound carrying no verdict. `PR-006` registered and blocked on a trade log |

**The one-line summary:** the machinery is real and honest; almost nothing about the strategy is
known, and what is known is mostly negative.

## 2. What the finish line still needs

`CHARTER.md` §4 names six capabilities. Measured against the code as it stands:

| Capability | State |
|---|---|
| a single command produces a dated report | **done** — `swingdesk scan` |
| every displayed number traces to a component with provenance and validation status | **done** for the components that exist; the trace is carried by `ObservationSeries`, not reconstructed |
| the whole run is reproducible from its manifest | **done** — replay is a merge gate |
| every candidate carries `Trade`/`Watch`/`Skip`/`Pause` with a reason code | **done** — asserted by test and by the journal's uncoded-refusal count |
| open positions are evaluated before new candidates | **done** — a position store, evaluated first, with the run's own step trace as the evidence |
| the pre-trade checklist is generated with machine-verifiable items pre-filled | **done** — generated per candidate from the transcription. 5 of 18 items answerable today, 8 reporting `unavailable` with the reason, 5 human |

**All six are now done** (2026-08-02). The v1 finish line as ratified on 2026-08-01 is reached.

That is a smaller claim than it sounds, and deliberately so: the finish line requires the machinery
to be honest and reproducible, not the strategy to work. §7 still stands unchanged.

## 3. Now

Work that is started or next, and that nothing else waits on.

| # | Item | Why now |
|---|---|---|
| ~~N1~~ | ~~Golden vectors for `breadth` and `regime`~~ | **DONE 2026-08-02.** 9 vectors added, plus a differential check against pandas and seven metamorphic relations. The vector format grew a `kind` so a cross-sectional measure and a fit/apply classifier can have vectors at all |
| ~~N2~~ | ~~Position store + open-position evaluation~~ | **DONE 2026-08-02.** Append-only, read as-of; the run proposes and never applies (D1, D6); the step order is recorded rather than asserted |
| ~~N3~~ | ~~Checklist generation~~ | **DONE 2026-08-02.** 84 items parsed from the transcription, Appendix E generated per candidate. 4 of 18 answerable when it landed, 5 since X1; the remaining 8 machine items report `unavailable` and name what is missing |
| ~~N4~~ | ~~`registry/components.yml`~~ | **DONE 2026-08-02.** 465 rows, and gate 11 runs all six checks. It caught swing high and swing low sharing one function on its first run — the violation import analysis cannot see, because both imports are legal |
| ~~X1~~ | ~~Universe path end to end~~ | **DONE 2026-08-03.** `scan --universe` applies the DR-003 rule. The symbol directory is now a stored, as-of-readable snapshot rather than a per-tool download, the universe is pinned in the manifest as a run input, and E02 answers. §4 has the fetch-budget consequence |
| ~~X3~~ | ~~CI gates 4, 5~~ | **DONE 2026-08-03.** ruff and `mypy --strict` both green and wired into `check_gates.py`, 14 gates. They paid for themselves immediately: a `date.today()` in the pipeline's completeness window that gate 7 could not see, an `ExitDecision` that could claim an exit with no price, and a `Fetcher` type that had drifted from every one of its call sites. **Gate 10 stays unwired** — its strongest check is "every `active` component has a test" and there are zero `active` components, so it would pass vacuously |
| ~~X5~~ | ~~Tier 7 UX~~ | **DONE 2026-08-03, as two documents rather than six.** `UX_TASK_FLOWS.md` maps Appendix T's six phases onto the code and reports **11 of 34 items served** — the `После сделки` phase is 0 of 6, and structurally so, because D1 means nothing executes and nothing comes back. `UX_COPY.md` freezes the controlled vocabulary. The other four specify a visual surface that does not exist and are deferred to G7 with the reason recorded in `docs/README.md` |
| ~~X4~~ | ~~`EVENT_SPEC.md`, `CHART_SPEC.md`~~ | **DONE 2026-08-03.** 11 quotes, gate-2 verified. EVENT_SPEC settles why E11 is blocked: M34 and M40 name 38 event types between them and carry **two** pass/fail criteria total, one per module, repeated identically on every topic — so there is no course basis for `screen.earnings_buffer_days` or for treating any catalyst differently from another. 8 of M40's 18 topics are `Untested Hypothesis` by the course's own label. CHART_SPEC records that the course's figures are synthetic teaching data with a frozen cutoff, and that **512 of the 867 "charts" are not price charts at all** |
| ~~X2~~ | ~~`REGIME_SPEC.md`~~ | **DONE 2026-08-03.** 12 quotes, gate-2 verified. **The regime→strategy matrix does not exist** — topic 451 is an `Operational Course Rule` whose entire content is one sentence, and no mapping is enumerated anywhere. Recorded as a finding rather than authored. Also states plainly that the shipped classifier covers **one axis of three**, and that the two-axis variant was measured and rejected on stability |

## 4. Next

Ready to start once Now is done. Ordered by what unblocks the most.

**The fetch budget is now the binding constraint, and it was found by building X1.** DR-003 admits
roughly a third of 13,043 eligible US symbols — about 4,300 instruments. At the free tier's
throughput a full daily refresh is over an hour, against the 45-minute budget in `NFR.md`. The rule
is fine; fetching everything it admits every day is not. So the work is tiered — a budgeted
`tools/refresh_universe.py` pass widens coverage, and the daily run reads what is stored and never
blocks on a fetch. That is also the cadence Appendix T already uses (`До недели` / `До сессии`).

The consequence is carried in the data rather than in a footnote: until coverage is complete,
`UniverseSelection.is_partial` is True and every report says the universe is a subset of the rule's
answer. **A partial universe is honest; a partial universe presented as the rule's answer would be a
survivorship filter of our own making**, which is exactly what DR-003 exists to avoid.

| # | Item | Phase | Waits on |
|---|---|---|---|
| **P1** | **Close phase 1.** §46 knowledge graph, then the five prose shortfalls — §3's 25 questions, §7's entity mapping, §11's terminology fields, §43's change taxonomy, §53's QA scorecard | 1 | nothing |
| **P2** | **First `active` component.** ATR and SMA are the candidates: ATR's period is `assumed`, SMA has no parameter of its own, and both have golden vectors. What each still needs is a `verification` and a `spec` anchor | 2 | nothing — this is authoring, not code |
| **P3** | **Measure costs.** Corwin–Schultz / Abdi–Ranaldo effective spread from daily OHLC. Pre-registered first | 4, moved ahead | a trade log is *not* needed; this is a spread estimate over bars |
| **P4** | **Revisit the scheduling deferral.** The dated decision point adjustment C creates. Paper cannot start without it, and Track A cannot close without paper | 3′ | an owner decision, at the start of phase 3 |
| **P5** | **First strategy card**, which is what makes coverage demand-driven rather than exhaustive. Until one exists there is no demand to serve | 3 | `STRATEGY_CARD_SPEC.md` is written; the card itself is not |
| X6 | **Universe coverage** — refresh passes until `is_partial` is False, then re-check DR-003's plateau against the full population rather than a 115-symbol sample | 3 | elapsed time and fetch budget, not code |

**P3 is the only research that moves ahead of its phase**, and §9 D records why: the sign of the only
result this project owns sits inside an assumed 5bps, so everything built in phase 3 inherits it.

**P5 is the load-bearing one for phase 3.** Demand-driven coverage has no meaning without a card to
create the demand, so the first card is not one item among several — it is the thing that decides
which of the 465 components get built at all.

## 5. Later

Named so they are not rediscovered as ideas.

- **Web admin panel, Telegram approvals, Firebase push** (owner decisions D3/D6). G7. The CLI must
  be complete first — a second surface built on an incomplete first one duplicates the gap.
- **Canada.** Blocked on enumerating a `.TO` universe (`DR-003` gap 1). Until then every result is
  single-market and says so.
- **A second exit model.** `PR-005` tested two of the course's four exit slots. Its sharpest
  limitation, and the cheapest genuinely new question available.
- **`PR-001b`** — sweep the ADX threshold rather than pick one.

## 6. Not planned, and why

Recording these stops them being re-proposed.

| | |
|---|---|
| **Paid market data** | Owner decision D10, 2026-08-02, taken with the price known. Consequence: survivorship exposure is never confirmable, and `criteria.yml` `b.survivorship_caveat` applies to every Track B result forever |
| **Another trend-definition study** | The family is closed by PR-001 and PR-005. Reopening needs a *different* trigger or exit model, which is a different question |
| **Order placement, automation, multi-user** | `CHARTER.md` §3 non-goals. Reopening requires a charter amendment, not a roadmap entry |
| **Optimising the current strategy's parameters** | PR-005 measured it at +0.028R per trade ungated and −0.123R under cost stress. Tuning a flat strategy is how a project spends a year discovering it had no edge |

## 7. The honest risk to this plan

**Track A is reachable and Track B may not be.**

The v1 finish line is a machinery target and needs no profitable strategy — that was the point of
ratifying it that way. Everything in §2, §3 and §4 lands it.

Track B is different. Three studies produced one fragile positive, on a base strategy measured as
flat before costs and negative after stress. Nothing in this roadmap fixes that, because a roadmap
cannot. `SUCCESS_AND_KILL_CRITERIA.md` `k.programme_exhausted` exists for the case where the
validation programme runs out of hypotheses without one surviving, and that outcome is live.

Stating it here means the project can reach v1, report honestly that it has no validated edge, and
that will be a **successful outcome against the ratified criteria** rather than a failure to be
argued about later.

## 8. Open items

- [ ] Sequence N2 and N3 against `k.project_timebox` (2 months from G0 to G5 — **met**, G5 closed
      2026-08-02). The next timebox has not been set and should be, in the same form.
- [ ] Whether `REGIME_SPEC.md` should be written before or after `registry/components.yml`. Writing
      it first risks specifying components the registry cannot express.

### From the parallel track's unresolved register (2026-08-04)

Five `UDR-*` entries arrived with the master-ТЗ track. Three were already answered here, which is
itself the pattern that made the reconciliation necessary. Dispositioned:

| | Question | Disposition |
|---|---|---|
| `UDR-001` | Lessons incomplete, so domain extraction cannot finish | **OPEN and genuinely new.** The 116-PDF course *is* fully extracted — 1379 topics, 465 components, three studies run. This entry refers to a **forthcoming book** the owner is still writing. That is new information and it changes nothing structural: the catalogues fill from it when it arrives |
| `UDR-002` | Which graph database for the Knowledge Graph projection | **OPEN, owner input needed.** Low urgency — §46 ranks last of nine absent sections, and the logical schema does not depend on the engine |
| `UDR-003` | Scope of the execution and broker layer | **CLOSED.** Owner decision D1, `CHARTER.md` — the system never places orders. §29 is `DEFERRED` with its ontology slot fixed |
| `UDR-004` | Canonical regime ontology | **OPEN, and sharper than recorded.** The ТЗ suggests eight regimes; the course names **eleven** (`REGIME_SPEC.md` §2) and they are a vocabulary, not a partition. PR-002 validated a classifier on one axis of three. The real question is whether the ТЗ list or the course list is canonical — and only the course list has evidence behind it |
| `UDR-005` | Should the reference vertical slice come before mass documentation? | **CLOSED — it already did.** G5 closed 2026-08-02, walking skeleton green, replay a merge gate. The ТЗ's own §50 ordering was followed before the ТЗ arrived |

## 9. The phase plan — adopted 2026-08-08

**This section governs §3, §4 and §5.** Where they disagree with it, it wins.

The owner set the shape on 2026-08-08 — describe everything, then MVP, then maximum coverage coded
step by step, then paper trading and research — and adopted four adjustments to it the same day. The
adopted plan is therefore:

| Phase | What it is | Exit |
|---|---|---|
| **1. Describe** | no research, no implementation | ТЗ `ABSENT` = 0; the prose shortfalls closed |
| **2. Activate** | *(not "MVP" — that closed at G5 on 2026-08-02)* | first component `active`, status displayed |
| **3. Coverage, demand-driven** | a component is built when a strategy card needs it | every component a live card needs is `active` |
| **3′. Paper, in parallel** | measures the system, not the edge | Track A's four run-measurable criteria met |
| **4. Research and calibration** | costs measured first | a pre-registered study reports on forward data |

The four adjustments are recorded below with the evidence that prompted each, because the reasoning
is what makes the plan re-decidable later. One of them (C) creates a dated decision point rather than
settling a question, and that is stated where it arises.

### What the plan gets right, and it is not the obvious thing

**Research last is normally a mistake, and here it is defensible.** Calibrating before the machinery
is trustworthy is how a project fits noise, and this one has the evidence: three of four studies
refuted, and the one positive is erased by a survivorship exposure that free data cannot close. The
instinct — do not tune until the thing being tuned can be trusted — matches what PR-005 found rather
than fighting it. §7's honest risk still stands, and this ordering does not make it worse.

### A. Phase 2 already happened

**G5 closed 2026-08-02.** `CHARTER.md` §4's six capabilities are all done, replay is a merge gate,
253 tests and 18 gates run from one command. The MVP is behind us, not ahead.

What *is* ahead and looks like an MVP is **activation**: 465 components are registered, 7 are
implemented and **0 are `active`**. `COVERAGE_MATRIX.md` §3 names that gap as the number to watch —
implemented-but-not-runtime is the population where code exists that nothing may yet rely on.

**Adopted.** Phase 2 is **activation**. Its exit is the first component reaching `active` with its
parameters valued, its verification present and its status displayed wherever its output appears.

### B. "Maximum coverage" is this project's own named kill risk

`k.project_timebox`'s note, ratified 2026-08-01: *the real risk is scope drift into the
460-component catalogue rather than time.* A phase that codes all 465 components is that risk written
out as a plan.

The activation gate exists precisely so this does not happen — components sit at `registered`
indefinitely at **no cost**, and reaching `active` is deliberate (`COMPONENT_REGISTRY_SPEC.md` §3).

**Adopted.** Coverage is **demand-driven**: a component is implemented when a strategy card needs it,
not because the catalogue has a row for it. Building 465 components for a strategy with no validated
edge produces 465 pieces of unvalidated machinery and a much larger surface to keep honest.

The practical test, so this does not erode: **before implementing a component, name the strategy card
that consumes it.** If there is none, it stays `registered` — which costs nothing and is what the
activation gate is for.

### C. Paper trading is not a late phase — it is how Track A closes

`a.run_completes` requires **20 consecutive trading days** of the run completing. That clock cannot be
compressed by throughput, and it **does not need a strategy**: a forward test measures misses, delays,
alerts and journal quality — the four things `VALIDATION_PROGRAM.md` §2 says a backtest structurally
cannot see. Three further Track A criteria need taken trades.

**Adopted, and it creates a decision point rather than settling one.** Paper runs in parallel from
the start of phase 3.

It cannot run without a scheduled daily run, and scheduling is deferred (below). So adopting C means:
**at the start of phase 3, the scheduling deferral is revisited.** Either it is reversed and paper
begins, or it stands and Track A remains unreachable — but the choice is made on a date the plan
names, rather than by drift.

### D. One study belongs before maximum coverage

The base strategy measured **+0.028R before costs and −0.123R at 3× costs**, so the sign of the only
result this project owns sits inside an assumed 5bps. Corwin–Schultz (2012) and Abdi–Ranaldo (2017)
estimate effective spread from daily OHLC — **no new data, no vendor, no new fetch**.

**Adopted.** Costs are measured before the machinery is dimensioned on top of them. This is the one
piece of research that moves ahead of phase 3 rather than waiting for phase 4 — it is a single study,
it needs no new data, and everything built in phase 3 inherits whatever the number turns out to be.

### The consequence the plan must carry

**Scheduling the daily run was deferred on 2026-08-08, and under this phasing it lands in phase 3 or
4.** Two things follow, and the second is structural:

1. `departures()` accumulates forward only, so the survivorship record for the whole of phases 1–2
   does not exist and cannot be reconstructed at any price.
2. **`a.run_completes` cannot be met without a scheduled run.** If the deferral becomes permanent,
   Track A never closes — and Track A is the entire question of whether the system is sound. The
   ratified `k.track_a_timebox` now fires on exactly that: 180 days from 2026-08-08 with no run ever
   scheduled, and its action is to restate the project as documentation-and-research only.

That is not an argument to reverse the deferral. It is the plan's own arithmetic: **adjustment C is
available only if the schedule exists**, and if it never does, phase 4 is unreachable and the
project's honest end state is the one `k.track_a_timebox` already names.

### Mapped onto the gates that already exist

Expressed in the existing ladder rather than a second vocabulary — ТЗ §8 forbids maintaining one
logic in two places, and this repository has already paid for that once.

| Phase | Existing gate | Exit condition |
|---|---|---|
| 1 Describe | G1, G2, G3 | ТЗ `ABSENT` = 0; the 24 `PARTIAL` shortfalls that are prose are closed |
| ~~2 MVP~~ | ~~G5~~ | **closed 2026-08-02** |
| 2′ Activate | — | first component `active`, with its status displayed |
| 3 Coverage, demand-driven | G6 | every component a live strategy card needs is `active` |
| 3′ Paper, in parallel | — | Track A's four run-measurable criteria met |
| 4 Research and calibration | Track B | a pre-registered study reports on forward data |

### Phase 1's remaining scope, enumerated

Because "describe everything" has a measurable end and it is close. `SPEC_GAP_ANALYSIS.md`:
**FULL 29 · PARTIAL 24 · ABSENT 1.**

Documentation-only work left: **§46** (knowledge graph), and the prose subset of the shortfalls —
§3 (no document walks all 25 questions), §7 (the ТЗ's 22-entity table is not mapped one-to-one),
§11 (`GLOSSARY.md` has no `synonyms_discouraged` / `ambiguous_terms`), §43 (no change-type taxonomy
or rollback policy), §53 (no QA scorecard against the ТЗ's 13 counters).

The remaining shortfalls are **code**, not prose — §8's generated schemas, §12's six missing time
types, §39's end-to-end scenarios — and they belong in phase 3 regardless of how phase 1 ends.
