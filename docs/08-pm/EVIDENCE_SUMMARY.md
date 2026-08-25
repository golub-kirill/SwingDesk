# EVIDENCE SUMMARY — what is actually known

**Status:** drafting · **Tier:** 8 (project management) · **Content:** authored

Migrated from `HANDOFF.md` §3 on 2026-08-15. `AGENTS.md` §10.7 makes `HANDOFF.md` session memory —
what changed, what is in flight, what is frozen — and this is none of those. It is a standing
account of what the reported studies support, which outlives any session and is cited from outside
one.

**The machinery is real and honest. The strategy is not known to work, and what is known is mostly
negative.**

---

## 1. The base strategy is negative at measured costs, across the whole admissible universe

`PR-005` reported **+0.028R** at 1× and **−0.123R** at 3×; both are net, because gross is never
reported (`DR-004` consequence 1), so "before costs" is the one description that is wrong. Those two
points give gross 0.1036R, cost 0.0757R and break-even at **1.369×** the assumption — and `DR-005`
measures slippage at **25bp per side** against the assumed 5.

Recomputed 2026-08-09 (`DR-005`, *Consequence for PR-005*): **−0.073R at the $5 universe floor,
−0.224R at $50.** Break-even would need an average traded price of **$1.02**; `universe.min_price`
is **$5.00**. **No price an eligible instrument can have makes it positive.** The 1× column was
never applicable.

**Read these two figures as what they are.** They are not the output of a run. They are an
arithmetic recomputation from `PR-005`'s two reported points under a corrected cost model — a
two-point extrapolation, not a measured expectancy. The direction is well supported; the magnitude
inherits every limitation of the study it is derived from, including its universe construction
(§5).

## 2. The direction is settled and the level is not

`PR-008` reached the opposite conclusion — that the estimators cannot resolve the spread — and that
explanation was **withdrawn on 2026-08-09** after a calibration-free sign test refuted it. But
neither effort settled the magnitude: Abdi-Ranaldo correlates **+0.46** with volatility and **−0.02**
with liquidity, which is backwards for a spread, and the published literature documents exactly that
bias.

**`PR-010` closed this on 2026-08-09.** EDGE — the 2024 estimator built to fix both, and the only one
that reads the open — reports 25.65bp against its own zero-spread floor of **41.87bp** at this
universe's measured volatility. Two estimators agree to 0.21bp *inside their shared noise*. **The
level is not obtainable from daily OHLC**; `PR-006`, real fills, is the only route left.

Treat 25bp as "materially more than 5", never as a measurement of 25.

## 3. The one positive finding is fragile at a plausible magnitude

`PR-002` — breadth separates breakout outcomes — is erased by **1.6–2.3% of trades missing at −2R**,
and Yahoo serves no delisted history, so that exposure can never be confirmed on the free tier.

**And its verdict does not follow its own decision rule.** `PR-002` §6 permits `accept` only on both
countries independently; the third amendment, dated before the run, states that a single-market
result takes the `inconclusive` branch. `tools/run_pr002.py` implements the percentile branches with
no country condition and emits `accept`. The defect is in the runner, not in the disclosure — the
limitation was registered before the data was seen. Tracked in `TODO.md` §5.

## 4. There is no legal source of probability in this system today

No expectation estimate exists and no calibrated model exists (`EXPECTATION_MODEL.md` §9c). Any
probability displayed would be manufactured.

## 5. Historical results carry a universe caveat that has not been discharged

`PR-001`, `PR-002` and `PR-005` build their universe from the **current** symbol directory, and
apply the liquidity rule at the **last bar of full history** rather than at each session. Session-level
point-in-time membership is not used, though `reference_data.universe.members()` already accepts an
`as_of` date and `LiquidityRule.admits()` already accepts an index — the capability exists and the
studies do not call it. Direction and magnitude of the resulting bias are unknown. Tracked in
`TODO.md` §5.

## 6. ~~Two ratified criteria are inert~~ One is, for two independent reasons

`k.strategy_rejected` cannot fire, and **both blockers must clear before it ever can**
(`EXPECTATION_MODEL.md` §9b): `criteria.yml` v1.1.0 settles that Track B evaluates on **journalled
trades only**, so no backtest can fire it whatever else is true — and its benchmark comparison is
**not commensurable**, because a per-trade R expectancy and a buy-and-hold return need a horizon and
an exposure assumption to be compared at all.

**Resolved 2026-08-24. The heading was a wording defect and the count was the wrong noun.** It said
*two* and named *one*; every other source in the tree means two *reasons*. Checked against the
second candidate before concluding: `k.drawdown_pause` was the project's other inert gate — ratified
against `validation.max_allowable_drawdown` while that parameter was `unset`, so its verdict was
invariant across every input the system could produce — and `DR-007` gave it a value on 2026-08-08.
`RULE_SPEC.md` §7 states the result exactly: **"The gate went from unable to fail to untested, which
is progress and is not the same as working."** Untested is not inert, so it does not belong in this
count, and nothing else in the tree does either.

Struck through rather than rewritten, per `AGENTS.md` §10.5's own convention: a heading that stood
for weeks and was wrong is worth more visible than absent.

## 7. Reaching v1 with no validated edge is a success, not a failure

`CHARTER.md` §4's v1 finish line is a **machinery** target and was reached 2026-08-02. Reaching v1
and reporting no validated edge is a **success** against the ratified criteria. `SUCCESS_AND_KILL_CRITERIA.md`
is explicit that a negative result is a result.

## 8. The cross-sectional family has been looked at twice, and neither look found anything

Added 2026-08-24. **Both are labelled, and the labels are the point.**

**`PR-012` REFUSED a verdict** — not `inconclusive`. Four concurrent positions held at most twenty
sessions produce about fifty entries a year, so its holdout supplied 181–203 trades against its own
declared minimum of 200. It reported the measurement and declined to conclude, which is what
`PREREG_TEMPLATE` §8 asks for. **A refusal still spends its trials.**

**`PR-013` is EXPLORATORY by its own declaration** and therefore advances no validation status and
sets no parameter. Its drafter had read `PR-012`'s numbers, said so in §0b before the run, and
registered it anyway because the question is different: does the ORDERING carry information, rather
than does a capacity-constrained book beat another one.

**What it measured, and this is the part worth carrying.** Over 142 holdout formation dates — the
sample rule was **met**, which `PR-012` could not manage — **all six gross intervals include zero**,
in both periods and all three arms. Before a single basis point of cost, the top-decile minus
bottom-decile forward return is not distinguishable from nothing. The largest point estimate is
+0.24% over five sessions against an interval running −0.15% to +0.61%, and the three forms do not
separate from one another either.

**Survivorship makes that the stronger reading rather than the weaker one.** The directory is
today's, so every figure is biased upward; a measurement inclined to find an edge found none.

**What it does NOT establish.** One lookback (126 sessions) and one horizon (5 sessions), neither
searched. The family is not refuted and `CARD-001`'s four selection inputs remain `unset` — a study
that sets nothing is what an exploratory result is.

**And a caution about its own verdict word.** `PR-013` reports `inconclusive` because the registered
decision rule has no branch for *both the arm and the control are losing*, so an arm whose interval
sat wholly below zero was not rejected by it. The numbers are what to read; the verdict word
understates them. The gap is recorded in that study's report for whoever writes the next
pre-registration.

---

**Do not write anything implying more confidence than the above.** `UX_COPY.md` §3 carries the
standing warning verbatim.
