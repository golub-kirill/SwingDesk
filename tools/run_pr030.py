"""`PR-030` - which ORDER should carry `CARD-001`'s entries: today's day limit, a limit-on-open, or a
market-on-open?

**What is already known.** `PR-024`: the card's names pay 37.8 bps a side to meet the book after the
open. `PR-025` (exploratory): an order filled at the opening cross, no spread, earns what 15:55
earns and 0.375% a trade more than the continuous open. But the live order is none of those: it is
a DAY LIMIT at the sizing price - the signal session's close (`DR-027` §3.1) - which pays the spread
when it is marketable at the open, and otherwise RESTS, filling at the limit if the price comes to
it and not at all if it does not. A limit-on-open (`opg`) takes the cross or nothing. So switching
routes wins the spread on the marketable entries and loses the ones that would have filled later at
the limit. This measures the net of the two, with every drawn entry counted: an order that never
filled earns what cash earns, nothing.

**Four orders, one entry, the limit at the signal close `L`:**

* `D` - today's day limit, meeting the continuous book after the cross. The 09:30 minute's ask is
  its first print plus the quoted half-spread: at or under `L`, it fills there; otherwise it rests
  at `L` and fills at `L` in the first minute whose low reaches it, paying no spread; else no fill;
* `G` - a limit-on-open (`opg`): the adjusted opening cross if at or under `L`, else no fill;
* `M` - a market-on-open: the cross, always. `PR-025`'s auction arm, already counted;
* `J` - a day limit that JOINS the cross when marketable there, and rests at `L` from the cross's
  minute otherwise. How a queued `day` order is routed at the open Alpaca does not document; `J`
  bounds the answer from the other side. Counted, never read.

**The verdict reads `G - D`**: does changing the route win more on the marketable entries than it
loses on the resting ones? `M - D` and `J - D` are reported beside it.

**Everything else is `PR-024`'s and `PR-025`'s**: the draw, the stores and their instants, the walk
(`run_pr024.walk_entry`), the exits and their costs by moment, and the cross read from the tape and
brought onto the bars' basis (`run_pr025.cross_price`, `run_pr025.adjustment_factor`).

    PYTHONPATH=$PWD/src python tools/run_pr030.py --data <store> --minutes <m> --quotes <q> \
        --auctions <a> --as-of <t> --minutes-as-of <t> --quotes-as-of <t> --auctions-as-of <t> \
        --resamples 10000
    python tools/run_pr030.py --report
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr024 as p24
import run_pr025 as p25
from run_pr016 import BLOCK, atr_registry, cluster_of
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.reference import ExchangeSession
from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.market_data.auctions import CLOSING, OPENING, AuctionStore, Print
from swingdesk.market_data.minutes import Minute, MinuteStore
from swingdesk.market_data.quotes import CLOSE, ELEVEN, OPEN, Quote, QuoteStore
from swingdesk.validation.backtest import CostModel
from swingdesk.validation.backtest.intraday import (
    MinuteTieBreak,
    TieBreak,
    regular_hours,
    reproduces,
    session_for,
)

DAY, OPG, MOO, JOINED = "D", "G", "M", "J"
ARMS = (DAY, OPG, MOO, JOINED)
PRIMARY = (OPG, DAY)
READINGS: dict[str, tuple[str, str]] = {"G-D": PRIMARY, "M-D": (MOO, DAY), "J-D": (JOINED, DAY)}
COSTINGS = ("net", "gross", "cost_adverse")
MOMENTS = (OPEN, ELEVEN, CLOSE)

#: How an arm came to be in the market, or not. A missed order is a result, not an exclusion.
MARKETABLE, CROSSED, RESTED, MISSED = "marketable", "crossed", "rested", "missed"

BOOTSTRAP_SEED = 20260920
RESULT = p24.RESULTS / "PR-030.json"
POWER = p24.RESULTS / "PR-030-power.json"
POWER_RESAMPLES = 2000
QA_SAMPLE = p24.RESULTS / "PR-030-qa-sample.csv"
QA_ROWS = 400

#: Whose QA rows an order must come back to, to the digit: `M` is `PR-025`'s auction arm on the same
#: stores; `D`, where marketable at the open, is `PR-024`'s `O` - the same fill, spread and walk.
#: Amendment A-1: the registered tuple asked `M` for the fill "M" where its fills are `CROSSED`,
#: so it checked none of `PR-025`'s rows.
REPRODUCES = ((MOO, CROSSED, p24.RESULTS / "PR-025-qa-sample.csv", p25.AUCTION),
              (DAY, MARKETABLE, p24.RESULTS / "PR-024-qa-sample.csv", p24.BASE))


@dataclass
class Ordered:
    """One drawn entry: how each order fared, and its net per dollar - 0.0 for a missed order."""

    entry: p24.Entry
    early: str | None = None
    #: Amendment A-1, a diagnostic: how `DR-040` §4's own test - the first PRINT at or under the
    #: limit, not the ask - classes the entry.
    by_print: str | None = None
    how: dict[str, str] = field(default_factory=dict)
    value: dict[tuple[str, str], float] = field(default_factory=dict)
    trades: dict[str, Trade] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)

    def priced(self, arm: str, costing: str = "net") -> bool:
        return (arm, costing) in self.value


def _fixed(value: Decimal) -> Callable[[], Decimal]:
    return lambda: value


def _free(_reason: ExitReason) -> CostModel:
    return p24.cost(Decimal(0))


def first_touch_at(minutes: Sequence[Minute], limit: Decimal) -> Minute | None:
    """The first minute whose low reaches the limit - where a resting buy at `limit` fills."""
    return next((m for m in minutes if m.low <= limit), None)


def price_entry(entry: p24.Entry, series: BarSeries, atr_value: Decimal,
                minutes: tuple[Minute, ...] | None,
                windows: Mapping[str, tuple[datetime, tuple[Quote, ...]] | None],
                auctions: Mapping[str, tuple[Print, ...] | None],
                session: ExchangeSession | None, tie_break: TieBreak | None,
                counts: Counter[str]) -> Ordered:
    """Every order for one entry, each walked from its own fill, or missed."""
    got = Ordered(entry)
    if minutes is None:
        got.early = "minutes_unavailable"
        return got
    if session is None:
        got.early = "not_a_session"
        return got
    regular = regular_hours(minutes, session)
    bar = next((b for b in series.bars if b.session_date == entry.session_date), None)
    signal_bar = next((b for b in series.bars if b.session_date == entry.signal_date), None)
    if bar is None or signal_bar is None:
        got.early = "session_not_stored"
        return got
    if not regular or not reproduces(regular, bar):
        got.early = "minutes_mismatch"
        return got
    limit = signal_bar.close

    spreads: dict[str, Decimal | None] = {}
    for moment in MOMENTS:
        window = windows.get(moment)
        spreads[moment] = None if window is None else p24.half_spread_bps(window[1], window[0])

    def spread_for(moment: str) -> Decimal:
        value = spreads[moment]
        if value is None:
            raise p25._MissingExitQuote(moment)  # noqa: SLF001
        return value

    opening_cross = p25.cross_price(auctions.get(OPENING), OPENING)
    closing_cross = p25.cross_price(auctions.get(CLOSING), CLOSING)
    factor = p25.adjustment_factor(opening_cross, bar.open, closing_cross, bar.close)

    # How each order gets in: the fill price, what it pays on top, and the minutes after it.
    fills: dict[str, tuple[Decimal, Decimal, list[Minute]]] = {}

    def rest_from(arm: str, start: Minute) -> None:
        later = [m for m in regular if m.at >= start.at]
        touched = first_touch_at(later, limit)
        if touched is None:
            got.how[arm] = MISSED
        else:
            got.how[arm] = RESTED
            fills[arm] = (limit, Decimal(0), p24.after_fill(regular, touched))

    first = regular[0]
    got.by_print = (MARKETABLE if first.open <= limit
                    else RESTED if first_touch_at(regular, limit) is not None else MISSED)
    if spreads[OPEN] is None:
        got.missing[DAY] = "no_fresh_two_sided_quote"
    else:
        ask = first.open * (1 + spread_for(OPEN) / Decimal(10_000))
        if ask <= limit:
            got.how[DAY] = MARKETABLE
            fills[DAY] = (first.open, spread_for(OPEN), p24.after_fill(regular, first))
        else:
            rest_from(DAY, first)

    if opening_cross is None:
        for arm in (OPG, MOO, JOINED):
            got.missing[arm] = "no_opening_cross"
    else:
        cross = opening_cross.price / factor
        holding = p25.minute_holding(regular, opening_cross.at)
        if holding is None:
            for arm in (OPG, MOO, JOINED):
                got.missing[arm] = "cross_outside_the_minutes"
        else:
            after = p24.after_fill(regular, holding)
            got.how[MOO] = CROSSED
            fills[MOO] = (cross, Decimal(0), after)
            if cross <= limit:
                got.how[OPG] = got.how[JOINED] = CROSSED
                fills[OPG] = fills[JOINED] = (cross, Decimal(0), after)
            else:
                got.how[OPG] = MISSED
                rest_from(JOINED, holding)

    def at_moment(reason: ExitReason) -> CostModel:
        return p24.cost(spread_for(p24.EXIT_MOMENT[reason]))

    def at_the_open(_reason: ExitReason) -> CostModel:
        return p24.cost(spread_for(OPEN))

    for arm in ARMS:
        if got.how.get(arm) == MISSED:
            for costing in COSTINGS:
                got.value[(arm, costing)] = 0.0
            continue
        if arm not in fills:
            continue
        quoted, own, day = fills[arm]
        crossed = got.how[arm] == CROSSED
        plans: dict[str, tuple[Callable[[], Decimal], Callable[[ExitReason], CostModel]]] = {
            "net": (_fixed(own), at_moment),
            "gross": (_fixed(Decimal(0)), _free),
            # The stress: a crossed fill charged the close's spread as if the auction cost what
            # the continuous close does, every exit at the open's.
            "cost_adverse": ((lambda: spread_for(CLOSE)) if crossed else _fixed(own), at_the_open),
        }
        for costing, (entry_bps, exits) in plans.items():
            try:
                walked: Trade | str = p24.walk_entry(
                    entry, series.bars, atr_value, quoted, p24.cost(entry_bps()), exits, day,
                    tie_break, counts if costing == "net" else Counter(), arm)
            except p25._MissingExitQuote:  # noqa: SLF001
                walked = "exit_quote_missing"
            if isinstance(walked, str):
                got.missing.setdefault(arm, walked)
                continue
            got.value[(arm, costing)] = p24.per_dollar(walked)
            if costing == "net":
                got.trades[arm] = walked
    return got


# --- inference -------------------------------------------------------------------------------------


def _pairs(ordered: Sequence[Ordered], first: str, second: str, costing: str) -> list[Ordered]:
    return [o for o in ordered if o.priced(first, costing) and o.priced(second, costing)]


def reading(ordered: Sequence[Ordered], first: str, second: str, drawn: int, resamples: int,
            seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """`first - second` per drawn entry - a missed order counting as 0 - under each costing."""
    def clustered(costing: str, value: Callable[[Ordered], float]) -> dict[str, float]:
        by_month: dict[str, list[Decimal]] = defaultdict(list)
        for o in _pairs(ordered, first, second, costing):
            by_month[cluster_of(o.entry.session_date)].append(Decimal(str(value(o))))
        return p24._clustered(by_month, resamples, seed)  # noqa: SLF001

    def difference_under(costing: str) -> Callable[[Ordered], float]:
        return lambda o: o.value[(first, costing)] - o.value[(second, costing)]

    net = _pairs(ordered, first, second, "net")
    cell: dict[str, Any] = {
        "first": first, "second": second, "pairs": len(net), "drawn": drawn,
        "complete_share": len(net) / drawn if drawn else 0.0,
        "months": len({cluster_of(o.entry.session_date) for o in net}),
    }
    for costing in COSTINGS:
        cell["difference" if costing == "net" else costing] = clustered(
            costing, difference_under(costing))
    cell["level"] = clustered("net", lambda o: o.value[(first, "net")])
    return cell


def by_day_fill(ordered: Sequence[Ordered], first: str, second: str = DAY
                ) -> dict[str, dict[str, float]]:
    """`first - second` taken apart by how the day limit fared: each group's entries, its mean
    difference, and its share of the reading's mean. What the spread saved on the marketable entries
    and what abstaining cost or saved on the others are different claims, and one number hides both.
    """
    net = _pairs(ordered, first, second, "net")
    groups: dict[str, list[float]] = defaultdict(list)
    for o in net:
        groups[o.how.get(second, "unpriced")].append(
            o.value[(first, "net")] - o.value[(second, "net")])
    return {how: {"entries": len(values), "mean": sum(values) / len(values),
                  "contribution": sum(values) / len(net)}
            for how, values in sorted(groups.items())}


def fill_rates(ordered: Sequence[Ordered]) -> dict[str, dict[str, int]]:
    return {arm: dict(Counter(o.how[arm] for o in ordered if arm in o.how).most_common())
            for arm in ARMS}


def branch_for(cell: Mapping[str, Any]) -> str:
    return p24.branch_for(cell)


def repeats_prior_studies(ordered: Sequence[Ordered],
                          sources: Sequence[tuple[str, str, Path, str]] = REPRODUCES
                          ) -> dict[str, dict[str, int]]:
    """Each order against the prior study's QA rows it repeats; a difference is a defect."""
    index = {(o.entry.instrument_id, o.entry.session_date.isoformat()): o for o in ordered}
    out: dict[str, dict[str, int]] = {}
    for arm, how, path, theirs in sources:
        tally = Counter({"checked": 0, "differ": 0, "not_priced": 0, "other_fill": 0})
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row["arm"] != theirs:
                        continue
                    o = index.get((row["instrument_id"], row["session_date"]))
                    if o is None or arm not in o.trades:
                        tally["not_priced"] += 1
                        continue
                    if o.how.get(arm) != how:
                        tally["other_fill"] += 1
                        continue
                    tally["checked"] += 1
                    trade = o.trades[arm]
                    if (str(trade.exit_date) != row["exit_date"]
                            or trade.exit_reason.value != row["exit_reason"]
                            or abs(o.value[(arm, "net")] - float(row["per_dollar"])) > 1e-6):
                        tally["differ"] += 1
        out[arm] = dict(tally)
    return out


# --- the run ----------------------------------------------------------------------------------------


def price_sample(args: argparse.Namespace, entries: Sequence[p24.Entry]
                 ) -> tuple[list[Ordered], Counter[str], Counter[str], dict[str, str]]:
    bars = BarStore(args.data / "bars.duckdb")
    as_of = p24.read_instant(args.as_of, bars.latest_knowledge_time())
    far = datetime.max.replace(tzinfo=as_of.tzinfo)
    minutes_store = MinuteStore(args.minutes)
    quotes_store = QuoteStore(args.quotes)
    auction_store = AuctionStore(args.auctions)
    minutes_as_of = p24.read_instant(args.minutes_as_of, far)
    quotes_as_of = p24.read_instant(args.quotes_as_of, far)
    auctions_as_of = p24.read_instant(args.auctions_as_of, far)
    tie_break: TieBreak = MinuteTieBreak(minutes_store, minutes_as_of)
    registry = atr_registry()
    ordered: list[Ordered] = []
    before: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    by_name: dict[str, list[p24.Entry]] = defaultdict(list)
    for entry in entries:
        by_name[entry.instrument_id].append(entry)
    for count, name in enumerate(sorted(by_name), start=1):
        series = bars.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series is None or not series.bars:
            before["series_unavailable"] += len(by_name[name])
            continue
        atr_series = atr_component.compute(series, registry)
        for entry in by_name[name]:
            atr_value = p24.atr_at(atr_series, series, entry.signal_date)
            if atr_value is None:
                before["no_atr"] += 1
                continue
            windows = {m: quotes_store.window(name, entry.session_date, m, quotes_as_of)
                       for m in MOMENTS}
            auctions = {side: auction_store.window(name, entry.session_date, side, auctions_as_of)
                        for side in (OPENING, CLOSING)}
            ordered.append(price_entry(entry, series, atr_value,
                                       minutes_store.session(name, entry.session_date,
                                                             minutes_as_of),
                                       windows, auctions, session_for(name, entry.session_date),
                                       tie_break, counts))
        if count % 400 == 0:
            print(f"  priced {count}/{len(by_name)} instruments", flush=True)
    bars.close()
    minutes_store.close()
    quotes_store.close()
    auction_store.close()
    return ordered, before, counts, {"bars": as_of.isoformat(), "minutes": minutes_as_of.isoformat(),
                                     "quotes": quotes_as_of.isoformat(),
                                     "auctions": auctions_as_of.isoformat()}


def build(args: argparse.Namespace) -> dict[str, Any]:
    entries = p24.read_sample(args.sample)
    ordered, before, counts, instants = price_sample(args, entries)
    registered = args.resamples == p24.BOOTSTRAP_RESAMPLES
    cells = {name: reading(ordered, first, second, len(entries), args.resamples)
             for name, (first, second) in READINGS.items()}
    branch = branch_for(cells["G-D"]) if registered else "SMOKE"
    sessions = sorted(o.entry.session_date for o in _pairs(ordered, *PRIMARY, "net"))
    span = ((sessions[-1] - sessions[0]).days / 365.25) if sessions else 0.0
    excluded = Counter(before)
    excluded.update(o.early for o in ordered if o.early)
    payload: dict[str, Any] = {
        "prereg": "PR-030",
        "trials": 3,
        "verdict": p24.TOKEN[branch] if registered else "smoke",
        "branch": branch,
        "country": "USA",
        "as_of": instants,
        "measured_span": {"first_session": sessions[0].isoformat() if sessions else None,
                          "last_session": sessions[-1].isoformat() if sessions else None,
                          "years": round(span, 2)},
        "split": {"registered": "none - PR-024's draw, four orders paired within each entry",
                  "buys": "nothing a split could buy: four routings of one decision, none tuned"},
        "perturbations": {"registered": ["cost_adverse", "gross"],
                          "run": ["cost_adverse", "gross"]},
        "registered_settings": {
            "sample": "PR-024-sample.jsonl", "primary": "G-D", "limit": "the signal session's close",
            "bootstrap": {"unit": "entry month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                          "resamples": args.resamples},
            "unit": "net per dollar per DRAWN entry; a missed order is 0",
            "power_floor": p24.POWER_FLOOR, "min_complete_share": p24.MIN_COMPLETE_SHARE,
            "min_pairs": p24.MIN_PAIRS, "min_months": p24.MIN_MONTHS,
        },
        "sample": {"drawn": len(entries), "excluded_before_any_order": dict(excluded.most_common())},
        "fills": fill_rates(ordered),
        "fills_by_print": dict(Counter(o.by_print for o in ordered if o.by_print).most_common()),
        "missing_by_arm": {arm: dict(Counter(o.missing[arm] for o in ordered
                                             if arm in o.missing).most_common())
                           for arm in ARMS},
        "tie_breaks": dict(counts.most_common()),
        "reproduces": repeats_prior_studies(ordered),
        "by_day_fill": {name: by_day_fill(ordered, first, second)
                        for name, (first, second) in READINGS.items()},
        "cells": cells,
    }
    if registered:
        write_qa(ordered)
    return payload


def write_qa(ordered: Sequence[Ordered], path: Path = QA_SAMPLE) -> None:
    rng = random.Random(BOOTSTRAP_SEED)
    usable = _pairs(ordered, *PRIMARY, "net")
    chosen = sorted(rng.sample(usable, min(QA_ROWS, len(usable))),
                    key=lambda o: (o.entry.session_date, o.entry.instrument_id))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["instrument_id", "signal_date", "session_date", "order", "how",
                         "entry_price", "exit_date", "exit_reason", "per_dollar"])
        for o in chosen:
            for arm in ARMS:
                if not o.priced(arm):
                    continue
                t = o.trades.get(arm)
                writer.writerow([o.entry.instrument_id, o.entry.signal_date, o.entry.session_date,
                                 arm, o.how.get(arm), t.entry_price if t else "",
                                 t.exit_date if t else "", t.exit_reason.value if t else "",
                                 round(o.value[(arm, "net")], 6)])


def power(args: argparse.Namespace) -> dict[str, Any]:
    """Each reading's end-to-end WIDTH on the registered sample, and nothing else.

    The verdict estimator's own interval, run before registration - `PR-021`..`PR-023`'s precedent -
    under `power_pr019.assert_no_effect_leaked`: no estimate, no bound, no fill rate leaves it.
    """
    from power_pr019 import assert_no_effect_leaked

    entries = p24.read_sample(args.sample)
    ordered, _, _, instants = price_sample(args, entries)
    widths = {name: round(reading(ordered, first, second, len(entries),
                                  POWER_RESAMPLES)["difference"]["width"], 6)
              for name, (first, second) in READINGS.items()}
    payload = {"for": "PR-030", "as_of": instants, "resamples": POWER_RESAMPLES,
               "widths": widths, "power_floor_width": p24.POWER_FLOOR}
    assert_no_effect_leaked(payload)
    return payload


def _fmt(cell: Mapping[str, float], scale: float = 100.0) -> str:
    if math.isnan(cell.get("estimate", math.nan)):
        return "n/a"
    return (f"{cell['estimate'] * scale:+.3f} [{cell['lo'] * scale:+.3f}, "
            f"{cell['hi'] * scale:+.3f}]")


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-030   verdict {payload['verdict']}   branch {payload['branch']}")
    print(f"  drawn {payload['sample']['drawn']}   excluded {payload['sample']['excluded_before_any_order']}")
    for arm, how in payload["fills"].items():
        print(f"  {arm} fills {how}")
    print(f"  D by DR-040's print test {payload.get('fills_by_print')}")
    print(f"  reproduces {payload['reproduces']}")
    for name, cell in payload["cells"].items():
        print(f"  {name}   pairs {cell['pairs']}   months {cell['months']}   "
              f"complete {cell['complete_share']:.1%}")
        print(f"    per drawn entry (%)     {_fmt(cell['difference'])}")
        print(f"    gross (%)               {_fmt(cell['gross'])}")
        print(f"    cost-adverse (%)        {_fmt(cell['cost_adverse'])}")
        print(f"    first order's own (%)   {_fmt(cell['level'])}")
        for how, part in payload["by_day_fill"][name].items():
            print(f"      D {how:<10} {part['entries']:>5} entries   mean {part['mean']:+.4%}   "
                  f"share of the reading {part['contribution']:+.4%}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb")
    parser.add_argument("--minutes", type=Path, help="the minute store")
    parser.add_argument("--quotes", type=Path, help="the quote store")
    parser.add_argument("--auctions", type=Path, help="the auction store")
    parser.add_argument("--sample", type=Path, default=p24.SAMPLE, help="PR-024's drawn entries")
    parser.add_argument("--as-of", help="the bar store's knowledge instant (default: latest)")
    parser.add_argument("--minutes-as-of", help="the minute store's knowledge instant")
    parser.add_argument("--quotes-as-of", help="the quote store's knowledge instant")
    parser.add_argument("--auctions-as-of", help="the auction store's knowledge instant")
    parser.add_argument("--resamples", type=int, default=p24.BOOTSTRAP_RESAMPLES,
                        help="bootstrap resamples; anything but the registered 10000 is a smoke run")
    parser.add_argument("--report", action="store_true", help="print the stored result")
    parser.add_argument("--power", action="store_true",
                        help="write each reading's interval width only, before registration")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if None in (args.data, args.minutes, args.quotes, args.auctions):
        parser.error("--data, --minutes, --quotes and --auctions are required")
    if args.power:
        estimate = power(args)
        POWER.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
        print(f"PR-030 power: widths {estimate['widths']}")
        return 0
    payload = build(args)
    if payload["verdict"] != "smoke":
        RESULT.write_text(json.dumps(payload, indent=2, default=p24._default) + "\n",  # noqa: SLF001
                          encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
