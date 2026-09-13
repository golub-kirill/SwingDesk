"""Is the answer still true? A scheduled re-observation of a registered question, on a rolling window.

`AGENTS.md` §19.7: a verdict is one draw, and *still true* is a property of a SEQUENCE of them. No
measurement of any length produces one - a ten-year backtest re-read in a year is the same ten-year
backtest. This tool re-runs a registered study's own construction and decision rule on the 48 months
ending at its `as_of`, and appends ONE record to a series that is never rewritten.

**It spends no trial** (owner ruling 2026-09-08): the rule, the parameters and the decision rule are
the registration's; only the window moves. **The guard that ruling needs**: consecutive windows
overlap heavily, so re-running until an answer flips is a search in time. So a re-measurement is
SCHEDULED (`tools/remeasure.cmd`), every result is appended whatever it says, and an `as_of` earlier
than the series' last point is refused - the series cannot be re-drawn into the past.

A point in this series is a RE-OBSERVATION, not a result: it never changes a verdict, and a report
citing one says so. It lives in `data/`, beside the other passes' runtime state.

    PYTHONPATH=$PWD/src python tools/remeasure.py PR-019b --data <store>
    python tools/remeasure.py PR-019b --report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

#: `AGENTS.md` §19's current market. The window is the one thing a re-observation moves.
WINDOW_MONTHS = 48


def _pr019b(data: Path, as_of: str | None) -> dict[str, Any]:
    """`PR-019b` on the rolling window: the candidate against `SPY` over the same days.

    Through the streamed loader - one series in memory at a time - because a scheduled pass that
    needed 22 GB would take the machine with it.
    """
    import run_pr019b

    result = run_pr019b.build(argparse.Namespace(
        data=data, as_of=as_of, reference=REPO / "absent", streamed=True,
        rolling_months=WINDOW_MONTHS))
    cell = result["cells"]["rolling"][run_pr019b.CELL]
    return {
        "as_of": result["as_of"],
        "window": result["window"],
        "trades": cell.get("trades", 0),
        "months": cell.get("months", 0),
        "candidate": cell.get("mean_interval"),
        "candidate_level": cell.get("mean_net_r"),
        "index_leg": cell.get("market_mean"),
        "candidate_minus_index": cell.get("difference"),
        "branch": result["verdict"],
    }


def _pr016(data: Path, as_of: str | None) -> dict[str, Any]:
    """`PR-016` on the rolling window: the ratified screen against every liquid name, same months.

    The finding the programme leans on besides `PR-019b`'s: the screen loses less than no screen.
    Streamed for the same reason, and it writes nothing beside `PR-016`'s committed evidence.
    """
    import run_pr016

    result = run_pr016.build(argparse.Namespace(
        data=data, as_of=as_of, start=None, end=None, streamed=True,
        rolling_months=WINDOW_MONTHS))
    ranked = result["arms"]["ranked"]["rolling"]
    return {
        "as_of": result["as_of"],
        "window": result["window"],
        "trades": ranked.get("trades", 0),
        "months": ranked.get("months", 0),
        "ranked_level": ranked.get("mean_net_r"),
        "unselected_level": result["arms"]["unselected"]["rolling"].get("mean_net_r"),
        "ranked_minus_unselected": ranked.get("difference_mean"),
        "branch": result["verdict"],
    }


#: The registered questions this tool re-observes, each with the function that re-runs it.
STUDIES: dict[str, Callable[[Path, str | None], dict[str, Any]]] = {
    "PR-019b": _pr019b, "PR-016": _pr016}

#: The one quantity each study's decision rule reads, as the report prints it: label, record key.
READS: dict[str, tuple[str, str]] = {
    "PR-019b": ("candidate - index", "candidate_minus_index"),
    "PR-016": ("ranked - unselected", "ranked_minus_unselected"),
}


def series_path(data: Path, study: str) -> Path:
    return data / "remeasure" / f"{study}.jsonl"


def read_series(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def refuse_backdating(series: list[dict[str, Any]], as_of: str) -> None:
    """The guard. A point before the last one would be re-drawing the past."""
    if series and datetime.fromisoformat(as_of) < datetime.fromisoformat(series[-1]["as_of"]):
        raise SystemExit(f"refused: as_of {as_of} precedes the series' last point "
                         f"{series[-1]['as_of']} - a re-observation cannot be re-done into the past")


def append(path: Path, record: dict[str, Any]) -> None:
    """Append-only: the file is opened for append and never rewritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record, sort_keys=True) + "\n")


def _span(block: dict[str, Any] | None) -> str:
    if not block:
        return "-"
    return f"{block['observed']:+.4f} [{block['low']:+.4f}, {block['high']:+.4f}]"


def report(series: list[dict[str, Any]]) -> None:
    """Every point, oldest first, and how the read quantity has moved - what §19.7 asks for."""
    if not series:
        print("no re-observations yet - the scheduled pass has not run")
        return
    print(f"{series[0]['study']}: {len(series)} re-observation(s), a {WINDOW_MONTHS}-month window "
          f"each - RE-OBSERVATIONS, not results\n")
    label, key = READS[series[0]["study"]]
    print(f"  {'recorded':20} {'as_of':12} {'trades':>7} {label:>30}  branch")
    for point in series:
        print(f"  {point['recorded_at'][:19]:20} {point['as_of'][:10]:12} {point['trades']:>7} "
              f"{_span(point.get(key)):>30}  {point['branch']}")
    first, last = series[0].get(key), series[-1].get(key)
    if first and last and len(series) > 1:
        print(f"\n  moved {last['observed'] - first['observed']:+.4f}R since the first point")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("study", choices=sorted(STUDIES))
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--as-of", default=None, help="knowledge instant; defaults to the latest")
    parser.add_argument("--report", action="store_true", help="print the series and exit")
    args = parser.parse_args()

    path = series_path(args.data, args.study)
    series = read_series(path)
    if args.report:
        report(series)
        return 0
    if args.as_of:
        refuse_backdating(series, args.as_of)
    record = {"study": args.study, "recorded_at": datetime.now(UTC).isoformat(),
              **STUDIES[args.study](args.data, args.as_of)}
    refuse_backdating(series, record["as_of"])
    append(path, record)
    report([*series, record])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
