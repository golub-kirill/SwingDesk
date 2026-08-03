# PR-001 RESULT: the trend definitions are **not** interchangeable

```
prereg:     PR-001 (registered 2026-08-02, amended twice before running)
status:     reported
run:        2026-08-02
verdict:    REJECT - the registered hypothesis is refuted
data:       PR-001.json
```

---

## The hypothesis, and what happened to it

Registered: *the candidate definitions produce highly overlapping selections, so the choice among
them is a threshold choice (how many candidates) rather than a signal choice (which candidates).*

**Refuted.** Not one pair cleared the accept bar, and four of six cleared the reject bar.

## Result

68 US instruments, 2004 sessions common to all of them, 2018-08-09 → 2026-07-31.

| Pair | median | p10 | min |
|---|---|---|---|
| MA_STACK ~ STRUCTURE | 0.296 | 0.111 | 0.000 |
| PRICE_AND_STACK ~ STRUCTURE | 0.324 | 0.111 | 0.000 |
| ABOVE_LONG_MA ~ STRUCTURE | 0.362 | 0.167 | 0.000 |
| ABOVE_LONG_MA ~ PRICE_AND_STACK | 0.632 | 0.367 | 0.000 |
| MA_STACK ~ PRICE_AND_STACK | 0.667 | 0.286 | 0.000 |
| ABOVE_LONG_MA ~ MA_STACK | 0.786 | 0.472 | 0.030 |

Decision rule from §6, fixed before the run: accept needs median ≥ 0.70 **and** p10 ≥ 0.50 on every
pair; reject needs median ≤ 0.40 **or** p10 ≤ 0.25 on any pair.

- **Accept fails on every pair.** Even the closest, `ABOVE_LONG_MA ~ MA_STACK`, has p10 0.472.
- **Reject triggers on four pairs.**

Mean instruments selected per session, out of 68:

| Definition | mean selected | undecided rate |
|---|---|---|
| ABOVE_LONG_MA | 38.41 | 0.004 |
| MA_STACK | 38.57 | 0.004 |
| PRICE_AND_STACK | 24.56 | 0.004 |
| STRUCTURE | 22.99 | 0.000 |

## What this actually says

**1. Structure is a different signal, not a stricter one.** `STRUCTURE` overlaps the
moving-average definitions by about a third. If it were merely a tighter version of the same idea,
its selections would be a near-subset and the Jaccard would sit near `22.99 / 38.41 ≈ 0.60`. It is
half that. The instruments it picks are substantially *different* instruments, not fewer of the
same ones.

**2. Even inside the moving-average family the choice matters.** `ABOVE_LONG_MA` and
`PRICE_AND_STACK` differ by a median 0.632 — and `PRICE_AND_STACK` is logically the conjunction of
the other two, so this is the largest overlap the family can produce. It is not enough.

**3. The p10 column carries the finding.** `ABOVE_LONG_MA ~ MA_STACK` looks nearly interchangeable
at the median (0.786) and its p10 is 0.472: on the worst tenth of sessions the two definitions
agree on less than half the names. That is exactly the pattern §5 was written to catch — agreement
on calm days, divergence when the decision is hard.

**4. Minimums of 0.000 on five of six pairs.** There are sessions on which two definitions select
*disjoint* sets. Whatever these definitions measure, on some days they do not measure the same
thing at all.

## Consequence

Per §6's reject branch, taken as written:

- `screen.trend_definition` **stays `unset`**. It may not be chosen by convenience, simplicity or
  computational cost, because those criteria were only admissible under the accept branch.
- Adopting any definition now requires a **performance study** — a pre-registration that measures
  what the different populations actually do, not just that they differ.
- The three definitions built on the same two moving averages are not substitutes for one another,
  so a strategy card must name which one it uses, and a component that says "trend filter" without
  naming the definition is under-specified.

## Limitations, stated with the result rather than beneath it

| | |
|---|---|
| **survivorship** | **absent.** Delisted instruments are unavailable on free data. For an overlap study the bias is weaker than for a return study — a delisted name would be missing from every definition's selection alike — but the sampled universe is a survivors' universe and the result inherits that. |
| **country** | **US only.** Canada has no free symbol directory in hand (`DR-003`), so `BR-9`'s per-country reporting could not be honoured. This is a US result. |
| **definition E** | **not run.** ADX needs a threshold with no course basis; setting one would have answered part of the question. Deferred to PR-001b, which will sweep the threshold rather than pick one. |
| **universe** | 68 instruments surviving a random draw of 320 from 13,048 eligible rows: 215 rejected by the liquidity rule, 28 admitted but short of 2000 bars, 9 fetch failures. The history filter biases toward older listings, which is inherent in requiring a long common window. |
| **first run** | an earlier run of this study produced 45 instruments and **277** common sessions and a `reject` verdict. That verdict was **refused** under §8, which requires 2000 sessions. The numbers were similar; that is not why it was refused. |

## Reproducing

```bash
python tools/run_pr001.py --sample 320 --seed 20260802
```

Seed, sample size, liquidity rule, moving-average periods and pivot settings are all recorded in
`PR-001.json`. The universe is not identical across runs — Yahoo's availability varies — so the
admitted list is recorded rather than assumed reproducible.
