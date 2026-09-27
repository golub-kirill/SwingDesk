# DR-054: `CARD-002`'s paper passes, and whose holding is whose on one account

```
date:            2026-09-26
status:          accepted — the owner chose on 2026-09-26 to build the paper passes, with
                 CARD-001 stopping new entries on the first paper submission (CARD-002 §7). The
                 clauses below are how that choice reaches code; none sets a threshold
parameters:      none set here. Reads overnight.position_pct (50, owner) and
                 overnight.risk_unit_lookback (14)
components:      none new
implemented_by:  src/swingdesk/broker/night.py :: CardView
```

## 1. What was ruled, and what this record adds

**The owner's choice, 2026-09-26:** build the two paper passes `DR-048` §3 specifies, so the paper
account carries `CARD-002` at the size ruled on 2026-09-20 — 50% of equity a fund, every night —
and stop `CARD-001` taking new entries the day the first paper order goes out. `CARD-002` §7 had
proposed exactly that and it was accepted with the choice.

**What this record adds is the rule nobody had to write while one card owned the account.** Two
cards now share one venue, and every guard `CARD-001` carries asks the venue *what do you hold*
and treats anything its own book does not carry as a defect. That is correct for one card and
wrong for two, and §3 is why it cannot be left to be discovered.

## 2. The passes, and their clocks

Every clock is read from the exchange calendar for the session, never from a constant, so an
early close moves the window with it.

| pass | window, ET | what it does |
|---|---|---|
| **close** | from 30 to 12 minutes before the session's close — the venue refuses `cls` from 10 minutes before | reconciles last night; refuses both funds if `CARD-002` still holds anything from it; sizes each fund; journals, then submits one `cls` market buy a fund |
| **exit** | after 19:00 on the session's day, or before 09:28 on the next | for each of tonight's buys, reads its filled quantity by our own id; journals, then submits one `opg` market sell for exactly that quantity |
| **report** | any time | the nights journalled, the curve, and holding the two funds beside it |

**A pass outside its window refuses and says so.** It never places a late order: a `cls` sent after
19:00 is an order for the NEXT session's close, and one sent between 15:50 and 19:00 is rejected —
Alpaca's own rules, `DR-048` §3. So the window check is the difference between a missed night and a
position nobody decided.

**The close pass reconciles the previous night before it buys.** One pass instead of a third
scheduled task, and the ordering is the point: the question *did last night's sell fill at the
open* has to be answered before tonight's buy is sized, or a failed exit is doubled.

## 3. Whose holding is whose — the defect this prevents

**`CARD-001`'s submission path stops on any disagreement between its book and the venue, and it
stops BEFORE it restores a protective stop** (`cli.py :: _submit`: the `DR-035` reconciliation
returns ahead of the `DR-037` restoration). An `IJR` holding bought by the close pass is a
`venue_only` divergence to that path. So the first paper night would stop `CARD-001` protecting its
own open positions, every evening, for as long as both cards ran — found while planning this
record, not by a run.

**The rule: `CARD-001` sees the venue minus exactly what `CARD-002`'s ledger accounts for.**

1. **An order is `CARD-002`'s if its client id is in the ledger's `sent` rows.** Not a prefix and
   not a symbol — `reconcile.ours` gives the reason: a prefix test adopts anything a person types
   with the right first word, and a symbol test would hide a person's own `IJR` order.
2. **A fill is `CARD-002`'s if its venue order id is in the ledger's `answered` rows.**
3. **A holding is set aside by QUANTITY**: in each fund, the shares `CARD-002`'s buys filled less
   the shares its sells filled. Whatever the venue holds beyond that stays in `CARD-001`'s view and
   is still a divergence. A holding smaller than the ledger's claim is `CARD-002`'s defect to
   report, never `CARD-001`'s to absorb.
4. **A `sent` row with no `answered` row is healed before it is trusted**: the exit and close
   passes look the order up by its client id and journal what the venue says. Until then its fills
   cannot be attributed, and they stay visible to `CARD-001` — a divergence, which is the loud
   outcome.
5. **An unreadable ledger sets nothing aside, and counts as `CARD-002` having started.** The
   holdings then read as divergences and `CARD-001` stops, which is the behaviour before this record
   and the fail-closed one. Reading it as an EMPTY ledger instead would set nothing aside and let
   `CARD-001` resume entries - and only the first half of that is safe.

**One construction path.** Every command in `cli.py` that reads the venue opens it through
`CardView`, so the rule lives in one place — `DR-053` is the record of what a second copy of an
ownership rule costs.

## 4. `CARD-001` stops taking entries, and keeps protecting what it holds

From the first `sent` row in the ledger, `CARD-001`'s submission path journals every candidate as
stopped with this record's reason and submits nothing. **Everything before that point still runs**:
the reconciliation (through the view), the protective-stop restoration, the stop raises. Its open
positions leave by their own rules and it goes `Retired` in `registry/cards.yml` when the last one
has closed.

## 5. Sizing on the paper venue

**Each fund's notional is `overnight.position_pct` of the venue's `equity`, capped at half the
venue's `cash`. The card never borrows.** Shares are the notional over the prior close, rounded
down; a fund whose prior close is missing or stale refuses as `card002_plan.py` already does.

The cash cap is not a new number. `CARD-002` §3 lists *the account short of cash* as a
cancellation, and while `CARD-001`'s last positions are still open the account's cash is below its
equity by their value. Capping at cash is that cancellation applied proportionally rather than
refusing the night.

**The paper account's equity, not `account.equity`.** That parameter is `CARD-001`'s risk
denominator and the kill switch's baseline, set to the owner's REAL capital. This card's paper
trial exists to show the rule on the whole paper account, which is what the owner asked to see.

## 6. What the paper nights are, and are not

**Paper nights are journalled apart from the real ones**, in `data/card002/paper.jsonl`, never in
`data/card002/executions.jsonl`. Alpaca's paper fills are simulated (`DR-048` §2), so a paper
night's cost is this project's own model returned to it, and mixing the two would contaminate the
one number the twenty real sessions exist to measure.

**What they measure:** the machinery, every night — both orders placed, both filled, nothing held
at the open — and the rule's curve at full size on the paper account. **What they do not:** the
auction's cost. That remains the real sessions' job.

## 7. The kill switch still governs every submission

`DR-048` §7, unchanged. **The consequence is stated, not engineered around:** disarming the switch
between a close fill and the exit pass leaves that night's position without its `opg` sell, and
the next close pass refuses to buy while it is held. Re-arming lets the next exit pass lodge the
sell; otherwise it is sold by hand.

## 8. How it is enforced

| clause | enforced by |
|---|---|
| §2's windows and the reconcile-first order | `tools/card002_paper.py` and its tests |
| §3's view, and that every venue read in `cli.py` goes through it | `swingdesk.broker.night.CardView` and `tests/test_night.py`; a test that `cli.py` constructs no client except through it |
| §3's ownership by id, never by prefix or symbol | tests that plant a person's `IJR` order with our prefix and a person's `IJR` holding |
| §4's retirement | `cli.py :: _submit` and a test with a ledger holding one `sent` row |
| §5's sizing | `tools/card002_paper.py :: size` and its tests |
| the new order shape | `registry/broker_policy.yml`'s `night` block, gate 39, and `AlpacaClient.submit_night` — `submit` is untouched (`DR-048` §4) |
