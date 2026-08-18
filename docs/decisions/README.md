# Decision records

**Status:** drafting · **Tier:** cross-cutting

Four documents already require a "decision record" and none defined it (`contracts/README.md` §7,
`ADR-0003` §3, `EXIT_MODEL_SPEC.md`, `TEST_STRATEGY.md` §3). This is that definition.

---

## 1. What a decision record is for

A **choice that is not a hypothesis.**

Some things this project must fix cannot be tested, because they are conventions rather than claims.
Whether a Sharpe ratio annualises by √252 or √12 is not true or false — it is a convention, and two
studies that pick differently are not comparable. Choosing one is a decision; the record is what
makes it auditable.

The distinction that matters:

| | Instrument | Produces | Provenance it earns |
|---|---|---|---|
| a convention or definition | **decision record** (`DR-NNN`) | a fixed choice, usable immediately | `assumed:DR-NNN` or `assumed:<citation>` |
| a claim that could be false | **pre-registration** (`PR-NNN`, `../prereg/`) | a study | `validated:<evidence-id>` |

Both are written **before** the value is used. That is the whole discipline: a DR is not a
retrospective justification of a number someone already picked.

A choice frequently needs both — a DR to pick a starting value so the system can run, and a PR to
register the study that would confirm or refute it. `screen.trend_definition` is the archetype: you
need *a* definition to have a strategy at all, and whether that definition is any good is a separate,
testable question.

## 2. Format

One file per decision, `DR-NNN-<slug>.md`:

```
# DR-NNN: <the choice, in one line>

date:      YYYY-MM-DD
status:    proposed | accepted | superseded by DR-NNN
parameters: <ids in registry/parameters.yml this sets>
components: <component ids whose version this moves, if any>

## Decision
What was chosen. Precisely enough that two people implement it identically.

## Why this one
The reasoning, and the citation if there is one.

## Alternatives rejected
Each with the reason. An alternatives section with one entry is a decision that was never made.

## What would overturn this
The observation or study that would change it. Names the PR if one is registered.

## Consequences
What now has to be true elsewhere.
```

## 3. Rules

1. **Written before use.** The commit that sets the parameter carries the DR.
2. **Never edited after `accepted`.** Superseded by a new DR that names the old one. Same rule as the
   journal and the pre-registrations, for the same reason.
3. **A DR that sets a parameter must name it**, and the parameter's provenance must point back —
   `assumed:DR-007`. `tools/verify_parameters.py` accepts that form because a decision record is a
   citation.
4. **A DR that changes component behaviour bumps the component version** and regenerates its golden
   vectors in the same commit (`COMPONENT_REGISTRY_SPEC.md` §6, `CI_POLICY.md` §3).
5. **`assumed` is where a DR leaves a parameter — never `validated`.** Only evidence from a
   pre-registered study moves a value to `validated`, and a decision record is not evidence. This is
   the line that keeps a considered guess from acquiring the authority of a measurement.

## 4. Not an ADR

`docs/adr/` holds architecture decisions: storage engine, schema language, calendar source. Those are
structural and rarely revisited. A DR is about a **value or a definition** the domain needs, and it
is expected to be superseded when a study says so. Different lifetimes, different directories.

## 5. Index

| ID | Decision | Sets | Status |
|---|---|---|---|
| `DR-001` | Sharpe ratio convention | `stats.sharpe_convention` | proposed |
| `DR-002` | Process score scale | `stats.process_score_scale`, `stats.quality_grade_scale` | proposed |
| `DR-003` | A-tier liquidity rule | `universe.min_price`, `universe.min_adtv_20d`, `universe.min_bar_history` | proposed |
| `DR-004` | Cost model | `costs.commission_model`, `costs.slippage_model` | proposed — slippage superseded by `DR-005` |
| `DR-005` | Slippage measured from daily OHLC | `costs.slippage_model` | proposed |
| `DR-006` | Portfolio risk block | six `risk.*` constraints | **proposed — binds a real account** |
| `DR-007` | Validation programme thresholds | fourteen of fifteen `validation.*` | **accepted — ratified 2026-08-08** |
| `DR-008` | Daily US directory collection under local control | operational policy; no trading parameter | **accepted — ratified 2026-08-10** |
| `DR-009` | The owner's broker charges no commission, and the cost model never knew | account-structure choice only — its parameter moved to `DR-010` (§5, correction 2026-08-13) | proposed |
| `DR-010` | Sizing costs are price-aware and currency-aware, not one flat constant | `risk.costs_bp_usd`, `risk.costs_bp_cad`, `risk.costs_floor_usd`, `risk.costs_floor_cad` | **accepted — ratified 2026-08-13** |
| `DR-011` | The run notice is a local desktop notification — not Firebase, not Telegram | none — a surface, not a measured component. Also corrects `PRODUCT_SURFACES` §3.4's self-contradicting example | proposed — mechanism chosen by the owner 2026-08-16 |
| `DR-012` | The protective stop is 2.0 × ATR(14) and the maximum holding period is 20 sessions | `exit.atr_stop_multiple`, `exit.max_holding_period` | **accepted — ratified 2026-08-17** |
| `DR-013` | A non-critical proposal expires after 3 days; a critical one never expires and never proceeds unanswered | `management.proposal_expiry_days` | **accepted — ruled 2026-08-17** |
| `DR-015` | Two sessions is too stale to decide on; a failed fetch retries 3x30s then once more at 19:30 | `data.freshness_window` | **accepted — ruled 2026-08-18** |
| `DR-014` | No owner capital in the observable state of the project — paper only; Canada deferred with a re-entry condition | none directly — changes the STANDING of `DR-006`'s six `risk.*` parameters and withdraws `PR-006`'s precondition | **accepted — ruled 2026-08-17** |

`DR-007` is the largest of these by a distance: fifteen parameters at once, four of them ratifying
what a reported study already used and eight genuinely authored. It exists because a ratified kill
criterion referenced a parameter nobody had set, which made it a gate that could not fail.

**One of its fifteen did not survive the 2026-08-09 reconciliation.** `DR-007` §3.7 authored
`validation.max_allowable_drawdown` as −15R and called it the weakest of the set; the owner had
already set the same parameter directly to 20% of equity on 2026-08-05, on a branch `DR-007` could
not see. An `owner` value outranks an `assumed:DR-007` one on this registry's own provenance ladder,
so the owner's stands and §3.7 is superseded. Nothing else in the record changes.


Measurements backing a decision live in `measurements/`, committed alongside the record. A threshold
whose evidence cannot be re-read is a threshold that will be re-argued from memory.
