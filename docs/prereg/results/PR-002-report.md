# PR-002 RESULT: breadth separates outcomes — and one confound could explain all of it

```
prereg:     PR-002 (registered 2026-08-02, amended twice before running)
status:     reported
run:        2026-08-02
verdict:    ACCEPT - the first hypothesis this project has failed to refute
data:       PR-002.json
```

---

## The hypothesis

Registered: *a regime label carries decision-relevant information — the distribution of forward
outcomes for the same setup differs materially across regimes, measured out of sample.*

Not refuted. `BREADTH_MEDIAN` separates outcomes on the test window under both cost regimes, under
the registered baseline **and** under a stricter one added post-hoc.

## How the variant was chosen

Thresholds fitted on **train only** (2016-08-01 → 2021-07-28, 1257 sessions). The variant selected
on **validation** (2021-07-29 → 2023-07-27, 502 sessions) by **stability** — fewest label flips per
100 labelled sessions — never by outcome:

| Variant | flips / 100 sessions |
|---|---|
| **`BREADTH_MEDIAN`** | **3.785** ← selected |
| `VOL_TERCILE` | 5.179 |
| `BREADTH_TERCILE` | 5.777 |
| `BREADTH_X_VOL` | 5.777 |

Selecting on the outcome difference would have been the study answering its own question. The
registration prohibited it, and the prohibition bound: the selected variant was not chosen for
separating best.

Fitted breadth boundary: **0.647** — the train-window median share of the universe above its own
200-day average. Frozen, then applied forward.

## Result — test window only, 2023-07-28 → 2026-07-31

`BREADTH_MEDIAN`, 1183 trades at 1× costs:

| Regime | trades | mean net R |
|---|---|---|
| `BREADTH_LOW` (≤ 0.647) | 466 | **+0.2299** |
| `BREADTH_HIGH` (> 0.647) | 717 | **−0.1304** |

Range **+0.3602R**, against a random-partition baseline whose 95th percentile is 0.1819 —
**percentile 100.0**.

At 3× costs: `LOW` +0.1084, `HIGH` −0.2281, range +0.3365R, percentile 100.0. The separation is not
a cost artefact; the whole distribution shifts down and the gap stays.

**The direction is the finding, and it is counterintuitive.** Breakouts bought when *fewer* than
two-thirds of the universe is above its 200-day average outperform breakouts bought when *most* of
it is — by about a third of an R per trade. The naive expectation is the opposite.

## The post-hoc check, and why it was needed

**Not part of the registered decision rule.** The registered baseline permutes individual trades,
which assumes they are exchangeable. They are not: on any session dozens of instruments fire
together, so trades within a regime are clustered in time and correlated. Under clustering the
effective sample is far smaller than 1183, and a trade-level permutation understates the null's
spread — which inflates the observed percentile.

So a second baseline permutes the **date → label** assignment instead, preserving both the number of
sessions per regime and the clustering of trades within a session. It is strictly harder to beat.

| Variant | trade-null (registered) | date-block null (post-hoc) |
|---|---|---|
| `BREADTH_MEDIAN` 1× | 100.0 | **100.0** separates |
| `BREADTH_MEDIAN` 3× | 100.0 | **99.6** separates |
| `BREADTH_TERCILE` 1× | 99.8 | 98.2 separates |
| `BREADTH_X_VOL` 1× | 91.6 | 94.8 **does not** separate |
| `VOL_TERCILE` 1× | 85.0 | 82.3 does not separate |

The check earns its place: `BREADTH_X_VOL` clears the trade-level null at 3× and fails the
date-block null at 1×, which is exactly the inflation the correction was added to catch. The
selected variant survives both.

## What this does and does not say

**Does:** on this universe, this trigger and this exit model, the share of instruments above their
own 200-day average, thresholded at a boundary fitted years earlier, sorts subsequent breakout
outcomes by roughly a third of an R per trade, out of sample, under cost stress, and under a null
that respects date clustering.

**Does not:** say the effect will persist, that it is exploitable after portfolio constraints, or
that breadth *causes* anything. And it does not say what a strategy should do — a regime is
`измеритель, а не источник уверенности`, a gauge and not a source of confidence (M30-T0450). Acting
on it is `M30-T0451`, a separate Untested topic.

## The confound that could explain the whole thing

**Survivorship is absent, and this is where it bites hardest.**

Low-breadth periods are drawdowns. In a survivors' universe, the instruments that failed *during
those drawdowns* are missing from the sample entirely — they were delisted and no free source
serves them (`DR-003`). So the `BREADTH_LOW` cell is measured over exactly the instruments that
survived the conditions defining that cell.

That is not a generic caveat. It is a mechanism that would produce this specific result — a positive
mean in the stressed regime — with no real effect present. It cannot be measured or bounded on free
data.

**Treat the direction as unconfirmed until it is reproduced on survivorship-complete data.** The
separation itself is harder to explain away than its sign, but the sign is the part anyone would act
on.

## Other limitations

| | |
|---|---|
| **single market** | US only. §6 required significance in both countries independently; Canada cannot be enumerated (`DR-003`), so that cannot be met and the result is reported as single-market, which §6's inconclusive branch anticipates. |
| **one trigger, one exit model** | 20-day breakout, 2×ATR stop, 20-session time exit. A different setup could reverse this. |
| **breadth is of our universe** | 68 instruments, not the market. The measure describes the sample it was computed over. |
| **one test window** | 755 sessions, 2023-07-28 onward — a single, mostly rising market. A regime study on a window containing one regime transition is weaker than its trade count suggests. |
| **no portfolio** | independent trades, no position or correlation limits. |
| **VOL_TERCILE's thin cell** | 7 trades in `VOL_LOW`. Reported, and its verdict refused on that basis. |

## Consequence

`regime.classifier_rule` is set to **`BREADTH_MEDIAN`, boundary fitted on the training window**,
provenance `validated:PR-002` — the first `validated` parameter in this project.

That provenance is permitted on survivorship-incomplete data only because the owner decision of
2026-08-02 allows advancement *provided the record discloses the coverage*, and the disclosure above
is that record. Anyone reading the value must be able to reach this page in one step, which is why
the registry note names the confound rather than the result.

## Reproducing

```bash
python tools/run_pr002.py --sample 320 --seed 20260802
```
