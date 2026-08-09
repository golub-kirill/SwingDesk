# DR-001: Sharpe ratio convention

```
date:       2026-08-02
status:     proposed
parameters: stats.sharpe_convention
components: none yet - no Sharpe implementation exists
```

The course lists `Sharpe ratio` among the fifteen M69 metrics and supplies **no formula, no
periodicity and no risk-free rate** (`STATISTICS_SPEC.md` §3). Every part of the number is therefore
a choice, and the number changes by a large factor depending on which choices are made.

---

## Decision

Sharpe is computed on a **contiguous daily series of portfolio returns**, defined as:

| Element | Choice |
|---|---|
| return series | **daily**, one observation per exchange session in the evaluation window |
| non-trading days | **included as 0.0**, not omitted |
| return definition | change in account equity over the session, **net of modelled costs** |
| risk-free rate | **not subtracted** — excess return over zero |
| annualisation | multiply by **√252** |
| minimum observations | governed by `stats.min_sample_for_verdict`; below it the figure is reported and the verdict refused |

Reported as `Sharpe (daily, zero-filled, rf=0, ×√252, net)`. The convention travels with the number,
in the same string, wherever it is displayed.

## Why this one

**Zero-filling is the load-bearing choice.** A Sharpe computed only over sessions that had a trade
measures the volatility of *trading days* and divides by a denominator that never saw the flat
periods. It is systematically and sometimes dramatically inflated, and it looks entirely normal — the
same class of error `STATISTICS_SPEC.md` §3 records as having produced a silently inflated Sharpe in
a previous system. A contiguous series is the only version that answers "what did holding this
strategy feel like".

**Daily rather than per-trade.** A per-trade Sharpe has no time axis, so it cannot be annualised
honestly and it rewards a strategy for trading rarely. Daily portfolio return is the standard the
literature assumes (Sharpe 1994, *The Sharpe Ratio*), and it is what makes the figure comparable to
a benchmark's.

**rf = 0, stated rather than hidden.** Subtracting a risk-free rate is defensible and requires a
point-in-time rate series this project does not have. Setting it to zero and saying so is honest;
quietly omitting it while calling the result "Sharpe" is not. The consequence — the figure is
slightly flattering in a high-rate environment — is recorded here rather than discovered later.

**√252 with a caveat.** Annualising by √T assumes i.i.d. returns. Trading strategy returns are
autocorrelated, and Lo (2002), *The Statistics of Sharpe Ratios*, shows the naive factor can be
materially wrong when they are. This decision takes the standard factor for comparability and
records the assumption as the thing PR-003 should test, rather than pretending it holds.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| per-trade Sharpe over the R series | no time axis; cannot be annualised; rewards inactivity; not comparable to a benchmark |
| trade-month series (months containing trades) | the inflation trap above, in a less obvious costume |
| subtract a risk-free rate | needs a point-in-time rate series we do not have; would be backfilled, and backfilled is not point-in-time (`POINT_IN_TIME_SPEC.md` §7) |
| Lo's autocorrelation-adjusted annualisation | correct, and it needs an estimated autocorrelation from a sample we do not yet have. Adopting it now would mean estimating a correction from nothing |
| skip Sharpe, report Sortino only | the course names Sharpe explicitly; dropping a listed metric is a departure needing its own record |

## What would overturn this

- A measured autocorrelation in daily returns large enough that √252 misstates the annual figure by
  more than the difference the figure is used to decide. That is **PR-003** when there is a return
  series to measure.
- A decision to report against a benchmark, which would make rf = 0 the wrong baseline and require
  excess-over-benchmark instead.

## Consequences

1. The backtest must produce a **daily equity series**, not only a trade list. That is a harness
   requirement and it follows from this decision, not from the course.
2. Non-trading sessions come from the exchange calendar, so the calendar is an input to the
   statistics layer as well as the data layer.
3. `Sortino` and `Recovery factor` inherit the same series and the same zero-fill rule; their own
   conventions (MAR threshold, drawdown definition) still need decision records of their own.
   *(Written when the next free numbers were 4 and 5, and named them. Those were taken on 2026-08-02
   and 2026-08-05 by the cost model and measured slippage, so the numbers are removed rather than
   left pointing somewhere else. A reference that still resolves but resolves to the wrong thing is
   exactly what gate 3e cannot catch.)*
4. Any Sharpe displayed without its convention string is a defect.
