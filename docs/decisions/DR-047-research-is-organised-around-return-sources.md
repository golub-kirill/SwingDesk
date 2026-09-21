# DR-047: Research is organised around SOURCES OF RETURN, not around trading expressions

```
date:            2026-09-20
status:          accepted — ruled by the owner 2026-09-20 after an advisory council reviewed
                 PR-030..PR-035 and an external review of the whole research stack. The owner's
                 instruction: "запиши все новое, исправь старые требования и подходы... Это все
                 крайне важно для нас"
parameters:      none set here. criteria.yml gains b.excess_cagr and b.beta_matched; the metric
                 change is section 3.5
components:      none new
implementation: none
binds:           documents and a registry rather than code - PREREG_TEMPLATE.md rules 11-15,
                 RETURN_SOURCE_REGISTER.md, BACKTEST_PROTOCOL.md sections 6 and 6b, and
                 criteria.yml b.excess_cagr / b.beta_matched. Section 7 names each
```

## 1. What was ruled

**A study registers a SOURCE OF RETURN and the reason it should exist. It does not register an
entry rule.** Nine clauses follow from that and they are binding on every pre-registration written
after this date. They are in §3.

## 2. What forced it — this project's own numbers, not an opinion

Two reviews landed on 2026-09-20: an advisory council on `PR-030`..`PR-035`, and an external
critique of the research stack. Both were checked against this repository before anything here was
written, because *"advisors reason from the prompt, not the repo"*. What survived the check:

| the claim | what this repository says |
|---|---|
| The universe is judged against a benchmark it does not resemble | `EVIDENCE_SUMMARY` §26's own table: the admitted universe correlates **0.982 with `MDY`** and **0.912 with `SPY`**, and trails `SPY` by **−3.02% a year** as a style gap. It is an equal-weighted mid-cap book measured against a mega-cap index |
| The trading expression was optimised before the signal was established | `PR-016`..`PR-019` varied stop, target, hold and filters. `PR-019`'s best configuration had no demonstrated positive expectancy, and `PR-019b` found the index earned more over the same days |
| A four-name book is too small to discover anything | `PR-015`: the four-name book's intervals are **1.4× to 3.9× wider** than the decile's |
| ...but that is not the whole diagnosis | **`PR-015` also measured the decile itself — about 130 names, gross — and it does not separate from zero either.** The content was missing, not merely blurred |
| Survivorship is still open | Every stock study declares `survivorship: ABSENT`. `BACKTEST_PROTOCOL` §6 recorded on 2026-09-05 that Alpaca serves **19,188 inactive US assets** and returned full daily history for seven of eight probed — so the remedy is a fetch nobody has run, not a purchase |
| The metric is not the question | `EXPECTATION_MODEL` already says mean R a trade and a buy-and-hold return are not commensurable, and `criteria.yml`'s `b.expectancy` is still `E[R] > 0` |
| Execution was researched before the signal was proven | `PR-024`, `PR-025`, `PR-030` priced fills for a card whose own net is zero |
| A published rule is not an edge | `PR-031` reproduced 8.5% a year on `SPY` and **0.45% since publication**; `PR-032` found it absent on three funds it was never fitted to |

**And the arithmetic of the programme**, as `HANDOFF.md` §2 counts it on the day this was ruled:
every registered component, 166 evaluated configurations, and **zero validated strategies**. The research engine is more productive than the alpha engine, and
that is a fact about how the search was aimed.

**What was wrong in the external critique, checked and corrected:** `PR-035` HAS run (reported
2026-09-20, `COST_FRAGILE` — and its warning that the combined book is capital efficiency rather
than alpha is exactly what the run showed); the delisted remedy is a fetch rather than a paid
vendor; and the four-name diagnosis is incomplete because the decile failed too.

## 3. The nine clauses

### 3.1 The unit of research is a source of return

A registration names the economic mechanism it is testing and why anyone should be paid for
bearing it, with the literature that describes it. *"Rank by strength and hold the top decile"* is
a trading expression; *"cross-sectional momentum in mid-cap equities"* is a source. The register
(§4) holds them.

### 3.2 A source's first test carries no stop, no target and no sizing rule

Exit is the rebalance or the signal leaving. **A first test that carries risk management cannot
separate "the source pays" from "the stop pays"**, and `PR-016`..`PR-019` spent nineteen
registrations learning that. Risk management is a SECOND study on a source that survived the first.

### 3.3 Discovery needs at least twenty names; implementation is a separate study

Below that the idiosyncratic noise of a few names dominates the signal — `PR-015` measured the
factor at 1.4× to 3.9×. A book of four is a question about implementation, and it is asked after
the source is established, never instead.

### 3.4 The benchmark is a set, and it is one equity curve

Every study on a directional equity strategy reports, from the same starting capital and on the
same calendar:

1. the strategy;
2. **its own universe**, held passively — *can I pick inside my pool?*;
3. **`SPY` total return** — *is my pool worth being in?*;
4. **`SPY` matched to the strategy's own volatility** — *am I paid for skill or for exposure?*

`PR-021` is why (4) is mandatory: beta 1.45 and a worse result than the index.

### 3.5 The primary metric is geometric excess return, not mean R

`R` a trade stays as an operational diagnostic — position sizing needs it and the journal reports
it. It is not what answers *"does this make more money than the index"*. `criteria.yml` gains
**`b.excess_cagr`** (geometric annualised excess over `SPY` on one equity curve, bootstrap interval
excluding zero) and **`b.beta_matched`** (the same against volatility-matched `SPY`).
`b.expectancy` is unchanged and no longer carries a study's verdict.

### 3.6 Rolling three-year excess is reported, and a single-epoch result is not believed

A strategy that earns its whole advantage in one era has not been shown to have one. `PR-031` is
the case: an `ACCEPT` whose every point came before the paper that described it was published.

### 3.7 One registration, one hypothesis

A parameter sweep is a search. It may be run, and it is declared as N trials against the budget
before it runs. `12-1 → 9-1 → 6-1 → 126 → 189 → 252 → ATR 2 → ATR 3` is not a study; it is eight.

### 3.8 The order of operations

```
gross signal → risk-adjusted signal → out of sample → cost robustness → execution → implementation
```

Execution research on an unproven signal answers *"how cheaply can I trade something that may be
worth nothing"*. It is not forbidden — `PR-024`'s 29 bps a trade is the largest single improvement
this project has measured — but it is not evidence about a source and never precedes it again.

### 3.9 A stock study uses the repaired universe or refuses

From this date, a pre-registration whose population is individual equities must read a universe
including delisted names, or carry `REFUSED` in its own decision rule. `survivorship: ABSENT` stops
being a disclosure a study can choose; it becomes a blocker. **ETF-only studies are exempt and the
register says why**: a fund's own provider maintains its constituents, so the survivorship question
does not arise at the fund level.

## 4. The closed families, and closing is the point

`RETURN_SOURCE_REGISTER.md` carries every source this project has touched, what was measured, and
what would reopen it. Six families are **closed** by the evidence already spent on them:

| closed | what was measured | what reopens it |
|---|---|---|
| breakout and trend definitions | `PR-001`, `PR-005`: costs exceed the edge | a cost structure an order of magnitude cheaper |
| 5-20 day reversal | `PR-021`: `REJECT`, −25 points a year against `SPY` | nothing at this horizon; a different holding period is a different source |
| stop, target and ATR variation | `PR-016`..`PR-019`: the container, on a signal never established | a source that passed its first test under §3.2 |
| four-name discovery books | `PR-015`: 1.4-3.9× wider, and the decile failed too | never as discovery; only as implementation |
| published intraday rules | `PR-031`, `PR-032`: reproduced then absent | a rule with an economic mechanism that predicts where it should NOT work, tested there first |
| execution before a signal | `PR-024`, `PR-025`, `PR-030` | §3.8's order |

**Closing costs nothing and saves the hurdle.** Every configuration evaluated raises
`b.deflated_sharpe` for every study after it; a family re-opened out of forgetfulness is paid for
twice.

## 5. What this does NOT change

Pre-registration before the run, and never edited in place. The trial budget and its 2.70 sd
hurdle. Fail-closed refusal over defaults. `A-002`'s paper-only boundary and the four guards on
submission. Mutation-tested runners. `null` and `inconclusive` as first-class outcomes. **None of
the machinery was wrong** — it was aimed at a space that could only answer "no", and it answered
correctly every time.

## 6. What it costs

- **The survivorship repair is real work**: 19,188 inactive assets, a fetch measured in hours, and
  a universe rule that reads membership as of the decision date rather than today.
- **Every study gets longer**: four curves instead of one number, and a rolling window beside the
  headline.
- **Fewer studies**: one hypothesis per registration, at roughly a day each, against the dozen a
  day this project has been capable of. That is the intended trade.
- **And it promises nothing about the size of the answer.** Long-only medium-term momentum in large
  caps is a factor tilt with a historical excess of a few points a year and multi-year droughts; a
  2025 paper on the classic 12-1 rule in the S&P 500 reports a negative net result after costs.
  **This decision buys trustworthy answers, not bigger ones**, and a reader who expects otherwise
  will be disappointed by the first study that follows it.

## 7. How it is enforced

| clause | enforced by |
|---|---|
| 3.1, 3.7 | `PREREG_TEMPLATE` rules 11 and 14; gate 25 reads the template's conformance |
| 3.2, 3.3 | `PREREG_TEMPLATE` rules 12 and 13 |
| 3.4, 3.5 | `criteria.yml`'s two new criteria, and the template's §3 |
| 3.6 | the template's §5 diagnostics list |
| 3.8, 3.9 | `BACKTEST_PROTOCOL` §6 and §9 |
| §4 | the register, cited from every §0 |
