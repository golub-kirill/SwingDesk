"""`PR-026`..`PR-029` - four single changes to `CARD-001`, each against one baseline, read against SPY.

**The owner's pick, 2026-09-19**, after `PR-024` showed the card breaks even entered at 15:55. Four
ideas, and the owner asked that they not be mixed, so each is its own registration with its own
verdict, and all four share ONE baseline, ONE draw and ONE pass:

* `PR-026` **garbage** - the baseline without leveraged or inverse funds;
* `PR-027` **pullback** - the baseline's entries whose signal close sits below their 20-day mean;
* `PR-028` **exit** - the baseline's own entries under `PR-019`'s selected exit: a 4 ATR stop, no
  target, 60 sessions;
* `PR-029` **regime** - the baseline's dates with `SPY` below its 200-day mean against those above.

**The baseline** is `CARD-001` as it is - `run_pr016`'s ranked rule, the top decile - entered at the
CLOSE of the session after the signal, the nearest daily price to `PR-024`'s 15:55, under the
ratified exit. Daily bars only: 2018-09..2022-08 has no minutes or quotes in any store here.

**Every trade is read in excess of SPY over its own days** - its net return per dollar less `SPY`'s
from the entry session's close to the exit session's close. A longer hold earns more of the market's
drift, and `PR-019b` is what reading an exit without that costs. So `level` - what `BOTH_NEGATIVE`
reads - is "does it beat the index", and an arm better than the baseline and still behind `SPY` says
so in its branch.

**Costs are `PR-024`'s measured decile half-spreads by moment**, the only per-name spreads this
project has for these names: 5.0 bps at the close, 8.4 at 11:00 for an intraday stop or target,
37.8 at the open for a gap through the stop (`PR-024.json`, `diagnostics`). The `SPY` leg is charged
nothing, which leans against every arm.

    PYTHONPATH=$PWD/src python tools/run_pr026.py --data <store> --directory <dir> --draw
    PYTHONPATH=$PWD/src python tools/run_pr026.py --data <store> --directory <dir> --resamples 10000
    python tools/run_pr026.py --report
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import run_pr024 as p24
from run_pr014 import BENCHMARK
from run_pr016 import BLOCK, atr_registry, block_bootstrap, cluster_of
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import Minute
from swingdesk.market_data.quotes import CLOSE, ELEVEN, OPEN
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.reference_data.universe import DirectoryEntry
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest import CostModel

# --- the studies ------------------------------------------------------------------------------------

GARBAGE, PULLBACK, EXIT, REGIME = "PR-026", "PR-027", "PR-028", "PR-029"
STUDIES = (GARBAGE, PULLBACK, EXIT, REGIME)
NAMES = {GARBAGE: "garbage", PULLBACK: "pullback", EXIT: "exit", REGIME: "regime"}

#: 48 months, and the 48 before `PR-024`'s: the exploration that suggested these ideas read
#: 2022-09..2026-08 and nothing earlier. `PR-019` DID read this window for its exits, which is why
#: `PR-028` is a re-price of its selected cell and not a fresh selection.
WINDOW_START = date(2018, 9, 1)
WINDOW_END = date(2022, 8, 31)

#: Registered BEFORE the draw, from `power_pr026.py`.
PER_DATE = 40
SAMPLE_SEED = 20260919

#: `PR-024`'s measured half-spreads of the card's own names, by moment (`PR-024.json` diagnostics:
#: 37.76, 8.36, 4.97 bps). A daily walk knows which kind of exit it took and not when, so each exit
#: is charged the moment its kind happens at - `run_pr024.EXIT_MOMENT`.
COST_BPS = {OPEN: Decimal("37.8"), ELEVEN: Decimal("8.4"), CLOSE: Decimal("5.0")}
STRESS_MULTIPLE = Decimal(3)
COSTINGS = {"net": Decimal(1), "gross": Decimal(0), "cost_adverse": STRESS_MULTIPLE}

BASE_POLICY = p24.POLICY
#: `PR-019`'s selected cell, `h60_stop4.0`: a 4 ATR stop, no target, 60 sessions.
WIDE_POLICY = ExitPolicy(Decimal("4.0"), 60, None)
POLICIES = {"base": BASE_POLICY, "wide": WIDE_POLICY}

PULLBACK_MEAN = 20
REGIME_MEAN = 200

#: A fund's name marks it leveraged or inverse. Read from the directory's current names - the only
#: names stored - and applied to funds only (`is_etf`). Checked against the directory's own fund
#: names on 2026-09-19. Two kinds of mark:
#:
#: * HARD - "leveraged", "inverse", "bear", a multiple such as "3X" or "-1x", "Daily ... Bull" -
#:   always a leveraged or inverse product;
#: * SOFT - "ultra" and "short" - which ALSO name ultra-short and short-duration BOND funds, so they
#:   count only where the name carries no bond word, or where the issuer is ProShares, whose Ultra
#:   and Short lines are the leveraged and inverse ones ("ProShares UltraShort 20+ Year Treasury").
HARD_MARK = re.compile(
    r"\b(leveraged|inverse|bear)\b|(?<![\w.])-?[1-5](\.\d+)?x\b|\bdaily\b.*\b(bull|bear|long|short)\b",
    re.IGNORECASE)
SOFT_MARK = re.compile(r"\bultra\w*|\bshort\b", re.IGNORECASE)
BOND_WORD = re.compile(
    r"\b(income|bond|duration|municipal|muni|treasury|government|term|maturity|credit|corporate|"
    r"mortgage|cash|money|floating|tips|inflation)\b", re.IGNORECASE)

MIN_COMPLETE_SHARE = 0.90
MIN_DATES = 500
MIN_MONTHS = 24
POWER_FLOOR = 0.0030
BOOTSTRAP_SEED = 20260919
BOOTSTRAP_RESAMPLES = 10_000

#: "The latest pull there is" - an instant later than any pull can be stamped.
FAR_FUTURE = datetime(9999, 1, 1, tzinfo=UTC)

RESULTS = p24.RESULTS
SAMPLE = RESULTS / "PR-026-sample.jsonl"
QA_SAMPLE = RESULTS / "PR-026-qa-sample.csv"
QA_ROWS = 400


def result_path(study: str) -> Path:
    return RESULTS / f"{study}.json"


def levered_name(name: str) -> bool:
    """Whether a fund's name marks it leveraged or inverse (`HARD_MARK`, `SOFT_MARK`)."""
    if HARD_MARK.search(name):
        return True
    if not SOFT_MARK.search(name):
        return False
    return "proshares" in name.lower() or not BOND_WORD.search(name)


def is_levered(entry: DirectoryEntry | None) -> bool:
    """A fund whose name says it is leveraged or inverse. A stock never is."""
    return bool(entry is not None and entry.is_etf and levered_name(entry.name or ""))


def mean_of_last(values: Sequence[float], count: int) -> float | None:
    return statistics.fmean(values[-count:]) if len(values) >= count else None


# --- one entry --------------------------------------------------------------------------------------


@dataclass
class Walked:
    """One drawn entry: its features at the signal, and its excess over SPY per exit and costing."""

    entry: p24.Entry
    levered: bool = False
    pullback: bool | None = None
    regime_up: bool | None = None
    excess: dict[tuple[str, str], float] = field(default_factory=dict)
    trades: dict[str, Trade] = field(default_factory=dict)
    reason: str | None = None

    def priced(self, exit_name: str, costing: str = "net") -> bool:
        return (exit_name, costing) in self.excess


def _cost(bps: Decimal) -> CostModel:
    return p24.cost(bps)


def walk(entry: p24.Entry, series: BarSeries, atr_value: Decimal, spy_close: Mapping[date, float],
         policy: ExitPolicy, scale: Decimal) -> tuple[Trade, float] | str:
    """The baseline's walk from the entry session's close, and the trade's excess over SPY."""
    bar = next((b for b in series.bars if b.session_date == entry.session_date), None)
    if bar is None:
        return "entry_session_not_stored"

    def exits(reason: ExitReason) -> CostModel:
        return _cost(COST_BPS[p24.EXIT_MOMENT[reason]] * scale)

    closing = [Minute(at=bar.event_time, open=bar.close, high=bar.close, low=bar.close,
                      close=bar.close)]
    trade = p24.walk_entry(entry, series.bars, atr_value, bar.close, _cost(COST_BPS[CLOSE] * scale),
                           exits, closing, None, Counter(), "B", policy=policy)
    if isinstance(trade, str):
        return trade
    start, end = spy_close.get(entry.session_date), spy_close.get(trade.exit_date)
    if start is None or end is None:
        return "spy_not_stored"
    return trade, p24.per_dollar(trade) - (end / start - 1)


def features(series: BarSeries, signal: date, spy_closes: Sequence[tuple[date, float]]
             ) -> tuple[bool | None, bool | None]:
    """At the signal close: below its 20-day mean? And SPY above its 200-day mean?"""
    closes = [float(b.close) for b in series.bars if b.session_date <= signal]
    mean20 = mean_of_last(closes, PULLBACK_MEAN)
    pullback = None if mean20 is None or not closes else closes[-1] < mean20
    spy = [c for d, c in spy_closes if d <= signal]
    mean200 = mean_of_last(spy, REGIME_MEAN)
    regime = None if mean200 is None else spy[-1] > mean200
    return pullback, regime


# --- inference ------------------------------------------------------------------------------------


def _interval(values_by_date: Mapping[date, float], resamples: int,
              seed: int = BOOTSTRAP_SEED) -> dict[str, float]:
    by_month: dict[str, list[Decimal]] = defaultdict(list)
    for day, value in values_by_date.items():
        by_month[cluster_of(day)].append(Decimal(str(value)))
    got = block_bootstrap([by_month[k] for k in sorted(by_month)], "mean", BLOCK, seed, resamples)
    if got is None:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "width": math.nan}
    estimate, lo, hi = got
    return {"estimate": estimate, "lo": lo, "hi": hi, "width": hi - lo}


def two_group_interval(values_by_date: Mapping[date, float], group: Mapping[date, bool],
                       resamples: int, seed: int = BOOTSTRAP_SEED) -> dict[str, float]:
    """Mean over `False` dates minus mean over `True` dates, months resampled in moving blocks."""
    months: dict[str, list[tuple[bool, float]]] = defaultdict(list)
    for day, value in values_by_date.items():
        if day in group:
            months[cluster_of(day)].append((group[day], value))
    keys = sorted(months)

    def statistic(chosen: Sequence[str]) -> float | None:
        down = [v for k in chosen for g, v in months[k] if not g]
        up = [v for k in chosen for g, v in months[k] if g]
        return statistics.fmean(down) - statistics.fmean(up) if down and up else None

    observed = statistic(keys)
    if observed is None or len(keys) < 2:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "width": math.nan}
    block = min(BLOCK, len(keys))
    starts = len(keys) - block + 1
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(resamples):
        chosen: list[str] = []
        while len(chosen) < len(keys):
            s = rng.randrange(starts)
            chosen.extend(keys[s:s + block])
        resampled = statistic(chosen[:len(keys)])
        if resampled is not None:
            draws.append(resampled)
    if not draws:
        return {"estimate": observed, "lo": math.nan, "hi": math.nan, "width": math.nan}
    draws.sort()
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    return {"estimate": observed, "lo": lo, "hi": hi, "width": hi - lo}


def _by_date(walked: Sequence[Walked], value: Callable[[Walked], float | None]
             ) -> dict[date, list[float]]:
    out: dict[date, list[float]] = defaultdict(list)
    for w in walked:
        got = value(w)
        if got is not None:
            out[w.entry.signal_date].append(got)
    return out


def contrast_values(walked: Sequence[Walked], study: str, costing: str
                    ) -> tuple[dict[date, float], dict[date, float]]:
    """Per date: the study's contrast, and the arm's own level (its mean excess over SPY)."""
    def base(w: Walked) -> float | None:
        return w.excess.get(("base", costing))

    everything = _by_date(walked, base)
    contrast: dict[date, float] = {}
    level: dict[date, float] = {}
    if study in (GARBAGE, PULLBACK):
        def kept(w: Walked) -> bool:
            return not w.levered if study == GARBAGE else w.pullback is True

        chosen = _by_date([w for w in walked if kept(w)], base)
        for day, values in chosen.items():
            level[day] = statistics.fmean(values)
            contrast[day] = level[day] - statistics.fmean(everything[day])
    elif study == EXIT:
        pairs = [w for w in walked if w.priced("base", costing) and w.priced("wide", costing)]
        for day, values in _by_date(pairs, lambda w: w.excess[("wide", costing)]
                                    - w.excess[("base", costing)]).items():
            contrast[day] = statistics.fmean(values)
        for day, values in _by_date(pairs, lambda w: w.excess[("wide", costing)]).items():
            level[day] = statistics.fmean(values)
    else:
        for day, values in everything.items():
            contrast[day] = statistics.fmean(values)
            level[day] = contrast[day]
    return contrast, level


def reading(walked: Sequence[Walked], study: str, drawn: int, resamples: int) -> dict[str, Any]:
    """One study's cell: its contrast under each costing, its level, and its sample."""
    regimes = {w.entry.signal_date: w.regime_up for w in walked if w.regime_up is not None}
    cell: dict[str, Any] = {"study": study, "name": NAMES[study], "drawn": drawn}
    for costing in COSTINGS:
        contrast, level = contrast_values(walked, study, costing)
        if study == REGIME:
            cell["difference" if costing == "net" else costing] = two_group_interval(
                contrast, {d: bool(g) for d, g in regimes.items()}, resamples)
            if costing == "net":
                down = {d: v for d, v in level.items() if regimes.get(d) is False}
                cell["level"] = _interval(down, resamples)
                cell["dates"] = len([d for d in contrast if d in regimes])
                cell["dates_by_regime"] = {"spy_above": sum(1 for d in contrast if regimes.get(d)),
                                           "spy_below": sum(1 for d in contrast
                                                            if regimes.get(d) is False)}
        else:
            cell["difference" if costing == "net" else costing] = _interval(contrast, resamples)
            if costing == "net":
                cell["level"] = _interval(level, resamples)
                cell["dates"] = len(contrast)
        if costing == "net":
            cell["months"] = len({cluster_of(d) for d in contrast})
    priced = sum(1 for w in walked if w.priced("base") and (study != EXIT or w.priced("wide")))
    cell["priced"] = priced
    cell["complete_share"] = priced / drawn if drawn else 0.0
    return cell


def branch_for(cell: Mapping[str, Any]) -> str:
    """`PR-024`'s order, with the sample rule in DATES - every reading here is a per-date mean."""
    difference = cell["difference"]
    if (cell["complete_share"] < MIN_COMPLETE_SHARE or cell["dates"] < MIN_DATES
            or cell["months"] < MIN_MONTHS):
        return "REFUSED"
    if math.isnan(difference["width"]):
        return "INCONCLUSIVE"
    if difference["lo"] > 0.0:
        if cell["level"]["hi"] < 0.0:
            return "BOTH_NEGATIVE"
        if not cell["cost_adverse"]["estimate"] > 0.0:
            return "COST_FRAGILE"
        return "ACCEPT"
    if difference["hi"] < 0.0:
        return "REJECT"
    if difference["width"] > POWER_FLOOR:
        return "INCONCLUSIVE"
    return "NULL"


# --- the sample and the pass -------------------------------------------------------------------------


def window_formations(calendar: Sequence[date]) -> list[date]:
    return p24.formation_dates(calendar, WINDOW_START, WINDOW_END)


def directory_index(path: Path, as_of: datetime | None) -> dict[str, DirectoryEntry]:
    with DirectoryStore(path) as directory:
        known: datetime | None = as_of or directory.latest_pull(FAR_FUTURE)
        if known is None:
            return {}
        return {e.symbol: e for e in directory.as_of(known)}


def listing(index: Mapping[str, DirectoryEntry], name: str) -> DirectoryEntry | None:
    return index.get(name) or index.get(name.replace("-", ".")) or index.get(name.replace("-", ""))


def walk_sample(args: argparse.Namespace, entries: Sequence[p24.Entry]
                ) -> tuple[list[Walked], dict[str, str]]:
    bars = BarStore(args.data / "bars.duckdb")
    as_of = p24.read_instant(args.as_of, bars.latest_knowledge_time())
    directory_as_of = datetime.fromisoformat(args.directory_as_of) if args.directory_as_of else None
    index = directory_index(args.directory, directory_as_of)
    spy = bars.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    if spy is None:
        raise SystemExit(f"{BENCHMARK} is not in the store")
    spy_pairs = [(b.session_date, float(b.close)) for b in spy.bars]
    spy_close = dict(spy_pairs)
    registry = atr_registry()
    by_name: dict[str, list[p24.Entry]] = defaultdict(list)
    for entry in entries:
        by_name[entry.instrument_id].append(entry)
    walked: list[Walked] = []
    for count, name in enumerate(sorted(by_name), start=1):
        series = bars.as_of(name, Interval.DAY, Series.RAW, as_of)
        levered = is_levered(listing(index, name))
        if series is None or not series.bars:
            walked += [Walked(e, levered, reason="series_unavailable") for e in by_name[name]]
            continue
        atr_series = atr_component.compute(series, registry)
        for entry in by_name[name]:
            w = Walked(entry, levered)
            w.pullback, w.regime_up = features(series, entry.signal_date, spy_pairs)
            atr_value = p24.atr_at(atr_series, series, entry.signal_date)
            if atr_value is None:
                w.reason = "no_atr"
                walked.append(w)
                continue
            for exit_name, policy in POLICIES.items():
                for costing, scale in COSTINGS.items():
                    got = walk(entry, series, atr_value, spy_close, policy, scale)
                    if isinstance(got, str):
                        w.reason = w.reason or f"{exit_name}:{got}"
                        continue
                    trade, excess = got
                    w.excess[(exit_name, costing)] = excess
                    if costing == "net":
                        w.trades[exit_name] = trade
            walked.append(w)
        if count % 400 == 0:
            print(f"  walked {count}/{len(by_name)} instruments", flush=True)
    bars.close()
    return walked, {"bars": as_of.isoformat(),
                    "directory": directory_as_of.isoformat() if directory_as_of else "latest pull"}


def diagnostics(walked: Sequence[Walked]) -> dict[str, Any]:
    base = [w for w in walked if "base" in w.trades]
    wide = [w for w in walked if "wide" in w.trades]
    return {
        "levered_entries": sum(w.levered for w in walked),
        "pullback_entries": sum(w.pullback is True for w in walked),
        "regime": {"spy_above": sum(w.regime_up is True for w in walked),
                   "spy_below": sum(w.regime_up is False for w in walked)},
        "base_exits": dict(Counter(w.trades["base"].exit_reason.value for w in base).most_common()),
        "wide_exits": dict(Counter(w.trades["wide"].exit_reason.value for w in wide).most_common()),
        "base_sessions_held": statistics.fmean(
            (w.trades["base"].exit_date - w.entry.session_date).days for w in base) if base else None,
        "wide_sessions_held": statistics.fmean(
            (w.trades["wide"].exit_date - w.entry.session_date).days for w in wide) if wide else None,
        "excluded": dict(Counter(w.reason for w in walked if w.reason).most_common()),
    }


def build(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    entries = p24.read_sample(args.sample)
    walked, instants = walk_sample(args, entries)
    registered = args.resamples == BOOTSTRAP_RESAMPLES
    seen = diagnostics(walked)
    signal_dates = sorted({w.entry.signal_date for w in walked if w.priced("base")})
    span = ((signal_dates[-1] - signal_dates[0]).days / 365.25) if signal_dates else 0.0
    payloads: dict[str, dict[str, Any]] = {}
    for study in STUDIES:
        cell = reading(walked, study, len(entries), args.resamples)
        branch = branch_for(cell) if registered else "SMOKE"
        payloads[study] = {
            "prereg": study,
            "trials": 1,
            "verdict": p24.TOKEN[branch] if registered else "smoke",
            "branch": branch,
            "country": "USA",
            "as_of": instants,
            "measured_span": {
                "first_session": signal_dates[0].isoformat() if signal_dates else None,
                "last_session": signal_dates[-1].isoformat() if signal_dates else None,
                "years": round(span, 2),
            },
            "split": {
                "registered": "none - one draw, the change read against the baseline within it",
                "buys": ("nothing a split could buy: one rule fixed before the run, nothing tuned, "
                         "and the window is one the idea was not found on"),
            },
            "perturbations": {"registered": ["cost_adverse", "gross"],
                              "run": ["cost_adverse", "gross"]},
            "registered_settings": {
                "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
                "per_date": PER_DATE, "sample_seed": SAMPLE_SEED,
                "entry": "the close of the session after the signal",
                "costs_bps": {k: str(v) for k, v in COST_BPS.items()},
                "base_exit": "2.0 x ATR(14) stop, 1R target, 20 sessions",
                "wide_exit": "4.0 x ATR(14) stop, no target, 60 sessions",
                "pullback": f"signal close below its {PULLBACK_MEAN}-session mean",
                "regime": f"SPY close above its {REGIME_MEAN}-session mean at the signal",
                "bootstrap": {"unit": "signal month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                              "resamples": args.resamples},
                "min_complete_share": MIN_COMPLETE_SHARE, "min_dates": MIN_DATES,
                "min_months": MIN_MONTHS, "power_floor": POWER_FLOOR,
            },
            "sample": {"drawn": len(entries), "priced": cell["priced"]},
            "diagnostics": seen,
            "cell": cell,
        }
    if registered:
        write_qa(walked)
    return payloads


def write_qa(walked: Sequence[Walked], path: Path = QA_SAMPLE) -> None:
    rng = random.Random(BOOTSTRAP_SEED)
    usable = [w for w in walked if "base" in w.trades and "wide" in w.trades]
    chosen = sorted(rng.sample(usable, min(QA_ROWS, len(usable))),
                    key=lambda w: (w.entry.signal_date, w.entry.instrument_id))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["instrument_id", "signal_date", "session_date", "exit", "entry_price",
                         "stop_price", "exit_date", "exit_price", "exit_reason", "per_dollar",
                         "excess_over_spy", "levered", "pullback", "spy_above_200"])
        for w in chosen:
            for exit_name in ("base", "wide"):
                t = w.trades[exit_name]
                writer.writerow([w.entry.instrument_id, w.entry.signal_date, w.entry.session_date,
                                 exit_name, t.entry_price, t.stop_price, t.exit_date, t.exit_price,
                                 t.exit_reason.value, round(p24.per_dollar(t), 6),
                                 round(w.excess[(exit_name, "net")], 6), w.levered, w.pullback,
                                 w.regime_up])


def run_draw(args: argparse.Namespace) -> int:
    store = BarStore(args.data / "bars.duckdb")
    as_of = p24.read_instant(args.as_of, store.latest_knowledge_time())
    benchmark = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    if benchmark is None:
        raise SystemExit(f"{BENCHMARK} is not in the store")
    calendar = [b.session_date for b in benchmark.bars]
    formations = window_formations(calendar)
    print(f"as_of {as_of.isoformat()}   window {WINDOW_START} .. {WINDOW_END}   "
          f"formation sessions {len(formations)}", flush=True)
    selection, instruments = p24.frame(store, as_of, formations, benchmark)
    store.close()
    entries = p24.draw(selection, calendar, formations, args.per_date, SAMPLE_SEED)
    p24.write_sample(entries, args.sample)
    print(f"instruments scored {instruments}   thin dates {selection.thin}   "
          f"entries written {len(entries)} -> {args.sample}")
    return 0


def _fmt(cell: Mapping[str, float] | None) -> str:
    if not cell or math.isnan(cell.get("estimate", math.nan)):
        return "n/a"
    return f"{cell['estimate'] * 100:+.3f}% [{cell['lo'] * 100:+.3f}, {cell['hi'] * 100:+.3f}]"


def report(payloads: Mapping[str, Mapping[str, Any]]) -> None:
    for study, payload in payloads.items():
        cell = payload["cell"]
        print(f"{study} ({cell['name']})   verdict {payload['verdict']}   branch {payload['branch']}"
              f"   dates {cell['dates']}   months {cell['months']}   "
              f"complete {cell['complete_share']:.1%}")
        print(f"    difference (net)   {_fmt(cell['difference'])}")
        print(f"    gross              {_fmt(cell['gross'])}")
        print(f"    cost-adverse       {_fmt(cell['cost_adverse'])}")
        print(f"    own level vs SPY   {_fmt(cell['level'])}")
    first = next(iter(payloads.values()))
    print(f"  diagnostics {first['diagnostics']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb")
    parser.add_argument("--directory", type=Path, help="the symbol directory store")
    parser.add_argument("--directory-as-of", help="the directory pull to read (default: latest)")
    parser.add_argument("--sample", type=Path, default=SAMPLE, help="the drawn entries")
    parser.add_argument("--as-of", help="the bar store's knowledge instant (default: latest)")
    parser.add_argument("--per-date", type=int, default=PER_DATE, help="names per date to draw")
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES,
                        help="bootstrap resamples; anything but the registered 10000 is a smoke run")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--draw", action="store_true", help="draw and write the sample, then stop")
    mode.add_argument("--report", action="store_true", help="print the stored results")
    args = parser.parse_args(argv)
    if args.report:
        report({s: json.loads(result_path(s).read_text(encoding="utf-8")) for s in STUDIES})
        return 0
    if args.data is None:
        parser.error("--data is required")
    if args.draw:
        return run_draw(args)
    if args.directory is None:
        parser.error("--directory is required")
    payloads = build(args)
    if next(iter(payloads.values()))["verdict"] != "smoke":
        for study, payload in payloads.items():
            result_path(study).write_text(json.dumps(payload, indent=2, default=p24._default)  # noqa: SLF001
                                          + "\n", encoding="utf-8")
    report(payloads)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
