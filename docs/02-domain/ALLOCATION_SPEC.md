# ALLOCATION SPEC — ranking when candidates exceed capacity

**Status:** drafting · **Tier:** 2 (domain) · **Content:** authored, audited against the tree

Master ТЗ v1.0 §31. The gap analysis ranks it second of the remaining five and dates its urgency:
*needed the moment candidates exceed capital. With 1,133 universe members that day is close.*

**The one sentence this document exists to protect** is already in the code, in
`application/universe.py`:

> the rule says who is admissible; a cap says who we had time for, and the two must never be
> confused.

Everything below is that distinction, applied to capital instead of fetch budget.

---

## 1. Admissibility and preference are different questions

| | Admissibility | Preference |
|---|---|---|
| Question | may this be traded at all? | of those that may, which first? |
| Machinery | gates and vetoes (`RULE_SPEC.md` §5) | a ranking |
| Compensable? | **never** — no score clears a critical gate | that is what a ranking is |
| Failure if confused | a good score trades something inadmissible | an arbitrary order presented as a judgement |
| Wrong answer costs | a rule violation | a missed opportunity |

**A ranking never runs before the gates and never re-admits what they rejected.** Ordering is applied
to the surviving set only. This is `FAIL_CLOSED_POLICY.md` §3 restated at portfolio level, and it is
the reason allocation is a separate document from the screener rather than a step inside it.

## 2. What binds first is open risk, not cash

Worth stating early because it inverts the intuition. Sizing here is risk-based: equity × risk% gives
an allowed risk in dollars, and shares follow from the stop distance (`RISK_SPEC.md` §1). A candidate
therefore consumes **R**, not a fixed slice of the account.

So "candidates exceed capital" almost never means the cash ran out. It means one of these did:

| Constraint | Parameter | Value | Evaluable? |
|---|---|---|---|
| total open risk across positions | `risk.max_open_risk` | 4R | yes — **enforced** |
| how many positions can be managed at once | `risk.max_concurrent_positions` | 4 | yes — **enforced** |
| one position's share of the account | `risk.max_position_value` | 2500 | yes |
| order size against liquidity | `risk.liquidity_cap_order_to_adtv_pct` | 1.0% | yes |
| risk concentrated in one sector or theme | `risk.max_sector_risk` | 2R | **no** — no sector source |
| duplicate economic exposure | `risk.correlation_threshold` | 0.70 over 60 sessions | yes — **enforced** |

**All six were `unset` when this document was written.** `DR-006-portfolio-risk-block.md` proposed
values for them on 2026-08-08 (`assumed:DR-006`, awaiting ratification), and that record's §3 carries
the evaluability column above.

**Updated 2026-08-22.** The owner ratified four of the six with provenance `owner` (`DR-006` §8.3),
and the first two moved: the anchor is **4R and 4 positions**, not 6R and 6. The trade log this
project did not have when §1 of that record was written says a gap exit loses −1.692R rather than
1R, so a whole-book gap session costs 10.15R and the −15R drawdown pause is 1.5 sessions away, not
the two and a half §1 designed for. Four restores the intent. The two rows still marked **no** are
`assumed` and unratified; `DR-006` §8.4 shows both are buildable and neither is built.

**Updated 2026-08-23: the correlation row moved to enforced.** A candidate whose daily returns
correlate at or above `risk.correlation_threshold` with any OPEN position leaves with `Skip` / `RISK`
(`DR-006` §11). The window it is measured over is now its own parameter,
`risk.correlation_lookback_sessions` = 60 — it had been prose inside the threshold's registry note,
where nothing could read it. **The value stays `assumed` and unratified**: §8.4's condition was that
the owner rules on numbers whose checks actually run, and building the check is what makes that
ruling possible, not a substitute for it. `risk.max_sector_risk` is the one row still marked **no**,
and the ETF-look-through degeneracy guard §8.7 names is a precondition of moving it.

Two things follow, and they are different:

- **Four are now computable**, so the capacity arithmetic this document specifies has inputs.
- **Two are set and cannot be checked.** Those must report `unavailable` — not pass, and *not* fail
  closed into a blanket refusal. A sector check that refused every candidate for want of sector data
  would halt the system while looking like risk discipline. Fail-closed governs a decision made on
  *degraded* data; it does not govern a check the system was never able to perform, and conflating
  those is the error `HANDOFF.md` §7 calls the most damaging this product can make.

None of this enables trading. `risk.per_trade_pct` stays `unset` by course instruction
(`RISK_SPEC.md` §4 — *`Риск % задаётся личным планом`*), so `size_long` still returns a coded
refusal and the allocation path has nothing to allocate.

`CODES.md` already reserves the outcome — `RISK`: *open/sector/currency/event limit exceeded*, action
*Skip or choose better candidate*. The skip code for a candidate that lost the allocation exists;
the arithmetic that would raise it does not.

**Half of that last sentence stopped being true on 2026-08-22, and the half that remains is the
point of §7.** The arithmetic for the two ADMISSIBILITY caps exists —
`trade_management/portfolio.py`, read at step 6 of `RISK_SPEC.md` §3 — and a candidate that would
push the book past either leaves with `Skip` / `RISK`. What still does not exist is the RANKING:
choosing which of several admissible candidates takes the last slot. Those are the two questions §1
insists on keeping apart, and this is what it looks like to have answered one of them.

## 3. What the course supplies

Four topics, and the **claim types are the finding** — taken from `registry/course_index.yml`, not
from reading around:

| Topic | Title | Claim type | Parameter |
|---|---|---|---|
| `M32-T0477` | Приоритизация сетапов | **Untested Hypothesis** | — |
| `M31-T0465` | Long strongest / short weakest | **Untested Hypothesis** | `rs.ranking_method` |
| `M32-T0476` | Удаление слабых кандидатов | Inference | `watchlist.eviction_rule` |
| `M32-T0474` | Размер watchlist | Definition | `watchlist.max_size` |

Appendix T adds the only quantified-*shaped* statement — *Daily Priority 1 ограничен*, a bounded
daily priority list (`watchlist.daily_priority_limit`, unset).

**The course's only two statements about how to order candidates are both labelled `Untested
Hypothesis` by the course's own taxonomy**, and one of them — *long the strongest, short the
weakest* — is the entire content of its topic. Roughly 3% of the catalogue carries that label
(`COMPONENT_REGISTRY_SPEC.md` §5), so its appearance on both of the topics that matter here is not
noise.

That sets the standard of evidence. An ordering adopted from the course is not a transcription and
does not inherit the course's authority: it is a hypothesis the course itself flags, so it needs a
pre-registration before it selects a trade, not a decision record (`AGENTS.md` §8). Relative strength
in particular is the kind of claim that is cheap to believe and has a large published literature on
both sides.

## 4. The precedent already in the tree

The universe cap is this project's only existing ranking, and it is worth copying rather than
re-deriving. `swingdesk scan --limit` truncates the admissible universe, and the implementation makes
four choices that generalise:

1. **Members are ordered by id, not by liquidity.** An unordered collection feeding a run is the
   classic source of silent non-determinism, and ordering by a *measure* would quietly turn a
   membership rule into a ranking the first time anyone truncated the list.
2. **Truncation is done explicitly, by a named measure**, dollar volume descending — not by whatever
   order the rows happened to be in.
3. **The count before truncation is recorded** as `capped_from`, so a report can say "40 of 1,133"
   rather than "40".
4. **The result is re-sorted to the stable key afterwards**, so the output order does not leak the
   ranking into everything downstream.

Choice 1 has a trap behind it that allocation must not walk into: **truncating an id-sorted list
without ranking it is an alphabetical bias, silently applied.** It selects `AAPL` over `ZTS` for no
reason anybody chose, and it looks exactly like a list.

## 5. The allocation record

When candidates exceed capacity, the run must record what it did, not just what survived. A candidate
that lost an allocation is not a candidate that failed a filter, and the journal must be able to tell
them apart afterwards (`TRANSITION_SPEC.md` §2 — losing an allocation changes what a later run may
assume).

```yaml
- allocation_id: alloc-2026-08-08-001
  run_id: run-20260808T210000Z-...
  as_of: 2026-08-08

  admissible: 14                 # candidates that passed every gate
  capacity:
    binding_constraint: risk.max_open_risk
    available: "3.0R"            # what remained after open positions
    requested: "14.0R"           # what the admissible set would have consumed

  ranking:
    method: null                 # UNSET - rs.ranking_method has no value
    measure: null
    tie_break: instrument_id      # total order, always
    version: null

  allocated: []                  # ids, in ranked order
  deferred: []                   # admissible, ranked below the line - NOT skipped
  skip_code: RISK                # for those that leave the run without an allocation
```

**`deferred` is a separate outcome from `Skip`.** A candidate that was admissible and lost on capacity
should return tomorrow at the top of the list; a candidate that failed a gate should not. Collapsing
them loses the difference, and `DECISION_STATE_MACHINE.md` §3's watchlist already has the states to
express it.

## 6. Rules

1. **Gates first, always.** Rank only what survived. A ranking that can promote a rejected candidate
   is not a ranking, it is a compensation scheme.
2. **A ranking is a total order with a deterministic tie-break.** Two runs on identical inputs select
   the identical set — `a.reproducible` is a ratified criterion and a ranking is the easiest place to
   break it. The tie-break is a stable key (instrument id), never insertion order.
3. **The ranking method is versioned and recorded**, like any other rule. Changing it changes which
   trades were taken, so a result computed under one ordering is not comparable to a result computed
   under another.
4. **An unset ranking method refuses.** It does not fall back to id order, to the screener's output
   order, or to whatever `sorted()` happens to give. §4's trap is the reason this is spelled out.
5. **An expectation may inform preference and never admissibility** (`EXPECTATION_MODEL.md` §7). This
   is the one place an estimate is legitimately allowed to influence a decision, and its influence
   stops at the ordering of an already-admissible set.
6. **Capacity is recomputed from open positions before ranking**, not carried from the last run. Open
   risk moves when a stop moves, and `Position.open_risk` is a property rather than a stored field for
   exactly this reason.
7. **Every candidate leaves with a next action**, allocated or deferred or skipped, with a code. The
   course's own operational standard: *нет кандидатов без следующего действия*.

## 7. What this cannot do yet, stated plainly

- **No sector data.** `Instrument.sector` and `.industry` are `None`, and no free point-in-time
  sector source is in hand (`application/checklist.py` E13 reports it). So `risk.max_sector_risk`
  cannot be evaluated even once it has a value.
- **No correlation input.** `risk.correlation_threshold` needs a correlation matrix over the
  candidate set; nothing computes one.
- **No live positions to consume capacity.** The position store exists and is empty, so today's
  available capacity is trivially the whole budget.
- **No strategy to generate the pressure.** The live path reaches `"sized; awaiting a trigger"`, so
  the run produces at most one candidate per instrument and never competes for capital.

**Correction, 2026-08-22: the first two bullets overstate the blockage, and `DR-006` §8.4 measured
it.** Correlation is not blocked at all — the full 1152 × 1152 matrix over 60 sessions of daily
returns builds from the existing store in 0.09 s, so "nothing computes one" is a statement about
missing CODE, not missing data. Sector has a free source for live admission (`yfinance` returns it
directly, with an ETF look-through), and the vendor fabricates that look-through for bond funds, so a
degeneracy guard is a precondition rather than a refinement (§8.7). What is genuinely missing is only
the **point-in-time** sector, which restricts a backtest and not live admission. The bullets are kept
as written because they are what was believed; neither is a reason the two caps stay unratified.

**And the correlation bullet is now closed, 2026-08-23.** `derived_observations/correlation.py`
computes it and `trade_management/portfolio.py` spends it, so *"nothing computes one"* is no longer
true of this tree. Note what it is not: the matrix is never built. A candidate is correlated against
the OPEN BOOK — at most `risk.max_concurrent_positions` comparisons, not 662,976 — because the pair
that matters is candidate-to-held, and candidate-to-candidate is a ranking (§6 rule 4). The sector
bullet stands.

**Allocation is therefore specified ahead of its first use, deliberately** — the same reason the
intrabar policy in `EXECUTION_MODEL.md` §4 was written before a target existed. Written now it costs
a document; written the day 1,133 universe members first produce 40 admissible candidates, it is
written under pressure and against a live account.

### What was built on 2026-08-22, and what deliberately was not

**Built: the admissibility half.** Each candidate is measured against the OPEN BOOK — "if this one
were taken, would the book pass 4R or 4 positions?" — and refused with `Skip` / `RISK` if it would.
`open-position` applies the same test before recording a manual entry, and refuses without
`--acknowledge-over-cap "<reason>"`, which is itself recorded (`DR-006` §9.2).

**Not built: the ranking.** Candidates do not compete with each other for the remaining capacity, and
that is rule 4 being obeyed rather than a shortcut: `rs.ranking_method` is `unset`, so there is no
ordering to apply, and truncating an id-sorted list is §4's alphabetical bias. The consequence has to
be said out loud wherever the room is displayed, and the run report says it — **the room shown is for
ONE more position, not for every candidate listed under it.** Two `Watch` names each individually
inside a book with one slot left are still two names and one slot.

`deferred` (§5) is therefore still unbuilt too: with no ranking there is no line to fall below.

## 8. Open items

- [ ] **`rs.ranking_method` needs a pre-registration, not a decision record** (§3) — the course marks
      its own answer as an untested hypothesis, so adopting it is a claim that could be false.
      Whether the first ordering should be relative strength at all is genuinely open: liquidity,
      spread cost and the expectation's own confidence interval are each defensible, and the course
      prefers none of them.
- [ ] **Whether `deferred` is a watchlist status or a decision outcome.** The nine watchlist states
      include `Ready`, which is close; the candidate-decision enum has only four and none of them
      means "admissible but no room". Resolve with the watchlist transition graph, still open in
      `DECISION_STATE_MACHINE.md` §6.
- [ ] **The six portfolio parameters** (§2). `DR-007` set the `validation.*` family; the `risk.*`
      portfolio block is the obvious next record, and it is larger because each value has a real
      consequence for a real account rather than for a study.
- [ ] Whether capacity should be expressed in R or in currency at all. R is scale-free and matches
      the sizing law; a human thinks in dollars. Probably both, computed from one.
