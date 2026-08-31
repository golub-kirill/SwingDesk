# DR-016: A raw PRICE that changes is a critical fault; a raw VOLUME that changes is Tuesday

```
date:            2026-08-18
status:          accepted — ratified by the owner 2026-08-30
parameters:      data.revision_epsilon — scoped to CLOSE, and volume taken out of the rule entirely
components:      none - swingdesk.trade_management.manage guards a held position against a split,
                 swingdesk.market_data.store holds the actions series
supersedes:      nothing. Supplies the number DATA_QUALITY_SPEC section 4 has always required
implemented_by:  src/swingdesk/market_data/store.py :: def close_revision
also_built:      market_data/store.py (the actions series, 2026-08-18), trade_management/manage.py
                 (the split guard, 2026-08-23), tools/refresh_universe.py (the one caller that
                 supplies the epsilon — see §11)
built:           2026-08-23. The header carried `still_to_build: the revision comparison at write
                 time` until 2026-08-30, and it had been stale since the day §10.2 built it.
```

> **Read §8 before acting on §3.** Re-measured 2026-08-23 under the longer capture window §6 asked
> for: the *value* survives and the *scope* does not. `0.001` over all four price fields would raise
> about **94 `Critical` faults every evening**; over `close` alone it fires **zero** times in the
> whole window. §3's four-field scope is superseded by §8.4, which recommends the same number scoped
> to `close`. The ruling is still the owner's.

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

---

## 8. Re-measured 2026-08-23, and §3's SCOPE does not survive it

§6 named the condition that would overturn this record: *"a longer capture window."* The window is
now longer, and re-measuring under it does not move the **number** — it moves what the number may
be applied **to**. Reproduce with:

```bash
python tools/measure_revisions.py --data data --out docs/decisions/measurements/revisions-2026-08-23.json
```

Owner asked for research rather than a ruling from intuition. This is it.

### 8.1 §2's table left one column blank, and that is where the defect was

§2 characterised `volume`, `high`, `low` and `close`, and printed **`open | 806 | — | — | — | —`**.
The open was counted and never described. Measured now, over 7,141 settled version pairs across 9
sessions:

| field | revised | p50 | p90 | p99 | max |
|---|---|---|---|---|---|
| `close` | 122 | 0.0008% | 0.019% | 0.071% | **0.084%** |
| `low` | 1,966 | 0.013% | 0.107% | 0.495% | 2.45% |
| `high` | 2,152 | 0.013% | 0.122% | 0.607% | 3.03% |
| **`open`** | **809** | **0.128%** | **0.772%** | **2.25%** | **5.45%** |

**The open's MEDIAN revision is larger than the threshold §3 proposes.** The close's largest
revision in the whole window is 0.084%, twelve times *below* it. These are not one population and
0.001 is not one threshold for them.

### 8.2 What §3 as written would actually do

Fires per session, at the proposed value and around it:

| | >0.05% | **>0.1%** | >0.5% | >1% | >5% |
|---|---|---|---|---|---|
| `close` | 0.4 | **0.0** | 0.0 | 0.0 | 0.0 |
| `low` | 44.6 | 23.6 | 2.1 | 0.6 | 0.0 |
| `high` | 54.8 | 29.6 | 4.3 | 0.7 | 0.0 |
| `open` | 62.8 | 49.4 | 15.6 | 6.6 | 0.1 |
| **all four, as §3 scopes it** | 147.4 | **94.1** | 20.6 | 7.0 | 0.1 |

**`data.revision_epsilon = 0.001` over `open`/`high`/`low`/`close` raises roughly 94 `DATA_ERR` /
`Critical` faults every evening.**

§5 of this record rejected the volume form of the rule in these words: *"It would raise a Critical
fault on ~1,150 instruments an evening. A gate that is wrong gets fixed or removed, never ignored —
and one that cries wolf nightly gets ignored regardless of policy."* **The scoped-to-price form
makes the same error one field over**, an order of magnitude smaller and still nightly. The record
diagnosed the disease precisely and then carried it across, because the field that carries it was
the one its own table did not describe.

### 8.3 The tail has no gap to cut, and that is checked rather than assumed

A wide tail could be a vendor event — a bad afternoon, one instrument, one session — in which case a
threshold above it would work. It is not. The 44 open revisions above 1% are spread across **44
distinct instruments and six of the nine sessions**: one apiece, every day. That is what the field
does, not something that happened to it.

So the same test §3 applied to volume applies here: *"there is no threshold for volume — a parameter
would assert that there is one."* There is no threshold in the open, high or low either.

### 8.4 What this supports

**Keep 0.001. Scope it to `close`.**

That is §3's own reasoning taken one step further, not a new argument. §3 removed volume because its
revisions form no population a threshold could separate; `open`, `high` and `low` fail the same test.
The close passes it cleanly — a tight population ending at 0.084%, a threshold twelve times above it,
and **zero** firings across the window.

**And the close is the field the decision path reads.** `pipeline.py` takes `entry` from
`stored.bars[-1].close`, and sizing spends its risk against that entry. A restated close moves the
entry, the share count and the stop distance together.

**Two corollaries, because §3's wording bundles two different things.**

1. **A revision is always RECORDED; only a close revision past the epsilon is a FAULT.** §3 says
   *"below it, the row is not written and no alarm is raised"*, which would discard the audit trail
   for a 5% open restatement. `POINT_IN_TIME_SPEC` §3 requires the version; the epsilon governs the
   alarm. The store's existing `_PRICE_QUANTUM` already suppresses float noise at write time and is
   a different mechanism with a different job.
2. **`high` and `low` still reach a decision through ATR**, and get no fault. That is the same
   accepted consequence volume already carries through `universe.min_adtv_20d`: a field whose
   revisions form no separable population does not get a worse threshold, it gets none. Recorded
   here so it is a known limit rather than an oversight.

### 8.5 A precondition is built and has never been fed

`corporate_actions` holds **zero rows**. The table, the contract, the vendor call and the read path
all exist — nothing in the scheduled run calls `fetch_actions`, so the series that §6 says would
explain a large price revision cannot explain anything yet.

This is the third instance of the shape `AGENTS.md` §7 was written for, inside the record that
closed the previous one. The split guard is what will feed it: it protects held positions, there are
at most `risk.max_concurrent_positions` of them, and fetching actions for exactly those names is
bounded work the evening run can afford.

### 8.6 What is still open

**The ruling.** The value does not move; the scope does. `data.revision_epsilon` stays
`unset` until the owner rules on the scoped form.

**The window is still short.** Nine sessions of settled revisions is enough to show that the open
and the close are different populations, and thin for the tail of either. §6's overturning condition
is unchanged and now has a tool: re-run `measure_revisions.py` in a month.

---

## 9. The split guard, built 2026-08-23

§7 listed three consequences and said the held-position path *"gains a split guard"*. This is that
guard. **It needed no ruling and was built ahead of one**, because a split either happened or it did
not — there is no threshold in it, which is precisely what separates it from the revision comparison
still waiting on §8.

### 9.1 The failure it stops

Both decision paths read `Series.RAW`. Raw bars are unadjusted, so a split does **not** restate
history — the next bars simply arrive at a different price level. A 2:1 split over a weekend leaves
a stored stop of 290 being compared against Monday prices near 145, and `manage.evaluate` reads that
as a stop touched. It would propose `EXIT_NOW` on a stop-out that never happened, confidently, with
every freshness check passing.

Everything else a split distorts produces a wrong `Watch`. This produces a wrong exit on a position
the owner actually holds, which is why §7 called it the one place where being wrong costs money.

### 9.2 Where it lives, and what it refuses to do

| | |
|---|---|
| The verdict | `trade_management/manage.py` — `split_guard`, `SplitAlert`, `SplitGuard`, pure |
| The held-position path | `application/pipeline.py`, before the freshness check |
| The feed | the same path, `actions_fetcher` — **held names only** |
| The display | `presentation/report.py`, a `splits:` line on the position |

**It pauses; it does not adjust.** `SplitAlert.stop_after` carries the restated number into the
proposal's reason so the owner can act on it, and nothing writes it anywhere. Adjusting the stop
would be the system rewriting a risk parameter the owner set on its own authority, which
`CHARTER.md` A-001 reserves to them and `AUDIT_AND_IMMUTABILITY.md` makes a position record immutable
to prevent.

**It runs BEFORE the freshness check**, and that ordering is a decision rather than an accident. A
stale series recovers by itself tomorrow; a split does not, and it is the one condition under which
evaluating anyway produces a *confident wrong answer* rather than a refusal. A transient staleness
must not mask it for a day.

### 9.3 Three readings, all authored

1. **The reference instant is the position VERSION's `knowledge_time`, not `opened_on`.** A stop
   moved last week was set against last week's prices, so a split before that move is already
   reflected in it. `Position` is append-only and a stop move writes a new version, so the version's
   own knowledge time is exactly when its `current_stop` became true. Using `opened_on` would
   re-alert on every split the owner had already handled.
2. **Strictly after.** A split effective on the same date the stop was set is treated as already
   reflected: splits take effect at the open, so a stop set during that session was set against
   post-split prices. Tested from both sides, because an off-by-one here pauses a position for
   nothing.
3. **Dividends raise nothing.** `price_factor` already returns 1 for a dividend — the ex-date move
   is a market reaction rather than a re-denomination — and the guard filters by KIND as well, so a
   future action type cannot fall through by happening to have a factor of 1. Pausing on a dividend
   would cry wolf on every dividend-paying holding, which is the failure §5 rejected for volume.

### 9.4 §8.5's empty table now has a caller

The guard is what feeds the actions series. It fetches for **held names only** — at most
`risk.max_concurrent_positions`, four today — which is what makes it affordable inside the evening
run and unaffordable across a 1,148-member universe.

**And the fetch is fail-open, exactly as the bar fetch is.** A vendor failure leaves whatever is
stored standing. What changes is that the run then knows it did not ask: `SplitGuard` carries
`refreshed` separately from `stored`, because zero actions is genuinely ambiguous — an instrument
may never have split, or nobody may have asked. The store cannot record a negative, so the run
records whether it ASKED. Without that, an unfed store and a clean instrument render identically,
and only one of them is safe.

An unanswered guard **does not pause**. `CHECKLIST_SPEC.md` §4 exists so a data failure cannot lock
the owner out of managing risk they already carry, so the position is managed and the report says
the check could not run.

### 9.5 What is still not built

**The revision comparison at write time**, which is the half that needs §8's ruling. The store still
compares versions at `_PRICE_QUANTUM` — a float-noise quantum, not a fault threshold — and nothing
raises `DATA_ERR` for a restated raw price. `data.revision_epsilon` stays `unset` and `read_by:
none` until the owner rules on the scoped form §8.4 recommends.

---

## 10. The ruling, 2026-08-23 — and the half of §9.5 it unblocks

§8.6 said the value does not move and the scope does, and left the ruling open. **The owner ruled
on §8.4 as written: keep `0.001`, scope it to `close`.**

### 10.1 What the registry now says

`data.revision_epsilon` moves from `unset` to **`owner` / `0.001`**, with its unit narrowed from
*"relative tolerance per series"* to *"relative tolerance on the close"*. The unit change is not
cosmetic — the old wording is what let §3 scope a single number across four fields whose revision
distributions §8.1 then measured an order of magnitude apart.

The parameter's `read_by` moves from `none` to `swingdesk.market_data.store:close_revision`, which
is the point of this section. **A ratified decision that reaches no code is a decision that did not
happen** (`AGENTS.md` §7), and this record has now produced two of that shape in a row — §8.5's
empty `corporate_actions` table was the first, and it was found inside the record that closed the
previous one.

### 10.2 What was built

`§9.5` named the missing half: *"The revision comparison at write time … nothing raises `DATA_ERR`
for a restated raw price."* The comparison exists now.

| | |
|---|---|
| The rule | `market_data/store.py` — `close_revision`, `CloseRevision`, pure |
| The write | `BarStore.write(bars, knowledge_time, revision_epsilon=None)` |
| The report | `WriteResult.close_revisions` |
| A caller | `tools/refresh_universe.py`, which reads the epsilon from the registry and prints faults |

**Three properties, each of them a decision:**

1. **The epsilon governs the alarm and never the record.** §8.4 corollary 1 in code: every revision
   is written whether or not it faults, `close_revisions` is a *subset* of `revised`, and the store
   test asserts both the fault and the stored row. Suppressing a row would discard the audit trail
   `POINT_IN_TIME_SPEC` §3 requires, which is precisely what corollary 1 was written to forbid.
2. **`None` means NOT CHECKED, not clean.** A caller that passes no epsilon gets an empty tuple
   because nothing was asked. The store does not fall back to a tolerance it was not given —
   `unavailable` is not `pass`, applied to a write.
3. **The comparison is relative.** A one-cent restatement is 0.2% of a $5 stock and 0.002% of a
   $500 one, and `universe.min_price` admits names at exactly $5.

**It does not touch `application/pipeline.py`.** That file is frozen under `DR-015` §3 and a change
to it that moves decision output resets `a.run_completes`. Nothing here needed it: the rule, the
write and a live caller are all outside the freeze, so this lands without spending a counter that
`SESSION-HANDOFF` §1 says is the slowest thing on the board.

### 10.3 The tests are scoped tests, and the first version of them was not

`tests/test_revision_epsilon.py`. Worth recording because the failure was invisible and is the exact
shape §8.1's blank column was:

The three "the other price fields raise nothing" cases originally held the close **identical** while
moving `open`, `high` or `low`. They passed — and they passed against a deliberately mutated version
that faulted on all four fields, because an unchanged close returns early before scope is consulted.
**A test that cannot fail is not evidence**, and these were testing the early return while reading
as though they tested the scope.

Fixed by moving the close 0.05% — under the threshold on its own — while moving the other field far
past it. Measured: the four-field form now fails six assertions where it previously failed three,
and the three new ones are the scope cases.

### 10.4 What is still open

**Surfacing the fault in the decision path.** `refresh_universe.py` prints; nothing refuses. A
restated close past the epsilon should reach the run as a `DATA_ERR` / `Critical`, and that is a
`pipeline.py` change, which is frozen, resets the counter, and needs its own decision about what the
run does — refuse the instrument, or refuse the session. **Deliberately not decided here.** §8.2
measured the scoped form firing **zero** times across the capture window, so nothing is being missed
while this waits, and spending a counter reset on a path that has never fired is the worse trade.

**The window is still short**, unchanged from §8.6: nine sessions of settled revisions is enough to
separate the open from the close and thin for the tail of either. Re-run `measure_revisions.py` in a
month; §6's overturning condition stands.

## 11. Ratified 2026-08-30, and what the header was getting wrong

**The record is accepted at the value and scope §10 settled**: `data.revision_epsilon = 0.001`,
scoped to `close`, provenance `owner`, already in the registry since the 2026-08-23 ruling.

**The header was stale and said so about the wrong half.** It carried
`still_to_build: the revision comparison at write time` — but §10.2 built exactly that on
2026-08-23. `BarStore.write` takes a `revision_epsilon`, and when it is supplied every restated
close past the threshold comes back on `WriteResult.close_revisions`. Seven days of a record
advertising as unbuilt something it had itself recorded building.

### 11.1 Built is not the same as reached, and the distinction is worth stating precisely

`BarStore.write(..., revision_epsilon=...)` is **optional**, and exactly one caller supplies it:
`tools/refresh_universe.py`. The two writes in `application/pipeline.py` do not, so the **scheduled
evening run stores restated closes without comparing them at all** — it does not merely decline to
refuse on a fault, it never computes one.

That is a sharper statement of §10.4 than §10.4 makes, and it does not change what §10.4 concluded:

- Wiring the epsilon into `pipeline.py` is a change to a frozen file on the decision path, and it
  would cost a Track A counter reset.
- §8.2 measured the scoped form firing **zero** times across the whole capture window, so nothing
  is being missed while it waits.
- And it still needs the decision §10.4 names and does not take: does the run refuse the
  **instrument** or the **session**?

So it waits, and it waits for the reason it always did. What changes here is that the reason is now
written where a reader will find it, instead of behind a header line claiming the comparison did not
exist. `TODO.md` carries the open item.
