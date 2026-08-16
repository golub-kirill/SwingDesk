# GLOSSARY

**Status:** drafting · **Tier:** 0 (charter) · **Content:** `verbatim`

<!-- verbatim-sources: Appendix_A_Slovar_terminov_v2.0.pdf -->

**Source:** `Appendix_A_Slovar_terminov_v2.0.pdf` pages 2–3, verified 2026-08-01.

35 terms. These definitions are **the** definitions: identical wording in code identifiers, database
columns, UI labels and documents. Where a term also names a controlled-vocabulary value
(`Setup`, `Trigger`, `Watchlist`), the value is never translated — Production Rules §3.9.

---

## Terms

```verbatim
Average True Range; измеритель типичного истинного диапазона, не направления.
Лучшая доступная цена немедленной покупки.
Лучшая доступная цена немедленной продажи.
Ширина участия акций в движении индекса.
Выход цены из значимой структуры с попыткой удержания.
Влияние валюты на стоимость и риск американских позиций канадского счёта.
Событие, способное изменить ожидания и торговую активность.
Качество решения независимо от P&L.
Цена × объём; грубая оценка денежной ликвидности.
Снижение капитала от предыдущего пика.
Допустимый диапазон исполнения, а не одна магическая цена.
Средний ожидаемый результат сделки на серии.
Разрыв между предыдущей торговой областью и новым открытием.
Условие, при котором гипотеза больше не действительна.
Способность исполнить нужный размер без чрезмерного влияния на цену.
Максимальное движение против позиции за время сделки.
Последняя допустимая цена; выше/ниже неё сделка Late.
Максимальное движение в пользу позиции за время сделки.
Устойчивость и скорость направленного движения.
Суммарный remaining worst-case риск открытых позиций.
Данные, действительно доступные на момент исторического решения.
Контролируемое движение против основного импульса.
Единица планового риска конкретной сделки.
Сравнительное поведение инструмента относительно benchmark.
Группа позиций с общим экономическим фактором риска.
Потенциальная структура сделки до появления trigger.
Разница между ожидаемой и фактической ценой исполнения.
Разница между ask и bid.
Заранее определённое условие защитного выхода.
Искажение от исключения исчезнувших инструментов из истории.
Выход при отсутствии ожидаемого развития за заданное время.
Измеримое событие, разрешающее действие.
Масштаб и скорость колебаний.
Структурированная очередь кандидатов со статусами и действиями.
```

| Термин | Рабочее определение |
|---|---|
| `ATR` | Average True Range; измеритель типичного истинного диапазона, не направления. |
| `Ask` | Лучшая доступная цена немедленной покупки. |
| `Bid` | Лучшая доступная цена немедленной продажи. |
| `Breadth` | Ширина участия акций в движении индекса. |
| `Breakout` | Выход цены из значимой структуры с попыткой удержания. |
| `CAD/USD exposure` | Влияние валюты на стоимость и риск американских позиций канадского счёта. |
| `Catalyst` | Событие, способное изменить ожидания и торговую активность. |
| `Decision Quality` | Качество решения независимо от P&L. |
| `Dollar volume` | Цена × объём; грубая оценка денежной ликвидности. |
| `Drawdown` | Снижение капитала от предыдущего пика. |
| `Entry zone` | Допустимый диапазон исполнения, а не одна магическая цена. |
| `Expectancy` | Средний ожидаемый результат сделки на серии. |
| `Gap` | Разрыв между предыдущей торговой областью и новым открытием. |
| `Invalidation` | Условие, при котором гипотеза больше не действительна. |
| `Liquidity` | Способность исполнить нужный размер без чрезмерного влияния на цену. |
| `MAE` | Максимальное движение против позиции за время сделки. |
| `Maximum entry` | Последняя допустимая цена; выше/ниже неё сделка Late. |
| `MFE` | Максимальное движение в пользу позиции за время сделки. |
| `Momentum` | Устойчивость и скорость направленного движения. |
| `Open risk` | Суммарный remaining worst-case риск открытых позиций. |
| `Point-in-time data` | Данные, действительно доступные на момент исторического решения. |
| `Profit factor` | Gross Profit / Gross Loss. |
| `Pullback` | Контролируемое движение против основного импульса. |
| `R` | Единица планового риска конкретной сделки. |
| `Relative strength` | Сравнительное поведение инструмента относительно benchmark. |
| `Risk bucket` | Группа позиций с общим экономическим фактором риска. |
| `Setup` | Потенциальная структура сделки до появления trigger. |
| `Slippage` | Разница между ожидаемой и фактической ценой исполнения. |
| `Spread` | Разница между ask и bid. |
| `Stop-loss` | Заранее определённое условие защитного выхода. |
| `Survivorship bias` | Искажение от исключения исчезнувших инструментов из истории. |
| `Time stop` | Выход при отсутствии ожидаемого развития за заданное время. |
| `Trigger` | Измеримое событие, разрешающее действие. |
| `Volatility` | Масштаб и скорость колебаний. |
| `Watchlist` | Структурированная очередь кандидатов со статусами и действиями. |

## Notes

**Three definitions are computable and therefore binding on code, not just prose:**

- `Dollar volume` = `Цена × объём`. Used by the liquidity filter and the ADTV cap.
- `Profit factor` = `Gross Profit / Gross Loss`.
- `Open risk` = `Суммарный remaining worst-case риск открытых позиций` — **remaining**, and
  **worst-case**, which is why `RISK_SPEC.md` recomputes it after every partial and stop change
  rather than decrementing.

**One inconsistency, minor but real.** Appendix A gives `Profit factor` as `Gross Profit / Gross
Loss`; Appendix D gives `Gross profit / |Gross loss|`. The absolute value is present in the formula
sheet and absent in the glossary. Appendix D is the computational source
(`STATISTICS_SPEC.md`), so the implementation takes the absolute value. Recorded rather than
silently resolved.

**Two definitions are requirements on the data layer, not vocabulary:**

- `Point-in-time data` = *"Данные, действительно доступные на момент исторического решения"* — the
  course requires point-in-time correctness by definition, which is why `POINT_IN_TIME_SPEC.md` is
  mandatory and not an optimisation.
- `Survivorship bias` = *"Искажение от исключения исчезнувших инструментов из истории"* — the
  course names the exact defect that the free data path cannot avoid. See
  `docs/adr/ADR-0001-market-data.md` condition 6: accepted, declared, stamped.

**`Maximum entry`** defines the `LATE` skip code operationally: *"Последняя допустимая цена;
выше/ниже неё сделка Late."* Note it is two-sided — above for longs, below for shorts.

## Ambiguous terms

Master ТЗ v1.0 §11 requires this section and `SPEC_GAP_ANALYSIS.md` recorded its absence. Every
entry below is a collision **this tree has already hit**, not a hypothetical — each one cost a
document, a rename or a defect, and the citation is where it was paid for.

The rule: where one word means two things, the two live in **separate columns** and code never
compares across them.

| Term | Meaning A | Meaning B | Kept apart by |
|---|---|---|---|
| **event** | something that happened in the *market* — `EVENT_SPEC.md`, M34/M40 catalysts | something that happened in the *system* — the ТЗ's §16 object | the ТЗ's object was **renamed** to *transition* (`TRANSITION_SPEC.md` §1) |
| **Watch · Trade · Skip** | three of the four candidate-decision states | three of the nine watchlist statuses | separate columns `decision` and `watchlist_status` (`DECISION_STATE_MACHINE.md` §3) |
| **Late** | a watchlist status | a skip code (`CODES.md`) | as above — same words, different enums |
| **risk** | what is at risk: `Σ position remaining risk` | position *value*: `Shares × Entry` | Appendix C's own control cell — `Не равно риску` (`RISK_SPEC.md` §2) |
| **validated** | a parameter's provenance, of the form `validated:<evidence-id>` | a component's validation status, one of nine | two ladders; a decision record never produces either (`decisions/README.md` §3). **No parameter currently holds it** — `regime.classifier_rule` was the only one and became `assumed:PR-002` on 2026-08-16, so this row's example is deliberately a form rather than a live id |
| **expectation** | the *definition* — a formula in `STATISTICS_SPEC.md` | an *estimate* — a number from a sample | `EXPECTATION_MODEL.md` §1, the estimate/definition split |
| **coverage** | universe coverage — instruments measured | ТЗ coverage — FULL/PARTIAL/ABSENT | plus **survivorship coverage** (`EvidenceRecord`) and test coverage. Four meanings; always qualify |
| **active** | a component's activation state | a position that is open | `COMPONENT_REGISTRY_SPEC.md` §3 vs `Position.is_open` |
| **drift** | five families with different responses | — | never aggregated into one score (`DRIFT_AND_LEARNING.md` §6) |
| **run** | the daily pipeline run | a study run, or a replay | `RunMode` on the manifest (`SYSTEM_MODES.md`) |

**The one that is not a naming problem.** `unavailable` and `fail` are different **claims**, not
different words for one thing: a gap in the *system* and a fact about the *trade*
(`contracts/checklist.py`, `HANDOFF.md` §7). Collapsing them is the most damaging error this product
can make, and it is listed here because it presents as a vocabulary question and is not one.

## Discouraged synonyms

The course bans four adjectives outright in decision logic — *smart*, *strong*, *quality*,
*confirmed* — unless reduced to an observable rule or explicitly reserved for human review
(`LIFECYCLE_AND_LAYERS.md` §2, layer 3). A field named for one of them must resolve to a stated rule.

Project-specific, and each has a preferred term:

| Do not write | Write | Why |
|---|---|---|
| signal | **trigger** (the event) or **setup** (the conditions) | the course separates them and "signal" collapses both |
| filter passed | **admissible** | a filter's output is admissibility, not approval |
| score | name the **effect class** — `SOFT_FACTOR` contribution | a bare score invites clearing a gate with it (`RULE_SPEC.md` §5) |
| the model says | name the **component and version** | `REQ-OUTPUT-001` |
| edge | **expectancy**, with its sample and window | "edge" has no definition and no units |

## Open items

- [ ] Terms used throughout the course but absent from Appendix A and needing project definitions:
      `regime`, `setup quality`, `process score`, `risk-off ladder`, `run`, `snapshot`,
      `knowledge time`. Add them as project-defined and mark them as such — they are ours, not the
      course's.
