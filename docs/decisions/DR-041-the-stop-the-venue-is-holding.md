# DR-041: the book adopts a TIGHTER stop the venue is holding, and refuses a wider one

```
date:            2026-09-07
status:          proposed — the owner's ruling is asked for in §6
parameters:      none
components:      none - swingdesk.trade_management.adoption:moved_stop decides; the CLI writes
supersedes:      nothing. DR-036 stands and this is its converse; DR-031 and DR-038 are the precedent
implemented_by:  src/swingdesk/trade_management/adoption.py :: moved_stop
```

## 1. What made this necessary: the last guard with no automatic path

Owner instruction, 2026-09-07 — *"давай починим авто-восстановление после TECH"*.

Auditing every `_stop_all` in the submission path found **ten stop conditions and nine already
recover or correctly need a person**:

| condition | recovery |
|---|---|
| the venue could not be read | transient — the next pass reads it |
| the book and the venue disagree, `book_only` | **`DR-038`** closes it from the venue's fill |
| a position holding NO stop | **`DR-037`** places the protection already decided on |
| the venue holds something we never sent | a person's, and correctly — that is somebody trading by hand |
| the drawdown pause, the caps, the allocation | working as ratified |
| **a stop resting at the WRONG price** | **nothing. Ever.** |

`reconcile.restorable` splits unprotected positions into the ones `DR-037` places for and the ones
it must not, and the second half is exactly this case: a trigger IS standing, at a price the book
does not record. `DR-037` deliberately leaves it — putting a second trigger on one position would
apply a move nobody approved, and `unprotected` reads *the highest wins*.

**So the run restores what it can, re-reads the venue, still finds the position unprotected, and
stops. Every evening. For ever.** That is the same shape `DR-035` names two guards earlier:
*"a stopped-out position stays open in the book for ever, holds its slot, and after four stop-outs
the machine submits nothing again, silently."*

## 2. The rule

**A stop resting ABOVE the book's is adopted into the book.** `reconcile.unprotected` already
writes the argument in the reason it emits for this case:

> *"the book records a stop at X and the venue is holding one at Y. Every R this position reports
> is denominated in the book's number (`RISK_SPEC` 2), and the loss would be taken at the venue's."*

The number that will actually be taken is the number the caps must be measured against. `DR-036`
ruled that a stop the market cannot see is not a stop; this is its converse, and refusing to write
the venue's number down does not undo the move — it keeps the book wrong **and** the system stopped.

**A stop resting BELOW the book's is REFUSED, and stays a person's.**

## 3. Why the second half is not symmetric, and the contract is what found it

The first implementation adopted both directions. `ManagementAction` rejected it outright:

```
proposed stop 40.00 is below the current 45.00. A stop move that increases risk is
rejected (CODES WIDE_STOP)
```

**That rejection is the argument, not an obstacle to it.** A trigger further from entry than the
book records means somebody widened the loss this position can take, beyond what was approved when
it was sized. Writing that down as an APPROVED move would launder an unapproved risk increase into
the book and into every `R` the position reports. It is the same class as a holding that traces to
no order of ours: the venue's word is the fact, and what to do about it is a person's.

So the run still stops on a widened stop — **for a correct reason rather than a mechanical one**,
and with a sentence saying which.

## 4. Why this is bookkeeping and not a management action

`DR-027` §2 lists management actions on open positions as not submittable and leaves them to `D6`.
This sends nothing and moves nothing: **the trigger is already resting at that price.** The same
argument `DR-031` makes for an opening and `DR-038` for a closing — the event happened at the venue,
and writing it down is bookkeeping.

It is written through the one chain that defines a stop move — `propose`, `respond`,
`manage.apply_approved` — so there stays one place that knows what moving a stop does to the book,
and the old number survives as a `Position` version rather than being overwritten. The approval is
recorded against this decision record rather than a person, and the reason says so.

## 5. Where it runs

`sync-fills`, beside the opening and closing halves, and for the same reason: `daily_run.cmd` runs
it **before** the scan, so the caps are measured against a book that already describes what the
venue is holding. One more `GET` (`open_orders`) and no new write verb.

## 6. What is asked of the owner

**Ratify or refuse §2.** The half that adopts is the one that needs a ruling — the half that refuses
is already ratified by `CODES`' `WIDE_STOP` and changes nothing.

**The case against**, stated as strongly as I can put it: a tighter stop at the venue is still a move
nobody approved, and adopting it silently reduces the recorded open risk, which frees capacity under
`risk.max_open_risk` for another position. The system would be letting an unapproved change enlarge
what it may do next.

**The case for**, and it is why this is proposed: the alternative is not "the move does not happen".
The move has already happened. The alternative is a book that records a stop the market is not
holding, caps denominated in a number that does not exist, and a machine that stops submitting for
ever with no path back that does not involve a person at a keyboard. `DR-036` refused to accept
exactly that state in the other direction.

**Until it is ruled, nothing changes in behaviour that was not already stopped** — the code refuses
the widening half and adopts the tightening half, and both were previously a permanent stop.
