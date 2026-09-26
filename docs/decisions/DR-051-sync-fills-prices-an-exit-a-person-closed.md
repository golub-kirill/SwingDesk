# DR-051: `sync-fills` prices an exit a person closed, from the venue's own sale of an order of ours

```
date:            2026-09-26
status:          accepted — owner ruling 2026-09-26, answering the question `TODO.md` §1 put:
                 "yes for sync-fills"
parameters:      none
components:      none new
implemented_by:  src/swingdesk/presentation/cli.py :: _closed_without_a_price
```

## Decision

**`sync-fills` attaches the venue's fill to a position the book CLOSED through an approved
`EXIT_NOW` that no fill settles** — when, and only when, a SELL of exactly the size the book closed
traces by order id, a venue-built leg included, to an order this system sent.

It writes one `Fill` against that approved sequence and nothing else: the position stays as the
owner closed it, `closed_on` included, and nothing is sent to the venue.

A holding the book closed that way and the venue **still holds** is reported as `AWAITING SALE` and
is never adopted as a new position.

## Why this one

**The gap was an extra command a person had to remember, and forgetting it now stops the machine.**
`respond --approve` on an `EXIT_NOW` closes a position and records no price — correct, because at
approval time the owner may not have sold yet. Until this record, only a person's `record-fill`
supplied the price. Since 2026-09-26, `k.drawdown_pause` counts closed positions (`criteria.yml`
v1.1.2, the fix merged as #231), and a closed position with no exit price is an account whose result
is unknown — `UNAVAILABLE`, which stops every submission. So **every approved `EXIT_NOW` halted the
paper run until somebody typed a second command.**

**`BTSG` is the instance, and the price this derives is the one the owner typed.** Sold at the
venue on a stop leg on 2026-09-17; closed in the book by approval on 2026-09-22; priced by hand on
2026-09-26 as `record-fill POS-BTSG-2026-09-03 26 --shares 18 --price 57.57 --filled-on 2026-09-17`.
On a copy of the live stores with that fill removed, this change recorded **`#26`, 18 shares at
57.57 on 2026-09-17, planned 57.61**, settling order `64752e7f-…` — the leg — identical to the hand
entry.

**It is the boundary `DR-031`, `DR-038` and `DR-050` already drew, one step further.** Those records
let the book be written from the venue's word when the event already happened and traces to
something this system placed: shares arriving (`DR-031`), shares leaving (`DR-038`), shares leaving
through a leg the venue built (`DR-050`). A person's approval does not change what the venue did; it
only moved the close ahead of the price.

## Alternatives rejected

- **Keep `record-fill` as the only way.** That is the status quo, and it is what produced the
  advice error of 2026-09-22: the closing command was handed over without saying the price is a
  second step (`TODO_CLOSED.md`, the `BTSG` item).
- **Make `respond --approve` take a price.** At approval the sale has usually not happened; a price
  typed then is a guess, and `record-fill` exists precisely so the price is what the venue did.
- **Attribute any sell of the symbol.** A sale by hand is not ours. Crediting it would be this
  command deciding what a sale meant — the assumption `DR-031` and `DR-038` refuse for a reason.
- **Also rewrite `closed_on` to the sale's date.** It is the owner's record of when they closed it,
  and the equity curve does not need it moved: realised P&L enters on the FILL's date and
  `closed_on` only stops the marking (`drawdown.curve`). Changing a person's record is a different
  decision from supplying a missing price.
- **Adopt a held symbol the book closed and price it later.** Re-recording the holding opens a
  second position for one the owner just closed. Measured before this change: it failed only because
  the new position's id happened to collide with the old one's (`could not be recorded: … already
  recorded`, exit 2) — an accident, and a different first-fill date in the fetched window would have
  walked past it.

## What would overturn this

A price attached from a sale that was not the one closing the position — for example two positions
on one symbol whose sales interleave in the window. `closing_exit`'s size check refuses the cases it
can see (a sale larger or smaller than the book closed); one it cannot would be the evidence.

## Consequences

| clause | where it lives | enforced by |
|---|---|---|
| which positions are waiting for a price | `cli.py :: _closed_without_a_price` — approved `EXIT_NOW`, no fill | `test_a_rejected_exit_is_not_one_a_sale_can_settle`, and the fixture's approved `MOVE_STOP` |
| attribution is unchanged: ours, legs included, exact size | `cli.py :: _sync_fills` reuses `adoption.closing_exit` and `leg_ids` | `test_a_sale_that_is_not_ours_is_left_to_a_person`, `test_a_sale_of_a_different_size_is_refused_not_recorded` |
| the fills window reaches back to the closed position's opening | `_sync_fills`'s `earliest` | `test_the_fills_window_reaches_back_to_a_sale_older_than_the_open_book` |
| two approved unfilled exits are a person's question | the price half's `len(sequences)` refusal | `test_two_approved_exits_with_no_fill_are_a_persons_question` |
| one rule for the planned price | `cli.py :: _planned_price`, shared with `record-fill` | `test_sync_prices_an_exit_the_owner_closed_from_the_venues_own_stop_leg` |
| approved but unsold is `AWAITING SALE`, never a new position | the adoption loop | `test_a_holding_the_owner_closed_but_has_not_sold_is_awaiting_a_sale_not_adopted` |
| the kill switch measures again | `_drawdown_now` reads the fill | `test_the_kill_switch_measures_again_once_the_venue_prices_the_exit` |

**Eleven mutants of the change were run against these tests and all eleven were caught**, among
them the window left narrow, legs walked only for open positions, the clock's date instead of the
sale's, and a rejected or non-exit action counted as waiting.

**What this does NOT change.** `record-fill` stays, for a sale this cannot attribute. `DR-027` §11's
guard still stops submission while the venue holds what the book says is closed, which is exactly
the `AWAITING SALE` state. Commission is recorded as zero, as `DR-038`'s close half records it.
`A-002`'s paper boundary, and the pause on real-money trading.

## Found while building it: a name held twice could not close its second position

**This record amends one clause of `DR-038` §6**, the third refusal — *"a sell dated before the
position opened — it cannot have closed this position"*. The premise stands; the consequence was
wrong. **Such a sell is now ignored, not refused.**

**Five whys**, because this one was latent in the live book and this record made it likelier:

1. **Why would `AIS`'s second position fail to close when it stops out?** `closing_exit` would
   refuse, naming a sell dated before the position opened.
2. **Why is there such a sell?** `AIS` has been held twice — `POS-AIS-2026-09-03`, closed, and
   `POS-AIS-2026-09-23`, open on 2026-09-26 (`positions.duckdb`) — and the first one's sale is one of
   ours, in the same feed, with the same symbol.
3. **Why does the function see it?** It selects "this position's sells" by SYMBOL, side and
   ownership. The fills window is per account, from the oldest position still waiting on anything,
   so whenever that window reaches back past the first sale, the first sale is selected too.
4. **Why was that a refusal?** `DR-038` read a sell before the opening as the book and the venue
   disagreeing about which position this is — true when a name is only ever held once, and every
   test held each name once. The live book re-traded `AIS` on 2026-09-23, nineteen days after the
   clause was written.
5. **The root: the selection's key is the symbol, and the claim is about a position.** A symbol
   outlives its positions; a position's sells are the ones inside its life. The same shape as a join
   on a column whose name is not its meaning (`AGENTS.md` §12).

**Why this record made it likelier.** The price half widens the fills window back to the opening of
any closed position awaiting a price — so one old unpriced exit would pull every earlier sale of
every re-traded name into view, and each such name's next stop-out would be refused. Measured on
the live book on 2026-09-26, the window did not yet reach the first `AIS` sale: latent, not live.

**What it costs: nothing it did not cost before.** With no sale on or after the opening the answer is
still `None`, so a position the venue closed through a sale the book cannot place stays open, and
`DR-027` §11 still stops submission until a person answers it. What changes is that the second
position's OWN sale is no longer vetoed by the first's.

| clause | where it lives | enforced by |
|---|---|---|
| a sell before the opening is ignored | `adoption.py :: closing_exit`, the date filter | `test_a_name_held_twice_closes_on_its_own_sale_not_the_earlier_positions`, which dies both with the filter removed and with the old refusal restored |
| a lone early sell closes nothing | the same filter | `test_a_sell_dated_BEFORE_the_position_opened_closes_NOTHING`, renamed from the test that pinned the refusal |
