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
| Merge gates running | 11, from one command |
| Tests | 182 |
| Components implemented | 7 · 6 with golden vectors (25) · **0 `active`** — five blocked by an unset parameter, which is the fail-closed design working |
| Parameters | 96 — 84 `unset`, 9 `assumed`, 2 `owner`, **1 `validated`** |
| Studies | 4 registered, 4 reported — **3 refuted, 1 accepted and quantifiably fragile** |

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
| open positions are evaluated before new candidates | **ordering exists, subject does not.** There is no position store, so nothing is evaluated first because nothing is open |
| the pre-trade checklist is generated with machine-verifiable items pre-filled | **not built.** `CHECKLIST_SPEC.md` transcribes 84 items; none is generated |

Two gaps, both concrete, neither requiring a research result. **That is the whole remaining v1
scope**, and it is deliberately unglamorous.

## 3. Now

Work that is started or next, and that nothing else waits on.

| # | Item | Why now |
|---|---|---|
| ~~N1~~ | ~~Golden vectors for `breadth` and `regime`~~ | **DONE 2026-08-02.** 9 vectors added, plus a differential check against pandas and seven metamorphic relations. The vector format grew a `kind` so a cross-sectional measure and a fit/apply classifier can have vectors at all |
| N2 | **Position store + open-position evaluation** | The finish line's fifth capability. Needs a positions table, an open-position path through the pipeline before candidates, and the `Management` record from `JOURNAL_SCHEMA.md` |
| N3 | **Checklist generation** | The finish line's sixth capability. 84 transcribed items, each classified machine-verifiable or human-only; the machine ones pre-filled from the run |
| ~~N4~~ | ~~`registry/components.yml`~~ | **DONE 2026-08-02.** 465 rows, and gate 11 runs all six checks. It caught swing high and swing low sharing one function on its first run — the violation import analysis cannot see, because both imports are legal |

## 4. Next

Ready to start once Now is done. Ordered by what unblocks the most.

| # | Item | Waits on |
|---|---|---|
| X1 | **Universe path end to end** — the CLI takes a rule, not a ticker list | N4, and `DR-003` is already set |
| X2 | **`REGIME_SPEC.md`** — transcribe the 11 regimes, the regime→strategy matrix, and record that this project's classifier covers one axis of three | PR-002 is reported, so the doc can state what was measured rather than what was hoped |
| X3 | **CI gates 4, 5, 10** — ruff, mypy, traceability | nothing; gate 11 shipped with N4 |
| X4 | **`EVENT_SPEC.md`, `CHART_SPEC.md`** | nothing; they are transcription and were deferred, not blocked |
| X5 | **Tier 7 UX** — six documents, none started | the surfaces they describe do not exist yet, so they are cheap to defer and expensive to write early |

## 5. Later

Named so they are not rediscovered as ideas.

- **Web admin panel, Telegram approvals, Firebase push** (owner decisions D3/D6). G7. The CLI must
  be complete first — a second surface built on an incomplete first one duplicates the gap.
- **Canada.** Blocked on enumerating a `.TO` universe (`DR-003` gap 1). Until then every result is
  single-market and says so.
- **Share-class symbology.** `AMH$G`-style symbols fail to fetch; the exclusion is systematic
  (preferred shares and units), not random.
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

Track B is different. Four studies produced one fragile positive, on a base strategy measured as
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
