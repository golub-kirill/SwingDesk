# PREREG: bought as last week's biggest losers and held one to five sessions, do US stocks beat SPY after costs?

```
id:            PR-021
date:          2026-09-13
author:        Claude, on the owner's ruling of 2026-09-13 choosing the next strategy CLASS -
               "принимаю рекомендацию, делай краткосрочный откат 1-5 дней" - after the
               relative-strength family was measured out at selection, exit and sizing
               (EVIDENCE_SUMMARY 20.9)
status:        reported   (2026-09-13 - results/PR-021-report.md)
verdict:       REJECT. Half A selected the five-session hold; on half B the book trails SPY by
               -24.95 points a year [-38.82, -10.09] net of DR-005, wholly below zero, and every
               other hold is further below. Before costs it is -3.67 against SPY and +1.59
               [-8.29, +11.89] against its own universe - no reversal edge to pay for. Break-even
               against SPY is negative at every hold on both halves, so no execution time
               rescues it. Section 9's four checks held; width 28.73 against 32.78 predicted
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md`, `TODO.md` §§4–5, `DR-040`. The censuses live
in `HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-013` | whether relative strength separates forward returns at all | `INCONCLUSIVE` — every gross interval contains zero |
| `PR-015` | five signals in a four-name book at a 20-session hold, one of them `REVERSAL_21` | `INCONCLUSIVE` — `REVERSAL_21`'s book [−72.25%, +14.84%] a year; its decile +7.04% [−9.67%, +25.12%] gross |
| `PR-020` | the top relative-strength decile held 5 sessions against its own universe | `INCONCLUSIVE`, and §9 refused even that; its `REJECT` branch was registered as *"the short-term reversal the literature documents"* and did not fire |
| `DR-040` §9, `execution-time-2026-09-06` | what a fill costs by time of day | exploratory — **26.5 bps a side at the open, 4.0 at the close**, 2026 medians |
| `EVIDENCE_SUMMARY` §20.9 | whether sizing explains the gap to the index | it explains half and flips nothing: holding `SPY` beats the family per dollar |

**distinct because the class is new here.** Every study above bought WINNERS — relative strength,
momentum, the 52-week high — or low volatility. The one reversal arm, `PR-015`'s `REVERSAL_21`,
formed on 21 sessions (Jegadeesh's monthly horizon), held 20 and traded four names. **No study has
formed on the last WEEK, held one to five sessions, or measured a book of losers per dollar against
`SPY` over the same days.** The refutation family is empty; this is its first member.

**What is known in advance, stated first.** The window's calendar span was read by `PR-019`..`PR-020`
out of sample, for a different selection — the top relative-strength decile, held through a stop.
**No file in this tree holds the return of a loser decile at any hold.** The power estimate
(`tools/power_pr021.py`) loaded half A of the names only and reported interval widths, turnover and
the yearly cost turnover implies — properties of the construction, not of what the book earns.

## 1. Question

On US common stocks the live liquidity rule admits, does a book that buys each session's bottom
decile by five-session return at the next open, and holds it H sessions — H in 1..5, chosen on half
A of the names — earn more than `SPY` over exactly the same sessions, net of `DR-005`'s cost on the
turnover it actually trades, on half B of the names?

## 2. Hypothesis

**H1.** At the hold half A selects, half B's annualised mean of `book net − SPY` has an interval
wholly above zero: buying last week's losers beats the index after paying the opening minute's
spread.

**H0.** It does not.

No parameter is concerned and `CARD-001` is untouched. The signal has no component; it is
implemented in `tools/run_pr021.py` and that is a declared reimplementation risk — if H1 survives,
the next step is a component and a card, not a parameter. What each verdict licenses is in §6.

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean over half B's sessions of (book net return - SPY return over the same
                   open-to-open session), x252, in percentage points a year, at the hold half A
                   selects
predicted:         REJECT or INCONCLUSIVE, never ACCEPT - and the cost arithmetic decides which
                   before any return is seen. The power estimate measured the book buying 38.0%
                   of itself a session at a one-session hold and 16.8% at five, which DR-005
                   charges 47.9 and 21.2 points a year. At a half-width near 16.5 the five-session
                   book REJECTS if its gross excess over SPY is under about 5 points a year, is
                   INCONCLUSIVE between about 5 and 38, and ACCEPTS only above 38. The
                   literature's weekly reversal in liquid US stocks after 2000 is a few points a
                   year gross and survives costs only among the largest names with turnover
                   managed (de Groot, Huij & Zhou 2012); this universe reaches down to a $5m-a-day
                   floor and trades at the open. Centre of the prediction: gross 0 to +10, net -11
                   to -21 points a year against SPY. The author's reading of other work, not this
                   store's
if H1 were TRUE:   an interval wholly above zero - a gross edge over SPY above about 38 points a
                   year at the five-session hold, which no published reversal result in liquid US
                   stocks after 2000 approaches
minimum detectable effect:  16.4 points a year at the five-session hold, 16.4 to 16.9 across the
                   holds - the predicted half B half-width of book net - SPY, from
                   tools/power_pr021.py (PR-021-power.json): half A only, 1,002 sessions, the
                   verdict estimator's own bootstrap
power floor:       20 points a year end to end, fixed in tools/run_pr021.py before the power
                   estimate ran. It gates NULL only - section 6 says why
```

```bash
PYTHONPATH=$PWD/src python tools/power_pr021.py --report
```

| hold | sessions | cohort | bought a session | cost, points a year | width vs `SPY` | width vs pool |
|---|---|---|---|---|---|---|
| 1 | 1,002 | 110 | 38.0% | 47.9 | 33.42 | 24.70 |
| 2 | 1,002 | 110 | 27.0% | 34.0 | 33.72 | 24.44 |
| 3 | 1,002 | 110 | 22.0% | 27.7 | 33.71 | 23.84 |
| 4 | 1,002 | 110 | 18.9% | 23.9 | 33.20 | 23.10 |
| 5 | 1,002 | 110 | 16.8% | 21.2 | 32.78 | 22.40 |

**No hold and no contrast is readable at the floor, and that is written down before the data.**
Every interval against `SPY` is about 33 points wide against the 20 the floor allows; against the
book's own pool, 22 to 25. The width is mostly the market's: a book of last week's losers carries
more beta than the index, and the pool removes the market without removing the losers' own
volatility. **So `NULL` is unreachable at this precision: the study can establish the SIGN of a
large net effect and cannot establish that one is absent.** `SPY` stays the primary contrast because
it is the owner's question; the pool is a diagnostic.

**Neither way of buying precision is taken.** A longer window is the reason `AGENTS.md` §19.4 names
as not holding — *"the intervals are too wide otherwise"*. Dropping the name split would double the
names and barely move a width the market owns, and it would spend the only protection the
selection of a hold has.

**The break-even cost is registered as a diagnostic, and it is the number the owner can act on.**
`gross excess over SPY / (2 × turnover)`, in bps a side, printed beside `DR-040`'s measured curve —
26.5 at the open, 7.5 at 10:00, 5.8 at 11:00, 4.0 at the close. **§6 never reads it.** If the class
fails at the open and breaks even below the open's cost, the next registration is the same book
executed later in the day, and `DR-040` §4 already says why that is not the same trade at a lower
price.

## 4. Data

```
store:         data/bars.duckdb and data/directory.duckdb, byte-identical copies taken
               2026-09-13 (the live files were unchanged since 11:17 that day)
as_of:         2026-09-13T11:00:01.727280-05:00 - the bar store's latest knowledge_time
window:        48 months back from as_of (AGENTS.md 19): open-to-open sessions from 2022-09-13
               to 2026-09-10, the last with a following open. MEASURED span reported beside it
country:       USA
universe:      the LIVE liquidity rule (application.universe.rule_from_registry: price >= $5,
               20-session ADTV >= $5m read universe.adtv_lag_sessions = 3 back, 250 bars of
               history) at each formation's own bar - not the lag-0 rule PR-013..PR-020 used,
               because the owner ruled the lag one number for live admission and for studies.
               Half A admitted 1,907 stocks at least once in the window
stocks only:   the directory's is_etf flag as known at as_of. A fund, or a name the directory
               does not carry, is excluded and counted - in half A 2,832 funds and 31 unknown.
               The directory holds pulls only since 2026-08, so the flag is today's; a name
               whose type changed is misclassified, which a static attribute makes rare
survivorship:  ABSENT and material, and worse for THIS book than for any before it: a loser is
               likelier than a winner to die, and a name that died is missing from the store.
               The book is biased UPWARD - toward H1
adjustment:    split-adjusted, not dividend-adjusted, on both legs. SPY's dividend is missing
               from the benchmark, which favours H1 by about a point and a half a year
costs:         DR-005, 25 bps a side (costs.slippage_model) - which DR-040 measured as right for
               the opening minute this book trades in - charged on MEASURED net turnover, the
               round trip at purchase. Commission zero (costs.commission_model). Regulatory
               fees excluded, about 1% of the slippage term, which favours H1
```

## 5. Method

* **Formation.** At each session's close, the admitted stocks of one half, ranked by their own
  close-to-close return over the last five sessions, most negative first; ties on the instrument
  id. The bottom decile, `int(pool × 0.10)` over every admitted name, is that session's cohort; a
  name without a price five sessions back counts toward the size and is never bought. A formation
  with fewer than 100 admitted names in its half forms no cohort.
* **Holding.** A cohort is bought at the next session's OPEN and sold at the open `H` sessions
  later. The book holds the last `H` cohorts at `1/H` of the capital each, equal-weighted within, so
  every trade is at an open and a name that a leaving and an arriving cohort share is kept. A thin
  formation's share sits in cash for its hold, counted.
* **Costs.** Turnover each session is the weight BOUGHT — `Σ max(0, w_today − w_yesterday)` over
  the book's target weights, `run_pr014.turnover`'s convention — charged `2 × 25` bps.
* **The statistic.** Per session, `book net − SPY`, both open to open; the mean over the window
  ×252, in points a year, arithmetic. A 95% moving-block bootstrap over sessions, block 10 (two
  weeks: consecutive sessions share holdings, never the period a return covers), 10,000 resamples,
  seed 20260913 — `run_pr014.moving_block_bootstrap`.

### 5a. The split, and what it buys

```
split:           NAMES, sha256(instrument_id)[0] % 2 (run_pr015.half_of). Each half forms its
                 own decile from its own admitted stocks, over the same 48 months. AGENTS.md
                 19.6: at forty-eight months the name split is the default
selection rule:  the hold with the LARGEST half-A mean of book net - SPY at 1x costs. An exact
                 tie selects nothing and the verdict is INCONCLUSIVE
split buys:      the selection. Five holds are tried and one is kept; half B, which neither the
                 selection nor the power estimate ever loads, is the only place a verdict may be
                 read
perturbations:   cost_stress_3x - the book at three times DR-005, SPY unchanged. Section 6 reads
                 its point estimate on an ACCEPT only
```

**Diagnostics, printed and never read by §6:** the gross excess over `SPY`; the book net and gross
against its own admitted pool, the second being the signal before any cost; `SPY`'s and the pool's
own levels; the book's own net return; the break-even cost a side against `SPY` and against the
pool; beta to `SPY`; the book's worst drawdown beside `SPY`'s; the worst session; turnover and
cohort size; every hold on both halves.

## 6. Decision rule

**Read on half B at the selected hold, by `run_pr021.branch_for`, in this order:**

```
REFUSED        fewer than 500 sessions, or more than 5% of formations too thin to form a cohort.
BOTH_NEGATIVE  the interval lies wholly above zero AND the book's own net return lies wholly
               below zero - it beat an index that fell. PREREG_TEMPLATE rule 8.
COST_FRAGILE   the interval lies wholly above zero and the point estimate at three times DR-005
               is not above zero. An edge a plausible error in the cost erases is not one.
ACCEPT         the interval lies wholly ABOVE zero.
REJECT         the interval lies wholly BELOW zero.
INCONCLUSIVE   the interval contains zero and is wider than the 20-point floor: too blunt to say
               the effect is absent. The likeliest outcome after REJECT, per section 3.
NULL           the interval contains zero, inside the floor. Rule 10. Unreachable at the width
               section 3 predicts, and kept so a realised width under the floor can still say it.
```

**The floor gates `NULL`, not the sign, and `PR-019b` is why.** It read −0.1543R [−0.2930,
−0.0501], wholly below zero, and its §6 refused the reading because the interval was wider than the
floor — *"INCONCLUSIVE, for precision and not for sign"*. A 95% interval that excludes zero answers
the sign whatever its width, and half B was never seen by the selection, so a wide interval is
imprecise about the SIZE and not biased about the SIGN. What width cannot do is say an effect is
absent — rule 10's `NULL`, the one branch the floor must gate. Earlier studies put the floor first;
this one registers why it does not, before the data.

**The report's `verdict:` token** is `ACCEPT`, `REJECT`, `INCONCLUSIVE` or `REFUSED`; `NULL`,
`BOTH_NEGATIVE`, `COST_FRAGILE` and a tied selection are reported under `INCONCLUSIVE` with the
branch named first in the same line.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *on names the selection never saw, buying last week's biggest losers at the open beat
  the index net of the opening minute's cost.* The next step is a component, a card and paper
  trading; the survivorship bias in §4 means it is **not** evidence of profit.
* `REJECT` — *at the cost of trading at the open, the class loses to the index.* The break-even
  diagnostic says whether a later execution could change that, and a later execution is a new
  registration.
* `INCONCLUSIVE` — *the net result's sign is not established at a 16-point half-width.* Not a lever
  to build on, and not evidence that none exists.
* `NULL` — *any net edge over the index is smaller than about 10 points a year.*

## 6a. Trials

**Five** — one per hold, the owner's range. The cumulative figure and the hurdle are the tool's,
never typed here:

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

It read **115** before this registration; five more take it to **120** and the hurdle from **2.58**
to **2.59** sd(SR).

**Registered as NOT run, each with its reason**, because each is another configuration:

* **ETFs included** — the `CHARTER` universe. A leveraged or inverse fund sits in the loser tail by
  construction and turns the book into a bet on the index's own week (§4).
* **A buy/hold band** — the strongest turnover cut in the literature (Novy-Marx & Velikov 2016), and
  it makes the hold emergent; the hold is what this study varies.
* **Execution later in the day** — `DR-040`'s lever. The break-even diagnostic says whether it is
  worth registering.
* **Other formation lengths, and residual or industry-adjusted reversal** — each a different signal.

## 7. Stopping rule

One pass, one pinned `--as-of`. No interim look, no early stop, no hold, universe, cost or formation
tried after the first result is seen.

## 8. Sample

```
minimum:       500 sessions in half B's window, at most 5% of formations thin, 100 admitted
               stocks per half per formation
power floor:   20 points a year end to end on half B's interval, gating NULL
if not met:    report the measurement and REFUSE to read the window as evidence
```

The power estimate measured **1,002 sessions and a cohort of 110 stocks** on half A; half B shares
the sessions.

## 9. What would refute this

**H1 is refuted** by `REJECT` or `NULL`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* half B's realised width more than 1.5 times half A's predicted one, which would mean the halves
  are not the same instrument and the MDE above did not describe the verdict's;
* more than 1% of the book's name-sessions unpriced — a book the prices cannot follow;
* a typical cohort under 50 names, which would make a decile book a handful of bets.

**What would NOT settle anything:** an `ACCEPT` read as *it makes money*. §4 biases the book upward
twice over, and whether a strategy survives real fills is `PR-006`'s question.

## 10. Amendments

None.
