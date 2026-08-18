# DR-017: The ADTV window is lagged three sessions, because volume is still being written for two

```
date:            2026-08-18
status:          proposed — needs an owner ruling on the lag
parameters:      universe.adtv_lag_sessions (new, proposed value 3)
components:      none — the universe builder already windows the bars it averages
supersedes:      nothing. DR-003 set the threshold; this decides which bars it is applied to
implementation:  none
still_to_build:  the lag itself, where the universe builder picks its window,
                 once the number is ruled
```

## 1. The defect

`universe.min_adtv_20d` admits an instrument on 20-day average dollar volume. **The vendor's volume
for recent sessions is not final**, so membership is decided on a number that is still being
written.

Measured on the store's own bitemporal history — the experiment was already in it and nobody had
looked. Of 7,131 already-settled bars the vendor served twice, **7,129 had their volume rewritten**:
p50 **1.1%**, p90 **32%**, p99 **83%**, worst case **164×**. Prices are not comparable — the close
moves by p90 0.02%.

**The consequence, measured rather than argued: 6 of 1,172 instruments cross the $5M line between
first sight and settlement, and all six in the same direction** — refused on the provisional number,
admitted on the settled one. Small, but strictly one-way, on the population every study runs on.

## 2. When volume actually settles — and the number this record first got wrong

**CORRECTION, and it is mine.** The first measurement of this reported *"volume settles completely
within 8 calendar days"*. That is not wrong as arithmetic, and it is the wrong unit:
`AGENTS.md` §3 makes sessions the unit of every duration in this system, and eight calendar days is
a different quantity every week. Re-measured in sessions, the answer is **much tighter and much
easier to justify**.

Revisions by the bar's age **in sessions** at the moment it was re-fetched, over the daily-run era
(2026-08-10 onward, one observation per session), 5,980 revisions:

| Age at re-fetch | Revisions | Share |
|---|---|---|
| 0 sessions | 1,013 | 16.9% |
| 1 session | 4,788 | 80.1% |
| **2 sessions** | **179** | **3.0%** |
| 3+ sessions | **0** | — |

**No bar three or more sessions old has ever been revised in this regime.**

### 2.1 The trap in this measurement, and why the era matters

Across the *whole* store the tail runs to 5 sessions — 802 revisions at 4 and 317 at 5. Every one of
them comes from a single capture, **2026-08-09**, the first scheduled run, which re-observed bars
first seen during the 08-02/08-03 bootstrap.

**Age-at-re-fetch is not settlement age.** If nothing looks at a bar for five sessions, a revision
the vendor made when the bar was one session old is recorded as a five-session-old revision. The
bootstrap gap manufactures exactly that. Only a regime that observes every session can separate the
two, which is why the table above is restricted to one — and why a future observation gap will
re-create the artefact rather than reveal a longer settlement.

## 3. Decision proposed

**`universe.adtv_lag_sessions = 3`**, provenance `assumed:DR-017`. The 20-day ADTV window ends three
sessions before the run rather than at the last completed session, so every bar it averages is one
the vendor has never been observed to revise.

Three, not two: two is the oldest age at which a revision was *seen*, so a window ending two
sessions back still includes a bar that was revised. Three is the first age with a measured zero.

**The direction was council-reviewed on 2026-08-18** (5 advisors + peer review). Unanimous against
treating the drift as noise, and unanimous against widening the $5M threshold to absorb it — the
latter dies at this project's own provenance gate, since a fudge factor has no course citation.
Direction chosen 4–1, and **the argument that carried it was reproducibility, not bias**: a lagged
window makes admission **idempotent**, so a replayed screen returns the number the live screen
returned. Today it cannot, because the bars underneath it keep changing.

**One universe and one lag for live admission and for studies.** Two universes is the failure mode
this would otherwise create, and it is worse than the defect being fixed.

### 3.1 The parameter is not in the registry yet, and that is not an oversight

Gate 3e refuses a document that cites a parameter id the registry does not hold, and it refused this
record's index row until the id was taken out of it. The id enters `registry/parameters.yml` **when
this record is ratified**, carrying `assumed:DR-017`.

**The reason to say so out loud is `AGENTS.md` §7**: every parameter needs `named_in` citing where
the course mentions the concept, and *the course does not mention a settlement lag*. It names dollar
volume as the liquidity measure (M33-T0481, Appendix A) and says nothing about which vintage of
volume to read. So on the strictest reading this is **invented scope** — the category §7 exists to
reject.

The defence, and the owner should weigh it rather than take it: the lag is not a new threshold about
the market. It is a correction to *how a course-named quantity is computed*, in the same class as
using the calendar rather than calendar days. `named_in` would therefore cite the ADTV source it
modifies. If that reads as a stretch, the alternative is to hard-code the lag as a constant beside
the universe builder with this record as its provenance — no registry entry, no `named_in` claim,
and the number still has one written reason.

## 4. What this costs

**Three sessions of staleness in the liquidity estimate.** An instrument whose volume collapses is
admitted for three more sessions than it would have been; one whose volume spikes waits three
sessions. Against a 20-session window that is a 15% shift in the averaging period, and the threshold
sits on a measured plateau — `DR-003` records that membership moves by 2 instruments in 115 between
$5M and $10M — so the admitted set is not sensitive at the margin the lag moves it.

**Cutover churn is a one-off and should be logged, not smoothed.** The first lagged run will admit
and refuse a different set than the last unlagged one, and that difference is a fact about the fix
rather than about the market.

## 5. What this does NOT decide

**Is backfilled volume executable?** The council's sharpest question and this record does not answer
it. The fill-in is overwhelmingly upward. If it is late off-exchange prints, then settled ADTV
**overstates the very liquidity $5M is a proxy for**, and lagging optimises toward a number that is
more reproducible and no more true. That is a separate measurement — the venue mix of the delta —
and it needs a source this project does not currently have.

**Whether `universe.min_adtv_20d = $5M` is the right threshold at all.** It is `assumed:DR-003` and
has never been swept. A $3M–$8M sweep would test it and would answer, in the same pass, whether the
six crossers are noise or signal. Ruling this record does not make that less needed.

## 6. What would overturn this

An observation regime with no gaps that still shows revisions at 3+ sessions. The table in §2 is
eight sessions of daily observation; it is enough to place the cliff and not enough to call it
permanent. The check is cheap and should be re-run after a quarter of scheduled evenings — the same
query, the same buckets, against a longer store.
