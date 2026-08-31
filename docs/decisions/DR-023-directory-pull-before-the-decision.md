# DR-023: The symbol directory is pulled before the run decides, not after it

```
date:            2026-08-30
status:          accepted — ratified by the owner 2026-08-30
parameters:      none — an ordering, not a threshold
components:      none — the universe builder and the collector are both unchanged
supersedes:      nothing. It AMENDS DR-008's Decision, which places the collector "after the
                 trading scan"; DR-008 is accepted, so it is corrected forward here rather than
                 edited (AGENTS.md §11 rule 2)
implemented_by:  tools/daily_run.cmd :: goto :directory_done
built:           2026-08-30, merged with DR-017 as one Track A counter reset (DR-015 §3)
```

## 1. The subject, and why it is a third record

`DR-015` decides **how fresh a bar must be** to decide on. `DR-008` decides **how the directory is
pulled** — the source, the local switch, the calendar, the audit trail. Neither decides **when the
pull happens relative to the decision that reads it**, and that is this record.

`DR-008`'s Decision names the order — *the collector runs after the trading scan* — but as a
consequence of calling it a sidecar, not as a choice about input freshness. The word doing the work
there is "sidecar": the point being made was that a failed pull must not fail the run. That argument
is untouched and still holds (§4).

## 2. The defect

`tools/daily_run.cmd` ran `fetch_directory.py --scheduled` **after** the pipeline, and only in the
first pass. So on any evening:

- the **18:30** pass built its universe from the directory pulled the **previous** evening;
- the pull then ran, at about 18:35;
- the **19:30** pass — which pulls nothing — built its universe from **that** pull.

The 18:30 run, the one Track A counts and the one the owner reads, was the only run of the day
deciding on a day-old list of what exists.

### 2.1 What that actually costs, measured

`data/directory.duckdb`, comparing the directory as each pass saw it. **Not the count the pull
reports** — the eligible set the universe builder actually reads:

| Evening | Eligible at 18:30 | Eligible at 19:30 | Listed that day, invisible to 18:30 | **Already delisted, still visible to 18:30** |
|---|---|---|---|---|
| 2026-08-25 | 13,136 | 13,140 | 7 | **3** |
| 2026-08-26 | 13,140 | 13,148 | 15 | **7** |
| 2026-08-27 | 13,148 | 13,151 | 21 | **18** |

**The right-hand column is the one that matters.** The newly-listed symbols cost nothing today: the
store holds no daily bar for a single one of the 43, and `universe.min_bar_history` needs 250, so
none of them could have entered the universe on either pass. The cost there is a day's delay in
starting to accumulate their history — a coverage cost, phase 3's currency, not a decision cost.

The delisted symbols do reach the decision. On 2026-08-27 the 18:30 pass decided on `LEG`, which had
already left the vendor's directory; it recorded a `Skip/DATA`. Deciding on an instrument that no
longer exists is the defect, and a `Skip` is only the least harmful way for it to surface.

## 3. The measurement this record was expected to explain — and does not

**The session that scheduled this work attributed something else to this ordering, and that
attribution is wrong.** The claim was that the two evening passes' `universe_hash` diverged
*because* they read different directories. Checked against the stores on 2026-08-30, before
building anything:

Across 2026-08-24 → 08-27, comparing the passes decision by decision rather than by hash:

| Evening | 18:30 decisions | 19:30 decisions | Instruments that left | Joined | **Decisions that changed** |
|---|---|---|---|---|---|
| 08-24 | 1,141 | 1,141 | 0 | 0 | **0** |
| 08-25 | 1,141 | 1,140 | 1 | 0 | **0** |
| 08-26 | 1,140 | 1,137 | 3 | 0 | **0** |
| 08-27 | 1,137 | 1,134 | 3 | 0 | **0** |

**Not one decision ever differed** — that part of the original finding replicates exactly. But the
seven departures do not come from the directory. Six of the seven were present in **both**
directories, and the directory *grew* between the passes rather than shrinking. Recomputing each
one from the bar store as of each pass:

| Instrument | ADTV at 18:30 | ADTV at 19:30 | Why it left |
|---|---|---|---|
| `DGCB` | 5,138,709 | 4,997,203 | volume revised down across the $5M floor |
| `CAC` | 5,247,115 | 4,990,264 | same |
| `DMLP` | 5,209,775 | 4,913,197 | same |
| `BSTZ` | 5,062,641 | 4,841,386 | same |
| `EEMA` | 5,684,003 | 4,801,971 | same |
| `ANNX` | — | — | the 08-26 bar had not arrived at 18:30; when it did, the close was 4.99 against a $5.00 price floor |
| `LEG` | — | — | **the directory** — the one of seven that this record explains |

**Five of seven are `DR-017`'s defect**, arriving an hour apart instead of a replay apart: the
vendor rewrote volume between 18:30 and 19:30 and five instruments sitting within 3% of the $5M
line crossed it. Under the three-session lag `DR-017` ratifies, **all five hold their side of the
floor at both passes** — 5.50M, 5.57M, 5.96M, 5.34M and 7.41M against the same floor.

So the two changes in this merge fix two different halves of the same symptom, and neither would
have fixed it alone. That is the strongest argument for `DR-015` §3's one-reset rule yet: split
across two merges, the first would have been verified against a divergence it could not close, and
would have looked like a failure.

**This record's own justification is §2.1, not this section.** An input read after the decision that
consumes it is wrong on its face; it did not need a hash divergence to justify it, and it turns out
it never had one.

## 4. The constraint the move had to preserve

`DR-008` placed the pull after `set RC=%ERRORLEVEL%` **so that it could not change the run's exit
code**, and therefore could not spend a Track A `a.run_completes` session on a vendor's bad
afternoon. That is a real guarantee and moving the pull above the pipeline puts it back inside the
exit code's path.

It is preserved, and made explicit rather than positional:

1. `set RC=%ERRORLEVEL%` still reads the scan and only the scan — it sits immediately after it.
2. The pull's own errorlevel is cleared (`ver > nul`) before anything else can read it.
3. A failed pull writes a line to the same log and the pass continues on the directory already
   stored — which is precisely what every pass did before this change, since a pull that failed
   after the scan also left the next run on the previous directory.
4. Two tests in `tests/test_gates.py` pin 1–3, because the guarantee is now a property of the code's
   order rather than of the pull being out of reach.

**What is NOT preserved is the accident that made it safe.** Position was doing the work; now the
argument is written down and tested. That is the honest trade for reading the directory on time.

## 5. Alternatives rejected

**Pull in both passes.** Rejected by `DR-008` c3 and still rejected: a pull is attributed to the
session date the vendor's own `Last-Modified` reports, so an hour-later second pull adds a duplicate
row or a refusal to the one record whose entire value is being auditable.

**Pull in a separate scheduled task before 18:30.** It removes the coupling, and it adds a second
thing that must fire on a machine whose *availability* is the measured binding constraint on Track A
— two chances to be asleep instead of one. The pull is 30 seconds inside a six-minute pass.

**Leave it, and accept a day-stale directory.** This is what the numbers in §2.1 refuse: 3 to 18
delisted instruments reaching the decision every evening, and the one run the owner actually reads
being the stale one.

## 6. What would overturn this

A pull that becomes slow or unreliable enough that running it ahead of the scan delays the decision
past the owner's evening window. It is about 30 seconds today. If it grew, the answer is the
separate scheduled task rejected in §5, and the machine-availability argument would have to be
re-weighed against a real number rather than a hypothetical one.

## 7. Consequences

**The two passes now read one directory, pulled before either decides.** Combined with `DR-017`'s
lag they should also produce one `universe_hash`; §3 is the reason that expectation belongs to both
changes together and not to this one.

**The verification is the next evening's journal**, not a test: `universe_hash` for the 18:30 and
19:30 passes of the same date should agree, where for the last four measured evenings the 18:30 hash
instead matched the *previous* evening's 19:30 hash.

### 7.1 The prediction above is not unconditional, and saying so now is the point

**One of §3's seven departures survives both changes, and it would be dishonest to let the next
evening's journal discover that for us.** `ANNX` left the universe on 2026-08-26 because the
session's bar had not arrived by 18:30; when it did, the close was 4.99 against a $5.00 price floor.
Neither change touches that:

- `DR-017` lags the **ADTV window**. It deliberately does **not** lag the price test — §7.2 of that
  record explains why, and a stale close is not something either record wants.
- `DR-023` fixes the **directory**, and the directory said nothing about `ANNX` either way.

So **a bar arriving between the two passes can still move the universe**, and on an evening it does,
`universe_hash` will differ with both fixes working exactly as designed. That is `DR-019` §2's late
arrival, measured at 4.8 to 7.1 hours after the close, and it is the one thing an hour's gap between
the passes is genuinely for.

**What the two changes remove is the two causes that were NOT that**: a day-stale directory, and a
liquidity screen decided on volume the vendor was still rewriting. If the passes disagree again, the
question to ask the journal is *which* instrument moved and why — not whether the fix landed.
Comparing the passes **decision by decision** is what §3 had to do to get a true answer, and it
remains the right comparison.
