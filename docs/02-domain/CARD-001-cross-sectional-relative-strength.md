# CARD-001 — Cross-sectional relative strength

**Status:** drafting · **Tier:** 2 (domain) · **Card version:** 1 · **Family selected by the
owner:** 2026-08-24

**The CARD's validation status is `Untested`** — a different field from this document's, and §2 is
why it cannot move without journalled trades.

The machine-readable card is [`registry/cards.yml`](../../registry/cards.yml); this document is its
reasoning. The split is the one `components.yml` and `COMPONENT_REGISTRY_SPEC.md` already use, and
[`tools/verify_cards.py`](../../tools/verify_cards.py) (gate 27) checks that every reference here
resolves.

**This is the first strategy card this project has ever had.** `ROADMAP.md` P5 named it load-bearing
on 2026-08-02 and `STRATEGY_CARD_SPEC.md` has described its shape since — there was no card.

---

## 1. What it trades, in one paragraph

Rank the admitted universe by strength relative to its index over a lookback, and hold the strongest
few. **It selects; it does not time.** There is no price trigger, and that is a property of the
family rather than a missing field: a cross-sectional rule asks *which of these* rather than *is this
one ready yet*.

It was chosen because it is a **different family** from the one `PR-005` refuted. That study, every
trade log, and the whole cost-model calibration describe long-only time-series breakout with a regime
filter. Declaring a second card in that family would spend the first slot on a known answer.

## 2. Why it is `Untested`, and why it must stay that way

**The course flags this hypothesis itself.** `M31-T0465` — *"Long strongest / short weakest"* —
carries `claim_type: Untested Hypothesis` in the course's own taxonomy, and that is the entire
content of the topic. `ALLOCATION_SPEC.md` §3 draws the consequence and it governs this card:

> An ordering adopted from the course is not a transcription and does not inherit the course's
> authority: it is a hypothesis the course itself flags, so it needs a pre-registration before it
> selects a trade, not a decision record.

So the selection rule's three inputs — `rs.lookback`, `rs.ranking_method`,
`screen.relative_strength_rule` — get values from a **study**, never from a decision record. All
three are `unset`, so the card refuses. **That is the design working, not a defect** (`AGENTS.md`
§12): a component with an unset parameter refuses rather than defaulting, and a ranking that fell
back to whatever order the system happened to have would be an alphabetical bias silently applied
(`ALLOCATION_SPEC.md` §4, choice 1).

`criteria.yml` v1.1.0 adds the other half: **Track B evaluates on journalled trades only.** A
backtest is evidence about a hypothesis, never about a card. So nothing short of live paper
journalling can move this card past `Untested`, whatever a study says.

## 3. What this card revealed by existing — and it is the argument for P5

A card's first job is to convert *"what should we build?"* into a list somebody can close. This one
did that immediately, and one of the four items was not previously written down anywhere.

### 3a. The backtest has no portfolio, and this family is a portfolio rule

**Measured 2026-08-24, by search and by the code graph:** nothing in `src/swingdesk/validation/`
references `portfolio`, `risk.max_concurrent_positions` or `risk.max_open_risk`. `run_arm` walks
**one instrument** with unlimited capital, and the study runners loop it per instrument and merge the
results.

*"Hold the strongest N of the universe at once"* is a **portfolio construction rule.** A
per-instrument engine would enter every name that was ever ranked inside the cutoff, independently
and without a cap — which measures a different strategy from the one this card declares.
`tools/measure_sector_cap.py` already records the symptom from the other side: `PR-005`'s base slice
held a **median of 20 positions at once, maximum 54**, on a book whose ratified cap is **4**.

**The 2026-08-24 `EntryTrigger` seam did not reach this.** That change made the entry *rule*
injectable and left the engine single-instrument. Worth stating plainly because the two look alike
from a distance.

**BUILT the same day: `validation/backtest/book.py`.** `run_book` walks a **session** axis rather
than an instrument's bars, asks every instrument what it wants on each session, and lets the
survivors compete for a bounded number of slots. Four properties are pinned by tests that provably
fail without them: `deferred` is a separate outcome from `Skip` (`ALLOCATION_SPEC` §5), a slot freed
by today's exit is available to today's candidates (`CHECKLIST_SPEC` §4), the ranking is **injected**
with no default, and `risk.max_open_risk` binds independently of the position count. A one-name book
with capacity to spare reproduces `run_arm`'s trades exactly, which is what makes the two engines
answer the same question when they should.

**What remains is that no study runner calls it.** The engine can express this card's family; nothing
has run it, because running it needs the ranking rule, which needs a pre-registration.

### 3b. There was no index to be strong relative to — and the fix found something worse

`M31-T0464` measures strength **against the index**. No index series was stored: the bar store holds
instruments from the NASDAQ Trader directory, and the proxies were absent only because coverage is
an **alphabetical prefix** that had not reached the letter S. Fetched 2026-08-24 — `SPY`, `QQQ`,
`IWM`, `IVV`, `VOO`, five years each — and settled in [`DR-018`](../decisions/DR-018-relative-strength-benchmark.md).

**The measurement that record ran changed the question.** On a single cross-section the usual
point-to-point relative strength, `(1 + own) / (1 + benchmark)`, is a **strictly monotone transform
of the name's own return** — the benchmark's return is one constant for every name that day, so
dividing by it reorders nothing. Measured as a control that must return exactly 1: **15 of 15**
benchmark × lookback pairs give ρ = **1.000000** against a ranking on raw return alone, over 1,148
names.

**So point-to-point relative strength is momentum with a decorative denominator**, and a card
declaring it would be declaring the family it was chosen to avoid.

A **path-dependent** form escapes the identity — share of sessions the name beat the benchmark reads
ρ ≈ 0.6 against raw return, a genuinely different signal — and there the index choice bites: SPY
against QQQ at **0.616** on 63 sessions, while SPY against IVV (same index, different fund) reads
**0.973**. **The index is the decision; the proxy is not.**

`rs.benchmark` is therefore `SPY` and `rs.benchmark_form` is **`unset`**, because the form decides
what this card actually trades and `ALLOCATION_SPEC.md` §3 sends that to a pre-registration.

### 3c. G6 has a denominator for the first time

`ROADMAP.md` §3 defines G6 as *"every component a live strategy card needs is `active`"*.
**Demand-driven coverage has no meaning without a card to create the demand**, and until now there
was none — which is why *"1 of 465 components active"* has been quoted as a gap it never was
(`plans/2026-08-24-from-machinery-to-evidence.md` §0, correction 2).

This card needs **four** components, and gate 27 prints how many are `active`:

| component | what it supplies | activation |
|---|---|---|
| `M31-T0464-v5.0` | relative strength against the index — the measure | **`active`** (2026-08-30, `DR-024`) |
| `M31-T0465-v5.0` | long strongest / short weakest — the hypothesis | `registered` |
| `M33-T0487-v5.0` | the relative-strength screen | `registered` |
| `M77-T1138-v4.0` | relative strength at the setup stage | `registered` |

Four is the denominator. It was never 465. **One of the four is `active`**: the daily run computes
the RS line for every candidate and the report prints it with its validation status, which is the
condition `COMPONENT_REGISTRY_SPEC.md` §3 attaches to that state.

**The measure being active does not make the card runnable, and the distinction is the whole point.**
`M31-T0464` answers *how strong is this name against the index*; the three that remain are the
*hypothesis*, the *screen* and the setup-stage reading — the ones that would turn the number into a
selection. Those wait on `rs.benchmark_form`, `rs.lookback`, `rs.ranking_method` and
`screen.relative_strength_rule`, all unset and all bound for a pre-registration under
`ALLOCATION_SPEC.md` §3. The report says so on every candidate, in as many words: *selects nothing*.

## 4. What the card inherits rather than authors

Deliberately almost everything, because a card that re-derived the machinery would be a second
implementation of it (`STRATEGY_CARD_SPEC.md` §5 rule 1).

| | from | standing |
|---|---|---|
| universe | `DR-003` | **ratified** 2026-08-23 — `min_adtv_20d` is `owner`, the other two `assumed` |
| stop, time exit | `DR-012` | ratified |
| portfolio caps | `DR-006` | **fully ratified** 2026-08-23 |
| freshness | `DR-015` | built |
| splits, revisions | `DR-016` | split guard built; revision comparison built, fault not surfaced |
| costs | `DR-005`, `DR-010` | slippage measured, commission assumed |
| trial accounting | `TRIAL_BUDGET.md` | owner-pending |

**Only the selection rule is this card's own**, and it is exactly the part that is `unset`.

## 5. The conditions, and the one that cannot be outvoted

`STRATEGY_CARD_SPEC.md` §2's three kinds, verbatim in effect: required must hold, confirming may be
absent, **prohibiting is non-compensatory** and can never be outvoted by any number of confirming
conditions.

- **Required** — admitted by the liquidity rule on the decision date; ranked inside the cutoff on
  the decision date; a stop can be placed below the entry.
- **Confirming** — none. Authoring a confirming condition would be authoring a rule, and §8 of
  `AGENTS.md` says that needs a pre-registration. An empty list is the honest state.
- **Prohibiting** — a stale series; a split effective after the stop was set; any `DR-006` cap that
  the candidate would breach.

## 6. What would retire this card

- The selection rule's pre-registration reports **refuted** — then the family is closed the way
  trend definitions were by `PR-001` and `PR-005`, and this card is `Retired`, not edited.
- `k.programme_exhausted` or `k.strategy_rejected` fires.
- `b.deflated_sharpe` cannot be cleared at the cumulative trial count. `TRIAL_BUDGET.md` owns that
  figure and it is derived, never quoted: `python tools/trial_budget.py`.

**A retired card is superseded, never deleted** (`AGENTS.md` §11 rule 2). A version-1 card that was
refuted is the record of what was tried, and it is the thing a future session needs most.

## 7. What this card does not claim

It does not claim an edge exists. `EVIDENCE_SUMMARY.md` §1 is the standing counterweight: the base
strategy is negative at measured costs across the whole admissible universe, and this card is on the
same data at the same tier.

It does not change `DR-014`: **no owner capital, paper only.**

And it does not claim to be runnable. Four blockers are declared in `registry/cards.yml`, gate 27
requires that a card citing an unset input declares them, and the first two — no portfolio in the
backtest, no index series — are engineering that nobody had scheduled because nothing had asked for
it.
