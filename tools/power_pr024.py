"""`PR-024`'s power estimate - how wide the interval on close-minus-open can be, before any minute.

**Widths only, never a level** (`power_pr019.assert_no_effect_leaked`). Everything here is a
dispersion, computed from the DAILY bars the store already holds, so the study's own inputs - the
minutes and the quotes - have not been fetched when this runs, and nothing it prints could tell the
author which way the answer goes.

**What the precision depends on, and why the sample is shaped as it is.** The difference between
entering at the close and at the open contains the market's own move from the open to the close,
which every name on a date shares. That part averages out over DATES, not over names, so the
interval is governed by how many dates the sample holds; names per date only average the part the
names do not share. So the estimate is split in two:

* `between_date_sd` - the spread of the per-date averages of a proxy difference;
* `within_date_sd` - the spread of names around their own date's average;

and the half-width at `D` dates and `k` names per date is

    1.96 * sqrt(between^2 / D + (within^2 + cost^2) / (D * k))

where `cost` is the dispersion of the entry spread itself, which daily bars cannot see.

**The proxy.** A daily bar has no 15:55 print, so the close arm is proxied by the session's CLOSE and
the open arm by its OPEN, each walked through the ratified exit exactly as the study walks it
(`run_pr024.walk_entry`); the close arm's entry day holds nothing after its fill. Costs are zero in
the proxy - their dispersion is the `cost` term, bounded from `DR-040`'s own measurement: the widest
year of the opening window's p10-to-p90 range, read as a normal spread. The traded decile is more
liquid than that universe, so the bound is conservative.

**The check that refutes the estimate.** The formula is checked against a month-clustered bootstrap
on the pilot itself; `reproduces` is their ratio, and a study whose realised interval does not come
near its registered width has a broken design, which section 9 of the registration names.

    PYTHONPATH=$PWD/src python tools/power_pr024.py --data <store>
    python tools/power_pr024.py --report
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr024 as study
from power_pr019 import assert_no_effect_leaked
from run_pr014 import BENCHMARK
from run_pr016 import BLOCK, atr_registry, block_bootstrap, cluster_of
from swingdesk.contracts.market import Interval, Series
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import Minute

RESULT = REPO / "docs" / "prereg" / "results" / "PR-024-power.json"
SPREADS = REPO / "docs" / "decisions" / "measurements" / "quoted-spread-2026-09-06.json"

PILOT_DATES = 60
PILOT_PER_DATE = 20
PILOT_SEED = study.SAMPLE_SEED + 1
RESAMPLES = 2000
Z = 1.96
#: The one-sided z of 80% power: a true difference this many standard errors past the 1.96 bound is
#: detected four times in five.
Z_POWER = 0.8416
#: p90 minus p10 of a normal distribution, in standard deviations.
P10_TO_P90 = 2.563

GRID_DATES = (250, 400, 500, 750, 1000)
GRID_PER_DATE = (4, 6, 8, 10, 12)
#: The grid's last row: every formation session the window holds. A fixed count above the calendar
#: can never be drawn, and the first run of this tool found the only readable counts there - a
#: 48-month window holds 982 sessions and the grid stopped at a round 1,000.
EVERY = "Dall"
#: Requests per drawn entry: one minute session and three quote windows.
REQUESTS_PER_ENTRY = 4
#: Seconds a request costs in practice: the 0.32 s pace plus the round trip.
SECONDS_PER_REQUEST = 0.6


def cost_sd(path: Path = SPREADS) -> float:
    """The widest year's opening-window p10-to-p90 range, as a standard deviation, in return units."""
    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
    ranges = [float(row["p90"]) - float(row["p10"]) for row in rows
              if str(row["window"]).startswith("09:30")]
    if not ranges:
        raise SystemExit(f"{path.name} holds no opening-window rows")
    return max(ranges) / P10_TO_P90 / 10000


def components(values_by_date: Mapping[date, Sequence[float]]) -> dict[str, float]:
    """The between-date and within-date standard deviations of a per-entry quantity."""
    usable = {d: list(v) for d, v in values_by_date.items() if v}
    if len(usable) < 2:
        raise ValueError("at least two dates are needed to separate the two parts")
    per_date = [statistics.fmean(v) for v in usable.values()]
    deviations = [x - statistics.fmean(v) for v in usable.values() for x in v]
    pooled = [len(v) - 1 for v in usable.values()]
    within = (math.sqrt(sum(x * x for x in deviations) / sum(pooled))
              if sum(pooled) > 0 else 0.0)
    return {"between_date_sd": statistics.stdev(per_date), "within_date_sd": within}


def predicted_half_width(parts: Mapping[str, float], dates: int, per_date: int,
                         cost: float) -> float:
    between, within = parts["between_date_sd"], parts["within_date_sd"]
    return Z * math.sqrt(between ** 2 / dates + (within ** 2 + cost ** 2) / (dates * per_date))


def detectable(half_width: float) -> float:
    """The smallest true difference an interval of this half-width detects with 80% power."""
    return half_width * (Z + Z_POWER) / Z


def at_min_share(half_width: float) -> float:
    """The half-width if only `MIN_COMPLETE_SHARE` of the draw is priced - the widest the sample
    rule still reads. Exclusions thin every term, so the width grows by the root of the share."""
    return half_width / math.sqrt(study.MIN_COMPLETE_SHARE)


def grid(parts: Mapping[str, float], cost: float, available_dates: int) -> dict[str, Any]:
    """Every registered (D, k): its predicted half-width, what it costs to fetch, and the choice.

    **The choice is the cheapest cell that can be read at all**: its predicted interval is no wider
    than the floor even when only the lowest admitted share of the draw is complete, the calendar
    holds that many dates, and that share still keeps `MIN_PAIRS` pairs. Cheapest in requests,
    because the fetch is the cost; a tie keeps the cell met first. The last row is every formation
    session, `EVERY`, whose count is the calendar's own.
    """
    rows = [(f"D{dates}", dates) for dates in GRID_DATES] + [(EVERY, available_dates)]
    cells: dict[str, Any] = {}
    chosen: tuple[str, int, int] | None = None
    for label, dates in rows:
        for per_date in GRID_PER_DATE:
            half = predicted_half_width(parts, dates, per_date, cost)
            requests = dates * per_date * REQUESTS_PER_ENTRY
            readable = at_min_share(half) <= study.POWER_FLOOR / 2
            within = dates <= available_dates
            enough = dates * per_date * study.MIN_COMPLETE_SHARE >= study.MIN_PAIRS
            cells[f"{label}_k{per_date}"] = {
                "dates": dates,
                "half_width": round(half, 6),
                "half_width_at_min_share": round(at_min_share(half), 6),
                "detectable_at_80_power": round(detectable(at_min_share(half)), 6),
                "readable_at_floor": readable,
                "within_the_calendar": within,
                "enough_pairs": enough,
                "requests": requests,
                "fetch_hours": round(requests * SECONDS_PER_REQUEST / 3600, 2),
            }
            if (readable and within and enough
                    and (chosen is None or requests < chosen[1] * chosen[2] * REQUESTS_PER_ENTRY)):
                chosen = (label, dates, per_date)
    if chosen is None:
        return {"cells": cells, "chosen": {
            "dates": None, "per_date": None,
            "why": "no registered cell reaches the floor within the calendar"}}
    label, dates, per_date = chosen
    return {"cells": cells, "chosen": {
        "cell": f"{label}_k{per_date}", "every_session": label == EVERY,
        "dates": dates, "per_date": per_date, **{
            key: cells[f"{label}_k{per_date}"][key]
            for key in ("half_width", "half_width_at_min_share", "detectable_at_80_power",
                        "requests", "fetch_hours")}}}


def bootstrap_half_width(values_by_date: Mapping[date, Sequence[float]], resamples: int,
                         seed: int) -> float:
    """The pilot's own month-clustered interval, as a half-width - the formula's check."""
    by_month: dict[str, list[Decimal]] = defaultdict(list)
    for day, values in values_by_date.items():
        by_month[cluster_of(day)].extend(Decimal(str(v)) for v in values)
    got = block_bootstrap([by_month[k] for k in sorted(by_month)], "mean", BLOCK,
                                seed, resamples)
    if got is None:
        return math.nan
    _, lo, hi = got
    return (hi - lo) / 2


def proxy_differences(store: BarStore, as_of: datetime, entries: Sequence[study.Entry]
                      ) -> tuple[dict[date, list[float]], int]:
    """Per date, the close-proxy minus open-proxy per-dollar return of each pilot entry."""
    registry = atr_registry()
    free = study.cost(Decimal(0))
    by_name: dict[str, list[study.Entry]] = defaultdict(list)
    for entry in entries:
        by_name[entry.instrument_id].append(entry)
    out: dict[date, list[float]] = defaultdict(list)
    skipped = 0
    for name in sorted(by_name):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series is None or not series.bars:
            skipped += len(by_name[name])
            continue
        atr_series = atr_component.compute(series, registry)
        index_of = {bar.session_date: i for i, bar in enumerate(series.bars)}
        for entry in by_name[name]:
            atr_value = study.atr_at(atr_series, series, entry.signal_date)
            position = index_of.get(entry.session_date)
            if atr_value is None or position is None:
                skipped += 1
                continue
            bar = series.bars[position]
            opened = study.walk_entry(entry, series.bars, atr_value, bar.open, free,
                                      lambda _reason: free, None, None, Counter(), "O")
            closing = Minute(at=bar.event_time, open=bar.close, high=bar.close, low=bar.close,
                             close=bar.close)
            closed = study.walk_entry(entry, series.bars, atr_value, bar.close, free,
                                      lambda _reason: free, [closing], None, Counter(), "C")
            if isinstance(opened, str) or isinstance(closed, str):
                skipped += 1
                continue
            out[entry.signal_date].append(study.per_dollar(closed) - study.per_dollar(opened))
    return out, skipped


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = study.read_instant(args.as_of, store.latest_knowledge_time())
    benchmark = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    if benchmark is None:
        raise SystemExit(f"{BENCHMARK} is not in the store")
    calendar = [b.session_date for b in benchmark.bars]
    start, formations = study.window_formations(calendar)
    pilot_dates = study.pick_dates(formations, args.pilot_dates, PILOT_SEED)
    print(f"as_of {as_of.isoformat()}   formation sessions {len(formations)}   "
          f"pilot dates {len(pilot_dates)}", flush=True)
    selection, instruments = study.frame(store, as_of, pilot_dates, benchmark)
    entries = study.draw(selection, calendar, pilot_dates, args.pilot_per_date, PILOT_SEED)
    print(f"instruments scored {instruments}   pilot entries {len(entries)}", flush=True)
    differences, skipped = proxy_differences(store, as_of, entries)
    store.close()

    parts = components(differences)
    cost = cost_sd()
    used = sum(len(v) for v in differences.values())
    per_date = used / len(differences)
    formula = predicted_half_width(parts, len(differences), max(1, round(per_date)), 0.0)
    resampled = bootstrap_half_width(differences, args.resamples, PILOT_SEED)
    payload: dict[str, Any] = {
        "for": "PR-024",
        "purpose": ("the half-width of close-minus-open per dollar, from daily-bar proxies, before "
                    "any minute or quote is fetched - widths only"),
        "as_of": as_of.isoformat(),
        "window": {"start": start.isoformat(), "end": calendar[-1].isoformat(),
                   "months": study.WINDOW_MONTHS,
                   "formation_sessions": len(formations)},
        "pilot": {"dates": len(differences), "entries": used, "skipped": skipped,
                  "names_per_date": round(per_date, 2), "seed": PILOT_SEED,
                  "instruments_scored": instruments},
        "components": {k: round(v, 6) for k, v in parts.items()},
        "cost_sd": round(cost, 6),
        "cost_sd_source": f"{SPREADS.name}: widest opening-window p10-to-p90 range / {P10_TO_P90}",
        "formula_check": {
            "formula_half_width": round(formula, 6),
            "bootstrap_half_width": round(resampled, 6),
            "reproduces": round(resampled / formula, 3) if formula else None,
            "block": BLOCK, "resamples": args.resamples,
        },
        "power_floor_width": study.POWER_FLOOR,
        "grid": grid(parts, cost, len(formations)),
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-024 power   as_of {payload['as_of']}")
    pilot, parts = payload["pilot"], payload["components"]
    print(f"  pilot  {pilot['dates']} dates   {pilot['entries']} entries   "
          f"skipped {pilot['skipped']}")
    print(f"  sd     between dates {parts['between_date_sd']:.5f}   within a date "
          f"{parts['within_date_sd']:.5f}   entry spread {payload['cost_sd']:.5f}")
    check = payload["formula_check"]
    print(f"  check  formula {check['formula_half_width']:.5f}   bootstrap "
          f"{check['bootstrap_half_width']:.5f}   ratio {check['reproduces']}")
    for key, cell in payload["grid"]["cells"].items():
        mark = "READABLE" if cell["readable_at_floor"] else "        "
        fits = "" if cell["within_the_calendar"] else "  (beyond the calendar)"
        print(f"  {key:<10} half-width {cell['half_width'] * 100:.3f}%  at 90% "
              f"{cell['half_width_at_min_share'] * 100:.3f}%  {mark}  "
              f"{cell['requests']:>6} requests  ~{cell['fetch_hours']} h{fits}")
    print(f"  chosen {payload['grid']['chosen']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb")
    parser.add_argument("--as-of", help="the bar store's knowledge instant (default: latest)")
    parser.add_argument("--pilot-dates", type=int, default=PILOT_DATES)
    parser.add_argument("--pilot-per-date", type=int, default=PILOT_PER_DATE)
    parser.add_argument("--resamples", type=int, default=RESAMPLES)
    parser.add_argument("--report", action="store_true", help="print the stored estimate")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.data is None:
        parser.error("--data is required")
    payload = build(args)
    RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
