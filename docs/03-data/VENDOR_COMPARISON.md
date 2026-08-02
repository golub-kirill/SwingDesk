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

### 2.2 Yahoo — non-bar capabilities, **empirically probed 2026-08-01**

Bars are only part of the requirement list. Probed separately:

| Requirement | Result | Verdict |
|---|---|---|
| **Delisted instruments** (M72, survivorship) | `TWTR`, `SIVB`, `FRC`, `ATVI` — **all return 0 rows**, `possibly delisted; no timezone found` | **NOT MET** |
| **Earnings dates** with `confirmed / estimated` status (M34-T495) | `get_earnings_dates()` returns columns `EPS Estimate`, `Reported EPS`, `Surprise(%)` with a timestamped date (`2026-10-29 16:00:00-04:00`). **No confirmation-status field.** Future vs past is inferable from a null `Reported EPS`; `Confirmed` vs `Estimated` is not. | **PARTIAL** |
| **Index levels** | `^GSPC`, `^NDX`, `^RUT`, `^GSPTSE`, `^VIX` all return data | MET |
| **Advance-decline** | `^ADD` → `No data found, symbol may be delisted` | **NOT MET** |
| **Sector / industry / exchange / currency** | `AAPL` → `Technology` / `Consumer Electronics` / `NMS` / `USD`; `CNQ.TO` → `Energy` / `Oil & Gas E&P` / `TOR` / `CAD` | MET |

**The survivorship finding is the serious one.** Yahoo serves no history for delisted tickers, so a
universe assembled from currently-listed names is survivorship-biased by construction. M72 names
`Delisted stocks` as a required control and M72's own `FAIL-CLOSED` forbids
`survivorship` — and this is the exact failure that has previously invalidated a result the owner
believed in. It is very unlikely any free source fixes this. Therefore treat it as an unavoidable
**property of the free path**, stamped on every backtest result and every evidence record, rather
than as a vendor-selection criterion that some other free vendor will satisfy.

**Breadth is computable, not purchasable.** With `^ADD` unavailable, advance-decline and
percent-above-MA must be computed in-house from the bars already fetched for the universe. That is
feasible — but it produces *our universe's* breadth, which is **not** S&P 500 breadth. It must be
registered as a Derived Observation with its universe stated, and must never be labelled as index
breadth. M31-T457's own wording (`breadth tests whether index direction is supported by constituent
participation`) requires constituents we do not have.

### 2.3 Other vendors

| Vendor | Free tier | Status |
|---|---|---|
| **Alpha Vantage** | **25 API requests per day** | `verified` — alphavantage.co/premium, 2026-08-01 |
| **Polygon** → now **massive.com** | Plan `Stocks Basic`, **$0/mo, 5 API calls/minute, 2 years historical, end-of-day only, US stocks only** | `verified` — massive.com/pricing, 2026-08-01. Note the domain moved; `polygon.io/pricing` 301s to `massive.com/pricing`. |
| **EODHD** | `Free Package` $0/mo, **20 calls/day, past year only, intraday NOT included** | `verified` — eodhd.com/pricing, 2026-08-01 |
| **Twelve Data** | `Basic`: **800 credits/day, 8/minute, 3 exchanges**; real-time US equities/ETFs, forex, crypto | `verified` — twelvedata.com/pricing, 2026-08-01. **TSX inclusion on free: unverified** (page shows `XTSE` in examples but does not state which 3 exchanges the free tier allocates). |
| **Finnhub** | 60 API calls/minute; US-only on free; international requires paid | `partially verified` — multiple maintainer/issue reports state the **stock candles (OHLCV) endpoint returns "You don't have access to this resource" on free**, and that previously-free endpoints moved to premium (Finnhub-API issues #271, #546). **Not confirmed against Finnhub's own current docs** — their pricing and rate-limit pages did not render server-side. |
| **Questrade** | **Free for anyone to use.** Historical OHLC candlesticks for **Canadian and US** stocks and options; TSX supported. Granularity enum includes `HalfHour`, `OneHour`, `OneDay` — exactly the three this system needs. Max **2,000 candles per response**. OAuth 2.0. A practice account carries L1 data access. Rate-limited with HTTP 429 on breach. | `verified` via Questrade developer docs and search, 2026-08-01. **Unverified:** intraday historical depth, exact rate-limit numbers, delisted-symbol availability, redistribution terms. Their doc pages return HTTP 403 to automated fetching, so these need a manual read or a live API probe. |
| **Tiingo** | `Starter` (free): **500 unique symbols/month, 50 requests/hour, 1,000 requests/day, 1 GB bandwidth, 30+ years of price history**, 5 years fundamentals | `partially verified` — figures from third-party summaries, not Tiingo's own pricing page, 2026-08-01. Canada coverage claimed at platform level; **free-tier Canadian access unverified**. Note the 500-symbol/month cap is a universe-size constraint, not just a rate limit. |
| **Stooq** | free CSV endpoint | `unverified` — `https://stooq.com/q/d/l/?s=<sym>&i=d` returned **HTTP 404 for all of** `cnq.ca`, `cnq.to`, `aapl.us`, `shop.ca` on 2026-08-01. Either the symbol convention or the endpoint has changed. Not usable until the correct form is established. |
| **TradingView** | — | **`unverified` and structurally doubtful.** TradingView publishes no documented public REST API for historical OHLCV; its data is licensed from exchanges. Charting-library and widget usage is governed by their terms. **No use until a ToS review is completed and recorded here.** Note: a *calendar* feed is a different question from *price* data and may be assessable separately. |

### 2.3 Not yet assessed

`unverified` — carried as open work: Tiingo, Stooq, Nasdaq Data Link, Alpaca (IEX-only free feed),
Marketstack, Questrade API (free with a Canadian brokerage account — the only listed source with a
native Canadian mandate), IBKR. Also unassessed: free sources for **index breadth** (advance-decline,
% above MA) and for **earnings dates with confirmed/estimated status**, both of which are hard
requirements and may need a different provider from the bar data.

---

### 2.4 Questrade — **empirically probed 2026-08-01** (`tools/probe_questrade.py`)

Run by the owner against a live account. API server `api01.iq.questrade.com`.

| Symbol | Exchange | Currency | `OneDay` | `OneHour` | `HalfHour` |
|---|---|---|---|---|---|
| AAPL | NASDAQ | USD | 2498 bars, 2016-08-04 → 2026-07-31 | 1054 bars, **2026-05-04** → | 2046 bars, **2026-05-04** → |
| CNQ.TO | TSX | CAD | 2507 bars, 2016-08-04 → | 441 bars, **2026-05-04** → | 882 bars, **2026-05-04** → |
| SHOP.TO | TSX | CAD | 2500 bars, 2016-08-04 → | 441 bars, **2026-05-04** → | 881 bars, **2026-05-04** → |

Second run, lookback extended to 30 years:

| Symbol | `OneDay` |
|---|---|
| AAPL | 7509 bars, **1996-08-09** → 2026-07-31 |
| CNQ.TO | 7528 bars, **1996-08-09** → |
| SHOP.TO | 2803 bars, **2015-05-21** → (its actual listing date) |

**Four readings, in order of consequence:**

1. **Questrade does not solve the intraday problem.** Every intraday series begins `2026-05-04` —
   ~63 trading days, materially the same cap as Yahoo's measured 60. Yahoo's `1h` reaches ~725
   trading days, so **Yahoo is roughly 11× deeper on hourly**. The `30m` evidence ceiling stands on
   both sources.
2. **Delisted history does not exist — confirmed.** `TWTR`, `SIVB` and `ATVI` resolve as symbol
   records but come back `tradable=False, quotable=False`, and their candles return
   `HTTP 404 {"code":1019,"message":"Symbol not found"}`. The record is a stub. **Survivorship bias
   is now measured as unavoidable on two independent sources**, which promotes it from "assumed
   permanent" to "demonstrated permanent" for the free path.
3. **Questrade intraday sessions are dirty, and inconsistently so.** Measured on 2026-07-31,
   `HalfHour`:
   - AAPL — **33 bars, 03:30 → 19:30** (≈16.5 hours; deep pre- and post-market)
   - CNQ.TO — **14 bars, 09:00 → 15:30** (7 hours; includes a pre-open 09:00 bar)

   Neither is regular hours, and the two markets differ from each other. Yahoo returns a clean
   13-bar RTH session (`09:30 … 15:30`) **identically for both markets**. For a system whose
   indicators must be comparable across US and Canadian names, Yahoo's intraday is materially
   cleaner and needs no per-exchange filtering.
4. **Daily depth ≥30 years, ceiling still unknown** — `1996-08-09` is again the probe's floor, not
   the vendor's. Yahoo reaches 1980 for AAPL, so Yahoo remains deeper there; for CNQ.TO the two are
   comparable (Yahoo 1995-01-12 vs Questrade ≤1996-08-09). SHOP.TO returns `2015-05-21` from **both**
   sources — a useful cross-validation that both are reporting the true listing date rather than a
   truncated window.

**Where Questrade earns its place anyway.** The fail-closed degradation table's first row requires,
verbatim, *"использовать второй источник и последний валидный snapshot"* — a **second source** on
data doubt. Questrade is a licensed, documented API covering exactly the same universe, which makes
it the natural corroborating source for conflict detection, even though it loses as the primary.
That satisfies a course requirement that Yahoo alone cannot meet.

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
6. **Questrade is now the strongest candidate on paper and must be evaluated before G5.** It is the
   only free option verified to be a *licensed, documented API* rather than an unofficial scrape, it
   is natively Canadian **and** US, and its granularity enum contains exactly `HalfHour`, `OneHour`,
   `OneDay`. If its intraday depth beats Yahoo's 60 trading days, it supersedes ADR-0001 outright.
   The blocking unknowns are depth, rate limits and redistribution terms — none obtainable by
   automated fetch (their docs return 403), so this needs a manual read or a live probe with an
   account.
7. **Survivorship bias is a property of the free path, not a vendor choice.** No free source
   examined serves delisted instruments. Every backtest result on this path carries it, and the
   evidence record must say so rather than the result being quietly quoted without it.
8. **Two hard requirements have no source at all yet**: earnings `confirmed / estimated` status
   (M34-T495) and true index breadth (M31-T457). Universe-breadth computed in-house is a legitimate
   substitute only if it is labelled as what it is.

---

## 4. Open work before this document can be marked `frozen`

**Blocking (must resolve before G5 / walking skeleton):**

- [x] ~~Questrade intraday depth~~ — **~63 trading days, no better than Yahoo.**
- [x] ~~Do delisted symbols have candles in Questrade?~~ — **no.** They resolve as untradable stubs;
      candles 404. Survivorship confirmed permanent on both sources.
- [x] ~~Questrade daily depth~~ — **≥30 years**; ceiling still unmeasured but no longer decision-relevant.
- [x] ~~Questrade session coverage~~ — **dirty and market-dependent** (US 03:30–19:30, CA 09:00–15:30).
- [ ] Questrade rate limits and redistribution terms — needed only for its **second-source** role.
- [ ] Whether Questrade intraday can be filtered to RTH reliably enough for cross-checking, or
      whether corroboration is restricted to daily bars.
- [ ] Decide the **earnings `confirmed / estimated`** source, or formally downgrade M34-T495's status
      field to `unavailable` and record what the system does without it.
- [ ] Decide **breadth**: register in-house universe-breadth as a Derived Observation with its
      universe stated, or find a constituent source.

**Non-blocking:**

- [ ] Confirm Finnhub's free-tier candle access against their own live docs (their pages do not
      render server-side).
- [ ] Confirm whether Twelve Data's free `3 exchanges` can include TSX.
- [ ] Confirm Tiingo's free-tier Canadian access against Tiingo's own pricing page, and whether the
      500-symbols/month cap is compatible with the intended universe size.
- [ ] Establish Stooq's current symbol convention (all four probed forms 404'd).
- [ ] Assess Alpaca (IEX-only free feed) and Nasdaq Data Link.
- [ ] Record a TradingView ToS review, or formally exclude it.

**Closed:**

- [x] Delisted-instrument availability on Yahoo — **measured: none**. Survivorship bias confirmed
      unavoidable on this source (§2.2).
