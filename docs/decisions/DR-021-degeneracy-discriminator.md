# DR-021: The degeneracy guard should ask whether the fund holds equity, not infer it from the shape

```
date:            2026-08-30
status:          proposed — owner ratification required. It amends an ACCEPTED record
parameters:      none. Deliberately - see section 5
components:      reference_data.classification:look_through
supersedes:      nothing. It AMENDS DR-006 section 8.7, which stays in force until this is ratified
implementation:  none
still_to_build:  the discriminator itself, once ruled
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
