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

## 2. Two exchanges, two calendars — measured

NYSE and TSX both trade 09:30–16:00 ET, which makes them look interchangeable. They are not.

**Measured 2026-08-01:** over the same ~725-trading-day window, Yahoo returned **5,073** hourly bars
for AAPL and **5,089** for CNQ.TO and SHOP.TO — a **16-session divergence** from differing holiday
calendars.

The course already forbids merging them:

> "Запрещено смешивать USA и Canada без отдельных индексов или игнорировать sector/risk-bucket
> concentration."

**Requirement:** separate calendars per exchange, always. Any operation aligning a US and a Canadian
series must join on timestamp and tolerate missing sessions on either side — never assume index
alignment, never forward-fill across a foreign holiday.

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

- [ ] **Half-days are unverified.** US markets close at 13:00 on several days a year, which should
      yield 7 `30m` bars instead of 13 and 4 `1h` bars instead of 7. TSX half-days do not always
      coincide. Probe a known half-day on both markets before the walking skeleton — an unhandled
      half-day is a silent off-by-N in every intraday aggregate.
- [ ] Exchange calendar source. Deriving calendars from observed bar data is self-consistent and
      needs no dependency, but cannot distinguish "market closed" from "vendor missing data" — which
      matters, because one is normal and the other is a `DATA` skip.
- [ ] Whether `1h` bars are stored with their true duration, so the trailing stub is explicit rather
      than implied by position.
- [ ] TSX early-close and holiday list differences from NYSE, enumerated rather than inferred from
      the 16-session count.
