# DR-019: The second evening pass runs only when the first refused something a retry could repair

```
date:            2026-08-24
status:          accepted — the CONDITION ratified by the owner 2026-08-30, WITH the §7 amendment.
                 The TIME is untouched and remains the owner's (§6)
parameters:      none. The condition is read from the journal, not from a threshold
components:      none
supersedes:      DR-015 section 3's "then one more pass at 19:30", in its UNCONDITIONAL form only.
                 The retry policy inside the run - three attempts, 30 seconds apart - is untouched.
implemented_by:  tools/retry_needed.py :: def count_repairable
also_built:      tools/daily_run.cmd (the second-pass branch)
built:           2026-08-24
```

## 1. Why this record exists

`DR-015` §3 gave the evening a second scheduled pass, and gave a good reason: a fetch that failed
inside the run deserves one more chance, and blocking the first run for an hour would corrupt what
`a.run_completes` measures. Nothing in that reasoning is wrong.

**What was never checked is whether the pass does anything.** Measured 2026-08-24 from
`journal.duckdb`, over every evening that ran both passes:

| Session | Passes | `output_hash` |
|---|---|---|
| 2026-08-18 | 18:30 + 19:30 | identical |
| 2026-08-19 | 18:30 + 19:30 | identical |
| 2026-08-21 | 18:30 + 19:30 | identical |
| 2026-08-24 | 18:31 + 19:31 | identical |

The first three ran while the store carried a drifted column and both passes died, so they are weak
evidence. **2026-08-24 is the only pair where both passes were healthy, and the two runs decided
byte-identically.** That is also the first live observation of the idempotence `DR-015` §3 asserted
and nothing had ever demonstrated.

**And the failure the pass insures against has not been observed here.**
`market_data/retry.py`'s own docstring records ten scheduled runs across roughly 11,200
instrument-fetches with **zero** `VendorUnavailable`.

## 2. What actually happens, and why the 19:30 pass could not fix it

On 2026-08-24 the run left **86 of 1,141** admitted candidates refused *"one session behind"* — last
bar Friday 08-21 against a last completed session of Monday 08-24. The 19:30 pass re-fetched them
and changed nothing.

**Re-asking the same vendor at 22:09 local returned every one of those sessions, clean**, using the
runtime's own request shape (`period='max'`, daily). All 86, no missing fields, no errors.

So the bars existed; they had not been published when the run asked. Times are local, and the NYSE
close is 15:00 local:

| Moment | Hours after the close | Candidates without Monday's bar |
|---|---|---|
| 18:30–18:50 (first pass) | ~3.5 | 86 |
| 19:30–19:50 (second pass) | ~4.5 | 86 |
| 22:09 | ~7.1 | **0** |

**This is a late arrival, not a failed fetch.** A retry an hour later cannot create data the vendor
has not published, and one hour was not enough of a wait.

**Independently corroborated inside this repository.** `TODO.md` records that `PR-005`'s published
trade log stopped reproducing because **seven bars arrived three hours after it was published** —
the same tail, found the same day by a different session looking at something else.

**No publication schedule is documented.** Searched 2026-08-24; the vendor publishes none, and the
one relevant known defect — an open `yfinance` issue where `period='max'` omits the latest day — does
**not** apply, because the scheduled run requests `1y` (`pipeline.run(lookback="1y")`).

## 3. The decision

**The second pass asks the journal first: did tonight's run refuse anything a later attempt could
repair?**

- **`DATA` is that class.** Stale, incomplete or absent source data — precisely what arriving later
  fixes.
- **Every other code is not.** `RISK`, `STOP`, `LIQ` and the rest are decisions about the trade.
  Waiting does not move the book, the stop or the spread.
- **Nothing to retry ⇒ the pass does not run**, and says so in the log. Declining is a clean
  outcome, exit 0.
- **Unmeasurable ⇒ the pass RUNS.** If the journal cannot be read the condition is unmeasured, and an
  unmeasured condition must not silently suppress a pass. `AGENTS.md` §12: *unavailable is not
  `fail`, and it is not `pass` either.*

**The condition is read from the journal rather than a sentinel file.** The decisions are already
recorded; a marker would be a second copy of a fact the store holds (`AGENTS.md` §10.5).

## 4. Why this is allowed to touch a frozen file

`tools/daily_run.cmd` is frozen under `DR-015` §3, and the amendment resets `a.run_completes` when a
change **moves decision output**.

**This does not.** Track A counts the attempt whose start falls within ±30 minutes of 18:30, and the
branch added here is reachable only when the wrapper is invoked with `second-pass`. The first pass
jumps over the question entirely — asserted by a test, not by inspection. The 18:30 run's decisions,
exit code and log markers are unchanged.

## 5. What was proven, and how

The wrapper cannot be run here — it would start a real scan against the live stores — so its three
branches were exercised against a **stubbed copy that is otherwise byte-for-byte the real file**,
with only the external calls replaced:

| `retry_needed` exit | Wrapper exit | Scan ran | Log line |
|---|---|---|---|
| 0 warranted | 0 | yes | — |
| 1 nothing to retry | 0 | **no** | `second pass skipped, nothing to retry` |
| 4 unavailable | 0 | **yes** | — |

The first pass was run with the condition stubbed to *nothing to retry* and ran normally.

**The trap this design avoids, pinned by a test.** `if errorlevel N` in cmd means *N or greater*.
Written ascending, an `UNAVAILABLE` (4) would match the `1` branch and **suppress the pass on a
condition nobody could measure** — the exact inverse of the intent, silently. The test asserting the
descending order was confirmed to go red when the two lines are swapped.

## 6. Open — the owner's, and this record does not take it

**The condition is built. The TIME is not changed.** The measurement in §2 says the tail arrives
between roughly 4.8 and 7.1 hours after the close, so a pass at 19:30 local will keep missing it. A
later pass — around 22:30 — would catch what was measured.

**The cost is not technical.** `docs/runbooks/README.md` §1a makes registering a scheduled task the
owner's step, and `HANDOFF.md` records the task as `Logon Mode: Interactive only` — so a later pass
means being logged in later. That is a decision about the owner's evening, not about the software.

**One evening is one evening.** The arrival window rests on a single session's measurement. Before
moving the schedule it is worth measuring the curve over several evenings, which costs nothing but
patience and is recorded in `TODO.md`.

## 7. Amendment, 2026-08-30 — §1's headline claim is no longer true, and the conclusion survives

Ratified with this amendment attached, because **§1 rests on a sentence that stopped being true the
day after it was written**:

> *2026-08-24 is the only pair where both passes were healthy, and the two runs decided
> byte-identically.*

Three more healthy pairs have run since, and none of them produced an identical `output_hash`.
Leaving §1 as the record's only evidence would have left it standing on a one-observation claim that
the very next evening contradicted.

### 7.1 What the four evenings actually show

Re-measured 2026-08-30 from `journal.duckdb`, **decision by decision** rather than by hash — which
is the comparison §1 should have made and did not:

| Session | `output_hash` | `universe_hash` | Instruments that left | Joined | **Decisions that changed** |
|---|---|---|---|---|---|
| 2026-08-24 | identical | identical | 0 | 0 | **0** |
| 2026-08-25 | **differs** | **differs** | 1 | 0 | **0** |
| 2026-08-26 | **differs** | **differs** | 3 | 0 | **0** |
| 2026-08-27 | **differs** | **differs** | 3 | 0 | **0** |

**Across all four evenings, not one instrument was ever decided differently by the two passes.** The
hash moved because the *universe* moved — seven instruments left it between the passes over the
three later evenings, and every one of those departures has a cause that is not the second pass:
five were volume revised across the $5M liquidity floor within the hour (`DR-017`'s defect, fixed
2026-08-30), one was a bar arriving late, one was the symbol directory (`DR-023`).

### 7.2 So the conclusion is stronger, not weaker

§1 concluded that the second pass has never changed an outcome. The byte-identity that supported it
was a coincidence of one quiet evening; the decision-level comparison supports it **four times over,
including on three evenings where the hash said otherwise**.

**And it corrects a trap this record nearly set.** `output_hash` is the right thing to pin a run
with and the wrong thing to ask *"did the second pass matter?"* — it moves when any input moves,
including inputs neither pass controls. A record that had gone on citing hash identity would have
reported the pass as newly useful on 08-25 for a reason that had nothing to do with it.

### 7.3 What is NOT amended

§6 stands exactly as written. The condition is ratified; the TIME is not, the 19:30 pass will keep
missing the tail §2 measured, and moving it is a decision about the owner's evening rather than
about the software.
