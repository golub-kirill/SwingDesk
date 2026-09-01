# DR-028: The liquidity cap ADJUSTS the order and refuses only at zero, and it measures against the universe rule's own ADTV

```
date:            2026-09-01
status:          accepted — the VALUE was ratified by the owner (risk.liquidity_cap_order_to_adtv_pct
                 = 1.0, provenance owner). This record supplies the DEFINITION that value needed and
                 never had, and sets no threshold of its own
parameters:      none new. Gives risk.liquidity_cap_order_to_adtv_pct a `read_by` for the first time
components:      trade_management.sizing:size_long
implemented_by:  src/swingdesk/trade_management/sizing.py :: def size_long
built:           2026-09-01
```

## 1. A ratified value that reached no code

`risk.liquidity_cap_order_to_adtv_pct` has carried `provenance: owner`, `value: 1.0` and
**`read_by: none`** since it was set. `AGENTS.md` §7 names that shape exactly: *"a ratified decision
that reaches no code is a decision that did not happen"*, and gate 1 has printed it in the orphan
list on every run since.

**It was harmless when it was written and it is not any more.** `CHARTER` A-002 (2026-09-01) lets
the system place orders at a paper venue with no per-order approval, so the size of an order that
reaches a market stopped being hypothetical the same day. `ALLOCATION_SPEC.md` §3 lists this cap
beside the four that are enforced; `CARD-001` lists it under `sizing.portfolio_constraints`. Two
documents and a strategy card assert a control that did not exist.

Wiring it needed a definition, and that is what was missing rather than the number.

## 2. The decision

**The cap bounds the ORDER'S VALUE at `risk.liquidity_cap_order_to_adtv_pct` percent of the
instrument's average daily dollar volume. When it binds it REDUCES the share count; it refuses only
when the reduced count is zero, with the course's `LIQ` code.**

```
cap_value = adtv x pct / 100
if position_value > cap_value:  shares = floor(cap_value / entry)
if shares == 0:                 refuse LIQ
```

### 2.1 Why it adjusts rather than skips, and the course is the reason

The cap's course reference is `M49-T0760`, and its title is **"Поправка на ликвидность"** — a
liquidity **adjustment**. Its sibling `M49-T0761` is "Поправка на корреляцию", and `RISK_SPEC.md`
already renders that pair as *"correlation threshold **and its size adjustment**"*. The family the
course names here is size adjustment, not admission.

**And this project already implements exactly that shape one step earlier.** `risk.max_position_value`
reduces the share count and refuses `LIQ` only at zero — step 5 of `size_long`, since it was
written. A second cap in the same step behaving differently would be two rules where the course
names one family, and the difference would be invisible in a report that prints a share count.

`AGENTS.md` §16 applies and is worth stating: the course being a requirements source is why its
*definition* of the control is followed, and it is **not** evidence that 1.0% is the right number.
The number is the owner's and this record does not touch it.

### 2.2 Why it measures against the UNIVERSE RULE's own ADTV

The window is `application.universe.ADTV_WINDOW` and the lag is
`universe.adtv_lag_sessions` — the same two the `DR-003` liquidity rule admits an instrument with,
and the same lag `DR-017` ratified because volume is still being written for two sessions after the
close.

**Not a second window, deliberately.** A cap measured over a different window than the rule that
admitted the instrument would mean two liquidity opinions about one name, disagreeing on the days
that matter — and the failure this project has paid for repeatedly is one logic kept in two places
(`AGENTS.md` §10.5, master specification §8). Authoring a window here would also be authoring a
threshold, which §8 forbids without a pre-registration.

### 2.3 An ADTV that cannot be measured REFUSES

`size_long` takes `adtv` as a required keyword with **no default**, the same shape `LiquidityRule.
adtv_lag` was given under `DR-017` and for the same reason: every candidate default is silently
wrong in one direction. `None` means the window was not full or no series was available, and it
refuses with `LIQ` rather than sizing uncapped.

**This is the ordinary fail-closed polarity and it was checked, not assumed.** `DR-025` §2.1 records
a guard in this repository whose refusal *admitted* the candidate, so "fail closed" read correct and
behaved backwards. Here a refusal from `size_long` produces a `Refusal`, the candidate gets a coded
`Skip`, and nothing is sized — the refusal actually refuses. Traced before this was written.

In practice an admitted candidate always has a full window: `universe.min_bar_history` requires far
more bars than `ADTV_WINDOW` needs. The branch exists for `scan <TICKER>` on a name the universe
rule never saw, which is exactly where an uncapped order would otherwise be sized.

## 3. What this changes, measured

**Nothing, at this account size, and that is the point of recording it now rather than later.**
`DR-003`'s addendum measured a position at a median **0.0026%** of one session's dollar volume; the
cap is 1.0%. It begins to bind at roughly a **$2.2M** account.

So the cap is wired while it costs nothing to get wrong, instead of at the moment it first matters.
The run's manifest gains one `ParameterUse` and `output_hash` moves with it — the golden replay is
regenerated in the same commit (`COMPONENT_REGISTRY_SPEC.md` §6).

**The Track A streak is 0** as of this date, counting from the 2026-08-31 restart, so a change that
moves decision output costs no counted sessions. That was checked with
`python tools/track_a_streak.py` rather than assumed, and it is why this landed today rather than
being deferred again.

## 4. Alternatives rejected

- **Skip the candidate instead of trimming it.** Rejected on §2.1: the course names an adjustment,
  and the neighbouring cap in the same function already trims. It would also be strictly worse for
  the owner — a name that can absorb 60% of the intended order becomes no trade at all.
- **Trim silently with no floor.** Rejected: a cap that can produce a zero-share order has to say
  so, or the candidate leaves the run with a `Trade` decision and nothing to buy.
- **Measure ADTV over a window authored here.** Rejected on §2.2 — two liquidity opinions about one
  instrument, and an authored threshold with no pre-registration (`AGENTS.md` §8).
- **Apply the cap at submission instead of at sizing.** Tempting, because that is where an order
  meets a market. Rejected because the decision and the order would then disagree: the run would
  record a `Trade` for a size it never intended, and the report — the thing the owner reads — would
  print the uncapped number.

## 5. What would overturn this

- **A measured fill showing the cap is the wrong shape of control** — that a 1%-of-ADTV order moves
  the price materially, or that a much larger one does not. Either makes the *value* the owner's
  question again; neither touches §2's definition.
- **A venue that reports its own liquidity.** Alpaca serves quotes and depth; a cap measured against
  the book at the moment of submission is a better control than one measured against 20 sessions of
  history. That is a different record and needs the intraday data this project does not store.
