# DR-005: The validation programme's thresholds

```
date:       2026-08-08
status:     proposed — owner ratification required
parameters: validation.* (all fifteen)
components: none - these govern the validation programme, not a computation
```

Fifteen parameters, all `unset`. The consequence is not theoretical: `registry/criteria.yml` ratifies
`k.drawdown_pause`, whose trigger reads *"realised drawdown exceeds
`validation.max_allowable_drawdown`"* — a ratified kill criterion whose verdict is invariant across
every input the system can produce. `REQUIREMENTS.md` `REQ-VALIDATION-001` names that exact shape as
the thing that must not reach runtime, and `RULE_SPEC.md` §7 row 8 records it as the one rule in this
tree with no discriminating pair.

**This record proposes values so the programme can evaluate. It proves nothing.** Every value below
becomes `assumed:DR-005`, which travels with any number computed from it. Setting a threshold is a
modelling choice, not evidence — the same rule `DR-004-cost-model.md` states about costs, and the
reason `PARAMETER_REGISTRY.md` §5 makes provenance travel adjacent to the number.

---

## Decision

Four of the fifteen ratify what a reported study already used. Those are the strong ones, and they
are marked. The rest are authored, and §3 says how weak each is.

| Parameter | Value | Anchor |
|---|---|---|
| `validation.is_oos_split` | **0.50 / 0.20 / 0.30** train / validation / test | **used by PR-002** — 1257 / 502 / ~755 sessions |
| `validation.stress_cost_multiplier` | **3×** both cost components | **used by PR-005**, and already stated in `DR-004-cost-model.md` |
| `validation.monte_carlo_runs` | **10,000** resamples | **used by PR-005**; PR-002's 1000-partition null stands as reported |
| `validation.backtest_min_trades` | **200** per arm in the primary period, **60** in the holdout | **used by PR-005** §8, and every arm cleared it |
| `validation.backtest_period` | **2016-08-01 → present**, or all available history if shorter | the window all three studies used, bounded by the free tier's depth |
| `validation.walkforward_window` | train **756** · test **252** · step **252** trading days | authored; derived in §3.1 |
| `validation.embargo` | **21** trading days | authored; derived in §3.2 |
| `validation.parameter_stability_tolerance` | **verdict invariance** under ±1 grid step; report fragile if the statistic moves >0.5× its own magnitude | authored; §3.3 |
| `validation.missed_trade_rate` | **5%** of trades dropped at random, seeded | authored; §3.4 |
| `validation.execution_delay` | **1 bar** — fill one session later than modelled | authored; §3.5 |
| `validation.qa_recheck_fraction` | **10%**, minimum 20 trades | authored; §3.6 |
| `validation.forward_test_min_duration` | **12 weeks** | Appendix R's 90-day practice plan |
| `validation.forward_test_min_trades` | **20** trades | Appendix S stage 1 — a **process** threshold, not a statistical one |
| `validation.go_live_criteria` | Appendix S stage 1 gate: **100% plan/stop/journal, no critical violations**, plus every ratified Track A criterion met | the course's only hard gate |
| `validation.max_allowable_drawdown` | **−15R** peak-to-trough | authored, and **the weakest of the fifteen** — §3.7 |

## 1. What ratifying existing practice buys

The first four are not proposals in any meaningful sense. PR-002 and PR-005 pinned those values
before their runs, recorded them, and reported against them; the registry simply never learned what
the studies had already decided. Writing them down means the next study inherits the same
constants instead of choosing its own, which is what makes two results comparable.

`validation.stress_cost_multiplier` is the clearest case: `DR-004-cost-model.md` states *"Stress
regime: 3× both components"* **and names this parameter**, so the value has been decided and
undeclared since 2026-08-02.

## 2. The one the course actually settles

`validation.go_live_criteria` is not authored. Appendix S supplies the only hard, checkable gate in
116 files — `100% plan/stop/journal; no critical violations` — and its closing note inverts the
obvious criterion: *a positive or acceptable expectancy is not required without a sufficient sample,
but the process must be stable* (`GO_LIVE_GATES.md` §3). **Profit is not the gate. Process is.**

So the value is that clause plus the Track A criteria already ratified in `criteria.yml`, and
nothing about edge appears in it. A break-even hundred trades with clean process passes; a
profitable hundred with critical violations does not.

## 3. The authored eight, and how weak each is

### 3.1 `validation.walkforward_window` — 756 / 252 / 252

Derived from what the data can support, not from preference. The measured window is ~2,514 sessions
(2016-08-01 → 2026-07-31). Three years of training (756) and one year of test (252), stepped one
year, yields **⌊(2514 − 756 − 252) / 252⌋ + 1 ≈ 7 folds** — enough for `keep/revise/retire` per
window to mean something, and short enough that a fold spans a single regime rather than averaging
across all of them.

Moves if the history deepens. It is arithmetic on the available depth, so it is the parameter most
likely to change for a reason that has nothing to do with markets.

### 3.2 `validation.embargo` — 21 trading days

A rule rather than a taste: **the embargo must exceed the longest a single trade can straddle the
boundary.** The harness's maximum holding period is 20 bars and entry lags the signal by one, so a
trade begun on the last training bar can still be open 21 sessions into the test window. Anything
shorter leaks the same trade into both.

**This value is a function of the exit model.** If `exit.max_holding_period` is ever set to something
other than 20, this must move with it, and a check that they stay consistent is cheaper than
remembering.

### 3.3 `validation.parameter_stability_tolerance` — verdict invariance

The course frames robustness as pass/fail (`WALKFORWARD_SPEC.md` §5, topic 1104), so the tolerance is
expressed the same way: **moving a parameter one step to either neighbour on its natural grid must
not change the accept/reject verdict.** If it does, the result is fragile and the parameter is not
ratifiable at that value.

The 0.5× magnitude clause is for reporting only, so a result that survives the verdict test but
moves a lot is still visible. A single ratio would have been easier to write and would have measured
the wrong thing — a statistic can move 30% and never cross the decision boundary, or move 5% and
cross it.

### 3.4 `validation.missed_trade_rate` — 5%

A **perturbation magnitude, not a measurement**: the robustness battery drops a seeded random 5% of
trades and asks whether the conclusion survives. One trade in twenty is roughly one missed signal per
Appendix S stage, which is the scale a real operator misses at.

The forward test measures the true rate (`VALIDATION_PROGRAM.md` §2 — `пропуски` is one of the four
things a backtest structurally cannot see). When it does, that measurement replaces this guess and
this parameter's provenance changes.

### 3.5 `validation.execution_delay` — 1 bar

Under D1 the owner reads a report after the close and acts at the next open, which is already the
modelled fill (`EXECUTION_MODEL.md` E1). The perturbation therefore asks the only question left:
what if they act one session later? One bar is the smallest unit daily data has, and a strategy whose
edge does not survive a single session of delay is not tradeable by a human on a daily timeframe.

### 3.6 `validation.qa_recheck_fraction` — 10%, minimum 20 trades

Appendix J requires an independent re-check of *part* of the sample and does not say what part.
10% of the 200-trade floor is 20 trades, which ties this to `validation.backtest_min_trades`
deliberately: the two move together, and the floor guarantees the re-check is never a single-digit
sample.

The sampling rule must be seeded and recorded — `BACKTEST_PROTOCOL.md` §7 requires the sample to be
drawn by rule rather than chosen by the person checking, and §8 has kept that as an open item.

### 3.7 `validation.max_allowable_drawdown` — −15R, and why it is the weakest

This is the one to argue with.

**Expressed in R, not percent.** `risk.per_trade_pct` is itself `unset`, so a percentage threshold
would depend on a number nobody has set. In R the threshold is scale-free; at 1% risk per trade,
−15R is roughly −15% of equity.

**Why not −10R.** PR-005 measured a hit rate of 0.412 and a median trade of −1.005R on the ungated
arm — the median trade is a full stop. An equity curve with a near-zero mean and that shape reaches
double-digit negative R in ordinary sequences, so a −10R pause would fire on noise, and a gate that
fires on noise gets disabled. −15R is chosen to sit above the range a zero-edge sequence produces
routinely, while still firing well before the account is impaired.

**Why that reasoning is not good enough, stated plainly.** `WALKFORWARD_SPEC.md` §4 topic 1097 makes
the point that undoes it: *shuffling the order of the same trades leaves total R unchanged and
changes maximum drawdown completely.* A realised drawdown is one draw from a distribution, so the
correct threshold is a percentile of that distribution, not an intuition about it. The machinery to
compute it already exists — `validation/studies/trend_performance.py` permutes trade order with a
seed.

**The study that would replace this value:** permute PR-005's trade sequence 10,000 times, take the
distribution of maximum drawdown, and set the threshold above its 95th percentile. That is a
pre-registration, not a calculation to slip into this record, and it is why this value is `assumed`
rather than `validated`. Until it runs, −15R is a placeholder that fails closed in the right
direction — a pause, per `criteria.yml`, never a kill.

## 4. Alternatives rejected

| Alternative | Why not |
|---|---|
| Leave them `unset` until each is measured | `k.drawdown_pause` stays inert, and an inert ratified gate is worse than an absent one — it reads as protection |
| Set only `max_allowable_drawdown` | fixes the one visible symptom and leaves fourteen parameters whose absence blocks the walk-forward and forward-test programmes entirely |
| A single "risk appetite" scalar with the rest derived | the ТЗ and the course both treat these as independent thresholds; deriving them from one number hides which choice each result depends on |
| Percentage drawdown rather than R | depends on `risk.per_trade_pct`, which is unset. A threshold defined by an unset parameter is the defect this record exists to remove |
| Waiting for the forward test to measure the honest values | four of the fifteen gate the forward test itself. Circular |

## 5. What would overturn this

- **The drawdown permutation study** (§3.7) replaces `max_allowable_drawdown` with a measured
  percentile. Highest priority of the five.
- **The forward test** measures the real missed-trade rate and execution delay, replacing §3.4
  and §3.5 with observations.
- **A deeper history** changes the walk-forward arithmetic in §3.1.
- **A change to the exit model** forces `validation.embargo` to move with it (§3.2).
- **Owner amendment.** These are proposed values; the owner may set any of them differently, and the
  record then carries the owner's value with provenance `owner` rather than `assumed:DR-005`.

## 6. Consequences

1. **`k.drawdown_pause` can evaluate.** The ratified criterion stops being a gate that cannot fail.
2. **The narrow `REQ-VALIDATION-001` gate becomes possible** — *every ratified criterion's referenced
   parameters are set* is the cheapest check in `RULE_SPEC.md` §9 and it would fail today. It should
   land in the same change that ratifies this record, not before: a gate that fails on merge is not a
   gate, it is a blocked repository.
3. **The walk-forward and forward-test programmes become runnable.** Both were blocked on parameters
   rather than on code.
4. **Every result computed from these carries `assumed` provenance** and says so wherever it is
   displayed. Nine of the 96 parameters were `assumed` before this record; ratifying it makes it 24,
   and `RunManifest.assumed_parameter_count` is reported daily precisely so that number stays
   visible. **It should fall over time. If it never falls, the validation programme is not
   progressing.**
