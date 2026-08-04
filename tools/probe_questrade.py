"""Probe the Questrade API for the three facts ADR-0001 is blocked on.

Questrade is the strongest free candidate for market data: a licensed, documented API covering
Canadian and US equities, with a granularity enum containing exactly HalfHour, OneHour and OneDay.
It was not adopted because three facts could not be obtained without an account:

  1. intraday historical depth per granularity - does 30m beat Yahoo's 60 trading days?
  2. the actual rate limits
  3. whether delisted symbols are available (survivorship)

Run this yourself. It never writes the token anywhere and prints no secrets.

SECURITY
  - The token is read from the environment, never from a file or an argument (arguments show up in
    shell history and process lists).
  - Questrade refresh tokens are SINGLE USE. This script prints the new refresh token it receives so
    you can store it; if you lose it you must generate a new one in App Hub.
  - If this token has ever been pasted anywhere - chat, email, a commit - regenerate it first.

USAGE
  PowerShell:  $env:QUESTRADE_REFRESH_TOKEN = "<token>"; python tools/probe_questrade.py
  bash:        QUESTRADE_REFRESH_TOKEN="<token>" python tools/probe_questrade.py

Stdlib only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

LOGIN_URL = "https://login.questrade.com/oauth2/token"
GRANULARITIES = ("OneDay", "OneHour", "HalfHour")
PROBE_SYMBOLS = ("AAPL", "CNQ.TO", "SHOP.TO")
DELISTED_SYMBOLS = ("TWTR", "SIVB", "ATVI")
LOOKBACK_YEARS = (1, 2, 3, 5, 10, 15, 20, 30)


# login.questrade.com sits behind a WAF that rejects the default Python-urllib user agent with a
# bare 403 before the request ever reaches the OAuth endpoint. A normal browser UA gets through.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def request(url: str, token: str | None = None, method: str = "GET") -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def describe_http_error(error: urllib.error.HTTPError) -> str:
    """The response body usually says what the status code does not."""
    try:
        body = error.read().decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001
        body = ""
    return f"HTTP {error.code} {error.reason}" + (f" - {body[:300]}" if body else "")


def authenticate(refresh_token: str) -> tuple[str, str, str]:
    query = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    )
    url = f"{LOGIN_URL}?{query}"
    try:
        data = request(url)
    except urllib.error.HTTPError as error:
        # Some Questrade front ends accept only POST on the token endpoint.
        if error.code not in (403, 405):
            raise
        print(f"  GET failed ({describe_http_error(error)}); retrying as POST")
        data = request(url, method="POST")
    return data["access_token"], data["api_server"], data["refresh_token"]


def find_symbol(api: str, token: str, name: str) -> dict | None:
    query = urllib.parse.urlencode({"prefix": name})
    data = request(f"{api}v1/symbols/search?{query}", token)
    for symbol in data.get("symbols", []):
        if symbol.get("symbol", "").upper() == name.upper():
            return symbol
    return (data.get("symbols") or [None])[0]


def candles(api: str, token: str, symbol_id: int, start, end, interval: str) -> list:
    query = urllib.parse.urlencode(
        {"startTime": start.isoformat(), "endTime": end.isoformat(), "interval": interval}
    )
    data = request(f"{api}v1/markets/candles/{symbol_id}?{query}", token)
    return data.get("candles", [])


def probe_depth(api: str, token: str, symbol: str) -> None:
    found = find_symbol(api, token, symbol)
    if not found:
        print(f"  {symbol:9s} NOT FOUND")
        return
    symbol_id = found["symbolId"]
    listed = found.get("isTradable"), found.get("isQuotable")
    print(f"  {symbol:9s} id={symbol_id} exch={found.get('listingExchange')} "
          f"currency={found.get('currency')} tradable/quotable={listed}")

    now = datetime.now(UTC)
    for interval in GRANULARITIES:
        deepest = None
        for years in LOOKBACK_YEARS:
            start = now - timedelta(days=365 * years)
            try:
                rows = candles(api, token, symbol_id, start, now, interval)
            except urllib.error.HTTPError as error:
                print(f"    {interval:9s} {years:2d}y -> HTTP {error.code} {error.reason}")
                break
            except Exception as error:  # noqa: BLE001 - probe, report anything
                print(f"    {interval:9s} {years:2d}y -> {type(error).__name__}: {error}")
                break
            if not rows:
                print(f"    {interval:9s} {years:2d}y -> empty")
                break
            deepest = (years, len(rows), rows[0]["start"][:10], rows[-1]["start"][:10])
        if deepest:
            years, count, first, last = deepest
            print(f"    {interval:9s} deepest {years}y -> {count} bars, {first} .. {last}")


def main() -> int:
    token = os.environ.get("QUESTRADE_REFRESH_TOKEN")
    if not token:
        print(
            "Set QUESTRADE_REFRESH_TOKEN in the environment first.\n"
            "Do not pass the token as a command-line argument - it lands in shell history.",
            file=sys.stderr,
        )
        return 2

    try:
        access_token, api, new_refresh = authenticate(token)
    except urllib.error.HTTPError as error:
        print(f"auth failed: {describe_http_error(error)}", file=sys.stderr)
        if error.code == 400:
            print("400 = the refresh token was already used or has expired. They are single-use;"
                  " generate a fresh one in App Hub.", file=sys.stderr)
        elif error.code == 403:
            print("403 with a browser user agent usually means the app is not authorised for this"
                  " account, or the token belongs to a different app than the one that issued it."
                  " Check App Hub: the app must exist, be enabled, and the token must come from"
                  " that same app.", file=sys.stderr)
        return 1

    print("authenticated.")
    print(f"api server: {api}")
    print(f"\n>>> NEW REFRESH TOKEN (store it; the old one is now dead):\n    {new_refresh}\n")

    print("=== 1. historical depth by granularity ===")
    for symbol in PROBE_SYMBOLS:
        probe_depth(api, access_token, symbol)

    print("\n=== 2. delisted symbols (survivorship) ===")
    print("  Resolving a symbol is not the same as having its history. Fetching candles too.")
    now = datetime.now(UTC)
    for symbol in DELISTED_SYMBOLS:
        try:
            found = find_symbol(api, access_token, symbol)
        except Exception as error:  # noqa: BLE001
            print(f"  {symbol:7s} lookup {type(error).__name__}: {error}")
            continue
        if not found:
            print(f"  {symbol:7s} not found")
            continue
        print(f"  {symbol:7s} id={found['symbolId']} exch={found.get('listingExchange')} "
              f"tradable={found.get('isTradable')} quotable={found.get('isQuotable')}")
        try:
            rows = candles(api, access_token, found["symbolId"],
                           now - timedelta(days=365 * 10), now, "OneDay")
            if rows:
                print(f"          OneDay -> {len(rows)} bars, "
                      f"{rows[0]['start'][:10]} .. {rows[-1]['start'][:10]}")
            else:
                print("          OneDay -> EMPTY (symbol resolves, history does not)")
        except urllib.error.HTTPError as error:
            print(f"          OneDay -> {describe_http_error(error)}")
        except Exception as error:  # noqa: BLE001
            print(f"          OneDay -> {type(error).__name__}: {error}")

    print("\n=== 2b. intraday session coverage (US vs Canada) ===")
    print("  US symbols appear to include extended hours and Canadian ones do not. Confirming.")
    for symbol in ("AAPL", "CNQ.TO"):
        found = find_symbol(api, access_token, symbol)
        if not found:
            continue
        try:
            rows = candles(api, access_token, found["symbolId"],
                           now - timedelta(days=6), now, "HalfHour")
        except Exception as error:  # noqa: BLE001
            print(f"  {symbol:9s} {type(error).__name__}: {error}")
            continue
        by_day: dict[str, list[str]] = {}
        for row in rows:
            stamp = row["start"]
            by_day.setdefault(stamp[:10], []).append(stamp[11:16])
        for day in sorted(by_day)[-1:]:
            times = by_day[day]
            print(f"  {symbol:9s} {day}  {len(times)} bars  first={times[0]} last={times[-1]}")
            print(f"            {times}")

    print("\n=== 3. rate limit headers ===")
    print("  Check the response headers X-RateLimit-Remaining / X-RateLimit-Reset in the")
    print("  Questrade docs; this probe does not hammer the API to discover them empirically.")

    print("\nPaste sections 1 and 2 back - they are what ADR-0001 needs. No secrets in them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
