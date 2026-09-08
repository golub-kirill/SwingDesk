"""What the live paper record actually contains, so watching it costs nobody an afternoon.

**This exists because the alternative is what happened on 2026-09-07.** Asked what the forward
record held, I answered from a memory of a defect five days old and got it wrong in three separate
ways: the record was running, `positions.duckdb` had an automatic writer, and the system had already
opened four positions and round-tripped one. Finding that out took a dozen ad-hoc queries against
three stores. This is those queries, once, with the reasoning attached.

**Why the forward record is worth watching at all.** It is the only evidence in this project that
does **not** raise the multiple-testing hurdle. `b.deflated_sharpe` counts every configuration a
backtest evaluates - 95 so far, hurdle 2.51 sd(SR) - and a forward trade counts nothing, because
nothing was searched to produce it. Every day it runs is free evidence, and it accrues whether or
not anybody is looking.

**What it cannot tell you.** Whether the strategy works. Two closed trades are not a track record,
`b.min_sample` is what says how many are, and this prints the distance rather than an opinion about
it. It also prints no Sharpe: `criteria.yml` v1.1.0 evaluates Track B on journalled trades and the
dispersion of a handful of them is not a number worth computing.

Reads three stores and nothing else. No network, no venue, no writes.

    PYTHONPATH=$PWD/src python tools/forward_record.py --data data
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import duckdb

#: The switch `DR-027` §4.2 keys submission on. Its presence is the whole difference between a
#: system that decides and one that acts, so its mtime is when the forward record began.
ARMED = ".paper-trading-armed"

#: Used inside a raise, where a literal escape would be the thing this file cannot carry cleanly.
NEWLINE = chr(10)


class Busy(Exception):
    """A store another process is holding. Not an error in this tool and not an empty record."""


def read(path: Path, query: str) -> list[tuple[object, ...]]:
    """One query against one store, or `Busy` naming which store and why.

    Collapsing "the store is locked" into "there is nothing there" is the error `AGENTS.md` §12
    calls the most damaging this product can make, and a report about an EMPTY forward record when
    the record is merely unreadable is exactly that error.
    """
    if not path.exists():
        # NOT "held by another process". DuckDB raises the same IOException for both, and a report
        # that told an operator to wait for a pass that had already finished would send them
        # looking for the wrong thing entirely.
        raise Busy(f"{path.name} does not exist at {path.parent}. That is a setup problem, not a "
                   f"forward record of nothing.")
    try:
        with duckdb.connect(str(path), read_only=True) as store:
            return list(store.execute(query).fetchall())
    except duckdb.IOException as busy:
        raise Busy(f"{path.name} is held by another process - almost certainly the daily pass. "
                   f"Nothing is wrong; try again when it finishes.{NEWLINE}  {busy}") from busy


def main() -> int:
    parser = argparse.ArgumentParser(prog="forward_record")
    parser.add_argument("--data", type=Path, default=Path("data"))
    args = parser.parse_args()
    now = datetime.now(UTC)

    switch = args.data / ARMED
    print("THE SWITCH")
    if switch.exists():
        since = datetime.fromtimestamp(switch.stat().st_mtime, tz=UTC)
        print(f"  ARMED since {since.date()} ({(now - since).days} days) - {switch}")
    else:
        print(f"  STOPPED - {switch} is absent, and DR-027 4.2 defaults to stopped")

    # READ-ONLY, which is what this tool needs and is NOT enough to run alongside the daily pass.
    #
    # **Measured 2026-09-07, and the first version of this comment claimed the opposite.** DuckDB
    # takes a file lock per PROCESS: while the evening run holds `positions.duckdb` read-write, a
    # second process is refused even for reading. So this reports cleanly and exits `UNAVAILABLE`
    # rather than crashing, and the twenty-odd minutes a day the pass is running are minutes this
    # cannot answer in. Asking read-only anyway is still right - it means this can never be the
    # process that blocks the run.
    try:
        every = read(
            args.data / "positions.duckdb",
            "SELECT position_id, instrument_id, opened_on, closed_on, entry_price, shares, "
            "initial_stop FROM positions WHERE version = (SELECT max(version) FROM positions p2 "
            "WHERE p2.position_id = positions.position_id) ORDER BY opened_on",
        )
        rows = read(
            args.data / "journal.duckdb",
            "SELECT session_date, outcome, venue_status, count(*) FROM submissions "
            "GROUP BY 1, 2, 3 ORDER BY 1",
        )
    except Busy as busy:
        print(f"  UNAVAILABLE  {busy}", file=sys.stderr)
        return 2

    print("\nTHE BOOK")
    closed = [row for row in every if row[3] is not None]
    open_now = [row for row in every if row[3] is None]
    print(f"  {len(every)} position(s) ever, {len(open_now)} open, {len(closed)} closed")
    for _pid, name, opened, shut, entry, shares, stop in every:
        risk = (Decimal(str(entry)) - Decimal(str(stop))) * shares
        state = f"closed {shut}" if shut else "OPEN"
        print(f"    {name:<6} {shares:>4} sh  opened {opened}  {state:<16} "
              f"risk at entry {risk:.2f}")

    print("\nWHAT WENT TO THE VENUE, and what the guards refused")
    sessions = sorted({row[0] for row in rows})
    accepted = sum(n for _, _, status, n in rows if status == "accepted")
    print(f"  {len(sessions)} session(s) with submissions, {sessions[0]} to {sessions[-1]}"
          if sessions else "  no submissions recorded")
    print(f"  {accepted} order(s) accepted by the venue")
    refused = Counter()
    for _, outcome, status, n in rows:
        if status != "accepted":
            refused[str(outcome)] += n
    for outcome, n in refused.most_common():
        print(f"  {n:>6} not sent - {outcome}")
    if refused.get("stopped"):
        print("         `stopped` is overwhelmingly the position cap refusing candidate five")
        print("         onwards, which is the cap working rather than a fault.")

    print("\nWHAT IT IS WORTH AGAINST THE RATIFIED CRITERIA")
    print(f"  b.deflated_sharpe evaluates Track B on JOURNALLED trades. Closed: {len(closed)}.")
    print("  A forward trade raises the hurdle by NOTHING - nothing was searched to produce it,")
    print("  which is what makes this the only evidence here that does not cost the programme.")
    print("  No Sharpe is printed: the dispersion of a handful of trades is not a number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
