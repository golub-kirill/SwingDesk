# PR-026 RESULT: leaving leveraged funds out changes nothing a book would notice — and none of the four ideas the exploration found survived a window it had not seen

```
prereg:        PR-026
ran:           2026-09-19
verdict:       INCONCLUSIVE, branch NULL, as section 3 predicted. Leaving leveraged and inverse
               funds out moves the card's excess over SPY by -0.007% per dollar a trade
               [-0.039, +0.018], inside the 0.30 floor. They were 1,508 of 40,240 entries. Beside
               it: the card itself trails SPY over its own days by -0.271% a trade [-0.647, +0.135]
status:        final - one rule fixed before the run, no selection. Section 9's checks held
tool:          tools/run_pr026.py (one pass for PR-026..PR-029), sized by tools/power_pr026.py;
               the ideas' source: tools/measure_entry_features.py
evidence:      PR-026.json, PR-026-power.json, PR-026-sample.jsonl, PR-026-qa-sample.csv,
               docs/decisions/measurements/entry-features-2026-09-19.json
trials:        1, declared before the run (PR-026..PR-029 count one each)
```

---

## Read this first

**The four ideas the owner picked on 2026-09-19 came from slicing `PR-024`'s own trades.** Tested on
the 48 months before — 2018-09 to 2022-08, 40,240 entries, which that slicing never read — none of
them is confirmed:

| study | the change | what the slicing saw (2022–26) | what this window says (2018–22) | branch |
|---|---|---|---|---|
| `PR-026` | leave leveraged and inverse funds out | those funds −0.68% a trade, 423 entries | **−0.007%** [−0.039, +0.018] for the book | **`NULL`** |
| `PR-027` | buy the leader only on a pullback | +0.57% a trade, the best slice of all | **−0.094%** [−0.392, +0.176] | `INCONCLUSIVE` |
| `PR-028` | `PR-019`'s wide exit | — (`PR-019`: +0.19R) | **+0.699%** [−0.992, +2.615] | `INCONCLUSIVE` |
| `PR-029` | `SPY` below its 200-day mean | +0.77% against −0.14% | **+0.477%** [−0.312, +1.317] | `INCONCLUSIVE` |

**The pullback is the lesson.** The slicing's strongest pattern — leaders bought below their 20-day
mean, +0.57% a trade — reads slightly NEGATIVE on a window it had not seen. Registering before the
run is what stopped it from becoming a rule on the strength of the data that suggested it.

**And the card still trails the index.** Entered at the close with its own measured spreads, over
2018–2022, `CARD-001`'s trades earn **−0.27% a trade** less than `SPY` over the same days — an
interval that includes zero, and a point estimate on the wrong side of it.

## §9, which had to hold first

| check | registered | realised |
|---|---|---|
| widths against the power estimate, half to twice | `PR-026` 0.044, `PR-027` 0.522, `PR-028` 2.048, `PR-029` 0.952 | **0.056, 0.569, 3.607, 1.629** — 1.27×, 1.09×, 1.76×, 1.71× |
| the draw priced | at least 90% | **99.9%** — 40,199 of 40,240 for the baseline |
| dates, months | 500, 24 | **1,006 and 48** (996 dates hold a pullback entry) |

The two wide ones came in wider than predicted, inside the band: the pilot's every-fourth date
could not see how strongly a month's overlapping holds move together.

## The verdict, as §6 reads it

| `PR-026`, per dollar a trade | estimate | 95% interval |
|---|---|---|
| **kept entries less all entries (net)** | **−0.007%** | **[−0.039, +0.018]** |
| gross | −0.007% | [−0.038, +0.017] |
| cost-adverse | −0.007% | [−0.038, +0.018] |
| the kept entries against `SPY` | −0.271% | [−0.647, +0.135] |

The interval contains zero and is 0.056 wide, inside the 0.30 floor: **`NULL`**. Leveraged and
inverse funds were 3.7% of the decile's entries on this window; whatever they cost, a book of the
rest earns the same within four hundredths of a point.

## What this establishes, and what it does not

**Established:** on 2018-09..2022-08, taking leveraged and inverse funds out of `CARD-001`'s picks
changes the card's per-trade excess over `SPY` by nothing a 0.056-wide interval can see.

**Not established:** that holding such funds is harmless in a four-name book. A 3× fund in one of
four slots is a quarter of the book on three times the exposure; that is a risk question this
per-trade mean does not ask. The filter is `NULL` on return and remains a reasonable piece of
hygiene for the owner to weigh.

## Diagnostics — printed, never read by §6

1,508 leveraged or inverse entries; 13,087 pullback entries; 29,280 entries signalled with `SPY`
above its 200-day mean and 10,960 below. The baseline exits: target 18,670, stop 14,662, clock
4,001, gap 2,866, held 12.8 calendar days on average; the wide exit: clock 21,901, stop 15,171, gap
3,108, held 63.0. Exclusions: 39 zero-share baseline entries, 12 wide stops below zero, 7 wide
zero-share entries, 2 entry sessions not stored.

## What it changes

* **The slicing that produced four ideas is now evidence of one thing**: patterns read off a
  strategy's own trades did not carry to another four years. The next idea mined that way is
  registered the same way, or not at all.
* **`CARD-001` still does not beat holding `SPY`** — now at the close, at measured spreads, on a
  second window. `EVIDENCE_SUMMARY` §26.
* **What is left open** is the exit (`PR-028`) and the regime (`PR-029`): both point up, and both
  are too noisy on 48 months to read. Neither licenses a change.

## What the study cost

One pass of a few minutes on daily bars already stored, shared by the four; no fetch. One trial.
