# PR-018 RESULT: the exit policy costs 0.15R a trade and buys the difference between a −7.7R tail and a −23.8R one

```
prereg:        PR-018
ran:           2026-09-08
verdict:       INCONCLUSIVE by §6's rule — both windows exceed §8's power floor, so no branch
               fires. §3's minimum detectable effect was wrong and the report says why.
               What the study nevertheless MEASURED is the largest thing in this repository:
               holding to the clock earns +0.065R and +0.040R where the ratified exit loses
               0.080R and 0.114R, and the exit removes a tail in which one trade in five
               goes below −2R
status:        PRELIMINARY on `DR-042`'s terms
tool:          tools/run_pr018.py
evidence:      PR-018.json
trials:        2, declared before the run
```

---

## Read this first

**The verdict is `INCONCLUSIVE` and it is not a null.** Both difference intervals are wider than
the 0.15R floor §8 registered — 0.451 and 0.268 — so §6 refuses to read either window, including
the out-of-sample one whose interval excludes zero. That refusal is the rule working: an interval
this wide could not have distinguished the effects the study was built to separate.

**§3's minimum detectable effect was wrong.** §3 took `PR-017`'s 0.05R on the grounds that the
arms *"share entries exactly"*. A-1, registered from the synthetic store before any real data,
recorded that they do not: a position that never stops out holds its name through the next
formation date. Measured on the real store, **7,305 hold-only entries against 11,019 ratified** — a
third fewer. ~~The pairing is far weaker than `PR-017`'s and the intervals came out five to nine
times wider than predicted. **The amendment was right and the MDE that survived it was not.**~~

> **CORRECTED 2026-09-12 — the entry gap is real, and it is not why the intervals are wide.** The
> struck sentence put the width down to the weak pairing. `tools/power_pr019.py` then measured the
> same kind of contrast — a 2 ATR stop against no stop, both at 20 sessions — with the entries
> paired **exactly**, and the in-sample half-width is still **0.187R** (corrected for subsampling
> noise; a normal approximation, so a lower bound) against this study's realised **0.226R**. Exact
> pairing removes at most about a sixth of the width. **The rest is the difference itself moving
> month to month** — in some months holding without a stop wins by a lot and in others it loses by
> a lot, and no pairing cancels that. The MDE was wrong mainly because `PR-017`'s contrast, half a
> position closed at 1R, is a far smaller change to a trade than removing its stop. Caveat: that
> estimate takes the decile within a 25% instrument subsample. Evidence:
> `docs/prereg/results/PR-019-power.json`. `PR-019` is sized from it for exactly this reason.

Derive every figure with `python tools/run_pr018.py --report`, never from these lines.

## §9's reproduction check, which had to pass before anything else could be read

| | PR-018 | PR-016's `ranked` |
|---|---|---|
| in-sample | 11,019 trades, −0.0797R, 49.98% | **11,019, −0.0797R, 49.98%** |
| out-of-sample | 16,320 trades, −0.1144R, 48.41% | **16,320, −0.1144R, 48.41%** |

**Identical to every digit on both windows.** Same construction, same entries, same exit, two
studies, two runs. `PR-017`'s analogue differed by 197 trades for a known reason; this one does not
differ at all.

## The numbers

```
series                   window               n   win%     meanR     p95
ratified                 in_sample        11019  49.98   -0.0797  +0.972
ratified                 out_of_sample    16320  48.41   -0.1144  +0.971
hold_only                in_sample         7305  53.25   +0.0645  +2.750
hold_only                out_of_sample    10774  50.16   +0.0404  +2.846
```

**`hold_only` is the first positive mean net R this project has measured on selected entries**, on
both windows. The ratified exit loses on both.

| window | ratified − hold_only | 95% interval | width | floor |
|---|---|---|---|---|
| in-sample | −0.1442R | [−0.3629, +0.0884] | 0.451 | 0.15 ✗ |
| out-of-sample | −0.1547R | [−0.2763, **−0.0080**] | 0.268 | 0.15 ✗ |

## And the MAE, which §6 requires in this paragraph rather than after it

| | worst | p01 | p05 | below −1R | below −2R | below −3R |
|---|---|---|---|---|---|---|
| `ratified` | −7.74R | −2.49R | −1.66R | 46.7% | **2.3%** | **0.4%** |
| `hold_only` | **−23.81R** | **−5.86R** | **−3.49R** | 53.3% | **21.7%** | **7.9%** |
| `ratified_no_target` | −8.92R | −2.60R | −1.76R | 52.3% | 3.0% | 0.6% |

**That is the trade, with both prices on it.** The exit policy costs roughly **0.15R a trade** and
takes the share of trades running below −2R from **21.7% to 2.3%**, below −3R from **7.9% to 0.4%**,
and the worst single excursion from **−23.8R to −7.7R**.

**This is not "the exit is a mistake".** It is "the exit buys survivability with the whole of the
return, and here is what each side is worth". Which of those two numbers matters more is a decision
about ruin, not a measurement, and `CHARTER` A-001 says whose it is.

**And the stop is doing the work, not the target.** `ratified_no_target` — stop and clock, no
take-profit — reads −0.0261R and −0.0650R with a tail almost identical to the full ratified policy:
3.0% below −2R against 2.3%. So the target costs about 0.05R and buys **nothing** on the tail; the
stop costs the rest and buys all of it.

## The finding that decides what a strategy should be

| | in-sample | out-of-sample |
|---|---|---|
| `hold_only` on the **selected** decile | +0.0645R | **+0.0404R** |
| `hold_only` on **every admitted name** | +0.0641R | **−0.1174R** |

**Holding without a stop is profitable only on the names the screen picks.** Unselected, the same
policy loses 0.117R out of sample. The screen is worth **+0.158R** there — larger than the +0.088R
`PR-016` measured for it under the ratified exit, and the reason is mechanical: a stop truncates the
right tail of a name that was going to run, and the screen's whole contribution is names that run.

**So selection and exit are not independent choices.** The value of the screen depends on the exit
it is paired with, which is exactly what a strategy assembled from separately-ratified parts cannot
know.

## The perturbations

**Triple costs**: `ratified` −0.2986R and −0.3594R; `hold_only` −0.1588R and −0.2041R. Both lose,
`hold_only` by less. The ordering survives.

**Cheap execution** at `EVIDENCE_SUMMARY` §10's measured 11:00 median of 5.75 bps a side:
`ratified` −0.0017R and −0.0245R, `hold_only` **+0.1469R and +0.1305R**. **Not a claim that the
strategy can be executed there** — `DR-040` §4 records that a later entry changes the gross as well
as the cost, and this re-prices an entry struck at the open. What it says is which arm the cost
level favours, and it favours the one holding longer, because it pays the same round trip for more
gross.

## What this does NOT establish

* **A verdict.** §6 read nothing; the intervals were too wide. The levels above are measurements,
  the difference is not established, and no parameter moves.
* **That holding without a stop is safe.** One trade in five below −2R and one in twelve below −3R
  is not a drawdown, it is a way to stop trading. `PR-018` measures return per trade and models no
  account.
* **Anything per YEAR.** A-1: `hold_only` takes a third fewer trades because it holds its names
  longer. More per trade is not more per year, and this study measures only the first.
* **Anything without the survivorship caveat.** 2,598 of 2,598 decade-long instruments still trade.
* **Ten years.** 8.91, identical to `PR-016` by design.

## What it costs the programme

**2 trials**, declared before the run. Cumulative: **101**, hurdle 2.53 sd(SR).

## Reproducing

```bash
PYTHONPATH=$PWD/src python tools/run_pr018.py --data data
```

```bash
PYTHONPATH=$PWD/src python tools/run_pr018.py --report
```

The QA stage has not been run for this study; `verify_pr016_qa.py` is specific to `PR-016`'s sample
and constants, and an arm with no protective stop needs its own reconstruction.
