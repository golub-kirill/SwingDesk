"""Which index does relative strength measure AGAINST - and can the answer change a ranking at all?

`CARD-001` ranks the universe by strength relative to the index. `M31-T0464` says *relative strength
against the index*, and the course names three of them as Definitions: **S&P 500** (`M31-T0454`),
**Nasdaq-100** (`M31-T0455`), **Russell 2000** (`M31-T0456`). It does not say which one a candidate
is measured against, and this project has no index series at all - the store holds instruments from
the NASDAQ Trader directory, so the only stand-in is an ETF that tracks one.

**The first version of this tool measured the wrong thing, and the result looked like a finding.**
It computed relative strength as `(1 + own) / (1 + benchmark)` on one cross-section and reported
Spearman rho = 1.000000 between every pair of benchmarks, at every lookback, over 1,148 names -
then called that "near-perfect agreement". It is not agreement. **It is an algebraic identity**: on
a single date the benchmark's return is one constant for every name, so dividing by it is a strictly
monotone transform of the name's own return, and a monotone transform cannot reorder anything.
Subtracting instead gives the same identity. The reading dressed arithmetic as evidence, which is
the failure this repository keeps paying for, so the identity is now asserted as a CONTROL that must
come back exactly 1 - and the real question is asked separately.

**The real question: is there a form of relative strength a benchmark can move?** Two ways out of
the identity, and both are in the course:

  - **Path dependence.** *How often* a name beat the benchmark over the window is not a function of
    the endpoint return, so it is not a monotone transform of it and the benchmark can reorder.
  - **A per-name benchmark.** Sector-relative strength - `M31-T0460`, `M31-T0461`, `M31-T0462` -
    gives different names different denominators, which is exactly what a common factor is not.

This tool measures the first; the second needs the classification store and is named as the next
check rather than guessed at.

**And the bias that survives every choice.** Relative strength is computed from `Series.RAW`, which
is what both decision paths read. Raw prices drop on an ex-dividend date, so a payer looks weaker
than a non-payer by roughly its yield over the lookback, whatever the benchmark. The store holds no
adjusted series, so the drag is uncorrected; it is measured here rather than assumed away.

**Actions are read at the RUN's clock, not the bar store's.** The two stores are filled by different
passes, and reading actions at the bar store's knowledge time hides every action fetched since the
last bar refresh - which on the first run is all of them. That is the same trap
`SESSION-HANDOFF-2026-08-24` §3 records for the classification store, and this tool tripped it: the
first run reported "0 payments" for five funds holding 101 dividends between them.

    python tools/measure_benchmark.py --data C:/PycharmProjects/SwingDesk/data \\
        --out docs/decisions/measurements/benchmark-2026-08-24.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.application.universe import ADTV_WINDOW
from swingdesk.contracts.market import BarSeries, CorporateActionKind, Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.directory import DirectoryStore

#: The course's three indexes, each mapped to the most liquid ETF that tracks it. The mapping is the
#: AUTHORED half; the indexes are the course's (M31-T0454 / T0455 / T0456).
PROXIES = {"S&P 500": "SPY", "Nasdaq-100": "QQQ", "Russell 2000": "IWM"}

#: Three funds tracking the SAME index. Kept because a reader will ask, and because the answer is
#: settled by the identity below rather than by their tracking error.
SAME_INDEX = ("SPY", "IVV", "VOO")

#: Lookbacks to sweep, in sessions. `rs.lookback` is unset and gets its value from a study, never
#: from here - these span the range a study would plausibly register.
LOOKBACKS = (63, 126, 252)


def _return(series: BarSeries, end_index: int, lookback: int) -> Decimal | None:
    start = end_index - lookback
    if start < 0 or end_index >= len(series.bars):
        return None
    first = series.bars[start].close
    if first <= 0:
        return None
    return (series.bars[end_index].close - first) / first


def _daily_returns(series: BarSeries, end_index: int, lookback: int) -> list[Decimal] | None:
    start = end_index - lookback
    if start < 0 or end_index >= len(series.bars):
        return None
    out: list[Decimal] = []
    for index in range(start + 1, end_index + 1):
        previous = series.bars[index - 1].close
        if previous <= 0:
            return None
        out.append((series.bars[index].close - previous) / previous)
    return out


def spearman(left: list[float], right: list[float]) -> float | None:
    """Rank correlation. Ties take their average rank, which is what makes it Spearman rather than
    a correlation of whatever order `sorted` happened to produce."""
    if len(left) != len(right) or len(left) < 3:
        return None

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        position = 0
        while position < len(order):
            end = position
            while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
                end += 1
            average = (position + end) / 2 + 1
            for index in range(position, end + 1):
                out[order[index]] = average
            position = end + 1
        return out

    a, b = ranks(left), ranks(right)
    n = len(a)
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a <= 0 or var_b <= 0:
        return None
    return cov / (var_a * var_b) ** 0.5


def _dividend_drag(store: BarStore, symbol: str, actions_as_of: datetime,
                   series: BarSeries) -> dict[str, object]:
    """Cash dividends over the stored window, as a share of the opening price.

    The size of the bias a RAW-price relative strength carries. Not a correction - there is nothing
    here to correct it with - a measurement of what is being ignored.
    """
    actions = store.actions_as_of(symbol, actions_as_of)
    window = (series.bars[0].session_date, series.bars[-1].session_date)
    inside = [
        a for a in actions
        if a.kind is CorporateActionKind.DIVIDEND and window[0] <= a.effective_date <= window[1]
    ]
    paid = sum((a.value for a in inside), start=Decimal(0))
    opening = series.bars[0].close
    years = Decimal((window[1] - window[0]).days) / Decimal(365)
    share = paid / opening if opening > 0 else Decimal(0)
    return {
        "dividends_in_window": len(inside),
        "cash_paid": float(paid),
        "share_of_opening_price": round(float(share), 6),
        "annualised_pct": round(float(share / years * 100), 4) if years > 0 else None,
        "window": [str(window[0]), str(window[1])],
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_benchmark")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    actions_clock = datetime.now(UTC)

    with (
        BarStore(args.data / "bars.duckdb") as store,
        DirectoryStore(args.data / "directory.duckdb") as directory,
    ):
        as_of = store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("bar store is empty")

        benchmarks: dict[str, BarSeries] = {}
        for symbol in sorted({*PROXIES.values(), *SAME_INDEX}):
            series = store.as_of(symbol, Interval.DAY, Series.RAW, as_of)
            if not series.bars:
                raise SystemExit(f"{symbol} is not in the bar store - fetch it first")
            benchmarks[symbol] = series

        print(f"bars as of   {as_of.isoformat()}")
        print(f"actions as of {actions_clock.isoformat()}  (the RUN's clock - see the docstring)")
        for symbol, series in benchmarks.items():
            print(f"  {symbol:>4}  {len(series.bars):>5} bars  "
                  f"{series.bars[0].session_date} -> {series.bars[-1].session_date}")

        print("\nDIVIDEND DRAG on a RAW-price relative strength")
        drag: dict[str, object] = {}
        for symbol, series in benchmarks.items():
            measured = _dividend_drag(store, symbol, actions_clock, series)
            drag[symbol] = measured
            print(f"  {symbol:>4}  {measured['dividends_in_window']:>3} payments  "
                  f"{float(measured['share_of_opening_price']) * 100:>6.2f}% of the opening price"
                  f"  {measured['annualised_pct']:>6}% a year")

        rule = rules.LiquidityRule(
            min_price=Decimal("5.00"), min_adtv=Decimal(5_000_000),
            adtv_window=ADTV_WINDOW, min_history=250,
        )
        stored = set(store.instrument_ids(as_of))
        admitted: dict[str, BarSeries] = {}
        for entry in directory.as_of(as_of, eligible_only=True):
            if entry.symbol not in stored or entry.symbol in benchmarks:
                continue
            series = store.as_of(entry.symbol, Interval.DAY, Series.RAW, as_of)
            if series.bars and rule.admits(series):
                admitted[entry.symbol] = series
        print(f"\nuniverse for the ranking: {len(admitted)} admitted names")

        controls: list[dict[str, object]] = []
        path_results: list[dict[str, object]] = []

        for lookback in LOOKBACKS:
            own_return: dict[str, float] = {}
            own_daily: dict[str, list[Decimal]] = {}
            for name, series in admitted.items():
                end = len(series.bars) - 1
                value = _return(series, end, lookback)
                daily = _daily_returns(series, end, lookback)
                if value is None or daily is None:
                    continue
                own_return[name] = float(value)
                own_daily[name] = daily

            for symbol, series in benchmarks.items():
                end = len(series.bars) - 1
                bench_return = _return(series, end, lookback)
                bench_daily = _daily_returns(series, end, lookback)
                if bench_return is None or bench_daily is None:
                    continue

                # CONTROL: the point-to-point ratio must rank EXACTLY as the raw return does. It is
                # an identity, not a result - if this is ever not 1.0 the arithmetic is broken.
                shared = sorted(own_return)
                ratio = [float((1 + Decimal(str(own_return[n]))) / (1 + bench_return))
                         for n in shared]
                rho = spearman(ratio, [own_return[n] for n in shared])
                controls.append({
                    "lookback": lookback, "benchmark": symbol, "names": len(shared),
                    "spearman_vs_raw_return": None if rho is None else round(rho, 12),
                })

                # THE REAL MEASURE: how often the name beat the benchmark, session by session. Not a
                # function of the endpoint return, so a benchmark CAN reorder it.
                beat: dict[str, float] = {}
                for name in shared:
                    daily = own_daily[name]
                    if len(daily) != len(bench_daily):
                        continue
                    wins = sum(1 for a, b in zip(daily, bench_daily, strict=True) if a > b)
                    beat[name] = wins / len(daily)
                if len(beat) >= 3:
                    names = sorted(beat)
                    rho_vs_raw = spearman([beat[n] for n in names],
                                          [own_return[n] for n in names])
                    path_results.append({
                        "lookback": lookback, "benchmark": symbol, "names": len(names),
                        "measure": "share of sessions beating the benchmark",
                        "spearman_vs_raw_return": (
                            None if rho_vs_raw is None else round(rho_vs_raw, 6)
                        ),
                        "scores": beat,
                    })

    print("\nCONTROL - point-to-point RS must rank exactly as the raw return (an identity)")
    identical = [c for c in controls if c["spearman_vs_raw_return"] == 1.0]
    print(f"  {len(identical)} of {len(controls)} benchmark x lookback pairs return exactly 1.0")
    if len(identical) != len(controls):
        for c in controls:
            if c["spearman_vs_raw_return"] != 1.0:
                print(f"  BROKEN: {c['benchmark']} @ {c['lookback']} -> "
                      f"{c['spearman_vs_raw_return']}")
        return 1
    print("  So on ONE cross-section the benchmark cannot move the order. Dividing or subtracting")
    print("  a per-day constant is a monotone transform, and the choice of index is irrelevant to")
    print("  any ranking built that way - by algebra, not by measurement.")

    print("\nPATH-DEPENDENT RS - share of sessions the name beat the benchmark")
    print(f"{'lookback':>9} {'benchmark':>10} {'names':>7} {'rho vs raw return':>19}")
    for row in path_results:
        print(f"{row['lookback']:>9} {row['benchmark']:>10} {row['names']:>7} "
              f"{row['spearman_vs_raw_return']:>19}")

    print("\nDOES THE BENCHMARK MATTER, in the path form?")
    cross: list[dict[str, object]] = []
    by_key = {(r["lookback"], r["benchmark"]): r for r in path_results}
    for lookback in LOOKBACKS:
        for left, right in (("SPY", "QQQ"), ("SPY", "IWM"), ("QQQ", "IWM"), ("SPY", "IVV")):
            a, b = by_key.get((lookback, left)), by_key.get((lookback, right))
            if not a or not b:
                continue
            names = sorted(set(a["scores"]) & set(b["scores"]))  # type: ignore[index]
            rho = spearman([a["scores"][n] for n in names],  # type: ignore[index]
                           [b["scores"][n] for n in names])  # type: ignore[index]
            print(f"{lookback:>9} {left + ' vs ' + right:>14} {len(names):>7} "
                  f"{'n/a' if rho is None else f'{rho:.6f}':>10}")
            cross.append({"lookback": lookback, "left": left, "right": right,
                          "names": len(names),
                          "spearman": None if rho is None else round(rho, 6)})

    payload = {
        "bars_as_of": as_of.isoformat(),
        "actions_as_of": actions_clock.isoformat(),
        "proxies": PROXIES,
        "same_index_funds": list(SAME_INDEX),
        "admitted_names": len(admitted),
        "dividend_drag": drag,
        "identity_control": controls,
        "path_form_vs_raw_return": [
            {k: v for k, v in row.items() if k != "scores"} for row in path_results
        ],
        "path_form_across_benchmarks": cross,
        "not_measured": (
            "sector-relative strength (M31-T0460/0461/0462), which gives different names different "
            "denominators and is the other way out of the single-cross-section identity. It needs "
            "the classification store and is the next check, not a guess."
        ),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
