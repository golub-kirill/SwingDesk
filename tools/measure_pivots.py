"""What `pivot.left` and `pivot.right` actually cost, measured on stored bars.

**The question, and why it is not obvious.** `DR-020` authors the watchlist transition graph, and
its `Ready → Triggered` edge fires when price breaks a prior swing high. That level is produced by
`derived_observations.pivots`, which — correctly — emits a pivot at the CONFIRMATION bar `P + right`
and never at `P`. So `right` is a look-ahead lag, not a smoothing knob, and the registry says so.

**The question it was built to answer, and the answer, which was no.** The hypothesis was that
confirmation SPENDS the entry budget: that by the time a level is knowable price has run past it, so
a small `entry.maximum_entry_atr` would leave the trigger permanently `Late`. **Measured 2026-08-24
over 400 instruments, the drift is negative at every setting on the grid** - at confirmation the
close sits 1.1 to 2.4 ATR BELOW the level, and it must, because a swing high is confirmed precisely
by the following `right` bars failing to exceed it. The two parameters never competed.

That paragraph is kept rather than deleted: the hypothesis was stated as a fact before it was
checked, which is what `AGENTS.md` §15 asks to be left visible. `DR-020` §7 carries the table.

**What it measures per (left, right), all descriptive:**

  * **density** - confirmed swing highs per instrument per 252 sessions. Too few and there is no
    structure to trade; too many and the level means nothing.
  * **confirmation drift** - `(close[P+right] - high[P]) / ATR[P]`, in ATR units. Where the market
    stands relative to the level at the moment the level becomes knowable.
  * **breakout base rate** - how often a confirmed high is exceeded within a horizon. **Not a win
    rate and not an edge**: it says price exceeded a recent high, and nothing about what followed or
    about costs.

**Descriptive, and deliberately not a study.** It measures a property of the DATA, the way
`measure_revisions.py` and `measure_liquidity_floor.py` do. It evaluates no strategy, compares no
arms and reports no return, so it spends no trial from `b.deflated_sharpe`'s budget. Choosing a
value from it is a separate act that needs a decision record or a pre-registration (`AGENTS.md` §8).

**Read-only, no network.** Opens `bars.duckdb` read-only and touches nothing else.

    python tools/measure_pivots.py --data data
    python tools/measure_pivots.py --data data --limit 200 --out docs/decisions/measurements/pivots.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.derived_observations.pivots import pivots

#: The grid. `left` and `right` must both be >= 1 (the component refuses otherwise). Kept small and
#: odd-free: these are candidate neighbourhood widths, not a search over a continuum.
GRID: tuple[tuple[int, int], ...] = (
    (2, 2), (3, 2), (3, 3), (5, 3), (5, 5), (10, 5), (10, 10),
)

#: Sessions after confirmation within which a break of the level counts. Chosen to bracket the
#: ratified holding period (`exit.max_holding_period` = 20) and the 5-session horizon `PR-013` used,
#: so the base rate can be read at both without a second run.
HORIZONS: tuple[int, ...] = (5, 20)

#: ATR window. `atr.period` is 14 and `assumed`; this measurement does not read the registry because
#: it is describing the DATA, not running a component under its ratified configuration.
ATR_PERIOD = 14


class _Series:
    """The minimal `BarSeries` shape `pivots()` reads: `.bars`, each with `.high` and `.low`."""

    __slots__ = ("bars",)

    def __init__(self, bars: Sequence[object]) -> None:
        self.bars = tuple(bars)


class _Bar:
    __slots__ = ("high", "low")

    def __init__(self, high: Decimal, low: Decimal) -> None:
        self.high = high
        self.low = low


def _atr(highs: list[float], lows: list[float], closes: list[float], index: int) -> float | None:
    """Wilder true range averaged over `ATR_PERIOD`, ending at `index`. `None` if too little data."""
    if index < ATR_PERIOD:
        return None
    ranges = []
    for i in range(index - ATR_PERIOD + 1, index + 1):
        previous_close = closes[i - 1]
        ranges.append(max(highs[i] - lows[i],
                          abs(highs[i] - previous_close),
                          abs(lows[i] - previous_close)))
    average = sum(ranges) / len(ranges)
    return average if average > 0 else None


def measure_instrument(
    highs: list[float], lows: list[float], closes: list[float], left: int, right: int
) -> dict[str, list[float]]:
    """Confirmation drift and breakout outcomes for one instrument at one (left, right)."""
    series = _Series([_Bar(Decimal(str(h)), Decimal(str(low))) for h, low in zip(highs, lows, strict=True)])
    found = pivots(series, left, right, highs=True)

    drift: list[float] = []
    broke: dict[int, list[float]] = {h: [] for h in HORIZONS}
    for pivot in found:
        p, c = pivot.index, pivot.confirmed_index
        atr = _atr(highs, lows, closes, p)
        if atr is None or c >= len(closes):
            continue
        level = highs[p]
        # How much of the entry budget the confirmation itself spent, in ATR at the pivot bar.
        drift.append((closes[c] - level) / atr)
        for horizon in HORIZONS:
            window = highs[c + 1: c + 1 + horizon]
            broke[horizon].append(1.0 if window and max(window) > level else 0.0)
    return {"drift": drift, **{f"broke_{h}": broke[h] for h in HORIZONS}}


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)

    def at(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]

    return {"p10": at(0.10), "p50": at(0.50), "p90": at(0.90),
            "mean": statistics.fmean(ordered), "n": len(ordered)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="measure_pivots", description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--limit", type=int, default=150,
                        help="instruments to sample; the store is an alphabetical prefix, so this "
                             "is a prefix of a prefix and the report says so")
    parser.add_argument("--min-bars", type=int, default=300)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    import duckdb

    store = args.data / "bars.duckdb"
    if not store.is_file():
        print(f"pivots: UNAVAILABLE - no bar store at {store}", file=sys.stderr)
        return 4
    connection = duckdb.connect(str(store), read_only=True)

    instruments = [
        row[0] for row in connection.execute(
            "SELECT instrument_id FROM bars GROUP BY instrument_id "
            "HAVING count(*) >= ? ORDER BY instrument_id LIMIT ?",
            [args.min_bars, args.limit],
        ).fetchall()
    ]
    print(f"pivots: {len(instruments)} instrument(s), {len(GRID)} (left, right) pair(s)\n")

    report: dict[str, object] = {"instruments": len(instruments), "grid": [], "atr_period": ATR_PERIOD}
    for left, right in GRID:
        drift: list[float] = []
        broke: dict[int, list[float]] = {h: [] for h in HORIZONS}
        sessions = 0
        pivot_count = 0
        for instrument in instruments:
            rows = connection.execute(
                "SELECT high, low, close FROM ("
                "  SELECT high, low, close, session_date, "
                "         row_number() OVER (PARTITION BY session_date ORDER BY knowledge_time DESC) rn"
                "  FROM bars WHERE instrument_id = ?"
                ") WHERE rn = 1 ORDER BY session_date",
                [instrument],
            ).fetchall()
            if len(rows) < args.min_bars:
                continue
            highs = [float(r[0]) for r in rows]
            lows = [float(r[1]) for r in rows]
            closes = [float(r[2]) for r in rows]
            sessions += len(rows)
            result = measure_instrument(highs, lows, closes, left, right)
            drift.extend(result["drift"])
            pivot_count += len(result["drift"])
            for horizon in HORIZONS:
                broke[horizon].extend(result[f"broke_{horizon}"])

        density = (pivot_count / sessions * 252) if sessions else 0.0
        stats = _percentiles(drift)
        line = {
            "left": left, "right": right,
            "pivots_per_252_sessions": round(density, 2),
            "confirmation_drift_atr": {k: round(v, 4) for k, v in stats.items()},
            **{f"breakout_rate_{h}": round(statistics.fmean(broke[h]), 4) if broke[h] else None
               for h in HORIZONS},
        }
        report["grid"].append(line)  # type: ignore[union-attr]
        print(f"  left={left:<3} right={right:<3} "
              f"pivots/yr {density:6.2f}   "
              f"drift ATR p50 {stats.get('p50', float('nan')):6.3f} "
              f"p90 {stats.get('p90', float('nan')):6.3f}   "
              f"broke@5 {line['breakout_rate_5']}  broke@20 {line['breakout_rate_20']}")

    connection.close()
    print("\nDescriptive only. Choosing a value from this needs a decision record or a "
          "pre-registration (AGENTS.md section 8).")
    print("The sample is an alphabetical prefix of the stored universe, which is itself a prefix "
          "of the directory (AGENTS.md section 12).")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"written {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
