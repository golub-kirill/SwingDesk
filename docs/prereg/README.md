# Pre-registrations

One file per study, `PR-NNN-<slug>.md`, written and committed **before** the study runs. The template
and the rules are in `../05-validation/PREREG_TEMPLATE.md`.

A registered study that has not run is the normal state. Registration is cheap; it is the thing that
has to happen first, not the thing that has to happen last.

## Index

| ID | Question | Status | Blocked on |
|---|---|---|---|
| `PR-001` | Does the trend definition change which population is selected, or only its size? | **reported — REJECT** | — |
| `PR-001b` | Does definition E's ADX threshold change the answer, across its whole range? | not written | — |
| `PR-005` | Do the trend definitions' populations behave differently, net of costs? | **reported — REJECT** | — |
| `PR-002` | Does a regime classifier improve decisions, or only partition them? | **reported — INCONCLUSIVE**, corrected 2026-08-16 (was `ACCEPT`) | — |
| `PR-003` | Is √252 annualisation wrong enough to matter for this return series? | not written | a daily return series |
| `PR-004` | Do the process-score weights change any ranking? | not written | ~100 journalled trades |
| `PR-006` | Does measured live slippage match the modelled figure? | not written | a forward test — id reserved by `DR-004`, 2026-08-02 |
| `PR-007` | Does the base strategy have positive expectancy net of **measured** costs? | **registered** | — (re-fetch done 2026-08-13, all 68 instruments; see its own §10) |
| `PR-008` | Is the assumed 5bp slippage an understatement of the spread this universe pays? | **reported — INCONCLUSIVE**, then corrected | — |
| `PR-009` | Is a −15R drawdown limit distinguishable from ordinary sequence luck? | **registered**, and its subject moved — see its §10 first amendment, 2026-08-25: the live threshold is 20 percent of equity and has never been −15R | ~~a trade log — none exists~~ **it exists** (`results/PR-005-trades.csv`, 2026-08-16). Blocked instead on that log no longer reproducing (`TODO.md` §5) and on the research suspension |
| `PR-010` | Does EDGE resolve the spread level Corwin-Schultz and Abdi-Ranaldo could not? | **reported — REJECT** | — |
| `PR-011` | Does a 2 × ATR stop behave as the risk model assumes, on names whose ATR is a large fraction of their price? | **reported — `reject`** 2026-09-04, and the direction is the REVERSE of the one predicted: overshoot falls monotonically as volatility rises, −0.0747R between the extreme bands with an interval excluding zero. The sample rule was MET | — |
| `PR-011b` | Should whole instrument CLASSES whose stops are unenforceable — bond and foreign-market ETFs — be screened out? | not written | — **exploratory in advance** when written: the class evidence in `TODO.md` §5 includes a sign flip seen on the fitted data, so no class study judged on expectancy can be confirmatory. `PR-011`'s appendix carries the constraint |
| `PR-012` | Does a cross-sectional ranking beat plain momentum on a capacity-constrained book? | **reported — REFUSED** 2026-08-24, the minimum sample is not met on two of three arms | `CARD-001`; the capacity cap caps the sample, and both caps are ratified |
| `PR-013` | Does relative strength separate forward returns **at all**, measured on names rather than on a four-position book? | **reported — `inconclusive`** 2026-08-24, and the verdict understates it: **all six GROSS intervals include zero**, so the ordering does not separate forward returns before costs are considered at all. **Exploratory by declaration** (§0b) | The sample rule was MET — 142 holdout dates against a minimum of 100 — which is what `PR-012` could not reach. `CARD-001`'s inputs stay `unset` |
| `PR-014` | At what holding period, if any, does the ratified selection rule earn a net excess that excludes zero - and is the shortest such period longer than the twenty sessions `exit.max_holding_period` now assumes? | **registered** 2026-09-06, not yet run | **The horizon itself has never been tested**: `exit.max_holding_period` is 20, `assumed:DR-012`. Every prior measurement of this family fixed a holding period and asked about the signal, and every one used NON-OVERLAPPING windows - which is why 126 sessions yields seventeen observations and nothing can be resolved there. This registers the standard overlapping-portfolio construction and a moving-block bootstrap to match, plus a primary/holdout split whose whole job is to stop the sweep picking its own maximum. 12 trials |

**`PR-011`'s question narrowed when it was written, 2026-09-04, and the half that was cut is
`PR-011b`.** The id was reserved on 2026-08-22 for *"should instrument classes that cannot hold a
stop be screened out"*. Writing it exposed that the two halves are not the same study: the ATR-vs-price
half has no prior fitted on it and is confirmatory, while the CLASS half is contaminated — `TODO.md`
§5 records a sign flip in mean net R observed on the fitted data, which `PREREG_TEMPLATE.md` rule 3
makes exploratory for whoever writes it. Splitting them is what keeps the clean half clean; a
citation of `PR-011` written before this date means the wider question.

**Three ids collided on 2026-08-09 and several studies moved.** Three efforts registered studies without
seeing each other. `RECONCILIATION_PLAN.md` D-R4 awards a contested id to the earliest commit
timestamp, so:

- `PR-007` stayed with the base-strategy study (2026-08-08); the effective-spread study became
  `PR-008`. Both ask about costs, from opposite directions.
- `PR-006` stayed **reserved** for live slippage — `DR-004` claimed it on 2026-08-02, before any file
  existed — so the drawdown study became `PR-009`.

That second one is the case this index predicted two paragraphs down and asked someone to fix "if a
third one appears". A third appeared. **A `PR-006` or `PR-007` citation written before 2026-08-09
may mean a different study than the same string written after.** Git history is unedited throughout,
because a registration commit is what proves a hypothesis predated its run.

**`PR-009` is blocked on something the project did not know it lacked.** No reported study here
persisted a trade log, and `BACKTEST_PROTOCOL.md` §3 lists one as the third of the five artefacts the
course requires for a strategy claim. The results are honest; their supporting detail is not
reconstructible. So its step 1 is to reproduce PR-005 under its recorded constants and persist the
log — and if the reproduction does not match the reported aggregates, that mismatch is the result,
reported as `inconclusive` rather than buried.


`PR-003` and `PR-004` are named in `DR-001` and `DR-002` as the studies that would overturn them.
`PR-006` is named in `DR-004` and `PR-007` in `DR-005`, the same way. `PR-005` is required by
PR-001's result: the definitions are not interchangeable, so choosing one needs evidence about what
its population does, not just that it differs. They are listed here unwritten so the debt is visible
rather than implied.

**`PR-006` was reserved on 2026-08-02 and went unlisted here until 2026-08-05.** Reserving an id in
a decision record and not recording it in the index is how the debt stops being visible, which is
the one thing this table exists to prevent. ~~Nothing catches it: `verify_docs.py` fails on a decision
record whose *file* is missing from the decisions index, but an id reserved **by reference only**,
with no file behind it, leaves nothing for a gate to find. Worth fixing if a third one appears.~~

**A third appeared, and gate 29 (`tools/verify_prereg_ids.py`) now catches all three shapes**, 2026-08-24:
a study document missing from this index, an id reserved by reference anywhere in `docs/` and not
listed here, and two **unmerged** branches numbering different studies the same. That last one is
`AGENTS.md` §10.2 as a check rather than a habit — `POSTMORTEM-2026-08-09.md` root cause A is two
efforts whose trees were each internally consistent. Merged branches are excluded deliberately:
this repository's two real collisions — a second `PR-006` and a second `PR-007` — are both on merged
branches, so the numbering was reconciled and the old filenames are correct statements about a commit.

**The spread level is closed by evidence.** Three estimators — Corwin-Schultz (2012),
Abdi-Ranaldo (2017) and EDGE (2024, built to fix both) — cannot resolve it on this universe.
`PR-010` reports a median of 25.65bp per side against its own zero-spread floor of 41.87bp, and
Abdi-Ranaldo's 25.44bp sits under a 33.85bp floor. The two agree to 0.21bp *inside their shared
noise*, which is what common bias looks like. `PR-006` — real fills — is the only route left, and
that is now measured rather than assumed.

Results live in `results/`, one JSON of record plus a written report.

**PR-002 is the first hypothesis this project has failed to refute — on one market.** Breadth
separates breakout outcomes out of sample, under cost stress and under a stricter null than the one
registered — and a survivorship confound could produce the same result with no real effect present.

**Its verdict was corrected from `ACCEPT` to `INCONCLUSIVE` on 2026-08-16.** §6 permitted `accept`
only where the effect held in both countries independently, and the third amendment — written before
any data was seen — had already assigned a single-market result to the inconclusive branch. The
runner implemented the percentile thresholds with no country condition and emitted `accept` anyway.
The measurements are unchanged; the label was wrong. `regime.classifier_rule` moved to
`assumed:PR-002` and **this project now has zero `validated` parameters**. Read
`results/PR-002-report.md` — including its Correction section — before using it.

**The trend-definition family is closed.** PR-001 found the definitions select different
instruments; PR-005 found those different instruments then do the same thing. Three refuted
hypotheses, both pre-registered, and `screen.trend_definition` stays `unset` as a result. See
`results/PR-001-report.md` and `results/PR-005-report.md`.

## Status values

`registered` — committed, not yet run · `running` · `reported` · `abandoned`

An abandoned pre-registration stays in the repository. A study abandoned after seeing partial data is
exactly what vanishes from a dishonest record.
