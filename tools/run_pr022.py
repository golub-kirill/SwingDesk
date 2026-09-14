"""`PR-022`: held while above its ten-month average and in T-bills otherwise, does SPY beat holding SPY?

**The owner's choice on 2026-09-14, after two classes lost to the index.** `PR-021` found holding
`SPY` beat every active construction measured over 48 months, so the question left is whether the
index itself can be held BETTER - the same exposure, stepped aside when its trend breaks. The course
names time-series momentum (`M77-T1145`, an untested hypothesis, no rule given); the rule here is
the published one:

* **Faber (2007)**, *A Quantitative Approach to Tactical Asset Allocation*: at the last session of
  each month, if `SPY`'s close is above the mean of its last ten month-end closes, hold `SPY` for
  the next month; otherwise hold `BIL`, a 1-3 month T-bill fund. Equality is cash. One decision a
  month, so the rule trades a few times a year.
* **Traded at the next session's open**, as the live pipeline would, charged `DR-005`'s 25 bps on
  each fill - a switch is two fills. That is about twenty-five times `SPY`'s own spread, and it is
  the registry's number, so it stays and the report says which way it leans.
* **Total return on both legs.** A T-bill fund pays its whole return as dividends and its price
  barely moves; without them cash would earn nothing and the comparison would be rigged against the
  rule. Prices arrive split-adjusted and so do the vendor's dividends, so no split is applied again.

**The statistic is the Sharpe ratio's difference** (`stats.sharpe_convention`: daily, net of costs,
rf = 0, x sqrt 252), with a moving-block bootstrap of the paired daily returns. The class promises
less risk for about the same return; one number that pays for both is the risk-adjusted return.

    PYTHONPATH=$PWD/src python tools/run_pr022.py --data <store directory> --as-of <instant>
"""

from __future__ import annotations

import argparse
import bisect
import calendar as calendar_module
import json
import math
import random
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr014 import moving_block_bootstrap
from swingdesk.contracts.market import CorporateActionKind, Interval, Series
from swingdesk.market_data import BarStore

BENCHMARK = "SPY"
CASH = "BIL"

#: Faber's (2007) average: the last ten month-end closes, the current one included.
SMA_MONTHS = 10

#: `DR-005`, `costs.slippage_model`: 25 bps of price, each side, applied to the fill.
SLIPPAGE_BPS = 25.0
STRESS_MULTIPLE = 3.0

#: A quarter of sessions: a monthly rule's exposure persists for months and volatility regimes
#: longer, so a block shorter than the decision period would cut the dependence it carries.
BLOCK = 63
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260914
SESSIONS_PER_YEAR = 252

#: Sharpe units, end to end, on the difference - fixed before the power estimate ran. `SPY`'s own
#: Sharpe sits near 0.6; an interval wider than +/-0.2 cannot tell a rule that improves it by a third
#: from one that does nothing. It gates NULL only (`branch_for`, `PR-021`'s order).
POWER_FLOOR = 0.40

#: Ten years of monthly decisions.
MIN_MONTHS = 120

#: `AGENTS.md` §19's current market, read as a diagnostic beside the registered window.
RECENT_MONTHS = 48

#: A drawdown of the index deeper than this is an EPISODE, and each is tabulated.
EPISODE_DEPTH = 0.15

RESULT = REPO / "docs" / "prereg" / "results" / "PR-022.json"

NAN = float("nan")


@dataclass
class Prices:
    """Both legs on the benchmark's calendar. `nan` where the cash fund has no bar."""

    calendar: list[date]
    spy_open: list[float]
    spy_close: list[float]
    cash_open: list[float]
    cash_close: list[float]
    spy_dividend: dict[date, float] = field(default_factory=dict)
    cash_dividend: dict[date, float] = field(default_factory=dict)


def load(store: BarStore, as_of: datetime) -> Prices:
    spy = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    cash = store.as_of(CASH, Interval.DAY, Series.RAW, as_of)
    calendar = [bar.session_date for bar in spy.bars]
    cash_by_day = {bar.session_date: bar for bar in cash.bars}
    prices = Prices(
        calendar,
        [float(bar.open) for bar in spy.bars], [float(bar.close) for bar in spy.bars],
        [float(cash_by_day[d].open) if d in cash_by_day else NAN for d in calendar],
        [float(cash_by_day[d].close) if d in cash_by_day else NAN for d in calendar],
    )
    for name, target in ((BENCHMARK, prices.spy_dividend), (CASH, prices.cash_dividend)):
        for action in store.actions_as_of(name, as_of):
            if action.kind is CorporateActionKind.DIVIDEND:
                target[action.effective_date] = target.get(action.effective_date, 0.0) + float(action.value)
    return prices


def month_ends(calendar: Sequence[date]) -> list[int]:
    """Calendar indices of each month's last session."""
    return [i for i in range(len(calendar))
            if i + 1 == len(calendar) or calendar[i + 1].month != calendar[i].month]


def signals(prices: Prices, ends: Sequence[int]) -> dict[int, bool]:
    """Month-end index -> invested next month. Only closes at or before that month-end are read."""
    decided: dict[int, bool] = {}
    for k in range(SMA_MONTHS - 1, len(ends)):
        window = [prices.spy_close[ends[j]] for j in range(k - SMA_MONTHS + 1, k + 1)]
        decided[ends[k]] = prices.spy_close[ends[k]] > statistics.fmean(window)
    return decided


def first_decision(prices: Prices, ends: Sequence[int], decided: dict[int, bool]) -> int:
    """The first month-end whose NEXT month the cash fund covers from its first session."""
    for end in ends[:-1]:
        if end in decided and not math.isnan(prices.cash_open[end + 1]):
            return end
    raise SystemExit(f"{CASH} never covers a whole month after {SMA_MONTHS} month-ends of {BENCHMARK}")


@dataclass
class Paths:
    """The two books' daily returns over the window, and what the timed one did."""

    sessions: list[date] = field(default_factory=list)
    timed: list[float] = field(default_factory=list)
    held: list[float] = field(default_factory=list)
    invested: list[bool] = field(default_factory=list)
    switches: int = 0
    cash_unpriced: int = 0


def _leg(prices: Prices, invested: bool) -> tuple[list[float], list[float], dict[date, float]]:
    if invested:
        return prices.spy_open, prices.spy_close, prices.spy_dividend
    return prices.cash_open, prices.cash_close, prices.cash_dividend


def build_paths(prices: Prices, decided: dict[int, bool], start_end: int, cost_multiple: float = 1.0,
                last: int | None = None) -> Paths:
    """Both books from the open of the session after `start_end` to `last` (default: the store's end).

    The decision at month-end `m` governs every session after `m` up to and including the next
    month-end. On the session a decision changes the holding, the old asset earns the overnight -
    and the dividend of an ex-date that day, which belongs to whoever held at the prior close - and
    the new one earns open to close, with a fill charged on each side of the switch.
    """
    rate = SLIPPAGE_BPS * cost_multiple / 10_000.0
    ends = sorted(decided)
    out = Paths()
    stop = len(prices.calendar) - 1 if last is None else last
    begin = start_end + 1
    for d in range(begin, stop + 1):
        m = ends[bisect.bisect_left(ends, d) - 1]
        now = decided[m]
        day = prices.calendar[d]
        spy_div = prices.spy_dividend.get(day, 0.0)
        if d == begin:
            # Both books are bought at this open, and neither pays for it: the question is how
            # they differ from here, not what entering costs.
            opens, closes, _ = _leg(prices, now)
            timed = closes[d] / opens[d] - 1.0
            held = prices.spy_close[d] / prices.spy_open[d] - 1.0
        else:
            held = (prices.spy_close[d] + spy_div) / prices.spy_close[d - 1] - 1.0
            before = out.invested[-1]
            opens, closes, dividends = _leg(prices, now)
            if now == before:
                gain = (closes[d] + dividends.get(day, 0.0)) / closes[d - 1]
                if math.isnan(gain):
                    out.cash_unpriced += 1
                    gain = 1.0
                timed = gain - 1.0
            else:
                old_open, old_close, old_div = _leg(prices, before)
                overnight = (old_open[d] + old_div.get(day, 0.0)) / old_close[d - 1]
                intraday = closes[d] / opens[d]
                if math.isnan(overnight) or math.isnan(intraday):
                    out.cash_unpriced += 1
                    overnight = 1.0 if math.isnan(overnight) else overnight
                    intraday = 1.0 if math.isnan(intraday) else intraday
                timed = overnight * (1.0 - rate) ** 2 * intraday - 1.0
                out.switches += 1
        out.sessions.append(day)
        out.timed.append(timed)
        out.held.append(held)
        out.invested.append(now)
    return out


# ------------------------------------------------------------------------------- statistics


def sharpe(returns: Sequence[float]) -> float:
    """`stats.sharpe_convention`: daily, rf = 0, annualised x sqrt(252)."""
    if len(returns) < 2:
        return NAN
    spread = statistics.stdev(returns)
    return statistics.fmean(returns) / spread * math.sqrt(SESSIONS_PER_YEAR) if spread > 0 else NAN


def _prefix(values: Sequence[float]) -> tuple[list[float], list[float]]:
    total, squares = [0.0], [0.0]
    for v in values:
        total.append(total[-1] + v)
        squares.append(squares[-1] + v * v)
    return total, squares


def _sharpe_from(total: float, squares: float, n: int) -> float:
    mean = total / n
    variance = (squares - n * mean * mean) / (n - 1)
    return mean / math.sqrt(variance) * math.sqrt(SESSIONS_PER_YEAR) if variance > 0 else NAN


def bootstrap_sharpes(x: Sequence[float], y: Sequence[float], block: int, seed: int,
                      resamples: int) -> list[tuple[float, float]]:
    """(Sharpe of x, Sharpe of y) per moving-block resample of the PAIRED series.

    The same block starts for both, so the pairing is kept; blocks laid end to end until the
    resample has the sample's length, the last one cut short - `run_pr014.moving_block_bootstrap`'s
    scheme, with prefix sums so each block costs four lookups rather than a loop.
    """
    n = len(x)
    if n < 2 or n != len(y):
        return []
    width = min(block, n)
    starts = n - width + 1
    xs, xq = _prefix(x)
    ys, yq = _prefix(y)
    rng = random.Random(seed)
    out: list[tuple[float, float]] = []
    for _ in range(resamples):
        count = 0
        sx = qx = sy = qy = 0.0
        while count < n:
            begin = rng.randrange(starts)
            take = min(width, n - count)
            sx += xs[begin + take] - xs[begin]
            qx += xq[begin + take] - xq[begin]
            sy += ys[begin + take] - ys[begin]
            qy += yq[begin + take] - yq[begin]
            count += take
        out.append((_sharpe_from(sx, qx, n), _sharpe_from(sy, qy, n)))
    return out


def _percentiles(values: list[float], resamples: int) -> tuple[float, float]:
    ordered = sorted(values)
    return ordered[int(0.025 * resamples)], ordered[int(0.975 * resamples) - 1]


def sharpe_readings(timed: Sequence[float], held: Sequence[float], resamples: int,
                    seed: int = BOOTSTRAP_SEED) -> dict[str, dict[str, float]]:
    """The difference and each book's own Sharpe, each with its 95% moving-block interval."""
    draws = bootstrap_sharpes(timed, held, BLOCK, seed, resamples)
    if not draws:
        blank = {"point": NAN, "lo": NAN, "hi": NAN, "width": NAN}
        return {"difference": blank, "timed": blank, "held": blank}
    point_t, point_h = sharpe(timed), sharpe(held)
    lo_d, hi_d = _percentiles([a - b for a, b in draws], resamples)
    lo_t, hi_t = _percentiles([a for a, _ in draws], resamples)
    lo_h, hi_h = _percentiles([b for _, b in draws], resamples)
    return {"difference": {"point": point_t - point_h, "lo": lo_d, "hi": hi_d, "width": hi_d - lo_d},
            "timed": {"point": point_t, "lo": lo_t, "hi": hi_t, "width": hi_t - lo_t},
            "held": {"point": point_h, "lo": lo_h, "hi": hi_h, "width": hi_h - lo_h}}


def mean_difference(timed: Sequence[float], held: Sequence[float], resamples: int) -> dict[str, float]:
    """Annualised arithmetic return difference, points a year, with its moving-block interval."""
    result = moving_block_bootstrap([a - b for a, b in zip(timed, held, strict=True)],  # type: ignore[arg-type]
                                    BLOCK, BOOTSTRAP_SEED, resamples)
    if result is None:
        return {"point": NAN, "lo": NAN, "hi": NAN}
    scale = SESSIONS_PER_YEAR * 100.0
    return {"point": result[0] * scale, "lo": result[1] * scale, "hi": result[2] * scale}


def growth(returns: Sequence[float]) -> list[float]:
    value, curve = 1.0, []
    for r in returns:
        value *= 1.0 + r
        curve.append(value)
    return curve


def cagr(returns: Sequence[float]) -> float:
    if not returns:
        return NAN
    return growth(returns)[-1] ** (SESSIONS_PER_YEAR / len(returns)) - 1.0


def drawdown(returns: Sequence[float], sessions: Sequence[date]) -> dict[str, Any]:
    """The worst peak-to-trough fall, with the dates it ran between."""
    peak_value, peak_at, worst, worst_peak, worst_trough = 1.0, 0, 0.0, 0, 0
    for i, value in enumerate(growth(returns)):
        if value > peak_value:
            peak_value, peak_at = value, i
        fall = value / peak_value - 1.0
        if fall < worst:
            worst, worst_peak, worst_trough = fall, peak_at, i
    return {"depth": worst,
            "peak": sessions[worst_peak].isoformat() if sessions else None,
            "trough": sessions[worst_trough].isoformat() if sessions else None}


def episodes(paths: Paths, depth: float = EPISODE_DEPTH) -> list[dict[str, Any]]:
    """Every fall of the HELD index deeper than `depth`, and what the timed book did through it.

    An episode runs from a high of the index to its next new high (or the window's end). Its trough
    is the lowest point between. The timed book is read over the same sessions: its return from the
    index's peak to the trough, and from the trough to the recovery - the second is what a late
    return to the market costs.
    """
    held, timed = growth(paths.held), growth(paths.timed)
    found: list[dict[str, Any]] = []
    peak = 0
    i = 1
    while i < len(held):
        if held[i] >= held[peak]:
            peak = i
            i += 1
            continue
        end = i
        while end < len(held) and held[end] < held[peak]:
            end += 1
        trough = min(range(peak, end), key=lambda k: held[k])
        fall = held[trough] / held[peak] - 1.0
        if fall <= -depth:
            recovered = end < len(held)
            last = end if recovered else len(held) - 1
            found.append({
                "peak": paths.sessions[peak].isoformat(),
                "trough": paths.sessions[trough].isoformat(),
                "recovered": paths.sessions[end].isoformat() if recovered else None,
                "held_fall": fall,
                "timed_over_the_fall": timed[trough] / timed[peak] - 1.0,
                "held_recovery": held[last] / held[trough] - 1.0,
                "timed_over_the_recovery": timed[last] / timed[trough] - 1.0,
                "timed_worst_inside": min(timed[k] / max(timed[peak:k + 1]) - 1.0
                                          for k in range(peak, last + 1)),
            })
        peak = end if end < len(held) else peak
        i = end + 1 if end < len(held) else len(held)
    return found


def per_year(paths: Paths) -> dict[str, dict[str, float]]:
    years: dict[int, tuple[list[float], list[float]]] = {}
    for day, t, h in zip(paths.sessions, paths.timed, paths.held, strict=True):
        years.setdefault(day.year, ([], []))[0].append(t)
        years[day.year][1].append(h)
    return {str(year): {"timed": growth(t)[-1] - 1.0, "held": growth(h)[-1] - 1.0}
            for year, (t, h) in sorted(years.items())}


def book_readings(paths: Paths, resamples: int) -> dict[str, Any]:
    sessions = len(paths.sessions)
    years = sessions / SESSIONS_PER_YEAR
    return {
        "sessions": sessions,
        "months": len({(d.year, d.month) for d in paths.sessions}),
        "sharpe": sharpe_readings(paths.timed, paths.held, resamples),
        "mean_difference_points": mean_difference(paths.timed, paths.held, resamples),
        "cagr": {"timed": cagr(paths.timed), "held": cagr(paths.held)},
        "volatility": {"timed": statistics.stdev(paths.timed) * math.sqrt(SESSIONS_PER_YEAR),
                       "held": statistics.stdev(paths.held) * math.sqrt(SESSIONS_PER_YEAR)},
        "max_drawdown": {"timed": drawdown(paths.timed, paths.sessions),
                         "held": drawdown(paths.held, paths.sessions)},
        "invested_share": sum(paths.invested) / sessions if sessions else NAN,
        "switches": paths.switches,
        "switches_a_year": paths.switches / years if years else NAN,
        "cash_unpriced_sessions": paths.cash_unpriced,
    }


def window_start(as_of: date, months: int) -> date:
    total = as_of.year * 12 + (as_of.month - 1) - months
    year, month = divmod(total, 12)
    return date(year, month + 1, min(as_of.day, calendar_module.monthrange(year, month + 1)[1]))


def break_even_bps(gross: Paths) -> float:
    """The per-fill cost at which the timed book's arithmetic mean equals the held one's.

    A switch is two fills and costs about `2c` of the book on its day, so the mean falls by
    `2c x switches / sessions`; negative when the timed book trails before any cost.
    """
    edge = statistics.fmean(gross.timed) - statistics.fmean(gross.held)
    switches_a_session = gross.switches / len(gross.sessions) if gross.sessions else 0.0
    if switches_a_session <= 0.0:
        return NAN
    return edge / (2.0 * switches_a_session) * 10_000.0


def branch_for(cell: dict[str, Any]) -> str:
    """Section 6, in `PR-021`'s order: the floor gates NULL, never the sign."""
    difference, timed = cell["sharpe"]["difference"], cell["sharpe"]["timed"]
    if cell["months"] < MIN_MONTHS:
        return "REFUSED"
    if math.isnan(difference["width"]):
        return "INCONCLUSIVE"
    if difference["lo"] > 0.0:
        if timed["hi"] < 0.0:
            return "BOTH_NEGATIVE"
        if not cell["stress_difference_point"] > 0.0:
            return "COST_FRAGILE"
        return "ACCEPT"
    if difference["hi"] < 0.0:
        return "REJECT"
    if difference["width"] > POWER_FLOOR:
        return "INCONCLUSIVE"
    return "NULL"


TOKEN = {"ACCEPT": "accept", "REJECT": "reject", "NULL": "inconclusive",
         "BOTH_NEGATIVE": "inconclusive", "COST_FRAGILE": "inconclusive",
         "INCONCLUSIVE": "inconclusive", "REFUSED": "refused"}


def build(args: argparse.Namespace) -> dict[str, Any]:
    with BarStore(args.data / "bars.duckdb") as store:
        as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("the bar store is empty")
        prices = load(store, as_of)
    ends = month_ends(prices.calendar)
    decided = signals(prices, ends)
    start = first_decision(prices, ends, decided)
    net = build_paths(prices, decided, start, 1.0)
    gross = build_paths(prices, decided, start, 0.0)
    stressed = build_paths(prices, decided, start, STRESS_MULTIPLE)
    primary = book_readings(net, args.resamples)
    primary["stress_difference_point"] = sharpe(stressed.timed) - sharpe(stressed.held)
    primary["gross_difference_point"] = sharpe(gross.timed) - sharpe(gross.held)
    primary["break_even_bps_a_fill"] = break_even_bps(gross)
    recent_from = window_start(as_of.date(), RECENT_MONTHS)
    cut = next(i for i, d in enumerate(net.sessions) if d >= recent_from)
    recent = Paths(net.sessions[cut:], net.timed[cut:], net.held[cut:], net.invested[cut:],
                   sum(1 for i in range(max(cut, 1), len(net.invested))
                       if net.invested[i] != net.invested[i - 1]))
    branch = branch_for(primary)
    registered = args.resamples == BOOTSTRAP_RESAMPLES
    first_seen, last_seen = net.sessions[0], net.sessions[-1]
    return {
        "prereg": "PR-022",
        "trials": 1,
        "country": "USA",
        "as_of": as_of.isoformat(),
        "registered_settings": registered,
        "rule": {"benchmark": BENCHMARK, "cash": CASH, "sma_months": SMA_MONTHS,
                 "evaluated": "each month's last session close; equality is cash",
                 "executed": "the next session's open", "slippage_bps_a_fill": SLIPPAGE_BPS,
                 "fills_a_switch": 2, "returns": "total - dividends on their ex-date, both legs"},
        "window": {"first_decision": prices.calendar[start].isoformat(),
                   "start": first_seen.isoformat(), "end": last_seen.isoformat()},
        "measured_span": {"first_session": first_seen.isoformat(),
                          "last_session": last_seen.isoformat(),
                          "years": round((last_seen - first_seen).days / 365.25, 2)},
        "split": {"registered": "none",
                  "buys": "nothing is selected - one published rule, fixed before the run - so a "
                          "split would halve nineteen years and their handful of drawdowns for a "
                          "protection there is nothing to protect (PREREG_TEMPLATE 7)"},
        "perturbations": {"registered": ["cost_stress_3x"], "run": ["cost_stress_3x"]},
        "inference": {"block": BLOCK, "resamples": args.resamples, "seed": BOOTSTRAP_SEED,
                      "power_floor_sharpe": POWER_FLOOR, "min_months": MIN_MONTHS},
        "primary": primary,
        "episodes": episodes(net),
        "recent_48_months": {**book_readings(recent, args.resamples), "from": recent_from.isoformat()},
        "per_year": per_year(net),
        "branch": branch if registered else "SMOKE",
        "verdict": TOKEN[branch] if registered else "smoke",
    }


def _interval(reading: dict[str, float], digits: int = 3) -> str:
    return (f"{reading['point']:+.{digits}f} [{reading['lo']:+.{digits}f}, {reading['hi']:+.{digits}f}]")


def report(payload: dict[str, Any]) -> None:
    p = payload["primary"]
    print(f"\nPR-022 - SPY above its 10-month average, BIL below, against holding SPY\n{'=' * 72}")
    print(f"  as_of {payload['as_of']}   window {payload['window']['start']} .. "
          f"{payload['window']['end']}   ({payload['measured_span']['years']} years, {p['months']} months)")
    readings = (("REGISTERED WINDOW", p), ("LAST 48 MONTHS (diagnostic)", payload["recent_48_months"]))
    for label, cell in readings:
        s = cell["sharpe"]
        print(f"\n  {label}")
        print(f"    Sharpe difference      {_interval(s['difference'])}   "
              f"width {s['difference']['width']:.3f}")
        print(f"    Sharpe, timed / held   {_interval(s['timed'])}  /  {_interval(s['held'])}")
        print(f"    mean difference, pts   {_interval(cell['mean_difference_points'], 2)}")
        print(f"    CAGR timed / held      {cell['cagr']['timed']:+.2%} / {cell['cagr']['held']:+.2%}")
        vol = cell["volatility"]
        print(f"    volatility             {vol['timed']:.1%} / {vol['held']:.1%}")
        t, h = cell["max_drawdown"]["timed"], cell["max_drawdown"]["held"]
        print(f"    max drawdown           {t['depth']:.1%} ({t['peak']}..{t['trough']})"
              f" / {h['depth']:.1%} ({h['peak']}..{h['trough']})")
        print(f"    invested {cell['invested_share']:.1%} of sessions   switches {cell['switches']} "
              f"({cell['switches_a_year']:.2f} a year)   cash unpriced {cell['cash_unpriced_sessions']}")
    print(f"\n  Sharpe difference gross {p['gross_difference_point']:+.3f}   at 3x DR-005 "
          f"{p['stress_difference_point']:+.3f}   break-even {p['break_even_bps_a_fill']:+.1f} bps a fill")
    print("\n  episodes of the held index deeper than 15%")
    for e in payload["episodes"]:
        print(f"    {e['peak']} -> {e['trough']} -> {e['recovered']}   held {e['held_fall']:+.1%}  "
              f"timed {e['timed_over_the_fall']:+.1%} (worst inside {e['timed_worst_inside']:+.1%})   "
              f"recovery held {e['held_recovery']:+.1%} timed {e['timed_over_the_recovery']:+.1%}")
    print("\n  per year, timed / held")
    for year, row in payload["per_year"].items():
        print(f"    {year}  {row['timed']:+7.1%}  {row['held']:+7.1%}")
    print(f"\n  branch {payload['branch']}   verdict {payload['verdict']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data",
                        help="directory holding the bars.duckdb with SPY and BIL")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--out", type=Path, default=RESULT)
    parser.add_argument("--report", action="store_true",
                        help="re-read an existing result instead of running it")
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES,
                        help="smoke tests only; anything but 10,000 emits no verdict")
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
