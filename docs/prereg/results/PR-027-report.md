# PR-027 RESULT: the leader bought on a pullback did not beat the leader — the exploration's best slice reads slightly negative on a window it had not seen

```
prereg:        PR-027
ran:           2026-09-19
verdict:       INCONCLUSIVE, as section 3 predicted, and on the wrong side of it. Per date, the
               pullback entries' excess over SPY less all entries' is -0.094% per dollar a trade
               [-0.392, +0.176], 0.569 wide against the 0.30 floor. The exploration that suggested
               it saw +0.57% on 2022-2026. Beside it: the pullback entries trail SPY by -0.375%
               [-0.931, +0.213]
status:        final - one rule fixed before the run; the shared pass and checks are PR-026's
tool:          tools/run_pr026.py
evidence:      PR-027.json; PR-026's sample, power estimate and QA rows
trials:        1, declared before the run
```

---

## Read this first

**The idea the author liked best failed first.** `CARD-001`'s top decile, bought only when the signal
close sits below its own 20-day mean, against the whole decile, on 2018-09..2022-08: **−0.094%** a
trade [−0.392, +0.176]. The slicing of `PR-024`'s trades that suggested it read **+0.57%** on the four
years after. Same rule, a different four years, and the sign went.

| `PR-027`, per dollar a trade | estimate | 95% interval |
|---|---|---|
| **pullback entries less all entries (net)** | **−0.094%** | **[−0.392, +0.176]** |
| gross | −0.105% | [−0.400, +0.162] |
| cost-adverse | −0.080% | [−0.385, +0.195] |
| the pullback entries against `SPY` | −0.375% | [−0.931, +0.213] |

§6: the interval contains zero and is wider than the floor — **`INCONCLUSIVE`**. It cannot say the
pullback is worse; it can say the +0.57% did not come back. 13,087 of 40,240 entries were
pullbacks, on 996 dates. The width, 0.569, is 1.09× the predicted 0.522.

## What this establishes

**That a pattern read off a strategy's own trades did not replicate** on a window chosen before the
run. `PREREG_TEMPLATE` rule 3 is why the exploration was never evidence; this is what that rule
buys. Everything else about the run is in `PR-026-report.md`.

**What it licenses:** nothing about the card. A pullback entry is not established, and on this
window it points the other way.
