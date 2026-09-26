# DR-053: the legs of our own resting bracket are not foreign exposure — the 19:30 retry stopped on every evening the 18:30 pass traded

```
date:            2026-09-26
status:          accepted — a defect found in the audit the owner asked for on 2026-09-26, measured
                 in the journal before it was fixed
parameters:      none
components:      none new
implemented_by:  src/swingdesk/broker/reconcile.py :: _sent_by_us
```

## Decision

**An order at the venue is ours if its own client id is one we journalled, OR if it is a leg whose
parent's id is.** `uncommitted_exposure` now asks that question, and so does the stop-raise
ownership check, through one function — they were two copies of the rule and only one was right.

A leg whose parent is not ours is still exposure, and still stops submission.

## What was wrong, measured

`uncommitted_exposure` excluded a live order from *"exposure the book does not carry"* only when the
ORDER'S OWN client id was in the journal. A bracket this system sends comes back from
`open_orders` as the parent and its two legs, flattened (`DR-036`, since 2026-09-04), and each leg
carries an id the venue generated. So the legs of our own unfilled entry read as somebody else's.

**The journal, every run that stopped on it** (`submissions`, grouped by run):

| evening | 18:30 pass sent | 19:30 pass | named |
|---|---|---|---|
| 2026-09-07 | 2 entries | stopped 392 candidates with `TECH: the venue holds 2 symbol(s) this system's book does not carry` | `AIS`, `PTF` — exactly the two sent |
| 2026-09-22 | 4 entries | stopped 313 with `TECH: the venue holds 4 symbol(s) …` | `AIS`, `LPG`, `MPC`, `PAYS` — exactly the four sent |

**Two of two**: every evening on which a first pass sent entries and a second pass ran, the second
pass stopped on the first pass's own orders.

**What it cost so far: no trade.** On both evenings the first pass had already filled
`risk.max_concurrent_positions` (4), so the retry had no room. **What it cost structurally: the
retry pass `DR-015` exists for could never add a name on a day the first pass traded**, and each
such evening wrote hundreds of `TECH` rows into the journal that were not true.

## Five whys

1. **Why did the 19:30 pass stop with `TECH` on 2026-09-22?** `uncommitted_exposure` named `AIS`,
   `LPG`, `MPC` and `PAYS` as held at the venue and absent from the book.
2. **Why those four?** They were the 18:30 pass's entries, resting unfilled — the venue listed each
   as a parent and two legs.
3. **Why were the legs foreign?** The check read only the order's own client id, and a leg's is the
   venue's. `DR-043` (2026-09-15) gave every flattened leg its parent's id for exactly this reason,
   and it was applied in the stop-raise check and nowhere else.
4. **Why did no test catch it?** `test_our_own_resting_order_no_longer_halts_the_retry_pass` built
   the resting order as ONE order with our id — an order as this system thinks of it, not as the
   venue returns it. `AGENTS.md` §12's first trap: a fixture built from the same assumption as the
   code is a mirror. It passed throughout.
5. **Why did the audit of 2026-09-21 not find it?** `DR-050` §4 checked *"every other place that
   attributes an order to us"* and recorded that `_uncommitted_exposure` *"skips sells before it
   looks anything up"*. **It does not and never did** — the sell filter (`b2cd4a1`, 2026-09-03) is
   in the caps' count of committed orders, a different function. A claim that something was checked
   is itself a claim (`AGENTS.md` §10.8), and this one closed the search one step short.

**The root, stated so it can be checked elsewhere:** *"is this order ours"* was answered in three
places — the close attribution (`DR-050`), the stop-raise check (`DR-043`) and this exposure check —
and each learned the venue's leg structure separately. Two learned it; this one did not.

## Alternatives rejected

- **Skip every SELL in the exposure check.** What `DR-050` §4 believed was there. A resting sell
  typed by hand in a name the book does not carry is exposure (a short, or a sale of a holding the
  book does not know), and ignoring it is the admit-on-unknown inversion.
- **Match on the `swingdesk-` prefix.** `DR-032` §1 names why not: a prefix is a shape, and a
  person can type it.
- **Leave it, since no trade was lost.** Two of two evenings stopped, and the reason it cost nothing
  is that the caps were already full — the day they are not, the retry is the pass that would have
  added the name, and it would have stopped.

## What would overturn this

A venue that returns legs without their parent — then `parent_client_order_id` is empty, the leg is
exposure again, and the retry stops as before. Fail-closed, and visible in the log.

## Consequences

| clause | where it lives | enforced by |
|---|---|---|
| our legs are ours | `reconcile.py :: _sent_by_us` | `test_our_resting_BRACKET_does_not_halt_the_retry_pass`, built as the venue returns a bracket |
| a stranger's legs are not | the same | `test_a_leg_whose_parent_is_not_ours_is_still_exposure` |
| one rule, two callers | `uncommitted_exposure` and the stop-raise check both call `_sent_by_us` | four mutants, all caught — including restoring the own-id-only test and reverting either caller |

## What this woke up, and it is fixed in the same change

**A retry that no longer stops reaches code that had never run with a resting name in it.** The
19:30 pass sees the 18:30 pass's names come back as `Trade` decisions. `_allocate` offered them
alongside `committed` - our resting orders - so each resting name took a SECOND slot and was sent a
SECOND time. A test built the way the retry actually sees it (one resting bracket for `R1`, and
`R1` and `NEW0` as candidates) sent **`['R1', 'R1', 'NEW0']`** and printed `NOT JOURNALLED R1 ...
Duplicate key`. The venue would have refused the duplicates on their repeated `client_order_id`, so
no position would have doubled; the costs were slots spent on duplicates that a new name could have
had, and attempts that never reached the journal, which `DR-027` §6 requires of every one.

**A name already resting is now spent capacity, not a candidate:** it is taken out of the ranked
list before the walk and journalled as `stopped`, with the reason. The existing slot test had used
fresh names distinct from the resting ones — the second mirror fixture in this record.

| clause | where it lives | enforced by |
|---|---|---|
| a resting name is not offered twice, and is journalled | `cli.py :: _allocate` | `test_the_retry_does_not_offer_again_a_name_already_resting`; two mutants, both caught |

`DR-050` is accepted and is not edited. Its §4 sentence about `_uncommitted_exposure` is corrected
here, and `AGENTS.md` §12's trap on lessons that do not travel records this as its third instance.
