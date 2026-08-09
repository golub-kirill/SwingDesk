# DR-004: The cost model

```
date:       2026-08-02
status:     proposed - slippage component superseded by DR-005 on 2026-08-05
parameters: costs.commission_model, costs.slippage_model
components: none - swingdesk.validation.backtest.costs implements it; this sets its inputs
```

> **The 5bps slippage figure below is no longer current.** `DR-005` measured it from daily OHLC and
> replaced it with **25bps per side**. Everything else here stands, including the commission model,
> the 3× stress regime, and the reasoning for charging slippage to the fill rather than deducting it
> afterwards. This record is left otherwise unedited: it is what was decided on 2026-08-02 and why,
> and the fact that its own "what would overturn this" section named the wrong replacement route is
> part of what it has to say.

M72-T1081 (`Комиссии`) and M72-T1082 (`Проскальзывание`) both exist as topics and neither contains a
number. PR-002 names setting them as a precondition, and for a reason worth quoting:

> a regime effect smaller than the cost spread is not a finding

A study that models zero costs can discover an edge that a broker consumes entirely, and the
difference between "this works" and "this works before costs" is the whole question.

---

## Decision

| Parameter | Value |
|---|---|
| `costs.commission_model` | **0.005 USD per share, each side** |
| `costs.slippage_model` | **5 basis points of price, each side**, applied to the fill |

Stress regime: **3×** both components (`validation.stress_cost_multiplier`).

Slippage is applied to the **fill price**, not deducted afterwards. A buyer pays up, a seller
receives less, and the recorded entry is the price actually paid — so MFE and MAE are measured from
a real fill rather than an idealised one. Deducting at the end gets the P&L right and the excursions
wrong.

## Why these

**Commission: 0.005/share.** A per-share schedule rather than per-trade, because per-trade flatters
small positions and this system sizes by risk, so position size varies by an order of magnitude
across instruments. 0.005 is a common retail per-share rate and is an **assumption, not a quote** —
no broker has been selected (`CHARTER.md` non-goal: no broker integration).

**Slippage: 5bp, proportional.** Proportional rather than a fixed cent amount because a cent is 20bp
on a $5 stock and 0.1bp on a $500 one, and `universe.min_price` admits both ends. 5bp on a
liquid instrument entering at the open is on the optimistic side of plausible, which is why the
stress regime exists and why PR-005 reported both.

**3× stress rather than 2× or 5×.** `WALKFORWARD_SPEC.md` §4 requires cost stress and does not
quantify it. 3× turns 5bp into 15bp and 0.005 into 0.015 — roughly the difference between a liquid
open fill and a poor one on a thinner name. It changed PR-005's answer from "flat" to "clearly
negative", which is the discrimination a stress test is for.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| zero costs | discovers edges a broker eats; PR-002 rules it out explicitly |
| fixed per-trade commission | flatters small positions, and risk-based sizing makes position size vary widely |
| fixed cent slippage | 20bp on a $5 stock and 0.1bp on a $500 one, across a universe admitting both |
| spread-derived slippage from quoted bid/ask | correct and unavailable — no free source serves historical intraday spreads point-in-time |
| modelling market impact as a function of order size vs ADTV | right for large orders and irrelevant at $1000 risk per trade against a $5M ADTV floor. Revisit if position sizes ever approach the liquidity cap |

## What would overturn this

**Measured live slippage against modelled** (M74-T1110, `Проверка реального проскальзывания`). The
forward test records actual fills; the difference between those and this model is directly
observable and is the intended way this value gets replaced. That is `PR-006` when a forward test
exists.

Also: adopting a broker. A real commission schedule replaces an assumed one, and that is a
substitution rather than a study.

## Consequences

1. Every backtest reports net figures. Gross is not reported at all — Appendix J says `Net R`, and
   showing gross with costs in a footnote is how a losing strategy looks profitable.
2. Results are reported at 1× **and** 3×. PR-005 established why: at 1× the strategy was flat and
   at 3× every arm was negative, and quoting only the first would have been a materially different
   claim.
3. These values are `assumed`, so any number computed from them is marked as assumption-derived
   wherever it appears (`PARAMETER_REGISTRY.md` §5). A cost model is a modelling choice sitting
   underneath every R in the system, and it should be visible as one.
