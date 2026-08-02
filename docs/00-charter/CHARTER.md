# CHARTER

**Status:** drafting — §4 finish line **RATIFIED by the owner 2026-08-01**
**Tier:** 0 (charter) · **Amendments:** dated entries appended to §7, never edits in place

---

## 1. Purpose

**SwingDesk computes the charts, indicators, market structure, setups, risk figures, journal and
statistics defined by the owner's swing-trading course, and records every decision with an audit
trail that can be reproduced from its inputs.**

It exists because the previous system was built before its goals, limits and algorithm were frozen,
and never converged. This one freezes them first.

## 2. What it is

A single-user decision-support tool for swing trading Canadian and US equities and ETFs on daily
bars, with intraday refinement. It prepares decisions and records them. **A human makes every
trading decision.**

The course is the requirements source. Where the course is silent — and it is silent on every
numeric threshold — this system supplies an authored value that carries its provenance, or it
refuses to decide. It never guesses.

## 3. Non-goals

Explicit, and each with its reason. A non-goal is not a "later"; reopening one requires an amendment.

| Non-goal | Why |
|---|---|
| **Placing orders** | Owner decision D1. Removes the largest irreversible-risk surface entirely. Orders are *recorded*, never sent. |
| **Automated trading of any kind** | The course requires documented human judgment at named points (§3.8). An autonomous path would violate its own governance model. |
| **Advice to anyone but the owner** | Single-user by design; no recommendations to third parties, no signals service. |
| **Becoming a multi-user product or service** | Yahoo's data terms state personal use only (`ADR-0001` condition 1). Growing beyond one user invalidates the data source, not just the licence. |
| **Redistributing market data** | Same constraint, and it is a legal one rather than a design preference. |
| **An intraday strategy engine** | The course is explicit: `30m — только исполнение валидного дневного setup`. Intraday refines; it never originates a setup. |
| **Beating a benchmark as the definition of success** | Deliberately excluded here and deferred to `SUCCESS_AND_KILL_CRITERIA.md`. The previous project discovered its edge was ≈benchmark *after* being built; the criterion has to be set before, by the owner, not assumed by the builder. |
| **Predicting price** | Every setup in the course is classified `Untested Hypothesis`, and the system inherits that status rather than improving on it. |

## 4. The v1 finish line — RATIFIED 2026-08-01

Stated as a demonstrable capability, so that "done" is observable rather than argued:

> **v1 is done when, for a defined universe of Canadian and US equities and ETFs, a single command
> produces a dated report in which every displayed number traces to a registered component with a
> recorded parameter provenance and validation status; open positions are evaluated before new
> candidates; every candidate carries a `Trade`/`Watch`/`Skip`/`Pause` decision with a reason code;
> the pre-trade checklist is generated with its machine-verifiable items pre-filled; and the whole
> run is reproducible from its manifest.**

Note what this deliberately does **not** require: that any setup be profitable, validated, or even
parametrised. Those are the *next* programme, governed by `VALIDATION_PROGRAM.md`. v1 finishes when
the machinery is honest and reproducible — a target that is reachable in months and cannot be
argued about.

**Ratified by the owner, 2026-08-01.** The roadmap is built on this; changing it now requires an
amendment in §7.

## 5. What must be true throughout

Five properties, each traceable to a course rule, each enforced somewhere rather than hoped for:

1. **Fail-closed decisions.** Missing, stale or conflicting data produces a coded refusal, never a
   guess. → `FAIL_CLOSED_POLICY.md`
2. **Nothing displayed as more validated than it is.** Every component shows its validation status;
   every assumed parameter is visible wherever it affected a number. → `PARAMETER_REGISTRY.md` §5
3. **Immutable records.** The initial plan is never rewritten; corrections create versions. → the
   schema itself, `AUDIT_AND_IMMUTABILITY.md`
4. **Reproducibility.** A re-run matches a control run. → `DETERMINISM_SPEC.md`
5. **Non-compensation.** No score, and no quantity of weak positive signals, may clear a critical
   gate. → `FAIL_CLOSED_POLICY.md` §3

## 6. Companions

`SUCCESS_AND_KILL_CRITERIA.md` (**owner-pending**) · `CONSTRAINTS.md` · `GLOSSARY.md` ·
`docs/README.md` for the full document set and gates.

## 7. Amendments

_None yet. Each amendment: date, what changed, why, who decided._
