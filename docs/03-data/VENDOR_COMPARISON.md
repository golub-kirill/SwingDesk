# VENDOR COMPARISON — market data

**Status:** drafting · **Tier:** 3 (data) · **Decision record:** `docs/adr/ADR-0001-market-data.md`

Every factual cell below is marked `verified` with its source and date, or `unverified`. Nothing is
asserted from memory: free-tier terms change often, and a wrong number here selects the wrong vendor.
Verification was incomplete this session (web search hit a session quota) — the unverified rows are
listed as open work, not quietly filled in.

---

## 1. What this system actually needs

Derived from the course, not from preference:

| Requirement | Source | Hard? |
|---|---|---|
| Canadian **and** US equities and ETFs | Every appendix cover: `Акции и ETF Канады/США` | Hard |
| Daily bars, deep history | `1Y`/`3M` context windows + M72 historical testing over multiple regimes | Hard |
| `1H` bars (confirmation/trigger) | Owner decision, 2026-08-01 | Hard |
| `30m` bars (execution) | Every appendix cover: `30m execution only` | Hard |
| Corporate actions (splits, dividends), raw **and** adjusted separately | M72 `Corporate actions`; Appendix N `DATA` → `wrong split/currency` | Hard |
| Point-in-time correctness | Appendix A `Point-in-time data`; Appendix J bar-by-bar prohibition; M72 look-ahead/survivorship | Hard |
| Delisted instruments | M72 `Delisted stocks` — required to avoid survivorship bias | Hard |
| Earnings dates with `confirmed / estimated` status | M34-T495 field schema | Hard |
| Index and breadth data (S&P 500, Nasdaq-100, Russell 2000, advance-decline, % above MA) | M31-T453…T459 | Hard |
| Sector / industry classification | M31, Appendix G `Instrument` entity | Hard |
| Short borrow availability / fee | M33-T493, Appendix N `BORROW` | Soft (shorts can be gated off) |
| Spread / depth | M33-T481-482, Appendix N `LIQ` | Soft (proxy acceptable) |

**Two decisive filters:** TSX coverage, and intraday history depth. Most free tiers fail one or both.

---

## 2. Verified findings

### 2.1 Yahoo Finance via `yfinance` — **empirically probed 2026-08-01**

This is the strongest evidence in this document because it was measured, not read.

Probe: `yfinance` `Ticker.history()` for `AAPL`, `SHOP.TO`, `CNQ.TO`.

| Interval | Requested | Result | Range |
|---|---|---|---|
| `1d` | `max` | AAPL 11500 rows · CNQ.TO 7930 · SHOP.TO 2811 | AAPL from **1980-12-12**, CNQ.TO from **1995-01-12**, SHOP.TO from 2015-05-21 |
| `1h` | `730d` | AAPL 5073 rows · CNQ.TO 5089 · SHOP.TO 5089 | from **2023-09-01** ⇒ ~**725 trading days** at 7 bars/day |
| `30m` | `60d` | 780 rows for all three | ~**60 trading days** at 13 bars/day |
| `30m` | `730d` | **EMPTY** | Yahoo error, verbatim: `The requested range must be within the last 60 days.` |

Bar composition (probed separately, timestamps converted to `America/New_York`):

- `30m` → **13 bars/day**, `09:30 10:00 10:30 11:00 11:30 12:00 12:30 13:00 13:30 14:00 14:30 15:00 15:30`
- `1h` → **7 bars/day**, `09:30 10:30 11:30 12:30 13:30 14:30 15:30`
- **Regular trading hours only** — no pre/post-market contamination on either interval.
- **US and TSX are structurally identical** (both 09:30–16:00 ET, same bar counts).
- The `1h` series is already anchored at 09:30, so the 6.5-hour session's unavoidable half-bar lands
  as a **trailing 30-minute stub** (15:30–16:00). This is Yahoo's convention and it matches what
  `CALENDAR_SPEC.md` needs to state.
- CNQ.TO and SHOP.TO returned 5089 hourly bars vs AAPL's 5073 — **16 more**, i.e. NYSE and TSX
  holiday calendars genuinely differ over the window. Confirms that a single shared calendar is a
  defect, as M30/M31/M33 `FAIL-CLOSED` already requires (`Запрещено смешивать USA и Canada`).

**Consequence for the architecture:** `1H` must be **stored independently, not derived from `30m`** —
deriving it would cap hourly history at 60 trading days and discard ~665 days that are actually
available. Each interval carries its own honest depth, and any component reading `30m` inherits a
~3-month backtest ceiling.

**Legal status** — `verified` from the project README (2026-08-01):
> "yfinance is not affiliated, endorsed, or vetted by Yahoo, Inc."
> "Remember - the Yahoo! finance API is intended for personal use only."

Library licence: Apache-2.0. The **data** terms are Yahoo's, not the library's.

### 2.2 Other vendors

| Vendor | Free tier | Status |
|---|---|---|
| **Alpha Vantage** | **25 API requests per day** | `verified` — alphavantage.co/premium, 2026-08-01 |
| **Polygon** → now **massive.com** | Plan `Stocks Basic`, **$0/mo, 5 API calls/minute, 2 years historical, end-of-day only, US stocks only** | `verified` — massive.com/pricing, 2026-08-01. Note the domain moved; `polygon.io/pricing` 301s to `massive.com/pricing`. |
| **EODHD** | `Free Package` $0/mo, **20 calls/day, past year only, intraday NOT included** | `verified` — eodhd.com/pricing, 2026-08-01 |
| **Twelve Data** | `Basic`: **800 credits/day, 8/minute, 3 exchanges**; real-time US equities/ETFs, forex, crypto | `verified` — twelvedata.com/pricing, 2026-08-01. **TSX inclusion on free: unverified** (page shows `XTSE` in examples but does not state which 3 exchanges the free tier allocates). |
| **Finnhub** | 60 API calls/minute; US-only on free; international requires paid | `partially verified` — multiple maintainer/issue reports state the **stock candles (OHLCV) endpoint returns "You don't have access to this resource" on free**, and that previously-free endpoints moved to premium (Finnhub-API issues #271, #546). **Not confirmed against Finnhub's own current docs** — their pricing and rate-limit pages did not render server-side. |
| **TradingView** | — | **`unverified` and structurally doubtful.** TradingView publishes no documented public REST API for historical OHLCV; its data is licensed from exchanges. Charting-library and widget usage is governed by their terms. **No use until a ToS review is completed and recorded here.** Note: a *calendar* feed is a different question from *price* data and may be assessable separately. |

### 2.3 Not yet assessed

`unverified` — carried as open work: Tiingo, Stooq, Nasdaq Data Link, Alpaca (IEX-only free feed),
Marketstack, Questrade API (free with a Canadian brokerage account — the only listed source with a
native Canadian mandate), IBKR. Also unassessed: free sources for **index breadth** (advance-decline,
% above MA) and for **earnings dates with confirmed/estimated status**, both of which are hard
requirements and may need a different provider from the bar data.

---

## 3. Reading of the evidence

1. **On the free tier, Yahoo is the only verified source that covers Canada *and* provides
   intraday.** Every other free tier verified so far is either US-only (massive, Finnhub),
   daily-only (EODHD), or so rate-limited as to be unusable for a universe scan
   (Alpha Vantage at 25 requests/day cannot refresh even a 50-name watchlist).
2. **No free vendor offers point-in-time data.** Yahoo actively rewrites adjusted history on every
   refetch. This is not a reason to reject it — it is a reason the bitemporal layer
   (`POINT_IN_TIME_SPEC.md`) is mandatory rather than optional: the system builds *its own*
   point-in-time record going forward by snapshotting what it saw and when, because the vendor
   will not preserve it.
3. **The `30m` execution layer has a hard ~3-month evidence ceiling** on this path. Any component
   depending on `30m` can never claim a validation status stronger than that window supports. This
   must be visible in the component registry, not buried.
4. **`personal use only` is a real constraint, not boilerplate.** It is compatible with this project
   as chartered (single user, no redistribution, no third-party advice) and incompatible with ever
   turning the tool into a service. That makes it a charter-level non-goal, not a data detail.
5. **A composite is likely unavoidable.** Bars from one source, earnings/events from another,
   breadth from a third. That is precisely why `DATA_CONTRACTS/` and the `Source Facts` layer exist:
   the rest of the system must not know which vendor a fact came from, only its provenance and
   as-of time.

---

## 4. Open work before this document can be marked `frozen`

- [ ] Confirm Finnhub's free-tier candle access against their own live docs.
- [ ] Confirm whether Twelve Data's free `3 exchanges` can include TSX.
- [ ] Assess Tiingo, Stooq, Alpaca, Questrade, Nasdaq Data Link.
- [ ] Identify a source for index breadth (advance-decline, % above MA) — hard requirement, no
      candidate yet.
- [ ] Identify a source for earnings dates carrying `confirmed / estimated` status — hard
      requirement (M34-T495), no candidate yet.
- [ ] Record a TradingView ToS review, or formally exclude it.
- [ ] Measure delisted-instrument availability on the chosen source (survivorship bias, M72).
