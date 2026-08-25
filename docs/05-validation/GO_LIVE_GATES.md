# GO-LIVE GATES

**Status:** drafting · **Tier:** 5 (validation) · **Content:** `verbatim` + authored

<!-- verbatim-sources: Appendix_Q_Plan_pervykh_30_dnei_v2.0.pdf, Appendix_R_Plan_pervykh_90_dnei_v2.0.pdf, Appendix_S_Plan_pervykh_100_realnykh_sdelok_v2.0.pdf, Module_75_Perekhod_k_realnoi_torgovle_v4.0.pdf -->

**Source of truth:** Appendices Q, R and S (the staged plans) and Module 75, topics 1115–1124.
Verified 2026-08-02 by re-extraction.

**This system does not trade.** It is decision support, and the charter's first non-goal is order
execution (`CHARTER.md`, owner decision D1). So these gates govern *the owner*, and this system's
obligation is to **measure and display** whether each gate is met — never to authorise crossing one.

That distinction is what makes this document buildable: every gate below is a query over the journal.

---

## 1. The rule that outranks the schedule

Appendix R states it as a prohibition, above the plan table:

> "Календарный срок сам по себе не разрешает реальную торговлю. Переход зависит от качества данных,
> соблюдения процесса и критериев готовности."
>
> *(A calendar period by itself does not authorise real trading. The transition depends on data
> quality, process adherence and readiness criteria.)*

Three named dependencies, and time is not among them. So the plans in §2 and §3 are **sequences, not
schedules**: reaching day 90 authorises nothing on its own.

For this system that means the readiness display must never show a countdown. A progress bar toward a
date implies the date is the gate, and the course says it is not.

## 2. The staged plans

Appendix Q covers the first 30 days of study — no trades at all. Its six periods and their required
outputs, verbatim:

```verbatim
Устройство рынка, инструменты, ордера, брокер; без реальных сделок.
Свечи, структура, уровни на 1Y/3M/30D.
Объём, volatility, liquidity, regimes.
Watchlist, screener, catalysts.
Одна базовая стратегия и риск.
Paper workflow, journal, weekly review.
```

Appendix R covers the first 90 days of practice as three phases with a criterion each:

```verbatim
База и одна стратегия
Форвард-тест и исполнение
Robustness и готовность
```

```verbatim
Разметка, manual backtest, paper routine.
Стабильные checklists, минимум нарушений, realistic costs.
Rolling stats, regime breakdown, risk protocol, micro-size gate review.
```

Two things the system owes each phase: `manual backtest` and `paper routine` need the journal to
accept manually-entered decisions, not only generated ones; and `Rolling stats, regime breakdown`
is a reporting requirement that presupposes the regime classifier exists.

## 3. The first hundred real trades

Appendix S is the only place in the course that states a hard, checkable gate. Five stages of twenty
trades each, with a task and a gate per stage.

Tasks, verbatim:

```verbatim
Micro-size; одна стратегия; цель — техническая точность.
Стабилизация execution и alerts.
Проверка разных режимов при неизменных правилах.
Оценка exit model и portfolio overlap.
Полный audit готовности к следующему уровню.
```

Gates, verbatim:

```verbatim
100% plan/stop/journal; no critical violations.
Slippage и missed-trade причины измеряются.
Regime tags и rolling stats.
MFE/MAE, sector buckets, event risk.
```

**Four gate cells against five stages.** The worksheet extracts as two interleaved rows and the
fifth stage's gate cell is not separable from the closing note that follows it. The pairing of the
first four is unambiguous by position; **the gate for trades 81–100 is not asserted here** rather
than guessed. It needs a look at the rendered page, and it is listed in §7.

The closing note, verbatim:

> "Положительный/приемлемый expectancy не обязателен без достаточной выборки, но процесс должен быть
> устойчивым."
>
> *(A positive or acceptable expectancy is not required without a sufficient sample, but the process
> must be stable.)*

This is the sharpest sentence in the course about what a hundred trades can and cannot tell you, and
it inverts the obvious gate. **Profit is not the criterion. Process stability is.** A profitable
hundred trades with critical violations fails; a break-even hundred trades with clean process
passes.

## 4. The size-increase gate

Appendix S, above the table:

> "Увеличение размера. Только по заранее определённым gates: отсутствие critical violations,
> стабильный process score, приемлемый drawdown, совместимость live и test execution, техническая
> готовность."
>
> *(Size increase. Only by pre-defined gates: absence of critical violations, a stable process score,
> acceptable drawdown, compatibility of live and test execution, technical readiness.)*

Five conditions. Note `заранее определённым` — pre-defined. A gate agreed after seeing the results is
not a gate.

| Condition | Measurable from | Status |
|---|---|---|
| no critical violations | error codes in the journal (`CODES.md`) | **computable today** — the twelve error codes are transcribed |
| stable process score | `stats.process_score_scale` | `assumed:DR-002`, read by nothing — the course names the concept and no scale, so the value is authored rather than taken |
| acceptable drawdown | `validation.max_allowable_drawdown` | `owner`, read by nothing. ~~`DR-007` gave it a value on 2026-08-08~~ — **corrected 2026-08-25:** the **owner** set it to 20 percent of equity; `DR-007` §3.7 proposed −15R and the 2026-08-09 reconciliation superseded that, since `owner` outranks `assumed:DR-007`. `RULE_SPEC.md` §7 states what having a value bought: *"the gate went from unable to fail to untested"* — and it is still untested, because nothing computes realised drawdown |
| live/test execution compatible | recorded slippage vs modelled slippage | needs `costs.slippage_model` |
| technical readiness | run success rate, alert delivery, journal completeness | Track A criteria |

Only the first is computable now, and only because the course supplied the error codes. That ratio —
one of five quantified — is the tier-5 situation in miniature.

## 5. Drawdown is an actuator, not a report

Topic 1122, `Максимальная допустимая просадка`:

> "Drawdown измеряет снижение от пика капитала и отражает как дисперсию стратегии, так и качество
> контроля риска. Лимиты просадки должны автоматически снижать размер и активировать паузу."
>
> *(Drawdown measures the decline from the equity peak and reflects both the strategy's dispersion
> and the quality of risk control. Drawdown limits must automatically reduce size and activate a
> pause.)*

`автоматически` — automatically. The course requires the limit to *act*, not to be noticed.

For a decision-support system that does not trade, "act" resolves to: the sizing path returns a
reduced size or a `Pause`, and the reason names the drawdown rule. That is a refusal the operator
cannot skip past unknowingly, which is the achievable form of automatic here. The ladder itself is
`risk.drawdown_size_reduction_ladder` and `risk.risk_off_ladder` — both `unset`, both named by the
course and quantified nowhere.

## 6. Module 75's own progression

Topics 1115–1121 describe the same ladder from the risk side: minimum position size, reduced risk, a
single strategy, a capped trade count, gradual size increase, and criteria for raising *and* lowering
risk. Topic 1121 is `Критерии снижения риска` — the descent has criteria too, which is the part
usually left implicit.

Topic 1116, `Сниженный риск`, carries the calculated-value clause rather than the generic one:

> "«Сниженный риск» должно рассчитываться из заранее определённых входных значений. Формула, единицы
> измерения, округление, ограничения и поведение при отсутствующих данных фиксируются до применения."
>
> *(Must be calculated from pre-defined input values. The formula, units, rounding, limits and
> behaviour on missing data are fixed before use.)*

That sentence is a specification of a function signature, and it is the same contract
`ALGORITHM_SPEC.md` imposes on every derived observation: formula, units, rounding, limits, and
**behaviour on missing data fixed in advance**. Reduced risk is not a mood; it is a computation with
a declared refusal path.

## 7. Open items

- [ ] The gate for trades 81–100 in Appendix S — read from the rendered page rather than extracted
      text, and transcribe it then. Recorded as unknown rather than inferred.
- [ ] Whether this system displays go-live readiness at all before a forward test exists. Showing
      four unmeasurable conditions as "pending" is honest; showing them as a checklist implies they
      are close.
- [ ] `stats.process_score_scale` blocks two separate gates (§4, and the Track A process criteria).
      It is the highest-leverage unset parameter in tier 5 and needs a pre-registration.
