# ADR-0001 — Market data source for v1

- **Status:** Proposed — awaiting owner ratification
- **Date:** 2026-08-01
- **Evidence:** `docs/03-data/VENDOR_COMPARISON.md`

## Context

The course requires Canadian **and** US equities and ETFs, deep daily history for regime-spanning
backtests, and intraday bars (`1H` confirmation, `30m` execution). The owner's constraint is to stay
on free tiers.

Free tiers verified on 2026-08-01 fail at least one hard requirement:

| Vendor | Fails on |
|---|---|
| Alpha Vantage | 25 requests/day — cannot refresh a watchlist |
| massive.com (ex-Polygon) | US only, end-of-day only, 2 years |
| EODHD | 20 calls/day, 1 year, no intraday |
| Finnhub | US only on free; OHLCV candles reported premium |
| Twelve Data | 3 exchanges on free; TSX inclusion unconfirmed |
| TradingView | no documented public OHLCV API; ToS unreviewed |

Yahoo Finance, probed empirically, is the only verified free source covering Canada with intraday:
full daily history for both markets (CNQ.TO back to 1995-01-12), ~725 trading days of `1H`, and
60 trading days of `30m`, regular-hours only, identical bar structure for NYSE and TSX.

## Decision

Use **Yahoo Finance via `yfinance`** as the v1 bar source for `1d`, `1h` and `30m`, for both US and
Canadian instruments, behind a vendor-agnostic adapter in `swingdesk.market_data`.

Store the three intervals **independently**. Do not derive `1h` from `30m`: `30m` is capped at 60
trading days while `1h` reaches ~725, and deriving would discard ~665 days of available history.

## Conditions this decision carries

1. **Personal use only.** Yahoo's terms state the API is for personal use. This binds the charter:
   single user, no redistribution of data, no third-party service. Promote to a non-goal in
   `CHARTER.md`.
2. **The system owns point-in-time, because the vendor does not.** Yahoo rewrites adjusted history on
   refetch. `POINT_IN_TIME_SPEC.md` is therefore mandatory: every fetch is snapshotted with its
   `knowledge_time`, raw and adjusted stored separately, revisions inserted rather than overwritten.
   Backtests run against snapshots, never against a live refetch.
3. **`30m` carries a ~3-month evidence ceiling.** Any component reading `30m` is capped at what 60
   trading days can support. The component registry records this, and no such component may display
   a validation status its window cannot justify.
4. **No SLA, unofficial library.** The adapter is fail-closed per `FAIL_CLOSED_POLICY.md`: a fetch
   failure or a staleness/conflict check failure raises skip code `DATA` → `Automatic Skip until
   corrected`, never a silent fallback to stale bars.
5. **Bars only.** This ADR does not cover earnings dates with `confirmed/estimated` status, index
   breadth, sector classification, or borrow availability. Those are separate, still-unsourced
   requirements and will get their own ADRs.

## Alternatives considered

- **Pay for a vendor** (Tiingo/EODHD/massive paid tiers, ~$30–200/month). Solves point-in-time,
  corporate actions and intraday depth properly. Rejected for v1 on the owner's free-tier
  constraint; revisit trigger below.
- **Questrade API** (free with a Canadian brokerage account). The only candidate with a native
  Canadian mandate and the only one that could later serve execution too. Not assessed — it is the
  highest-value item on the open-work list, and could supersede this ADR.
- **Composite from day one** (Yahoo bars + others for events/breadth). Deferred, not rejected: the
  adapter interface is designed for it, but v1 proves one source end to end first.
- **Derive `1h` from `30m`.** Rejected on measured evidence, see Decision.

## Consequences

- Positive: zero cost; Canada and US covered by one adapter; deep daily history enables the
  regime-spanning backtests M72 requires; identical bar structure across both markets simplifies
  `CALENDAR_SPEC.md`.
- Negative: no point-in-time from the vendor, so the snapshot layer must exist before any backtest
  is trustworthy; `30m` research is depth-limited; no SLA; the personal-use term forecloses ever
  making this a service.
- Neutral: NYSE and TSX holiday calendars measurably differ (16 sessions over ~2.9 years), so
  separate exchange calendars are required regardless of vendor.

## Revisit when

- The `30m` ceiling blocks a decision the owner actually wants to make, **or**
- Yahoo access breaks or degrades (unofficial, no SLA), **or**
- The project moves beyond single-user personal use, **or**
- Questrade (or another account-linked source) is assessed and covers the same ground under clearer
  terms.
