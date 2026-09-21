"""`CARD-002`'s plan pass: what to buy into tonight's close, and what it risks.

**Why this is the first thing built and why it writes no order.** `DR-048` split the card across two
accounts: the paper account is driven by this system under `CHARTER` A-002, and the REAL account is
driven by the owner, order by order, under A-001 §1. The owner's twenty sessions are what measure
the auction fill - the one number `PR-034` priced and could not observe, and the number `PR-036`
made decisive, because at half a cent the night is an effect and at a whole cent it is nothing.

So this pass reads, sizes, refuses and PRINTS. It never submits. A later pass submits the paper
copy; this one is the card the owner types from, and it is deliberately the part that can run first.

**It refuses rather than guesses.** A fund whose prior close is missing or behind the session every
other fund reached is not sized from the last number that happens to be stored - `CARD-002` §3's
data row and `FAIL_CLOSED_POLICY` §3. One fund refusing does not refuse the other: the card holds
whichever funds it could size, which is what the card document says happens when one does not fill.

**Risk is denominated even though there is no stop.** `RISK_SPEC` §2 wants every position to report
`R`, and `R` is normally `entry - stop + costs`. This card has no stop (`DR-048` §5), so `R` is the
position's notional times the standard deviation of that fund's own overnight return over
`overnight.risk_unit_lookback` sessions. It is measured, it refuses when too few nights are stored,
and it puts a night's loss in the same unit as every other position this project has journalled.

    python tools/card002_plan.py [--data DIR] [--equity N] [--shares N] [--session YYYY-MM-DD]

    exit 0  a plan was produced for every fund
    exit 2  REFUSED for at least one fund - the plan names which and why
    exit 4  UNAVAILABLE - the store could not be read here
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(REPO / "src"))

from swingdesk.contracts.market import CorporateActionKind, Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry

#: The token `DR-048` points at. The record and the code name each other, which is what
#: `tools/verify_decisions.py` reads.
PLAN = "card002-plan"

#: `CARD-002` §3. The card trades these two and nothing else; a third fund is a new card version.
FUNDS = ("IJR", "VB")

PLANNED = 0
REFUSED = 2
UNAVAILABLE = 4

#: Alpaca accepts `cls` only before 15:50 ET and `opg` only before 09:28 or after 19:00 ET
#: (`DR-048` §3). They are printed so the owner types against the venue's clock, not a habit.
CLOSE_CUTOFF_ET = "15:50"
OPEN_WINDOW_ET = "after 19:00 tonight, or before 09:28 tomorrow"


class Unreadable(Exception):
    """The store cannot answer here - `AGENTS.md` §12's unavailable, never a silent zero."""


@dataclass(frozen=True)
class Night:
    """One completed overnight move: the close paid for it, the next open realised it."""

    session: date
    ret: float


@dataclass(frozen=True)
class Leg:
    """One fund's share of tonight's plan, or the reason it has none."""

    fund: str
    refused: str = ""
    prior_close: float = 0.0
    prior_session: date | None = None
    nights: int = 0
    overnight_sd: float = 0.0
    paper_shares: int = 0
    owner_shares: int = 0
    notional: float = 0.0
    risk_r: float = 0.0

    @property
    def admitted(self) -> bool:
        return not self.refused


def dividends_of(store: BarStore, fund: str, as_of: datetime) -> dict[date, float]:
    """Cash dividends by EX-DATE, summed where a fund pays more than one on a day.

    The same convention `PR-033`..`PR-036` measured on: a dividend detaches at the ex-date's OPEN,
    so it belongs to the night that ends there and not to the session that follows it.
    """
    out: dict[date, float] = defaultdict(float)
    for action in store.actions_as_of(fund, as_of):
        if action.kind is CorporateActionKind.DIVIDEND:
            out[action.effective_date] += float(action.value)
    return dict(out)


def nights_of(bars: Sequence[Any], dividends: Mapping[date, float]) -> list[Night]:
    """Every completed night in a fund's stored bars, oldest first.

    A night is `(next open + the dividend detaching at it) / this close - 1`. It needs two
    consecutive stored sessions, so a gap in the store shortens the sample rather than inventing a
    move across it - the returned list is what was MEASURED, and the caller counts it.

    **The session comes from `Bar.session_date`, never from `event_time.date()`** - the contract
    says so in its own field description, because a timestamp's date depends on the timezone it
    happens to carry and the storage layers convert.
    """
    out: list[Night] = []
    for earlier, later in itertools.pairwise(bars):
        close = float(earlier.close)
        if close <= 0:
            continue
        session = later.session_date
        out.append(Night(session, (float(later.open) + dividends.get(session, 0.0)) / close - 1.0))
    return out


def size(equity: float, position_pct: float, price: float) -> int:
    """Whole shares of one leg, rounded DOWN.

    Down, because a fund rounded up is a position larger than the size the owner ruled, and two of
    them are an account that cannot pay for its own plan.
    """
    if price <= 0 or equity <= 0:
        return 0
    return math.floor(equity * (position_pct / 100.0) / price)


def leg_for(fund: str, bars: Sequence[Any], dividends: Mapping[date, float], *,
            decision_session: date, equity: float, position_pct: float, lookback: int,
            owner_shares: int) -> Leg:
    """One fund's plan, or the refusal that replaces it."""
    if not bars:
        return Leg(fund, refused="no stored bars")

    last = bars[-1]
    prior_session = last.session_date
    if prior_session != decision_session:
        return Leg(fund, refused=f"last stored session {prior_session} is behind {decision_session}")

    # TWO at the very least, whatever the registry says: a standard deviation of one number is
    # not a small sample, it is undefined - and `statistics.stdev` raises rather than returning
    # zero. A crash is the wrong shape of failure for a pass whose job is to refuse cleanly.
    needed = max(2, lookback)
    nights = nights_of(bars, dividends)[-needed:]
    if len(nights) < needed:
        return Leg(fund, refused=f"{len(nights)} stored nights, {needed} needed for R")

    close = float(last.close)
    sd = statistics.stdev(night.ret for night in nights)
    paper = size(equity, position_pct, close)
    return Leg(
        fund=fund,
        prior_close=close,
        prior_session=prior_session,
        nights=len(nights),
        overnight_sd=sd,
        paper_shares=paper,
        owner_shares=owner_shares,
        notional=owner_shares * close,
        risk_r=owner_shares * close * sd,
    )


def decision_session_of(series: Mapping[str, Sequence[Any]]) -> date | None:
    """The session the plan is decided from: the latest one ANY fund reached.

    The latest rather than the earliest, deliberately. Taking the earliest would let one stale fund
    silently drag the other back to a price that is no longer the prior close, and the plan would
    look complete while being a day old. Taking the latest makes the stale fund refuse, loudly.
    """
    ends = [bars[-1].session_date for bars in series.values() if bars]
    return max(ends) if ends else None


def build(args: argparse.Namespace) -> dict[str, Any]:
    """Read the store, size both legs, and return the plan as a record."""
    registry = ParameterRegistry.load(REPO / "registry" / "parameters.yml")
    position_pct = float(registry.decimal_value("overnight.position_pct")[0])
    lookback = registry.int_value("overnight.risk_unit_lookback")[0]

    path = args.data / "bars.duckdb"
    if not path.exists():
        raise Unreadable(f"no store at {path}")
    store = BarStore(path)
    try:
        as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
        if as_of is None:
            raise Unreadable("the store holds no knowledge instant")
        series = {
            fund: tuple(store.as_of(fund, Interval.DAY, Series.RAW, as_of).bars) for fund in FUNDS
        }
        dividends = {fund: dividends_of(store, fund, as_of) for fund in FUNDS}
    finally:
        store.close()

    session = date.fromisoformat(args.session) if args.session else decision_session_of(series)
    if session is None:
        raise Unreadable("neither fund has a stored bar")

    legs = [
        leg_for(fund, series[fund], dividends[fund], decision_session=session,
                equity=args.equity, position_pct=position_pct, lookback=lookback,
                owner_shares=args.shares)
        for fund in FUNDS
    ]
    return {
        "card": "CARD-002",
        "decided_from": session.isoformat(),
        "as_of": as_of.isoformat(),
        "position_pct": position_pct,
        "risk_unit_lookback": lookback,
        "paper_equity": args.equity,
        "owner_shares_each": args.shares,
        "legs": [asdict(leg) for leg in legs],
        "refused": [leg.fund for leg in legs if not leg.admitted],
    }


def report(plan: Mapping[str, Any]) -> None:
    """Print the plan, then the card the owner types from."""
    print(f"CARD-002 plan   decided from the close of {plan['decided_from']}"
          f"   (knowledge {plan['as_of'][:19]})")
    for leg in plan["legs"]:
        if leg["refused"]:
            print(f"  {leg['fund']:5s} REFUSED - {leg['refused']}")
            continue
        print(f"  {leg['fund']:5s} close ${leg['prior_close']:.2f}"
              f"   overnight sd {100 * leg['overnight_sd']:.2f}% over {leg['nights']} nights")
        # The paper leg is printed only when an equity was given. Printing "0 shares at 50% of $0"
        # for an owner who asked only for their own minimum size is a line that looks like a
        # refusal and is not one.
        paper = (f"paper {leg['paper_shares']} shares at {plan['position_pct']:.0f}% of "
                 f"${plan['paper_equity']:,.0f}   |   " if plan["paper_equity"] > 0 else "")
        print(f"        {paper}owner {leg['owner_shares']} share(s), ${leg['notional']:.2f}, "
              f"R ${leg['risk_r']:.2f}")

    admitted = [leg for leg in plan["legs"] if not leg["refused"]]
    print()
    if not admitted:
        print("  nothing to enter: every fund refused.")
        return
    print(f"  ENTER BY {CLOSE_CUTOFF_ET} ET - market-on-close (MOC) BUY:")
    for leg in admitted:
        print(f"      BUY  {leg['owner_shares']}  {leg['fund']}   MOC")
    print(f"  THEN {OPEN_WINDOW_ET} - market-on-open (MOO) SELL, the whole position:")
    for leg in admitted:
        print(f"      SELL {leg['owner_shares']}  {leg['fund']}   MOO")
    print()
    print("  The MOO sell IS the protection (DR-048 section 5). There is no stop, and a night with"
          " no exit order lodged stops the trial (CARD-002 section 5).")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data",
                        help="the directory holding bars.duckdb")
    parser.add_argument("--equity", type=float, default=0.0,
                        help="paper account equity, for the 50%%-a-fund paper sizing")
    parser.add_argument("--shares", type=int, default=1,
                        help="whole shares a fund for the owner's REAL minimum-size session")
    parser.add_argument("--session", help="decide from this session instead of the latest stored")
    parser.add_argument("--as-of", help="the store's knowledge instant")
    parser.add_argument("--out", type=Path, help="write the plan as JSON here")
    args = parser.parse_args(argv)

    try:
        plan = build(args)
    except Unreadable as unreadable:
        print(f"CARD-002 plan UNAVAILABLE: {unreadable}")
        return UNAVAILABLE

    report(plan)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(plan, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"  plan written to {args.out}")
    return REFUSED if plan["refused"] else PLANNED


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
