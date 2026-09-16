# DR-046: Monthly and quarterly bars are rolled up from daily bars by calendar period

```
date:            2026-09-16
status:          accepted — ratified by the owner 2026-09-15 in the same ruling as DR-045: "add and
                 ratify 1M/3M", answered "both" when asked whether that meant minutes or months
parameters:      none
components:      none new. M29-T0427 (monthly context) stays registered - see section 4
implemented_by:  src/swingdesk/market_data/periods.py :: def roll_up_daily
```

## 1. What the owner ruled

Asked whether *1M/3M* meant minute resolutions or month-scale context, the owner answered **both**.
`DR-045` is the minute half. This is the other: a one-month and a three-month view above the daily
decision, which `CONSTRAINTS` D9 already names (*1Y/3M context → 1D decision*) and which the course
opens its top-down analysis with.

## 2. What is built

**One bar per calendar month or calendar quarter, from the daily bars already stored.**
`market_data.periods.roll_up_daily` groups one instrument's daily bars by the period their session
falls in: the open is the first session's, the close the last session's, the high and low are the
period's extremes, volume is the sum. Nothing is fetched and nothing is stored.

**Calendar periods, not rolling session counts.** A monthly chart's candle is a calendar month, 19 to
23 sessions long. A rolling 21-session window is a different object — a reading of the daily
series — and a consumer that wants one computes it there. No session count is set, so no parameter
is introduced.

## 3. A period is a fact only once it has closed

A monthly candle read in the middle of the month has a high, a low and a close that are still
moving. Reading it as settled is look-ahead, and nothing in the bar would show it. So:

* **Only complete periods are returned by default.** Complete is MEASURED: the period holds a daily
  bar for every session the exchange calendar says it had.
* **A past month missing one daily bar is incomplete too.** That is a gap in the data, and it is
  said as one rather than silently summed.
* `include_partial=True` returns the others as well, each carrying `complete = False` and both
  counts, for a consumer that wants the forming candle and knows it is forming.
* **Refused outright:** a period other than month or quarter, bars that are not daily (a month built
  from intraday bars would be a second definition of the same month — `DR-045` is the intraday
  path), bars of more than one instrument, and a session given twice.

## 4. What the course says, and what this does not decide

Course module 29, *Анализ сверху вниз*, lays the ladder out as twelve topics, all `registered` and
none implemented until now. **This record builds data for the first rung and decides no reading of
it.**

| topic | title | what this record does |
|---|---|---|
| `M29-T0427` | Месячный контекст | builds the monthly bar; the context READING stays registered |
| `M29-T0428` | Недельный тренд | nothing — weekly is not in the owner's ruling |
| `M29-T0429` | Дневной сетап | nothing — an untested hypothesis |
| `M29-T0430` | Четырёхчасовое подтверждение | nothing — see below |
| `M29-T0431` | Часовой триггер | `DR-045` builds the hourly bar |
| `M29-T0432` | Внутридневное исполнение | `DR-045` builds the minute rungs |
| `M29-T0436` | Конфликт таймфреймов | nothing |
| `M29-T0437` | Слишком большое количество таймфреймов | nothing — and worth reading before adding more |

**What a monthly bar SAYS about direction is `M29-T0427`'s definition**, and the course PDFs are not
in this repository. Implementing that reading from a guess would be authoring a threshold under the
course's name (`AGENTS.md` §8). It stays registered until the text is read or a pre-registered study
defines it.

**Three things the ruling did not cover, recorded so they are not decided by omission:**

1. **The quarter is not in the course's ladder.** Module 29 names month, week, day, four hours, one
   hour and intraday. The three-month view comes from `CONSTRAINTS` D9, so it is this project's own
   rung.
2. **The week is in the course's ladder and not in the ruling.** A weekly bar is the same roll-up
   with a different period, and adding it is one word plus a decision.
3. **Four hours does not tile a US session.** A regular session is 390 minutes, so a 240-minute bar
   leaves a 150-minute remainder every day. `DR-045` does not build it, and building it means
   choosing between two unequal bars a day, a 2-hour ladder, or bars that cross sessions.

## 5. What would overturn this

* **The course defining monthly context as something other than calendar-month candles** — a rolling
  window, say. Then `M29-T0427`'s reading consumes the daily series directly, and this roll-up stays
  what it is: the monthly chart.
* **A vendor's own monthly bar disagreeing with the roll-up** on a complete month. The comparison is
  one request; until it is made, this record claims equality of construction, not of the vendor's
  arithmetic.
