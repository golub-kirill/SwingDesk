# BRD — business requirements

**Status:** drafting · **Tier:** 1 (requirements) · **Content:** authored, constrained by tier 0 and 2

---

## 1. Who this serves

One person: the owner, trading their own account. Single install, single user
(`CONSTRAINTS.md` §7). Every requirement below exists to serve that user's own process, not a
market of users.

## 2. Capabilities in scope

Derived from the course's lifecycle, not invented. Each maps to the stage it serves.

| # | Capability | Lifecycle stage |
|---|---|---|
| C1 | Maintain point-in-time market and reference data for a defined universe | Source Facts |
| C2 | Build the tradable universe by a liquidity rule, recomputed daily | Context |
| C3 | Compute derived observations — indicators, structure, levels, volatility, relative strength | Derived Observations |
| C4 | Classify market regime for USA and Canada separately | Context |
| C5 | Screen the universe into ranked candidates with recorded reasons | Candidate |
| C6 | Evaluate setups and triggers against strategy cards | Setup, Trigger |
| C7 | Compute stop, size and portfolio fit | Risk |
| C8 | Assign `Trade`/`Watch`/`Skip`/`Pause` with a reason code to every candidate | Entry |
| C9 | Generate the pre-trade checklist with machine-verifiable items pre-filled | Entry |
| C10 | Evaluate exits on open positions before any new candidate | Management, Exit |
| C11 | Propose open-position actions for human approval and record the outcome | Management |
| C12 | Maintain an immutable, versioned journal with a full audit trail | Review |
| C13 | Compute trade statistics net of costs, broken down on the required axes | Review |
| C14 | Render the charts a decision requires (`1Y`/`3M`/`30D`, `30m` on execution) | all |
| C15 | Backtest and walk-forward a strategy card under point-in-time constraints | Validation |
| C16 | Report, alert and notify across CLI, web, Telegram and push | all |

## 3. Out of scope

The charter's eight non-goals, unchanged: no order placement, no automation, no advice to others,
no multi-user, no data redistribution, no intraday strategy engine, no benchmark-beating as the
definition of success, no price prediction. See `CHARTER.md` §3.

## 4. Non-negotiable business rules

These override any feature. A change request that conflicts with one of these is refused, not
negotiated.

| # | Rule | Source |
|---|---|---|
| BR-1 | **The human decides.** The system prepares and records; it never acts. | D1, `CHARTER.md` §3 |
| BR-2 | **Fail closed.** Missing, stale or conflicting data yields a coded refusal, never a guess. | `FAIL_CLOSED_POLICY.md` |
| BR-3 | **Risk limits override signal.** A signal never overrides a risk gate. | M76 standard |
| BR-4 | **Critical gates are non-compensatory.** No score, and no number of weak positives, clears one. | `FAIL_CLOSED_POLICY.md` §3 |
| BR-5 | **Stop before size.** Sizing that reverses this ordering is rejected at write time. | `RISK_SPEC.md` §3 |
| BR-6 | **Stops never widen.** `WIDE_STOP` is `Critical`. | `CODES.md` |
| BR-7 | **Records are immutable.** The original plan is never rewritten; corrections create versions. | `JOURNAL_SCHEMA.md` §4 |
| BR-8 | **Nothing displays as more validated than it is.** Validation status and assumed parameters are visible wherever they affected a number. | `PARAMETER_REGISTRY.md` §5 |
| BR-9 | **USA and Canada are never merged** without separate indexes, calendars and currency handling. | M30/M31/M33 fail-closed |
| BR-10 | **Every candidate leaves with a next action.** No candidate ends a run without a decision and a reason. | M32/M33 operational standard |
| BR-11 | **Every result is net of costs** — commission, spread, slippage, borrow, FX. | Appendix D |
| BR-12 | **Reproducibility.** A re-run from a manifest matches its control run. | fail-closed row 3 |

## 5. What "done" means

`registry/criteria.yml` v1.0.0, frozen 2026-08-02. Track A is the system's own bar; Track B belongs
to individual strategy cards. See `SUCCESS_AND_KILL_CRITERIA.md`.

The v1 finish line is in `CHARTER.md` §4 and is ratified.

## 6. Priorities

When two requirements conflict, resolve in this order:

1. **Correctness of the record** — an inaccurate journal is worse than no journal.
2. **Refusing rather than guessing** — a missing decision beats a fabricated one.
3. **Reproducibility** — a result that cannot be reproduced is not a result.
4. **Coverage** — more components registered.
5. **Convenience** — fewer keystrokes, prettier output.

This ordering is deliberate and unusual: convenience is last, and coverage is fourth. The previous
project optimised coverage and convenience first and paid for it in results it could not trust.

## 7. Assumptions

- Free-tier data, with survivorship bias and no point-in-time support from any vendor. Measured, not
  assumed — `ADR-0001` conditions 2 and 6.
- ~40 h/week of owner time; 2 months to the walking skeleton.
- Account equity $10,000 USD, configurable; Canadian positions carry a currency effect.
- Every setup imported from the course is `Untested` and stays that way until evidence says
  otherwise.
