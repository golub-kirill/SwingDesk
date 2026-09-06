# DR-040: the spread is a function of the time of day, and the card trades at its worst value

```
date:            2026-09-06
status:          proposed
parameters:      costs.slippage_model (its SHAPE and its note; this record proposes no new number)
components:      none - swingdesk.validation.backtest.costs charges it; this is about its input
supersedes:      nothing. DR-005's 25.44 bps per side stands, and this record shows it is RIGHT
                 about the moment CARD-001 trades. What it supersedes is DR-004's PREMISE, which
                 said the quantity could not be measured at all
evidence:        measurements/quoted-spread-2026-09-06.json  (the venue's own NBBO)
                 measurements/fill-convention-2026-09-06.json (which fills actually happen)
derived_by:      tools/measure_quoted_spread.py, tools/probe_quotes.py,
                 tools/measure_fill_convention.py
trial_spend:     ZERO. This measures a COST INPUT rather than a strategy's return, the same rule
                 trial_budget.py already applies to PR-008 and PR-010 - there is no Sharpe here to
                 deflate. The study that WOULD spend trials is named in section 6 and is not run.
```

---

## 1. The premise under `DR-005` was false, and testing it is what this record is for

`DR-004` closed the quoted route in one sentence:

> spread-derived slippage from quoted bid/ask: correct and unavailable - no free source serves
> historical intraday spreads point-in-time

So `DR-005` fell back to two daily-OHLC estimators and set **25.44 bps per side**, honestly labelled
`assumed`. `EVIDENCE_SUMMARY` §2 then locked the door: *"the level is not obtainable from daily
OHLC; `PR-006`, real fills, is the only route left."*

**`python tools/probe_quotes.py` refutes it.** The venue this project already holds an account with
serves consolidated **SIP** NBBO quotes, historical and point-in-time, on the free tier. Only the
last fifteen minutes are withheld - the one window a backtest never reads.

**Why it stayed hidden is the transferable part, and the duration is not the point.** `DR-004` is
dated 2026-08-02 and this refutation is 2026-09-06 - **thirty-five days**, in which an untested
sentence became the input every negative headline in the project is computed at. A false premise
does not need to survive long to become load-bearing; it needs to be convenient. The free tier's
*real-time*
feed is IEX: one venue, a few percent of volume, and a single venue's book is far wider than the
consolidated one. At the same instant in 2019, `AAPL` reads **0.49 bps** on SIP and **621.82 bps**
on IEX. Reading IEX and concluding the data is unusable is a correct measurement of the wrong tape.
The same vendor had been tested twelve days earlier - **for bars**. Nobody asked it for quotes.
`AGENTS.md` §17: the granularity, not the source.

## 2. `DR-005` is not wrong. It is right about ONE MINUTE of the day

2,208 windows, the venue's own NBBO, the same `S/2 per side` convention `DR-005` reports. **The
universe is rebuilt on each sampled date from the bars that date had**, because drawing one sample
from today's admitted names and pricing it in 2016 measures what today's survivors cost then, which
is a different and much less useful quantity.

Median per-side spread, bps:

| window | 2016 | 2019 | 2022 | 2024 | 2026 | `DR-005` is |
|---|---|---|---|---|---|---|
| **09:30 open** | 21.9 | 22.7 | 24.9 | 30.2 | 26.5 | **right — 0.8x to 1.2x** |
| 10:00 | 5.6 | 5.1 | 6.7 | 6.8 | 7.5 | 3.4x to 5.0x too high |
| 11:00 | 3.9 | 3.3 | 4.2 | 5.3 | 5.8 | 4.4x to 7.6x too high |
| **15:55 close** | 1.9 | 2.1 | 2.6 | 3.5 | 4.0 | **6.3x to 13.6x too high** |

**Two readings, and the second is the one that matters.**

**The estimators were measuring something real.** Across five years and a universe that grew from 38
admissible names to 3,999, the opening spread sits within a factor of 1.2 of the number two
daily-OHLC estimators produced from high, low and close. That is a better outcome for `DR-005` than
this record went looking for.

**And `CARD-001` trades at exactly that moment.** `entry.method` is **`next session's open`**, and
the backtest implements it - `engine.py`: *"entry still fills at `bars[i + 1].open`"*. The opening
minute is **6.6x** the closing spread in 2026 and the ratio holds in every year measured. **The one
number the strategy pays is the worst value the day offers.**

Read the median, not the mean. The mean column in the evidence file is dominated by a handful of
very wide books - in 2016 it is 165 against a median of 22 on 38 names - and a mean above the p90 is
a tail, not a level.

## 3. What the constant is worth, in the project's own published numbers

`measure_exit_surface.py` published a gross expectancy and the R cost of the charged 50 bps
together, so the cost at which each result turns sign is arithmetic on committed numbers rather than
a new claim. `tools/measure_quoted_spread.py` derives it (`AGENTS.md` §10.6 rule 4).

| subject | gross | break-even round trip | per side |
|---|---|---|---|
| buy and hold, 20 sessions, no stop, no target | **+0.140R** | 41.1 bps | **20.6 bps** |
| the ratified cell, stop 2.0 x ATR, target 1R | **+0.042R** | 12.4 bps | **6.2 bps** |

Against the measured curve:

| executed at | per-side spread, 2026 | buy and hold | the ratified exit policy |
|---|---|---|---|
| **09:30 open** (ratified) | 26.5 | **negative** | **negative** |
| 10:00 | 7.5 | positive | negative |
| 11:00 | 5.8 | positive | **positive, barely** |
| 15:55 close | 4.0 | positive | positive |

**`DR-029` §7 concluded that expectancy cannot come from the exit. It can come from the CLOCK**, and
the clock was never a parameter - it was a phrase in a card.

## 4. What this does NOT establish, and it is the limit that matters

**A later entry is not the same trade at a lower price.** Moving execution from 09:30 to 15:55
changes the price paid, so it changes the GROSS return as well as the cost - and the gross column
above was measured on entries struck at the open. **Subtracting a smaller cost from an unchanged
gross is precisely the error this record corrects in `DR-029` §5**, which read an attractive lever
off a table its own record labelled *"Gross of costs"*. Section 6 names what would settle it.

**A quoted spread is not a realised cost.** It is an upper bound for an order that crosses and an
over-charge for one that rests. `tools/measure_fill_convention.py` measures which happens: over
147,712 non-overlapping entries the live limit at the prior close is **50.6% marketable at the open,
32.8% passive at the limit, 16.6% never filled**. Only the first pays a spread at all.

**No market impact.** This is top of book and says nothing about depth. At four positions on names
clearing $5m a day the effect is small, but small is a claim and nothing here measures it.

**Sixty names, two dates a year.** Enough to establish the SHAPE - the intraday curve is the same in
all five years and monotone in all five - and not enough to set a constant.

## 5. Decision

**No number changes.** What is proposed is the shape and the record:

1. **`costs.slippage_model`'s note records WHICH MOMENT its value describes.** Today it reads as a
   property of the universe. It is a property of the universe *at the opening minute*, and a reader
   who does not know that will apply it to an execution it does not describe.
2. **The model gains an execution-time dimension**, so a study can state the moment it charges for.
   One constant charged to both sides of every fill can represent none of the three fill types
   `measure_fill_convention.py` counts.
3. **`DR-004`'s premise is struck** wherever it is quoted as a reason not to measure, and
   `tools/probe_quotes.py` is the standing refutation - re-derived on every run rather than recorded
   as prose, because that block read as measured for its whole life while being wrong.

**`CARD-001`'s `entry.method` is NOT changed here.** It is a card field, the card is `Untested`, and
changing it creates a new version that resets any validation claim (`STRATEGY_CARD_SPEC` 5 rule 2).
That is the owner's, and §6 is what they should have first.

## 6. What would overturn this, and the study that settles it

**Register and run an execution-time study.** Same universe, same selection, same holding period;
entry and exit struck at 09:30, 11:00 and 15:55 against **intraday bars**, which the venue also
serves free and which this project does not yet store. It reports net expectancy per execution time.

* If the gross decays by more than the cost saved, this record is refuted and the open is correct.
* If it does not, the clock is the largest lever measured in this project - **0.10R per trade** was
  the entire cost of the exit policy `DR-029` §7 priced, and the open-to-close spread difference is
  **22.5 bps per side**, about **0.15R** at a 2.0 x ATR stop.

**That study spends trials** - it evaluates configurations of a strategy and produces a Sharpe -
which is exactly why it is not run inside a decision record.

## 7. Alternatives rejected

**Set `costs.slippage_model` to the late-session number.** It would flip several published results
on the assumption that gross is unchanged, which §4 says is not established. A number that turns a
negative into a positive is the last one to adopt without the study.

**Keep the single constant and note the caveat in prose.** A caveat in prose is what `DR-004`'s
premise was. Gate 28 exists because this project has paid for status claims that no tool re-derives.

**Wait for `PR-006`, real fills.** That was the plan `EVIDENCE_SUMMARY` §2 recorded, and it rests on
the premise §1 refutes. Real fills remain the better evidence and are now the second source rather
than the only one - and at four positions a night they would take years to reach this sample.

**Do nothing, because `DR-005` turned out to be accurate.** It is accurate about the open. Leaving it
unqualified means the next study to move execution off the open will silently charge itself six
times the true cost, and conclude correctly from a wrong input.

## 8. Consequences

* **Every net figure this project has published is a figure at the open.** `PR-005`'s sign,
  `DR-029` §7's surface, `EVIDENCE_SUMMARY` §8a's conversion - all correct at the cost they charge,
  and all charging the most expensive minute of the session.
* **`EVIDENCE_SUMMARY` §2's second clause is struck**, with the refutation beside it.
* **The audit's base rate moves to eight impossibility claims tested, five false** (`TODO.md` §2).
* **Intraday bars become worth storing.** Nothing in `data/` holds them today, and §6 needs them.
