# SUCCESS AND KILL CRITERIA

**Status: OWNER-PENDING — this document is deliberately unfinished.**
**Tier:** 0 (charter) · Gate **G0 cannot close until it is filled in.**

---

## Why this is empty

Writing these criteria is the single thing in this project that must not be delegated. The previous
system was built, run, and only then measured against a benchmark — at which point the answer was
"≈benchmark", and there was no pre-agreed rule for what to do about it. That is not a measurement
failure. It is a **missing decision, made too late**.

Filling this in with plausible-looking numbers would recreate exactly that failure while appearing
to have avoided it. So it stays open, and G0 stays open with it.

Note that this is separate from the **v1 finish line** in `CHARTER.md` §4, which concerns whether
the *machinery* is built and honest. This document concerns whether the *trading* is worth doing.
The two can be answered independently, and the finish line is not blocked on this.

## What has to be decided

### 1. What "the system works" means, numerically

The course refuses to supply this too — it defines nine validation statuses and says outright that
they are not grades. So the bar is yours. Some framings, none recommended over another:

- **Process-first.** Success = the process is followed and recorded: 100% plan/stop/journal, no
  critical violations, `Process compliance` above a stated level. This is the only bar the course
  itself states a version of (Appendix S, first 20 trades). It is measurable within weeks and says
  nothing about profit.
- **Expectancy with uncertainty.** Success = expectancy positive, net of all costs, with a
  confidence interval excluding zero, on a stated minimum sample, out of sample.
- **Benchmark-relative.** Success = risk-adjusted return above buy-and-hold on the same universe,
  net of costs. Hardest bar; the one the previous system failed.
- **Decision-support only.** Success = the tool measurably improves the owner's own decisions —
  fewer `LATE` entries, fewer `WIDE_STOP` violations, better MFE capture — regardless of the
  strategy's edge. Note this is the bar that actually matches D1, and it is the only one that can be
  met while every setup remains `Untested`.

### 2. The minimum sample before any verdict

`registry/parameters.yml` → `stats.min_sample_for_verdict`, currently `unset`. The course names
"малая выборка" as a prohibition and never quantifies it. Until this has a number, **no result is a
verdict** — the system reports the count and declines the conclusion.

### 3. The kill criteria

The harder half, and the half that is almost always skipped. What result makes this project stop?

- A measured outcome that ends it (and after how many trades, over what window).
- A time or cost ceiling that ends it regardless of outcome.
- A condition under which it converts to something smaller — e.g. journal and statistics only,
  abandoning signal generation.

A project with no kill criterion does not fail; it just continues. That is the failure mode this
document exists to prevent.

### 4. Who decides, and when

The review cadence at which these criteria are checked, and the rule that they may not be edited
after seeing a result — the same discipline `PREREG_TEMPLATE.md` applies to individual levers,
applied to the project itself.

## Constraints on whatever gets written here

1. **Criteria are frozen before the run that tests them.** Editing after seeing a result creates a
   new criterion and voids the claim — §3.7, applied at project level.
2. **Both branches are written in advance.** What happens on pass, and what happens on fail. A
   criterion with only a success branch is a hope.
3. **Net of costs**, always — commission, spread, slippage, borrow, FX.
4. **The survivorship caveat applies** and cannot be assumed away: no free source serves delisted
   instruments (`ADR-0001` condition 6). Any historical criterion is optimistic by an unknown
   amount, and the criterion should say how that is handled.
5. **A negative result is a result.** `Rejected` is a legitimate terminal validation status and
   reaching it honestly is a success of the *process*, whatever it means for the strategy.
