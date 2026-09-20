"""`PR-031` - does the published intraday momentum rule make money on `SPY`, long only, and does it
still make it after publication?

**The rule, as Zarattini, Aziz and Barbon published it (SSRN 4824172, 2024-05-10).** Each minute of
the session has a NOISE AREA: the day's open times one plus and one minus `sigma`, the mean absolute
move from the open to that minute over the last 14 sessions - widened by the overnight gap, so the
upper bound starts from the higher of the open and the prior close. At every HH:00 and HH:30 from
10:00, the position is LONG if the price is above both the upper bound and the session's VWAP, and
flat otherwise; everything is flat at the close. Size: the equity times `min(4, 2% / sigma_daily)`,
`sigma_daily` the last 14 daily returns' standard deviation.

**Three choices made here, each stated because each could move the answer:**

* **No look-ahead at the half hour.** The decision reads the close of the minute that ENDS at HH:00
  or HH:30 and fills at the open of the next one. The paper trades at the bar it reads.
* **Long only**, the owner's preference of 2026-09-19. The paper's short leg is run as `SPY-both`,
  counted and never read.
* **Costs per share per side**: half the one-cent quoted spread, $0.005 (`net`); the paper's
  $0.0035 commission plus $0.001 slippage, $0.0045 (`paper`); the whole cent (`cost_adverse`).
  Alpaca charges no commission (`DR-039`); `SPY`'s quoted spread is a cent nearly always, and this
  store holds no quotes to measure it.

**Returns are per unit of equity, per day**: the leverage times each trade's move over the day's
open, less the leverage times two sides' cost over the open. Nothing compounds inside a reading.

    PYTHONPATH=$PWD/src python tools/run_pr031.py --minutes <store> --minutes-as-of <t> \
        --resamples 10000
    python tools/run_pr031.py --report
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr016 import BLOCK, block_bootstrap, cluster_of
from swingdesk.contracts.reference import ExchangeSession
from swingdesk.market_data.minutes import Minute, MinuteStore
from swingdesk.reference_data import calendar as cal
from swingdesk.validation.backtest.intraday import regular_hours, session_for

RESULTS = REPO / "docs" / "prereg" / "results"
RESULT = RESULTS / "PR-031.json"
POWER = RESULTS / "PR-031-power.json"

#: The paper's constants, none of them chosen here.
LOOKBACK = 14
FIRST_DECISION = 30
EVERY = 30
VOL_TARGET = 0.02
MAX_LEVERAGE = 4.0

#: Dollars per share per side.
COSTS: dict[str, float] = {"net": 0.005, "paper": 0.0045, "cost_adverse": 0.01, "gross": 0.0}

#: The window: every session the minute store can hold (`sip` serves from 2016-01-04), to the
#: last completed session before registration; and the day the paper appeared.
START = date(2016, 1, 4)
END = date(2026, 9, 18)
PUBLISHED = date(2024, 5, 10)

PRIMARY = "SPY-long"
#: name -> (instrument, whether the short leg trades).
READINGS: dict[str, tuple[str, bool]] = {
    "SPY-long": ("SPY", False), "QQQ-long": ("QQQ", False), "SPY-both": ("SPY", True)}

BOOTSTRAP_SEED = 20260921
BOOTSTRAP_RESAMPLES = 10_000
POWER_RESAMPLES = 2000
#: End-to-end width, in daily return, below which a zero-containing interval is `NULL`: a mean
#: within +-0.04% a day, about +-10% a year - a quarter of the paper's claim either side of zero.
POWER_FLOOR = 0.0008
MIN_DAYS, MIN_MONTHS, MIN_COMPLETE_SHARE = 1000, 24, 0.90
#: A session is read only when its minutes cover this share of the regular session.
MIN_COVERAGE = 0.90

#: A result file's `verdict` speaks the project's four-word vocabulary, as `run_pr024.TOKEN` does
#: and `tools/verify_studies.py` enforces; the BRANCH is what carries the detail. `PR-032` A-1.
TOKEN = {"REFUSED": "refused", "COST_FRAGILE": "inconclusive",
         "PUBLICATION_FRAGILE": "inconclusive", "ACCEPT": "accept", "REJECT": "reject",
         "INCONCLUSIVE": "inconclusive", "NULL": "inconclusive", "SMOKE": "smoke"}


@dataclass(frozen=True)
class Day:
    """One regular session, minute by minute from the bell, gaps carried forward."""

    session: date
    open: float
    close: float
    opens: tuple[float, ...]
    closes: tuple[float, ...]
    vwap: tuple[float, ...]
    coverage: float


def build_day(minutes: Sequence[Minute], session: ExchangeSession) -> Day | None:
    """The session's minutes by offset from the bell, or None when it holds none."""
    regular = regular_hours(minutes, session)
    if not regular:
        return None
    length = int((session.close_time - session.open_time) / timedelta(minutes=1))
    by_offset = {int((m.at - session.open_time) / timedelta(minutes=1)): m for m in regular}
    first = regular[0]
    opens: list[float] = []
    closes: list[float] = []
    vwap: list[float] = []
    last = float(first.open)
    weighted = volume = 0.0
    for offset in range(length):
        m = by_offset.get(offset)
        if m is None:
            opens.append(last)
            closes.append(last)
        else:
            opens.append(float(m.open))
            closes.append(float(m.close))
            last = float(m.close)
            if m.volume:
                price = (float(m.vwap) if m.vwap is not None
                         else (float(m.high) + float(m.low) + float(m.close)) / 3)
                weighted += price * m.volume
                volume += m.volume
        vwap.append(weighted / volume if volume else closes[-1])
    return Day(session=session.session_date, open=float(first.open), close=closes[-1],
               opens=tuple(opens), closes=tuple(closes), vwap=tuple(vwap),
               coverage=len(by_offset) / length)


def noise(history: Sequence[Day], length: int) -> list[float] | None:
    """`sigma` at each minute: the mean absolute move from the open over the prior sessions."""
    if len(history) < LOOKBACK:
        return None
    recent = history[-LOOKBACK:]
    out: list[float] = []
    for offset in range(length):
        moves = [abs(d.closes[offset] / d.open - 1) for d in recent if offset < len(d.closes)]
        out.append(sum(moves) / len(moves) if moves else math.nan)
    return out


def leverage(history: Sequence[Day]) -> float | None:
    """`min(4, 2% / sigma_daily)`, from the last 14 close-to-close returns."""
    if len(history) < LOOKBACK + 1:
        return None
    closes = [d.close for d in history[-(LOOKBACK + 1):]]
    returns = [b / a - 1 for a, b in pairwise(closes)]
    spread = statistics.stdev(returns)
    return MAX_LEVERAGE if spread == 0 else min(MAX_LEVERAGE, VOL_TARGET / spread)


def trade_day(day: Day, prior_close: float, sigma: Sequence[float],
              both: bool) -> list[tuple[int, float, float]]:
    """Every trade of the session as (side, entry, exit): decided on the minute that ends at each
    half hour, filled at the next minute's open, flat at the close."""
    upper_base = max(day.open, prior_close)
    lower_base = min(day.open, prior_close)
    trades: list[tuple[int, float, float]] = []
    side, entry = 0, 0.0
    for at in range(FIRST_DECISION, len(day.closes), EVERY):
        seen = at - 1
        price, vwap = day.closes[seen], day.vwap[seen]
        upper = upper_base * (1 + sigma[seen])
        lower = lower_base * (1 - sigma[seen])
        want = 1 if price > max(upper, vwap) else (-1 if both and price < min(lower, vwap) else 0)
        if want != side:
            fill = day.opens[at]
            if side:
                trades.append((side, entry, fill))
            side, entry = want, fill
    if side:
        trades.append((side, entry, day.close))
    return trades


@dataclass
class Traded:
    """One session's result under every costing, with what produced it."""

    session: date
    leverage: float
    trades: int
    returns: dict[str, float] = field(default_factory=dict)
    held: float = 0.0


def day_result(day: Day, prior_close: float, sigma: Sequence[float], lev: float,
               both: bool) -> Traded:
    trades = trade_day(day, prior_close, sigma, both)
    moved = sum(side * (exit_ - entry) for side, entry, exit_ in trades)
    got = Traded(session=day.session, leverage=lev, trades=len(trades))
    for costing, per_share in COSTS.items():
        got.returns[costing] = lev * (moved - 2 * per_share * len(trades)) / day.open
    return got


def run_instrument(days: Sequence[Day], both: bool) -> tuple[list[Traded], dict[str, int]]:
    """Walk the sessions in order; a session is traded once 15 read sessions stand before it."""
    history: list[Day] = []
    traded: list[Traded] = []
    skipped: dict[str, int] = defaultdict(int)
    for day in days:
        sigma = noise(history, len(day.closes))
        lev = leverage(history)
        if sigma is None or lev is None:
            skipped["warm_up"] += 1
        elif any(math.isnan(s) for s in sigma[:len(day.closes) - 1]):
            skipped["no_noise_at_some_minute"] += 1
        else:
            traded.append(day_result(day, history[-1].close, sigma, lev, both))
        history.append(day)
    return traded, dict(skipped)


# --- inference -------------------------------------------------------------------------------------


def clustered_mean(values: Mapping[date, float], resamples: int,
                   seed: int = BOOTSTRAP_SEED) -> dict[str, float]:
    by_month: dict[str, list[Any]] = defaultdict(list)
    for session, value in values.items():
        by_month[cluster_of(session)].append(value)
    clusters = [by_month[k] for k in sorted(by_month)]
    got = block_bootstrap([[Decimal(str(v)) for v in c] for c in clusters], "mean", BLOCK, seed,
                          resamples)
    if got is None:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "width": math.nan}
    estimate, lo, hi = got
    return {"estimate": estimate, "lo": lo, "hi": hi, "width": hi - lo}


def described(values: Sequence[float]) -> dict[str, float]:
    """Annualised, descriptive, never read by the decision rule."""
    if len(values) < 2:
        return {}
    mean, spread = statistics.fmean(values), statistics.stdev(values)
    equity, peak, worst = 1.0, 1.0, 0.0
    for r in values:
        equity *= 1 + r
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    years = len(values) / 252
    return {"days": len(values), "annual_mean": mean * 252,
            "annual_volatility": spread * math.sqrt(252),
            "sharpe": mean / spread * math.sqrt(252) if spread else math.nan,
            "cagr": equity ** (1 / years) - 1 if years and equity > 0 else math.nan,
            "max_drawdown": worst}


def reading(traded: Sequence[Traded], sessions: int, resamples: int) -> dict[str, Any]:
    cell: dict[str, Any] = {"days": len(traded), "sessions": sessions,
                            "complete_share": len(traded) / sessions if sessions else 0.0,
                            "months": len({cluster_of(t.session) for t in traded})}
    for costing in COSTS:
        cell["mean" if costing == "net" else costing] = clustered_mean(
            {t.session: t.returns[costing] for t in traded}, resamples)
    after = {t.session: t.returns["net"] for t in traded if t.session > PUBLISHED}
    cell["after_publication"] = {"days": len(after), **clustered_mean(after, resamples)}
    before = {t.session: t.returns["net"] for t in traded if t.session <= PUBLISHED}
    cell["before_publication"] = {"days": len(before), **clustered_mean(before, resamples)}
    cell["described"] = described([t.returns["net"] for t in traded])
    cell["described_after_publication"] = described(list(after.values()))
    cell["days_traded"] = sum(1 for t in traded if t.trades)
    cell["mean_leverage"] = statistics.fmean(t.leverage for t in traded) if traded else math.nan
    return cell


def branch_for(cell: Mapping[str, Any], floor: float = POWER_FLOOR) -> str:
    if (cell["days"] < MIN_DAYS or cell["months"] < MIN_MONTHS
            or cell["complete_share"] < MIN_COMPLETE_SHARE):
        return "REFUSED"
    mean, adverse = cell["mean"], cell["cost_adverse"]
    if mean["lo"] > 0:
        if not adverse["lo"] > 0:
            return "COST_FRAGILE"
        if not cell["after_publication"]["estimate"] > 0:
            return "PUBLICATION_FRAGILE"
        return "ACCEPT"
    if mean["hi"] < 0:
        return "REJECT"
    return "INCONCLUSIVE" if mean["width"] > floor else "NULL"


def holding(days: Sequence[Day], traded: Sequence[Traded]) -> dict[str, float]:
    """Holding the instrument close to close on the same sessions, price only - it leaves out the
    dividends, about 1.3% a year on `SPY` - beside the rule. Descriptive."""
    close_before = {b.session: a.close for a, b in pairwise(days)}
    by_day = {d.session: d.close for d in days}
    pairs = [(t.returns["net"], by_day[t.session] / close_before[t.session] - 1)
             for t in traded if t.session in close_before]
    if len(pairs) < 3:
        return {}
    rule, hold = [p[0] for p in pairs], [p[1] for p in pairs]
    return {**{f"hold_{k}": v for k, v in described(hold).items()},
            "correlation": statistics.correlation(rule, hold)}


# --- the run ----------------------------------------------------------------------------------------


def read_instant(text: str | None, default: datetime) -> datetime:
    return default if text is None else datetime.fromisoformat(text)


def load_days(store: MinuteStore, instrument: str, as_of: datetime
              ) -> tuple[list[Day], dict[str, int], int]:
    exchange = cal.exchange_for(instrument)
    sessions = cal.sessions(exchange, START, END)
    days: list[Day] = []
    missing: dict[str, int] = defaultdict(int)
    for session in sessions:
        minutes = store.session(instrument, session.session_date, as_of)
        if minutes is None:
            missing["never_fetched"] += 1
            continue
        found = session_for(instrument, session.session_date)
        day = None if found is None else build_day(minutes, found)
        if day is None:
            missing["no_regular_minutes"] += 1
        elif day.coverage < MIN_COVERAGE:
            missing["thin"] += 1
        else:
            days.append(day)
    return days, dict(missing), len(sessions)


def build(args: argparse.Namespace, resamples: int) -> dict[str, Any]:
    store = MinuteStore(args.minutes)
    as_of = read_instant(args.minutes_as_of, datetime.max.replace(tzinfo=UTC))
    loaded = {name: load_days(store, name, as_of) for name in {i for i, _ in READINGS.values()}}
    store.close()
    cells: dict[str, Any] = {}
    for name, (instrument, both) in READINGS.items():
        days, missing, sessions = loaded[instrument]
        traded, skipped = run_instrument(days, both)
        cell = reading(traded, sessions - skipped.get("warm_up", 0), resamples)
        cell["excluded"] = {**missing, **skipped}
        cell["holding"] = holding(days, traded)
        cells[name] = cell
    return {"as_of": {"minutes": as_of.isoformat()}, "cells": cells}


def power(args: argparse.Namespace) -> dict[str, Any]:
    """Each reading's WIDTH before registration, and nothing else."""
    from power_pr019 import assert_no_effect_leaked

    built = build(args, POWER_RESAMPLES)
    widths = {name: {"whole": round(cell["mean"]["width"], 6),
                     "after_publication": round(cell["after_publication"]["width"], 6),
                     "days": cell["days"], "days_after_publication": cell["after_publication"]["days"]}
              for name, cell in built["cells"].items()}
    payload = {"for": "PR-031", "as_of": built["as_of"], "resamples": POWER_RESAMPLES,
               "widths": widths, "power_floor_width": POWER_FLOOR}
    assert_no_effect_leaked(payload)
    return payload


def _fmt(cell: Mapping[str, float]) -> str:
    if math.isnan(cell.get("estimate", math.nan)):
        return "n/a"
    return (f"{cell['estimate']:+.4%} [{cell['lo']:+.4%}, {cell['hi']:+.4%}]")


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-031   verdict {payload['verdict']}   branch {payload['branch']}")
    for name, cell in payload["cells"].items():
        print(f"  {name}   days {cell['days']}   months {cell['months']}   "
              f"complete {cell['complete_share']:.1%}   excluded {cell['excluded']}")
        print(f"    mean a day, net         {_fmt(cell['mean'])}")
        for costing in ("paper", "cost_adverse", "gross"):
            print(f"    {costing:<23} {_fmt(cell[costing])}")
        print(f"    before publication      {_fmt(cell['before_publication'])}")
        print(f"    after publication       {_fmt(cell['after_publication'])}   "
              f"{cell['after_publication']['days']} days")
        print(f"    described               {cell['described']}")
        print(f"    holding it              {cell['holding']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=Path, help="the minute store holding SPY and QQQ")
    parser.add_argument("--minutes-as-of", help="the minute store's knowledge instant")
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES,
                        help="bootstrap resamples; anything but the registered 10000 is a smoke run")
    parser.add_argument("--report", action="store_true", help="print the stored result")
    parser.add_argument("--power", action="store_true",
                        help="write each reading's interval width only, before registration")
    args = parser.parse_args(argv)
    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.minutes is None:
        parser.error("--minutes is required")
    if args.power:
        estimate = power(args)
        POWER.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
        print(f"PR-031 power: widths {estimate['widths']}")
        return 0
    built = build(args, args.resamples)
    registered = args.resamples == BOOTSTRAP_RESAMPLES
    branch = branch_for(built["cells"][PRIMARY]) if registered else "SMOKE"
    payload: dict[str, Any] = {
        "prereg": "PR-031", "trials": 3, "verdict": TOKEN[branch], "branch": branch,
        "country": "USA", "as_of": built["as_of"],
        "measured_span": {"first_session": START.isoformat(), "last_session": END.isoformat(),
                          "years": round((END - START).days / 365.25, 2)},
        "split": {"registered": "none - a published rule with every constant fixed by the paper",
                  "buys": "nothing a split could buy: nothing is selected; the period since "
                          "publication is read apart and gates ACCEPT"},
        "perturbations": {"registered": ["paper", "cost_adverse", "gross"],
                          "run": ["paper", "cost_adverse", "gross"]},
        "registered_settings": {
            "lookback": LOOKBACK, "first_decision_minute": FIRST_DECISION, "every": EVERY,
            "vol_target": VOL_TARGET, "max_leverage": MAX_LEVERAGE, "costs_per_share": COSTS,
            "published": PUBLISHED.isoformat(), "primary": PRIMARY,
            "bootstrap": {"unit": "month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                          "resamples": args.resamples},
            "power_floor": POWER_FLOOR, "min_days": MIN_DAYS, "min_months": MIN_MONTHS,
            "min_complete_share": MIN_COMPLETE_SHARE, "min_coverage": MIN_COVERAGE},
        "cells": built["cells"],
    }
    if registered:
        RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
