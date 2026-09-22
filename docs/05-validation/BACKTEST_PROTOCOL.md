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

## 6. Survivorship: a repair this project can run, and from 2026-09-20 must

**RULED 2026-09-20 (`DR-047` §3.9), and it changes this section's title.** A pre-registration whose
population is INDIVIDUAL EQUITIES must read a universe that includes delisted names, or carry
`REFUSED` in its own decision rule. `survivorship: ABSENT` stops being a disclosure a study may
choose. The remedy is the fetch described below - 19,188 inactive assets this project already has
credentials for - and the sentence further down that calls a paid vendor "the only remedy" was
already refuted on 2026-09-05 by measurement.

**ETF-only studies are exempt**, and the reason is structural rather than a concession: a fund's
provider maintains its own constituents, so a fund that trades today traded under the same ticker
with the same mandate, and the survivorship question does not arise at the fund level.
`RETURN_SOURCE_REGISTER.md` §2.3 records which studies rely on that exemption.

### 6a. The section as it stood, kept because the history is the argument

The course requires delisted instruments (topic 1084, and the `Пропуски` stage). ~~**No free data
source provides them**~~ — that was established by measurement (`DATA_QUALITY_SPEC.md`): Yahoo
returns zero rows for a delisted ticker; Questrade resolves the symbol as a non-tradable stub whose
candle endpoint returns `code 1019`.

**REFUTED 2026-09-05, and this section was the last document still carrying it.**
`tools/probe_alpaca_delisted.py` enumerated **19,188** inactive US equity assets and asked Alpaca
for daily bars on eight of them: **seven returned a full daily path**, from 2016-01-04 on
`feed=sip`. The correction reached `EVIDENCE_RECORD_SPEC.md`, `REGIME_SPEC.md` §133,
`SUCCESS_AND_KILL_CRITERIA.md` and `EVIDENCE_SUMMARY.md` §3 on the day, and did not reach here for
two days — which is `AGENTS.md` §11 working exactly as it should and being caught late.

**What changes and what does not.** The remedy is no longer *"a paid vendor, and that is a budget
decision"*: it is a fetch this project already has credentials for. What has NOT changed is that
nobody has run it — no study's universe has been repaired, so every consequence below stands
unaltered until one is. **The bias is now measurable and unmeasured, which is a different sentence
from unmeasurable**, and a study that reports `survivorship: ABSENT` today is reporting a choice
rather than a limit. Three limits on the refutation itself are in the probe's own docstring; the
first — whether SIP history is a free-tier entitlement or an attribute of this account — is the one
to settle before anything is built on it.

### 6c. MEASURED 2026-09-21, and the repair is a sixth of the problem rather than the whole of it

Three measurements, all zero-trial, and together they replace the headline this section carried for
sixteen days.

**The entitlement question is settled** - the probe's own first limit, *"whether SIP historical is
a free-tier entitlement or an attribute of this account"*. Alpaca's subscription table, read
2026-09-21: the **Basic** plan is free, is the default for both paper and live accounts, serves
**historical data since 2016**, withholds only **the latest 15 minutes**, and allows **200
historical calls a minute**. So the entitlement is everybody's, the 2016 floor is everybody's, and
200 a minute is the pace any repair must hold.

**The 19,188 is real and it is not the tradable universe**
(`docs/decisions/measurements/delisted-universe-2026-09-21.json`):

| | |
|---|---|
| inactive US equity assets | **19,175** |
| on a real exchange, alphabetic ticker | **1,973** |
| distinct symbols among them | 1,966 |
| symbols reissued to a LIVING asset | **189** |
| clean - one ticker, one company | **1,770 (90%)** |

**A ticker is not an identity**, and 189 dead tickers now belong to listed companies. The bars
endpoint is keyed by symbol, so one request for such a name returns a series spliced out of two
businesses, reaching all the way to today - **the survivorship bias this repair exists to remove,
reintroduced by the repair itself**. `SEMG` is the worked example: 1,147 daily bars to 2025 for a
company acquired in 2019.

**And the broker remembers about one delisting in six**
(`docs/decisions/measurements/edgar-coverage-2026-09-21.json`). SEC EDGAR is the independent
census: 43 quarterly indexes list **20,644** Form 25 and 25-NSE filings over 2016-2026, of which a
stratified sample of 860 says **36.6% concern common stock** - implying about **7,554** company
delistings. Against that:

**ALPACA REMEMBERS 16.3% of them [12.2%, 20.4%].** (Stated as a paragraph and not as a
blockquote, deliberately: in a document declaring `verbatim-sources` every markdown blockquote is
checked against the course PDFs by gate 2, so a MEASUREMENT set in that form is a measured number
wearing the source material's authority. It was written as one on 2026-09-21 and gate 2 rejected it
the same day - and CI could not have, because the course PDFs exist only on the owner's machine,
which is the one gate `actions/checkout` can never run.)

The unmatched names were checked by hand rather than assumed: `SolarWinds`, `PMC Sierra`,
`Rubicon Minerals` and `Skystar Bio-Pharmaceutical` are absent from the broker's list entirely,
active and inactive alike, so the gap is a real gap and not a name-matching artefact.

**What that does to `DR-047` §3.9**, which made a repaired universe a blocker for stock studies:
the repair available here **removes about a sixth of the survivorship bias, not all of it**. A study
can satisfy §3.9 to the letter while five sixths of the bias remains. So a stock study reading the
repaired universe writes `survivorship: PARTIALLY REPAIRED - 16.3% of the SEC census [12.2, 20.4]`
and never `survivorship: REPAIRED`. **That is a smaller claim, and it is the one the evidence
supports.**

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

### 6d. A session missing INSIDE a hold — asked 2026-09-21, and it is not a problem here

**The question, and it is the backtest's version of a live defect found the same day.** `DR-050`
records that the live book kept every winner and dropped every loser because a stop-out settled an
order it could not name. The engine has the same SHAPE of exposure: `run_arm` walks the STORED
bars, so a session the vendor refused is simply absent, and a stop that would have triggered on it
never triggers. A position survives a day it should not have. **That asymmetry favours the
survivor, which is the direction that flatters.**

**Measured rather than argued.** A seeded sample of 400 instruments drawn across the whole bar
store, counting calendar sessions between each instrument's own first and last stored bar - so a
listing or a delisting is not counted as a gap:

| | |
|---|---|
| instruments measured | **366** |
| **with ZERO missing sessions** | **363** |
| instrument-sessions inside their own spans | 487,714 |
| with no stored bar | **104 — 0.021%** |

**101 of the 104 belong to `PCG$B`**, a preferred share. A second sample drawn a different way
found the same concentration in `BCV$A`, also preferred. Among ordinary common stocks the whole
decade holds **three** missing sessions, across `ALP` and `FISV`.

**So the exposure is real in principle and empty in practice**, and the reason is structural rather
than lucky: the names that lose sessions are `$`-suffixed preferred issues, which the universe rule
does not admit. Recorded so the question is closed with a number instead of being asked again.

### 6e. An uncorrected SPLIT in the store — found 2026-09-21, real, and outside the admitted universe

**The store can hold a split discontinuity, and this is what one looks like.** `AIXI`, straight
from the owner's own bar store:

```
2026-09-04   0.472
2026-09-08   3.260      <- +590% in one session
```

0.472 x 7 = 3.30. It is a 1-for-7 reverse split, read as a return by anything that reads the series.
**Its `corporate_actions` rows are empty**, so nothing can detect or correct it - and store-wide only
**7 instruments of 13,140** carry any action record at all.

**The mechanism**, and it explains why this is bounded. `refresh_universe` re-fetches the admitted
universe every evening, and the vendor back-adjusts the WHOLE history for a split on each fetch - so
an admitted name's basis is rewritten and stays current. A name that leaves the universe stops being
re-fetched: `AIXI`'s last stored session is **2026-09-11** against the store's **2026-09-18**. Its
history froze on the pre-split basis, and the one bar fetched after the split sits on the new one.

**Measured against an independent vendor**, because the store's own consistency cannot answer this.
Stored closes were compared with Alpaca's daily bars at `adjustment=split` - a different vendor, a
different adjustment pipeline - over 2026-06-01..2026-09-18, on names the universe could admit
(median close at or above the $5 floor):

| sample | same basis | different basis |
|---|---|---|
| 59 drawn at random | **59** | 0 |
| 45 chosen because they CARRY a split-shaped jump since 2024 | **45** | 0 |

**104 of 104.** The hazard is real and its current impact on the studies is zero, because the names
that hold a stale basis are the ones the price floor already excludes.

**A first attempt at this measurement was wrong and is recorded rather than quietly replaced.**
Scanning the store alone for one-day moves near a round ratio reported *"29,365 split-shaped moves
across 534 instruments"* - about fifty-five per instrument, which is absurd on its face. With 74,273
big one-day moves in the window, a 2% tolerance around 2x catches coincidence far more often than
splits, and `JAGX`'s correctly-adjusted 2017 price of 74 billion is what a long chain of reverse
splits looks like rather than a defect. **The detector had to be the independent vendor, not the
store's own shape.**

**What makes it bite, so the trigger is written down:** a study reading a name that left the
admitted universe and split afterwards. `TODO` §1 already carries the guard that would catch the
rewrite - *"a restated close is detected and printed, and nothing REFUSES on it"* - and this is the
measurement of what that open item is currently costing: nothing yet.

## 6b. The order of operations — `DR-047` §3.8

```
gross signal -> risk-adjusted signal -> out of sample -> cost robustness -> execution -> implementation
```

**`out of sample` means a DECLARED window from 2026-09-21** (`DR-049` §4.2). A study names the
span it will not read before it runs, the runner bounds itself to exclude it, and opening it later
is a second registration. `PR-036` read an untouched decade and is the precedent - but it did so
after `PR-034` reported, and a holdout chosen after the fact cannot be told from one chosen before.

**And the stage after cost robustness now carries a FACTOR reading** (`DR-049` §4.1): the alpha the
five Fama-French factors plus momentum cannot explain. It vetoes nothing and it renames one thing -
a return the factors explain is an exposure, not a skill.

Execution research on an unproven signal answers *"how cheaply can I trade something that may be
worth nothing"*. `PR-024`, `PR-025` and `PR-030` did exactly that, and their findings stand -
`PR-024`'s 29 bps a trade is the largest single improvement this programme has measured. What is
ruled out is doing that work FIRST: a source establishes itself gross, survives an untouched
window, and survives an adverse cost assumption, and only then is the fill worth optimising.

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
- [x] ~~Whether a backtest may run at all while `validation.backtest_min_trades` is unset.~~
      **Moot since the parameter was set**, and left here as a closed item rather than deleted
      because the answer it reached is the live rule: `validation.backtest_min_trades` is
      `assumed:DR-007` at 200 primary / 60 holdout per arm, and PR-012 did exactly what this line
      predicted - it ran, observed 181 to 203 trades, and refused a VERDICT rather than the run.
      Closed 2026-09-21; the open question underneath it was the sample ceiling, which
      `registry/cards.yml` carries as `the-capacity-cap-caps-the-sample`.
- [ ] Cost model shape. `costs.commission_model` and `costs.slippage_model` are named as models
      rather than scalars because a flat per-trade commission and a spread-proportional slippage are
      different functions, and the course names both concepts without choosing either.
