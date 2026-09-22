"""On every ambiguous bar PR-016 recorded, which leg printed first - read the way a backtest now reads it.

`DR-042` §9, ruled by the owner 2026-09-14: build the minute-bar resolution now, *"because it can
make it worth in a future and nobody really can proof, that the code has no mistakes now"*. This is
the proof asked for. It runs the resolver a backtest now calls (`intraday.MinuteTieBreak`) on every
ambiguous bar the harness has recorded, against stored minutes, next to what the 2026-09-08 probe
measured on the same bars.

**Four readings of each bar, so every difference from the probe has exactly one cause:**

1. `probe` - the whole UTC day, RAW prices. What `probe_ambiguous_bar.py` did; it should reproduce
   the probe's recorded counts, and a mismatch would mean the vendor's history moved.
2. `split` - the whole UTC day, split-adjusted. Differs from 1 in the prices only.
3. `window` - regular hours, split-adjusted. Differs from 2 in the session window only.
4. `resolver` - 3, refused where the minutes do not reproduce the daily bar. Differs from 3 in that
   check only. This is the answer a backtest with minutes now uses.

**And the units check behind 4, reported as ratios.** The regular-hours minutes' own high and low
against the stored daily bar's: a split between the session and the fetch shows as a factor near 2
or 1/2, a print one tape has and the other lacks as one extreme off and the other exact.

**What it moves.** Each bar the resolver answers `target` is a trade the harness closed at the
stop and the minutes close at the target: `(target - stop) / (entry - stop)` R, gross. Summed per
arm over PR-016's trade count, that is the change to the arm's mean R per trade.

    PYTHONPATH=$PWD/src python tools/measure_first_touch.py --store <split minutes>
        --raw-store <raw minutes> --daily <bars.duckdb>

Reads stores only; no network. `tools/fetch_minutes.py` fills the minute stores. Without `--daily`
the resolver has no bar to check against and every row reads `unavailable`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

# A TOOL MUST IMPORT THE CHECKOUT IT LIVES IN. `swingdesk` is installed editable and the .pth
# carries the MAIN checkout's `src` as an absolute path, so without this line a tool run from a
# git worktree measures another tree's code. Found 2026-09-21, by the same defect in the suite.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.reference import ExchangeSession
from swingdesk.market_data.minutes import Minute, MinuteStore
from swingdesk.validation.backtest.intraday import (
    RANGE_TOLERANCE,
    MinuteTieBreak,
    Touch,
    first_touch,
    regular_hours,
    reproduces,
    session_for,
)

REPO = Path(__file__).resolve().parents[1]
AMBIGUOUS_BARS = REPO / "docs" / "prereg" / "results" / "PR-016-ambiguous-bars.jsonl"
STUDY = REPO / "docs" / "prereg" / "results" / "PR-016.json"
PROBE = REPO / "docs" / "decisions" / "measurements" / "ambiguous-bar.json"
RESULT = REPO / "docs" / "decisions" / "measurements" / "first-touch-2026-09-14.json"

OUTCOMES = [touch.value for touch in Touch]
READINGS = ("probe", "split", "window", "resolver")

Sessions = Callable[[str, date], ExchangeSession | None]


@dataclass(frozen=True)
class Day:
    """The daily bar as the resolver needs it: `intraday.DailyRange`."""

    session_date: date
    high: Decimal
    low: Decimal


def read(minutes: Sequence[Minute] | None, stop: Decimal, target: Decimal) -> str:
    """First touch over the minutes given, or `unavailable` for none."""
    if not minutes:
        return Touch.UNAVAILABLE.value
    return first_touch(minutes, stop, target).value


def in_session(minutes: Sequence[Minute] | None,
               session: ExchangeSession | None) -> list[Minute]:
    return regular_hours(minutes, session) if minutes and session is not None else []


def units(minutes: Sequence[Minute], day: Day | None) -> dict[str, Any]:
    """The minutes' high and low as ratios of the daily bar's, and whether they reproduce it."""
    if not minutes or day is None:
        return {"high_ratio": None, "low_ratio": None, "agrees": None}
    return {"high_ratio": float(max(m.high for m in minutes) / day.high),
            "low_ratio": float(min(m.low for m in minutes) / day.low),
            "agrees": reproduces(minutes, day)}


def daily_bars(path: Path, pairs: Sequence[tuple[str, date]],
               as_of: datetime) -> dict[tuple[str, date], tuple[Decimal, Decimal]]:
    """(high, low) of each session's daily bar as the study saw it. Read-only: another process
    may hold the store."""
    connection = duckdb.connect(str(path), read_only=True)
    try:
        found: dict[tuple[str, date], tuple[Decimal, Decimal]] = {}
        for instrument_id, on in pairs:
            row = connection.execute(
                "SELECT high, low FROM bars WHERE instrument_id = ? AND interval = '1d' "
                "AND series = 'raw' AND session_date = ? AND knowledge_time <= ? "
                "ORDER BY knowledge_time DESC LIMIT 1", [instrument_id, on, as_of]).fetchone()
            if row is not None:
                found[(instrument_id, on)] = (row[0], row[1])
        return found
    finally:
        connection.close()


def measure(rows: Sequence[dict[str, str]], split_store: MinuteStore,
            raw_store: MinuteStore | None,
            daily: dict[tuple[str, date], tuple[Decimal, Decimal]], as_of: datetime,
            sessions: Sessions = session_for) -> dict[str, Any]:
    """Every row read four ways, plus the units check. Pure over the stores it is given."""
    resolver = MinuteTieBreak(split_store, as_of, sessions)
    readings: dict[str, Counter[str]] = {name: Counter() for name in READINGS}
    by_arm: dict[str, Counter[str]] = {}
    per_row: list[dict[str, Any]] = []
    for row in rows:
        instrument_id, on = row["instrument_id"], date.fromisoformat(row["session_date"])
        stop, target = Decimal(row["stop"]), Decimal(row["target"])
        entry = Decimal(row["entry_price"])
        bar = daily.get((instrument_id, on))
        day = Day(on, bar[0], bar[1]) if bar is not None else None
        session = sessions(instrument_id, on)
        split_minutes = split_store.session(instrument_id, on, as_of)
        raw_minutes = raw_store.session(instrument_id, on, as_of) if raw_store else None
        regular = in_session(split_minutes, session)

        answers = {
            "probe": read(raw_minutes, stop, target) if raw_store is not None else None,
            "split": read(split_minutes, stop, target),
            "window": read(regular, stop, target),
            "resolver": (resolver(instrument_id, day, stop, target).value if day is not None
                         else Touch.UNAVAILABLE.value),
        }
        for name, answer in answers.items():
            if answer is not None:
                readings[name][answer] += 1
        by_arm.setdefault(row["arm"], Counter())[answers["resolver"]] += 1
        per_row.append({
            "instrument_id": instrument_id, "session_date": on.isoformat(), "arm": row["arm"],
            "stop": row["stop"], "target": row["target"], "entry_price": row["entry_price"],
            **answers,
            "flip_r": float((target - stop) / (entry - stop)),
            "regular_minutes": len(regular),
            "daily_high": str(bar[0]) if bar else None, "daily_low": str(bar[1]) if bar else None,
            "units_split": units(regular, day),
            "units_raw": (units(in_session(raw_minutes, session), day)
                          if raw_store is not None else None),
        })

    def changed(before: str, after: str) -> list[str]:
        return [f"{r['instrument_id']} {r['session_date']} {r['arm']}: {r[before]} -> {r[after]}"
                for r in per_row if r[before] is not None and r[before] != r[after]]

    def disagreeing(key: str) -> list[str]:
        return [f"{r['instrument_id']} {r['session_date']}: high x{r[key]['high_ratio']:.4f} "
                f"low x{r[key]['low_ratio']:.4f}"
                for r in per_row if r[key] is not None and r[key]["agrees"] is False]

    return {
        "rows": len(per_row),
        "sessions": len({(r["instrument_id"], r["session_date"]) for r in per_row}),
        "readings": {name: {o: counts[o] for o in OUTCOMES} for name, counts in readings.items()},
        "resolver_by_arm": {arm: {o: counts[o] for o in OUTCOMES}
                            for arm, counts in sorted(by_arm.items())},
        "changed_by_the_adjustment": changed("probe", "split"),
        "changed_by_the_window": changed("split", "window"),
        "changed_by_the_check": changed("window", "resolver"),
        "units": {
            "tolerance": str(RANGE_TOLERANCE),
            "split_agrees": sum(1 for r in per_row if r["units_split"]["agrees"] is True),
            "split_disagrees": disagreeing("units_split"),
            "split_unchecked": sum(1 for r in per_row if r["units_split"]["agrees"] is None),
            "raw_agrees": sum(1 for r in per_row
                              if r["units_raw"] is not None and r["units_raw"]["agrees"] is True),
            "raw_disagrees": disagreeing("units_raw"),
        },
        "per_row": per_row,
    }


def impact(per_row: Sequence[dict[str, Any]], study: dict[str, Any]) -> dict[str, Any]:
    """Each arm's change in mean gross R per trade, and the harness's own ambiguous count beside
    this file's - they must be the same bars."""
    trades = {name: cells.get("full", {}).get("trades", 0)
              for group in ("arms", "diagnostics") for name, cells in study.get(group, {}).items()}
    recorded = study.get("ambiguous_exits", {})
    arms: dict[str, Any] = {}
    for arm in sorted({r["arm"] for r in per_row}):
        rows = [r for r in per_row if r["arm"] == arm]
        moved = sum(r["flip_r"] for r in rows if r["resolver"] == Touch.TARGET.value)
        count = trades.get(arm, 0)
        arms[arm] = {
            "ambiguous_rows": len(rows), "harness_counted": recorded.get(arm),
            "resolved_to_target": sum(1 for r in rows if r["resolver"] == Touch.TARGET.value),
            "gross_r_moved": moved, "trades": count,
            "mean_r_per_trade_moves_by": moved / count if count else None,
        }
    return arms


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, required=True, help="split-adjusted minutes")
    parser.add_argument("--raw-store", type=Path, help="raw minutes, for the probe's reading")
    parser.add_argument("--daily", type=Path, help="the bar store the study read (bars.duckdb)")
    parser.add_argument("--bars", type=Path, default=AMBIGUOUS_BARS)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--as-of", help="the minutes' knowledge instant; default now")
    parser.add_argument("--out", type=Path, default=RESULT)
    args = parser.parse_args(argv)

    as_of = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(UTC)
    rows = [json.loads(line) for line in args.bars.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    study = json.loads(args.study.read_text(encoding="utf-8"))
    study_as_of = datetime.fromisoformat(study["as_of"])
    pairs = sorted({(r["instrument_id"], date.fromisoformat(r["session_date"])) for r in rows})
    daily = daily_bars(args.daily, pairs, study_as_of) if args.daily else {}

    with MinuteStore(args.store) as split_store:
        raw_store = MinuteStore(args.raw_store) if args.raw_store else None
        try:
            report = measure(rows, split_store, raw_store, daily, as_of)
        finally:
            if raw_store is not None:
                raw_store.close()
    report["impact"] = impact(report["per_row"], study)
    probe = json.loads(PROBE.read_text(encoding="utf-8")) if PROBE.exists() else {}
    recorded = probe.get("outcomes", {})
    report.update({
        "measured_on": as_of.date().isoformat(),
        "question": "DR-042 §9 - on a session reaching both the stop and the target, which "
                    "printed first, read by the resolver a backtest now uses",
        "ruled_by": "the owner, 2026-09-14: build the minute resolution now",
        "minutes_as_of": as_of.isoformat(),
        "daily_bars_as_of": study_as_of.isoformat() if args.daily else None,
        "sources": {"minutes": "https://data.alpaca.markets v2 bars, 1Min, feed=sip, "
                               "whole UTC day stored (tools/fetch_minutes.py)",
                    "split": "adjustment=split", "raw": "adjustment=raw",
                    "daily": "bars.duckdb, series raw, interval 1d, as the study read it"},
        "probe_recorded_2026_09_08": recorded,
        "probe_reproduced": ({o: report["readings"]["probe"][o] for o in recorded} == recorded
                             if recorded and args.raw_store else None),
        "exploratory": True,
        "not_measured": [
            "which leg a real OCO would have filled: the venue's matching is not observable, and "
            "a minute bar is still a bar - the `within_a_minute` count is that floor",
            "the exit's own slippage: `gross_r_moved` is target minus stop in R, before costs",
            "which tape is right on a `mismatch`: only that the two disagree",
        ],
    })

    readings = report["readings"]
    print(f"ambiguous bars {report['rows']} ({report['sessions']} sessions)   minutes as of "
          f"{as_of.isoformat()}")
    print(f"\n  {'':28}" + "".join(f"{o:>16}" for o in OUTCOMES))
    if recorded:
        print(f"  {'probe, recorded 2026-09-08':28}"
              + "".join(f"{recorded.get(o, 0):>16}" for o in OUTCOMES))
    labels = {"probe": "1 probe's reading, now", "split": "2 split-adjusted, whole day",
              "window": "3 regular hours", "resolver": "4 resolver: 3 + the check"}
    for name, label in labels.items():
        if name == "probe" and not args.raw_store:
            continue
        print(f"  {label:28}" + "".join(f"{readings[name][o]:>16}" for o in OUTCOMES))
    for key, label in (("changed_by_the_adjustment", "1 -> 2, the adjustment"),
                       ("changed_by_the_window", "2 -> 3, the window"),
                       ("changed_by_the_check", "3 -> 4, the check")):
        print(f"\n  changed by {label}: {len(report[key])}")
        for line in report[key]:
            print(f"    {line}")
    check = report["units"]
    print(f"\n  units: regular-hours minutes against the stored daily bar, within "
          f"{float(RANGE_TOLERANCE):.1%}")
    print(f"    split-adjusted  {check['split_agrees']} agree, {len(check['split_disagrees'])} "
          f"do not, {check['split_unchecked']} unchecked")
    for line in check["split_disagrees"]:
        print(f"      {line}")
    if args.raw_store:
        print(f"    raw             {check['raw_agrees']} agree, {len(check['raw_disagrees'])} "
              f"do not")
        for line in check["raw_disagrees"]:
            print(f"      {line}")
    print("\n  what it moves in PR-016, gross R per trade")
    for arm, cell in report["impact"].items():
        moves = cell["mean_r_per_trade_moves_by"]
        if moves is None:
            print(f"    {arm}: no trade count in the study")
            continue
        print(f"    {arm:12} {cell['resolved_to_target']:>4} of {cell['ambiguous_rows']:>4} to "
              f"target (harness counted {cell['harness_counted']})   "
              f"{cell['gross_r_moved']:+.2f} R over {cell['trades']} trades = "
              f"{moves:+.6f} R a trade")

    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
