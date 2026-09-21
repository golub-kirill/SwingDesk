"""`CARD-002`'s reconcile: what the owner's auction fills actually cost, against what the model charged.

**This is the trial's product.** `PR-034` priced the closing and opening auctions at half a cent and
a whole cent a share and could observe neither; `PR-036` then made the difference decisive, because
over 2004-2015 the night is an effect at half a cent and nothing at a whole one. So the twenty
sessions exist to produce ONE number - the realised cost a side - and this is the tool that
produces it.

**The fills arrive by hand, and that is by design rather than by omission.** `DR-048` §1 puts the
real orders in the owner's hands, order by order, and §6 records the consequence: the live host is
not on gate 39's allowlist, so this system cannot read the owner's real fills at all. It takes them
as arguments and says so.

**The benchmark is the stored daily bar**, because that is the price the whole case rests on:
`PR-033`..`PR-036` all measured the night as `(next open + dividend) / close - 1` on exactly these
bars. The difference between a fill and that price IS the slippage the model charges for, so the
comparison is against the number that would have been earned rather than against an abstraction.
An auction print is a finer benchmark and `CARD-002` §6.4 keeps it as the later refinement; it is
not needed to answer "did the fill match the price the backtest assumed".

**It is a measurement record, not the trade journal.** `TRADE_JOURNAL`'s record holds decisions and
`CARD-002` §6.5 keeps folding a night into it as its own build item. This file holds executions and
their divergence from a model, which is a different fact with a different owner (`AGENTS.md` §10.5).

    python tools/card002_journal.py record --session 2026-09-22 --fund IJR --entry 138.92 --exit 139.40
    python tools/card002_journal.py report [--data DIR]

    exit 0  recorded, or reported with every trip-wire clear
    exit 2  a trip-wire FIRED - the report names it
    exit 4  UNAVAILABLE - the store could not be read here
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(REPO / "src"))

from swingdesk.contracts.market import CorporateActionKind, Interval, Series
from swingdesk.market_data import BarStore

#: The token `DR-048` points at from its own header.
RECONCILE = "card002-reconcile"

FUNDS = ("IJR", "VB")

OK = 0
TRIPPED = 2
UNAVAILABLE = 4

#: `CARD-002` §5. The cent is `PR-034`'s cost-adverse gate: past it the measured edge is gone, so a
#: realised cost above it over the trial's own length stops the trial rather than being noted.
COST_TRIPWIRE_PER_SIDE = 0.01
COST_TRIPWIRE_AFTER = 20

#: An alert, deliberately not a stop: `PR-034` measured −31.6% and `PR-036` −21.1%, so a return
#: trip-wire tight enough to catch a defect would fire on an ordinary bad quarter.
DRAWDOWN_ALERT = -0.25

#: `CARD-002` §5 again: the daily noise is about ±0.8% of equity against a mean of +0.055%.
NO_JUDGEMENT_BEFORE = 60


class Unreadable(Exception):
    """The store cannot answer here - `AGENTS.md` §12's unavailable, never a silent zero."""


@dataclass(frozen=True)
class Night:
    """One recorded night, priced against the bars if they are stored yet."""

    session: date
    fund: str
    shares: int
    entry_fill: float
    exit_fill: float
    priced: bool = False
    pending: str = ""
    bar_close: float = 0.0
    bar_open: float = 0.0
    dividend: float = 0.0
    exit_session: date | None = None

    @property
    def entry_slippage(self) -> float:
        """Dollars a share paid ABOVE the benchmark close. Positive is a cost."""
        return self.entry_fill - self.bar_close

    @property
    def exit_slippage(self) -> float:
        """Dollars a share received BELOW the benchmark open. Positive is a cost."""
        return self.bar_open - self.exit_fill

    @property
    def cost_per_side(self) -> float:
        return (self.entry_slippage + self.exit_slippage) / 2.0

    @property
    def realised(self) -> float:
        """What the night actually returned on the fills, dividend included."""
        return (self.exit_fill + self.dividend) / self.entry_fill - 1.0

    @property
    def modelled(self) -> float:
        """What the same night returned at the benchmark prices, gross of any cost."""
        return (self.bar_open + self.dividend) / self.bar_close - 1.0


def rows_path(data: Path) -> Path:
    return data / "card002" / "executions.jsonl"


def read_rows(data: Path) -> list[dict[str, Any]]:
    path = rows_path(data)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_row(data: Path, row: Mapping[str, Any]) -> Path:
    """Append one execution. Append-only, like every store here: a correction is a new row.

    The file is the record of what the owner reported, and a report that silently rewrote history
    would make the one number this trial produces unauditable.
    """
    path = rows_path(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True) + "\n")
    return path


def dividends_of(store: BarStore, fund: str, as_of: datetime) -> dict[date, float]:
    """Cash dividends by EX-DATE - paid to the night that ENDS at that open (`PR-033`'s convention)."""
    out: dict[date, float] = defaultdict(float)
    for action in store.actions_as_of(fund, as_of):
        if action.kind is CorporateActionKind.DIVIDEND:
            out[action.effective_date] += float(action.value)
    return dict(out)


def price(row: Mapping[str, Any], bars: Sequence[Any], dividends: Mapping[date, float]) -> Night:
    """Attach the benchmark prices to one recorded night, or say what is still missing.

    The exit's benchmark is the NEXT stored session's open, which does not exist until that session
    has been fetched. A night recorded tonight is therefore `pending` until tomorrow evening, and
    saying so is the honest answer - a report that priced it against today's open would compare the
    exit with a price from before the position existed.
    """
    session = date.fromisoformat(row["session"])
    base = Night(session=session, fund=row["fund"], shares=int(row.get("shares", 1)),
                 entry_fill=float(row["entry"]), exit_fill=float(row["exit"]))
    by_session = {bar.session_date: bar for bar in bars}
    entry_bar = by_session.get(session)
    if entry_bar is None:
        return replace(base, pending=f"no stored bar for {session}")

    later = sorted(day for day in by_session if day > session)
    if not later:
        return replace(base, pending=f"the session after {session} is not stored yet")

    exit_session = later[0]
    exit_bar = by_session[exit_session]
    return replace(base, priced=True, bar_close=float(entry_bar.close),
                   bar_open=float(exit_bar.open),
                   dividend=dividends.get(exit_session, 0.0), exit_session=exit_session)


def tripwires(nights: Sequence[Night]) -> dict[str, Any]:
    """`CARD-002` §5, applied to what has been priced so far.

    The cost gate reads only PRICED nights, because an unpriced one has no cost yet - counting it
    as zero would drag the mean toward the answer the trial is trying to test.
    """
    priced = [night for night in nights if night.priced]
    costs = [night.cost_per_side for night in priced]
    mean_cost = statistics.fmean(costs) if costs else 0.0

    equity, peak, worst = 1.0, 1.0, 0.0
    for night in priced:
        equity *= 1.0 + night.realised
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)

    # ROUNDED to a hundredth of a cent before the comparison. Fills are quoted to the cent, so a
    # difference below that is float noise and not a cost - and without the rounding a mean of
    # exactly one cent arrives as 0.010000000000005 and stops a trial that is inside its gate.
    # The boundary belongs to the passing side: PR-034 measured a positive result AT a cent.
    cost_fired = len(priced) >= COST_TRIPWIRE_AFTER and round(mean_cost, 4) > COST_TRIPWIRE_PER_SIDE
    return {
        "priced": len(priced),
        "recorded": len(nights),
        "mean_cost_per_side": mean_cost,
        "cost_tripwire": cost_fired,
        "drawdown": worst,
        "drawdown_alert": worst <= DRAWDOWN_ALERT,
        "judgement_allowed": len(priced) >= NO_JUDGEMENT_BEFORE,
        "equity": equity,
    }


def build(data: Path, as_of_text: str | None) -> dict[str, Any]:
    rows = read_rows(data)
    path = data / "bars.duckdb"
    if not path.exists():
        raise Unreadable(f"no store at {path}")
    store = BarStore(path)
    try:
        as_of = datetime.fromisoformat(as_of_text) if as_of_text else store.latest_knowledge_time()
        if as_of is None:
            raise Unreadable("the store holds no knowledge instant")
        funds = sorted({str(row["fund"]) for row in rows})
        series = {f: tuple(store.as_of(f, Interval.DAY, Series.RAW, as_of).bars) for f in funds}
        dividends = {f: dividends_of(store, f, as_of) for f in funds}
    finally:
        store.close()

    nights = [price(row, series[row["fund"]], dividends[row["fund"]]) for row in rows]
    nights.sort(key=lambda night: (night.session, night.fund))
    return {"as_of": as_of.isoformat(), "nights": nights, "gates": tripwires(nights)}


def report(built: Mapping[str, Any]) -> None:
    nights: Sequence[Night] = built["nights"]
    gates = built["gates"]
    print(f"CARD-002 executions   {gates['recorded']} recorded, {gates['priced']} priced"
          f"   (knowledge {built['as_of'][:19]})")
    if not nights:
        print("  nothing recorded yet.")
        return

    for night in nights:
        if not night.priced:
            print(f"  {night.session} {night.fund:5s} PENDING - {night.pending}")
            continue
        print(f"  {night.session} {night.fund:5s} "
              f"entry {night.entry_fill:8.4f} vs close {night.bar_close:8.4f} "
              f"({100 * night.entry_slippage:+.2f}c)   "
              f"exit {night.exit_fill:8.4f} vs open {night.bar_open:8.4f} "
              f"({100 * night.exit_slippage:+.2f}c)")
        print(f"                 realised {100 * night.realised:+.3f}%   "
              f"modelled {100 * night.modelled:+.3f}%   "
              f"cost {100 * night.cost_per_side:+.2f}c a side")

    print()
    print(f"  MEAN COST A SIDE: {100 * gates['mean_cost_per_side']:+.2f} cents"
          f"   (the model charges 0.50; the trial stops above 1.00 after"
          f" {COST_TRIPWIRE_AFTER} priced nights)")
    print(f"  equity {gates['equity']:.4f}   worst drawdown {100 * gates['drawdown']:.1f}%")
    if gates["cost_tripwire"]:
        print("  TRIP-WIRE FIRED: the realised cost a side is above a whole cent. CARD-002 §5 stops"
              " the trial - at that cost PR-034's own edge is gone.")
    if gates["drawdown_alert"]:
        print("  ALERT: the book is more than 25% below its peak. This is the market, not a defect"
              " (CARD-002 §5), and it is the owner's call.")
    if not gates["judgement_allowed"]:
        print(f"  NO JUDGEMENT YET: {gates['priced']} priced nights against {NO_JUDGEMENT_BEFORE}."
              " The daily noise is about +-0.8% against a mean of +0.055%.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("record", "report"))
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--session", help="the session whose CLOSE the entry filled at")
    parser.add_argument("--fund", choices=FUNDS)
    parser.add_argument("--entry", type=float, help="the closing auction fill, a price a share")
    parser.add_argument("--exit", dest="exit_fill", type=float,
                        help="the next opening auction fill, a price a share")
    parser.add_argument("--shares", type=int, default=1)
    parser.add_argument("--note", default="")
    parser.add_argument("--as-of", help="the store's knowledge instant")
    args = parser.parse_args(argv)

    if args.mode == "record":
        missing = [name for name, value in
                   (("--session", args.session), ("--fund", args.fund),
                    ("--entry", args.entry), ("--exit", args.exit_fill)) if value is None]
        if missing:
            parser.error(f"record needs {', '.join(missing)}")
        if args.entry <= 0 or args.exit_fill <= 0:
            parser.error("a fill is a price a share and cannot be zero or negative")
        written = append_row(args.data, {
            "session": date.fromisoformat(args.session).isoformat(), "fund": args.fund,
            "shares": args.shares, "entry": args.entry, "exit": args.exit_fill,
            "note": args.note, "recorded_at": datetime.now().astimezone().isoformat(),
        })
        print(f"recorded {args.fund} {args.session}: entry {args.entry}, exit {args.exit_fill}"
              f"  -> {written}")
        return OK

    try:
        built = build(args.data, args.as_of)
    except Unreadable as unreadable:
        print(f"CARD-002 executions UNAVAILABLE: {unreadable}")
        return UNAVAILABLE
    report(built)
    return TRIPPED if built["gates"]["cost_tripwire"] else OK


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
