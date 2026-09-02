# DR-027: What the system may submit to the paper venue, and the four things that stop it

```
date:            2026-09-01
status:          accepted — authorised by CHARTER A-002, ruled by the owner 2026-09-01
parameters:      none. Every choice below is a definition or a structural guard, not a threshold.
                 The one thing that looks like a threshold - the limit price - is deliberately the
                 sizing price itself and therefore introduces no new number (§3.1)
components:      none new
implemented_by:  src/swingdesk/broker/submit.py :: def entry_order
                 the ratified caps bind across one run's own output through
                 src/swingdesk/trade_management/portfolio.py :: def allocate, called by
                 src/swingdesk/presentation/cli.py :: def _allocate (§10)
                 the venue is asked what it already holds before anything is added by
                 src/swingdesk/broker/reconcile.py :: def uncommitted_exposure, read through
                 src/swingdesk/broker/alpaca.py :: def open_orders (§11)
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

---

## 9. Amendment, 2026-09-01 — two defects a real order found, and a target that is now mandatory

**Appended, not edited.** §3.2 and §5 were written from the API reference and were wrong in ways
only the venue could say. A probe placed one deliberately unfillable order and both surfaced in the
first attempt, which is the whole argument for probing before depending on something.

### 9.1 A bracket is a chain of THREE, and the target is now mandatory anyway

§3.2 specified a bracket carrying a stop leg only. The venue refused it:

> `bracket orders require take_profit.limit_price`

`oto` would have taken a single leg — and in the same hour the owner ruled that **a target is
mandatory, and not only for paper**: a trade is carried from discovery to close and then observed,
so that the research data comes from a **completed** trade rather than from one that ran out of
time. So `bracket` is right for a reason better than the wire format, and the take-profit leg is
`exit.target_r_multiple` R above the entry.

**The form is the course's and the value is the owner's, exactly as the stop multiple was.**
`M53-T0807`, `T0808` and `T0809` are *"exit at 1R"*, *"exit at 2R"* and *"exit at 3R"* — three
Definitions, no ruling between them. **The parameter is `unset` and therefore nothing can be
submitted at all**, which is the fail-closed design rather than a gap: inventing a target to satisfy
a wire format would be authoring a threshold (`AGENTS.md` §8).

In R rather than percent or ATR, because R is what the validation programme is denominated in and it
is already volatility-normalised — `entry - stop + costs`, frozen at entry (`RISK_SPEC.md` §2). A
percentage target would be 0.5R on a volatile name and 3R on a quiet one.

### 9.2 The session is the exchange's, never a clock's date — and this one was nearly invisible

§5 keys idempotency on "the session date" and the code read `now.date()`. The probe ran at about
**19:57 New York** on 1 September and the derived key said **`2026-09-02`**.

**That breaks the property in exactly the case it exists for.** `DR-015` provides for a retried
evening pass at 19:30. The 18:30 pass and the retry straddle midnight UTC on **every ordinary
evening**, so the two would carry different ids for one decision and the venue would accept both —
the same entry, submitted twice, on the one mechanism that was supposed to make that impossible.

`broker.submit.trading_session` now resolves it through the exchange calendar
(`last_completed_session`), which has no such seam: both passes land on the session that closed at
16:00 local. Re-run after the fix, the key read `swingdesk-2026-09-01-SPY`.

**Nothing would have caught this.** Every test passed, both before and after; a fixture clock does
not straddle midnight unless somebody thought to make it, and nobody had. It took an order.

### 9.3 What the probe established, and what it did not

The venue **accepted** a full bracket through the production path — `entry_order` built it,
`AlpacaClient.submit` sent it, `guards` let it through, and the journal recorded it under a `probe-`
run id. Order `1a44d118-59f3-428f-83e7-47cc09bd3e98`, status `accepted`, 0 of 1 filled.

It establishes that the write path works. It establishes **nothing** about the strategy: the limit
was far below the market on purpose, so the order could not fill, and no position was acquired. The
switch was disarmed immediately afterwards and is absent again, which is its default.

---

## 10. Amendment, 2026-09-02 — the four guards do not count, and the caps were never applied to a run

**Appended, not edited.** §4's four guards were correct and are unchanged. They answer *may this
system write to this venue at all*, and they answered it correctly on the first evening somebody
tried to arm the switch. They do not answer **how many**, and nothing else did either.

### 10.1 What an armed run would have submitted, measured

Run `run-20260902T143239Z-b908f635`, full universe, 2026-09-02:

| | ratified | what `--submit` would have sent |
|---|---|---|
| positions | **4** (`risk.max_concurrent_positions`) | **114** |
| open risk | **4R** (`risk.max_open_risk`) | **103.5R** |
| sector | **2R** (`risk.max_sector_risk`) | technology **41.0R**; eight of eleven sectors over |
| notional | — | **$153,040** against an `account.equity` of **$10,000** |

**The venue would have accepted every one of them.** The paper account holds $100,000 of equity and
$399,899.99 of buying power against a book modelled on $10,000, so nothing bounces — the one place
this could have failed loudly is ten times too large to notice. And `access.allowed_methods` carries
no `DELETE` by the deliberate choice §3.3 argues, so 114 accepted brackets could not have been
recalled through this software at all.

### 10.2 The seam, and every piece of it was correct on its own

Three files, no bug in any of them:

1. **`trade_management/portfolio.py`** measures each candidate against the OPEN BOOK alone, by
   owner ruling 2026-08-22, because *a `Watch` is not a position and consumes no capacity*.
2. **`application/pipeline.py`** prices that book **once** before the candidate loop and never
   grows it, so all 114 were judged against the same empty book and each one honestly reported
   *"heaviest sector after this candidate is technology at 0.98R of the 2R allowed"*.
3. **`decision_logic/selection.py`** takes the top decile and says in its own docstring that *"the
   ratified book cap is what decides how many are actually taken anyway"* — which `DR-030` §2.4
   states as the model: the cutoff picks **eligibility**, the caps pick **what is taken**.

Every one of those was true while the terminal state was `Watch` and a human applied the caps by
choosing four names off a report. `CARD-001` emitting `Trade` straight to `--submit` removed the
human without moving the cap, and the sentence *"the ratified caps pick which are taken"* became a
claim about a step that did not exist.

### 10.3 Why no gate and no test caught it

Worth stating, because the answer is not "somebody was careless":

- **The four guards are boundary guards.** Gate 39 reads the syntax tree for write verbs and hosts.
  A cap on quantity is invisible to every one of them, and correctly so.
- **Every submit test carried exactly ONE `Trade` decision.** The question *do they fit together*
  could not be asked of a fixture with one candidate. A fixture with one is not a small version of
  a fixture with many — the same lesson `daily_run.cmd`'s log-rotation comment already records.
- **The probe (§9) submitted one deliberately unfillable order.** It proved the wire and could not
  have surfaced this: one order is inside every cap.

### 10.4 What changed

**`portfolio.allocate` walks a RANKED cross-section and grows the book as it takes names**, so the
three ratified caps bind across one run's own output. Nothing about a cap is re-implemented: it
re-enters `assess` and `assess_sector` with a grown book, because specification §8 forbids one logic
in two places and a second copy of *"count + 1 > max_concurrent"* is how the report and the
decisions drifted apart once already.

**The order is `CARD-001`'s ranking and nothing else.** `ALLOCATION_SPEC` §6 rule 4 forbids falling
back to the order the system happens to hold, so a run whose screen produced no `Selection` is
**not allocated at all** — it submits nothing rather than the first four alphabetically. This is
also why the module docstring's *"it does not allocate between candidates"* is struck rather than
deleted: that ruling's stated premise was `rs.ranking_method` being `unset`, and `DR-030` ruled it
`descending` on 2026-09-01. The premise is gone; the rule it cites still governs.

**Every branch that cannot measure a cap STOPS.** A book that was never priced, a sector split that
refused, a cap with no value, a `Trade` that reached the wire with no sector verdict: each is
`unavailable`, and `unavailable` here means stopped. `DR-025` §2.1 records this project shipping a
guard whose refusal ADMITTED the candidate — *fail closed* read correct and behaved backwards. At a
venue that inversion is paid for in orders, so each of the four is asserted separately by
`test_submission_stops_when_a_cap_could_not_be_measured` rather than trusted to one branch.

**A candidate the caps pass over is journalled `stopped`, with the cap's own reason and the
parameter that bound.** §8.1's argument applied one level down: a session on which the machine would
have entered 114 names and took 4 is otherwise indistinguishable from one on which it found 4.

### 10.5 What this does NOT change

**No decision moves.** `Trade` still means *eligible*, exactly as `DR-030` §2.4 defines it; the
funnel still reports 114; `output_hash` is untouched and the per-candidate verdicts in `pipeline`
are byte-identical. The cap is applied in the submission path, which is where `DR-030` already said
it was applied. Nothing here re-opens what the screen selects.

**This authors no threshold.** All three numbers are ratified `owner` parameters that already had
consumers (`DR-006` §8.3, 2026-08-22), and the ordering is `DR-030`'s. `AGENTS.md` §8 is satisfied
because nothing new was chosen — three existing numbers were connected to a path that was ignoring
them.

**The switch is still absent, which is still its default.** Nothing has been submitted by a run.
This amendment removes a reason not to arm; it is not an arming.

### 10.6 What would overturn this

- **A run whose selection is not a ranking.** `allocate` must be given a ratified order or nothing;
  a future screen that returns an unordered set makes this refuse, which is correct and will look
  like a regression to whoever writes it.
- **The book cap ceasing to be the binding constraint.** At 4 slots against a ~114-name eligible
  set, which of the two caps binds is never in doubt. If `risk.max_concurrent_positions` rises far
  enough that sector concentration decides most sessions, the ordering question `DR-030` answered
  for *eligibility* has to be re-asked for *allocation* — they are not the same question, and this
  record borrows the answer to one for the other because at four slots the difference cannot show.

---

## 11. Amendment, 2026-09-02 — §10 bounded a run against itself; nothing bounded it against yesterday

**Appended, not edited.** §10 is correct and unchanged. It makes the three ratified caps bind
across **one run's own output**, which is the question it was written for. It leaves a second one
open, and the second one compounds.

### 11.1 The book the caps are measured against is written only by a person

`portfolio.book` is built from `positions.duckdb`. Every writer to that store is a command a human
runs — `open-position` and `respond`, and those two only; grep is the whole proof. **The submission
path does not write a position, deliberately**: §6 keeps a `Position` a thing created from the
*fill*, and an accepted order is not a fill.

So the sequence is:

| evening | book says | venue actually holds | submitted |
|---|---|---|---|
| 1 | 0 open | 0 | **4** |
| 2 | 0 open — nobody recorded the fills | 4 | **4 more** |
| 3 | 0 open | 8 | **4 more** |

Four a night, for ever, against a cap of four in total. It is §10's defect one level up and slower,
and slower is worse: §10's would have been obvious on the first evening, and this one looks
completely normal until the account is twenty names deep.

**The `client_order_id` does not save it.** §5's idempotency is keyed on the *session*, so it stops
a repeat submission of the same name **within** one session — a retried evening pass, which is what
it was built for. Consecutive sessions derive different keys by design, because they are different
decisions. Nothing about it was wrong; it was answering a different question.

### 11.2 What changed

**Before adding, the venue is asked what it already holds.** `uncommitted_exposure` compares the
venue's positions **and its live orders** against the book, and any symbol the venue is exposed to
that the book does not carry stops submission entirely.

**`TECH`, and it is not invented here.** Appendix N already carries *"Broker/platform/journal
mismatch"* with the prescribed action *"Pause new entries"*. `DR-027` §7 already ruled that on this
path a divergence is a stop-submitting condition rather than a note. This implements a ruling that
existed and had no code.

**An unfilled order counts, and that is the half that is easy to miss.** A resting bracket is not a
position and never will be if it does not fill — but until the venue says which, the name is spoken
for. A guard counting only filled positions would let the same name be entered on two consecutive
evenings, which is the exact failure it exists to stop.

**Two GETs, and gate 39 stays absolute.** `AlpacaClient.open_orders` reads `/v2/orders?status=open`.
No write verb is added anywhere; `access.allowed_methods` is untouched.

**After the arming check, never before.** `AlpacaClient.guards` puts arming first on purpose: a
refusal reporting *the venue is unreachable* when the truth is *the owner never armed it* sends
somebody to debug a network at 18:31. A disarmed run therefore costs no request at all, and a test
asserts it by giving the stub a venue that raises on every read.

**Unavailable is stopped**, on all three of its causes — no position store, a venue that could not
be read, a divergence. A venue whose holdings are unknown is not a venue to add to.

### 11.3 What clears it

Recording the fills. `open-position` for each one puts the book and the venue back in agreement,
and then §10's caps do the rest — with four recorded positions, the next run's `assess` admits
nobody and submits nothing, which is the ratified cap working rather than a guard firing.

**This is deliberately not automatic.** Constructing a `Position` from the venue's answer is what
`DR-026` refused, and §3.2's observation that a bracket makes the stop readable narrows that
argument without closing it — a fill price, a costs figure and a strategy tag are still ours to
state. Automating it is a decision record, and `TODO.md` carries it. Until then the guard is what
makes the omission loud instead of expensive.

### 11.4 It caught something on its first real read, and the something was ours

**Exercised against the live paper venue on 2026-09-02, before this was merged**, in the same
spirit as §1: two GETs, no write. The venue reported **zero positions and ONE live order** —

```
order_id       : 1a44d118-59f3-428f-83e7-47cc09bd3e98
client_order_id: swingdesk-2026-09-01-SPY
symbol/status  : SPY / new
```

— which is **§9.3's probe order, still working**. §9.3 says *"The switch was disarmed immediately
afterwards and is absent again"*, and that sentence is true about the switch and silent about the
order. It was submitted after the close on 1 September, queued, and released by the venue at the
next session open; `filled_shares` is 0 because the limit was put far below the market on purpose,
which is the one thing about it that went to plan.

So the first thing this guard ever did on real data was refuse to add to a book that already had
something in it that nobody had recorded — which is the whole thesis, demonstrated by the record
that introduced it.

**And the remedy is the one this system deliberately cannot perform.** §3.3 gives every order
`time_in_force: day` and `access.allowed_methods` therefore carries no `DELETE`, so SwingDesk cannot
cancel it: it expires at the close, or a human cancels it in the venue's own dashboard. That is the
`DELETE`-is-absent decision meeting its first real consequence, and it is being recorded rather than
quietly reversed — an order the machine cannot recall is exactly why the machine is bounded on how
many it may place.

### 11.5 What would overturn this

- **Positions recorded from fills automatically.** Then this guard should stop firing in normal
  operation and becomes a check on the automation rather than on the operator. It should not be
  deleted at that point — it is the thing that catches the automation failing.
- **A second account on the same key pair.** `uncommitted_exposure` reads one account's holdings
  and assumes every symbol at the venue is this system's business. A venue position opened by hand
  in the dashboard correctly stops submission today, which is the conservative reading and may
  become an irritation before it becomes wrong.
