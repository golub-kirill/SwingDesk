# EVENT SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim` + measured

<!-- verbatim-sources: Module_34_Katalizatory_i_sobytiya_v5.0.pdf, Module_40_Earnings_i_event_driven_strategii_v5.0.pdf -->

**Sources:** Module 34 (`Катализаторы и события`, topics 495–514, Source Facts layer) and Module 40
(`Earnings и event-driven стратегии`, topics 606–623, Decision Logic layer). 38 topics between them.

This document exists because checklist item **E11** — event proximity — reports `unavailable`, and
`screen.earnings_buffer_days` is `unset`. The question it had to answer was whether the course
supplies a value. **It does not, and it does not supply the shape of one either.**

---

## 1. The two operational criteria, in full

Module 34 names twenty catalyst types. Module 40 names eighteen event-driven patterns. Between them
they carry **two** pass/fail statements, and each one is repeated *identically* on every topic in
its module — twenty times and eighteen times respectively.

Module 34, on all twenty catalysts:

```verbatim
Event confirmed by price and volume
```

```verbatim
Headline without price confirmation
```

Module 40, on all eighteen patterns:

```verbatim
Event gap earns post-event acceptance
```

```verbatim
Gap loses acceptance after the event
```

That is the complete operational content. **A catalyst type does not get its own criterion** — an
FDA decision, a buyback and a central-bank rate decision are all judged by "confirmed by price and
volume". The taxonomy is fine-grained; the rule applied to it is not.

The consequence for this project is direct: **there is no course basis for treating one event type
differently from another**, so any per-type handling would be authored, and it would need a `PR-`
study rather than a transcription.

## 2. What the modules do add

Three sentences carry real design content, all from `Operational Course Rule` or risk topics.

**M40-T0623** `Условия пропуска event-driven сделки` — the skip conditions:

```verbatim
Условия делятся на обязательные, подтверждающие и запрещающие; критический запрет не компенсируется большим количеством слабых положительных признаков.
```

Conditions split into **mandatory, confirming and prohibiting**, and a critical prohibition is not
offset by a larger number of weak positive signs. This is the same shape as `FAIL_CLOSED_POLICY.md`
and as the checklist's refusal to average items — a veto is not a score.

The same topic states what an event-driven decision is made of:

```verbatim
Event-driven торговля отделяет факт события от реакции рынка. Важны surprise, guidance, gap, relative volume, удержание цены и риск следующего события.
```

Event-driven trading **separates the fact of the event from the market's reaction**. Six inputs are
named: surprise, guidance, gap, relative volume, price holding, and *the risk of the next event*.

**M34-T0514** `Риски торговли до события`, on residual risk:

```verbatim
Остаточный риск, который нельзя устранить, ограничивается размером позиции или отказом от действия.
```

Residual risk that cannot be eliminated is bounded by **position size or by not acting**. Note what
is absent: no buffer in days, no "avoid N sessions before earnings", no threshold of any kind.

## 3. The catalogue

### Module 34 — catalysts, as source facts

| Topics | Group | Claim types |
|---|---|---|
| 495–500 | company results and estimates: quarterly report, earnings surprise, guidance change, revenue/earnings growth, analyst upgrade, analyst downgrade | 5 Definition, 1 Inference |
| 501–508 | corporate actions and decisions: new products, contracts, M&A, buyback, secondary offering, regulatory decisions, court decisions, FDA events | 7 Definition, 1 Inference |
| 509–512 | macro and political: macroeconomic data, central-bank decisions, sector news, political and geopolitical events | 4 Definition |
| 513–514 | trading after an event; risks of trading before one | 1 **Untested Hypothesis**, 1 Definition |

### Module 40 — event-driven patterns, as decision logic

| Topics | Pattern family | Claim types |
|---|---|---|
| 606–609 | post-earnings announcement drift; gap continuation, pullback, consolidation | 2 Definition, 2 **Untested Hypothesis** |
| 610–613 | gap-and-hold, gap-and-go, gap-and-fade, breakaway gap | 4 Definition |
| 614–617 | reactions that contradict the news: continuation after a raised forecast, reversal after a weak reaction to good news, strength despite bad news, weakness despite good news | 2 Definition, 2 **Untested Hypothesis** |
| 618–621 | analyst-upgrade momentum, contract-driven breakout, FDA-event continuation, trading after a macro event | 4 **Untested Hypothesis** |
| 622–623 | risk of holding into the next event; skip conditions | 1 Definition, 1 **Operational Course Rule** |

**Eight of Module 40's eighteen topics are labelled `Untested Hypothesis` by the course itself** —
44%, against roughly 3% across the whole catalogue. The course is unusually explicit here that its
event-driven patterns are conjecture, and that label should survive into anything built on them.

## 4. What this project can and cannot do with it

| Capability | State |
|---|---|
| Detect an event at all | **no source.** No free point-in-time earnings calendar is in hand, and none is wired |
| `screen.earnings_buffer_days` | **`unset`, and the course gives no value or shape** — see §2. Any number is authored |
| Separate event fact from market reaction (M40-T0623) | **computable in principle** from bars alone — a gap and relative volume need no event feed. The *fact* does not |
| Per-catalyst-type handling | **not supported by the source.** One criterion covers all twenty types |

Checklist item **E11** therefore stays `unavailable`, and its note is now accurate rather than
merely honest: it is not waiting on a parameter someone forgot to set, it is waiting on a data
source *and* on a study, because the course supplies neither the value nor the rule.

**PEAD is named (M40-T0606) and is a `Definition` rather than a hypothesis.** Recorded here because
it is the one event topic with a large external literature, which makes it the cheapest event study
this project could ever register — and, for the same reason, the one most likely to be a
well-documented dead end. It is not proposed; it is noted so the choice is deliberate when it comes.

## 5. Open items

- [ ] **No event source.** Until one exists, everything in §3 is catalogue, not capability. The
      constraint is D8/D10 (free tier), so this is a sourcing problem rather than a modelling one.
- [ ] **`screen.earnings_buffer_days` has no course basis.** It stays `unset`. Setting it requires a
      decision record with a stated rationale, or a study — not a transcription.
- [ ] Whether the gap/relative-volume half of M40-T0623 is worth implementing without an event feed.
      It would detect *reactions* without knowing what caused them, which is a weaker but genuinely
      computable thing, and the course's own framing separates the two.
