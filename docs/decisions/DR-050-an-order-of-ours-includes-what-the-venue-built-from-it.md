# DR-050: "an order of ours" includes what the venue built out of it — the book recorded every winner and dropped every loser

```
date:            2026-09-21
status:          accepted — found while auditing on the owner's instruction, 2026-09-21:
                 "let us slow down with real-money trading, I am sure we still have enough
                 errors we have not found". This is the first one the audit turned up, and it
                 was live
parameters:      none
components:      none new
implemented_by:  src/swingdesk/presentation/cli.py :: leg_ids
```

## 1. What was wrong, in one sentence

**A position that exited on a STOP was never closed in the book, while a position that exited on a
take-profit always was** — so the record kept the winners and lost the losers, and no test, gate or
mutant could see it.

## 2. What it did, measured rather than described

| | |
|---|---|
| `BTSG` sold at the venue | **2026-09-17 19:11 UTC, 18 shares at 57.57** |
| still open in the book | **four days later** |
| entries submitted since | **zero** — every one carries `outcome = stopped` |
| the reason in the log | `STOPPED TECH: the book and Alpaca paper trading disagree about 1 position(s) - BTSG (book_only). Pause new entries` |

**`CARD-001` stopped trading on 2026-09-17 and nobody noticed for four days.** The guard
(`DR-027` §11) did exactly its job — it refused to act on a book it could not trust. The defect was
upstream of it.

**Three exits on the same book tell the whole story:**

| name | exit type | the order's `client_order_id` | recorded? |
|---|---|---|---|
| `XMTR`, `DINO`, `VGT` | take-profit LIMIT | `swingdesk-protect-2026-09-16-…` | **yes** |
| `BTSG` | **STOP** | `42b24323-8e1e-4128-9330-44688cf733df` | **no** |

## 3. Five whys

1. **Why is `BTSG` still open four days after it sold?**
   `sync-fills` could not attribute the sell to an order of ours.

2. **Why could it not?**
   `adoption.closing_exit` accepts a fill only when `ours(fill.order_id)` is true, and `ours`
   resolved the venue's order id through the journal's `submissions`. The filling order's id is
   not there.

3. **Why is it not in the journal?**
   Because it is a **leg**, not the order we sent. An `oco` is ONE order to us and TWO to the
   venue: `protect()` journals the one it submitted, with the one `venue_order_id` the venue
   answered with, and Alpaca creates the second leg itself with an id of its own.

4. **Why does that bite stop-outs and only stop-outs?**
   Because in an Alpaca `oco` the **limit is the primary** and the **stop is the leg**. A
   take-profit exit fills the primary, whose id IS journalled. A stop-out fills the leg, whose id
   is not. **The loss is not random — it is exactly the losing exits.**

5. **Why did no test catch it?**
   Because the code's definition of *"an order of ours"* was *"an id we sent"*, and **every test
   was built from the same definition**: a fixture sends an order and then reports a fill on that
   id. The test and the code shared the assumption, so no fixture and no mutant could separate
   them. Nothing in the suite had ever modelled an order the VENUE created.

**And the knowledge already existed in the same file.** On 2026-09-04, `open_orders` was taught
exactly this - its docstring records the measurement (`status=open&nested=true -> 3 rows, 3 legs`)
and concludes *"a leg IS a resting order"*. `DR-036` needed it to see what protection was standing.
`DR-038`'s close half was written afterwards, ninety lines below, and did not carry it. **So this
was not a thing nobody knew: it was a lesson that stayed local to the path that learned it.**

**The root**, stated so it can be checked against other code: *our* notion of ownership was **an id
we sent**, and the venue's notion of *what can close our position* includes **children it created
from what we sent**. The two were never the same set, and the difference was invisible because
nothing ever looked at it from the venue's side.

## 4. The fix, and why it is the root rather than the instance

**`ours` now means: an order we sent, OR a leg the venue built out of one.**

* `broker/alpaca.py :: legs_of` — a read-only `GET` with `nested=true`, returning the venue ids of
  an order's legs. **The walk has to go downwards**: measured 2026-09-21, a leg fetched alone
  returns `legs: None` and names no parent, so from a leg there is no way up.
* `journal.py :: sent_venue_order_ids` — every id the venue gave us for one instrument, so the
  question *"what did you build out of each"* can be asked.
* `cli.py :: _sync_fills` — collects those leg ids once per open position and widens the predicate.
  **Bounded by the book, not by the account's history.**

**Every other place that attributes an order to us was checked** rather than assumed: there are
three, and the other two ask a different question. `_uncommitted_exposure` skips sells before it
looks anything up (a sell commits no exposure, `DR-032`), and the adoption half keys on the SYMBOL
of a holding rather than on an order id.

**Verified on the live book**, which is the only verification that counts here:

```
Alpaca paper trading  0 holding(s) at the venue
  WOULD CLOSE   BTSG       18 sh at 57.57 on 2026-09-17
  WOULD CLOSE   VGT        20 sh at 123.47 on 2026-09-21
```

Both prices and both dates match the venue's own fills exactly.

## 5. The test that would have caught it, and the one that would not

`test_a_stop_out_on_a_venue_created_LEG_closes_the_position` models what every earlier test left
out: a fill whose `order_id` is a leg the venue made, with the journal holding only the parent.
**It fails without the fix and passes with it** — checked by reverting the predicate and watching it
go red.

**What would NOT have caught it, and this is the transferable part:** any test that builds its
fixture from our own submission. The suite had many, they were all correct, and they all shared the
blind spot. A fixture drawn from the same assumption as the code is a mirror, not a check.

## 6. What this does NOT change

`DR-027` §11's guard, which behaved correctly throughout and is the reason this cost four idle days
rather than a wrong book acted upon. `DR-031`'s and `DR-038`'s standard — a close is a POSITIVE
record of shares leaving, traced to something this system caused. **That standard is unchanged; what
changed is the definition of "caused".** `A-002`'s paper boundary. The pause on real-money trading.

## 7. What it costs

One `GET` per order this system sent for a name still open in the book — a handful an evening,
against a page bound that already exists. Nothing in the write path is touched, so gate 39 still
sees exactly two call sites reaching the transport.

## 8. How it is enforced

| clause | enforced by |
|---|---|
| §4's widened ownership | `cli.py :: leg_ids`, and `tests/test_cli.py`'s leg test, which reverts red |
| §4's downward walk | `broker/alpaca.py :: legs_of`, a `GET` on an endpoint the policy already names |
| an unreadable leg list is loud | a refusal line rather than a silent skip, asserted by its own test |
| the root, stated for the next reader | §3's five whys, and `AGENTS.md` §12's trap on shared assumptions |
