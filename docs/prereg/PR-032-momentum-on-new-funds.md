# PREREG: does the intraday momentum rule still work on funds this project has never read?

```
id:            PR-032
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19. Shown PR-031's ACCEPT and the
               near-zero two years since publication on SPY, the owner picked "Проверить на
               новых ETF" over writing a live paper-trial specification
status:        reported   (2026-09-19 - results/PR-032-report.md)
verdict:       INCONCLUSIVE, branch NULL - the basket since publication -0.0054% a day [-0.0293, +0.0199], zero inside
               the floor, and +0.0003% gross. The secondary reading says more: BEFORE publication
               the same basket earned +0.0035% a day, 0.9% a year - the rule was never present on
               these funds
```

---

## 0. Refutation-family check

**searched:** `PR-031` and its report, `EVIDENCE_SUMMARY` §29, `CHARTER` A-003.

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-031` | the published rule, long only on `SPY`, 2016-2026 | `ACCEPT` — +0.0336% a day [+0.0169, +0.0521], 8.5% a year at a Sharpe ratio of 1.01, against holding `SPY`'s 0.83 |
| `PR-031`, since publication | the same 590 sessions after 2024-05-10 | **+0.0018% a day [−0.0228, +0.0263]**, a Sharpe ratio of 0.06 |
| `PR-031`, `QQQ` (counted, never read) | the same rule on `QQQ` | 8.6% a year since publication, Sharpe 1.06 |

**distinct because two stories fit `PR-031` and they differ on funds nobody has looked at.** Either
the rule decayed when it was published — the `CHARTER`'s standing caution — or `SPY`'s last two
years are one fund's bad run and `QQQ`'s are one fund's good one. Choosing `QQQ` because it did
better after the fact would settle nothing; three funds picked for what they ARE, read only since
publication, is the cheapest thing that can.

**What is known in advance, stated first.** Every number above. Nothing in this repository has read
a minute of `IWM`, `DIA` or `EFA`: the fetch that fills them runs after this registration is
written, and the power estimate below lets only widths out.

## 1. Question

Over the 590 sessions since the paper appeared, does `PR-031`'s rule — unchanged, long only —
earn a positive mean daily return net of costs on an equally weighted basket of `IWM`, `DIA` and
`EFA`?

## 2. Hypothesis

**H1.** The basket's mean daily net return has a 95% interval wholly above zero.

**H0.** It does not.

**Counted and never read:** each fund on its own since publication, and the same basket over
2016-01-04 .. the day before publication.

## 3. Prediction, stated numerically before the run

```
primary quantity:  the mean over sessions since 2024-05-13 of the equally weighted basket's net
                   return on equity, each fund traded by run_pr031's rule; month-clustered bootstrap
predicted:         the basket about +0.02% a day (about +5% a year), between 0.00 and +0.04.
                   PR-031 measured +0.0426% a day on SPY before publication and +0.0341% on QQQ
                   since; EFA's intraday range is the narrowest of the three, so a basket holding
                   it should read under the funds that carry the rule best. The predicted width is
                   0.047 points a day (results/PR-032-power.json), so ACCEPT needs the estimate
                   above about +0.024 and a zero-containing interval is NULL, not INCONCLUSIVE:
                   the author puts ACCEPT and NULL near even, with REJECT the outside case.
                   Per fund: IWM 0.076 wide, DIA 0.080, EFA 0.038
if H1 were TRUE:   an interval wholly above zero
minimum detectable effect:  0.034 points a day (0.00034, about 8.5% a year) - the difference this
                   window detects with 80% power: the predicted half-width, 0.0237, x (1.96 + 0.84)
                   / 1.96. It sits a fifth BELOW what PR-031 measured on SPY before publication
                   (0.043 a day), so an effect of that size is readable here and a smaller one may
                   not be.
                   From `run_pr032.py --power`, widths only under
                   `power_pr019.assert_no_effect_leaked`
power floor:       0.08 points a day end to end (0.0008), PR-031's; it gates NULL only
```

## 4. Data

```
funds:         IWM (small caps), DIA (thirty large caps, price-weighted), EFA (developed markets
               outside the US). Chosen for what they are: liquid enough to quote a one-cent
               spread, minutes back to 2016, and unread by anything in this repository. SPY and
               QQQ are PR-031's and are not in the basket
store:         one-minute bars from Alpaca's sip feed, adjustment=split, fetched by
               tools/fetch_minutes.py into the same scratchpad MinuteStore PR-031 used; the
               knowledge instant is recorded with the result
as_of:         2026-09-19T21:38:38.502579-05:00 - the fetch's last knowledge_time; 2,693
               sessions of each fund, none served empty
window:        2024-05-13, the first session after the paper appeared, to 2026-09-18. Sessions
               before it are read only to warm the rule up (14 sessions) and as the secondary
               reading
window rationale: the question IS the period since publication - CHARTER A-003's standing caution,
               and AGENTS.md 19.4's first reason, a regime the rest of the window does not
               contain. The secondary reading over 2016-2026 carries the same rationale as
               PR-031's
country:       USA and developed markets
survivorship:  none - three index funds trading throughout
costs:         PR-031's, unchanged: $0.005 a share a side (net), $0.0045 (the paper's), $0.01
               (cost_adverse); commission 0 (DR-039)
```

## 5. Method

* **The rule is `PR-031`'s module, not a copy.** `run_pr032` imports `run_pr031`'s noise area,
  leverage, decision and day walk and changes none of them: the noise area from the last 14
  sessions' moves from the open, long at each HH:00/HH:30 from 10:00 when above both the upper
  bound and the session's VWAP, decided on the minute that ENDS there and filled at the next
  minute's open, flat at the close, sized `min(4, 2% / 14-day volatility)`.
* **The basket is equal capital**: each session's return is the mean over the funds that read that
  session. A fund the store does not hold for a session does not weigh the others down, and it
  counts against the complete share.
* **The statistic.** The mean daily net return since publication; a 95% moving-block bootstrap over
  calendar months, block 3, 10,000 resamples, seed 20260922.

### 5a. The split, and what it buys

```
split:           none - PR-031's rule with every constant fixed, on three funds chosen before
                 any of their minutes was read
split buys:      nothing a split could buy: nothing is selected or tuned here
perturbations:   paper - the paper's $0.0045 a share a side
                 cost_adverse - a whole cent a share a side. Section 6 reads it on an ACCEPT
                 gross - no cost
```

**Diagnostics, printed and never read by §6:** each fund's own reading, annualised return,
volatility, Sharpe ratio, CAGR, worst drawdown, sessions traded and mean leverage; holding each fund
over the same sessions, price only; every excluded session by fund and reason; and **`SPY` through
this tool's own loader against `PR-031`'s published estimate since publication**
(`run_pr032.repeats_pr031`) — the rule and the walk are `PR-031`'s module, so only the loading and
the windowing are new, and a defect in either moves every fund at once.

## 6. Decision rule

**For the basket since publication, in this order:** `REFUSED` under 500 sessions, 24 months, or 90%
of the window's sessions read; `COST_FRAGILE` if the interval is wholly above zero and the
cost-adverse reading's is not; `ACCEPT` wholly above; `REJECT` wholly below; `INCONCLUSIVE`
containing zero and wider than 0.08 points a day; `NULL` containing zero inside it.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *the rule still earns on funds it was never fitted to, in the years since it was
  published*: `SPY`'s two flat years are one fund's, and a live paper trial is worth specifying.
* `REJECT` — *it loses on them*: the rule is done, and `PR-031`'s `ACCEPT` belongs to the years
  before publication.
* `NULL` — *it earns within about ±10% a year of nothing on them*: the same reading `SPY` gave,
  on three more funds, which is the decay the `CHARTER` warned about.
* `INCONCLUSIVE` — *not established at this width.*
* `COST_FRAGILE` — *it earns at half a cent and not at a cent.*

**Nothing is built on any branch.** There is no intraday loop (`CHARTER` A-003 §4), and whether to
specify one stays the owner's call.

## 6a. Trials

**Three** — `IWM`, `DIA` and `EFA`. The basket is the verdict's reading of them, not a fourth
configuration. The tool reads **146** with `PR-031`; three more take it to **149** and the hurdle
from **2.661 to 2.668** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** any other fund, including `QQQ` at a second look; any change to the
rule's constants; a basket weighted any other way; the short leg.

## 7. Stopping rule

One fetch of the minutes, repeated only to fill sessions that failed. One run at the pinned
knowledge instant. No fund, costing or window tried after the first result is seen.

## 8. Sample

```
minimum:       500 sessions across at least 24 months, and 90% of the window's sessions read
power floor:   0.08 points a day end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by `REJECT`, `NULL`, `INCONCLUSIVE` or `COST_FRAGILE`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* `SPY` through this tool's loader differing from `PR-031`'s published estimate since publication
  by more than 1e-12 — the same code on the same store, so a difference is a defect here;
* more than a tenth of any fund's sessions unread;
* a realised half-width outside half to twice §3's predicted 0.0237;
* a mean leverage outside 1 to 4 on any fund.

**What would NOT settle anything:** an `ACCEPT` read as *a working strategy to run*. It would say
the rule still earns on three funds in a backtest; what it licenses is the same specification
`PR-031` licensed, with better grounds.

## 10. Amendments

### A-1 — 2026-09-19, AFTER the run: the verdict's word, not its branch

The runner wrote `"verdict": "null"`, a fifth word in a vocabulary of four (`accept`, `reject`,
`inconclusive`, `refused`; `run_pr024.TOKEN`, and `tools/verify_studies.py` enforces it). A `NULL`
branch reports as `INCONCLUSIVE` with the branch beside it, as `PR-026` did. `run_pr031.TOKEN`
invented the word and this study inherited it. **Fixed with a test**; the branch, the decision rule
and every number are untouched, and the re-run reproduced the first run's cells to the digit.
