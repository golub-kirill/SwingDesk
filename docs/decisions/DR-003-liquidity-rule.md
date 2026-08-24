# DR-003: The A-tier liquidity rule

```
date:       2026-08-02
status:     accepted — ratified by the owner 2026-08-23 on the population measurement, and on the
            quality-proxy argument rather than the plateau one, which the same measurement refuted
parameters: universe.min_price, universe.min_adtv_20d, universe.min_bar_history
components: none - swingdesk.reference_data.universe implements the rule; this record sets its inputs
evidence:   measurements/liquidity-sample.json (seed 20260802, 115 instruments measured)
            measurements/liquidity-floor-2026-08-23.json (the population, 3,551 measured)
implemented_by: src/swingdesk/reference_data/universe.py :: LiquidityRule
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

   Confirmed 2026-08-03 on a larger, deliberately non-random slice: the first 400 eligible symbols
   alphabetically returned **33 failures (8.25%)**, every one of them a `$` preferred, a `.U` unit or
   a `W`/`PW` warrant. The higher rate is not a worse vendor — it is the alphabetical head being
   dense in exactly those forms, which is what "systematic" predicts and a random 2.5% would not.

   **Mostly RESOLVED 2026-08-03, and it was worse than recorded.** A 1,500-symbol pass surfaced
   `BRK.A` and `BRK.B` among the failures, reported by the vendor as "possibly delisted". Berkshire
   Hathaway is not delisted — the directory and the vendor simply disagree on separators, and this
   record had filed the whole class under "preferred shares and units", which sounded peripheral.
   It was not: the exclusion was silently removing **the most liquid names the rule could admit**.

   `reference_data.universe.vendor_symbol` now maps both forms, each verified against the vendor
   before being written:

   | Directory | Vendor | Kind |
   |---|---|---|
   | `BRK.B` | `BRK-B` | class shares — dot becomes hyphen |
   | `AMH$G` | `AMH-PG` | preferred series — `$` becomes `-P` |

   That covers **546 of 13,043 eligible symbols** (160 dot-form, 386 dollar-form). Warrants, units
   and rights (`.W`, `.U`, `.R`) map to nothing the vendor accepts — `ACHR.W` resolves as neither
   `ACHR-W` nor `ACHR-WT` — and are left unchanged rather than given an invented form, so they stay
   visible as an unmappable kind instead of becoming a plausible symbol that resolves elsewhere.
   They are also outside what `CHARTER.md` scopes: equities and ETFs.

   **The lesson is about the record, not the code.** Gap 2 was accurate about the mechanism and
   wrong about the stakes, because 2.5% of a random sample of 120 made it look like a rounding
   error. It took a pass large enough to contain a household name before anyone looked again.
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

---

## What `min_adtv_20d` actually does, measured 2026-08-18

Added rather than edited above, because this record's reasoning is history and must not be rewritten
(`AGENTS.md` §3). Nothing here changes a threshold. It names what one of them is **for**, which had
never been written down and which the next argument about it would otherwise have to guess.

### The screen does not constrain execution at this account size, and it is not close

Measured against the 2026-08-17 scheduled run, using the live registry, the real `size_long`, and the
stored bars — 1,148 of that run's 1,149 sized candidates:

| | |
|---|---|
| Risked per trade | **$100** (`account.equity` $10,000 × `risk.per_trade_pct` 1%) |
| Position value | median **$1,355**, max **$2,500** |
| 20-day ADTV of the admitted set | median **$46.8M**, min **$5.1M** |
| **Position as a share of one session's dollar volume** | median **0.0026%**, p99 **0.0418%**, **worst 0.0462%** |

The conventional execution limit is to stay under **10% of ADV**. The worst case here is **0.046%**,
which is more than two hundred times below it. Scaling linearly with equity — position size is a
fixed fraction of it — **the screen would begin to bind at roughly a $2.2M account.**

**So `universe.min_adtv_20d = $5M` is not doing the job its name suggests.** At this size the owner
is invisible in any admitted instrument, and would be invisible at ten times the threshold's
strictness. What the screen actually buys is a **quality proxy**: a name with $5M a day of turnover
has a tighter spread, real price discovery, and is not a shell — all of which matter, none of which
are "can I get out".

### Why this is worth recording rather than leaving implicit

Three things follow, and each would otherwise be re-argued from scratch:

1. **A tighter threshold is not a safety improvement.** Raising $5M would shrink the universe and
   buy no executability that is not already there a hundredfold over. Any future argument for
   raising it has to be made on spread or on data quality, not on liquidity.
2. **`DR-017`'s lag is justified by reproducibility alone.** That record lags the ADTV window three
   sessions so a replayed screen returns what the live screen returned. It cannot also be defended
   as protecting the owner from an unfillable position, because no admitted position is anywhere
   near unfillable. Stating that here keeps the weaker argument from being borrowed later.
3. **This is a proxy, and the thing it proxies for is measurable directly.** Spread is the honest
   quantity, and `EVIDENCE_SUMMARY.md` already records that its LEVEL is not obtainable from daily
   OHLC. Until a source exists, dollar volume stands in for it — which is a defensible reason for
   the rule and a different reason from the one its name implies.

### The shape of the rule is off-convention, and that is the open question

Index providers do not screen on absolute dollar volume. They screen on **turnover relative to
size**:

| | Measure | Threshold |
|---|---|---|
| S&P U.S. indices | **Float-Adjusted Liquidity Ratio** — annual dollar value traded ÷ float-adjusted market cap | **≥ 0.75** (reduced from 1.00), plus ≥ 250,000 shares in each of the prior six months |
| MSCI GIMI | **ATVR** — annualised traded value ÷ free-float market cap | Developed: 20% (3-month) + 90% frequency of trading + 20% (12-month). Emerging: 15% / 80% / 15% |

The reason is that an absolute figure means different things at different sizes: $5M a day is heavy
turnover for a $200M company and a rounding error for a $200B one, and the second is the less liquid
of the two *relative to how much of it exists*. A ratio measures that; a dollar figure cannot.

**This is recorded as an open question, not as a defect.** A ratio needs float-adjusted market
capitalisation, which this project has no point-in-time source for — the same constraint that made
index membership unusable in the first place (see the head of this record). So the dollar form may
well be the only implementable one here. What changes is that the choice is now **recorded as a
constraint rather than assumed to be the standard**, and `DR-017` §5's proposed $3M–$8M sweep is
known to be testing the level of a measure whose *form* is also unvalidated.

---

## The plateau does not exist, measured 2026-08-23

Appended, not edited. This record's reasoning is history (`AGENTS.md` §3) and the 2026-08-18 section
above set the precedent. **No threshold moves here.** What moves is the argument under one of them,
and that is worth more than a number because the argument is what the next revision would reuse.

Consequence 5 above named this check: *"The plateau was located on 115 instruments and should be
re-checked on the population."* Known gap 3 named its own limit: the sample *"is not adequate for
tail percentiles."* Both were right, and the second is why the first mattered.

```bash
python tools/measure_liquidity_floor.py --data data \
    --out docs/decisions/measurements/liquidity-floor-2026-08-23.json
```

Offline, read at the bar store's own latest knowledge time so a re-run over an unchanged store
returns the same answer. Admission uses `average_dollar_volume` and the same three comparisons
`LiquidityRule.admits` makes, so this is the rule's membership rather than a second implementation
of it. Cross-check: the ratified values admit **1,148**, which is the figure the 2026-08-17 run
sized.

### The claim, and what the population says about it

The record above chose 5M from one sentence: *"From 5M to 10M — a doubling — membership changes by
**two instruments out of 115**."* Two of the 38 that sample admitted is **5.3%**.

| | 115-name sample | 3,551 measured names |
|---|---|---|
| 5M → 10M, share of membership lost per doubling | 5.3% | **12.9%** |
| 5M → 25M, share of membership lost | not computed | **33.7%** (1,148 → 761) |

**A third of the universe is gone by 25M.** The range this record called a plateau — *"the choice is
insensitive anywhere on the 5M–25M plateau"* — costs 387 of 1,148 names. That is not insensitivity,
and no reading of the population makes it one.

The whole sweep is smooth and its sensitivity rises with the floor: **7.0%** of members lost per
doubling at the cheapest step (ending at 250k) against **33.5%** at the dearest (ending at 100M).
There is one 1.5-point dip, at the 5M → 10M step, and it is the entire empirical basis the plateau
ever had. A dip of that size inside a curve costing 13–18% per doubling through the same region is
not a flat stretch; it is noise on a slope.

### The sample was good, and it was wrong in exactly one place

This is the part worth carrying forward, because it is not "the sample was too small" — the sample
was mostly excellent:

| | sample | population | ratio |
|---|---|---|---|
| p5 | 12,974 | 14,180 | ×1.09 |
| p10 | 31,265 | 36,739 | ×1.18 |
| p25 | 191,371 | 183,471 | ×0.96 |
| p50 | 1,241,658 | 1,468,739 | ×1.18 |
| **p75** | **34,056,034** | **19,263,239** | **×0.57** |
| p90 | 110,426,657 | 106,741,517 | ×0.97 |

Five of six percentiles land within ×0.96–×1.18. **The sixth is p75, high by a factor of 1.77 — and
p75 is the single number the plateau argument was built on**: *"between the median (~1.2M) and p75
(~34M) there is very little."* The gap was an artefact of one order statistic on 115 draws, and the
argument that rested on it inherited the artefact whole.

Gap 3 predicted this in advance and in the right words. It was recorded as a limitation and then not
treated as one, because the tail figure had already been spent on a conclusion three paragraphs
earlier in the same document.

### What this changes, and what it deliberately does not

**It does not move `universe.min_adtv_20d`.** The value's *original* justification is refuted; its
*current* one is not, and they are different arguments. The 2026-08-18 section above establishes that
the screen does not constrain execution at this account size by a factor of about two hundred, and
that what it actually buys is a **quality proxy** for a spread whose level `PR-010` has since shown
is not obtainable from daily OHLC. Nothing measured here touches that.

So the honest statement of the rule's standing is now:

1. **5M is a choice on a continuum, not a point the data selects.** There is no break in this
   distribution and therefore no floor the population recommends. Any value has to be argued from
   what the screen is *for*.
2. **What it is for is a quality proxy** (2026-08-18), and the proxy argument neither prefers 5M to
   2M nor to 10M. It bounds the class of instrument, not the digit.
3. **"It sits on a plateau" must not be reused.** It was the reason of record for three weeks and it
   is now measured false. A future argument for moving the floor gains nothing from this measurement
   and a future argument for keeping it loses its stated reason.

**The price floor is nearly free on the population too, as this record claimed.** 5.00 costs 59 of
1,207 names against a 2.00 floor — the same order as the *"roughly four names in this sample"* the
record recorded, and the cost-side justification stands unchanged.

### What bounds every number above

- **Coverage is 28.5%** — 3,738 of 13,136 eligible symbols have bars, 3,551 with a full 20-bar
  window. Derive the current figure with `python tools/build_state.py`; do not quote this one later.
- **The stored set is an alphabetical prefix, not a draw.** `tools/refresh_universe.py` queues
  never-fetched symbols in directory order and the directory is sorted by symbol, so **99.0%** of
  measured names sit in the directory's first half (a uniform draw reads 50.0%). *The check that
  this does not bias the result is the percentile table above*: a seeded random sample of 115 and an
  alphabetical prefix of 3,551 agree on five of six percentiles, which is what a liquidity-neutral
  sampling frame looks like. Ticker spelling carries no dollar volume. This is a check rather than a
  conjecture (`AGENTS.md` §10.4), and it is the only reason the population figures may be read as
  statements about the directory at all.
- **Gap 2's systematic absence is unchanged.** Warrants, units and rights fetch as nothing, so they
  are missing here as they are missing everywhere.
- **99.9% of measured names carry a last stored session behind the newest one**, spanning 2026-07-30
  to 2026-08-21. Each instrument's ADTV is its own last 20 stored bars, which is what the daily run
  reads; it is not a common-date cross-section, and a name refreshed three weeks ago is measured
  over a three-week-old window.
- **Spread per liquidity tier is absent on purpose.** `PR-010` measured EDGE across ADTV thirds at
  25.45 / 27.90 / 24.02 bp — flat, most liquid third lowest — and `HANDOFF.md` §7 closes the spread
  level from daily OHLC by evidence. Sweeping modelled spread against the floor would re-run a
  refuted measurement in new clothes. **The admitted population is measurable; the spread it would
  pay is not.**

### What would overturn this

Coverage past roughly half the directory changing the p75 materially. That is the one figure the
prefix could still be wrong about, because it is where the sample and the population already
disagree, and it is cheap to re-check: re-run the command above after
`tools/refresh_universe.py --budget 500` has been run enough times. Nothing else here depends on a
single order statistic.

### Ratified 2026-08-23, and on which argument

The owner ratified **`universe.min_adtv_20d = $5,000,000` as it stands**. The header moves from
`proposed` to `accepted`.

**What it is ratified ON matters more than the digit**, because the digit did not move and one of
its two arguments did:

- **Dead:** *"it sits on a plateau"* — measured false above, and it was the reason of record from
  2026-08-02 to 2026-08-23.
- **Alive, and now the only one:** the quality-proxy argument of 2026-08-18. The screen does not
  constrain execution at this account size by a factor of about two hundred; what it buys is a
  tighter spread, real price discovery and not-a-shell, standing in for a spread whose level
  `PR-010` showed is not obtainable from daily OHLC. Nothing measured on 2026-08-23 touches it, and
  no amount of further coverage will — the population measurement killed the plateau claim and left
  the proxy claim exactly where it was.

**Anyone re-opening this floor argues from what the screen is FOR.** The distribution selects no
value; every floor on it is a choice on a continuum. There is a live argument for lowering it —
inefficiency plausibly lives in the corner this rule excludes by construction — and it is a
**strategy** question rather than a data one, so it belongs beside the first strategy card, not
here.

**The other two parameters are NOT ratified by this and stay `assumed:DR-003`.**
`universe.min_price` and `universe.min_bar_history` were not part of the ruling; only
`min_adtv_20d` moves to `owner`. This follows `DR-006`'s precedent exactly — that record is fully
ratified and `risk.correlation_threshold` still reads `assumed` — because **an accepted record and
an owner-set value are different claims**, and collapsing them would record a decision nobody made.

The price floor's own evidence is unchanged and favourable: 5.00 costs 59 of 1,207 names against a
2.00 floor, the same order as the *"roughly four names in this sample"* recorded above, and its
justification was always the cost side rather than the population side.
