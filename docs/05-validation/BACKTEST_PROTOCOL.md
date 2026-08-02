# BACKTEST PROTOCOL

**Status:** drafting · **Tier:** 5 (validation) · **Content:** `verbatim` + authored

<!-- verbatim-sources: Appendix_J_Ruchnoi_bektest_v2.0.pdf, Module_72_Istoricheskoe_testirovanie_v4.0.pdf -->

**Source of truth:** Appendix J (the manual-backtest worksheet) and Module 72, topics 1071–1090.
Verified 2026-08-02 by re-extracting both with `pdftotext -enc UTF-8`.

The course is unusually direct here. It does not describe backtesting as a way to discover an edge;
it describes it as a way to **fail to disprove** one, and it names the four ways a result becomes
worthless.

---

## 1. What a backtest is for

Topic 1071, `Цель бэктеста`:

> "Backtest должен скрывать будущие данные, использовать point-in-time universe, делистинги,
> корпоративные действия и реальные расходы. Красивый equity curve без этих проверок не является
> доказательством."
>
> *(A backtest must hide future data and use a point-in-time universe, delistings, corporate actions
> and real costs. A pretty equity curve without those checks is not evidence.)*

Five requirements in one sentence, and the last clause is the operative one. **A result is not
evidence until all five hold.** This project can satisfy four of them; §6 states plainly which one it
cannot, and what that costs.

## 2. The nine stages

Appendix J is a two-row table: a stage, and the record that stage must produce. The mapping below is
by column position, which is how the worksheet reads.

Stages, verbatim:

```verbatim
Перед началом
Bar-by-bar
Кандидат
Сигнал
Риск
Выход
Результат
Пропуски
QA
```

Mandatory records, verbatim, in the same order:

```verbatim
Зафиксировать strategy version, universe, dates, costs и sample size.
Скрыть будущие свечи; решения только по доступным данным.
Market, sector, 1Y, 3M, 30D, event и liquidity.
Setup date, trigger date, available execution.
Entry, stop, shares, slippage, gap handling.
Все rules без discretionary hindsight.
Net R, MFE, MAE, holding period.
Делистинги, halts, unfilled orders, missing data.
Повторная независимая проверка части выборки.
```

**What each stage obliges this system to build**

| Stage | Obligation | Where |
|---|---|---|
| Перед началом | The run pins strategy version, universe, date range, costs and sample size **before** it starts. This is a pre-registration, and it is the course asking for one. | `PREREG_TEMPLATE.md` |
| Bar-by-bar | Future bars are not merely unused — they are **unreachable**. An as-of query is the only read path. | `POINT_IN_TIME_SPEC.md` |
| Кандидат | Context is recorded per candidate, not per trade: market, sector, three windows, events, liquidity. Rejected candidates therefore have records too. | `SCREENER_SPEC.md` |
| Сигнал | Setup date and trigger date are **separate fields**, and execution is what was *available*, not what was ideal. | `contracts/` |
| Риск | Entry, stop, shares, slippage and gap handling per trade. Stop before size, always. | `RISK_SPEC.md` |
| Выход | Every exit follows a rule. `discretionary hindsight` is named as the thing being excluded. | `EXIT_MODEL_SPEC.md` |
| Результат | Net R, MFE, MAE, holding period. **Net**, so costs are inside the number, not a footnote. | `STATISTICS_SPEC.md` |
| Пропуски | Delistings, halts, unfilled orders and missing data are recorded as *outcomes*, not dropped as noise. A dropped row is a silent survivorship filter. | `DATA_QUALITY_SPEC.md` |
| QA | An **independent re-check of part of the sample**. Not a re-run of the same code — a second, independent pass. | §7 |

The QA row is the one most easily skipped and the hardest to fake. A re-run of the same code proves
determinism, not correctness; the course is asking for something else.

## 3. The four prohibitions

Verbatim, the `FAIL-CLOSED` clause attached to the backtest topics in M72, M73 and M74:

> "Запрещены look-ahead, survivorship, data snooping и переход live по красивой in-sample equity
> curve."
>
> *(Look-ahead, survivorship, data snooping and going live on a pretty in-sample equity curve are
> prohibited.)*

And the evidence that must exist for the claim to stand:

> "Protocol, code/data version, trade log, OOS/walk-forward report и paper/live gate."

Five artefacts. Note what is **not** in the list: a chart, a summary statistic, or a narrative. The
evidence for a strategy claim is the protocol plus the record, and both are versioned.

## 4. The standard

The `STANDARD` block carried by the validation topics:

> "не принимать результат без point-in-time данных, out-of-sample проверки, реалистичных расходов и
> версии. Использовать point-in-time данные, delistings, реалистичное исполнение, временное
> разделение и stress/robustness tests."
>
> *(Do not accept a result without point-in-time data, an out-of-sample check, realistic costs and a
> version. Use point-in-time data, delistings, realistic execution, temporal separation and
> stress/robustness tests.)*

And the limitation printed on every topic in the course:

> "Эта тема не доказывает торговое преимущество сама по себе. Применимость ограничена указанным
> рынком, режимом, свежестью данных и версией правила."

## 5. Everything the course leaves unset

Module 72 contains topics titled *Минимальное количество сделок* (1074), *Выбор исторического
периода* (1072), *Комиссии* (1081), *Проскальзывание* (1082) and *Чувствительность результатов*
(1087). **None of them contains a number.** Each carries the same boilerplate definition as every
other topic in the course.

That is not a criticism of the source; it is the single most important fact about it, and it is why
every one of these is a registry entry with `status: unset`:

| Concept | Course topic | Parameter |
|---|---|---|
| minimum trades for a verdict | M72-T1074 | `validation.backtest_min_trades` |
| historical period selection | M72-T1072 | `validation.backtest_period` |
| commissions | M72-T1081 | `costs.commission_model` |
| slippage | M72-T1082 | `costs.slippage_model` |
| in-sample / out-of-sample split | M72-T1090, M73-T1091, M73-T1092 | `validation.is_oos_split` |
| sensitivity tolerance | M72-T1087 | `validation.parameter_stability_tolerance` |

An unset parameter here does not mean "pick something sensible at runtime". It means the backtest
**refuses to produce a verdict** until a human sets it and records why (`PARAMETER_REGISTRY.md` §4).
A protocol that silently defaults its own sample-size threshold is a protocol that will always find
its sample sufficient.

## 6. Survivorship: the requirement this project cannot meet

The course requires delisted instruments (topic 1084, and the `Пропуски` stage). **No free data
source provides them**, and this was established by measurement rather than assumption
(`DATA_QUALITY_SPEC.md`): Yahoo returns zero rows for a delisted ticker; Questrade resolves the
symbol as a non-tradable stub whose candle endpoint returns `code 1019`.

The consequence, stated without softening:

- Every backtest this project runs is **survivorship-biased upward** by an amount it cannot measure.
- No result may be reported as satisfying topic 1084 while this holds.
- The only remedy is a paid vendor. That is a budget decision, not an engineering one, and it is
  deferred until a specific study is blocked by it rather than settled on principle.

**Owner decision, 2026-08-02: a component may still advance above `Untested`, provided the record
discloses the coverage and every display of that component shows it.** The alternative — blocking
advancement — would mean nothing ever advances on free data, which converts an honest limitation
into a permanent halt.

That decision rests entirely on the disclosure being impossible to omit, so it is enforced rather
than documented: `survivorship` is a **required field with no default** on
`swingdesk.contracts.evidence.EvidenceRecord`, and a record constructed without it raises. The
qualification then travels with the number wherever it is displayed — adjacent to it, not in a
footnote (`PARAMETER_REGISTRY.md` §5, same rule as `assumed` parameters).

Reporting a survivorship-biased result *as though* it met the standard would violate the prohibition
in §3 directly. Reporting it with the bias named, on every display, does not.

## 7. Independent re-check (the QA stage)

The course asks for `Повторная независимая проверка части выборки`. Concretely, for this project:

1. A sample of trades is drawn from the run by a seeded, recorded rule — not chosen by the person
   checking.
2. Each sampled trade is reconstructed **from the stored evidence alone**: the as-of snapshot, the
   recorded parameters and the rule version. Not from the run's own output.
3. Disagreement is a defect in the run, not a rounding difference to be waved through.

This is deliberately a different check from the determinism replay (`DETERMINISM_SPEC.md` §7), which
proves the code reproduces itself. This one asks whether the record supports the conclusion.

## 8. Open items

- [ ] Sampling rule and sample size for the QA stage. Seeded and recorded, per `DETERMINISM_SPEC.md`
      §3.4 — the seed goes in the manifest.
- [ ] Whether a backtest may run at all while `validation.backtest_min_trades` is unset. Producing
      trade records is useful; producing a *verdict* is not. Likely: run permitted, verdict refused.
- [ ] Cost model shape. `costs.commission_model` and `costs.slippage_model` are named as models
      rather than scalars because a flat per-trade commission and a spread-proportional slippage are
      different functions, and the course names both concepts without choosing either.
