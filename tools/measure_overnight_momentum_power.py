"""Overnight momentum on single stocks: the width a study of it would read. A power measurement.

**Sized 2026-09-27 and NOT registered - owner ruling the same night.** The owner chose this source
when asked what could raise income; before a registration spent a trial, this measured the width
the design below would read, and no return of the rule: the paired bootstrap's 95% interval on
the book's geometric excess over `SPY` held is about 18 points a year wide over forty-eight
months, so the smallest separable excess is about 13 points - above the published long-SHORT
effect, and a long-only book keeps only part of that. Asked, the owner ruled: do not spend the
trial (`RETURN_SOURCE_REGISTER` §3.2).

**The source.** Lou, Polk & Skouras (2019, *Journal of Financial Economics* 134, "A tug of war:
Overnight versus intraday expected returns") decompose fourteen cross-sectional strategies over
1993-2013 and find momentum's profit earned entirely overnight: the long-short momentum portfolio's
overnight CAPM alpha is 0.98% a month (t = 3.84) and its intraday alpha -0.02%, with the overnight
component carrying a Sharpe ratio of 0.77 against 0.31 close to close. Their open is the VWAP of the
first half hour, not an auction. The mechanism they document is a tug of war between clienteles
trading at the open and through the session - the same source `PR-034` found on small caps.

**The construction a registration would have fixed:**

* **formation** - at the last session of each month, every admitted common stock (the live liquidity
  rule; funds and test issues excluded by the directory) ranked by its return from 252 sessions to
  21 sessions before - the classic twelve-minus-one. The top decile is next month's book, equally
  weighted;
* **the night** - every session of the following month, each name bought at the closing auction and
  sold at the next opening auction, on the daily bars' close and open, charged the venue's fees;
* **the day** - the same dollar in `SPY` from the opening auction to the closing one, as `PR-035`'s
  book does, charged the fees;
* **the contrast** - that book's geometric excess over holding `SPY`, monthly, paired bootstrap
  (`run_pr037`), over the forty-eight months ending with the last whole month every stored name
  reaches.

**What the bars cannot see:** the store carries no dividends for single stocks, so a stock's night
over its ex-date reads the dividend as a loss - biased AGAINST the book by the winners' yield.

    PYTHONPATH=$PWD/src python tools/measure_overnight_momentum_power.py --data DIR --as-of T
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from array import array
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr031 as p31
import run_pr037 as p37
import run_pr040 as p40
from run_pr021 import liquidity_rule, stock_symbols
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data.directory import DirectoryStore

OUT = REPO / "docs" / "decisions" / "measurements" / "overnight-momentum-power-2026-09-27.json"

BENCHMARK = "SPY"
#: The window's last month: the last whole month every stored name reaches (the store refreshes
#: names on a weekly rotation, so its most recent weeks are partial).
LAST_MONTH = (2026, 8)
WINDOW_MONTHS = 48
LOOKBACK = 252
SKIP = 21
DECILE = 0.10
MIN_NAMES = 300
SEED = 20260928
NAN = float("nan")


def month_ends(calendar: Sequence[date]) -> list[int]:
    """The index of each month's last session."""
    return [i for i, d in enumerate(calendar)
            if i + 1 == len(calendar) or calendar[i + 1].month != d.month]


def window(calendar: Sequence[date]) -> tuple[int, int, list[int]]:
    """`(first formation, last session, formations)` - forty-eight holding months ending LAST_MONTH.

    A holding month is traded from its previous month's last session, so the first formation is
    the last session of the month before the window.
    """
    ends = month_ends(calendar)
    last_year, last_month = LAST_MONTH
    last = max(i for i in ends if (calendar[i].year, calendar[i].month) == (last_year, last_month))
    position = ends.index(last)
    formations = ends[position - WINDOW_MONTHS:position]
    if len(formations) < WINDOW_MONTHS or formations[0] < LOOKBACK:
        raise SystemExit("the benchmark's calendar does not reach back a year before the window")
    return formations[0], last, formations


@dataclass
class Panel:
    calendar: list[date]
    first: int
    closes: dict[str, array[float]] = field(default_factory=dict)
    opens: dict[str, array[float]] = field(default_factory=dict)
    admitted: dict[int, list[str]] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def close(self, name: str, t: int) -> float:
        return self.closes[name][t - self.first]

    def open(self, name: str, t: int) -> float:
        return self.opens[name][t - self.first]


def load(args: argparse.Namespace) -> tuple[Panel, list[int], int, dict[str, Any]]:
    store = BarStore(args.data / "bars.duckdb")
    directory = DirectoryStore(args.data / "directory.duckdb")
    as_of = p31.read_instant(args.as_of, store.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC))
    rule, rule_values = liquidity_rule()
    stocks, funds = stock_symbols(directory, as_of)
    spy = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    calendar = [bar.session_date for bar in spy.bars]
    start, last, formations = window(calendar)
    first = start - LOOKBACK
    panel = Panel(calendar, first, counts={})
    index_of = {d: i for i, d in enumerate(calendar)}
    size = last - first + 1
    for name in (BENCHMARK, *sorted(store.instrument_ids(as_of))):
        if name != BENCHMARK:
            if name in funds:
                panel.counts["funds_excluded"] = panel.counts.get("funds_excluded", 0) + 1
                continue
            if name not in stocks:
                panel.counts["type_unknown"] = panel.counts.get("type_unknown", 0) + 1
                continue
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series is None or not series.bars:
            continue
        position = {bar.session_date: k for k, bar in enumerate(series.bars)}
        admitted = [t for t in formations if (k := position.get(calendar[t])) is not None
                    and rule.admits(series, k)] if name != BENCHMARK else []
        if name != BENCHMARK and not admitted:
            continue
        opens, closes = array("d", [NAN]) * size, array("d", [NAN]) * size
        for bar in series.bars:
            t = index_of.get(bar.session_date)
            if t is not None and first <= t <= last:
                opens[t - first], closes[t - first] = float(bar.open), float(bar.close)
        panel.opens[name], panel.closes[name] = opens, closes
        for t in admitted:
            panel.admitted.setdefault(t, []).append(name)
    dividends = _dividends(store, BENCHMARK, as_of)
    store.close()
    directory.close()
    return panel, formations, last, {"as_of": as_of.isoformat(), "rule": rule_values,
                                     "spy_dividends": dividends}


def _dividends(store: BarStore, fund: str, as_of: datetime) -> dict[date, float]:
    import run_pr033 as p33

    return p33.dividends_of(store, fund, as_of)


def momentum(panel: Panel, name: str, t: int) -> float:
    """Twelve-minus-one: the close 21 sessions back over the close 252 sessions back."""
    early, late = panel.close(name, t - LOOKBACK), panel.close(name, t - SKIP)
    return late / early - 1.0 if early > 0 and late > 0 else NAN


def winners(panel: Panel, t: int) -> list[str]:
    ranked = [(m, name) for name in panel.admitted.get(t, [])
              if not math.isnan(m := momentum(panel, name, t))]
    if len(ranked) < MIN_NAMES:
        return []
    ranked.sort(reverse=True)
    return [name for _, name in ranked[:max(1, int(len(ranked) * DECILE))]]


def night_of(panel: Panel, name: str, d: int) -> float:
    """Bought at session d-1's close, sold at session d's open, less the venue's fees."""
    before, after = panel.close(name, d - 1), panel.open(name, d)
    if not before > 0 or not after > 0:
        return NAN
    if not cal.consecutive(cal.exchange_for(name), panel.calendar[d - 1], panel.calendar[d]):
        return NAN
    return ((after - before) / before - p40.CAT_PER_SHARE / before
            - (p40.SEC_RATE + (p40.TAF_PER_SHARE + p40.CAT_PER_SHARE) / after))


def book(panel: Panel, formations: Sequence[int], last: int,
         spy_dividends: Mapping[date, float]) -> tuple[dict[date, float], dict[date, float],
                                                       dict[str, int]]:
    """The book (winners by night, `SPY` by day) and `SPY` held, session by session."""
    daily: dict[date, float] = {}
    held: dict[date, float] = {}
    sizes: dict[str, int] = {}
    ends = [*formations[1:], last]
    for formed, until in zip(formations, ends, strict=True):
        names = winners(panel, formed)
        sizes[panel.calendar[formed].isoformat()] = len(names)
        for d in range(formed + 1, until + 1):
            nights = [v for name in names if not math.isnan(v := night_of(panel, name, d))]
            spy_open, spy_close = panel.open(BENCHMARK, d), panel.close(BENCHMARK, d)
            spy_before = panel.close(BENCHMARK, d - 1)
            if not nights or not spy_open > 0 or not spy_close > 0 or not spy_before > 0:
                continue
            night = sum(nights) / len(nights)
            day = ((spy_close - spy_open) / spy_open - p40.CAT_PER_SHARE / spy_open
                   - (p40.SEC_RATE + (p40.TAF_PER_SHARE + p40.CAT_PER_SHARE) / spy_close))
            session = panel.calendar[d]
            daily[session] = (1 + night) * (1 + day) - 1
            held[session] = (spy_close + spy_dividends.get(session, 0.0) - spy_before) / spy_before
    return daily, held, sizes


def power(args: argparse.Namespace) -> dict[str, Any]:
    """The primary contrast's interval WIDTH, before registration - never its centre."""
    from power_pr019 import assert_no_effect_leaked

    panel, formations, last, meta = load(args)
    daily, held, sizes = book(panel, formations, last, meta["spy_dividends"])
    cell = p37.paired_bootstrap(p40.monthly(daily), p40.monthly(held), 2000, SEED)
    width = cell["width"]
    counts = sorted(sizes.values())
    payload = {"measurement": "overnight-momentum-power", "power": True,
               "as_of": {"bars": meta["as_of"]},
               "months": len(p40.monthly(daily)), "sessions": len(daily),
               "winners_per_formation": {"fewest": counts[0], "most": counts[-1]},
               "width_a_year": width, "half_width": width / 2,
               "minimum_detectable": width / 2 * (1.96 + 0.84) / 1.96,
               "stocks_loaded": len(panel.closes) - 1, "excluded": panel.counts,
               "note": "bars with the fees; widths only, no estimate is written"}
    assert_no_effect_leaked(payload)
    return payload


def month_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    payload = power(args)
    out = args.out or OUT
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"overnight momentum power: {payload['months']} months, "
          f"width {payload['width_a_year']:.4f} a year, "
          f"minimum detectable {payload['minimum_detectable']:.4f}; "
          f"winners a formation {payload['winners_per_formation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


