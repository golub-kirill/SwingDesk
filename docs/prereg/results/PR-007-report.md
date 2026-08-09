# PR-007 RESULT: the spread cannot be measured this way, and the estimators say so loudly

```
prereg:     PR-007 (registered 2026-08-09)
status:     reported
run:        2026-08-09
verdict:    INCONCLUSIVE - section 6's negative-estimate branch, on both estimators
data:       PR-007.json
```

---

## The hypothesis, and what happened to it

Registered: *`costs.slippage_model` at 5bp per side understates the spread component of transaction
cost for the instruments this system would actually trade.*

**Neither accepted nor refuted.** Both estimators produced negative estimates on far more than the
25% of instrument-months §6 fixed as the refusal threshold — Corwin-Schultz on **53.2%**,
Abdi-Ranaldo on **41.3%**. A negative spread is not a narrow spread; it is the estimator reporting
that its assumptions do not hold on this data. §6 was written before the run to refuse a verdict in
exactly this case, and it refuses one.

**`costs.slippage_model` stays `assumed` at 5bp, and `DR-004` is unchanged.** No parameter moved.

## Coverage

```
instruments in store        3,688
eligible under DR-003       1,134     (section 8 minimum: 200 - met)
rejected by the rule        1,821
short history or <12 months   733
instrument-months          26,865
window            2024-08-05 → 2026-08-03, knowledge_time 2026-08-03T22:17:23-05:00
```

The sample requirement was met comfortably. This is not a study that failed for want of data.

## Result, as registered

Per-side half-spread in basis points, across 26,865 instrument-months:

| Estimator | median | p25 | p75 | p95 | ADTV-weighted | negative rate |
|---|---|---|---|---|---|---|
| Corwin-Schultz | **0.000** | 0.000 | 11.600 | 48.321 | 1.012 | **0.532** |
| Abdi-Ranaldo | **14.976** | 0.000 | 50.098 | 132.254 | 19.723 | **0.413** |

Two estimators of the same quantity, on the same bars, disagreeing by a factor of infinity at the
median. Either branch of §6 would have refused this: the negative rate fires first, and the
estimators also fall on opposite sides of 5bp.

## Why it failed — exploratory, and not evidence

Everything in this section was computed **after** the registered arm ran and its negative rate was
seen. Under `PREREG_TEMPLATE.md` §3 rule 4 it is exploratory: it may generate the next
pre-registration and may not advance any validation status. It is here because "inconclusive" is
worth much more when it says why, and the why is checkable.

Pooling over each instrument's whole 500-session series instead of by month — roughly 499 two-day
pairs rather than 20, which removes small-sample noise as an explanation:

```
Corwin-Schultz negative on 696 of 1,134 instruments      61.4%
```

Sixty-one percent of full-series estimates are negative. Small samples are not the problem.

Then the diagnostic that settles it. A spread measure must fall as liquidity rises, and must not
track volatility:

| Correlation | Abdi-Ranaldo | Corwin-Schultz | Expected |
|---|---|---|---|
| vs mean daily range (volatility) | **+0.464** | +0.192 | ≈ 0 |
| vs log ADTV (liquidity) | **−0.021** | −0.156 | strongly negative |

Abdi-Ranaldo is essentially uncorrelated with liquidity and moderately correlated with volatility.
It reports a median of **21.9%** of the mean daily range as spread. On the ten most liquid names in
the store the same estimator returns 33–75bp per side, against true effective spreads under 1bp —
that is, it scores mega-caps *wider* than the universe median, which is backwards.

There is a cleaner way to say the same thing, and it needs no market data at all. Run Abdi-Ranaldo
over 2,000 sessions of synthetic bars built with **no spread in them** and it returns **0.00145**
round trip — **7.25bp per side.** That is the estimator's own noise floor, and it is *larger than the
5bp per side `DR-004` assumes and this study set out to test.* The instrument cannot resolve the
quantity, and that is measurable on the bench before any real bar is involved. It is pinned in
`tests/test_invariants.py`.

The reading is simple. Both estimators infer the spread from second-order differences in quantities
of order 240bp — the mean daily range here is 2.4% of price. The spread they are being asked to
find is under 1bp on the liquid end. **The signal is roughly three orders of magnitude below the
noise floor of daily OHLC**, and no amount of averaging recovers it, because the error is bias
rather than variance.

This is consistent with where the papers were validated: Corwin & Schultz on decades of NYSE data
when spreads were whole percentage points, Abdi & Ranaldo on TAQ samples where they were tens of
basis points. Post-decimalisation US large-cap spreads are simply not in range of either method.
`DR-004`'s alternatives table rejected spread estimation for the wrong reason and reached the right
answer.

## What this does not say

**It does not say `DR-004`'s 5bp is correct.** Nothing here measured the spread, so nothing here
ratifies the assumption. `costs.slippage_model` remains `assumed`, and every R in this project still
rests on it.

**It does not say PR-005's headline is dead.** `PR-007.json` carries
`pr005_sensitivity.survives_under_every_split: false`, because the worst estimator's median
(14.98bp) exceeds the 6.85bp break-even bound. **That field must not be read as a finding.** It
compares a real threshold against a number this same report has just declared unusable. The honest
statement is that PR-005's sensitivity is unchanged and still unresolved:

```
gross per trade      G  = 0.103642 R
cost per trade       C  = 0.075695 R      (at DR-004's assumed 1x)
break-even multiple  k* = 1.3692
```

The base strategy's +0.028R survives while true costs stay under 1.369× the assumption. Whether they
do is still not known, and this study did not narrow it.

**It does not close the question.** It closes one route to it.

## Consequence

1. **`costs.slippage_model` stays `assumed:DR-004` at 5bp per side.** Unchanged.
2. **`DR-004` stands, unedited.** It should eventually gain a fourth rejected alternative —
   OHLC-derived spread estimation, rejected on measurement rather than on availability, which is a
   stronger rejection than the one it currently records. That edit is an owner decision and is not
   made here; this report is the evidence for it when it is.
3. **`PR-006` is now the only route to a measured cost**, exactly as `DR-004` said when it reserved
   the id: record real fills in a forward test and compare them against the model. There is no
   free-data shortcut, and this study is the evidence for that claim rather than an assumption of it.
4. **Do not re-run this family on a wider universe.** §7 fixed one pass, and the failure is a
   resolution limit rather than a sampling one — finishing universe coverage would not change it.
   A variant estimator (Roll, or the Kyle-Obizhaeva form) is the same family and inherits the same
   noise floor; treat a proposal to try one as needing to explain why the three-orders-of-magnitude
   gap closes.

## Limitations, with the result rather than beneath it

- **Survivorship: absent.** Harmless here in the usual direction — delisted names would have wider
  spreads and push the estimate up — but the study reached no estimate, so the bias has nothing to
  act on.
- **US only.** `DR-003` records that no free Canadian symbol directory is in hand. A spread estimator
  that cannot resolve US large-cap spreads would not do better on the TSX, but that is inference,
  not measurement.
- **28.3% universe coverage**, 1,134 of a possible ~4,000 eligible. §8's minimum was met more than
  five times over and the failure mode is not sample-size dependent, so coverage is recorded rather
  than caveated.
- **`MINIMUM_PAIRS_PER_MONTH = 15` was fixed at run time, not at registration.** §5 said "monthly"
  without pinning the floor. It was chosen once, before the run, and not varied; it is recorded in
  `PR-007.json` under `run_parameters`. The full-series arm makes it moot in any case.
- **A 300-instrument smoke test preceded the full run** and showed the same negative rates. The
  exploratory arm was designed after seeing it. That ordering is why the arm is labelled exploratory
  rather than reported as a second result.

## Reproducing

```bash
python tools/run_pr007.py --store data/bars.duckdb
```

Offline. Reads the bar store at its own maximum `knowledge_time`, so the run reproduces as long as
the snapshot exists. The estimators are pure and unit-tested in `tests/test_effective_spread.py`,
including the synthetic recovery test that caught the per-pair Jensen bias recorded in PR-007 §10.
