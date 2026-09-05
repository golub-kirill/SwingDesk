# DR-038: the book closes a position from the venue's FILL, never from its silence

```
date:            2026-09-04
status:          accepted — ruled by the owner 2026-09-04
parameters:      none
components:      none - swingdesk.trade_management.adoption:closing_exit decides; the CLI writes
supersedes:      nothing. DR-026 stands; DR-031 is extended to the closing half
implemented_by:  src/swingdesk/trade_management/adoption.py :: closing_exit
```

## 1. What made this necessary, and it was a stopped machine rather than a design review

On 2026-09-04 the 18:30 pass produced **320 `Trade` decisions, sized and eligible**, with the
submission switch armed, and sent nothing:

```
STOPPED  TECH: the book and Alpaca paper trading disagree about 1 position(s) - AIS (book_only)
```

`AIS` had ended at the venue and the book never learned. Traced afterwards to this system's own
records rather than inferred: the activities feed carries a SELL fill of 17 shares at 70.03 on
2026-09-04, settling order `1e5b565a-…`, and `journal.duckdb`'s `submissions` table carries that
same order id as a `sent` protective order with `limit_price 70.03` and `stop_price 61.70`. **The
system's own protective bracket closed the position and the system could not write it down.**

**The mechanism, established in the code:** `closed_on` was written in exactly one place —
`manage.apply_approved`, for an approved `EXIT_NOW` — and `EXIT_NOW` was proposed in exactly one
place, `manage.manage_one`, **from bars**. The venue's view never reached that decision, and
`record-fill` settles an approved action of which there was none. So a position that ended at the
venue held its slot in `risk.max_concurrent_positions` for ever and stopped every submission after
it. `presentation/cli.py` already described this outcome in a comment; nothing could act on it.

## 2. The decision

**`sync-fills` closes a book position when, and only when, the venue reports a SELL FILL that
settles an order this system placed.**

| | |
|---|---|
| what closes a position | a positive record of shares leaving, traced **by order id** to a `sent` row in `submissions` |
| what does **not** | the position being absent from the venue. Absence is not evidence |
| the exit price | the venue's own, **share-weighted** across the executions that closed it |
| the exit date | the last fill's session — the position ended when the last share left |
| everything else | stays `TECH`, and a person answers it with `close-position` |

## 3. Why this is not `DR-026` reversed

`DR-026` refused to construct a `Position` from a broker's answer, and its stated reason was that
**the venue does not know the stop**. `DR-031` narrowed that for entries this system placed: the
stop is read from our own record of what we decided, not from the venue's echo. This is the same
narrowing applied to the other end of the trade, and it needs **less** than `DR-031` did — a close
needs no stop at all, only what filled.

**The boundary that keeps it honest is the order id.** A sale this system did not place closes
nothing here. That is the same rule `DR-031` applies to a holding that traces to no order of ours,
and it is what stops this module deciding that anything at the venue must have been ours.

**`CHARTER` A-001 is not engaged.** The trade already happened at the venue; writing it down is
bookkeeping, and the human-only rule is about *deciding to trade*. The alternative considered and
rejected — the machine PROPOSING an `EXIT_NOW` for a person to approve — puts a click between the
operator and a fact, on every stop-out, and the price it would record still comes from the same
activities feed. It buys ceremony rather than authority.

## 4. Why not close on absence, which was the question as first put

Because absence does not say **how**, and a close with no price is a closed trade with no result.
`b.min_sample` counts closed trades toward a verdict; one recorded without an exit price contributes
a row and no information. The fill carries price, size, time and the order it settled — everything
the book needs — so there was never a reason to read the weaker signal.

*(An earlier draft of this argument claimed absence was unsafe because an empty response cannot be
told from a failed read. **That was wrong and is recorded rather than quietly dropped**: the adapter
raises `BrokerUnavailable` on any non-200, on bad credentials and on a non-JSON body, so an empty
position list is a positive answer. The correct objection is the one above — absence is a fact
without a price.)*

## 5. What it writes, and through whose definition

The one chain that already defines closing: propose the `EXIT_NOW`, record the approval and its
reason, apply it through `manage.apply_approved`, settle it with a `Fill` carrying the venue's price.
No second definition of `closed_on` is created.

**The approval is recorded against this record rather than against a person**, and the reason text
says so — it names the shares, the price, the date, the settled order ids and the activity ids, so
the row carries its own evidence.

**The event date and the knowledge date stay apart.** `apply_approved` dates a close from the clock,
which is right for an exit the system proposes and wrong for one it is being told about; the stored
`closed_on` is the venue's session and `knowledge_time` is when we read it.

## 6. What it refuses

Each is a fact the book cannot describe, never a threshold:

- **fewer shares sold than held** — a partial exit is a different action with different vocabulary;
- **more shares sold than held** — which figure is wrong is a person's question;
- **a sell dated before the position opened** — it cannot have closed this position.

All three leave the divergence standing, which keeps `DR-027` §11 stopping submission until somebody
answers it. **A refusal here is the conservative outcome**, and that is checked rather than assumed:
the book keeps the position, the slot stays taken, and nothing new is sent.

## 7. What would overturn this

A close attributed to an order this system placed that turns out not to have closed that position —
an order id reused by the venue, or a sell of a holding acquired outside this system that happened
to settle one of our orders. Neither is possible in the venue's current model; if either becomes
possible, the trace is no longer sufficient and this record is superseded rather than amended.
