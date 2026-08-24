"""A backtest with a BOOK: many instruments, one capital constraint, a date axis.

`run_arm` walks ONE instrument with unlimited capital. That is the right shape for a time-series
question - "does this rule work on this name?" - and the wrong shape for every question about a
portfolio. `CARD-001` is a portfolio rule ("hold the strongest N of the universe at once") and
could not be simulated at all until this existed; the symptom was visible from the other side long
before it was named, in `PR-005`'s base slice holding a median of 20 positions at once against a
ratified cap of 4.

**The axis is the difference.** `run_arm` iterates an instrument's bars; this iterates SESSIONS, and
asks every instrument what it wants on each one. That is what makes candidates compete, and
competition is what a portfolio rule is about.

Four rules this module exists to obey, each from a document rather than from taste:

  1. **A ranking never runs before the gates and never re-admits what they rejected**
     (`ALLOCATION_SPEC` section 1). Ordering is applied to the surviving set only, so admissibility
     is decided per instrument exactly as `run_arm` decides it, and only then does anything compete.
  2. **`deferred` is a separate outcome from `Skip`** (`ALLOCATION_SPEC` section 5). A candidate that
     lost on capacity should return tomorrow at the top of the list; one that failed a gate should
     not. Collapsing them would report a capital constraint as a rule rejection.
  3. **Open positions before candidates** (`CHECKLIST_SPEC` section 4). A slot freed by this
     session's exit is available to this session's candidates - refusing it would make capacity
     depend on the order the code happens to run in.
  4. **Truncation IS a ranking, so it is done explicitly by an injected rule.** Falling back to any
     order the system happens to have is an alphabetical bias silently applied
     (`ALLOCATION_SPEC` section 4, choice 1). `Ranking` has no default for the same reason
     `BacktestConfig.trigger` has none.

**No look-ahead, and the loop shape is what enforces it.** On session `D` an instrument is read at
its own bar for `D` and no further; entry fills at that instrument's NEXT bar's open. Instruments
are not required to share a calendar - a halted name simply has no bar for `D` and cannot be a
candidate that session.

**What this module does NOT do.** It does not read the registry, it does not apply the sector or
correlation caps, and it does not size in currency. `BacktestConfig` pins what a study ran under
(the same contract `run_arm` keeps), and the caps this file enforces are the two that are countable
without classification data: position count and open risk in R. Sector and correlation need
point-in-time classification a backtest does not have, and admitting them here would let a cap
appear to have been tested when it was not.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from swingdesk.contracts.market import Bar, BarSeries
from swingdesk.contracts.observation import ObservationSeries
from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.validation.backtest.engine import BacktestConfig, Skipped, close_position


@dataclass(frozen=True, slots=True)
class Candidate:
    """One instrument that passed every per-instrument test on one session, before competing.

    Carries the numbers the ranking may read and nothing else. A ranking that could reach back into
    the bars could look forward, and this type is the boundary that stops it.
    """

    instrument_id: str
    session_date: date
    index: int
    close: Decimal
    entry_price: Decimal
    stop: Decimal
    risk_per_share: Decimal
    shares: int


class Ranking(Protocol):
    """Orders candidates competing for a scarce slot. Most preferred first.

    **A total order is mandatory.** Two candidates that compare equal must still be separated, or
    the book depends on dictionary order and a re-run is not a re-run (`DETERMINISM_SPEC` 3.2).
    `by_instrument_id` is the deterministic reference implementation and is deliberately NOT a
    default - see rule 4 in the module docstring.
    """

    def __call__(self, candidates: list[Candidate]) -> list[Candidate]: ...


def by_instrument_id(candidates: list[Candidate]) -> list[Candidate]:
    """Alphabetical. Deterministic, and an honest stand-in for nothing.

    Exists so a test can exercise capacity without smuggling in a preference, and so a study that
    has no ranking rule has to NAME this one rather than get it by default. It is a real bias -
    `AAPL` over `ZTS` for no reason anybody chose - and a study using it is measuring capacity, not
    selection.
    """
    return sorted(candidates, key=lambda candidate: candidate.instrument_id)


@dataclass(frozen=True, slots=True)
class Capacity:
    """What bounds the book. Both are enforced; `DR-006` section 1 explains why both exist.

    Open risk and position count are the same constraint counted two ways while every position
    risks 1R, and they stop being the same the moment sizing rounds shares down. Enforcing only one
    would leave the other silently unchecked the first time they diverge.
    """

    max_positions: int
    max_open_risk: Decimal


@dataclass
class BookResult:
    """What the book did, including what it wanted to do and could not.

    `deferred` is the field this type exists for. It counts candidates that passed every gate and
    lost on capacity - not a rejection, and not a trade. Folding it into `skipped` would report a
    capital constraint as a rule verdict, and folding it into nothing at all would make a
    capacity-bound strategy look more selective than it is.
    """

    trades: list[Trade] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)
    signals: int = 0
    unevaluable_bars: int = 0
    deferred: int = 0
    sessions: int = 0
    max_concurrent: int = 0

    @property
    def net_r_values(self) -> list[Decimal]:
        return [trade.net_r for trade in self.trades]


def _index_by_session(series: BarSeries) -> dict[date, int]:
    return {bar.session_date: index for index, bar in enumerate(series.bars)}


def _open_risk(positions: dict[str, dict[str, Any]], risk_per_trade: Decimal) -> Decimal:
    """Open risk in R: each position's planned dollar risk over the per-trade budget.

    Not simply `len(positions)`. Shares round DOWN, so a position whose stop distance divides the
    budget badly risks meaningfully less than 1R, and counting it as a whole R would refuse a
    candidate the book could actually carry.
    """
    total = Decimal(0)
    for position in positions.values():
        total += (position["risk_per_share"] * position["shares"]) / risk_per_trade
    return total


def run_book(
    series_by_instrument: dict[str, BarSeries],
    gates: dict[str, list[bool | None]],
    atr_by_instrument: dict[str, ObservationSeries],
    config: BacktestConfig,
    capacity: Capacity,
    ranking: Ranking,
) -> BookResult:
    """Walk every session once, letting instruments compete for a bounded number of slots.

    `gates` and `atr_by_instrument` align with each instrument's own bars, one entry per bar, the
    same contract `run_arm` enforces.
    """
    for instrument_id, series in series_by_instrument.items():
        gate = gates.get(instrument_id)
        atr = atr_by_instrument.get(instrument_id)
        if gate is None or atr is None:
            raise ValueError(f"{instrument_id}: needs both a gate and an ATR series")
        if len(series.bars) != len(gate) or len(series.bars) != len(atr.observations):
            raise ValueError(
                f"{instrument_id}: gate and ATR must align with the bars, one entry per bar"
            )

    result = BookResult()
    indices = {i: _index_by_session(s) for i, s in series_by_instrument.items()}
    sessions = sorted({bar.session_date for s in series_by_instrument.values() for bar in s.bars})
    positions: dict[str, dict[str, Any]] = {}

    for session in sessions:
        result.sessions += 1

        # --- rule 3: open positions before candidates. A slot freed today is available today.
        for instrument_id in sorted(positions):
            position = positions[instrument_id]
            index = indices[instrument_id].get(session)
            if index is None:
                continue  # no bar for this name today; the position is carried, not evaluated
            bar = series_by_instrument[instrument_id].bars[index]
            held = index - position["entry_index"]
            decision = config.exits.evaluate(bar, position["stop"], held)

            high_r = (bar.high - position["entry_price"]) / position["risk_per_share"]
            low_r = (bar.low - position["entry_price"]) / position["risk_per_share"]
            position["mfe"] = max(position["mfe"], high_r)
            position["mae"] = min(position["mae"], low_r)

            if decision.exited and decision.price is not None and decision.reason is not None:
                result.trades.append(
                    close_position(position, bar, decision.price, decision.reason, config)
                )
                del positions[instrument_id]

        # --- rule 1: admissibility per instrument, decided exactly as run_arm decides it
        candidates: list[Candidate] = []
        for instrument_id in sorted(series_by_instrument):
            series = series_by_instrument[instrument_id]
            index = indices[instrument_id].get(session)
            if index is None or index + 1 >= len(series.bars):
                continue  # no bar today, or no next bar to fill on

            verdict = config.trigger(series, index)
            if verdict is None:
                result.unevaluable_bars += 1
                continue
            if instrument_id in positions:
                if verdict is True and gates[instrument_id][index] is True:
                    result.skipped[Skipped.POSITION_OPEN] += 1
                continue
            if verdict is not True or gates[instrument_id][index] is not True:
                continue

            result.signals += 1

            atr_value = atr_by_instrument[instrument_id].observations[index].value
            if atr_value is None or atr_value <= 0:
                result.skipped[Skipped.NO_ATR] += 1
                continue

            entry_bar = series.bars[index + 1]
            entry_price = config.costs.buy_fill(entry_bar.open)
            stop = config.exits.stop_for(entry_price, atr_value)
            if stop >= entry_price:
                result.skipped[Skipped.STOP_NOT_BELOW_ENTRY] += 1
                continue

            risk_per_share = entry_price - stop
            shares = int(config.risk_per_trade / risk_per_share)
            if shares < 1:
                result.skipped[Skipped.ZERO_SHARES] += 1
                continue

            candidates.append(
                Candidate(
                    instrument_id=instrument_id,
                    session_date=session,
                    index=index,
                    close=series.bars[index].close,
                    entry_price=entry_price,
                    stop=stop,
                    risk_per_share=risk_per_share,
                    shares=shares,
                )
            )

        # --- rules 2 and 4: rank the survivors, fill what fits, COUNT what did not
        for candidate in ranking(candidates):
            room_by_count = len(positions) < capacity.max_positions
            would_add = (candidate.risk_per_share * candidate.shares) / config.risk_per_trade
            room_by_risk = (
                _open_risk(positions, config.risk_per_trade) + would_add
            ) <= capacity.max_open_risk
            if not (room_by_count and room_by_risk):
                result.deferred += 1
                continue

            series = series_by_instrument[candidate.instrument_id]
            positions[candidate.instrument_id] = {
                "instrument_id": candidate.instrument_id,
                "signal_date": candidate.session_date,
                "entry_index": candidate.index + 1,
                "entry_date": series.bars[candidate.index + 1].session_date,
                "entry_price": candidate.entry_price,
                "stop": candidate.stop,
                "risk_per_share": candidate.risk_per_share,
                "shares": candidate.shares,
                "mfe": Decimal(0),
                "mae": Decimal(0),
            }

        result.max_concurrent = max(result.max_concurrent, len(positions))

    # --- the window ended holding. Closed at the last bar each name has and FLAGGED, never dropped:
    #     open positions at the end of a window are not randomly distributed.
    for instrument_id in sorted(positions):
        last: Bar = series_by_instrument[instrument_id].bars[-1]
        result.trades.append(
            close_position(
                positions[instrument_id], last, last.close, ExitReason.END_OF_DATA, config
            )
        )

    result.trades.sort(key=lambda trade: (trade.entry_date, trade.instrument_id))
    return result


__all__ = [
    "BookResult",
    "Candidate",
    "Capacity",
    "Ranking",
    "by_instrument_id",
    "run_book",
]
