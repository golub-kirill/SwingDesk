# EVIDENCE RECORD SPEC

**Status:** drafting · **Tier:** 4 (journal) · **Content:** `verbatim`

<!-- verbatim-sources: Course_Production_Rules_v3.8.md -->

An evidence record is what a claim about a rule must carry before the claim may be made. The course
specifies its contents field by field; this transcribes them.

---

## 1. The required fields

Verbatim, §3.7, "Every evidence panel for an implementable strategy or material decision rule
records, where applicable":

```verbatim
rule ID, version, claim type, validation status, and status date;
exact definition and frozen parameters;
market, country, universe, instrument type, timeframe, and holding period;
data providers, sample dates, sample size, missing-data policy, corporate-action
benchmark and return convention;
primary metrics, uncertainty estimates, drawdown, and material distributional
in-sample, out-of-sample, walk-forward, and prospective boundaries;
number of variants tried, selection process, multiple-testing controls, and
known failure regimes, applicability limits, and the condition that would suspend
reproducible artifact or record location and last verification date.
```

Two of those eleven lines are worth reading twice, because they are the ones a self-assessment
naturally omits:

> "number of variants tried, selection process, multiple-testing controls, and relevant rejected
> variants"

> "known failure regimes, applicability limits, and the condition that would suspend or retire the
> rule"

The first makes the search space visible — it is what `criteria.yml` `b.deflated_sharpe` computes
against, and why the trial count is **cumulative across the programme** rather than per strategy.
The second requires stating, in advance, what would make you stop believing the rule.

## 2. What cannot upgrade a claim

Verbatim:

> "Visual examples, selected trades, anecdotes, clean charts, high win rates, and mechanically
> correct formulas do not upgrade validation status. Editing a threshold after seeing results creates
> a new rule version and resets any validation claim that depended on the earlier frozen definition."

And:

> "Rejected, null, and harmful results remain in the evidence record. They may not be removed merely
> because they weaken the presentation."

**Binding:** the evidence store is append-only and includes failures. A rule that was `Rejected` keeps
its record, and that record is what stops the same idea being re-proposed as new.

## 3. Status is not a grade

Verbatim:

> "Validation statuses are not grades. "Forward Tested" does not mean profitable, universal,
> permanent, or suitable for every user. The measured result and acceptance verdict remain visible."

The nine statuses are enumerated in `COMPONENT_REGISTRY_SPEC.md` §4. Every one of them is displayed
with the measured result, never instead of it.

## 4. Project-specific mandatory fields

Beyond the course's list, three fields are mandatory here because of what was measured:

| Field | Why |
|---|---|
| **survivorship marker** | no free source serves delisted instruments (`ADR-0001` §6), so every historical result is optimistic by an unknown amount. `criteria.yml` `b.survivorship_caveat` makes this a ratified obligation. |
| **evidence-window ceiling** | any result touching `30m` is bounded by ~60 trading days of history. A claim cannot be stronger than its window. |
| **point-in-time coverage** | results computed from data predating this system's first fetch cannot claim point-in-time correctness — our revision record starts when we start (`POINT_IN_TIME_SPEC.md` §7). |

The third is easy to forget and important: **backfilled history is not point-in-time history.** It
is today's version of the past.

## 5. Relationship to the other records

| Record | Holds |
|---|---|
| `registry/criteria.yml` | the bars a claim must clear — frozen before the run |
| pre-registration | the hypothesis and the gates, written before the result exists |
| **evidence record** | what was actually measured, against those gates |
| component registry | the resulting validation status, displayed wherever the component's output appears |

The sequence is one-way. A criterion is frozen, then a pre-registration is written, then a result is
measured, then a status changes. A status that changed without an evidence record behind it is a
defect.

## 6. Open items

- [ ] Storage format. It is structured data with a fixed field set, so YAML alongside
      `criteria.yml` fits — but it grows per experiment rather than being a single document.
- [ ] Whether the evidence record embeds its metrics or references the run manifest that produced
      them. Referencing is DRY and makes the result reproducible; embedding survives the run store
      being pruned, which `POINT_IN_TIME_SPEC.md` §8 says will not happen.
- [ ] Who may set a validation status. Mechanically it should require an evidence-record id, which
      makes the answer "whoever produced the evidence" rather than a permission model.
