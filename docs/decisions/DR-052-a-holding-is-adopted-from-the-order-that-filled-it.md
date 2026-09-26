# DR-052: a holding is adopted from the ORDER its buys filled — never from the earliest fill or the latest order in its symbol

```
date:            2026-09-26
status:          accepted — a defect found in the audit the owner asked for on 2026-09-26 ("keep
                 sniffing for our mistakes in the code and logic, five whys for the critical
                 ones"), reproduced on the live account before it was fixed
parameters:      none
components:      none new
implemented_by:  src/swingdesk/trade_management/adoption.py :: opening_entry
```

## Decision

**`sync-fills` identifies the order a venue holding came from by the ORDER ID its BUY fills
settled, and takes the holding's opening date and its stop from that order alone.** The most recent
of our entries to fill is the holding. A BUY in the window that settles no order of ours makes the
holding untraceable (`TECH`, exit 3), whatever this system sent in that name before.

This amends `DR-031`'s implementation, not its standard: *"adopt only what traces to an order this
system placed"* stands. What changes is how *traces* is decided.

## What was wrong, and it was reproduced rather than argued

Until this record, the open half of `sync-fills`:

- dated a holding by the **earliest fill of ANY side in its symbol** within the fills window, and
- took the stop from the **latest order sent in its symbol** (`journal.latest_sent_submission`).

**`AIS` has been held twice** — `POS-AIS-2026-09-03`, closed, and `POS-AIS-2026-09-23`, open — and
the venue's feed carries both positions' buys. On a copy of the live stores with the second position
removed (as it was before its first `sync-fills`) and a window reaching back to 2026-08-31, the code
before this record printed:

```
REFUSED  AIS: could not be recorded: POS-AIS-2026-09-03 v1 already recorded.
```

The second holding was dated from the FIRST position's buy, recorded under the first position's id,
refused by the append-only store — and then never adopted, so the venue holds a name the book does
not carry and `DR-027` §11 stops every entry. The same copy under this record:

```
RECORDED  AIS  17 sh entry 76.159412 stop 71.320000 ... opened 2026-09-23
```

**It did not happen live, by luck.** On 2026-09-23 no older position was still open, so the window
started on 2026-09-20 and held only the second position's buys. Any open position older than
2026-09-03 would have widened it past the first buy.

**And the stop could come from the wrong order.** The latest order sent in a name is as often a
`swingdesk-protect-…` SELL as an entry, so a holding adopted after its protection was sent would
have carried the protection's stop, not the one it was sized with.

## Five whys

1. **Why would `AIS`'s second position never reach the book?** It was dated 2026-09-03 and so given
   the first position's id, which the store refuses.
2. **Why 2026-09-03?** The date was the earliest fill in the SYMBOL, and the first position's buys
   are in the same feed.
3. **Why could the feed hold them?** The window is per account — from the oldest position still
   open, and since `DR-051` from the oldest closed one still awaiting a price — not per holding.
4. **Why was the symbol the key?** `DR-031` was written when every name had been held once, and
   *"earliest fill wins"* was the right rule for one order's partial fills.
5. **The root: a selection keyed on the symbol for a claim about one position — and the exact
   anchor already existed.** `journal.submission_for_order` was built for `DR-038`'s close half,
   and its own docstring says why: *"an exact anchor rather than the latest row for a symbol"*. The
   open half, written first, was never brought up to it. `AGENTS.md` §12 names this shape — a
   lesson learned in one code path does not travel to the next by itself — and records `DR-050` as
   its first instance; this is the second, in the same function.

**`DR-051` made it likelier**, which is why it is fixed in the same change: a closed position
awaiting a price widens the window back to its own opening.

## Alternatives rejected

- **Narrow the window per holding.** The window is one request for the whole account
  (`client.fills(now, after=since)` in `_sync_fills`); narrowing it per holding means a request per
  holding and still leaves the stop read by symbol.
- **Refuse any symbol held before.** It would stop the machine every time a name is re-entered,
  which the live book has already done once.
- **Keep the symbol, skip fills older than the latest SELL.** A heuristic about ordering that the
  order id answers exactly.

## What would overturn this

A holding built from two of our entries at once. This system holds a name at most once at a time,
so an earlier entry's shares are sold before a later one can fill; if that stops being true, the
holding is the SUM of several entries and taking the most recent one's stop is wrong.

## Consequences

| clause | where it lives | enforced by |
|---|---|---|
| the holding's order is found by the id its buys settled | `adoption.py :: opening_entry` | `test_the_opening_entry_is_the_latest_of_our_orders_to_fill_dated_by_its_first_share` |
| dated by that order's first share, not the symbol's first fill | `cli.py :: _sync_fills` | `test_a_name_held_twice_is_adopted_from_its_own_entry_not_the_first_positions` |
| the stop is that order's, never the latest order sent | the same | `test_the_stop_comes_from_the_entry_that_filled_not_the_latest_order_sent` |
| a stranger's buy in a name we traded is untraceable | the same | `test_a_hand_bought_holding_in_a_name_we_once_traded_is_not_adopted` |

**Seven mutants of the change were run and all seven were caught** — among them dating by the
symbol again, reading the stop from the latest order again, counting a sell as an entry, and taking
the oldest of our entries. One survived the first version of the tests (a sell counted as an entry)
and the unit test was given a partial sale of ours as the latest fill in the name.
