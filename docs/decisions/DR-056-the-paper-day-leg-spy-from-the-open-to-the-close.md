# DR-056: the paper day leg — `SPY` from the opening auction to the closing auction, so the paper account carries the whole book

```
date:            2026-09-27
status:          accepted — the owner ruled on 2026-09-27 (DR-055) that proof (2) is sixty paper
                 sessions of the WHOLE book, and that SPY may be held through a paper session
                 without a stop on DR-055 section 4's terms. This record says how, and sets no
                 threshold the owner has not
parameters:      none new. The day leg's size is the book's own - the equity the night leg frees at
                 the open - which is PR-035's book as registered, not a new number
components:      none new
implemented_by:  tools/card002_paper.py :: morning_pass
```

## 1. What the paper account does each session, once this is built

| ET | pass | orders |
|---|---|---|
| 15:30-15:48 | **close** | if `SPY` is held and no market-on-close sell for it is resting, lodge one; then price last night, and buy `IJR` and `VB` in the closing auction (`DR-054`, unchanged) |
| after 19:00 | **exit** | sell the night's `IJR` and `VB` in the next opening auction (`DR-054`, unchanged), **and buy `SPY` in the same auction** with the equity that sale frees |
| 09:40-15:40 | **morning** (new) | read what the `SPY` buy filled, by our own id, and lodge a market-on-close sell for exactly that |

**The same dollar twice, as `PR-035` measured it.** The opening auction sells the small caps and buys
`SPY`; the closing auction sells `SPY` and buys the small caps.

## 2. The size of the day leg is the book's, not a new number

`SPY` is bought with what the night leg frees: the venue's cash plus the value of this card's `IJR`
and `VB` at their last close, divided by `SPY`'s close that session, rounded down. **Never more than
the equity**, so the card never borrows across the auction even though the venue's buying power
would let it. While `CARD-001`'s last positions are open the day leg is smaller by their value, as
the night leg already is (`DR-054` §5).

## 3. The protection, and the one window without it

`DR-055` §4's terms: `SPY`, opening cross to closing cross, a market-on-close sell for the whole
position resting from the moment the buy is known to have filled. **The venue cannot accept that sell
before the buy exists**, so there is a window from 09:30 until the morning pass runs in which the
position holds no exit order. The morning pass runs at 09:40 ET to keep it to minutes; the close pass
checks again before 15:48 and lodges the sell if the morning pass did not, because a `SPY` position
left without one would be held into the night - a night leg nobody decided. **Held past the close,
it is an ALERT**, exactly as a night leg still held at the next close is.

## 4. The order shape

`registry/broker_policy.yml` gains the day leg's own symbols and times: `day_symbols: [SPY]`,
bought `opg` and sold `cls` - the night leg's times reversed. `AlpacaClient.submit_night` chooses by
the symbol, and refuses a symbol that is in neither list; `submit` is still untouched.

## 5. What this does NOT change

`DR-054`'s ownership rule - the ledger's ids and quantities - covers the day leg without change, so
`CARD-001` still sees the venue less exactly what this card holds. The kill switch governs every
order. Nothing here reaches the owner's real account (`DR-055` §1.2).

## 6. How it is enforced

| clause | enforced by |
|---|---|
| §1's three passes and their windows | `tools/card002_paper.py`, its tests, and a third scheduled task |
| §2's size | `tools/card002_paper.py :: day_size` and its tests |
| §3's protection and its ALERT | the morning pass, the close pass's check, and tests that leave a filled buy with no sell |
| §4's shape | the policy's `day_*` keys, `policy.load`, gate 39, and `submit_night`'s symbol check |
