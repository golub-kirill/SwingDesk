# DEFINITION OF READY / DONE

**Status:** drafting · **Tier:** 8 (project management) · **Content:** authored

Five kinds of work item, each with different entry and exit criteria. A single checklist for all of
them would be either too loose for a component or absurd for a document.

**Done means the merge gates pass**, always, for every kind. What follows is what each kind needs
*beyond* that.

---

## 1. Component

A calculation implementing a course topic.

**Ready when**
- the course topic id exists in `registry/course_index.yml`, and its `layer` is the package it will
  live in — a Decision Logic topic does not go in `derived_observations`
- the eleven `ALGORITHM_SPEC` fields are answerable: inputs, formula, parameters, units, timeframe,
  session rules, warm-up, missing-data behaviour, time alignment, output range, version
- every parameter it needs exists in `registry/parameters.yml`, set or `unset` — `unset` is ready,
  *absent* is not

**Done when**
- `SPEC` mirrors the registry row and the mirror test passes
- **golden vectors exist**, with expected values authored from the source arithmetic and a
  `derivation` field explaining them — a vector that only records what the code printed cannot tell
  you the code was ever right
- warm-up emits `None` rather than a partially-warmed value
- an unset parameter produces a coded refusal naming the parameter
- it is registered in `validation/golden.py` and in the component test's `SPECS`

**Not done if** it works and has no vectors. That state has a name — `specified` — and calling it
`active` is the drift `RISK_REGISTER.md` B-2 records.

## 2. Parameter

**Ready when**
- the id is `group.name`, and `named_in` cites where the course mentions the concept — or says
  explicitly that it is authored
- it is clear whether the value is a **convention** (needs a decision record) or a **claim** (needs a
  pre-registration). See `docs/decisions/README.md` §1

**Done when**
- `unset` — nothing more. This is a legitimate terminal state and the commonest one: 84 of 96
- `assumed` — a `DR-NNN` or a literature citation resolving to something a reader can open, and the
  DR names what would overturn it
- `validated` — evidence from a **pre-registered** study, its report committed, and its limitations
  in the registry note where anyone reading the value sees them before the number

**Never** — a value set because code needed one. The refusal path exists so that never happens.

## 3. Study

**Ready when**
- `PR-NNN` is committed **before** the run — the commit timestamp is the evidence that it was
- §0's refutation-family check names what was searched and why this is not the same question again
- the decision rule, stopping rule and minimum sample are fixed, and `inconclusive` is reachable
- the statistic's convention is named, not just its name

**Done when**
- the result JSON records the seed, every parameter, the admitted universe and the verdict
- a written report states what the result does **and does not** say
- limitations sit **with** the result, not beneath it
- the verdict is refused if the sample rule was not met, whatever the numbers looked like
- any deviation from the registration is an appended, dated amendment saying when it was made
  relative to seeing data

**Post-hoc analysis is permitted and must be labelled.** PR-002's stronger null and its survivorship
bound are both post-hoc, both labelled, and both changed how the result should be read without
changing its verdict.

## 4. Document

**Ready when**
- its row exists in `docs/README.md` with what it freezes and where its content comes from
- if it transcribes, the `verbatim-sources` declaration is written in the same commit — gate 2 only
  checks documents that opt in, and that is its one weakness

**Done when**
- every `verbatim` block passes gate 2 against freshly extracted source
- authored content is distinguishable from transcribed content on sight
- open items are listed as open items rather than omitted
- counts and figures it quotes are current — three stale numbers were found in `docs/README.md`
  by accident, which is the wrong way

## 5. Surface

CLI command, report section, web view, notification.

**Ready when**
- `PRODUCT_SURFACES.md` says which surface owns it, and no rule lives here that is absent from the
  CLI
- every number it shows can name its component, version, parameter provenance and validation status

**Done when**
- assumption-derived numbers are marked **adjacent to the number**, not in a footnote
- a qualified evidence record shows its qualification wherever its component's output appears
- refusals are legible: a `Skip` names its code and, where relevant, the parameter that was missing
- it renders on a Windows console without an encoding crash — the course's vocabulary is Russian and
  a report that cannot print it crashes exactly when it has something to say

---

## 6. The two rules that outrank the rest

**A gate that is wrong gets fixed or removed, never skipped.** There is no `--skip` flag and adding
one is out of scope permanently. A routinely-bypassed gate teaches that red is normal, which is
worse than having no gate.

**Nothing is done because it is finished.** Six of the eight realised risks in `RISK_REGISTER.md`
were found *after* the work looked complete — by a gate, a test, or an attempt to break a gate.
Finished is a feeling; done is a definition.
