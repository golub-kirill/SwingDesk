# ADR-0002 — Exchange calendar source

- **Status:** Proposed
- **Date:** 2026-08-02
- **Evidence:** `docs/03-data/CALENDAR_SPEC.md` §2–§2e, measured with `tools/probe_calendar.py`

## Context

Short intraday sessions occur for two incompatible reasons: a scheduled early close (normal, must
not block trading) and a vendor data gap (abnormal, must raise `DATA` and block). **Both present
identically as fewer bars than usual.**

Measured, no signal available from the price data separates them:

| Signal | Detects | Blind to |
|---|---|---|
| bar count ≠ modal | any truncation | half-day vs gap |
| daily close vs last intraday close | end-truncation | start-truncation (2026-02-02 begins 13:30; diff +$0.05) |
| Σ intraday ÷ daily volume | catastrophic loss only | ranges overlap: normal 0.366–0.824, half-day 0.160–0.749, gap 0.003–0.677 |
| daily bar exists | market opened | intraday completeness |

Three real gaps were confirmed (2026-01-30, 2026-02-02, 2025-04-24) — `CNQ.TO` returned **0.3%** of
its daily volume across two bars while its daily bar was normal. Seven genuine half-days were also
confirmed, at 3 hourly bars each.

**Root cause: nothing in the system knows independently whether a market was open, or for how long.**
Data cannot validate itself.

## Decision

Adopt **`pandas_market_calendars`** as the authoritative exchange calendar, with the `NYSE` calendar
for US instruments and `TSX` for `.TO` instruments.

**Apply it uniformly to the live path and the backtest path.** This is a deliberate departure from
prior practice — see Precedent.

The calendar answers three questions no other source can:

1. Was the exchange open on date D?
2. What were that session's open and close times, including early closes?
3. Therefore, how many bars should this session contain at each interval?

A session whose actual bar count differs from its calendar-derived expected count is a **`DATA`
skip**. A session that matches its expected short count is a normal half-day and passes.

## Precedent

TradAlert (the owner's prior system) uses the same library in `src/core/freshness.py`, exchange-aware
for NYSE and TSX. Two things differ deliberately here:

| | TradAlert | SwingDesk |
|---|---|---|
| Scope | **live path only** — the module states it explicitly, and the calendar appears in exactly one file, imported from exactly one place | live **and** backtest |
| Use | staleness at the **end** of the series (`sessions_behind`, `drop_unclosed_bar`) | staleness **and** completeness across the whole history |

Restricting the calendar to the live path leaves the backtester unable to notice a hole in the
middle of its history — which is the side where an undetected gap silently corrupts a conclusion
rather than skipping one day's scan.

## Alternatives considered

- **Derive the calendar from observed bars.** Self-referential and provably insufficient: the thing
  being detected is missing bars, and absent bars are exactly what a closure looks like. Rejected on
  measurement, not on principle.
- **Hardcode recurring holiday rules.** Rejected: **2025-01-09** was an unscheduled NYSE closure
  present in the measured data and absent from every recurring rule. The calendar must be a
  *record*, not a formula.
- **Take the calendar from the data vendor.** Neither free source publishes one.
- **Ignore the problem** and accept occasional bad sessions. Rejected — it contradicts `BR-2`
  (fail closed) and `criteria.yml` `a.no_uncoded_failures`.

## Consequences

- Positive: half-days and gaps become distinguishable, which is the only way `DATA` can be raised
  correctly rather than always or never. Unscheduled closures are handled because the source is a
  record. Backtests gain completeness checking they would not otherwise have.
- Negative: one runtime dependency, and it must be kept current — a calendar that is stale about
  *future* early closes silently reverts to the ambiguous state. Version it and pin it.
- Neutral: it also supplies the session open/close times `CALENDAR_SPEC` §3 needs, so bar-boundary
  expectations stop being hardcoded constants.

## Revisit when

- The library stops being maintained, or is wrong about a session we can verify independently.
- Instruments outside NYSE/TSX enter the universe.
- A vendor begins publishing an authoritative calendar with its data.
