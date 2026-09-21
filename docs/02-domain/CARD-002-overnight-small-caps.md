# CARD-002 — Overnight small caps

**Status:** drafting · **Tier:** 2 (domain) · **Card version:** 1 · **Family selected by the
owner:** 2026-09-20

**The CARD's validation status is `Untested`** — as every card starts, and as it must stay until
journalled trades exist (`criteria.yml` v1.1.0: Track B evaluates on journalled trades only). A
backtest is evidence about a hypothesis, never about a card.

The machine-readable card is [`registry/cards.yml`](../../registry/cards.yml); this document is its
reasoning, the same split `CARD-001` uses.

**Nothing here is running.** §6 lists what must be built first. The size was ruled by the owner on
2026-09-20 — **50% of equity a fund, the account fully invested every night**, which is `PR-034` as
measured; the card still cannot run because the two passes §6 names do not exist.

---

## 1. What it trades, in one paragraph

**Buy `IJR` and `VB` in the closing auction, sell both in the next session's opening auction, every
session, unconditionally.** There is no selection, no trigger, no timing and no stop. The claim is
not a signal: it is the measured fact that these funds' return accrues while the market is shut and
their own sessions lose money (`PR-034`, `EVIDENCE_SUMMARY` §32). The card owns a clock, not a view.

That makes it the simplest card this project can hold. Everything a strategy usually decides — which
instrument, when to enter, when to leave, where the stop sits — is fixed by the calendar, and the
only real choices are **how much** and **what the fills cost**.

## 2. Why this is a card and not another study

`PR-034` returned `ACCEPT` and licensed exactly one thing: *a specification for a paper trial*. The
reason it licenses a trial rather than a decision is that **the one number the backtest could not
measure is the one the trial produces**: every fill is an auction, and this project has priced
auctions only on stocks (`PR-025`, `PR-030`). The trial's product is not "does it earn" — that is
measured — it is **what the closing and opening auctions actually give a small account**.

| what it says | where it comes from |
|---|---|
| the night earns +13.8% a year net at half a cent a share, +11.7% at a cent | `PR-034`, 2,692 sessions |
| the session on the same funds loses 5.4% a year | `PR-034` |
| the night's Sharpe ratio is 1.06 against holding's 0.59 | `PR-034` — the first result in this project to beat holding per unit of risk |
| the last 590 sessions are its best stretch (15.7% a year at 1.24) | `PR-034`'s recent gate |
| the arms are an exact decomposition of holding (3e-16) | `PR-034` §9 |
| **the effect is not a wrapper around this decade** — over 2004-2015 the night compounded at 10.6% against holding's 8.8%, with a −21.1% drawdown against −58.8% | `PR-036`, 3,002 sessions nobody here had read |

**And what it does not say**, carried here so the card cannot outrun its evidence: `IJR`, `VB` and
`IWM` hold overlapping companies, so this is not an independent second sample; and the worst
drawdown is −31.6%, an equity drawdown.

**And what `PR-036` added on the same evening, which raises the stakes on the fill measurement
rather than lowering them.** The pre-2016 decade answers the epoch objection — the night beat
holding there too, on return and on drawdown — but it returned `COST_FRAGILE`: at a whole cent a
share a side the interval touches zero. The reason is arithmetic, not an era. A cent is a fraction
of the share price, these funds traded at about a third of today's price in that decade, and the
same cent cost 2.6× more. **So the card's edge is a cost question at least as much as a signal
question**, and the twenty sessions in §7 are what settles it.

**Tax, stated correctly for THIS owner and not for a textbook.** The owner holds a TAXABLE account
and funds it in Canadian dollars (owner, 2026-09-20). The American framing an adviser reached for —
short-term versus long-term capital gains — **does not apply**: Canada does not distinguish them.
What does apply is the risk that a rule trading every session is assessed as BUSINESS INCOME rather
than capital gains, which changes the inclusion rate rather than the rate itself. That is a question
for an accountant, it is immaterial at the twenty-session measurement size below, and it is material
at scale. **Nothing in this project is tax advice.**

## 3. The rules, field by field

`STRATEGY_CARD_SPEC` §4's merged record. Fields the family does not use say so rather than being
left blank.

| group | field | this card |
|---|---|---|
| Scope | markets · instruments | US; `IJR` and `VB`, equally weighted |
| Scope | timeframe · holding horizon | one night: the close to the next session's open, about 17.5 hours |
| Scope | allowed regimes | every session. The card does not time, and a regime filter would be a new configuration and a new study |
| Context | 1Y/3M · 30D · trend | **none, by construction.** Nothing is read but the calendar and the prior close |
| Entry | candidate selection · setup · trigger · confirmation | **none.** Both funds, every session |
| Entry | method | **market-on-close** (`cls` time-in-force), placed by the close pass between **15:35 and 15:45 ET** — ten minutes of slack before Alpaca's 15:50 cutoff |
| Entry | maximum entry | none. A market-on-close order cannot carry a limit, and `DR-027` §3.1's argument for a limit does not apply where the price paid IS the benchmark being measured |
| Entry | what the fill should cost | **possibly less than modelled, and that cuts the other way.** `PR-033`..`PR-035` charged half a cent a share a side, a number inherited from `PR-031`, where fills met the continuous book. An auction order does not: `cls` and `opg` clear at the auction's single price, so the spread a taker pays is not charged at all and what remains is the fees. If the twenty sessions below show that, the night's measured 13.8% a year is the PESSIMISTIC reading and the gross 16.0% is nearer the truth. The measurement decides it in either direction |
| Invalidation | initial stop | **none — see §4.** The exit order at the venue is the protection |
| Invalidation | cancellation | the kill switch absent, a fund's bar stale (`DR-015`), or the account short of cash |
| Sizing | rule | equal weight: each fund gets `overnight.position_pct` — **50%, ruled 2026-09-20** — of equity, shares from the prior session's close, rounded down |
| Sizing | portfolio constraints | `overnight.position_pct` = 50 (ruled 2026-09-20, §7), which exceeds `risk.max_position_pct` = 25 deliberately — the parameter note carries the reasoning |
| Exits | exit | **market-on-open** (`opg`) for the whole position, placed by the evening pass after 19:00 ET for the next session |
| Exits | targets · trailing · partials · time | none; the exit IS the time exit |
| Gates | skip · pause · error | the kill switch (`.paper-trading-armed`), the host allowlist, `A-002`'s paper-only boundary, a stale or missing prior close, an unfilled entry (no entry, no exit order), and a rejected `cls` order |
| Data | requires | the two funds' daily bars for sizing; the venue for fills; the minute store for the fill-quality check |
| Data | latency and degradation | a missing or stale prior close refuses the session for that fund (`FAIL_CLOSED_POLICY` §3); a fund that did not fill is simply not held, and the other one still is |
| Validation | protocol | `PR-033` and `PR-034`, both reported; the trial measures fills, not returns |
| Validation | status | `Untested` |
| Monitoring | kill criteria | §5 |

**Risk, denominated.** `RISK_SPEC` §2 requires every position to report `R`, and `R` is normally
`entry − stop + costs`. This card has no stop, so **`R` is the position's notional times the
14-session standard deviation of that fund's overnight return** at the decision close, the same 14
sessions `PR-031`..`PR-034` used. It is a measured quantity, it refuses when fewer than 14 sessions
are stored, and it makes a night's loss readable in the same unit as every other position this
project has ever journalled.

## 4. Why there is no stop, and why that is not a hole

`DR-027` §3.2 requires the stop to exist at the venue from the moment the fill does, because *"a
stop the market cannot see is not a stop"*. That rule was written for a position held for days,
exposed to a market that is open. This position is held **only while the market is shut**.

1. **A stop cannot trigger while the exchange is closed.** The first moment any protective order
   could execute is the opening auction.
2. **The opening auction is exactly when this card already sells**, in full, at market.
3. So a stop would be a second order competing for the same shares at the same instant — and
   `DR-044` is this project's record that a queued cancel is not protection.

**What replaces it, and it is stronger than a stop:** from the evening pass until the open, the
venue holds a market-on-open sell for the entire position. The exit is resting at the venue, it is
unconditional, and it needs no trigger. The window between the 16:00 fill and the evening pass —
when no exit order is lodged — is a window in which **no execution is possible for anyone**.

**What this does not protect against, stated plainly:** an overnight gap. The card is long the
market while it sleeps, which is the whole of its exposure and the whole of its edge. `PR-034`
measured what that cost historically: a −31.6% worst drawdown.

## 5. Monitoring, and the criteria that stop the trial

The trial exists to measure fills. **A drawdown is not a criterion**: `PR-034`'s own years show the
night falling 17.4% in 2022, 17.8% in 2025 and 31.6% in 2020, so a return trip-wire tight enough to
catch a defect would fire on an ordinary bad quarter. What stops the trial is the machinery being
wrong, or the fills not being the prices the whole case rests on.

| what is watched | measured how | what it does |
|---|---|---|
| **the machinery** | a position held with no exit order lodged; a position still open after the opening auction; a rejected or unfilled order | **stops the trial.** This is a defect |
| **divergence from the model** | each night's realised return against what the same night earned at that session's official auction prices — the difference IS the slippage | **stops the trial** when it exceeds **1 cent a share a side** over 20 sessions: `PR-034`'s cost-adverse gate is that cent, and past it the edge is gone |
| the drawdown | the book's equity | **alerts the owner at −25%.** It is the market, not a defect, and `PR-034` measured worse |
| the sample | sessions journalled | **no judgement before 60 sessions.** The daily noise is about ±0.8% of equity against a mean of +0.055%: a month says nothing |

Weekly report; none of these is a verdict about the strategy, which needs the journalled sample
`criteria.yml` defines.

## 6. What must be built, in order

Nothing on this list exists. `CHARTER` A-003 §4 records the gap and `CONSTRAINTS` §4 calls it a
build gap rather than a scope rule.

1. **The close pass** — a run between 15:40 and 15:48 ET that sizes both funds from the prior close
   and submits two `cls` market buys. Needs `BrokerPolicy` to permit `cls`, which today's policy
   does not name.
2. **The evening pass** — a run after 19:05 ET that reads the filled positions and submits an `opg`
   market sell for each. It is the protection, so a failure to place it is an alert, not a log line.
3. **The morning reconciliation** — the existing read-only broker read, after the open, checking
   every position closed and journalling the night: entry fill, exit fill, dividend if the date had
   one, and `R`.
4. **The fill-quality measurement** — each fill against the stored auction price, which is what §5
   watches and what `PR-034` could not measure.
5. **The journal entry shape** — a night is one trade with two fills; `TRADE_JOURNAL`'s existing
   record takes it unchanged, and this list says so rather than assuming it.

Each step is specification-first work under `A-001`: a decision record before the code, and the code
behind the same four guards `DR-027` §4 already imposes.

## 7. What the owner has ruled, and what is still open

**Ruled 2026-09-20:**

1. **Size — 50% of equity a fund**, the account fully invested every night. That is `PR-034` as
   measured, and it deliberately exceeds `risk.max_position_pct`; the parameter's note carries the
   reasoning and the drawdown it implies. **The size for real money is a separate decision** and
   this is not it.
2. **The direction after it** — asked for more return than the night alone, the owner chose to
   occupy the idle day slot over using leverage. `PR-035` registers that: the same dollar owning
   small caps at night and `SPY` through the session. **If `PR-035` returns `ACCEPT`, this card
   gains a second leg and becomes version 2**; if it does not, the card stays the night alone.

**Ruled 2026-09-20, the same evening, and each one changes what happens next:**

3. **The account is TAXABLE and funded in Canadian dollars.** See §2 — the consequence is a question
   for an accountant at scale, not a blocker at measurement size.
4. **The owner can add about CAD 500 a month.** This is the largest single lever in the whole
   project and it is recorded here because no study can move it: at this rate, five years of
   deposits contribute roughly twice what five years of the measured edge contributes on the
   current balance. A strategy decision that ignores it optimises the smaller term.
5. **The owner will run the first twenty sessions at minimum REAL size** — one or two shares a fund.
   This is the only way the fill number can be obtained: **Alpaca's paper fills are simulated**, so a
   paper trial would confirm this project's own cost model because it IS that model. An auction
   clears at one price for one share and for a thousand, so the minimum size measures it exactly,
   and the capital at risk is a few hundred dollars.

**Still open:** when `CARD-001` stops. The two cannot share the paper account — `CARD-001` holds up
to four positions for twenty sessions and this one wants the account every night. The proposal is
that the day `CARD-002` first submits, `CARD-001` submits no new entries and goes `Retired` once its
open positions have left by their own rules.

**What is NOT a choice, because `A-002` fixes it:** the trial runs on paper, and nothing here
reaches a live venue.
