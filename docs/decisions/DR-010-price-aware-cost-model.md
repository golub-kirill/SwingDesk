# DR-010: Sizing costs are price-aware and currency-aware, not one flat constant

```
date:            2026-08-13
status:          accepted — ratified by the owner 2026-08-13
parameters:      risk.costs_bp_usd, risk.costs_bp_cad, risk.costs_floor_usd, risk.costs_floor_cad
components:      none - swingdesk.trade_management.sizing reads them; this sets their input
supersedes:      DR-009 section 2 (the single risk.costs_allowance = 0.25 parameter)
implemented_by:  registry/parameters.yml :: assumed:DR-010
```

## 1. What DR-009 got right, and the one thing it flagged and shipped anyway

`DR-009` correctly identified the broker's actual fee structure — no commission, a 1.5% CAD↔USD
conversion fee — and correctly excluded account structure B on that basis. Both stand unchanged.

It also set `risk.costs_allowance = 0.25`, a single flat currency-per-share constant, and recorded
its own two limitations honestly in the same document: it is a flat number charging a proportional
cost, and it is one number spanning two currencies the project's own non-negotiable rule says are
"never merged." Both were named as debt at the time, with the fix deferred behind `sizing.py`'s
freeze. This decision pays that debt down, not by re-deriving new numbers from nothing, but by
reshaping the one number DR-009 already derived into a form that is honest at more than one price.

## 2. What was wrong with one flat number

`risk_per_share = entry − stop + costs`. A **smaller** `costs` value produces **more** shares —
understating cost is the unsafe direction, since the position silently exceeds 1R of intended risk.

A flat $0.25/share charges the same amount regardless of price. At DR-009's own $50 reference this
matches its 50bp round-trip derivation exactly. Off that reference it does not:

| Price | 50bp round trip (the true figure) | Flat $0.25 charged | Error |
|---|---|---|---|
| $5   | $0.025 | $0.25 | **10× too much** — suppresses size on cheap instruments |
| $50  | $0.25  | $0.25 | exact |
| $200 | $1.00  | $0.25 | **a quarter of the truth** — permits an oversized position |

The $200 direction is the dangerous one. Sizing something proportional to price is the obvious fix —
but proportional-only is *also* wrong, in the same dangerous direction, at the other end of the
range: spread on a cheap instrument behaves like a fixed minimum, not a fraction of price. A pure
`bp × price` term at $5 and 50bp charges $0.025 — understating a real, non-trivial fixed cost
component that does not shrink just because the share price did.

Neither term alone is honest across the range this project trades. Both together are:

```
costs_per_share = max(floor_per_share, bp / 10_000 × entry)
```

The floor protects the cheap end (the term price cannot rescue); the proportional term protects the
expensive end (the term the flat constant could not reach). Below the crossover price
(`floor / (bp/10_000)` — **$50 at 50bp and a $0.25 floor**, which is exactly the reference point
DR-009 was built from) the floor governs and pricing is unchanged from today. Above it, the
proportional term takes over and finally charges what DR-009 already admitted it should.

## 3. Why two currencies, not one

`sizing.py` had no currency handling at all. A CAD instrument and a USD instrument received the same
number, in whichever currency each priced in — the exact violation `AGENTS.md` 3 names as
non-negotiable. `risk.costs_bp_usd` / `risk.costs_bp_cad` and `risk.costs_floor_usd` /
`risk.costs_floor_cad` are set to the same numeric value on both sides of this decision, because
DR-009 measured structures A (TSX from CAD) and C (US from USD) at the same ~50bp round trip with no
conversion leg on either — not because one number was reused, but because two independent
measurements happened to agree. `size_long` now takes an explicit `currency` argument and refuses,
rather than guesses, for any currency without a parameter pair (`AGENTS.md`: unset is not default).

CAD is not reachable from the live universe yet — `reference_data.universe.to_instrument` only
produces `USD` until Canada is unblocked (`DR-003` gap 1). The CAD parameters are set now anyway, so
the day Canada lands, sizing does not silently merge currencies for want of a value.

## 4. What this still does not establish

Both terms remain `assumed`, not `validated`. `risk.costs_bp_*` restates DR-005's measured slippage
honestly — "materially more than 5bp," per `HANDOFF.md` §3's own instruction for reading that figure
— rather than treating 25bp (one side) as a precise input; 50bp is the round-trip framing DR-009
already used. `risk.costs_floor_*` is DR-009's original constant, unrevalued: no per-currency floor
has been separately measured, so the same number is carried in each currency's own units rather than
invented fresh or shared cross-currency.

This is not the study that resolves the sign of the base strategy. `PR-007` — registered
2026-08-05, blocked on a ten-year re-fetch — measures expectancy net of costs directly, over the
same 68 instruments and window as `PR-005`. This parameter change is what `sizing.py` charges in the
meantime; it is not a substitute for that measurement, and does not report on it.

## 5. What DR-009 keeps

`DR-009` is not superseded wholesale. Its account-structure content — the fee schedule, the
exclusion of structure B, the choice of A and C — is unchanged and remains the record for that
decision. Only its parameter-setting role (section 2) moves here. See the correction appended to
`DR-009` itself.

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| Keep the flat constant, revalue it | No single value is honest at both $5 and $200; the debt DR-009 named would just be renamed, not paid |
| Proportional only (`bp × entry`), no floor | Understates cost on cheap instruments, in the unsafe direction — a $30 stock at 50bp charges $0.15 against the $0.25 DR-009 already judged conservative |
| One currency-merged parameter, price-aware | Fixes the price problem, keeps the currency problem `AGENTS.md` 3 forbids |
| A price validity band that refuses outside $25–$100 | Refuses on the wrong variable. Price is not what is uncertain; the cost basis for that currency is. A correctly-sized $200 trade would be refused while a mis-sized $30 one passed. Refusing when `costs_bp`/`costs_floor` is unset for the currency achieves the same fail-closed intent on the variable that is actually missing |
| Wait for `PR-006` (real fills) before touching `sizing.py` | `PR-006` is not written — reserved by `DR-004`, blocked on live trading, which is blocked on Track A, whose counter has barely started. Waiting makes this decision permanent-by-neglect rather than interim |
| Wait for five clean daily runs before lifting the freeze | The freeze's own criterion (`a.run_completes`) measures whether the daily run *completes*, not whether sizing is correct — it was never protecting this. The counter is near its start; the cost of the edit only grows the longer it waits |

## What would overturn this

- `PR-007` reports expectancy net of these costs. If the aggregates do not reproduce or the sign
  question resolves, the parameters this decision sets do not change on their own, but the
  strategy conclusion built on top of them does.
- Real fills (`PR-006`, whenever paper trading exists to produce them) replace either term with a
  measured value. Until then both stay `assumed`.
- A per-currency floor is separately measured. Today's shared numeral is a placeholder carried
  from one constant, not two independent measurements.

## Consequences

1. `risk.costs_allowance` is retired — left in the registry, `value: null`, `status: unset`, so the
   id stays findable from `DR-009` and prior history rather than vanishing (`AGENTS.md` §11:
   corrections supersede, they do not delete).
2. `size_long` requires a `currency` argument. Every call site names it explicitly; there is no
   default.
3. `sizing.py`'s freeze is lifted for this one edit, by owner decision 2026-08-13, ahead of the
   five-clean-run threshold — recorded here because the freeze rule itself is a standing decision
   and this is a deliberate, dated exception to it, not a silent bypass.
