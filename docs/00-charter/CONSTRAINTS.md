# CONSTRAINTS

**Status:** drafting — budget items **owner-pending** · **Tier:** 0 (charter) · **Content:** `verbatim` + owner decisions

<!-- verbatim-sources: Appendix_C_Formuly_upravleniya_riskom_v2.0.pdf, Appendix_T_Professionalnyi_chek_list_treidera_v2.0.pdf -->

---

## 1. From the course

Printed on the cover of all 116 files and in every appendix scope line:

> "Акции и ETF Канады/США · 1D decision timeframe · 30m execution only · versioned evidence record."

And the authoritative timeframe statement, from Appendix T's conclusion:

> "Основной рабочий график — 1D; 1Y и 3M задают контекст, 30D формирует план, 30m только исполняет."

| Constraint | Value |
|---|---|
| Markets | Canada + US |
| Instruments | equities and ETFs |
| Decision timeframe | `1D` |
| Context | `1Y`, `3M` (windows over daily bars) |
| Planning window | `30D` |
| Execution timeframe | `30m` — execution only, never setup origination |
| Evidence | versioned record required for every decision |

**Exchanges are never merged.** From M30/M31/M33 `FAIL-CLOSED`:

> "Запрещено смешивать USA и Canada без отдельных индексов или игнорировать sector/risk-bucket concentration."

Measured consequence: over a ~2.9-year window, NYSE and TSX differed by 16 trading sessions
(`VENDOR_COMPARISON.md` §2.1). Separate calendars are mandatory regardless of data source.

## 2. Owner decisions

| # | Decision | Date |
|---|---|---|
| D1 | Decision support only — no order execution | 2026-08-01 |
| D2 | v1 covers the full catalogue of derived observations and setups (~460 components) | 2026-08-01 |
| D3 | CLI + reports first → web admin panel → Telegram approvals + Firebase push | 2026-08-01 |
| D4 | Local database; Firebase for push notifications only | 2026-08-01 |
| D5 | Parameters: literature-sourced starting values marked `assumed`, editable from the web UI | 2026-08-01 |
| D6 | Telegram approves open-position actions (stop moves, partial exits) | 2026-08-01 |
| D7 | English throughout — documents, code, UI | 2026-08-01 |
| D8 | Market data: free tier (see `ADR-0001`, status Proposed) | 2026-08-01 |
| D9 | Timeframes: `1Y`/`3M` context → `1D` decision → `1H` confirmation → `30m` execution | 2026-08-01 |

**D9 is an extension beyond the course.** Appendix T's conclusion names 1Y/3M/30D/1D/30m and does
**not** mention 1H. The hourly confirmation layer is the owner's addition, recorded as such so it is
never mistaken for a transcribed requirement.

## 3. Data constraints (measured, `ADR-0001`)

| Interval | Depth available |
|---|---|
| `1d` | full history (AAPL from 1980-12-12, CNQ.TO from 1995-01-12) |
| `1h` | ~725 trading days (~2.9 years) |
| `30m` | **60 trading days (~3 months)** |

Three consequences that constrain what the system may ever claim:

1. **Any component reading `30m` has a ~3-month evidence ceiling.** No validation status stronger
   than that window supports.
2. **Survivorship bias is permanent on the free path** — no delisted instruments are available.
   Stamped on every backtest result.
3. **Personal use only** — Yahoo's terms. This is why "becoming a service" is a charter non-goal
   rather than a roadmap item.

## 4. Operating constraints

- **Single user**, single machine, local database.
- **One daily run**, post-close, with open positions processed before new candidates
  (`CHECKLIST_SPEC.md` §4).
- **No live intraday loop** in v1 — `30m` is fetched for execution refinement, not streamed.
- **Firebase for push only**; no market data, no journal, no decisions leave the machine.

## 5. Capacity and account (owner, 2026-08-01)

| Constraint | Value | Notes |
|---|---|---|
| Account equity | **$10,000**, configurable default | Not a hardcoded figure — `account.equity` is a parameter with this default. |
| Base currency | **USD** | Simplifies FX: Canadian positions carry a currency effect, US positions do not. `FX-adjusted P&L` (Appendix C) applies to `.TO` names only. |
| Universe | **A-tier** — definition pending, see §6 | Drives fetch volume, rate limits, and whether in-house breadth is meaningful. |
| Data spend | **$0** (free tier, D8) | See `ADR-0001`. A paid feed is the only thing that would fix point-in-time and survivorship. |

**A USD base with Canadian holdings makes currency a first-class concern, not an afterthought.** Every
`.TO` position's result is reported as asset return and currency effect separately — Appendix C,
`Разделять asset и FX return` — and sizing must convert at a recorded rate with its own as-of time.

## 6. Universe — A-tier by liquidity rule (owner, 2026-08-01)

Membership is **computed from our own bars**, not taken from index constituents:

```
eligible  <=>  price >= universe.min_price
           AND 20-day average dollar volume >= universe.min_adtv_20d
           AND daily history >= universe.min_bar_history
```

Recomputed daily; membership is therefore itself a point-in-time fact and is stored as one.

**Why not S&P 500 + TSX 60.** Index membership is the intuitive reading of "A-tier", but free
sources give only *today's* constituents. Backtesting against today's membership means testing on
the names that survived and were promoted — stacking a second survivorship bias on top of the
delisting problem `ADR-0001` already accepts. The liquidity rule needs no membership data, behaves
identically on both exchanges, and its inputs (`Dollar volume` = `Цена × объём`, Appendix A) are
already in the glossary.

All three thresholds are `unset` in `registry/parameters.yml`.

## 7. Users — single-user, configurable defaults (owner, 2026-08-01)

Equity, risk and universe thresholds are **parameters with defaults**, not constants, so the numbers
are easy to change. But: **one install, one owner.** The charter non-goals stand, and Yahoo's
personal-use terms remain satisfied (`ADR-0001` condition 1).

## 8. Still open

- [ ] **Time budget**: hours per week. Determines whether D2's full-catalogue scope is reachable at
      `specified` or only at `registered`.
- [ ] **Hardware**: whether backtests run on this machine or elsewhere.
- [ ] **`k.project_timebox`** in `registry/criteria.yml` — months from G0 close before Track A must
      be met. The last value blocking G0.
