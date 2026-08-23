# DR-006: The portfolio risk block

```
date:       2026-08-08
status:     accepted — partially ratified by the owner 2026-08-22 (four of six; sector and
            correlation stay proposed, §8.4)
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
further away.
