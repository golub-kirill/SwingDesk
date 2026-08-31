# DR-024: The card's own measure is computed and reported before anything is ranked by it

```
date:            2026-08-30
status:          accepted — ratified by the owner 2026-08-30
parameters:      none new. Reads rs.benchmark (= SPY, assumed:DR-018) and no other
components:      M31-T0464-v5.0 activated — `specified` to `active`
supersedes:      nothing. It supplies the CONSUMER that COMPONENT_REGISTRY_SPEC 3's
                 "displays its validation status wherever its output appears" needs
implemented_by:  src/swingdesk/application/pipeline.py :: def _benchmark
also_built:      pipeline.run (the per-candidate call and the output_hash field),
                 presentation/report.py (the benchmark block and the RS lines),
                 registry/components.yml (the activation)
built:           2026-08-30. Merged inside the same window as DR-017 and DR-023, so it shares
                 their Track A restart rather than taking a second one — §6 measures that.
```

## 1. What was wrong, and it was not a defect in anything

`CARD-001` is the live strategy card and `ROADMAP.md` §9 makes phase 3's exit *"every component a
live card needs is `active`"*. The card names four components. One of them, `M31-T0464` — relative
strength against the index, the card's **measure** — was implemented, property-tested, spec'd, and
**called by nothing outside its own tests**.

That is the shape `DR-015` found once already: a correct function with no caller, which survived the
whole suite as the last mutant. Nothing was broken. The measure simply did not exist anywhere the
owner could see it.

**And it could have been marked `active` at any time without a line of code changing.** It declares
no parameters, so `COMPONENT_REGISTRY_SPEC` §3's bar — parameters valued, verification present,
`implements` pointing at real code — was already met on 2026-08-24. `cards.yml` says so in as many
words: *"it is held at `specified` because activation is a decision, not because an artefact is
missing."*

**Flipping the flag was the option this record rejects.** §3 also says an active component
*"displays its validation status wherever its output appears"*, and the output appeared nowhere. A
component nothing calls, declared `active`, is a status claiming more than the system does — which
is the one thing `AGENTS.md` §3 exists to prevent, at the exact point where it would be easiest and
cheapest to do.

## 2. The decision

**The run computes the RS line for every candidate and the report prints it, with its validation
status and with a line saying it selects nothing.** `M31-T0464` then activates, because it is now
true that its output appears somewhere with its status beside it.

Three properties, and each is a constraint rather than a description:

| | |
|---|---|
| **It decides nothing** | there is no branch anywhere below it that reads the value |
| **One benchmark per run** | fetched once, before the candidate loop |
| **It is in `output_hash`** | so gate 9 can see it change |

### 2.1 It decides nothing, and that is enforced by there being nothing to enforce

`CARD-001`'s selection reads `rs.benchmark_form`, `rs.lookback`, `rs.ranking_method` and
`screen.relative_strength_rule`. All four are `unset`, `ALLOCATION_SPEC` §3 sends them to a
pre-registration rather than a decision record, and `PR-012` — the study that would have set them —
refused a verdict for want of sample. So the card is blocked, and this record does not unblock it.

**What it does is put the measure in front of the owner while the selection question is still
open**, which is the right order: a number nobody has looked at is a poor thing to build a ranking
on.

The consequence for the code is that every failure mode of the benchmark must cost an *observation*
and never a *decision*. `_benchmark` therefore returns a `Benchmark` carrying a reason where the
other run-level reads return a `Refusal`:

- `rs.benchmark` unset → unavailable, run unaffected;
- `rs.benchmark` **absent from the registry** → unavailable, run unaffected, and the report says
  *"code and registry disagree"*. That case is a real defect gates 1 and 28 make impossible in a
  shipped tree, and the proportionate response to it here is still not to kill the daily run over a
  measure that decides nothing;
- the vendor fails but the store holds bars → the stored series is used and **labelled stale**,
  because refusing to report an RS line over a vendor blip loses the measure for a reason that has
  nothing to do with it;
- the vendor fails and the store is empty → unavailable.

`tests/test_relative_strength_run.py` pins each against a control run that reaches `Watch`.

### 2.2 One benchmark, fetched once, and that is correctness rather than caching

**A cross-sectional measure compares names to a common denominator.** Read inside the candidate
loop, names sorted before `SPY` would be measured against yesterday's benchmark and names after it
against today's — a point-in-time split decided by **alphabetical order**. That is the same class of
bug `DR-023` closed a few hours earlier at the level of the whole directory, and it would have been
much harder to see here.

**Fetched by name rather than relied on as a universe member.** `SPY` is admitted by the `DR-003`
rule today, so the run already pulls it and the series is fresh. That is incidental. Fetching it
here keeps the measure working on the day the proxy falls out of the universe — which is exactly the
day nobody would notice it had, because the RS line would go on printing against a slowly ageing
denominator.

### 2.3 In `output_hash`, and the argument is the docstring's own

`_output_hash` records four measured cases of a number the run computed, printed, and hashed
identically anyway: halved share counts, stops moved 40%, and an entire open position. Its standard
is *"two runs that hash alike must be two runs the owner could not tell apart at the point of doing
something."*

**The RS line is printed beside the decisions, so it is exactly that kind of number**, and leaving
it out would make it the fifth case. The counter-argument — that it selects nothing, so nobody can
act on it — is an argument about what the value is *for*, not about whether a replay should
reproduce it. A new computation on the decision path that gate 9 cannot see is a blind spot whether
or not anything currently branches on it.

## 3. What the report says, and why the second line is not decoration

```
  M31-T0464-v5.0 v1
      RS vs benchmark    3.3519  ratio
      validation         Not Applicable
      selects nothing    rs.benchmark_form is unset; CARD-001 is blocked
```

The `validation` line is the condition of activation (`COMPONENT_REGISTRY_SPEC` §3).

**The `selects nothing` line is there because `DR-018` §1 measured the misuse.** Ranking a
cross-section by this value is identical to ranking by raw return — Spearman **1.000000** across 15
benchmark × lookback pairs over 1,148 names — because the benchmark's return is one constant for
every name that day. The component's own docstring calls the misuse natural. A report that printed
the number beside the decisions without saying so would be issuing the invitation.

## 4. Alternatives rejected

**Flip the activation flag and write no code.** Cheapest, and it makes `active` mean less for every
other component. §1.

**Compute it in a tool rather than in the run.** It keeps `pipeline.py` untouched, and it produces a
number from a different code path than the one the owner's evening actually runs — so the reported
measure and the run's measure could disagree, and nothing would notice. The card names it as the
card's measure; the card's run is where it belongs.

**Rank by it now.** It is the one thing `ALLOCATION_SPEC` §3 forbids without a pre-registration, and
`DR-018` §1 shows the obvious form would be ranking by raw return with a decorative denominator.

**Journal the RS values for a future study.** Not needed, and rejected as scope: the RS line is a
pure function of stored bars and the bar store is bitemporal, so any past run's RS is recomputable
exactly as of when it ran. A journal column would be a second copy of a derivable fact
(`AGENTS.md` §10.5).

## 5. What this does NOT do

**It does not move `CARD-001` off `Untested`,** and it closes only the fourth of the card's four
`blocked_by` entries in part: `M31-T0464` is now `active`; `M31-T0465`, `M33-T0487` and `M77-T1138`
remain `registered`. The three unset-selection blockers are untouched and need a study.

**It does not make the sample problem smaller.** `PR-012`'s structural shortfall is unchanged.

**It does not settle `M77-T1138`.** That row is the same measure at the Setup stage and is
deliberately not claimed by this function — Production Rules 3.8 forbids two components sharing one
definition and gate 11 enforces it. Whether it names something distinct needs the source PDFs.

## 6. The Track A cost, measured rather than assumed

**This moves decision output** — `output_hash` gains a field, so no run before it replays to the
same hash — and that ordinarily spends an `a.run_completes` reset.

**It spends none, because it lands inside the window `DR-017` and `DR-023` already reset.**
Measured on 2026-08-30 rather than argued: `track_a_streak.restarted_at` returns 2026-08-30, the
streak counts only sessions **strictly after** the restart date, and the count of countable sessions
after it is **zero** — 2026-08-30 is a Sunday, so the next session is Monday 2026-08-31. A second
restart row dated the same day truncates the identical window.

**That is a fact about today and not a general licence.** From the first countable session onward,
the standing rule applies again in full: a change that moves decision output either joins a merge
already taking a reset, or waits for the next window.

## 7. What would overturn this

A measured cost to the run's duration. The benchmark is one extra fetch and the RS line is one pass
over each candidate's stored bars; on the live universe that is 1,186 candidates against a six-minute
pass. If it ever bound, the answer is to compute the line only for candidates that reach a decision
worth printing, not to stop reporting it.

And the obvious one: **`rs.benchmark_form` getting a value.** The moment a pre-registration sets the
form, this record's "selects nothing" line becomes false and the report must stop saying it.
