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

## 6. Two ratified criteria are inert

`k.strategy_rejected` cannot fire — Track B evaluates on journalled trades only, and its benchmark
comparison is not commensurable. See `HANDOFF.md` §5.

**UNRESOLVED:** this sentence says *two* and names *one*. Every other source in the tree means two
*reasons*, not two criteria. Carried forward unchanged rather than silently corrected, because a
migration preserves the record; the wording defect is tracked in `TODO.md` §3.

## 7. Reaching v1 with no validated edge is a success, not a failure

`CHARTER.md` §4's v1 finish line is a **machinery** target and was reached 2026-08-02. Reaching v1
and reporting no validated edge is a **success** against the ratified criteria. `SUCCESS_AND_KILL_CRITERIA.md`
is explicit that a negative result is a result.

---

**Do not write anything implying more confidence than the above.** `UX_COPY.md` §3 carries the
standing warning verbatim.
