# EXIT MODEL SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim` + derived from `registry/`

<!-- verbatim-sources: Module_58_Adaptivnyi_vybor_vykhoda_v4.0.pdf, Module_55_Trailing_exits_v4.0.pdf, Module_52_Zashchitnye_vykhody_v4.0.pdf -->

**Sources:** Modules 52–58. The taxonomy below is **generated from
`registry/course_index.yml`**, whose titles are extracted from the PDFs and self-checked
(`tools/build_course_index.py`), so it is not hand-transcribed. The normative quotes are verified
separately by `tools/verify_transcription.py`.

**92 topics across M52–M58**, of which 8 are explicitly commentary (advantages/disadvantages,
comparisons, standardisation). The rest are named exit policies or rules governing them.

---

## 1. The four-slot model

Every one of Module 58's twelve topics carries the **identical** `STANDARD`:

> "Задать защитный, прибыльный, контекстный и временной выход; указать количество и порядок
> исполнения."

That single sentence is the course's exit architecture, and it is genuinely useful as a data model:

| Slot | Meaning | Module |
|---|---|---|
| `protective` | the exit that caps loss | M52 |
| `profit` | the exit that realises gain | M53 (fixed) · M54 (partial) · M55 (trailing) |
| `contextual` | the exit driven by price/market behaviour | M56 |
| `time` | the exit driven by elapsed time or an approaching event | M57 |

Plus two required attributes on every slot: **quantity** and **execution order**.

**Assignment caveat:** placing M55 trailing under `profit` is an authored interpretation. The course
names the four slots and never maps its modules onto them. M52→protective, M56→contextual and
M57→time are unambiguous; trailing is not. Recorded so the choice is visible rather than assumed.

## 2. What Module 58 does not do

M58 is the module that should map strategy → exit policy. It names twelve such mappings — momentum
breakout, trend pullback, mean reversion, false breakout, earnings drift, event-driven, reversal,
short-selling, pairs trade, volatility breakout — and **all twelve share byte-identical operational
content**. There is no per-strategy exit assignment anywhere in the course.

Consequence: the four-slot model is imported; its per-strategy population is **authored work**, one
entry per strategy card (`STRATEGY_CARD_SPEC.md`).

## 3. The taxonomy

Generated from the registry. Topic IDs are the component IDs.

**M52 · protective (795–806)**
Выход по первоначальному стопу · Выход при немедленном провале сетапа · Выход при закрытии за
уровнем отмены · Выход при пробое структуры · Выход по ATR · Выход по volatility stop ·
Catastrophic exit · Event-risk exit · Выход перед отчётностью · Выход при ухудшении ликвидности ·
Time-based protective exit · Выход при нарушении рыночного контекста

**M53 · profit, fixed targets (807–820)**
Выход на 1R · Выход на 2R · Выход на 3R · Выход на следующем сопротивлении · Выход на следующей
поддержке · Выход у предыдущего максимума · Выход у предыдущего минимума · Measured move ·
ATR target · Percentage target · Средняя линия диапазона · Противоположная граница диапазона ·
Полная фиксация позиции · *Ограничения фиксированной цели (commentary)*

**M54 · profit, partial (821–832)**
Частичный выход на 1R · Частичный выход на первом уровне · Продажа половины позиции · Продажа трети
позиции · Scale-out · Уменьшение риска · Перенос стопа после частичной фиксации · Удержание runner ·
Стабильное правило частичных выходов · *Психологические преимущества · Математические недостатки ·
Сравнение partial и all-out выхода (commentary)*

**M55 · profit, trailing (833–848)**
Trailing stop по проценту · Trailing stop по ATR · Chandelier Exit · Trailing под swing lows ·
Trailing над swing highs · Moving-average trailing exit · 10 EMA exit · 20 EMA exit · 50 SMA exit ·
Donchian exit · Lowest-low exit · Highest-high exit · Previous-day low exit · Previous-day high
exit · Trendline exit · *Преимущества и недостатки trailing stop (commentary)*

**M56 · contextual (849–864)**
Failed follow-through · Потеря momentum · Break of structure · Change of character · Lower high
против long-позиции · Higher low против short-позиции · Heavy-volume reversal · Bearish engulfing у
цели · Bullish engulfing у цели · Failed breakout · Failed breakdown · Climax candle · Rejection от
ключевого уровня · Потеря relative strength · Ослабление сектора · Ослабление широкого рынка

**M57 · time (865–874)**
Сделка не развивается · Максимальный срок удержания · Отсутствие follow-through · Снижение
волатильности после входа · Потеря opportunity cost · Выход перед выходными · Выход перед
праздником · Выход перед отчётностью · Выход перед макроэкономическим событием · *Отличие терпения
от удержания мёртвой позиции (commentary)*

**M58 · adaptive selection (875–886)** — twelve strategy-to-exit mappings, all empty (§2).

## 4. Not one exit carries a parameter

Audited across all 92 topics: **no exit policy in the course states a numeric parameter.** Where a
title implies one, the number is in the title only and the body never defines how it is computed:

| Policy | Missing |
|---|---|
| `Trailing stop по ATR` | ATR period, multiplier |
| `Chandelier Exit` | period, multiplier, anchor definition — the name is the entire specification |
| `Donchian exit` · `Lowest-low` · `Highest-high` | lookback |
| `Trailing stop по проценту` · `Percentage target` | the percentage |
| `Максимальный срок удержания` | days or bars |
| `10 EMA` / `20 EMA` / `50 SMA exit` | what "cross" means — close, touch, or two closes |
| `Продажа половины / трети позиции` | the trigger price (the fraction is in the title) |
| `Перенос стопа после частичной фиксации` | where the stop moves to |

M55's own standard defers the period explicitly:

> "Скользящая средняя сглаживает цену и задаёт ориентир тренда или динамической зоны. Её период
> фиксируется заранее; касание средней само по себе не является сигналом."

Two things in that sentence are binding beyond the parameter gap: the period is **fixed in advance**
(not re-chosen per trade), and **touching a moving average is not by itself a signal** — a
crossing rule must be stated.

## 5. Binding rules

1. **Every exit slot records quantity and execution order.** Two policies firing on the same bar
   need a deterministic resolution order; it is part of the strategy card, not runtime chance.
2. **The R denominator does not move.** Partials and stop moves change open risk but never the
   planned risk that R divides by (`RISK_SPEC.md` §2).
3. **Stops do not widen.** Error `WIDE_STOP` is `Critical` with control `Hard violation protocol`
   (`CODES.md`). This is enforced at write time on the `Management` entity: a stop change that
   increases risk is rejected, not warned about.
4. **Exit reasons are coded**, not free text (`CHECKLIST_SPEC.md` §3:
   `Final exit имеет код причины`). The taxonomy above supplies the code set.
5. **Do not change the exit model because of current P&L.** The most frequent prohibition in
   M52–M58, appearing on 69 topics: *"Запрещено менять модель выхода только из-за текущего P&L или
   эмоции."*

## 6. Open items

- [ ] Every parameter in §4 — registry entries with provenance `assumed`, per owner decision D5.
- [ ] The per-strategy exit mapping M58 omits (§2).
- [ ] Resolution order when protective, contextual and time exits fire on the same bar. The course
      requires an order be stated; it does not state one.
- [ ] Whether trailing belongs in the `profit` slot (§1 caveat) or warrants a fifth slot. Deviating
      from four slots is a departure from the course and needs an explicit decision record.
