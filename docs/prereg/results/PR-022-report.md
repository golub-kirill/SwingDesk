# PR-022 RESULT: the trend exit halves the index's worst fall and gives up a third of its return — per unit of risk, a wash

```
prereg:        PR-022
ran:           2026-09-14
verdict:       INCONCLUSIVE, exactly as section 3 predicted. Over 2007-06-01 .. 2026-09-11 the
               rule's Sharpe is 0.625 and holding SPY's is 0.615: a difference of +0.011
               [-0.370, +0.389], 0.759 wide against the 0.40 floor. Beside it, and never read by
               section 6: the worst drawdown falls from -55.2% to -26.9% and volatility from 19.7%
               to 12.6%, while the compound return falls from 10.70% to 7.34% a year
status:        final - one rule, no selection, no split; section 9's checks reproduced the power
               estimate to the digit
tool:          tools/run_pr022.py, sized by tools/power_pr022.py, data by tools/fetch_history.py
evidence:      PR-022.json, PR-022-power.json
trials:        1, declared before the run
```

---

## Read this first

**The rule did what the class promises, and charged exactly what the risk was worth.** Holding
`SPY` only above its ten-month average cut the worst fall of nineteen years in half and a third off
the volatility — and gave up 3.4 points of compound return a year. Per unit of risk the two books
are the same: 0.625 against 0.615. The verdict is `INCONCLUSIVE` because a difference of 0.011 sits
in an interval 0.76 wide, which §3 said before the run is all one index over nineteen years can
resolve.

**So this is a risk dial, not an edge.** It does not make the index earn more; it holds less of the
index's risk, on average, and is paid accordingly. And an exploratory comparison made after the run
(below) says the plainest risk dial — simply holding less `SPY` — did at least as well on every
reading except the worst fall of 2008.

**In the last 48 months it cost ten points a year.** Every recent fall was sharp and quickly
recovered, and a rule that decides once a month re-entered each recovery late.

## §9, which had to hold before anything else could be read

| check | registered | realised |
|---|---|---|
| switches, against the power estimate | the same, to the digit | **32 and 32** |
| the Sharpe difference's width, against the power estimate | the same, to the digit | **0.759 and 0.759** |
| sessions the timed book held `BIL` without a price | none | **none** |
| `BIL`'s price in 2007 and in 2026, a split never applied twice | about 91.5 | **91.52–92.04 and 91.39–91.68** |

**All four hold.** The run reproduced its own power estimate, which is the check that the verdict
and the sizing read the same series.

## The verdict, as §6 reads it

```
Sharpe, timed - held:     +0.011   [-0.370, +0.389]   width 0.759
branch:                   INCONCLUSIVE - the interval contains zero and is wider than 0.40
```

| | the rule | holding `SPY` |
|---|---|---|
| Sharpe (daily, net, rf = 0, ×√252) | **0.625** [0.213, 1.077] | **0.615** [0.240, 1.076] |
| compound return a year | 7.34% | 10.70% |
| volatility | 12.6% | 19.7% |
| worst drawdown | **−26.9%**, 2022-01-03 → 2023-03-13 | **−55.2%**, 2007-10-09 → 2009-03-09 |
| arithmetic return difference, points a year | −4.23 [−9.63, +1.32] | |
| share of sessions invested | 78.0% | 100% |
| switches | 32, 1.66 a year | — |

## §3's prediction, graded

| | predicted | realised |
|---|---|---|
| branch | `INCONCLUSIVE` | **`INCONCLUSIVE`** |
| centre, Sharpe difference | +0.05 to +0.25 | **+0.011** — below the band |
| width | 0.759 | **0.759** |

**The branch was right and the centre was too kind again.** The published record puts this rule's
improvement near +0.1 to +0.3; on this window, after `DR-005`'s cost, it was nearly nothing. At zero
cost the difference is +0.077, so the cost the registry charges — about twenty-five times `SPY`'s
own spread — takes most of what gross there was.

## Perturbation — three times `DR-005`

The difference falls to **−0.125**. Read by §6 on an `ACCEPT` only.

## Diagnostics — registered, printed, never read by §6

**Every fall of the index deeper than 15% in the window — five, and the last 48 months hold one:**

| the index's fall | `SPY` | the rule, same sessions | the rule's own worst inside | the recovery: `SPY` / the rule |
|---|---|---|---|---|
| 2007-10-09 → 2009-03-09 | **−55.2%** | **−4.7%** | −17.8% | +124.2% / +28.0% |
| 2018-09-20 → 2018-12-24 | −19.3% | **−22.5%** | −22.5% | +24.4% / +8.4% |
| 2020-02-19 → 2020-03-23 | −33.7% | −12.1% | −13.5% | +51.2% / +10.4% |
| 2022-01-03 → 2022-10-12 | −24.5% | −18.0% | −26.9% | +34.1% / +0.7% |
| 2025-02-19 → 2025-04-08 | −18.8% | −9.2% | −10.0% | +23.6% / +4.5% |

**The shape is the whole story.** In the one slow bear market, 2008, the rule was out before most of
the fall — and then back too late for most of the recovery. In the sharp ones it either stepped out
after the damage (2018, where it did worse than the index) or stepped out and missed the rebound
(2020, 2022, 2025). A monthly decision cannot tell a fall that will last from one that will not, and
the recoveries are where the return went.

**Each year**, the rule / `SPY`:

| | | | | | | | | | |
|---|---|---|---|---|---|---|---|---|---|
| 2007 | −3.6 / −3.6 | 2008 | **+1.2 / −36.8** | 2009 | +21.6 / +26.4 | 2010 | +0.2 / +15.1 | 2011 | −2.4 / +1.9 |
| 2012 | +9.5 / +16.0 | 2013 | +32.3 / +32.3 | 2014 | +13.5 / +13.5 | 2015 | −7.6 / +1.3 | 2016 | +8.2 / +12.0 |
| 2017 | +21.7 / +21.7 | 2018 | −8.3 / −4.6 | 2019 | +4.8 / +31.2 | 2020 | +14.6 / +18.4 | 2021 | +28.7 / +28.7 |
| 2022 | −22.5 / −18.2 | 2023 | +8.7 / +26.2 | 2024 | +24.9 / +24.9 | 2025 | +11.3 / +17.7 | 2026 | +1.4 / +12.7 |

Percent, total return, the rule net of `DR-005`. **One year in twenty — 2008 — carries the rule's
case.** In every one of the other nineteen it trails the index or ties it: thirteen behind, six
level, none ahead.

**The last 48 months**, `AGENTS.md` §19's current market: Sharpe difference **−0.380 [−1.130,
+0.061]**, compound return 9.67% against 19.81%, worst drawdown −11.2% against −18.8%, invested
84.1%, nine switches.

## Exploratory, after the run — against simply holding less `SPY`

*Not registered, chosen after the result was seen (`PREREG_TEMPLATE` rule 3), read by nothing.* The
rule's volatility, 12.6%, is what a fixed 64% in `SPY` and 36% in `BIL` carries. Rebalanced daily and
charged nothing:

| | the rule | fixed 64% `SPY` / 36% `BIL` | holding `SPY` |
|---|---|---|---|
| compound return a year | 7.34% | **7.73%** | 10.70% |
| volatility | 12.6% | 12.6% | 19.7% |
| Sharpe | 0.625 | **0.655** | 0.615 |
| worst drawdown | **−26.9%** | −38.1% (2008) | −55.2% (2008) |
| last 48 months, compound a year | 9.67% | **14.37%** | 19.81% |

**At the same risk, the fixed mix earned a little more, and in the current market a great deal
more.** The rule's one advantage is the worst fall: in 2008 it lost 4.7% through the index's
decline where the mix lost 38.1%. That is a real difference, and it is one event.

## What this establishes, and what it does not

**Established, at the registered design:**

* **The rule's Sharpe ratio equals the index's on this window** — within an interval that cannot
  tell ±0.38 apart. The class did not buy more return per unit of risk.
* **It cut the worst drawdown by half and volatility by a third, for 3.4 points of compound return a
  year** — measured on one path, not estimated.
* **It was out of the market for 22% of the sessions and switched 32 times in nineteen years**, at a
  cost the registry prices at 0.83 points a year.

**Not established:**

* **Anything about the next crash.** Five falls, each different; the rule met each at a month-end.
* **That a different trend rule does better.** The 200-session daily average, twelve-month
  momentum, a band and other markets were registered as not run, and each is another draw.
* **The exploratory mix as a finding.** It was chosen after the run and has no interval.

## What this licenses

> *On `SPY` since 2007, stepping into T-bills below the ten-month average did not earn more per unit
> of risk than holding the index; it held less risk and earned correspondingly less.*

No parameter moves and no card exists.

## What it changes

**Three classes are now measured, and holding the index has not been beaten on a risk-adjusted basis
by any of them**: the relative-strength family (`EVIDENCE_SUMMARY` §20.6–§20.9), short-term reversal
(§21), and the index with a trend exit (§22). The trend exit is the first that did not lose to it
outright — it matched it per unit of risk — and the first whose value is a CHOICE about risk rather
than a claim about return. **How much of the index's risk to carry is a question about the owner's
capital and tolerance for loss, not one this study can answer**, and it is not investment advice.

## Addendum, 2026-09-14, after the run — the convention flatters any book that holds cash

*Exploratory; read by nothing; the verdict stands.* `stats.sharpe_convention` sets rf = 0, so a book
paid the T-bill yield for the fifth of the time it sits in `BIL` has that yield counted as reward for
risk. Measured on the same series, with `BIL`'s own daily total return as the risk-free leg (1.38% a
year on average over the window):

| | rf = 0, as registered | excess over `BIL` |
|---|---|---|
| Sharpe, the rule | 0.625 | **0.516** |
| Sharpe, holding `SPY` | 0.615 | **0.543** |
| difference | +0.011 [−0.370, +0.389] | **−0.027 [−0.401, +0.343]** |

**The sign of the point estimate turns.** Neither interval excludes zero, so the verdict is
`INCONCLUSIVE` either way; but the small edge the registered reading showed was the convention, not
the rule. `PR-023` registers the excess-over-`BIL` Sharpe as its primary for this reason and reports
the convention beside it.

## What the study cost

**One trial.** The programme's count moves from **120 to 121** and the hurdle from **2.594 to 2.597**
sd(SR) — derive both with `python tools/trial_budget.py`. The run took six seconds from the
registration commit's own snapshot.
