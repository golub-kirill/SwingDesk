# DR-015: Two sessions is too stale to decide on, and a failed fetch retries three times then once more at 19:30

```
date:            2026-08-18
status:          accepted — ruled by the owner 2026-08-18
parameters:      data.freshness_window
components:      none — calendar.sessions_behind already implements the measurement
supersedes:      nothing. Supplies the number DATA_QUALITY_SPEC section 2.1 has always required
implemented_by:  src/swingdesk/market_data/freshness.py :: def assess
also_built:      market_data/retry.py (the wrapper), application/pipeline.py (both decision reads),
                 presentation/cli.py (the injection), tools/daily_run.cmd (the 19:30 pass)
built:           2026-08-18. Section 7 records what landed and the one number it had to read
                 between the lines.
```

## 1. Why this record exists

`DATA_QUALITY_SPEC.md` §2.1 specifies the whole staleness rule and always has:

> Compare the last bar's session date against the calendar's last completed session for that
> instrument's exchange. `sessions_behind > 0` means stale.
> Stale → refetch once. Still stale → `DATA` skip. `data.freshness_window` sessions behind → the
> instrument is dropped from the run entirely.

`calendar.sessions_behind()` implements the measurement correctly. **Nothing calls it**, because
`data.freshness_window` is `unset` — and an unset parameter is a refusal, not a default, so wiring
it before this record would have refused every instrument.

Found 2026-08-18 as the last mutant surviving the whole test suite: not a weak test, but a correct
function with no caller.

## 2. Decision

**`data.freshness_window = 2` trading sessions**, provenance `assumed:DR-015`.

**Retry on a failed fetch: three attempts, 30 seconds apart, inside the run. Then one more pass at
19:30**, an hour after the scheduled 18:30.

### 2.1 The window is not a tolerance, and this is the part most likely to be misread

**A refetch is triggered by ANY staleness — `sessions_behind > 0` — not by reaching the window.**
The window decides when to *stop trying and drop the instrument*, not when to start caring.

The owner raised exactly this: *"from Friday to Monday we have to update data before calculations,
because on weekends anything might happen."* That case is already covered, and it is worth showing
the arithmetic, because "window = 2" reads like "two sessions of tolerance" and is not.

A Monday 18:30 run against a series ending Friday: the sessions in `[Fri, Mon]` are two, so
`sessions_behind` is **1**. One is greater than zero, so Monday refetches before it computes
anything. The window would only matter if Monday's refetch also failed and Tuesday's did too.

### 2.2 Sessions, never calendar days

Friday's bar on Monday is **one session** old and **three calendar days** old. Counting calendar
days would make a normal Monday run declare the whole universe stale and refuse. Every duration in
this system counts sessions (`AGENTS.md` §3), and this one is no exception.

### 2.3 Why 2

The weakest part of this record, stated plainly. It is a judgment, not a measurement, and it reads
`assumed`.

What can be said for it: one session behind is the ordinary state of a run whose fetch failed once
and will be fixed by the retry. Two is the first count that cannot be explained by a single failed
attempt — it means both today's retries and yesterday's failed, which is a vendor outage rather
than a hiccup. Deciding a trade on it would be deciding on data from before the last session the
market actually had.

## 3. The retry policy, and where it lives

**Three attempts, 30 seconds apart.** Ninety seconds inside a run that takes about five minutes. It
costs nothing and covers the failure this is actually for — a transient vendor error or a momentary
network fault.

**Then one more pass at 19:30.** The owner chose a second scheduled run over blocking the first.
That is the right call and the reasoning belongs here:

- **Blocking would corrupt the measurement.** `a.run_completes` counts a run that completes and
  produces a report. A run that sleeps for an hour still "completes", so the counter would read
  clean while the owner's evening was held hostage. The notice would arrive at 19:35 with a report
  an hour stale at birth.
- **A second pass is idempotent by construction.** The stores are append-only and bitemporal, so a
  19:30 run that finds nothing new writes nothing new. `output_hash` covers the decisions, so two
  runs that decided the same thing are visibly the same run.

**The retry wrapper goes around the FETCHER, not inside `pipeline.py`.** `run()` takes the fetcher
as an injected argument, so retries can be added without touching a frozen file, and the pipeline
stays pure — no sleeping inside the decision path.

**The 19:30 pass does touch `tools/daily_run.cmd`, which is frozen, and merging it resets the Track
A counter.** Doing it now is deliberate: the counter is at **0** after the 2026-08-17 restart, so
the reset costs nothing today and would cost two weeks in two weeks.

## 4. What this does NOT decide, and it is bigger than what it does

**Corporate actions.** The owner's reason for the rule — *"on weekends anything might happen"* —
points at a risk this record does not close.

Both the candidate path and the held-position path read `Series.RAW` (`pipeline.py`). Raw bars are
unadjusted, so a split does not restate history; it means **the next bars arrive at a different
price level**. A 2:1 split over a weekend leaves a stored stop of 290 being compared against Monday
raw prices near 145 — an instant stop-out that never happened, on a position the owner still holds.

`DATA_QUALITY_SPEC.md` §4 specifies the gate that catches this in full, including the
`DATA_ERR` / `Critical` case for a changed raw bar. **None of it is implemented** — there is no
mention of splits or dividends anywhere in `src/` — and its parameter `data.revision_epsilon` is
`unset`. It is the same shape as this record one gate over, and it needs its own.

**This is the more dangerous of the two.** Stale data makes the system decide on old information,
which the refusal above now prevents. An unhandled split makes it decide on *wrong* information
while every freshness check passes.

## 5. Alternatives rejected

- **Calendar days.** §2.2. It would refuse the universe every Monday.
- **Blocking the run for an hour.** §3. It launders a stalled evening as a clean run.
- **A tolerance rather than a trigger** — refetching only once the window is reached. It inverts the
  spec: staleness would go unaddressed for a full session before anything tried to fix it.
- **Retrying more than three times inside the run.** The failure this covers is transient; a fourth
  attempt at 30 seconds tells you nothing the third did not, and every added attempt is time the
  scheduled job holds open.
- **Leaving `sessions_behind` unwired and deleting it.** It is a correct implementation of a
  ratified rule. The missing thing was never the code.

## 6. What would overturn this

A measured distribution of how often fetches fail and how many sessions behind the store actually
gets. `data/daily_run.log` has recorded every scheduled run since 2026-08-09 and nobody has counted
this. If failures are almost always fixed by the first retry, the second and third are ceremony; if
they routinely survive to 19:30, the window is the wrong instrument and the vendor is the problem.

## 7. Built, 2026-08-18

Recorded here rather than in a session file because §6 asks a question this build partly answered,
and because one number had to be read between two the record states.

**What landed.** The retry wrapper (`market_data/retry.py`), injected in `cli.py` so `pipeline.py`
never sleeps; the freshness verdict (`market_data/freshness.py`), read at both decision points in
`pipeline.py`; and the second pass, as an argument to the same `daily_run.cmd` rather than a second
copy of it. `data.freshness_window`'s `read_by` now names its consumer, so the parameter has left
the decided-but-not-wired count (27 → 26).

**The refetch in §2.1 is discharged by the pipeline's own shape, not skipped.** "Stale → refetch
once" describes a store-first system. This pipeline fetches every candidate and every held position
*before* anything reads the store, and with the wrapper in place that fetch is up to three attempts.
A further vendor call at the freshness check would be a second request for the same bars
milliseconds after the first — 67 of them on the 2026-08-17 universe — answering nothing the first
did not.

**The one number this record does not state, and the implementation needed.** §3 gives two figures
that do not agree: *"three attempts, 30 seconds apart"* is two sleeps and 60 seconds; *"ninety
seconds"* is three. The attempt count is stated twice, so it governs per instrument. Ninety seconds
is then read as what it literally says — a ceiling on a **run** — and implemented as a sleep budget
spent across the whole run.

**That ceiling is not decoration.** §3 costs the retry as *"ninety seconds inside a run that takes
about five minutes"* and concludes *"it costs nothing"*, which is the arithmetic for one instrument
failing once. The wrapper is called per instrument and the scheduled universe was **1152 members**
on 2026-08-17, so an unbounded retry through a vendor outage is over nineteen hours of sleeping on
a job that must finish before this record's own 19:30 pass. The budget is what makes §3's stated
cost true. **It is an implementation reading of this record, not a second ruling** — if the owner
wants a different ceiling, or wants the full three attempts guaranteed for every instrument
whatever the total cost, that is a change to make here.

**§6's question, partly answered.** The distribution it asks for was measured before building, from
the log it names: ten scheduled runs (2026-08-09 → 08-17), roughly 11,200 instrument-fetches,
**zero** `VendorUnavailable` — no "no data returned", no "no usable rows after validation". So on
the evidence so far the retry is insurance against a failure that has not yet occurred here, which
is precisely why its worst case is bounded rather than extrapolated from the observed one. The half
§6 still wants — how many sessions behind the store actually gets — was also measured, and it is
not zero: see §8.

## 8. What the gate found on the day it was wired

Measured against the 2026-08-17 scheduled run, before any of this existed:

| | |
|---|---|
| Candidates evaluated | 1152 |
| Level with the last completed session | 1085 |
| **One session behind** | **67 (5.8%)** |
| At or past the window | 0 |

Every one of those 67 was **sized and left on `Watch`** against a close from the previous session,
and every one reported `completeness clean` — correctly, because §2.2 looks for a hole *inside* the
stored window and a series that simply stops early has no hole. Staleness and completeness are
different questions, which is why `DATA_QUALITY_SPEC` §2 asks both, and why nothing in the report
distinguished those 67 from the other 1085.

They now leave with a `DATA` skip. **That is a behaviour change on the live path**, it moves
`output_hash`, and it is the change this record was ruled to make.
