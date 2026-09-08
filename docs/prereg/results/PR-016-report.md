# PR-016 RESULT: the screen beats no screen and both lose money — and the ratified target is what makes the left tail

```
prereg:        PR-016
ran:           2026-09-08
verdict:       ACCEPT by the registered rule — AND THE ARM IS UNPROFITABLE. §6 reads the
               DIFFERENCE between two arms and never asks whether either makes money.
               Both lose: the ranked arm -0.100R a trade, the control -0.192R
status:        PRELIMINARY. DR-042's tie-break is unruled and the owner ruled on 2026-09-07
               that the measured share comes first. The share is 0.05% — see §7 — but the
               ruling is theirs and this file may not close it
tool:          tools/run_pr016.py
evidence:      PR-016.json · PR-016-trades-sample.csv · PR-016-ambiguous-bars.jsonl
trials:        2, declared before the run
```

---

## Read this first

**This is the first affirmative verdict this project has produced, and the sentence it licenses is
narrow.** §6 registered exactly one quantity — the paired difference in mean net R between the
ratified screen and taking every liquid name — and that difference excludes zero on both windows.
It says the screen changes the outcome distribution measurably.

**It does not say the strategy works.** The ranked arm loses **0.100R a trade**. Its win rate is
49.04% against a break-even of 54.22%. What the study found is that **the screen loses less than
no screen**, by about a tenth of an R per trade.

Three more things belong in the first paragraph rather than in a footnote:

* **The window is 8.91 years, not the ten the instruction asked for.** The store holds ten years of
  bars (`--period 10y`, owner ruling 2026-09-06) and a study needs its lookback before its first
  entry. `TODO` §4 carries what a wider fetch would cost.
* **Survivorship is absent and material.** Of the 2,598 instruments here with a decade of history,
  2,598 are still trading. Every number below is optimistic by an amount this run cannot measure.
* **The control CONTAINS the treatment.** The ranked decile is a subset of the admitted names, so
  the reported difference is attenuated by about a tenth — see §4.

Derive every figure with `python tools/run_pr016.py --report`, never from these lines.

## What ran

| | |
|---|---|
| store | `bars.duckdb` at `as_of 2026-09-06T22:36:49.635786-05:00` |
| instruments | 10,330 with at least 273 daily bars |
| window asked for | 2016-01-04 … 2026-09-04, 2,522 sessions |
| **window measured** | **2017-09-07 … 2026-08-07 — 8.91 years of entries** |
| formation dates | 119, every 20th session; 6 skipped as too thin to decile |
| exit | stop `2.0 × ATR(14)`, target `1.0R`, time exit at session 20, stop first |
| costs | 25 bps a side plus $0.005 a share, inside every figure |
| split | in-sample to 2021-12-31 (51 months), out-of-sample after (54 months) |
| intervals | moving-block bootstrap, entry months, block 3, seed 20260908, 10,000 resamples |

## The numbers

```
arm                    window               n   win%   b/e%   meanR    medR      p5     p95  payoff
unselected             in_sample       103911  48.64  57.38  -0.176  -0.161  -1.349  +0.970   0.743
unselected             out_of_sample   154846  46.21  56.31  -0.203  -0.492  -1.400  +0.971   0.776
ranked                 in_sample        11019  49.98  54.13  -0.080  -0.005  -1.147  +0.972   0.848
ranked                 out_of_sample    16320  48.41  54.27  -0.114  -0.210  -1.196  +0.971   0.843
```

**The quantity §6 reads, and nothing else:**

| window | ranked − unselected | 95% interval | width | floor | win rate |
|---|---|---|---|---|---|
| in-sample | **+0.096R** | [+0.057, +0.137] | 0.080 | 0.20 ✓ | +1.33pp |
| out-of-sample | **+0.088R** | [+0.018, +0.158] | 0.140 | 0.20 ✓ | +2.20pp |

Both exclude zero, both clear the power floor, both windows carry more than the registered minimum
of 200 trades and 24 months. §6's `ACCEPT` branch fired on its own terms.

## The verdict, arrived at by the registered rule

**ACCEPT.** And §6 said in advance what it licenses: *"one sentence — the ratified screen changes
the outcome distribution of the ratified exit by a measurable amount — and a follow-up study, on
the book, would be needed before anything traded differently."* That still stands, and no parameter
moves.

**§9 anticipated most of this and missed one thing.** It registered that *"a mean net R near zero
in BOTH arms"* would not refute H1 and would be the most consequential thing the study could find.
What it did not anticipate is both arms being **clearly negative** while the difference is clearly
positive. The registered rule has no clause for that, so it returns `ACCEPT`, and the honest
reading is in the title of this file.

## The tails, which is what the owner asked for, and the target is what shapes them

`PR-005`'s log at the same stop and hold **without a target** is right-skewed at **+1.61**: losses
cluster at −1R and a thin right tail pays for them. Under the ratified exit that reverses.

| | control | ranked |
|---|---|---|
| skew | **−2.41** | **−0.25** |
| sd of net R | 1.167 | 1.014 |
| p1 | −2.863R | **−1.735R** |
| worst single trade | **−47.24R** | −7.16R |
| p95 | +0.971R | +0.971R |

**The 1R target caps every winner and caps no loser**, so the distribution turns left-skewed by
construction: p95 is +0.971R in both arms — the target, minus costs — while the left side runs to
−47R. A `stop_gap` on a name whose stop is a small fraction of its price is the whole left tail,
which is `EVIDENCE_SUMMARY` §17 and `DR-006` §10.3 showing up in a different measurement.

**The screen's largest measurable effect is on that tail, not on the winners.** p95 is identical.
p1 improves by 1.13R, the worst trade by 40R, and the standard deviation by 13%.

## Where the +0.096R comes from, decomposed rather than asserted

| | control | ranked | |
|---|---|---|---|
| reached the target | 42.48% | **44.72%** | the largest single driver |
| stopped, gapped | 8.86% | **6.73%** | worth about +0.012R — see below |
| stopped, clean | 37.44% | 39.33% | |
| timed out | 11.22% | 9.21% | |

**Gap avoidance is real and it is not the explanation.** §17 measures a gap stop at −1.712R against
a clean stop's −1.137R, so 2.13 percentage points fewer gaps is worth about **+0.012R** — roughly
**13% of the in-sample difference**, and less out of sample where the gap gap narrows to 0.78pp.
The rest is the target being reached more often.

## The cost stress, which is where this nearly went wrong

**Found by reading the verdict before reporting it.** Every arm was being differenced against the
1× control, so `ranked_3x` carried *ranked at 3× minus unselected at 1×* — a selection change and a
cost change added together, which is not a quantity anyone asked for. That is `PR-002`'s exact
shape and gate 25's reason for existing: a perturbation declared, run, and never read into the
comparison. Corrected, three mutations of the mapping killed, and the study re-run.

| window | ranked_3x − unselected_3x | 95% interval | width |
|---|---|---|---|
| in-sample | **+0.311R** | [+0.268, +0.359] | 0.091 |
| out-of-sample | **+0.231R** | [+0.085, +0.342] | **0.256 — over the floor** |

**The difference survives triple costs and grows.** Levels collapse — the ranked arm reads −0.299R
and the control −0.610R — but the gap widens, because the control is hurt more. **Stated as a
hypothesis and not a finding:** slippage is charged on price and R is `2 × ATR`, so an arm whose
names carry a larger `ATR / price` pays less per bp in R. That is testable and this study did not
test it.

**The out-of-sample stressed interval is wider than the registered power floor.** §6 does not read
it, so no verdict rests on it, and it is reported as underpowered rather than as a result.

## The registered diagnostics, neither of which §6 reads

**The ratified target costs money, and it does not separate from zero.**

| window | no target − 1R target | 95% interval | win rate |
|---|---|---|---|
| in-sample | +0.026R | [−0.039, +0.093] | **−8.16pp** |
| out-of-sample | +0.052R | [−0.038, +0.157] | **−8.64pp** |

**The direction agrees with `EVIDENCE_SUMMARY` §17's arithmetic and the interval contains zero on
both windows.** So the target's cost is *consistent with* the mechanism §3 predicted and is **not
established**. What IS established is the trade it makes: the target buys about **8.5 percentage
points of win rate** and hands back the right tail — the two-slot arm's payoff ratio is 1.145
against 0.743.

**§3's registered prediction was directionally right and numerically off.** It predicted the
break-even win rate would rise *"from about 41% to about 50%"*. Measured: **46.62% → 57.38%**. The
DELTA was close (+10.8pp against +9pp predicted); both levels are higher than `PR-005`'s because
this study charges 25 bps a side where that one charged 5.

**The top four does not replicate.** `ranked_top4` reads +0.159R [+0.064, +0.278] in sample and
+0.051R [−0.083, +0.199] out of sample — one window excluding zero, both intervals wider than the
power floor, on 216 and 228 trades. Consistent with `PR-015` §16: a four-position book is too noisy
an instrument, and that is a fact about the instrument.

## What the power floor and the sample rule caught

Nothing was refused this time — every §6 cell qualified. The floor bit on two diagnostics
(`ranked_top4` both windows, `ranked_3x` out of sample) and those are reported as underpowered.

**§3's minimum detectable effect was conservative by a factor of two.** It registered 0.14R from
`PR-005`'s monthly sd of 0.5444R. The realised half-widths are **0.040R and 0.070R**, because this
study's months carry thousands of trades where `PR-005`'s carried single figures, so its monthly
means are far less noisy. Registering a floor that turned out generous is the right direction to be
wrong in, and it is recorded because the next study should use this study's dispersion and not
`PR-005`'s.

## `DR-042`'s tie-break is immaterial, measured

**132 ambiguous bars in 286,096 trades — 0.05% in both arms.** Reaching a stop 2 ATR below entry
and a target 1 R above it in one session needs a range of **four ATR**, and that is rare.

The rule can go either way and move nothing this study reports. **The ruling is still the owner's**
— they ruled on 2026-09-07 that the measured share comes first, and `tools/probe_ambiguous_bar.py`
will fetch these 132 sessions at one-minute resolution and report which leg printed first. Until
`DR-042` §8 is closed this file stays `PRELIMINARY`, and 0.05% is a reason to close it quickly, not
a reason for an agent to close it.

## What it costs the programme

**2 trials**, declared in §6a before the run: the `ranked` arm, and `unselected_two_slot` as a
second exit configuration. The control spends none. Cumulative: **97**.

## What this does NOT establish

* **That anything is profitable.** Both arms lose. Nothing here is a reason to trade.
* **Anything about a book.** The unit is one trade — no cap, no sector limit, no correlation limit,
  no capacity. `PR-015` measured the book and found nothing separable from zero.
* **That the screen has alpha rather than a cost profile.** Part of the difference is gap
  avoidance, measured at about 13% of it, and the cost-stress result suggests a further part may be
  cost sensitivity rather than selection. Both are properties of *which names* the screen picks,
  which is a real effect and a different claim from *forecasting*.
* **That the target should change.** Its diagnostic contains zero, and `DR-029` chose it so a trade
  completes and can be observed, not for expectancy.

## Reproducing

```bash
PYTHONPATH=$PWD/src python tools/run_pr016.py --data data
```

```bash
PYTHONPATH=$PWD/src python tools/run_pr016.py --report
```

```bash
PYTHONPATH=$PWD/src python tools/verify_pr016_qa.py --data data
```

## The QA stage, done

`BACKTEST_PROTOCOL` §7 asks for *"a repeat INDEPENDENT check of part of the sample"*, reconstructed
*"from the stored evidence alone... not from the run's own output"*. `tools/verify_pr016_qa.py`
imports nothing from the harness it checks — not `ExitPolicy`, not `run_arm`, not `derived_observations.atr:compute`,
not `CostModel`. Wilder's true range and smoothing, both fill rules and the four ordering rules are
written out again from the specifications they come from. It rebuilds each sampled trade from
`(instrument, entry date)` plus the ratified parameters, and refuses outright if the constants it
restates differ from the ones `PR-016.json` recorded.

| | |
|---|---|
| sampled, seeded 20260908, 400 per series | **2,400** over 1,525 instruments |
| **agreed on every field** | **2,390** |
| label only, final bar | 10 |
| **disagreed** | **0** |
| not reconstructable | **0** |

Entry price, stop, exit price, exit date, exit reason, shares, risk per share and costs, compared
as exact `Decimal` — §7's own sentence is that a disagreement is a defect and not a rounding
difference to wave through, so nothing is compared approximately.

**What the re-check found that no test had.** Ten trades — every one an entry dated 2026-08-07 —
are recorded `end_of_data` where the evidence says `time`. `run_arm` iterates `range(len(bars) - 1)`
because forming an ENTRY needs `bars[i + 1]`, so the final stored bar is never evaluated for an
EXIT either: a position that completes its holding period there is closed as `END_OF_DATA` at the
last close instead of as `TIME` at the same close.

**Identical bar, identical price, identical net R.** No figure in this report moves. What does move
is the `exit_reason` mix: the control shows 1,087 `end_of_data` out of sample and an unknown share
of those are time exits under another name. Counted in its own bucket rather than folded into
either — burying it in "agreed" would hide a real disagreement between the record and the evidence,
and calling it a defect would overstate one that changes nothing.

**What this does and does not say.** It says the trade log says what the evidence says. It says
nothing about whether the STUDY is right — a faithful log of a badly designed study is still a
faithful log.
