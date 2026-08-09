# PR-008 RESULT: the decision rule refused, and the reason first given for it was wrong

```
prereg:     PR-008 (registered 2026-08-09 AS PR-007; renumbered 2026-08-09)
status:     reported, then CORRECTED 2026-08-09
run:        2026-08-09
verdict:    INCONCLUSIVE - section 6's negative-estimate branch, on both estimators
data:       PR-008.json
```

> **Registered as `PR-007`, renumbered to `PR-008`.** A parallel branch had used that id for a
> different study eight days earlier; `RECONCILIATION_PLAN.md` D-R4 gives a contested id to the
> earliest commit timestamp, so this one moved. Registration is commit `0097bb4`, the run and report
> `8a548da`, and **the git history still says `PR-007` throughout** — which is what proves
> registration preceded the run. A citation of `PR-007` written before 2026-08-09 means this study;
> one written after means the other.

> **Read §"Correction" at the end before quoting anything here.** The `inconclusive` verdict stands:
> it is what §6's registered decision rule returns on these numbers. The **explanation** this report
> first gave for it does not survive. A sign test run afterwards shows the real bars do carry a
> spread the estimator detects, so the claim that the signal sits three orders of magnitude below
> the noise floor is **false and withdrawn**. The affected passages are marked in place, not deleted.

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

> ⚠️ **The two paragraphs below are WITHDRAWN.** They were the strongest claims in this report and
> they are wrong. See §"Correction". They are kept in place because deleting a withdrawn claim
> hides that it was ever made.

~~There is a cleaner way to say the same thing, and it needs no market data at all. Run Abdi-Ranaldo
over 2,000 sessions of synthetic bars built with **no spread in them** and it returns **0.00145**
round trip — **7.25bp per side.** That is the estimator's own noise floor, and it is larger than the
5bp per side `DR-004` assumes and this study set out to test. The instrument cannot resolve the
quantity, and that is measurable on the bench before any real bar is involved.~~

~~The reading is simple. Both estimators infer the spread from second-order differences in quantities
of order 240bp — the mean daily range here is 2.4% of price. The spread they are being asked to
find is under 1bp on the liquid end. **The signal is roughly three orders of magnitude below the
noise floor of daily OHLC**, and no amount of averaging recovers it, because the error is bias
rather than variance.~~

The single-seed reading of 7.25bp was real but not representative: across 40 seeds the same
zero-spread construction ranges from 0 to 29bp per side, because roughly half of all draws clamp at
zero and the rest scatter widely. **One draw was quoted as if it were a property.** That is the same
error this report congratulates itself for catching in the per-pair CS form, committed one section
later.

The paragraph below was written to explain a failure that the correction shows did not happen the
way it says, and it is left standing only because it is still true about where the papers were
validated:

This is consistent with where the papers were validated: Corwin & Schultz on decades of NYSE data
when spreads were whole percentage points, Abdi & Ranaldo on TAQ samples where they were tens of
basis points. Post-decimalisation US large-cap spreads are near the edge of either method.

~~`DR-004`'s alternatives table rejected spread estimation for the wrong reason and reached the right
answer.~~ **Withdrawn.** It rejected it for the wrong reason and reached the **wrong** answer: the
estimators do detect a spread here, and `DR-005` found it a day earlier.

## What this does not say

**It does not say `DR-004`'s 5bp is correct.** Nothing here measured the spread, so nothing here
ratifies the assumption. `costs.slippage_model` remains `assumed`, and every R in this project still
rests on it.

**It does not say PR-005's headline is dead.** `PR-008.json` carries
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

**Superseded by §"Correction". Points 3 and 4 are withdrawn outright; 1 and 2 are now an owner
decision rather than a conclusion.** Kept in place so the reasoning that produced them is legible.

1. ~~`costs.slippage_model` stays `assumed:DR-004` at 5bp per side.~~ It stays `assumed`, but this
   report is no longer an argument that 5bp is defensible. `DR-005` proposes 25bp per side.
2. ~~`DR-004` stands, unedited.~~ Unedited here, but the correction supports superseding its
   slippage component, which `DR-005` already does.
3. ~~**`PR-006` is now the only route to a measured cost.**~~ **Withdrawn.** The sign test shows a
   free-data route does detect a spread. A forward test remains the only route to a *validated* one.
4. ~~**Do not re-run this family on a wider universe.**~~ **Withdrawn.** It rested on the
   three-orders-of-magnitude claim, which is false. §7's one-pass stopping rule still binds *this*
   study; a wider re-run needs a new pre-registration, not a prohibition.

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
  `PR-008.json` under `run_parameters`. The full-series arm makes it moot in any case.
- **A 300-instrument smoke test preceded the full run** and showed the same negative rates. The
  exploratory arm was designed after seeing it. That ordering is why the arm is labelled exploratory
  rather than reported as a second result.

## Reproducing

```bash
python tools/run_pr008.py --store data/bars.duckdb
```

Offline. Reads the bar store at its own maximum `knowledge_time`, so the run reproduces as long as
the snapshot exists. The estimators are pure and unit-tested in `tests/test_effective_spread.py`,
including the synthetic recovery test that caught the per-pair Jensen bias recorded in PR-008 §10.

---

## Correction — 2026-08-09, after comparing against a parallel effort

This report was written without knowing that another branch
(`claude/swingdesk-handoff-continue-1feb49`, tip 2026-08-08) had measured the same thing with the
same two estimators and reached the opposite conclusion: `DR-005`, superseding `DR-004`'s slippage
component at **25 bps per side**, with Abdi-Ranaldo as the headline. Both efforts branched from
`9a07fab` and neither saw the other. `COURSE_V7_DELTA.md` §3 describes the same failure at document
level on 2026-08-04; this is its third occurrence.

The two implementations of Abdi-Ranaldo are **term for term identical** — `4(c−η_t)(c−η_{t+1})`,
averaged before rooting. So the disagreement was never in the code. It was in what each side did
with a synthetic control.

### What decided it

**1. The sign test.** Abdi-Ranaldo returns zero whenever its mean product is negative. On data with
no spread the products are noise about zero, so about half of all series should clamp; on data with
a real spread, clamping becomes rare. This needs no view about the right intraday grid or
volatility, which is exactly why it settles a disagreement that was about calibration.

| Series | Clamped to zero |
|---|---|
| **real instruments** (n=1,134, 500 sessions) | **19.1%** |
| **simulated, zero spread, matched volatility** (n=200, σ=2.24%, 500 sessions) | **45.5%** |

If the real bars carried no spread the two rates would agree. They do not, and not marginally.

**2. Every instrument beats its own floor.** For 126 instruments sampled evenly across the liquidity
range, a zero-spread series was simulated at *that instrument's own* realised volatility. Real
reading exceeded own floor in **126 of 126**, at a median ratio of **4.87×**.

**So the withdrawn claim is refuted.** The real bars do carry a spread this estimator detects. It is
not three orders of magnitude below the noise floor; it is roughly five times the floor.

**`DR-005`'s direction is right and this report's explanation was wrong.** 5bp per side is too low.

### What does not change

**The `inconclusive` verdict stands.** §6 was registered before the run and keys on the
negative-estimate rate, which was 53.2% and 41.3% against a 25% threshold. A decision rule that is
overridden once its author dislikes the answer is not a decision rule. The verdict is a fact about
this study's registered criteria, not a claim that nothing is measurable.

**Two findings survive the correction, and `DR-005` should absorb them:**

1. **Its zero-spread control rests on one seed.** `tests/test_spread.py` asserts Abdi-Ranaldo reads
   below 0.001 on a spreadless series at STEPS=78. Across 40 seeds at that same calibration, **19
   exceed 5bp per side and the maximum is 24.30bp** — nearly the whole 25.44bp headline. The
   estimator is roughly unbiased in aggregate and wildly dispersed per instrument, so a *per-name*
   spread from it is not trustworthy even though the *cross-sectional direction* is.
2. **The cross-section is still backwards.** Abdi-Ranaldo correlates **+0.464** with volatility and
   **−0.021** with log ADTV, and the most liquid third of the sample reads **wider** (26.6bp) than
   the least liquid (24.5bp). A genuine effective spread falls as liquidity rises. Whatever the
   level is, it is contaminated by something that is not spread — so 25.44bp should be treated as
   "materially more than 5" rather than as a measurement of 25.

### Consequence

`costs.slippage_model` should not stay at 5bp on this report's authority. The reconciliation of
`DR-005` with this correction is an owner decision and is recorded in `docs/08-pm/POSTMORTEM-2026-08-09.md`
along with everything else that went wrong here.
