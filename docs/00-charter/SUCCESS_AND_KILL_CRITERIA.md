# SUCCESS AND KILL CRITERIA

**Status: FROZEN — ratified by the owner 2026-08-02.** `registry/criteria.yml` v1.1.0.
**Tier:** 0 (charter)

**G0 is closed.** 19 criteria: 7 Track A, 6 Track B, 6 kill. **All nineteen ratified** — the Track A
time box was added and ratified 2026-08-08 (§5a).

These may not be edited after seeing a result they govern. Changing one is an **amendment** — a new
version of `criteria.yml` with the change recorded — and it voids any claim that depended on the
earlier definition (Production Rules §3.7, applied at project level).

---

## 1. Two tracks, and why

The system and the strategy are separate accountabilities. Merging them is what made the previous
project unfalsifiable: when "does it work?" means both *is the machinery sound?* and *is there an
edge?*, a bad answer to the second contaminates the first and neither gets decided.

| | Track A | Track B |
|---|---|---|
| Question | Is the system sound? | Is there an edge? |
| Scope | the whole system | **one strategy card** |
| Depends on the market | no | entirely |
| Measurable within | weeks | 100+ closed trades |
| Satisfiable while every setup is `Untested` | **yes** | no |
| Gates | G0 | activation of a card beyond `Untested` |

Track A is what SwingDesk is accountable for and it is fully in our control. Track B is what the
*trading* is accountable for, and it is pre-registered per card — never project-global, because
"the system is profitable" is not a testable claim when the system contains 460 components.

**Structure is frozen. Values are configurable.** That is the whole meaning of "flexible" here —
flexibility in the numbers, never in whether a criterion exists or when it may be edited.

## 2. Track A — the G0 bar

Seven criteria, all in `registry/criteria.yml`. In short: the run completes for 20 consecutive
trading days; every candidate carries a decision and a reason code; no refusal is uncoded; a re-run
reproduces its control byte-identically; plan/stop/journal present on 100% of taken trades; overall
process compliance ≥ 95%; zero `Critical` errors.

Two of these are the course's own words rather than our invention:

- **100% plan/stop/journal, no critical violations** — Appendix S, the single hard numeric gate
  anywhere in the course.
- **A re-run matches a control run** — the fail-closed table's return condition after a screener
  failure, `повторный run совпал с контрольным`. Determinism stated as an operating procedure.

## 3. Track B — per strategy card

Six criteria. The load-bearing choices:

- **Minimum 100 closed trades before any verdict.** The course's own figure (Appendix S). Below
  roughly this the expectancy confidence interval is too wide to act on, because the right tail
  dominates the mean — a handful of large winners moves the average more than the other ninety
  trades combined, so a small sample measures luck in tail placement rather than edge.
- **Deflated Sharpe on the *cumulative* trial count**, across the whole programme rather than
  per-strategy. With ~460 registered components the search space is large enough that a per-feature
  significance figure means nothing; the trial count carries forward across every pre-registration.
- **Benchmark-relative, not absolute.** Beating cash is not the bar.
- **Era stability.** An effect carried by one stretch of history is not an effect.
- **The survivorship marker is mandatory** on every Track B result. Not a threshold — a reporting
  obligation, because ~~no free source serves delisted instruments~~ **— refuted 2026-09-05,
  `python tools/probe_alpaca_delisted.py` serves complete daily paths for delisted names from
  2016; the free IEX feed serves none of it and the entitlement question is open —** every
  historical number is
  therefore optimistic by an unknown amount.

## 4. Kill criteria

Boxed by **time and sample**, not only by outcome. A project with no kill criterion does not fail;
it continues indefinitely, which is the failure mode this document exists to prevent.

| Scope | Trigger | Action |
|---|---|---|
| **project** | G5 not reached within 2 months of G0 close | **stop building** |
| **project** | Track A's run-measurable criteria not met within 120 days of the first scheduled run — or no run scheduled within 180 days of ratification | **stop; re-open the data tier**, or restate the project as documentation-only — §5a |
| strategy card | after 100 trades, expectancy CI entirely below benchmark | `Rejected`; retire the card — the project continues |
| programme | every card `Rejected`/`Retired` and no new premise clears the prereg refutation check | convert to journal + statistics only |
| live | drawdown exceeds the allowable limit | **`Pause`, not kill** — reduce size per the risk-off ladder |

Note the graduated shape: a failing strategy kills a card, not the project; an exhausted programme
converts to something smaller rather than to nothing; a drawdown pauses rather than stops. Only one
trigger stops the build, and it is a **time box**, not an outcome.

## 5. The time box (owner, 2026-08-01)

**2 months from G0 close to reach G5 — the walking skeleton green in CI. Not to reach Track A.**

This is the right shape, and the reasoning is worth keeping: **Track A contains its own 4-week
clock.** `a.run_completes` requires 20 consecutive trading days of the system running, which is a
calendar month *after* it works. Timeboxing Track A therefore mixes two different questions — *can
this be built?* and *is it stable?* — and a schedule miss on the first would trip a kill criterion
meant for the second.

So G5 is boxed, and the Track A box is set afterwards from **measured throughput** rather than
guessed at now (`k.timebox_review`).

**That afterwards is now: §5a.**

At the owner's stated capacity of ~40 h/week, 2 months is ~**350 working hours**. That is generous
for one vertical slice, which means the real risk is not the clock — it is scope drifting into the
~460-component catalogue. The activation gate exists for exactly this: components may sit at
`registered` indefinitely at no cost, and only reach `active` deliberately.

## 5a. The Track A time box — ratified 2026-08-08

`k.timebox_review` fired when G5 closed on 2026-08-02 and required the Track A box to be set **from
measured throughput** and issued as v1.1.0. This is that amendment. It adds `k.track_a_timebox` and
edits nothing: v1.0.0 stays on record exactly as ratified.

**Ratified: 120 calendar days from the first scheduled daily run — or 180 calendar days from
ratification if no run is ever scheduled** — covering only Track A's four run-measurable criteria.

**What was measured.** First commit 2026-08-01; walking skeleton running end to end 2026-08-02.
**G5 took one day against a two-month box.** So the build side is not the constraint and boxing it
again would box the wrong thing — which is the first finding this amendment owes to §5's own
reasoning.

**What cannot be compressed.** `a.run_completes` requires 20 **consecutive** trading days — about 28
calendar days — and *consecutive* is the operative word: one missed session restarts the window.
Throughput cannot shorten that by a single day. 120 days allows **three full attempts** plus roughly
five weeks to diagnose and fix between them.

| Alternative | Why not |
|---|---|
| 60 days | two attempts. The first free-tier outage puts the box on a knife edge and converts a data gap into a kill trigger — precisely the mix-up §5 warns about |
| 180 days | three failures already answer the question; past that the box stops discriminating and becomes a formality |
| from the ratification date | the clock would run before the thing it measures can start. That is the mistake `k.project_timebox` made in the other direction, and it was reached in a day |

### The second clause, and why the first one alone was a defect

The draft had one clause: 120 days from the first scheduled daily run. On the same day it was
drafted, the owner **deferred scheduling that run** with the survivorship loss accepted. Those two
decisions together produce a criterion that can never fire.

That is the `REQ-VALIDATION-001` shape — a gate whose verdict is invariant across every input — and
gate 3g cannot catch this one, because the trigger references no parameter. It would have been the
second inert criterion in a ratified file, drafted by the process that exists to prevent the first.

So the ratified version has a second clause: **180 days from ratification if no run is ever
scheduled.** A kill criterion that can be evaded by inaction is not a kill criterion, and the two
expiries mean different things:

| Expired with | Finding | Action |
|---|---|---|
| a run scheduled | the daily run cannot be made reliable on this data source | stop; re-open D10, the data-tier decision |
| **no run ever scheduled** | the system is not being operated at all | restate the project as documentation-and-research only, and stop maintaining a live contour nothing uses |

The second row is the uncomfortable one and it is the reason the clause is worth having. Deferring
the schedule is a legitimate owner decision — it was taken deliberately, with the cost known. What
it must not do is quietly become permanent while a kill criterion sits in a ratified file looking
like protection.

~~**The 180-day clock is running from 2026-08-08.** The 120-day clock has not started.~~

**CORRECTED 2026-08-15.** The 120-day clock started 2026-08-09, the first scheduled daily run
(`data/daily_run.log`, verified against `git log`; the run's first scheduled attempt failed on
batteries the next day, commit `664e84a` — a data-tier gap, not a scheduling one, and not what this
clock measures). The 180-day fallback above never engaged and is now moot. Full evidence in
`registry/criteria.yml` v1.1.1. The struck line is not deleted: it was true when it was written, on
what was then known, and this file corrects forward rather than silently rewriting (`AGENTS.md`
§10.5).

**Three Track A criteria sit outside the box**: process compliance core and overall, and no critical
violations. All three require *taken trades*, whose pace is the owner's trading cadence rather than
the project's throughput. Boxing them would put a kill criterion on the owner's discretion, which is
not what a time box is for.

## 6. Ratification record

| Date | Event |
|---|---|
| 2026-08-01 | Two-track structure adopted by the owner; values drafted here for ratification |
| 2026-08-01 | `k.project_timebox` (2 months → G5) and `k.timebox_review` set by the owner |
| **2026-08-02** | **All remaining Track A and Track B values ratified. `criteria.yml` v1.0.0 frozen. G0 closed.** |
| **2026-08-08** | **`k.track_a_timebox` ratified** and issued as `criteria.yml` v1.1.0, with an inaction clause added to the draft (§5a). `k.timebox_review` fired at G5 on 2026-08-02, sat unactioned for six days, and is now `met` |
| 2026-08-08 | Owner deferred scheduling the daily run, survivorship loss accepted. Recorded here because it is what makes §5a's second clause load-bearing rather than decorative |

One value was deliberately **absent rather than unset**: the Track A time box, scheduled by
`k.timebox_review` to be added at G5 from measured throughput as v1.1.0. It is now set and ratified
(§5a). That was an amendment, not an edit — v1.0.0 stays on record.

## 7. Standing rules

1. Criteria are frozen before the run that tests them.
2. Editing after seeing a result creates a new version and voids the claim — §3.7 at project level.
3. Both branches written in advance; a criterion with only a success branch is a hope.
4. Everything net of costs — commission, spread, slippage, borrow, FX.
5. A negative result is a result. Reaching `Rejected` honestly is a success of the process,
   whatever it means for the strategy.
