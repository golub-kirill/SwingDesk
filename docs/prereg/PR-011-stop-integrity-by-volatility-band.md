# PREREG: does a 2 x ATR stop behave as the risk model assumes, on names whose ATR is a large fraction of their price?

```
id:            PR-011
date:          2026-09-04
author:        owner (direction), agent (drafting)
status:        registered
```

**Read §0 and §0b before the design.** This study's id was reserved on 2026-08-22 for a broader
question — *should instrument classes that cannot hold a stop be screened out* — and that question
splits in two. One half is contaminated by a result its drafter has already seen and is deferred to
`PR-011b`; this file registers the half that is not.

## 0. Refutation-family check

```
searched:     docs/prereg/ across every local branch (AGENTS.md 10.2) and docs/decisions/, plus
              HANDOFF.md 7 "Closed by evidence - do not re-open". Terms: stop, ATR, volatility,
              screen, filter, instrument class, gap.
found:        PR-001   trend definitions select different instruments          REFUTED
              PR-005   those populations then behave the same, net of costs    REFUTED
              PR-013   cross-sectional relative strength separates returns     inconclusive
              DR-003   the liquidity rule - price, ADTV and history floors     ratified
              DR-006   the portfolio risk block, incl. the sector degeneracy guard
              HANDOFF.md 7: "New entry filters | Same family, same evidence"   CLOSED
distinct because:
              The closed family is filters that claim to select BETTER TRADES - a screen justified
              by the expectancy it produces. This study's primary statistic is not expectancy and
              its hypothesis is not about alpha. It asks whether the RISK MODEL IS VALID on a
              subset of names: whether a 2 x ATR stop, once placed, caps the loss near 1R the way
              `trade_management/sizing.py` assumes when it divides the risk budget by
              `entry - stop`. A screen justified here removes names on which the sizing arithmetic
              MISSTATES RISK, which is a different claim from one that removes names because they
              lose money.
              It also starts from a LIVE observation rather than a backtest fit. The live path has
              been refusing this shape on a real instrument since 2026-08-24, and each refusal is
              in `journal.duckdb`:
                SELECT instrument_id, COUNT(*) FROM decisions WHERE reason_code = 'STOP' GROUP BY 1;
              Nothing was fitted to produce those rows.
```

## 0b. What this study's drafter has seen, and what follows from it

`PREREG_TEMPLATE.md` rule 3 downgrades a study to exploratory when it is designed after seeing data
that bears on its own question. `PR-013` §0b is the precedent for declaring that in advance rather
than having it noticed later.

**Seen, and it bears on the deferred half only.** `TODO.md` §5 records that excluding bond ETFs and
foreign-market ETFs flips mean net R from −0.0691 to +0.0362 **on the fitted data**, together with
the gap rates that motivated it. That is an EXPECTANCY result about a CLASS screen. A study that
tested a class screen on expectancy, designed by someone who had read that, could not be
confirmatory.

**So the class screen is deferred to `PR-011b` and declared exploratory in advance**, before it is
written. It is indexed as not written, with the contamination recorded here so that whoever writes
it inherits the constraint rather than rediscovering it.

**Seen, and it does NOT bear on this half.** The motivating observation for THIS study is that the
condition exists in production: a name whose price round-tripped from about $4 to $91 to $10 in four
weeks left ATR(14) carrying a spike the price no longer had, so `close − 2 × ATR` went below zero and
the live guard refused it. That observation establishes that the condition occurs. **It says nothing
about this study's outcome measure** — nobody has measured how a stop behaves once placed on such a
name, at any band, and no number in this design was chosen by looking at one.

**Therefore: confirmatory.** If that reading is wrong the study is worth less, not more, so it is
stated here where a reader can disagree with it before the run rather than after.

## 0c. What the literature says, ranked

`AGENTS.md` §16 rule 2: rank the source and say which rank was used. §10.3's boundary holds — these
supply *method*, *calibration* and *known limitations*, and none of them is evidence about this
system's parameters.

| Rank | Source | What it says, and what it does to this design |
|---|---|---|
| peer-reviewed | Kaminski & Lo, *When do stop-loss rules stop losses?*, **Journal of Financial Markets** 18 (2014) 234–254 | Under a random walk a simple stop-loss **always reduces** expected return; it adds value only in the presence of momentum. **This is why the study does not measure expectancy.** A stop's job here is to bound a loss, and asking whether it pays is a question this literature says is answered by the return process rather than by the stop |
| peer-reviewed | Ang, Hodrick, Xing & Zhang, *The Cross-Section of Volatility and Expected Returns*, **Journal of Finance** 61:1 (2006) 259–299, with international and further US evidence by the same authors in the **Journal of Financial Economics** (2009) — that follow-up's volume and pages are **not** verified here | Stocks with high idiosyncratic volatility earn **abysmally low** average returns — over 1% a month between extreme quintiles. **This is a confound and is recorded as one.** A high-ATR%-of-price screen is a crude idiosyncratic-volatility screen, so if it were judged on returns it could "work" for a reason that has nothing to do with stops. Judging it on stop overshoot instead is what keeps the two apart |
| practitioner | Trading-education material on ATR% bands (LuxAlgo, QuantifiedStrategies and similar), 2024–2026 | A common practitioner scale calls ATR% of 3–6% high and above 6% very high, and sizes positions as `risk / (ATR × multiple)` — the same arithmetic `sizing.py` uses. **Used only to fix the band EDGES in §5** so they are conventional rather than invented, and marked as resting on the bottom rank. It is worth noting how far outside it the motivating case sits: `2 × ATR ≥ price` is ATR% ≥ 50, an order of magnitude beyond what this rank calls extreme |

**Where the course stands.** `screen.atr_pct_band` is `named_in: M33-T0484` — the course names the
concept and supplies no number, which `AGENTS.md` §8 says makes it a pre-registration or a ruling
and never a guess. `AGENTS.md` §16 governs what its naming licenses: an `Operational Course Rule`,
not an `Empirical Result`.

## 1. Question

Over the admitted US universe, does a 2 × ATR(14) protective stop **overshoot** — the realised exit
landing worse than the stop that was placed — materially more often, and by materially more, on
names whose ATR is a large fraction of their price than on the rest of the universe?

## 2. Hypothesis

`sizing.size_long` divides the risk budget by `entry − stop` and calls the result 1R. That is only a
risk measure if a stop-out costs about 1R. The claim: **on names in the top ATR%-of-price band that
assumption fails**, so admitting them makes the position-sizing arithmetic misstate risk rather than
merely produce a worse trade.

Components and values this concerns:

- `exit.atr_stop_multiple` = **2.0** (`assumed`) and `exit.max_holding_period` = **20**
  (`assumed`) — pinned here as study constants, never read from the registry at run time, so the
  study cannot change meaning the day either is ratified (`ExitPolicy`'s own docstring, and
  `PR-005`'s precedent);
- `screen.atr_pct_band` — **`unset`**, `read_by: none`, `named_in: M33-T0484`. This study informs
  it and **does not set it**: a value is the owner's ruling or a later study's outcome.

## 3. Prediction

Stated numerically before the run. The statistic is defined in §5.

| | TRUE | FALSE |
|---|---|---|
| Mean overshoot, top band vs bottom band | difference **≥ 0.25R**, 95% CI excluding zero | difference below 0.25R, or its CI includes zero |
| Overshoot in the bottom band | small — the risk model holds where it is supposed to | as large as the top band's, in which case the screen discriminates nothing |

**Why 0.25R, derived rather than picked.** `risk.max_concurrent_positions` is **4** and
`risk.max_open_risk` is **4R**, both ratified (`DR-006` §8.3, owner 2026-08-22). An extra 0.25R on
each of four positions is one full R — a quarter of the book's entire ratified risk budget, lost
outside the model that is supposed to bound it. Below that, an overshoot is real and is absorbed by
the cap's own margin; at or above it, the cap is not the cap.

**If both look the same the study cannot inform.** They do not: the FALSE column is a live
possibility, because a stop is placed at a distance already scaled by that name's own ATR. The
sizing arithmetic widens the stop exactly as volatility rises, and whether that self-correction
holds all the way into the top band is the open question.

## 4. Data

```
universe:      the DR-003 liquidity rule evaluated AS OF each signal date - `universe.min_price`
               5.00 USD and `universe.min_bar_history` 250 bars, both `assumed:DR-003`, with
               `universe.min_adtv_20d` 5,000,000 USD per day, which is `owner`. Never today's
               admitted set applied to an older window (PR-013 A-2's correction, inherited).
window:        the bar store's full extent at the pinned snapshot, less the ATR and history
               warm-up. Derive the dates rather than quoting them here:
                 SELECT MIN(session_date), MAX(session_date) FROM bars;
snapshot:      the bar store's latest knowledge_time at run time, pinned and recorded with the
               result. Two stores, two clocks (AGENTS.md 12) - the classification store is not
               read by this study at all.
costs:         slippage 25 bps per side (DR-005, MEASURED). Commission is ZERO and that is a
               fact about the broker rather than an omission - DR-009 established the fee
               structure as no commission plus a 1.5% CAD-USD conversion, and DR-010 left that
               standing while reshaping the per-share allowance into the price-aware
               risk.costs_bp_* pair. This study is US-only, so the conversion fee is not engaged.
               ***None of it enters the primary statistic***: overshoot is measured in R against
               the placed stop, and both legs of that comparison sit inside the same fill. The
               net figure is reported beside it and decides nothing.
survivorship:  ABSENT, and here the direction is the opposite of the usual one. The directory is
               today's, so names that delisted are missing - and a delisted name is
               disproportionately one whose volatility exploded, which is exactly this study's
               top band. Every other study in this repository is biased UPWARD by survivorship;
               this one is biased toward FINDING NOTHING. A null result is therefore weaker
               evidence than it looks, and that is stated before the run rather than after.
```

## 5. Method

```
unit:          one STOP-OUT EVENT. Not one name, not one trade of a strategy.
entries:       a CENSUS, not a strategy. On every 20th session (non-overlapping, matching the
               pinned 20-bar holding period) every admitted name is entered at the NEXT session's
               open. There is no trigger and no gate.
               This is the design's load-bearing choice: with no entry rule there is no entry
               FAMILY, so the study cannot be the refuted "new entry filter" in different
               clothing, and its answer does not depend on a strategy this project has already
               refuted.
exit:          ExitPolicy(2.0, 20) - the protective stop first, the time exit second, exactly as
               `trade_management/exits.py` orders them. A bar that both breaks the stop and
               completes the period is a stop-out.
bands:         ATR(14) / close at the SIGNAL bar, cut at fixed edges taken from the practitioner
               scale in 0c so they are conventional rather than invented:
                 B1  <= 3%        B2  3-6%        B3  6-10%        B4  10-50%
                 B5  >= 50%   - the arithmetic-break band, where 2 x ATR meets or exceeds the
                                price and `sizing.py` refuses outright. Its trades are counted
                                and reported and are NOT part of the primary comparison, because
                                the live system never opens them.
overshoot:     for a stop-out, (stop - realised exit) / (entry - stop), in R. Zero when the stop
               is honoured at its price; positive when the session gapped through it.
               `ExitDecision` already distinguishes STOP from STOP_GAP, so the two are separable
               without inference.
statistic:     the MEAN overshoot per band, and the difference between B4 and B1. 95% bootstrap
               CI resampling SIGNAL DATES, 10,000 resamples, seed 20260904.
               Resampling dates and not events, because every name entered on one date shares
               that date's market move: the cross-section is one observation, not a thousand
               (PR-013 §5's correction, inherited).
split:         NONE.
split buys:    NOTHING, and that is the answer the form asks for. No parameter is fitted and none
               is selected from any window: the multiple, the period, the band edges and the
               horizon are all fixed above. PR-012 paid 70% of its judged sample for a protection
               it had nothing to protect (PREREG_TEMPLATE 7); this study declines to repeat it.
selection rule: NONE.
perturbations: WALKFORWARD_SPEC 4, run: cost stress at 3x, reported on the net figure only - it
               cannot move the primary statistic, which is pre-cost by construction.
               NOT run, and named rather than omitted: a sweep of the stop multiple, a sweep of
               the band edges, a sweep of the holding period. Each is a further shot at the data
               and none is taken.
```

## 6. Decision rule

```
accept if:     mean overshoot in B4 exceeds B1's by >= 0.25R AND the 95% CI on that difference
               excludes zero.
reject if:     the CI includes zero, OR the difference is below 0.25R.
both negative: if BOTH bands show mean overshoot indistinguishable from zero, the verdict is
               REJECT and the reason is recorded as "the stop holds everywhere measured", not as
               "no difference". A screen that removes names on which nothing goes wrong buys
               nothing, and the two readings prescribe opposite actions.
               If both bands overshoot LARGELY and similarly, the verdict is also REJECT, and
               the finding is about the 2 x ATR stop rather than about any band - it would say
               the risk model is optimistic universally, which is a DR-012 question and not a
               screening one.
inconclusive:  everything else, including a difference that clears 0.25R with a CI that also
               spans it.
REFUSED:       reserved for the sample rule in section 8. REFUSED is not INCONCLUSIVE
               (AGENTS.md 12): one says the study could not look, the other that it looked and
               could not tell.
```

**No verdict sets a value.** An `accept` means the band edge is worth an owner ruling on
`screen.atr_pct_band` or a follow-up study that locates it; it does not locate it. The edges here
were chosen to be conventional, not to be right.

## 6a. Trials

**One trial.** The primary comparison is a single configuration: B4 against B1 at the edges fixed in
§5, on the pre-registered statistic. The other bands are reported as description and no decision
rests on them; the cost stress is a sensitivity on the same configuration and costs no additional
trial (`TRIAL_BUDGET.md`: a cost stress is not a new shot at the data).

`b.deflated_sharpe` is computed on the **cumulative** trial count across the whole programme
(`registry/criteria.yml`, ratified 2026-08-08) and **a refused study still spends its trials**
(`AGENTS.md` §12). Derive the running count with `python tools/trial_budget.py`; never quote one
from here.

## 7. Stopping rule

The study ends when every admitted name has been walked over the full window at the pinned snapshot.
No early stop, no extension, and the window is not contingent on the result.

**What it costs, because that is the argument against running it casually.** The research suspension
was lifted entirely by the owner on 2026-08-30 and the lift is *permission, not a plan*: every study
competes with Track A for the same evening window and the same single-writer stores (`ADR-0004`), and
Track A sits inside a ratified 120-day timebox. This study reads the bar store only, so it must run
against a **copy** and outside the 18:30 and 19:30 passes (`AGENTS.md` §12's rule about long jobs).

## 8. Sample

```
minimum:       200 stop-out events in B4 and 200 in B1.
               DERIVED BY ANALOGY, and the analogy is declared rather than hidden. b.min_sample is
               100 CLOSED TRADES per strategy card and a census stop-out is not a card's trade.
               What that criterion protects against is an interval too wide to act on; the same
               argument applies here, and the number is DOUBLED because this is a comparison of
               two populations against each other rather than one population against zero - which
               is the accounting PR-012 got right and PR-013 explicitly did not need.
if not met:    the study reports the measurement and REFUSES a verdict (PR-012's precedent). It
               does not widen a band, extend the window or pool bands to reach the floor: each of
               those is a design change made after seeing the sample, which rule 3 downgrades.
expected:      NOT stated, because nobody has counted. The count is derivable before the run and
               deriving it is step 1 of the runner rather than a guess written here.
```

## 9. What would refute this

A window in which B4's mean overshoot is within 0.25R of B1's, or in which the CI on the difference
includes zero. Either observation says a 2 × ATR stop is honoured about as well on a volatile name
as on a quiet one — that the sizing arithmetic's self-correction holds — and that a volatility band
screens on something other than risk-model validity.

**It would not refute the FAMILY**, and the boundary matters. `2 × ATR ≥ price` (band B5) is an
arithmetic impossibility rather than a hypothesis: those names cannot be sized at all and the live
path already refuses them. A null result here leaves that refusal exactly where it is. What it would
refute is the wider claim — that the boundary belongs earlier, at screening, and further out than
the point where the arithmetic breaks.

## 10. Amendments

Appended, dated, never edited in place. An amendment after data is seen is recorded as such and
downgrades this study to exploratory (rule 3).

*(none)*

---

## Appendix: `PR-011b`, reserved here

**Question:** should whole instrument CLASSES whose stops are unenforceable — bond ETFs and
foreign-market ETFs, whose underlyings trade while the US market is shut — be screened out?

**Status: not written, and exploratory in advance when it is.** §0b has the reason: the class
evidence in `TODO.md` §5 includes a sign flip observed on the fitted data, so a class study judged
on expectancy cannot be confirmatory whoever writes it. Two mechanisms are already stated there and
both are mechanical rather than statistical — a bond ETF's 2 × ATR stop is a fraction of a percent
of price while round-trip costs eat most of it, and a foreign-market ETF's underlying moves while
its stop cannot be hit.

**One thing whoever writes it must not inherit:** the gap rates that motivated it (bond ETFs 27.4%,
foreign-market ETFs 23.3%, US single names 7.5%) were migrated into `TODO.md` from a session handoff
that has since been deleted, and **no tool in this tree re-derives them**. They are a prior, not a
measurement this repository can currently reproduce. `PR-011b` measures them; it does not cite them.
