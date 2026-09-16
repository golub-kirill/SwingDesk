# DR-045: The intraday ladder is rolled up from stored minutes

```
date:            2026-09-15
status:          accepted — ratified by the owner 2026-09-15, who asked for the minute resolutions
                 to be added and ratified. The context half of the same ruling is DR-046
parameters:      none
components:      none new
implemented_by:  src/swingdesk/market_data/intraday.py :: def roll_up
```

## 1. What the owner ruled

Add and ratify the intraday resolutions. `CONSTRAINTS.md` D9 already carried the ladder — *1Y/3M
context → 1D decision → 1H confirmation → 30m execution* — and the only rung this project had ever
stored was `1D`, plus one-minute bars fetched for the few sessions `DR-042` could not settle from a
daily bar.

## 2. What is stored, and what is not

| | |
|---|---|
| **fetched and stored** | `1d` from Yahoo (`BarStore`), `1m` from Alpaca (`MinuteStore`) |
| **derived on read** | `3m`, `5m`, `15m`, `30m`, `60m` — rolled up from stored minutes |
| **never derived** | `1d`. It comes from its own vendor, adjusted its own way |

`market_data.intraday.roll_up` is the whole of the derivation: minutes in, bars out, nothing
written back under a resolution nobody fetched.

## 3. Why deriving is right HERE and stays wrong for the daily path

`contracts.market.Interval` says each resolution is fetched independently and never derived from
another. **That rule was written about Yahoo, and its reason does not survive the change of
vendor.** Yahoo serves 730 days of hourly bars and 60 days of half-hourly ones (`vendor_policy.yml`),
so a 30-minute series derived from hourly bars would have had a past the vendor does not serve, and
one built from 30-minute bars would have stopped 60 days back. Alpaca's minutes have no such
ceiling — the free tier's SIP feed serves them from 2016-01-04, established 2026-09-05 — so every
rung above a minute has exactly the history the minutes have, from one source, with one adjustment
and one knowledge time.

**The daily path keeps the old rule**, and for the old reason: `1d` comes from a different vendor
with a different adjustment, and rolling it up from minutes would silently change which prices a
twenty-year study is denominated in.

## 4. What the roll-up refuses

* **A span it cannot build.** `3, 5, 15, 30, 60` and nothing else; `1` is absent because that is
  what is stored.
* **A short final bar, unless asked.** A half day ends inside a bucket, and a bar covering ten
  minutes beside bars covering sixty has a high and a low that mean something different.
  `allow_partial=True` admits it deliberately; the default refuses.
* **Reindexing around a gap.** Buckets come from the clock, never from position in the list. A
  minute the vendor never printed — a halt, a thin name — leaves a bar holding fewer minutes and
  moves nothing after it. Every bar carries the count, so a study can exclude them by measurement
  rather than discover them in its results.
* **Counting backwards from the open.** `MinuteStore` keeps the whole UTC day, pre-market included
  (`DR-042` §9 chose that so the reader decides the hours). Measured from the first minute present,
  a 30-minute series would start at 04:03 and straddle every boundary a trader reads, so a caller
  passes `anchor` — the session's open — and a minute earlier than it is refused, not bucketed.

## 5. What this does not decide

* **No strategy.** This is data. `CHARTER` still rules an intraday strategy engine out of scope and
  `30m` execution-only; using these rungs to ORIGINATE a setup needs the owner's amendment to that,
  which they have not given.
* **No parameter.** No window, threshold or lookback is set here. The spans are the ladder's own
  rungs, and a study that picks one picks it in its pre-registration.
* **No fetch policy.** What gets fetched, for which instruments and how far back, is operational and
  stays in `tools/fetch_minutes.py` and the runbook.

## 6. What would overturn this

* **Alpaca's minute history proving incomplete over a span we rely on** — then a rung built from it
  is not the rung we thought, and the honest answer is to fetch that rung directly and compare.
  `MinuteStore` already records every fetch, served or empty, so the question is answerable.
* **A measured difference between a rolled-up bar and the vendor's own bar at the same span.** The
  test for it is one request; until somebody makes it, this record claims equality of CONSTRUCTION,
  not of the vendor's arithmetic.
