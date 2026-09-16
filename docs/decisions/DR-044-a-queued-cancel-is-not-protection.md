# DR-044: A stop whose cancel is queued is not protection

```
date:            2026-09-15
status:          accepted — ratified by the owner 2026-09-15, the same evening it was measured
parameters:      none
components:      none new
implemented_by:  src/swingdesk/broker/reconcile.py :: WITHDRAWN
```

## 1. What was measured, tonight

The owner cancelled three hand-placed stops at 19:35 so that `DR-037` would restore this system's
own protection in their place. The venue accepted all three cancels and carried out none: the
market had closed, and each order went to `pending_cancel`.

**The 19:30 pass then restored nothing, and exited 0.** `reconcile.resting_stops` read the order
TYPE and the trigger and never the STATUS, so three stops on their way out counted as protection in
force. `unprotected` found nothing to report, `DR-037` had nothing to restore, and the pass finished
cleanly at 19:54 with the book and the venue apparently agreeing.

| | |
|---|---|
| stops cancelled, accepted, and not executed | **3** — DINO, VGT, XMTR |
| what the pass saw | three stops resting at the book's prices |
| what was actually standing | three orders the venue had agreed to retire |
| when the cancels would land | the next open, with the next armed pass twelve hours later |

So the exposure was: **three positions naked for a whole session**, with nothing in the system
saying so. The one position that was genuinely bare — `BTSG`, whose cancel had executed during the
session — was restored by the same machinery an hour earlier, which is what makes the gap here a
reading of status rather than a failure of `DR-037`.

## 2. The rule

**An order in `pending_cancel` is not protection.** It is listed, it is going away, and until it
goes it still holds the shares.

1. `resting_stops` ignores it, so `unprotected`, `swingdesk status` and the submission guard all
   see the position as unprotected — one definition, as before.
2. `unprotected` names this case apart from *nothing is resting*: the reason says the stop is being
   withdrawn and that it holds the shares until the cancel lands. The operator's next move differs
   between the two, and a reason that blurred them would send them to the wrong one.
3. `own_stop` (`DR-043`) refuses to raise it. Amending an order the venue is already retiring is a
   request about an order that will not exist, and the approved move belongs on the replacement.
4. `swingdesk status` prints a NOTE rather than a place command, because the command would be
   refused (§3).

## 3. Why the pass still tries, and why the screen does not

`DR-043` §1 measured the cost of sending into a queued cancel: on 2026-09-12 a replacement for
`VGT` was refused `insufficient qty` because the old stop's cancel was waiting for Monday.

The armed pass attempts anyway, and that is deliberate: the venue is the authority, the cancel may
land between the read and the write, and a refusal is journalled under the `Submission` contract
like any other — `rejected`, with the venue's own words. The screen does not, because a printed
command is read as *do this now*, and this one would fail until a fact outside the operator's
control changes.

**Either way `DR-036` pauses new entries** while a position reads unprotected, which is the
behaviour this record restores rather than invents.

## 4. What this does not change

* **Nothing about cancelling.** `DELETE` stays refused (`broker.policy.REFUSED_METHODS`); the
  cancels this record is about were the owner's, sent by hand.
* **Nothing about what may be sent.** `DR-027` and `DR-043` still bound that exactly.
* **Nothing about the book.** A stop being withdrawn at the venue does not touch `current_stop`;
  the book's number stays the one every `R` is denominated in.

## 5. What would overturn this

* **The venue freeing the shares when it accepts a cancel rather than when it executes it.** Then a
  replacement placed immediately would succeed, and the honest action becomes sending one rather
  than waiting. Measured on the next such evening, not assumed.
* **A venue status this record does not know.** `pending_cancel` is the one Alpaca uses and the one
  measured tonight; another word for the same state would need adding by measurement, and until it
  is, it would read as protection — which is why the constant carries this record's number.

## 6. The operating lesson, recorded because it cost a session

**Cancel a hand-placed stop DURING the session, not after the close.** A cancel sent while the
market is open executes at once and the evening pass restores the system's own stop the same day.
A cancel sent after the close is queued until the next open, which puts the gap in the middle of a
trading session — the worst place for it. `docs/runbooks/README.md` §7.5 carries this beside the
handover commands.
