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
level is not obtainable from daily OHLC**; ~~`PR-006`, real fills, is the only route left.~~

Treat 25bp as "materially more than 5", never as a measurement of 25.

**THE SECOND CLAUSE IS REFUTED, 2026-09-06 — `python tools/probe_quotes.py`.** The first clause is
still true and is not what closed the question. What closed it was `DR-004`'s premise underneath:

> spread-derived slippage from quoted bid/ask: correct and unavailable — no free source serves
> historical intraday spreads point-in-time

**The venue this project already holds an account with serves them.** Consolidated **SIP** NBBO
quotes, historical, point-in-time, free tier; only the last fifteen minutes are withheld, which is
the one window a backtest never reads. The probe re-derives it on every run rather than recording
the answer as prose, because that block read as measured for the whole time it was wrong.

**Why it stayed hidden is worth more than the fact.** The free tier's *real-time* feed is IEX — one
venue, a few percent of volume — and a single venue's book is far wider than the consolidated one.
The probe prints both: at the same instant in 2019, `AAPL` reads **0.49bp** on SIP and **621.82bp**
on IEX. Reading IEX and concluding the data is unusable is a correct measurement of the wrong tape.
The same source had already been checked, on 2026-09-05, and it was checked for **bars**; nobody
asked it for **quotes**. That is `AGENTS.md` §17 again — the granularity, not the source.

**What this does NOT overturn.** `PR-005`'s sign, `DR-029` §7's surface and §8a's conversion all
stand as computed; they are correct at the cost they charge. What moves is the standing of the
charge itself, and §10 measures it.

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
it. ~~And **whether SIP historical is a free-tier entitlement or an attribute of this account
is not established** — it is the first thing to settle before anything is built on this.~~
**SETTLED BY THE OWNER 2026-09-05: the account is FREE TIER.** So the free tier serves
delisted daily history on `feed=sip`, and it is settled by the only party who could settle
it — an account's tier is not observable in what the account returns, which is why the probe
was able to measure the DATA and not the ENTITLEMENT.
**What it still does not establish**, and the distinction is not pedantry: this is ONE free
account observed serving it, not Alpaca's documented policy for every free account. If the
terms change the route closes, and nothing here would notice.

**What it changes, stated narrowly.** The −2R assumption is no longer forced. It was the last
unmeasurable input to the bound that erases this project's one positive finding, and the route
to measuring it now exists. **Nothing here re-derives the bound or reopens `PR-002`** — that is
a research decision and the owner's, and doing it would need a pre-registration like any other.

**ANSWERED 2026-09-05: *"only if we need to"*. A DEFERRAL, NOT A NO**, and the difference is
the whole of `AGENTS.md` §15 — a session that reads silence here as a closed door will cite it
as settled. The route stays open and unused, deliberately.
**What "need to" would look like is not ruled and is not mine to invent.** The one condition
that plainly meets it: **`PR-002` being relied on for a live decision** rather than sitting
parked, because that is the moment its kill line stops being hypothetical. That reading is
MINE, not the owner's — anything else is a question to ask, not an inference to act on (§14).

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

### 8a. The horizon result is LONG-SHORT and this system is LONG-ONLY — measured 2026-09-06

`python tools/measure_long_only_horizon.py --data <store>`, evidence in
`docs/decisions/measurements/long-only-horizon-2026-09-06.json`. **EXPLORATORY; sets nothing.**

**What everybody quotes.** `measure_momentum_horizon` found the decile spread rising monotonically
with horizon and excluding zero only at 126 sessions — **+7.271% [+1.899, +12.512]**. It is the only
interval-excluding-zero result about this family in the store, and every argument for a longer hold
rests on it.

**It is `_spread`: top-decile mean MINUS bottom-decile mean.** Capturing it needs a short leg.
`trade_management/portfolio.py` states *"this system is long-only today"*, and `CARD-001` holds the
top decile and shorts nothing. A long-only book earns the top decile against the **benchmark**, not
against the bottom decile.

**That tool's own docstring says so** — *"a gross spread is not a tradeable result and nothing here
should be read as one"* — and it was read as one anyway, in this session among others.

**Measured, same formation window, same skips, same liquidity rule, same non-overlapping dates, same
bootstrap. Only the statistic changes:**

| horizon | n | top decile − `SPY`, gross | net of 25bp/side |
|---|---|---|---|
| 5 | 453 | +0.107% [−0.123, +0.336] | **−0.393% [−0.623, −0.164]** ✗ |
| **20** (ratified) | 112 | +0.557% [−0.288, +1.393] | +0.057% [−0.788, +0.893] |
| 63 | 35 | +2.209% [−0.355, +5.128] | +1.709% [−0.855, +4.628] |
| **126** | **17** | **+4.805% [−0.009, +10.125]** | +4.305% [−0.509, +9.625] |

**THE SIGNIFICANT RESULT DOES NOT SURVIVE THE CONVERSION.** Long-short at 126 excludes zero;
long-only at 126 does **not** — its lower bound is **−0.009%**, which is zero to three decimals. By
this project's own standard (`b.expectancy`: *bootstrap CI excluding zero*) the tradeable half is
**not** established.

**And at five sessions the long-only excess is significantly NEGATIVE after costs.** That is
`PR-013`'s horizon. Its six intervals all included zero gross; the sign is now determined net, and
it is the wrong one.

**What binds is not the sample rule, it is the calendar.** Seventeen non-overlapping 126-session
windows exist in a decade. The horizon where the point estimate is largest is the horizon at which
independent observations are scarcest, and no amount of patience changes the arithmetic: a longer
hold buys a bigger effect and fewer chances to see it.

**What this does NOT establish.** The family is not refuted — the point estimates are positive and
monotone in horizon, and 126 misses by a hair on seventeen observations. It is not *shown* either,
which is the only claim `b.expectancy` accepts. And `exit.max_holding_period` = 20 (`DR-012`,
ratified) sits in the band where the measurement is indistinguishable from zero, one band above the
one where it is negative.

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

## 10. The cost constant is right about one minute of the day, and the card trades in it

Measured 2026-09-06, `DR-040`. `python tools/measure_quoted_spread.py`, evidence in
`docs/decisions/measurements/quoted-spread-2026-09-06.json`. **EXPLORATORY; it sets no parameter,
and it spends no trial — a cost input has no Sharpe to deflate (`trial_budget.py`, the `PR-008` /
`PR-010` rule).**

**The route was open the whole time.** §2's *"`PR-006`, real fills, is the only route left"* rested
on `DR-004`'s premise that no free source serves historical intraday spreads. The venue this
project already holds an account with serves consolidated SIP NBBO, point-in-time, back to 2016;
only the last fifteen minutes are withheld. `tools/probe_quotes.py` re-derives it on every run.

**2,208 windows, the venue's own NBBO, the same `S/2 per side` convention `DR-005` reports.** The
universe is rebuilt on each sampled date from the bars that date had — a sample drawn from today's
admitted names and priced in 2016 measures what today's survivors cost then, which is a different
quantity. Median per-side spread, bps:

| window | 2016 | 2019 | 2022 | 2024 | 2026 | vs `DR-005`'s 25.44 |
|---|---|---|---|---|---|---|
| **09:30 open** | 21.9 | 22.7 | 24.9 | 30.2 | 26.5 | **right — 0.8x to 1.2x** |
| 10:00 | 5.6 | 5.1 | 6.7 | 6.8 | 7.5 | 3.4x to 5.0x too high |
| 11:00 | 3.9 | 3.3 | 4.2 | 5.3 | 5.8 | 4.4x to 7.6x too high |
| **15:55 close** | 1.9 | 2.1 | 2.6 | 3.5 | 4.0 | **6.3x to 13.6x too high** |

**`DR-005` is vindicated and the card is not.** Two daily-OHLC estimators reproduced the opening
spread to within a factor of 1.2, across five years and a universe growing from 38 admissible names
to 3,999. And `CARD-001`'s `entry.method` is **`next session's open`** — the one moment of the
session that costs **6.6x** the close.

**What that is worth, in this document's own published numbers.** The exit surface reported gross
expectancy and the R cost of the charged 50 bps together, so the turning point is arithmetic:

| subject | gross | break-even per side | at the open (26.5) | at the close (4.0) |
|---|---|---|---|---|
| buy and hold, 20 sessions | +0.140R | 20.6 bps | **negative** | positive |
| the ratified 2.0/1R cell | +0.042R | 6.2 bps | **negative** | positive |

**THE LIMIT, AND IT IS THE WHOLE CAVEAT.** A later entry is not the same trade at a better price: it
changes the gross return as well as the cost, and the gross column above was measured on entries
struck at the open. **Subtracting a smaller cost from an unchanged gross is exactly the error
`DR-029` §5 made** when it read a lever off a table labelled *"Gross of costs"*. Nothing here says
the strategy is profitable later in the day. What it says is that **the published results are all
computed at the top of a curve nobody knew was a curve**, and that settling it needs intraday bars
this project does not store — `DR-040` §6 registers what that study would be.

**And the live path pays a spread on only half its entries.** `tools/measure_fill_convention.py`,
over 147,712 non-overlapping entries: the limit resting at the prior close is **50.6% marketable at
the open, 32.8% passive at the limit, 16.6% never filled**. The backtest fills all of them at the
open and charges all of them a spread. The resulting adverse selection is real and small — the names
the limit misses do run better (+3.136% against +1.777%), the cheaper fills offset it, and the net
is **-0.024% per entry**.

---

**Do not write anything implying more confidence than the above.** `UX_COPY.md` §3 carries the
standing warning verbatim.
