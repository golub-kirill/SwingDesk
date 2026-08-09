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
| `PR-002` | Does a regime classifier improve decisions, or only partition them? | **reported — ACCEPT** | — |
| `PR-003` | Is √252 annualisation wrong enough to matter for this return series? | not written | a daily return series |
| `PR-004` | Do the process-score weights change any ranking? | not written | ~100 journalled trades |
| `PR-006` | Does measured live slippage match the modelled 5bp? | not written | a forward test — id reserved by `DR-004` |
| `PR-007` | Does the base strategy survive measured rather than assumed costs? | registered on `claude/…-1feb49`, **unmerged** | the reconciliation |
| `PR-008` | Is the assumed 5bp slippage an understatement of the spread this universe pays? | **reported — INCONCLUSIVE**, then corrected | — |

**`PR-008` was registered as `PR-007`.** Two branches used that id for different studies without
knowing about each other. `RECONCILIATION_PLAN.md` D-R4 awards a contested id to the earliest commit
timestamp, so the `1feb49` study (2026-08-08) keeps it and this one (2026-08-09) moved. **A `PR-007`
citation written before 2026-08-09 means the effective-spread study; written after, it means the
base-strategy one.** Both files carry the note and the git history is unedited.

`PR-008` was the first study of an **input** rather than a rule. Its registered decision rule
returned **inconclusive** — both estimators produced negative estimates on more than half the
sample, against a 25% threshold fixed before the run — and that verdict stands. **The explanation it
first gave was wrong and is withdrawn:** a calibration-free sign test shows the real bars do carry a
spread the estimator detects (19.1% clamped against 45.5% for spreadless synthetic at matched
volatility). Costs on `master` remain `assumed`; `DR-005` on the unmerged branch measures them at
25bp per side and is right about the direction. See `results/PR-008-report.md` §"Correction".

`PR-003` and `PR-004` are named in `DR-001` and `DR-002` as the studies that would overturn them.
`PR-005` is required by PR-001's result: the definitions are not interchangeable, so choosing one
needs evidence about what its population does, not just that it differs. They are listed here
unwritten so the debt is visible rather than implied.

Results live in `results/`, one JSON of record plus a written report.

**PR-002 is the first hypothesis this project has failed to refute.** Breadth separates breakout
outcomes out of sample, under cost stress and under a stricter null than the one registered — and a
survivorship confound could produce the same result with no real effect present. Read
`results/PR-002-report.md` before using `regime.classifier_rule`.

**The trend-definition family is closed.** PR-001 found the definitions select different
instruments; PR-005 found those different instruments then do the same thing. Two refuted
hypotheses, both pre-registered, and `screen.trend_definition` stays `unset` as a result. See
`results/PR-001-report.md` and `results/PR-005-report.md`.

## Status values

`registered` — committed, not yet run · `running` · `reported` · `abandoned`

An abandoned pre-registration stays in the repository. A study abandoned after seeing partial data is
exactly what vanishes from a dishonest record.
