# DR-027: What the system may submit to the paper venue, and the four things that stop it

```
date:            2026-09-01
status:          accepted — authorised by CHARTER A-002, ruled by the owner 2026-09-01
parameters:      none. Every choice below is a definition or a structural guard, not a threshold.
                 The one thing that looks like a threshold - the limit price - is deliberately the
                 sizing price itself and therefore introduces no new number (§3.1)
components:      none new
implemented_by:  src/swingdesk/broker/submit.py :: def entry_order
                 the wire call is AlpacaClient.submit, gated by AlpacaClient.guards; the four
                 guards live in registry/broker_policy.yml, src/swingdesk/broker/armed.py and
                 tools/verify_broker_policy.py (gate 39)
built:           2026-09-01
```

## 1. What this is downstream of

`DR-026` read `D1`'s *"order"* as one that moves real money and recorded that three constraints
survived that reading, because their stated reason was never capital. The owner was asked the
question those three left open — *"may the system submit a paper order that no human approved
order-by-order?"* — and answered **yes** on 2026-09-01. `CHARTER` A-002 is that amendment.

This record is the *what and how*. A-002 authorises; nothing here re-argues it.

**The read path was proven against the live paper venue on 2026-09-01**, before any of this was
built: `swingdesk broker` returned an `ACTIVE` USD account, $100,000 equity, zero positions, and a
reconciliation that agreed with an empty book. Every field parsed on the first attempt. So the
write path is built on a boundary that has been exercised rather than only tested against fixtures.

## 2. What may be submitted, and nothing else

**One shape of order: an ENTRY for a candidate this run decided `Trade`, sized by `sizing`.**

The input is an `InstrumentOutcome` whose `decision.decision` is `Trade` and whose `risk` is a
`RiskSnapshot` rather than a `Refusal`. Everything else the run produced is not submittable, and
that is a list rather than an omission:

| Not submitted | Why |
|---|---|
| `Watch`, `Skip`, `Pause` | not a decision to trade |
| a `Trade` whose sizing refused | there is no share count and no stop. `sizing` refusing is the fail-closed design working |
| management actions on open positions | `D6` governs stop moves and partial exits and A-002 §4 leaves it standing |
| anything short | every stop validator in `contracts.position` requires the stop below entry; this system cannot describe a short |
| anything fractional | `Position.shares` is a whole number, and rounding to record it would make the two books disagree by design |

## 3. The order

**BUY, limit at the sizing price, `time_in_force: day`, `order_class: bracket` with a stop-loss leg
at the sized stop, quantity in whole shares.** Each half of that is load-bearing.

### 3.1 A LIMIT at exactly the price the sizing used — which is why this record sets no parameter

A market order fills wherever the book is. Every `R` a position reports is denominated in
`entry - stop + costs` (`RISK_SPEC.md` §2), frozen at entry — so a fill above the price the sizing
was computed against makes the reported `R` a fiction in the flattering direction, permanently, on
the one statistic the whole validation programme is measured in.

**A limit at the sizing price is also the `CHASE` and `LATE` controls by construction.** Appendix N
gives `LATE` as *"Price beyond maximum entry — no chase; wait new setup"*, and Appendix O gives
`CHASE` as *"Entry beyond maximum"*. `entry.maximum_entry_atr` is `unset` and this record does not
set it. It does not need to: **an order that can only fill at the decision price cannot chase.**
If the market has moved, the order does not fill, and not filling is the correct outcome rather
than a missed one.

### 3.2 A BRACKET, because a stop the market cannot see is not a stop

`DR-026` §4.6 named this. A stop held only in `positions.duckdb` protects nothing between runs: the
system does not watch the tape, and the course's own `LATE_EXIT` error is *"ignoring the exit
rule"* with the control given as *"alerts/bracket/manual fallback"*. The stop leg is submitted with
the entry so the protection exists at the venue from the moment the fill does.

**And it closes the loop that read-only could not.** `DR-026` recorded that a broker's answer cannot
construct a `Position` because the venue does not know the stop. When *this system* placed the
bracket, the venue does know it — the stop leg is readable from `/v2/orders` — so a filled entry
carries everything a `Position` needs.

### 3.3 `time_in_force: day`

An order that outlives the session outlives the analysis that produced it. `DR-015` fixed two
sessions as too stale to decide on; an order resting overnight decides on data older than that
every morning it is still open. `day` makes the decision expire with the day it was made in.

## 4. The four things that stop it, and they are independent

Any one of them alone stops submission. That is deliberate: `FAIL_CLOSED_POLICY.md` §3 forbids a
score clearing a critical gate, and four guards that could compensate for each other would be one
guard with three decorations.

1. **The host allowlist.** One https host, the live venue named under `forbidden_hosts` and compared
   as a hostname. A brokerage account object carries no paper/live flag, so this is the whole
   boundary — and A-002 §3 says so in the charter, where a future reader weakening it will see what
   they are weakening.
2. **The kill switch, which defaults to STOPPED.** A file the owner creates. Absent means stopped;
   unreadable means stopped; present and empty means stopped. Only an explicit armed marker permits
   submission. **A switch that defaults to on is not a kill switch**, and one that fails open is
   the `unavailable`-admits-unchecked inversion this project has already paid for once (`DR-025`
   §2.1).
3. **`access.write_enabled` in the committed policy.** Changing it is a commit a reviewer sees,
   which is `DR-008`'s *new human decision* applied to the highest-consequence surface here.
4. **One chokepoint in the code, checked by gate 39.** Every write goes through `alpaca._write`,
   which consults 1, 2 and 3 before a socket is opened. No HTTP write verb may appear anywhere else
   in `swingdesk/broker/`, read from the syntax tree.

## 5. Idempotency, which is the property a retry would otherwise destroy

**Every order carries a `client_order_id` derived deterministically from the session date and the
instrument**, never from the run id and never from a clock:

```
swingdesk-<session_date>-<instrument_id>
```

The venue rejects a duplicate, so a second submission for the same instrument on the same session
is refused **by the venue** rather than by our bookkeeping. That is the right place for it: a local
guard fails exactly when the local state is what went wrong.

**The session date and not the run id, deliberately.** A run id is unique per run, so a retried
evening pass — which `DR-015` explicitly provides for — would carry a new one and submit the same
entry twice. The decision is a decision about a *session*; the id says so.

**No new store table, and that is the point of the package.** Idempotency is enforced by the venue,
the stop is readable from the bracket's stop leg, and the fill is readable from the activities feed.
Everything a local `submissions` table would hold is already held by the party that actually knows.

## 6. What is recorded — and the one thing that is NOT, which gates arming

Every submission, every refusal and every stopped guard is **reported on the run's output** with its
reason, including the count of eligible `Trade` decisions when the switch was stopped. That last one
matters: a line printed only when armed would hide the difference between a run that had nothing to
submit and a run that was stopped from submitting something.

**It is not yet written to the append-only journal, and that is stated here rather than implied.**
`journal.duckdb` holds runs and decisions; a submission is neither, and giving it a table is a
schema migration rather than a line of code. Until it has one, an attempt exists only in a console
buffer — and `SECURITY.md` §4's rule for the approval channel is that *an action with no record did
not happen*. The `REVENGE` and `HINDSIGHT` controls both depend on the ATTEMPT being recorded, not
the result.

> **Standing condition: the switch is not armed until submissions are journalled.** This is a
> condition on arming and not on merging, because nothing can be submitted while the switch is
> absent — which it is, and which is its default. `TODO.md` carries the migration.

**A `Position` is still created from the FILL, never from the submission.** An accepted order is not
a position; `leaves_qty` exists because partial fills do. Nothing in this record changes that a
position is a thing that happened.

## 7. What would overturn this

- **Real money reaching the venue by any route.** Then A-002 §2 governs and this record is void
  until a human approves each order. The route no gate can see is a live key pair in the
  environment the policy names — a key is a value, and this repository never holds one.
- **A fill materially away from the limit price.** That would mean the venue is not honouring the
  limit, and §3.1's whole argument rests on it. `broker.reconcile` already reports an
  `entry_price` divergence; on this path it is a stop-submitting condition, not a note.
- **The owner arming the switch and finding the machinery submits something it should not.** The
  switch is a file for exactly this reason: the remedy is deleting it, not a release.

---

## 8. Amendment, 2026-09-01 — §6's standing condition is discharged

**Appended rather than edited.** §6 was accurate when written and its second paragraph is now
history; `AGENTS.md` §11 corrects a ratified record forward, and §12's rot trap is a *cited* fact
changing while the citation stands. So this is what changed, and §6 stays as it was.

**Submissions are journalled.** `journal.duckdb` grew a `submissions` table — twelve columns, keyed
`(run_id, client_order_id)` — and `scan --submit` writes one row per eligible candidate before and
after the wire, with a coded outcome from `SUBMISSION_OUTCOMES`: `sent`, `stopped`, `refused`,
`rejected`.

Three things about it are decisions rather than plumbing:

1. **A stopped attempt gets a row, and that is most of the value.** A session on which the machine
   would have entered three names and was stopped is otherwise indistinguishable from a session on
   which it found nothing. Only the row tells them apart, and it carries the guard's own reason.
2. **`(run_id, client_order_id)` and not the order id alone.** The id is derived from the session
   and the instrument (§5), so a run the switch stopped and a later run the owner armed share one —
   and both attempts are facts. Append-only, like everything else in that store.
3. **`Submission` refuses to exist without its explanation.** A `sent` row must carry the venue's
   order id, or it asserts something happened at the venue that nothing can trace back; every other
   outcome must carry a reason, because an attempt recorded without why it failed is the sentence
   `AGENTS.md` §10.4 is about, stored.

**And the migration was proven rather than assumed.** `Journal.__init__` already reconciles its
schema at open (`platform/schema.py`, the defect that cost four trading days), so an existing
journal grows the table on the next open. That was checked by copying the live
`journal.duckdb` — 33 runs and 23,819 decisions — opening the **copy**, and confirming both counts
survived and all twelve columns appeared. The live store was not touched.

**What this does NOT change.** The switch is still absent, which is still its default, so nothing
has been submitted. §6's condition was the blocker on *arming*; arming remains the owner's act.
