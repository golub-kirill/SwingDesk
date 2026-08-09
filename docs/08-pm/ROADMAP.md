# ROADMAP

**Status:** drafting · **Tier:** 8 (project management) · **Content:** authored

**Written 2026-08-02, after four studies rather than before them.** A roadmap drafted at G0 would
have planned a trend-filter programme that the evidence has since closed. This one is built on what
was measured.

The finish line it serves is `CHARTER.md` §4, ratified 2026-08-01 and unchanged.

---

## 1. Where the project actually is

| | |
|---|---|
| Gates closed | G0 charter · G4 architecture · **G5 walking skeleton** |
| Gates open | G1 requirements · G2 transcription · G3 data · G6 catalogue · G7 surfaces |
| Merge gates running | 14, from one command |
| Tests | 260 |
| Components implemented | 7 · 6 with golden vectors (25) · **0 `active`** — five blocked by an unset parameter, which is the fail-closed design working |
| Parameters | 96 — 83 `unset`, 9 `assumed`, 3 `owner`, **1 `validated`** |
| Studies | 5 registered, 4 reported — **2 refuted, 1 accepted and quantifiably fragile** |

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

| # | Item | Waits on |
|---|---|---|
| X6 | **Universe coverage** — run the refresh passes until `is_partial` is False, then re-check DR-003's plateau against the full population rather than a 115-symbol sample | nothing; it is elapsed time and fetch budget, not code |

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

Track B is different. Four reported studies produced one fragile positive, on a base strategy
measured as flat at 1x costs and negative under stress — both figures net, because gross is never
reported (`DR-004` consequence 1). `DR-005` then measured slippage at 25bp per side against the
assumed 5, which makes the negative column the operative one. Nothing in this roadmap fixes that,
because a roadmap cannot. `SUCCESS_AND_KILL_CRITERIA.md` `k.programme_exhausted` exists for the case where the
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
| `UDR-001` | Lessons incomplete, so domain extraction cannot finish | **OPEN and genuinely new.** The 116-PDF course *is* fully extracted — 1379 topics, 465 components, four studies run. This entry refers to a **forthcoming book** the owner is still writing. That is new information and it changes nothing structural: the catalogues fill from it when it arrives |
| `UDR-002` | Which graph database for the Knowledge Graph projection | **OPEN, owner input needed.** Low urgency — §46 ranks last of nine absent sections, and the logical schema does not depend on the engine |
| `UDR-003` | Scope of the execution and broker layer | **CLOSED.** Owner decision D1, `CHARTER.md` — the system never places orders. §29 is `DEFERRED` with its ontology slot fixed |
| `UDR-004` | Canonical regime ontology | **OPEN, and sharper than recorded.** The ТЗ suggests eight regimes; the course names **eleven** (`REGIME_SPEC.md` §2) and they are a vocabulary, not a partition. PR-002 validated a classifier on one axis of three. The real question is whether the ТЗ list or the course list is canonical — and only the course list has evidence behind it |
| `UDR-005` | Should the reference vertical slice come before mass documentation? | **CLOSED — it already did.** G5 closed 2026-08-02, walking skeleton green, replay a merge gate. The ТЗ's own §50 ordering was followed before the ТЗ arrived |
