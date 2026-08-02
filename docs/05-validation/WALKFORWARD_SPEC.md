# WALK-FORWARD AND ROBUSTNESS SPEC

**Status:** drafting · **Tier:** 5 (validation) · **Content:** `verbatim` + authored

<!-- verbatim-sources: Appendix_K_Walk_forward_test_v2.0.pdf, Module_73_Walk_forward_i_robustness_testing_v4.0.pdf -->

**Source of truth:** Appendix K (the walk-forward worksheet, 12 fields) and Module 73, topics
1091–1104. Verified 2026-08-02 by re-extraction.

Module 73 is the densest specification in the course that this project can act on directly: it names
**six distinct perturbations** a result must survive, and Appendix K names the twelve fields a window
must record. Neither is quantified — but both are structural, and structure is the part the course
actually supplies.

---

## 1. What the two words mean here

Topic 1093, `Walk-forward analysis`:

> "Walk-forward разделяет настройку и последующую проверку во времени. Robustness требует, чтобы
> соседние параметры, другие режимы и повышенные расходы не уничтожали результат."
>
> *(Walk-forward separates tuning from subsequent checking in time. Robustness requires that adjacent
> parameters, other regimes and increased costs do not destroy the result.)*

Two separate claims, and they fail in different ways:

- **Walk-forward** is about *when* a parameter was chosen. It fails when the choice saw the data it
  is later judged on.
- **Robustness** is about *how narrow* the result is. It fails when the result exists only at one
  parameter value, in one regime, at one cost assumption.

A strategy can pass either alone. The course requires both, and `COMPONENT_REGISTRY_SPEC.md` has a
separate validation status for each: `Out-of-Sample Tested` and `Walk-Forward Tested`.

## 2. The window record

Appendix K, verbatim — twelve fields per window:

```verbatim
Window ID
Train dates
Validation dates
Test dates
Universe snapshot
Parameters selected
Selection rule
Out-of-sample trades
Costs/slippage stress
Result by regime/country
Parameter stability
Decision: keep/revise/retire
```

Three of these are stronger than they look:

**Three date ranges, not two.** `Train`, `Validation` and `Test` are separate fields. That is a
three-way split: parameters are fitted on train, *selected* on validation, and judged on test. A
two-way split lets selection contaminate the out-of-sample period, and selection is where data
snooping actually happens.

**`Selection rule` is a field.** How the parameter set was chosen is recorded alongside what was
chosen. Without it, "we picked the best one" and "we picked the median of the stable plateau" are
indistinguishable in the record, and they are not the same claim.

**`Universe snapshot` is per window.** The universe is a point-in-time fact, re-resolved for each
window (`POINT_IN_TIME_SPEC.md`). A single universe applied across all windows is survivorship bias
wearing a walk-forward costume.

`Result by regime/country` also matters for this project specifically: Canada and the US are never
merged (`BR-9`), so a result must be reported per country, not pooled. A US-driven result presented
as a system-wide one would pass an aggregate check and fail this field.

## 3. The decision is three-valued

The last field is `Decision: keep/revise/retire` — not pass/fail.

| Value | Meaning | Consequence in this system |
|---|---|---|
| keep | the window supports the current parameters | validation status may advance |
| revise | the parameters change | **component version increments, validation status resets** (`COMPONENT_REGISTRY_SPEC.md` §6) |
| retire | the strategy is withdrawn | status `Retired`, which the course distinguishes from `Rejected` |

`revise` is the expensive one, and deliberately so: revising after seeing test results is precisely
the move that turns a walk-forward into an in-sample fit. It is permitted — the course lists it — but
it costs a version bump and a reset, so it cannot be done quietly.

## 4. The six perturbations

Module 73 names each of these as its own topic. Together they are the robustness battery:

| # | Topic | Perturbation | Parameter |
|---|---|---|---|
| 1 | 1095 `Parameter stability` | move each parameter to its neighbours | `validation.parameter_stability_tolerance` |
| 2 | 1103 `Разные рыночные режимы` | re-evaluate per regime, not pooled | `REGIME_SPEC.md` |
| 3 | 1099 `Увеличенное проскальзывание` | raise slippage | `validation.stress_cost_multiplier` |
| 4 | 1100 `Увеличенные комиссии` | raise commissions | `validation.stress_cost_multiplier` |
| 5 | 1101 `Пропущенные сделки` | drop trades that would not have been taken | `validation.missed_trade_rate` |
| 6 | 1102 `Задержка исполнения` | execute later than the signal | `validation.execution_delay` |

Plus two resampling checks that perturb nothing but the arrangement:

| Topic | Check |
|---|---|
| 1096 `Monte Carlo simulation` | resample outcomes to get a distribution rather than a point estimate |
| 1097 `Перестановка последовательности сделок` | permute trade order — drawdown depends on sequence, expectancy does not |

Topic 1097 is worth stating plainly: **shuffling the order of the same trades leaves total R
unchanged and changes maximum drawdown completely.** A drawdown figure from one historical ordering
is one draw from a distribution, and reporting it as *the* drawdown overstates what is known.

## 5. The acceptance rule

Topic 1104, `Критерии устойчивой стратегии`:

> "«Критерии устойчивой стратегии» задаёт pass/fail-критерии. Условия делятся на обязательные,
> подтверждающие и запрещающие; критический запрет не компенсируется большим количеством слабых
> положительных признаков."
>
> *(Sets pass/fail criteria. Conditions divide into required, confirming and prohibiting; a critical
> prohibition is not compensated by a large number of weak positive signs.)*

This is the same non-compensatory rule that governs entries (`FAIL_CLOSED_POLICY.md` §3), applied to
strategy acceptance. Structurally it means the acceptance decision **is not a score**: prohibiting
conditions are evaluated outside any weighted total, and no quantity of confirming evidence clears
one.

Concretely, a strategy that fails the survivorship requirement (`BACKTEST_PROTOCOL.md` §6) does not
become acceptable by being robust on the other five perturbations.

## 6. What the course does not supply

Every quantity in this document is unset:

| Concept | Topic | Parameter |
|---|---|---|
| in-sample / out-of-sample split | 1091, 1092 | `validation.is_oos_split` |
| window length, step, fold count | 1093, 1094 | `validation.walkforward_window` |
| gap between train and test | — | `validation.embargo` |
| stability tolerance | 1095 | `validation.parameter_stability_tolerance` |
| resampling count | 1096, 1097 | `validation.monte_carlo_runs` |
| cost stress multiple | 1099, 1100 | `validation.stress_cost_multiplier` |
| missed-trade rate | 1101 | `validation.missed_trade_rate` |
| execution delay | 1102 | `validation.execution_delay` |

`validation.embargo` has no course topic at all, and is recorded as **authored, not inherited**. It
exists because a train window ending the day a test window begins leaks through any feature with a
lookback: an indicator computed on the first test bar reads bars that were in train. The course's
`временное разделение` implies a separation; it does not specify a gap. This project adds one and
says so.

## 7. Open items

- [ ] Whether windows roll (fixed length, sliding) or anchor (growing train set). Topic 1094 names
      `Rolling-window тест` specifically, which argues for rolling; anchored uses more data. Decide
      with the first real study, and record the choice in the pre-registration, not after.
- [ ] Whether `Result by regime/country` requires a minimum sample **per cell**. Regime breakdowns
      shatter a small sample into cells too thin to read, and a per-cell verdict on four trades is
      noise presented as a finding.
- [ ] How `Monte Carlo simulation` resamples — trade outcomes, returns, or blocks. Block resampling
      preserves autocorrelation; i.i.d. resampling assumes it away. They answer different questions.
