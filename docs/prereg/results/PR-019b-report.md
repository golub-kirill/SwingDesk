# PR-019b RESULT: the candidate earned less than `SPY` over the same days — every interval but one says so, and the one §6 reads is too wide to

```
prereg:        PR-019b
ran:           2026-09-13
verdict:       INCONCLUSIVE - for PRECISION, and not for sign. Out of sample, trade minus SPY over
               the trade's own sessions is -0.1543R [-0.2930, -0.0501]: wholly below zero, and
               0.243 wide against the 0.15R floor, so §6 may not read it. §3 predicted the SIGN
               (at or below zero) and got it; it predicted a half-width of 0.0743 and the study
               realised 0.1214. The power estimate was wrong, and §"The precision miss" says how
status:        PRELIMINARY on DR-042's terms
tool:          tools/run_pr019b.py, sized by tools/power_pr019b.py
evidence:      PR-019b.json, PR-019b-power.json
trials:        1, declared before the run
```

---

## Read this first

**The candidate did not beat the index.** Over exactly the days each trade was exposed, the same
notional in `SPY` earned **+0.2071R** a trade out of sample; the candidate earned **+0.0528R**. The
difference is **−0.1543R, interval [−0.2930, −0.0501]** — below zero at every point.

**It is `INCONCLUSIVE`, not `REJECT`, and that is the registered rule working, not a technicality.**
§6 reads a difference only when its interval is inside the 0.15R floor, and this one is 0.243 wide.
The rule exists so that a verdict cannot be read off an instrument that was blunter than promised —
and this one was: §3 promised a half-width of 0.0743 and delivered 0.1214. **A reader who takes
"wholly below zero" as a verdict is doing what §6 forbids**, so this report does not, and says what
the numbers show beside it instead.

**What the numbers show, all in one direction:** the index beat the candidate in sample (−0.1057R,
not read), out of sample (−0.1543R), at triple trade costs (−0.2512R [−0.3608, −0.1616]), and on
every admitted name without the screen (−0.2772R [−0.4220, −0.1496]). Only one reading touches
zero: with the index leg charged `DR-005`'s costs, −0.0950R [−0.2211, +0.0028]. **And three known
biases were pointing the other way the whole time** (§5 of the pre-registration): survivorship,
a beta above one, and the index's missing dividend all flatter the candidate against this null.

Derive every figure with `python tools/run_pr019b.py --report`, never from these lines.

## §9's reproduction, which had to pass before anything else could be read

| book | window | this run | `PR-019` committed |
|---|---|---|---|
| `h60_stop4.0`, selected | in sample | 4,935 trades, +0.1080R [−0.1275, +0.3358] | **identical** |
| | out of sample | 7,236 trades, +0.0528R [−0.1106, +0.2234] | **identical** |
| `h60_stop4.0`, every admitted name | in sample | 31,320, +0.1020R | **identical** |
| | out of sample | 46,687, +0.0202R | **identical** |

**Every digit**, read from `PR-019.json` by `run_pr019b.reproduction` rather than typed. 29,031
selected signals, 12,189 after spacing at 60 sessions, 12,171 realised in both the 1× and 3× books
and nothing dropped to the common set. **No trade lacked a benchmark price** — 0 of 12,171 selected,
0 of 78,007 unselected.

## The verdict, as §6 reads it

| out of sample, `h60_stop4.0` | mean | 95% interval | width |
|---|---|---|---|
| the trade, net | +0.0528R | [−0.1106, +0.2234] | 0.334 |
| `SPY` over the same sessions, zero cost | +0.2071R | [+0.0271, +0.4142] | 0.387 |
| **trade − `SPY`** | **−0.1543R** | **[−0.2930, −0.0501]** | **0.243** |

Sample rule met: 7,236 trades over 54 entry months against 200 and 24. Power floor **not** met:
0.243 > 0.15. **`INCONCLUSIVE`** by `run_pr019b.verdict_for`, whose every branch the tests pin.

**§3's prediction, graded.** Sign: predicted at or below zero, centred −0.05R to −0.10R — realised
−0.1543R, the right side of zero and further from it than predicted. The index leg: predicted
+0.07R to +0.20R — realised +0.2071R, the top of the range. Precision: predicted 0.0743 — **wrong by
a factor of 1.64**.

## The precision miss

**The estimator missed on its own window too**, which says the fault is in the estimator and not in
the out-of-sample period: in sample it predicted a half-width of **0.0772** and the full universe
realised **0.1306**, 1.69×. Two calibration points from `PR-019` had it running 6–8% WIDE; here it
ran 40% narrow.

**The cause, predicted from arithmetic and then measured.** The power estimate is a normal
approximation that treats entry months as independent; the study resamples blocks of three. For
`PR-019`'s contrasts — one exit against another — the market largely cancels and the two agreed.
**This contrast is different in kind**: a trade held about 60 sessions spans roughly three entry
months, so the index legs of trades entered one month apart share about two thirds of their days,
and two months apart about one third. That predicts a variance factor near `1 + 2(0.67) + 2(0.33)
≈ 3` — a half-width **×1.73**, the size of the miss.

**Measured the same day, in sample only, on the power estimate's own subsample**: the lag-1 and
lag-2 autocovariances of the monthly trade-minus-`SPY` values, read against the noise-corrected
between-month variance (the subsample's noise is independent month to month, so it lives in lag 0
only), give a factor of **3.30**. Carried into the half-width, the in-sample prediction becomes
**0.1403 against the 0.1306 the full study realised** — 7% wide, the same calibration `PR-019`'s two
points showed — and out of sample 0.135 against 0.1214. **The overlap accounts for the whole miss.**
For the trade alone the same correction runs wide (0.291 against 0.232), which is the safe side for a
power estimate.

**What that costs.** `PREREG_TEMPLATE` rule 9 exists so that a study states what it can detect
before it spends a trial, and this one stated it wrong. The trial is spent. The fix is to the tool,
not the verdict — rule 3 forbids re-reading this window at a corrected width. The measurement above
was made with a scratch copy of the correction; `TODO.md` §5 carries the change to
`tools/power_pr019.py` that makes it reproducible, with its committed record, before any other
market-paired study registers.

## Perturbations, out of sample

| | trade − `SPY` | reads |
|---|---|---|
| primary: `SPY` at zero cost | −0.1543R [−0.2930, −0.0501] | below zero, too wide |
| `benchmark_costed_1x`: `SPY` charged `DR-005` | −0.0950R [−0.2211, +0.0028] | **touches zero** |
| `cost_stress_3x`: the trade at 3× `DR-005` | −0.2512R [−0.3608, −0.1616] | below zero |

**The one reading that reaches zero is the one that charges the index a round trip it would not pay
in practice** — `DR-005`'s 25 bps a side was estimated on this universe's names, and `SPY` is the
most liquid instrument there is. It is registered, it is reported, and it is the most flattering
reading the design allows.

## Diagnostics — registered, printed, never read by §6

**The in-sample window**, which selected the cell and is biased upward by that: −0.1057R
[−0.2229, +0.0384]. The cell chosen as the best of twelve on the older market still earned less than
the index there.

**Every admitted name, no screen** (`STRATEGY_CONTRACT` C-3's no-selection null against the market):
−0.3150R in sample, **−0.2772R [−0.4220, −0.1496]** out — below zero and, out of sample, 0.272 wide.
**The exit alone is worse than the index by more than the selected book is.** The screen closes about
0.12R of the gap — the same order as `PR-016`'s +0.088R and `PR-018`'s +0.158R screen effects — and
does not close it. The two books are not paired with each other, so that 0.12R is a description,
not an estimate.

**The tail**, out of sample: 0.815% of trades below −2R, worst −4.67R — exactly `PR-019`'s, as it
must be on identical trades. The candidate's tail is thin. Its level is the problem.

**Why the index leg is so large in R.** A 4 ATR stop sits far from the entry, so a trade's risk is a
small fraction of its notional, and a small index move is a large number of R. The unselected
book's index leg is larger still (+0.2973R) because unselected names are calmer, their stops are
nearer in percent, and each unit of risk carries more notional. **This is the same arithmetic that
makes a wide stop look good against a tight one, seen from the other side**: a wide stop holds more
notional per R, and in a rising market more notional per R earns more R whether or not the selection
knows anything.

## What this establishes, and what it does not

**Establishes, on measurement and not on §6:** out of sample on the current market, the candidate
earned **−0.15R a trade less than the index over the same exposure**, with every reading but the
most flattering one excluding zero, and in-sample, no-screen and 3×-cost readings pointing the same
way. Against its cheapest alternative, the 4 ATR long-hold exit has not earned its keep.

**Does NOT establish:**

* **a `REJECT`.** §6 refused it for precision, and the refusal stands. Rule 3 forbids re-reading a
  window at a different floor after the data is seen.
* **that the index would have been the better TRADE.** The null holds notional, not risk; an account
  sized to the candidate's R would hold the index at many times its ordinary position, and nothing
  here measures that book.
* **beta.** A beta above one moves the null toward the candidate's favour, so correcting for it can
  only widen the gap — but the size of the correction is not measured.
* **that the selection is worthless.** It closes part of the gap. It does not close all of it.

## What it changes

**The candidate in `STRATEGY_CONTRACT` §4 is not retired by this verdict — and no evidence here
supports it.** C-3 retires on `REJECT` or `NULL`; this is neither, so the status is unchanged and the
contract row says what was measured beside it. **The owner's working-strategy question gets the
plain version:** on 2022–2026, the best exit this programme has found on the ratified screen earned
less than holding `SPY` for the same days. A strategy card built on it would be claiming an edge its
own cheapest null does not concede.

**Owed next, in order:**

1. **the power tool** — measure the autocorrelation of monthly means and carry it into the
   half-width, before any other paired-market study registers (`TODO.md` §5);
2. **the programme's direction.** Four studies (`PR-016`..`PR-019b`) have now varied the EXIT on one
   screen and one universe. The index beats the exit alone by more than it beats the screened book,
   so the leverage is in what is selected, not in how it is left — which is where `TODO.md` §5 and
   the owner's standing direction already point: vary the universe and the signal, not the stop.
