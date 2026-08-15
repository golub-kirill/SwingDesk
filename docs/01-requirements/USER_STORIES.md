# USER STORIES

**Status:** drafting · **Tier:** 1 (requirements) · **Content:** authored, structured by the course's own playbooks

Stories are grouped by the four playbooks the course actually prescribes. Each has an ID that a test
should cite. The check that would enforce it is `CI_POLICY.md` gate 10 (traceability), which is
honestly marked **to build** — it is not wired yet, so citing an ID today is a convention, not a
gate. See the open items below for how few IDs are cited today and the command that measures it.

`Given/When/Then` here is not decoration — a story is not done until its scenarios exist as
executable tests.

---

## A. Daily operating loop (M80–M83, 8 steps)

### US-001 · The daily run produces a dated, traceable report
> As the owner, I want one command to produce the day's report, so that preparation is a single
> reproducible act rather than a sequence I might vary.

```gherkin
Given a defined universe and a data snapshot for date D
When I run the daily scan for D
Then a dated report is produced
And every displayed number resolves to a registered component id with a version
And every parameter that affected a number is shown with its provenance
And a run manifest records the code hash, config hash, snapshot id and spec versions
```

### US-002 · Open positions are evaluated before new candidates
> So that risk on capital already at work is never queued behind opportunity.

```gherkin
Given at least one open position and at least one candidate
When the daily run executes
Then exit evaluation for open positions completes before candidate screening begins
And the run manifest records the two phases in that order
```
*Course rule: `Открытые позиции и gaps проверены первыми` (Appendix T).*

### US-003 · Stale or conflicting data blocks new decisions
> So that the system never trades on data it cannot vouch for.

```gherkin
Given the freshness check fails for an instrument
When the daily run evaluates that instrument
Then no Trade decision is produced for it
And a Skip is recorded with code DATA
And the report shows the failing check and its as-of time

Given two configured sources disagree beyond tolerance for the same bar
When the daily run evaluates that instrument
Then the conflict is surfaced rather than reconciled
And the instrument is Skipped with code DATA
```
*The second scenario is why Questrade exists in this system — `ADR-0001` adopts it as the second
source precisely so this check can run.*

### US-004 · Market regime is classified per country
```gherkin
Given daily bars for the US and Canadian benchmarks
When the daily run computes regime
Then a regime label is recorded separately for USA and for Canada
And each records the inputs that produced it and the classifier version
And neither is derived from the other
```

### US-005 · The universe is rebuilt daily from a liquidity rule
```gherkin
Given the universe parameters are set
When the daily run rebuilds the universe for date D
Then membership is computed from bars available as of D
And membership for D is stored as a point-in-time fact
And instruments failing the rule are excluded with a recorded reason

Given any universe parameter is unset
When the daily run rebuilds the universe
Then the run refuses with a coded error rather than applying a default
```

### US-006 · Screening produces ranked candidates with reasons
```gherkin
Given a universe and an enabled strategy card
When screening runs
Then each instrument receives either a candidate record or a Skip with one of the 12 codes
And no instrument ends the run without one of the two
```

### US-007 · Every candidate carries a decision and a reason
```gherkin
Given a candidate has passed screening
When the decision stage runs
Then it receives exactly one of Trade, Watch, Skip or Pause
And Watch creates an alert and does not create an order-equivalent action
And Skip records a reason code
And Pause suppresses the whole run rather than one candidate
```

### US-008 · Risk is computed in the mandated order
```gherkin
Given a candidate with an invalidation level
When risk is computed
Then the stop is derived from invalidation before size is computed
And risk per share includes the costs allowance
And shares are rounded down
And position value and liquidity caps are applied after the raw share count

Given a proposed stop at or beyond the entry for the direction
When risk is computed
Then the candidate is Skipped with code STOP
And no share count is produced
```

### US-009 · The pre-trade checklist is generated, not asked
```gherkin
Given a candidate with a Trade decision
When the pre-trade checklist is generated
Then items the system can verify are pre-filled with the evidence that satisfied them
And items requiring judgment are presented as bounded choices
And the checklist cannot reach Complete while a required item is unanswered
```

### US-022 · The run says why nothing matched
> As the owner, I want the run to report its funnel and what moved since the last run, so that I can
> tell a quiet day from a broken one without reading every candidate block.

```gherkin
Given a completed run with a universe attached
When the funnel is computed
Then eligible, measured, admitted and evaluated counts are shown in that order
And Trade, Watch, Skip and Pause counts sum to the evaluated count together with any unaccounted
    candidate

Given at least one Skip decision
When the funnel is rendered
Then each skip code is broken out with its count
And a Skip that names a parameter (an unset required value) is shown separately from a Skip with
    the same code that does not (a fact about the account or the market, not the system)

Given a candidate whose decision differs from its previous_decision
When the funnel is computed
Then it is counted as changed
And a candidate with no previous_decision is counted as a first sighting, never as changed

Given a run with no candidates at all
When the funnel is rendered
Then it still prints a funnel block stating zero, not silence
```
*Nothing here is a new measurement — every count is read from `RunResult` /
`UniverseSelection`, the same objects the per-instrument blocks already print
(`swingdesk.presentation.funnel`).*

## B. Position management (M59–M62, Appendix T)

### US-010 · Open-position actions are approved by the human
```gherkin
Given an exit policy proposes a stop move or a partial exit
When the proposal is sent for approval
Then it states the observation, the bounded set of choices and the rule that produced it
And the response records the choice, a reason and a timestamp
And no action is applied without a recorded response

Given a proposed stop change would increase risk
When the proposal is constructed
Then it is rejected before being sent
And error code WIDE_STOP is recorded
```
*Owner decision D6. The three recorded fields are the course's human-judgment requirement (§3.8).*

### US-011 · Fills are recorded and actual risk recomputed
```gherkin
Given a trade was executed manually at the broker
When the fill is reported
Then the fill price, shares, commission and slippage are recorded
And open risk is recomputed across the whole book rather than decremented
And slippage in R is computed against the originally planned risk
```

### US-012 · Exits follow the four-slot model
```gherkin
Given an open position and a strategy card
When exits are evaluated
Then each of protective, profit, contextual and time slots is evaluated
And each firing exit states its quantity and its execution order
And where two exits fire on the same bar, the card's resolution order decides
And R is computed against the initial planned risk regardless of stop moves or partials
```

## C. Journal and review (M67–M69, Appendix H)

### US-013 · The journal is immutable and versioned
```gherkin
Given a trade plan has been recorded
When any field of it is changed
Then the original is preserved and a new version is created
And the audit trail links the versions
And no update-in-place occurs

Given a required field is empty or two sources conflict
When the record is submitted
Then it cannot be saved as complete
And it takes Pause, Research or Skip
```

### US-014 · Statistics are net of costs and broken down
```gherkin
Given a set of closed trades
When statistics are computed
Then every metric is net of commission, spread, slippage, borrow and FX
And results are grouped by strategy, version, regime, country, sector, setup, weekday, entry type and exit type
And win rate is never displayed without average win and average loss
And max drawdown is reported in dollars, percent and R
And every figure carries its sample size

Given the sample is below the minimum for a verdict
When statistics are reported
Then the count is shown and no verdict is stated
```

### US-015 · The weekly review is generated
```gherkin
Given a completed week
When the weekly review is generated
Then all 13 Appendix H items are present
And outcome and decision quality are reported separately
And the watchlist funnel and skip quality are included
And one measurable improvement task is recorded
```

## D. Validation (M71–M76)

### US-016 · Backtests are point-in-time and bar-by-bar
```gherkin
Given a strategy card and a historical window
When a backtest runs
Then only data whose knowledge time precedes each decision bar is visible
And universe membership is the membership as of that bar
And costs are applied
And the result carries a survivorship-bias marker
And future bars are never readable from a decision function
```

### US-017 · Walk-forward records its windows
```gherkin
Given a strategy card with parameters
When walk-forward runs
Then each window records train, validation and test dates, the universe snapshot, the parameters selected and the selection rule
And out-of-sample trades are reported separately from in-sample
And the window ends with keep, revise or retire
```

## E. Cross-cutting

### US-018 · Every number traces to its source
```gherkin
Given any figure displayed on any surface
When I ask where it came from
Then it resolves to a component id and version, its parameters with their provenance, and the trace step that produced it
```

### US-019 · A run is reproducible from its manifest
```gherkin
Given a stored run manifest
When the run is replayed from it
Then the output is byte-identical to the original
```

### US-020 · An unset parameter refuses rather than defaults
```gherkin
Given a component whose parameter has no value
When that component is evaluated
Then it returns a coded refusal
And it does not substitute a default
And the refusal names the parameter
```

### US-021 · Validation status is always visible
```gherkin
Given a component with validation status Untested
When its output appears on any surface
Then the status appears with it
And a parameter with provenance assumed is marked as assumed adjacent to the number it produced
```

---

## Coverage note

These stories cover Track A of `criteria.yml` completely. Track B needs no stories — it is
evidence about a strategy, not behaviour of the system.

Deliberately absent: any story about placing orders, and any story about a strategy being
profitable. Both are non-goals (`CHARTER.md` §3).

## Open items

- [ ] **Gate 10 (traceability) is unbuilt**, so story-id citation is a convention today, not an
      enforced link. Very few ids are cited anywhere in the tree yet:
      `grep -rn "US-0[0-9][0-9]" --include="*.py" src/` — measure it fresh rather than trusting a
      number written here, since this document is not where a measured count is allowed to live
      (`AGENTS.md` §10.5).
- [ ] Stories for the web admin surface and push notifications, once `PRODUCT_SURFACES.md` fixes
      what each owns. The CLI stories above are surface-agnostic on purpose.
- [ ] US-004's regime classifier has no rule yet (`regime.classifier_rule`, unset). The story is
      written; it cannot be satisfied until the rule is authored and pre-registered.
