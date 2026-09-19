# PR-031 RESULT: the published intraday momentum rule, long only on SPY, made 8.5% a year at a Sharpe ratio of 1.01 — and almost nothing since it was published

```
prereg:        PR-031
ran:           2026-09-19
verdict:       ACCEPT, as registered - and by the thinnest margin the rule allows. SPY-long's net
               mean +0.0336% a day [+0.0169, +0.0521], cost-adverse [+0.0130, +0.0485]; the
               publication gate asked for an estimate above zero after 2024-05-10 and got
               +0.0018% a day [-0.0228, +0.0263], a Sharpe ratio of 0.06 over 590 sessions
status:        final. Run once from the registration commit's snapshot at the pinned instant
tool:          tools/run_pr031.py
evidence:      PR-031.json; SPY and QQQ minutes from Alpaca sip, 2,693 sessions each, in a
               scratchpad store at 2026-09-19T20:57:13.362351+00:00
trials:        3, declared before the run (SPY-long, QQQ-long, SPY-both)
```

---

## Read this first

**This is the first rule in this project to make money net of costs and beat holding `SPY` per
unit of risk.** Traded long only on `SPY` from 2016 to 2026, deciding on the minute that ends at each
half hour and filling at the next one, it earned **8.5% a year at 8.4% volatility, a Sharpe ratio
of 1.01**. Its worst drawdown was **−9.9%**. Holding `SPY` over the same sessions earned 14.8% a
year at 17.7% volatility, a Sharpe ratio of 0.83, with a −34.2% drawdown, counting price only. The
two correlate at 0.27.

**Since the paper appeared, on `SPY`, it has made almost nothing.** Over the 590 sessions after
2024-05-10 the mean is **+0.0018% a day [−0.0228, +0.0263]**, 0.45% a year, at a Sharpe ratio of
**0.06**. Its worst drawdown, −9.9%, came in that period. The registered rule asked for an estimate
above zero after publication, and this one is above zero by about a seventh of its own standard
error.

**Read the `ACCEPT` as "worked on `SPY` until it was published; not shown to work since".** The
registration's own branch for that reading was `PUBLICATION_FRAGILE`, and it missed it by 0.0018.

**On `QQQ` it held up.** The same rule, counted and never read, earned **8.6% a year after
publication at a Sharpe ratio of 1.06** (+0.0341% a day [−0.0018, +0.0646]). Over the whole window
it earned 10.2% a year at 1.20. It is a secondary reading, so it is reported and not read, and
choosing the fund that did better after the fact would be a new trial.

## §9, as registered

| check | registered | realised |
|---|---|---|
| sessions unread | at most a tenth | **0** of `SPY`'s 2,678 after warm-up; 3 thin `QQQ` sessions |
| realised half-width against §3's 0.018 | half to twice | **0.0176**, 0.98× |
| mean leverage | 1 to 4 | **2.66** (`SPY`), 2.06 (`QQQ`) |

**Does it replicate the paper?** The paper's own long-and-short rule, `SPY-both`, earned **+0.0687%
a day** on the years before publication, **17.3% a year**. The paper reports 19.6% a year over
2007-2024 with a same-bar fill. The implementation reproduces the published result within what the
one-minute delay and the shorter window would cost.

## The readings

| mean daily net return | whole, 2016-01 .. 2026-09 | before publication | **after publication** (590 sessions) |
|---|---|---|---|
| **`SPY-long`** (the verdict) | **+0.0336%** [+0.0169, +0.0521] | +0.0426% [+0.0233, +0.0644] | **+0.0018%** [−0.0228, +0.0263] |
| cost-adverse (a cent a side) | +0.0299% [+0.0130, +0.0485] | | |
| the paper's cost ($0.0045) | +0.0340% [+0.0173, +0.0524] | | |
| gross | +0.0373% [+0.0207, +0.0556] | | |
| `QQQ-long` (counted, never read) | +0.0405% [+0.0206, +0.0599] | +0.0424% [+0.0189, +0.0658] | +0.0341% [−0.0018, +0.0646] |
| `SPY-both` (counted, never read) | +0.0565% [+0.0259, +0.0902] | +0.0687% [+0.0335, +0.1059] | +0.0134% [−0.0434, +0.0840] |

**Described, never read by §6:**

| | a year | volatility | Sharpe | CAGR | worst drawdown | sessions in the market |
|---|---|---|---|---|---|---|
| `SPY-long`, whole | 8.5% | 8.4% | **1.01** | 8.5% | −9.9% | 887 of 2,678 |
| `SPY-long`, after publication | 0.45% | 7.6% | **0.06** | 0.2% | −9.9% | |
| `QQQ-long`, whole | 10.2% | 8.5% | 1.20 | 10.4% | −14.7% | 843 of 2,675 |
| `QQQ-long`, after publication | 8.6% | 8.1% | 1.06 | 8.6% | −6.3% | |
| `SPY-both`, whole | 14.2% | 14.4% | 0.99 | 14.1% | −25.8% | 1,612 of 2,678 |
| holding `SPY`, price only | 14.8% | 17.7% | 0.83 | 14.1% | −34.2% | every session |
| holding `QQQ`, price only | 20.9% | 22.2% | 0.94 | 20.2% | −35.6% | every session |

Costs barely matter here. Half a cent a share a side takes 0.0037% a day, and a whole cent takes
0.0074%. `SPY`'s spread is a tick, and the rule trades on a third of sessions.

## What this establishes, and what it does not

**Established:** over 2016-2026, the published rule made money long only on `SPY`, net of a
half-cent a share and with no look-ahead. Its return per unit of risk was above holding `SPY`'s, with
a correlation of 0.27. Its whole-window interval is clear of zero at a cent a share.

**Not established:**

* **that it still works on `SPY`.** 590 sessions since publication earned 0.45% a year. Their
  interval is wide enough to hold 6% a year either way, so this is not a finding that it stopped.
  It is the absence of a finding that it continued. `CHARTER` A-003's first caution is why that
  period was read apart.
* **that `QQQ` is the better fund.** It is a secondary reading, and it was picked out of three
  after the fact.
* **that it can be run.** Nothing here trades inside a session (`CHARTER` A-003 §4). The rule needs
  a decision every half hour, orders a minute later, and leverage up to 4×. Under the
  pattern-day-trader rule, a margin account under $25,000 may make only three day trades in five
  sessions, and 4× intraday leverage needs an account above that.

## What it changes

* **The first strategy worth a specification.** The registration licensed exactly this. An
  `ACCEPT` is *worth a specification for a live paper trial*, and nothing is built on any branch
  without the owner. A paper trial run forward would measure the one thing this backtest cannot:
  whether the rule still works in the market that has read the paper.
* **Which fund, what leverage, and whether to build an intraday loop at all are the owner's calls.**

## What the study cost

5,386 requests to the vendor over an hour for the minutes; one run of two minutes. Three trials.
