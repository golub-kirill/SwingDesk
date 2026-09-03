# Decision records

**Status:** drafting · **Tier:** cross-cutting

Four documents already require a "decision record" and none defined it (`contracts/README.md` §7,
`ADR-0003` §3, `EXIT_MODEL_SPEC.md`, `TEST_STRATEGY.md` §3). This is that definition.

---

## 1. What a decision record is for

A **choice that is not a hypothesis.**

Some things this project must fix cannot be tested, because they are conventions rather than claims.
Whether a Sharpe ratio annualises by √252 or √12 is not true or false — it is a convention, and two
studies that pick differently are not comparable. Choosing one is a decision; the record is what
makes it auditable.

The distinction that matters:

| | Instrument | Produces | Provenance it earns |
|---|---|---|---|
| a convention or definition | **decision record** (`DR-NNN`) | a fixed choice, usable immediately | `assumed:DR-NNN` or `assumed:<citation>` |
| a claim that could be false | **pre-registration** (`PR-NNN`, `../prereg/`) | a study | `validated:<evidence-id>` |

Both are written **before** the value is used. That is the whole discipline: a DR is not a
retrospective justification of a number someone already picked.

A choice frequently needs both — a DR to pick a starting value so the system can run, and a PR to
register the study that would confirm or refute it. `screen.trend_definition` is the archetype: you
need *a* definition to have a strategy at all, and whether that definition is any good is a separate,
testable question.

## 2. Format

One file per decision, `DR-NNN-<slug>.md`:

```
# DR-NNN: <the choice, in one line>

date:      YYYY-MM-DD
status:    proposed | accepted | superseded by DR-NNN
parameters: <ids in registry/parameters.yml this sets>
components: <component ids whose version this moves, if any>

## Decision
What was chosen. Precisely enough that two people implement it identically.

## Why this one
The reasoning, and the citation if there is one.

## Alternatives rejected
Each with the reason. An alternatives section with one entry is a decision that was never made.

## What would overturn this
The observation or study that would change it. Names the PR if one is registered.

## Consequences
What now has to be true elsewhere.
```

## 3. Rules

1. **Written before use.** The commit that sets the parameter carries the DR.
2. **Never edited after `accepted`.** Superseded by a new DR that names the old one. Same rule as the
   journal and the pre-registrations, for the same reason.
3. **A DR that sets a parameter must name it**, and the parameter's provenance must point back —
   `assumed:DR-007`. `tools/verify_parameters.py` accepts that form because a decision record is a
   citation.
4. **A DR that changes component behaviour bumps the component version** and regenerates its golden
   vectors in the same commit (`COMPONENT_REGISTRY_SPEC.md` §6, `CI_POLICY.md` §3).
5. **`assumed` is where a DR leaves a parameter — never `validated`.** Only evidence from a
   pre-registered study moves a value to `validated`, and a decision record is not evidence. This is
   the line that keeps a considered guess from acquiring the authority of a measurement.

## 4. Not an ADR

`docs/adr/` holds architecture decisions: storage engine, schema language, calendar source. Those are
structural and rarely revisited. A DR is about a **value or a definition** the domain needs, and it
is expected to be superseded when a study says so. Different lifetimes, different directories.

## 5. Index

| ID | The question it answers | Decision | Sets | Status |
|---|---|---|---|---|
| `DR-001` | **Which Sharpe do we mean?** | Sharpe ratio convention | `stats.sharpe_convention` | proposed |
| `DR-002` | **How is process quality scored?** | Process score scale | `stats.process_score_scale`, `stats.quality_grade_scale` | proposed |
| `DR-003` | **Which instruments may we even look at?** | A-tier liquidity rule | `universe.min_price`, `universe.min_adtv_20d`, `universe.min_bar_history` | proposed |
| `DR-004` | **What does a trade cost?** | Cost model | `costs.commission_model`, `costs.slippage_model` | proposed — slippage superseded by `DR-005` |
| `DR-005` | **How much of that cost is slippage?** | Slippage measured from daily OHLC | `costs.slippage_model` | proposed |
| `DR-006` | **How many positions may be open at once?** | Portfolio risk block | six `risk.*` constraints | **proposed — binds a real account** |
| `DR-007` | **What counts as a study that passed?** | Validation programme thresholds | fourteen of fifteen `validation.*` | **accepted — ratified 2026-08-08** |
| `DR-008` | **Where does the list of tradeable symbols come from?** | Daily US directory collection under local control | operational policy; no trading parameter | **accepted — ratified 2026-08-10** |
| `DR-009` | **Does the broker charge commission?** | The owner's broker charges no commission, and the cost model never knew | account-structure choice only — its parameter moved to `DR-010` (§5, correction 2026-08-13) | proposed |
| `DR-010` | **What does a trade cost at THIS price, in THIS currency?** | Sizing costs are price-aware and currency-aware, not one flat constant | `risk.costs_bp_usd`, `risk.costs_bp_cad`, `risk.costs_floor_usd`, `risk.costs_floor_cad` | **accepted — ratified 2026-08-13** |
| `DR-011` | **How does the owner find out a run finished?** | The run notice is a local desktop notification — not Firebase, not Telegram | none — a surface, not a measured component. Also corrects `PRODUCT_SURFACES` §3.4's self-contradicting example | **accepted — ratified 2026-08-30**; mechanism chosen by the owner 2026-08-16 |
| `DR-012` | **Where is the stop, and how long may a trade live?** | The protective stop is 2.0 × ATR(14) and the maximum holding period is 20 sessions | `exit.atr_stop_multiple`, `exit.max_holding_period` | **accepted — ratified 2026-08-17** |
| `DR-013` | **How long does a proposal stay answerable?** | A non-critical proposal expires after 3 days; a critical one never expires and never proceeds unanswered | `management.proposal_expiry_days` | **accepted — ruled 2026-08-17** |
| `DR-014` | **Is real money involved?** | No owner capital in the observable state of the project — paper only; Canada deferred with a re-entry condition | none directly — changes the STANDING of `DR-006`'s six `risk.*` parameters and withdraws `PR-006`'s precondition | **accepted — ruled 2026-08-17** |
| `DR-015` | **How old may data be before we refuse to decide on it?** | Two sessions is too stale to decide on; a failed fetch retries 3x30s then once more at 19:30 | `data.freshness_window` | **accepted — ruled 2026-08-18** |
| `DR-016` | **When is a changed bar a fault rather than a revision?** | A raw PRICE that changes is a critical fault; a raw VOLUME that changes is Tuesday | `data.revision_epsilon` = 0.001, scoped to CLOSE; volume taken out of the rule and given no parameter | **accepted — ratified 2026-08-30** |
| `DR-017` | **How settled must volume be before it admits an instrument?** | The ADTV window is lagged three sessions, because volume is still being written for two | `universe.adtv_lag_sessions` = 3, provenance `owner` | **accepted — ratified 2026-08-30** |
| `DR-018` | **What is relative strength measured AGAINST — and can that choice matter?** | The course names three indexes and this project has none, so the benchmark is an ETF proxy; but on one cross-section the usual point-to-point form ranks exactly as raw return does, so the benchmark is decorative until the FORM makes it otherwise | `rs.benchmark` = SPY, kept `assumed:DR-018` at the owner's ruling (§8.1); `rs.benchmark_form` deliberately left `unset` for a pre-registration, and that absence is now ratified | **accepted — ratified 2026-08-30** |
| `DR-019` | **Does the second evening pass do anything, and when should it run?** | It has never changed an outcome and the failure it insures against has not occurred here; what DOES occur is a late vendor publication an hour cannot fix. It now runs only when the first pass refused something a retry could repair | none — the condition is read from the journal | **accepted — the CONDITION ratified 2026-08-30 with an amendment (§7); the TIME is still the owner's** |
| `DR-020` | **What are the legal transitions between the nine watchlist states?** | The graph the course never supplied: Trade is reachable only through Ready to Triggered, Skip from every pre-position state, and Late/Invalid/Skip end the CYCLE and not the instrument | `entry.maximum_entry_atr` (new, `unset`) | proposed — owner ratification required |
| `DR-021` | **Can the guard that refuses a fabricated sector look-through tell a bond fund from a real sector ETF?** | Not today: it infers *holds no equity* from the SHAPE of the sector weights, and five of the eleven SPDR Select Sector funds report exactly one sector at exactly 100%, so they are refused with a reason that is false for them. The vendor serves the fact itself in the same response | none - the test stays exact in both halves, so no tolerance and no threshold | **accepted - ratified 2026-08-31** |
| `DR-022` | **What does `code_dirty` have to be dirty ABOUT?** | Only what the run reads - `src/`, `tools/`, `registry/`, `golden/`. It read the whole working tree, so the wrapper's own regenerated `HANDOFF.md` spent `a.reproducible` on six consecutive scheduled passes over a document no run has ever opened | none - a definition, not a threshold | **accepted - ratified 2026-08-30** |
| `DR-023` | **When is the symbol directory pulled, relative to the run that decides on it?** | Before the decision, not after. It ran after the scan, so the 18:30 pass - the one Track A counts and the owner reads - built its universe from the previous evening's directory and decided on 3 to 18 already-delisted instruments a night | none - an ordering, not a threshold | **accepted - ratified 2026-08-30** |
| `DR-024` | **When may a strategy card's measure be called `active`?** | When the run computes it and the report prints it with its validation status - not when the artefacts alone would allow it. `M31-T0464`, `CARD-001`'s relative-strength measure, was implemented and property-tested with no caller outside its own tests; it now runs for every candidate and selects nothing, because all four of the card's selection parameters are unset | none new - reads `rs.benchmark`; activates `M31-T0464-v5.0` | **accepted - ratified 2026-08-30** |
| `DR-025` | **Does a look-through of one sector at 100% mean the fund holds no equity?** | No, and the shape never meant anything: the vendor's weights sum to 1.0000 for EVERY fund regardless of holdings, including funds reporting 0% equity. The guard stops reading the shape and refuses only on a vendor-declared 0% equity | none - no threshold is introduced or needed | **accepted - ratified 2026-08-31** |
| `DR-026` | **Does `D1` - "the system never places orders" - forbid a submission to a PAPER venue?** | No, and `D1`'s own stated reason is why: it exists to remove *"the largest irreversible-risk surface"*, and a paper venue has none. But paper money removes the RISK argument and leaves the GOVERNANCE argument standing - `CHARTER.md` §3's automated-trading non-goal and A-001 §1-§2 say the human decides, for a reason that never mentioned capital. So an owner-approved paper order is permitted and an unapproved one is a separate ruling | none - an interpretation, not a threshold | **accepted - the `D1` reading ruled by the owner 2026-08-31; §5 is open and is the owner's** |
| `DR-027` | **What may the machine actually SEND to the paper venue, and what stops it?** | One shape only: an entry for a candidate this run decided `Trade` and `sizing` sized - a LIMIT at the sizing price (which is the `CHASE`/`LATE` control by construction and therefore needs no threshold), a bracket carrying the stop, `day`, whole shares, and a `client_order_id` derived from the SESSION DATE so a retried pass cannot submit twice. Four independent guards: the host allowlist, a kill switch that defaults to STOPPED, `write_enabled`, and one code chokepoint gate 39 reads | none - definitions and guards, no threshold | **accepted - authorised by `CHARTER` A-002, ruled by the owner 2026-09-01** |
| `DR-028` | **The order-size cap was ratified at 1.0% of ADTV and read by no code. What does 1.0% of WHAT mean, and what happens when it binds?** | It TRIMS the share count and refuses only at zero, with the course's `LIQ` - `M49-T0760` names a liquidity *adjustment*, its sibling is the correlation adjustment, and the position-value cap in the same function already trims. It measures against the universe rule's OWN ADTV window and `DR-017` lag, so an instrument has one liquidity opinion rather than two; an ADTV that cannot be measured refuses. Binds on nothing until roughly a $2.2M account, which is why it was wired now | none new - gives `risk.liquidity_cap_order_to_adtv_pct` a `read_by` for the first time | **accepted - the VALUE was already the owner's; this supplies the DEFINITION it never had** |
| `DR-029` | **The venue needs a take-profit leg and the course names three - 1R, 2R, 3R - and picks none. Which?** | **1R**, and the data excludes the alternatives rather than taste doing it: over 91,572 windows, 3R never resolves in 46% of them and 2R is already negative. The reachable range is structurally ~1.5R, because R is two ATR and these names travel about three ATR in twenty sessions. So a wider target is bought by moving the STOP or the HOLD, never the target - and every number is on UNSELECTED entries, which is why the research it defers is about those three levers | `exit.target_r_multiple` = 1.0, provenance `owner` | **accepted - ruled by the owner 2026-09-01** |
| `DR-030` | **`CARD-001` selects nothing because four inputs are `unset`, and `ALLOCATION_SPEC` §3 says only a study may set them. Both studies are spent. Now what?** | The route is CLOSED, not blocked: `PR-012` refused on a structural sample ceiling and `PR-013` - the per-date design an LLM council independently reached for - already ran and returned six intervals all including zero, gross. And `b.min_sample` is journal-measured, so **no backtest could ever mark the card `Validated` anyway.** So the four values are the owner's preference with structural grounds, provenance `owner`, never `validated:` - the mechanism `screen.trend_definition`'s own note prescribes for a closed family. The card ships `Untested`, paper only, and starts the 100-journalled-trade clock, with its expected FAILURE registered in advance | `rs.benchmark_form` = path, `rs.lookback` = 126, `rs.ranking_method` = descending, `screen.relative_strength_rule` = top_decile - all four `owner` | **accepted - ruled by the owner 2026-09-01** |
| `DR-031` | **`DR-027` §11 pauses new entries whenever the venue holds something the book does not carry, and `positions.duckdb` is written only by a person. So the machine ran once. May a fill record itself?** | Yes, and `DR-026`'s refusal is answered rather than stepped around: it refused because *the venue does not know the stop*, which is true of a book somebody else opened and false of an entry THIS system placed - `DR-027` §3.2 submits the stop as a bracket leg and §8 journals it before the order goes. So the entry price and share count are the venue's, the stop and the cost model are **ours, from our own record**, and a holding tracing to no `sent` submission of ours is reported and NEVER adopted | none - every value is an observation or a number already decided; the one computed field calls `DR-010`'s existing model | **accepted - owner instruction 2026-09-02** |
| `DR-032` | **The 18:30 pass submits; the 19:30 retry then finds its OWN resting orders at the venue, calls them a mismatch and stops. `DR-015`'s retry is dead and `DR-027` §5's duplicate rejection is unreachable. Whose orders are those?** | Ours, and the journal is what says so - `DR-027` §8 records every submission BEFORE the wire, which is a stronger record than the venue's echo. So a live order whose id is in our own `sent` set no longer halts the run - and, because exempting it from the halt without counting it would let the retry add four more on top of four resting, **it is offered to `allocate` ahead of every candidate** and consumes its slot and its R, priced from our own submission | none - the two caps are `DR-006` §8.3's and the R calls `DR-010`'s existing cost model | **accepted - owner instruction 2026-09-02** |
| `DR-033` | **The first four real orders this system ever sent were ALL rejected: `invalid limit_price 66.949997. sub-penny increment does not fulfill minimum pricing criteria`. The caps, the guards and the allocation were right and the wire format was wrong.** | Snap every leg to the venue's increment — SEC Rule 612, so it is the VENUE's rule and lives in the committed policy beside the host, never in `parameters.yml`. The DIRECTION is ours and `DR-027` §3.1 already ruled it: entry rounds **down** so it can only fill at or below the decision price, the stop rounds **up** so realised R can never exceed the frozen one, the target rounds **down**. Legs that collapse once rounded are refused before the wire | none — the increment is the venue's and the direction is derived from `DR-027` §3.1 | **accepted — forced by the venue 2026-09-02** |
| `DR-034` | **`k.drawdown_pause` is ratified, scope `live`, threshold owner-set at 20% — and NOTHING in `src/` ever called the measurement. `TODO.md` §1 said it was harmless "today and only today"; on 2026-09-02 four orders were accepted at a venue.** | Evaluate it on every armed submission. A breach **pauses new entries** — the only outward action this system has, and the mapping `TECH` already uses. A drawdown that cannot be MEASURED also stops, because a kill switch that admits when it cannot read the book is `DR-006` §3's inversion on the highest-consequence surface — the first implementation had exactly that bug and its own test caught it. **`risk.risk_off_ladder` stays `unset`**: measurable is not automatic | none set. `validation.max_allowable_drawdown` and `account.equity` gain a consumer | **accepted 2026-09-03** |

**The middle column is the one to read first.** A record's own title states its *conclusion*, which
is the least useful thing about it to someone who has not read it - `DR-006` is "the portfolio risk
block", which says nothing to anybody arriving cold. The question is what a reader is actually
holding when they come looking, and sorting the shelf by conclusions is how a decision store becomes
unbrowsable. Added 2026-08-22 at the owner's request, after "I can't tell anything if I don't even
have a normal name".


`DR-007` is the largest of these by a distance: fifteen parameters at once, four of them ratifying
what a reported study already used and eight genuinely authored. It exists because a ratified kill
criterion referenced a parameter nobody had set, which made it a gate that could not fail.

**One of its fifteen did not survive the 2026-08-09 reconciliation.** `DR-007` §3.7 authored
`validation.max_allowable_drawdown` as −15R and called it the weakest of the set; the owner had
already set the same parameter directly to 20% of equity on 2026-08-05, on a branch `DR-007` could
not see. An `owner` value outranks an `assumed:DR-007` one on this registry's own provenance ladder,
so the owner's stands and §3.7 is superseded. Nothing else in the record changes.


Measurements backing a decision live in `measurements/`, committed alongside the record. A threshold
whose evidence cannot be re-read is a threshold that will be re-argued from memory.
