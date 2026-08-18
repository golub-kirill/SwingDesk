# DR-015: Two sessions is too stale to decide on, and a failed fetch retries three times then once more at 19:30

```
date:            2026-08-18
status:          accepted — ruled by the owner 2026-08-18
parameters:      data.freshness_window
components:      none — calendar.sessions_behind already implements the measurement
supersedes:      nothing. Supplies the number DATA_QUALITY_SPEC section 2.1 has always required
implementation:  none
still_to_build:  the retry wrapper around the fetcher, the freshness check at the decision read,
                 and the 19:30 second pass. This record is the rule they were waiting on.
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
