# DATA QUALITY SPEC

**Status:** drafting · **Tier:** 3 (data) · **Content:** authored on measured evidence

<!-- verbatim-sources: Module_33_Skrinery_v5.0.pdf -->

**Depends on:** `ADR-0002` (exchange calendar) · `CALENDAR_SPEC.md` · `FAIL_CLOSED_POLICY.md`

---

## 1. What the course requires

The fail-closed table's first row states the failure, the response **and** the return condition:

```verbatim
Нет/сомнительны данные
Остановить новые решения; использовать второй источник и последний валидный snapshot.
Freshness, symbol/currency, corporate actions и event time подтверждены.
```

Four named gates, and nothing may resume until all four pass:

| Gate | Question |
|---|---|
| **freshness** | is the data current enough to decide on? |
| **symbol / currency** | is this the instrument we think it is, priced in the currency we think? |
| **corporate actions** | have splits and dividends been accounted for? |
| **event time** | is the event calendar current? |

Plus the skip codes: `DATA` → `Automatic Skip until corrected`, and `DATA_ERR` (`Critical`) →
`Fail-closed gate`.

## 2. Gate 1 — freshness

Two distinct checks, often confused:

### 2.1 Staleness — is the series behind?

Compare the last bar's session date against the **calendar's** last completed session for that
instrument's exchange (`ADR-0002`). `sessions_behind > 0` means stale.

- Stale → refetch once.
- Still stale → `DATA` skip.
- `data.freshness_window` sessions behind → the instrument is dropped from the run entirely.

The unclosed current bar is **never** used (`CALENDAR_SPEC.md` §5). A run before the close either
refuses or marks output provisional.

### 2.2 Completeness — is any session missing from the middle?

This is the check the measurement work exists to justify, and it is **only possible with the
calendar**:

```
expected_bars(session, interval) = f(calendar open, calendar close, interval)
actual_bars   != expected_bars   ->  DATA skip for that session
```

A genuine half-day has a *short expected count* and passes. A vendor gap has a normal expected count
and a short actual count, and fails.

**Measured basis:** three confirmed gaps and seven confirmed half-days produce indistinguishable
signatures without the calendar (`CALENDAR_SPEC.md` §2c–§2d).

**Backtest and live both run this check.** A hole in the middle of history corrupts a conclusion
rather than skipping a scan, which is the more expensive failure.

### 2.3 What NOT to gate on

Measured negatives, recorded so they are not reinvented:

- **Never** `Σ intraday volume == daily volume`. False on every session — the daily figure is
  consolidated. Measured normal range **0.366–0.824**.
- **Never** the volume ratio alone. Normal, half-day and gap ranges overlap almost completely; only
  a two-orders-of-magnitude outlier against the instrument's *own* history is informative.
- **Never** "last intraday close == daily close". It legitimately differs by **~0.6%** on half-days,
  and a start-truncated gap shows **no** difference at all.

## 3. Gate 2 — symbol and currency

| Check | Rule |
|---|---|
| currency present | mandatory on every instrument; missing → `DATA` |
| currency stable | a change in an instrument's currency is a `DATA_ERR`, not a revision |
| exchange stable | likewise |
| symbol identity | a reused ticker is a different instrument; identity is the internal id, never the ticker string |

Ticker reuse is real and silent — a delisted symbol can be reassigned. Since neither vendor gives us
delisted history (`ADR-0001` §6), we cannot detect reuse from price continuity, so **the internal id
is the only safe identity** and tickers are labels attached to it.

## 4. Gate 3 — corporate actions

From `POINT_IN_TIME_SPEC.md` §4, raw and adjusted are separate series:

| Observation | Meaning | Action |
|---|---|---|
| adjusted history changed, and an action exists at that date | expected restatement | write revision, no alarm |
| adjusted history changed, **no** action explains it | unexplained restatement | `DATA` skip + investigate |
| **raw** bar changed | a raw bar should never change | `DATA_ERR` (`Critical`) |
| mass revision across many instruments | vendor-wide re-adjustment | alarm — visible only because storage is delta-based (`POINT_IN_TIME_SPEC.md` §3) |

A float epsilon is required or vendor noise produces phantom revisions: `data.revision_epsilon`,
per series, currently `unset`.

## 5. Gate 4 — event time

Earnings and event calendars must be current, and every event carries its `confirmed`/`estimated`
status where the source provides one.

**Known gap:** Yahoo supplies earnings dates with `EPS Estimate / Reported EPS / Surprise(%)` but
**no confirmation-status field**, which M34-T495 requires (`VENDOR_COMPARISON.md` §2.2). Until a
source is found, the status is recorded as `unavailable` — not silently assumed `confirmed`.

## 6. Second-source corroboration

The course requires a second source on data doubt. Questrade fills that role (`ADR-0001`).

| Rule | Reason |
|---|---|
| Corroborate on **daily** bars first | both sources are clean there |
| Intraday corroboration requires RTH filtering **per exchange** first | Questrade returns `03:30–19:30` for US and `09:00–15:30` for Canada; unfiltered comparison conflicts on every bar |
| A conflict is **surfaced, never reconciled** | §3.6 layer 1: "не сливаются в ложную определённость" — conflicting providers stay visible |
| A conflict is a `DATA` skip | not a vote, not an average |

**Averaging two disagreeing sources is prohibited.** It manufactures a number that neither vendor
reported and hides the disagreement.

## 7. Mapping to codes

| Condition | Code | Action |
|---|---|---|
| stale beyond window | `DATA` | Automatic Skip until corrected |
| session bar count ≠ calendar expectation | `DATA` | Skip that session |
| unexplained adjusted-history change | `DATA` | Skip + investigate |
| raw bar changed | `DATA_ERR` (`Critical`) | Fail-closed gate |
| currency or exchange changed | `DATA_ERR` (`Critical`) | Fail-closed gate |
| two sources disagree beyond tolerance | `DATA` | Skip, surface both values |
| spread / dollar volume / depth incompatible | `LIQ` | Skip or smaller universe category |

## 8. Parameters this spec requires

All `unset` in `registry/parameters.yml`; each makes its check refuse rather than default.

`data.freshness_window` · `data.staleness_action_threshold` · `data.revision_epsilon` ·
`data.volume_ratio_outlier_factor` · `data.source_conflict_tolerance` ·
`data.max_missing_sessions_per_instrument`

## 9. Open items

- [ ] Whether corroboration runs daily or only on suspicion. Daily doubles fetch time; on-suspicion
      cannot detect what it never looks at. `NFR.md` §9 carries the same question.
- [ ] Per-series epsilon values — price, volume and adjusted series need different tolerances.
- [ ] Whether an instrument accumulating repeated `DATA` skips is auto-dropped from the universe,
      and after how many.
- [ ] Half-day expected bar counts at `30m` are still unmeasured (the 60-day window contained none).
      The calendar gives the close time, so the expectation is derivable — but it should be verified
      against a real half-day before being trusted.
