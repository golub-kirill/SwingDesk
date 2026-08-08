# EXECUTION MODEL

**Status:** drafting · **Tier:** 2 (domain) · **Content:** authored, measured against the tree

Master ТЗ §28 requires the rules that turn a decision into a fill to be specified.
`SPEC_GAP_ANALYSIS.md` §2 recorded this as **ABSENT** — `validation/backtest/costs.py` models
commission and slippage and nothing states the execution semantics around them — and §4 ranked it
fourth with a precise justification worth repeating:

> currently latent rather than harmful … It becomes a correctness defect the day a target exists.

This document is written **while it is still free to write**. Every rule below can be stated without
choosing between two results, because no result yet depends on the choice. That stops being true the
moment a profit slot is implemented.

---

## 1. What is executed today

The backtest engine (`validation/backtest/engine.py`) is the only path that produces fills. The live
path has no trigger and therefore no execution at all (`REQUIREMENTS.md` §3).

| Step | Rule | Status |
|---|---|---|
| signal | evaluated on bar `i`, from `bars[:i+1]` only | implemented |
| entry | **next session's open**, `bars[i+1].open` | implemented |
| entry fill | quoted open, moved against the trader by `costs.slippage_model` | implemented |
| commission | `costs.commission_model`, charged both sides | implemented |
| protective exit | stop at `entry − multiple × ATR`, fixed at entry | implemented |
| time exit | close of the session `max_holding` bars after entry | implemented |
| profit exit | **none** | **not implemented** |
| contextual exit | **none** | **not implemented** |

**A decision made on bar `T` executes at `T+1` or it is look-ahead.** The engine enforces this
structurally rather than by convention: the loop stops one bar short of the end so an entry fill
always exists, and there is no path by which bar `i`'s close can both generate and fill a signal.

Slippage is applied to the **fill price**, not deducted afterwards (`DR-004`). The recorded entry is
the price actually paid, so MFE and MAE are measured from a real fill rather than an idealised one.
Deducting at the end gets the P&L right and the excursions wrong.

## 2. The four exit reasons that exist

`ExitReason` has exactly four members, and the set is deliberately smaller than the course's exit
model:

| Reason | Meaning |
|---|---|
| `STOP` | the stop was touched intraday |
| `STOP_GAP` | the session **opened** through the stop |
| `TIME` | maximum holding period reached |
| `END_OF_DATA` | the window ended with the position open |

`EXIT_MODEL_SPEC.md` §1 defines four *slots* — `protective`, `profit`, `contextual`, `time` — from
M58's single repeated standard. **This harness implements the protective and time slots only, and
says so rather than pretending otherwise.** That is the whole reason the ambiguity in §3 is currently
unreachable.

`END_OF_DATA` deserves its own note. A position still open when the window ends is closed at the last
close and **flagged**, never dropped. A dropped open position is a silently removed outcome, and
open positions at the end of a sample are not randomly distributed — they are disproportionately the
trades that were working.

## 3. The intrabar ambiguity, specified before it can occur

**The problem.** A daily bar gives open, high, low and close. It does not give the path. When a
session's low reaches the stop *and* its high reaches the target, the bar is consistent with both
orders of events, and the trade is a loss or a win depending on which came first. Daily OHLC cannot
distinguish them, ever.

**Why it cannot arise today.** There is no profit slot, so no target price exists, so no bar can
contain both. Every current exit is unambiguous:

- `STOP` — one price level; touched or not.
- `STOP_GAP` — the open is already through the stop; the fill is the open and the loss recorded is
  the **actual** loss, not `−1R`. Assuming `−1R` on gaps is the single most common way a backtest
  flatters itself.
- `TIME` — a bar count, not a price.

There is also a guard for the inverse case: when a gap up puts the entry fill at or below the
computed stop, the engine **skips the trade** (`STOP_NOT_BELOW_ENTRY`) rather than opening a position
with non-positive risk per share, which would make every R-multiple derived from it meaningless.

**The resolution rule this project must adopt.** The registry already holds the parameter that
governs it — `exit.slot_resolution_order`, `unset`, cited to M58's standard *"указать количество и
порядок исполнения"* with the note that the course requires an order be stated and does not state
one. So the ambiguity is already represented, and the system fails closed on it rather than guessing.

The candidate resolutions, with what each costs:

| Resolution | Effect | Verdict |
|---|---|---|
| **pessimistic** — assume the stop resolved first | biases results **down** by a known direction | the only one that cannot flatter a strategy into looking tradeable |
| optimistic — assume the target first | biases **up** | inadmissible; it is the assumption that manufactures an edge |
| proportional — split the trade by some ratio | invents a fractional outcome that never occurred | inadmissible; the journal records facts, not expectations |
| refuse — mark the trade unresolved and report the count | honest, and can make most results unreportable | correct as a *reported figure*, not as the only rule |
| finer bars for ambiguous sessions only | actually resolves it | limited: intraday history is short and not point-in-time (`ADR-0001`) |

**Recommendation, for a decision record rather than for this document to settle:** *pessimistic, with
the ambiguous-session count reported alongside every result.* Pessimistic because a cost model
underneath every R should never be the thing that makes a strategy look tradeable; the count reported
because a result where 40% of trades were resolved by assumption is a different claim from one where
2% were, and collapsing them hides exactly the sensitivity a reader needs.

Setting `exit.slot_resolution_order` is a **decision record**, not a study — it is a convention, and
a convention cannot come out "no" (`../decisions/README.md` §1).

## 4. What must be true before a profit slot is added

In this order, in the same change:

1. **`exit.slot_resolution_order` is set** by a decision record naming the resolution above.
2. **`ExitReason` gains its target member**, and every result that reports exit reasons is
   regenerated rather than merged with older ones — the reason distribution changes meaning.
3. **The ambiguous-session count becomes a reported field** on the result, not a log line.
4. **The trigger is unified first** if the live path is to execute anything. `REQ-VALIDATION-002` is
   unmet and structural, and adding a second exit path across two implementations compounds it.

Adding a target without step 1 produces numbers whose sign depends on an unrecorded assumption. That
is the specific defect this document exists to make impossible to introduce quietly.

## 5. What this model does not cover

Stated so the boundary is visible rather than assumed:

- **Order types.** The system places no orders (D1), so limit-versus-market has no meaning here. A
  fill is modelled, never requested.
- **Partial fills and queue position.** Not modelled. At the position sizes this project
  contemplates against a $5M ADTV floor, `DR-004` argues impact is irrelevant — an argument that
  holds only while that remains true.
- **Market impact as a function of size.** Same reasoning, same limit.
- **Borrow, locate and short execution.** The engine is long-only.
- **Corporate actions during a holding period.** The store keeps raw and adjusted series separately
  and never derives one from the other; which series a backtest reads is a `BACKTEST_PROTOCOL.md`
  concern, and the execution model inherits it rather than restating it.

## 6. Open items

- [ ] **`exit.slot_resolution_order` needs a decision record** before any profit slot exists. §3
      states the recommendation; the record is what makes it binding.
- [ ] **All fifteen `exit.*` parameters are `unset`**, including `exit.percentage_target`,
      `exit.max_holding_period` and `exit.atr_stop_multiple`. The backtest runs because a study pins
      its own values and records them; nothing else can run at all.
- [ ] **Two exits firing on one bar** needs the same treatment as stop-versus-target — a time exit
      and a stop on the same session are already possible in principle, and the engine resolves it by
      evaluating the open position before candidates without that order being specified anywhere.
      `EXIT_MODEL_SPEC.md` §5 requires quantity and execution order on every slot; today only the
      implicit order exists.
- [ ] **Intraday resolution is untested as a strategy.** Fetching finer bars only for ambiguous
      sessions is sound in principle and constrained by what a free tier serves point-in-time.
