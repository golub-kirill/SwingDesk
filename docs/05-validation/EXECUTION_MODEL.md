# EXECUTION MODEL

**Status:** drafting · **Tier:** 5 (validation) · **Content:** authored, measured against the tree

Master ТЗ v1.0 §28, ranked fourth of the nine absent sections in `SPEC_GAP_ANALYSIS.md` §4 —
*"currently latent rather than harmful … it becomes a correctness defect the day a target exists."*
This document states the model before that day.

**What an execution model is in a system that never executes.** Owner decision D1 means no order is
ever sent, so this is not an order router — it is the **measurement device** that turns a decision
into a fill price. Every R this project reports is a claim about a fill that was assumed, and the
assumptions belong in one place where they can be attacked.

---

## 1. What the course requires

`BACKTEST_PROTOCOL.md` §2 transcribes two stages that are entirely about execution. The `Риск` stage
requires five fields per trade — entry, stop, shares, slippage and **gap handling** — and the
`Сигнал` stage requires setup date, trigger date and the execution that was *available*, not the one
that would have been ideal.

That word carries the whole section. An execution model exists to record what could actually have
been done, and every simplification below is measured against it.

| Course requirement | State |
|---|---|
| entry | **implemented** — next bar's open |
| stop | **implemented** — ATR-derived, set before size |
| shares | **implemented** — integer, floored |
| slippage | **modelled** — `costs.slippage_model`, provenance `assumed:DR-004` |
| gap handling | **implemented** — a gap through the stop fills at the open |
| available execution | **partial** — see §5 |

## 2. The model as implemented

Measured from `validation/backtest/engine.py`, `trade_management/exits.py` and
`validation/backtest/costs.py`.

| # | Rule | Implementation |
|---|---|---|
| E1 | A signal at bar `i`'s close fills at bar `i+1`'s open. Never the same bar. | the loop forms no index but `i+1`, and stops one short of the end |
| E2 | Slippage is applied to the **fill price**, not deducted afterwards. | `buy_fill` pays up, `sell_fill` receives less |
| E3 | Commission is per share and charged on both sides. | `commission(shares)` returns twice the per-share rate |
| E4 | A session that **opens** below the stop fills at the open. The loss recorded is the real loss. | `ExitReason.STOP_GAP`, price `bar.open` |
| E5 | A session that trades through the stop without gapping fills **at** the stop. | `ExitReason.STOP`, price `stop` |
| E6 | Within one bar the protective exit is checked before the time exit. | a bar that both breaks the stop and completes the holding period is a stop-out |
| E7 | Quantity is an integer, floored. A fractional result is a smaller position, never a rounded-up one. | `int(risk_per_trade / risk_per_share)` |
| E8 | Costs are inside every reported number. Gross is not reported at all. | `Trade.net_r`; `DR-004-cost-model.md` consequence 1 |

E4 is the one that pays for itself. Assuming every stopped trade loses exactly 1R is the most common
way a daily backtest flatters itself, and it is wrong by the largest margin on precisely the
instruments that gap. PR-005 recorded 250 gap exits in 2629 ungated trades — **9.5%** of them — so
this is not a corner case in this data.

## 3. What is deliberately absent

Absent is not the same as overlooked. Each row states what would have to change for it to matter.

| Not modelled | Why it does not bite yet | What makes it bite |
|---|---|---|
| **Profit target / limit orders** | the harness implements two of the course's four exit slots — protective and time (`EXIT_MODEL_SPEC.md`) | any target: `exit.percentage_target`, `exit.partial_trigger` |
| **Partial fills** | one order, one instrument, at $1000 risk against a `universe.min_adtv_20d` floor of $5M | size approaching the liquidity cap `risk.liquidity_cap_order_to_adtv_pct` |
| **Market impact** | rejected in `DR-004-cost-model.md` as irrelevant at this order size — right for large orders, not for these | the same cap |
| **Halts, limit up/down** | daily bars; a halted session is a data-completeness question first (`DATA_QUALITY_SPEC.md`) | intraday data, or event-driven strategies |
| **Short sales and borrow** | the system is long-only end to end — there is no `size_short` and no short path in the engine | a short playbook; `BORROW` already exists as a skip code |
| **Latency and queue position** | one decision per day, filled at an open | any intraday timeframe |
| **Currency conversion on the fill** | USA and Canada are never merged, and each trade settles in its own currency (`CONSTRAINTS.md`) | a combined portfolio view |

## 4. The intrabar ambiguity policy

This is the section §28 exists for, and the reason to write it while nothing depends on it.

**The problem.** A daily bar records open, high, low and close. If a position's stop and its target
both lie inside `[low, high]`, the bar does not say which came first. Nothing in daily data can
resolve it.

**Today it cannot arise.** There is no target — the only exits are the protective stop and the time
stop, and a bar that touches the stop is a stop-out under E5 regardless of where else it traded. The
policy below therefore changes no existing number, which is exactly why now is the time to fix it.

**The policy, in order of precedence:**

1. **Stop before target.** When both levels lie within one bar and the data cannot order them, the
   model assumes the stop filled first.
2. **Gap wins over both.** If the bar opened beyond a level, that level filled at the open (E4), and
   no intrabar reasoning applies — the open is observed, not inferred.
3. **The assumption is recorded on the trade**, not applied silently. A trade closed under rule 1
   carries an ambiguity flag, so the fraction of results resting on the assumption is a number rather
   than a footnote.
4. **Resolving it requires intraday data, not a better rule.** If a source ever supplies it, the flag
   identifies exactly which trades to re-measure.

**Why pessimistic.** The alternative — target first — is unfalsifiable on daily data and biases every
affected trade upward by the full stop-to-target distance. A known-direction bias is manageable: it
makes the reported edge a floor. An optimistic assumption makes it an unknown. `BACKTEST_PROTOCOL.md`
§3 names going live on a flattering in-sample curve as prohibited, and choosing the favourable branch
of an unresolvable ambiguity is that prohibition applied one bar at a time.

**Cost of the choice, stated.** Rule 1 is conservative and will understate any strategy whose targets
are genuinely hit before its stops. Rule 3 exists so that understatement is measurable rather than
assumed away.

## 5. `available execution` — the exclusions, found and closed

The engine's contract is that skipped signals are counted with a reason and never dropped: a signal
discarded silently is a survivorship filter applied to the signal set. Writing this document found
that the ledger did not meet its own contract. **Fixed 2026-08-08**, and recorded here because the
finding is more useful than the fix.

**What was wrong.** `Skipped` declared five reasons and incremented three — `NO_ATR`,
`STOP_NOT_BELOW_ENTRY` and `ZERO_SHARES`. `POSITION_OPEN` and `NO_NEXT_BAR` were incremented nowhere
in `src/`, `tests/` or `tools/`, verified by search rather than inferred. Separately, a bar with no
lookback window and a bar that genuinely failed the trigger took the same branch, so the first
`trigger_lookback` bars of every instrument left the denominator without being counted anywhere.

**What changed.** Three things, none of which alters a trade:

| | Before | Now |
|---|---|---|
| A signal while a position is open | evaluated after the management branch had already returned | the trigger is evaluated on every bar; a would-be signal increments `POSITION_OPEN` |
| A bar with no lookback window | indistinguishable from a rejection, counted nowhere | `ArmResult.unevaluable_bars`, deliberately **not** a `Skipped` reason |
| A signal on the final bar | unreachable, unstated | unreachable, and the enum now says why: the loop stops one bar short |

`unevaluable_bars` is a separate field on purpose. `Skipped` counts **signals** that produced no
trade; this counts **bars** on which the trigger could not be evaluated at all. Folding them
together would report an unanswerable bar as a rejected signal — the `UNKNOWN`-becomes-`FALSE`
collapse `RULE_SPEC.md` §4 forbids, in the one place the engine could quietly commit it.

**`POSITION_OPEN` counts only a bar that both triggered and passed the gate**, so it means "this
would have been a signal", which is the same standard `signals` uses. Counting every triggered bar
regardless of the gate would overstate what the constraint cost.

**Consequence for the reported studies: none, and one caveat.** No trade, R, or signal count moves —
the three tests that pin entry timing, gap fills and R denominators are unchanged and green. But
PR-005's stored skip counts were produced before these counters existed, so a re-run would report
`POSITION_OPEN` and `unevaluable_bars` that the record does not contain. The reports are records of
what ran and are not being edited.

This is what `validation.missed_trade_rate` is for. `DR-007` gave it a value on 2026-08-08 and it is
`assumed:DR-007`, read by nothing. A forward test measures misses
against a live schedule (`VALIDATION_PROGRAM.md` §2); a backtest can only measure them against its
own ledger, and that requires the ledger to be complete. It now is.

## 6. Costs, and the number the verdict rests on

`DR-004-cost-model.md` sets both inputs and both are `assumed`:

| Parameter | Value | Stress |
|---|---|---|
| `costs.commission_model` | 0.005 USD per share, each side | 3× (`validation.stress_cost_multiplier`) |
| `costs.slippage_model` | 5 bps of price, each side, applied to the fill | 3× |

**PR-005 measured the base strategy at +0.028R per trade at 1× costs and −0.123R at 3×.** The sign of
the project's central result therefore sits inside an assumed number — `HANDOFF.md` §3 states it
plainly and this document is where the mechanism lives.

Two consequences follow directly:

1. **Every result is reported at 1× and 3×.** Quoting either alone is a materially different claim.
2. **Measuring the spread is the highest-value study available.** Corwin–Schultz (2012) and
   Abdi–Ranaldo (2017) estimate effective spread from daily OHLC — no new data, no vendor, and it
   converts `costs.slippage_model` from `assumed` to something a pre-registration can test
   (`HANDOFF.md` §5 item 5). `screen.max_spread_pct` is `unset` and would become settable from the
   same measurement.

Until then, every number derived from these values carries its `assumed` provenance wherever it is
displayed — the parameter registry's rule, applied here because a cost model sits underneath every R
in the system.

## 7. The live path has a different execution model, and nobody has said so

Measured. In `application/pipeline.py` the sizing input is the **last stored close**, with no cost
model applied:

```
entry = stored.bars[-1].close
stop  = entry - latest_atr
sized = size_long(entry, stop, registry)
```

In `validation/backtest/engine.py` the entry is the **next bar's open, marked up by slippage**. The
two paths therefore disagree about what an entry price is:

| | Backtest | Live |
|---|---|---|
| Price | next bar's open | last bar's close |
| Slippage | applied to the fill | not applied |
| Purpose | measure a realised trade | size an indicative proposal |

Neither is wrong for its own purpose, and no result diverges **today** because the live path stops at
`"sized; awaiting a trigger"` and never opens a position. But `REQUIREMENTS.md` `REQ-VALIDATION-002`
requires the two paths to produce an identical `Decision` from an identical bar, and this is the
first concrete instance of them not being able to: the same instrument on the same day is sized from
two different prices.

**The fix is the same one already ranked**: the execution model belongs in one place both paths call,
written once before the live path gains a trigger (`HANDOFF.md` §5 item 6). Adding it after means
reconciling two implementations instead of writing one.

Until it exists, the live report's entry is **indicative** and must be labelled so — it is not a fill
and it carries no slippage.

## 8. Rules this document freezes

1. Decision at close, fill at the next open. Same-bar fills are prohibited (`POINT_IN_TIME_SPEC.md`).
2. Slippage is applied to the fill price; costs are never deducted at the end.
3. A gap through a level fills at the open, and the realised loss is recorded rather than assumed.
4. Within a bar: gap, then protective, then time. Stop before target when both are ambiguous (§4).
5. Quantity floors; a fractional share is never rounded up.
6. Every exclusion from the trade set is counted with a reason. An uncounted exclusion is a
   survivorship filter regardless of intent.
7. One execution model, called by every mode (`SYSTEM_MODES.md`). A mode may pin different inputs; it
   may not implement different fills.

## 8a. What must be true before a profit slot is added

In this order, in the same change:

1. **`exit.slot_resolution_order` is set** by a decision record naming the resolution above.
2. **`ExitReason` gains its target member**, and every result that reports exit reasons is
   regenerated rather than merged with older ones — the reason distribution changes meaning.
3. **The ambiguous-session count becomes a reported field** on the result, not a log line.
4. **The trigger is unified first** if the live path is to execute anything. `REQ-VALIDATION-002` is
   unmet and structural, and adding a second exit path across two implementations compounds it.

Adding a target without step 1 produces numbers whose sign depends on an unrecorded assumption. That
is the specific defect this document exists to make impossible to introduce quietly.

## 9. Open items

- [ ] **The ambiguity flag has no field yet.** §4 rule 3 needs a column on `Trade` before the first
      target exists; adding it afterwards leaves earlier trades unlabelled and unlabelled is
      indistinguishable from unambiguous.
- [x] ~~**`POSITION_OPEN` is never counted**~~ — **done 2026-08-08** (§5), with `unevaluable_bars`
      alongside it. Two counters, one new test, no trade moved.
- [ ] **`validation.execution_delay` is `assumed:DR-007` and read by nothing** — it was `unset` when
      this item was written, and gaining a value did not gain it a consumer. It is not unclaimed:
      `WALKFORWARD_SPEC.md` §4 makes it perturbation 6 of the robustness suite — *execute later than
      the signal* — so the execution model owes it a definition even though the perturbation is what
      consumes it. Under D1 the delay is real and human-sized: the owner reads a report and acts
      later, or not at all.
- [ ] **Short-side execution is undefined**, and `BORROW` already exists as a skip code for it. Not
      urgent — the system is long-only — but the code implies a path the model does not have.
- [ ] Whether the live path's indicative entry should apply the modelled slippage. Arguments both
      ways: applying it makes the proposal comparable to the backtest, and not applying it keeps the
      displayed number a price the owner can verify on a chart.
