# Pre-registrations

One file per study, `PR-NNN-<slug>.md`, written and committed **before** the study runs. The template
and the rules are in `../05-validation/PREREG_TEMPLATE.md`.

A registered study that has not run is the normal state. Registration is cheap; it is the thing that
has to happen first, not the thing that has to happen last.

## Index

| ID | Question | Status | Blocked on |
|---|---|---|---|
| `PR-001` | Does the trend definition change which population is selected, or only its size? | registered | fetch + run (A-D only; US only) |
| `PR-001b` | Does definition E's ADX threshold change the answer, across its whole range? | not written | PR-001 |
| `PR-002` | Does a regime classifier improve decisions, or only partition them? | registered | harness + PR-001 |
| `PR-003` | Is √252 annualisation wrong enough to matter for this return series? | not written | a daily return series |
| `PR-004` | Do the process-score weights change any ranking? | not written | ~100 journalled trades |

`PR-003` and `PR-004` are named in `DR-001` and `DR-002` as the studies that would overturn them.
They are listed here unwritten so the debt is visible rather than implied.

## Status values

`registered` — committed, not yet run · `running` · `reported` · `abandoned`

An abandoned pre-registration stays in the repository. A study abandoned after seeing partial data is
exactly what vanishes from a dishonest record.
