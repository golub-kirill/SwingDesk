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

## 5. Owner-pending

These are budget and capacity limits only the owner can set. They are **not** trading parameters —
those live in `registry/parameters.yml`.

- [ ] **Money**: monthly ceiling for data and infrastructure. Currently assumed **$0** (free tier,
      D8). If a paid vendor is acceptable, `ADR-0001` changes materially — a paid feed would fix
      point-in-time and possibly survivorship, which are otherwise permanent limitations.
- [ ] **Time**: hours per week available. This determines whether the roadmap is months or years,
      and whether D2's full-catalogue scope is reachable at `specified` or only at `registered`.
- [ ] **Universe size**: how many instruments. Drives fetch volume, rate limits, and whether
      in-house breadth is meaningful.
- [ ] **Account equity and currency** (CAD or USD base). Needed before `risk.per_trade_pct` means
      anything, and before FX handling can be specified.
- [ ] **Hardware**: whether backtests run on this machine or somewhere else.
