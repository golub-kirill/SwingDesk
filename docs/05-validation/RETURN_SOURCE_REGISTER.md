# Return source register

**Status:** drafting · **Tier:** 5 (validation) · Created 2026-09-20 by `DR-047`

**A source of return is an economic reason someone is paid.** It is not a rule, not an indicator and
not a holding period — those are the expressions a source can take. `DR-047` §3.1 made the source
the unit of research; this file is the list, and **every pre-registration's §0 must name the source
it tests and link to its row here**.

**Why a register rather than a memory.** Every configuration evaluated raises the deflated-Sharpe
hurdle for every study after it — 166 of them, hurdle 2.70 sd. A family re-opened because nobody
remembered it was closed is paid for twice, and the second payment buys nothing. So a closed source
carries **what was measured** and **what would reopen it**, and reopening is a deliberate act with a
stated trigger rather than a fresh idea that happens to rhyme with an old one.

**Statuses:** `open` — never tested here · `measured` — tested, result recorded, may be extended ·
`closed` — tested enough that another look needs the stated trigger · `operating` — a card exists.

---

## 1. Closed

### 1.1 Breakout and trend definitions — `closed`

**The claim:** price crossing a level or a moving average predicts continuation.
**Measured:** `PR-001` (four trend definitions), `PR-005` (five regime arms). The edge does not
survive this project's cost model; `DR-040` later showed why — the entries paid 37.8 bps a side at
the open.
**Reopens on:** a cost structure an order of magnitude cheaper than measured, or a venue where the
fill is the benchmark price. Not on a new definition of "trend".

### 1.2 Short-horizon reversal (5-20 sessions) — `closed`

**The claim:** recent losers bounce.
**Measured:** `PR-021`, `REJECT` — the bottom decile of five-day losers trails `SPY` by about 25
points a year net, beta 1.45, drawdown −41%. Gross it does not beat its own universe.
**Reopens on:** nothing at this horizon. A different holding period is a different source and gets
its own row.

### 1.3 Stop, target and holding-period variation — `closed` as a source

**The claim:** how a position is managed creates return.
**Measured:** `PR-016`..`PR-019`, nineteen registrations. `PR-019`'s best configuration (4 ATR, no
target, 60 sessions) had no demonstrated positive expectancy, and `PR-019b` found the index earned
more over the same days. `PR-018` showed exits move the distribution more than selection does —
which is the point: **management reshapes a return, it does not create one**.
**Reopens on:** a source that has passed its first test under `DR-047` §3.2. Then risk management
is the second study, and it is welcome.

### 1.4 Four-name discovery books — `closed` as discovery

**Measured:** `PR-015` — the four-name book's intervals are 1.4× to 3.9× wider than the decile's,
**and the ~130-name decile itself does not separate from zero either, gross.**
**Reopens on:** never as a discovery instrument. A small book is an implementation question, asked
after a source is established on twenty names or more.

### 1.5 Published intraday rules — `closed`

**The claim:** a rule published in a paper keeps working.
**Measured:** `PR-031` reproduced Zarattini-Aziz-Barbon on `SPY` (8.5% a year, Sharpe 1.01) and
found **0.45% a year since publication**; `PR-032` found it absent on `IJR`, `DIA` and `EFA`, funds
it was never fitted to — and absent there **before** publication too.
**Reopens on:** a rule whose economic mechanism predicts where it should NOT work, tested there
first. A backtest that reproduces is not evidence; a mechanism that forbids is.

### 1.6 Execution research ahead of a signal — `closed` as a research line

**Measured:** `PR-024` (+0.311% a trade from moving the entry to 15:55 — the largest single
improvement this project has measured), `PR-025`, `PR-030`. All of it on a card whose own net is
zero.
**Reopens on:** `DR-047` §3.8's order — a source that has passed out-of-sample and cost robustness.
The findings themselves stand and are reused; what is closed is doing this work FIRST.

---

## 2. Measured, and what is left of them

### 2.1 Cross-sectional relative strength in the admitted universe — `measured`, negative

**Measured:** `PR-012`..`PR-020`, ~120 configurations. Break-even at best; the decile it selects
from does not separate from zero; the universe itself trails `SPY` by 3.02% a year as a style gap.
**What is left:** the universe question, not the signal question. The admitted pool is an
equal-weighted mid-cap book (`MDY` correlation 0.982) and was always judged against a mega-cap
index. A cross-sectional test on a universe that MATCHES its benchmark has not been run.

### 2.2 Index timing — `measured`, a risk dial

**Measured:** `PR-022` (Faber 10-month SMA on `SPY`, Sharpe 0.625 against 0.615), `PR-023`
(GTAA-5). Drawdown improves, excess return does not appear.
**What is left:** nothing as an edge. As a risk overlay on a source that pays, it is a second study.

### 2.3 The overnight/intraday decomposition — `operating`

**The claim:** the compensation for holding equity risk accrues while the market is shut, and the
session is where the risk is traded rather than paid for. Published since 2008.
**Measured:** `PR-033` (five funds: the night pays, the session barely does, and the night still
loses to holding on the basket), `PR-034` (`ACCEPT` on `IJR`+`VB`: 13.8% a year at Sharpe 1.06
against holding's 0.59, 11.7% at a cent a share, the last 590 sessions its best), `PR-035`
(`COST_FRAGILE`: adding an `SPY` day leg returns 18.9% against the index's 15.7%, but the margin is
+0.35% at a cent), `PR-036` (**the epoch objection answered**: over 2004-2015, a window no
study here had read, the night compounded at **10.6% against holding's 8.8%** with a −21.1%
drawdown against −58.8%, and the session arm lost 80% peak to trough — `COST_FRAGILE`, because a
whole cent a share touches zero at that decade's price level).
**Status:** `CARD-002` specifies it; nothing is built. **It is exempt from `DR-047` §3.9** because
its population is funds, not individual equities.
**What is unmeasured and decisive:** what the closing and opening auctions actually give. No paper
account can answer it — Alpaca's paper fills are simulated, so a paper trial would confirm this
project's own cost model because it IS that model. **The owner ruled on 2026-09-20 that the first
twenty sessions run at minimum REAL size** (one or two shares a fund); an auction clears at one
price whatever the size, so the minimum measures it exactly.

**And the cost assumption may be too harsh rather than too kind.** The half-cent a share came from
`PR-031`, where fills met the continuous book. `cls` and `opg` orders clear at the auction price and
pay no spread, so if the twenty sessions show that, 13.8% a year is the pessimistic reading and the
gross 16.0% is nearer the truth.

### 2.4 Intraday momentum on index funds — `closed`, see 1.5

---

## 3. Open — never tested here

Ranked by what `DR-047` §3.1 asks: a mechanism, a literature, and an instrument this project can
actually reach.

### 3.1 Industry and sector momentum — `open`, and NOT answerable on eleven funds

**The claim:** sectors trend as a block, and a large part of individual stock momentum is industry
momentum rather than firm-level (Moskowitz and Grinblatt, 1999).

**It was first in this queue and it is not any more, because somebody measured.** The reason it was
ranked first still holds — eleven sector funds inherit no survivorship problem, need no
point-in-time index membership, and the data was a single fetch away. But *cheapest to TEST* and
*answerable* are different properties, and only the first had been checked.

**Measured 2026-09-21, before any registration**
(`docs/decisions/measurements/sector-momentum-power-2026-09-21.json`, 0 trials): the ranking was
replaced by a coin, so the proxy carries the design's turnover, costs, concentration and calendar
and none of its signal. What it reports is how wide an interval the design produces — and a width
carries no sign, which is what made it safe to run first.

| the book | effect it could separate from zero, a year |
|---|---|
| 2 of 11 | 4.56% |
| 3 of 11 | 3.18% |
| 4 of 11 | 2.32% |
| 5 of 11 | 2.16% |
| the top tercile (3, then 4 as the pool grows) | 2.86% |
| 6 of 11 | 1.67% — **and six of eleven is 55% of the pool, which is barely a selection** |

**Against a literature claiming about two points a year.** Every book that is still a selection sits
above it, over 320 months and 27 years. **The binding constraint is the CROSS-SECTION — eleven
candidates — and not the book size or the window**, so no long-only variant rescues it.

**So `PR-037` was not registered and no trial was spent.** Every configuration evaluated raises the
deflated-Sharpe hurdle for every study after it, and a design that cannot detect its own claimed
effect buys nothing with that. `tools/run_pr037.py` is the finished instrument, tested and
mutation-tested, waiting for a pool wide enough to use it on.

**Reopens on:** a wider cross-section — industry-level funds rather than eleven sector ones, or the
repaired stock universe of §3.2 grouped by industry. Not on a new formation window, a new book size
or a longer history: those were measured and none of them is what binds.

### 3.2 Medium-term cross-sectional momentum in a matched universe — `open`, and now first

**The claim:** the classical 12-month-minus-1 effect (Jegadeesh and Titman), measured on a universe
that matches its benchmark rather than one that trails it by 3 points a year.

**Why it inherits first place from §3.1**, rather than being promoted on enthusiasm: §3.1's
measurement says the constraint that binds is the width of the cross-section, and this is the only
source in this register with a wide one. Hundreds of names rank against each other, so the same
2-point effect that eleven funds cannot separate is separable here — the arithmetic that made §3.1
unanswerable is the arithmetic that makes this one worth the trial.

**Blocked by:** point-in-time index membership and delisted prices. The delisted half is a fetch
this project can run (19,188 inactive assets at the vendor, `BACKTEST_PROTOCOL` §6); the membership
half needs a source. **That fetch is the single highest-value unblocked task in this register.**
**How it fails:** a 2025 paper on the classic 12-1 rule in the S&P 500 reports a negative net result
after costs; long-only large-cap momentum is a factor tilt with multi-year droughts.

### 3.3 Time-series momentum across asset classes — `open`

**The claim:** an asset's own past twelve months predicts its next month (Moskowitz, Ooi and
Pedersen).
**Reachable as:** ETFs standing in for futures — and that substitution is itself a limitation to
declare, because the funds carry financing and tracking differences the futures do not.

### 3.4 Volatility-managed exposure — `open`, and second-order by construction

**The claim:** scaling exposure down when realised volatility is high raises the Sharpe ratio
(Moreira and Muir; Daniel and Moskowitz on momentum crashes).
**Why it is not first:** it is a management overlay, and `DR-047` §3.2 puts management after a
source has passed its own test.

### 3.5 Turn-of-month and FOMC-window effects — `open`, low priority

**How it fails:** roughly 130 and 80 independent events respectively against a 2.70 sd hurdle. The
sample is the problem before the effect is.

---

## 4. Rules for using this file

1. **Every pre-registration's §0 names its source and links here.** A study whose source is not in
   the register adds the row in the same commit.
2. **A closed source is reopened by its stated trigger, in a decision record** — not by a study that
   simply registers it again.
3. **A row records what was MEASURED, not what was concluded in conversation.** Every number here
   cites the study that produced it.
4. **Adding a source costs nothing. Testing one costs trials**, and the budget is the reason this
   list is ranked rather than exhaustive.
