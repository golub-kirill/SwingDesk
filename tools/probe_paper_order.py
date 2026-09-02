"""Place ONE order at the paper venue, deliberately, to prove the write path works end to end.

**A probe, not a feature, and not a trade.** `DR-027` §2 fixes what the SYSTEM may submit: an entry
for a candidate a run decided `Trade` and `sizing` sized. This is none of that. It is an operator
checking that the code between a decision and a venue actually functions, before the day something
depends on it — the same reason `verify_*.py` exists for everything else here.

It uses the **real** path: `broker.entry_order` builds the order and `AlpacaClient.submit` sends it,
through `guards`. Nothing is stubbed, so a green result is evidence about production rather than
about a probe.

**The limit is deliberately far below the market and that is the whole safety design.** An order
that cannot fill proves the venue ACCEPTED it — which is what the write path is being asked about —
without acquiring a position the system's own book knows nothing about. `time_in_force: day` then
retires it at the close, and `DR-027` §3.3 is why nothing here needs a cancel verb.

**It records what it did.** A `Submission` row under a `probe-` run id, so a real order placed by a
human is not the one action in this system with no record (`SECURITY.md` §4).

    PYTHONPATH=$PWD/src python tools/probe_paper_order.py --symbol F --limit 1 --stop 0.5 --target 2
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk import broker as broker_pkg
from swingdesk.journal_evidence.journal import Journal, Submission


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="a REAL US ticker; the venue rejects TEST.1")
    parser.add_argument("--shares", type=int, default=1)
    parser.add_argument("--limit", type=Decimal, required=True,
                        help="far below the market on purpose - an order that cannot fill still "
                             "proves the venue accepted it")
    parser.add_argument("--stop", type=Decimal, required=True, help="below the limit")
    parser.add_argument("--target", type=Decimal, required=True,
                        help="above the limit. A bracket is a chain of three and the venue "
                             "refuses one with a leg missing")
    parser.add_argument("--data", type=Path,
                        default=Path(os.environ.get("SWINGDESK_DATA") or REPO / "data"))
    args = parser.parse_args()

    now = datetime.now(UTC)
    policy = broker_pkg.load_policy()
    # The exchange session, never the clock's date - `DR-027` 9, which this probe found.
    session = broker_pkg.trading_session(policy.market, now)
    arming = broker_pkg.read_arming(args.data, policy.write)
    print(f"venue    {policy.label}  {policy.base_url}")
    print(f"arming   {'ARMED' if arming.armed else 'STOPPED'} - {arming.reason}")
    if arming.stopped:
        print("\nnothing was sent. Arm the switch first; it is stopped by default (DR-027 4.2).")
        return 2

    write = policy.write
    assert write is not None
    client = broker_pkg.open_client(policy, arming=arming)

    order = broker_pkg.entry_order(
        instrument_id=args.symbol, shares=args.shares,
        limit_price=args.limit, stop_price=args.stop, target=args.target,
        session_date=session, write=write, market=policy.market,
    )
    print(f"order    {order.shares} {order.symbol} limit {order.limit_price} "
          f"stop {order.stop_price} target {order.target_price}  id {order.client_order_id}")

    run_id = f"probe-{now.strftime('%Y%m%dT%H%M%SZ')}"
    outcome, detail, venue_id, venue_status = "rejected", "", None, None
    try:
        placed = client.submit(order, now)
    except broker_pkg.SubmissionStopped as stopped:
        outcome, detail = "stopped", str(stopped)
        print(f"\nSTOPPED  {stopped}")
    except broker_pkg.BrokerUnavailable as unavailable:
        detail = str(unavailable)
        print(f"\nREJECTED {unavailable}")
    else:
        outcome, venue_id, venue_status = "sent", placed.order_id, placed.status
        print(f"\nACCEPTED {placed.status}  venue order {placed.order_id}")
        print(f"         filled {placed.filled_shares} of {order.shares}")

    with Journal(args.data / "journal.duckdb") as journal:
        journal.record_submission(Submission(
            run_id=run_id, client_order_id=order.client_order_id, attempted_at=now,
            session_date=session, instrument_id=order.instrument_id, shares=order.shares,
            limit_price=order.limit_price, stop_price=order.stop_price,
            outcome=outcome, detail=detail or None,
            venue_order_id=venue_id, venue_status=venue_status,
        ))
    print(f"recorded {run_id}")

    print("\nA probe, not a trade. Nothing here decided anything, and the position store is")
    print("untouched: an order the venue accepted is not a fill (DR-027 6).")
    return 0 if outcome == "sent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
