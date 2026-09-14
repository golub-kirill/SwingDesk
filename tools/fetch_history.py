"""Fetch named instruments' whole daily history, and their splits and dividends, into a store.

**Why a tool and not a flag on `refresh_universe.py`.** That pass widens COVERAGE over the directory
and never stores corporate actions. A study that needs one instrument's full history AND its
dividends - `PR-022` reads `SPY` and `BIL` total returns back to 2007, and a T-bill fund pays its
entire return as dividends, so its price alone earns nothing - had no tool that wrote both. This is
that tool and nothing more.

**Resolved by identity, refused otherwise.** Each symbol is looked up in the directory as it is known
now and built with `universe.to_instrument`, the same identity every stored bar carries. A symbol the
directory does not know is refused and named - never guessed into an instrument.

**One knowledge_time for the bars and the actions of a pull**, so a study's `--as-of` reads exactly
this pull and nothing that arrived later.

Network tool. Never imported by anything in src/, never run in CI (CI_POLICY 4).

    python tools/fetch_history.py --data <store dir> --directory <dir holding directory.duckdb> SPY BIL
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.contracts.market import Interval
from swingdesk.contracts.reference import Instrument
from swingdesk.market_data import BarStore, VendorUnavailable, fetch, fetch_actions, vendor_yahoo
from swingdesk.reference_data import universe
from swingdesk.reference_data.directory import DirectoryStore

#: Everything the vendor holds. `registry/vendor_policy.yml` sets no daily ceiling.
DEFAULT_PERIOD = "max"

MISSING = 2
VENDOR = 3


def resolve(directory: DirectoryStore, symbols: Sequence[str],
            as_of: datetime) -> tuple[list[Instrument], list[str]]:
    """(instruments, symbols the directory does not know)."""
    entries = {entry.symbol: entry for entry in directory.as_of(as_of)}
    found = [universe.to_instrument(entries[symbol]) for symbol in symbols if symbol in entries]
    return found, [symbol for symbol in symbols if symbol not in entries]


def pull(store: BarStore, instruments: Sequence[Instrument], knowledge_time: datetime,
         period: str, pause: float) -> list[dict[str, Any]]:
    """Fetch and write each instrument's bars and actions; one row of counts per instrument."""
    rows: list[dict[str, Any]] = []
    for position, instrument in enumerate(instruments):
        if position and pause:
            time.sleep(pause)
        series = fetch(instrument, Interval.DAY, knowledge_time, period=period)
        bars = store.write(series.bars, knowledge_time)
        actions = fetch_actions(instrument, knowledge_time, period=period)
        acted = store.write_actions(actions, knowledge_time)
        rows.append({
            "symbol": instrument.id,
            "bars": len(series.bars),
            "first": series.bars[0].session_date.isoformat() if series.bars else None,
            "last": series.bars[-1].session_date.isoformat() if series.bars else None,
            "bars_inserted": bars.inserted,
            "actions": len(actions),
            "actions_inserted": acted.inserted,
        })
    return rows


def run(data: Path, directory_dir: Path, symbols: Sequence[str], period: str, pause: float) -> int:
    knowledge_time = datetime.now(UTC)
    with DirectoryStore(directory_dir / "directory.duckdb") as directory:
        instruments, missing = resolve(directory, symbols, knowledge_time)
    if missing:
        print(f"refused - the directory does not know: {', '.join(missing)}. Nothing fetched.")
        return MISSING
    try:
        with BarStore(data / "bars.duckdb") as store:
            rows = pull(store, instruments, knowledge_time, period, pause)
    except VendorUnavailable as error:
        print(f"vendor UNAVAILABLE - {error}")
        return VENDOR
    print(f"knowledge_time {knowledge_time.isoformat()}   period {period}   store {data / 'bars.duckdb'}")
    for row in rows:
        print(f"  {row['symbol']:6} {row['bars']:>6} bars {row['first']} .. {row['last']}   "
              f"{row['bars_inserted']} new   {row['actions']} actions, {row['actions_inserted']} new")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="fetch_history")
    parser.add_argument("symbols", nargs="+", help="directory symbols to fetch, e.g. SPY BIL")
    parser.add_argument("--data", type=Path, required=True,
                        help="directory whose bars.duckdb receives the pull")
    parser.add_argument("--directory", type=Path, default=REPO / "data",
                        help="directory holding directory.duckdb, which resolves each symbol")
    parser.add_argument("--period", default=DEFAULT_PERIOD,
                        help="the vendor's window; 'max' is everything it holds")
    parser.add_argument("--pause", type=float, default=None,
                        help="seconds between instruments; defaults to limits.pause_seconds in "
                             "registry/vendor_policy.yml")
    args = parser.parse_args()
    pause = args.pause if args.pause is not None else vendor_yahoo.policy().pause_seconds
    return run(args.data, args.directory, args.symbols, args.period, pause)


if __name__ == "__main__":
    raise SystemExit(main())
