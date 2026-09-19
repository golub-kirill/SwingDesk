"""`PR-024`, after the run: what dropped each entry, and is the answer the whole book or a few names?

**EXPLORATORY, and it says so in its payload.** Section 6 read `run_pr024.build`, and nothing here
changes that verdict. What this reads was chosen after the result was seen:

* **what excluded each entry, by arm and by costing.** `run_pr024.price_entry` stops at the first
  failure of ANY arm or costing, so an entry whose anchored-stop perturbation cannot be walked, or
  whose 11:00 arm - counted, never read - printed nothing, is dropped from `C - O` as well;
* **the difference on three nested populations** - the registered one, the one that needs only the
  three NET walks, and the one that needs only `O` and `C` - so the effect of that rule is a number;
* **the shape of the difference** - its median, a 1% trimmed mean, how often `C` came out ahead, the
  largest single contributions and the mean without them - because a mean can be a few names;
* **the difference by the open's own spread and by how `O` exited**, which says where it comes from.

Same stores, same instants and the same walk as the registered run; `registered` reproduces
`PR-024.json`'s difference to the digit, and a test holds it there.

    PYTHONPATH=$PWD/src python tools/attribute_pr024.py --data <store> --minutes <m> --quotes <q> \
        --as-of <t> --minutes-as-of <t> --quotes-as-of <t>
    python tools/attribute_pr024.py --report
"""

from __future__ import annotations

import argparse
import json
import statistics
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

import run_pr024 as study
from run_pr016 import atr_registry, cluster_of
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.reference import ExchangeSession
from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
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

RESULT = study.RESULTS / "PR-024-attribution.json"
MOMENTS = (OPEN, ELEVEN, CLOSE)
LARGEST = 8
TRIM = 0.01
QUINTILES = 5

#: The populations, each needing less than the one before it: every arm and costing (what section 6
#: read), the three NET walks with their gross twins, and `O` and `C` alone.
REGISTERED, THREE_ARMS, TWO_ARMS = "registered", "three_arms", "two_arms"


class _MissingExitQuote(Exception):
    """An exit whose moment's spread the window could not give."""


@dataclass
class Walked:
    """One entry with every arm and costing attempted, and every failure kept."""

    entry: study.Entry
    early: str | None = None
    quote_reason: dict[str, str | None] = field(default_factory=dict)
    spreads: dict[str, Decimal | None] = field(default_factory=dict)
    fills: dict[str, Minute | None] = field(default_factory=dict)
    signal_stored: bool = True
    trades: dict[str, dict[str, Trade | str]] = field(default_factory=dict)

    def first_reason(self) -> str | None:
        """What `run_pr024.price_entry` would have returned - its checks, in its order."""
        if self.early:
            return self.early
        for moment in MOMENTS:
            if self.quote_reason.get(moment):
                return self.quote_reason[moment]
        for arm in study.ARMS:
            if self.fills.get(arm) is None:
                return "no_print_at_the_moment"
        if not self.signal_stored:
            return "signal_session_not_stored"
        for arm in study.ARMS:
            for costing in study.COSTINGS:
                got = self.trades.get(arm, {}).get(costing)
                if isinstance(got, str):
                    return got
        return None

    def failures(self) -> list[str]:
        """Every failure, as `reason:arm:costing` - or the entry-level reason alone."""
        if self.early:
            return [self.early]
        found = [f"{reason}:{moment}" for moment, reason in self.quote_reason.items() if reason]
        found += [f"no_print_at_the_moment:{arm}" for arm in study.ARMS
                  if self.fills.get(arm) is None]
        for arm, costings in self.trades.items():
            found += [f"{got}:{arm}:{costing}" for costing, got in costings.items()
                      if isinstance(got, str)]
        return found

    def priced(self, arms: Sequence[str], costings: Sequence[str]) -> bool:
        return all(isinstance(self.trades.get(arm, {}).get(costing), Trade)
                   for arm in arms for costing in costings)

    def trade(self, arm: str, costing: str = "net") -> Trade:
        got = self.trades[arm][costing]
        assert isinstance(got, Trade)
        return got


def walk_every(entry: study.Entry, series: BarSeries, atr_value: Decimal,
               minutes: tuple[Minute, ...] | None,
               windows: Mapping[str, tuple[datetime, tuple[Quote, ...]] | None],
               session: ExchangeSession | None, tie_break: TieBreak | None) -> Walked:
    """`run_pr024.price_entry`'s walk, attempted for every arm and costing whose own inputs exist."""
    walked = Walked(entry)
    if minutes is None:
        walked.early = "minutes_unavailable"
        return walked
    if session is None:
        walked.early = "not_a_session"
        return walked
    regular = regular_hours(minutes, session)
    bar = next((b for b in series.bars if b.session_date == entry.session_date), None)
    if bar is None:
        walked.early = "entry_session_not_stored"
        return walked
    if not reproduces(regular, bar):
        walked.early = "minutes_mismatch"
        return walked

    for moment in MOMENTS:
        window = windows.get(moment)
        half = None if window is None else study.half_spread_bps(window[1], window[0])
        walked.spreads[moment] = half
        walked.quote_reason[moment] = ("quotes_unavailable" if window is None
                                       else "no_fresh_two_sided_quote" if half is None else None)
    for arm in study.ARMS:
        walked.fills[arm] = study.fill_minute(regular,
                                              study.fill_instant(session, study.MOMENT[arm]))
    signal_bar = next((b for b in series.bars if b.session_date == entry.signal_date), None)
    walked.signal_stored = signal_bar is not None

    spreads = walked.spreads

    def spread_for(moment: str) -> Decimal:
        got = spreads[moment]
        if got is None:
            raise _MissingExitQuote(moment)
        return got

    def at_moment(reason: ExitReason) -> CostModel:
        return study.cost(spread_for(study.EXIT_MOMENT[reason]))

    for arm in study.ARMS:
        own, fill = spreads[study.MOMENT[arm]], walked.fills[arm]
        if own is None or fill is None:
            continue
        stressed = own * study.STRESS_MULTIPLE if arm == study.LATE else own
        plans: dict[str, tuple[Decimal, Callable[[ExitReason], CostModel], Decimal | None]] = {
            "net": (own, at_moment, None),
            "gross": (Decimal(0), lambda _reason: study.cost(Decimal(0)), None),
            "cost_adverse": (stressed, lambda _reason: study.cost(spread_for(OPEN)), None),
            "exits_at_registry": (own, lambda _reason: study.cost(study.REGISTRY_EXIT_BPS), None),
        }
        if signal_bar is not None:
            plans["anchored_stop"] = (own, at_moment, signal_bar.close)
        day = study.after_fill(regular, fill)
        walked.trades[arm] = {}
        for costing, (entry_bps, exits, anchor) in plans.items():
            try:
                got: Trade | str = study.walk_entry(
                    entry, series.bars, atr_value, fill.open, study.cost(entry_bps), exits, day,
                    tie_break, Counter(), arm, anchor=anchor)
            except _MissingExitQuote:
                got = "exit_quote_missing"
            walked.trades[arm][costing] = got
    return walked


def walk_sample(args: argparse.Namespace, entries: Sequence[study.Entry]
                ) -> tuple[list[Walked], Counter[str], dict[str, str]]:
    """Every drawn entry, one series in memory at a time - `run_pr024.price_sample`'s loop."""
    bars = BarStore(args.data / "bars.duckdb")
    as_of = study.read_instant(args.as_of, bars.latest_knowledge_time())
    minutes_store = MinuteStore(args.minutes)
    quotes_store = QuoteStore(args.quotes)
    far = datetime.max.replace(tzinfo=as_of.tzinfo)
    minutes_as_of = study.read_instant(args.minutes_as_of, far)
    quotes_as_of = study.read_instant(args.quotes_as_of, far)
    tie_break = MinuteTieBreak(minutes_store, minutes_as_of)
    registry = atr_registry()
    walked: list[Walked] = []
    before: Counter[str] = Counter()
    by_name: dict[str, list[study.Entry]] = defaultdict(list)
    for entry in entries:
        by_name[entry.instrument_id].append(entry)
    for name in sorted(by_name):
        series = bars.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series is None or not series.bars:
            before["series_unavailable"] += len(by_name[name])
            continue
        atr_series = atr_component.compute(series, registry)
        for entry in by_name[name]:
            atr_value = study.atr_at(atr_series, series, entry.signal_date)
            if atr_value is None:
                before["no_atr"] += 1
                continue
            windows = {moment: quotes_store.window(name, entry.session_date, moment, quotes_as_of)
                       for moment in MOMENTS}
            walked.append(walk_every(entry, series, atr_value,
                                     minutes_store.session(name, entry.session_date, minutes_as_of),
                                     windows, session_for(name, entry.session_date), tie_break))
    bars.close()
    minutes_store.close()
    quotes_store.close()
    instants = {"bars": as_of.isoformat(), "minutes": minutes_as_of.isoformat(),
                "quotes": quotes_as_of.isoformat()}
    return walked, before, instants


def population(walked: Sequence[Walked], name: str) -> list[Walked]:
    if name == REGISTERED:
        return [w for w in walked if w.first_reason() is None]
    arms = study.ARMS if name == THREE_ARMS else (study.BASE, study.LATE)
    return [w for w in walked if not w.early and w.priced(arms, ("net", "gross"))]


def _difference(w: Walked, arm: str, costing: str = "net") -> float:
    return study.per_dollar(w.trade(arm, costing)) - study.per_dollar(w.trade(study.BASE, costing))


def _interval(picked: Sequence[Walked], arm: str, costing: str, resamples: int) -> dict[str, float]:
    by_month: dict[str, list[Decimal]] = defaultdict(list)
    for w in picked:
        by_month[cluster_of(w.entry.session_date)].append(
            Decimal(str(_difference(w, arm, costing))))
    return study._clustered(by_month, resamples, study.BOOTSTRAP_SEED)  # noqa: SLF001


def shape(picked: Sequence[Walked], resamples: int) -> dict[str, Any]:
    """`C - O` on one population: the registered interval's twin and what the mean is made of."""
    differences = [_difference(w, study.LATE) for w in picked]
    ordered = sorted(differences)
    cut = int(len(ordered) * TRIM)
    trimmed = ordered[cut:len(ordered) - cut] or ordered
    largest = sorted(zip(picked, differences, strict=True), key=lambda pair: -abs(pair[1]))
    kept = [d for _, d in largest[LARGEST:]]
    total = sum(abs(d) for d in differences)
    return {
        "entries": len(picked),
        "difference": _interval(picked, study.LATE, "net", resamples),
        "gross_part": _interval(picked, study.LATE, "gross", resamples),
        "timed_difference": (_interval(picked, study.TIMED, "net", resamples)
                             if all(w.priced((study.TIMED,), ("net",)) for w in picked) else None),
        "median": statistics.median(differences) if differences else None,
        "trimmed_mean": statistics.fmean(trimmed) if trimmed else None,
        "trim_each_side": TRIM,
        "share_close_ahead": (sum(d > 0 for d in differences) / len(differences)
                              if differences else None),
        "largest": [{"instrument_id": w.entry.instrument_id,
                     "session_date": w.entry.session_date.isoformat(), "difference": d,
                     "open_exit": w.trade(study.BASE).exit_reason.value,
                     "close_exit": w.trade(study.LATE).exit_reason.value}
                    for w, d in largest[:LARGEST]],
        "largest_share_of_absolute_total": (sum(abs(d) for _, d in largest[:LARGEST]) / total
                                            if total else None),
        "mean_without_largest": statistics.fmean(kept) if kept else None,
    }


def by_open_spread(picked: Sequence[Walked]) -> list[dict[str, Any]]:
    """Quintiles of the open's own half-spread: where the difference comes from."""
    ranked = sorted(picked, key=lambda w: w.spreads[OPEN] or Decimal(0))
    rows = []
    for q in range(QUINTILES):
        group = ranked[q * len(ranked) // QUINTILES:(q + 1) * len(ranked) // QUINTILES]
        if not group:
            continue
        net = [_difference(w, study.LATE) for w in group]
        rows.append({
            "quintile": q + 1, "entries": len(group),
            "open_half_spread_bps": statistics.fmean(float(w.spreads[OPEN] or 0) for w in group),
            "close_half_spread_bps": statistics.fmean(float(w.spreads[CLOSE] or 0) for w in group),
            "difference": statistics.fmean(net),
            "gross_part": statistics.fmean(_difference(w, study.LATE, "gross") for w in group),
            "median": statistics.median(net),
        })
    return rows


def by_open_exit(picked: Sequence[Walked]) -> dict[str, dict[str, float | int]]:
    """`C - O` split by how the open arm left: the difference lives in the flips."""
    groups: dict[str, list[float]] = defaultdict(list)
    for w in picked:
        groups[w.trade(study.BASE).exit_reason.value].append(_difference(w, study.LATE))
    return {reason: {"entries": len(values), "difference": statistics.fmean(values),
                     "median": statistics.median(values)}
            for reason, values in sorted(groups.items(), key=lambda kv: -len(kv[1]))}


def build(args: argparse.Namespace) -> dict[str, Any]:
    entries = study.read_sample(args.sample)
    walked, before, instants = walk_sample(args, entries)
    first = Counter(before)
    first.update(reason for w in walked if (reason := w.first_reason()) is not None)
    every = Counter(failure for w in walked for failure in w.failures())
    pops = {name: population(walked, name) for name in (REGISTERED, THREE_ARMS, TWO_ARMS)}
    return {
        "for": "PR-024",
        "exploratory": True,
        "purpose": ("after the registered run: what excluded each entry, and whether C - O is the "
                    "whole book or a few names. Section 6 read PR-024.json; nothing here changes it"),
        "as_of": instants,
        "drawn": len(entries),
        "excluded_first_reason": dict(first.most_common()),
        "failures_by_arm_and_costing": dict(every.most_common()),
        "populations": {name: shape(picked, args.resamples) for name, picked in pops.items()},
        "by_open_spread": by_open_spread(pops[TWO_ARMS]),
        "by_open_exit": by_open_exit(pops[TWO_ARMS]),
        "resamples": args.resamples,
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.3f}%"


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-024 attribution (EXPLORATORY)   drawn {payload['drawn']}")
    print(f"  excluded, first reason   {payload['excluded_first_reason']}")
    for name, cell in payload["populations"].items():
        d = cell["difference"]
        print(f"  {name:<11} {cell['entries']:>5} entries   C - O {_pct(d['estimate'])} "
              f"[{_pct(d['lo'])}, {_pct(d['hi'])}]   median {_pct(cell['median'])}   "
              f"trimmed {_pct(cell['trimmed_mean'])}   C ahead {cell['share_close_ahead']:.1%}   "
              f"without the {LARGEST} largest {_pct(cell['mean_without_largest'])}")
    for row in payload["by_open_spread"]:
        print(f"  open-spread Q{row['quintile']}  O {row['open_half_spread_bps']:6.1f} bps  "
              f"C {row['close_half_spread_bps']:5.1f} bps  C - O {_pct(row['difference'])}  "
              f"gross {_pct(row['gross_part'])}  median {_pct(row['median'])}")
    for reason, row in payload["by_open_exit"].items():
        print(f"  O left by {reason:<12} {row['entries']:>5}  C - O {_pct(row['difference'])}  "
              f"median {_pct(row['median'])}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb")
    parser.add_argument("--minutes", type=Path, help="the minute store")
    parser.add_argument("--quotes", type=Path, help="the quote store")
    parser.add_argument("--sample", type=Path, default=study.SAMPLE, help="the drawn entries")
    parser.add_argument("--as-of", help="the bar store's knowledge instant (default: latest)")
    parser.add_argument("--minutes-as-of", help="the minute store's knowledge instant")
    parser.add_argument("--quotes-as-of", help="the quote store's knowledge instant")
    parser.add_argument("--resamples", type=int, default=study.BOOTSTRAP_RESAMPLES)
    parser.add_argument("--out", type=Path, default=RESULT, help="where the payload is written")
    parser.add_argument("--report", action="store_true", help="print the stored payload")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(args.out.read_text(encoding="utf-8")))
        return 0
    if args.data is None or args.minutes is None or args.quotes is None:
        parser.error("--data, --minutes and --quotes are required")
    payload = build(args)
    args.out.write_text(json.dumps(payload, indent=2, default=study._default) + "\n",  # noqa: SLF001
                        encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
