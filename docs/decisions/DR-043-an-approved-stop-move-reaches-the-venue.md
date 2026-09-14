# DR-043: An approved stop move reaches the venue

```
date:            2026-09-14
status:          accepted — ratified by the owner 2026-09-14, option A. This is the separate
                 ruling CHARTER A-002 §4 left D6's stop moves waiting for
parameters:      none
components:      none new
implemented_by:  src/swingdesk/presentation/status.py :: class Handover
                 the interim - the printed commands, built 2026-09-14. The replace itself is being
                 built next, and this line moves to it when it lands
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
