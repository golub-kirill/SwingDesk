# PR-029 RESULT: the card did better on dates when SPY sat below its 200-day mean, by an amount the four years cannot separate from zero

```
prereg:        PR-029
ran:           2026-09-19
verdict:       INCONCLUSIVE, as section 3 predicted. Dates signalled with SPY below its 200-day
               mean less dates above, each date's mean excess over SPY: +0.477% per dollar a trade
               [-0.312, +1.317], 1.63 wide. 274 dates below, 732 above. The exploration saw the same
               direction on 2022-2026
status:        final - a property of the date, read two-sided; the shared pass and checks are
               PR-026's
tool:          tools/run_pr026.py
evidence:      PR-029.json; PR-026's sample, power estimate and QA rows
trials:        1, declared before the run
```

---

## Read this first

**Same direction as the exploration, not enough to tell.** On 2018-09..2022-08 the card's trades
signalled with `SPY` below its 200-day mean beat `SPY` by **+0.48%** a trade more than those
signalled above — an interval from −0.31% to +1.32%.

| `PR-029`, per dollar a trade | estimate | 95% interval |
|---|---|---|
| **dates below less dates above (net)** | **+0.477%** | **[−0.312, +1.317]** |
| gross | +0.461% | [−0.324, +1.294] |
| cost-adverse | +0.476% | [−0.319, +1.325] |
| the below dates against `SPY` | +0.083% | [−0.445, +0.867] |

§6: containing zero and wider than the floor — **`INCONCLUSIVE`**. 274 of 1,006 dates sat below the
mean, in three spells — late 2018, spring 2020, 2022 — which is why the interval is 1.63 wide, 1.71×
the predicted 0.95. The published expectation is the other sign (momentum suffers after the market
turns down); two windows now point this way, each unable to read it.

**What it licenses:** nothing about the card. A regime gate is a further study, and it needs more
downturns than any four years hold.
