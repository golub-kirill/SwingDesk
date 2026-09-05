# PR-011 RESULT: the stop holds BETTER on volatile names, and the hypothesis is refuted in the opposite direction

```
prereg:     PR-011 (registered 2026-09-04)
status:     reported
run:        2026-09-04
verdict:    REJECT by the registered rule - and the direction is the reverse of the one predicted
data:       PR-011.json
trials:     1 configuration, spent
```

---

Derive every figure with `python tools/run_pr011.py --data <store>`, never from this line.

## The verdict

**REJECT.** §6's rule accepts when the top band's mean overshoot exceeds the bottom band's by at
least the registered 0.25R with an interval excluding zero. The measured difference is
**−0.0747R**, interval **(−0.0900, −0.0589)** over 264 signal dates carrying both bands.

The interval **excludes zero on the negative side**, so this is not a failure to find an effect. The
effect is real, it is the size of a rounding error against the threshold, and **it points the other
way**: the band whose ATR is a large share of its price overshoots its stop *less* than the quiet
band, not more.

§9 named exactly one observation that would refute the hypothesis — *"a window in which B4's mean
overshoot is within 0.25R of B1's, or in which the CI on the difference includes zero"*. The first
clause fired.

## What ran

| | |
|---|---|
| universe | the `DR-003` liquidity rule evaluated at each signal date, US only |
| window | 1982-11-16 → 2026-09-03 — **the store's full extent**, as registered, not a chosen span |
| snapshot | `2026-09-04T18:30:15` — taken from a copy of the store between the evening passes |
| names walked | 10,377 |
| entries | 126,564, one per admitted name per 20th session, **no trigger and no gate** |
| refused | 223,822 not admitted at that date · 10,388 no ATR · 2,500 names too short · **71 non-positive stop** |

**The sample rule was met in all four compared bands**, which `PR-012` could not manage and which
was a live risk here: §8's floor is 200 stop-outs per band and the thin band returned 820.

## The numbers

Mean overshoot is in R against the placed stop; 0 means the stop-out cost exactly the 1R the risk
model assumes.

| band | ATR% of price | entries | stop-outs | mean overshoot | 95% interval | gap-through rate |
|---|---|---|---|---|---|---|
| **B1** | ≤ 3% | 72,041 | 39,742 | **0.0953** | (0.0907, 0.1003) | 20.9% |
| B2 | 3–6% | 42,414 | 19,537 | 0.0463 | (0.0428, 0.0500) | 14.4% |
| B3 | 6–10% | 9,408 | 3,741 | 0.0419 | (0.0347, 0.0499) | 14.5% |
| **B4** | 10–50% | 2,701 | 820 | **0.0264** | (0.0186, 0.0349) | 13.8% |
| B5 | ≥ 50% | **0** | 0 | — | — | — |

## The finding

**Overshoot falls monotonically as volatility rises, across all four measured bands**, and B1's
interval does not overlap B4's. The quietest names — the ones a risk model is least suspicious of —
are where a stop-out most often costs more than the 1R it was sized against.

The gap-through **rate** moves the same way and is a second, independent measurement rather than a
restatement: 20.9% of B1's stop-outs opened through the stop against 13.8% of B4's. Volatile names
both gap through less often *and* cost less when they do.

**Why, and this sentence is CONJECTURE** (`AGENTS.md` §10.4). 1R *is* 2 × ATR, so the stop distance
scales with the name's own volatility while an overnight gap need not scale with it as fast. In R
terms a quiet name's gap is therefore a larger multiple. Nothing here measures gap size against ATR
directly — that statistic was not registered, and adding it after seeing this would be an
exploratory extension rather than part of this result.

**What it means for the risk model.** The self-correction §3 named as the live possibility — *"the
sizing arithmetic widens the stop exactly as volatility rises"* — does not merely hold into the top
band. It over-corrects. `entry − stop` is a **better** risk measure on volatile names than on quiet
ones, measured in the only currency the model uses.

## B5, and a prediction that came true on real data

**No entry ever reached B5.** Every candidate whose ATR met or exceeded half its price was refused
before it could become one: **66 of the 71 non-positive-stop refusals** are B5, and the band's entry
count is zero because the refusal happens first. The arithmetic break is real and rare — 71 refusals
against 126,635 attempted entries.

**And five of the 71 are B4**, which is amendment A-2 item 3 confirmed rather than merely stated: a
band is assigned from the signal bar and the stop is placed against the next open, so a name can sit
in B4 and still produce a stop below zero. The runner records the two separately for that reason,
and the case a unit test constructs by hand occurs five times in the real universe.

## What this does NOT settle

- **The live guard stands untouched, and §9 said so before the run.** `sizing.size_long`'s refusal
  of a non-positive stop is arithmetic, not a hypothesis: those names cannot be sized at all. A null
  here — or a reversal, as here — leaves that refusal exactly where it is.
- **`screen.atr_pct_band` stays `unset`.** No value is set, none is proposed, and this study
  supplies no argument for one on risk-model grounds. `read_by: none` is unchanged.
- **`PR-011b` is untouched.** The class half — bond and foreign-market ETFs — asks a different
  question with a different mechanism, and is still exploratory in advance when written.
- **This is not an argument that volatile names are better to trade.** See the next section.

## The net-R column, and why it is reported rather than interpreted

The result carries a mean net R per band: **−0.238** for B1 against **+0.037**, **+0.110** and
**+0.112** for B2–B4. It is reported because withholding a number the run produced would be the
file-drawer this discipline exists to stop. **It is not interpretable, for three reasons that
compound:**

1. **These are not trades.** The entries are a census with no trigger and no gate — nobody would
   take them, and no strategy proposes them.
2. **Survivorship is absent and it cuts this way.** A name whose volatility exploded and then
   delisted is missing from every band, and it is missing disproportionately from the volatile ones.
3. **`HANDOFF.md` §7 closes "new entry filters" by evidence**, and the volatility anomaly
   (Ang, Hodrick, Xing & Zhang, *JF* 61:1, 2006) predicts the opposite sign for a return-based
   screen anyway. A census's net R is not a test of either.

## Limitations, stated before the run and standing after it

- **Overshoot is a lower bound** (A-2). `ExitPolicy.evaluate` fills a touched stop *at the stop*, so
  only a gap can produce a positive figure; intraday slippage past a touched stop is invisible to
  daily bars. Every band's number is biased downward, and there is no reason to think the bias is
  equal across bands.
- **Survivorship runs toward this result, not against it.** §4 warned the study was biased *toward
  finding nothing*. It found less than nothing — a reversal — and part of that gap could be
  survivorship removing exactly the names B4 is made of. **The reversal is therefore weaker evidence
  than its interval suggests**, and no figure here corrects it.
- **One market.** US only; `single_market: true` is declared in the result. `BR-9`'s per-country
  requirement is unmet, as it is in every reported study here.
- **The threshold's fraction was a judgement** (A-1, owner 2026-09-04). It decided nothing here:
  the difference is negative, so any positive threshold rejects.

## What it cost the programme

**One trial**, declared in §6a before the run and spent whatever the outcome — a refused or rejected
study spends its trials the same as an accepting one. Derive the running count with
`python tools/trial_budget.py`; never quote one from here.

## Reproducing

```bash
PYTHONPATH=$PWD/src python tools/run_pr011.py --data <a copy of the store>
```

Without `--write` it publishes nothing. The run reads the bar store only and must be pointed at a
copy, outside the 18:30 and 19:30 passes — the stores are single-writer (`ADR-0004`).
