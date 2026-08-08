# AI AUTHORITY MODEL

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored, bounded by `CHARTER.md` A-001

Required by charter amendment **A-001** (2026-08-08), which put an AI agent in scope in exactly one
role — *subsume context and present a global picture* — and made writing this a **precondition of
implementing anything**. `COVERAGE_AUDIT.md` §5 licenses this document and only this one; model
governance follows it and does not precede it.

Sourced from master ТЗ §37, §38 and §39, with §3.8, §35.2 and §41.3. Where the ТЗ presumes a
deciding agent, this document does not adopt it, and each such departure is named.

**On the name.** The ТЗ calls this object an *AI Decision Agent*. That name is not used here, because
under A-001 the agent does not decide anything. A name that presumes the authority the charter denies
is the §11 terminology failure the same specification warns about — and naming is where an authority
boundary erodes first.

---

## 1. The authority chain, and how it differs from the ТЗ's

Master ТЗ §37.1 states the chain as:

> AI selects the preferred permitted action → Risk Engine decides whether the action is allowed →
> Execution Gate decides whether an order may be sent → Order Management executes an approved
> instruction.

**Three of those four stages do not exist here and two of them never will.** D1 and `CHARTER.md` §3
make order placement a ratified non-goal, so there is no execution gate and no order management. And
A-001 removes the first stage: the agent does not select an action.

What remains:

```
deterministic components  →  context assembly  →  AI synthesis  →  HUMAN DECISION  →  journal
     (registered,              (versioned,          (bounded,        (the only          (immutable)
      provenanced)              point-in-time)       attributable)    authority)
```

**The human is not the last approver in a chain of approvers. They are the only decider in it.** That
is stronger than the ТЗ's model and it is deliberate: an approval step can be automated later by
someone who thinks it is a formality, and A-001 admits no configuration that would allow it.

## 2. What the agent may never do

Adopted from ТЗ §37.5 and §35.2, and binding under A-001:

| | |
|---|---|
| decide | emit or imply a `Trade` / `Watch` / `Skip` / `Pause` verdict — see §3 |
| size | determine or suggest a position size, share count or risk fraction |
| override | bypass, soften or re-weigh a veto, a hard gate or a skip code |
| originate a number | produce a probability, win rate, expectancy, score, threshold, stop, target or edge that no deterministic component computed |
| mutate | change a parameter, a rule, a strategy or its own permissions |
| reach out | call a broker, a vendor or any external service directly |
| substitute | treat missing data as a value, or its own memory as a source of truth |

`REQ-AI-001` and `REQ-AI-002` state the first four of these normatively and are **applicable and
unmet** — unmet because no agent exists, not because they are deferred.

## 3. The boundary that actually matters: synthesis versus recommendation

A-001 says the agent may present a global picture and may never decide. The whole difficulty is that
those two shade into each other, and this section is the reason this document had to be written
before any implementation.

**The decision artifact is `Trade` / `Watch` / `Skip` / `Pause`.** It is course-verbatim (M32, M33,
M69), it is a five-enum controlled vocabulary that `UX_COPY.md` forbids paraphrasing, and
`DECISION_STATE_MACHINE.md` binds each value to an action. **An agent that emits one of those values
has decided**, whatever the surrounding prose says. So:

1. **The agent may not emit the vocabulary, or any synonym, paraphrase or translation of it.** Not
   "looks tradeable", not "I would skip this", not a colour, not an emoji, not a score that maps
   onto it one-to-one.
2. **The agent may not order candidates by desirability.** A ranked list is a recommendation wearing
   a table, and the top row is a decision the reader did not make.
3. **The agent may order candidates by a deterministic key, and must name it.** Ordering by 20-day
   dollar volume, by session date, by a validated component's own output — all fine, because the
   ordering belongs to the component and is reproducible without the model. **An ordering the agent
   cannot attribute to a named key is forbidden.**

Rule 3 is what makes rules 1 and 2 checkable rather than aspirational: every ordering carries the key
it used, and a reviewer can recompute it.

### What it may do

- Assemble what is known about an instrument across the layers and state it in one place.
- Surface **conflict** — two components disagreeing, a validated finding contradicting an assumed
  parameter, a fresh price against stale fundamentals.
- Surface **absence** — a checklist item reporting `unavailable`, a parameter still `unset`, a
  component whose validation status is `Untested`.
- Restate a deterministic component's output with its provenance attached, which is what every
  number in this system already carries.
- Say that it cannot brief, and why (§6).

The distinction in one line: **the agent may tell you what the system knows and where the system
disagrees with itself. It may not tell you what to do about it.**

## 4. Decision context — what the agent is allowed to see

ТЗ §3.8 corrects the loose claim that an AI "considers all information". The accurate form:

> the agent receives all **relevant, permitted, point-in-time available, quality-gated** information
> included in a versioned decision context.

The context is assembled by deterministic code, versioned, and pinned to a `knowledge_time` exactly
as every other read in this system is (`POINT_IN_TIME_SPEC.md`). **The agent never fetches**; the
layer contracts already forbid the decision path from reaching a vendor, and gate 6 enforces it.

Excluded from the context by construction, not by instruction:

- anything with `knowledge_time` after the context's `as_of` — the look-ahead rule, unchanged
- unverified external claims with no provenance
- disabled components, and hypotheses recorded as refuted
- values that are stale or unknown without their status travelling with them (`REQ-DATA-002`)

**Every value in the context arrives with its provenance and validation status**, because
`ParameterUse` and the nine validation statuses already travel with every computed value
(`REQ-OUTPUT-001`). The agent inherits that; it does not get a cleaned-up view that has lost it.

## 5. Probability, and the six things that are not it

ТЗ §39 refuses a single `confidence` number, and this tree already has most of the dimensions:

| Dimension | Where it lives now |
|---|---|
| outcome probability | **nowhere** — needs a validated expectation estimate; none exists |
| evidence quality | validation status, nine values, on every `ObservationSeries` |
| data quality | `DATA_QUALITY_SPEC.md` gates and the completeness check |
| assumption exposure | `uses_assumed_parameters`, already computed and reported |
| model calibration | not applicable until a model exists |
| operational health | `OBSERVABILITY_SPEC.md` |

**A probability may come only from a validated expectation estimate, a calibrated statistical model,
or a matched historical cohort.** A model's own stated confidence is not a probability and may not
be rendered as one, compared against one, or stored in a field typed for one.

This is not hypothetical caution. The project's one validated finding is fragile to ~2% of trades
missing at −2R, and its base strategy is negative at measured costs. A fluent agent asked "how likely
is this to work" can produce a confident-sounding number in the same register as those measured ones,
and the reader has no way to tell them apart. **High setup score with low evidence quality is
interesting and not authorised** — the two must be displayed as separate quantities and never
combined into one.

## 6. Abstention is a first-class output

Adapted from ТЗ §37.7. Where the ТЗ requires `NO_TRADE`, this system has no action for the agent to
take, so abstention takes the form of a **coded refusal to brief** — the same shape every other
component uses when it cannot answer (`FAIL_CLOSED_POLICY.md`, `CODES.md`).

The agent must refuse when: a critical input is missing or stale; a parameter it would rely on is
`unset`; the regime is unknown; the instrument is outside the validated domain; evidence is
insufficient; its own output fails schema validation; a veto conflict is unresolved; a data provider
is quarantined.

**A refusal is not a failure of the agent.** `unavailable` is not `fail` — a gap in the system and a
fact about the trade are different claims, and collapsing them is the most damaging error this
product can make. An agent that always produces a brief is the same defect as a gate that always
passes.

## 7. Determinism, and where it stops

`DETERMINISM_SPEC.md` requires byte-identical re-runs from a manifest, and that is a ratified Track A
criterion. **An external model cannot be promised to satisfy it** — no provider guarantees token-level
reproducibility across time.

The boundary is therefore explicit: **the deterministic core stays byte-identical; the agent sits
above it**, in the same position as `SYSTEM_MODES.md` places research relative to the snapshot.

What is recorded instead, so a decision remains auditable as a historical record even if a re-run
produces different prose: full input context, model identifier and version, prompt version, tool
policy version, output schema version, context-builder version, temperature, seed if offered, the
raw output, a response hash, and timestamps.

**The recorded brief reproduces as a record, not as a computation.** That distinction is stated
plainly because it is the one place this system knowingly holds something it cannot recompute, and
pretending otherwise would be the dishonesty the whole tree is built against.

## 8. Untrusted text

News, filings and web pages are **untrusted input**, in the same category `SECURITY.md` already
assigns to the market-data vendor: *"unofficial and scrapes a consumer site — treat its output as
untrusted input."*

Required before any such source reaches a context: a source allowlist; provenance on every claim;
separation of data from instructions, so that text inside a document can never be read as a
directive to the agent; duplicate-story clustering; contradiction handling; expiry; the extraction
model's version; and confirmation against a primary source before anything derived from it is
treated as a fact.

## 9. No live self-learning

Adopted from ТЗ §38.3 without modification, because it matches this project's existing discipline
exactly:

```
live outcome → immutable journal → offline research → new hypothesis
             → pre-registered validation → review → versioned promotion
```

Forbidden: autonomous parameter changes, self-editing prompts, online optimisation after a losing
streak, and silent strategy mutation. All four are the same failure — a change to the system that no
pre-registration predicted and no version records. `AUDIT_AND_IMMUTABILITY.md` and the prereg
discipline already forbid this for humans; the agent gets no exemption.

## 10. Open items

- [ ] **Owner ratification of §3.** The synthesis/recommendation boundary is the load-bearing part
      of this document and it is authored, not derived. Rule 3 — *an ordering must name a
      deterministic key* — is the specific proposal that wants a yes or no.
- [ ] **No expectation estimate exists**, so §5's probability row has no source. The agent cannot
      state an outcome probability at all until `COVERAGE_AUDIT.md`'s expectation/baseline work
      lands, and it should refuse rather than approximate.
- [ ] **Nothing here is gated.** The prohibitions in §2 and §3 are prose. At minimum, the controlled
      vocabulary should be checkable against agent output automatically, in the way gate 2 checks
      verbatim blocks — a spec that only a careful reader enforces is what §1's chain diagram exists
      to avoid.
- [ ] **Model governance** — the model record, evaluation suite and approved-action list from ТЗ §38
      — follows this document. It is not written and must not be written first.
