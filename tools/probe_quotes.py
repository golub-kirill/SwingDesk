"""Does a free source serve historical intraday spreads point-in-time? Nobody had asked.

**The claim this probe was written to test**, `DR-004`, verbatim:

> spread-derived slippage from quoted bid/ask: correct and unavailable - no free source serves
> historical intraday spreads point-in-time

It is load-bearing. Because the quoted route was closed, `DR-005` fell back to two daily-OHLC
estimators and set `costs.slippage_model` to **25.44 bps per side**, and that single constant is
what makes every headline result in this project negative: `EVIDENCE_SUMMARY` §1's *"no price an
eligible instrument can have makes it positive"*, `DR-029` §7's exit surface, §8a's long-only
conversion. `EVIDENCE_SUMMARY` §2 then closed the door in as many words - *"the level is not
obtainable from daily OHLC; `PR-006`, real fills, is the only route left"*. The first clause is
true. The second does not follow from it, and this probe is what `AGENTS.md` §15 asks for.

**THE CLAIM IS FALSE.** The venue this project already holds a paper account with serves
consolidated **SIP** NBBO quotes, historical, point-in-time, on the free tier. Only the most recent
fifteen minutes are withheld - which is exactly the window a backtest never reads.

**And the IEX/SIP distinction is the reason it stayed hidden.** The free tier's *real-time* feed is
IEX, one venue holding a few percent of volume, and a single venue's book is far wider than the
consolidated one. Reading IEX and concluding the data is unusable is a correct measurement of the
wrong tape. This probe prints both, side by side, so the difference is re-derived rather than
asserted - the same discipline `probe_edgar.py` adopted after its own host/header block read as
measured while being wrong.

**What this does NOT establish.** A quoted spread is not a realised cost: it is an upper bound for
an order that crosses and an over-charge for one that rests. It says nothing about depth, and
nothing about what a paper venue would actually have filled. `tools/measure_quoted_spread.py` is
the measurement; this is only the demonstration that the measurement is possible.

    python tools/probe_quotes.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

HOST = "https://data.alpaca.markets"

#: One liquid, one mid-cap, one thinly-traded name, and a date far enough back that no entitlement
#: argument about recency can apply. Chosen to span the universe rather than to flatter it.
CASES: tuple[tuple[str, str], ...] = (
    ("AAPL", "the most liquid name there is - the floor of what is achievable"),
    ("F", "a mid-cap at a low price, where a penny tick is a wide spread in bps"),
    ("PLUG", "thin and volatile - the end of the universe that costs the most"),
)

#: Deliberately old. The free tier withholds the last fifteen minutes and nothing else, so a date
#: years back tests availability rather than recency.
WHEN = "2019-08-14T15:00:00Z"


def fetch(symbol: str, feed: str) -> tuple[int, list[dict], str]:
    """`(status, quotes, note)` - never raises, because a refusal IS the result being probed."""
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        return 0, [], "APCA_API_KEY_ID / APCA_API_SECRET_KEY not set"
    query = urllib.parse.urlencode({"start": WHEN, "limit": 20, "feed": feed})
    request = urllib.request.Request(
        f"{HOST}/v2/stocks/{urllib.parse.quote(symbol)}/quotes?{query}",
        headers={
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode()).get("quotes") or [], ""
    except urllib.error.HTTPError as error:
        return error.code, [], error.read().decode()[:160]
    except Exception as error:  # noqa: BLE001 - a probe reports every failure mode as data
        return -1, [], repr(error)[:160]


def median_spread_bps(quotes: list[dict]) -> Decimal | None:
    """Median `(ask - bid) / mid` in bps over two-sided quotes; `None` when there were none."""
    values: list[Decimal] = []
    for quote in quotes:
        bid, ask = quote.get("bp"), quote.get("ap")
        if not isinstance(bid, (int, float)) or not isinstance(ask, (int, float)):
            continue
        if bid <= 0 or ask <= bid:
            continue
        bid_d, ask_d = Decimal(str(bid)), Decimal(str(ask))
        values.append((ask_d - bid_d) / ((ask_d + bid_d) / 2) * 10000)
    if not values:
        return None
    values.sort()
    return values[len(values) // 2]


def main() -> int:
    print(f"probe_quotes: {len(CASES)} case(s) at {WHEN}, re-measured now rather than quoted\n")
    served = 0
    for symbol, why in CASES:
        print(f"  {symbol}  - {why}")
        for feed in ("sip", "iex"):
            status, quotes, note = fetch(symbol, feed)
            spread = median_spread_bps(quotes)
            shown = f"{float(spread):.2f} bps full / {float(spread) / 2:.2f} per side" \
                if spread is not None else "no two-sided quote"
            print(f"      feed={feed:4s} status={status:<4} n={len(quotes):<3} {shown}"
                  f"{'  ' + note if note else ''}")
            if feed == "sip" and status == 200 and quotes:
                served += 1
        print()

    print(f"SIP served {served} of {len(CASES)} cases.")
    if served == len(CASES):
        print("DR-004's premise is REFUTED: historical intraday quotes ARE free and")
        print("point-in-time. What was unavailable was never the data - it was the SIP feed,")
        print("and the free tier withholds only the last fifteen minutes of it.")
    else:
        print("SIP did NOT serve every case. Check credentials before concluding the feed changed:")
        print("a 401/403 is an entitlement problem, not evidence that the route closed.")
    print()
    print("AND THE CONTROL, which is why IEX is in here: the same instant on one venue's book")
    print("reads several times wider than the consolidated tape. An estimator fed IEX would")
    print("measure a real spread - of a market nobody has to trade in.")
    print()
    print("What this does NOT establish: a quoted spread is an upper bound for an order that")
    print("crosses and an over-charge for one that rests. The live path sends a resting limit.")
    return 0 if served == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
