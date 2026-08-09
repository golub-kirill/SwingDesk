"""The bar-by-bar engine. One instrument, one arm, one pass.

BACKTEST_PROTOCOL's `Bar-by-bar` stage: hide future candles, decisions only from available data.

That is enforced by the loop's shape rather than by care. At index `i` the engine may read
`bars[:i+1]` and observation values at `i`; entry happens at `bars[i+1].open`. There is no path
through this function that reads a bar it has not reached, because the only index it ever forms is
`i + 1` for the entry fill and the loop stops one short of the end.

The `Skips` stage is the other one this file owns: skipped signals are counted with a reason, never
dropped. A signal discarded silently is a survivorship filter applied to the signal set.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from swingdesk.contracts.market import Bar, BarSeries
from swingdesk.contracts.observation import ObservationSeries
from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest.costs import CostModel


class Skipped(StrEnum):
    """Why a triggered signal produced no trade. Counted, never discarded.

    `NO_NEXT_BAR` is reserved and structurally unreachable: the loop stops one bar short of the end,
    so a signal on the final bar is never generated rather than generated and refused. Kept in the
    enum because the reason is real and the loop shape is what makes it moot - if the loop ever runs
    to the last bar, this is the counter it owes.
    """

    NO_ATR = "no_atr"                    # ATR had not warmed up at the signal bar
    NO_NEXT_BAR = "no_next_bar"          # signal on the last bar; nothing to enter on
    POSITION_OPEN = "position_open"      # already in a trade on this instrument
    STOP_NOT_BELOW_ENTRY = "stop_ge_entry"  # a gap up put the fill at or below the stop
    ZERO_SHARES = "zero_shares"          # risk budget bought nothing


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Everything the engine needs, all of it pinned by the study.

    Nothing here is read from the registry. PR-005 fixes these values before the run and records
    them with the result, so the study cannot change meaning when a parameter is ratified later.
    """

    arm: str
    exits: ExitPolicy
    costs: CostModel
    risk_per_trade: Decimal = Decimal(1000)
    trigger_lookback: int = 20


@dataclass
class ArmResult:
    """One arm's trades, plus what it refused to trade and why.

    `unevaluable_bars` is deliberately not a `Skipped` reason. Those count SIGNALS that produced no
    trade; this counts BARS on which the trigger could not be evaluated at all, for want of a
    lookback window. Folding the two together would report an unanswerable bar as a rejected signal,
    which is the UNKNOWN-becomes-FALSE collapse `RULE_SPEC.md` §4 forbids.
    """

    arm: str
    trades: list[Trade] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)
    signals: int = 0
    unevaluable_bars: int = 0

    @property
    def net_r_values(self) -> list[Decimal]:
        return [trade.net_r for trade in self.trades]

    def merge(self, other: ArmResult) -> None:
        self.trades.extend(other.trades)
        self.skipped.update(other.skipped)
        self.signals += other.signals
        self.unevaluable_bars += other.unevaluable_bars


def breakout_high(series: BarSeries, index: int, lookback: int) -> Decimal | None:
    """Highest high of the `lookback` sessions BEFORE `index`.

    Excludes the current bar deliberately: a breakout compared against a window that includes the
    breaking bar can never fire, and one that includes it in the maximum is comparing a value to
    itself.
    """
    if index < lookback:
        return None
    return max(bar.high for bar in series.bars[index - lookback: index])


def run_arm(
    series: BarSeries,
    gate: list[bool | None],
    atr: ObservationSeries,
    config: BacktestConfig,
) -> ArmResult:
    """Walk one instrument for one arm.

    `gate` is the arm's trend verdict per bar - True, False or None for "could not answer". A None
    gate does not trade: it is not a rejection, and PR-005 treats it the same way PR-001 did, as an
    absence of an answer rather than a negative one.
    """
    result = ArmResult(arm=config.arm)
    bars = series.bars
    if len(bars) != len(gate) or len(bars) != len(atr.observations):
        raise ValueError("gate and ATR series must align with the bars, one entry per bar")

    position: dict[str, Any] | None = None

    for index in range(len(bars) - 1):
        bar = bars[index]

        # The trigger is evaluated on every bar, including bars spent holding. A signal that could
        # not be acted on is an EXCLUSION from the trade set, and an unrecorded exclusion is a
        # survivorship filter applied to the signal set regardless of intent (Appendix J, Skips stage).
        threshold = breakout_high(series, index, config.trigger_lookback)
        triggered = threshold is not None and bar.close > threshold

        # --- manage an open position first (CHECKLIST_SPEC 4: open positions before candidates)
        if position is not None:
            if triggered and gate[index] is True:
                # It would have been a signal. One position per instrument is a real constraint,
                # and a strategy that fires often while already positioned looks more selective
                # than it is unless this is counted.
                result.skipped[Skipped.POSITION_OPEN] += 1
            held = index - position["entry_index"]
            decision = config.exits.evaluate(bar, position["stop"], held)

            high_r = (bar.high - position["entry_price"]) / position["risk_per_share"]
            low_r = (bar.low - position["entry_price"]) / position["risk_per_share"]
            position["mfe"] = max(position["mfe"], high_r)
            position["mae"] = min(position["mae"], low_r)

            if decision.exited and decision.price is not None and decision.reason is not None:
                result.trades.append(_close(position, bar, decision.price, decision.reason, config))
                position = None
            continue

        # --- look for a new signal
        if threshold is None:
            # No lookback window yet. NOT a rejection - the rule had nothing to answer with, and
            # collapsing it into "did not trigger" removes these bars from the denominator without
            # saying so. The first `trigger_lookback` bars of every instrument land here.
            result.unevaluable_bars += 1
            continue
        if not triggered:
            continue
        if gate[index] is not True:
            continue

        result.signals += 1

        atr_value = atr.observations[index].value
        if atr_value is None or atr_value <= 0:
            result.skipped[Skipped.NO_ATR] += 1
            continue

        entry_bar = bars[index + 1]
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

        position = {
            "instrument_id": series.instrument_id,
            "signal_date": bar.session_date,
            "entry_index": index + 1,
            "entry_date": entry_bar.session_date,
            "entry_price": entry_price,
            "stop": stop,
            "risk_per_share": risk_per_share,
            "shares": shares,
            "mfe": Decimal(0),
            "mae": Decimal(0),
        }

    if position is not None:
        # The window ended with the position open. Closed at the last close and flagged, never
        # dropped - a dropped open position is a silently removed outcome, and open positions at
        # the end of a window are not randomly distributed.
        last = bars[-1]
        result.trades.append(_close(position, last, last.close, ExitReason.END_OF_DATA, config))

    return result


def _close(position: dict[str, Any], bar: Bar, quoted: Decimal, reason: ExitReason,
           config: BacktestConfig) -> Trade:
    exit_price = config.costs.sell_fill(quoted)
    return Trade(
        instrument_id=position["instrument_id"],
        arm=config.arm,
        signal_date=position["signal_date"],
        entry_date=position["entry_date"],
        exit_date=bar.session_date,
        entry_price=position["entry_price"],
        stop_price=position["stop"],
        exit_price=exit_price,
        shares=position["shares"],
        initial_risk_per_share=position["risk_per_share"],
        costs=config.costs.commission(position["shares"]),
        mfe=position["mfe"],
        mae=position["mae"],
        exit_reason=reason,
    )
