# DR-033: The venue prices in pennies, and rounding is never allowed to flatter

```
date:            2026-09-02
status:          accepted — forced by the venue, ruled by DR-027 §3.1's existing argument
parameters:      none. The increment is the VENUE's rule (SEC Rule 612) and lives in the committed
                 policy beside the host; the rounding DIRECTION is derived from DR-027 §3.1 rather
                 than chosen
components:      none new
implemented_by:  src/swingdesk/broker/submit.py :: def to_tick
                 the increment is registry/broker_policy.yml write.tick_size, loaded by
                 src/swingdesk/broker/policy.py :: def tick_for
built:           2026-09-02
```

## 1. The first four orders this system ever sent were all rejected

2026-09-02, run `run-20260903T033910Z-d561a5e0`. Everything worked: 105 `Trade` decisions, the caps
took four, the guards passed, the payloads were built and reached the venue. All four came back
`422`:

```
AIS   invalid limit_price 66.949997.  sub-penny increment does not fulfill minimum pricing criteria
DINO  invalid limit_price 106.059998. sub-penny increment ...
BFH   invalid limit_price 106.480003. sub-penny increment ...
BTSG  invalid take_profit.limit_price 65.72569193187650639356166246. sub-penny ...
```

**The pipeline was right and the wire format was wrong.** `66.949997` is the vendor's close, carried
through the sizing at full precision because every price in this system is a `Decimal` and nothing
had reason to round one. The take-profit is worse: `entry + 1.0 × risk_per_share` where
`risk_per_share` is itself `entry - stop + costs`, so it arrives with twenty-six decimal places.

**This is the third defect only a real order could find**, after `DR-027` §9.1 (a bracket is a chain
of three) and §9.2 (the session is the exchange's, never a clock's). Every test passed before and
after; a fixture price is whatever the fixture author typed, and nobody types `66.949997`.

## 2. The increment is the venue's, so it lives beside the host

SEC Rule 612 forbids sub-penny pricing for a US equity quoted at or above $1.00; below that the
increment is $0.0001. That is a fact about the market this venue serves, in the same class as *which
host is the paper one* — not a threshold this project chose. So it sits in
`registry/broker_policy.yml` under `write`, where changing it is a commit a reviewer sees, and
**not** in `registry/parameters.yml`, which would claim this project authored it.

**The sub-dollar increment is declared although it is unreachable.** `universe.min_price` admits
nothing under $5. A rounding rule that silently did the wrong thing below a dollar would be waiting
for the day that floor moves, and a test asserts it now rather than then.

**Quoted as strings in the YAML and parsed to `Decimal`.** `0.01` is famously not representable as
a float, and a tick that is almost right is a tick that fails on the one price where it matters.

## 3. The direction is ours, and it is the half that matters

Snapping to a tick is arithmetic. **Which way** it snaps is a decision, and `DR-027` §3.1 already
made it: a fill above the price the sizing was computed against makes the reported `R` a fiction in
the flattering direction, permanently, on the one statistic the whole validation programme is
measured in.

So every leg rounds toward the side that makes the submitted trade **no worse** than the sized one:

| leg | direction | why |
|---|---|---|
| entry limit | **down** | it can then only fill at or below the decision price — §3.1's argument strengthened rather than weakened |
| stop | **up** | nearer the entry risks *less* per share than planned, so realised R can never exceed the frozen one |
| take-profit | **down** | a nearer target asks less of the trade than planned |

`to_tick` therefore takes an explicit `favouring` argument rather than calling `quantize` with a
default. `ROUND_HALF_EVEN` would round `66.945` **up**, and the mutation that swaps the direction in
for it kills five tests.

**The rounded risk is smaller than the planned risk, never larger.** `shares` was sized against the
unrounded numbers, so after rounding the position risks at most what the sizing intended — which is
the only direction that is safe to be wrong in.

## 4. Rounding may not produce an order with no R denominator

Two legs a fraction apart can collapse onto one another once snapped. `entry_order` refuses both
cases **before the wire**, because finding out from a `422` is finding out in the most expensive
place:

- a stop that rounds up onto the limit — the position's R denominator would be zero;
- a take-profit that rounds down onto the limit — an instruction to sell at a loss on the way up,
  and one tick of rounding is not a reason to send it.

## 5. What this does NOT change

- **No decision moves.** Rounding happens in `broker.submit`, below `application`. The pipeline's
  prices, `R`, `output_hash` and the funnel are untouched — this is a wire-format transformation on
  the way out.
- **`sizing` still owns the price.** `entry_order` does not choose a limit; it snaps the one it was
  handed, in a direction argued from an existing record.
- **The 113 journalled rows from the rejected run stand.** They are the evidence this happened, and
  `DR-027` §8 keeps every attempt including the ones that failed.

## 6. What would overturn this

- **A venue with a different increment**, or one that varies by instrument. `tick_for` reads two
  values from the policy; a venue publishing a per-symbol tick would need it fetched rather than
  declared.
- **A fill materially away from the rounded limit.** `DR-027` §7 already makes that a
  stop-submitting condition; this record adds at most one tick to the gap it would report.
- **Fractional shares.** `DR-027` §2 refuses them, and a venue permitting them would make the
  rounded price interact with a rounded quantity — two roundings whose directions would have to be
  argued together rather than separately.
