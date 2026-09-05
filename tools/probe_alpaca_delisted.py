"""Does Alpaca serve the PRICE PATH of a delisted equity? Asked because nobody had asked.

**The claim this probe was written to test**, and it is load-bearing twice over:

  * `EVIDENCE_SUMMARY.md` section 3 - *"What those trades would have returned is not: no free source
    serves the price path of a symbol that has gone."*
  * and the sentence that rests on it - *"the one positive finding (`PR-002`) is erased by 1.6-2.3%
    of trades missing at -2R, which the free tier can never rule out."*

**Half of the wider claim was already refuted.** `tools/probe_edgar.py` established on 2026-08-24
that the FACT and DATE of a delisting are free and official from SEC EDGAR, and left the PRICE half
standing. **The price half was never asked of Alpaca**, whose credentials this project already
holds and whose broker adapter already runs against them.

**Measured 2026-09-05, and the price half does not survive it:**

    inactive US equity assets enumerated            19,188
    delisted names tried for daily bars                  8
    served a full daily path                             7

    EIO    767 daily bars   2016-01-04 .. 2019-01-18
    BHBK   815 daily bars   2016-01-04 .. 2019-03-29
    EEP    747 daily bars   2016-01-04 .. 2018-12-19
    YESR   277 daily bars   2017-08-30 .. 2018-10-04
    OCIP   637 daily bars   2016-01-04 .. 2018-07-13

**Three limits, stated because they bound what the finding licenses:**

1. **The IEX feed serves NONE of it** - zero bars for every delisted name tried. The histories come
   from `feed=sip`, and the request that returned them used this project's existing paper key.
   **Whether SIP historical data is a free-tier entitlement or an attribute of this account is NOT
   established here**, and it is the first thing to settle before anything is built on this.
2. **Coverage starts 2016-01-04** in every name measured. A study window opening before 2016 is
   still unserved. `PR-002`'s and `PR-005`'s windows both open 2016-08-01, inside it.
3. **This probe answers about PRICES only.** The claim also appears about point-in-time index
   constituents (`DR-003`), historical intraday spreads (`DR-004`, `DR-005`) and the event schedule
   (`EVENT_SPEC`). None of those is touched by this measurement and none is refuted by it.

Read-only: GET only, no write verb, no order, no account mutation. Reaches
`data.alpaca.markets`, which is neither the allowlisted broker host nor the forbidden live one -
`registry/broker_policy.yml`'s allowlist is the boundary on which ACCOUNT may be written, and this
writes nothing.

    python tools/probe_alpaca_delisted.py
    python tools/probe_alpaca_delisted.py --sample 20

Needs `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`; reports UNAVAILABLE without them rather than
failing. Network tool, never run in CI (`CI_POLICY` section 4).
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

ASSETS = "https://paper-api.alpaca.markets/v2/assets"
BARS = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
REAL_EXCHANGES = {"NASDAQ", "NYSE", "ARCA", "AMEX"}


def _headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": os.environ.get("APCA_API_KEY_ID", ""),
        "APCA-API-SECRET-KEY": os.environ.get("APCA_API_SECRET_KEY", ""),
        "User-Agent": "SwingDesk-probe/1.0",
    }


def get(url: str) -> tuple[int, object]:
    """One GET. A non-200 is returned rather than raised - a probe reports, it does not die."""
    try:
        request = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")[:300]
    except Exception as error:  # noqa: BLE001 - the message is the point
        return -1, f"{type(error).__name__}: {error}"


def daily_history(symbol: str, feed: str) -> tuple[int, str, str]:
    """Every daily bar the feed will serve, paged to the end. `(count, first, last)`."""
    total, first, last, token = 0, "", "", None
    while True:
        url = (f"{BARS.format(symbol=symbol)}?timeframe=1Day"
               f"&start=2010-01-01T00:00:00Z&end=2025-12-31T00:00:00Z&limit=10000&feed={feed}")
        if token:
            url += f"&page_token={token}"
        status, body = get(url)
        if status != 200 or not isinstance(body, dict):
            return -1, f"HTTP {status}", str(body)[:60]
        bars = body.get("bars") or []
        if bars:
            first = first or str(bars[0].get("t"))[:10]
            last = str(bars[-1].get("t"))[:10]
        total += len(bars)
        token = body.get("next_page_token")
        if not token:
            return total, first, last


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", type=int, default=5,
                        help="how many delisted names to pull a full history for")
    args = parser.parse_args(argv)

    if not (os.environ.get("APCA_API_KEY_ID") and os.environ.get("APCA_API_SECRET_KEY")):
        print("delisted history: UNAVAILABLE - APCA_API_KEY_ID/SECRET are not in the environment")
        return 0

    status, body = get(f"{ASSETS}?status=inactive&asset_class=us_equity")
    if status != 200 or not isinstance(body, list):
        print(f"delisted history: UNAVAILABLE - assets endpoint returned {status}: "
              f"{str(body)[:120]}")
        return 0

    listed = [a for a in body if a.get("exchange") in REAL_EXCHANGES
              and str(a.get("symbol", "")).isalpha()]
    print(f"inactive US equity assets enumerated : {len(body):,}")
    print(f"  of those on a real exchange        : {len(listed):,}")
    print()

    served = 0
    print(f"{'symbol':8} {'feed':5} {'bars':>6}  range")
    for asset in listed[:args.sample]:
        symbol = asset["symbol"]
        for feed in ("iex", "sip"):
            count, first, last = daily_history(symbol, feed)
            if count < 0:
                print(f"{symbol:8} {feed:5} {first:>6}  {last}")
            else:
                print(f"{symbol:8} {feed:5} {count:>6}  {first} .. {last}")
                if feed == "sip" and count:
                    served += 1
    print()
    print(f"delisted names served a daily path: {served} of {min(args.sample, len(listed))}")
    if served:
        print("  The PRICE half of \"no free source serves delisted history\" does not survive this.")
        print("  Whether SIP historical is a free-tier entitlement or this account's is NOT")
        print("  established here, and is the first thing to settle before building on it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
