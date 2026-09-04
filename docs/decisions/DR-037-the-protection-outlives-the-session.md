# DR-037: The entry expires with its session and the protection does not

```
date:            2026-09-03
status:          accepted — owner ruling 2026-09-03, inside CHARTER A-002's scope
parameters:      none set. The stop is the position's own `current_stop` and the target is
                 `exit.target_r_multiple` R above its recorded entry — the same rule
                 `broker.submit.target_price` already applies to an entry
components:      none new
implemented_by:  src/swingdesk/broker/submit.py :: def protective_order
                 the wire call is src/swingdesk/broker/alpaca.py :: def protect, and the caller is
                 src/swingdesk/presentation/cli.py :: def _restore_protection
built:           2026-09-03
```

## 1. The contradiction inside one record

`DR-027` §3.2 argues for a bracket because **a stop the market cannot see is not a stop**. §3.3 gives
every order `time_in_force: day` because *"an order that outlives the session outlives the analysis
that produced it."*

Both are right about what they are about, and a bracket's legs inherit the entry's
`time_in_force` — so §3.3's rule reaches the protection, which §3.2 requires to last as long as the
position. The position lasts up to `exit.max_holding_period` sessions.

`DR-036` measured the consequence on the first day this system held anything: all three stop legs
`canceled` and all three targets `expired` at the first close, leaving three holdings with no
protective order and a book still recording one.

## 2. What was ruled, and the two options it beat

The owner ruled on 2026-09-03: **keep the bracket `day`, and place a separate `gtc` OCO once the
position is recorded.** Not instead of the bracket — *as well as*. The protection is then continuous:

- **the session of the fill** is covered by the bracket's own legs, which are alive until its close;
- **from that evening onward** by the OCO, which is `gtc` and does not expire;
- **the entry keeps `day`**, so §3.3 is untouched.

The window between the two is from the close to the evening pass. The market is shut across it.

**`gtc` on the whole bracket was rejected**, and by evidence rather than taste: the legs cannot carry
their own `time_in_force` — Alpaca accepts it only on the parent — so `gtc` would reach the entry
too. An unfilled entry would then rest for days and fill on analysis that had expired, which is
exactly what §3.3 refused. `BFH` is the live example: it rested unfilled and expired on schedule.

**Leaving it manual was rejected** because the machine stops after its first fill, and `b.min_sample`
needs a hundred closed trades.

## 3. It is an order shape `DR-027` §2 did not permit

§2's table excludes *"management actions on open positions"* and leaves them to `D6`; `CHARTER`
A-002 §4 leaves that standing. This record adds the shape, and the distinction that makes it
addable is narrow and has to stay narrow:

**`D6` governs a stop MOVE. This moves nothing.** It restores the protection this system already
decided on and already sent, which the venue retired for a mechanical reason. The stop it places is
the one already in the book; the target is the one that stop already implies.

**A stop at the WRONG price is therefore not restored.** That is a stop somebody moved, and placing
a second one would leave two triggers on one position — which `unprotected` reads as *the highest
wins*, silently applying a move nobody approved. It is reported and left alone.

## 4. Everything it sends comes from somewhere that already existed

| field | source |
|---|---|
| `stop_price` | the position's own `current_stop` |
| `target_price` | `exit.target_r_multiple` R above the recorded entry — `target_price`'s rule, applied to a position |
| `shares` | what the book records as held |
| `gtc`, `oco`, `sell` | `registry/broker_policy.yml`, beside the host, where changing one is a commit a reviewer sees |
| the prices as sent | snapped by `DR-033` — stop **up**, target **down**, the conservative side of each |

**A distinct `client_order_id` prefix**, because the entry for this instrument on this session
already used the other one and the venue rejects a duplicate. `DR-027` §5's property is unchanged:
one protective order per instrument per session, and a second refused by the party that knows.

**The same chokepoint.** `protect` calls `_write` like every other write here, so §4's guards run
before a socket opens and gate 39 still sees exactly two call sites reaching the transport. A second
write *method* is not a second write *path*.

**Every attempt is journalled** under the same `Submission` contract an entry uses, whatever the
venue said. A protective order the venue refused is the fact an operator most needs.

## 5. The wire format is READ and not yet MEASURED

Stated plainly because this project has been wrong here three times: a bracket needed three legs, a
session had to come from the exchange rather than a clock, and every price had to sit on the venue's
own increment. **All three were documentation facts the venue corrected by refusing.**

The `oco` payload here is built from Alpaca's reference. If it is wrong, the venue answers `422`,
the journal records it under `rejected`, `DR-036`'s guard stops the submission, and the next
evening's operator reads exactly which field was wrong — which is `DR-027` §9's pattern working
rather than a gap. **The first armed evening settles it.**

## 5.1 Amendment, 2026-09-03 — it settled it, and the format was wrong

**Appended rather than edited**, per `AGENTS.md` §11 rule 2. §5 was a prediction with a stated
mechanism; this is what the mechanism returned, four hours later.

**The measurement.** The evening pass ran armed at 19:30 CDT and sent three protective orders. All
three came back:

```
422  {"code":40010001,"message":"invalid order type"}
```

`AIS`, `BTSG` and `DINO` stayed unprotected, and the journal holds three `submissions` rows with
`outcome = rejected` carrying that exact message. **Everything §5 promised happened**: the venue
answered, the journal recorded it, `DR-036`'s guard stopped the run — 96 sized and eligible Trade
decisions were *not* submitted behind an unprotected book — and the field was named. The prediction
was right about the process and wrong about the payload, which is the outcome that costs least.

**What was wrong.** The payload carried no `type` at all. The reasoning, written into the code, was
that an `oco` *is* its two legs and therefore needs no shape of its own. It reads well and it was
false.

**What settles it, and it is not a document.** This system's own accepted entry sends `type`
alongside `order_class: bracket` and the same nested `stop_loss`/`take_profit` legs, and the venue
takes it. So `order_class` says how the legs relate and `type` is still the parent order's own
shape. `protect_order_type: limit` is now in the committed policy, because an `oco`'s take-profit
leg is a limit order. **It sets no threshold** — the two prices are still the book's own stop and
the target `exit.target_r_multiple` implies, and both travel in the legs.

**Why no test caught it.** Nothing in the suite looked inside the protective payload; the builder
was covered and the wire shape was not. `tests/test_submit.py` now compares the protective
payload's top-level fields against the entry payload the venue has **accepted**, with each
difference named and its reason written down. Removing `type` again fails two tests. That check is
the general form of this defect rather than a patch for this instance: the four wire-format facts
this project has got wrong were all discoverable by asking what the venue had already taken.

**The count is now four**, not three: a bracket needs three legs, a session comes from the exchange,
prices sit on the tick, and an order class does not replace an order type.

## 5.2 Amendment, 2026-09-04 — the protection landed and the run stopped anyway

**Appended, per `AGENTS.md` §11 rule 2.** §5.1 fixed the payload; this is what the first *accepted*
restoration then found.

**The measurement.** The pass placed all three OCOs and the venue accepted all three — `AIS` 61.70,
`BTSG` 55.08, `DINO` 98.59, `gtc`, stop legs `held`. The journal holds three `sent` rows. Then the
re-check called all three positions unprotected and the run stopped, sending `101` candidates to
`stopped` behind protection that was standing.

**The cause is the response shape, again.** An `oco` answers with its **parent**, and the stop is a
nested leg:

```
parent   type=limit  order_class=oco  stop_price=None  status=accepted
  leg    sell stop   stop=61.7                         status=held
```

`unprotected` requires `order_type in PROTECTIVE_TYPES` and a `stop_price`. The parent is neither,
so splicing it into the live-orders view proved nothing about a stop.

**The fix is not to read the legs out of the echo.** That would work and it would be the wrong
shape of answer. `DR-036`'s whole argument is that a stop the market cannot see is not a stop; a
re-check assembled from our own write's receipt is the same claim wearing better clothes. The run
now spends **one `GET`** and asks the party that will be holding the order when the gap comes. It
also covers what an echo cannot — a leg accepted and then rejected, or a partial acceptance.

**Unavailable is not confirmation.** If that read fails, the run stops and says the protection was
placed but could not be confirmed. The venue may well be holding it; that is precisely the guess
this refuses to make, and it is the same polarity `DR-025` §2.1 records this project getting
backwards once already.

**Why the suite did not catch it.** The fixture was more cooperative than the venue: it returned
`order_type="stop"` with a `stop_price` — an object Alpaca never sends — and its `open_orders`
returned the same static tuple however many times it was asked. Both are fixed. **A fake more
helpful than the system it stands for tests the fake**, and that is now the third defect this
project has paid for at the boundary between what a document says and what the venue does.

**The count is five**: three legs to a bracket, a session from the exchange, prices on the tick, an
order class that does not replace an order type, and an `oco` whose confirmation is not its echo.

## 6. What this does NOT do

- **It does not move a stop, close a position, or cancel anything.** `access.allowed_methods` is
  `GET` and `POST`; there is no verb here that could amend an order even if a record permitted it.
- **It does not fire when the switch is stopped.** Placing an order is a write, and the kill switch
  governs writes. A disarmed evening protects nothing and submits nothing, which is consistent.
- **It does not remove `DR-036`'s guard.** The run re-asks `unprotected` against the picture
  including what it just placed, and still pauses on anything it could not fix.

## 7. What would overturn this

- **A venue that lets a bracket's legs carry their own `time_in_force`.** Then the simple answer
  becomes available and this second order shape is unnecessary complexity.
- **An automated stop move.** The moment `D6` can reach the venue, *restore* and *move* stop being
  distinguishable by whether a stop is standing, and §3's narrow line has to be drawn again.
- **A second position in one instrument.** The OCO is keyed by symbol and session; two positions in
  one name would need the quantity split across two protective orders that cannot be told apart.
