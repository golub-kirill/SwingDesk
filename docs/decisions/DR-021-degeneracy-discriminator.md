# DR-021: The degeneracy guard should ask whether the fund holds equity, not infer it from the shape

```
date:            2026-08-30
status:          accepted — ratified by the owner 2026-08-31
parameters:      none. Deliberately - see section 5
components:      reference_data.classification:look_through
supersedes:      nothing. It AMENDS DR-006 section 8.7, which is corrected forward here rather than
                 edited (AGENTS.md section 11 rule 2)
implemented_by:  src/swingdesk/reference_data/classification.py :: def look_through
also_built:      contracts/reference.py (Classification.equity_share),
                 reference_data/classification.py (the column), market_data/vendor_yahoo.py (the
                 fetch), platform/schema.py (a nullable column may now be added to a populated
                 table - section 9.3)
built:           2026-08-31. Section 9 records what landed, what it cost, and the one claim in
                 section 6 that was wrong.
```

## 1. What `DR-006` §8.7 does today, and why it exists

The vendor answers `NEAR` — a short-maturity bond fund holding no equity at all — as
**healthcare 100.0%**, every other sector 0.0%. Consumed naively, one bond fund would spend an
entire sector budget on a fiction, silently, which is worse than the check not existing.
`look_through` refuses that shape and reports `unavailable`.

**The test is EXACT and §12.1 states the reason:**

> A genuine sector ETF is legitimately almost all one sector, so a tolerance would refuse the
> instruments this cap most needs.

The reasoning is sound. **The premise is half wrong, and *almost* is the word doing the work.**

## 2. The measurement

`tools/probe_sector_benchmarks.py`, 2026-08-30, over the SPDR Select Sector family — one fund per
canonical sector, all eleven listed in `directory.duckdb` and none a test issue:

| | Dominant sector | `_degenerate_sector` | Equity share the vendor reports |
|---|---|---|---|
| `XLC` communication services | 100.0% | **refused** | 100.0% |
| `XLE` energy | 100.0% | **refused** | 99.8% |
| `XLV` healthcare | 100.0% | **refused** | 99.9% |
| `XLRE` real estate | 100.0% | **refused** | 99.9% |
| `XLU` utilities | 100.0% | **refused** | 99.7% |
| `XLB`, `XLY`, `XLP`, `XLF`, `XLI`, `XLK` | 84.0–99.3% | clears | 99.9–100.0% |
| **`NEAR`** — the fund the guard was written for | healthcare 100.0% | **refused** | **0.0%** |

Reproduce it:

```bash
PYTHONPATH=$PWD/src python tools/probe_sector_benchmarks.py --data data
```

**Five of the eleven report exactly one sector at exactly 100%**, which is `_degenerate_sector`'s
signature exactly. The guard cannot tell them from `NEAR` because it is not looking at the thing
that separates them.

## 3. What is wrong, stated precisely, because it is smaller than it sounds

**The behaviour is correct.** A refused look-through makes `SectorCapacity.is_unavailable` true,
which **admits** the candidate by design — `DR-006` §3 forbids a check the system could not perform
from refusing every candidate — and the reason travels on the record. Nothing is fabricated, nothing
is silent, and no number is invented. A reader of the journal can see exactly what happened.

**What is wrong is the reason.** It reads:

> the look-through is degenerate … which is how this vendor describes a fund holding no equity at
> all (DR-006 8.7)

For `XLU` that sentence is false. It holds 99.7% equity. `AGENTS.md` §15 rule 1 and §10.4 both say
an explanation is itself a claim, and this one is attached to a live risk control — a reader who
believes it looks for a bond fund that is not there.

**And the cap is weaker than it reads on exactly the wrong instruments.** A refused look-through
makes the per-sector split an understatement (`SectorBook.is_complete` reports it), and the
instruments it refuses are the most single-sector-concentrated ones in the universe. That is the
permissive direction, which is the direction §8.7 was written to close.

**The cost today is zero and that is why this is `proposed` rather than urgent.** None of the five
is in the admitted universe: none of the eleven has bars stored, the same alphabetical-prefix gap
`DR-018` found for `SPY`.

## 4. The proposal

**Keep the shape test as the trigger. Add the vendor's own answer as the discriminator.**

Refuse a fund look-through when the sector weights are degenerate **and** the vendor does not
positively report that the fund holds equity — `funds_data.asset_classes.stockPosition`, which is
served in the same response the sector weights come from.

- `NEAR`: degenerate shape, equity share `0.0` → **refused**, as today.
- `XLU`: degenerate shape, equity share `0.997` → **admitted**, with its sector spent.
- Vendor does not answer the field at all → **refused**, as today. Absence is not evidence of
  equity, and this is the fail-closed direction (`AGENTS.md` §3).

**This is a proxy being replaced by the fact it was a proxy for**, which is `AGENTS.md` §12's named
trap with the measurement sitting in the same payload.

## 5. Why this introduces no parameter, deliberately

A tolerance would need a number, and a number the course does not supply needs a pre-registration
rather than a guess (`AGENTS.md` §8). **There is no tolerance here.** The test stays exact in both
halves: the shape must be degenerate, and the equity share must be positively reported. `0.997`
versus `0.0` is not a close call and nothing in this record turns on where a line between them
would sit.

**Rejected alternative — a tolerance on the sector weight** (refuse at ≥ 99.5% rather than at
exactly 100%). It inverts the problem: it refuses `XLK` at 99.3% today and would refuse more as the
funds drift, and it is `DR-006` §12.1's own rejected option, correctly rejected. Nothing here
disagrees with that reasoning; what has changed is that the exact test was believed to be free of
the same cost and is not.

**Rejected alternative — a curated allow-list of known sector ETFs.** It closes the entries someone
thought of while reading as though it closed the class, which is the objection
`application/ai_guard.py` records against a synonym list, and it goes stale the first time State
Street launches a twelfth fund.

## 6. What ratifying this would change, and what it would not

**Would change:** a candidate or an open position in one of those five funds gets its sector
exposure measured and spent against `risk.max_sector_risk` instead of being admitted unmeasured. On
today's stored universe that is **no instrument**, so this moves no decision output the day it lands
— but it is a change to what the cap admits in principle, and it must be measured against the live
universe before it is called cosmetic.

**Would not change:** `risk.max_sector_risk` keeps its value and its `assumed:DR-006` provenance;
`DR-006` §3's admit-on-unavailable rule is untouched; the `NEAR` case behaves exactly as it does
today; and nothing about the point-in-time weakness of the classification (`DR-006` §3 records that
the sector known is today's, not the one in force on an older date) is addressed here.

## 7. Why this is not simply a bug fix

`DR-006` is accepted and §8.7 is one of its rules. Changing what the sector cap admits is a decision
output, and `AGENTS.md` §14 says an agent does not take a decision that is the owner's by calling it
a defect. **The measurement is not the owner's; the amendment is.** Until this is ratified, §8.7
stands as written and the guard behaves as it does today.

## 8. Measured against the live universe, 2026-08-30 — §6's "no instrument" is wrong

§6 says this change *"moves no decision output the day it lands"* and asks for exactly one thing
before that is believed: **"it must be measured against the live universe before it is called
cosmetic."** Measured. It is not cosmetic, and the record should not be ratified on the belief that
it is.

### 8.1 Twenty-three admitted instruments are refused by this guard today

Every member of the live universe, run through `look_through`:

| Outcome | Members |
|---|---|
| sector spendable | 1,018 |
| **degenerate — refused by `DR-006` §8.7** | **23** |
| no sector served at all | 101 |
| nothing stored | 44 |
| **total** | **1,186** |

**Robust to `DR-017`'s lag**, checked both ways so the number cannot be an artefact of the change
that landed the same day: 23 under `adtv_lag=0` (1,128 members) and 23 under `adtv_lag=3` (1,186).

### 8.2 Why §6 got it wrong, and it is a sampling error rather than a reasoning one

§6 reasons about *"a candidate or an open position in one of those five funds"* — the five SPDR
Select Sector funds §2 measured. **None of the eleven SPDR funds is in the universe**, for a reason
that has nothing to do with this record: coverage is still an alphabetical prefix of the directory
and the letter X has not been reached, the same reason `DR-018` §2b found the benchmark ETFs
missing.

So §6 measured the population the record was *written about* and not the population the guard
actually runs on. The guard fires on **any** fund whose sector weights are degenerate, and 23 of
those are admitted today.

### 8.3 How many would flip is NOT measured here, and it is certainly not zero

The 23, with the sector the vendor puts at exactly 100%:

| | Reported sector at 100% |
|---|---|
| `CURE`, `ARKG` | healthcare |
| `DPST`, `BIZD`, `DFAR`(realestate), `ANGL`, `BCI`, `BINC`, `BOND`, `COMT` | financial_services / realestate |
| `AAPU`, `AMUU`, `AVL`, `CHPY`, `BNDW`, `BNDX` | technology |
| `AMZU` | consumer_cyclical |
| `DFEN` | industrials |
| `DRN` | realestate |
| `CARY` | basic_materials |
| `FIXD` | utilities |
| `UITB` | energy |
| `NEAR` | healthcare |

**The split is inference, not measurement, and is marked as such** (`AGENTS.md` §10.4). Some are
plainly equity funds whose reported sector is *correct* and which this guard is wrongly refusing —
`CURE` is a 3× healthcare equity fund reported as healthcare, `DPST` a 3× regional-bank fund
reported as financial services, `DRN` a 3× real-estate fund reported as real estate. Others are
plainly the `NEAR` signature — `BNDW` and `BNDX` are global bond index funds reported as
**technology**, `UITB` a core bond fund reported as **energy**, `FIXD` an active bond fund reported
as **utilities**.

**The exact count needs `stockPosition`, and that is §8.4.** What is settled is that it is not zero,
because at least the first group exists.

### 8.4 The discriminator reads a field this project does not store

`still_to_build: the discriminator itself` understates the work. `Classification` carries
`quote_type`, `industry` and the sector weights; the `classifications` table carries the same. The
vendor adapter reads `funds_data.sector_weightings` and nothing else. **`asset_classes` is read in
exactly one place — `tools/probe_sector_benchmarks.py`, live, over the network.**

So building §4 requires, before the discriminator: a field on the contract, a column on the store, a
vendor-adapter change, and a **refetch of every stored classification** to populate it. None of that
is in the header.

### 8.5 What follows for ratification

**Nothing here disagrees with §4.** The defect is real, the proposal is right, and §8.1 makes the
case stronger rather than weaker — the guard is wrongly refusing instruments that are actually in
the universe, not hypothetical ones.

What changes is the **cost and the timing**. Building this moves decision output on the live
universe today, so it spends a Track A `a.run_completes` reset. `DR-017` and `DR-023` took this
window's reset on 2026-08-30, and the standing rule is that a second one either joins that merge
before it lands or waits. It did not join it. **So this waits for the next window**, and §6's
"no decision output" is no longer available as an argument for landing it cheaply.

## 9. Built and ratified 2026-08-31

Ratified with §8's correction attached: §6's *"on today's stored universe that is no instrument"* was
measured false on 2026-08-30 — **23 admitted members of the live universe** sit in the refused state,
not zero — and §8.2 records that the error was sampling rather than reasoning.

### 9.1 The shape is the trigger; the vendor's own answer is the discriminator

`look_through` refuses a degenerate look-through **only when the vendor does not positively report
equity**. `Classification` gained `equity_share`, read from `funds_data.asset_classes.stockPosition`
in the same response the sector weights already came from — which is what made the inference
avoidable all along, and is `AGENTS.md` §12's named trap with the measurement sitting in the payload.

§5's promise is kept: **no parameter, and no tolerance in either half.** The shape must be degenerate
and the equity share must be positive. 0.997 against 0.0 is not a close call.

### 9.2 `None` is not zero, and that asymmetry is what makes this safe to ship

An unanswered `equity_share` is a fact about the **vendor**; a reported `0.0` is a fact about the
**fund**. Neither is evidence of equity, so neither clears the refusal — and the two print
differently, because a reason that collapsed them would send someone re-fetching a fund that
answered.

**The consequence is that the code change alone moves nothing.** Every one of the 1,148
classifications stored before today has `equity_share = NULL` and behaves exactly as it did. Only an
affirmative answer can admit, never silence, so the rollout is incremental and fail-closed by
construction. What moves admission is the **backfill** — §9.4.

### 9.3 A nullable column may now be added to a populated table

`platform/schema.py` refused to open any store missing a declared column while it held rows. Its own
reasoning is about `NOT NULL`: *"filling one on existing rows means inventing a value, and unset is
not a default."* **That argument does not reach a nullable column.** NULL is not a default — it is
"this row was written before the column existed and nobody asked", which is exactly true of all
1,148 rows here.

So the reconciler now adds a missing **nullable** column to a populated table and still refuses a
missing `NOT NULL` one, naming only the column that actually cannot be added. Without it this record
would have required a hand migration of the shipped store to record a fact already true of every row
in it. Both branches are tested, including that the exemption does not leak into the `NOT NULL` case
— which would silently re-open the four-day defect that module was written for.

### 9.4 What it costs on Track A, and what actually spends it

**A restart, taken 2026-08-31 on the owner's grant.** The code alone changes no admission (§9.2);
the **backfill** of the 23 degenerate-shaped instruments is what does, by giving the guard an answer
to read. The two land together because separately the first is inert and the second is unexplained.

Of the 23, some are equity funds refused on a reason false for them — `CURE` (3× healthcare equity,
reported healthcare), `DPST` (3× regional banks, financial services), `DRN` (3× real estate) — and
others are the `NEAR` signature and stay refused, with `BNDW` and `BNDX` global bond funds reported
as **technology**. **Which is which is the vendor's to say, not this record's**, and that is the
whole point of asking instead of inferring.

### 9.5 What this still does not do

`risk.max_sector_risk` keeps its value and its `assumed:DR-006` provenance. `DR-006` §3's
admit-on-unavailable rule is untouched. The point-in-time weakness of the classification — the
sector known is today's, not the one in force on an older date — is unaddressed and stays so.
