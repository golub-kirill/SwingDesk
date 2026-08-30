# DR-017: The ADTV window is lagged three sessions, because volume is still being written for two

```
date:            2026-08-18
status:          accepted — ratified by the owner 2026-08-30
parameters:      universe.adtv_lag_sessions = 3, provenance `owner` — NOT `assumed:DR-017`;
                 §3.1 anticipated the wrong one and §7.1 records why
components:      none — the universe builder already windows the bars it averages
supersedes:      nothing. DR-003 set the threshold; this decides which bars it is applied to
implemented_by:  src/swingdesk/reference_data/universe.py :: def admits
also_built:      application/universe.py (rule_from_registry reads the lag and refuses when it is
                 unset; select widens the tail it reads by it), registry/parameters.yml (the entry)
built:           2026-08-30. §7 records what landed, the two things this record left open that
                 building it forced shut, and the one claim in it that was wrong.
```

## 1. The defect

`universe.min_adtv_20d` admits an instrument on 20-day average dollar volume. **The vendor's volume
for recent sessions is not final**, so membership is decided on a number that is still being
written.

Measured on the store's own bitemporal history — the experiment was already in it and nobody had
looked. Of 7,131 already-settled bars the vendor served twice, **7,129 had their volume rewritten**:
p50 **1.1%**, p90 **32%**, p99 **83%**, worst case **164×**. Prices are not comparable — the close
moves by p90 0.02%.

**The consequence, measured rather than argued: 6 of 1,172 instruments cross the $5M line between
first sight and settlement, and all six in the same direction** — refused on the provisional number,
admitted on the settled one. Small, but strictly one-way, on the population every study runs on.

## 2. When volume actually settles — and the number this record first got wrong

**CORRECTION, and it is mine.** The first measurement of this reported *"volume settles completely
within 8 calendar days"*. That is not wrong as arithmetic, and it is the wrong unit:
`AGENTS.md` §3 makes sessions the unit of every duration in this system, and eight calendar days is
a different quantity every week. Re-measured in sessions, the answer is **much tighter and much
easier to justify**.

Revisions by the bar's age **in sessions** at the moment it was re-fetched, over the daily-run era
(2026-08-10 onward, one observation per session), 5,980 revisions:

| Age at re-fetch | Revisions | Share |
|---|---|---|
| 0 sessions | 1,013 | 16.9% |
| 1 session | 4,788 | 80.1% |
| **2 sessions** | **179** | **3.0%** |
| 3+ sessions | **0** | — |

**No bar three or more sessions old has ever been revised in this regime.**

### 2.1 The trap in this measurement, and why the era matters

Across the *whole* store the tail runs to 5 sessions — 802 revisions at 4 and 317 at 5. Every one of
them comes from a single capture, **2026-08-09**, the first scheduled run, which re-observed bars
first seen during the 08-02/08-03 bootstrap.

**Age-at-re-fetch is not settlement age.** If nothing looks at a bar for five sessions, a revision
the vendor made when the bar was one session old is recorded as a five-session-old revision. The
bootstrap gap manufactures exactly that. Only a regime that observes every session can separate the
two, which is why the table above is restricted to one — and why a future observation gap will
re-create the artefact rather than reveal a longer settlement.

## 3. Decision proposed

**`universe.adtv_lag_sessions = 3`**, provenance `assumed:DR-017`. The 20-day ADTV window ends three
sessions before the run rather than at the last completed session, so every bar it averages is one
the vendor has never been observed to revise.

Three, not two: two is the oldest age at which a revision was *seen*, so a window ending two
sessions back still includes a bar that was revised. Three is the first age with a measured zero.

**The direction was council-reviewed on 2026-08-18** (5 advisors + peer review). Unanimous against
treating the drift as noise, and unanimous against widening the $5M threshold to absorb it — the
latter dies at this project's own provenance gate, since a fudge factor has no course citation.
Direction chosen 4–1, and **the argument that carried it was reproducibility, not bias**: a lagged
window makes admission **idempotent**, so a replayed screen returns the number the live screen
returned. Today it cannot, because the bars underneath it keep changing.

**Reproducibility is the ONLY argument for this lag, and that is now measured rather than assumed.**
It would be natural to defend the lag as protecting the owner from an unfillable position. It does
not, and the claim would not survive contact with the numbers: measured over the 2026-08-17 run's
1,148 sized candidates, the largest position the sizing rule produces is **0.046% of one session's
dollar volume** against a conventional 10%-of-ADV execution limit — more than two hundred times
inside it, and the screen would only begin to bind at roughly a **$2.2M** account. `DR-003`'s
addendum carries the full table. So the lag buys an idempotent screen and nothing else, which is
enough on its own and is the only thing this record claims for it.

**One universe and one lag for live admission and for studies.** Two universes is the failure mode
this would otherwise create, and it is worse than the defect being fixed.

### 3.1 The parameter is not in the registry yet, and that is not an oversight

> **Overtaken 2026-08-30 by ratification.** The id is now in `registry/parameters.yml` and carries
> `provenance: owner`, not the `assumed:DR-017` this section expected. The rest of the section still
> stands — in particular the `named_in` argument, which is the part the owner had to weigh, and which
> the registry entry restates rather than hides. §7.1 has the reasoning. Left as written and
> corrected forward rather than rewritten, per `AGENTS.md` §11 rule 2.


Gate 3e refuses a document that cites a parameter id the registry does not hold, and it refused this
record's index row until the id was taken out of it. The id enters `registry/parameters.yml` **when
this record is ratified**, carrying `assumed:DR-017`.

**The reason to say so out loud is `AGENTS.md` §7**: every parameter needs `named_in` citing where
the course mentions the concept, and *the course does not mention a settlement lag*. It names dollar
volume as the liquidity measure (M33-T0481, Appendix A) and says nothing about which vintage of
volume to read. So on the strictest reading this is **invented scope** — the category §7 exists to
reject.

The defence, and the owner should weigh it rather than take it: the lag is not a new threshold about
the market. It is a correction to *how a course-named quantity is computed*, in the same class as
using the calendar rather than calendar days. `named_in` would therefore cite the ADTV source it
modifies. If that reads as a stretch, the alternative is to hard-code the lag as a constant beside
the universe builder with this record as its provenance — no registry entry, no `named_in` claim,
and the number still has one written reason.

## 4. What this costs

**Three sessions of staleness in the liquidity estimate.** An instrument whose volume collapses is
admitted for three more sessions than it would have been; one whose volume spikes waits three
sessions. Against a 20-session window that is a 15% shift in the averaging period, and the threshold
sits on a measured plateau — `DR-003` records that membership moves by 2 instruments in 115 between
$5M and $10M — so the admitted set is not sensitive at the margin the lag moves it.

**Cutover churn is a one-off and should be logged, not smoothed.** The first lagged run will admit
and refuse a different set than the last unlagged one, and that difference is a fact about the fix
rather than about the market.

## 5. What this does NOT decide

**Is backfilled volume executable?** The council's sharpest question and this record does not answer
it. The fill-in is overwhelmingly upward. If it is late off-exchange prints, then settled ADTV
**overstates the very liquidity $5M is a proxy for**, and lagging optimises toward a number that is
more reproducible and no more true. That is a separate measurement — the venue mix of the delta —
and it needs a source this project does not currently have.

**Whether `universe.min_adtv_20d = $5M` is the right threshold at all — and whether a dollar
threshold is the right SHAPE.** It is `assumed:DR-003`, never swept, and a $3M–$8M sweep would test
it while also answering whether the six crossers are noise. Ruling this record does not make that
less needed.

But the sweep tests a level, and the form underneath it is also unvalidated. Index providers do not
screen on absolute dollar volume; they screen on turnover relative to size — S&P's **Float-Adjusted
Liquidity Ratio** (annual dollar value traded ÷ float-adjusted market cap, ≥ 0.75) and MSCI's
**ATVR** (annualised traded value ÷ free-float market cap, 20% for developed markets). $5M a day is
heavy turnover for a $200M company and a rounding error for a $200B one, and the ratio is what
separates them. `DR-003`'s 2026-08-18 addendum records this, along with the constraint that makes it
hard here: a ratio needs point-in-time float-adjusted market capitalisation, which this project has
no free source for.

## 6. What would overturn this

An observation regime with no gaps that still shows revisions at 3+ sessions. The table in §2 is
eight sessions of daily observation; it is enough to place the cliff and not enough to call it
permanent. The check is cheap and should be re-run after a quarter of scheduled evenings — the same
query, the same buckets, against a longer store.

## 7. What was built, 2026-08-30

Ratified and implemented in the same change, merged with `DR-023` as one Track A counter reset —
`STREAK_RESTARTS` carries the row and `DR-015` §3 carries the argument for merging.

**`LiquidityRule` gained `adtv_lag`, and `admits` measures ADTV over the window ending that many
sessions before the bar it is judging.** `rule_from_registry` reads
`universe.adtv_lag_sessions`; `application.universe.select` widens the tail it pulls from the store
to `adtv_window + adtv_lag`, because a twenty-bar tail cannot carry a twenty-bar window that stops
three bars early — without that, the fail-closed branch would have refused *every* instrument in
the universe.

### 7.1 The provenance is `owner`, and §3.1 said it would be `assumed:DR-017`

§3.1 was written while this record was proposed, and it assumed ratification would leave the value
where a decision record leaves one: `assumed:DR-017`, per the decision-record README's rule 5. The
owner ratified the value directly on 2026-08-30, which is a different act and a stronger claim —
the same distinction `DR-003` drew when the owner ratified `universe.min_adtv_20d` on 2026-08-23
and left the other two `assumed`, and the one `DR-006` set the precedent for.

**It is not cosmetic.** `is_assumed` drives the daily report's *"ASSUMED, not evidence"* flag, so
the two provenances put different words next to the number in front of the owner. A value the owner
ruled on should not be shown back to them as an assumption this project made.

`README.md` rule 5 — *"`assumed` is where a DR leaves a parameter — never `validated`"* — is not
contradicted: `owner` is not `validated`, no study has measured the lag, and nothing here claims
evidence. The rule exists to stop a considered guess acquiring the authority of a measurement, and
an owner ruling does not acquire that either.

### 7.2 The lag moves the ADTV window and NOT the price test

§3 says "the 20-day ADTV window ends three sessions before the run" and says nothing about the
close. Building it made the question unavoidable, because `admits` tests both at one index.

**The close is read at the run; only ADTV is lagged.** §1's own measurement is the argument: closes
move by 0.02% at p90 where volume moves 32%, so lagging the price buys no reproducibility worth
having — and `universe.min_price` is a claim about what an instrument costs to trade *now*. An
instrument whose price collapsed yesterday should be refused today, not in three sessions.
Widening the lag to the price test would be a second decision, and nobody has taken it.

### 7.3 The parameter has no default, in code as well as in the registry

`rule_from_registry` refuses when the lag is unset, exactly as it does for the other three
thresholds. `LiquidityRule.adtv_lag` has no default value either, so the seventeen study,
measurement and test call sites that construct a rule directly each had to state one.

**Both possible defaults are wrong, which is why there is none.** A default of `0` hands a caller
that has never heard of this record the old, non-reproducible universe. A default of `3` silently
rewrites what an already-reported study ran under. §3's "one universe and one lag" is enforced by
making every caller name the lag it means, not by picking one for them.

Every study and measurement tool that predates this record pins `adtv_lag=0` — that is the rule it
actually ran under, and pinning it is what `LiquidityRule`'s own docstring says the record is for.
**Re-running those studies under the lag is not decided here**, and would be a change to what their
evidence records describe.

### 7.4 A negative lag raises

It would end the window *after* the run — lookahead, in the one direction that makes a screen look
better rather than worse, and therefore the direction least likely to be noticed downstream.
`__post_init__` refuses it.
