# PREREG: Does the trend definition change which population is selected, or only its size?

```
id:      PR-001
date:    2026-08-02
author:  owner
status:  registered
blocked: backtest harness (BACKTEST_PROTOCOL 2)
```

## 0. Refutation-family check

- **searched:** `registry/course_index.yml` for trend topics (M71-T1057 `Условия тренда`, M22–M24
  trend structure topics); `docs/` for any prior trend study; `docs/prereg/` — empty before this.
- **found:** none. This project has run zero studies. The course names `Условия тренда` as a required
  strategy-card field and supplies no definition.
- **distinct because:** first study of this family.

A note this section exists to make: this project inherits **no** refuted levers, because it has
inherited no results. That is a real and temporary advantage, and this file is the start of the
record that will make section 0 useful for the next study.

## 1. Question

Given several defensible definitions of "in an uptrend", do they select **different instruments** on
the same day, or largely the same instruments in different quantities?

## 2. Hypothesis

The candidate definitions produce **highly overlapping selections**, so the choice among them is a
threshold choice (how many candidates) rather than a signal choice (which candidates).

Concerns: `screen.trend_definition`, and by extension `screen.pullback_definition` and
`screen.breakout_definition`, which are all stated relative to a trend.

## 3. Prediction

Candidate definitions, all computable from daily bars alone:

| | Definition |
|---|---|
| A | close > SMA(200) |
| B | SMA(50) > SMA(200) |
| C | close > SMA(50) > SMA(200) |
| D | higher highs and higher lows over the last N swing pivots |
| E | ADX > threshold with +DI > −DI |

**If the hypothesis is TRUE:** pairwise Jaccard overlap of the daily selected sets is high — the same
names appear under every definition and the definitions differ mainly in count.

**If FALSE:** overlap is low, at least one definition selects a substantially different population,
and the choice is a signal choice that must be made on evidence rather than convenience.

**Threshold, fixed now:** median daily pairwise Jaccard ≥ 0.70 across the window supports TRUE;
≤ 0.40 supports FALSE; between is inconclusive.

This is deliberately a **selection-overlap** study and not a performance study. Overlap is measurable
without a strategy, an exit model, or a cost model — none of which exist yet — and it answers the
question that actually blocks progress: whether picking one definition now is a cheap decision or an
expensive one.

## 4. Data

```
universe:      the liquidity rule (universe.min_adtv_20d, universe.min_price) once set;
               until then, an explicit frozen instrument list recorded with the run
window:        10 years of daily bars ending at the study's snapshot, both exchanges,
               reported separately per BR-9
snapshot:      the knowledge_time pinned at registration time, recorded in the manifest
costs:         not applicable - no trades are simulated
survivorship:  ABSENT. Delisted instruments are unavailable (BACKTEST_PROTOCOL 6). For an
               overlap study the bias is weaker than for a return study, because a delisted
               name would be absent from every definition's selection alike - but it is
               recorded on the evidence record regardless, per owner decision 2026-08-02.
```

## 5. Method

```
split:          none - this is descriptive, not fitted. No parameter is being chosen from
                the data, so there is nothing to hold out. Stated explicitly because a
                study with no split usually means someone forgot one.
selection rule: not applicable
perturbations:  SMA periods moved +/- 20% (parameter stability, WALKFORWARD_SPEC 4 row 1);
                overlap recomputed per regime once a classifier exists
statistic:      daily Jaccard index |A n B| / |A u B| between each pair of definitions;
                report the median and the 10th percentile across sessions, both per country
```

The 10th percentile matters more than the median: if definitions agree on calm days and diverge in
exactly the conditions where the decision is hard, a high median hides the finding.

## 6. Decision rule

```
accept (TRUE):  median pairwise Jaccard >= 0.70 AND 10th percentile >= 0.50
                -> pick a definition by simplicity and cost, record as DR-003
reject (FALSE): median <= 0.40 OR 10th percentile <= 0.25
                -> the choice is a signal choice; a performance study is required before
                   any definition is adopted, and screen.trend_definition stays unset
inconclusive:   anything else -> report, adopt nothing, and say what would resolve it
```

## 7. Stopping rule

The study ends when all five definitions have been computed over the full window. There is no
interim look and no early stop — the window is fixed at registration and the statistic is computed
once, over all of it.

## 8. Sample

```
minimum:     2000 trading sessions per exchange, and at least 30 instruments with full
             history over the window
if not met:  report the coverage and refuse the verdict (VALIDATION_PROGRAM 3)
```

## 9. What would refute this

A single pair of definitions with median Jaccard below 0.40 refutes the hypothesis, even if the other
pairs agree. The claim is that the *family* is interchangeable; one member that is not is enough.

## 10. Amendments

**2026-08-02 — before any data was seen, before the study ran.** Checked whether the five candidate
definitions are course-sourced. Four are; one is not.

ADX appears nowhere in the course as a rule, a definition or a topic title. It occurs only as a
chart-panel label (`S 94.5 ADX · ATR`) on Module 30 figures. The regime topics that carry those
figures define a regime as direction, breadth and volatility, and name no indicator at all.

**Definition E is therefore an authored candidate, not an inherited one**, and is marked as such
here rather than allowed to look like transcription. It stays in the study — an outside definition
is a legitimate comparison and arguably the most informative one, since it is the only candidate not
built from moving averages. But if E wins, adopting it is a decision record with no course backing,
and that has to be visible at the moment the choice is made rather than discovered later.

Definitions A, B and C rest on `M25-T0382` (SMA). Definition D rests on `M12-T0201`/`M12-T0202`
(previous high, previous low) and `M09-T0162`/`M09-T0163` (loss of the previous low/high).

No other section changed.

---

**2026-08-02, second amendment — still before any data was seen, before the study ran.** Three
changes, each forced by something that turned out to be true rather than by a preference.

**1. The study runs on A–D. Definition E is deferred to PR-001b.**

E needs `regime.adx_threshold`, which is `unset` and whose only citation is a chart-panel label.
Setting it would mean choosing a number that changes which instruments E selects — inside a study
whose entire question is whether the choice of definition changes which instruments get selected.
That is the study answering part of itself.

PR-001b will run E across a **range** of thresholds and report overlap as a function of threshold,
rather than picking one. That is strictly more informative and it needs no arbitrary choice. It is
registered separately because it is a different design, not a footnote to this one.

Consequence for §6: the decision rule applies to the six pairs among A–D. A verdict on those six
is a verdict about the moving-average family plus structure, not about "all five candidates", and
must be reported as such.

**2. The universe is US-only, and this is a limitation, not a scope choice.**

`DR-003` set the liquidity rule, and the Canadian side has no free symbol directory in hand — the
rule applies to `.TO` identically but the instruments cannot be *enumerated*. §4 said "both
exchanges, reported separately per BR-9". That cannot be honoured, so the result is a US result and
says so. Rerunning on Canada when enumeration is solved is a separate run, not a silent extension.

**3. Pairs are compared only over instruments both definitions could evaluate.**

§5 said the statistic is the daily Jaccard between selected sets. Implementing it revealed an
ambiguity that matters: a definition that *cannot answer* for an instrument selects nothing there,
and a naive Jaccard scores that as disagreement. STRUCTURE warms up later than the moving-average
definitions, so it would have scored artificially low against all three for exactly the reason §3
of the original registration warned about — a definition looking different for a reason unrelated
to trend.

The statistic is therefore computed on the co-decidable subset per session, and each pair reports
`mean_decidable` so a comparison made over three instruments is distinguishable from one made over
forty. Sessions where neither could answer contribute no observation rather than a 1 or a 0.

This is a clarification of §5, not a change of question — but it changes numbers, so it is recorded
here rather than absorbed into the code.

---

**2026-08-25, third amendment — long after the study reported, and it changes no result.** The
second amendment's point 2 said the Canadian instruments *"cannot be **enumerated**"*. **They can.**
TMX serves its own listed-company directory free, no account and no key
(`python tools/probe_canada.py --full`; `DR-003` *"Gap 1 is closed"*, 2026-08-25).

**What is being corrected is a qualifier, not a fact about this study.** `DR-003` wrote *"no free
symbol directory **in hand** … cannot **presently** enumerate"* — which says nobody had one, not
that none exists. `PR-001`, `PR-002`, `PR-005` and `PR-008` all narrowed to a US-only universe on
that record, citing it eight times between their registrations and their reports. **Five keep the
qualifier** — this registration's own line above, `PR-002`'s third amendment, and the country rows
of this study's report, `PR-005`'s and `PR-008`'s, all say *"in hand"*. **Three drop it into an
unqualified "cannot":** the sentence above, and `PR-002`'s report twice, once in its limitations
table and once where it paraphrases its own amendment as *"records that Canada cannot be
enumerated"* — an amendment that says *"in hand"*.

Derive the split rather than trusting this paragraph. It counts the citations that existed **before**
this amendment; the command below also returns this amendment's own quotations and the matching
correction appended to `PR-002`'s report the same day, so subtract those to reconcile:

```bash
git grep -nEi "in hand|cannot be \*?enumerat|cannot presently" -- 'docs/prereg/*.md' 'docs/prereg/results/*.md'
```

**The sharpest instance is in this file, and it is one sentence long.** The paragraph above keeps
`DR-003`'s qualifier in its first clause and drops it in its second: *"no free symbol directory in
hand — the rule applies to `.TO` identically but the instruments cannot be enumerated."* Citation
rot did not need a second document or a second week; it happened across a dash. That is why
`AGENTS.md` §15 asks for an impossibility to be treated as a claim, and it is worth more than the
refutation itself.

**This repairs nothing and is not an invitation to re-run.** The endpoint serves **today's**
directory; applying it to the 2015-2024 window this study measured is survivorship bias with extra
steps, which is the objection `DR-003`'s own alternatives table already raises against index
membership. Bar coverage is a further and separate question — the Canadian half of the store is
empty. **The verdict, the sample and every number in the report are untouched**, and this study's
finding was negative in any case, so a wider universe could only have widened a refutation.

**What it does change** is the standing of the sentence *"rerunning on Canada when enumeration is
solved is a separate run"*: enumeration is solved, so that separate run is now blocked on stored
bars rather than on a source that does not exist.

No other section changed.
