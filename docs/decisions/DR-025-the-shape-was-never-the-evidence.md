# DR-025: The look-through's shape carries no information about holdings, so the guard stops reading it

```
date:            2026-08-31
status:          accepted — ratified by the owner 2026-08-31
parameters:      none. No threshold is introduced and none is needed — §4
components:      reference_data.classification:look_through
supersedes:      DR-021 §4 (the shape as a trigger), and with it DR-006 §8.7's inference.
                 DR-021's measurement and its correction of §8.7 stand; only its RULE is replaced
implemented_by:  src/swingdesk/reference_data/classification.py :: def look_through
built:           2026-08-31, in the restart window the owner granted for this date
```

## 1. What killed the inference, and it is a measurement

`DR-006` §8.7 refuses a fund whose look-through is one sector at exactly 100%, reading that shape as
*this fund holds no equity*. `DR-021` kept the shape as a trigger and added the vendor's equity share
as a discriminator.

**Both rest on the shape meaning something. It does not.** Measured 2026-08-31 over 35 funds:

> The vendor's `sector_weightings` sum to **1.0000 for every fund, regardless of what it holds** —
> including every one of the ten funds that report **0% equity**.

The weights are normalised over whatever the vendor could classify, not over the fund's assets. A
fund that is 7.4% equity still reports weights summing to 1; so does one that is 0% equity. **The
shape is a property of the vendor's normalisation, not of the fund**, and it never carried the
information §8.7 read out of it.

What it did carry was a cost: five of the eleven SPDR Select Sector funds report exactly one sector
at exactly 100% and are 99.7%+ equity, and 23 admitted members of the live universe sat refused —
which, under `DR-006` §3's admit-on-unavailable, means admitted with **no sector charged at all**.

**And the inference was held to a lower bar than the thresholds this project forbids.** *"One sector
at 100% implies no equity"* is an invented rule with no citation and no study. A numeric threshold
would have been refused at the door.

## 2. The decision

**The shape is not consulted. A fund is refused when, and only when, the vendor positively reports
that it holds 0% equity.**

`NEAR` — the bond fund §8.7 was written about — answers 0.0% in the same response as its healthcare
100.0% look-through. That is evidence about the *fund*. The shape never was.

### 2.1 `None` does not refuse, and that is the reverse of `DR-021`'s asymmetry

`DR-021` §4 made silence refuse: *"absence is not evidence of equity, and this is the fail-closed
direction."* **That reasoning is inverted here, and the inversion is the point.**

A refusal reports `unavailable`. `DR-006` §3 **admits an unavailable candidate unchecked**. So in
this system a refusal is the *permissive* outcome, and widening the refusal is the dangerous
direction — not the safe one. Refusing on silence would hand every unanswered fund a free pass past
the sector cap.

`DR-021` had the fail-closed polarity backwards because it was reasoning about the guard in
isolation rather than about what a refusal costs downstream.

## 3. What this changes, measured

On the live universe of 1,186 members:

| | today | ruled |
|---|---|---|
| sector spendable | 1,018 | **1,041** |
| refused by the shape | 23 | 0 |
| refused on a declared 0% equity | — | the subset that answers zero |
| no sector served / nothing stored | 145 | 145 |

The 23 stop being refused for a reason that is false for most of them. Of the 23, ten answer exactly
0.0000 equity and stay refused on their own evidence (`NEAR`, `BNDW`, `BNDX`, `UITB`, `FIXD`, `BOND`,
`ANGL`, `BCI`, `CARY`, `COMT`); thirteen carry positive equity and charge their sector.

**Every part of that moves in the conservative direction** — more sector charged, never less.

## 4. The look-through is NOT scaled by the equity share

The obvious next step is to charge `weight × equity_share`, which is arithmetically right for a fund
holding cash. **It is rejected, and the reason is `AAPU`.**

`AAPU` is Direxion Daily AAPL Bull 2X: ~15% Apple stock, a ~12.6% Apple swap, ~67% Treasury
collateral. It reports `stockPosition` **0.074** while being economically **2× Apple — 200%
technology**. `stockPosition` measures **physical equity, not economic exposure**, and scaling by it
would undercharge the single most concentrated instrument in the universe by roughly **27×**, in the
permissive direction.

No threshold repairs a field that measures the wrong quantity, which is also why `DR-021` §5's *"no
tolerance"* promise could not be kept by a floor: the measured distribution runs continuously from
`BINC` 0.0001 through 0.074, 0.160, 0.172, 0.317 to 1.000, with no break.

**So funds that over-charge their sector are left over-charging.** `BINC` (0.01% equity) charges
100% financial services; `ALLW` (21% equity) charges 100%. Both are fictions and both err the safe
way: they bind the cap early and cost an entry, where undercharging costs the cap itself.

### 4.1 The dissent, recorded because it is the strongest objection

This was put to a five-advisor council on 2026-08-31. The reasoning that carried it — that the
budget is denominated in **R**, measured on the instrument's own chart, so leverage is already
inside it and the look-through only ever had to answer *which sectors* — was judged strongest by two
of three reviewers.

**The dissent is that it is half-true.** R contains leverage for *sizing*; it does not for *sector
aggregation*. A 1R `AAPU` position and a 1R `XLK` position charge technology identically, while
`AAPU`'s economic technology exposure is twice `XLK`'s and its gap behaviour is not `XLK`'s. That
seam is real, it is not closed here, and `TODO.md` carries it.

## 5. What this does NOT do

**It does not touch `DR-006` §3's admit-on-unavailable.** The council was unanimous that a cap which
fails open is not a cap, and that flipping it is the deeper fix. It is a ratified rule, and the peer
review named two costs nobody had priced: a vendor outage or schema change becomes a **book-wide
halt** with no staleness or last-known-good policy, and refusing instruments mid-position produces a
book the guard says cannot exist — a migration, not a branch. That is the owner's, and `TODO.md`
carries it with those costs.

**It does not fix the selection effect.** Refusing on any basis tilts the universe toward funds the
vendor happens to classify, and the cap never measures that. Raised in review; unaddressed.

**It does not remove `equity_share`.** The field stays: it is the evidence that killed the shape
inference, it is what refuses `NEAR` on the fund's own answer, and it is the seed of an instrument
registry — ticker to asset class, leverage factor and economic exposure — that would let the guard
charge `AAPU` what it actually carries.
