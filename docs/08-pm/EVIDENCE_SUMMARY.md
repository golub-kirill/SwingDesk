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
and Yahoo serves no delisted history. ~~so that exposure can never be confirmed on the free tier.~~

**Corrected 2026-08-24, and only half of it was true.** The bound has two halves and the free tier
closes one of them. **How many names vanished** is measurable: SEC EDGAR keeps every filer back to
1993, free and official, and dates each delisting by Form 25 or 25-NSE — demonstrated by
`tools/probe_edgar.py`. ~~**What those trades would have returned** is not: no free source serves
the price path of a symbol that has gone, so the −2R assumption stays an assumption. So the
exposure's SIZE can be constrained by measurement and its MAGNITUDE cannot.~~ Struck rather than
rewritten, per `AGENTS.md` §15: it was an impossibility asserted without a test.

**AND THE SECOND HALF FELL ON 2026-09-05, to the owner's question rather than to a plan.**
*"Have you checked EDGAR or Alpaca as a second data provider?"* — EDGAR had been checked and
Alpaca had not, by anyone, ever. `python tools/probe_alpaca_delisted.py` enumerates **19,188**
inactive US equities and returns complete daily histories for delisted names: `EIO` **767** bars
to 2019-01-18, `BHBK` **815** to 2019-03-29, `EEP` **747** to 2018-12-19, `YESR` **277** to
2018-10-04.

**Three limits, because they bound what this licenses and the finding is worth nothing
overstated.** The free **IEX** feed serves **zero** of it — every history came from `feed=sip`,
requested with the paper key this project already holds. Coverage begins **2016-01-04**, so a
window opening earlier is still unserved; `PR-002`'s and `PR-005`'s both open 2016-08-01, inside
it. And **whether SIP historical is a free-tier entitlement or an attribute of this account is
not established** — it is the first thing to settle before anything is built on this.

**What it changes, stated narrowly.** The −2R assumption is no longer forced. It was the last
unmeasurable input to the bound that erases this project's one positive finding, and the route
to measuring it now exists. **Nothing here re-derives the bound or reopens `PR-002`** — that is
a research decision and the owner's, and doing it would need a pre-registration like any other.

**And the SIZE half is now measured rather than merely measurable — 2026-08-25.**
`python tools/classify_departures.py` classifies every symbol that left the directory between two
pulls. Over the first three weeks of the record it resolved a material share of the departures into
**confirmed delistings of that security**, with the rest split between structured symbols that
depart on separation, renames, and names this route could not place. Derive the counts with the
command, never from this paragraph (`AGENTS.md` §10.5).

**Two things about that measurement change how it should be read, and both cut against comfort.**
First, **`unresolved` is not `not delisted`** — it is a symbol the route could not place, and it is
the largest bucket. Second, and more important: **EDGAR's ticker metadata LAGS the vendor's
directory by more than the observation window.** Measured at 34 of 36 resolvable names still
carrying their departed ticker while absent from the live vendor files. So the discriminator
`probe_edgar.py` validated on a 2024 delisting — an empty ticker and exchange list — is right for
history and useless for last week; the **Form 25 date** is the timely one, and it lands on the same
pull the symbol vanished at. A classifier reading a present ticker as survival would understate this
exposure in the flattering direction.

**It also cost this project an assumption it had written down.** `TODO.md` had eyeballed the sample
and reasoned that *"`AVB` is a large S&P 500 REIT and cannot have [delisted]"*. AvalonBay filed a
Form 25-NSE the day it left the directory and is absent from both live vendor files; so is Equity
Residential, which reports no ticker at all at EDGAR. **The bound is not merely uncertain in the
tails — a departure that looks obviously benign can be a delisting**, which is the direction that
makes `PR-002`'s 1.6–2.3% threshold easier to reach rather than harder.

**And its verdict does not follow its own decision rule.** `PR-002` §6 permits `accept` only on both
countries independently; the third amendment, dated before the run, states that a single-market
result takes the `inconclusive` branch. `tools/run_pr002.py` implements the percentile branches with
no country condition and emits `accept`. The defect is in the runner, not in the disclosure — the
limitation was registered before the data was seen. Tracked in `TODO.md` §5.

## 4. There is no legal source of probability in this system today

No expectation estimate exists and no calibrated model exists (`EXPECTATION_MODEL.md` §9c). Any
probability displayed would be manufactured.

**Audited 2026-08-25 under `AGENTS.md` §15 rule 1, which asks an impossibility to name the check
that establishes it. This one can, and that changes its character.** It is not a claim about the
world — it is a claim about this system's own evidence, and it is DERIVED:

```bash
PYTHONPATH=$PWD/src python tools/verify_studies.py      # accepted verdicts
PYTHONPATH=$PWD/src python tools/verify_parameters.py   # validated parameters
```

A probability of an outcome needs a validated expectation, and a parameter reaches `validated` only
by citing a study that ACCEPTed. **So the sentence above is true exactly while those two commands
report none, and it stops being true the day either changes — without anyone having to remember to
revisit it.** That is the difference between a closure that names its check and one that does not,
and it is why this row does not need the audit the other three did.

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

## 9. The risk model is MORE valid on volatile names, not less, and that reverses an intuition

Added 2026-09-04. **`PR-011` REJECTED its own hypothesis, in the opposite direction to the one it
predicted**, and the reversal is the finding rather than the rejection.

The study asked whether a 2 × ATR stop still costs about 1R on names whose ATR is a large share of
their price — a question about whether `entry − stop` is a risk measure there at all, not about
whether such names are worth trading. Over 126,564 census entries across 10,377 names, **mean
overshoot falls monotonically as volatility rises**: the quietest band overshoots its stop by about
0.095R and the most volatile measured band by about 0.026R, with non-overlapping intervals. The
gap-through rate moves the same way — about 21% against about 14% — which is a second measurement
rather than a restatement of the first.

**Why the sign matters more than the verdict.** 1R *is* 2 × ATR, so the stop distance already scales
with the name's own volatility. The sizing arithmetic's self-correction does not merely survive into
the top band; it over-corrects. *(The mechanism sentence is CONJECTURE — `AGENTS.md` §10.4. Nothing
here measures gap size against ATR directly, and that statistic was not registered.)*

**Two boundaries this does not move.** The live refusal of a non-positive stop is arithmetic rather
than a hypothesis and stands untouched — the study said so in advance. And `screen.atr_pct_band`
stays `unset` with `read_by: none`: the study supplies no argument for a value.

**The caveat that cuts against it, stated in the report rather than buried.** Survivorship removes
exactly the names the top band is made of, so part of the reversal could be the missing data rather
than the mechanism. The study was registered as *biased toward finding nothing*; it found less than
nothing, and no figure here corrects for that.

**The net-R column in that result is NOT interpretable** and the report says so at length: a census
is not a set of trades, survivorship is absent, and `HANDOFF.md` §7 closes the new-entry-filter
family by evidence anyway.

---

**Do not write anything implying more confidence than the above.** `UX_COPY.md` §3 carries the
standing warning verbatim.
