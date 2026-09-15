# DR-043: An approved stop move reaches the venue

```
date:            2026-09-14
status:          accepted — ratified by the owner 2026-09-14, option A. This is the separate
                 ruling CHARTER A-002 §4 left D6's stop moves waiting for
parameters:      none
components:      none new
implemented_by:  src/swingdesk/broker/alpaca.py :: def replace_stop
                 the replace, built 2026-09-14 (section 9). `presentation/status.py`'s `Handover`
                 still prints the commands for every case the replace leaves alone
```

## 1. What happens today, measured

`D6` asks the owner to approve every stop move, and `respond --approve` writes the new stop into the
book as a new `Position` version. **Nothing reaches the venue** — the system has no verb that
cancels or amends an order (`registry/broker_policy.yml` permits `GET` and `POST`; `DELETE`,
`PATCH` and `PUT` are refused by `broker.policy.REFUSED_METHODS`). The venue goes on holding the old
trigger; `reconcile.unprotected` reads the book and the venue apart, `DR-036` pauses new entries, and
the owner cancels and re-places by hand.

**What that cost in the five sessions to 2026-09-14**, read from the venue's own order history for
the four open positions:

| | |
|---|---|
| stops placed by hand | **13** — BTSG 4, DINO 4, VGT 3, XMTR 2 |
| stops cancelled by hand, or queued and cancelled | about **9**, plus both of `DR-037`'s protective OCOs |
| a replacement refused `insufficient qty` | **1** — VGT, 2026-09-12: the old stop's cancel was queued for Monday and still held the shares |
| **time the four positions stood with no stop in an open market** | **55 minutes**, 2026-09-14: every resting stop's cancel landed at 08:00 CDT and the replacements went in at 09:25 |

Every one of those orders was a number the system had already decided and approved. The person was
the transport.

## 2. The options, and what each costs

| | what it does | a gap with no stop? | what it needs |
|---|---|---|---|
| **A. Replace** | on approval, amend the resting protective order's `stop_price` to the approved one — Alpaca's `PATCH /v2/orders/{id}`, one request; the venue retires the old order as `replaced` | **none** — the replacement is the venue's own atomic step | `PATCH` in the policy, and this ruling |
| **B. Cancel, then place** | `DELETE` the resting order, wait for it to land, `POST` a new one | **yes**, between the two; and a queued cancel (a weekend, a halt) blocks the new stop for `insufficient qty` - measured above | `DELETE` in the policy, and this ruling |
| **C. Print the commands** | `swingdesk status` shows the exact cancel-and-place commands for the operator's shell | yes, as long as the person takes | **nothing — built 2026-09-14** |

## 3. What is proposed: A, and narrowly

**The system replaces its OWN protective stop, to an APPROVED, HIGHER price, and does nothing else.**

1. **Only on an approval.** The trigger is `respond --approve` of a `MOVE_STOP` — `D6`'s decision
   point, unchanged. Nothing the system proposes moves the venue unapproved.
2. **Only upward.** `manage.lowers_stop` already refuses an approval that would lower the book's stop;
   the replace path refuses the same, a second time, at the venue boundary.
3. **Only an order this system placed.** The order's `client_order_id` must carry `DR-037`'s protective
   prefix. A stop the operator placed by hand is reported and left alone — its owner is a person, and
   the book cannot know what they meant by it. To hand one back, the operator cancels it and
   `DR-037` restores a protective order at the book's stop on the next armed pass.
4. **Only `stop_price`.** Quantity, side, lifetime and the take-profit leg are not touched. The price
   sent is the approved stop snapped UP to the venue's tick (`DR-033`).
5. **Only armed.** The same switch file every submission reads (`DR-027` §8).
6. **Journalled like every write**, under the `Submission` contract, whatever the venue answers — and a
   refusal leaves the old stop standing, which is `DR-036`'s finding, not a new failure.

**The boundary moves in two places a reviewer sees.** `registry/broker_policy.yml` gains `PATCH` in
`allowed_methods`, and `broker.policy.REFUSED_METHODS` loses it. Gate 39's absolute rule — no write
verb spelled anywhere in `swingdesk/broker/` — is unchanged, because the verb still comes from the
policy; the transport's call sites go from two to three, and the gate's count moves with this record.

## 4. What it deliberately does not do

* **No cancellation.** `DELETE` stays refused. A replace never leaves a position without a stop; a
  cancel always does, for however long the second request takes.
* **No partial exits, no target moves, no new positions.** `D6`'s other actions stay manual.
* **Nothing on a stop the system did not place**, and nothing on a lower price.

## 5. The wire format is READ, not MEASURED

Alpaca's reference documents `PATCH /v2/orders/{order_id}` with `stop_price` for a resting stop, and
describes the legs of an advanced order as orders of their own. **This project has been corrected by
the venue four times on documentation facts** (`DR-037` §5.1 is the latest), so the first armed
approval settles it: a `422` is journalled under `rejected`, the old stop stands, and the operator
reads which field was wrong.

## 6. The question put to the owner

**Ratify A** — the system replaces its own protective stop to an approved higher price — or **keep
C**, the printed commands, and go on being the transport. B is not recommended by anyone: it is A's
effect with a gap in the middle.

## 7. What would overturn this

* The venue refusing to replace a leg of an `oco` — then A needs the protection placed as a plain
  `gtc` stop rather than an `oco`, which is its own amendment to `DR-037`.
* A replace that the venue executes as cancel-then-new with a window between — measured, not
  assumed, on the first armed approval.

## 9. Built, 2026-09-14 — and two places the build is stricter than §3

**Where it lives.** `respond --approve` records and applies the answer first, closes the book, and
only then calls `cli._send_stop_move`, and only for a `MOVE_STOP` that raised the book's stop. That
reads the arming switch, asks the venue what is resting, picks the stop with
`reconcile.own_stop`, and sends `AlpacaClient.replace_stop`: one request to
`endpoints.order` (`/v2/orders/{order_id}`) whose body is `{"stop_price": ...}` and nothing else.
The price is the approved stop rounded UP to the venue's tick (`DR-033`). Every attempt is a
`Submission` row under run id `respond-<position>-<sequence>`: `stopped` when unarmed or the venue
could not be read, `refused` when the stop is not ours, `rejected` with the venue's reason, `sent`
under the id the venue answered with.

**The policy names each verb's job.** `access.allowed_methods` is `GET`, `POST`, `PATCH`;
`write.submit_method: POST` and `write.replace_method: PATCH` say which does what, and
`policy.load` refuses a permitted write verb with no job, a job whose verb is not permitted, and one
verb holding both. `REFUSED_METHODS` is `DELETE` and `PUT`. Taking the replace away is two deleted
lines, and gate 39 passes the narrower policy (`tests/test_verify_broker_policy.py`).

**Stricter than §3, in two places.**

1. **"Ours" is decided by the journal, not by the prefix §3.3 names.** A stop is this system's when
   its own id or its `oco` parent's is in `Journal.sent_client_order_ids` — `DR-032`'s `ours` rule,
   for `DR-032`'s reason: a prefix test adopts a stop a person typed with the right first word. The
   parent is how the stop leg is found at all, since its own id is one the venue generated;
   `open_orders` now keeps it on each leg (`PlacedOrder.parent_client_order_id`). A stop this
   system already replaced is found by the id the replace was journalled under, so the chain holds
   even if the venue hands the replacement back without its parent.
2. **Transport call sites stay at two, not three.** The replace goes through `_write`, which now
   takes the verb as an argument — the callers pass `policy.write_method` or
   `policy.replace_method` — so the arming switch, `write_enabled` and `check_method` are consulted
   exactly as for a submission, and gate 39's count did not have to move.

**What it leaves alone, and says so:** two stops resting for one name (raising one leaves the
other), a stop at the venue already above the approval (`DR-041` adopts it; a replace would lower
it), a stop already at the price, and every stop a person placed — which on 2026-09-14 is all four
open positions. For those the move stays printed by `swingdesk status`. To hand a position back,
cancel the hand-placed stop **after the close** and before the 18:30 run: `DR-037` then places this
system's own `oco` at the book's stop with no session in between.

**Not yet measured:** the wire format (§5). The first armed approval that meets a stop of ours
settles whether the venue replaces an `oco` leg — `sent` in the journal and a `replaced` order in
the venue's history — or refuses it, which §7's first bullet already answers. **The likeliest
refusal is named in advance:** an `oco`'s stop rests with status `held` (measured 2026-09-04,
`AlpacaClient.open_orders`), and Alpaca's replace reference speaks of orders, not of held legs. A
refusal there costs nothing but the attempt — the old stop stands and the row says why.
