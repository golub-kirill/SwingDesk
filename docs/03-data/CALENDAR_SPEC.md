# CALENDAR SPEC

**Status:** drafting · **Tier:** 3 (data) · **Content:** authored on measured evidence

<!-- verbatim-sources: Appendix_T_Professionalnyi_chek_list_treidera_v2.0.pdf, Module_33_Skrinery_v5.0.pdf -->

---

## 1. The timeframe stack

Authoritative statement, Appendix T's conclusion:

> "Основной рабочий график — 1D; 1Y и 3M задают контекст, 30D формирует план, 30m только исполняет."

Plus the owner's `1H` confirmation layer (D9), which is an **extension beyond the course** — the
sentence above does not mention it.

| Layer | Resolution | Role |
|---|---|---|
| `1Y`, `3M` | windows over **daily** bars | context |
| `30D` | window over **daily** bars | plan formation |
| `1D` | daily bars | **the decision timeframe** |
| `1H` | hourly bars | confirmation / trigger (owner extension) |
| `30m` | half-hour bars | execution only — never originates a setup |

`1Y`, `3M` and `30D` are **not resolutions**. They are windows. Only three series are stored:
`1d`, `1h`, `30m` — independently, never derived from one another (`ADR-0001`).

## 2. Two exchanges, two calendars — enumerated

NYSE and TSX both trade 09:30–16:00 ET, which makes them look interchangeable. They are not.

Measured with `tools/probe_calendar.py` over `2023-09-06 … 2026-07-31`:

| | |
|---|---|
| Sessions with US data | **728** |
| Sessions with CA data | **730** |
| Sessions in both | 714 |
| **US open, CA closed** | **14** |
| **CA open, US closed** | **16** |
| **Gross divergence** | **30 sessions** |

**The net figure is dangerously misleading.** The bar-count difference is 16 bars ≈ 2 sessions net,
and an earlier draft of this document reported that as the divergence. It is not: netting hides
93% of it. **30 sessions** exist where exactly one market traded, and each is a session where a
cross-market computation would silently compare a real bar to nothing.

**US open, CA closed** — Canadian holidays: Canadian Thanksgiving (2023-10-09, 2024-10-14,
2025-10-13) · Boxing Day (2023-12-26, 2024-12-26, 2025-12-26) · Victoria Day (2024-05-20,
2025-05-19, 2026-05-18) · Canada Day (2024-07-01, 2025-07-01, 2026-07-01) · Civic Holiday
(2024-08-05, 2025-08-04).

**CA open, US closed** — US holidays: US Thanksgiving (2023-11-23, 2024-11-28, 2025-11-27) · MLK
Day (2024-01-15, 2025-01-20, 2026-01-19) · Memorial Day (2024-05-27, 2025-05-26, 2026-05-25) ·
Juneteenth (2024-06-19, 2025-06-19, 2026-06-19) · Independence Day (2024-07-04, 2025-07-04,
2026-07-03) · **2025-01-09**, an unscheduled NYSE closure.

That last date matters more than the others: it is not on any recurring holiday list. **A calendar
built from a rule rather than a record would have missed it.**

The course already forbids merging the two:

> "Запрещено смешивать USA и Canada без отдельных индексов или игнорировать sector/risk-bucket
> concentration."

**Requirement:** separate calendars per exchange, always. Any operation aligning a US and a Canadian
series must join on timestamp and tolerate missing sessions on either side — never assume index
alignment, never forward-fill across a foreign holiday.

## 2b. Half-days — measured, and they lose the close

Confirmed at `1h`, where history is deep enough (`30m` reaches only ~60 trading days):

| Date | US | CA |
|---|---|---|
| 2023-11-24 | **3 bars** `09:30–11:30` | 7 bars (full) |
| 2024-07-03 | **3 bars** | 7 bars (full) |
| 2024-11-29 | **3 bars** | 7 bars (full) |
| 2024-12-24 | **3 bars** | **3 bars** |
| 2025-07-03 | **3 bars** | 7 bars (full) |
| 2025-11-28 | **3 bars** | 7 bars (full) |
| 2025-12-24 | **3 bars** | **3 bars** |

Two findings:

1. **Half-days rarely coincide.** Of seven US early closes, only the two Christmas Eves are also
   short on TSX. A shared half-day is the exception.
2. **The session close is missing from the intraday series.** A 13:00 ET close yields bars at
   `09:30`, `10:30`, `11:30` — covering 09:30–12:30. The final 12:30–13:00 half-hour **is not
   returned**. So on a half-day the last intraday close is a 12:30 price, while the daily bar closes
   at 13:00.

**Consequence:** any component that treats "last intraday close" as "session close" is wrong on
those days, and wrong silently. Where a component needs the session close it reads the **daily**
series, never the last intraday bar.

### The stub is kept on regular sessions and dropped on early closes

Found while implementing `ExchangeSession.expected_bars`. At `1h`:

| Session | Duration | Full hours | Stub | Calendar says | Yahoo returns |
|---|---|---|---|---|---|
| regular | 6.5 h | 6 | 30 min | 7 | **7** — stub kept |
| early close | 3.5 h | 3 | 30 min | 4 | **3** — stub dropped |

Consistent across all five measured half-days (2023-11-24, 2024-07-03, 2024-11-29, 2024-12-24,
2025-07-03, 2025-11-28, 2025-12-24). **The reason is unknown**; the behaviour is not.

At `30m` the question does not arise — both 390 and 210 minutes divide evenly, so there is no stub
either way.

**Architectural consequence, and it matters:** the calendar returns **session truth** and must not be
bent to match a vendor. If it were, it would stop being an independent check — which is the entire
reason `ADR-0002` adopts it. Vendor quirks live in the `market_data` adapter as a **vendor profile**:

```
expected_from_calendar(session, interval)      -> session truth
vendor_profile.adjust(expected, session, ...)  -> what THIS vendor will actually return
```

Comparing raw calendar expectation against Yahoo's actual counts would raise `DATA` on **every
half-day** — precisely the false-positive flood `ADR-0002` was adopted to avoid.

## 2c. Short sessions are indistinguishable from vendor gaps

The same probe found three sessions that are **not** exchange half-days:

| Date | US | CA |
|---|---|---|
| 2026-01-30 | 2 bars `09:30–10:30` | 2 bars `09:30–10:30` |
| 2026-02-02 | 3 bars **`13:30–15:30`** | 3 bars **`13:30–15:30`** |
| 2025-04-24 | full | 3 bars `13:30–15:30` |

Two of these truncate **both exchanges identically**, and one *starts* at 13:30 — no exchange
schedule does that.

**Confirmed as vendor gaps by cross-checking Yahoo against itself.** Every suspect date has a
**normal daily bar**, so the market was open:

| Date | Instrument | Daily volume | Σ intraday volume | ratio | bars | daily close | last 1h close |
|---|---|---|---|---|---|---|---|
| 2026-01-30 | AAPL | 92,443,400 | 19,006,396 | **0.21** | 2 | 259.48 | **254.92** |
| 2026-01-30 | CNQ.TO | 5,517,400 | **16,838** | **0.003** | 2 | 50.63 | 50.34 |
| 2026-02-02 | AAPL | 73,913,400 | 20,132,165 | 0.27 | 3 | 270.01 | 269.96 |
| 2025-04-24 | CNQ.TO | 5,695,300 | 2,447,587 | 0.43 | 3 | 40.69 | 40.70 |
| *control* 2026-01-29 | AAPL | 67,253,000 | 31,998,989 | 0.48 | 7 | 258.28 | 258.17 |
| *control* 2026-02-03 | CNQ.TO | 6,255,300 | 2,976,990 | 0.48 | 7 | 51.11 | 51.12 |

`CNQ.TO` on 2026-01-30 carries **0.3% of its daily volume** across two bars — unambiguously broken
data, not a short session. `AAPL` the same day is missing $4.56 of close movement between its last
hourly bar and the daily close.

**But this does not solve the classification problem**, and it is important to say why. A missing
session and a closed market still have the same signature in the intraday series. What the daily
series adds is *evidence the market was open* — which is only decisive because the daily series is
independently more complete. It narrows the ambiguity; it does not remove it, because a genuine
half-day also produces a daily bar with reduced volume and a short intraday session.

This is the root cause behind the half-day risk, and it generalises:

1. An unhandled short session is an off-by-N in every intraday aggregate.
2. It cannot be detected by counting bars, because a normal half-day counts short too.
3. A vendor gap must raise `DATA` and block decisions; a half-day must not.
4. Distinguishing them requires knowing whether the market was open.
5. **Nothing in the system knows that independently of the vendor.**

**Requirement, promoted from an open item: an authoritative exchange calendar, independent of the
bar data.** Without it, `DATA` is either raised on every half-day (crying wolf until the operator
ignores it) or never raised on a gap (trading on a truncated session). Deriving the calendar from
observed bars is self-referential and cannot work.

Until such a calendar exists, the honest fallback is: **any session whose bar count differs from the
exchange's modal count is `DATA`-skipped**, accepting false positives on genuine half-days rather
than trading through a gap. That is the fail-closed direction.

## 2d. Volume does not reconcile, even on good days

A tempting completeness check — "does the sum of intraday volume equal daily volume?" — **does not
work**, and would produce constant false alarms if used naively.

Measured ratios of Σ(hourly volume) to daily volume, across both instruments:

| Session type | Observed range |
|---|---|
| normal | 0.366 – 0.824 |
| genuine half-day | 0.160 – 0.749 |
| confirmed vendor gap | 0.003 – 0.677 |

**The three ranges overlap almost completely.** Volume ratio classifies nothing. A half-day at 0.749
is *higher* than a normal session at 0.366, and a confirmed gap at 0.677 sits inside the normal
band.

Consequences for `DATA_QUALITY_SPEC.md`:

- **Never** gate on `Σ intraday == daily`. It is false on every session — the daily figure is
  consolidated and includes activity the regular-hours bars do not carry.
- **Never** gate on the ratio alone. Measured, it separates only catastrophic loss: `CNQ.TO` at
  **0.003** against its own ~0.48 norm is two orders of magnitude out and unmistakable. Everything
  between 0.16 and 0.82 is uninformative.
- Comparison must be **per instrument against its own history**, and only an extreme outlier counts.

### What each signal can and cannot detect

| Signal | Detects | Blind to |
|---|---|---|
| bar count ≠ modal | any truncation | cannot separate half-day from gap |
| daily close vs last intraday close | **end**-truncation (missing final bars) | start-truncation — 2026-02-02 starts at 13:30 and its diff is +0.05 |
| volume ratio | catastrophic loss only | everything else; ranges overlap |
| daily bar exists | market was open | says nothing about intraday completeness |

**No single signal classifies a short session, and neither does the combination.** Each is blind
where another sees, but none distinguishes a legitimate half-day from a gap — which is precisely
the distinction that decides whether to raise `DATA`. This is the measured case for §2c's
requirement.

## 2e. The half-day close discrepancy, quantified

From §2b, a half-day's final half-hour is absent. Measured:

| Date | Instrument | daily close | last 1h close | difference |
|---|---|---|---|---|
| 2025-11-28 | AAPL | 278.85 | 277.05 | **1.80** (~0.65%) |
| 2025-12-24 | AAPL | 273.81 | 275.36 | **1.55** (~0.57%) |
| 2025-12-24 | CNQ.TO | 45.07 | 45.36 | 0.29 (~0.64%) |

Roughly **0.6% in both directions**. That is larger than many of the thresholds this system will
compare against, so it is not a rounding concern — a component reading "last intraday close" as the
session close on a half-day is materially wrong, in an unpredictable direction.

**Rule:** the session close comes from the daily series. Always.

## 3. Session and bar boundaries

Measured from Yahoo, both markets identical, timestamps in `America/New_York`:

| Interval | Bars/session | Times |
|---|---|---|
| `30m` | **13** | `09:30 10:00 10:30 11:00 11:30 12:00 12:30 13:00 13:30 14:00 14:30 15:00 15:30` |
| `1h` | **7** | `09:30 10:30 11:30 12:30 13:30 14:30 15:30` |

Regular trading hours only. No pre- or post-market contamination on either interval.

### The 6.5-hour problem

A 6.5-hour session does not divide into whole hours. The final `1h` bar (`15:30`) covers only 30
minutes — a **trailing stub**.

**Convention: anchor at the open, accept a trailing stub.** `09:30`-anchored, so bars are
09:30–10:30 … 14:30–15:30, and 15:30–16:00 is a half-length bar.

This is not a choice we made — it is what the vendor already does, and adopting it means no
resampling and no chance of a mismatch between our bars and theirs. It must be **stated** rather than
inherited silently, because any code computing bar duration will otherwise be wrong once per
session.

## 4. Vendor session differences

The second source does not agree, and it must never be silently substituted. Measured 2026-08-01,
`30m` on 2026-07-31:

| Source | AAPL | CNQ.TO |
|---|---|---|
| **Yahoo** | 13 bars, `09:30 → 15:30` | 13 bars, `09:30 → 15:30` |
| **Questrade** | **33 bars, `03:30 → 19:30`** | **14 bars, `09:00 → 15:30`** |

Questrade carries deep extended hours on US symbols, a pre-open bar on Canadian ones, and the two
markets differ from each other. Yahoo is clean and symmetric.

**Requirements:**

1. Intraday bars come from Yahoo (`ADR-0001`).
2. Any Questrade intraday used for corroboration must be **filtered to RTH first**, with the filter
   defined per exchange — a single filter would be wrong for one of them.
3. Cross-source comparison of intraday bars without that filter is prohibited. It would report a
   conflict on every bar and thereby train the operator to ignore conflict alarms.

## 5. Bar finality

A bar is **final** when its session interval has fully elapsed and the vendor has stopped revising
it.

- The **unclosed current bar is never used for a decision.** A partially-formed daily bar looks like
  a complete one and silently changes after the decision.
- The main scan is **post-close** — the course's daily process runs after the session
  (`Вечерний процесс`, M82).
- A run started before the close either refuses, or marks its output as provisional. It never
  presents a provisional decision as final.

This follows directly from the module gate's first precondition, *fresh data*, and from the
fail-closed rule that a decision on incomplete data is not permitted.

## 6. Time representation

| Rule | Value |
|---|---|
| Storage | **UTC**, unambiguous |
| Computation and display | **exchange-local** — a session belongs to its exchange's day |
| Session date | the exchange-local calendar date, not the UTC date |
| DST | handled by the exchange calendar; both NYSE and TSX observe US DST, so intraday timestamps shift in UTC twice a year while staying fixed in exchange-local time |

The DST detail is why storage is UTC and computation is local: `09:30 ET` is a different UTC instant
in January and July, and a naive UTC-only pipeline would misalign bars across the transition.

## 7. Currency

Base currency USD (`CONSTRAINTS.md` §5), universe spans both markets.

- Every instrument carries its own `currency` — measured available from both vendors
  (`AAPL → USD`, `CNQ.TO → CAD`).
- FX rates are point-in-time facts with their own `knowledge_time`, like any other fact.
- Sizing converts at a **recorded** rate; the rate used is stored with the risk snapshot, not
  looked up again at reporting time.
- Results split asset return from currency effect — Appendix C, `Разделять asset и FX return`.

## 8. Open items

- [x] ~~Half-days are unverified~~ — **measured, §2b.** 3 hourly bars, and the session close is
      missing from the intraday series.
- [x] ~~TSX/NYSE differences inferred rather than enumerated~~ — **enumerated, §2.** 30 gross
      divergent sessions, not the 2 the net suggested.
- [x] ~~Source an authoritative exchange calendar~~ — **`ADR-0002`: `pandas_market_calendars`**,
      `NYSE` + `TSX`, applied to **both** live and backtest. It is a record rather than a rule, so
      2025-01-09 is covered.
- [x] ~~Confirm whether the three anomalies in §2c are vendor gaps~~ — **confirmed, §2c.** All three
      dates have normal daily bars, so the markets were open. Yahoo's own daily series contradicts
      its intraday series. The second source was not needed.
- [ ] Re-check the same dates against Questrade daily anyway, to establish whether the cross-source
      conflict check would independently have flagged them. Useful as a test of the check, not of
      the dates.
- [ ] Whether `1h` bars are stored with their true duration, so the trailing stub — and the missing
      half-day close — are explicit rather than implied by position.
- [ ] Half-day behaviour at `30m` is still unmeasured: the 60-day window contained no half-day.
      Re-probe after the next US early close (the pattern predicts 7 bars, `09:30–12:30`, with
      12:30–13:00 absent).
