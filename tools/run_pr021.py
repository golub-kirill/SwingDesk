"""`PR-021`: bought as last week's biggest losers and held one to five sessions, do stocks beat SPY?

**The first study here in a different CLASS of strategy.** Every study from `PR-013` to `PR-020`
ranked on relative strength and bought the WINNERS, and holding the index beat that family per
dollar (`EVIDENCE_SUMMARY` §20.9). The owner chose the next class on 2026-09-13 - short-term
reversal, a one- to five-session hold - which is the sign Jegadeesh (1990) and Lehmann (1990)
document at this horizon and which nothing here has run: `PR-015`'s `REVERSAL_21` used a
21-session formation, a 20-session hold and a four-name book.

**Per dollar, never in R.** `PR-020` read a pool in the trade's R and T-bill funds carried a
thousand times an equity's weight. A book's return is a return on the money in it.

**Common stocks only.** The directory's `is_etf` flag decides. A leveraged or inverse fund moves
three times the index's week, so it sits in the loser tail by construction, and a book of them is a
leveraged bet on the index's own reversal rather than on any stock's. The class the literature
documents is a property of single stocks.

The construction, fixed by the registration rather than by this file:

* **formation** - at each session's close, the admitted stocks of one half of the universe
  (`run_pr015.half_of`), ranked by their own close-to-close return over the last FIVE sessions,
  most negative first; the bottom decile is that session's cohort;
* **holding** - a cohort is bought at the next session's OPEN and sold at the open H sessions
  later, H in 1..5. The book holds the last H cohorts at 1/H of the capital each, equal-weighted
  within. Every trade happens at an open, so a name that a leaving cohort and an arriving one
  share is kept rather than sold and bought back;
* **costs** - `DR-005`'s 25 bps a side, which `DR-040` measured as right for the opening minute
  this book trades in, on MEASURED net turnover: the round trip is charged when a weight rises
  (`run_pr014.turnover`'s convention). No commission (`costs.commission_model`);
* **the contrast** - the book's net return minus `SPY`'s over the same open-to-open session, day
  by day; the mean of that series annualised x252, with a moving-block bootstrap over sessions.

    PYTHONPATH=$PWD/src python tools/run_pr021.py --data <store directory> --as-of <instant>
"""

from __future__ import annotations

import argparse
import calendar as calendar_module
import json
import math
import statistics
import sys
from array import array
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr014 import moving_block_bootstrap
from run_pr015 import half_of
from swingdesk.application.universe import rule_from_registry
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.directory import DirectoryStore

BENCHMARK = "SPY"

#: The formation: a name's own close-to-close return over the last five sessions. Lehmann's (1990)
#: weekly horizon, and fixed so that the hold is the only thing the study varies.
FORMATION = 5

#: The owner's range. One configuration each - five trials, declared.
HOLDS = (1, 2, 3, 4, 5)

#: `screen.relative_strength_rule`'s cutoff, the one every study here has used. Exact, as
#: `run_pr014.select` sizes it: `int(len(pool) * 0.10)`.
DECILE = Decimal("0.10")

#: `AGENTS.md` §19: forty-eight months back from the run's own `as_of`.
WINDOW_MONTHS = 48

#: `DR-005`, `costs.slippage_model`: 25 bps of price, each side.
SLIPPAGE_BPS = 25.0
SIDES = 2
STRESS_MULTIPLE = 3.0

#: Two weeks of sessions. Consecutive sessions are different days, so the series overlaps in what
#: the book HOLDS and never in the period a return covers; ten covers any weekly dependence twice.
BLOCK = 10
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260913

SESSIONS_PER_YEAR = 252

#: Annualised percentage points, end to end, on the holdout's excess over SPY - fixed before the
#: power estimate ran. The index's own long-run return is about ten points a year; an interval
#: wider than +/-10 cannot tell a book that doubles it from one that adds nothing. It gates NULL
#: only (`branch_for`): the estimate measured ~33 points, so this design can read a large effect's
#: sign and cannot read an absence.
POWER_FLOOR = 20.0

#: About two years of sessions in the judged window, and `run_pr013`'s cross-section minimum.
MIN_SESSIONS = 500
MIN_NAMES_PER_DATE = 100

#: A window where more than this share of formations was too thin to form a cohort is refused.
MAX_THIN_SHARE = 0.05

SELECTION_HALF = "A"
HOLDOUT_HALF = "B"

RESULT = REPO / "docs" / "prereg" / "results" / "PR-021.json"

NAN = float("nan")


def window_start(as_of: date, months: int) -> date:
    """`months` calendar months before `as_of`, the day clamped to the month's length."""
    total = as_of.year * 12 + (as_of.month - 1) - months
    year, month = divmod(total, 12)
    last = calendar_module.monthrange(year, month + 1)[1]
    return date(year, month + 1, min(as_of.day, last))


@dataclass
class Panel:
    """Opens and closes on the benchmark's calendar for every admitted stock the caller kept.

    `array('d')` from calendar index `first` onward, NaN where a name has no bar: thirteen thousand
    names as Python floats in dicts would be gigabytes, and every reading is by calendar index.
    """

    calendar: list[date]
    first: int
    start: int
    spy_open: list[float]
    opens: dict[str, array[float]] = field(default_factory=dict)
    closes: dict[str, array[float]] = field(default_factory=dict)
    admitted: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def open(self, name: str, t: int) -> float:
        return self.opens[name][t - self.first]

    def close(self, name: str, t: int) -> float:
        return self.closes[name][t - self.first]


def stock_symbols(directory: DirectoryStore, as_of: datetime) -> tuple[frozenset[str], frozenset[str]]:
    """(stocks, funds) as the directory knew them at `as_of`. A name in neither is not a stock."""
    entries = directory.as_of(as_of)
    stocks = frozenset(e.symbol for e in entries if not e.is_etf and not e.is_test_issue)
    funds = frozenset(e.symbol for e in entries if e.is_etf)
    return stocks, funds


def load_panel(
    store: BarStore,
    as_of: datetime,
    rule: rules.LiquidityRule,
    stocks: frozenset[str],
    funds: frozenset[str],
    keep: Callable[[str], bool],
    months: int = WINDOW_MONTHS,
) -> Panel:
    """Every kept stock the rule admits on at least one formation, one series in memory at a time."""
    spy = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    calendar = [bar.session_date for bar in spy.bars]
    begin = window_start(as_of.date(), months)
    start = next((i for i, d in enumerate(calendar) if d >= begin), None)
    if start is None or start < FORMATION + max(HOLDS) + 1 or start >= len(calendar) - 2:
        raise SystemExit(f"{BENCHMARK} does not cover a window starting {begin}")
    first = start - max(HOLDS) - FORMATION
    panel = Panel(calendar, first, start, [float(bar.open) for bar in spy.bars])
    formations = range(start - max(HOLDS), len(calendar) - 1)
    index_of = {d: i for i, d in enumerate(calendar)}
    size = len(calendar) - first
    for name in store.instrument_ids(as_of):
        if name == BENCHMARK or not keep(name):
            continue
        if name in funds:
            panel.counts["funds_excluded"] += 1
            continue
        if name not in stocks:
            panel.counts["type_unknown_excluded"] += 1
            continue
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        position = {bar.session_date: k for k, bar in enumerate(series.bars)}
        admitted = [t for t in formations
                    if (k := position.get(calendar[t])) is not None and rule.admits(series, k)]
        if not admitted:
            panel.counts["never_admitted"] += 1
            continue
        opens = array("d", [NAN]) * size
        closes = array("d", [NAN]) * size
        for bar in series.bars:
            t = index_of.get(bar.session_date)
            if t is None or t < first:
                continue
            opens[t - first] = float(bar.open)
            closes[t - first] = float(bar.close)
        panel.opens[name] = opens
        panel.closes[name] = closes
        for t in admitted:
            panel.admitted[t].append(name)
        panel.counts["stocks_admitted"] += 1
    return panel


def formation_return(panel: Panel, name: str, t: int) -> float | None:
    """Close at `t` over close at `t - FORMATION`, minus one. Nothing after `t` is read."""
    now, then = panel.close(name, t), panel.close(name, t - FORMATION)
    if not (now > 0.0 and then > 0.0):
        return None
    return now / then - 1.0


def losers(panel: Panel, t: int, names: Sequence[str],
           min_names: int = MIN_NAMES_PER_DATE) -> list[str] | None:
    """The bottom decile at formation `t`, most negative first, or None when the pool is thin.

    Sized over EVERY admitted name, an unscored one included, and an unscored name is ordered last
    so it is never bought - the same two conventions `stream_selection` holds the live ranker to.
    Ties break on the instrument id, so the order is total.
    """
    if len(names) < min_names:
        return None
    size = int(len(names) * DECILE)
    if size < 1:
        return None
    scored: list[tuple[float, str]] = []
    unscored: list[str] = []
    for name in names:
        value = formation_return(panel, name, t)
        if value is None:
            unscored.append(name)
        else:
            scored.append((value, name))
    scored.sort()
    ordered = [name for _, name in scored] + sorted(unscored)
    return ordered[:size]


def session_return(panel: Panel, name: str, e: int) -> float | None:
    """Open at `e` to open at `e + 1`, or None when either price is missing."""
    here, there = panel.open(name, e), panel.open(name, e + 1)
    if not (here > 0.0 and there > 0.0):
        return None
    return there / here - 1.0


@dataclass
class Book:
    """One half, one hold: the per-session series every reading is built from."""

    hold: int
    sessions: list[date] = field(default_factory=list)
    gross: list[float] = field(default_factory=list)
    turnover: list[float] = field(default_factory=list)
    spy: list[float] = field(default_factory=list)
    pool: list[float] = field(default_factory=list)
    cohort_sizes: list[int] = field(default_factory=list)
    unpriced: int = 0
    idle_cohorts: int = 0


def cohorts_for(panel: Panel, half: str, min_names: int = MIN_NAMES_PER_DATE
                ) -> tuple[dict[int, list[str]], dict[int, list[str]], int]:
    """(cohorts, pools, thin) for one half over every formation the window needs."""
    cohorts: dict[int, list[str]] = {}
    pools: dict[int, list[str]] = {}
    thin = 0
    for t in range(panel.start - max(HOLDS), len(panel.calendar) - 1):
        pool = [n for n in panel.admitted.get(t, ()) if half_of(n) == half]
        pools[t] = pool
        picked = losers(panel, t, pool, min_names)
        if picked is None:
            if t >= panel.start - 1:
                thin += 1
            continue
        cohorts[t] = picked
    return cohorts, pools, thin


def build_book(panel: Panel, cohorts: dict[int, list[str]], pools: dict[int, list[str]],
               hold: int) -> Book:
    """The book the construction holds, one open-to-open session at a time.

    At the open of session `e` the book holds the cohorts formed at the closes `e - hold` through
    `e - 1`, each at `1 / hold` of the capital. A thin formation has no cohort and its share sits in
    cash for its hold - counted, not refilled with something worse. Turnover is read from the same
    target weights the return uses, so the two halves of the arithmetic describe one portfolio.
    """
    out = Book(hold)
    previous: dict[str, float] | None = None
    for e in range(panel.start - 1, len(panel.calendar) - 1):
        weights: dict[str, float] = {}
        gross = 0.0
        for t in range(e - hold, e):
            members = cohorts.get(t)
            if not members:
                if e >= panel.start:
                    out.idle_cohorts += 1
                continue
            share = 1.0 / hold / len(members)
            for name in members:
                weights[name] = weights.get(name, 0.0) + share
            priced = [r for name in members if (r := session_return(panel, name, e)) is not None]
            if e >= panel.start:
                out.unpriced += len(members) - len(priced)
            if priced:
                gross += statistics.fmean(priced) / hold
        if previous is None:
            previous = weights  # the session before the window: the book is already held
            continue
        bought = sum(max(0.0, weight - previous.get(name, 0.0)) for name, weight in weights.items())
        previous = weights
        members_now = [n for n in pools.get(e - 1, ())]
        pool_returns = [r for n in members_now if (r := session_return(panel, n, e)) is not None]
        spy_here, spy_there = panel.spy_open[e], panel.spy_open[e + 1]
        out.sessions.append(panel.calendar[e])
        out.gross.append(gross)
        out.turnover.append(bought)
        out.spy.append(spy_there / spy_here - 1.0)
        out.pool.append(statistics.fmean(pool_returns) if pool_returns else 0.0)
        out.cohort_sizes.append(len(cohorts.get(e - 1, ())))
    return out


def net(book: Book, multiple: float = 1.0) -> list[float]:
    """Gross minus the round trip on what was bought, at `multiple` times `DR-005`."""
    rate = SIDES * SLIPPAGE_BPS * multiple / 10_000.0
    return [g - u * rate for g, u in zip(book.gross, book.turnover, strict=True)]


def minus(left: Sequence[float], right: Sequence[float]) -> list[float]:
    return [a - b for a, b in zip(left, right, strict=True)]


def annual(value: float) -> float:
    """A per-session figure as percentage points a year: x252, x100. Arithmetic, not compounded."""
    return value * SESSIONS_PER_YEAR * 100.0


def interval(values: Sequence[float], resamples: int, seed: int = BOOTSTRAP_SEED) -> dict[str, float]:
    """Mean and 95% moving-block interval of a per-session series, in points a year."""
    result = moving_block_bootstrap(list(values), BLOCK, seed, resamples)  # type: ignore[arg-type]
    if result is None:
        return {"mean": NAN, "lo": NAN, "hi": NAN, "width": NAN}
    mean, lo, hi = result
    return {"mean": annual(mean), "lo": annual(lo), "hi": annual(hi), "width": annual(hi - lo)}


def max_drawdown(returns: Sequence[float]) -> float:
    """The worst peak-to-trough fall of the compounded series, as a negative fraction."""
    peak, value, worst = 1.0, 1.0, 0.0
    for r in returns:
        value *= 1.0 + r
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def beta(returns: Sequence[float], market: Sequence[float]) -> float:
    if len(returns) < 2:
        return NAN
    variance = statistics.pvariance(market)
    if variance <= 0.0:
        return NAN
    mx, my = statistics.fmean(market), statistics.fmean(returns)
    covariance = statistics.fmean((m - mx) * (r - my) for m, r in zip(market, returns, strict=True))
    return covariance / variance


def break_even_bps(gross_edge: Sequence[float], turnover: Sequence[float]) -> float:
    """The per-side cost at which the gross edge is exactly paid for, in bps."""
    turn = statistics.fmean(turnover) if turnover else 0.0
    if turn <= 0.0:
        return NAN
    return statistics.fmean(gross_edge) / (SIDES * turn) * 10_000.0


def readings(book: Book, thin: int, resamples: int) -> dict[str, Any]:
    """Every figure the report prints for one book. Section 6 reads `excess` and `absolute` only."""
    one, stressed = net(book, 1.0), net(book, STRESS_MULTIPLE)
    excess = minus(one, book.spy)
    formations = len(book.sessions)
    return {
        "hold": book.hold,
        "sessions": formations,
        "first_session": book.sessions[0].isoformat() if book.sessions else None,
        "last_session": book.sessions[-1].isoformat() if book.sessions else None,
        "thin_formations": thin,
        "thin_share": thin / formations if formations else 1.0,
        "idle_cohort_sessions": book.idle_cohorts,
        "unpriced_name_sessions": book.unpriced,
        "cohort_size": {"typical": statistics.median(book.cohort_sizes) if book.cohort_sizes else 0,
                        "smallest": min(book.cohort_sizes, default=0)},
        "turnover_per_session": statistics.fmean(book.turnover) if book.turnover else NAN,
        "cost_points_a_year": annual(statistics.fmean(book.turnover) * SIDES * SLIPPAGE_BPS / 10_000.0)
        if book.turnover else NAN,
        "excess": interval(excess, resamples),
        "absolute": interval(one, resamples),
        "excess_gross": interval(minus(book.gross, book.spy), resamples),
        "excess_cost_stress_3x": interval(minus(stressed, book.spy), resamples),
        "versus_pool": interval(minus(one, book.pool), resamples),
        "signal_gross_versus_pool": interval(minus(book.gross, book.pool), resamples),
        "spy": interval(book.spy, resamples),
        "pool": interval(book.pool, resamples),
        "break_even_bps_a_side": {"versus_spy": break_even_bps(minus(book.gross, book.spy),
                                                               book.turnover),
                                  "versus_pool": break_even_bps(minus(book.gross, book.pool),
                                                                book.turnover)},
        "beta_to_spy": beta(book.gross, book.spy),
        "max_drawdown": {"book_net": max_drawdown(one), "spy": max_drawdown(book.spy)},
        "worst_session_excess": min(excess, default=NAN),
    }


def select_hold(cells: dict[int, dict[str, Any]]) -> int | None:
    """Section 5a: the hold with the largest selection-half excess. A tie selects nothing."""
    scores = {hold: cell["excess"]["mean"] for hold, cell in cells.items()
              if not math.isnan(cell["excess"]["mean"])}
    if not scores:
        return None
    best = max(scores.values())
    winners = [hold for hold, value in scores.items() if value == best]
    return winners[0] if len(winners) == 1 else None


def branch_for(cell: dict[str, Any]) -> str:
    """Section 6, in its order. The report's `verdict` token is `TOKEN[branch]`.

    **The floor gates NULL and nothing else.** An interval that excludes zero answers the SIGN
    whatever its width - half B was never seen by the selection, so width is imprecision about the
    size, not bias about the sign. What a wide interval cannot do is say an effect is ABSENT.
    `PR-019b` read one wholly below zero and its rule refused it for width; that is the reading
    this order exists not to repeat.
    """
    excess, absolute = cell["excess"], cell["absolute"]
    if cell["sessions"] < MIN_SESSIONS or cell["thin_share"] > MAX_THIN_SHARE:
        return "REFUSED"
    if math.isnan(excess["width"]):
        return "INCONCLUSIVE"
    if excess["lo"] > 0.0:
        if absolute["hi"] < 0.0:
            return "BOTH_NEGATIVE"
        if not cell["excess_cost_stress_3x"]["mean"] > 0.0:
            return "COST_FRAGILE"
        return "ACCEPT"
    if excess["hi"] < 0.0:
        return "REJECT"
    if excess["width"] > POWER_FLOOR:
        return "INCONCLUSIVE"
    return "NULL"


TOKEN = {"ACCEPT": "accept", "REJECT": "reject", "NULL": "inconclusive",
         "BOTH_NEGATIVE": "inconclusive", "COST_FRAGILE": "inconclusive",
         "INCONCLUSIVE": "inconclusive", "REFUSED": "refused", "TIE": "inconclusive"}


def liquidity_rule() -> tuple[rules.LiquidityRule, dict[str, str]]:
    """The LIVE rule, `universe.adtv_lag_sessions` included - the owner's one-number ruling."""
    built = rule_from_registry(ParameterRegistry.load())
    if not isinstance(built, tuple):
        raise SystemExit(f"the liquidity rule cannot be built: {built}")
    rule, _ = built
    return rule, {"min_price": str(rule.min_price), "min_adtv": str(rule.min_adtv),
                  "adtv_window": str(rule.adtv_window), "min_history": str(rule.min_history),
                  "adtv_lag": str(rule.adtv_lag)}


def open_stores(data: Path) -> tuple[BarStore, DirectoryStore]:
    return BarStore(data / "bars.duckdb"), DirectoryStore(data / "directory.duckdb")


def build(args: argparse.Namespace) -> dict[str, Any]:
    store, directory = open_stores(args.data)
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        raise SystemExit("the bar store is empty")
    stocks, funds = stock_symbols(directory, as_of)
    if not stocks:
        raise SystemExit("the directory knew no stocks at this instant - nothing to classify by")
    directory.close()
    rule, rule_values = liquidity_rule()
    print(f"as_of {as_of.isoformat()}   loading both halves ...", flush=True)
    panel = load_panel(store, as_of, rule, stocks, funds, lambda _: True, args.window_months)
    store.close()
    registered = (args.window_months == WINDOW_MONTHS and args.resamples == BOOTSTRAP_RESAMPLES
                  and args.min_names == MIN_NAMES_PER_DATE)
    cells: dict[str, dict[int, dict[str, Any]]] = {}
    for half in (SELECTION_HALF, HOLDOUT_HALF):
        cohorts, pools, thin = cohorts_for(panel, half, args.min_names)
        cells[half] = {}
        for hold in HOLDS:
            cells[half][hold] = readings(build_book(panel, cohorts, pools, hold), thin,
                                         args.resamples)
            print(f"  half {half}  hold {hold}  done", flush=True)

    chosen = select_hold(cells[SELECTION_HALF])
    branch = "TIE" if chosen is None else branch_for(cells[HOLDOUT_HALF][chosen])
    judged = cells[HOLDOUT_HALF][chosen] if chosen is not None else None
    months = args.window_months
    measured = cells[HOLDOUT_HALF][HOLDS[0]]
    first_seen = date.fromisoformat(measured["first_session"])
    last_seen = date.fromisoformat(measured["last_session"])
    return {
        "prereg": "PR-021",
        "trials": len(HOLDS),
        "country": "USA",
        "as_of": as_of.isoformat(),
        "registered_settings": registered,
        "universe": {"rule": rule_values, "stocks_only": True, **dict(panel.counts)},
        "window": {"asked_months": months,
                   "start": panel.calendar[panel.start].isoformat(),
                   "end": panel.calendar[-2].isoformat()},
        "measured_span": {"first_session": first_seen.isoformat(),
                          "last_session": last_seen.isoformat(),
                          "years": round((last_seen - first_seen).days / 365.25, 2)},
        "construction": {"formation_sessions": FORMATION, "holds": list(HOLDS),
                         "decile": str(DECILE), "slippage_bps_a_side": SLIPPAGE_BPS,
                         "commission": "none - costs.commission_model", "block": BLOCK,
                         "resamples": args.resamples, "seed": BOOTSTRAP_SEED,
                         "power_floor_points": POWER_FLOOR, "min_sessions": MIN_SESSIONS,
                         "min_names_per_date": args.min_names},
        "split": {"registered": "names: sha256(instrument_id)[0] % 2, half A selects the hold, "
                                "half B is judged",
                  "buys": "the hold is SELECTED - the largest half-A excess - so half B, which "
                          "the selection never saw, is the only window a verdict may be read on",
                  "selection_half": SELECTION_HALF, "holdout_half": HOLDOUT_HALF},
        "perturbations": {"registered": ["cost_stress_3x"], "run": ["cost_stress_3x"]},
        "cells": {half: {str(hold): cell for hold, cell in by_hold.items()}
                  for half, by_hold in cells.items()},
        "selected_hold": chosen,
        "branch": branch if registered else "SMOKE",
        "verdict": TOKEN[branch] if registered else "smoke",
        "judged": judged,
    }


def _row(label: str, reading: dict[str, float]) -> str:
    return (f"    {label:28} {reading['mean']:+8.2f}  [{reading['lo']:+8.2f}, {reading['hi']:+8.2f}]"
            f"  width {reading['width']:6.2f}")


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-021 - the five-session losers, held 1..5 sessions, against SPY\n{'=' * 72}")
    print(f"  as_of {payload['as_of']}   window {payload['window']['start']} .. "
          f"{payload['window']['end']}   ({payload['window']['asked_months']} months)")
    print(f"  universe {json.dumps(payload['universe'])}")
    print("  every figure: percentage points a year, x252, arithmetic; 95% moving-block interval")
    for half, by_hold in payload["cells"].items():
        role = "SELECTS the hold" if half == SELECTION_HALF else "JUDGED"
        print(f"\n  half {half} - {role}")
        for hold, cell in by_hold.items():
            print(f"\n  hold {hold}   sessions {cell['sessions']}   cohort "
                  f"{cell['cohort_size']['typical']}   turnover/session "
                  f"{cell['turnover_per_session']:.3f}   cost {cell['cost_points_a_year']:.1f}/yr")
            for key in ("excess", "absolute", "excess_gross", "excess_cost_stress_3x",
                        "versus_pool", "signal_gross_versus_pool", "spy", "pool"):
                print(_row(key, cell[key]))
            even = cell["break_even_bps_a_side"]
            print(f"    break-even a side: {even['versus_spy']:+.1f} bps vs SPY, "
                  f"{even['versus_pool']:+.1f} vs pool   beta {cell['beta_to_spy']:.2f}   "
                  f"max drawdown {cell['max_drawdown']['book_net']:.1%} (SPY "
                  f"{cell['max_drawdown']['spy']:.1%})")
    print(f"\n  selected hold (half {SELECTION_HALF}): {payload['selected_hold']}")
    print(f"  branch {payload['branch']}   verdict {payload['verdict']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data",
                        help="directory holding bars.duckdb and directory.duckdb")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true",
                        help="re-read an existing result instead of running it")
    parser.add_argument("--window-months", type=int, default=WINDOW_MONTHS,
                        help="smoke tests only; anything but 48 emits no verdict")
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES,
                        help="smoke tests only; anything but 10,000 emits no verdict")
    parser.add_argument("--min-names", type=int, default=MIN_NAMES_PER_DATE,
                        help="smoke tests only; anything but 100 emits no verdict")
    args = parser.parse_args()
    if args.report:
        report(json.loads(args.out.read_text(encoding="utf-8")))
        return 0
    payload = build(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report(payload)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
