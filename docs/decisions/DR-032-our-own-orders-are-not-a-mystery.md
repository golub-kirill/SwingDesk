# DR-032: An order we sent is the exposure we know best, not the one we know least

```
date:            2026-09-02
status:          accepted — owner instruction 2026-09-02, inside CHARTER A-002's scope
parameters:      none. The two caps this consults are `risk.max_concurrent_positions` and
                 `risk.max_open_risk`, both ratified by DR-006 §8.3, and the R it prices a
                 resting order at calls DR-010's existing cost model
components:      none new
implemented_by:  src/swingdesk/broker/reconcile.py :: def ours
                 the capacity half is
                 src/swingdesk/presentation/cli.py :: def _committed_by_live_orders, and the
                 journal reads it trusts are
                 src/swingdesk/journal_evidence/journal.py :: def sent_client_order_ids
built:           2026-09-02
```

## 1. How this was found, and it was a question rather than a failure

The owner asked to run the pass again *"and check how the duplicate protection works"*. Answering
that meant reading the interaction rather than the intent, and the interaction was this:

1. The 18:30 pass submits four orders. They rest at the venue, unfilled.
2. The 19:30 pass runs. `sync-fills` records nothing — **an unfilled order is not a fill**.
3. `DR-027` §11 reads the venue, finds four live orders the book does not carry, reports `TECH`
   and stops everything.

Nothing was wrong with any of those three steps in isolation. Together they meant **`DR-015`'s
19:30 retry was dead from the moment the first pass submitted anything** — and a candidate that
failed on the first pass for a transient reason would never be retried, which is the entire purpose
`DR-015` §3 gives that pass.

**And the thing the owner asked about could never happen.** `DR-027` §5 keys idempotency on the
session so that a retry derives the same `client_order_id` and *the venue* refuses the duplicate.
§11 now stopped the run before a payload was ever built, so the venue's refusal — the mechanism §5
is entirely about — had become unreachable. It has never once been observed: the submissions table
holds exactly two rows in this system's history, one `sent` and one `rejected`, and the rejection
was `bracket orders require take_profit.limit_price`.

## 2. The distinction §11 was missing

§11 asks *is there exposure at the venue the caps were not measured against?* It answered by
symbol, and a symbol carries no history.

**An order this system sent an hour ago is not an unknown.** `DR-027` §8 journals every submission
**before the wire**, with its instrument, shares, limit and stop. That is a stronger record than
the venue's echo of it. Treating it as a mismatch inverts what the guard is for: it is the exposure
we can account for *best*.

**Ours is decided by the journal, never by the shape of an id.** `ours` tests membership of
`sent_client_order_ids()` — the set of ids this system actually put on the wire. A prefix test
against `swingdesk-` would adopt anything a person typed into the dashboard with the right first
word, which is precisely the holding §11 exists to catch. `outcome = 'sent'` only: a `stopped` or
`refused` attempt never reached the venue, so no order there can carry its id.

## 3. The obligation this creates, and it is the half that matters

**Exempting a resting order from the halt obliges the caps to count it.** Exempt it from both and
the 19:30 pass adds four more names on top of the four already resting — the accumulation failure
`DR-027` §10 and §11 both exist to prevent, one step subtler and one pass later.

So a live order of ours is offered to `portfolio.allocate` **ahead of every candidate**, shaped as
an `Allocatable`, and consumes its slot and its R through the same walk that takes a new name.
Seeding a `Book` by hand instead would be a second implementation of *how does an order consume a
slot*, and the two would agree until the day they did not (specification §8).

**Its R is priced from our own submission**, never from the venue: `shares`, `limit_price` and
`stop_price` are what we journalled, and the cost model is `DR-010`'s. That is `DR-031`'s split of
authority applied to a leg that has not filled — the venue knows an order is resting, and only we
know what it was sized against.

### 3.1 Only the part that has not filled

**A partial fill is otherwise charged twice against one name.** `sync-fills` records a `Position`
for the shares that filled and the book prices those; pricing the whole order again on top reads
**1.29R against a real 1R** on a 17-share order with 5 filled.

Over-counting is the safe direction — it refuses a legitimate candidate rather than admitting an
illegitimate one — and it is still the wrong number, so the resting quantity is
`ordered − filled`. `filled_shares` is the venue's and the ordered quantity is ours, which is §2's
split of authority applied one level down: **the venue knows what filled, we know what was asked.**

A fully filled entry that is still listed open is a bracket **leg**, not an entry with something
left to fill. It holds nothing here; the position it produced is in the book and is already
consuming the slot.

**A resting order we cannot price stops the run.** An unset cost parameter, a stop at or above the
limit, a submission that cannot be read: each means a slot is held whose size is unknown, and the
alternative — treating it as zero — is the `unavailable`-admits-unchecked inversion (`DR-025` §2.1)
in the one place it is paid for in orders.

## 3.1 Amendment, 2026-09-04 - a SELL commits nothing, and this counted it

**Appended, per `AGENTS.md` §11 rule 2.** §3 was right that a resting order of ours consumes a slot
and its R. It did not say *which* resting orders, because when it was written every order this
system could place was an entry. `DR-037` added one that is not.

**The measurement.** With three protective `oco`s standing, the pass reported:

```
book holds 3 position(s) at 2.43R; resting orders hold 5.22R more
PASS  0 within the caps, 101 passed over
```

The cap is 4R. The three protections alone held more than the whole of it, and the one candidate
that fit was refused.

**The arithmetic is not merely double-counting, it is a number that is not risk.** A protective
submission is journalled with the TARGET as its `limit_price` and the stop as its `stop_price`, so
`limit - stop + costs` reads the entire span between them - `70.03 - 61.70` for `AIS`, about 8.33 a
share against a real 1R of roughly 4.16. The position it protects is *already* counted, in the book,
at the right number.

**Read from the venue's own `side`.** Not from our id prefix: that is the shortcut §1 names, and it
would also miss a protective order placed by hand, which commits nothing either and for the same
reason. Exposure is created by an order that OPENS.

**Why the direction still matters.** Over-counting refuses a legitimate candidate rather than
admitting an illegitimate one, which is the safe way to be wrong. It is still wrong, and this
particular wrongness lasts as long as the protection does - which is the life of the position. **A
machine that stops trading the moment it protects itself has not been made safe.**

## 4. What moved in `_submit`, and why the order had to change

The allocation now depends on the venue, and the venue is read only after the arming check —
`AlpacaClient.guards`' own ordering, so a refusal saying *the venue is unreachable* never stands in
for *nobody armed it*. So the sequence is now:

```
arming ──► venue ──► what is already resting ──► the caps ──► submit
```

**A disarmed run allocates against the book alone** and says so. Nothing can be submitted on that
path, so the record is its whole purpose, and `DR-027` §6's argument still holds: a run that would
have entered six names and was stopped stays distinguishable from one that found four. The four it
would have taken are journalled against the *switch*; the two the caps passed over are journalled
against the *cap*. Two different facts, two different reasons, one row each.

## 5. What this does NOT change

- **An order we did not send still halts everything.** The exemption is membership of our own
  journal and nothing else, asserted separately by a test that gives the venue an id shaped exactly
  like ours and never recorded.
- **Idempotency is unchanged.** `DR-027` §5's key still derives from the session, and the venue is
  still the party that refuses a duplicate. What changed is that the refusal is now *reachable*.
- **Nothing about what may be submitted.** `DR-027` §2 is untouched.

## 6. What would overturn this

- **`sync-fills` recording positions from unfilled orders.** It does not and must not — `DR-027` §6
  keeps a `Position` a thing created from the fill — but a future path that did would make this
  bookkeeping run twice over the same exposure.
- **A venue that reuses client order ids across accounts.** `ours` would then admit somebody else's
  order. Alpaca scopes them per account; a venue that did not would need the account fingerprint in
  the test.
- **The first observed duplicate rejection.** `DR-027` §5's mechanism has still never fired. Until
  it does, the claim that the venue refuses a duplicate is read from an API reference rather than
  measured — the same standing this record's own §1 gives it, and the reason §9 of `DR-027` exists.
