# PR-005 RESULT: the definitions select different instruments that then do the same thing

```
prereg:     PR-005 (registered 2026-08-02)
status:     reported
run:        2026-08-02
verdict:    REJECT - the registered hypothesis is refuted
data:       PR-005.json
```

---

## The hypothesis, and what happened to it

Registered: *at least one definition's gated population produces a mean R per trade, net of costs,
that differs from the ungated population by more than sampling noise.*

**Refuted.** All four gated arms sit inside the ungated arm's permutation interval, under both cost
regimes and in both periods. The registered null — *the definitions differ in which instruments they
select and not in what those instruments then do* — is what the data shows.

## Result, 1× costs, primary period

68 US instruments, sessions 2016-08-01 → 2026-07-31, holdout from 2023-07-28.

| Arm | trades | mean R | median R | hit rate | mean MFE | mean MAE | gap exits |
|---|---|---|---|---|---|---|---|
| `NONE` | 2629 | **+0.0279** | −1.005 | 0.412 | 1.29 | −0.94 | 250 |
| `A` above long MA | 1877 | −0.0254 | −1.007 | 0.405 | 1.27 | −0.96 | 196 |
| `B` MA stack | 1474 | −0.0317 | −1.008 | 0.403 | 1.25 | −0.97 | 149 |
| `C` price and stack | 1453 | −0.0163 | −1.008 | 0.407 | 1.26 | −0.96 | 145 |
| `D` structure | 1274 | **+0.0322** | −1.006 | 0.414 | 1.32 | −0.96 | 127 |

Against the ungated reference:

| Arm | difference | permutation null | |
|---|---|---|---|
| A | −0.0533R | [−0.0939, +0.0916] | inside |
| B | −0.0596R | [−0.0986, +0.1007] | inside |
| C | −0.0442R | [−0.1019, +0.0999] | inside |
| D | **+0.0042R** | [−0.1106, +0.1099] | inside |

Every arm cleared §8's sample floor — 200 primary trades and 60 holdout trades — by a wide margin,
so this is a reject, not a refusal.

## Stability

Rankings by mean R, best first:

```
1x primary:  D, NONE, C, A, B
3x primary:  D, NONE, C, B, A
1x holdout:  D, NONE, A, B, C
```

`D` and `NONE` hold the top two places in all three. Everything below them reshuffles freely —
which is what a ranking of things that do not differ looks like. Under §6 this is academic: nothing
separated at 1× costs, so the stability check never gets a candidate to test.

## What this actually says

**1. PR-001's finding is real and, for this purpose, decorative.** The definitions genuinely select
different instruments — PR-001 measured overlaps as low as 0.30. Those different instruments then
produce indistinguishable outcome distributions. Both results are needed to know that; either alone
would mislead.

**2. `D` (structure) is the only arm that beat the reference, and it did not beat it.** +0.0042R
against a null interval of ±0.11. It ranks first in all three cuts and has the highest MFE (1.32)
and the fewest gap exits per trade. That is a hint, not a finding, and the pre-registration's whole
purpose is to stop a hint being reported as a finding.

**3. The strategy itself is at best flat and clearly negative under cost stress.** The ungated arm
earns +0.0279R per trade at 1× costs and **−0.1234R at 3×**. Every arm is negative at 3×. A median
R of ≈ −1.0 across every arm says most trades stop out and the mean is carried by a thin right tail
— 41% hit rate, mean MFE 1.29 against mean MAE −0.94.

This is a statement about **this trigger, these exits, this universe, this window** — a 20-day
breakout with a 2×ATR stop and a 20-session time exit. It is not a statement about breakouts,
trend-following, or markets.

**4. Gating reduced trade count by 28–52% and bought nothing measurable.** `D` takes 1274 trades
where `NONE` takes 2629. Whatever a trend filter is for, on this evidence it is not for improving
the average outcome of this trigger.

## Consequence

Per PR-005 §0, stated before the run:

> If it also fails to separate the definitions, the family is closed and
> `screen.trend_definition` becomes an owner preference recorded as such, not a validated choice.

**The trend-definition family is closed.** Two pre-registered studies:

- PR-001 — the definitions are not interchangeable (they select different instruments).
- PR-005 — the difference does not reach outcomes under this trigger and exit model.

`screen.trend_definition` therefore stays `unset` and, if a value is ever set, it is set by
**owner preference with that fact recorded** — provenance `owner`, never `validated:` — unless a
future study with a *different* trigger or exit model separates them. That would be a new question,
a new pre-registration, and it does not inherit these results.

## Limitations, with the result rather than beneath it

| | |
|---|---|
| **survivorship** | **absent**, and material here in a way it was not for PR-001. This study measures outcomes; instruments that delisted are missing from the outcome distribution, and delisting is not independent of trend. The result is from a survivors' universe. |
| **country** | **US only.** Canada has no free symbol directory in hand (`DR-003`). |
| **one trigger, one exit model** | 20-day breakout; 2×ATR stop; 20-session time exit; no profit target; no trailing. Two of the course's four exit slots. A different exit model could separate the arms and this result would not apply to it. |
| **no portfolio** | every signal is an independent trade. No position cap, no correlation limit, no open-risk budget. This says nothing about a portfolio. |
| **definition E** | not run (PR-001b). |
| **the whole window is one regime-mixture** | 2016–2026 contains one major drawdown and a long expansion. `WALKFORWARD_SPEC.md` §2 requires a per-regime breakdown, which needs a classifier this project does not have (PR-002). |

## Reproducing

```bash
python tools/run_pr005.py --sample 320 --seed 20260802
```

Every constant is recorded in `PR-005.json`, including the permutation seed and resample count. The
admitted universe is recorded rather than assumed reproducible — vendor availability varies.
