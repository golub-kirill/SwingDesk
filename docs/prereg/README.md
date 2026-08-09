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
| `PR-007` | Is the assumed 5bp slippage an understatement of the spread this universe pays? | **reported — INCONCLUSIVE** | — |

`PR-007` was the first study of an **input** rather than a rule, and it came back **inconclusive**.
Both OHLC spread estimators produced negative estimates on more than half the sample, and the
exploratory diagnostic shows why: they track volatility, not liquidity, because a sub-basis-point
spread sits roughly three orders of magnitude below the noise floor of daily bars. Costs remain
`assumed`. `PR-006` — real fills in a forward test — is now the only route to a measured cost, and
that is a measured claim rather than an assumed one. See `results/PR-007-report.md`.

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
