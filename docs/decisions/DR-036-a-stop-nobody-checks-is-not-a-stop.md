# DR-036: The protection expired at the first close, and nothing was checking

```
date:            2026-09-03
status:          accepted — a guard, not a management action. Re-placing the stop stays DR-027 §2's
                 and D6's, and is NOT done here
parameters:      none
components:      none new
implemented_by:  src/swingdesk/broker/reconcile.py :: def unprotected
                 the venue read it needs is PlacedOrder.stop_price, filled by
                 src/swingdesk/broker/alpaca.py :: def _order
built:           2026-09-03
```

## 1. What was true on the first day this system held anything

The owner asked what stops and targets the open trades carried. The book had an answer for all
three. **The venue had none.**

```
DINO  leg limit  expired    limit=114.06      leg stop  canceled  stop=98.59
AIS   leg limit  expired    limit=72.54       leg stop  canceled  stop=61.70
BTSG  leg limit  expired    limit=65.72       leg stop  canceled  stop=55.08
```

A bracket's legs inherit the entry's `time_in_force`. `DR-027` §3.3 makes that `day`, and its
argument is exact: *"An order that outlives the session outlives the analysis that produced it."*

**That is true of an entry and false of a protection.** The entry is a decision about one session.
The POSITION lives up to `exit.max_holding_period` — twenty sessions — and its stop has to live
exactly as long. §3.2 and §3.3 of the same record therefore contradict each other for every position
held overnight, which is every position the strategy can produce.

So all three holdings spent a night, and the whole of the next session, with **no protective order
at the venue at all** — and `DR-027` §3.2's own words are why that matters:

> A stop held only in `positions.duckdb` protects nothing between runs: the system does not watch
> the tape.

## 2. Nothing could have noticed, and that is four separate omissions

Audited on 2026-09-03 after the owner's question:

| where | what it checks | the stop |
|---|---|---|
| `reconcile` | side, asset class, share count, entry price | **never compared** |
| the run report | ATR, RS, entry/stop, sizing, the funnel | never asks whether the stop is *at the venue* |
| `DR-027` §11 / `DR-032` | exposure the caps have not seen | positions and orders, not protection |
| `DR-035` | the two books describe the same positions | says nothing about whether the loss is bounded |

**The one number that bounds the loss was the one number nothing verified.**

## 3. What now happens

`unprotected` compares each open position's `current_stop` against the venue's **resting** orders,
and reports two different facts separately:

- **no protective order at all** — the case above;
- **a stop at a different price**. `manage.apply_approved` writes a new `Position` version when the
  owner approves a stop move and sends nothing anywhere — this system has no verb that could — so
  the book and the venue can hold different triggers while both hold one. A person acts on that
  differently, so it is worded differently.

**Only a `stop` protects.** A resting `limit` above the entry is the take-profit and guards nothing;
both legs arrive in the same list from the same endpoint, and a check that counted either would
report a naked position as guarded by its own target. **The highest resting trigger is the one in
force**, because it fires first; a lower one behind it changes nothing about the loss.

**A submission stops on it, and the reason is arithmetic rather than tidiness.**
`risk.max_open_risk` is denominated in `entry − stop`. A book whose stops are not standing is a book
whose caps are measured against a number that does not exist, so adding a fifth position to it is
the failure every guard here exists to prevent, reached from underneath.

**`broker` reports it and exits `3`.** Same code as any other mismatch: this *is* a broker/journal
mismatch, about the one number that matters, and Appendix N's action for `TECH` does not soften
because the share counts happened to agree.

## 4. What this deliberately does NOT do

**It does not re-place the stop.** `DR-027` §2 lists *management actions on open positions* as not
submittable and leaves them to `D6`; `CHARTER` A-002 §4 leaves that standing. And this system has no
verb that could amend an order anyway — `access.allowed_methods` is `GET` and `POST`, so even a
correct fix would be *place a new stop*, which is a new order shape and a new decision.

**Saying so loudly is what a guard may do, and it is most of the value.** Before this, three
positions were unprotected for a day and a night and no line anywhere said so.

**What the owner has to rule**, stated so the choice is available rather than implied:

1. **`gtc` on the bracket**, so the legs outlive the session. Simplest, and it makes the ENTRY rest
   overnight too — which is exactly what §3.3 refused, for a reason that has not gone away.
2. **A separate protective stop after the fill**, `gtc`, placed by `sync-fills` once a position is
   recorded. Keeps §3.3 intact for the entry and needs a new order shape under `DR-027` §2.
3. **Leave it manual** and let this guard pause the machine until a person restores the protection.
   Correct, and it makes the system stop trading after its first fill.

## 4.1 Amendment, 2026-09-03 — §4's "it does not re-place the stop" is now history

**Appended rather than edited**, per `AGENTS.md` §11 rule 2. §4 was accurate when written: the
options were laid out for the owner and the guard was the whole behaviour.

**The owner ruled the same day.** `DR-037` keeps the bracket `day` and adds a separate `gtc` OCO
once a position is recorded, so a missing protection is now *restored* before the run continues,
and this guard is what it falls back to when the restoration fails — plus what still reports a stop
standing at the wrong price, which `DR-037` deliberately does not touch.

## 5. What would overturn this

- **A venue that reports a position's protective orders on the position itself.** The join here is
  by symbol across two endpoints; one that carried the stop inline would make this a field
  comparison rather than a search.
- **Short positions.** `unprotected` reads *highest trigger wins*, which is true for a long and
  inverted for a short. `contracts.position` cannot describe a short, so there is no subject today.
- **More than one position per symbol.** The book keys on `instrument_id`, and two positions in one
  name would share a stop search that cannot tell which order guards which.
