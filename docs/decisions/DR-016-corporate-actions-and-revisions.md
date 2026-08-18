# DR-016: A raw PRICE that changes is a critical fault; a raw VOLUME that changes is Tuesday

```
date:            2026-08-18
status:          proposed — owner ratification required
parameters:      data.revision_epsilon — scoped to price, and volume taken out of the rule entirely
components:      none yet — the actions series has no implementation and no contract member
supersedes:      nothing. Supplies the number DATA_QUALITY_SPEC section 4 has always required
implementation:  none
still_to_build:  the actions series (splits and dividends), the revision comparison at write time,
                 and the held-position split guard. This record is the rule they are waiting on.
```

## 1. Why this record exists

`DATA_QUALITY_SPEC.md` §4 specifies the corporate-actions gate in full and has since it was written:

| Observation | Meaning | Action |
|---|---|---|
| adjusted history changed, and an action exists at that date | expected restatement | write revision, no alarm |
| adjusted history changed, **no** action explains it | unexplained restatement | `DATA` skip + investigate |
| **raw** bar changed | a raw bar should never change | `DATA_ERR` (`Critical`) |
| mass revision across many instruments | vendor-wide re-adjustment | alarm |

**None of it is implemented.** There is no mention of splits or dividends anywhere in `src/`, and
`data.revision_epsilon` is `unset`. `DR-015` §4 handed this over by name as the more dangerous of the
two data risks it identified, and it is the last of the three findings from the week of 2026-08-11 —
the exit policy, the staleness gate, the corporate-actions gate — still open. The other two are
built.

**The reason it needs a record and not just code:** the epsilon. `DATA_QUALITY_SPEC` §4 states plainly
that *"a float epsilon is required or vendor noise produces phantom revisions"*, and names no value.
Wiring the gate without one makes every comparison a coin toss on float representation.

## 2. What was measured first, and it changes the rule

The store is bitemporal, so it already contains the experiment: 6,760 `(instrument, session)` pairs
have been captured more than once, giving **7,231 comparable version pairs** across 2026-08-03 →
08-14. Nobody had looked. Measured 2026-08-18, restricted to bars that were **already settled** when
first captured — the session's close had passed, so any later change is a restatement and not a
mid-session capture:

**7,131 settled bars were revised.** Which field the vendor rewrote:

| Field | Revised | p50 | p90 | p99 | max |
|---|---|---|---|---|---|
| **volume** | **7,129 of 7,131** | **1.1%** | **32%** | **83%** | **164×** |
| high | 2,150 | 0.013% | 0.12% | 0.62% | 3.0% |
| low | 1,963 | 0.013% | 0.11% | 0.50% | 2.4% |
| open | 806 | — | — | — | — |
| close | 122 | 0.0009% | 0.022% | — | 0.084% |

### 2.1 What the table above does and does not say — corrected 2026-08-18

**The table is conditional, and an earlier draft of this record read it as absolute.** Its denominator
is *bars that were revised at all*, because `BarStore.write` is delta-based (`POINT_IN_TIME_SPEC.md`
§3): a re-fetch returning an identical bar writes nothing, so a bar with two versions is **by
construction** a bar that changed. "Volume revised on 7,129 of 7,131" therefore means **when a bar is
revised, it is volume 99.97% of the time and price almost never** — which is the finding, and it
stands. It does **not** mean the vendor rewrites most bars.

**The absolute rate, measured against the right denominator.** On the 2026-08-17 run, 1,152
instruments were fetched over a one-year lookback, re-observing **293,851** prior bars. Rows written:
2,411 — of which 1,085 were the new session and **1,326 were revisions**. So the vendor revises
**0.451%** of re-observed bars.

**And that number is an average over a cliff.** By the age of the bar at the moment of re-fetch:

| Age at re-fetch | Re-observed | Revised | Rate |
|---|---|---|---|
| 0–3 days | 1,097 | 1,081 | **98.5%** |
| 4–7 days | 9,036 | 347 | 3.84% |
| 8–14 days | 6,926 | 0 | **0.00%** |
| 15–30 days | 11,832 | 0 | **0.00%** |
| 30+ days | 264,960 | 0 | **0.00%** |

**Volume settles completely within eight calendar days: zero revisions in 283,718 observations of
bars older than a week.** That is a measured cliff, not an estimated percentile, and it is the single
most useful number this exercise produced — see §4 and `TODO.md`, because it belongs to the ADTV
question rather than to this record.

### 2.2 The rule as written still fires far too often

The correction above does not rescue §4's third row. *Raw bar changed → `DATA_ERR` (`Critical`)*,
applied literally to the whole bar, fires **1,326 times on the single evening of 2026-08-17** —
because the bars a nightly run re-observes include the recent ones, and those are revised 98.5% of the
time. **A Critical gate that fires over a thousand times an evening is a gate that gets switched
off**, and that is the outcome this record exists to prevent.

The rule is right about prices and wrong about volume, and it cannot tell them apart because it was
written before anyone had measured which fields move.

### 2.3 Prices, by contrast, are stable enough to gate on

Close is the tightest: 122 revisions, median 9 parts per million, **maximum 8.4 basis points**. High
and low are looser but still bounded — p99 under 0.7%, maximum 3%. Nothing in three weeks of real
captures came near the 1% level, so a threshold between vendor noise and a genuine restatement exists
and is measurable rather than assumed. That is what makes this record possible at all.

## 3. Decision

**One parameter, scoped — and volume removed from the rule rather than given a number of its own.**

- **`data.revision_epsilon = 0.001`** (10 basis points, relative), provenance `assumed:DR-016`.
  **Applies to `open`, `high`, `low`, `close` on the `raw` series and to nothing else.** A settled raw
  price that moves by more than this is `DATA_ERR` / `Critical` per §4. Below it, the row is not
  written and no alarm is raised.
- **Volume is out of scope of §4's raw-immutability rule, and gets no parameter.** A volume revision
  is recorded as a revision and is never a fault, at any magnitude. A second parameter was drafted
  here and withdrawn: `AGENTS.md` §7 requires `named_in` to cite where the course mentions the
  concept, the course says nothing about volume revision, and inventing a citation to hold a number
  nobody needs is the invented-scope case that rule rejects. **There is no threshold for volume — a
  parameter would assert that there is one.**

**The registry predicted this shape and could not resolve it.** `data.revision_epsilon`'s own note
already reads *"Price, volume and adjusted series need different values."* §2 settles the open half:
volume does not need a different value, it needs **no value**, because its revisions form no
population a threshold could separate.

**Why 0.001 and not tighter.** It sits an order of magnitude above the worst close revision measured
(8.4bp) and an order of magnitude below the 1% level nothing reached, so it separates the two observed
populations with room on both sides. It is a judgment about where to cut a measured gap, which is why
it reads `assumed` and not `validated` (`docs/decisions/README.md` §3 rule 5).

**The actions series.** `POINT_IN_TIME_SPEC.md` §4 names **three** series — `raw`, `adjusted`,
`actions` — and `contracts/market.py` `Series` implements **two**. The `actions` member does not
exist, so the record a split would be checked against cannot be stored. The vendor supplies them:
`yfinance` 1.5.2 exposes `.splits`, `.dividends` and `.actions` on a Ticker, and the adapter already
fetches with `auto_adjust=False`. **This record's precondition is adding `Series.ACTIONS` and storing
them**; the split guard is unbuildable until an action can be looked up.

## 4. What this does NOT decide

**The unclosed-bar contamination already in the store, which this measurement found by accident.** Of
220 raw closes that changed, **98 were not vendor restatements at all** — the first capture was taken
*before* that session's close. All 98 are session 2026-08-03, first captured 13:25 local against a
16:00 ET close: one early manual fetch stored mid-session prices as closes.
`CALENDAR_SPEC.md` §5 forbids using the unclosed current bar, and `last_completed_session` implements
that correctly for *reads* — but nothing stopped a fetch from *writing* one.

That is a separate defect with a separate fix (refuse at write time, and decide what to do about the
98 rows already stored), and it is not a corporate action. It is recorded in `TODO.md` rather than
solved here, because bundling it into this record would hide it.

**Whether ADTV admission is sound.** `universe.min_adtv_20d` admits on 20-day average dollar volume,
and §2 establishes that recent volume is provisional by tens of percent. That is not a corporate-actions
question and it is potentially larger than one — it bears on which 1,152 instruments the run evaluates
at all. `TODO.md` carries it as its own item.

## 5. Alternatives rejected

- **One epsilon for the whole bar.** §2.1. Any value large enough to absorb a 164× volume revision
  admits a doubled price, and any value tight enough to catch a split fires on every volume rewrite.
  The unscoped form the spec implies cannot be made to work, and this is the record's main finding.
- **A second parameter for volume.** §3. It would need a course citation that does not exist, and it
  would assert a threshold the measured distribution does not contain.
- **Treating volume revision as `DATA_ERR`, as §4 reads literally.** It would raise a Critical fault
  on ~1,150 instruments an evening. `HANDOFF.md` §7's own habit applies: a gate that is wrong gets
  fixed or removed, never ignored — and one that cries wolf nightly gets ignored regardless of policy.
- **Deriving `adjusted` from `raw` on read** instead of storing it. `POINT_IN_TIME_SPEC.md` §4
  forbids it, and for the reason this record demonstrates: the actions record needed to do the
  derivation is exactly what is missing.
- **Detecting splits from price discontinuity alone**, with no actions series. Measured: 464 raw jumps
  beyond ±40%/+70% in the last year across the store, of which only 85 land on round split ratios and
  9 involve current universe members. So a price-only detector has a large false-positive population
  of genuine volatility, and it cannot distinguish a 2:1 split from a stock that halved. The vendor
  supplies the actions; guessing them from prices is a worse instrument freely chosen.

## 6. What would overturn this

**A longer capture window.** Three weeks of bitemporal history and 7,131 revisions is enough to
establish that volume moves and prices barely do, and thin for the tail: the largest close revision
measured is 8.4bp, and one genuine vendor correction of a settled print would be far larger. If a
close revision above 0.1% ever appears without a corporate action behind it, `data.revision_epsilon`
is measuring the wrong thing and the number should move.

**An actual split on a held position.** Zero positions exist today (`positions.duckdb` is empty), so
the catastrophic case `DR-015` §4 describes — a stored stop of 290 compared against post-split prices
near 145 — has **no current exposure**. The first real position changes that, and the guard should be
in place before it exists rather than after.

## 7. Consequences

- **`contracts/market.py` gains `Series.ACTIONS`**, and the bar store gains somewhere to put split and
  dividend records with their own `knowledge_time`. Nothing else in §3 is buildable first.
- **The write path gains a comparison.** `POINT_IN_TIME_SPEC.md` §3's "compare before writing" is
  where both epsilons are read; the store is the only place that sees an old value and a new one
  together.
- **The held-position path gains a split guard.** `pipeline.py` reads `Series.RAW` for a position's
  current bar and compares it against a stored stop. That comparison is invalid across a split, and it
  is the one place in the system where being wrong costs money rather than a skipped candidate.
- **`data.revision_epsilon`'s `read_by` stops being `none`**, which is the measurement `AGENTS.md` §7
  exists to make visible.
- **The candidate path is affected but not endangered.** A split mid-history distorts ATR for that
  instrument on that day, which moves a stop and a share count. Nine universe members in a year, so it
  is real and rare — a wrong `Watch`, not a phantom stop-out.
