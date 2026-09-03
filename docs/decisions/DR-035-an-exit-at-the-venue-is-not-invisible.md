# DR-035: A stop that fires overnight held its slot for ever, and nothing said so

```
date:            2026-09-03
status:          accepted — implements DR-027 §7's existing ruling on the submission path
parameters:      none
components:      none new
implemented_by:  src/swingdesk/presentation/cli.py :: agreement = broker_pkg.reconcile
                 the comparison itself is src/swingdesk/broker/reconcile.py :: def reconcile,
                 which existed and was reachable from one caller the scheduler never runs
built:           2026-09-03
```

## 1. The guard looked one way

`DR-027` §11 asks *is there exposure at the venue the caps were not measured against?* and answers
by walking venue → book. `DR-032` narrowed it so our own resting orders stop halting the retry.
Neither can see the opposite direction, and the opposite direction is what an ordinary Tuesday looks
like:

1. A bracket entry fills. `sync-fills` records the position (`DR-031`).
2. Overnight or intraday the **stop leg fires**. The venue closes the position.
3. Nothing records the exit. `closed_on` is written only by `respond` and `record-fill`, both
   commands a person runs, and the scheduled wrapper never runs `broker`.
4. The evening pass reads a venue holding nothing, finds nothing to complain about, and the caps
   count a position that no longer exists.

**For ever.** `risk.max_concurrent_positions` is 4, so after four stop-outs the book is permanently
full and the machine submits nothing again — silently, with no line anywhere saying why. The most
expensive failure this project can have is not a wrong order; it is a system that looks like it is
working and has quietly stopped.

## 2. The check already existed, and so did the ruling

`reconcile` has always asked **both** directions and already words this one:

> the book holds N shares and the venue reports no position. **An exit that happened at the venue
> and was never recorded looks exactly like this.**

And `DR-027` §7 already ruled what to do with a divergence here: *"`broker.reconcile` already
reports an `entry_price` divergence; **on this path it is a stop-submitting condition, not a
note**."*

So nothing is authored. `reconcile` was reachable from exactly one caller — the `broker` command,
which a person runs by hand and the scheduler never runs. This puts it on the only command that ever
runs unattended.

## 3. What now stops a submission

Every divergence `reconcile` reports, because `Reconciliation.agrees` is deliberately false when
anything at all diverged — *"mostly reconciled" is a score*, and `FAIL_CLOSED_POLICY` §3 forbids a
score clearing a critical gate:

| divergence | what it usually is |
|---|---|
| `book_only` | an exit at the venue nobody recorded — **the case this record exists for** |
| `venue_only` | an entry nobody recorded; no risk cap has ever seen it |
| `shares` | a partial exit or a partial fill nobody recorded |
| `entry_price` | the two sides describing different trades. Every `R` is denominated in the book's number |
| `short`, `fractional`, `asset_class` | a position this system cannot describe at all |

The refusal names up to six and says what to do: run `swingdesk broker` for the full comparison,
then `record-fill` or `open-position` until the two describe the same book.

**It runs before `uncommitted_exposure`, not instead of it.** `reconcile` compares positions;
`uncommitted_exposure` additionally sees **live orders**, which are not positions and which
`DR-032`'s exemption is about. The two answer different halves and both are needed.

## 4. What this does NOT do

- **It does not close a position.** Recording an exit is `D6`'s and stays a person's act; this makes
  the omission loud instead of permanent. Automating it is the same shape `DR-031` took for entries
  and is not attempted here — an exit carries a fill price, a commission and a reason, and the venue
  knows one of the three.
- **It does not change the caps.** A position the book carries still holds its slot; what changed is
  that a book which no longer describes reality now stops the run instead of quietly bounding it.
- **It does not touch `broker`.** That command still reports and writes nothing.

## 5. What would overturn this

- **An exit recorded automatically.** Then this stops firing in normal operation and becomes a check
  on that automation — which is when it is most worth having, not least.
- **A venue that reports a closed position as a zero-share holding** rather than omitting it.
  `_compare` would then read `fractional` or `shares` rather than `book_only`; the run still stops,
  but the reason would name the wrong thing.
- **Positions in a currency this venue cannot hold.** `reconcile` already reports those
  `out_of_scope` rather than as divergences, and a `.TO` book would exercise a path that has never
  had a subject.
