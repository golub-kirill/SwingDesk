# PRE-REGISTRATION TEMPLATE

**Status:** drafting · **Tier:** 5 (validation) · **Content:** authored, required by tier 2

<!-- verbatim-sources: Appendix_J_Ruchnoi_bektest_v2.0.pdf, Appendix_K_Walk_forward_test_v2.0.pdf, Module_72_Istoricheskoe_testirovanie_v4.0.pdf -->

The course never uses the word *pre-registration*. It requires the thing three separate times, and
this document is what satisfies all three at once.

---

## 1. Why this exists

| Course requirement | Where | What it forces |
|---|---|---|
| fix version, universe, dates, costs and sample size **before** the run | Appendix J, stage `Перед началом` | the plan predates the data |
| record the `Selection rule` beside the parameters chosen | Appendix K | how you chose is part of the claim |
| `data snooping` is prohibited | M72–M74 `FAIL-CLOSED` | the hypothesis predates the result |

Verbatim, the first:

> "Зафиксировать strategy version, universe, dates, costs и sample size."

And the prohibition:

> "Запрещены look-ahead, survivorship, data snooping и переход live по красивой in-sample equity
> curve."

**`data snooping` has no operational meaning without a pre-registration.** You cannot check after the
fact whether a hypothesis preceded a result unless it was written down first. A rule that cannot be
violated in a detectable way is not a rule, so either this document exists or that prohibition is
decoration.

## 2. The form

One file per study, in `docs/prereg/`, named `YYYY-MM-DD-<slug>.md`. Written and committed **before**
the study runs. The commit timestamp is the evidence that it was.

```
# PREREG: <one-line question>

id:            PR-NNN
date:          YYYY-MM-DD
author:        <owner>
status:        registered | running | reported | abandoned

## 0. Refutation-family check
Has this lever, or a lever of the same family, already been refuted here?
  - searched:   <where, and with what terms>
  - found:      <prior studies, with their verdicts, or "none">
  - distinct because: <why this is not the same question in new clothes>

## 1. Question
What is being asked, in one sentence, in a form that can come out "no".

## 2. Hypothesis
The specific claim. Names the component and version it concerns.

## 3. Prediction
What the result looks like if the hypothesis is TRUE, stated numerically before the run.
And what it looks like if FALSE. If both look the same, stop here - the study cannot inform.

## 4. Data
  universe:      the rule, not a ticker list
  window:        start, end, and why those
  snapshot:      knowledge_time this study reads
  costs:         commission model, slippage model, with values
  survivorship:  present / absent - and if absent, that the result is biased upward

## 5. Method
  split:         train / validation / test dates
  selection rule: how a parameter set is chosen from the validation window
  perturbations:  which of the six (WALKFORWARD_SPEC 4) are run, with magnitudes
  statistic:      the exact figure that decides, and its convention

## 6. Decision rule
  accept if:     <threshold, fixed now>
  reject if:     <threshold, fixed now>
  inconclusive:  everything else - a legitimate and expected outcome

## 7. Stopping rule
When the study ends. Fixed in advance and NOT contingent on the result.

## 8. Sample
  minimum:       n, and the parameter it comes from
  if not met:    the study reports the measurement and refuses a verdict

## 9. What would refute this
The observation that would make the hypothesis wrong. If nothing would, the hypothesis is not
a hypothesis.

## 10. Amendments
Appended, dated, never edited in place. An amendment after data was seen is recorded as such,
and downgrades the result to exploratory.
```

## 3. The rules around it

1. **Committed before the run.** Not written before and committed after.
2. **Never edited in place.** Amendments are appended and dated — the same discipline the journal
   uses (`AUDIT_AND_IMMUTABILITY.md`), and for the same reason: a record you can rewrite is not a
   record.
3. **An amendment made after seeing data downgrades the study to exploratory.** Exploratory results
   are useful and are not evidence. They may generate the next pre-registration; they may not
   advance a validation status.
4. **A study without a pre-registration is not evidence.** It can be reported as exploratory and
   cannot advance a validation status. `EvidenceRecord.prereg_id` is nullable precisely so this state
   is representable, and a record without one discloses `exploratory: no pre-registration` alongside
   its numbers.
5. **A choice that cannot come out "no" is not a pre-registration.** Conventions and definitions —
   Sharpe annualisation, a score scale, which moving average counts as a trend — go through a
   decision record instead (`../decisions/README.md`). The two instruments are not
   interchangeable, and a convention dressed as a hypothesis produces a study that cannot fail.
6. **`inconclusive` is a first-class outcome.** A decision rule with only accept and reject
   guarantees one of them, which is how a coin flip becomes a finding.

## 4. Section 0 deserves its own explanation

The refutation-family check exists because of a specific, cheap failure: re-running a question that
has already been answered, in slightly different clothing, and treating the new run as new evidence.

It is cheap because each individual re-run looks reasonable. It is expensive in aggregate for two
reasons — the obvious one is wasted effort; the less obvious one is that **repeatedly testing
variants of a refuted idea until one passes is data snooping conducted across studies rather than
within one.** The prohibition in §1 does not stop at the boundary of a single run.

So the check asks for the *family*, not the exact lever. "We tested a 20-day breakout and it failed;
this is a 25-day breakout" is the same family, and the burden is to say why the new version is a
different question rather than another draw from the same one.

## 5. Section 5's `statistic` field

Annualisation factor, whether the risk-free rate is subtracted, whether returns are per-trade or
per-period, and whether costs are inside the number all change the figure without changing the
strategy. A study that names "Sharpe" without naming the convention has not specified its decision
rule, and two such studies cannot be compared.

`stats.sharpe_convention` is now set by `DR-001` — `daily zero-filled portfolio returns, net of
costs, rf=0, annualised ×√252`, provenance `assumed:DR-001`. A study may use a different convention;
it must say so, and it must say why, because the comparison to every other study breaks.

The same applies to any figure in `STATISTICS_SPEC.md` whose convention is a choice rather than a
definition.

## 6. Open items

- [ ] **Multiple-testing correction.** Running many studies against one dataset inflates the chance
      that one passes. Candidate approaches from the literature: White's Reality Check, the deflated
      Sharpe ratio (Bailey & López de Prado), and the multiple-testing adjustments argued for in
      Harvey & Liu. None is adopted yet, and none comes from the course — this is an authored
      import and must be marked as one when it lands.
- [ ] Whether the trial count for such a correction is per component, per strategy, or project-wide.
      Project-wide is the honest denominator and the harshest one.
- [ ] Where pre-registrations live once there are dozens. A directory works to about thirty; an index
      generated from their front matter is the obvious next step, alongside the component registry.
- [ ] Whether an abandoned pre-registration stays in the repository. It should: a study abandoned
      after seeing partial data is exactly the kind of thing that vanishes from an honest record.
