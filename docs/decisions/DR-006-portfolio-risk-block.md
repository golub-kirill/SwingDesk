# DR-006: The portfolio risk block

```
date:       2026-08-08
status:     accepted — fully ratified by the owner: four of six 2026-08-22 (§8.4), the sector cap
            and the correlation cap 2026-08-23 (§17)
parameters: risk.max_open_risk, risk.max_concurrent_positions, risk.max_sector_risk,
            risk.correlation_threshold, risk.correlation_lookback_sessions,
            risk.max_position_value, risk.liquidity_cap_order_to_adtv_pct
components: none - swingdesk.trade_management.portfolio enforces the book and correlation caps,
            swingdesk.derived_observations.correlation supplies the statistic,
            swingdesk.trade_management.sizing the position-value cap
implemented_by: src/swingdesk/trade_management/portfolio.py :: risk.max_open_risk
```

**The header moved from `proposed` to `accepted` on 2026-08-22 and §9 says why**, so the change is
recorded rather than silent: §8.3 ratified four of the six on that date and the header went on
reading `proposed — owner ratification required` for as long as the caps reached no code. Gate 20
now binds this record to the file that enforces it.

`ALLOCATION_SPEC.md` §2 named six constraints and reported all six `unset` — which meant the system
could not tell you that you had too many candidates, because it did not know what "too many" was.
This record proposes the six, and that section now carries the values and an evaluability column
instead.

**These bind a real account, and `DR-007`'s did not.** That record set thresholds governing studies;
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
2. **So every value that expresses a RISK limit is in R**, the per-trade risk unit, rather than in
   dollars or in percent of equity. Those are scale-free: they hold whatever risk percent the owner
   eventually chooses. The two that are not risk limits — `max_position_value` in currency and the
   liquidity cap in percent — measure position *size* against the account and the market rather
   than risk against the book, so R would be the wrong unit for them. §7 records the one place that
   distinction still bites.

## Decision

| Parameter | Value | Unit |
|---|---|---|
| `risk.max_open_risk` | **6R** | multiples of per-trade risk |
| `risk.max_concurrent_positions` | **6** | positions |
| `risk.max_sector_risk` | **2R** | multiples of per-trade risk |
| `risk.correlation_threshold` | **0.70** over 60 sessions of daily returns | correlation |
| `risk.max_position_value` | **2,500** — 25% of `account.equity` at its current value | currency |
| `risk.liquidity_cap_order_to_adtv_pct` | **1.0%** of 20-day ADTV | percent |

## 1. Why 6R, and how it ties to a number already ratified

`risk.max_open_risk` is the anchor; the rest follow from it.

**6R means six concurrent positions each risking their full 1R.** The sizing law makes every position
cost one unit of risk, so open risk and position count are the same constraint counted two ways —
hence `risk.max_concurrent_positions` = 6 rather than an independently chosen number. Setting them
inconsistently would let one bind while the other looked satisfied.

**The link to `validation.max_allowable_drawdown` = −15R** (`DR-007`) is the part worth checking. A
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

**`risk.max_position_value` = 2,500, being 25% of equity.** The cap Appendix C requires after the
share count is computed (*`Ограничить max position value/liquidity`*). At four positions of maximum size the account
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
| Express the *risk* caps in dollars or percent of equity | they would change meaning the day equity or risk% changes, and `risk.per_trade_pct` is deliberately not set here. R is scale-free. `max_position_value` is currency anyway because `size_long` compares it to a position value — §7 |
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

## 7. Open items

- [ ] **`risk.max_position_value` should be a percentage, not a currency amount.** It is stored as
      2,500 because `size_long` reads it as a number and compares it to a position value, so a
      percentage there would not work without changing the sizing code. The consequence is that it
      silently means something different the day `account.equity` changes. A percentage parameter
      plus one line in `sizing.py` fixes it; both are out of scope for a record about limits.
- [ ] **The correlation lookback needs its own registry entry.** `risk.correlation_threshold` is
      0.70 and the 60-session window it is measured over lives in a note. Two numbers in one
      parameter is the shape this registry exists to prevent, and it stayed that way here only
      because nothing computes a correlation yet.
- [ ] **`risk.max_sector_risk` and `risk.correlation_threshold` are set and unevaluable** (§3).
      Whether a set-but-uncheckable parameter should be visible as such in the daily report is a
      display decision nobody has taken.

---

## 8. Partially ratified 2026-08-22, and the anchor moved from 6R to 4R

Appended, never edited above: §1's argument for 6R is history and stays readable as what was believed
(`AGENTS.md` §3). What follows is why it did not survive its own project's trade log.

### 8.1 The measurement that moved it

§1 anchors 6R on this: *"A single catastrophic session — everything gaps through its stop at once —
costs roughly the whole open risk, so about 6R … Two and a half such days reach the drawdown pause."*

Recomputed from `docs/prereg/results/PR-005-trades.csv`, 26,351 trades, which did not exist when this
record was drafted:

| | |
|---|---|
| Mean loss on a clean stop | **−1.070R** |
| **Mean loss when the exit gaps through the stop** | **−1.692R** |
| Worst single gap exit | **−11.78R** |
| Gap exits worse than −1.5R | 35% of gaps, 4.0% of all trades |

So a session in which the whole book gaps does not cost ~6R. It costs **6 × 1.692 = 10.15R**, and
`validation.max_allowable_drawdown` = −15R is then **1.5 sessions away, not two and a half**. The
record's own design intent — *"the pause should fire on a pattern, not on one bad day"* — was not
met by the number chosen to meet it.

**Four positions restores it:** 4 × 1.692 = 6.77R, and 15 ÷ 6.77 = **2.2 sessions**, which is what §1
was reaching for.

### 8.2 And the risk this cap addresses is correlated, which is why it is the RIGHT instrument

The per-trade stop cannot defend against a gap — by construction, the price it names does not trade
between the close and the open. What can defend is a bound on how much is exposed at once, and the
log says that is exactly the shape of the risk:

- **89 sessions hold 52% of all 3,003 gap exits.** Gap risk arrives in clusters, not independently.
- The worst single session produced **87 simultaneous gap-outs**.

A cap on concurrent open risk is therefore not one control among six. It is the only control in this
system that acts on the failure mode that actually occurs.

### 8.3 What the owner ratified

| Parameter | Value | Provenance |
|---|---|---|
| `risk.max_open_risk` | **4R** (was 6R) | `owner`, 2026-08-22 |
| `risk.max_concurrent_positions` | **4** (was 6) | `owner`, 2026-08-22 |
| `risk.max_position_value` | 2,500 | `owner`, 2026-08-22 |
| `risk.liquidity_cap_order_to_adtv_pct` | 1.0% | `owner`, 2026-08-22 |

§5 already provided for this: *"Any value the owner sets directly carries provenance `owner` rather
than `assumed:DR-006`, and that is the stronger provenance for exactly these six."*

**A consistency the smaller cap produces for free:** at four positions of maximum size the account is
exactly fully invested (4 × 2,500 = 10,000 = `account.equity`). §2 wanted that as a floor on
diversification and got it only approximately at six; at four the two caps coincide exactly.

### 8.4 Two parameters stay proposed, and §3's reason for it was wrong

`risk.max_sector_risk` and `risk.correlation_threshold` are NOT ratified here. But §3 called them
*unevaluable*, and researching that before ratifying showed the claim does not hold:

- **Correlation is not blocked at all.** §3 says *"nothing computes a correlation matrix over the
  candidate set"* — a statement about missing CODE, not missing data. Measured 2026-08-22: the full
  **1152 × 1152** matrix over 60 sessions of daily returns builds from the existing store in
  **0.09 seconds**. Of 662,976 pairs, **1.57% sit at r ≥ 0.70**, and the 99th percentile is r = 0.759
  — so the threshold is neither vacuous nor over-broad.
- **Sector has a free source.** §3 says *"no free point-in-time sector source"*. Half of that is
  wrong and the half that is right is not the half that blocks it: `yfinance` — already this
  project's only bar vendor — returns sector and industry directly for equities on both exchanges
  (`AAPL` → Technology, `XOM` → Energy, `CNQ.TO` → Energy). What is missing is the **point-in-time**
  version: it serves today's classification, not the one in force in 2016. That is a real
  restriction for a backtest and **no restriction at all for live admission.**

**What genuinely blocks the sector cap is narrower and was not named:** an ETF returns no sector at
all (`SPY` → `None`), and §2 requires ETFs to consume their constituents' sector budget, quoting the
course's *`Учитывать ETF и корреляции`*. Look-through to an ETF's holdings is the missing piece —
not the sector of an ordinary share.

### 8.5 Ratified is not wired

All four remain `read_by: none` today. `positions.open_risk_as_of` already computes total open risk
and the report already prints it; nothing compares it to a limit. Until that lands these are decided
and unenforced, which is the exact shape `AGENTS.md` §7 counts and prints on every gate run.

### 8.6 The clustered days cannot be seen coming, and the obvious signal points the wrong way

§8.2 says a cap is the right instrument because gap risk is correlated. The natural objection is
that a correlated risk you can *forecast* should be dodged rather than capped. Tested, on the two
signals this project's data can actually produce:

**Day of week — refuted.** If weekend news drove it, Monday would dominate. Monday holds 23.6% of the
89 clustered days against a 19.2% base rate, and **Tuesday holds 24.7%**. There is no weekend effect
to trade.

**Prior realised volatility — refuted, and inverted.** Annualised 10-session volatility of the
cross-sectional median return, measured strictly before the session in question:

| | median prior vol | p90 |
|---|---|---|
| Ordinary session (n=1,708) | **8.40%** | 17.42% |
| Clustered gap session (n=89) | **7.09%** | 14.99% |

**The violent days arrive out of calmer tape than average, not out of storms.** A rule standing down
whenever prior volatility exceeded the ordinary p75 would have caught 15% of the clustered days while
sitting out 25% of all sessions — a **lift of 0.59×, worse than choosing at random**. At p90 it is
0.68×. The reflex to cut exposure when volatility rises would have made this worse.

That is not mysterious in hindsight: a market already at high volatility has repriced, and the
recognisable episodes here — the peak day is 2020-02-24 with 87 simultaneous gap-outs — arrived into
a quiet, record-high tape.

**Two caveats, because this is one test and not a law.** The cross-section before 2024 is the same 68
instruments the trade log holds, so "market" here is thin and is the same population that gapped.
And only two signals were tested; implied volatility, options skew and an earnings calendar are all
plausible and none of them exist in this project's data.

**What survives is the conclusion this section was written to check:** the days that do the damage
were not forecastable from what we hold, so a standing bound on how much is exposed at once is not
the fallback. It is the control.

### 8.7 The ETF look-through exists too — and the vendor lies about it for bond funds

§8.4 named ETF look-through as the one thing genuinely missing. Checked rather than assumed:
**`yfinance` supplies it.** `Ticker.funds_data.sector_weightings` returns exactly the composition §2
requires so that an ETF consumes its constituents' sector budget:

| | |
|---|---|
| `SPY` | technology 37.4% · financial services 12.2% · communication services 9.9% |
| `VGK` | financial services 25.2% · industrials 19.9% · healthcare 12.3% |
| **`NEAR`** | **healthcare 100.0%**, every other sector 0.0% |

**`NEAR` is a short-maturity BOND fund. It has no equity sectors at all.** The vendor does not
answer "not applicable"; it answers confidently and wrongly. Consumed naively, one bond ETF would
spend an entire sector budget on a fiction — and it would do so silently, which is worse than the
check not existing.

**So the guard is a precondition of the feature, not a refinement of it.** A look-through whose
weights are degenerate — one sector at 100%, or an instrument that is not an equity fund — must be
refused and reported `unavailable`, never consumed. That is `AGENTS.md` §12's
`unavailable`-is-not-`fail` rule applied at the one point where the source is confidently wrong,
and it is the same shape as `SECURITY.md` §6 treating this vendor as untrusted input.

Nothing here changes what §8.3 ratified. It moves `risk.max_sector_risk` from "cannot be evaluated"
to "buildable, with a named guard that must land with it".

---

## 9. Built 2026-08-22, and the three rulings that shaped it

§8 ratified the numbers. This section records what enforces them, because a ratified decision that
reaches no code is a decision that did not happen (`AGENTS.md` §7) — and between §8.3 and this
section, these two caps sat in the registry with `read_by: none` for exactly as long as it took to
build the gate.

### 9.1 Where the cap lives

| | |
|---|---|
| The verdict | `src/swingdesk/trade_management/portfolio.py` — pure: `limits`, `book`, `assess` |
| The candidate path | `application/pipeline.py`, step 6 of `RISK_SPEC.md` §3, after `size_long` |
| The manual entry | `presentation/cli.py`, `open-position`, before the position is recorded |
| The display | `presentation/report.py`, a `BOOK CAPACITY` block |
| The audit of a breach | `positions.duckdb`, new append-only table `cap_overrides` |

The refusal is `Skip` / `RISK` — `CODES.md` reserved *open/sector/currency/event limit exceeded*
with action *Skip or choose better candidate* long before any arithmetic could raise it, and it
carries **no** `parameter_id`: a full book is a fact about the account, not an unset threshold, and
`funnel.py` splits skip causes on exactly that field.

### 9.2 Three owner rulings, taken before the build

1. **`open-position` refuses over the cap**, and records only with
   `--acknowledge-over-cap "<reason>"`. The reason lands in `cap_overrides` with the book as it
   stood — an override that is only printed is a decision nobody can review afterwards. The command
   records a fill that already happened at the broker, so the escape hatch is required; what it
   must never do is record a fifth position as though the limit had been met.
2. **Candidates are measured against the open book alone.** A `Watch` is not a position and consumes
   no capacity. Allocating the last slot *between* admissible candidates is a ranking,
   `rs.ranking_method` is `unset`, and `ALLOCATION_SPEC.md` §6 rule 4 forbids falling back to id
   order — which would be an alphabetical bias silently applied. The report says so in the block, so
   "room for 3 more" cannot be read as "open the three Watch names below".
3. **Negative open risk counts as it is, unclamped.** A stop above entry frees R-capacity, and
   `risk.max_concurrent_positions` still bounds how many instruments can gap at once. Clamping would
   hide the difference between "risk removed" and "risk locked in as profit", which is the reason
   `Position.open_risk` already refuses to clamp.

### 9.3 What the build made visible, and did not invent

- **A mixed-currency book cannot be totalled while `account.fx_rate_cad` is `unset`.** The cap is
  denominated in R and R is base currency, so a CAD position's risk has no expression at all. The
  consequence is larger than one command: once such a position is in the book, no later run can
  total the book either, and every candidate refuses. `open-position` therefore refuses a `.TO`
  entry and names the parameter. Canada is deferred (`DR-014`), so this costs nothing today.
- **`PositionStore.open_risk_as_of` sums across currencies with no conversion.** It has never been
  wrong — the store holds no CAD position — and it cannot convert, because the dependency law lets
  that module depend only on `platform`. Its docstring now says plainly that it is a raw
  per-currency sum, and everything that compares a book to a limit goes through `portfolio.book`.
- **The cap widened what can refuse a manual entry, and that is worth stating rather than
  discovering.** Before it, `open-position` needed only the `DR-010` cost parameters; it now also
  needs `account.equity` and `risk.per_trade_pct` (one R has to be valued before a book can be
  measured in R), both caps, and — for a `.TO` name — the FX rate. All carry values today except
  the rate, so nothing is blocked; each refusal names its parameter, and
  `--acknowledge-over-cap` records past any of them. The general shape: a command that records a
  FACT now depends on parameters that describe a POLICY, which is correct fail-closed behaviour and
  is also one registry edit away from being felt.
- **Open risk excludes round-trip costs and 1R includes them.** `Position.open_risk` is
  `(entry − stop) × shares` and `sizing.allowed_risk` is spent against `entry − stop + costs`, so a
  book measured in R understates by the cost fraction — small, one-directional, and in the
  permissive direction. Recorded rather than corrected: `ALLOCATION_SPEC.md` §6 rule 6 names
  `Position.open_risk` as the quantity, and inventing a cost-inclusive variant here would put a
  second definition of open risk in the tree. §10 carries it as an open item.

### 9.4 What this still does not do

`risk.max_sector_risk` and `risk.correlation_threshold` remain `assumed:DR-006` and unenforced —
§8.4 established that both are *buildable*, not that either is built. The degeneracy guard §8.7
names is a precondition of the sector cap and does not exist yet. Neither omission weakens the two
caps above: they are the ones §8.2 shows acting on the failure mode that actually occurs.

## 10. Open items added 2026-08-22

- [ ] **Whether the book's R should include round-trip costs** (§9.3). The understatement is the
      cost fraction and always permissive. Fixing it means either a cost-inclusive open-risk
      property on `Position` or a cap expressed against `initial_risk`, and both are domain
      definitions rather than implementation details.
- [ ] **`account.fx_rate_cad` needs a value with a source and an as-of date.** Until it has one the
      cap cannot see a Canadian position at all. Owner's own note, 2026-08-22: worth doing when the
      time is right. It is not a value this record may draft — a rate is a measured market fact.
- [ ] **`risk.liquidity_cap_order_to_adtv_pct` is ratified and still reads nothing.** §2 said it
      would not bind until the account is roughly 20× larger, which is why it was not built here.
      That is a reason to defer it, not a reason for it to be invisible.

---

## 11. The correlation cap, built 2026-08-23

§8.4 established that this constraint was buildable and §9.4 recorded that it was not built. This
section is that gap closed. **It changes nothing about the parameter's status:**
`risk.correlation_threshold` is still `assumed:DR-006` and still unratified, because §8.4's
condition was that the owner rules on numbers *whose checks actually run* — and building the check
is what makes that ruling possible rather than a substitute for it.

### 11.1 The second number stopped being a note

§7 carried this as an open item: *"the 60-session window it is measured over lives in a note. Two
numbers in one parameter is the shape this registry exists to prevent."* It was worse than the item
said. The threshold's entry carried **two `note:` keys**, so PyYAML kept the second and discarded
the first — the one describing the window. The lookback was not merely unreadable by code; it was
not in the loaded registry at all.

`risk.correlation_lookback_sessions` = **60**, `assumed:DR-006`, is the fix, and both are read
together by one function for the reason §1 gives about the book's pair: a threshold measured over an
unknown window is not a threshold.

### 11.2 Where it lives

| | |
|---|---|
| The statistic | `src/swingdesk/derived_observations/correlation.py` — `daily_returns`, `pearson`, `measure` |
| The verdict | `src/swingdesk/trade_management/portfolio.py` — `correlation_limit`, `assess_correlation` |
| The candidate path | `application/pipeline.py`, step 6b, immediately after the book cap |
| The display | `presentation/report.py`, a `CORRELATION` block, plus a per-candidate line |

The statistic sits in **Derived Observations** because that is where the course's own component
registry files both topics that name it — `M49-T0761` and `M51-T0781` — and a derived observation
does not own a decision. The verdict is a risk decision and sits with the other one.

**The matrix is never built.** §8.4 measured the full 1152 × 1152 matrix at 0.09 s and that
measurement is what established the constraint was evaluable; it is not what the run does. A
candidate is correlated against the OPEN BOOK — at most `risk.max_concurrent_positions` comparisons
— because the pair that matters is candidate-to-held. Candidate-to-candidate is a ranking, and
`rs.ranking_method` is `unset` (§9.2 rule 2, reused unchanged).

### 11.3 Four readings this build had to take, all authored

None of these is in the course, and each could have gone the other way.

1. **It refuses; it does not resize.** `RISK_SPEC.md` §4 lists *"correlation threshold and its size
   adjustment"* as one unsupplied input, and the adjustment is the half nobody has specified. A
   refusal is the fail-closed reading and it is what `TODO.md` §4 planned. **This is the item most
   worth an owner ruling** — halving the size of a correlated candidate is a defensible alternative
   and would need a number this record does not have.
2. **The sign is kept: `r >= threshold`, not `|r| >= threshold`.** What §2 bounds is *duplicate*
   exposure. This system is long-only, so a strongly negative r is the opposite arrangement, and
   refusing it would forbid the one pairing that reduces the exposure the cap exists to bound.
3. **The window is the last 60 sessions the pair SHARES**, not the last 60 calendar sessions
   intersected. A halt or a vendor gap on one side removes that session from the pair rather than
   from the window, so the statistic is always computed on the number of observations it claims. The
   alternative silently measures 41 sessions and reports a 60-session correlation.
4. **A candidate already in the book meets itself at r = 1 and is refused.** Adding to a position is
   the most complete duplicate exposure there is, and the course supplies no pyramiding rule that
   would tell it apart from a second bet. Recorded as a consequence rather than discovered later.

### 11.4 The two failure directions, which look alike and are opposite

This is the part most likely to be broken by a later change, so it is stated as a rule rather than
left in the code.

- **An UNSET threshold or lookback refuses every candidate** and names the parameter. That is the
  registry failing closed on a number nobody ruled (`AGENTS.md` §3), and it happens outside the
  position-store branch, exactly as the book cap does.
- **A pair that could not be MEASURED refuses nothing.** Too little overlapping history, or a side
  that did not move, is a gap in the *system*. §3 of this record is explicit: a check the system was
  never able to perform must not fail closed into a blanket refusal, because that stops the system
  entirely while looking like risk discipline. It is recorded, counted, and printed as `UNAVAILABLE`
  — and a candidate admitted that way is reported as **unchecked**, never as independent.

`pearson` returns `None` rather than `0.0` for a constant series, for the same reason: zero is the
strongest available claim of independence and a flat series is the weakest available data.

### 11.5 What it cost elsewhere

- **The test fixture had to gain a second price path.** `conftest.make_bars` walks one arithmetic
  sequence, so every instrument in the suite correlated with every other at exactly **r = 1.00** —
  which proves the cap bites and cannot prove it admits anything. `make_bars(zigzag=True)` is the
  alternating path; the two measure about **-0.03** apart over a year, and one test asserts that
  premise so the admitting tests cannot go green for the wrong reason.
- **The stored replay case gained both parameters**, re-recorded deliberately. `output_hash` was
  unchanged at `0a3858a76dbe8d0b` — that case passes no position store, so no candidate reaches the
  measurement — and only `config_hash` moved. A determinism gate whose hash had moved here would
  have been reporting a real change; it did not.
- **Track A is unaffected.** `pipeline.py` is frozen under `DR-015` §3, and this change does move
  decision output — but the counter restarted on 2026-08-22 and reads from
  `tools/track_a_streak.py`, never from this document (`AGENTS.md` §10.6).

### 11.6 What is still not built

`risk.max_sector_risk` alone. §8.7's degeneracy guard remains its precondition: the vendor answers
`NEAR` → healthcare 100.0% for a short-maturity bond fund, confidently and wrongly, and consuming
that would spend an entire sector budget on a fiction. Nothing in this section makes that closer or
further away. **§12 closes it, the same day.**

---

## 12. The sector cap, built 2026-08-23

The last of the six. `risk.max_sector_risk` stays `assumed:DR-006` and unratified for the same
reason §11 gives about the correlation threshold, and this section records what now enforces it.

### 12.1 The guard landed with the feature, because §8.7 said it had to

The vendor answers `NEAR` — a short-maturity bond fund with no equity sectors at all — as
**healthcare 100.0%**, every other sector 0.0%. `reference_data/classification.py`'s `look_through`
refuses a fund look-through in that exact shape and reports `unavailable`. It never consumes it.

**The test is EXACT, and that is a design choice worth stating.** A genuine sector ETF is
legitimately almost all one sector, so a tolerance would refuse the instruments this cap most needs
to see; the bond funds §8.7 measured come back at exactly 1 with every other sector at exactly 0,
while a real single-sector fund carries a remainder elsewhere. Exactness is what separates the
vendor saying *not applicable* in the only vocabulary it has from the vendor answering correctly.

**The known weakness, recorded rather than discovered later.** `funds_data.asset_classes` on the
same vendor object reports stock/bond/cash shares directly and would identify a bond fund without
this inference. It is the better guard, it is not used, and the reason is that it has not been
measured against this vendor — §8.7 specified the test that had been. A false positive here fails
toward `unavailable`, which **admits** the candidate unchecked; that is the permissive direction,
which is why §12.5 carries it as an open item rather than treating it as settled.

### 12.2 Where it lives

| | |
|---|---|
| The store | `reference_data/classification.py` — `ClassificationStore`, bitemporal, read as-of |
| The guard | the same file — `look_through`, pure, applied on the way OUT of the store |
| The vendor | `market_data/vendor_yahoo.py` — `fetch_classification` |
| The budget | `trade_management/portfolio.py` — `sector_limit`, `sector_book`, `assess_sector` |
| The candidate path | `application/pipeline.py`, step 6c, after the correlation cap |
| The refresh | `tools/refresh_classifications.py`, a separate pass |
| The display | `presentation/report.py`, a `SECTOR` block, plus a per-candidate line |

**Judged on the way out, not on the way in.** The vendor's answer is stored as given and refused
when read. Refusing at the fetch boundary would store nothing, and *"we asked and the answer was
unusable"* would become indistinguishable from *"we never asked"* — two different facts about the
same instrument, and only one of them is a reason to try again.

**Classification is a separate pass**, for the reason `refresh_universe.py` gives about bars: one
more vendor round trip per instrument, on a universe of 1152 members, inside a 45-minute evening
budget (`NFR.md`), to refresh a fact that changes a few times a year.

### 12.3 The arithmetic, and the ETF requirement it discharges

Appendix C's control cell says sector risk must count ETFs and correlations. An ETF therefore
consumes its **constituents'** sector budget rather than sitting outside it, so a candidate is
measured through its weights and never by a single label:

- an ordinary share carries its own sector as a single weight of 1;
- a fund carries its look-through;
- both are the same quantity, which is what lets the budget add a share to an ETF with no special
  case anywhere in the arithmetic.

Consequence, and it is the point of the requirement: on a book holding 1.50R of technology, a
pure-technology candidate asking 1R is refused at 2.50R while the same 1R through a
30%-technology fund is admitted at 1.80R. Both halves have a test, because either alone is
satisfied by a cap that ignores weights entirely.

### 12.4 Three ways the answer can be incomplete, and they are not the same

This is the part most likely to be flattened by a later change.

| | What it means | What happens |
|---|---|---|
| The **cap** is unset | nobody ruled the number | every candidate refuses, naming the parameter |
| The **candidate** cannot be classified | the check did not run | admitted **unchecked**, reported `UNAVAILABLE` |
| A **position** cannot be classified, or its look-through is partial | the split understates | nothing refuses; the report says the split understates |

The second is §3 of this record, verbatim in effect: a check the system was never able to perform
must not fail closed into a blanket refusal, because that stops the system entirely while looking
like risk discipline. **Until `tools/refresh_classifications.py` has run, that is every candidate**,
and the report says so on every run — which makes `unchecked` a coverage number to close rather
than a verdict to read past.

The third is the quietly dangerous one, because it is silent by nature: an unclassifiable position
and a partial look-through both make every per-sector figure an **understatement**, and an
understated sector admits candidates the full picture would have refused. `SectorBook.is_complete`
exists so that the report can say it out loud, and the block prints the unattributed R next to the
split rather than under it.

**A partial look-through spends what it reports and no more.** Weights summing to 0.94 put 94% of
the position's R into sectors and 6% into `unclassified_r`. Normalising to 1 would invent
composition the vendor did not report; dropping the position would hide exposure that was measured.
Carrying the remainder visibly is the only option that neither invents nor discards.

### 12.5 What this still does not do

- **The point-in-time sector is still missing, and is now ENCODED rather than described.** The store
  is read as-of, so a run replayed before the first pull finds nothing and reports `unavailable`. It
  does not answer a 2016 question with today's classification. §8.4 d is unchanged: that restricts a
  BACKTEST and does not restrict live admission.
- **The degeneracy guard should be `asset_classes`, once someone measures it** (§12.1). One vendor
  call answers it; nobody has made it, and inventing the answer here would be the substitution this
  record refuses everywhere else.
- **The classification store starts empty and nothing schedules the refresh.** `swingdesk scan`
  opens the store, so the cap is wired; `tools/refresh_classifications.py` fills it and is a manual
  pass, like `refresh_universe.py`. Whether it joins the weekend prep task is an operational
  decision, not a code one — `docs/runbooks/README.md` §1 carries it.
- **`risk.max_sector_risk` = 2R was anchored against the 6R book and the anchor moved to 4R** (§8.3)
  without this number moving with it. At 6R it was one third of the book; at 4R it is half. That may
  be right — half the book in one theme is still a bound — but it is now a different statement from
  the one §2 argued, and it is the owner's to rule on. §13 carries it.

---

## 13. Open items added 2026-08-23

- [ ] **The correlation cap REFUSES; the course also names a size adjustment** (§11.3 reading 1).
      `RISK_SPEC.md` §4 lists *"correlation threshold and its size adjustment"* as one unsupplied
      input and only the threshold has a value. **Measured in §15**, which supports keeping the
      refusal and finds the size adjustment unnecessary rather than merely unauthored: refusing
      costs nothing measurable in return, and halving would keep half of an exposure that gaps
      together five times more often. Still open — the ruling is the owner's.
- [ ] **`risk.max_sector_risk` = 2R was one third of a 6R book and is half of a 4R one** (§12.5).
      Ratified numbers moved around it and it did not move. Owner ruling — **measured in §14, which
      supports keeping 2R on a different argument from the one §2 made.** Still open: the ruling is
      the owner's and §14.4 states the case against as well as for.
- [ ] **The degeneracy guard should read `asset_classes` rather than infer from the weights**
      (§12.1). One measurement against the vendor decides it. Until then a genuine fund reporting
      exactly one sector at exactly 100% is refused, which admits it unchecked.
- [ ] **Nothing schedules `tools/refresh_classifications.py`.** The cap is wired and its input is
      empty, so today it reports `unavailable` for every candidate — correctly, and uselessly.

---

## 14. Calibrating the sector cap, 2026-08-23

§13 asked whether 2R is still the right sector budget. Owner asked for research rather than a
ruling on the argument alone. This is it.

Reproduce with:

```bash
python tools/measure_sector_cap.py --classifications docs/decisions/measurements/sector-classifications-2026-08-23.json --out docs/decisions/measurements/sector-cap-calibration-2026-08-23.json
```

Both files are in `docs/decisions/measurements/`. Every figure below comes out of the second one;
none is typed from memory.

### 14.1 The first finding is about the evidence, not the cap

**`PR-005`'s base slice held a median of 20 positions at once, a maximum of 54, and was over four
on 95.1% of days.** It is a per-instrument backtest with no capital constraint. It never simulated
a four-position book and **cannot be replayed as one.**

That is worth saying plainly because §8.1 used the same log to move the anchor from 6R to 4R and
was right to: a per-trade gap loss of −1.692R is concurrency-independent. A sector budget is not.
So this section does not measure what a capped book would have returned; it measures the
**population a four-position book would have drawn from**, and samples four names from it. The draw
is uniform because `rs.ranking_method` is `unset` and §6 rule 4 of `ALLOCATION_SPEC` forbids
falling back to any order the system happens to have — a uniform draw is the only assumption that
does not smuggle in the ranking the system refuses to make.

### 14.2 What each candidate cap actually means, in positions

At 0.98R per position — this system's own sizing, shares rounded down — the heaviest sector in a
four-position book, over 704,200 sampled books:

| | heaviest sector |
|---|---|
| median | **1.17R** |
| p75 | 1.96R |
| p90 | 2.01R |
| p95 | 2.21R |
| p99 | 2.94R |
| max | 3.92R |

The discrete structure is visible in those numbers and is the clearest way to read the choice:
0.98R is one position in a sector, 1.96R is two, 2.94R is three, 3.92R is all four. So

| cap | means | refuses |
|---|---|---|
| **1.33R** (a third of a 4R book) | at most **one** of four in one theme | **37.9%** of books |
| **2R** (what the registry carries) | at most **two** of four | **11.3%** of books |
| **3R** | at most three | **0.6%** of books |

**§4 predicted the last row and it holds.** That section rejected 3R open risk on the grounds that
*"sector and correlation caps would never bind and the concentration rules would be decorative"*.
At 0.6% a 3R sector cap is decorative, measured rather than asserted.

### 14.3 The two caps are not redundant, and this is the number that decides it

The obvious objection to any sector cap now that §11 exists: same-sector names are the correlated
ones, so is the correlation cap already doing this job? Measured over the 59 usable instruments,
every pair correlated over the ratified 60-session window and split by whether the two share a
dominant sector:

| | pairs | median r | p90 | at r ≥ 0.70 |
|---|---|---|---|---|
| same dominant sector | 230 | **+0.293** | +0.750 | **15.2%** |
| different sector | 1,481 | +0.118 | +0.438 | **1.6%** |

Two things follow, and they point in opposite directions.

**Sector membership genuinely predicts correlation** — a tenfold lift, 15.2% against 1.6%. The two
caps are measuring related things, so a sector cap is not noise next to a correlation cap.

**And the correlation cap catches only 15% of same-sector pairs.** The median same-sector pair sits
at r = 0.29, which is not one bet by any reading of §2. So **85% of what a tight sector cap would
refuse, the correlation cap does not** — the overlap is weak, and the sector cap is doing
non-redundant work: bounding names that would fall together on a sector shock without having moved
together in the last quarter.

### 14.4 What this supports, and it is a recommendation rather than a ruling

**Keep 2R** — but retire §2's justification for it and stand it on this instead.

*"One third of the book"* was true at a 6R anchor and is not true at 4R; repeating it would be
quoting a sentence whose premise moved. What the measurement supports is different and stronger:
2R is the cap that binds where concentration is genuinely extreme (the top ~11% of books) while
1.33R refuses more than a third of all books, and in roughly 85% of those refusals the two names
were not correlated at all — a lot of refusals earned by a label rather than by a measured
relationship. With four slots and eleven sectors, "at most one per sector" is close to forcing
perfect sector diversity on a book that small.

**The ruling is still yours.** The case for 1.33R is not empty: a sector shock is exactly the
correlated-gap failure §8.2 built the whole block around, and 15.2% of same-sector pairs really do
move together. Choosing 2R accepts that two positions — **−3.38R at the measured gap loss** — can
be lost to one theme overnight, which is a fifth of the −15R drawdown pause in a single session.

### 14.5 Three limits on every number above

1. **The sectors are today's, not the ones in force in 2016** (§8.4 d). A name that changed sector
   is misfiled for its whole history. This is the point-in-time gap, and it bounds this measurement
   exactly as it bounds any backtest.
2. **59 usable instruments is a thin cross-section, and it leans heavily financial.** Financial
   services was the most-represented sector on **57%** of days. A universe with that shape produces
   more same-sector collisions than a balanced one would, so the refusal rates above are more
   likely overstated than understated.
3. **Nine of the 68 are refused by §8.7's guard** and contribute to no sector, so measured
   concentration is an understatement by whatever they hold. The nine — `FIXD`, `FLTR`, `IAGG`,
   `NEAR`, `SH`, `TLT`, `UITB`, `VXX`, `WEAT` — are bond, inverse, commodity and volatility
   products without exception, and **not one genuine equity fund was refused**. That is the first
   evidence that §12.1's exactness argument holds outside the one case §8.7 measured.

### 14.6 And the research found a defect in §12's own build

**The vendor spells its eleven sectors two ways and the difference is silent.** An equity comes
back `Financial Services`; a fund look-through comes back `financial_services`; `Real Estate`
becomes `realestate` with no separator at all. Both vocabularies hold exactly the same eleven
sectors and nothing else.

Shipped unmapped, a share and an ETF in the same sector would each have received their own budget —
`LYV` (Communication Services) and `FCOM` (communication_services) counted as two themes — so a
concentrated book would have reported as a diversified one. **The cap would have failed in the
permissive direction, silently**, which is the same failure shape §8.7 was written about one layer
up and the reason that section insists the guard is a precondition rather than a refinement.

`reference_data.classification.canonical_sector` now maps both spellings to one label before
anything is compared or added, and merges weights that collide. A vendor answer carrying **both**
spellings of one sector, summing past 100%, is refused rather than clamped: clamping picks a number
the vendor never gave, on the one input that proves it wrong.

Found only because the calibration ran against real vendor output. It is not reachable from the
fixtures, and no gate would have caught it.

---

## 15. Calibrating the correlation cap, 2026-08-23

§13 asked whether the correlation cap should RESIZE rather than refuse. Owner asked for the same
treatment §14 gave the sector budget. Reproduce with:

```bash
python tools/measure_correlation_cap.py --out docs/decisions/measurements/correlation-cap-calibration-2026-08-23.json
```

Every correlation below is computed over the 60 sessions ending **strictly before** the candidate's
entry date, by the same `pearson` the run uses. A calibration correlating over today's window would
be answering a question the system never gets to ask.

### 15.1 How often the cap actually bites

**On a four-position book — the production number: 20.2% of candidates.** For **56.2%** of
candidates it is exactly zero, because nothing correlated is held at all. Computed rather than
sampled: with `n` names held and `k` of them correlated, the chance a three-name book contains at
least one is `1 - C(n-k,3)/C(n,3)`, and the correlated share of held names averages **9.2%**.

**Do not quote `PR-005`'s own figure of 43.5%.** Its book held a median of **22** names, so a
candidate had twenty-two chances to collide rather than three. The same trap §14.1 names: that log
is a per-instrument backtest with no capital constraint, and every figure taken from it has to be
corrected for a book size it never had.

### 15.2 What refusing would have cost — and the honest answer is *nothing measurable*

| | trades | mean | 95% block CI | median | p5 | loss rate |
|---|---|---|---|---|---|---|
| would be refused | 1,660 | **+0.057R** | **[−0.063, +0.169]** | −0.597 | −1.209 | 56.3% |
| admitted | 2,153 | −0.004R | [−0.080, +0.085] | −1.007 | −1.414 | 60.1% |

The interval is a **block bootstrap resampling whole calendar years**, not a standard error over
trades: the same trade appears in many co-held pairs and a year's trades share a regime, so a naive
interval would describe a sample that does not exist. Both intervals **contain zero and overlap
almost entirely.**

So the refused trades were not worse. They were, if anything, marginally better, and refusing them
would have forgone **+94.3R** across 1,660 trades — a figure that looks decisive and is not, because
the interval around it crosses zero. **Refusing costs nothing measurable, and it saves nothing
measurable either.** Any argument for this cap that rests on return is unsupported here.

Note also what refusing does NOT do: the refused trades have a **shallower** left tail (p5 −1.209
against −1.414). Removing them does not cut the per-trade downside.

### 15.3 The premise, on two measures that disagree — and the disagreement is the finding

§2 justifies the threshold by asserting that two names sharing about half their variance are one
bet. Tested rather than repeated, on co-held pairs:

| | pairs | measure | above r ≥ 0.70 | below |
|---|---|---|---|---|
| coarse | 8,352 / 74,867 | `P(both lose over the holding period)` | **22.8%** | **24.5%** |
| precise | 8,352 / 74,867 | **`P(both gapped out on the SAME session)`** | **1.030%** | **0.208%** |

**On the coarse measure the premise fails** — correlated pairs ended up losing together very
slightly *less* often. That is reported first and in full, because a calibration quoting only the
supportive measure is how `PR-008`'s strongest sentence passed sixteen gates and was false.

**On the precise measure it holds hard: a lift of 4.94×, 95% block CI [2.32, 7.56].** Resampling
whole calendar years — the right block, since §8.6 measured 89 sessions holding 52% of all gap
exits — the interval does not come close to 1.

The two are reconciled by what each asks. Two names can move together every day and still exit
weeks apart for unrelated reasons, so the holding-period measure washes the effect out. The
same-session gap is the failure mode §8.2 built this entire block around: the simultaneous
overnight move a per-trade stop cannot defend against, because the price the stop names does not
trade between the close and the open. **The cap is not there to improve the average trade. It is
there to stop two positions from being one overnight event, and on the measure that means that,
correlation predicts it five-fold.**

### 15.4 What this supports

**Keep the refusal. The size adjustment is unnecessary rather than merely unauthored.**

The reasoning is short because the two measurements above do all the work. Refusing costs nothing
measurable in return (§15.2). Halving instead would keep half of an exposure that gaps together
**five times more often** (§15.3), and would buy that by authoring a multiplier this project has no
basis for — which `AGENTS.md` §3 forbids for exactly this shape of reason. There is nothing to
trade off: the cheaper rule is also the one with the better-evidenced risk reduction.

This does not make `risk.correlation_threshold` `validated`. A parameter becomes validated by a
pre-registered study against this universe, and this is a calibration attached to a decision record.
What it does is retire the reading in §11.3 as *provisional* and replace it with a measured one.

### 15.5 Four limits on every number above

1. **`PR-005`'s strategy is refuted** and its base slice returns about +0.028R per trade. Every
   expectancy figure in §15.2 is measured on a strategy with no established edge, so "refusing cost
   nothing" is a statement about *this* population and not a law.
2. **`PR-005` never simulated a capped book** (§14.1). §15.1 corrects for book size arithmetically;
   §15.2 and §15.3 are conditional statistics on trades that were actually taken, which is weaker.
3. **86 same-session gap events above the threshold** is a small count, which is why the lift
   carries a bootstrapped interval rather than a point estimate.
4. **68 instruments, one arm, one regime.** The same thin cross-section §14.5 names, and it leans
   heavily financial. **§16 closes this one at full width, the same day, and it moved both
   calibrations.**

---

## 16. The wide cross-section, 2026-08-23 — and what it corrected

§14.5 limit 2 and §15.5 limit 4 were the same complaint: 59 usable instruments out of `PR-005`'s
68-name sample is thin, and it leaned heavily financial, so every refusal rate taken from it
described that sample rather than the universe a run nominates from.

**That limit is now closed**, because the two structural questions need no trade log — only stored
bars and stored classifications. `tools/refresh_classifications.py --universe` classified the whole
admitted universe on 2026-08-23: **1,148 of 1,148, zero vendor failures, 125 unusable** once §8.7's
guard had judged them (10.9%). Reproduce the rest with:

```bash
python tools/measure_sector_cap.py --classifications docs/decisions/measurements/sector-classifications-2026-08-23.json --wide
```

### 16.1 The universe is not financial-heavy. That was the sample.

| sector | share of the admitted universe, by weight |
|---|---|
| financial services | 17.2% |
| technology | 17.1% |
| healthcare | 14.6% |
| industrials | 13.5% |
| consumer cyclical | 10.0% |
| basic materials · real estate · energy · consumer defensive · utilities · communication services | 3.5–5.6% each |

Five sectors between 10% and 17%, then a tail. **The *"financial services was the most-represented
sector on 57% of days"* figure in §14.5 is a fact about `PR-005`'s 68 names and nothing else**, and
carrying it as a property of the universe would have been exactly the kind of borrowed conclusion
§10.3 of `AGENTS.md` warns about — inside this project rather than from outside it.

### 16.2 The correlation cross-tab holds, and the non-redundancy argument gets stronger

Over 1,023 usable instruments and 522,753 pairs, against the 59-instrument version in §14.3:

| | pairs | median r | p90 | at r ≥ 0.70 |
|---|---|---|---|---|
| same dominant sector | 70,553 | +0.207 | +0.618 | **6.38%** |
| different sector | 452,200 | +0.073 | +0.364 | **0.82%** |

The **lift survives** — 7.8× here against 9.8× on the narrow sample, the same order — so sector
membership really does predict correlation.

But the absolute rate fell by more than half, from 15.2% to **6.38%**. So **93.6% of same-sector
pairs are not caught by the correlation cap**, against 85% on the narrow sample. §14.3's conclusion
that the two caps do non-redundant work is not merely intact; it is stronger than the narrow data
suggested.

### 16.3 What each cap costs on the real universe — and one figure moved the wrong way

20,000 four-position books drawn uniformly from the admitted universe, both caps scored on the
**same** draw because that is how step 6 applies them:

| | refuses |
|---|---|
| correlation cap (r ≥ 0.70 with any held name) | **4.15%** |
| sector cap at 1.33R | **49.65%** |
| sector cap at **2R** | **14.16%** |
| sector cap at 3R | **0.66%** |

**The correlation cap is far cheaper than §15.1 estimated** — 4.15% against 20.2%. That estimate
came from `PR-005`'s own book, and those 68 names were markedly more correlated with each other
than the universe is. The corrected figure makes the cap a rarely-binding rule aimed at a 5× effect,
which is the best shape a risk control can have.

**The sector cap at 2R is slightly MORE expensive than §14.2 estimated**, not less — 14.16% against
11.3%. Recorded because the expectation ran the other way: a balanced universe was assumed to
collide less, and with four draws across eleven roughly-equal sectors it collides more. The
birthday arithmetic is the whole of it, and guessing the sign of that was a mistake.

**1.33R nearly doubled, to 49.65%.** With four slots and eleven sectors it now refuses **half of
all books**, which is close to forbidding any repeated sector at all.

### 16.4 What this does to the two recommendations

**Both stand, and both are better supported than they were.**

- **Sector: keep 2R.** §14.4 argued it on the narrow data; the wide data makes the alternative
  worse rather than the recommendation better. 1.33R refusing half of every book is not a
  concentration limit, it is a diversification mandate the course never asked for, and §16.2 shows
  most of what it would refuse is not correlated. 3R remains decorative at 0.66%, twice measured.
- **Correlation: keep the refusal.** §15.4's argument was that refusing costs nothing measurable
  while halving would keep half of a five-fold gap exposure. §16.3 adds that the rule fires on only
  4.15% of books, so what it costs is smaller again — and a size adjustment nobody has authored is
  being weighed against a rule that rarely triggers.

**Neither ruling is taken here.** §13 still carries both, and both parameters stay `assumed:DR-006`.

### 16.5 What is still narrow, and it is the important half

**Everything about OUTCOMES.** §15.2's expectancy, §15.3's same-session gap lift, and §14.2's
book-drawn-from-held-positions all need a trade log, and the only trade log this project holds
covers 68 names from a single arm of `PR-005` — whose registered hypothesis was rejected. The
structural half is now measured at full width; the behavioural half is not, and no amount of
classification fixes that. It needs a backtest over a wider sample, which is a study rather than a
calibration.

`PR-005`'s own sample was 320 symbols, of which the liquidity rule rejected 215, short history
excluded 28, and the vendor failed on 9 — 68 survivors. **The universe is 1,148 admitted of 3,713
with bars, out of 13,136 eligible: coverage is 28.3%**, and that, rather than the universe rule, is
what bounds a wider study today.

---

## 17. Both remaining rulings, taken 2026-08-23

§16.4 put two recommendations to the owner and said *"neither ruling is taken here."* Both are taken
now, both as recommended, and this record moves from partially to fully ratified. **No threshold
moves.** What changes is that two parameters stop being provisional and one of them stops resting on
a premise that had already gone.

### 17.1 `risk.max_sector_risk` — keep 2R, on the measured argument and not §2's

**Ruled: keep 2R.** Status moves `assumed:DR-006` → **`owner`**.

And §14.4's other half is ruled with it: **§2's justification is retired.** *"One third of the
book"* was true against a 6R anchor; §8.3 moved the anchor to 4R without moving this number, so 2R
is now half the book and the old sentence quotes a premise that no longer holds. Repeating it would
be the proxy failure `AGENTS.md` §12 names — answering from a document that once said the right
thing rather than from the artefact that owns the claim.

What the ruling stands on instead, from §14.2 and §16.4:

- 2R binds where concentration is genuinely extreme — the top ~11% of books — while **1.33R refuses
  more than a third of all books**, and in roughly **85%** of those refusals the two names were not
  correlated at all. Those are refusals earned by a label rather than by a measured relationship.
- With four slots and eleven sectors, *"at most one per sector"* is close to forcing perfect sector
  diversity on a book that small.

**The cost is named rather than argued away.** Two positions — **−3.38R** at the measured gap loss —
can be lost to one theme overnight, which is a fifth of the −15R drawdown pause in a single session.
§14.4 put that case for 1.33R honestly and the ruling accepts it with its eyes open.

### 17.2 The correlation cap — keep the refusal; the size adjustment is closed

**Ruled: refuse, do not resize.** The open question §11 has carried since this record was written is
**closed**, and closed as *unnecessary* rather than *unauthored* — which is the stronger of the two
and the one §15.4 argued.

The reasoning is §15.4's and §16.3's, and it needs no expansion: refusing costs nothing measurable
in return, the rule fires on only **4.15%** of books, and halving instead would retain half of an
exposure that gaps together **five times more often** while requiring a multiplier nothing in this
project supports. There was no trade-off to make — the cheaper rule is also the one with the better
evidence behind it.

**`risk.correlation_threshold` stays `assumed:DR-006` and that is deliberate.** The ruling settles
the SHAPE of the rule, not the number. 0.70 becomes `validated` through a pre-registered study
against this universe and through nothing else — not through a calibration attached to a decision
record, and not through an owner ruling about whether to refuse or resize. §15.4 said so before the
ruling existed and it is worth repeating after it.

### 17.3 What this ruling does not touch

- **`risk.correlation_lookback_sessions`** stays `assumed:DR-006`. Nobody was asked about 60
  sessions and nothing above measures it.
- **Every limit in §14.5, §15.5 and §16.5 stands.** Today's sectors rather than point-in-time ones,
  a thin behavioural sample from one arm of a refuted study, and the nine products §8.7's guard
  refuses. A ruling is a decision about what to do under uncertainty; it does not reduce the
  uncertainty, and §16.5's *"everything about OUTCOMES"* is unchanged.
- **`DR-014` still makes this paper-only**, so neither cap is spending real money today. That is why
  neither was blocking, and it is also why leaving them provisional had a cost worth ending: a
  parameter that reads `assumed` forever is one nobody ever has to defend.
