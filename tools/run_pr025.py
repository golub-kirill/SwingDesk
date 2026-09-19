"""`PR-025` - does an entry that joins the opening auction earn what the 15:55 entry earns?

**What is already known.** `PR-024` bought `CARD-001`'s entries at the 09:30 open and at 15:55,
each paying its own quoted half-spread, and the close won by +0.311% a trade - all of it the spread,
37.8 bps a side at the open against 5.0. It priced the open as an order meeting the continuous book
seconds after 09:30. **An order in the opening auction pays the cross's single price and no quoted
spread**, and moving an order into the auction is a change of routing - Alpaca's `opg` - where moving
it to 15:55 needs a pass during the session that does not exist. This asks which the saving is.

**Four arms, one entry.** Signal on session T, entry on T+1:

* `A` - the listing market's opening cross, no spread. **The verdict reads `A - C`**;
* `C` - 15:55 as `PR-024` priced it: the minute's open plus that moment's own half-spread;
* `X` - the closing cross of the entry session, no spread. Counted, reported as `X - C`, never read;
* `O` - `PR-024`'s open. Not a new configuration; `A - O` says what the auction itself saves.

**The cross is read from the tape** (`tools/fetch_auction_prints.py`, `market_data.auctions`): the
largest print carrying the cross's condition, `O` or `6`, earliest on a tie (`cross_price`).

**The walk is `PR-024`'s, unchanged** (`run_pr024.walk_entry`, which `--parity` proved is the
engine). `A` reads its entry session from the minute holding the cross; `X` has nothing after its
fill, so its entry session cannot exit - the single print at the close is all it sees.

**Each reading is priced on the entries IT needs.** `PR-024` dropped an entry from its verdict when
an unread arm or a perturbation failed (`TODO` §5, measured by `attribute_pr024.py`); here a pair is
in a reading when both of its arms are priced under that reading's costing, and nothing else.

    PYTHONPATH=$PWD/src python tools/run_pr025.py --data <store> --minutes <m> --quotes <q> \
        --auctions <a> --list-ambiguous
    PYTHONPATH=$PWD/src python tools/run_pr025.py --data <store> --minutes <m> --quotes <q> \
        --auctions <a> --as-of <t> --minutes-as-of <t> --quotes-as-of <t> --auctions-as-of <t> \
        --resamples 10000
    python tools/run_pr025.py --report
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
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr024 as base
from run_pr016 import BLOCK, atr_registry, cluster_of
from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
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
    Touch,
    regular_hours,
    reproduces,
    session_for,
)

# --- the arms ---------------------------------------------------------------------------------------

OPEN_ARM, AUCTION, LATE, CLOSING_ARM = "O", "A", "C", "X"
ARMS = (OPEN_ARM, AUCTION, LATE, CLOSING_ARM)

#: Each reading is a pair, first minus second. The verdict is the first.
PRIMARY = (AUCTION, LATE)
READINGS: dict[str, tuple[str, str]] = {"A-C": PRIMARY, "X-C": (CLOSING_ARM, LATE),
                                        "A-O": (AUCTION, OPEN_ARM)}

#: The condition the listing market's cross carries.
CROSS_FLAG = {OPENING: "O", CLOSING: "6"}

MOMENTS = (OPEN, ELEVEN, CLOSE)

#: The registered cost stress, read by section 6 on an ACCEPT: an auction arm charged the 15:55
#: half-spread, as if its fill cost what the continuous close costs; `O` and `C` at their own; every
#: exit at its own session's opening spread, `PR-024`'s exit stress.
COSTINGS = ("net", "gross", "cost_adverse", "exits_at_registry", "anchored_stop")

BOOTSTRAP_SEED = 20260919
RESULTS = base.RESULTS
RESULT = RESULTS / "PR-025.json"
AMBIGUOUS = RESULTS / "PR-025-ambiguous-bars.jsonl"
QA_SAMPLE = RESULTS / "PR-025-qa-sample.csv"
PR024_QA = RESULTS / "PR-024-qa-sample.csv"
QA_ROWS = 400

#: Two prices are the same print when they differ by no more than half a cent. The stored daily bars
#: carry a float's tail - 103.769997 for a cross at 103.77 - and an exact comparison would count
#: every one of those as a miss.
SAME_PRINT = Decimal("0.005")


def cross_price(prints: Sequence[Print] | None, side: str) -> Print | None:
    """The auction's own print: the largest carrying the cross's condition, earliest on a tie.

    Every market center stamps its own official open and close, and another venue can print a
    flagged trade before the listing market's cross; the cross is the one that clears the size.
    """
    flagged = [p for p in prints or () if CROSS_FLAG[side] in p.conditions]
    if not flagged:
        return None
    return min(flagged, key=lambda p: (-p.size, p.at))


def minute_holding(regular: Sequence[Minute], at: datetime) -> Minute | None:
    """The regular-hours minute an instant falls in - the auction arm's entry session starts there."""
    for minute in regular:
        if minute.at <= at < minute.at + timedelta(minutes=1):
            return minute
    return None


@dataclass
class Priced:
    """One entry: each arm's trade under each costing, or why not, and what it paid."""

    entry: base.Entry
    early: str | None = None
    trades: dict[str, dict[str, Trade | str]] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)
    paid: dict[str, Decimal] = field(default_factory=dict)
    crosses: dict[str, Print] = field(default_factory=dict)
    bar: Bar | None = None
    first_minute_open: Decimal | None = None

    def priced(self, arm: str, costing: str) -> bool:
        return isinstance(self.trades.get(arm, {}).get(costing), Trade)

    def trade(self, arm: str, costing: str = "net") -> Trade:
        got = self.trades[arm][costing]
        assert isinstance(got, Trade)
        return got


class _MissingExitQuote(Exception):
    pass


def _fixed(value: Decimal) -> Callable[[], Decimal]:
    return lambda: value


def _flat(bps: Decimal) -> Callable[[ExitReason], CostModel]:
    return lambda _reason: base.cost(bps)


def price_entry(entry: base.Entry, series: BarSeries, atr_value: Decimal,
                minutes: tuple[Minute, ...] | None,
                windows: Mapping[str, tuple[datetime, tuple[Quote, ...]] | None],
                auctions: Mapping[str, tuple[Print, ...] | None],
                session: ExchangeSession | None, tie_break: TieBreak | None,
                counts: Counter[str]) -> Priced:
    """Every arm and costing whose own inputs exist, each failure kept against its arm."""
    got = Priced(entry)
    if minutes is None:
        got.early = "minutes_unavailable"
        return got
    if session is None:
        got.early = "not_a_session"
        return got
    regular = regular_hours(minutes, session)
    bar = next((b for b in series.bars if b.session_date == entry.session_date), None)
    if bar is None:
        got.early = "entry_session_not_stored"
        return got
    if not reproduces(regular, bar):
        got.early = "minutes_mismatch"
        return got
    signal_bar = next((b for b in series.bars if b.session_date == entry.signal_date), None)
    if signal_bar is None:
        got.early = "signal_session_not_stored"
        return got
    got.bar = bar
    got.first_minute_open = regular[0].open if regular else None

    spreads: dict[str, Decimal | None] = {}
    for moment in MOMENTS:
        window = windows.get(moment)
        spreads[moment] = None if window is None else base.half_spread_bps(window[1], window[0])

    def spread_for(moment: str) -> Decimal:
        value = spreads[moment]
        if value is None:
            raise _MissingExitQuote(moment)
        return value

    def at_moment(reason: ExitReason) -> CostModel:
        return base.cost(spread_for(base.EXIT_MOMENT[reason]))

    # What each arm fills at, what it pays to enter, and what its entry session shows after.
    fills: dict[str, tuple[Decimal, Decimal, list[Minute]]] = {}
    for arm, moment in ((OPEN_ARM, OPEN), (LATE, CLOSE)):
        minute = base.fill_minute(regular, base.fill_instant(session, moment))
        if minute is None:
            got.missing[arm] = "no_print_at_the_moment"
        elif spreads[moment] is None:
            got.missing[arm] = "no_fresh_two_sided_quote"
        else:
            fills[arm] = (minute.open, spread_for(moment), base.after_fill(regular, minute))
    opening = auctions.get(OPENING)
    closing = auctions.get(CLOSING)
    cross = cross_price(opening, OPENING)
    if opening is None:
        got.missing[AUCTION] = "auction_not_fetched"
    elif cross is None:
        got.missing[AUCTION] = "no_opening_cross"
    else:
        holding = minute_holding(regular, cross.at)
        if holding is None:
            got.missing[AUCTION] = "cross_outside_the_minutes"
        else:
            got.crosses[AUCTION] = cross
            fills[AUCTION] = (cross.price, Decimal(0), base.after_fill(regular, holding))
    close_cross = cross_price(closing, CLOSING)
    if closing is None:
        got.missing[CLOSING_ARM] = "auction_not_fetched"
    elif close_cross is None:
        got.missing[CLOSING_ARM] = "no_closing_cross"
    else:
        got.crosses[CLOSING_ARM] = close_cross
        price = close_cross.price
        fills[CLOSING_ARM] = (price, Decimal(0), [Minute(at=session.close_time, open=price,
                                                         high=price, low=price, close=price)])

    def at_the_open(_reason: ExitReason) -> CostModel:
        return base.cost(spread_for(OPEN))

    for arm, (quoted, own, day) in fills.items():
        got.paid[arm] = own
        adverse = (lambda: spread_for(CLOSE)) if arm in (AUCTION, CLOSING_ARM) else _fixed(own)
        plans: dict[str, tuple[Callable[[], Decimal], Callable[[ExitReason], CostModel],
                               Decimal | None]] = {
            "net": (_fixed(own), at_moment, None),
            "gross": (_fixed(Decimal(0)), _flat(Decimal(0)), None),
            "cost_adverse": (adverse, at_the_open, None),
            "exits_at_registry": (_fixed(own), _flat(base.REGISTRY_EXIT_BPS), None),
            "anchored_stop": (_fixed(own), at_moment, signal_bar.close),
        }
        got.trades[arm] = {}
        for costing, (entry_bps, exits, anchor) in plans.items():
            try:
                walked: Trade | str = base.walk_entry(
                    entry, series.bars, atr_value, quoted, base.cost(entry_bps()), exits, day,
                    tie_break, counts if costing == "net" else Counter(), arm, anchor=anchor)
            except _MissingExitQuote:
                walked = "exit_quote_missing"
            got.trades[arm][costing] = walked
    return got


# --- inference ----------------------------------------------------------------------------------------


def _difference(p: Priced, first: str, second: str, costing: str = "net") -> float:
    return base.per_dollar(p.trade(first, costing)) - base.per_dollar(p.trade(second, costing))


def _pairs(priced: Sequence[Priced], first: str, second: str, costing: str) -> list[Priced]:
    return [p for p in priced if p.priced(first, costing) and p.priced(second, costing)]


def reading(priced: Sequence[Priced], first: str, second: str, drawn: int, resamples: int,
            seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """`first - second` per entry, each costing on the entries priced under it, and its own level."""
    def clustered(costing: str, value: Callable[[Priced], float]) -> dict[str, float]:
        by_month: dict[str, list[Decimal]] = defaultdict(list)
        for p in _pairs(priced, first, second, costing):
            by_month[cluster_of(p.entry.session_date)].append(Decimal(str(value(p))))
        return base._clustered(by_month, resamples, seed)  # noqa: SLF001

    net = _pairs(priced, first, second, "net")
    by_date: dict[Any, list[Decimal]] = defaultdict(list)
    by_instrument: dict[str, list[Decimal]] = defaultdict(list)
    for p in net:
        value = Decimal(str(_difference(p, first, second)))
        by_date[p.entry.session_date].append(value)
        by_instrument[p.entry.instrument_id].append(value)
    date_months: dict[str, list[Decimal]] = defaultdict(list)
    for day, values in by_date.items():
        date_months[cluster_of(day)].append(sum(values, Decimal(0)) / len(values))

    def difference_under(costing: str) -> Callable[[Priced], float]:
        return lambda p: _difference(p, first, second, costing)

    def in_r(p: Priced) -> float:
        return float(p.trade(first).net_r - p.trade(second).net_r)

    def own_level(p: Priced) -> float:
        return base.per_dollar(p.trade(first))

    readings = {costing: clustered(costing, difference_under(costing)) for costing in COSTINGS}
    return {
        "first": first, "second": second,
        "pairs": len(net), "drawn": drawn,
        "complete_share": len(net) / drawn if drawn else 0.0,
        "months": len({cluster_of(p.entry.session_date) for p in net}),
        "difference": readings["net"],
        "difference_r": clustered("net", in_r),
        "gross_part": readings["gross"],
        "cost_adverse": readings["cost_adverse"],
        "exits_at_registry": readings["exits_at_registry"],
        "anchored_stop": readings["anchored_stop"],
        "date_weighted": base._clustered(date_months, resamples, seed),  # noqa: SLF001
        "instrument_clustered": base._instrument_interval(by_instrument, resamples, seed),  # noqa: SLF001
        "level": clustered("net", own_level),
    }


def branch_for(cell: Mapping[str, Any]) -> str:
    """Section 6, in `PR-024`'s order, on the verdict's own reading."""
    return base.branch_for(cell)


# --- diagnostics --------------------------------------------------------------------------------------


def _summary(values: Sequence[float]) -> dict[str, float | int]:
    return base._spread_summary(values)  # noqa: SLF001


def crosses_against_the_bar(priced: Sequence[Priced]) -> dict[str, Any]:
    """How often the tape's cross is the stored bar's open or close, and the late opens."""
    opens = [p for p in priced if AUCTION in p.crosses and p.bar is not None]
    closes = [p for p in priced if CLOSING_ARM in p.crosses and p.bar is not None]

    def gap(price: Decimal, other: Decimal | None) -> float | None:
        if other is None or other == 0:
            return None
        return 0.0 if abs(price - other) <= SAME_PRINT else float(abs(price - other) / other)

    open_gaps = [g for p in opens
                 if (g := gap(p.crosses[AUCTION].price, p.bar.open if p.bar else None)) is not None]
    minute_gaps = [g for p in opens
                   if (g := gap(p.crosses[AUCTION].price, p.first_minute_open)) is not None]
    close_gaps = [g for p in closes
                  if (g := gap(p.crosses[CLOSING_ARM].price, p.bar.close if p.bar else None))
                  is not None]
    late: Counter[str] = Counter()
    for p in opens:
        session = session_for(p.entry.instrument_id, p.entry.session_date)
        if session is None:
            continue
        delay = (p.crosses[AUCTION].at - session.open_time).total_seconds()
        late["within 5 s" if delay < 5 else "within a minute" if delay < 60
             else "later than a minute"] += 1
    return {
        "opening_crosses": len(opens),
        "opening_equals_bar_open": sum(g == 0 for g in open_gaps),
        "opening_equals_first_minute_open": sum(g == 0 for g in minute_gaps),
        "opening_gap_to_bar_open": _summary(open_gaps),
        "opening_delay": dict(late),
        "closing_crosses": len(closes),
        "closing_equals_bar_close": sum(g == 0 for g in close_gaps),
        "closing_gap_to_bar_close": _summary(close_gaps),
    }


def diagnostics(priced: Sequence[Priced]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ARMS:
        net = [p for p in priced if p.priced(arm, "net")]
        out[arm] = {
            "priced": len(net),
            "exit_reasons": dict(Counter(p.trade(arm).exit_reason.value for p in net).most_common()),
            "exited_on_the_entry_session": sum(p.trade(arm).exit_date == p.entry.session_date
                                               for p in net),
            "entry_half_spread_bps": _summary([float(p.paid[arm]) for p in net]),
        }
    return out


def exclusions(priced: Sequence[Priced], before: Counter[str]) -> dict[str, dict[str, int]]:
    """Why each arm went unpriced: entry-level reasons, its own missing input, or its net walk."""
    out: dict[str, Counter[str]] = {arm: Counter(before) for arm in ARMS}
    for p in priced:
        for arm in ARMS:
            if p.early:
                out[arm][p.early] += 1
            elif arm in p.missing:
                out[arm][p.missing[arm]] += 1
            elif not p.priced(arm, "net"):
                out[arm][str(p.trades[arm]["net"])] += 1
    return {arm: dict(counts.most_common()) for arm, counts in out.items()}


def reproduces_pr024(priced: Sequence[Priced], path: Path = PR024_QA) -> dict[str, int]:
    """`O` and `C` are `PR-024`'s arms: every QA row it kept must come back to the digit."""
    if not path.exists():
        return {"checked": 0, "differ": 0, "not_priced": 0}
    index = {(p.entry.instrument_id, p.entry.session_date.isoformat()): p for p in priced}
    checked = differ = missing = 0
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["arm"] not in (OPEN_ARM, LATE):
                continue
            p = index.get((row["instrument_id"], row["session_date"]))
            if p is None or not p.priced(row["arm"], "net"):
                missing += 1
                continue
            checked += 1
            trade = p.trade(row["arm"])
            if (str(trade.exit_date) != row["exit_date"] or trade.exit_reason.value != row["exit_reason"]
                    or abs(base.per_dollar(trade) - float(row["per_dollar"])) > 1e-6):
                differ += 1
    return {"checked": checked, "differ": differ, "not_priced": missing}


# --- the run ----------------------------------------------------------------------------------------------


def price_sample(args: argparse.Namespace, entries: Sequence[base.Entry],
                 collect_ambiguous: bool = False
                 ) -> tuple[list[Priced], Counter[str], Counter[str], list[dict[str, str]],
                            dict[str, str]]:
    bars = BarStore(args.data / "bars.duckdb")
    as_of = base.read_instant(args.as_of, bars.latest_knowledge_time())
    far = datetime.max.replace(tzinfo=as_of.tzinfo)
    minutes_store = MinuteStore(args.minutes)
    quotes_store = QuoteStore(args.quotes)
    auction_store = AuctionStore(args.auctions)
    minutes_as_of = base.read_instant(args.minutes_as_of, far)
    quotes_as_of = base.read_instant(args.quotes_as_of, far)
    auctions_as_of = base.read_instant(args.auctions_as_of, far)
    registry = atr_registry()
    recorded: list[dict[str, str]] = []

    def recording(instrument_id: str, bar: Any, _stop: Decimal, _target: Decimal) -> Touch:
        recorded.append({"instrument_id": instrument_id,
                         "session_date": bar.session_date.isoformat()})
        return Touch.UNAVAILABLE

    tie_break: TieBreak = (recording if collect_ambiguous
                           else MinuteTieBreak(minutes_store, minutes_as_of))
    priced: list[Priced] = []
    before: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    by_name: dict[str, list[base.Entry]] = defaultdict(list)
    for entry in entries:
        by_name[entry.instrument_id].append(entry)
    for count, name in enumerate(sorted(by_name), start=1):
        series = bars.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series is None or not series.bars:
            before["series_unavailable"] += len(by_name[name])
            continue
        atr_series = atr_component.compute(series, registry)
        for entry in by_name[name]:
            atr_value = base.atr_at(atr_series, series, entry.signal_date)
            if atr_value is None:
                before["no_atr"] += 1
                continue
            windows = {m: quotes_store.window(name, entry.session_date, m, quotes_as_of)
                       for m in MOMENTS}
            auctions = {side: auction_store.window(name, entry.session_date, side, auctions_as_of)
                        for side in (OPENING, CLOSING)}
            priced.append(price_entry(entry, series, atr_value,
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
    instants = {"bars": as_of.isoformat(), "minutes": minutes_as_of.isoformat(),
                "quotes": quotes_as_of.isoformat(), "auctions": auctions_as_of.isoformat()}
    return priced, before, counts, recorded, instants


def build(args: argparse.Namespace) -> dict[str, Any]:
    entries = base.read_sample(args.sample)
    priced, before, counts, _, instants = price_sample(args, entries)
    registered = args.resamples == base.BOOTSTRAP_RESAMPLES
    cells = {name: reading(priced, first, second, len(entries), args.resamples)
             for name, (first, second) in READINGS.items()}
    branch = branch_for(cells["A-C"]) if registered else "SMOKE"
    sessions = sorted(p.entry.session_date for p in _pairs(priced, *PRIMARY, "net"))
    span = ((sessions[-1] - sessions[0]).days / 365.25) if sessions else 0.0
    payload: dict[str, Any] = {
        "prereg": "PR-025",
        "trials": 2,
        "verdict": base.TOKEN[branch] if registered else "smoke",
        "branch": branch,
        "country": "USA",
        "as_of": instants,
        "measured_span": {
            "first_session": sessions[0].isoformat() if sessions else None,
            "last_session": sessions[-1].isoformat() if sessions else None,
            "years": round(span, 2),
        },
        "split": {
            "registered": "none - PR-024's draw, the arms paired within each entry",
            "buys": ("nothing a split could buy: two routings of one decision on one session, "
                     "nothing tuned. Pairing removes the market's level, and PR-016's own split "
                     "already tested the rule the entries come from"),
        },
        "perturbations": {
            "registered": ["cost_adverse", "exits_at_registry", "anchored_stop",
                           "instrument_clustered", "date_weighted"],
            "run": ["cost_adverse", "exits_at_registry", "anchored_stop", "instrument_clustered",
                    "date_weighted"],
        },
        "registered_settings": {
            "sample": "PR-024-sample.jsonl", "primary": "A-C",
            "bootstrap": {"unit": "entry month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                          "resamples": args.resamples},
            "power_floor": base.POWER_FLOOR, "min_complete_share": base.MIN_COMPLETE_SHARE,
            "min_pairs": base.MIN_PAIRS, "min_months": base.MIN_MONTHS,
            "cross": {"opening": "the largest print flagged O", "closing": "the largest flagged 6"},
            "cost_adverse": "auction arms at the 15:55 half-spread; exits at the opening spread",
            "registry_exit_bps": str(base.REGISTRY_EXIT_BPS),
        },
        "sample": {"drawn": len(entries), "priced_by_arm": {
            arm: sum(p.priced(arm, "net") for p in priced) for arm in ARMS}},
        "excluded_by_arm": exclusions(priced, before),
        "tie_breaks": dict(counts.most_common()),
        "crosses": crosses_against_the_bar(priced),
        "reproduces_pr024": reproduces_pr024(priced),
        "diagnostics": diagnostics(priced),
        "cells": cells,
    }
    if registered:
        write_qa(priced)
    return payload


def write_qa(priced: Sequence[Priced], path: Path = QA_SAMPLE) -> None:
    """A seeded sample, every arm of each drawn entry side by side (`BACKTEST_PROTOCOL` §7)."""
    rng = random.Random(BOOTSTRAP_SEED)
    usable = _pairs(priced, *PRIMARY, "net")
    chosen = sorted(rng.sample(usable, min(QA_ROWS, len(usable))),
                    key=lambda p: (p.entry.session_date, p.entry.instrument_id))
    columns = ["instrument_id", "signal_date", "session_date", "arm", "paid_bps", "entry_price",
               "stop_price", "exit_date", "exit_price", "exit_reason", "shares", "net_r",
               "per_dollar"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for p in chosen:
            for arm in ARMS:
                if not p.priced(arm, "net"):
                    continue
                t = p.trade(arm)
                writer.writerow([p.entry.instrument_id, p.entry.signal_date, p.entry.session_date,
                                 arm, p.paid[arm], t.entry_price, t.stop_price, t.exit_date,
                                 t.exit_price, t.exit_reason.value, t.shares, t.net_r,
                                 round(base.per_dollar(t), 6)])


def run_list_ambiguous(args: argparse.Namespace) -> int:
    """The later sessions every arm's walk would ask the tie-break about - identifiers only."""
    _, _, _, recorded, _ = price_sample(args, base.read_sample(args.sample), collect_ambiguous=True)
    unique = sorted({(r["instrument_id"], r["session_date"]) for r in recorded})
    with AMBIGUOUS.open("w", encoding="utf-8") as handle:
        for name, day in unique:
            handle.write(json.dumps({"instrument_id": name, "session_date": day}) + "\n")
    print(f"wrote {len(unique)} ambiguous sessions to {AMBIGUOUS.name}")
    return 0


def _fmt(cell: Mapping[str, float], scale: float = 100.0) -> str:
    if cell is None or math.isnan(cell.get("estimate", math.nan)):
        return "n/a"
    return (f"{cell['estimate'] * scale:+.3f} [{cell['lo'] * scale:+.3f}, "
            f"{cell['hi'] * scale:+.3f}]")


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-025   verdict {payload['verdict']}   branch {payload['branch']}")
    print(f"  drawn {payload['sample']['drawn']}   priced by arm {payload['sample']['priced_by_arm']}")
    print(f"  reproduces PR-024 {payload['reproduces_pr024']}")
    print(f"  crosses {payload['crosses']}")
    for name, cell in payload["cells"].items():
        print(f"  {name}   pairs {cell['pairs']}   months {cell['months']}   "
              f"complete {cell['complete_share']:.1%}")
        print(f"    net per dollar (%)          {_fmt(cell['difference'])}")
        print(f"    gross part (%)              {_fmt(cell['gross_part'])}")
        print(f"    net in R                    {_fmt(cell['difference_r'], 1.0)}")
        print(f"    cost-adverse (%)            {_fmt(cell['cost_adverse'])}")
        print(f"    exits at registry (%)       {_fmt(cell['exits_at_registry'])}")
        print(f"    stops from the decision (%) {_fmt(cell['anchored_stop'])}")
        print(f"    date-weighted (%)           {_fmt(cell['date_weighted'])}")
        print(f"    instrument-clustered (%)    {_fmt(cell['instrument_clustered'])}")
        print(f"    first arm's own level (%)   {_fmt(cell['level'])}")
    for arm, seen in payload["diagnostics"].items():
        spread = seen["entry_half_spread_bps"]
        typical = (f"p10 {spread['p10']:.2f}  p50 {spread['p50']:.2f}  p90 {spread['p90']:.2f}"
                   if spread.get("entries") else "none priced")
        print(f"  {arm} priced {seen['priced']}   exits {seen['exit_reasons']}   same day "
              f"{seen['exited_on_the_entry_session']}   paid bps {typical}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb")
    parser.add_argument("--minutes", type=Path, help="the minute store")
    parser.add_argument("--quotes", type=Path, help="the quote store")
    parser.add_argument("--auctions", type=Path, help="the auction store")
    parser.add_argument("--sample", type=Path, default=base.SAMPLE, help="PR-024's drawn entries")
    parser.add_argument("--as-of", help="the bar store's knowledge instant (default: latest)")
    parser.add_argument("--minutes-as-of", help="the minute store's knowledge instant")
    parser.add_argument("--quotes-as-of", help="the quote store's knowledge instant")
    parser.add_argument("--auctions-as-of", help="the auction store's knowledge instant")
    parser.add_argument("--resamples", type=int, default=base.BOOTSTRAP_RESAMPLES,
                        help="bootstrap resamples; anything but the registered 10000 is a smoke run")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list-ambiguous", action="store_true",
                      help="write the later sessions the tie-break needs, then stop")
    mode.add_argument("--report", action="store_true", help="print the stored result")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if None in (args.data, args.minutes, args.quotes, args.auctions):
        parser.error("--data, --minutes, --quotes and --auctions are required")
    if args.list_ambiguous:
        return run_list_ambiguous(args)
    payload = build(args)
    if payload["verdict"] != "smoke":
        RESULT.write_text(json.dumps(payload, indent=2, default=base._default) + "\n",  # noqa: SLF001
                          encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
