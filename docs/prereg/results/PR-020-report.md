# PR-020 RESULT: the study failed its own null check out of sample, and its interval there is 3.7 times wider than promised

```
prereg:        PR-020
ran:           2026-09-13
verdict:       INCONCLUSIVE - and §9 refuses even that reading. Out of sample, trade minus the
               costed pool is -0.1412R [-0.4815, +0.0360]: 0.518 wide against the 0.15R floor, where
               §3 promised a half-width of 0.0704 and the study realised 0.2587. And the null's own
               check - every admitted name held the same way against the same pool - read -0.0669R
               out of sample, beyond the 0.05R §9 allows, so the pool leg is suspect and no verdict
               is read from it. In sample, where the estimator was calibrated, it held: -0.0160R
               [-0.0782, +0.0334], half-width 0.0558 against 0.0732 predicted
status:        final on DR-042's terms - no stop and no target, so no bar was ambiguous
tool:          tools/run_pr020.py, sized by tools/power_pr020.py
evidence:      PR-020.json, PR-020-power.json
trials:        1, declared before the run
```

---

## Read this first

**This study does not answer its question.** It was registered to say whether the ratified screen's
selected names, held a week with no stop, beat the universe they come from. Out of sample it cannot
say: the interval is 0.518 wide, and the check the registration put in front of the verdict failed.

**Why, measured after the run: the pool leg is expressed in the trade's own R, and the screen
selected cash.** §5 multiplies the pool's return over each trade's sessions by that trade's
`entry / risk`. For an equity whose 2 ATR is 5% of its price the factor is about 20; for a T-bill
ETF it is over a thousand. On 2022-11-04, in a bear market where cash beat `SPY`'s path, the ratified
screen's top decile held **SHV, TBLL, BIL, SGOV, GBIL, USFR, FTSM, TFLO, JPST, ICSH and GSY**. The pool rose
about 5% the following week, which in SHV's R is **+73R**; SHV itself lost 5.7R — its own round trip,
in the same units. **38 trades with `entry / risk` above 100 carry 85% of the out-of-sample
difference**; the other 7,198 average −0.021R. The same arithmetic broke the null's check.

**This is a defect in the design, and the design was mine.** It came from `PR-019b`'s `SPY` leg and
`measure_universe_null`'s pool, which express a basket's return in the trade's R — right for their
question about a constant-risk book, wrong for a question about what the screen knows, and absurd for
a cash fund whose round trip exceeds the whole R. Nothing in the registration bounded it.

Derive every figure with `python tools/run_pr020.py --report`, never from these lines.

## §9, which had to pass before anything else could be read

**The reproduction passed — every digit.** `PR-019`'s binding cell, rebuilt through the streamed
loader on the same store instant, read from `PR-019.json` by `run_pr020.reproduction`:

| `h60_stop4.0`, selected | this run | `PR-019` committed |
|---|---|---|
| in sample | 4,935 trades, +0.1080R [−0.1275, +0.3358] | **identical** |
| out of sample | 7,236 trades, +0.0528R [−0.1106, +0.2234] | **identical** |

12,176 entries realised by the candidate, 5 dropped to `PR-019`'s common set — the 5 the 4 ATR cell
refused, exactly as registered — leaving 12,171. **No trade lacked a pool price**: 0 selected, 0 of
78,187 unselected.

**The null's own check failed out of sample.** Every admitted name, held 5 sessions with no stop,
against the same costed pool:

| window | trades | trade − costed pool | §9 allows |
|---|---|---|---|
| in sample | 31,378 | −0.0377R [−0.1729, +0.1618] | within 0.05R of zero — **passes** |
| out of sample | 46,809 | **−0.0669R** [−0.1831, +0.0525] | **fails** |

A pool made of the very names being held should differ from them only by commission and weighting.
§9 set the tolerance before the run and this is outside it, so **the pool leg is treated as wrong
and the verdict is not read.** Both intervals contain zero; the rule is on the observed mean, and it
was written that way on purpose.

## The verdict, as §6 would have read it

| `h5_stopnone`, 5 sessions, no stop | in sample (printed, never read) | out of sample |
|---|---|---|
| trades · entry months | 4,935 · 51 | 7,236 · 54 |
| the trade, net | −0.1341R [−0.2766, −0.0427] | −0.1433R [−0.3054, +0.0114] |
| the pool, charged 25 bps a side | −0.1180R [−0.2524, −0.0204] | −0.0020R [−0.2350, +0.3492] |
| **trade − costed pool** | **−0.0160R [−0.0782, +0.0334]** | **−0.1412R [−0.4815, +0.0360]** |
| width | 0.112 | **0.518** |

Sample rule met (7,236 trades over 54 months against 200 and 24). Power floor **not** met out of
sample: 0.518 > 0.15. **`INCONCLUSIVE`** by `run_pr019b.verdict_for` — and not read, per §9.

**Perturbations**, each moving one thing:

| | in sample | out of sample |
|---|---|---|
| `pool_zero_cost` — the free pool | −0.1243R [−0.1840, −0.0758] | −0.2579R [−0.6279, −0.0695] |
| `cost_stress_3x` — the trade at 3× | −0.2415R [−0.2998, −0.1921] | −0.3837R [−0.7810, −0.1832] |
| `SPY`, diagnostic | −0.1511R [−0.2112, −0.0887] | −0.2847R [−0.6447, −0.0967] |

**The design decision the registration made before the run is visible here.** Against a free pool
the difference is about 0.11R lower in sample — the round trip, which §3 estimated at a tenth of an
R. Had the free pool been the primary, the in-sample reading would have been a clean negative and
would have said nothing about the screen.

**The tail**, printed beside the mean as `C-8` requires while unruled: 6.38% of trades below −2R in
sample and 6.44% out, 1.40% and 1.65% below −3R, worst excursions −7.74R and −9.87R — five sessions
with no stop.

## §3's prediction, graded

* **Sign and centre**: predicted `NULL`, centred +0.00R to +0.05R. In sample the difference is
  −0.016R inside the floor — the shape predicted, slightly the wrong side of the centre, and never
  read. Out of sample there is nothing readable to grade.
* **Precision**: predicted 0.0704 out of sample. In sample the estimator's own window realised
  **0.0558 against 0.0732** — 24% narrower, the conservative direction of `PR-019`'s calibration.
  Out of sample it realised **0.2587, 3.7×**. The estimator did not fail on its own window; the out-of-
  sample window behaved differently, and the next section is what differs.

## Why the out-of-sample window is wide — measured after the run, EXPLORATORY

`run_pr020.build` re-run unchanged, capturing each row's instrument and `entry / risk`; nothing about
the registered result moves. Mean `trade − costed pool` by the trade's `entry / risk`, and each
bucket's share of the window's SUM:

| selected, out of sample | trades | mean | share of the sum | mean \|pool R\| |
|---|---|---|---|---|
| 0–10 | 899 | +0.0347R | −0.03 | 0.137 |
| 10–25 | 4,441 | −0.0335R | 0.15 | 0.363 |
| 25–50 | 1,704 | −0.0118R | 0.02 | 0.664 |
| 50–100 | 154 | −0.0971R | 0.01 | 1.177 |
| **above 100** | **38** | **−22.8834R** | **0.85** | **27.542** |

In sample no selected trade sits above 100 — the screen took cash only when cash beat the index —
and the in-sample difference is spread across the buckets. **The null's check fails the same way**:
every admitted name's trades above 100 are 4.0% of them in sample and carry 99% of the −0.0377R, and
4.7% out of sample carrying 49% of the −0.0669R; out of sample the 25–100 buckets drift as well
(−0.115R and −0.171R), because 2022–23 bond funds sit there.

The largest out-of-sample rows are all the same event:

| instrument | entry | `entry / risk` | trade | pool leg | difference |
|---|---|---|---|---|---|
| SHV | 2022-11-04 | 1,390.7 | −5.676R | +73.197R | −78.873R |
| TBLL | 2022-11-04 | 1,330.8 | −6.889R | +70.044R | −76.933R |
| BIL | 2022-11-04 | 1,343.3 | −5.970R | +70.704R | −76.673R |
| SGOV | 2022-11-04 | 1,265.9 | −5.434R | +66.630R | −72.064R |
| GSY | 2023-03-03 | 761.6 | −2.729R | −44.954R | +42.224R |

**One re-read, at a threshold derived before this run.** `DR-005` charges 25 bps of price a side, so
the round trip costs `0.005 / (2 × ATR / price)` R, and below a ratio of 0.005 it exceeds the whole
R — measured on 2026-09-08 and recorded then, before this study existed. In this study's units that
is `entry / risk` above 200. Re-read with those trades removed, **exploratory and not a verdict**:

| `entry / risk` ≤ 200 | out of sample, kept | trade − costed pool |
|---|---|---|
| selected | 7,210 of 7,236 | **−0.0297R [−0.1121, +0.0299]** — 0.142 wide |
| every admitted name, the null's check | 45,799 of 46,809 | −0.0496R [−0.0903, −0.0100] |

In sample the cut removes no selected trade, and the null's check reads −0.0055R [−0.0568, +0.0584]
on 30,642 of 31,378. The 26 selected trades removed are all cash and short-bond funds — BIL, BILS,
FLOT, FLRN, FTSM, GBIL, GSY, ICSH, JMST, JPST, LDUR, MINT, NEAR, PTLC, PULS and the rest.

**Twenty-six trades out, and the width falls from 0.518 to 0.142 — inside the floor, at the half-width
§3 predicted (0.071 against 0.0704).** Read the way §6 would, it has the shape of the `NULL` §3
predicted. **It is not that verdict**: the cut was made after the study had shown where its width came
from, and the null's check still reads −0.0496R — inside 0.05 by a hair, with an interval that
excludes zero — because names between 100 and 200 are still leaning on the pool leg. What it does say
is that the instrument was sharp enough; the construction was not.

## What it means for `PR-019b` and `EVIDENCE_SUMMARY` §20.7 — the same construction

`PR-019b` paired each trade with `SPY` in the trade's R, and `measure_universe_null` with the pool
the same way. **The same capture on `PR-019b`'s own rows** — its registered result does not move:

| `h60_stop4.0` selected, out of sample, `entry / risk` | trades | mean trade − `SPY` | share of the sum | mean \|`SPY` R\| |
|---|---|---|---|---|
| 0–10 | 4,084 | −0.0012R | 0.00 | 0.351 |
| 10–25 | 2,960 | −0.2611R | 0.69 | 0.698 |
| 25–50 | 154 | −0.2683R | 0.04 | 1.152 |
| 50–100 | 12 | −4.0298R | 0.04 | 6.774 |
| above 100 | 26 | −9.5876R | 0.22 | 10.467 |

**Cash is a quarter of it there, not the whole.** The short-bond and cash funds the screen took on
2022-11-04 — GSY, NEAR, VUSB, PULS, RAVI and others — carry about 26%. **Most of the rest is the
10–25 bucket**: names whose 4 ATR is 4–10% of their price, where one R buys a large notional and the
`SPY` leg is a full-beta position on all of it. **The high-volatility half, 4,084 trades, matches the
index to −0.001R** — a subgroup read after the fact, exploratory.

**That weighting is not an error in `PR-019b`'s question.** A constant-risk book really does hold its
largest notional in its quietest names, and in a rising market that notional lags the same money in
the index; comparing per R is comparing the book as it is sized. What the table says is where the gap
sits — in how the book is sized across volatility more than in what was selected — which is §20.6's
own caveat, now measured. **The part that is an artifact is the cash**, whose round trip exceeds the
whole R. At the threshold derived before any of this ran, exploratory:

| `h60_stop4.0`, `entry / risk` ≤ 200 | kept | trade − `SPY` |
|---|---|---|
| selected, in sample | 4,935 of 4,935 | −0.1057R [−0.2229, +0.0384] |
| **selected, out of sample** | 7,217 of 7,236 | **−0.1310R [−0.2319, −0.0453]** — 0.187 wide |
| every admitted name, out of sample | 46,221 of 46,687 | −0.2541R [−0.3866, −0.1349] |

**`PR-019b`'s reading survives the cut**: 19 cash trades out, the gap moves from −0.1543R to −0.1310R,
still wholly below zero and still wider than the floor — the cash was worth about 0.02R of it.
**`PR-020` is the study the construction broke**, because a question about what the screen KNOWS
should weigh trades equally, and this one weighed a T-bill fund a thousand times an equity.

## What this licenses

**Nothing about the screen.** The registered question is unanswered, and the in-sample reading —
which looks like the `NULL` §3 predicted — was registered as never read and is not read here.

**Nor does the re-read.** It removes trades by a threshold that predates this study, and it is still
a look at data this study already showed; it says what the construction was doing, not what the
screen knows. **The question stays open, and asking it again is owed two things first**: a null that
cannot turn a low-volatility name's notional into tens of R — `entry / risk` bounded as an entry rule,
or both legs paired per unit invested — and a fresh power estimate under that construction. `TODO.md`
§5 carries both.

**What it does license, about the live system rather than the study:** by the path-strength
rule the ratified screen's top decile took T-bill funds in the 2022 bear market, and a trade in
one loses about 5R to its own round trip. The four-slot book ranks by score, and `DR-006` §11.3
found such names never above 52nd, so the book itself likely would not have bought them; every
other use of the decile would. The owner ratified the floor the same day: `2 × ATR / price ≥
0.005`, built in a separate change.

## What the study cost

One trial, declared before the run. `python tools/trial_budget.py` carries the cumulative figure.
