"""EXPLORATORY: `PR-034`'s own arms, re-read by calendar year and by trailing window.

**Why this exists.** `PR-034` reported one number over 2016-2026 and one over the last 590
sessions. Asked whether the rule holds over "the last four or five years", nothing in the result
file answers it: the window is a slice, not a configuration, and slicing after the verdict is read
is exactly what `PREREG_TEMPLATE` rule 3 calls exploratory.

**So this spends no trial and carries no verdict.** It adds no fund, no arm, no cost and no rule -
it imports `run_pr034`'s pricing unchanged and groups the same daily returns by calendar year and
by trailing window. What it can show is CONSISTENCY, which a single ten-year mean hides: a rule
that earned everything in one year and nothing in nine is a different proposition from one that
earned a little every year, and the difference decides whether a paper trial is worth running.

**Read it as description.** No interval here gates anything, and a sub-window that reads worse than
the whole is not a refutation - it is a smaller sample.

    PYTHONPATH=$PWD/src python tools/attribute_pr034.py --minutes <store> --minutes-as-of <t> \
        --data <history store dir> --as-of <t>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr031 as p31
import run_pr033 as p33
import run_pr034 as p34
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import MinuteStore

RESULT = p31.RESULTS / "PR-034-attribution.json"

#: Trailing windows, in years, read back from the last session.
TRAILING = (1, 2, 3, 4, 5, 7, 10)


def arms(args: argparse.Namespace) -> dict[str, dict[date, float]]:
    """`PR-034`'s three series for the verdict basket: the night, the session, and holding."""
    minutes = MinuteStore(args.minutes)
    bars = BarStore(args.data / "bars.duckdb")
    minutes_as_of = p31.read_instant(args.minutes_as_of, datetime.max.replace(tzinfo=UTC))
    latest = bars.latest_knowledge_time() or datetime.max.replace(tzinfo=UTC)
    bars_as_of = p31.read_instant(args.as_of, latest)
    by_arm: dict[str, dict[str, dict[date, float]]] = {p34.NIGHT: {}, p34.SESSION: {}, "hold": {}}
    for fund in p34.SMALL:
        dividends = p33.dividends_of(bars, fund, bars_as_of)
        sessions, _ = p34.load_sessions(minutes, fund, minutes_as_of, dividends)
        night, inside, held = p33.returns_of(sessions, args.per_share)
        by_arm[p34.NIGHT][fund], by_arm[p34.SESSION][fund], by_arm["hold"][fund] = (
            night, inside, held)
    minutes.close()
    bars.close()
    return {arm: p33.basket_of(by_arm[arm]) for arm in (p34.NIGHT, p34.SESSION, "hold")}


def described(values: Sequence[float]) -> dict[str, float]:
    """Annualised mean, volatility, Sharpe ratio, compounded return and worst drawdown."""
    if len(values) < 2:
        return {}
    mean, spread = statistics.fmean(values), statistics.stdev(values)
    equity, peak, worst = 1.0, 1.0, 0.0
    for r in values:
        equity *= 1 + r
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return {"days": len(values), "annual_mean": mean * 252,
            "annual_volatility": spread * (252 ** 0.5),
            "sharpe": mean / spread * (252 ** 0.5) if spread else float("nan"),
            "total_return": equity - 1, "max_drawdown": worst}


def by_year(series: Mapping[date, float]) -> dict[str, dict[str, float]]:
    years: dict[int, list[float]] = {}
    for session, value in sorted(series.items()):
        years.setdefault(session.year, []).append(value)
    return {str(year): described(values) for year, values in sorted(years.items())}


def trailing(series: Mapping[date, float], years: int) -> dict[str, float]:
    if not series:
        return {}
    last = max(series)
    first = date(last.year - years, last.month, min(last.day, 28))
    return described([value for session, value in sorted(series.items()) if session > first])


def build(args: argparse.Namespace) -> dict[str, Any]:
    series = arms(args)
    return {
        "exploratory": True,
        "of": "PR-034",
        "trials": 0,
        "note": ("a re-reading of PR-034's own arms by calendar year and trailing window; no fund, "
                 "arm, cost or rule is added and nothing here carries a verdict"),
        "funds": list(p34.SMALL),
        "per_share_cost": args.per_share,
        "whole": {arm: described(list(values.values())) for arm, values in series.items()},
        "by_year": {arm: by_year(values) for arm, values in series.items()},
        "trailing": {arm: {f"{years}y": trailing(values, years) for years in TRAILING}
                     for arm, values in series.items()},
    }


def report(payload: Mapping[str, Any]) -> None:
    def line(label: str, cell: Mapping[str, float]) -> str:
        if not cell:
            return f"  {label:<10} -"
        return (f"  {label:<10} {cell['annual_mean']:+7.2%} a year  vol {cell['annual_volatility']:6.2%}"
                f"  sharpe {cell['sharpe']:+5.2f}  total {cell['total_return']:+8.2%}"
                f"  worst {cell['max_drawdown']:+7.2%}  days {cell['days']:>4}")

    print(f"PR-034 attribution (EXPLORATORY, 0 trials) - {', '.join(payload['funds'])} "
          f"at ${payload['per_share_cost']} a share a side")
    for arm, label in ((p34.NIGHT, "THE NIGHT"), (p34.SESSION, "the session"), ("hold", "holding")):
        print(f"\n{label}")
        print(line("whole", payload["whole"][arm]))
        print("  --- by calendar year ---")
        for year, cell in payload["by_year"][arm].items():
            print(line(year, cell))
        print("  --- trailing ---")
        for window, cell in payload["trailing"][arm].items():
            print(line(window, cell))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=Path, required=True)
    parser.add_argument("--minutes-as-of")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--per-share", type=float, default=p31.COSTS["net"])
    parser.add_argument("--out", type=Path, default=RESULT)
    args = parser.parse_args(argv)
    payload = build(args)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
