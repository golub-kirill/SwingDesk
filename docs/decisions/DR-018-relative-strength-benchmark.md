# DR-018: The relative-strength benchmark, and the form that makes it matter

```
date:       2026-08-24
status:     proposed
parameters: rs.benchmark, rs.benchmark_form
components: none - M31-T0464 supplies the measure; this record fixes what it measures against
evidence:   measurements/benchmark-2026-08-24.json (1,148 admitted names, 3 lookbacks)
```

`CARD-001` ranks the universe by strength relative to the index and could not run: **no index series
was stored.** This record closes that, and in doing so found that the obvious form of the measure
cannot use a benchmark at all.

Reproduce every figure with:

```bash
python tools/measure_benchmark.py --data data \
    --out docs/decisions/measurements/benchmark-2026-08-24.json
```

---

## 0. What the course fixes and what it leaves to us

The course names **three** indexes, all as Definitions:

| topic | index |
|---|---|
| `M31-T0454` | S&P 500 |
| `M31-T0455` | Nasdaq-100 |
| `M31-T0456` | Russell 2000 |

`M31-T0464` then says *relative strength against the index* — **Derived Observation**. So the
indexes are the course's; **which one applies to a given candidate is not stated**, and neither is
the form of the comparison.

Two separate choices follow, and conflating them is what this record exists to prevent:

1. **Which index.** Unspecified by the course among the three it names.
2. **Which proxy for it.** Authored, because this project has no index series: the store holds
   instruments from the NASDAQ Trader directory, so the stand-in must be an ETF that tracks one.

## 1. The finding that reorders the whole question

**On a single cross-section, a benchmark cannot change a ranking.**

Relative strength in its usual point-to-point form is `(1 + own) / (1 + benchmark)` over a lookback.
On one date the benchmark's return is **one constant for every name**, so dividing by it is a
strictly monotone transform of the name's own return — and a monotone transform reorders nothing.
Subtracting instead gives the same identity.

Measured as a control that must return exactly 1: **15 of 15** benchmark × lookback pairs give
Spearman ρ = **1.000000** against a ranking on the raw return alone, over 1,148 names.

**So point-to-point relative strength is momentum with extra steps.** Choosing SPY over QQQ over IWM
changes nothing, and a study that reported "we ranked by relative strength against the S&P 500" would
be reporting a ranking by raw return with a decorative denominator.

*This is arithmetic, not a result.* The first version of the measuring tool computed exactly this
and reported it as "near-perfect agreement between benchmarks", which dressed an identity as
evidence. It is recorded here so the next reader does not rediscover it as a finding.

## 2. The form that a benchmark can move

Two ways out of the identity, and both are in the course:

- **Path dependence** — *how often* a name beat the benchmark over the window. Not a function of the
  endpoint return, so not a monotone transform of it.
- **A per-name benchmark** — sector-relative strength (`M31-T0460`, `M31-T0461`, `M31-T0462`), which
  gives different names different denominators. Not measured here; see §5.

Measured, path form = share of sessions the name's daily return exceeded the benchmark's:

| | vs raw-return ranking (ρ) |
|---|---|
| 63 sessions | 0.46 – 0.60 |
| 126 sessions | 0.59 – 0.60 |
| 252 sessions | 0.61 – 0.64 |

**It is a genuinely different signal** — around 0.6, not 1.0 — which is the whole reason the family
is worth testing at all.

And now the benchmark matters:

| lookback | SPY vs QQQ | SPY vs IWM | SPY vs IVV |
|---|---|---|---|
| 63 | **0.616** | 0.764 | 0.973 |
| 126 | 0.776 | 0.801 | 0.984 |
| 252 | 0.875 | 0.830 | 0.990 |

**The index is the decision; the proxy is not.** Two funds tracking the same index agree at
ρ ≈ 0.97–0.99; two different indexes disagree down to **0.616**. Choosing between SPY, IVV and VOO
is close to free. Choosing between the S&P 500, the Nasdaq-100 and the Russell 2000 is a real choice
that moves which names a card would hold.

## Decision

| Parameter | Value |
|---|---|
| `rs.benchmark` | **`SPY`** — the S&P 500 proxy |
| `rs.benchmark_form` | **`unset`** — the form gets its value from a pre-registration, not from here |

**`rs.benchmark = SPY`, and the argument is deliberately weak on preference and strong on scope.**
`CARD-001` declares a **US, equities-and-ETFs, whole-admitted-universe** card. The Nasdaq-100 is a
sector-tilted subset and the Russell 2000 a size-tilted one; measuring a broad universe against
either imports a tilt nobody chose. The S&P 500 is the broadest of the three the course names. Among
its proxies SPY is the most liquid and the choice is measured insensitive (ρ ≥ 0.973).

**`rs.benchmark_form` stays `unset` and that is the load-bearing half.** §1 shows the point-to-point
form makes the benchmark irrelevant, and §2 shows the path form makes it decisive. Choosing between
them chooses what the card actually trades — and `ALLOCATION_SPEC` §3 is explicit that an ordering
adopted from the course needs a **pre-registration** before it selects a trade, never a decision
record. So this record fixes the *denominator* and refuses to fix the *formula*.

## 2b. What was built alongside it

- **The benchmark bars are stored.** `SPY`, `QQQ`, `IWM`, `IVV`, `VOO`, five years each,
  2021-08-23 → 2026-08-21, fetched through the existing `refresh_universe.py --symbols-from`. They
  were absent only because coverage is an alphabetical prefix of the directory and the letter S had
  not been reached; every one was already an eligible ETF row.
- **`corporate_actions` is no longer empty.** `DR-016` §8.5 recorded that the table, contract, vendor
  call and read path all existed and nothing ever called `fetch_actions`. 101 dividend records for
  the five funds now sit in it — a first caller outside the held-position split guard.

## 3. The bias that survives every choice here

Relative strength is computed from `Series.RAW`, which is what both decision paths read. **Raw
prices drop on an ex-dividend date**, so a payer looks weaker than a non-payer by roughly its yield
over the lookback — whatever the benchmark, and whichever form is chosen.

Measured over the stored window:

| fund | payments | share of opening price | annualised |
|---|---|---|---|
| `SPY` | 20 | 7.62% | **1.52%** |
| `IVV` | 20 | 8.00% | 1.60% |
| `VOO` | 20 | 7.96% | 1.59% |
| `IWM` | 20 | 5.85% | 1.17% |
| `QQQ` | 21 | 3.42% | **0.68%** |

**Two consequences worth stating rather than leaving to be rediscovered:**

1. **Across a 63-session lookback SPY's own drag is roughly 0.38%**, and the spread between SPY's
   and QQQ's annual drag is **0.84 points**. A benchmark comparison that ignores this is comparing
   two differently-taxed series.
2. **The store holds no adjusted series at all** — `SELECT series, COUNT(*)` returns `raw` only. So
   the drag is not merely uncorrected; until the dividends above were fetched it was not even
   measurable. A future correction has an input now.

## 4. Alternatives rejected

| Alternative | Why not |
|---|---|
| Nasdaq-100 (`QQQ`) as the benchmark | a sector-tilted subset measured against a broad universe imports a tilt nobody chose; and its dividend drag is half the others', which biases every comparison against it |
| Russell 2000 (`IWM`) | size-tilted, same objection |
| An equal-weight S&P proxy (`RSP`) | defensible and **not measured here**; the course names the index, not its weighting scheme, and adding a fourth candidate without a measurement would be preference dressed as rigour |
| A real index series (`^GSPC`) | no free point-in-time source this project can rely on — the same constraint that made index membership unusable in `DR-003` |
| Choosing the form here as well | `ALLOCATION_SPEC` §3: an ordering from the course needs a pre-registration, and §1/§2 show the form decides whether the benchmark means anything at all |

## 5. Known gaps, recorded rather than quietly deferred

1. **Sector-relative strength — MEASURED 2026-08-24, see §7.** Gap closed the same day it was
   opened. It was the other way out of §1's identity and it does reorder; §7 has the numbers and
   the reading that is easy to get wrong.
2. **The path form measured here is one of many.** "Share of sessions beating the benchmark" was
   chosen because it is the simplest measure that is provably not a monotone transform of the
   endpoint return. It is **not a proposal**; a pre-registration picks the form.
3. **One window, one cross-section.** Every ρ above is computed at the store's latest session over
   1,148 names. Whether the SPY-vs-QQQ disagreement is stable across time is unmeasured, and it
   bears directly on how much the benchmark choice matters.
4. **`RSP` and other weighting schemes are unfetched.** Cheap to add; deliberately not added without
   a reason to prefer one.

## 6. What would overturn this

- **Sector-relative strength measured to reorder more than the index choice does** — then the
  denominator that matters is the sector, not the market, and `rs.benchmark` is answering a smaller
  question than it appears to.
- **The SPY-vs-QQQ disagreement collapsing across other windows.** At ρ = 0.875 on 252 sessions it
  is already much weaker than at 63; if the short-lookback disagreement is a property of one quarter
  rather than of the indexes, the choice matters less than §2 suggests.
- **An adjusted series arriving.** The drag in §3 is the argument for treating raw-price relative
  strength as biased; correcting it changes the comparison and every number above with it.


---

## 7. Sector-relative strength, measured 2026-08-24

§5 gap 1 named this as the other way out of §1's identity and refused to guess. This closes it.

```bash
python tools/measure_sector_relative.py --data data     --out docs/decisions/measurements/sector-relative-2026-08-24.json
```

A **sector** benchmark varies by name, so it is not a common factor and §1's proof does not apply to
it. Over **1,023** admitted names carrying a dominant sector across all **11** sectors, each name
measured against the equal-weighted mean of its own sector's admitted members:

| lookback | ρ vs raw return | ρ vs market point-to-point |
|---|---|---|
| 63 | **0.750** | 0.750 |
| 126 | **0.814** | 0.814 |
| 252 | **0.819** | 0.819 |

**The second column is a control, not a comparison, and its agreeing with the first is the point.**
§1 proved the market point-to-point form ranks identically to raw return, so the two columns *must*
be equal — the tool fails the run if they ever are not. It is §1 restated on a second dataset.

**So sector-relative strength is a genuine cross-sectional signal** where market-relative strength
in the same form is not.

### 7a. The reading that is easy to get wrong

**It reorders LESS than the market path form does.** §2 measured that at ρ ≈ 0.6 against raw return;
this reads 0.75–0.82.

**Further from raw return is not better.** Both departures are real, neither is evidence of
anything, and which — if either — predicts is a question only a pre-registration answers. Recorded
because the tempting inference runs the other way and would put a number on a preference.

### 7b. Three authored readings, stated rather than defaulted

1. **The sector return is EQUAL-WEIGHTED** across its admitted members. Not capitalisation-weighted:
   this project has no point-in-time float-adjusted market cap, the same constraint `DR-003` records
   for index membership and `DR-017` for the ADTV rule's shape.
2. **A name takes its DOMINANT sector** by `look_through`. **130 of 1,153** admitted names have no
   usable look-through — mostly the bond, inverse, commodity and volatility products `DR-006` §8.7's
   degeneracy guard refuses — and contribute to no sector.
3. **A name is included in its own sector's mean.** Sectors run 26 to 215 members, so the
   self-inclusion bias is small and symmetric; removing it per name would make the denominator
   depend on the numerator, which is worse.

### 7c. What it does not settle

**Whether the sector signal predicts anything.** This measures that the denominator changes the
order, not that the order is better. It also uses **today's** sectors rather than point-in-time ones
— `DR-006` §14.5's limit, unchanged — so a name that changed sector is misfiled for its whole
history.

**And it does not choose the card's measure.** `rs.benchmark_form` stays `unset`: market or sector,
point-to-point or path, all four combinations are now characterised and none is ratified. That is
`ALLOCATION_SPEC` §3's rule, and having four measured options rather than one guessed one is what
this record was for.
