"""`BACKTEST_PROTOCOL` §7's QA stage for `PR-016`: rebuild sampled trades from the evidence alone.

The course asks for `Повторная независимая проверка части выборки`, and §7 spells out what that
means here:

> 2. Each sampled trade is reconstructed **from the stored evidence alone**: the as-of snapshot, the
>    recorded parameters and the rule version. Not from the run's own output.
> 3. Disagreement is a defect in the run, not a rounding difference to be waved through.

**So this file imports NOTHING from the harness it checks.** Not `ExitPolicy`, not `run_arm`, not
`derived_observations.atr:compute`, not `CostModel`. Wilder's true range, Wilder's smoothing,
the two fill rules and the four ordering rules are written out again here from the specifications
they come from. A re-check
that calls the code under test proves the code is deterministic, which
`DETERMINISM_SPEC.md` §7 already proves and which is a different question.

It reads the bar store, which is evidence, and the sample `run_pr016.py` drew by a seeded rule —
400 per series, seed 20260908 — because §7 asks for a sample drawn by a rule and not by whoever is
checking.

**What a disagreement means.** Every field below is recomputable from `(instrument, entry date)`
plus the ratified parameters. If a reconstruction differs, either the run is wrong or this file is,
and both are worth knowing. Exact Decimal comparison on prices, because these are the same
arithmetic on the same stored numbers rather than two estimates of one quantity.

    PYTHONPATH=$PWD/src python tools/verify_pr016_qa.py --data data
    PYTHONPATH=$PWD/src python tools/verify_pr016_qa.py --data data --limit 50
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore

SAMPLE = REPO / "docs" / "prereg" / "results" / "PR-016-trades-sample.csv"
RESULT = REPO / "docs" / "prereg" / "results" / "PR-016.json"

#: The ratified exit and the ratified costs, restated rather than imported. These are the numbers
#: `PR-016.json` records for the run being checked, and the check asserts they match rather than
#: reading them from the runner - a QA pass that inherits the study's constants inherits its
#: mistakes.
ATR_PERIOD = 14
STOP_MULTIPLE = Decimal("2.0")
TARGET_R = Decimal("1.0")
HOLD = 20
SLIPPAGE_BPS = Decimal("25")
COMMISSION_PER_SHARE = Decimal("0.005")
RISK_PER_TRADE = Decimal(1000)
STRESS = 3

#: Arms whose costs are tripled. Their fills and therefore their stops differ, so the reconstruction
#: has to know which cost level a row was produced at - and getting that wrong would report a wall
#: of false disagreements, which is its own kind of useless.
STRESSED = ("unselected_3x", "ranked_3x")

#: The arm that runs the two-slot exit. `PR-005`'s policy: no profit slot.
NO_TARGET = "unselected_two_slot"


def wilder_atr(bars: list[Any], period: int) -> list[Decimal | None]:
    """ATR by Wilder, written out from `ALGORITHM_SPEC` rather than imported.

    True range is the largest of the bar's own range and its two gaps against the previous close;
    the average seeds with a simple mean of the first `period` ranges and then smooths at
    `(prev * (period - 1) + latest) / period`. No value before warm-up: a partially warmed average
    looks exactly like a valid one downstream.
    """
    out: list[Decimal | None] = [None]
    ranges: list[Decimal] = []
    average: Decimal | None = None
    for index in range(1, len(bars)):
        bar, previous = bars[index], bars[index - 1]
        ranges.append(max(bar.high - bar.low,
                          abs(bar.high - previous.close),
                          abs(bar.low - previous.close)))
        if len(ranges) < period:
            out.append(None)
            continue
        average = (sum(ranges[:period], Decimal(0)) / period if average is None
                   else (average * (period - 1) + ranges[-1]) / period)
        out.append(average)
    return out


def walk(bars: list[Any], entry_index: int, stop: Decimal, target: Decimal | None,
         hold: int) -> tuple[int, Decimal, str] | None:
    """The four ordering rules of `DR-042`, written out. Returns `(index, quoted price, reason)`.

    1. a session opening below the stop fills at the OPEN;
    2. a session opening above the target fills at the TARGET, not the better open;
    3. intraday the stop is checked BEFORE the target;
    4. the stop is checked before the clock.

    The loop starts at the entry bar itself, which is what the engine does: a position opened at
    `bars[i + 1].open` is managed from `bars[i + 1]` onward and can be stopped out the same session.
    """
    for index in range(entry_index, len(bars)):
        bar = bars[index]
        held = index - entry_index
        if bar.open <= stop:
            return index, bar.open, "stop_gap"
        if target is not None and bar.open >= target:
            return index, target, "target"
        if bar.low <= stop:
            return index, stop, "stop"
        if target is not None and bar.high >= target:
            return index, target, "target"
        if held >= hold:
            return index, bar.close, "time"
    return None


def reconstruct(bars: list[Any], atr: list[Decimal | None], row: dict[str, str],
                index_of: dict[date, int]) -> dict[str, Any] | str:
    """Rebuild one trade from `(instrument, entry date)` and the ratified parameters."""
    entry_date = date.fromisoformat(row["entry_date"])
    entry_index = index_of.get(entry_date)
    if entry_index is None or entry_index == 0:
        return "the entry date is not in the store at this as-of"
    signal_index = entry_index - 1
    atr_value = atr[signal_index] if signal_index < len(atr) else None
    if atr_value is None or atr_value <= 0:
        return "no ATR at the signal bar"

    stress = STRESS if row["arm"] in STRESSED else 1
    slip = SLIPPAGE_BPS * stress / Decimal(10_000)
    commission = COMMISSION_PER_SHARE * stress

    entry_fill = bars[entry_index].open * (Decimal(1) + slip)
    stop = entry_fill - STOP_MULTIPLE * atr_value
    if stop >= entry_fill or stop <= 0:
        return "the stop is not a price below the entry - the run should have skipped this"
    risk = entry_fill - stop
    shares = int(RISK_PER_TRADE / risk)
    if shares < 1:
        return "the risk budget buys no shares - the run should have skipped this"
    target = None if row["arm"] == NO_TARGET else entry_fill + TARGET_R * risk

    exit_at = walk(bars, entry_index, stop, target, HOLD)
    if exit_at is None:
        last = bars[-1]
        exit_index, quoted, reason = len(bars) - 1, last.close, "end_of_data"
    else:
        exit_index, quoted, reason = exit_at
    return {
        "entry_price": entry_fill,
        "stop_price": stop,
        "exit_price": quoted * (Decimal(1) - slip),
        "exit_date": bars[exit_index].session_date,
        "exit_reason": reason,
        "shares": shares,
        "initial_risk_per_share": risk,
        "costs": commission * shares * 2,
    }


CHECKED = ("entry_price", "stop_price", "exit_price", "exit_date", "exit_reason", "shares",
           "initial_risk_per_share", "costs")


def is_final_bar_label(differences: list[str], rebuilt: dict[str, Any], bars: list[Any]) -> bool:
    """True when the ONLY difference is `end_of_data` against `time` on the last stored bar.

    **Found by this file on its first run, 2026-09-08: 10 of 2,400 sampled trades, every one of
    them an entry dated 2026-08-07.** `run_arm` iterates `range(len(bars) - 1)` because forming an
    entry needs `bars[i + 1]`, so the final bar is never evaluated for an EXIT either. A position
    that completes its holding period there is closed as `END_OF_DATA` at the last close instead of
    as `TIME` at the same close - identical bar, identical price, identical net R, and only the
    reason differs.

    **Counted apart from both buckets on purpose.** Folding it into `agreed` would hide a real
    disagreement between the record and the evidence; calling it a defect would overstate one that
    moves no reported figure. `ExitReason.END_OF_DATA`'s own docstring reads *"the window ended
    while the position was open"*, which is also true of these trades - both labels are true and
    the loop's shape picks one.

    **What it does affect:** the `exit_reasons` mix any report prints. `PR-016`'s control shows
    1,087 `end_of_data` out of sample, and an unknown share of those are time exits wearing the
    other name.
    """
    if len(differences) != 1 or not differences[0].startswith("exit_reason"):
        return False
    return bool(rebuilt["exit_reason"] == "time"
                and "end_of_data" in differences[0]
                and rebuilt["exit_date"] == bars[-1].session_date)


def compare(rebuilt: dict[str, Any], row: dict[str, str]) -> list[str]:
    """Every field, exactly. These are the same arithmetic on the same stored numbers, so a
    difference is a disagreement and never a rounding artefact."""
    differences = []
    for field in CHECKED:
        recorded: Any = row[field]
        mine = rebuilt[field]
        if field == "exit_date":
            recorded = date.fromisoformat(recorded)
        elif field == "exit_reason":
            pass
        elif field == "shares":
            recorded = int(recorded)
        else:
            recorded = Decimal(recorded)
            mine = Decimal(str(mine))
        if recorded != mine:
            differences.append(f"{field}: run {recorded} vs rebuilt {mine}")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--sample", type=Path, default=SAMPLE)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--limit", type=int, help="check only this many rows, for a quick pass")
    args = parser.parse_args()

    if not args.sample.exists():
        print(f"QA: UNAVAILABLE - {args.sample.name} is not there. Run run_pr016.py first.")
        return 2
    study = json.loads(args.result.read_text(encoding="utf-8"))
    as_of = datetime.fromisoformat(study["as_of"])

    # The study's own constants must be the ones this file restates, or the check is of a
    # different study. Compared rather than imported, which is the point of the whole file.
    exit_spec = study["exit"]
    mismatched = [
        name for name, mine, theirs in (
            ("atr_period", ATR_PERIOD, exit_spec["atr_period"]),
            ("atr_stop_multiple", str(STOP_MULTIPLE), exit_spec["atr_stop_multiple"]),
            ("target_r_multiple", str(TARGET_R), exit_spec["target_r_multiple"]),
            ("max_holding_period", HOLD, exit_spec["max_holding_period"]),
            ("slippage_bps", str(SLIPPAGE_BPS), study["slippage_bps_per_side"]),
            ("commission", str(COMMISSION_PER_SHARE), study["commission_per_share"]),
        ) if mine != theirs
    ]
    if mismatched:
        print(f"QA: REFUSED - this file restates {mismatched}, the study recorded something else. "
              f"A re-check under different parameters is not a re-check.")
        return 1

    rows = list(csv.DictReader(args.sample.open(encoding="utf-8")))
    if args.limit:
        rows = rows[: args.limit]
    by_instrument: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_instrument.setdefault(row["instrument_id"], []).append(row)

    print(f"QA re-check of PR-016, {len(rows)} sampled trades over "
          f"{len(by_instrument)} instruments, at as_of {as_of.isoformat()}")
    print("Nothing from the harness is imported: ATR, the fills and the four ordering rules are "
          "written out again here.\n")

    agreed = 0
    label_only: list[str] = []
    unreconstructable: list[str] = []
    disagreements: list[str] = []
    per_arm: Counter[str] = Counter()
    with BarStore(args.data / "bars.duckdb") as store:
        for count, (instrument, sampled) in enumerate(sorted(by_instrument.items()), start=1):
            series = store.as_of(instrument, Interval.DAY, Series.RAW, as_of)
            if not series:
                unreconstructable.extend(f"{instrument}: no series at this as_of" for _ in sampled)
                continue
            bars = list(series.bars)
            atr = wilder_atr(bars, ATR_PERIOD)
            index_of = {bar.session_date: i for i, bar in enumerate(bars)}
            for row in sampled:
                rebuilt = reconstruct(bars, atr, row, index_of)
                if isinstance(rebuilt, str):
                    unreconstructable.append(f"{instrument} {row['entry_date']}: {rebuilt}")
                    continue
                differences = compare(rebuilt, row)
                if is_final_bar_label(differences, rebuilt, bars):
                    label_only.append(f"{instrument} {row['entry_date']} [{row['arm']}]")
                elif differences:
                    disagreements.append(
                        f"{instrument} {row['entry_date']} [{row['arm']}]: " + "; ".join(differences)
                    )
                    per_arm[row["arm"]] += 1
                else:
                    agreed += 1
            if count % 200 == 0:
                print(f"  {count}/{len(by_instrument)} instruments")

    print(f"\n  agreed on every field   {agreed}")
    print(f"  label only, final bar   {len(label_only)}   "
          f"- end_of_data where the hold ALSO completed on the last stored bar; same bar, "
          f"same price, same net R, and it moves no reported figure")
    print(f"  DISAGREED               {len(disagreements)}")
    print(f"  not reconstructable     {len(unreconstructable)}")
    for line in disagreements[:20]:
        print(f"    {line}")
    for line in unreconstructable[:10]:
        print(f"    (skipped) {line}")
    if per_arm:
        print(f"  disagreements by arm: {dict(per_arm.most_common())}")

    if label_only:
        print(f"    e.g. {label_only[0]}  (+{len(label_only) - 1} more)" if len(label_only) > 1
              else f"    {label_only[0]}")

    if disagreements:
        print("\n  §7: a disagreement is a defect in the run, not a rounding difference to be "
              "waved through. The verdict rests on trades this file could not reproduce.")
        return 1
    print("\n  Every sampled trade reproduces from the store and the ratified parameters alone. "
          "That is what BACKTEST_PROTOCOL §7 asks for, and it is not a claim that the STUDY is "
          "right - only that its trade log says what the evidence says.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
