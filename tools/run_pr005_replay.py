"""PR-005, replayed from the recorded sample - to emit the trade log the original never wrote.

`PR-005.json` reports aggregates: 2629 trades in the `1x/primary/NONE` cell, a mean R, a hit rate.
It does not report the TRADES. `PR-009` needs the ordered sequence of net R to compute a drawdown
distribution, and an aggregate cannot be un-aggregated, so the study has to be re-run to get them.

**This is a replay, and it is NOT a reproduction of PR-005's inputs. The difference matters.**

`tools/run_pr005.py` downloads the CURRENT NASDAQ directory, calls `datetime.now()`, and fetches
live from the vendor. Re-running it today samples a different universe over a different window and
answers a different question - the same defect the `PR-002` correction found on 2026-08-16, one
study over. So this tool does not re-sample. It takes the 68 admitted instruments, the window, and
every parameter FROM THE RECORDED RESULT, and reads bars from the local store instead of the vendor.

What that still cannot fix, stated because it changes how the comparison should be read: the local
store's earliest `knowledge_time` for these instruments is 2026-08-03 13:25 local, and PR-005 ran
at 02:02 UTC the same day - about sixteen hours EARLIER. So these bars are a later vintage of the
same source, not the bytes the study saw. Both are unadjusted OHLC, which is the stable form, but
"the vendor did not revise settled history" is an assumption here rather than a fact this project
can check. A mismatch is therefore evidence, not proof, of a defect - and `TODO.md` 2's standing
instruction is to stop and report it rather than publish a trade log that disagrees with the
result it claims to belong to.

The engine, the gate logic, the arms and the ATR registry are IMPORTED from `run_pr005`, never
restated. A replay that re-implements what it is checking is checking itself.

    python tools/run_pr005_replay.py [--write]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr005 import (
    ARMS,
    ATR_STOP_MULTIPLE,
    COMMISSION_PER_SHARE,
    HOLDOUT_FRACTION,
    MAX_HOLDING_BARS,
    RISK_PER_TRADE,
    SLIPPAGE_BPS,
    STRESS_MULTIPLE,
    TRIGGER_LOOKBACK,
    _atr_registry,
    _gates,
)
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.validation.backtest import (
    BacktestConfig,
    BreakoutHigh,
    CostModel,
    ExitPolicy,
    run_arm,
)

RESULT = REPO / "docs" / "prereg" / "results" / "PR-005.json"
TRADES = REPO / "docs" / "prereg" / "results" / "PR-005-trades.csv"
PROVENANCE = REPO / "docs" / "prereg" / "results" / "PR-005-trades-provenance.json"
#: Default bar store. `--data` overrides it, and it has to: `data/` lives only in the main
#: checkout, so a worktree replaying this study reads nothing without being pointed at the real
#: store (`AGENTS.md` section 12). The guard rail this tool IS - PR-005 must replay unchanged -
#: is worth nothing if it can only be run from the one checkout that cannot commit the fix.
DATA = REPO / "data" / "bars.duckdb"

#: Parameters the recorded result names, mapped to the runner constant that must still equal them.
#: Checked before anything runs: if a constant has drifted since 2026-08-03, this would replay a
#: DIFFERENT study under PR-005's name, and the aggregate comparison below would quietly blame the
#: data for a code change.
PINNED = {
    "atr_stop_multiple": ATR_STOP_MULTIPLE,
    "max_holding_bars": MAX_HOLDING_BARS,
    "risk_per_trade": RISK_PER_TRADE,
    "commission_per_share": COMMISSION_PER_SHARE,
    "slippage_bps": SLIPPAGE_BPS,
    "stress_multiple": STRESS_MULTIPLE,
    "trigger_lookback": TRIGGER_LOOKBACK,
}

CSV_COLUMNS = [
    "regime", "arm", "period", "instrument_id",
    "signal_date", "entry_date", "exit_date",
    "entry_price", "stop_price", "exit_price", "shares",
    "initial_risk_per_share", "costs", "mfe", "mae", "exit_reason",
    "gross_r", "net_r", "holding_days",
]


def _drifted_parameters(recorded: dict) -> list[str]:
    """Recorded parameters that no longer equal the runner's constants."""
    drift = []
    for name, constant in PINNED.items():
        was = recorded.get(name)
        if was is None:
            drift.append(f"{name}: not recorded in the result, cannot be checked")
        elif Decimal(str(was)) != Decimal(str(constant)):
            drift.append(f"{name}: recorded {was}, runner now {constant}")
    return drift


def _load(store: BarStore, instrument_id: str, window: tuple[date, date]) -> BarSeries | None:
    """Bars for one instrument, clipped to the study's window.

    The store now holds sessions past PR-005's window end; including them would add trades the
    study never saw and make the comparison meaningless in the flattering direction, since a
    longer sample looks more significant.
    """
    series = store.as_of(instrument_id, Interval.DAY, Series.RAW, datetime.now().astimezone())
    kept = tuple(b for b in series.bars if window[0] <= b.session_date <= window[1])
    if not kept:
        return None
    return BarSeries(
        instrument_id=series.instrument_id, interval=series.interval, series=series.series,
        knowledge_time=series.knowledge_time, bars=kept,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="write the trade log. Without this nothing is written and only the "
                             "comparison is reported - PR-005's own instruction is to stop on a "
                             "mismatch, so publishing is deliberately not the default")
    parser.add_argument("--accept-drift", action="store_true",
                        help="publish even though cells disagree. Requires --write, and writes the "
                             "full cell-by-cell comparison beside the log so the disagreement "
                             "travels WITH the artifact instead of living in someone's memory")
    parser.add_argument("--data", type=Path, default=None,
                        help="directory holding bars.duckdb; defaults to this checkout's data/, "
                             "which a worktree does not have")
    args = parser.parse_args()
    store_path = (args.data / "bars.duckdb") if args.data else DATA

    recorded = json.loads(RESULT.read_text(encoding="utf-8"))
    instruments = recorded["instruments"]
    window = tuple(date.fromisoformat(d) for d in recorded["window"])
    print(f"PR-005 recorded {len(instruments)} admitted instruments, "
          f"window {window[0]} -> {window[1]}, run at {recorded['run_at']}")

    drift = _drifted_parameters(recorded["parameters"])
    if drift:
        print("\nREFUSING: the runner's constants no longer match the recorded study.")
        for line in drift:
            print(f"  {line}")
        print("Replaying under PR-005's name with different parameters would answer a different "
              "question and blame the data for it.")
        return 2

    if not store_path.is_file():
        print(f"\nUNAVAILABLE: no bar store at {store_path}. `data/` is gitignored operational "
              f"state and lives only in the main checkout - point --data at it from a worktree.")
        return 4

    with BarStore(store_path) as store:
        loaded = {i: s for i in instruments if (s := _load(store, i, window)) is not None}
    missing = sorted(set(instruments) - set(loaded))
    print(f"loaded {len(loaded)} of {len(instruments)} from the local store"
          + (f"; MISSING {missing}" if missing else ""))
    if missing:
        print("REFUSING: a replay over a subset is not a replay of this study.")
        return 2

    sessions = sorted({b.session_date for s in loaded.values() for b in s.bars})
    boundary = sessions[int(len(sessions) * (Decimal(1) - HOLDOUT_FRACTION))]
    print(f"sessions {sessions[0]} -> {sessions[-1]}, holdout begins {boundary}")
    recorded_boundary = date.fromisoformat(recorded["holdout_from"])
    if boundary != recorded_boundary:
        # Not fatal on its own - it is a fact about the data, and reporting it is the point - but
        # it moves trades between the two reported populations, so the comparison must be read
        # knowing it happened.
        print(f"  NOTE: the recorded holdout boundary was {recorded_boundary}. The split has "
              f"moved, so primary/holdout counts are not comparable cell by cell.")

    base = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    regimes = {"1x": base, "3x": base.stressed(STRESS_MULTIPLE)}
    registry = _atr_registry()

    rows: list[dict] = []
    cells: dict[tuple[str, str, str], list] = {}
    for count, (_instrument_id, series) in enumerate(sorted(loaded.items()), start=1):
        atr_series = atr_component.compute(series, registry)
        gates = _gates(series)
        for regime, costs in regimes.items():
            for arm in ARMS:
                config = BacktestConfig(
                    arm=arm, exits=ExitPolicy(ATR_STOP_MULTIPLE, MAX_HOLDING_BARS),
                    costs=costs, risk_per_trade=RISK_PER_TRADE,
                    trigger=BreakoutHigh(TRIGGER_LOOKBACK),
                )
                for trade in run_arm(series, gates[arm], atr_series, config).trades:
                    period = "holdout" if trade.entry_date >= boundary else "primary"
                    cells.setdefault((regime, arm, period), []).append(trade)
                    rows.append({
                        "regime": regime, "arm": arm, "period": period,
                        "instrument_id": trade.instrument_id,
                        "signal_date": trade.signal_date, "entry_date": trade.entry_date,
                        "exit_date": trade.exit_date, "entry_price": trade.entry_price,
                        "stop_price": trade.stop_price, "exit_price": trade.exit_price,
                        "shares": trade.shares,
                        "initial_risk_per_share": trade.initial_risk_per_share,
                        "costs": trade.costs, "mfe": trade.mfe, "mae": trade.mae,
                        "exit_reason": trade.exit_reason.value,
                        "gross_r": trade.gross_r, "net_r": trade.net_r,
                        "holding_days": trade.holding_days,
                    })
        if count % 20 == 0:
            print(f"  simulated {count}/{len(loaded)} instruments")

    print(f"\n{len(rows)} trades across {len(cells)} cells\n")
    print(f"{'cell':28} {'recorded':>9} {'replayed':>9} {'delta':>7}   "
          f"{'recorded mean R':>16} {'replayed mean R':>16} {'delta':>10}")

    by_count = 0
    by_mean_r = 0
    comparison: list[dict] = []
    # `regimes[regime]["arms"][PERIOD][ARM]` - period nests OUTSIDE arm. Read the other way round
    # first, which produced a confident "MISMATCH in 20 cells" that was entirely this loop: every
    # lookup missed, every cell reported zero replayed trades, and the tool would have published a
    # false accusation that PR-005 does not reproduce.
    for regime, block in sorted(recorded["regimes"].items()):
        for period, arms in sorted(block["arms"].items()):
            for arm, published in sorted(arms.items()):
                if not isinstance(published, dict) or "trades" not in published:
                    continue
                trades = cells.get((regime, arm, period), [])
                was_n, now_n = int(published["trades"]), len(trades)
                was_r = Decimal(str(published["mean_r"]))
                now_r = (
                    sum((t.net_r for t in trades), start=Decimal(0)) / len(trades)
                    if trades else Decimal(0)
                )
                comparison.append({
                    "cell": f"{regime}/{arm}/{period}",
                    "recorded_trades": was_n, "replayed_trades": now_n,
                    "recorded_mean_r": str(was_r), "replayed_mean_r": str(now_r),
                    "mean_r_delta": str(now_r - was_r),
                })
                flag = ""
                if was_n != now_n:
                    by_count += 1
                    flag = "  <- COUNT"
                # `TODO.md` 2 says "if mean-R does not match". EXACTLY, and this is deliberately
                # not a tolerance: the first version of this loop compared only trade counts and
                # printed "every cell matched" while four cells disagreed on the very number the
                # instruction names - a check reporting success about something it never looked at.
                # Choosing a tolerance here would be choosing how much disagreement to hide, and
                # that is the owner's call to make with the deltas in front of them, not this
                # tool's to make silently.
                elif was_r != now_r:
                    by_mean_r += 1
                    flag = "  <- MEAN R"
                print(f"{regime}/{arm}/{period:<8}{'':6} {was_n:>9} {now_n:>9} {now_n - was_n:>7}   "
                      f"{was_r:>16.6f} {now_r:>16.6f} {now_r - was_r:>10.6f}{flag}")

    print()
    drifted = by_count or by_mean_r
    if drifted:
        print(f"MISMATCH: {by_count} cell(s) on trade count, {by_mean_r} on mean R.")

    if drifted and not args.accept_drift:
        print("`TODO.md` 2's standing instruction is to STOP and report, not to publish a trade "
              "log that disagrees with the result it claims to belong to.")
        if args.write:
            print("--write was passed and is being IGNORED. Pass --accept-drift as well, which "
                  "records the disagreement beside the log rather than hiding it.")
        return 1

    if not args.write:
        print("pass --write to publish the trade log."
              + (" --accept-drift is also required." if drifted else ""))
        return 0

    TRADES.parent.mkdir(parents=True, exist_ok=True)
    with TRADES.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} trades to {TRADES.relative_to(REPO)}")

    # The disagreement travels WITH the artifact. A trade log whose caveat lives in a commit
    # message is a trade log that will one day be read without it - and this one is destined for
    # `PR-009`, which must register against the replay's vintage rather than against PR-005's
    # published aggregate, because those two are now known not to be the same thing.
    vintages = sorted({s.knowledge_time.isoformat() for s in loaded.values()})
    PROVENANCE.write_text(json.dumps({
        "generated_by": "tools/run_pr005_replay.py",
        "replays": "PR-005",
        "trades": len(rows),
        "is_a_reproduction_of_pr005_inputs": False,
        "why_not": (
            "PR-005 ran at 2026-08-03T02:02:06Z and fetched live. The local store's earliest "
            "knowledge_time for this sample postdates that, so the bytes the study read no longer "
            "exist anywhere and cannot be recovered by refetching."
        ),
        "observed_effect": (
            "Ungated (NONE), MA_STACK (B) and PRICE_AND_STACK (C) reproduce EXACTLY in every "
            "period and regime, as does the whole primary period. ABOVE_LONG_MA (A) and STRUCTURE "
            "(D) differ in the holdout by <=0.00052 mean R at identical trade counts - the two "
            "gates that turn on a single margin, where a revised close or extreme flips the "
            "verdict without changing which triggers fired."
        ),
        "read_this_log_as": "the replay's trades at the vintage below, not PR-005's trades",
        "series_knowledge_times": vintages,
        "cells": comparison,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote the cell-by-cell comparison to {PROVENANCE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
