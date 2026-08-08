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
| `PR-006` | Does measured live slippage match the modelled figure? | not written | a forward test |
| `PR-007` | Does the base strategy have positive expectancy net of **measured** costs? | **registered** | a re-fetch — the window is 10 years, the store holds 2 |

`PR-003` and `PR-004` are named in `DR-001` and `DR-002` as the studies that would overturn them.
`PR-006` is named in `DR-004` and `PR-007` in `DR-005`, the same way. `PR-005` is required by
PR-001's result: the definitions are not interchangeable, so choosing one needs evidence about what
its population does, not just that it differs. They are listed here unwritten so the debt is visible
rather than implied.

**`PR-006` was reserved on 2026-08-02 and went unlisted here until 2026-08-05.** Reserving an id in
a decision record and not recording it in the index is how the debt stops being visible, which is
the one thing this table exists to prevent. Nothing catches it: `verify_docs.py` fails on a decision
record whose *file* is missing from the decisions index, but an id reserved **by reference only**,
with no file behind it, leaves nothing for a gate to find. Worth fixing if a third one appears.

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
