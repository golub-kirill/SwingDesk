# DR-009: The owner's actual broker charges no commission, and the cost model never knew

```
date:       2026-08-11
status:     proposed
parameters: risk.costs_allowance
components: none - swingdesk.trade_management.sizing reads it; this sets its input
supersedes: nothing. DR-004's commission model stands as a MODEL; this records that it does not
            describe the account this system is actually preparing decisions for.
```

`DR-004` models commission as **2 × $0.005 per share** and slippage as a percentage of price.
`DR-005` replaced the slippage half with a measurement. The commission half was never checked
against a broker, because until 2026-08-11 no broker had been named.

The owner's broker is **Wealthsimple**, and its published schedule charges **no commission on
stock trades**. What it charges instead is a **1.5% currency conversion fee** on CAD↔USD, applied
per filled order when US-listed securities are traded from a CAD account.

So the model was wrong in both directions at once: it charged a commission that does not exist, and
it omitted a conversion fee that can exceed every other cost combined.

## 1. Three structures, not one

Slippage of **25bp per side** (`DR-005`) applies throughout. The rest depends entirely on which
account holds which market:

| | Round trip | at $5 | at $20 | at $50 |
|---|---|---|---|---|
| **A. TSX from a CAD account** | 50bp | $0.025 | $0.10 | **$0.25** |
| **B. US from a CAD account** | 50bp + **300bp** | $0.175 | $0.70 | **$1.75** |
| **C. US from a USD account** | 50bp, conversion once at funding | $0.025 | $0.10 | **$0.25** |

**Structure B is excluded, and the arithmetic is not close.** `DR-005` established that break-even
requires costs under **6.85bp per side**. B's conversion fee alone is 150bp per side — **twenty-two
times the threshold**, before any slippage. No parameter setting reaches break-even through it, so
excluding B is not a preference between viable options; it is the removal of one that cannot work.

**Owner decision, 2026-08-11: A and C.** TSX traded from the CAD account, US traded from a USD
account. Both carry the same per-trade structure, which is why one parameter can serve both.

## 2. What is set

```
risk.costs_allowance = 0.25    provenance assumed:DR-009
```

Derived, not chosen: 50bp round trip against a **$50 reference price**. The reference is the
conservative end of the admissible range rather than its floor, and the direction matters.

`sizing.py` computes `risk_per_share = entry − stop + costs`, so a **smaller** allowance produces
**more** shares. Understating costs therefore understates risk, and the position silently exceeds
1R. Overstating them costs opportunity and nothing else. Where the error cannot be eliminated it is
pointed at the side that fails closed.

## 3. Two limitations, recorded rather than resolved

**It is a flat constant, and the cost it represents is proportional to price.** At $5 the true
figure is $0.025 and this parameter charges $0.25 — ten times too much, which suppresses position
size on cheap instruments. At $200 it charges a quarter of the truth. The honest fix is a
price-aware cost model, which is a change to `sizing.py` — the daily-run code path, frozen until
the Track A counter has five clean days (owner rule, 2026-08-11).

**It is one number spanning two currencies, and `AGENTS.md` §3 says they are never merged.**
`sizing.py` contains no reference to currency at all: `entry − stop + costs` adds this constant to
prices denominated in whichever currency the instrument carries. A CAD instrument and a USD one
receive the same allowance. The exchange rate has moved less than the modelling error already
present here, so this is second-order today — but it is a real violation of the separation rule and
it is written down rather than discovered later. A per-currency allowance needs the same code change
as the price-aware model, and should land with it.

## 4. What this does not establish

`assumed`, not `validated`. The slippage input is `DR-005`'s, which HANDOFF §3 instructs be read as
*"materially more than 5"* rather than as a measurement of 25 — three OHLC estimators agree only
inside their shared noise floor, and `PR-006` (real fills) remains the only route to the level.

The commission and conversion figures come from the broker's published schedule, which is a fact
about a fee table rather than evidence about this system. A published rate is not a measurement of
what this account will actually pay: partial fills, order types and the rate embedded in each
conversion all move it.

**Consequence for the strategy record: none, and that is deliberate.** `PR-005`'s recomputation
under `DR-005` used DR-004's commission model. Removing a $0.01-per-share commission moves the
result in the strategy's favour, and re-running it here — as an unregistered analysis, in the record
that also chose the parameter — is exactly the shape of a result nobody should trust. It needs a
pre-registration or it needs to stay unquantified. It stays unquantified.
