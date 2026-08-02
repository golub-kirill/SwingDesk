"""Measure the NYSE and TSX trading calendars from the data itself.

CALENDAR_SPEC asserts three things it had not verified:
  1. the two exchanges diverge on ~16 sessions over ~2.9 years - but only the COUNT was known
  2. half-days exist and shorten the session - untested
  3. an unhandled half-day is a silent off-by-N in every intraday aggregate

This enumerates the divergent sessions rather than inferring them, and measures what a half-day
actually looks like in the bar data.

Depth constraints, measured (ADR-0001): 1h reaches ~725 trading days, 30m only ~60. So half-days
are probed at 1h, where the history is deep enough, and recent holiday divergences at 30m.

Requires yfinance. Read-only; writes nothing.

Usage:
    python tools/probe_calendar.py
"""

from __future__ import annotations

import warnings
from collections import Counter

warnings.filterwarnings("ignore")

import yfinance as yf  # noqa: E402

US = "AAPL"
CA = "CNQ.TO"
TZ = "America/New_York"

# Sessions the exchanges are expected to treat differently. Listed so the probe reports
# agreement or disagreement with an expectation, rather than just dumping dates.
EXPECTED = {
    "2026-05-18": "Victoria Day - TSX closed, NYSE open",
    "2026-05-25": "Memorial Day - NYSE closed, TSX open",
    "2026-06-19": "Juneteenth - NYSE closed, TSX open",
    "2026-07-01": "Canada Day - TSX closed, NYSE open",
    "2026-07-03": "Independence Day observed - NYSE closed, TSX open",
}

# Known or suspected US early closes (13:00 ET) within reach of 1h history.
HALF_DAY_CANDIDATES = [
    "2023-11-24", "2023-12-22",
    "2024-07-03", "2024-11-29", "2024-12-24",
    "2025-07-03", "2025-11-28", "2025-12-24",
]


def sessions(ticker: str, interval: str, period: str) -> dict[str, list[str]]:
    """Return {session_date: [bar times]} in exchange-local time."""
    frame = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    if frame.empty:
        return {}
    index = frame.index.tz_convert(TZ)
    out: dict[str, list[str]] = {}
    for stamp in index:
        out.setdefault(str(stamp.date()), []).append(stamp.strftime("%H:%M"))
    return out


def main() -> int:
    print("=== A. session-level divergence, 1h over ~725 trading days ===")
    us = sessions(US, "1h", "730d")
    ca = sessions(CA, "1h", "730d")
    if not us or not ca:
        print("  no data returned; cannot proceed")
        return 1

    us_days, ca_days = set(us), set(ca)
    common_start = max(min(us_days), min(ca_days))
    us_days = {d for d in us_days if d >= common_start}
    ca_days = {d for d in ca_days if d >= common_start}

    only_us = sorted(us_days - ca_days)
    only_ca = sorted(ca_days - us_days)
    print(f"  window {common_start} .. {max(us_days | ca_days)}")
    print(f"  sessions: US {len(us_days)}, CA {len(ca_days)}, both {len(us_days & ca_days)}")
    print(f"  US open / CA closed: {len(only_us)}")
    for day in only_us:
        print(f"      {day}  ({len(us[day])} bars)")
    print(f"  CA open / US closed: {len(only_ca)}")
    for day in only_ca:
        print(f"      {day}  ({len(ca[day])} bars)")

    print("\n=== B. short sessions, 1h ===")
    normal_us = Counter(len(v) for v in us.values()).most_common(1)[0][0]
    normal_ca = Counter(len(v) for v in ca.values()).most_common(1)[0][0]
    print(f"  modal bars/session: US {normal_us}, CA {normal_ca}")
    short_us = sorted(d for d, v in us.items() if len(v) < normal_us)
    short_ca = sorted(d for d, v in ca.items() if len(v) < normal_ca)
    print(f"  short US sessions: {len(short_us)}")
    for day in short_us:
        print(f"      {day}  {len(us[day])} bars  {us[day][0]}..{us[day][-1]}"
              f"   {EXPECTED.get(day, '')}")
    print(f"  short CA sessions: {len(short_ca)}")
    for day in short_ca:
        print(f"      {day}  {len(ca[day])} bars  {ca[day][0]}..{ca[day][-1]}")

    print("\n=== C. named half-day candidates ===")
    for day in HALF_DAY_CANDIDATES:
        u = us.get(day)
        c = ca.get(day)
        fmt = lambda bars: (f"{len(bars):2d} bars {bars[0]}..{bars[-1]}" if bars else "CLOSED")
        print(f"  {day}   US {fmt(u):<28} CA {fmt(c)}")

    print("\n=== C2. daily-vs-intraday reconciliation ===")
    print("  A daily bar on a short session means the market was open, so the intraday series is")
    print("  incomplete. Note the ratio is never 1.0 even on normal days - see CALENDAR_SPEC 2d.")
    suspects = ["2026-01-30", "2026-02-02", "2025-04-24"]
    controls = ["2026-01-29", "2026-02-03", "2025-04-23"]
    for ticker in (US, CA):
        handle = yf.Ticker(ticker)
        daily = handle.history(period="3y", interval="1d", auto_adjust=False)
        hourly = handle.history(period="730d", interval="1h", auto_adjust=False)
        if daily.empty or hourly.empty:
            continue
        daily.index = daily.index.tz_convert(TZ)
        hourly.index = hourly.index.tz_convert(TZ)
        print(f"  -- {ticker}")
        for label, days in (("suspect", suspects), ("control", controls), ("half-day", HALF_DAY_CANDIDATES[-3:])):
            for day in days:
                drow = daily[daily.index.strftime("%Y-%m-%d") == day]
                hrow = hourly[hourly.index.strftime("%Y-%m-%d") == day]
                if drow.empty:
                    print(f"     {label:9s} {day}  no daily bar - market closed")
                    continue
                dv = float(drow["Volume"].iloc[0])
                hv = float(hrow["Volume"].sum()) if len(hrow) else 0.0
                dc = float(drow["Close"].iloc[0])
                hc = float(hrow["Close"].iloc[-1]) if len(hrow) else float("nan")
                ratio = hv / dv if dv else float("nan")
                print(f"     {label:9s} {day}  bars={len(hrow):2d}  vol_ratio={ratio:5.3f}  "
                      f"daily_close={dc:9.2f}  last_1h={hc:9.2f}  diff={dc - hc:+7.2f}")

    print("\n=== D. recent divergence at 30m (60-day window) ===")
    us30 = sessions(US, "30m", "60d")
    ca30 = sessions(CA, "30m", "60d")
    if us30 and ca30:
        start = max(min(us30), min(ca30))
        u30 = {d for d in us30 if d >= start}
        c30 = {d for d in ca30 if d >= start}
        print(f"  window {start} .. {max(u30 | c30)}")
        for day in sorted((u30 | c30) - (u30 & c30)):
            side = "US only" if day in u30 else "CA only"
            print(f"      {day}  {side:8s} {EXPECTED.get(day, '')}")
        modal30_us = Counter(len(v) for v in us30.values()).most_common(1)[0][0]
        modal30_ca = Counter(len(v) for v in ca30.values()).most_common(1)[0][0]
        print(f"  modal bars/session at 30m: US {modal30_us}, CA {modal30_ca}")
        for label, data, modal in ((US, us30, modal30_us), (CA, ca30, modal30_ca)):
            odd = {d: v for d, v in data.items() if len(v) != modal}
            print(f"  {label} sessions not at modal length: {len(odd)}")
            for day, bars in sorted(odd.items()):
                print(f"      {day}  {len(bars)} bars  {bars[0]}..{bars[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
