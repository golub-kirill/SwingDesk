"""`PR-026`..`PR-029`'s power estimate - how wide each of the four intervals can be. Widths only.

**Widths, never a level** (`power_pr019.assert_no_effect_leaked`). The pilot walks the baseline and
the wide exit on every fourth formation date of the window with every name the decile selected,
computes each study's per-date contrast exactly as `run_pr026.reading` will, and keeps only the
widths of their month-clustered intervals - so nothing it writes could tell the author which way
any of the four comes out.

**What it chooses.** Names per date, `k`, from `GRID`: each study's pilot width is scaled from the
pilot's dates to the window's (`sqrt(pilot / window)`, dates independent) and read at the lowest
complete share the sample rule admits (`/ sqrt(0.90)`). The choice is the smallest `k` at which all
four are readable at the floor, or the largest `k` when none is - a study that cannot be read at
any `k` is registered saying so, which is `PREREG_TEMPLATE` rule 9's answer, not a reason to widen
the window.

    PYTHONPATH=$PWD/src python tools/power_pr026.py --data <store> --directory <dir>
    python tools/power_pr026.py --report
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr024 as p24
import run_pr026 as study
from power_pr019 import assert_no_effect_leaked
from run_pr014 import BENCHMARK
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore

RESULT = study.RESULTS / "PR-026-power.json"
PILOT_EVERY = 4
PILOT_SEED = study.SAMPLE_SEED + 1
GRID = (10, 20, 40)
RESAMPLES = 2000
#: Draws of `k` names per date are repeated and their widths averaged, so a choice is not one
#: subsample's luck.
REPEATS = 3


def subsample(walked: Sequence[study.Walked], per_date: int, seed: int) -> list[study.Walked]:
    """`per_date` of each date's entries, seeded per date like `run_pr024.draw`."""
    by_date: dict[Any, list[study.Walked]] = defaultdict(list)
    for w in walked:
        by_date[w.entry.signal_date].append(w)
    out: list[study.Walked] = []
    for day in sorted(by_date):
        rows = sorted(by_date[day], key=lambda w: w.entry.instrument_id)
        if len(rows) > per_date:
            rows = random.Random(seed + day.toordinal()).sample(rows, per_date)
        out.extend(rows)
    return out


def widths(walked: Sequence[study.Walked], resamples: int) -> dict[str, float]:
    """Each study's end-to-end interval width on these entries, and nothing else."""
    out: dict[str, float] = {}
    for name in study.STUDIES:
        cell = study.reading(walked, name, len(walked), resamples)
        out[name] = cell["difference"]["width"]
    return out


def scaled(width: float, pilot_dates: int, window_dates: int) -> float:
    """A pilot width at the window's dates and the lowest admitted complete share."""
    return width * math.sqrt(pilot_dates / window_dates) / math.sqrt(study.MIN_COMPLETE_SHARE)


def choose(table: Mapping[int, Mapping[str, float]]) -> dict[str, Any]:
    """The smallest `k` at which every study is readable at the floor, else the largest."""
    for per_date in sorted(table):
        if all(w <= study.POWER_FLOOR for w in table[per_date].values()):
            return {"per_date": per_date, "all_readable": True}
    return {"per_date": max(table), "all_readable": False,
            "unreadable": sorted(name for name, w in table[max(table)].items()
                                 if not w <= study.POWER_FLOOR)}


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = p24.read_instant(args.as_of, store.latest_knowledge_time())
    benchmark = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    if benchmark is None:
        raise SystemExit(f"{BENCHMARK} is not in the store")
    calendar = [b.session_date for b in benchmark.bars]
    formations = study.window_formations(calendar)
    pilot_dates = formations[::PILOT_EVERY]
    print(f"as_of {as_of.isoformat()}   window sessions {len(formations)}   "
          f"pilot dates {len(pilot_dates)}", flush=True)
    selection, instruments = p24.frame(store, as_of, pilot_dates, benchmark)
    store.close()
    entries = p24.draw(selection, calendar, pilot_dates, 10_000, PILOT_SEED)
    print(f"instruments scored {instruments}   pilot entries {len(entries)}", flush=True)
    walked, instants = study.walk_sample(args, entries)

    table: dict[int, dict[str, float]] = {}
    for per_date in GRID:
        runs = [widths(subsample(walked, per_date, PILOT_SEED + r), args.resamples)
                for r in range(REPEATS)]
        table[per_date] = {name: scaled(sum(run[name] for run in runs) / REPEATS,
                                        len(pilot_dates), len(formations))
                           for name in study.STUDIES}
        print(f"  k={per_date}: " + "  ".join(f"{n} {w * 100:.3f}" for n, w in
                                             table[per_date].items()), flush=True)
    chosen = choose(table)
    payload: dict[str, Any] = {
        "for": list(study.STUDIES),
        "purpose": ("the end-to-end width of each study's interval at each names-per-date, "
                    "scaled to the window's dates and the lowest admitted complete share - "
                    "widths only"),
        "as_of": instants,
        "window": {"start": study.WINDOW_START.isoformat(), "end": study.WINDOW_END.isoformat(),
                   "formation_sessions": len(formations)},
        "pilot": {"dates": len(pilot_dates), "every": PILOT_EVERY, "entries": len(walked),
                  "seed": PILOT_SEED, "repeats": REPEATS, "resamples": args.resamples,
                  "instruments_scored": instruments},
        "power_floor_width": study.POWER_FLOOR,
        "widths_at_min_share": {str(k): {n: round(w, 6) for n, w in row.items()}
                                for k, row in table.items()},
        "chosen": chosen,
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-026..029 power   as_of {payload['as_of']}")
    pilot = payload["pilot"]
    print(f"  pilot {pilot['dates']} dates, {pilot['entries']} entries")
    for k, row in payload["widths_at_min_share"].items():
        cells = "  ".join(f"{name} {w * 100:.3f}" for name, w in row.items())
        print(f"  k={k:<3} widths (points)  {cells}")
    print(f"  floor {payload['power_floor_width'] * 100:.2f}   chosen {payload['chosen']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb")
    parser.add_argument("--directory", type=Path, help="the symbol directory store")
    parser.add_argument("--directory-as-of", help="the directory pull to read (default: latest)")
    parser.add_argument("--as-of", help="the bar store's knowledge instant (default: latest)")
    parser.add_argument("--resamples", type=int, default=RESAMPLES)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true", help="print the stored estimate")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(args.out.read_text(encoding="utf-8")))
        return 0
    if args.data is None or args.directory is None:
        parser.error("--data and --directory are required")
    payload = build(args)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
