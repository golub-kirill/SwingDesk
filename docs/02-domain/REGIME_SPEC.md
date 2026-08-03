# REGIME SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim` + measured

<!-- verbatim-sources: Module_30_Rynochnye_rezhimy_v5.0.pdf, Module_71_Formalizatsiya_strategii_v4.0.pdf -->

**Sources:** Module 30 (topics 439–452, the regime module) plus the operational regime topics
scattered through M59, M67, M71 and M80. Written **after** PR-002 reported, so it states what was
measured rather than what was hoped.

---

## 1. What the course means by a regime

One sentence, and it appears **identically in four modules** — M59-T0887, M67-T0988, M71-T1056 and
M80-T1176. Repetition across modules is the strongest attestation this course offers, so this is the
definition rather than one phrasing of it:

```verbatim
Рыночный режим описывает сочетание направления, breadth и volatility. Он не предсказывает день, а определяет, какие семейства стратегий и уровни риска допустимы.
```

Two claims worth separating:

1. **A regime is three-dimensional**: direction, breadth, volatility. Not a single axis, and not a
   single indicator.
2. **A regime is a permission, not a forecast.** It does not predict the day; it determines which
   strategy *families* and which *risk levels* are admissible. That is a constraint on what may be
   traded, which is a much weaker and much more defensible claim than a directional one.

## 2. The eleven regimes

Module 30 names eleven. Each topic's only regime-specific content is one English line under
`VALID · ЧТО ДОЛЖНО БЫТЬ` — the rest of every topic is the module's shared boilerplate.

```verbatim
Bull regime combines rising structure, participation, and manageable volatility.
Bear regime combines falling structure, weak participation, and failed rallies.
Sideways regime has overlapping price and low directional persistence.
High volatility is a range/ATR condition, not a directional forecast.
Low volatility is compressed range/ATR and may precede either direction.
Risk-on requires risk assets and breadth to outperform defensive assets.
Risk-off requires defensive leadership, weak breadth, and pressure on risk assets.
Trending regime needs directional structure plus sustained ADX evidence.
Mean-reverting regime needs bounded overlap and weak trend persistence.
Panic combines rapid drawdown, volatility expansion, and breadth collapse.
Recovery combines price repair, falling stress, and improving breadth.
```

| # | Topic | Regime | Axis it primarily speaks to |
|---|---|---|---|
| 439 | `Бычий рынок` | Bull | direction |
| 440 | `Медвежий рынок` | Bear | direction |
| 441 | `Боковой рынок` | Sideways | direction |
| 442 | `Высоковолатильный рынок` | High volatility | volatility |
| 443 | `Низковолатильный рынок` | Low volatility | volatility |
| 444 | `Risk-on` | Risk-on | breadth |
| 445 | `Risk-off` | Risk-off | breadth |
| 446 | `Trending regime` | Trending | direction (persistence) |
| 447 | `Mean-reverting regime` | Mean-reverting | direction (persistence) |
| 448 | `Panic regime` | Panic | all three at once |
| 449 | `Recovery regime` | Recovery | all three at once |

**These eleven are not mutually exclusive and the course never says they are.** "High volatility"
and "Bear" describe different axes and co-occur constantly; "Panic" is a conjunction of all three.
So the eleven are a **vocabulary**, not a partition — and any implementation that treats them as
eleven exclusive states is asserting something the source does not.

Three further topics govern them:

| Topic | Claim type | What it adds |
|---|---|---|
| 450 `Определение текущего режима` | Definition | `Regime classification triangulates direction, ATR, ADX, and participation.` |
| 451 `Выбор стратегии под режим` | **Operational Course Rule** | `Strategy selection follows the frozen regime definition; it is not hindsight labeling.` |
| 452 `Когда не торговать` | **Operational Course Rule** | `Stand aside when regime evidence conflicts or usable reward/risk is absent.` |

Topic 452 is directly implementable and is the one operational rule in the module that this project
can act on today: **conflicting regime evidence is itself a stand-aside condition**, which maps onto
the existing `Pause`/`Skip` states rather than needing a new one.

## 3. The regime→strategy matrix does not exist

This document was scheduled to transcribe it. It cannot, and that is the finding.

Topic 451 is titled `Выбор стратегии под режим` — "choosing a strategy for the regime" — and is
classified as an `Operational Course Rule`, which is the course's strongest claim type. Its entire
regime-specific content is the single line quoted above. **There is no table, no mapping, and no
enumeration of which strategy family belongs to which regime**, in M30 or anywhere else. M71-T1056
`Допустимые рыночные режимы` states that the regime *determines* permissible strategy families and
risk levels; it never says what the determination is.

This is the same shape as the finding in `PARAMETER_REGISTRY.md`: the course is a governance and
taxonomy specification with the operational content left empty. Authoring a matrix here and
presenting it as transcription would be the single most damaging thing this document could do —
a regime→strategy mapping looks exactly like received wisdom, and nothing would mark it as invented.

**Consequence:** `strategy.regime_matrix` is not a parameter, because there is no matrix to
parameterise. If one is ever wanted it must arrive as a `PR-` study with a pre-registered
hypothesis, not as a transcription.

## 4. What this project actually implements: one axis of three

`swingdesk.derived_observations.regime` implements **M30-T0450** and covers **breadth only**.

| Axis | Course requires | This project |
|---|---|---|
| direction | yes | **not classified** — `screen.trend_definition` is `unset`, closed by PR-001 and PR-005 |
| breadth | yes | **classified** — share of the universe above its own 200d SMA, split at the train-window median |
| volatility | yes | **not classified** — `regime.atr_percentile_bands` is `unset`; `VOL_TERCILE` was registered as a PR-002 variant and not selected |

So the shipped classifier answers one third of the course's own definition. That is stated here
rather than in a footnote because a component named `regime` invites the reader to assume it means
what the course means, and it does not.

**What PR-002 measured** (reported 2026-08-02, the project's only `validated` parameter):

- `BREADTH_MEDIAN`, cut at **0.647**, fitted on the train window and applied forward.
- Test window: `BREADTH_LOW` **+0.2299R** over 466 trades vs `BREADTH_HIGH` **−0.1304R** over 717.
- Percentile 100 on both permutation nulls.

**And how fragile that is:** concentrated in the low-breadth cell, only **1.6%–2.3% of trades
missing at −2R/−3R** erases the separation. Yahoo serves no delisted history (D10 reaffirmed the
free tier), so that exposure can never be confirmed or ruled out — see
`docs/prereg/results/PR-002-report.md` and the note on `regime.classifier_rule`.

The variant selection deserves its own line: `BREADTH_X_VOL` — the two-axis classifier — was
registered and **not** selected. It lost on **stability** (5.777 label flips per 100 sessions
against `BREADTH_MEDIAN`'s 3.785), measured on the validation window *before* any outcome was
looked at, because the pre-registration prohibited selecting on outcome. So the gap in this table is
not "we ran out of time": the richer classifier was measured, and the axis this project omits is one
it tested and rejected on a criterion that could not have been rigged after the fact.

## 5. Parameters

| Parameter | Status |
|---|---|
| `regime.classifier_rule` | **`validated:PR-002`** — the project's only validated parameter |
| `regime.pct_above_ma_period` | `unset` — see below |
| `regime.breadth_cutoffs` | `unset` — PR-002 fits the cut per window rather than fixing one |
| `regime.atr_percentile_bands` | `unset` — the volatility axis is not classified |
| `regime.adx_threshold` | `unset`, and **weakly cited** — see §6 |

**`regime.pct_above_ma_period` is `unset` while the rule that uses it is `validated`, and that is a
real inconsistency rather than a tidy one.** The 200-day period is embedded in
`regime.classifier_rule`'s own text — "share of universe above its own 200d SMA" — so the value is
pinned by the validated rule while its parameter row still reads `unset`. Nothing computes from the
empty row today, so nothing is wrong at runtime; what is wrong is that the registry does not show a
number the project has in fact committed to. Recorded rather than silently backfilled: promoting it
would mean deciding whether it inherits PR-002's `validated` status, and it did not earn that
independently — 200 was fixed by design before the study, not measured by it.

## 6. Open items

- [ ] **The ADX citation is weak and is recorded as such.** Topic 450 names ADX
      (`triangulates direction, ATR, ADX, and participation`), but every other ADX appearance in the
      course is a chart-panel label (`S 94.5 ADX · ATR`) on synthetic teaching figures, and no
      threshold is ever given. `regime.adx_threshold` stays `unset` and any value for it is authored.
- [ ] **Topic 452 is implementable and unimplemented.** "Stand aside when regime evidence conflicts"
      needs at least two axes to have anything to conflict, so it waits on §4.
- [ ] Whether the eleven regimes should exist as an enum at all, given §2. An enum implies a
      partition the source does not claim.
