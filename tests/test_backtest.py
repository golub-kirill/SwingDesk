"""The harness, on constructed series where the right answer is arithmetic.

The look-ahead tests come first because look-ahead is the failure that produces a beautiful result
and passes every test that is not specifically looking for it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.observation import Observation, ObservationSeries
from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.validation.backtest import CostModel, ExitPolicy
from swingdesk.validation.backtest.engine import (
    BacktestConfig,
    Skipped,
    breakout_high,
    run_arm,
)

UTC = UTC
KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
FREE = CostModel(commission_per_share=Decimal(0), slippage_bps=Decimal(0))


def _series(rows: list[tuple[str, str, str, str]]) -> BarSeries:
    """rows are (open, high, low, close)."""
    bars = []
    for offset, (o, h, low, c) in enumerate(rows):
        session = date(2025, 1, 6) + timedelta(days=offset)
        bars.append(
            Bar(
                instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session,
                open=Decimal(o), high=Decimal(h), low=Decimal(low), close=Decimal(c),
                volume=1_000_000, knowledge_time=KNOWN,
            )
        )
    return BarSeries(
        instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
        knowledge_time=KNOWN, bars=tuple(bars),
    )


def _atr(series: BarSeries, value: str | None) -> ObservationSeries:
    return ObservationSeries(
        component="M18-T0280-v5.0", component_version=1, instrument_id="TEST.1",
        units="price units", parameters=(), validation_status="Not Applicable",
        knowledge_time=KNOWN,
        observations=tuple(
            Observation(
                component="M18-T0280-v5.0", component_version=1, instrument_id="TEST.1",
                event_time=bar.event_time,
                value=None if value is None else Decimal(value),
                units="price units", knowledge_time=KNOWN,
            )
            for bar in series.bars
        ),
    )


def _config(**kwargs) -> BacktestConfig:
    defaults = dict(
        arm="TEST",
        exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20),
        costs=FREE,
        risk_per_trade=Decimal(1000),
        trigger_lookback=3,
    )
    defaults.update(kwargs)
    return BacktestConfig(**defaults)


def _flat(count: int, price: str = "100") -> list[tuple[str, str, str, str]]:
    return [(price, price, price, price)] * count


# --------------------------------------------------------------- look-ahead

def test_entry_is_the_next_session_never_the_signal_bar() -> None:
    """A decision made on bar T executes at T+1 or it is look-ahead."""
    rows = _flat(3) + [("100", "110", "100", "110")] + [("105", "112", "104", "111")] + _flat(5)
    series = _series(rows)
    gate = [True] * len(rows)

    result = run_arm(series, gate, _atr(series, "2"), _config())

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.signal_date == series.bars[3].session_date
    assert trade.entry_date == series.bars[4].session_date
    assert trade.entry_price == series.bars[4].open


def test_breakout_window_excludes_the_breaking_bar() -> None:
    """A window that includes the current bar compares its high to itself and never fires."""
    series = _series([("10", "12", "9", "11"), ("10", "15", "9", "14"), ("10", "11", "9", "10")])
    assert breakout_high(series, 2, 2) == Decimal("15")
    assert breakout_high(series, 1, 2) is None, "not enough history yet"


def test_a_signal_on_the_last_bar_produces_no_trade() -> None:
    """There is no next session to enter on, and inventing one is look-ahead."""
    rows = _flat(3) + [("100", "110", "100", "110")]
    series = _series(rows)
    result = run_arm(series, [True] * len(rows), _atr(series, "2"), _config())
    assert result.trades == []


# --------------------------------------------------------------- exits

def test_gap_through_the_stop_fills_at_the_open_not_the_stop() -> None:
    """The loss recorded is the ACTUAL loss.

    Assuming every stopped trade loses exactly 1R is the single most common way a backtest
    flatters itself, and it is wrong by the most on the instruments that gap.
    """
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]     # 3: signal
        + [("110", "112", "109", "111")]     # 4: entry at 110, stop 110 - 2*2 = 106
        + [("100", "101", "99", "100")]      # 5: opens at 100, far below the stop
        + _flat(3)
    )
    series = _series(rows)
    result = run_arm(series, [True] * len(rows), _atr(series, "2"), _config())

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.STOP_GAP
    assert trade.is_gap_loss
    assert trade.exit_price == Decimal("100")
    assert trade.gross_r == (Decimal("100") - Decimal("110")) / Decimal("4")
    assert trade.gross_r < Decimal("-2"), "a gap loses more than the planned 1R"


def test_stop_touched_intraday_fills_at_the_stop() -> None:
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]
        + [("110", "112", "109", "111")]     # entry 110, stop 106
        + [("110", "111", "105", "108")]     # low pierces 106
        + _flat(3)
    )
    series = _series(rows)
    trade = run_arm(series, [True] * len(rows), _atr(series, "2"), _config()).trades[0]

    assert trade.exit_reason is ExitReason.STOP
    assert trade.exit_price == Decimal("106")
    assert trade.gross_r == Decimal(-1), "a clean stop is exactly -1R gross"


def test_protective_exit_is_checked_before_the_time_exit() -> None:
    """A bar that both breaks the stop and completes the holding period is a stop-out.

    The other order would silently convert some losses into time exits at the close, which is
    usually a better price.
    """
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]
        + [("110", "112", "109", "111")]     # entry index 4
        + [("110", "111", "105", "109")]     # index 5: breaks the stop AND holding == 1
        + _flat(3)
    )
    series = _series(rows)
    config = _config(exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=1))
    trade = run_arm(series, [True] * len(rows), _atr(series, "2"), config).trades[0]
    assert trade.exit_reason is ExitReason.STOP


def test_time_exit_closes_at_the_close() -> None:
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]
        + [("110", "112", "109", "111")]
        + [("111", "113", "110", "112")]
        + [("112", "114", "111", "113")]
        + _flat(3)
    )
    series = _series(rows)
    config = _config(exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=2))
    trade = run_arm(series, [True] * len(rows), _atr(series, "2"), config).trades[0]
    assert trade.exit_reason is ExitReason.TIME
    assert trade.exit_price == Decimal("113")


def test_open_position_at_the_end_is_recorded_not_dropped() -> None:
    """Positions still open when the window ends are not randomly distributed."""
    rows = _flat(3) + [("100", "110", "100", "110")] + [("110", "112", "109", "111")] * 3
    series = _series(rows)
    config = _config(exits=ExitPolicy(atr_stop_multiple=Decimal(5), max_holding_bars=99))
    result = run_arm(series, [True] * len(rows), _atr(series, "2"), config)

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason is ExitReason.END_OF_DATA


# --------------------------------------------------------------- gating and refusals

def test_an_undecided_gate_does_not_trade() -> None:
    """None is not False, and it is not True either. Same rule PR-001 used."""
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(4)
    series = _series(rows)
    assert run_arm(series, [None] * len(rows), _atr(series, "2"), _config()).trades == []
    assert run_arm(series, [False] * len(rows), _atr(series, "2"), _config()).trades == []
    assert run_arm(series, [True] * len(rows), _atr(series, "2"), _config()).trades != []


def test_a_signal_without_atr_is_skipped_with_a_reason() -> None:
    """Counted, never discarded. A silently dropped signal is a filter nobody declared."""
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(4)
    series = _series(rows)
    result = run_arm(series, [True] * len(rows), _atr(series, None), _config())

    assert result.trades == []
    assert result.signals == 1
    assert result.skipped[Skipped.NO_ATR] == 1


def test_no_second_entry_while_a_position_is_open() -> None:
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]
        + [("110", "112", "109", "111")]
        + [("111", "120", "110", "119")]     # would trigger again
        + [("119", "121", "118", "120")]
        + _flat(3)
    )
    series = _series(rows)
    config = _config(exits=ExitPolicy(atr_stop_multiple=Decimal(5), max_holding_bars=99))
    result = run_arm(series, [True] * len(rows), _atr(series, "2"), config)
    assert len(result.trades) == 1


def test_misaligned_inputs_raise_rather_than_silently_shift() -> None:
    """A gate off by one bar is a look-ahead bug that produces plausible numbers."""
    rows = _flat(5)
    series = _series(rows)
    with pytest.raises(ValueError, match="one entry per bar"):
        run_arm(series, [True] * 3, _atr(series, "2"), _config())


# --------------------------------------------------------------- costs and R

def test_costs_are_charged_not_mentioned() -> None:
    """Appendix J says Net R. Gross with costs in a footnote is how a loser looks profitable."""
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]
        + [("110", "112", "109", "111")]
        + [("110", "111", "105", "108")]
        + _flat(3)
    )
    series = _series(rows)
    costly = CostModel(commission_per_share=Decimal("0.01"), slippage_bps=Decimal(10))
    trade = run_arm(series, [True] * len(rows), _atr(series, "2"), _config(costs=costly)).trades[0]

    assert trade.costs > 0
    assert trade.net_r < trade.gross_r


def test_r_denominator_is_the_initial_planned_risk() -> None:
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]
        + [("110", "112", "109", "111")]
        + [("111", "118", "110", "117")]
        + _flat(3)
    )
    series = _series(rows)
    config = _config(exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=1))
    trade = run_arm(series, [True] * len(rows), _atr(series, "2"), config).trades[0]

    assert trade.initial_risk_per_share == Decimal(4)
    assert trade.gross_r == (trade.exit_price - trade.entry_price) / Decimal(4)


def test_mfe_and_mae_are_measured_in_r_from_the_fill() -> None:
    """Excursions include the exit bar - the position was open during it."""
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]
        + [("110", "112", "109", "111")]     # entry 110, risk 4, stop 106
        + [("111", "118", "108", "112")]     # high 118 -> +2R, low 108 -> -0.5R, time exit here
        + _flat(3)
    )
    series = _series(rows)
    config = _config(exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=1))
    trade = run_arm(series, [True] * len(rows), _atr(series, "2"), config).trades[0]

    assert trade.exit_reason is ExitReason.TIME
    assert trade.mfe == Decimal(2)
    assert trade.mae == Decimal("-0.5")


def test_the_exit_bar_counts_toward_the_excursions() -> None:
    """A gap-out bar's low is part of the trade's adverse excursion, not excluded from it.

    Written after a fixture of mine assumed otherwise: the trailing flat bars sat below the stop,
    the trade gapped out on one of them, and MAE correctly reflected that bar rather than the
    prettier value from the bar before.
    """
    rows = (
        _flat(3)
        + [("100", "110", "100", "110")]
        + [("110", "112", "109", "111")]     # entry 110, risk 4, stop 106
        + [("111", "118", "108", "112")]
        + _flat(3)                            # opens at 100: gaps through the stop
    )
    series = _series(rows)
    config = _config(exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20))
    trade = run_arm(series, [True] * len(rows), _atr(series, "2"), config).trades[0]

    assert trade.exit_reason is ExitReason.STOP_GAP
    assert trade.mae == Decimal("-2.5"), "the gap bar's low, not the prior bar's"
    assert trade.mfe == Decimal(2)


def test_stress_multiplies_both_cost_components() -> None:
    base = CostModel(commission_per_share=Decimal("0.005"), slippage_bps=Decimal(5))
    stressed = base.stressed(Decimal(3))
    assert stressed.commission_per_share == Decimal("0.015")
    assert stressed.slippage_bps == Decimal(15)


def test_trade_rejects_an_entry_on_the_signal_bar() -> None:
    """The contract refuses it too, not only the engine."""
    with pytest.raises(ValueError, match="must be after signal"):
        Trade(
            instrument_id="TEST.1", arm="A",
            signal_date=date(2025, 6, 2), entry_date=date(2025, 6, 2), exit_date=date(2025, 6, 5),
            entry_price=Decimal(100), stop_price=Decimal(96), exit_price=Decimal(104),
            shares=10, initial_risk_per_share=Decimal(4), costs=Decimal(1),
            mfe=Decimal(1), mae=Decimal(0), exit_reason=ExitReason.TIME,
        )
