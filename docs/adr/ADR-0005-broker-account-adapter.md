# ADR-0005 — The broker-account adapter: where it lives, and which venue answers

- **Status:** Proposed
- **Date:** 2026-08-31

## Context

Until now the only way a fill entered this system was the owner typing `swingdesk record-fill`, and
the only way a position entered it was `swingdesk open-position`. Both are transcription, and the
project's own trap list already names what transcription does: a number a person types is a number
that drifts, and here it drifts against a broker statement nobody re-reads.

The owner instructed on 2026-08-31 that paper trading be wired so strategies and guesses can be
tested against a real venue, naming Alpaca. Two questions had to be answered before any code:
**which venue**, and **where in the package tree an account adapter belongs.**

Constraints already binding: `DR-014` (no owner capital in the observable state of the project),
`D1`/`BR-1` (the system prepares and records, it never acts), `SECURITY.md` §2.1 (secrets in the
environment, never in this public repository), `CI_POLICY.md` §4 (CI never touches the network).

## Decision

**Two decisions, and they are separable.**

### 1. The venue is Alpaca's paper endpoint

Researched 2026-08-31 against Alpaca's own documentation: accounts are free and open globally,
paper keys are **distinct** from live keys, the default balance is $100k, IEX market data is
included at no cost, and the API specification is identical to live — so nothing built against it
is throwaway. It fits `DR-014` exactly: a real venue's fills, partial fills, rejects and halts,
with no owner capital.

**One measured fact shaped everything downstream.** The account object carries **no field saying
whether an account is paper or live** — `id`, `account_number`, `status`, `currency`, `equity`,
`buying_power` and `trading_blocked` are the same in both. **Which host was called is the only
difference there is.** So the host is not configuration; it is the entire boundary `DR-014` rests
on, and it lives in `registry/broker_policy.yml` with gate 39 reading it.

### 2. `swingdesk.broker` is a **Source Facts** package, inside the layer chain

It sits above `reference_data` (whose calendar it reads to tell a US instrument from a Canadian
one) and below `derived_observations`, which is forbidden from importing it by the same contract
that forbids importing `market_data`.

```
... → derived_observations → market_data → broker → reference_data → platform
```

**Why a layer and not a service outside the chain.** A brokerage account's answer *is* a source
fact in the course's own taxonomy: it says what happened at a venue, in the past tense, and it
originates no observation and reaches no decision. `market_data` and `reference_data` are both
Source Facts packages already, so this is a third of a kind that exists rather than a new shape.
`journal_evidence` sits outside the chain because it is written to from four different heights;
nothing writes to a broker, and nothing may.

**And the forbidden contract is the point of placing it here at all.** The course rule *"strategies
do not fetch or normalize their own private version of shared facts"* is already executed against
`market_data`; adding `swingdesk.broker` to the same contract means a strategy that could ask the
venue what it holds fails the build. The book is the most consequential shared fact this system
has, and it is exactly the one a strategy would be tempted to look up directly.

## Alternatives considered

- **A service outside the chain, like `journal_evidence`.** Rejected: that shape exists because
  four layers write to the journal and two must not. A broker adapter has one caller height
  (`presentation`, and later `application`) and one direction of travel, so `layers` expresses it
  and two `forbidden` contracts would be a weaker statement of the same thing.
- **Inside `market_data`.** Rejected on the package's own charter — vendor adapters, bar storage,
  freshness. A position is not a bar, and folding them together would put `BrokerPosition` in the
  package whose forbidden contract exists to keep *bars* away from strategies.
- **Inside `trade_management`.** Rejected: that package owns sizing, stops, targets and portfolio
  constraints — decisions about a position. Reading what a venue holds is not one.
- **The official `alpaca-py` SDK instead of `urllib`.** Genuinely considered under `AGENTS.md`
  §10.3, which says to prefer a tested implementation over a re-derived one. Rejected because the
  rule is about *method* — an estimator, a statistic, a correction — and three authenticated `GET`
  requests are not a method. The SDK brings websockets, msgpack and an SSE client for a read path
  that needs none of them, and it would make the offline-transport injection that keeps the suite
  inside `CI_POLICY.md` §4 harder rather than easier. **This is reversible**: the adapter is one
  module behind one `Transport` protocol, so swapping the transport is local. Revisit it if the
  write path arrives, where order-state machines and retry semantics *are* method.
- **Reading `APCA_API_BASE_URL`, Alpaca's own environment override.** Rejected, and this is the
  one rejection that would have been easy to accept by default: it is a boundary one shell export
  wide, and the boundary in question is the owner's money.

## Consequences

- **Positive.** Fills and positions arrive from the venue's own record rather than a retyped one.
  The reconciliation reports in the course's existing vocabulary — Appendix N's `TECH`,
  *"Broker/platform/journal mismatch"*, whose prescribed action is *"pause new entries"* — so no
  parallel code set was invented. The suite is offline through an injected transport, and no new
  third-party dependency was declared.
- **Positive.** `D1`/`BR-1` became structural: the committed policy permits `GET` only, and gate 39
  reads the package's syntax tree for any URL or write verb. It was measured by planting a `POST`
  literal and watching the gate go red (`AGENTS.md` §10.8).
- **Negative, and named rather than discovered later.** A broker's answer cannot construct a
  `Position`: the venue knows the symbol, the quantity and the average entry, and it does **not**
  know the stop — which is what `RISK_SPEC.md` §2 denominates every `R` in. So ingestion reconciles
  and reports; it does not create positions, and it never guesses which approved action a fill
  settles. `TODO.md` §6b carries what would close that: a `client_order_id` this system sets, which
  only exists once it places the order.
- **Negative.** The adapter is dormant until the owner sets `APCA_API_KEY_ID` and
  `APCA_API_SECRET_KEY` in the environment. **It has never been run against the live endpoint** —
  every test here is a recorded fixture, and the field names come from Alpaca's published reference
  rather than from an observed response.
- **Open.** Wiring `TECH` into the daily run, so a divergence pauses new entries the way Appendix N
  says it should, would put the network inside the scheduled pass. That is a separate decision and
  `TODO.md` carries it.
