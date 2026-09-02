# DR-031: The fill records itself, and the stop comes from our journal rather than the venue

```
date:            2026-09-02
status:          accepted — owner instruction 2026-09-02, inside CHARTER A-002's scope
parameters:      none. Every value written is either the venue's observation or a number this
                 system already decided and journalled; the one computed field is DR-010's
                 existing cost model, called rather than re-derived
components:      none new
implemented_by:  src/swingdesk/trade_management/adoption.py :: def adopt
                 the command is src/swingdesk/presentation/cli.py :: def _sync_fills, and the join
                 it trusts is
                 src/swingdesk/journal_evidence/journal.py :: def latest_sent_submission
built:           2026-09-02
```

## 1. What this is downstream of, and the sentence it has to answer

`DR-027` §11 stops submission whenever the venue holds something this system's book does not carry.
That guard is right and it made the machine one that **ran once**: `positions.duckdb` is written
only by `open-position` and `respond`, both commands a person runs, so the first evening that
anything filled, every later evening stopped.

The owner's instruction on 2026-09-02 was to automate what can be automated and get the console
product to something end-to-end. This is the step that was a person.

**`DR-026` refused exactly this, and the refusal must be answered rather than stepped around.** It
recorded that a broker's answer cannot construct a `Position` **because the venue does not know the
stop**. That is a true statement about a book somebody else opened.

**It is not true of an entry this system placed.** `DR-027` §3.2 submits the stop as a bracket leg,
and §8 writes it into `journal.duckdb` *before* the order goes. So the stop is not read back from
the venue at all — it is read from **our own record of what we decided**, which is a strictly
better source than the venue's echo of it. `DR-026`'s premise is gone for this one path, and stands
everywhere else: a holding that traces to no order of ours is still not adoptable, and §4 is that
rule.

## 2. The split of authority, which runs one way each

| field | whose | why |
|---|---|---|
| `entry_price` | the **venue's** | what actually filled, averaged by the party that filled it |
| `shares` | the **venue's** | ditto, and partial fills are already summed into it |
| `initial_stop`, `current_stop` | **ours**, from `submissions` | a stop is a decision frozen at entry (`RISK_SPEC` §2), not an observation |
| `initial_costs_per_share` | **ours**, from `DR-010` | the venue does not charge what the model charges, and the model is what every `R` is computed with |
| `opened_on` | the **venue's** | the session the FILL happened in, never the one that decided it |
| `knowledge_time` | **ours** | when we learned it. The bitemporal split `open-position` keeps by hand |
| `strategy` | **ours** | `CARD-001`. A position tagged `unspecified` cannot be grouped with the trades that validate the card it came from |

**`current_stop` starts where `initial_stop` is** because `D6` governs every move after that and no
move has happened yet. Nothing here proposes, approves or applies a management action.

## 3. What it will not adopt, and this list is the substance

A function that turned every holding into a position would write numbers into the book that every
downstream `R` is computed from — and `b.min_sample` counts that book toward `Validated`. So:

| refused | why |
|---|---|
| a holding that traces to **no `sent` submission** | somebody traded by hand. §4 |
| a holding traced only to a `stopped`, `refused` or `rejected` row | that attempt never reached the venue, so no holding can have come from it — and adopting would write a stop that was never live |
| a **short** | every stop validator in `contracts.position` requires the stop below entry; this system cannot describe one |
| a **fractional** holding | `Position.shares` is a whole number, and rounding to record it would make the two books disagree by design |
| a fill **at or below the stop we sent** | the position is already past its exit at the moment it is recorded. Its `R` denominator would be zero or negative, and `R` is what the whole validation programme is denominated in. A person, not a record |
| a holding with **no fill in the activities feed** | `opened_on` is what every holding-period rule counts from, and it is never taken from a clock |
| an **unset cost parameter** | fail closed, exactly as `sizing` and `open-position` do: `costs` sits inside `entry - stop + costs`, so a guess flatters every statistic that follows |

## 4. A holding we cannot trace is NOT ours, and it stays that way

The single most dangerous thing this command could do is decide that anything at the venue must
have been ours. It does not: with no matching `sent` submission the holding is reported, **not
recorded**, the command exits `3`, and `DR-027` §11's guard goes on pausing new entries until a
person records it with `open-position` or closes it at the venue.

That is the course's `TECH` — *"Broker/platform/journal mismatch"*, action *"Pause new entries"* —
reaching the one place it can actually be acted on automatically, and stopping there.

## 5. Where it runs, and why the order is load-bearing

**Before the scan, in the same scheduled pass.** The caps `DR-027` §10 applies are measured against
the book, so the book has to describe what is actually held *before* the run reads it. Running the
sync after the scan would measure tonight's caps against last night's book, which is `DR-023`'s
mistake in a more expensive place.

**It never fails the run.** Exit `3` in particular is not a failure: it means a person is needed,
and the scan still decides and still reports while `DR-027` §11 stops the submission by itself.
The wrapper does not second-guess the guard.

**It writes the book and never the venue.** Two GETs, no write verb, gate 39 untouched. `D1` is
unaffected: this records a fill that has already happened, which is precisely what `open-position`
does — with the typing done from our own record instead of by an operator at 18:35.

## 6. What this does NOT do

- **It does not close positions.** An exit is `D6`'s and the exit card does not exist yet; a
  holding that leaves the venue is a divergence `broker` reports and a person resolves.
- **It does not move a stop.** `AI_AUTHORITY_MODEL` §3's MANAGEMENT vocabulary is untouched.
- **It does not make anything validated.** `CARD-001` is still `Untested` and `DR-030` §3.1 still
  registers in advance that it is expected to fail `b.expectancy`. This makes the trade log
  *accumulate without a person*; it says nothing about what the log will show.

## 7. What would overturn this

- **A venue that reports a holding this system placed but cannot echo the order id.** The join is
  `instrument_id` against a `sent` submission, which is unambiguous only because `DR-027` §5 allows
  one submission per instrument per session. A venue permitting several would need the order id
  carried through the fills feed instead.
- **Real money at the venue.** Then `CHARTER` A-002 no longer applies, `DR-027` is void, and a
  position recorded without a human reading the confirmation is exactly what `D1` forbids.
- **A second account on the same key pair.** §4 currently treats every untraceable holding as
  somebody trading by hand, which is the conservative reading and would become noise.
