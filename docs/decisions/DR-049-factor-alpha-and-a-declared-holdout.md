# DR-049: a study reports factor alpha, and it names the window it will NOT read

```
date:            2026-09-21
status:          accepted — ruled by the owner 2026-09-21. Shown DR-047's chain against their own,
                 the owner asked "are we following this way now on researches?" and the honest
                 answer was: nine stages yes, two no. These are the two
parameters:      none set here. criteria.yml gains b.factor_alpha; criteria.yml's b.beta_matched
                 is unchanged and keeps its narrower job
components:      none new
implemented_by:  tools/factor_attribution.py :: FACTORS
```

## 1. What was ruled

Two clauses, and they close the two stages of the owner's research chain that `DR-047` left open.

**1. A directional equity study reports ALPHA from a six-factor regression**, and it is a curve
rather than a diagnostic.

**2. A source's first test NAMES, before it runs, the window it will not read** — and reading that
window later is its own registration.

## 2. Why the first, and it was found by pointing it at our own best result

`DR-047` §3.4 requires four curves, and the fourth — `SPY` matched to the strategy's own volatility
— is the one that answers *"skill or exposure"*. **It only knows about the market.** Size, value,
profitability, investment and momentum are invisible to it, so a book of small profitable winners
can clear every gate this project has and own nothing but tilts that can be bought for a few basis
points.

**Measured the day this was ruled** (`docs/decisions/measurements/overnight-factor-alpha-2026-09-21.json`,
0 trials, exploratory), on `PR-034` — the `ACCEPT` that `EVIDENCE_SUMMARY` §32 calls the first
result here to beat holding the asset per unit of risk:

| the arm, and the window | alpha a year | `t` | market beta | survives? |
|---|---|---|---|---|
| **the night, 2016-2026** (`PR-034`'s own) | **+5.15%** | **+1.61** | 0.44 | **no** |
| the night, 2004-2015 (`PR-036`'s) | +7.96% | +2.50 | 0.36 | yes |
| the session, 2016-2026 | −12.56% | −4.32 | 0.56 | yes, and negative |
| holding the two funds, 2016-2026 | −1.62% | −1.89 | **1.00** | no |

**The last row is the proof the method works**: holding `IJR`+`VB` passively must look like a
small-cap market portfolio with no alpha, and it does — beta 1.00, `SMB` 0.73, R² 0.98, no alpha.

**And the first row changes how `PR-034` must be read.** Its 13.8% a year carries a market beta of
0.44 and a value beta of 0.23; what the six factors cannot explain is **+5.15% a year with a
`t` of 1.61**, which does not clear the two-sided 5% test. The point estimate is economically
large and the interval contains zero. `PR-034`'s `ACCEPT` stands — it was a verdict about returns
net of costs against holding, and it is still that — but **"the first result to beat holding per
unit of risk" may not be restated as "skill" without this number beside it.**

## 3. Why the second

`DR-047` §3.8 names *out of sample* in its order of operations and nothing defines it. `PR-036` did
the right thing — it read 2004-2015, a window no tool here had touched — but it did so **after**
`PR-034` was reported, which makes it a window that happened to be untouched rather than one held
back on purpose. The difference matters the day a result disappoints: an undeclared holdout can be
chosen after the fact, and a reader cannot tell the two apart.

## 4. The clauses, in the words that bind

### 4.1 Factor alpha is a required reading

Every registration whose population is directional equity reports, beside `DR-047` §3.4's four
curves:

```
r_strategy - RF = alpha + b1*(Mkt-RF) + b2*SMB + b3*HML + b4*RMW + b5*CMA + b6*MOM + e
```

* the factors are Kenneth French's five plus momentum, **free** and fetched by
  `tools/fetch_factors.py`;
* the standard errors are **Newey-West**, lag `floor(4*(n/100)^(2/9))`, because daily returns are
  autocorrelated and an ordinary error overstates significance;
* the reading is `criteria.yml`'s new **`b.factor_alpha`**, and the report states the alpha, its
  `t`, every beta and R².

**It does not carry a veto.** A source whose alpha does not survive is not thereby refuted: it may
be a cheaper or less volatile way to hold an exposure, which is a real thing to own and a different
claim from skill. **What is forbidden is calling it skill.** `b.beta_matched` keeps its own job and
is not replaced.

### 4.2 The holdout is declared before the run

A pre-registration whose data extends past the span it reads names, in §4, **the window it will not
read**, and why that window is the right one to hold. It may be an earlier era or a reserved tail.

* the runner **refuses** to read it — the window is a bound in the code, not a promise in prose;
* opening it is a **second registration** against the trial budget, written after the first
  verdict is recorded;
* a study whose data offers no such window says so and carries `out_of_sample: NONE AVAILABLE`,
  which is a disclosure and not a failure.

**`PR-036` is grandfathered and named as the precedent it is**: it did the right thing in the wrong
order, and it is the reason this clause is cheap to follow rather than a new burden.

## 5. What this does NOT change

`DR-047`'s nine clauses, every one of which stands. The trial budget and its 2.70 sd hurdle — this
adds a READING to each study, not a configuration, so it spends nothing. `b.expectancy`,
`b.excess_cagr` and `b.beta_matched`. The verdict vocabulary. `PR-034`'s `ACCEPT` and `CARD-002`'s
evidence, which gain a caveat in §2 rather than losing a verdict.

## 6. What it costs, and the three limits on what an alpha means

- **Two fetches and a regression** a study, both free. The measurement above took under a minute.
- **The library ends about two months behind the present**, so the last sessions of a current
  window are not attributed. A report states what was regressed, not what the window held.
- **Six factors are not every factor.** Liquidity, betting-against-beta and quality are not here,
  and an alpha that survives these six is not an alpha that survives all of them.
- **A partial-period strategy has attenuated betas.** A factor day runs close to close; the
  overnight arm is the part of it that runs close to next open, so its market beta of 0.44 says it
  captures 44% of the day's move rather than that it is levered at 0.44.

## 7. How it is enforced

| clause | enforced by |
|---|---|
| §4.1's regression | `tools/factor_attribution.py` and `tests/test_factor_attribution.py`, every mutant killed - including the three that only an independent re-implementation of the Newey-West kernel could catch |
| §4.1's reading | `criteria.yml`'s `b.factor_alpha`; `PREREG_TEMPLATE` rule 16 |
| §4.1's free data | `tools/fetch_factors.py` |
| §4.2's declaration | `PREREG_TEMPLATE` rule 17 and its §4 `out_of_sample:` line |
| §4.2's refusal | the runner's own window bound, as `run_pr036.BEFORE_LAST` already is |
| the worked example | `docs/decisions/measurements/overnight-factor-alpha-2026-09-21.json` |
