# DR-003: The A-tier liquidity rule

```
date:       2026-08-02
status:     proposed
parameters: universe.min_price, universe.min_adtv_20d, universe.min_bar_history
components: none - swingdesk.reference_data.universe implements the rule; this record sets its inputs
evidence:   measurements/liquidity-sample.json (seed 20260802, 115 instruments measured)
```

The owner decision of 2026-08-01 fixed the *shape*: A-tier is a liquidity rule computed from our own
bars, not index membership — because no free source serves index constituents point-in-time, and
filtering yesterday's data by today's membership stacks a second survivorship bias on the delisting
one. This record fixes the *numbers*.

---

## Decision

| Parameter | Value |
|---|---|
| `universe.min_price` | **5.00 USD**, last close |
| `universe.min_adtv_20d` | **5,000,000 USD/day**, mean of close × volume over 20 sessions |
| `universe.min_bar_history` | **250 daily bars** |

Both thresholds are evaluated **as of the decision date**, from bars up to that date only. The
universe on a past date is not today's universe.

## Why these

Measured, not preferred. A seeded random sample of 120 eligible US listings (13,048 eligible rows in
the NASDAQ Trader directory; 117 fetched, 115 with a full 20-bar window):

| Percentile | 20-day ADTV (USD/day) |
|---|---|
| p5 | 12,974 |
| p10 | 31,265 |
| p25 | 191,371 |
| **p50** | **1,241,658** |
| p75 | 34,056,034 |
| p90 | 110,426,657 |

**The distribution has a gap, and that is the finding.** Between the median (~1.2M) and p75 (~34M)
there is very little. Membership barely moves across that whole range:

| ADTV threshold | Admitted |
|---|---|
| ≥ 1M | 54% |
| ≥ 5M | 33% |
| ≥ 10M | 31% |
| ≥ 25M | 26% |

From 5M to 10M — a doubling — membership changes by **two instruments out of 115**. So the choice is
insensitive anywhere on the 5M–25M plateau, and that is precisely the reason to set it there rather
than at 1M, where a small move in the threshold swings membership by twenty percentage points.

A parameter sitting on a cliff is a parameter whose exact value is doing work nobody has justified.
5M is the low end of the plateau: inclusive, without reaching down into the illiquid mass.

**Price floor.** p5 of last close is 1.21 and p10 is 4.05, so a 5.00 floor removes roughly four names
in this sample — it is nearly free on the population side. It earns its place on the cost side:
below 5.00 a one-cent spread is 20bp or worse, and a slippage model that ignores that will flatter
every backtest of a cheap stock.

**History floor.** 250 bars ≈ one year, covering the longest indicator warm-up currently in scope
(SMA(200)) with margin. An instrument that cannot warm up its inputs cannot be evaluated, and
admitting it produces a candidate that silently never qualifies.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| index membership (S&P 500, TSX 60) | no free point-in-time constituent source; today's membership applied to old data is survivorship bias with extra steps |
| ADTV ≥ 1M | sits on the cliff — 54% admitted, and small threshold moves swing membership hard |
| ADTV ≥ 25M | also on the plateau, and needlessly narrow; nothing measured argues for the top of the range over the bottom |
| median dollar volume rather than mean | more robust to a single volume spike, and not what "average daily volume" conventionally means. Revisit if spikes prove to admit names that cannot actually be traded |
| separate thresholds for ETFs and equities | 58 of 115 sampled instruments are ETFs, so a split would matter — but nothing measured says the liquidity requirement should differ, and a second threshold doubles what has to be justified |

## What would overturn this

- Measured slippage on forward-test fills materially worse than modelled for instruments near the
  floor. That says the floor is too low, and it is checkable from `costs.slippage_model` against
  recorded fills (M74-T1110).
- A universe too small to produce candidates at the required sample sizes. 33% of 13,048 eligible US
  rows is roughly 4,300 instruments, so that is not the problem here.
- Extending to Canada — see gap 1.

## Known gaps, recorded rather than quietly deferred

1. **Canada has no free symbol directory in hand.** The NASDAQ Trader files cover US venues only.
   The rule applies to `.TO` instruments identically, but this project cannot presently *enumerate*
   them, so the Canadian universe is a list rather than a rule. `BR-9` requires results reported per
   country, so a US-only universe means a US-only result until this is solved. Not solved here.
2. **Share-class symbols fail to fetch.** 3 of 120 sampled symbols — `AMH$G`, `F$B`, `APACR`, about
   2.5% — returned nothing. The directory encodes share classes and units with `$`; the vendor
   expects another form, and `to_instrument` passes the ACT symbol through unchanged. Until mapped,
   these are silently absent from every universe, and the exclusion is **systematic rather than
   random**: preferred shares and units, not an arbitrary 2.5%.
3. **The sample is 115 instruments.** Adequate for choosing between order-of-magnitude thresholds
   and for locating the plateau. Not adequate for tail percentiles, and the p90 figure above should
   not be quoted as though it were precise.

## Consequences

1. `LiquidityRule` takes these as values rather than reading the registry, so a study pins the rule
   it actually ran under into its own evidence record instead of inheriting whatever the registry
   says later.
2. PR-001 can now draw its instrument list from a rule instead of from my judgement — which was the
   point. A study about how definitions select instruments, run on instruments selected by eye,
   mostly measures the eye.
3. **Choosing a threshold after seeing the distribution is selection on the data.** It is acceptable
   here because dollar volume involves no forward returns and so cannot leak outcome information,
   and because PR-001's design was frozen before this measurement existed. It is not nothing, and it
   is recorded as a limitation rather than glossed.
4. **The rule costs more to evaluate than the daily budget allows** — found when the universe path
   was built (2026-08-03). ~4,300 admitted instruments is over an hour of free-tier fetching against
   `NFR.md`'s 45 minutes, so bars are widened by a budgeted background pass and the daily run reads
   what is stored. Until coverage is complete the universe is a **subset** of what this rule admits,
   `UniverseSelection.is_partial` says so, and every report prints the coverage fraction. This does
   not change the thresholds; it changes how long they take to be fully applied.
5. **The plateau was located on 115 instruments and should be re-checked on the population.** Once
   coverage is complete the same percentiles can be computed over every eligible symbol rather than
   a sample, which is the cheap confirmation that 5M–25M really is flat (ROADMAP X6).
