# PREREG: under the RATIFIED exit, does the ratified screen change the distribution of trade outcomes — win rate, mean R and the tails — measurably, over a decade, in and out of sample?

```
id:            PR-016
date:          2026-09-07
author:        Claude, at the owner's instruction 2026-09-07 — "доля выигрышей, средний R,
               форма хвостов на ратифицированном ... minimum za last 10y s vozmozhnostu progona
               po specific date, minimalnym limitom (~ ne menshe 200 dney mezhdu datami)
               iis-oos and needed safety measures"
status:        reported   (2026-09-08 - results/PR-016-report.md)   PRELIMINARY
verdict:       ACCEPT by §6's rule - the paired difference in mean net R excludes zero on both
               windows, +0.096R [+0.057, +0.137] in sample and +0.088R [+0.018, +0.158] out.
               AND BOTH ARMS LOSE MONEY: the ranked arm -0.100R a trade against a break-even
               win rate of 54.22%, the control -0.192R. §6 reads the DIFFERENCE and never asks
               whether either arm is profitable, so the sentence this licenses is that the
               screen LOSES LESS than no screen. The finding that is not the verdict: the
               ratified 1R target caps every winner and no loser, so the distribution is
               left-skewed - skew -2.41 on the control against PR-005's +1.61 without a
               target - and the screen's largest measurable effect is on that left tail,
               p1 -1.735R against -2.863R, not on the winners, where p95 is identical.
               PRELIMINARY until DR-042 §8 closes; the ambiguous share is 0.05%
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md` §§8–16, `TODO.md` §5. The censuses live in
`HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-005` | do five trend gates change a breakout strategy's return? | **`reject`**. 26,351 trades, and the trade log survives |
| `PR-012` | does the four-position book with caps earn anything? | **`inconclusive`** — missed its own trade minimum |
| `PR-013` | does relative strength separate forward returns? | **`inconclusive`**; all six gross intervals include zero |
| `PR-014` | at what holding period does the ratified rule earn a net excess? | **`inconclusive`**, downgraded to exploratory 2026-09-07 |
| `PR-015` | does any of five long-only signals earn a net excess at 20 sessions? | **`inconclusive`**; nothing separates from zero, and neither does the decile |
| `measure_exit_surface` | expectancy over the stop × target grid | exploratory; **unselected entries**, so it measures the exit against the market and no edge |
| `measure_target_reachability` | how often is a target reached in 20 sessions? | exploratory; unselected entries |

**Distinct because no study in this repository has ever run the ratified EXIT.** `ExitPolicy`
implemented the protective and time slots and said so in its own docstring; the profit slot did not
exist until `DR-042`, today. `exit.target_r_multiple` was ruled 1R by the owner on 2026-09-01
(`DR-029`) and lived only in `broker/submit.py`. **Every backtested trade in this project ran the
stop and the clock while every live trade also carried a take-profit leg.**

`measure_exit_surface` is the closest prior and is distinct twice over: it sweeps a GRID of stop and
target values rather than measuring the ratified pair, and its entries are unselected, so it cannot
say anything about the screen. `PR-015` is the closest study and is distinct in its unit: it measures
a four-position BOOK's periodic return; this measures a TRADE.

**And the quantity is new.** `Trade` has carried `net_r`, `mfe`, `mae` and `exit_reason` since
`PR-005`, and no study has ever reported their distribution — win rate, tails, and the payoff ratio
that makes a win rate readable. `EVIDENCE_SUMMARY` carries annualised excesses and nothing else.

## 1. Question

Under the ratified exit — protective stop at `2.0 × ATR(14)` fixed at entry, take-profit at `1.0 R`,
time exit at the close of session 20, stop checked first — does the ratified screen
(`screen.relative_strength_rule`: the top decile by `ByMarketPathStrength` at `rs.lookback` 126)
produce a **different distribution of trade outcomes** from taking every liquid name, measured over
2016-01-04 … the latest session, and does the difference replicate out of sample?

**The unit is one trade.** Not a book, not a portfolio return. Nothing this study finds licenses a
statement about what an account would have earned.

## 2. Hypothesis

**H1.** The ranked arm's mean net R exceeds the unselected arm's, on both the in-sample and the
out-of-sample window, with the paired bootstrap interval on the difference excluding zero.

**H0.** It does not — the screen changes the distribution of outcomes by less than this design can
detect, and the ratified exit's outcome distribution is a property of the market rather than of the
selection.

**Why the difference and not the level.** A win rate of 44% is unreadable on its own. Against a
control that took every liquid name and got 41%, it is a measurement of what the screen contributes.
The level is reported for the owner's own question and is never the test.

**The arithmetic that makes H1 falsifiable, stated before the run.** A target 1R away against a stop
1R away needs a win rate above **50%** net of costs. Every winner is capped at +1.0R and the losers
are not capped below — a gap can take more than the stop. `PR-005`'s log, at the same stop and the
same hold and WITHOUT the target, shows the shape this study is testing against: 41.07% wins, mean
win +1.493R, mean loss −1.045R, payoff 1.429, break-even 41.17%, mean net R **−0.0023R**. **The
ratified 1R target is a bet that the win-rate gain exceeds the payoff-ratio loss, and nobody has
measured it.** That is what §5's registered diagnostic re-prices.

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean net R, ranked arm minus unselected arm, paired on entry months
minimum detectable effect:  0.14 R.  From PR-005's own trade log, which ran the same stop and
                   the same hold over the same decade: the standard deviation of MONTHLY mean
                   net R there is 0.5444 R across 120 entry months. A 95% interval half-width
                   is 1.96 x 0.5444 / sqrt(k) for k independent monthly clusters - 0.10 R at
                   120 clusters, 0.14 R at 60, 0.17 R at 40. This study splits the decade in
                   two, so ~60 months per window is the design point and 0.14 R is what it can
                   see. An effect smaller than that will not be detected by this instrument and
                   a null here says nothing about it.
power floor:       0.20 R end to end on the DIFFERENCE interval in either window. Wider than
                   that and the instrument could not have detected an effect worth trading, so
                   the study reports the measurement and refuses to treat the window as
                   evidence. Registered here, before any number exists.
also predicted:    the ratified target CUTS the payoff ratio. Under PR-005's two-slot exit the
                   mean win is +1.493R with p90 at +1.98R and p95 at +2.78R; a 1R target
                   removes that right tail by construction. So the break-even win rate should
                   RISE from about 41% to about 50%, and the study is a test of whether the
                   realised win rate rises further than that. This is registered as a
                   prediction so that a confirmation of it cannot later be presented as a
                   finding of the study.
```

## 4. Data

```
store:         data/bars.duckdb, daily bars, series RAW, read at a single --as-of instant
window:        2016-01-04 .. the latest stored session (default). 2016-01-04 is where
               probe_alpaca_delisted found delisted coverage to begin, so a future
               survivorship repair reaches exactly this far and the windows stay comparable
country:       USA
universe:      the ratified liquidity rule DR-003 - min price $5.00, min ADTV $5,000,000,
               20-session ADTV window, 250-session minimum history - judged at each formation
               date's own bar, never today's
history floor: 252 sessions before any formation date, applied to EVERY arm so the control and
               the hypothesis draw from one pool
benchmark:     SPY, rs.benchmark, ratified
adjustment:    the store is SPLIT-adjusted and NOT dividend-adjusted. Measured 2026-09-07
               rather than assumed: AAPL across its 2020-08-31 four-for-one and NVDA across
               its 2024-06-10 ten-for-one show no discontinuity. An ex-dividend gap is
               therefore a real down-move that a real stop would also see, which is the
               realistic treatment; the cash it pays is missing from every return here, so
               every arm is understated by the universe's dividend yield over 20 sessions
survivorship:  ABSENT, and MATERIAL. Measured 2026-09-07: of the 2,598 instruments in this
               store with a decade of history, 2,598 are still trading. Not one dead name.
               The store was built from today's directory backwards, so every arm is
               optimistic by an amount this run cannot measure. b.survivorship_caveat is
               ratified and the disclosure travels with every number.
               BACKTEST_PROTOCOL 6's claim that no free source serves delisted paths was
               refuted on 2026-09-05 by probe_alpaca_delisted - Alpaca feed=sip returned full
               daily histories from 2016-01-04 for 7 of 8 names tried. Repairing this study's
               universe with them is a SEPARATE change and this study does not pretend to
               have done it.
```

## 5. Method

**Entries.** Formation dates are every 20th session of the window, starting once 252 sessions of
history exist. On each, the liquidity rule is applied at that date's own bar and the admitted names
form the cross-section. A date whose cross-section holds fewer than `MIN_NAMES_PER_DATE` names is
skipped and counted.

  * **`unselected`** — every admitted name enters. The control.
  * **`ranked`** — the top decile by the live `ByMarketPathStrength`, through `select`, which is
    the same code path the running system uses. A study that reimplements the ratified rule can
    drift from it (`PR-014` amendment A-2's reason).

Entry fills at the **next** session's open, after slippage. The engine is
`validation/backtest/engine.py` unchanged: at index `i` it may read `bars[:i+1]` and it fills at
`i + 1`, and the loop stops one bar short of the end. The entry rule is injected as an
`EntryTrigger` (`OnDates`) that reads nothing but the session date, so the look-ahead guarantee is
the one `PR-005` runs under.

**Exits — the ratified three slots, and the bar-order rules that make them simulable.** A daily bar
records four prices and no times. Each assumption below is the pessimistic one, and `DR-042` records
them:

1. a session opening below the stop fills at the **open**, not the stop;
2. a session opening above the target fills at the **target**, not at the better open — the
   favourable gap is not credited;
3. intraday, the **stop is checked before the target**; a bar reaching both is flagged and the count
   is reported;
4. the stop is checked before the time exit, unchanged.

**Costs.** 25 bps a side (`DR-005`) plus $0.005 a share, inside every reported figure. `net_r`, never
`gross_r`.

**Statistics.** Per arm and window: win rate, mean and median net R, standard deviation, mean win,
mean loss, payoff ratio, **break-even win rate = 1 / (1 + payoff)**, skew, the p1–p99 ladder, worst
and best, mean MFE and MAE, the gap-loss share, the exit-reason mix and the median holding period.

**Intervals.** Moving-block bootstrap, 10,000 resamples, seed 20260908, **resampling entry MONTHS in
blocks of 3**. The trade is not the independent observation — trades opened in the same month share
one market — so an i.i.d. resample over trades would report an interval several times too narrow,
which is the flattering direction. Three months ≈ one quarter, the shortest span over which a regime
is conventionally treated as persistent. Künsch (1989), an authored import (`AGENTS.md` §10.3).

**The difference is PAIRED**: both arms are resampled on the same drawn months, so a month that was
bad for everything is drawn for both or neither.

**Registered diagnostics — reported, and never read by §6.** The device is `PR-015` amendment A-1's.

  * `ranked_top4` — the top FOUR by rank, which is what `risk.max_concurrent_positions` would
    actually take. Reported because it is the owner's real book size; not read, because it is a
    third selection rule and §6 registered two.
  * `unselected_two_slot` — the control's own signal DATES under the exit `PR-005` ran (**dates,
    not realised entries — amendment A-1**), no target. This is
    what says whether the ratified target bought anything, and it is a diagnostic rather than an arm
    because choosing a target is `DR-029`'s act, not this study's.

**Perturbation.** Cost stress ×3, **re-simulated rather than re-priced**: at 3× the entry fill is
worse, so the stop sits somewhere else and different bars take it. Subtracting a number afterwards
would price a trade the arm never made. Run on both arms and every window.

**The window knob.** `--from` / `--to` are refused closer than **200 trading sessions** apart (owner
instruction, 2026-09-07; sessions rather than calendar days, because 200 calendar days hold about
137 sessions and the instruction was about the size of the sample). Every non-default window is
appended to `results/PR-016-windows.jsonl`. A study whose sample can be resliced until it looks good
and whose reslicings nobody counts is `data snooping` with a command-line flag
(`BACKTEST_PROTOCOL` §3).

## 6. Decision rule

Read on **`ranked` minus `unselected`, mean net R**, and on nothing else.

```
ACCEPT        both windows meet §8's sample rule, both clear §8's power floor, and BOTH
              paired difference intervals lie entirely above zero.
REJECT        both windows qualify, both clear the floor, and BOTH intervals lie entirely
              below zero. PREREG_TEMPLATE rule 8's both-negative branch: a screen that
              reliably does worse than no screen is a finding, not an absence of one.
INCONCLUSIVE  anything else - a window that misses the sample rule, an interval wider than
              the power floor, or one window agreeing and the other not.
```

`ACCEPT` sets no parameter. It would license one sentence — *the ratified screen changes the
outcome distribution of the ratified exit by a measurable amount* — and a follow-up study, on the
book, would be needed before anything traded differently.

## 6a. Trials

**Two**, declared here and entered in `trial_budget.py`.

  1. the `ranked` arm — one selection rule evaluated;
  2. `unselected_two_slot` — the same signal dates under a DIFFERENT exit, which is a second
     configuration and not a cost restatement of the first.

**The control spends nothing**, for `PR-008`'s and `PR-010`'s reason: it carries no signal, so no
edge is being claimed by it. `ranked_top4` spends nothing either — it is a reading of the same
ordering the `ranked` arm already computed, at a different cutoff, and §6 never reads it. **That is
a claim a reader may reject**; if it is rejected the count is three, and the deflated-Sharpe hurdle
moves by the difference.

The 1× / 3× cost pair is one stress on the same configuration, not a second shot — `PR-005`'s
counting rule, unchanged.

## 7. Stopping rule

The run is one pass over the store at one `--as-of` instant. There is no interim look, no early
stop, and no second run at a different instant except to reconstruct a published sample for
attribution — which `AGENTS.md` requires and which reports the reconstruction, never a fresh verdict.

## 8. Sample

```
minimum:       200 trades AND 24 entry months in EACH window. Both, not either: PR-012 missed
               a verdict on a trade minimum alone, and 100,000 trades inside six months is six
               observations of one market rather than a large sample
power floor:   0.20 R end to end on the difference interval, registered in §3
if not met:    the study reports the measurement and REFUSES to treat the window as evidence,
               the way PR-012 did. A window that cannot support an interval, or supports one
               too wide to inform, is a finding about the instrument and saying so is the point
```

Expected, from the calendar: about **130 formation dates** over the decade, roughly 75 before 2022
and 55 after, and about 120 distinct entry months. The unselected arm should carry on the order of
10⁵ trades and the ranked arm about a tenth of that; the binding constraint in both windows is
**months**, not trades, which is the whole reason the bootstrap resamples months.

## 9. What would refute this

**H1 is refuted** if neither window's difference interval excludes zero above the floor. That is a
concrete, reachable observation, and `PR-013`, `PR-014` and `PR-015` all produced its analogue.

**H1 is damaged without being refuted** if the difference is positive in-sample and absent out of
sample. `PR-014` produced exactly that shape and the report must say so in those words.

**What would NOT refute H1:** a mean net R near zero in BOTH arms. That is a statement about the
exit and the market, not about the screen, and §6 does not read it. It would, however, be the most
consequential thing this study could find, and §5's `unselected_two_slot` diagnostic is what makes
it readable.

**What would refute the STUDY rather than the hypothesis:** the control failing to reproduce
`PR-005`'s two-slot distribution to within the differences the two designs actually have — a
different entry rule, 25 bps against 5, and a wider store. The report must show that comparison.

## 10. Amendments

### A-1 — the two-slot diagnostic shares signal DATES, not realised entries

**2026-09-08, before this study's own data produced any result.**

§5 called `unselected_two_slot` *"the same control entries under the exit `PR-005` ran"*. **It
cannot be.** The step and the holding period are both 20 sessions, so a position that runs to its
time exit is still open on the next formation date, the engine records `POSITION_OPEN`, and that
entry never happens. A position the target closes early frees its name in time.

Measured while smoke-testing the pipeline on a SYNTHETIC store of random prices, 2026-09-08:
**1,868 two-slot entries against 2,535 control entries from the same 27 dates.**

**This is a property of the exit being compared, not a defect.** A target that frees capital sooner
takes more trades, and that is part of what a target does. The amendment is therefore to the
DESCRIPTION and to how the diagnostic may be read: both entry counts are reported, and the
diagnostic is never read as a paired comparison.

**§6 is untouched.** It reads `ranked` against `unselected`, which run the same exit and are
genuinely paired. Rule 3's clock is not started by this: it comes from the harness's behaviour on
random prices, not from this study's data.

### A-2 — the 252-session floor is per INSTRUMENT; the benchmark's own gate is `rs.lookback`

**2026-09-08, before this study's own data produced any result.**

§4 says *"history floor: 252 sessions before any formation date, applied to EVERY arm so the
control and the hypothesis draw from one pool"*, and that is unchanged: `DR-003`'s `min_history`
(250) is evaluated for every name on every date, and a series shorter than `252 + 20 + 1` is never
loaded.

The first cut of the runner ALSO applied 252 to the benchmark's calendar, which charges the same
floor twice — an instrument's requirement imposed on `SPY`, which needs only its own `rs.lookback`
of 126 to be rankable against. Caught by arithmetic that did not match: the first run reported
**113 formation dates where 2,522 sessions at a 20-session step give 126**, and 13 dates are
exactly 260 sessions.

Corrected to `rs.lookback`. **No arm's admission changes** — only the first year of the window
stops being discarded. Registered here because a reader comparing §4 to the code would otherwise
find two numbers and no reason.

**And what it does not fix.** The store holds ten years of bars (`--period 10y`, owner ruling
2026-09-06), so even without the double floor the first entry sits a lookback inside the earliest
bar. §4's window is the one asked for; the result file now carries `measured_span`, which is the
one obtained, and says whether it meets the ten-year instruction. It does not.
