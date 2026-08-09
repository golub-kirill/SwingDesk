# TRANSITION SPEC — the discrete-change object

**Status:** drafting · **Tier:** 2 (domain) · **Content:** authored, audited against the tree

Master ТЗ v1.0 §16, and after `RULE_SPEC.md` it is top of the remaining six in
`SPEC_GAP_ANALYSIS.md` §4. A Rule produces a verdict; a **Transition** is what gets recorded when
that verdict, or anything else, changes the state of something the next run has to know about.

---

## 1. The name, and why it is not "Event"

`EVENT_SPEC.md` in this tree is the **market-event catalogue** — Module 34's twenty catalyst types
and Module 40's eighteen event-driven patterns. That name came from the course and it keeps it.

The ТЗ's §16 Event is a different object entirely: the formal discrete-transition record. Two things
would share one name, which is the §11 terminology failure the specification itself warns about, so
**the ТЗ's object is renamed here rather than the course's.**

The rule that follows, and it is worth freezing:

> In this system, **event** always means something that happened in the market. Something that
> happened in the *system* is a **transition**.

`GLOSSARY.md` has no `ambiguous_terms` section — `SPEC_GAP_ANALYSIS.md` row 11 records that as a
shortfall. This is the first entry it would need, and the reason that section is not decoration.

## 2. What a Transition is

A discrete, dated, recorded change of state that something downstream may depend on.

**The three-part test.** All three must hold, and each excludes something real:

| | Test | Excludes |
|---|---|---|
| 1 | It is **discrete** — it happened at an instant, not over a window | ATR, breadth, any observation: recomputable from bars, so it needs no record of its own |
| 2 | It **changes what a later run may assume** | a re-derived value that was already implied by stored inputs |
| 3 | Losing it makes a record **unreproducible or unexplainable** | logging, progress output, anything whose absence costs nothing |

Test 3 is the operative one. `LIFECYCLE_AND_LAYERS.md` §3 states the standard it enforces: *a
conclusion that cannot be reproduced from its recorded inputs and versions is a production defect*.
A transition is what has to exist for that reproduction to be possible when the cause was an event in
time rather than a number in a table.

**What a Transition is not.** Not an observation (continuous, recomputable). Not a rule (a function).
Not an action by the system — under D1 there are none.

## 3. The envelope

Every transition carries the same fields regardless of type. The point of one envelope is that the
audit query is one query.

```yaml
- transition_id: t-20260808T210000Z-0007   # stable, sortable, unique
  type: DECISION_RECORDED                  # from the closed set, §4
  subject: { kind: instrument, id: AAPL }  # what changed
  occurred_at: 2026-08-07T20:00:00Z        # when it happened (event time)
  recorded_at: 2026-08-08T21:00:00Z        # when we knew (knowledge time)

  producer:                                # who emitted it, at which version
    rule: M33-T0485-v5.0
    component_version: 1
    run_id: run-20260808T210000Z-3f2a1b0c

  from_state: Watch                        # null when the subject had no prior state
  to_state: Skip
  reason_code: DATA                        # from CODES.md where one applies
  reason: 2 incomplete session(s); first: 2026-08-05

  supersedes: null                         # the transition this corrects, never an edit
  actor: system                            # system | owner - a human decision names the human
  basis: OBSERVED                           # OBSERVED | INFERRED, see §7
```

Ten of these already exist somewhere in the tree; three do not exist anywhere. §4 says which.

## 4. What the tree emits today

Four shapes, no common envelope. Measured.

| Shape | Where | Stored in | Carries | Missing |
|---|---|---|---|---|
| `DecisionRecord` | `journal_evidence/journal.py` | `decisions` table | subject, to_state, **`from_state`**, reason_code, reason, run_id, version | `occurred_at` separate from `recorded_at`, producer, `basis` |
| `ManagementAction` | `contracts/position.py` | `management` table | subject, kind, status, reason_code, reason, old/new stop, `proposed_at`, run_id, sequence | `from_state`/`to_state` as such, producer, `supersedes` |
| Position version | `contracts/position.py` | `positions` table | subject, version, `knowledge_time`, the full new state | the *reason* the version exists — the change is visible, its cause is not |
| Run start / complete | `contracts/run.py` | `runs` table | run identity, **`mode`**, pinned inputs, `output_hash`, `started_at`, `completed_at` | — |

**The gaps this table exposed, and where they stand:**

1. ~~**`from_state` is nowhere.**~~ **Closed for decisions, 2026-08-08.** `DecisionRecord` carries
   `previous_decision`, read from the journal **as of the run's start** so it reports what was known
   when the run began rather than what it just wrote. `None` means no prior decision — a first
   sighting — and is explicitly not "unchanged".
   Still open for the other two shapes, and cheaply: a position's previous version and a management
   action's previous stop are both already in their stores, so the `from_state` is derivable rather
   than lost. Only the decision's was unrecoverable.
   **It is not part of `output_hash`**, deliberately: it describes what the run *knew*, not what it
   *decided*. A replay against an empty journal correctly finds nothing, and the replayed
   `output_hash` is unchanged — which is what let this land without re-opening a determinism
   question.
2. **`occurred_at` and `recorded_at` are one field in three of the four.** `DecisionRecord` has
   `recorded_at` only. This is the same collapse `POINT_IN_TIME_SPEC.md` refuses for market data,
   allowed for decisions because so far they coincide — a decision made in a run is recorded in that
   run. It stops being safe the moment a decision is entered after the fact, which is exactly what
   the owner's Telegram approval flow (D6) will produce.

## 5. What transitions and is not recorded at all

Ranked by what losing it costs. This is the actual §16 gap; the envelope above is the cheap part.

| # | Transition | Recorded? | Cost of losing it |
|---|---|---|---|
| 1 | **A symbol leaves the directory** | **inferred, not recorded** — `departures()` diffs two pulls | **Irreversible.** The only free survivorship evidence this project can ever hold (`DATA_QUALITY_SPEC.md`). Every unpulled day is permanently gone |
| 2 | **A watchlist status changes** | **no** — there is no watchlist store at all | Appendix G requires `Candidate.status history`, *a history and not a current value* (`JOURNAL_SCHEMA.md` §2). The nine states exist as an enum with no transition graph (`DECISION_STATE_MACHINE.md` §6) and nowhere to write one |
| 3 | **A parameter is ratified or changed** | partially — `config_hash` moves | The run's inputs changed and nothing says which, why, or on whose authority. Gate 9 catches the *effect* and names the field; the decision behind it lives only in a commit message |
| 4 | **A component version bumps** | partially — `component_versions` in the manifest | Evidence records pin versions, so the link survives; the moment of change does not |
| 5 | **A rule refuses inside a run** | only if it becomes a decision | A refusal that does not reach a candidate's record is invisible. `RULE_SPEC.md` §7 and `EXECUTION_MODEL.md` §5 each found one |
| 6 | **The owner approves or rejects a proposal** | **no** — `ActionStatus` has the states, nothing writes them | D6's whole flow. `PROPOSED → APPROVED` is the transition that makes a human decision auditable, and it is the one with a human actor |

Rows 1 and 6 are the two that cannot be reconstructed later by any amount of work. Row 1 because the
vendor publishes a current file and no archive; row 6 because a person's decision leaves no other
trace.

**Row 1 already has a ranked action** — `HANDOFF.md` §5 item 4, schedule `tools/fetch_directory.py`,
about five seconds a day. This document is the second independent argument for it: the departure is a
transition whose only witness is a pair of snapshots that must both exist.

## 6. Two times, and the third one that decides

`occurred_at` and `recorded_at` are the same `event_time` / `knowledge_time` pair
`POINT_IN_TIME_SPEC.md` uses for bars, applied to decisions. The rule is the same and the reason is
the same: a transition is usable by a decision at `T` only if `recorded_at ≤ T`, **never** because
`occurred_at ≤ T`.

The ТЗ's `available_time` — the third time type, and the one `SPEC_GAP_ANALYSIS.md` §5 names as the
admissibility clock — matters here more than it does for bars. A daily bar is available at session
close, so the two collapse safely. A transition does not have that property: an owner's approval
occurs when they tap the button and becomes available to the system when the message is processed,
and those genuinely differ. **Transitions are where the two-of-eight time-type shortfall stops being
theoretical.**

## 7. Observed and inferred

A transition is either **witnessed** or **derived by comparing two states**, and the record says
which. `basis: OBSERVED | INFERRED`.

`departures()` is the worked example and its own docstring states the limit plainly: a symbol that
stops appearing has almost certainly been delisted or renamed — ticker changes, venue moves and
symbol reuse all look identical from there. So the record says *what was observed, not what
happened*.

**An inferred transition names its witnesses.** For a departure that is the two pull timestamps it
was derived from. Without them the inference cannot be re-checked when a better source arrives, and
an unre-checkable inference stored as a fact is how a data limitation becomes a data claim.

## 8. Who may emit

The layer law decides this and there is no discretion in it.

1. **A pure component never emits.** `derived_observations`, `decision_logic` and `trade_management`
   may not write the journal (`DEPENDENCY_LAW.md`) and may not read a clock (gate 7). A rule
   *returns* a verdict; the caller records it. That is why `is_uptrend` returns `bool | None` and
   why `size_long` returns a `Refusal` object rather than logging one.
2. **The application layer emits**, because it is the layer that has both the clock and the store.
3. **Emission is idempotent.** The key is `producer + subject + occurred_at`. A replay re-emits the
   same transitions with the same keys — which is what makes a replay comparable at all — and
   emitting twice for one cause is a defect, not a duplicate to be de-duplicated downstream.

   **With one honest qualification.** A field derived from stored history — `from_state` is the first
   — is reproducible only against the same store. A replay runs against a fresh journal and correctly
   records `None` where the original recorded a prior decision. That is not a determinism defect: the
   two runs knew different things, and the field says what the run knew. It is why such fields stay
   out of `output_hash`, and why a store is an input to be pinned rather than context to be assumed.
4. **Order is `(occurred_at, recorded_at, transition_id)`**, total and stable. A transition log whose
   order depends on insertion is not reproducible, and `a.reproducible` is a ratified criterion.

## 9. A proposal is not an action

Under D1 the system proposes and the owner acts, so the transition set has a shape most trading
systems do not have:

| Transition | Actor | Exists |
|---|---|---|
| `ACTION_PROPOSED` | system | **yes** — `ManagementAction`, status `PROPOSED` |
| `ACTION_APPROVED` / `ACTION_REJECTED` | **owner** | no |
| `ACTION_EXPIRED` | system (a clock) | no |
| `ORDER_PLACED`, `FILLED` | **broker, reported back** | out of scope for emission — recorded if the owner supplies it (`JOURNAL_SCHEMA.md` §2) |

`ActionStatus` already declares all four proposal states. Only the first is ever written. That is not
a defect today — nothing approves anything yet — but it is the exact place where a human decision
enters the record, and `LIFECYCLE_AND_LAYERS.md` §6 sets the bar for it: the record must identify the
observation shown, the bounded choice offered, the decision made, and the reason. An approval
transition that records only "approved" fails that test.

## 10. Invariants that can be checked

| Check | Extends | Cost |
|---|---|---|
| every transition has a producer that resolves to a component or a named human actor | gate 11 | hours |
| `recorded_at ≥ occurred_at`, always | schema constraint | minutes |
| no transition is emitted twice for one idempotence key | schema constraint (unique index) | minutes |
| a replay emits the same transition set as the run it replays | gate 9, once transitions exist | days |
| every `INFERRED` transition names its witnesses | schema constraint | minutes |
| a `Skip` transition carries a code from `CODES.md` | already true for `DecisionRecord` | done |

Four of the six are database constraints rather than scripts, which is the cheapest kind of gate
there is: a violation cannot be committed rather than being caught after it is.

## 11. Open items

- [ ] **Whether to build a `transitions` table or add the envelope to the four existing shapes.**
      One table makes the audit query one query and risks becoming a dumping ground; four shapes keep
      the types honest and make "what happened to this instrument" a union of four selects. Leaning
      to one table with a typed `subject`, because the query the owner will actually ask is
      chronological and cross-type.
- [x] ~~**`from_state` on every shape**~~ — **done for `DecisionRecord`, 2026-08-08**, which was the
      only one where the prior state was genuinely unrecoverable. A position's previous version and a
      management action's previous stop are already in their own stores; those two are a projection,
      not a lost record, and can follow whenever the envelope in §3 is built.
- [ ] **A watchlist store** — blocked on the transition graph for the nine states, which
      `DECISION_STATE_MACHINE.md` §6 has had open since 2026-08-01. The states are the course's; the
      graph is authored, and it cannot be enforced until it is written down.
- [ ] **The approval transition** (§9), and with it the D6 record fields
      `LIFECYCLE_AND_LAYERS.md` §6 requires. Blocked on a Telegram surface, so G7.
- [ ] The closed set of `type` values. Six are named in §5 and four in §9; the enum should be frozen
      the same way the course's enums are — adding one is an amendment, not an edit.
