# DR-006: The portfolio risk block

```
date:       2026-08-08
status:     proposed — owner ratification required
parameters: risk.max_open_risk, risk.max_concurrent_positions, risk.max_sector_risk,
            risk.correlation_threshold, risk.max_position_value,
            risk.liquidity_cap_order_to_adtv_pct
components: none - swingdesk.trade_management.sizing and the allocation path read these
```

`ALLOCATION_SPEC.md` §2 names six constraints and reports all six `unset`, which means the system
cannot tell you that you have too many candidates because it does not know what "too many" is. This
record proposes the six.

**These bind a real account, and `DR-005`'s did not.** That record set thresholds governing studies;
this one sets the limits that would stop a position being taken. Scrutinise it harder.

---

## 0. What this record deliberately does not set

**`risk.per_trade_pct` stays `unset`, and the course is explicit about why.** Appendix C's first
control cell reads *`Риск % задаётся личным планом`* — risk percent is set by the personal plan. The
course states it rather than omitting it. That number is the owner's and no decision record should
draft it.

Two consequences worth stating plainly:

1. **Ratifying this record does not enable sizing.** `size_long` refuses while `risk.per_trade_pct`
   and `risk.costs_allowance` have no values, so the pipeline still returns a coded refusal after
   this lands. Nothing here moves the system closer to taking a position.
2. **So every value below is expressed in R**, the per-trade risk unit, rather than in dollars or in
   percent of equity. That makes them scale-free: they hold whatever risk percent the owner
   eventually chooses, and they do not silently change meaning when equity does.

## Decision

| Parameter | Value | Unit |
|---|---|---|
| `risk.max_open_risk` | **6R** | multiples of per-trade risk |
| `risk.max_concurrent_positions` | **6** | positions |
| `risk.max_sector_risk` | **2R** | multiples of per-trade risk |
| `risk.correlation_threshold` | **0.70** over 60 sessions of daily returns | correlation |
| `risk.max_position_value` | **25% of equity** — 2,500 at the current `account.equity` | currency |
| `risk.liquidity_cap_order_to_adtv_pct` | **1.0%** of 20-day ADTV | percent |

## 1. Why 6R, and how it ties to a number already ratified

`risk.max_open_risk` is the anchor; the rest follow from it.

**6R means six concurrent positions each risking their full 1R.** The sizing law makes every position
cost one unit of risk, so open risk and position count are the same constraint counted two ways —
hence `risk.max_concurrent_positions` = 6 rather than an independently chosen number. Setting them
inconsistently would let one bind while the other looked satisfied.

**The link to `validation.max_allowable_drawdown` = −15R** (`DR-005`) is the part worth checking. A
single catastrophic session — everything gaps through its stop at once — costs roughly the whole open
risk, so about 6R, and more than that when gaps overshoot (`EXECUTION_MODEL.md` §2 measured gap exits
at 9.5% of trades, and a gap exit loses more than the planned 1R). Two and a half such days reach the
drawdown pause.

That ratio is the design: **the pause should fire on a pattern, not on one bad day.** At 15R of open
risk a single session could trip the kill criterion, which would make the criterion a report of one
day's luck. At 2R the book would be too small to express a strategy. 6R sits where a bad day hurts
and only a bad month pauses.

## 2. The other four

**`risk.max_sector_risk` = 2R** — one third of the book in any one sector or theme. Appendix C's
control cell requires ETFs and correlations to count toward it (*`Учитывать ETF и корреляции`*), so
a sector ETF consumes its constituents' sector budget rather than sitting outside it.

**`risk.correlation_threshold` = 0.70 over 60 sessions.** At r = 0.7 two instruments share about half
their variance (r² ≈ 0.49), which is the point where calling them independent bets stops being
defensible. 60 sessions is a quarter — long enough to be stable, short enough to notice a regime
change. Both halves of that are authored; the course names the concept in `M49-T761` and quantifies
nothing.

**`risk.max_position_value` = 25% of equity.** The cap Appendix C requires after the share count is
computed (*`Ограничить max position value/liquidity`*). At four positions of maximum size the account
is fully invested, which is a floor on diversification independent of the risk calculation — and
`Не равно риску` in the same table is the reminder that position value and risk are different columns
and must not be conflated.

**`risk.liquidity_cap_order_to_adtv_pct` = 1.0%.** Deliberately **not binding today** and stated as
such: `universe.min_adtv_20d` is $5M, so 1% is a $50,000 order against a maximum position value of
$2,500. The cap does nothing until the account is roughly 20× larger. That is the right place for it
— `DR-004` rejected modelling market impact for exactly this reason, and a liquidity cap that never
binds costs nothing while an absent one is a hole that opens silently as an account grows.

## 3. What can and cannot be evaluated once these are set

The honest half of this record. Setting a value is not the same as being able to check it.

| Constraint | Evaluable today? | Blocked on |
|---|---|---|
| `risk.max_open_risk` | **yes** — from the position store | — |
| `risk.max_concurrent_positions` | **yes** — a count | — |
| `risk.max_position_value` | **yes** — equity × price | — |
| `risk.liquidity_cap_order_to_adtv_pct` | **yes** — ADTV is in the store | — |
| `risk.max_sector_risk` | **no** | `Instrument.sector` is `None`; no free point-in-time sector source |
| `risk.correlation_threshold` | **no** | nothing computes a correlation matrix over the candidate set |

**The two that cannot be evaluated must report `unavailable`, not pass and not fail.** This is the
distinction `HANDOFF.md` §7 calls the most damaging error this product can make: a gap in the
*system* and a fact about the *trade* are different claims. Checklist item E13 already reports
exposure as `unavailable` and names what is missing, which is the behaviour to copy.

They must specifically **not** fail closed into a blanket refusal. A sector check that refuses every
candidate for want of sector data would stop the system entirely while looking like risk discipline.
Fail-closed applies to a decision made on *degraded* data; it does not apply to a check the system
was never able to perform, and conflating those two produces a system that cannot act at all.

## 4. Alternatives rejected

| Alternative | Why not |
|---|---|
| Express the caps in dollars or percent of equity | they would change meaning the day equity or risk% changes, and `risk.per_trade_pct` is deliberately not set here. R is scale-free |
| Set `risk.per_trade_pct` too, so sizing works end to end | the course explicitly reserves it to the owner (§0). Drafting it would be the one place this project overrode a stated course rule for convenience |
| A single "max portfolio heat" number with the rest derived | hides which constraint bound. The journal has to record *which* limit refused a candidate, and `CODES.md`'s `RISK` code is one code for six different causes already |
| 10R open risk | a single gap-down session could reach the −15R pause on its own, making the kill criterion a report of one day's luck |
| 3R open risk | three positions is not a portfolio; sector and correlation caps would never bind and the concentration rules would be decorative |
| Leave sector and correlation unset until their data exists | then `ALLOCATION_SPEC.md`'s record has holes in it for a reason nobody can see. Setting them with a disclosed `unavailable` is more legible than absence |

## 5. What would overturn this

- **A measured correlation structure.** Once a correlation matrix exists over the real candidate set,
  0.70 becomes checkable against how often it actually separates duplicate exposure. That is a study.
- **A sector source.** `risk.max_sector_risk` cannot be evaluated without one, and it will be worth
  re-deriving the 2R once sector concentration is observable rather than assumed.
- **Any change to `validation.max_allowable_drawdown`.** §1's ratio is the reason 6R was chosen;
  PR-006 is registered to replace the −15R with a measured percentile, and if it moves materially
  this record should move with it.
- **Owner amendment.** These are proposed. Any value the owner sets directly carries provenance
  `owner` rather than `assumed:DR-006`, and that is the stronger provenance for exactly these six.

## 6. Consequences

1. `ALLOCATION_SPEC.md` can be implemented — its capacity calculation has inputs.
2. Two of the six are set and unevaluable, and the system must say so rather than skipping them
   silently (§3). That is a display requirement, not just an internal one.
3. Nothing about sizing changes. `risk.per_trade_pct` remains `unset`, so `size_long` still refuses,
   and the count of `assumed` parameters rises from 24 to 30 while the system's willingness to act
   stays exactly where it was.
4. **`risk.*` still has ten unset entries** after this record — the loss limits, the ladders, the
   discipline thresholds and the short-side allowance. Those are behavioural and personal in a way
   these six are not, and they belong in a record the owner drafts rather than ratifies.
