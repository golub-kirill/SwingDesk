"""`PR-024` - does `CARD-001` earn more entering near the close than at the open?

**What is already known, and why this is not a repeat.** `DR-040` §9 priced 6,176 paired entries at
09:30, 11:00 and 15:30 and found a net of +0.310% ±0.314 near the close. It said itself why that did
not settle anything (§9.2-§9.4): the cost saving was the difference between two MEDIAN spreads of the
whole admitted universe, applied to every entry, from a distribution with a p10 of 3 bps and a p90 of
114; the sample was not the names the card buys; and the answer flipped when dates were weighted
equally. This study changes exactly those three things and nothing else:

* **the population is `CARD-001`'s own** - `run_pr016`'s ranked rule, the top decile by the live
  `ByMarketPathStrength`, scored by the same streamed code;
* **every entry pays its OWN quoted spread**, read from the name's SIP quotes at the moment it
  entered (`tools/fetch_entry_quotes.py`, `market_data.quotes`);
* **every date carries the same number of names**, so weighting by entry and weighting by date
  agree up to exclusions, and §9.3's flip has nowhere to come from.

**Three arms, one entry.** Signal on session T, entry on T+1:

* `O` - the 09:30 minute's open, which is what every published study charged (`engine.py`);
* `C` - the minute five minutes before the close (15:55; 12:55 on a half day). **The verdict's arm**;
* `T` - 11:00. Counted and reported, never read by section 6: `DR-040` §9 flagged it.

**The entry day is walked from the fill, never from the open.** The engine checks exits on the
entry session itself, so a stop can be hit the day it is placed. For `C` the whole daily bar would
read prices printed before the order existed, so each arm reads only the regular-hours minutes at or
after its own fill; an entry-day bar reaching both legs is resolved from those minutes. From T+2 the
daily bars take over, exactly as the engine walks them, with `DR-042`'s minute tie-break.

**Nothing in the engine changes.** The walk lives here because the arms differ in their entry-day
window and in their per-entry costs, and because `run_arm`'s one-position-per-name rule would give
`C` a different set of entries than `O`. `--parity` proves the walk IS the engine: priced at the
daily open with `PR-016`'s costs, it must equal `run_arm` trade for trade.

    PYTHONPATH=$PWD/src python tools/run_pr024.py --data <store> --draw
    PYTHONPATH=$PWD/src python tools/run_pr024.py --data <store> --minutes <m> --quotes <q> --parity
    PYTHONPATH=$PWD/src python tools/run_pr024.py --data <store> --minutes <m> --quotes <q> \
        --list-ambiguous
    PYTHONPATH=$PWD/src python tools/run_pr024.py --data <store> --minutes <m> --quotes <q> \
        --minutes-as-of <t> --quotes-as-of <t> --resamples 10000
    python tools/run_pr024.py --report
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr014 import BENCHMARK, DECILE
from run_pr016 import (
    ATR_PERIOD,
    BLOCK,
    HISTORY,
    HOLD,
    LOOKBACK,
    RISK_PER_TRADE,
    STOP_MULTIPLE,
    TARGET_R,
    OnDates,
    atr_registry,
    block_bootstrap,
    cluster_of,
)
from run_pr016 import COMMISSION_PER_SHARE as PR016_COMMISSION
from run_pr016 import SLIPPAGE_BPS as PR016_SLIPPAGE
from run_pr021 import window_start
from stream_selection import Selection, score_instrument, select_streamed
from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.reference import ExchangeSession
from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.decision_logic.ranking import daily_returns
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.market_data.minutes import Minute, MinuteStore
from swingdesk.market_data.quotes import CLOSE, ELEVEN, OPEN, Quote, QuoteStore
from swingdesk.trade_management.exits import ExitDecision, ExitPolicy
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm
from swingdesk.validation.backtest.intraday import (
    MinuteTieBreak,
    TieBreak,
    Touch,
    break_tie,
    first_touch,
    regular_hours,
    reproduces,
    session_for,
)

# --- the arms ---------------------------------------------------------------------------------------

BASE, TIMED, LATE = "O", "T", "C"
ARMS = (BASE, TIMED, LATE)
PRIMARY = LATE
MOMENT = {BASE: OPEN, TIMED: ELEVEN, LATE: CLOSE}

#: Which quote window an EXIT is charged at. The exit's own session's quotes are not fetched - that
#: would be a request for every held day - so the name's ENTRY-session quotes stand in, matched to the
#: moment the exit happens: a gap through the stop fills at the open, an intraday stop or target at a
#: time nobody recorded (11:00 stands for "during the session"), a time exit at the close. The same
#: rule in every arm, so it cancels from the difference to first order; it sets each arm's own level,
#: which is what BOTH_NEGATIVE reads.
EXIT_MOMENT = {
    ExitReason.STOP_GAP: OPEN,
    ExitReason.STOP: ELEVEN,
    ExitReason.TARGET: ELEVEN,
    ExitReason.TIME: CLOSE,
    ExitReason.END_OF_DATA: CLOSE,
}

#: The fill minute must START within this long of the arm's instant, or the entry is unavailable for
#: that arm. A name that printed nothing for five minutes at the moment the order would have been sent
#: is a name this study cannot price, and borrowing a later print would price a different moment.
FILL_WITHIN = timedelta(minutes=5)

#: A quote window whose first quote arrives more than this after the requested instant describes a
#: later book, not the one the order met. Excluded, and counted.
QUOTE_MAX_AGE = timedelta(seconds=60)

#: The close arm's instant is this long before the session's own close.
LATE_OFFSET = timedelta(minutes=5)

# --- the sample ---------------------------------------------------------------------------------------

#: Registered BEFORE the draw, from `power_pr024.py` (`PR-024-power.json`): how many formation dates,
#: and how many of each date's selected names. Set by the power estimate, not by the answer. `None`
#: is EVERY formation session of the window - the only row the estimate found readable at the floor.
DATES: int | None = None
PER_DATE = 10
SAMPLE_SEED = 20260916

#: The last forty-eight months before the store's latest session, `AGENTS.md` §19's default, kept
#: rather than inherited from `PR-016`'s 2016 start: the question is what an order costs TODAY, and
#: `DR-040`'s own rows moved over the decade - the closing median from 1.9 to 4.0 bps between its
#: 2016 and 2026 rows, over an admitted universe that grew from 38 names to 3,999.
WINDOW_MONTHS = 48

#: The share of drawn entries that must be complete - minutes that reproduce the bar, a print at every
#: arm's instant, a two-sided fresh quote at every moment - for a verdict to be read at all. Below it,
#: the exclusions (halts, delayed openings, thin names: news days) are large enough to be the result.
MIN_COMPLETE_SHARE = 0.90
MIN_PAIRS = 1000
MIN_MONTHS = 24

# --- inference ----------------------------------------------------------------------------------------

BOOTSTRAP_SEED = 20260916
BOOTSTRAP_RESAMPLES = 10_000

#: Section 6's floor, as an END-TO-END width of the per-dollar difference: 0.30 percentage points, a
#: half-width of 0.15 - two thirds of the 22.5 bps a side `DR-040` measured between the open and the
#: close. An interval wider than this could not tell the saving the question is about from nothing.
POWER_FLOOR = 0.0030

#: The registered cost stress: the close arm at three times its own spread, the open arm at one, and
#: every exit at its own opening spread. A symmetric 3x would favour the close arm, whose spread is the
#: smaller one - the opposite of a stress.
STRESS_MULTIPLE = Decimal(3)

#: `exits_at_registry` - every exit at `DR-005`'s 25 bps, `PR-016`'s own convention.
REGISTRY_EXIT_BPS = Decimal(25)

RESULTS = REPO / "docs" / "prereg" / "results"
RESULT = RESULTS / "PR-024.json"
SAMPLE = RESULTS / "PR-024-sample.jsonl"
AMBIGUOUS = RESULTS / "PR-024-ambiguous-bars.jsonl"
QA_SAMPLE = RESULTS / "PR-024-qa-sample.csv"
QA_ROWS = 400

POLICY = ExitPolicy(STOP_MULTIPLE, HOLD, TARGET_R)


@dataclass(frozen=True, slots=True)
class Entry:
    """One drawn entry: the name, the session the card chose it on, and the session it entered."""

    instrument_id: str
    signal_date: date
    session_date: date

    def row(self) -> dict[str, str]:
        return {"instrument_id": self.instrument_id, "signal_date": self.signal_date.isoformat(),
                "session_date": self.session_date.isoformat()}

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> Entry:
        return cls(row["instrument_id"], date.fromisoformat(row["signal_date"]),
                   date.fromisoformat(row["session_date"]))


# --- the sample ---------------------------------------------------------------------------------------


def formation_dates(calendar: Sequence[date], start: date, end: date) -> list[date]:
    """Every session a formation may fall on: after the benchmark's own lookback, inside the window,
    and early enough that the hold fits before the store ends - `run_pr016`'s bounds at a step of 1."""
    if len(calendar) <= max(LOOKBACK, HOLD + 1):
        return []
    earliest = calendar[LOOKBACK]
    latest = calendar[-HOLD - 2]
    return [d for d in calendar if start <= d <= end and earliest <= d <= latest]


def window_formations(calendar: Sequence[date]) -> tuple[date, list[date]]:
    """The window's first day and every formation session in it, ending at the calendar's end."""
    start = window_start(calendar[-1], WINDOW_MONTHS)
    return start, formation_dates(calendar, start, calendar[-1])


def pick_dates(formations: Sequence[date], count: int | None, seed: int) -> list[date]:
    """`count` formation dates, seeded, in calendar order. All of them for `None`, or when there
    are fewer."""
    if count is None or count >= len(formations):
        return list(formations)
    return sorted(random.Random(seed).sample(list(formations), count))


def next_session(calendar: Sequence[date], day: date) -> date | None:
    """The session after `day` on the benchmark's calendar."""
    later = [d for d in calendar if d > day]
    return later[0] if later else None


def draw(selection: Selection, calendar: Sequence[date], dates: Iterable[date], per_date: int,
         seed: int) -> list[Entry]:
    """`per_date` of each date's selected names, drawn with a seed of its own.

    **Seeded per date, `seed + date.toordinal()`, so one date's draw never depends on another's.**
    Adding or dropping a date - a thin cross-section, a different window - moves nothing else in the
    sample, which is what lets the sample be re-derived from the registration alone.
    """
    by_date: dict[date, list[str]] = defaultdict(list)
    for name, chosen in selection.selected.items():
        for day in chosen:
            by_date[day].append(name)
    entries: list[Entry] = []
    for day in sorted(dates):
        names = sorted(by_date.get(day, []))
        if not names:
            continue
        entered = next_session(calendar, day)
        if entered is None:
            continue
        rng = random.Random(seed + day.toordinal())
        picked = names if len(names) <= per_date else sorted(rng.sample(names, per_date))
        entries.extend(Entry(name, day, entered) for name in picked)
    return entries


def frame(store: BarStore, as_of: datetime, dates: Sequence[date],
          benchmark: BarSeries) -> tuple[Selection, int]:
    """`CARD-001`'s selection on `dates`, scored one series at a time (`stream_selection`)."""
    benchmark_daily = daily_returns(benchmark)
    scores: dict[str, dict[date, Decimal]] = {}
    instruments = 0
    for name in sorted(store.instrument_ids(as_of)):
        series = (benchmark if name == BENCHMARK
                  else store.as_of(name, Interval.DAY, Series.RAW, as_of))
        if not series or len(series.bars) < HISTORY + HOLD + 1:
            continue
        instruments += 1
        got = score_instrument(series, list(dates), benchmark_daily, LOOKBACK)
        if got:
            scores[name] = got
    return select_streamed(scores, dates, DECILE), instruments


def write_sample(entries: Sequence[Entry], path: Path = SAMPLE) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry.row(), ensure_ascii=False) + "\n")


def read_sample(path: Path = SAMPLE) -> list[Entry]:
    return [Entry.from_row(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --- pricing ------------------------------------------------------------------------------------------


def fill_instant(session: ExchangeSession, moment: str) -> datetime:
    """The minute an arm's order meets the tape: the open, 11:00, or five minutes before the close."""
    if moment == OPEN:
        return session.open_time
    if moment == ELEVEN:
        return session.open_time.replace(hour=11, minute=0, second=0, microsecond=0)
    if moment == CLOSE:
        return session.close_time - LATE_OFFSET
    raise ValueError(f"no fill instant for {moment!r}")


def fill_minute(regular: Sequence[Minute], at: datetime,
                within: timedelta = FILL_WITHIN) -> Minute | None:
    """The first minute starting at or after `at`, if it starts within `within` of it."""
    for minute in sorted(regular, key=lambda m: m.at):
        if minute.at >= at:
            return minute if minute.at - at < within else None
    return None


def after_fill(regular: Sequence[Minute], fill: Minute) -> list[Minute]:
    """The session from the fill minute on - what the entry day can know once the order is in."""
    return [minute for minute in sorted(regular, key=lambda m: m.at) if minute.at >= fill.at]


def half_spread_bps(quotes: Sequence[Quote], requested_at: datetime,
                    max_age: timedelta = QUOTE_MAX_AGE) -> Decimal | None:
    """Half the median proportional spread of a window, in bps - `DR-040`'s per-side convention.

    `None` when the window's first quote is stale, or when no quote in it is two-sided. Crossed and
    locked books are dropped rather than read as zero: a locked market's spread is undefined, and a
    zero averaged in pulls the charge toward the flattering side (`measure_quoted_spread`).
    """
    if not quotes or quotes[0].at - requested_at > max_age:
        return None
    values = [(quote.ask - quote.bid) / ((quote.ask + quote.bid) / 2) * 10000
              for quote in quotes if quote.bid > 0 and quote.ask > quote.bid]
    if not values:
        return None
    return Decimal(str(statistics.median(values))) / 2


def cost(bps: Decimal) -> CostModel:
    """A study cost model: the spread only. Commission is zero (`DR-039`)."""
    return CostModel(Decimal(0), bps)


# --- the walk -------------------------------------------------------------------------------------------


def _day_bar(template: Bar, minutes: Sequence[Minute]) -> Bar:
    """The entry day as the order sees it: from the fill minute to the close."""
    return template.model_copy(update={
        "open": minutes[0].open,
        "high": max(m.high for m in minutes),
        "low": min(m.low for m in minutes),
        "close": minutes[-1].close,
    })


def _resolve_on_minutes(decision: ExitDecision, minutes: Sequence[Minute], stop: Decimal,
                        target: Decimal | None, counts: Counter[str]) -> ExitDecision:
    """An entry-day bar that reached both legs, answered by the post-fill minutes themselves."""
    if not decision.ambiguous or target is None:
        return decision
    touch = first_touch(minutes, stop, target)
    counts[f"entry_day_{touch.value}"] += 1
    if touch is Touch.TARGET:
        return ExitDecision(True, target, ExitReason.TARGET, ambiguous=True)
    return decision


def walk_entry(
    entry: Entry,
    bars: Sequence[Bar],
    atr_value: Decimal,
    quoted_entry: Decimal,
    entry_cost: CostModel,
    exit_cost: Callable[[ExitReason], CostModel],
    day_minutes: Sequence[Minute] | None,
    tie_break: TieBreak | None,
    counts: Counter[str],
    arm: str,
    anchor: Decimal | None = None,
    policy: ExitPolicy = POLICY,
) -> Trade | str:
    """One position, walked exactly as `engine.run_arm` walks it, from one arm's entry.

    `day_minutes` None reads the entry day's whole daily bar, which is the engine's own behaviour and
    what `--parity` uses; otherwise the entry day is the post-fill minutes. Returns the trade, or the
    engine's reason for not taking it.

    **`anchor` moves where the stop and target are placed, and nothing else.** The engine places them
    from the entry FILL, so a cheaper fill lowers the stop and the target with it, and a position that
    exits at either gives most of the saving back. The live bracket does not: its legs are priced in
    the evening, from the decision's own price (`DR-027` §3). With `anchor` the stop is
    `anchor - 2xATR` and the target one R above the anchor; R and the share count are still the
    position's own, `entry - stop`.

    **`policy` is the exit, and the ratified one unless a caller names another** - `PR-026` walks
    `PR-019`'s selected cell through the same code, so a difference between the two is the exit.
    """
    index = next((i for i, bar in enumerate(bars) if bar.session_date == entry.session_date), None)
    if index is None:
        return "entry_session_not_stored"
    entry_price = entry_cost.buy_fill(quoted_entry)
    placed_from = entry_price if anchor is None else anchor
    stop = policy.stop_for(placed_from, atr_value)
    if stop >= entry_price:
        return "stop_not_below_entry"
    if stop <= 0:
        return "stop_not_positive"
    risk = entry_price - stop
    shares = int(RISK_PER_TRADE / risk)
    if shares < 1:
        return "zero_shares"
    target = policy.target_for(placed_from, placed_from - stop)
    mfe = mae = Decimal(0)

    for i in range(index, len(bars) - 1):
        bar = bars[i]
        if i == index and day_minutes is not None:
            if not day_minutes:
                return "no_minutes_after_fill"
            seen = _day_bar(bar, day_minutes)
            decision = policy.evaluate(seen, stop, 0, target)
            decision = _resolve_on_minutes(decision, day_minutes, stop, target, counts)
        else:
            seen = bar
            decision = policy.evaluate(bar, stop, i - index, target)
            decision = break_tie(decision, tie_break, entry.instrument_id, bar, stop, target, counts)
        mfe = max(mfe, (seen.high - entry_price) / risk)
        mae = min(mae, (seen.low - entry_price) / risk)
        if decision.exited and decision.price is not None and decision.reason is not None:
            return _trade(entry, arm, bar, entry_price, stop, shares, risk, mfe, mae,
                          decision.price, decision.reason, entry_cost, exit_cost)
    last = bars[-1]
    return _trade(entry, arm, last, entry_price, stop, shares, risk, mfe, mae, last.close,
                  ExitReason.END_OF_DATA, entry_cost, exit_cost)


def _trade(entry: Entry, arm: str, bar: Bar, entry_price: Decimal, stop: Decimal, shares: int,
           risk: Decimal, mfe: Decimal, mae: Decimal, quoted_exit: Decimal, reason: ExitReason,
           entry_cost: CostModel, exit_cost: Callable[[ExitReason], CostModel]) -> Trade:
    """`engine.close_position`, with the exit charged at its own moment's cost."""
    return Trade(
        instrument_id=entry.instrument_id, arm=arm, signal_date=entry.signal_date,
        entry_date=entry.session_date, exit_date=bar.session_date, entry_price=entry_price,
        stop_price=stop, exit_price=exit_cost(reason).sell_fill(quoted_exit), shares=shares,
        initial_risk_per_share=risk, costs=entry_cost.commission(shares), mfe=mfe, mae=mae,
        exit_reason=reason,
    )


def per_dollar(trade: Trade) -> float:
    """Net return on the capital the position used. `CHARTER` A-003 §2's unit."""
    invested = trade.entry_price * trade.shares
    profit = (trade.exit_price - trade.entry_price) * trade.shares - trade.costs
    return float(profit / invested)


# --- parity ----------------------------------------------------------------------------------------------


def parity_trade(entry: Entry, series: BarSeries, atr_series: Any,
                 tie_break: TieBreak | None) -> tuple[Trade | str, Trade | None]:
    """This walk priced as `PR-016` priced it, beside the engine's own trade for the same signal."""
    engine_cost = CostModel(PR016_COMMISSION, PR016_SLIPPAGE)
    config = BacktestConfig(arm="parity", exits=POLICY, costs=engine_cost,
                            trigger=OnDates(frozenset({entry.signal_date})),
                            risk_per_trade=RISK_PER_TRADE, tie_break=tie_break)
    engine = run_arm(series, [True] * len(series.bars), atr_series, config)
    theirs = next((t for t in engine.trades if t.entry_date == entry.session_date), None)
    index = next(i for i, b in enumerate(series.bars) if b.session_date == entry.signal_date)
    atr_value = atr_series.observations[index].value
    if atr_value is None or atr_value <= 0:
        return "no_atr", theirs
    ours = walk_entry(entry, series.bars, atr_value, series.bars[index + 1].open, engine_cost,
                      lambda _reason: engine_cost, None, tie_break, Counter(), "parity")
    return ours, theirs


def same_trade(ours: Trade | str, theirs: Trade | None) -> bool:
    if isinstance(ours, str) or theirs is None:
        return isinstance(ours, str) and theirs is None
    return (ours.exit_date == theirs.exit_date and ours.exit_price == theirs.exit_price
            and ours.entry_price == theirs.entry_price and ours.shares == theirs.shares
            and ours.exit_reason == theirs.exit_reason and ours.costs == theirs.costs)


# --- one entry, every arm -------------------------------------------------------------------------------


@dataclass
class Priced:
    """What one entry produced: each arm's trade under each registered costing, or why not."""

    entry: Entry
    trades: dict[str, dict[str, Trade]]
    fills: dict[str, Decimal]
    spreads: dict[str, Decimal]


COSTINGS = ("net", "gross", "cost_adverse", "exits_at_registry", "anchored_stop")


def price_entry(
    entry: Entry,
    series: BarSeries,
    atr_value: Decimal,
    minutes: tuple[Minute, ...] | None,
    windows: Mapping[str, tuple[datetime, tuple[Quote, ...]] | None],
    session: ExchangeSession | None,
    tie_break: TieBreak | None,
    counts: Counter[str],
) -> Priced | str:
    """Every arm and costing for one entry, or the first reason the entry is incomplete."""
    if minutes is None:
        return "minutes_unavailable"
    if session is None:
        return "not_a_session"
    regular = regular_hours(minutes, session)
    bar = next((b for b in series.bars if b.session_date == entry.session_date), None)
    if bar is None:
        return "entry_session_not_stored"
    if not reproduces(regular, bar):
        return "minutes_mismatch"

    spreads: dict[str, Decimal] = {}
    for moment in (OPEN, ELEVEN, CLOSE):
        window = windows.get(moment)
        if window is None:
            return "quotes_unavailable"
        requested_at, quotes = window
        half = half_spread_bps(quotes, requested_at)
        if half is None:
            return "no_fresh_two_sided_quote"
        spreads[moment] = half

    fills: dict[str, Minute] = {}
    for arm in ARMS:
        found = fill_minute(regular, fill_instant(session, MOMENT[arm]))
        if found is None:
            return "no_print_at_the_moment"
        fills[arm] = found

    signal_bar = next((b for b in series.bars if b.session_date == entry.signal_date), None)
    if signal_bar is None:
        return "signal_session_not_stored"

    trades: dict[str, dict[str, Trade]] = {costing: {} for costing in COSTINGS}
    for arm in ARMS:
        day = after_fill(regular, fills[arm])
        quoted = fills[arm].open
        own = spreads[MOMENT[arm]]
        stressed = own * STRESS_MULTIPLE if arm == LATE else own
        def at_moment(reason: ExitReason) -> CostModel:
            return cost(spreads[EXIT_MOMENT[reason]])

        plans: dict[str, tuple[Decimal, Callable[[ExitReason], CostModel], Decimal | None]] = {
            "net": (own, at_moment, None),
            "gross": (Decimal(0), lambda _reason: cost(Decimal(0)), None),
            "cost_adverse": (stressed, lambda _reason: cost(spreads[OPEN]), None),
            "exits_at_registry": (own, lambda _reason: cost(REGISTRY_EXIT_BPS), None),
            "anchored_stop": (own, at_moment, signal_bar.close),
        }
        for costing, (entry_bps, exits, anchor) in plans.items():
            walked = walk_entry(entry, series.bars, atr_value, quoted, cost(entry_bps), exits, day,
                                tie_break, counts if costing == "net" else Counter(), arm,
                                anchor=anchor)
            if isinstance(walked, str):
                return walked
            trades[costing][arm] = walked
    return Priced(entry, trades, {arm: fills[arm].open for arm in ARMS},
                  {moment: spreads[moment] for moment in spreads})


# --- inference ----------------------------------------------------------------------------------------------


def _clustered(values_by_key: Mapping[str, list[Decimal]], resamples: int,
               seed: int) -> dict[str, float]:
    clusters = [values_by_key[key] for key in sorted(values_by_key)]
    got = block_bootstrap(clusters, "mean", BLOCK, seed, resamples)
    if got is None:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "width": math.nan}
    estimate, lo, hi = got
    return {"estimate": estimate, "lo": lo, "hi": hi, "width": hi - lo}


def paired_cell(priced: Sequence[Priced], arm: str, drawn: int, resamples: int,
                seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """`arm` minus `O`, per entry, and everything section 6 reads about it."""
    by_month: dict[str, dict[str, list[Decimal]]] = defaultdict(lambda: defaultdict(list))
    by_date: dict[date, list[Decimal]] = defaultdict(list)
    by_instrument: dict[str, list[Decimal]] = defaultdict(list)
    level: dict[str, list[Decimal]] = defaultdict(list)
    for p in priced:
        month = cluster_of(p.entry.session_date)
        differences = {costing: Decimal(str(per_dollar(p.trades[costing][arm])
                                            - per_dollar(p.trades[costing][BASE])))
                       for costing in COSTINGS}
        for costing, value in differences.items():
            by_month[costing][month].append(value)
        r_difference = p.trades["net"][arm].net_r - p.trades["net"][BASE].net_r
        by_month["net_r"][month].append(r_difference)
        by_date[p.entry.session_date].append(differences["net"])
        by_instrument[p.entry.instrument_id].append(differences["net"])
        level[month].append(Decimal(str(per_dollar(p.trades["net"][arm]))))

    date_months: dict[str, list[Decimal]] = defaultdict(list)
    for day, values in by_date.items():
        date_months[cluster_of(day)].append(sum(values, Decimal(0)) / len(values))

    readings = {costing: _clustered(by_month[costing], resamples, seed) for costing in COSTINGS}
    gross, net = readings["gross"]["estimate"], readings["net"]["estimate"]
    return {
        "arm": arm,
        "pairs": len(priced),
        "drawn": drawn,
        "complete_share": len(priced) / drawn if drawn else 0.0,
        "months": len(by_month["net"]),
        "difference": readings["net"],
        "difference_r": _clustered(by_month["net_r"], resamples, seed),
        "gross_part": readings["gross"],
        "cost_part": net - gross if not (math.isnan(net) or math.isnan(gross)) else math.nan,
        "cost_adverse": readings["cost_adverse"],
        "exits_at_registry": readings["exits_at_registry"],
        "anchored_stop": readings["anchored_stop"],
        "date_weighted": _clustered(date_months, resamples, seed),
        "instrument_clustered": _instrument_interval(by_instrument, resamples, seed),
        "level": _clustered(level, resamples, seed),
    }


def _instrument_interval(by_instrument: Mapping[str, list[Decimal]], resamples: int,
                         seed: int) -> dict[str, float]:
    """An i.i.d. bootstrap over NAMES - reported, never read. A name's own intraday profile is a
    second dependence the month clusters do not price (`DR-040` §9.2)."""
    names = sorted(by_instrument)
    if len(names) < 2:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "width": math.nan}
    totals = [(float(sum(by_instrument[n], Decimal(0))), len(by_instrument[n])) for n in names]
    count = sum(c for _, c in totals)
    estimate = sum(v for v, _ in totals) / count
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        drawn = [totals[rng.randrange(len(totals))] for _ in totals]
        draws.append(sum(v for v, _ in drawn) / sum(c for _, c in drawn))
    draws.sort()
    lo, hi = draws[int(0.025 * len(draws))], draws[min(int(0.975 * len(draws)), len(draws) - 1)]
    return {"estimate": estimate, "lo": lo, "hi": hi, "width": hi - lo}


def _spread_summary(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        return {"entries": 0}
    ordered = sorted(values)

    def at(share: float) -> float:
        return ordered[min(int(share * len(ordered)), len(ordered) - 1)]

    return {"entries": len(ordered), "p10": at(0.10), "p50": at(0.50), "p90": at(0.90),
            "average": statistics.fmean(ordered)}


def diagnostics(priced: Sequence[Priced]) -> dict[str, Any]:
    """Section 5a's printed-never-read readings: each arm's exits and the spread it paid to enter."""
    out: dict[str, Any] = {}
    for arm in ARMS:
        reasons = Counter(p.trades["net"][arm].exit_reason.value for p in priced)
        entry_day = sum(1 for p in priced
                        if p.trades["net"][arm].exit_date == p.entry.session_date)
        out[arm] = {
            "exit_reasons": dict(reasons.most_common()),
            "exited_on_the_entry_session": entry_day,
            "entry_half_spread_bps": _spread_summary([float(p.spreads[MOMENT[arm]])
                                                      for p in priced]),
        }
    return out


def branch_for(cell: Mapping[str, Any]) -> str:
    """Section 6, in its order. The report's `verdict` is `TOKEN[branch]`.

    **The floor gates NULL and nothing else**, as in `run_pr021`: an interval that excludes zero
    answers the sign whatever its width; what a wide one cannot do is say there is no effect.
    """
    difference = cell["difference"]
    if (cell["complete_share"] < MIN_COMPLETE_SHARE or cell["pairs"] < MIN_PAIRS
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


TOKEN = {"ACCEPT": "accept", "REJECT": "reject", "NULL": "inconclusive",
         "BOTH_NEGATIVE": "inconclusive", "COST_FRAGILE": "inconclusive",
         "INCONCLUSIVE": "inconclusive", "REFUSED": "refused"}


# --- the run ----------------------------------------------------------------------------------------------


def atr_at(atr_series: Any, series: BarSeries, day: date) -> Decimal | None:
    index = next((i for i, b in enumerate(series.bars) if b.session_date == day), None)
    if index is None:
        return None
    value = atr_series.observations[index].value
    return value if value is not None and value > 0 else None


def read_instant(text: str | None, fallback: datetime | None) -> datetime:
    if text:
        return datetime.fromisoformat(text)
    if fallback is None:
        raise SystemExit("no knowledge instant to read at")
    return fallback


def price_sample(args: argparse.Namespace, entries: Sequence[Entry],
                 collect_ambiguous: bool = False) -> tuple[list[Priced], Counter[str], Counter[str],
                                                           list[dict[str, str]], dict[str, str]]:
    """Walk every drawn entry through every arm. The heavy step, one series in memory at a time."""
    bars = BarStore(args.data / "bars.duckdb")
    as_of = read_instant(args.as_of, bars.latest_knowledge_time())
    minutes_store = MinuteStore(args.minutes)
    quotes_store = QuoteStore(args.quotes)
    minutes_as_of = read_instant(args.minutes_as_of, datetime.max.replace(tzinfo=as_of.tzinfo))
    quotes_as_of = read_instant(args.quotes_as_of, datetime.max.replace(tzinfo=as_of.tzinfo))
    registry = atr_registry()

    recorded: list[dict[str, str]] = []

    def recording(instrument_id: str, bar: Any, _stop: Decimal, _target: Decimal) -> Touch:
        recorded.append({"instrument_id": instrument_id,
                         "session_date": bar.session_date.isoformat()})
        return Touch.UNAVAILABLE

    tie_break: TieBreak = (recording if collect_ambiguous
                           else MinuteTieBreak(minutes_store, minutes_as_of))
    priced: list[Priced] = []
    excluded: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    by_name: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        by_name[entry.instrument_id].append(entry)
    for count, name in enumerate(sorted(by_name), start=1):
        series = bars.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series is None or not series.bars:
            excluded["series_unavailable"] += len(by_name[name])
            continue
        atr_series = atr_component.compute(series, registry)
        for entry in by_name[name]:
            atr_value = atr_at(atr_series, series, entry.signal_date)
            if atr_value is None:
                excluded["no_atr"] += 1
                continue
            windows = {moment: quotes_store.window(name, entry.session_date, moment, quotes_as_of)
                       for moment in (OPEN, ELEVEN, CLOSE)}
            got = price_entry(entry, series, atr_value,
                              minutes_store.session(name, entry.session_date, minutes_as_of),
                              windows, session_for(name, entry.session_date), tie_break, counts)
            if isinstance(got, str):
                excluded[got] += 1
            else:
                priced.append(got)
        if count % 200 == 0:
            print(f"  priced {count}/{len(by_name)} instruments", flush=True)
    bars.close()
    minutes_store.close()
    quotes_store.close()
    instants = {"bars": as_of.isoformat(), "minutes": minutes_as_of.isoformat(),
                "quotes": quotes_as_of.isoformat()}
    return priced, excluded, counts, recorded, instants


def build(args: argparse.Namespace) -> dict[str, Any]:
    entries = read_sample(args.sample)
    priced, excluded, counts, _, instants = price_sample(args, entries)
    registered = args.resamples == BOOTSTRAP_RESAMPLES
    cells = {arm: paired_cell(priced, arm, len(entries), args.resamples) for arm in (LATE, TIMED)}
    branch = branch_for(cells[PRIMARY]) if registered else "SMOKE"
    sessions = sorted(p.entry.session_date for p in priced)
    span = ((sessions[-1] - sessions[0]).days / 365.25) if sessions else 0.0
    payload: dict[str, Any] = {
        "prereg": "PR-024",
        "trials": 2,
        "verdict": TOKEN[branch] if registered else "smoke",
        "branch": branch,
        "country": "USA",
        "as_of": instants,
        "measured_span": {
            "first_session": sessions[0].isoformat() if sessions else None,
            "last_session": sessions[-1].isoformat() if sessions else None,
            "years": round(span, 2),
        },
        "split": {
            "registered": "none - the sample is one draw, and the arms are paired within it",
            "buys": (
                "nothing a split could buy here: the question is a price moved within one session, "
                "not a rule tuned on one half. Pairing removes the market level; the month-clustered "
                "interval and the date-equal reading are the protections a split would have given, "
                "and PR-016's own split already tested the rule the entries come from."
            ),
        },
        "perturbations": {
            "registered": ["cost_adverse", "exits_at_registry", "anchored_stop",
                           "instrument_clustered", "date_weighted"],
            "run": ["cost_adverse", "exits_at_registry", "anchored_stop", "instrument_clustered",
                    "date_weighted"],
        },
        "registered_settings": {
            "dates": DATES if DATES is not None else "every formation session",
            "per_date": PER_DATE, "sample_seed": SAMPLE_SEED,
            "bootstrap": {"unit": "entry month", "block": BLOCK, "seed": BOOTSTRAP_SEED,
                          "resamples": args.resamples},
            "power_floor": POWER_FLOOR, "min_complete_share": MIN_COMPLETE_SHARE,
            "min_pairs": MIN_PAIRS, "min_months": MIN_MONTHS,
            "fill_within_seconds": FILL_WITHIN.total_seconds(),
            "quote_max_age_seconds": QUOTE_MAX_AGE.total_seconds(),
            "stress_multiple": str(STRESS_MULTIPLE), "registry_exit_bps": str(REGISTRY_EXIT_BPS),
            "exit": {"atr_period": ATR_PERIOD, "atr_stop_multiple": str(STOP_MULTIPLE),
                     "target_r_multiple": str(TARGET_R), "max_holding_period": HOLD},
            "decile": str(DECILE), "lookback": LOOKBACK, "benchmark": BENCHMARK,
            "window_months": WINDOW_MONTHS,
        },
        "sample": {"drawn": len(entries), "complete": len(priced),
                   "excluded": dict(excluded.most_common())},
        "tie_breaks": dict(counts.most_common()),
        "diagnostics": diagnostics(priced),
        "cells": cells,
    }
    if registered:
        write_qa(priced)
    return payload


def write_qa(priced: Sequence[Priced]) -> None:
    """`BACKTEST_PROTOCOL` §7's sample: seeded, every arm of each drawn entry side by side."""
    rng = random.Random(BOOTSTRAP_SEED)
    chosen = sorted(rng.sample(list(priced), min(QA_ROWS, len(priced))),
                    key=lambda p: (p.entry.session_date, p.entry.instrument_id))
    columns = ["instrument_id", "signal_date", "session_date", "arm", "fill", "spread_bps",
               "entry_price", "stop_price", "exit_date", "exit_price", "exit_reason", "shares",
               "net_r", "per_dollar"]
    with QA_SAMPLE.open("w", encoding="utf-8") as handle:
        handle.write(",".join(columns) + "\n")
        for p in chosen:
            for arm in ARMS:
                t = p.trades["net"][arm]
                handle.write(",".join(str(v) for v in (
                    p.entry.instrument_id, p.entry.signal_date, p.entry.session_date, arm,
                    p.fills[arm], p.spreads[MOMENT[arm]], t.entry_price, t.stop_price,
                    t.exit_date, t.exit_price, t.exit_reason.value, t.shares, t.net_r,
                    round(per_dollar(t), 6))) + "\n")


def run_draw(args: argparse.Namespace) -> int:
    """Register the sample: dates and names, nothing known after each signal."""
    store = BarStore(args.data / "bars.duckdb")
    as_of = read_instant(args.as_of, store.latest_knowledge_time())
    benchmark = store.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
    if benchmark is None:
        raise SystemExit(f"{BENCHMARK} is not in the store")
    calendar = [b.session_date for b in benchmark.bars]
    start, formations = window_formations(calendar)
    dates = pick_dates(formations, args.dates, SAMPLE_SEED)
    print(f"as_of {as_of.isoformat()}   window {start} .. {calendar[-1]}   "
          f"formation sessions {len(formations)}   drawn {len(dates)}", flush=True)
    selection, instruments = frame(store, as_of, dates, benchmark)
    store.close()
    entries = draw(selection, calendar, dates, args.per_date, SAMPLE_SEED)
    write_sample(entries, args.sample)
    print(f"instruments scored {instruments}   thin dates {selection.thin}   "
          f"entries written {len(entries)} -> {args.sample}")
    return 0


def run_parity(args: argparse.Namespace) -> int:
    """The walk against the engine, entry by entry, at `PR-016`'s pricing."""
    store = BarStore(args.data / "bars.duckdb")
    as_of = read_instant(args.as_of, store.latest_knowledge_time())
    minutes_store = MinuteStore(args.minutes)
    tie_break = MinuteTieBreak(minutes_store, read_instant(args.minutes_as_of,
                                                       datetime.max.replace(tzinfo=as_of.tzinfo)))
    registry = atr_registry()
    checked = mismatched = 0
    by_name: dict[str, list[Entry]] = defaultdict(list)
    for entry in read_sample(args.sample)[: args.parity_limit]:
        by_name[entry.instrument_id].append(entry)
    for name in sorted(by_name):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series is None:
            continue
        atr_series = atr_component.compute(series, registry)
        for entry in by_name[name]:
            ours, theirs = parity_trade(entry, series, atr_series, tie_break)
            checked += 1
            if not same_trade(ours, theirs):
                mismatched += 1
                print(f"  MISMATCH {name} {entry.session_date}: ours={ours} engine={theirs}")
    store.close()
    minutes_store.close()
    print(f"parity: {checked} entries checked, {mismatched} differ from the engine")
    return 1 if mismatched else 0


def run_list_ambiguous(args: argparse.Namespace) -> int:
    """The later sessions the walk would ask the tie-break about - identifiers only, no outcomes."""
    _, _, _, recorded, _ = price_sample(args, read_sample(args.sample), collect_ambiguous=True)
    unique = sorted({(r["instrument_id"], r["session_date"]) for r in recorded})
    with AMBIGUOUS.open("w", encoding="utf-8") as handle:
        for name, day in unique:
            handle.write(json.dumps({"instrument_id": name, "session_date": day}) + "\n")
    print(f"wrote {len(unique)} ambiguous sessions to {AMBIGUOUS.name}")
    return 0


def _fmt(reading: Mapping[str, float], scale: float = 100.0, digits: int = 3) -> str:
    if math.isnan(reading["estimate"]):
        return "n/a"
    return (f"{reading['estimate'] * scale:+.{digits}f} "
            f"[{reading['lo'] * scale:+.{digits}f}, {reading['hi'] * scale:+.{digits}f}]")


def report(payload: Mapping[str, Any]) -> None:
    print(f"PR-024   verdict {payload['verdict']}   branch {payload['branch']}")
    sample = payload["sample"]
    print(f"  entries drawn {sample['drawn']}   complete {sample['complete']}   "
          f"excluded {sample['excluded']}")
    for arm, cell in payload["cells"].items():
        print(f"  {arm} - O   pairs {cell['pairs']}   months {cell['months']}   "
              f"complete {cell['complete_share']:.1%}")
        print(f"    net per dollar (%)        {_fmt(cell['difference'])}")
        print(f"    gross part (%)            {_fmt(cell['gross_part'])}")
        print(f"    net in R                  {_fmt(cell['difference_r'], scale=1.0)}")
        print(f"    cost-adverse (%)          {_fmt(cell['cost_adverse'])}")
        print(f"    exits at registry (%)     {_fmt(cell['exits_at_registry'])}")
        print(f"    stops from the decision (%) {_fmt(cell['anchored_stop'])}")
        print(f"    date-weighted (%)         {_fmt(cell['date_weighted'])}")
        print(f"    instrument-clustered (%)  {_fmt(cell['instrument_clustered'])}")
        print(f"    arm's own level (%)       {_fmt(cell['level'])}")
    for arm, seen in payload.get("diagnostics", {}).items():
        spread = seen["entry_half_spread_bps"]
        typical = (f"p10 {spread['p10']:.2f}  p50 {spread['p50']:.2f}  p90 {spread['p90']:.2f}"
                   if spread.get("entries") else "none priced")
        print(f"  {arm} exits {seen['exit_reasons']}   same day {seen['exited_on_the_entry_session']}"
              f"   entry half-spread bps {typical}")


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    raise TypeError(f"{type(value).__name__} is not serialisable")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, help="the directory holding bars.duckdb")
    parser.add_argument("--minutes", type=Path, help="the minute store")
    parser.add_argument("--quotes", type=Path, help="the quote store")
    parser.add_argument("--sample", type=Path, default=SAMPLE, help="the drawn entries (JSON lines)")
    parser.add_argument("--as-of", help="the bar store's knowledge instant (default: latest)")
    parser.add_argument("--minutes-as-of", help="the minute store's knowledge instant")
    parser.add_argument("--quotes-as-of", help="the quote store's knowledge instant")
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES,
                        help="bootstrap resamples; anything but the registered 10000 is a smoke run")
    parser.add_argument("--dates", type=int, default=DATES,
                        help="formation dates to draw (default: every one in the window)")
    parser.add_argument("--per-date", type=int, default=PER_DATE, help="names per date")
    parser.add_argument("--parity-limit", type=int, default=None,
                        help="check only the first N sampled entries in --parity")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--draw", action="store_true", help="draw and write the sample, then stop")
    mode.add_argument("--parity", action="store_true", help="check the walk against the engine")
    mode.add_argument("--list-ambiguous", action="store_true",
                      help="write the later sessions the tie-break needs, then stop")
    mode.add_argument("--report", action="store_true", help="print the stored result")
    args = parser.parse_args(argv)

    if args.report:
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    if args.data is None:
        parser.error("--data is required")
    if args.draw:
        return run_draw(args)
    if args.minutes is None:
        parser.error("--minutes is required")
    if args.parity:
        return run_parity(args)
    if args.quotes is None:
        parser.error("--quotes is required")
    if args.list_ambiguous:
        return run_list_ambiguous(args)
    payload = build(args)
    if payload["verdict"] != "smoke":
        RESULT.write_text(json.dumps(payload, indent=2, default=_default) + "\n", encoding="utf-8")
    report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
