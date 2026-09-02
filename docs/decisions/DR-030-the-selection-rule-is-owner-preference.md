# DR-030: The backtest route to CARD-001's selection rule is closed, so the four values are the owner's preference and the card ships `Untested`

```
date:            2026-09-01
status:          accepted — ruled by the owner 2026-09-01, after an LLM council and a verification
                 pass that found the council's favoured design had already been run and reported
parameters:      rs.benchmark_form, rs.lookback, rs.ranking_method, screen.relative_strength_rule
                 — all four provenance `owner`, status `owner`, NEVER `validated:`
components:      activates M31-T0465-v5.0 and M33-T0487-v5.0 for CARD-001
implemented_by:  src/swingdesk/application/pipeline.py :: def _select
built:           2026-09-01
```

## 1. Why a decision record, when `ALLOCATION_SPEC` §3 says an ordering needs a study

**Because the studies were run, and the route is closed.** §3's requirement is not waived here; it is
discharged, in the only way an unfalsifiable-by-backtest question can be.

| | |
|---|---|
| `PR-012` | **REFUSED**. The book holds 4 positions for 20 sessions, so the per-trade sample has a structural ceiling of ~50 entries a year. 9.5 years of history did not reach its own floor. |
| `PR-013` | **INCONCLUSIVE**, and stronger than that in its own words: the per-DATE cross-sectional spread, three arms, 142 formation dates against a registered minimum of 100 — **all six gross intervals include zero, in both periods, before a single basis point of cost.** |

`PR-013` matters most, because it is exactly the redesign an LLM council reached for on 2026-09-01
when asked how to make the next study succeed. Four of five advisors proposed changing the statistic
to a per-date spread with a sample rule stated in dates. **That study exists and is reported.** Its
own report anticipated the next drafter: *"comparing two losers on which loses less is not a
finding."*

**And no backtest could have finished the job anyway.** `criteria.yml`'s `b.min_sample` is
`measured_by: journal, per strategy and version` — 100 **closed journalled trades**, ratified. A
backtest cannot move `CARD-001` off `Untested` by construction, whatever it measures. The council
spent its whole budget arguing about how to earn `validated:` for a card whose own registry says it
can never have it that way.

### 1.1 The project's own worked precedent, which prescribes this exact mechanism

`screen.trend_definition` is a family this project already closed — `PR-001` and `PR-005` both
refuted — and its registry note says what happens next:

> *"If a value is ever set here it is set by OWNER PREFERENCE with that recorded — provenance
> `owner`, never `validated:` — unless a study with a different trigger or exit model separates
> them, which would be a new question that does not inherit these results."*

That is this record's shape, applied to a second closed family. **The note was invisible to every
tool when the council cited it**: `parameters.yml` carried two `note:` keys on that parameter and
YAML kept the last. Gate 40 now refuses a duplicate key, and both notes are folded.

## 2. The decision

**Four values, `provenance: owner`, and every ground below is STRUCTURAL or from the literature —
never "this arm scored best".** An outcome-chosen value would be `PR-013`'s null re-entering through
the door marked preference, which is the snooping this record exists not to do.

### 2.1 `rs.benchmark_form` = `path` — share of the lookback's sessions the name beat the benchmark

**Because the alternative is measured to be a lie about the card's own name.** Measured 2026-08-24:
the usual point-to-point form `(1+own)/(1+benchmark)` is a strictly monotone transform of the name's
own return on any single cross-section — the benchmark's return is one constant for every name that
day — so it ranks **exactly** as raw return does, **Spearman 1.000000** across 15 benchmark ×
lookback pairs over 1,148 names.

A card called *cross-sectional relative strength* whose ordering is arithmetically identical to plain
momentum would be the thing every gate in this repository exists to catch. The path form reads about
0.6 against raw return and is a genuinely different signal.

**Not chosen because `PR-013`'s MARKET arm read marginally best.** It read no better than the
control, and that is in §1's table.

### 2.2 `rs.lookback` = 126 sessions

**Because changing it changes the universe rule.** `PR-012` §4 defines the study window as *"the
first session on which at least 200 admitted names have a full 126-session lookback"*, and `PR-013`
inherited it. The number is load-bearing in the admission machinery, not only in the ranking.

It is also inside Jegadeesh & Titman (1993)'s 3–12 month **formation** band, which is the half of
that literature this project's 20-session hold does not contradict — the hold is the part that sits
in the reversal window, and `DR-012` owns it.

### 2.3 `rs.ranking_method` = descending rank across the admitted cross-section on the decision date

The only method both prior studies operationalised, with `ALLOCATION_SPEC` §6's stable tiebreak on
`instrument_id` — a total order is mandatory or a re-run is not a re-run (`DETERMINISM_SPEC` §3.2).
A name that cannot be scored sorts to the **bottom** rather than being dropped: it competes and
loses, which is a different and honest claim from disappearing.

### 2.4 `screen.relative_strength_rule` = top decile of the admitted cross-section

The cutoff both studies used. At ~1,100 admitted names the top decile is ~110, and the 4-slot book
(`risk.max_concurrent_positions`) binds **long** before the cutoff does — so this value picks which
names are eligible, and the ratified caps pick which are taken.

## 3. What ships, and what it is not

**`CARD-001` selects, and stays `Untested`.** `validation_status` does not move, `evidence` stays
null, and gate 27 keeps both honest. Every number the card produces carries `owner` provenance and
the report prints it, which is `CHARTER.md` §5 rule 2 working rather than being bypassed.

**Paper only, and that is already enforced elsewhere.** `DR-014` rules no owner capital; `CHARTER`
A-002 permits submission on a venue holding none; the host allowlist and gate 39 are what keep the
two apart.

**The clock this starts is the only one that can validate anything.** `b.min_sample` = 100 closed
journalled trades, ratified, journal-measured. At the book's ~50 entries a year that is about two
years — and it is the sole route to `Validated` that this project's own criteria admit.

### 3.1 The expectation, registered here, before the clock starts

**`CARD-001` v1 is expected NOT to clear `b.expectancy`.** Its ordering has no measured separation
at the ratified hold: `PR-013`'s six intervals all include zero gross, and the horizon measurement
puts this family's effect at 3–12 month holds while `exit.max_holding_period` is 20 sessions.

Writing that down **in advance** is what turns a future null from an embarrassment into a
pre-registered result. `criteria.yml`'s `k.card_rejected` already carries the branch — *"After
b.min_sample, the expectancy CI lies entirely below the benchmark → set validation status Rejected,
retire the card, the project continues"* — so nothing new is ratified by this record.

### 3.2 The objection that was put to the owner, and answered

**`unset` is currently fail-closed: zero recommendations, therefore zero bad ones.** Setting these
four values starts emitting trade recommendations backed by *provenance*, not evidence.

The owner ruled to proceed on 2026-09-01. What makes it defensible rather than merely permitted:
no capital is at risk (`DR-014`), the status stays `Untested` on every surface, the expectation of
failure is registered above, and the alternative — a card that selects nothing for ever — produces
no journalled trades and therefore forecloses the only validation route the criteria allow.

## 4. What would overturn this

- **A study with a different trigger or exit model that separates the arms.** `screen.trend_definition`'s
  note names this escape and it applies here unchanged: that would be a new question which does not
  inherit `PR-012`'s or `PR-013`'s results. The three levers `DR-029` §5 lists — a tighter stop, a
  longer hold, selection — are where such a study would come from.
- **The journal.** 100 closed trades and `k.card_rejected` fires or does not. That is the point of
  shipping.
- **Any of these four values being re-tuned.** `cards.yml` rule 2: changing any field creates a new
  card version and **resets the validation claim**, so every re-tune costs another two-year clock.
  That is the strongest argument against treating these as adjustable, and it is why they are ruled
  rather than searched.
