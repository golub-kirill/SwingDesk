# STATISTICS SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim`

<!-- verbatim-sources: Appendix_D_Formuly_torgovoi_statistiki_v2.0.pdf, Appendix_H_Ezhenedelnyi_obzor_v2.0.pdf, Module_69_Statistika_strategii_v4.0.pdf -->

**Sources:** `Appendix_D_Formuly_torgovoi_statistiki_v2.0.pdf` page 2 (the formulas),
`Module_69_Statistika_strategii_v4.0.pdf` (the metric list and the standard),
`Appendix_H_Ezhenedelnyi_obzor_v2.0.pdf` (the required reporting breakdown). Verified 2026-08-01.

---

## 1. The formulas, verbatim

One source cell per line, each checked independently:

```verbatim
Wins / Closed trades
Σ positive R / wins
|Σ negative R| / losses
WinRate×AvgWin − LossRate×AvgLoss
Gross profit / |Gross loss|
AvgWin / AvgLoss
Max peak-to-trough equity decline
Realized positive R / MFE
MAE / initial risk
Execution slippage $ / planned risk $
Compliant decisions / total decisions
```

| Метрика | Формула | Использование |
|---|---|---|
| Win rate | `Wins / Closed trades` | Не оценивать без average win/loss. |
| Average win | `Σ positive R / wins` | По стратегии и версии. |
| Average loss | `|Σ negative R| / losses` | Проверять tail losses. |
| Expectancy | `WinRate×AvgWin − LossRate×AvgLoss` | После расходов. |
| Profit factor | `Gross profit / |Gross loss|` | Указывать число сделок. |
| Payoff ratio | `AvgWin / AvgLoss` | Не учитывает вероятность. |
| Max drawdown | `Max peak-to-trough equity decline` | В $,%,R. |
| MFE capture | `Realized positive R / MFE` | Интерпретировать по exit model. |
| MAE ratio | `MAE / initial risk` | Ищет проблемы entry/stop. |
| Slippage R | `Execution slippage $ / planned risk $` | По типу ордера/liquidity. |
| Process compliance | `Compliant decisions / total decisions` | Отдельно major/critical violations. |

**`Process compliance` is the notable one.** It is a statistic about the *operator*, not the market,
and the course treats it as a first-class metric alongside expectancy. It requires that every
decision be recorded as compliant or not — which is only possible because the checklists and the
journal are mandatory.

## 2. Reporting rules the `Использование` column imposes

| Rule | Obligation |
|---|---|
| `Не оценивать без average win/loss` | Win rate may never be displayed alone. Any surface showing win rate shows average win and average loss beside it. |
| `По стратегии и версии` | Metrics are keyed by `(strategy, version)`. Pooling versions is prohibited. |
| `Проверять tail losses` | Average loss is reported with its tail, not as a bare mean. |
| `После расходов` | Expectancy is **net of all costs**. A gross figure is not expectancy. |
| `Указывать число сделок` | Profit factor is never quoted without `n`. |
| `Не учитывает вероятность` | Payoff ratio must be labelled as excluding probability, so it is not read as edge. |
| `В $,%,R` | Max drawdown is reported in **all three units**, not one. |
| `Интерпретировать по exit model` | MFE capture is meaningless without the exit model that produced it — the two are displayed together. |
| `Ищет проблемы entry/stop` | MAE ratio is a diagnostic of entry and stop placement, not of the exit. |
| `По типу ордера/liquidity` | Slippage R is broken down by order type and liquidity band. |
| `Отдельно major/critical violations` | Process compliance separates `Major` from `Critical` (severity enum in `CODES.md`). |

## 3. The metric list (M69, topics 1018–1032)

Beyond Appendix D's eleven, Module 69 names four more:

`Количество сделок` · `Win rate` · `Loss rate` · `Средняя прибыль` · `Средний убыток` ·
**`Average R`** · `Expectancy` · `Profit factor` · `Максимальная просадка` ·
**`Recovery factor`** · **`Sharpe ratio`** · **`Sortino ratio`** ·
`Максимальная серия побед` · `Максимальная серия убытков` · `Средняя продолжительность сделки`

**Recovery factor, Sharpe and Sortino have no formula anywhere in the course**, and no risk-free rate
or MAR threshold is stated for Sharpe/Sortino. Their definitions are authored work with conventions
that must be frozen and versioned — the exact class of ambiguity that produced a silently inflated
Sharpe in the previous project (ratio computed on trade-months only rather than a contiguous
zero-filled series). The chosen convention goes in `ALGORITHM_SPEC.md` with a golden vector.

## 4. Required breakdown axes

M69 topics 1033–1038 make six breakdowns mandatory:

`Результат по сетапам` · `Результат по рыночным режимам` · `Результат по секторам` ·
`Результат по дням недели` · `Результат по типам входа` · `Результат по типам выхода`

Appendix H adds the weekly-review grouping, verbatim:

> Результаты разделены по strategy/version/regime/country/sector.

Union of the two — the mandatory `GROUP BY` set for the statistics layer:

```
strategy · version · regime · country · sector · setup · weekday · entry type · exit type
```

`country` is separately required because USA and Canada may not be merged
(`FAIL_CLOSED_POLICY.md`, M30/M31/M33).

## 5. The standard and the prohibition

Verbatim from M69:

> "Определить формулу, выборку, стратегию/версию/режим и считать результат после всех расходов."

> "Запрещено делать вывод по малой выборке, смешивать стратегии или оценивать процесс только по P&L.
> Доказательство: Экспорт журнала, формула, sample size, rolling window и разрезы результатов."

**Binding:** every reported metric carries formula, sample, scope and a rolling window as
displayed metadata — not as a footnote. `sample size` is a required field, and
`малая выборка` is **unquantified**: the minimum-sample threshold is a parameter, and until it is
set the system reports the count and refuses the verdict rather than guessing.

## 6. Drawdown behaviour is not just reporting

From M69's drawdown definition:

> "Drawdown измеряет снижение от пика капитала… Лимиты просадки должны автоматически снижать размер
> и активировать паузу."

Drawdown limits **automatically** reduce size and trigger `Pause`. That makes max drawdown an input
to the risk engine, not only a report — see `RISK_SPEC.md` §4, where the ladder is listed as an
unquantified required parameter.

## 7. Open items

- [ ] Freeze conventions for Sharpe, Sortino and Recovery factor: periodicity, whether the series is
      contiguous and zero-filled, risk-free rate, annualisation. None is in the course.
- [ ] Minimum sample size for a verdict — named (`малая выборка`), never quantified.
- [ ] `Breakeven win rate` (M50-T775) has a dedicated topic and **no formula anywhere**, including
      Appendix D. Authored.
- [ ] Rolling-window length for rolling expectancy — required by M69, unquantified.
