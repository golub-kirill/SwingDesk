# COMPONENT REGISTRY SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim` + authored

<!-- verbatim-sources: Course_Production_Rules_v3.8.md -->

**Data:** `registry/course_index.yml` (generated) · `registry/parameters.yml` ·
`registry/components.yml` (to be created)

The registry is the spine. `course_index.yml` already holds all 1379 topics with their stable IDs;
this document defines what a *component* record adds on top, and what each of the three activation
states costs to reach.

---

## 1. The required record

Verbatim, §3.8:

> "Each component has one canonical definition, explicit inputs and outputs, an owner, a version,
> tests or verification method appropriate to its role, and a visible list of known consumers.
> Strategies reference components rather than copying their formulas or silently reimplementing
> them."

Seven mandatory fields, of which two are unusual and both are load-bearing:

- **`owner`** — a person, for a single-user system. It still matters: it is who decides when the
  component's validation status changes.
- **`known consumers`** — a *visible list*. This is what makes "changing a shared component never
  silently rewrites historical evidence" checkable rather than aspirational. Without it you cannot
  answer "what breaks if I change this".

For a Derived Observation, §3.6 adds eleven more fields, which `ALGORITHM_SPEC.md` owns:

> "Every derived observation defines inputs, formula or algorithm, parameters, units, timeframe,
> sampling and session rules, warm-up, missing-data behavior, time alignment, output range, and
> version."

## 2. Record shape

```yaml
- component: M26-T0393-v5.0     # from course_index.yml; the course's own id
  name: RSI
  layer: Derived Observations
  stage: Setup
  claim_type: Derived Observation
  validation: Untested
  activation: registered        # registered | specified | active
  implements: null              # module path, e.g. swingdesk.derived_observations.momentum:rsi
  parameters: []                # ids from registry/parameters.yml
  consumers: []                 # component ids that depend on this one
  owner: null
  verification: null            # golden vectors | property test | review
  spec: null                    # anchor into ALGORITHM_SPEC.md
```

`component`, `name`, `layer`, `stage`, `claim_type` and `validation` are **generated** from
`course_index.yml` and must not be hand-edited — `tools/build_course_index.py` self-checks them
against the source. Everything else is authored as a component advances.

## 3. Activation states

| State | Requires | Cost |
|---|---|---|
| `registered` | course id, name, layer, stage, claim type, validation status | free — all 1379 are here already |
| `specified` | algorithm spec written; parameters declared with provenance; consumers listed | authoring |
| `active` | parameters have values; verification exists (golden vectors or property test); `implements` points at real code | authoring + evidence |

**`Untested` is a permitted status for an `active` component.** The course is explicit that
validation statuses are not grades:

> "Validation statuses are not grades. "Forward Tested" does not mean profitable, universal,
> permanent, or suitable for every user. The measured result and acceptance verdict remain visible."

What is *not* permitted is hiding it. An active component displays its validation status wherever
its output appears. This is how full-catalogue coverage (owner decision D2) stays honest: ~460
computable components can be registered and specified without pretending any of them is proven.

## 4. Validation status — 9 values

Verbatim from §3.7, in order:

```verbatim
Not Applicable
Untested
Historically Tested
Out-of-Sample Tested
Walk-Forward Tested
Forward Test Running
Forward Tested
Rejected
Retired
```

Only the first two occur in the course as shipped: `Not Applicable` 1209, `Untested` 170, everything
else **zero**. Every component imported from the course therefore starts at `Not Applicable` or
`Untested`, and any higher status is something this project earned, never something it inherited.

`Retired` is worth noting — it exists for a component withdrawn *because the world changed*, not
because it failed. That is a different record from `Rejected` and the distinction should survive
into the UI.

## 5. Claim type — 8 values

Verbatim from §3.7:

```verbatim
Definition
Source Fact
Observed Market Mechanism
Derived Observation
Inference
Operational Course Rule
Empirical Result
Untested Hypothesis
```

**Only five are used in the course**: Definition 916, Operational Course Rule 173, Untested
Hypothesis 124, Derived Observation 121, Inference 45. `Source Fact`, `Observed Market Mechanism`
and `Empirical Result` are defined and never applied. The enum keeps all eight — `Empirical Result`
is precisely what this project will produce, and it needs somewhere to go.

The inference rule is worth transcribing because it constrains naming:

> "Terms describing hidden intent, such as accumulation, absorption, manipulation, institutional
> activity, or stop clustering, are Inferences unless the required direct data and identification
> method are stated. OHLCV alone may not convert them into Source Facts."

A component named for hidden intent is an `Inference` and must be classified as one, regardless of
how confident its output looks.

## 6. Versioning

> "changing a shared component never silently rewrites historical evidence. Affected strategy
> versions are re-tested or remain linked to the earlier component version"

1. A change to a component's definition **or any of its parameters** increments its version.
2. Its validation status resets (`PARAMETER_REGISTRY.md` §6).
3. Every consumer either re-tests against the new version or stays pinned to the old one. Both are
   legitimate; silently inheriting is not.
4. Evidence records pin the exact component versions they were produced with
   (`EVIDENCE_RECORD_SPEC.md`).

The course's ids already carry a version (`M26-T0393-**v5.0**`) — that is the *course's* version of
the topic. This system's component version is separate and independent; a component can reach v3
while its source topic stays at v5.0.

## 7. Checks this registry unlocks

Currently review-only (`DEPENDENCY_LAW.md` §4), mechanisable once `components.yml` exists:

| Check | Rule enforced |
|---|---|
| `implements` is injective | "one canonical definition" — two components may not map to the same function, and one component may not have two implementations |
| every `active` component has non-null `implements`, `verification` and `spec` | activation gate |
| every parameter id in `parameters` exists in `parameters.yml` | no dangling references |
| `consumers` is the transitive inverse of `parameters`+`spec` dependencies | "visible list of known consumers" is complete, not aspirational |
| no `active` component has an `unset` parameter | fail-closed |
| every non-Definition topic in `course_index.yml` has a registry row | full-catalogue coverage (D2) |

## 8. Open items

- [ ] Create `registry/components.yml`, generated from `course_index.yml` for the ~460 non-Definition
      topics at `registered`, then hand-advanced.
- [ ] Decide whether Definition topics get rows at all. They compute nothing — but they carry
      glossary content and the `GLOSSARY.md` seed, so a lighter record may be warranted.
- [ ] `tools/verify_components.py` implementing §7.
- [ ] Owner field: trivially "the owner" today, but the field exists to survive that not being true.
      Keep it required.
