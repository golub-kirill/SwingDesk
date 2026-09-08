# SwingDesk

**Decision-support software for swing trading Canadian and US equities — and a working record of
trying to find out whether its own strategy has an edge.**

It computes the charts, indicators, market structure, setups, risk figures, journal and statistics
defined by a 116-file swing-trading course, records every decision with an audit trail, and submits
to a paper venue used as a research instrument. Every number it acts on is authored, dated, and
carries a status saying how much it is believed.

The interesting part is the second half of that sentence. **This repository is as much a record of
disciplined negative results as it is a trading system**, and it is built so that a comfortable
conclusion is hard to reach and easy to catch.

---

## At a glance

| | |
|---|---|
| **Operational loop** | closed end to end — scan, propose, approve, apply, reconcile against the venue |
| **Strategy** | **not known to work.** No parameter has ever reached `validated` |
| **Live evidence** | a paper account, armed since 2026-09-02 |
| **Merge gates** | one command, every commit — `python tools/check_gates.py`. The inventory is `docs/06-engineering/CI_POLICY.md` §1; the count is `HANDOFF.md` §2 |
| **Search spent** | every configuration ever evaluated is counted against `b.deflated_sharpe` — `python tools/trial_budget.py` prints the total, the hurdle, and the counting rule for each |
| **Real money** | none, ever. `CHARTER` A-001 |

```bash
python tools/check_gates.py     # everything below is enforced by this
```

---

## What this is, and what it is not

**No broker integration that can move money, and no real order is ever placed.** No live venue, no
automated execution with capital behind it. The owner makes every trading decision that involves
money; this system prepares and records them. No advice to third parties, no multi-user service.

**What exists is a paper account used as a RESEARCH INSTRUMENT** — owner framing, 2026-09-01, and
the distinction is the point rather than a softening. The purpose is to put this system's machinery
in front of a real venue's fills, partial fills, rejects and halts instead of a fixture, so that
what it does can be studied. It is a measuring instrument that happens to speak a broker's protocol,
not a route to market.

`CHARTER` A-002 permits it, scoped exactly that narrowly: on an account with no owner capital the
system may submit without per-order approval, because the reason the human-only rule exists —
irreversible risk — does not apply there. On anything that can move money, A-001 stands unchanged.

The boundary between the two is a committed host allowlist enforced by a merge gate, because
**a brokerage account object carries no field saying whether it is paper or live** — which host was
called is the only difference there is. `DR-026`, `DR-027` and `DR-028` carry the reasoning.

---

## Quick start

```bash
python -m venv .venv && .venv/Scripts/pip install -e .
python tools/check_gates.py                                   # the whole gate suite; this is the contract
python -m swingdesk.presentation.cli scan AAPL MSFT --data data
```

`scan` fetches, computes, decides, writes a report and journals every decision. It places nothing:
submission needs `--submit` **and** a kill-switch file the owner creates outside this repository.

Reading the state of things:

```bash
python tools/forward_record.py --data data    # the live paper record: switch, book, what was refused
python tools/trial_budget.py                  # what the search has cost and what the next trial costs
```

---

## The discipline, which is the point

Every threshold in this system is **authored**, because the course supplies none — see
[Source of truth](#source-of-truth). So the project's central problem is not *how do we compute
this* but *how do we avoid believing a number we made up*. The answer is a set of rules that have
each cost something real:

| rule | what it stops |
|---|---|
| **A threshold needs a pre-registration, not a guess** | a value chosen after seeing the result |
| **An amendment after seeing data downgrades the study to exploratory** | a hypothesis edited to fit |
| **A study says the smallest effect it could DETECT, before it spends a trial** | a null from an instrument too blunt to see anything |
| **Every configuration evaluated is counted** | a search that finds a winner by looking often enough |
| **A green test is not evidence — mutate it** | a fixture that passes whatever the code does |
| **A count has one owner, and it is generated** | two documents disagreeing quietly |

**These are not aspirations.** `docs/05-validation/PREREG_TEMPLATE.md` carries the rules,
`tools/check_gates.py` enforces what a machine can, and `docs/08-pm/EVIDENCE_SUMMARY.md` carries
what has actually been measured — including the results that went against the person measuring
them.

### What the evidence says right now

**Nothing here has been shown to work, and the most recent studies say so with more precision than
the earlier ones.**

- `PR-015` (2026-09-07) put five long-only selection signals through a four-position book at a
  twenty-session hold, with two holdouts. **No signal produced a positive excess separable from
  zero** — and neither did the ~130-name decile each selects from, measured gross, before any cost.
  Two signals reliably *lost*.
- `PR-014` published an `ACCEPT` on 2026-09-06 and **withdrew it the next day**. Its cost model
  charged gross turnover — the whole book sold and rebought at every rebalance — where a book that
  re-picks a name holds it. The error was 2.69× at twenty sessions and 1.02× at a year, so it taxed
  short holding periods and let long ones through, on a study whose whole subject was the holding
  period.
- **Nothing has ever reached `validated`**, and the search that produced that is counted rather
  than estimated: `tools/trial_budget.py` prints the total, the hurdle it implies, and the rule each
  entry was counted by.

The forward paper record is the one kind of evidence here that does **not** raise the
multiple-testing hurdle, because nothing was searched to produce it. It has been running since
2026-09-02.

---

## Source of truth

The requirements source is a 116-PDF swing-trading course plus its verification manifest. Measured
by full text extraction — not assumed:

| | |
|---|---|
| Topics | **1379**, each with a stable component ID (`M26-T0393-v5.0`) |
| Claim types | Definition 916 · Operational Course Rule 173 · Untested Hypothesis 124 · Derived Observation 121 · Inference 45 |
| Computable components | **~460** (everything that is not a Definition) |
| Validation status in the source | `Not Applicable` 1209 · `Untested` 170 · **tested: 0** |
| Numeric thresholds the course supplies | **effectively none** — across 276 audited topic definitions, the count containing a parameter not already in their own title is 0 |
| Arithmetic the course supplies | Appendix C (11 risk formulas) and Appendix D (11 statistics formulas) only |
| Schema the course supplies | Appendix G — a 12-entity ER model with column lists |

**The consequence, stated plainly:** the course is a complete *governance and taxonomy*
specification and an empty *parameter* specification. Every threshold in this system is authored,
not inherited — which is why every parameter carries a provenance and a status, and why no
component is ever displayed as more validated than it is.

**And a course rule is not evidence.** `AGENTS.md` §16 settles what a sentence in the course
licenses: it names something worth looking at, and it never stands as the reason a threshold has
its value. Published work supplies method, calibration and known limitations; only a pre-registered
study against this universe moves a parameter to `validated`.

---

## Scope

- **Markets** — Canada + US equities and ETFs. **Never merged**: separate calendars, indexes and
  currencies. The paper venue serves only one of them, which the reconciliation reports as *out of
  scope* rather than as a missing position.
- **Timeframes** — context `1Y` / `3M` → decision `1D` → confirmation `1H` → execution `30m`. Lower
  frames refine a setup; they never invent one. Each resolution is fetched and stored independently:
  deriving `1H` from `30m` would cap hourly history at 60 trading days when ~725 are available
  (`ADR-0001`).
- **Storage** — local databases for bars, the directory, positions, classifications and the journal.
  Nothing leaves the machine except the two requests below.
- **Outbound network** — the daily symbol directory (`DR-008`) and the paper broker (`ADR-0005`).
  Both have their hosts, timeouts, byte caps and retry budgets in committed, merge-gated policy
  files rather than in code, so changing one is a commit a reviewer sees.
- **Notification** — a local desktop notice (`DR-011`). Firebase is specified in
  `PRODUCT_SURFACES` §3.4 and unbuilt; the record explains why local is stronger on §3.4's own
  terms.
- **Surfaces** — CLI and reports, built. A web admin panel and Telegram remain specified and
  unbuilt.

---

## The paper venue, and the nine things that stop it

Submission is **stopped by default** and every guard is independent — none can compensate for
another, which is `FAIL_CLOSED_POLICY.md` §3 applied to the one surface here that acts on the world.

**The boundary — may this system write here at all?**

1. **One allowlisted host**, with the live venue named as forbidden and compared as a hostname. This
   is the whole paper/live boundary, and gate 39 fails the build on a second entry.
2. **A kill switch that is a file the owner creates**, outside this repository. Absent, unreadable,
   or missing its marker all mean stopped. A switch that defaults to on is not a switch, and one
   that fails open is an inversion `DR-025` records this project paying for once already.
3. **`access.write_enabled` in the committed policy** — one line, one commit, one reviewer.
4. **A single chokepoint in the code.** Every write goes through one function that consults the
   other three first, and the gate reads the syntax tree to prove no second path exists.

**The book — how many, against what, how far down, still bounded?**

5. **The ratified caps, applied across one run's own output** (`DR-027` §10). The screen picks who
   is *eligible* — normally about a hundred names; `risk.max_concurrent_positions` (4),
   `risk.max_open_risk` (4R) and `risk.max_sector_risk` (2R) pick who is *taken*. Without it a
   single evening would have sent **114 orders and 103.5R**, measured.
6. **The venue is asked what it already holds, before anything is added** (`DR-027` §11). Any symbol
   the account is exposed to that this system's book does not carry stops submission with the
   course's `TECH` — *"pause new entries"*. An order this system itself sent is the exception
   (`DR-032`), identified by an id in our own journal and never by the shape of one.
7. **The book and the venue must describe the same positions** (`DR-035`) — the same question the
   other way round. A stop leg firing overnight closes a position at the venue, and if nothing
   records it the caps count it for ever and the machine stops trading after four stop-outs without
   a word. `DR-031` and `DR-038` are what keep 6 and 7 from being permanent halts: an entry records
   itself from the fill, and an exit closes itself from one.
8. **`k.drawdown_pause`, the only ratified `live` criterion** (`DR-034`). Peak-to-trough drawdown of
   account equity including open positions marked to market, against an owner-set 20 percent. A
   breach pauses new entries; a drawdown that cannot be *measured* pauses them too.
9. **Every open position's stop is standing at the venue** (`DR-036`). A bracket's legs expire with
   the entry's session while the position lives twenty of them. The caps are denominated in
   `entry − stop`; a book whose stops are not at the venue bounds nothing. `DR-037` restores a
   missing one and `DR-041` adopts a tighter one the venue is already holding.

The keys are the owner's and live only in the environment (`SECURITY.md` §2.1). This repository is
public and holds none.

**Operating it day to day** — arming, disarming, reading the evening's log, and the one message that
needs a person — is `docs/runbooks/README.md` §7.

---

## Repository map

```
docs/        the document set, by tier — start at docs/README.md
  02-domain/     strategy cards, specs, the fail-closed policy
  05-validation/ the pre-registration template and its rules
  06-engineering/CI_POLICY.md — the gate inventory and what each has caught
  08-pm/         EVIDENCE_SUMMARY.md — what is actually known
  decisions/     DR-nnn, one ruling each, with the reasoning that produced it
  prereg/        studies: the plan, then the result, never the other order
registry/    generated data and committed policy: components, parameters, network limits
golden/      frozen fixtures: component vectors and replay cases
src/         bounded contexts, one package each
tools/       generators, verification scripts, research runners, the gate runner
tests/
```

**Three files carry the state of the project**: `HANDOFF.md` (§2 generated — counts, branches,
runtime), `TODO.md` (every open item, and only open items), and
`docs/08-pm/EVIDENCE_SUMMARY.md` (what has been measured).

---

## Conventions

**English throughout** — documents, code, and UI. The course's controlled vocabulary (`STAGE`,
`LAYER`, `CLAIM TYPE`, `VALIDATION`, `Trade/Watch/Skip/Pause`, the skip and error codes) is used
verbatim and never translated or paraphrased.

This governs artifacts, not conversation. `AGENTS.md` §13 records an owner instruction about the
language an agent replies in, which changes nothing that lands in the repository. Where the two
appear to disagree, this rule wins for anything committed.

**`AGENTS.md` is the working agreement** — how to verify a claim, when to force an answer, what
counts as evidence, and a list of traps that have each cost real time.

---

## Every command and every flag

<!-- BEGIN GENERATED COMMANDS - build_commands.py writes this, do not edit -->

**Generated by `tools/build_commands.py` and checked by gate 45.** Do not edit between the
markers: a hand-kept list of flags is wrong within the week, which is the whole subject of
`AGENTS.md` §10.5. An argument whose name or help text is computed rather than written as a
literal appears with an empty description rather than being dropped.

### The application — 8 command(s)

#### `swingdesk broker`

read the paper account and reconcile it against the book. Reads only - it has no way to place, amend or cancel anything (D1/BR-1, DR-026)

| argument | what it does |
|---|---|
| `--data` | the store directory: bars, positions, journal and the arming switch all live here |
| `--as-of` | ISO instant this observation is recorded as of; defaults to now |
| `--fills` | also list the venue's executions |
| `--since` | ISO instant; with --fills, the earliest execution to ask for |

#### `swingdesk close-position`

record an exit that already happened at the broker (D1: this never places the order). The mirror of open-position

| argument | what it does |
|---|---|
| `position_id` | e.g. POS-AIS-2026-09-03; `swingdesk broker` names it |
| `--exit` **(required)** | fill price, per share, as the venue reports it |
| `--reason` **(required)** | why this position is closed in the book. Required, and recorded: a close with no stated reason is the unlogged judgment Production Rules 3.8 exists to prevent |
| `--commission` | as charged. Defaults to 0, which is DR-009's measured structure |
| `--shares` | defaults to the whole position. A smaller number is a PARTIAL_EXIT and is refused here rather than silently recorded as a close |
| `--closed-on` | ISO date the exit happened; defaults to today. Kept apart from --as-of on purpose: one is the event, the other is when we learned |
| `--reason-code` | the course's code for why, when one applies |
| `--data` | the store directory: bars, positions, journal and the arming switch all live here |
| `--as-of` | ISO instant this is being recorded as of; defaults to now |

#### `swingdesk open-position`

record a position already opened at the broker (D1: this never places the order)

| argument | what it does |
|---|---|
| `ticker` | e.g. AAPL or CNQ.TO |
| `--entry` **(required)** | fill price, per share |
| `--shares` **(required)** | shares actually filled at the venue, not the size that was planned |
| `--stop` **(required)** | initial stop, per share |
| `--opened-on` | ISO date the fill happened; defaults to today |
| `--costs-per-share` | override the DR-010 round-trip cost estimate with the real one, once a broker confirmation names it |
| `--strategy` |  (default: unspecified) |
| `--acknowledge-over-cap` | record this position even though it breaches a ratified portfolio cap (DR-006 8.3). The reason is written to the store, not just printed - an override nobody can audit is not an override |
| `--position-id` | override the default POS-<instrument id>-<opened-on> identity |
| `--data` | the store directory: bars, positions, journal and the arming switch all live here |
| `--as-of` | ISO instant this is being recorded as of; defaults to now |

#### `swingdesk pending`

proposals on open positions awaiting your answer (US-010)

| argument | what it does |
|---|---|
| `--data` | the store directory: bars, positions, journal and the arming switch all live here |
| `--as-of` | ISO instant to judge staleness at (DR-013); defaults to now |

#### `swingdesk record-fill`

report what the broker actually did for an approved action (US-011)

| argument | what it does |
|---|---|
| `position_id` | e.g. POS-AAPL-2026-08-10; `swingdesk pending` lists them |
| `sequence` | the approved action this settles |
| `--price` **(required)** | the actual fill price |
| `--shares` **(required)** | shares actually transacted |
| `--commission` **(required)** | as charged, not the modelled estimate |
| `--filled-on` | ISO date; defaults to today |
| `--data` | the store directory: bars, positions, journal and the arming switch all live here |
| `--as-of` | ISO instant this is recorded at; defaults to now |

#### `swingdesk respond`

answer a proposal. D1: this records a decision, it never places an order

| argument | what it does |
|---|---|
| `position_id` | e.g. POS-AAPL-2026-08-10 |
| `sequence` | the proposal's number, from `pending` |
| `--reason` **(required)** | why. Required - Production Rules 3.8: an approval with no stated reason is an unlogged judgment |
| `--data` | the store directory: bars, positions, journal and the arming switch all live here |
| `--as-of` | ISO instant this answer is recorded at; defaults to now |

#### `swingdesk scan`

run the daily pipeline and produce a report

| argument | what it does |
|---|---|
| `tickers` | e.g. AAPL CNQ.TO; omit and pass --universe |
| `--universe` | take candidates from the DR-003 liquidity rule instead of a list |
| `--limit` | cap the universe by dollar volume. A cap is a RANKING, not the rule, and the report says so |
| `--data` | the store directory: bars, positions, journal and the arming switch all live here |
| `--lookback` | how much history to fetch per instrument. A year is the shortest span the indicators need AND what makes a restated close visible (DR-016 10.4) (default: 1y) |
| `--as-of` | ISO instant; pins the clock so the run is reproducible |
| `--report-dir` | where the run's report file is written; defaults to <data>/reports |
| `--submit` | submit this run's Trade decisions to the paper venue as bracket orders (CHARTER A-002, DR-027). Does nothing unless the kill switch file has been armed - it is stopped by default and the refusal says which guard stopped it |
| `--no-notify` | skip the local desktop notice (DR-011). The report is written either way; this only suppresses the pop-up |

#### `swingdesk sync-fills`

record positions for entries THIS system placed that have since filled (DR-031). Reads the venue, writes the book, places no order

| argument | what it does |
|---|---|
| `--data` | the store directory: bars, positions, journal and the arming switch all live here |
| `--as-of` | ISO instant this is recorded at; defaults to now |
| `--dry-run` | say what would be recorded and record nothing |

### The tools — 66 script(s), of which 13 are things you type

#### Operator tools — 13

Run these. Everything else below either runs itself or ran once.

| command | what it does | arguments |
|---|---|---|
| `python tools/blocked_claims.py` | The open items in `TODO.md` that assert something is blocked, and therefore need testing. | `--list` · `--todo` |
| `python tools/classify_departures.py` | Classify the symbols that left the directory: delisting, rename, or still listed. | `--data` · `--out` |
| `python tools/fetch_directory.py` | Download the NASDAQ Trader symbol directory and record it as one dated pull. | `--data` · `--scheduled` · `--emergency-repull` · `--reason` |
| `python tools/forward_record.py` | What the live paper record actually contains, so watching it costs nobody an afternoon. | `--data` |
| `python tools/refresh_classifications.py` | Fetch sector classifications for instruments the store already holds bars for. | `--data` · `--budget` · `--symbols` · `--universe` |
| `python tools/refresh_universe.py` | Fetch bars for eligible symbols, oldest-first, up to a budget. | `--data` · `--budget` · `--period` · `--pause` · `--symbols-from` |
| `python tools/remove_unclosed_bars.py` | Remove bars that were captured before their own session closed. Owner-ruled, 2026-08-18. | `--apply` · `--data` |
| `python tools/retry_needed.py` | Is a later pass worth running tonight? Asked of the journal, not assumed. | `--data` · `--as-of` |
| `python tools/sample_liquidity.py` | Measure the dollar-volume distribution across a seeded random sample of US listings. | `--sample` · `--seed` · `--window` · `--out` |
| `python tools/trial_budget.py` | What the programme has spent against `b.deflated_sharpe`, and what the next trial costs. | `--budget` |
| `python tools/vendor_integrity.py` | Every bar the vendor served that arithmetic forbids, across the whole run log. | `--log` · `--top` |
| `python tools/verify_reproducible.py` | `a.reproducible`, measured against the real universe instead of three synthetic instruments. | `--data` · `--limit` |
| `python tools/verify_submission_guards.py` | Run every guard a submission runs, in its order, against the LIVE state. Sends nothing. | `--data` · `--as-of` |

#### Generators — 8

Each WRITES a generated block that a gate then checks. Run one after changing what it derives from, never to keep a document tidy.

| command | what it does | arguments |
|---|---|---|
| `python tools/build_checklists.py` | Generate registry/checklists.yml by parsing the verbatim blocks in CHECKLIST_SPEC.md. | `--check-only` |
| `python tools/build_commands.py` | Every command and every flag this project has, generated from the code that defines them. | `--check-only` |
| `python tools/build_components.py` | Generate registry/components.yml from registry/course_index.yml, preserving authored fields. | `--check-only` |
| `python tools/build_course_index.py` | Build registry/course_index.yml from the course PDFs and their verification manifest. | `--course-root` · `--out` · `--check-only` |
| `python tools/build_coverage.py` | Generate docs/08-pm/COVERAGE_MATRIX.md from the registries. | `--check-only` |
| `python tools/build_frd.py` | Generate docs/01-requirements/FRD.md from registry/course_index.yml. | `--check-only` |
| `python tools/build_lock.py` | Generate `requirements-lock.txt` - the transitive closure of what this project declares. | `--out` · `--check-only` |
| `python tools/build_state.py` | Gate 24: `HANDOFF.md` section 2's state block, generated rather than typed. | `--check-only` |

#### Gate implementations — 5

Invoked by `python tools/check_gates.py`, not singly. Listed so a failing gate can be re-run alone to read its full output.

| command | what it does | arguments |
|---|---|---|
| `python tools/golden.py` | Golden vector gate (CI_POLICY gate 8, TEST_STRATEGY 3). | — |
| `python tools/replay.py` | Determinism replay gate (CI_POLICY gate 9, DETERMINISM_SPEC 7). | `--record` |
| `python tools/verify_components.py` | Enforce the component-registry contract — COMPONENT_REGISTRY_SPEC §7. | — |
| `python tools/verify_parameters.py` | Enforce the parameter-registry contract. | `--registry` |
| `python tools/verify_transcription.py` | Verify that every `verbatim` claim in the documents still matches the course. | `--course-root` · `--docs` |

#### Evidence-bound research runners — 40

Each is bound to a committed result in `docs/prereg/results/` or `docs/decisions/measurements/` and reproduces it. They ran once, on a date. Nobody types these; they exist so a number can be re-derived.

| command | what it does | arguments |
|---|---|---|
| `python tools/attribute_pr014_flip.py` | Which of the two changes flipped `PR-014`'s verdict - the cost correction or the backfill. | `--result` · `--control` · `--published` |
| `python tools/measure_banding.py` | Does a buy/hold band pay for itself here? The one cost mitigation this project has not tried. | `--data` · `--rebalance` · `--out` |
| `python tools/measure_benchmark.py` | Which index does relative strength measure AGAINST - and can the answer change a ranking at all? | `--data` · `--out` |
| `python tools/measure_benchmark_fit.py` | Which index is the honest passive alternative to this universe? `rs.benchmark` is `assumed`. | `--data` · `--out` |
| `python tools/measure_correlation_cap.py` | Calibrate the correlation cap: what it would have refused, and what that would have cost. | `--data` · `--out` |
| `python tools/measure_decile_persistence.py` | How much of the selected book survives to the next rebalance, and what that does to its cost. | `--data` · `--as-of` · `--out` |
| `python tools/measure_drawdown.py` | Report the drawdown `k.drawdown_pause` triggers on, so the criterion can be evaluated at all. | `--data` |
| `python tools/measure_execution_time.py` | Does moving the trade off the open survive the gross it gives up? `DR-040` §6, run. | `--data` · `--sample` · `--seed` · `--hold` · `--out` |
| `python tools/measure_exit_surface.py` | Expectancy over the stop x target grid, NET of costs. `DR-029` §5's lever 1, priced. | `--data` · `--out` · `--limit` |
| `python tools/measure_fill_convention.py` | The backtest fills at the next open. The live path rests a limit at the prior close. Same trade? | `--data` · `--hold` · `--out` |
| `python tools/measure_gap_cost.py` | What a stop-out actually costs, in R, on the universe this system now trades. | `--data` · `--out` · `--limit` |
| `python tools/measure_latency.py` | `NFR.md` §3's latency budgets, measured — because until 2026-08-24 nothing measured any of them. | `--data` · `--limit` |
| `python tools/measure_liquidity_floor.py` | Recompute DR-003's liquidity plateau over the stored population instead of a 115-name sample. | `--data` · `--min-price` · `--min-history` · `--out` |
| `python tools/measure_long_only_horizon.py` | The one significant signal this project has found is LONG-SHORT. The system is LONG-ONLY. | `--data` · `--out` |
| `python tools/measure_momentum_horizon.py` | Does the cross-sectional momentum spread depend on the HOLDING HORIZON, in this store? | `--data` · `--out` |
| `python tools/measure_pivots.py` | What `pivot.left` and `pivot.right` actually cost, measured on stored bars. | `--data` · `--limit` · `--min-bars` · `--out` |
| `python tools/measure_quoted_spread.py` | What the admitted universe actually costs to cross, from the venue's own NBBO. | `--data` · `--sample` · `--seed` · `--years` · `--against` · `--out` |
| `python tools/measure_revisions.py` | What the vendor actually rewrites, per field, and where a threshold could cut. | `--data` · `--out` |
| `python tools/measure_sector_cap.py` | Calibrate `risk.max_sector_risk` against the only trade log this project holds. | `--classifications` · `--data` · `--out` · `--wide` · `--refusals` |
| `python tools/measure_sector_relative.py` | Sector-relative strength: the other way out of the identity `DR-018` found. | `--data` · `--out` |
| `python tools/measure_short_leg.py` | How much of the ONE significant result survives a short leg you could actually borrow? | `--data` · `--as-of` · `--out` |
| `python tools/measure_spread.py` | Measure the effective spread across the stored universe, to inform DR-005. | `--data` · `--limit` · `--min-pairs` · `--out` |
| `python tools/measure_study_drift.py` | How far has the store moved under each REPORTED study since it ran? | `--data` · `--results` |
| `python tools/measure_target_reachability.py` | Which R target is REACHABLE inside the holding period this project actually runs? | `--data` · `--out` · `--limit` |
| `python tools/probe_alpaca_delisted.py` | Does Alpaca serve the PRICE PATH of a delisted equity? Asked because nobody had asked. | `--sample` |
| `python tools/probe_canada.py` | Can the Canadian universe be enumerated? Asked of TMX, because the claim had hardened. | `--full` |
| `python tools/probe_events.py` | Is there a free source for the pre-trade event calendar? Asked of the source, not of our code. | `--days` · `--data` · `--as-of` |
| `python tools/probe_paper_order.py --symbol --limit --stop --target` | Place ONE order at the paper venue, deliberately, to prove the write path works end to end. | `--symbol` **(required)** · `--shares` · `--limit` **(required)** · `--stop` **(required)** · `--target` **(required)** · `--data` |
| `python tools/probe_sector_benchmarks.py` | Is there a benchmark series per sector, and does the vendor itself confirm the pairing? | `--data` |
| `python tools/run_pr001.py` | Run PR-001: does the trend definition change which population is selected? | `--sample` · `--seed` · `--period` · `--min-bars` · `--out` |
| `python tools/run_pr002.py` | Run PR-002: does a regime label carry decision-relevant information, or only relabel outcomes? | `--sample` · `--seed` · `--period` · `--min-bars` · `--out` |
| `python tools/run_pr005.py` | Run PR-005: do the trend definitions' populations behave differently, net of costs? | `--sample` · `--seed` · `--period` · `--min-bars` · `--out` |
| `python tools/run_pr005_replay.py` | PR-005, replayed from the recorded sample - to emit the trade log the original never wrote. | `--write` · `--accept-drift` · `--data` |
| `python tools/run_pr008.py` | Run PR-008: is the assumed 5bp slippage an understatement of the spread this universe pays? | `--store` · `--out` · `--limit` |
| `python tools/run_pr011.py` | PR-011's runner: does a 2 x ATR stop cost about 1R, on names whose ATR is a large share of price? | `--data` · `--write` · `--limit` |
| `python tools/run_pr012.py` | PR-012: does a cross-sectional ranking beat plain momentum on a capacity-constrained book? | `--as-of` · `--reproduce` · `--data` · `--write` · `--verify-sample` |
| `python tools/run_pr013.py` | PR-013: does relative strength separate forward returns at all, measured on names not on a book? | `--data` · `--write` |
| `python tools/run_pr014.py` | `PR-014`: at what holding period does the RATIFIED selection rule earn a net excess? | `--data` · `--as-of` · `--out` |
| `python tools/run_pr015.py` | `PR-015`: at a twenty-session hold, does ANY long-only selection signal earn a net excess? | `--data` · `--as-of` · `--out` · `--report` |
| `python tools/run_pr016.py` | `PR-016` — the outcome distribution of the RATIFIED exit, over a decade, in and out of sample. | `--data` · `--as-of` · `--from` · `--to` · `--out` · `--report` |

<!-- END GENERATED COMMANDS -->
