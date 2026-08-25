# PR-002 RESULT: breadth separates outcomes — and one confound could explain all of it

```
prereg:     PR-002 (registered 2026-08-02, amended twice before running)
status:     reported 2026-08-02 - VERDICT CORRECTED 2026-08-16
run:        2026-08-02
verdict:    INCONCLUSIVE - single-market finding, not generalised (corrected; was ACCEPT)
data:       PR-002.json
```

> ⚠️ **THE VERDICT ON THIS REPORT WAS WRONG AND IS CORRECTED.** It read `ACCEPT`. It should have
> read `INCONCLUSIVE` on the day it was written. See §"Correction, 2026-08-16" at the end.
>
> **Every measurement below stands.** The numbers are exactly what the 2026-08-02 run produced and
> none has been altered. What was wrong was the label applied to them, and the passages that lean on
> that label are struck through in place rather than deleted — deleting a withdrawn claim hides the
> record it exists to keep.

---

## The hypothesis

Registered: *a regime label carries decision-relevant information — the distribution of forward
outcomes for the same setup differs materially across regimes, measured out of sample.*

~~Not refuted.~~ **Not refuted, on one market.** `BREADTH_MEDIAN` separates outcomes on the test
window under both cost regimes, under the registered baseline **and** under a stricter one added
post-hoc — all of it on a US-only sample, which §6 sends to the inconclusive branch.

## How the variant was chosen

Thresholds fitted on **train only** (2016-08-01 → 2021-07-28, 1257 sessions). The variant selected
on **validation** (2021-07-29 → 2023-07-27, 502 sessions) by **stability** — fewest label flips per
100 labelled sessions — never by outcome:

| Variant | flips / 100 sessions |
|---|---|
| **`BREADTH_MEDIAN`** | **3.785** ← selected |
| `VOL_TERCILE` | 5.179 |
| `BREADTH_TERCILE` | 5.777 |
| `BREADTH_X_VOL` | 5.777 |

Selecting on the outcome difference would have been the study answering its own question. The
registration prohibited it, and the prohibition bound: the selected variant was not chosen for
separating best.

Fitted breadth boundary: **0.647** — the train-window median share of the universe above its own
200-day average. Frozen, then applied forward.

## Result — test window only, 2023-07-28 → 2026-07-31

`BREADTH_MEDIAN`, 1183 trades at 1× costs:

| Regime | trades | mean net R |
|---|---|---|
| `BREADTH_LOW` (≤ 0.647) | 466 | **+0.2299** |
| `BREADTH_HIGH` (> 0.647) | 717 | **−0.1304** |

Range **+0.3602R**, against a random-partition baseline whose 95th percentile is 0.1819 —
**percentile 100.0**.

At 3× costs: `LOW` +0.1084, `HIGH` −0.2281, range +0.3365R, percentile 100.0. The separation is not
a cost artefact; the whole distribution shifts down and the gap stays.

**The direction is the finding, and it is counterintuitive.** Breakouts bought when *fewer* than
two-thirds of the universe is above its 200-day average outperform breakouts bought when *most* of
it is — by about a third of an R per trade. The naive expectation is the opposite.

## The post-hoc check, and why it was needed

**Not part of the registered decision rule.** The registered baseline permutes individual trades,
which assumes they are exchangeable. They are not: on any session dozens of instruments fire
together, so trades within a regime are clustered in time and correlated. Under clustering the
effective sample is far smaller than 1183, and a trade-level permutation understates the null's
spread — which inflates the observed percentile.

So a second baseline permutes the **date → label** assignment instead, preserving both the number of
sessions per regime and the clustering of trades within a session. It is strictly harder to beat.

| Variant | trade-null (registered) | date-block null (post-hoc) |
|---|---|---|
| `BREADTH_MEDIAN` 1× | 100.0 | **100.0** separates |
| `BREADTH_MEDIAN` 3× | 100.0 | **99.6** separates |
| `BREADTH_TERCILE` 1× | 99.8 | 98.2 separates |
| `BREADTH_X_VOL` 1× | 91.6 | 94.8 **does not** separate |
| `VOL_TERCILE` 1× | 85.0 | 82.3 does not separate |

The check earns its place: `BREADTH_X_VOL` clears the trade-level null at 3× and fails the
date-block null at 1×, which is exactly the inflation the correction was added to catch. The
selected variant survives both.

## What this does and does not say

**Does:** on this universe, this trigger and this exit model, the share of instruments above their
own 200-day average, thresholded at a boundary fitted years earlier, sorts subsequent breakout
outcomes by roughly a third of an R per trade, out of sample, under cost stress, and under a null
that respects date clustering.

**Does not:** say the effect will persist, that it is exploitable after portfolio constraints, or
that breadth *causes* anything. And it does not say what a strategy should do — a regime is
`измеритель, а не источник уверенности`, a gauge and not a source of confidence (M30-T0450). Acting
on it is `M30-T0451`, a separate Untested topic.

## The confound that could explain the whole thing

**Survivorship is absent, and this is where it bites hardest.**

Low-breadth periods are drawdowns. In a survivors' universe, the instruments that failed *during
those drawdowns* are missing from the sample entirely — they were delisted and no free source
serves them (`DR-003`). So the `BREADTH_LOW` cell is measured over exactly the instruments that
survived the conditions defining that cell.

That is not a generic caveat. It is a mechanism that would produce this specific result — a positive
mean in the stressed regime — with no real effect present. It cannot be measured or bounded on free
data.

**Treat the direction as unconfirmed until it is reproduced on survivorship-complete data.** The
separation itself is harder to explain away than its sign, but the sign is the part anyone would act
on.

### How much bias would it take? — post-hoc bound, 2026-08-02

Owner decision D10 reaffirmed the free tier, so this confound will not be measured. It can still be
**bounded**, and the bound is the useful thing: not "how much bias is there" — unanswerable — but
"how much would there have to be".

Missing trades added to the `BREADTH_LOW` cell only, enough to pull the gap down to the date-block
null's 95th percentile:

| Missing trades at | count | share of the LOW cell | share of all trades |
|---|---|---|---|
| −1R each | 54 | 10.4% | **4.4%** |
| −2R each | 28 | 5.7% | **2.3%** |
| −3R each | 19 | 3.9% | **1.6%** |

Spread **proportionally** across both cells instead: **34.9%** of all trades would have to be
missing. (The missing trades' R cancels entirely in that shape — the gap simply scales by 1/(1+p) —
which is why the concentrated shape is the one that decides this.)

**This is the most important number in the report.** A delisted instrument is not a −1R trade; it is
a halt, a gap and a severe loss, so the −2R and −3R rows are the relevant ones. **Somewhere between
1.6% and 2.3% of trades going missing, concentrated in the stressed regime, erases the finding.**
Over a three-year window containing a drawdown, that is not an extreme assumption — it is a likely
one.

So the honest reading is narrower than the verdict:

- The **verdict stands** — it was computed under a rule fixed before the run, and the rule was met.
- The **result is fragile** to the one bias this project structurally cannot correct, and fragile at
  a magnitude that is plausible rather than far-fetched.
- What survives confidently is the weaker claim: **breadth is not obviously irrelevant**, and a
  breadth-conditioned study on survivorship-complete data would be worth running if such data ever
  became available.

Nothing here changes PR-002's verdict, and it is labelled post-hoc for that reason. It changes what
a careful reader should do with it.

## Other limitations

| | |
|---|---|
| **single market** | US only. §6 required significance in both countries independently; Canada cannot be enumerated (`DR-003`), so that cannot be met and the result is reported as single-market, which §6's inconclusive branch anticipates. |
| **one trigger, one exit model** | 20-day breakout, 2×ATR stop, 20-session time exit. A different setup could reverse this. |
| **breadth is of our universe** | 68 instruments, not the market. The measure describes the sample it was computed over. |
| **one test window** | 755 sessions, 2023-07-28 onward — a single, mostly rising market. A regime study on a window containing one regime transition is weaker than its trade count suggests. |
| **no portfolio** | independent trades, no position or correlation limits. |
| **VOL_TERCILE's thin cell** | 7 trades in `VOL_LOW`. Reported, and its verdict refused on that basis. |

## Consequence

~~`regime.classifier_rule` is set to **`BREADTH_MEDIAN`, boundary fitted on the training window**,
provenance `validated:PR-002` — the first `validated` parameter in this project.~~

~~That provenance is permitted on survivorship-incomplete data only because the owner decision of
2026-08-02 allows advancement *provided the record discloses the coverage*, and the disclosure above
is that record.~~

**Withdrawn 2026-08-16.** `validated:` required a verdict this study did not earn. The parameter
keeps its fitted value and moves to **`assumed:PR-002`** — the value came from a real study that did
not clear the validation bar, which is what `assumed:<citation>` means. **The project now has zero
`validated` parameters**, and that is the honest count. Anyone reading the value must still be able
to reach this page in one step, which is why the registry note names the confound rather than the
result.

## Correction, 2026-08-16

**The verdict violated the study's own decision rule, and the rule had already anticipated this
exact case before any data was seen.**

§6 permits `accept` only where the effect holds **in BOTH countries independently**, and sends a
result *"significant in one country only"* to the inconclusive branch — *"report as a single-market
finding and do not generalise"*. The **third amendment**, dated 2026-08-02 and marked *"before any
data was seen, before the study ran"*, records that Canada cannot be enumerated, that the
two-country requirement **"cannot be met and is NOT quietly dropped"**, and that §6's inconclusive
branch is *"the right handling"*.

The runner then implemented §6's percentile thresholds and nothing else. `tools/run_pr002.py` had no
country condition at all: it recorded `single_market: true` as a field beside the verdict — where no
reader and no gate treats it as part of the verdict — and emitted `accept`. The prereg had decided
this case; the code never encoded it.

The limitations table above named the problem on the day and the title said ACCEPT anyway, which is
worse than silence: it shows the rule was read, understood, and not applied.

**What changed:** the verdict label, here and in `PR-002.json`, and the parameter's provenance.

**What did not change:** every measurement. `BREADTH_LOW` +0.2299R vs `BREADTH_HIGH` −0.1304R over
1183 trades, percentile 100.0, survival at 3× costs, the date-block null at 99.6 — all of it is what
the 2026-08-02 run produced and all of it stands. `INCONCLUSIVE` here does not mean *"we measured
nothing"*; it means *"we measured one market and the rule requires two"*.

**This file was not regenerated, deliberately.** `run_pr002.py` fetches the current symbol directory
and current Yahoo history, so re-running it today samples a different universe over a different
window. That would replace a reported result with an unreported one rather than reproduce it, and
the record of what ran on 2026-08-02 is the thing being corrected — not re-derived. The runner is
patched so the defect cannot recur on the next study; this artifact is corrected in place, following
`PR-008`'s precedent.

**Not fixed here, and not bookkeeping.** §5 registers three perturbations — threshold ±20%, 1-bar
execution delay, and cost stress. **Only cost stress was run.** So the original `ACCEPT` rested on
one of three registered robustness checks, which weakens the finding independently of the country
condition. That is a separate defect needing a separate run, tracked in `TODO.md` §5 — recorded here
so this correction cannot be read as a relabelling exercise.

## Second correction, 2026-08-25 — a cited premise was refuted, and the verdict does not move

Two lines above assert that **"Canada cannot be enumerated (`DR-003`)"**. That is false, and it was
already an over-statement of what `DR-003` said when it was written.

**Measured, not argued.** TMX serves its own listed-company directory free, no account and no key -
`python tools/probe_canada.py --full`, and `DR-003` carries the refutation as *"Gap 1 is closed"*.
`DR-003`'s own wording was *"no free symbol directory **in hand** … cannot **presently** enumerate"*,
which says nobody had one rather than that none exists. The qualifier did not survive the citation.

**The verdict, the sample and every number in this report stand untouched, and the single-market
handling was correct then and is correct now.** Three reasons, and none of them is generosity:

1. The endpoint serves **today's** directory. Applying it to this study's 2023-07-28 → 2026-07-31
   window is survivorship bias with extra steps - the objection `DR-003`'s own alternatives table
   raises against index membership.
2. **No `.TO` bars are stored.** Enumeration and coverage are different problems and only the first
   is solved.
3. §6's inconclusive branch is reached by a single-market result whatever the reason for it, and the
   `INCONCLUSIVE` verdict of 2026-08-16 already rests on that branch.

**What changes is what a reader may conclude from this report about the future.** The two-country
requirement is no longer unmeetable in principle - it is blocked on stored bars, which is a fetch
nobody has run. A next study in this family may carry the requirement instead of declaring it
impossible, and `RISK_REGISTER.md` D-3 now says so.

**Corrected here rather than silently**, because the sentence is a claim about the world that nobody
had tested (`AGENTS.md` §15) and it sits in the file a reader opens to learn why this study could not
reach an affirmative verdict.

## Reproducing

```bash
python tools/run_pr002.py --sample 320 --seed 20260802
```

**This no longer reproduces the run above**, and did not on the day it was written either: the
directory download and the Yahoo fetch both take *current* data, and `as_of` is the wall clock. The
command re-runs the *method*, not the *sample*. Treat its output as a new study needing its own
pre-registration, not as a check on this one.
