"""`PR-016` — the outcome distribution of the RATIFIED exit, over a decade, in and out of sample.

**The question, in one number.** The ratified exit is a stop at `2.0 x ATR(14)`, a target at `1.0 R`
and a time exit at 20 sessions (`DR-012`, `DR-029`). A target one R away against a stop one R away
needs a win rate **above 50% net of costs** to make money. Everything else this tool prints is
detail; that is the test.

**Why it did not exist.** `exit.target_r_multiple` was ratified on 2026-09-01 and lived only in
`broker/submit.py`, so the backtest harness ran the stop and the clock while every live trade also
carried a take-profit leg. `DR-042` put the profit slot into `ExitPolicy`, and this is the first
study that can simulate the exit this system actually places.

**Two arms, because a win rate alone is unreadable.**

  * `unselected` — every liquid name, every `STEP` sessions. **The control**: the ratified exit
    against the market, no selection at all. Spends no trial, for `PR-008`'s and `PR-010`'s reason:
    no signal, so no edge is being claimed.
  * `ranked` — the top decile by the LIVE `ByMarketPathStrength`, which is
    `screen.relative_strength_rule`. **The hypothesis.** Spends a trial.

The only quantity §6 reads is the DIFFERENCE between them. A 44% win rate means nothing on its own;
44% against a control's 41% is a measurement.

**This measures the TRADE, not the book.** No cap, no sector limit, no correlation limit, no
capacity. `PR-015` measured the four-position book and found nothing separable from zero; this
measures what one trade does under the ratified exit, which is a different unit and a different
question. Nothing here licenses a statement about portfolio return.

**The window knob is a search, so it is counted.** `--from`/`--to` are refused closer than
`MIN_SESSIONS_BETWEEN` sessions apart (owner instruction, 2026-09-07), and every non-default window
is appended to `PR-016-windows.jsonl`. A study whose sample can be resliced until it looks good and
whose reslicings nobody counts is `data snooping` with a command-line flag
(`BACKTEST_PROTOCOL` §3).

**Registered diagnostics, reported and never read by §6** — the same device `PR-015` amendment A-1
used: the top FOUR by rank (which is what `risk.max_concurrent_positions` would actually take), and
the control's own signal DATES re-priced under the two-slot exit `PR-005` ran, which is what says
whether the ratified target bought anything. **Dates, not realised entries** - a position that runs
its full hold is still open on the next formation date and the entry never happens, where one the
target closed early frees its name in time. Amendment A-1 registers that and both counts are
reported.

    PYTHONPATH=$PWD/src python tools/run_pr016.py --data <store>
    PYTHONPATH=$PWD/src python tools/run_pr016.py --data <store> --from 2016-01-04 --to 2019-12-31
    python tools/run_pr016.py --report
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import BENCHMARK, DECILE, Candidate, select
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import Trade
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

# --- the ratified exit. Every one of these is a registry value, cited, and none is chosen here ---

#: `exit.atr_stop_multiple`, `assumed:DR-012`, ratified by the owner 2026-08-17.
ATR_PERIOD = 14
STOP_MULTIPLE = Decimal("2.0")

#: `exit.target_r_multiple`, `status: owner`, ruled 1R by the owner 2026-09-01 (`DR-029`).
#: THE POINT OF THE STUDY. `PR-005` and every study since ran without it because the harness had
#: no profit slot until `DR-042`.
TARGET_R = Decimal("1.0")

#: `exit.max_holding_period`, `assumed:DR-012`, reaffirmed by the owner 2026-08-31.
HOLD = 20

#: Sessions between entry dates for one name. Equal to the hold, so one instrument's trades never
#: overlap each other and a name cannot contribute two simultaneous observations of the same market.
STEP = HOLD

#: `rs.lookback`, ratified `owner` via `DR-030`. The live ranker's own window.
LOOKBACK = 126

#: The history floor, applied to EVERY arm so the control and the hypothesis draw from one pool.
#: The ranker needs `LOOKBACK`; the ATR needs `ATR_PERIOD`; the liquidity rule needs `min_history`.
#: This is the maximum of the three with room for the ATR to warm up inside the ranker's window.
HISTORY = 252

#: `DR-005`, ratified: 25 bps a side. `PR-005` charged 5 and predates the measurement.
SLIPPAGE_BPS = Decimal("25")
COMMISSION_PER_SHARE = Decimal("0.005")
STRESS_MULTIPLE = 3

#: `RISK_SPEC`: R is the position's own denominator. The dollar budget only decides share counts,
#: and every reported figure is in R, so this value cannot move a result.
RISK_PER_TRADE = Decimal(1000)

#: The IIS/OOS boundary. **Inherited from `PR-014` and `PR-015`, not chosen here** — a split point
#: picked today would be one picked after seeing this data. `PREREG_TEMPLATE` rule 7 asks what a
#: split buys; this one buys an untouched second window AND comparability with two studies that
#: already ran on the same boundary.
PRIMARY_END = date(2021, 12, 31)

#: Where the store's usable decade starts, and — not coincidentally — where `probe_alpaca_delisted`
#: found delisted coverage to begin. A future survivorship repair can reach exactly this far back,
#: so a window opening here will still be comparable after the repair lands.
WINDOW_START = date(2016, 1, 4)

#: Owner instruction, 2026-09-07: *"ne menshe 200 dney mezhdu datami"*. Trading sessions, not
#: calendar days — the sample is sessions and a calendar minimum would admit a 200-day window
#: holding 137 of them.
MIN_SESSIONS_BETWEEN = 200

BOOTSTRAP_SEED = 20260908
BOOTSTRAP_RESAMPLES = 10_000

#: Resampling unit: the ENTRY MONTH. Trades opened in the same month share one market, so the trade
#: is not the independent observation and an i.i.d. resample over trades would report an interval
#: several times too narrow. Kunsch (1989), an AUTHORED IMPORT (`AGENTS.md` §10.3).
#: Block THREE months ~ one quarter, the shortest span over which a regime is conventionally
#: treated as persistent. Fixed here, before any number exists.
BLOCK = 3

#: §8's power floor, registered before any number exists. Derived from `PR-005`'s own trade log:
#: the sd of monthly mean net R there is 0.5444R over 120 months, so 95% half-widths of ±0.10R
#: (120 clusters) to ±0.17R (40 clusters) are what this design can reach. An interval on the
#: DIFFERENCE wider than this could not have detected an effect worth trading, and a null read off
#: one is evidence of nothing.
POWER_FLOOR = Decimal("0.20")

#: §8's minimum detectable effect (`PREREG_TEMPLATE` rule 9, gate 44). Same prior, same arithmetic.
MINIMUM_DETECTABLE_EFFECT = Decimal("0.14")

MIN_TRADES = 200
MIN_MONTHS = 24

ARMS = ("unselected", "ranked")
DIAGNOSTICS = ("ranked_top4",)

#: `risk.max_concurrent_positions`, value 4, `status: owner`. Used ONLY by the diagnostic.
MAX_CONCURRENT = 4

RESULT = REPO / "docs" / "prereg" / "results" / "PR-016.json"
WINDOW_LOG = REPO / "docs" / "prereg" / "results" / "PR-016-windows.jsonl"

#: Where the ambiguous bars themselves are written - the (instrument, session) pairs on which the
#: tie-break decided the outcome. A COUNT cannot be checked against anything; the pairs can be
#: fetched at one-minute resolution and the true order measured, which is what `DR-042` §4a says is
#: owed before the ruling. Written beside the result and never inside it: there may be tens of
#: thousands, and a result file nobody can read is a result file nobody checks.
AMBIGUOUS_BARS = REPO / "docs" / "prereg" / "results" / "PR-016-ambiguous-bars.jsonl"

#: The QA stage's sample (`BACKTEST_PROTOCOL` §7), written for a second pass to reconstruct from
#: the stored evidence alone. §7 asks for "a sample of trades drawn from the run by a seeded,
#: recorded rule - not chosen by the person checking", and this is that rule.
#:
#: A SAMPLE and not the whole log, deliberately. The control arm alone carries on the order of
#: 10^5 trades and six series are simulated; the full log is tens of megabytes and would be a
#: committed artefact nobody opens. §7 asks for part of the sample, so this writes part of it -
#: stratified across arms so the control cannot swamp the arm the hypothesis is about.
TRADE_SAMPLE = REPO / "docs" / "prereg" / "results" / "PR-016-trades-sample.csv"
QA_SAMPLE_PER_ARM = 400
QA_SEED = 20260908

TRADE_COLUMNS = (
    "arm", "instrument_id", "signal_date", "entry_date", "exit_date", "entry_price", "stop_price",
    "exit_price", "shares", "initial_risk_per_share", "costs", "mfe", "mae", "exit_reason",
    "gross_r", "net_r", "holding_days",
)

#: `DR-042` §4a, owner ruling 2026-09-07 - *"Покажи долю, потом решу"*. The tie-break is UNRULED,
#: so every figure this tool produces carries an assumption the owner has not accepted. The label
#: travels in the result file and on the report, because labelling a number afterwards is not the
#: same as labelling it now.
PRELIMINARY = {
    "status": "PRELIMINARY - not a final result",
    "why": (
        "DR-042's tie-break is unruled. On a bar reaching both the stop and the target this run "
        "takes the STOP, which is the pessimistic reading and is not yet the owner's ruling. The "
        "owner ruled on 2026-09-07 that the measured share comes first (DR-042 §4a), so these "
        "figures stand until probe_ambiguous_bar.py reports it and the tie-break is settled."
    ),
    "direction": (
        "the assumption can only UNDERSTATE: every ambiguous bar recorded as a stop would "
        "otherwise have been a target. So the win rate and the mean net R here are lower bounds, "
        "and the size of the gap is exactly the ambiguous share."
    ),
    "settled_by": "docs/decisions/DR-042 §8, once tools/probe_ambiguous_bar.py has reported",
}


def atr_registry() -> ParameterRegistry:
    return ParameterRegistry({
        "atr.period": {"id": "atr.period", "value": ATR_PERIOD, "provenance": "assumed:DR-012",
                       "unit": "bars", "named_in": ["PR-016"]},
    })


@dataclass(frozen=True, slots=True)
class OnDates:
    """Fires on exactly the sessions the cross-sectional pass chose, and on no others.

    An `EntryTrigger` (`decision_logic.triggers`), so the engine's loop is untouched and its
    look-ahead guarantee is the same one `PR-005` runs under. The dates were computed from bars at
    or before each of them; this class only replays that decision, and it can see nothing else —
    it never reads `series` at all.

    A frozenset rather than a closure because a study has to RECORD what it ran, and a closure's
    `repr` says nothing.
    """

    dates: frozenset[date]

    def __call__(self, series: BarSeries, index: int) -> bool | None:
        return series.bars[index].session_date in self.dates


def window_sessions(calendar: list[date], start: date, end: date) -> list[date]:
    return [d for d in calendar if start <= d <= end]


def cluster_of(entry: date) -> str:
    """The resampling unit: the entry month, as `YYYY-MM`."""
    return f"{entry.year:04d}-{entry.month:02d}"


def totals_for(cluster: list[Decimal], statistic: str) -> tuple[float, int]:
    """One month reduced to `(numerator, count)`, which is all a resample of it ever needs.

    **This is what makes the bootstrap finish.** Both statistics here are ratios of two sums, so a
    resample's value is `sum(numerators) / sum(counts)` over the months it drew - it never has to
    look at a trade. The first cut of this file had no such function and `block_bootstrap` pooled
    the TRADES on every resample: with roughly 200,000 trades and 10,000 resamples that is 2e9
    `Decimal` additions per statistic, and 66 of them to run. Found 2026-09-07 by watching a run
    reach that phase and stop producing output; killed rather than waited out. The arithmetic is
    identical and the running time is O(months) instead of O(trades).
    """
    if statistic == "mean":
        return float(sum(cluster)), len(cluster)
    if statistic == "win_rate":
        return float(sum(1 for v in cluster if v > 0)), len(cluster)
    raise ValueError(f"unknown statistic {statistic!r}")


def block_bootstrap(
    clusters: list[list[Decimal]],
    statistic: str,
    block: int,
    seed: int,
    resamples: int,
) -> tuple[float, float, float] | None:
    """A 95% percentile interval for `statistic`, resampling CLUSTERS in moving blocks.

    A generalisation of `run_pr014.moving_block_bootstrap`, and generalised for a reason rather than
    for neatness: that one resamples a list of numbers and can therefore only bootstrap their mean.
    A win RATE is a ratio over a pooled set of trades, so the resample has to carry the trades and
    recompute the statistic — which is also the only way the mean and the rate come from the same
    resamples and can be reported side by side.

    Blocks of consecutive months are drawn with replacement and laid end to end until the resample
    holds as many months as the sample. Kunsch (1989), the same authored import.
    """
    n = len(clusters)
    if n < 2 or block < 1:
        return None
    block = min(block, n)
    rng = random.Random(seed)
    starts = n - block + 1
    reduced = [totals_for(c, statistic) for c in clusters]

    def value_of(drawn: list[tuple[float, int]]) -> float | None:
        count = sum(c for _, c in drawn)
        return None if count == 0 else sum(v for v, _ in drawn) / count

    observed = value_of(reduced)
    if observed is None:
        return None

    draws: list[float] = []
    for _ in range(resamples):
        pool: list[tuple[float, int]] = []
        taken = 0
        while taken < n:
            start = rng.randrange(starts)
            pool.extend(reduced[start:start + block])
            taken += block
        got = value_of(pool)
        if got is not None:
            draws.append(got)
    if len(draws) < resamples // 2:
        return None
    draws.sort()
    low = draws[int(0.025 * len(draws))]
    high = draws[min(int(0.975 * len(draws)), len(draws) - 1)]
    return observed, low, high


def paired_difference(
    left: dict[str, list[Decimal]], right: dict[str, list[Decimal]], statistic: str
) -> tuple[float, float, float] | None:
    """The arm-minus-control difference, resampled on the SAME months for both arms.

    Pairing is what makes the comparison mean anything: both arms trade the same decade, so a month
    that was bad for everything must be drawn for both or neither. Resampling them independently
    would add the two arms' market variance instead of cancelling it, and would widen the interval
    on the one quantity §6 actually reads.
    """
    months = sorted(set(left) & set(right))
    if len(months) < 2:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(months)
    block = min(BLOCK, n)
    starts = n - block + 1
    # The same reduction `block_bootstrap` uses, for the same reason. Indexed by POSITION, so one
    # drawn block picks the same months out of both arms - which is the whole point of pairing.
    left_totals = [totals_for(left[m], statistic) for m in months]
    right_totals = [totals_for(right[m], statistic) for m in months]

    def value_of(drawn: list[tuple[float, int]]) -> float | None:
        count = sum(c for _, c in drawn)
        return None if count == 0 else sum(v for v, _ in drawn) / count

    def difference(picked: list[int]) -> float | None:
        a = value_of([left_totals[i] for i in picked])
        b = value_of([right_totals[i] for i in picked])
        return None if a is None or b is None else a - b

    observed = difference(list(range(n)))
    if observed is None:
        return None
    draws: list[float] = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        picked: list[int] = []
        while len(picked) < n:
            start = rng.randrange(starts)
            picked.extend(range(start, min(start + block, n)))
        value = difference(picked)
        if value is not None:
            draws.append(value)
    if len(draws) < BOOTSTRAP_RESAMPLES // 2:
        return None
    draws.sort()
    return observed, draws[int(0.025 * len(draws))], draws[min(int(0.975 * len(draws)), len(draws) - 1)]


def percentiles(values: list[float]) -> dict[str, float]:
    if len(values) < 100:
        return {}
    ladder = statistics.quantiles(values, n=100)
    return {f"p{p}": round(ladder[p - 1], 4) for p in (1, 5, 10, 25, 50, 75, 90, 95, 99)}


def distribution(trades: list[Trade]) -> dict[str, Any]:
    """Win rate, mean R, and the shape of the tails. The three things the owner asked for.

    `break_even_win_rate` is the number that makes the win rate readable: at the realised payoff
    ratio, this is the share of winners the arm would have needed to come out flat. The comparison
    between it and the observed rate is the whole test, and it is arithmetic rather than a claim.
    """
    if not trades:
        return {"trades": 0}
    net = [float(t.net_r) for t in trades]
    wins = [v for v in net if v > 0]
    losses = [v for v in net if v <= 0]
    mean_win = statistics.mean(wins) if wins else 0.0
    mean_loss = statistics.mean(losses) if losses else 0.0
    payoff = abs(mean_win / mean_loss) if mean_loss else None
    sd = statistics.stdev(net) if len(net) > 1 else 0.0
    mean = statistics.mean(net)
    out: dict[str, Any] = {
        "trades": len(trades),
        "instruments": len({t.instrument_id for t in trades}),
        "win_rate": round(len(wins) / len(net), 4),
        "mean_net_r": round(mean, 4),
        "median_net_r": round(statistics.median(net), 4),
        "sd_net_r": round(sd, 4),
        "mean_win_r": round(mean_win, 4),
        "mean_loss_r": round(mean_loss, 4),
        "payoff_ratio": round(payoff, 4) if payoff else None,
        # 1 / (1 + payoff): the win rate at which mean net R is exactly zero.
        "break_even_win_rate": round(1 / (1 + payoff), 4) if payoff else None,
        "skew": round(sum((v - mean) ** 3 for v in net) / len(net) / sd ** 3, 4) if sd else None,
        "worst": round(min(net), 4),
        "best": round(max(net), 4),
        "mean_mfe_r": round(statistics.mean(float(t.mfe) for t in trades), 4),
        "mean_mae_r": round(statistics.mean(float(t.mae) for t in trades), 4),
        "gap_loss_share": round(sum(1 for t in trades if t.is_gap_loss) / len(trades), 4),
        "exit_reasons": dict(Counter(str(t.exit_reason) for t in trades).most_common()),
        "holding_days_median": statistics.median(t.holding_days for t in trades),
    }
    out["percentiles"] = percentiles(net)
    return out


def by_month(trades: list[Trade]) -> dict[str, list[Decimal]]:
    grouped: dict[str, list[Decimal]] = defaultdict(list)
    for trade in trades:
        grouped[cluster_of(trade.entry_date)].append(trade.net_r)
    return dict(grouped)


def qualifies(cell: dict[str, Any]) -> bool:
    """§6's sample rule: enough trades, enough months, or no verdict is offered at all."""
    return bool(cell.get("trades", 0) >= MIN_TRADES and cell.get("months", 0) >= MIN_MONTHS)


def underpowered(cell: dict[str, Any]) -> bool:
    """§8's floor, applied to the DIFFERENCE — the only quantity §6 reads."""
    interval = cell.get("difference_mean")
    if not interval:
        return True
    return bool((interval["high"] - interval["low"]) > float(POWER_FLOOR))


def cell_for(arm_trades: list[Trade], control_trades: list[Trade]) -> dict[str, Any]:
    cell = distribution(arm_trades)
    if not arm_trades:
        return cell
    months = by_month(arm_trades)
    cell["months"] = len(months)
    ordered = [months[m] for m in sorted(months)]
    for statistic, key in (("mean", "mean"), ("win_rate", "win_rate")):
        interval = block_bootstrap(ordered, statistic, BLOCK, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES)
        if interval:
            cell[f"{key}_interval"] = {"low": round(interval[1], 4), "high": round(interval[2], 4)}
    if control_trades is not arm_trades:
        for statistic, key in (("mean", "difference_mean"), ("win_rate", "difference_win_rate")):
            paired = paired_difference(months, by_month(control_trades), statistic)
            if paired:
                cell[key] = {"observed": round(paired[0], 4),
                             "low": round(paired[1], 4), "high": round(paired[2], 4)}
    return cell


def verdict_for(cells: dict[str, dict[str, Any]]) -> str:
    """§6, and it is the only place a verdict is formed.

    ACCEPT needs the paired difference in mean net R to exclude zero on BOTH windows, with the
    sample rule met and the power floor cleared on both. Anything else is INCONCLUSIVE, except the
    both-negative branch (`PREREG_TEMPLATE` rule 8) which is REJECT.
    """
    windows = ("in_sample", "out_of_sample")
    if not all(qualifies(cells.get(w, {})) for w in windows):
        return "inconclusive"
    if any(underpowered(cells[w]) for w in windows):
        return "inconclusive"
    excludes = [cells[w]["difference_mean"]["low"] > 0 for w in windows]
    if all(excludes):
        return "accept"
    if all(cells[w]["difference_mean"]["high"] < 0 for w in windows):
        return "reject"
    return "inconclusive"


def simulate(
    series: BarSeries,
    dates: frozenset[date],
    arm: str,
    exits: ExitPolicy,
    costs: CostModel,
    atr_series: Any,
) -> Any:
    config = BacktestConfig(arm=arm, exits=exits, costs=costs,
                            trigger=OnDates(dates), risk_per_trade=RISK_PER_TRADE)
    # The gate is True on every bar: this study has no regime filter, and a per-bar filter would be
    # a second selection rule the pre-registration never named.
    return run_arm(series, [True] * len(series.bars), atr_series, config)


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        raise SystemExit("the bar store is empty")

    series_by_name: dict[str, BarSeries] = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= HISTORY + HOLD + 1:
            series_by_name[name] = series
    store.close()
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to serve as the benchmark")

    benchmark = series_by_name[BENCHMARK]
    calendar = [b.session_date for b in benchmark.bars]
    start = date.fromisoformat(args.start) if args.start else WINDOW_START
    end = date.fromisoformat(args.end) if args.end else calendar[-1]
    sessions = window_sessions(calendar, start, end)
    if len(sessions) < MIN_SESSIONS_BETWEEN:
        raise SystemExit(
            f"the window {start} .. {end} holds {len(sessions)} sessions; "
            f"{MIN_SESSIONS_BETWEEN} is the registered minimum. A window narrow enough to be "
            f"chosen for its answer is not a window this tool will run."
        )

    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    # Formation dates start once the BENCHMARK has its own lookback, and inside the window.
    #
    # `LOOKBACK`, not `HISTORY`, and the difference is a YEAR of sample. `HISTORY` is what an
    # INSTRUMENT needs, and `DR-003`'s `min_history` (250) already enforces that inside
    # `_admitted_dates` for every name on every date. Applying it a second time to the benchmark's
    # calendar charges the same floor twice and throws away the first year of the window for
    # nothing. What the benchmark itself needs is `rs.lookback` - 126 sessions of relative-strength
    # history - and no more.
    #
    # Found 2026-09-07 by an arithmetic check that did not match: the run reported 113 formation
    # dates where 2,522 sessions at a 20-session step should give 126, and 13 is exactly 260
    # sessions. The header window would still have read `2016-01-04 .. 2026-09-04`.
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    formations = [d for d in sessions[::STEP] if d >= earliest and d <= sessions[-HOLD - 1]] \
        if len(sessions) > HOLD else []
    print(f"as_of {as_of.isoformat()}   instruments {len(series_by_name)}   "
          f"window {start} .. {end} ({len(sessions)} sessions)   "
          f"formation dates {len(formations)}")

    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}

    chosen: dict[str, dict[str, set[date]]] = {a: defaultdict(set) for a in (*ARMS, *DIAGNOSTICS)}
    thin = 0
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            thin += 1
            continue
        for candidate in pool:
            chosen["unselected"][candidate.instrument_id].add(session)
        ranker = ByMarketPathStrength(series=series_by_name, benchmark=benchmark, lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top:
            chosen["ranked"][name].add(session)
        for name in top[:MAX_CONCURRENT]:
            chosen["ranked_top4"][name].add(session)

    ratified = ExitPolicy(STOP_MULTIPLE, HOLD, TARGET_R)
    two_slot = ExitPolicy(STOP_MULTIPLE, HOLD)
    costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    registry = atr_registry()

    stressed = CostModel(COMMISSION_PER_SHARE * STRESS_MULTIPLE, SLIPPAGE_BPS * STRESS_MULTIPLE)
    series_names = [*ARMS, *DIAGNOSTICS, "unselected_two_slot",
                    *(f"{a}_3x" for a in ARMS)]
    trades: dict[str, list[Trade]] = {a: [] for a in series_names}
    ambiguous: Counter[str] = Counter()
    ambiguous_bars: list[dict[str, str]] = []
    skipped: Counter[str] = Counter()
    for count, (name, series) in enumerate(sorted(series_by_name.items()), start=1):
        needed = {a: chosen[a].get(name) for a in (*ARMS, *DIAGNOSTICS)}
        if not any(needed.values()):
            continue
        atr_series = atr_component.compute(series, registry)
        for arm, dates in needed.items():
            if not dates:
                continue
            armed = simulate(series, frozenset(dates), arm, ratified, costs, atr_series)
            trades[arm].extend(armed.trades)
            ambiguous[arm] += armed.ambiguous_exits
            ambiguous_bars.extend(
                {"instrument_id": t.instrument_id, "session_date": t.exit_date.isoformat(),
                 "arm": arm, "entry_price": str(t.entry_price), "stop": str(t.stop_price),
                 "target": str(t.entry_price + TARGET_R * t.initial_risk_per_share)}
                for t in armed.ambiguous_trades
            )
            skipped.update(armed.skipped)
            if arm in ARMS:
                # The registered cost perturbation. Re-simulated rather than re-priced: at 3x, the
                # entry fill is worse, so the stop sits somewhere else and different bars take it.
                # Subtracting a number afterwards would price a trade the arm never made.
                stress = simulate(series, frozenset(dates), f"{arm}_3x", ratified,
                                  stressed, atr_series)
                trades[f"{arm}_3x"].extend(stress.trades)
        if needed["unselected"]:
            control = simulate(series, frozenset(needed["unselected"]), "unselected_two_slot",
                               two_slot, costs, atr_series)
            trades["unselected_two_slot"].extend(control.trades)
        if count % 250 == 0:
            print(f"  simulated {count}/{len(series_by_name)} instruments")

    # The boundary belongs to ONE window. `PRIMARY_END` is the last in-sample session, so the
    # out-of-sample window opens the next day - without this, an entry dated exactly 2021-12-31
    # lands in both halves and the "untouched" window is not untouched.
    day_after = PRIMARY_END + timedelta(days=1)
    windows = {
        "full": (start, end),
        "in_sample": (start, min(PRIMARY_END, end)),
        "out_of_sample": (max(day_after, start), end),
    }
    result: dict[str, Any] = {
        "prereg": "PR-016",
        "trials": 2,
        "as_of": as_of.isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat(), "sessions": len(sessions)},
        "default_window": args.start is None and args.end is None,
        "exit": {"atr_period": ATR_PERIOD, "atr_stop_multiple": str(STOP_MULTIPLE),
                 "target_r_multiple": str(TARGET_R), "max_holding_period": HOLD,
                 "tie_break": "stop before target on an ambiguous bar (DR-042)"},
        "step": STEP, "lookback": LOOKBACK, "history_floor": HISTORY, "decile": str(DECILE),
        "benchmark": BENCHMARK,
        "slippage_bps_per_side": str(SLIPPAGE_BPS),
        "commission_per_share": str(COMMISSION_PER_SHARE),
        "bootstrap": {"unit": "entry month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                      "resamples": BOOTSTRAP_RESAMPLES},
        "power_floor": str(POWER_FLOOR),
        "minimum_detectable_effect": str(MINIMUM_DETECTABLE_EFFECT),
        "country": "USA",
        "split": {
            "in_sample": f"entries on or before {PRIMARY_END}",
            "out_of_sample": f"entries after {PRIMARY_END}",
            "buys": (
                "a second window this study's rule was never tuned on, at the boundary PR-014 and "
                "PR-015 already registered - so the boundary itself was not chosen after seeing "
                "these data, and the three studies are comparable at the same cut. The cost is "
                "roughly half the months in each window, which section 8's minimum is set against."
            ),
        },
        "perturbations": {
            "registered": ["cost_stress_1x", "cost_stress_3x"],
            "run": ["cost_stress_1x", "cost_stress_3x"],
            "note": (
                "re-SIMULATED at 3x, not re-priced: a worse entry fill moves the stop, so different "
                "bars take it. Run on both arms and every window, never only on the one section 6 "
                "reads."
            ),
        },
        "stress_multiple": STRESS_MULTIPLE,
        "instruments": len(series_by_name),
        "formation_dates": len(formations),
        "formations_skipped_for_a_thin_cross_section": thin,
        "preliminary": PRELIMINARY,
        "ambiguous_exits": dict(ambiguous),
        "ambiguous_bars_written_to": AMBIGUOUS_BARS.name,
        "skipped_signals": dict(skipped.most_common()),
        "survivorship": (
            "ABSENT. Every instrument with a decade of history in this store is still trading — "
            "measured 2026-09-07, 2,598 of 2,598 — because the store was built from today's "
            "directory backwards. Delisted names are missing entirely, so every arm here is "
            "optimistic by an amount this run cannot measure. `probe_alpaca_delisted.py` refuted "
            "the claim that no free source serves them (2026-09-05); repairing it is a separate "
            "change and this study does not pretend to have done it."
        ),
        "not_measured": [
            "dividends: the store is split-adjusted (measured) and NOT dividend-adjusted, so an "
            "ex-dividend gap is a real down-move a real stop would also see, and the cash it pays "
            "is missing from every return here. The bias is downward and its size is the universe's "
            "dividend yield over the holding period.",
            "the book: no cap, no sector limit, no correlation limit. This is a trade-level "
            "distribution and says nothing about portfolio return.",
            "borrow, halts, and partial fills.",
        ],
        "arms": {},
        "diagnostics": {},
    }

    for arm in series_names:
        cells: dict[str, Any] = {}
        for window, (first, last) in windows.items():
            selected = [t for t in trades[arm] if first <= t.entry_date <= last]
            control = [t for t in trades["unselected"] if first <= t.entry_date <= last]
            cells[window] = cell_for(selected, control if arm != "unselected" else selected)
        target = result["arms"] if arm in ARMS else result["diagnostics"]
        target[arm] = cells

    # **The requested window is not the measured one, and only the trades know which.** The owner
    # asked for at least ten years; the header window can say 2016-01-04 while the first entry sits
    # in 2017 because the store's own history begins later and a lookback runs on top of it. A
    # study that reports the window it was ASKED for rather than the one it MEASURED has answered a
    # question nobody can check.
    entered = sorted(t.entry_date for t in trades["unselected"])
    if entered:
        span_days = (entered[-1] - entered[0]).days
        result["measured_span"] = {
            "first_entry": entered[0].isoformat(),
            "last_entry": entered[-1].isoformat(),
            "years": round(span_days / 365.25, 2),
            "requested_window_years": round((end - start).days / 365.25, 2),
            "meets_the_ten_year_instruction": span_days / 365.25 >= 10.0,
        }
    result["verdict"] = verdict_for(result["arms"]["ranked"])
    result["qa_sample"] = write_qa_sample(trades)
    if ambiguous_bars:
        with AMBIGUOUS_BARS.open("w", encoding="utf-8") as handle:
            for row in ambiguous_bars:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {len(ambiguous_bars)} ambiguous bars to {AMBIGUOUS_BARS.name}")
    return result


def write_qa_sample(trades: dict[str, list[Trade]]) -> dict[str, Any]:
    """`BACKTEST_PROTOCOL` §7's sample, drawn by a seeded rule rather than by whoever checks.

    Stratified: the same number from each arm that has any. Drawing `n` at random from the pooled
    set would return almost nothing but the control, which carries two orders of magnitude more
    trades than the arm the hypothesis is about - and a QA pass that never re-checks the ranked arm
    has not re-checked the study.
    """
    rng = random.Random(QA_SEED)
    rows: list[dict[str, Any]] = []
    drawn_from: dict[str, int] = {}
    for arm in sorted(trades):
        pool = trades[arm]
        if not pool:
            continue
        take = rng.sample(pool, min(QA_SAMPLE_PER_ARM, len(pool)))
        drawn_from[arm] = len(take)
        for trade in take:
            rows.append({
                "arm": arm, "instrument_id": trade.instrument_id,
                "signal_date": trade.signal_date, "entry_date": trade.entry_date,
                "exit_date": trade.exit_date, "entry_price": trade.entry_price,
                "stop_price": trade.stop_price, "exit_price": trade.exit_price,
                "shares": trade.shares,
                "initial_risk_per_share": trade.initial_risk_per_share,
                "costs": trade.costs, "mfe": trade.mfe, "mae": trade.mae,
                "exit_reason": str(trade.exit_reason), "gross_r": trade.gross_r,
                "net_r": trade.net_r, "holding_days": trade.holding_days,
            })
    if not rows:
        return {"drawn": 0}
    with TRADE_SAMPLE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TRADE_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} trades to {TRADE_SAMPLE.name} for the QA stage")
    return {
        "file": TRADE_SAMPLE.name, "seed": QA_SEED, "per_arm": QA_SAMPLE_PER_ARM,
        "drawn": len(rows), "drawn_from": drawn_from,
        "rule": (
            "seeded and stratified across arms. BACKTEST_PROTOCOL §7 asks for an INDEPENDENT "
            "re-check of part of the sample - reconstructed from the stored evidence, not from "
            "this run's own output. Writing the sample is what makes that possible; it is not "
            "the check."
        ),
    }


def report(result: dict[str, Any]) -> None:
    exits = result["exit"]
    preliminary = result.get("preliminary")
    if preliminary:
        # First line, not a footnote. `DR-042` §4a: a number carrying an unruled assumption is not
        # a final number, and the label has to be where the number is read.
        print(f"*** {preliminary['status']} ***")
        print(f"    {preliminary['why']}")
        print(f"    {preliminary['direction']}\n")
    print(f"PR-016   as_of {result['as_of']}   verdict {result['verdict'].upper()}")
    print(f"  ratified exit: stop {exits['atr_stop_multiple']} x ATR({exits['atr_period']}), "
          f"target {exits['target_r_multiple']}R, time {exits['max_holding_period']} sessions")
    print(f"  window ASKED FOR {result['window']['start']} .. {result['window']['end']} "
          f"({result['window']['sessions']} sessions), {result['formation_dates']} formation dates")
    span = result.get("measured_span")
    if span:
        verdict = "MEETS" if span["meets_the_ten_year_instruction"] else "SHORT OF"
        print(f"  window MEASURED  {span['first_entry']} .. {span['last_entry']} "
              f"= {span['years']} years of entries - {verdict} the ten-year instruction")
    print(f"  {result['instruments']} instruments, {result['slippage_bps_per_side']} bps a side\n")

    head = (f"  {'arm':22} {'window':14} {'n':>7} {'win%':>6} {'b/e%':>6} {'meanR':>7} "
            f"{'medR':>7} {'p5':>7} {'p95':>7} {'payoff':>7}")
    print(head)
    for group in ("arms", "diagnostics"):
        for arm, cells in result[group].items():
            for window in ("full", "in_sample", "out_of_sample"):
                cell = cells.get(window, {})
                if not cell.get("trades"):
                    continue
                pct = cell.get("percentiles", {})
                # `distribution` refuses a percentile ladder below 100 trades rather than
                # interpolating one out of nine. Printing `nan` there reads as a defect; a dash
                # reads as what it is - a sample too small for that question.
                p5 = f"{pct['p5']:>+7.3f}" if "p5" in pct else f"{'-':>7}"
                p95 = f"{pct['p95']:>+7.3f}" if "p95" in pct else f"{'-':>7}"
                print(f"  {arm:22} {window:14} {cell['trades']:>7} "
                      f"{cell['win_rate'] * 100:>6.2f} "
                      f"{(cell['break_even_win_rate'] or 0) * 100:>6.2f} "
                      f"{cell['mean_net_r']:>+7.3f} {cell['median_net_r']:>+7.3f} "
                      f"{p5} {p95} "
                      f"{cell['payoff_ratio'] or 0:>7.3f}")
        print()

    print("  the only quantity section 6 reads: ranked minus unselected, paired on the same months")
    for window in ("full", "in_sample", "out_of_sample"):
        cell = result["arms"]["ranked"].get(window, {})
        diff = cell.get("difference_mean")
        rate = cell.get("difference_win_rate")
        if not diff:
            continue
        flag = "*" if diff["low"] > 0 or diff["high"] < 0 else " "
        line = (f"    {window:14} mean net R {diff['observed']:>+7.3f} "
                f"[{diff['low']:>+7.3f}, {diff['high']:>+7.3f}] {flag}")
        if rate:
            line += f"   win rate {rate['observed'] * 100:>+6.2f}pp"
        print(line)
        if (diff["high"] - diff["low"]) > float(POWER_FLOOR):
            print(f"    {'':14} interval wider than the {POWER_FLOOR} power floor "
                  f"— UNDERPOWERED, and a null read off it is evidence of nothing")

    print(f"\n  exit reasons, ranked arm, full window: "
          f"{result['arms']['ranked']['full'].get('exit_reasons')}")
    ambiguous = result["ambiguous_exits"]
    print(f"  ambiguous exit bars (both legs reachable, stop taken): {ambiguous}")
    for arm in ("unselected", "ranked"):
        total = result["arms"][arm]["full"].get("trades", 0)
        if total and arm in ambiguous:
            print(f"    {arm}: {ambiguous[arm]} of {total} trades = "
                  f"{ambiguous[arm] / total * 100:.2f}% - THE SIZE OF DR-042's UNRULED ASSUMPTION")
    print(f"  the bars themselves: {result.get('ambiguous_bars_written_to')}")
    print(f"\n  SURVIVORSHIP: {result['survivorship']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=REPO / "data",
                        help="directory holding bars.duckdb")
    parser.add_argument("--as-of", help="knowledge instant, ISO-8601; defaults to the latest")
    parser.add_argument("--from", dest="start",
                        help=f"first session of the window (default {WINDOW_START})")
    parser.add_argument("--to", dest="end", help="last session of the window (default: the latest)")
    parser.add_argument("--out", type=Path, default=RESULT, help="where to write the result JSON")
    parser.add_argument("--report", action="store_true",
                        help="print the report from an existing result file and exit")
    args = parser.parse_args()

    if args.report:
        report(json.loads(args.out.read_text(encoding="utf-8")))
        return 0

    result = build(args)
    if not result["default_window"]:
        # Every non-default window is a look at the data. Counted here so `trial_budget.py` can
        # read how many looks the study actually took, rather than how many it declared.
        record = {"ran_at": datetime.now().astimezone().isoformat(), "window": result["window"],
                  "as_of": result["as_of"], "verdict": result["verdict"],
                  "ranked_full_mean_net_r": result["arms"]["ranked"]["full"].get("mean_net_r")}
        with WINDOW_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"\nwindow appended to {WINDOW_LOG.name}: a non-default window is a look at the data")
    else:
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"\nwrote {args.out}")
    report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
