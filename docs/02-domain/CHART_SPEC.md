# CHART SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim` + generated from `registry/`

<!-- verbatim-sources: Module_30_Rynochnye_rezhimy_v5.0.pdf -->

**Sources:** the chart-lab pages carried by every chart-bearing topic in the course. The
per-topic figures are the most repeated artefact in the whole source — **867 of 1379 topics carry
one** — so the contract they share is worth transcribing even though no single one of them is.

---

## 1. The finding, first

**The course's charts are a teaching artefact and they specify nothing about what this system should
render.** Every one is generated from synthetic data with a frozen cutoff:

```verbatim
SYNTHETIC TEACHING OHLCV · equity/ETF teaching universe · 1D · sessions 30/30 unit price units · cutoff 2025-02-12 · price-return convention · price + time axes family default · frozen Support/Resistance · OHLC verified · indicator
```

Synthetic OHLCV, a teaching universe, 30 sessions, a cutoff of 2025-02-12, and unit price units.
Nothing in that line describes a live candidate, and a rendering built to match it would be
reproducing a textbook figure rather than showing today's instrument.

So this document transcribes the **contract** the figures obey — which is real and is about
decision hygiene — and explicitly does not become a rendering specification. Tier 7 owns that, and
tier 7 is not started.

## 2. The contract every chart lab obeys

Two lines, repeated on every chart-bearing topic:

```verbatim
Сравнить Valid и Failed на одинаковом 30-session окне; проверить OHLC, Support/Resistance, volume, trigger и invalidation до outcome.
```

```verbatim
Valid/failed: Support/Resistance, trigger и invalidation заданы до outcome.
```

Three requirements, and all three are decision hygiene rather than graphics:

1. **Valid and Failed on the same window.** Every topic shows the pattern working and the pattern
   failing over an identical 30-session frame. A figure that only shows the win is a figure that
   teaches the win rate is 100%.
2. **Support/Resistance, trigger and invalidation are set *before* outcome.** This is the
   anti-hindsight rule stated as a drawing instruction. It is the same constraint
   `POINT_IN_TIME_SPEC.md` enforces in data and `BACKTEST_PROTOCOL` enforces bar-by-bar — here it
   governs what may be drawn on a chart.
3. **Frozen Support/Resistance.** The levels do not move to fit what happened.

The layout line adds the presentational half:

```verbatim
Следующая страница: 30/30 sessions · 1D · крупные свечи · S/R в боковой шкале · labels вне plot area
```

30 of 30 sessions, daily, large candles, S/R on the side scale, **labels outside the plot area**.
The last is the only genuinely visual requirement in the source and it is a legibility rule, not a
style one.

## 3. Chart families

Generated from `registry/course_index.yml`, so this table is extracted rather than hand-copied.

| Family | Topics |
|---|---|
| `non-market analytical figure` | 512 |
| `default` | 343 |
| `support_resistance` | 74 |
| `pullback_retest` | 68 |
| `breakout` | 58 |
| `trend` | 51 |
| `false_breakout` | 44 |
| `indicator` | 42 |
| `volume` | 41 |
| `volatility` | 38 |
| `reversal` | 34 |
| `candlestick` | 26 |
| `gap` | 29 |
| `range` | 19 |

**512 of 1379 are `non-market analytical figure` — not price charts at all.** They are decision
tables, flow diagrams and the `Контекст / Trigger / Критерий есть / Критерий нет` matrices that
appear on the operational topics. Counting them as "charts" inflates the apparent chart surface by
more than a third, which is worth knowing before anyone plans to render 867 of anything.

The eleven price families are a **presentation** taxonomy, not a component one. `breakout` and
`false_breakout` are separate families and share every drawing element; `trend` and `range` differ
only in what the frozen levels mean. Nothing computes from `chart_family` today and nothing should
without a reason — it describes what a teaching figure looked like.

## 4. What this project renders today

Nothing. The CLI produces a text report (`presentation/report.py`), and `PRODUCT_SURFACES.md` §3.1
names the CLI as the complete surface for v1.

That is a deliberate ordering rather than a gap: a chart is a claim about what mattered, and the
three requirements in §2 are exactly the ones a hastily-built chart breaks. Drawing a support level
after seeing the outcome is easier to do accidentally in a plotting call than anywhere else in this
system, because nothing type-checks a line on a canvas.

When rendering does arrive, §2 is the acceptance criteria and it is already testable:

- the levels drawn must come from `derived_observations.pivots`, which **emits at the confirmation
  bar rather than the pivot bar** — the look-ahead guard is already in the component
- the trigger and invalidation drawn must be the ones the run recorded, read from the journal, not
  recomputed at render time from the full series

## 5. Open items

- [ ] **Tier 7 owns rendering.** This document deliberately stops at the contract. Splitting it that
      way keeps a transcription from turning into a design.
- [ ] `chart_family` is carried in the registry and used by nothing. Either something reads it or it
      is dead metadata; recorded so the choice is made rather than defaulted.
- [ ] The `non-market analytical figure` majority suggests the course's own "chart" label means
      "figure". If any future work counts charts, it must say which sense it means.
