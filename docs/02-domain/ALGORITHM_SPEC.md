# ALGORITHM SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** field list `verbatim`; per-component content authored

<!-- verbatim-sources: Course_Production_Rules_v3.8.md -->

The record every Derived Observation must fill before it can reach `specified`
(`COMPONENT_REGISTRY_SPEC.md` §3). The **field list** is the course's; the **content** is ours,
because the course names its observations and quantifies none.

---

## 1. The required fields

Verbatim, §3.6 layer 2:

> "Every derived observation defines inputs, formula or algorithm, parameters, units, timeframe,
> sampling and session rules, warm-up, missing-data behavior, time alignment, output range, and
> version."

Eleven fields. Four of them are the ones that get skipped, and each has already caused a measured
problem in this project:

| Field | Why it is not optional here |
|---|---|
| **sampling and session rules** | US and Canadian sessions differ, and half-days shorten them (`CALENDAR_SPEC.md` §2b) |
| **warm-up** | an indicator emitting values before its window is full produces confident nonsense |
| **missing-data behavior** | vendor gaps are measured and real (`CALENDAR_SPEC.md` §2c) — every component must state what it does when a bar is absent |
| **time alignment** | which bar a value belongs to decides whether it is look-ahead (`POINT_IN_TIME_SPEC.md` §2) |

## 2. Record template

```yaml
component: M26-T0393-v5.0        # course id; the requirement id
name: RSI
version: 1                        # OUR version, independent of the course's v5.0
layer: Derived Observations
inputs:
  - series: adjusted             # raw | adjusted - explicit, never a runtime choice
    interval: 1d
    fields: [close]
formula: >-
  <exact definition, or a reference to the canonical one it implements>
parameters: [rsi.period]         # ids in registry/parameters.yml
units: index 0-100
output_range: [0, 100]
timeframe: 1d
session_rules: regular hours only; exchange calendar per instrument
warm_up: <bars required before the first valid output>
missing_data: <refuse | propagate null | skip bar> + the code raised
time_alignment: value for bar T uses bars <= T; emitted at T's close
verification: golden vectors | property test
consumers: []                    # populated from the registry
```

## 3. Rules that apply to every entry

1. **Raw or adjusted is declared, never chosen at runtime.** Indicators over adjusted series are
   comparable across time; liquidity checks over adjusted dollar volume are not
   (`POINT_IN_TIME_SPEC.md` §4).
2. **A value for bar T may only read bars ≤ T.** This is the property test in `TEST_STRATEGY.md` §2,
   and it is the difference between a backtest and a fantasy.
3. **Warm-up is enforced, not documented.** Before the window is full the component emits *no value*,
   not a partial one. A partially-warmed indicator is indistinguishable from a valid one downstream.
4. **Missing data has a declared behaviour**, and "silently interpolate" is not among the options.
   Every component states which, and unset behaviour means refuse.
5. **Parameters are ids, not literals.** A number written into a formula is invisible to the
   parameter registry and therefore to `PARAMETER_REGISTRY.md` §5's display obligation.
6. **Session rules come from the calendar**, not from constants (`ADR-0002`).
7. **Classifications are outputs of stated rules.** From §3.6: *"A classification such as "healthy
   trend" is an output of a stated rule, not a raw fact and not proof of future direction."* Any
   component emitting a label declares the rule that produced it.

## 4. Banned vocabulary in decision-facing outputs

From §3.6 layer 3:

> "Terms such as "smart", "strong", "quality", or "confirmed" are prohibited unless reduced to
> observable rules or explicitly reserved for documented human review."

Enforceable in review: a field named `quality`, `strength`, `confirmed` or similar must either
resolve to a stated rule, or be marked as a human-review slot. `Setup.quality grade` in
`JOURNAL_SCHEMA.md` is the latter — its scale is undefined by the course and it is flagged as
authored.

## 5. Where the content comes from

The course supplies **names and mechanisms**, not definitions. `RSI` is described as
*"положение текущего импульса относительно недавних изменений цены"* with a note that overbought is
not automatically a short. No period, no smoothing method, no computation.

So each entry is authored, and its parameters enter `registry/parameters.yml` with provenance
`assumed:<citation>` per owner decision D5. Where a widely-used standard definition exists (Wilder's
RSI, ATR), the citation is that standard, and the fact that it is a *convention* rather than a
course requirement is recorded.

Four components are authored with **no standard to lean on**, and each needs a pre-registration
before activation rather than just a value: the regime classifier, and the definitions of trend,
breakout, pullback and contraction (`PARAMETER_REGISTRY.md` §7).

## 6. Order of work

`specified` is cheap for components with a standard definition and expensive for the four above. The
sensible order:

1. components with an unambiguous standard — ATR, SMA, EMA, RSI, Bollinger, Donchian, VWAP
2. structural observations with a stated mechanism but no standard — swing structure, levels, zones
3. the four authored definitions, each pre-registered

Nothing reaches `active` without parameter values, golden vectors and a recorded validation status.

## 7. Open items

- [ ] Whether specs live in this document or one file per component alongside the code. Per-component
      scales better at 463 requirements and keeps the spec next to what it governs; this document
      then holds the template and the rules.
- [ ] Warm-up interaction with `universe.min_bar_history` — an instrument may satisfy universe
      eligibility while still being warm-up-incomplete for a long-window component.
- [ ] Whether a component may declare a *fallback* interval (compute on `1d` if `1h` is missing) or
      whether that is always a refusal. Leaning refusal: a silently-substituted timeframe is exactly
      the kind of invisible difference this project exists to prevent.
