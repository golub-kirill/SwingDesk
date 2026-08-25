# PREREG: Is a −15R drawdown limit distinguishable from ordinary sequence luck?

```
id:      PR-009
date:    2026-08-08
author:  owner
status:  registered
blocked: no trade log exists - see section 4
```

## 0. Refutation-family check

- **searched:** `docs/prereg/` for any prior drawdown study — none; `registry/course_index.yml` for
  drawdown topics (M69's `Максимальная просадка`, M49-T765 the size-reduction ladder, M93's risk
  system); `docs/decisions/` for a prior threshold — `DR-007` §3.7 sets −15R and explicitly names
  this study as the thing that should replace it.
- **not a re-run of anything.** PR-001, PR-005 and PR-002 all measure *selection* — which
  instruments a rule picks and how they then behave. This measures the **sequence** property of one
  trade set, which none of them touched.
- **relationship to `DR-007`:** that record chose −15R from an argument, disclosed the argument as
  its weakest, and named the measurement that would replace it. This is that measurement. A study
  registered to check a number the same project already published is the case the refutation-family
  check exists to permit rather than to block.

## 1. Question

`validation.max_allowable_drawdown` triggers the ratified kill criterion `k.drawdown_pause`. It is
set to −15R with provenance `assumed:DR-007`. **Is that threshold outside the range a zero-edge
strategy produces from ordinary sequence luck, or inside it?**

A threshold inside the ordinary range fires on noise and will be disabled by whoever it annoys. A
threshold far outside it never fires and protects nothing. The question is where −15R sits.

## 2. Hypothesis

**H:** the maximum drawdown of the base strategy's realised trade sequence is **not** extreme
relative to the distribution of maximum drawdowns obtainable by permuting the same trades — i.e. the
realised drawdown is one draw from a sequence-luck distribution rather than evidence of a distinct
failure mode.

This is the null the study expects to fail to refute. `WALKFORWARD_SPEC.md` §4, topic 1097, states
the mechanism the hypothesis rests on: **shuffling the order of the same trades leaves total R
unchanged and changes maximum drawdown completely.**

## 3. Prediction

Registered before the data is drawn:

| | Prediction |
|---|---|
| The realised max drawdown falls **inside** the central 90% of the permutation distribution | expected |
| The distribution's **95th percentile** is the defensible threshold | the deliverable |
| That percentile is **larger in magnitude than −10R** | expected, and it is the reason −10R was rejected in `DR-007` §3.7 |
| Whether it is larger or smaller than **−15R** | **no prediction registered** — this is the number the study exists to produce, and predicting it would be the data-snooping the protocol forbids |

## 4. Data — and the reason this cannot run yet

**The trade log does not exist.** `docs/prereg/results/PR-005.json` stores aggregates only: per-arm
trade counts, mean and median R, hit rate, MFE, MAE and gap-exit counts. There is no per-trade
record anywhere in the repository.

That is a finding in its own right and it is recorded here rather than worked around.
`BACKTEST_PROTOCOL.md` §3 transcribes the course's required evidence for a strategy claim:

> Protocol, code/data version, trade log, OOS/walk-forward report и paper/live gate.

**Five artefacts, and the trade log is the third. No reported study in this project has one.** The
results are honest and their supporting detail is not reconstructible, which is precisely what the
requirement exists to prevent.

Compounding it: `tools/run_pr005.py` is a network tool. It fetches the symbol directory from
nasdaqtrader and bars from Yahoo, so re-running it today draws a **different** window end, different
fetch failures and possibly a different sampled universe. Permuting that trade set would answer a
different question than the one §1 asks, and reporting it as though it answered this one would be
the substitution this protocol exists to forbid.

**So step 1 of this study is to persist a trade log**, by reproducing PR-005 under its recorded
constants:

```
seed 20260802 · sample 320 · period 10y · min-bars 2000
window 2016-08-01 → 2026-07-31 · holdout from 2023-07-28
SMA 50/200 · pivots 3/3/2 · ATR 14 · trigger lookback 20 · ATR stop ×2.0 · max holding 20 bars
commission 0.005/share · slippage 5bps · stress ×3
```

**If the reproduction does not match PR-005's reported aggregates, that mismatch is the result of
this study and PR-009 reports `inconclusive`.** It would mean a reported figure in this project is
not reproducible, which is a larger and more useful finding than a drawdown percentile, and it must
not be buried in a footnote of a study about something else.

## 5. Method

1. Reproduce and persist the trade log (§4). Compare its aggregates against `PR-005.json`; a
   mismatch stops the study here.
2. Take the ungated arm (`NONE`) — 2,629 trades at 1× costs in the primary period, per the reported
   result. The gated arms are out of scope: `k.drawdown_pause` governs the account, not one filter.
3. Build the realised equity curve in R, in trade order, and record its maximum peak-to-trough
   decline.
4. **Permute the trade order 10,000 times** with a recorded seed, rebuilding the curve each time and
   recording each maximum drawdown. `validation.monte_carlo_runs` = 10,000 (`DR-007`), and
   `validation/studies/trend_performance.py` already contains a seeded permutation harness to
   extend.
5. Report the distribution: 50th, 80th, 90th, 95th and 99th percentiles, plus where the realised
   value falls in it.
6. Repeat at 3× costs (`validation.stress_cost_multiplier`), because the threshold has to hold under
   the cost regime that made the strategy clearly negative.

**Statistic:** maximum peak-to-trough decline of the cumulative net-R curve, in R.

**What is deliberately not done:** no optimisation over the threshold, no search across arms, no
choice of percentile after seeing the numbers. The 95th is registered here as the deliverable.

## 6. Decision rule

| Outcome | Verdict | Consequence |
|---|---|---|
| Realised drawdown inside the central 90% of the permutation distribution | **ACCEPT** the null | the realised figure is sequence luck; the 95th percentile becomes the threshold |
| Realised drawdown outside it | **REJECT** the null | the sequence has structure the permutation destroys — a separate finding, and the threshold question reopens |
| Reproduction fails (§4) | **INCONCLUSIVE** | report the reproduction failure; no threshold is set from this study |

In the ACCEPT case a **superseding decision record** sets `validation.max_allowable_drawdown` from
the measured percentile, citing this study. `DR-007` is frozen and may not be edited
(`decisions/README.md` §3 rule 2); the new record names it as superseded for that one parameter.

Whether the resulting parameter may carry provenance `validated:PR-009` is settled here in advance:
**it may not.** The study measures a distribution; choosing the 95th percentile from it is still a
decision, so the value stays `assumed:<the new DR>` and cites PR-009 as its basis. A measurement
underneath a choice does not make the choice a measurement.

## 7. Stopping rule

One run. 10,000 permutations at each cost regime, both fixed here. No re-running with a different
seed if the answer is inconvenient — and the seed is recorded in the result so a second run is
detectable.

## 8. Sample

The ungated arm's 2,629 primary-period trades, as reported by PR-005. `validation.backtest_min_trades`
is 200 primary / 60 holdout per arm (`DR-007`), which this clears by an order of magnitude. If the
reproduction yields materially fewer trades, §4's mismatch rule applies before any sample question.

## 9. What would refute this

- The realised drawdown sitting in the extreme tail of the permutation distribution — the sequence
  would then carry information the permutation destroys, and a threshold set from the permuted
  distribution would be the wrong instrument.
- The reproduction failing (§4).
- **Survivorship, as always.** The trade set contains no delisted instruments, so the drawdown
  distribution is drawn from survivors and is optimistic by an unmeasured amount. This does not
  invalidate the method; it bounds the claim, and the result will carry the disclosure like every
  other result here.

## 10. Amendments

~~None.~~ Any amendment after the data is drawn downgrades this to exploratory
(`PREREG_TEMPLATE.md` §3). **No data has been drawn — this study has never run** — so the amendment
below is a correction to the registration rather than a downgrade.

---

**2026-08-25, first amendment — the threshold this study is named after is not the one in force,
and both of §4's blockers have moved.**

**1. `validation.max_allowable_drawdown` has never been −15R.** §1 says it *"is set to −15R with
provenance `assumed:DR-007`"*. The registry holds **20, unit percent of equity, provenance
`owner`** and has held that since 2026-08-08 — the day this study was registered. `DR-007` §3.7
proposed −15R and called it *"the weakest of the fifteen"* and *"the one to argue with"*; the owner
had already argued it, and the 2026-08-09 reconciliation ruled that `owner` outranks
`assumed:DR-007` on this registry's provenance ladder, so §3.7 is **superseded**
(`docs/decisions/README.md`, `RECONCILIATION_PLAN.md` §4 item 3).

Fourteen of `DR-007`'s fifteen were adopted as proposed, and this study quotes three of them
correctly — `validation.monte_carlo_runs`, `validation.stress_cost_multiplier` and
`validation.backtest_min_trades` all match the registry today. **The one it got wrong is the one it
is about**, and it is the one `DR-007` itself invited an argument over.

**2. What that costs the design, stated rather than waved at.** §7's statistic is *"maximum
peak-to-trough decline of the cumulative net-R curve, in R"*. The live threshold is in **percent of
equity**, which needs an account-equity concept the store does not hold — `TODO.md` §1 records that
fills are recorded per position and nothing aggregates them. So the two are not the same measurement
in general.

**Today they coincide exactly, and that is worth knowing before anyone redesigns this.**
`risk.per_trade_pct` is 1.0 percent of equity and `account.equity` is a static registry value that
nothing recomputes from realised P&L, so 1R **is** 1 percent of equity and the pause sits at **20R**.
The method survives with the threshold restated; the title, §1, §3's table row and §6's branches all
name −15R and would need to name 20R. That is a registration change, not a run.

**3. §4's stated blocker is discharged.** *"The trade log does not exist"* — it does:
`docs/prereg/results/PR-005-trades.csv`, 26,351 trades, published 2026-08-16 with its provenance
beside it. **A different blocker replaced it and is not resolved:** that published log no longer
reproduces from a fresh replay, because seven bars arrived three hours after publication. `TODO.md`
§5 states the three options and they are the owner's.

**4. This study still may not run**, for a reason neither §4 nor this amendment is about: new
research is suspended by the 2026-08-16 council ruling, overridden by the owner for `PR-013` and no
other study.

**Nothing here is a result, a value or a verdict.** The registration is corrected forward because a
study named after a superseded threshold would measure something nobody uses.
