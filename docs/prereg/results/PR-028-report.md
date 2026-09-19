# PR-028 RESULT: re-priced at the close, PR-019's wide exit points up against the ratified exit — by less than a two-point interval can read

```
prereg:        PR-028
ran:           2026-09-19
verdict:       INCONCLUSIVE, as section 3 predicted. Per entry, the wide exit's excess over SPY
               less the ratified exit's is +0.699% per dollar a trade [-0.992, +2.615], 3.61 wide
               against the 0.30 floor. Beside it: the wide exit's own excess over SPY, +0.428%
               [-1.579, +2.695]
status:        final - PR-019's selected cell re-priced, not re-selected; the shared pass and
               checks are PR-026's
tool:          tools/run_pr026.py
evidence:      PR-028.json; PR-026's sample, power estimate and QA rows
trials:        1, declared before the run
```

---

## Read this first

**Too noisy to read, and pointing the way `PR-019` did.** The same 40,180 entries, walked under a
4 ATR stop with no target for 60 sessions, earned **+0.70%** a trade more against `SPY` over their own
days than under the ratified exit — an interval from −0.99% to +2.62%.

| `PR-028`, per dollar a trade | estimate | 95% interval |
|---|---|---|
| **wide exit less ratified exit, each against `SPY` (net)** | **+0.699%** | **[−0.992, +2.615]** |
| gross | +0.683% | [−1.017, +2.611] |
| cost-adverse | +0.735% | [−0.952, +2.649] |
| the wide exit against `SPY` | +0.428% | [−1.579, +2.695] |

§6: containing zero and wider than the floor — **`INCONCLUSIVE`**. The width, 3.61, is 1.76× the
predicted 2.05: a 60-session hold carries two months of each name's own drift against the index,
and adjacent months' holds overlap, which the pilot of every fourth date understated.

**Note what the level says and does not.** Against `SPY`, the wide exit's own point estimate is
positive here, where `PR-019b` found it −0.154R on 2022–2026. On this window it is an interval four
points wide around a small number; it is not a reversal of `PR-019b`.

**What it licenses:** nothing. An exit that could matter by a point a trade needs a design whose
width is a fraction of that — more years, or a statistic that does not carry the market's drift for
sixty days. Both are further studies.
