# DR-048: the overnight card runs as two auction passes, and its first twenty sessions are hand-entered

```
date:            2026-09-21
status:          accepted — ruled by the owner 2026-09-21, asked which way the twenty REAL
                 sessions reach the exchange. The answer: "гибрид: бумага автоматом, реал руками"
parameters:      none set here. registry/parameters.yml already carries overnight.position_pct
                 (50, owner) and overnight.risk_unit_lookback (14)
components:      none new
implemented_by:  tools/card002_plan.py :: PLAN
```

## 1. What was ruled

**`CARD-002` runs on two accounts at once, and they are not the same decision.**

1. **The paper account is driven by this system**, automatically, under `CHARTER` A-002 §1 — a
   venue holding none of the owner's capital may be given an order no human approved order by
   order. That is what proves the machinery.
2. **The real account is driven by the owner**, order by order, from a plan this system prints.
   `CHARTER` A-001 §1 and A-002 §2 are untouched: the human reaches the final trading decision on
   any venue that can move their money, and typing the order IS that decision.

**No charter amendment is needed, and that is the point of choosing this shape.** The alternative
the owner was offered — letting the system submit to the real account — would have required
amending A-002, which has held since 2026-09-01 and rests entirely on gate 39's single-host
allowlist. The hybrid buys the measurement without spending that.

## 2. Why the twenty sessions are real and not paper

`CARD-002` §2 states the trial's product: **not "does it earn" — that is measured — but what the
closing and opening auctions actually give.** `PR-034` priced them at half a cent and a whole cent
a share and could observe neither.

**A paper trial cannot answer it.** Alpaca's paper fills are simulated, so a paper account would
return this project's own cost assumption dressed as a measurement. The owner ruled on 2026-09-20
that the first twenty sessions run at **minimum real size** — one or two shares a fund. An auction
clears at one price for one share and for a thousand, so the minimum measures it exactly, at a few
hundred dollars of exposure.

**And `PR-036` raised what rides on that number**, the night before this was ruled. Over 2004-2015
the night paid — 10.6% compounded against holding's 8.8%, at a third of the drawdown — but at a
**whole cent** a share the interval touches zero. Half a cent is an effect; a whole cent is
nothing. **The fill measurement is no longer a detail of the card; it is the open question of the
whole line.**

## 3. The two passes, and the third that reads

| pass | when, ET | what it does | account |
|---|---|---|---|
| **plan** | 15:35-15:45 | sizes both funds from the prior close, prints the owner's hand-entry card, writes the plan | reads only |
| **close** | the same window | submits two `cls` market buys | **paper** |
| **evening** | after 19:05 | submits an `opg` market sell for each filled position | **paper** |
| **reconcile** | after the open | reads what closed, journals the night, compares each fill with that session's official auction price | reads only |

**Only the first exists today** (`tools/card002_plan.py`). The rest are `CARD-002` §6's list and
are tracked in `TODO`; this record specifies them so the code that follows has a specification to
follow, which is `CHARTER` A-001.

**The clocks are the venue's, not a preference.** Alpaca accepts `cls` only before 15:50 and `opg`
only before 09:28 or after 19:00, so the windows above carry ten minutes and five minutes of slack
respectively. A pass that misses its window does not place a late order: it refuses and says so.

## 4. What the policy must gain before the close pass is built

`registry/broker_policy.yml`'s `write` block fixes `time_in_force: day` and
`protect_time_in_force: gtc`, and `broker/alpaca.py :: submit` sends **a bracket** — a limit, a
stop leg and a target leg, because `DR-027` §3 requires all three for an entry it protects.

**This card sends none of that.** It sends a plain market order with `cls` or `opg` and no legs.
So the close pass needs its own policy block and its own adapter method, and **it must not reuse
`submit`**: widening `submit` to sometimes omit the stop would weaken the guard that protects
`CARD-001` as a side effect of adding a second card. A new method with its own block cannot.

## 5. Why there is no stop, ratified

`DR-027` §3.2 requires the stop to exist at the venue from the moment the fill does. **That rule
was written for a position exposed to a market that is open**, and `CARD-002` §4 argues the
exception: this position is held only while the exchange is shut, the first moment a protective
order could execute is the opening auction, and the opening auction is when this card already
sells in full at market.

**The exception is ratified here, narrowly**: a position whose entire holding period falls between
a closing auction and the next opening auction, carrying a resting market-on-open exit for its full
size, satisfies `DR-027` §3.2. Anything that can be executed against while the market is open keeps
the stop. **What it does not protect against is the overnight gap**, which is the card's whole
exposure and its whole edge — `PR-034` measured a −31.6% worst drawdown and `PR-036` a −21.1% one
in the older decade.

## 6. What the owner receives, and what they hand back

**The plan pass prints a card the owner can type from**, in the shell the owner actually uses
(`cmd.exe`), naming the symbol, the whole-share count, the order type and the cut-off for each of
the two moments. It refuses a fund whose prior close is missing or stale rather than guessing one —
`FAIL_CLOSED_POLICY` §3, and `CARD-002` §3's data row.

**The plan pass reads the store, so the store must be current.** It runs at 15:40 ET and the
evening fetch runs at 18:30, so it reads whatever the last evening left. On its first live run
(2026-09-20) that store had `VB` a session behind - the vendor had served Friday's close as `NaN`,
the documented not-yet-published condition - and the pass refused `VB` and planned `IJR` alone.
**That is the fail-closed rule working, and it is also a precondition**: a fetch of the two funds
precedes the pass, or a fund is refused for a reason a two-second request would have removed.

**The fills come back by hand, because they cannot be read.** The real account is not on the
allowlist and gate 39 fails the build on a second host, so this system cannot see the owner's real
fills at all. The reconcile pass therefore takes them as input. **That is a deliberate cost of the
hybrid** and is recorded here so nobody later reads the gap as a defect.

## 7. What this does NOT change

A-001 §1 and §2 on any venue that can move real money. A-002's paper boundary and its single-host
allowlist. The kill switch (`data/.paper-trading-armed`), which still defaults to stopped and still
governs every paper submission this project makes. `DR-027` §4's four guards. `CARD-001`'s own
rules, which keep their stops. **And `CARD-002`'s validation status stays `Untested`** — a card
earns that on journalled trades, and twenty sessions of fills is a measurement of execution, not a
verdict on a strategy.

## 8. How it is enforced

| clause | enforced by |
|---|---|
| §3's plan pass and its refusals | `tools/card002_plan.py` and its tests |
| §3's clocks | the two SUBMITTING passes refuse outside their own windows. **The plan pass carries no clock** and is not given one: it writes nothing, so running it at the wrong hour costs a printout, and a read-only pass that refuses by the time of day is a pass nobody can use to check tomorrow's sizing tonight |
| §4's separate policy block | a new block and a new adapter method; `submit` is untouched |
| §5's narrow exception | this record, cited from `CARD-002` §4 |
| §6's hand-back | the reconcile pass takes fills as an argument |
| §1's two accounts | gate 39's allowlist, unchanged |
