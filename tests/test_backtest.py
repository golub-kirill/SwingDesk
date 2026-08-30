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
from swingdesk.decision_logic.triggers import (
    BreakoutHigh,
    CloseBelowLow,
    breakout_high,
    lowest_low,
)
from swingdesk.validation.backtest import CostModel, ExitPolicy
from swingdesk.validation.backtest.engine import (
    BacktestConfig,
    Skipped,
    run_arm,
)

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
        trigger=BreakoutHigh(3),
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
    assert result.skipped[Skipped.POSITION_OPEN] >= 1, (
        "a signal that could not be acted on is an exclusion from the trade set. Uncounted, it "
        "makes the strategy look more selective than it is"
    )


def test_a_bar_with_no_lookback_window_is_not_a_rejected_signal() -> None:
    """UNKNOWN is not FALSE, in the one place the engine could quietly conflate them.

    The first `trigger_lookback` bars have no window to compare against, so the trigger has nothing
    to answer with. Counting them as bars the rule declined would shrink the denominator of every
    rate this arm reports, silently and by a fixed amount per instrument.
    """
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(4)
    series = _series(rows)
    result = run_arm(series, [True] * len(rows), _atr(series, "2"), _config(trigger=BreakoutHigh(3)))

    assert result.unevaluable_bars == 3, "one per bar before the window is full"
    assert result.signals == 1
    assert Skipped.POSITION_OPEN not in result.skipped


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


# ------------------------------------------------- the entry trigger is injected, not hardcoded

def test_breakout_high_and_lowest_low_read_the_same_window() -> None:
    """Two rules, one window. They exclude the current bar and go quiet on a short one identically,
    so a change to what "the prior N sessions" means cannot move one without moving the other."""
    rows = [("10", "12", "8", "11"), ("11", "15", "9", "14"), ("14", "16", "7", "9")]
    series = _series(rows)
    assert breakout_high(series, 2, 2) == Decimal("15")
    assert lowest_low(series, 2, 2) == Decimal("8")
    assert breakout_high(series, 1, 2) is None
    assert lowest_low(series, 1, 2) is None


def test_a_trigger_answers_three_states_and_the_third_is_not_false() -> None:
    """`None` is "the rule had nothing to answer with", and it is what `run_arm` counts as an
    unevaluable bar. A trigger that returned False there would move those bars into the rejected
    population and shrink every rate the arm reports, by a fixed amount per instrument."""
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(4)
    series = _series(rows)
    trigger = BreakoutHigh(3)

    assert trigger(series, 0) is None, "no window yet"
    assert trigger(series, 2) is None, "still short by one"
    assert trigger(series, 3) is True, "the breakout bar"
    assert trigger(series, 5) is False, "window full, rule did not fire"


def test_the_config_refuses_to_default_the_family() -> None:
    """`trigger` has no default. It replaced `trigger_lookback: int = 20`, which silently made every
    unconfigured backtest the one family PR-005 refuted - a strategy choice nobody made."""
    with pytest.raises(TypeError, match="trigger"):
        BacktestConfig(  # type: ignore[call-arg]
            arm="TEST",
            exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20),
            costs=FREE,
        )


def test_a_custom_trigger_drives_the_engine() -> None:
    """The seam itself: a rule the engine has never heard of decides the entries.

    Fires on exactly one bar, chosen so the assertion is about WHICH bar rather than how many."""

    def only_bar_four(series: BarSeries, index: int) -> bool | None:
        if index < 2:
            return None
        return index == 4

    rows = _flat(8)
    series = _series(rows)
    result = run_arm(series, [True] * len(rows), _atr(series, "2"), _config(trigger=only_bar_four))

    assert result.unevaluable_bars == 2, "the two bars the rule declined to answer for"
    assert result.signals == 1
    assert result.trades[0].signal_date == series.bars[4].session_date
    assert result.trades[0].entry_date == series.bars[5].session_date


def test_the_second_family_runs_end_to_end_through_the_same_engine() -> None:
    """`CloseBelowLow` is not a proposed strategy - see its docstring. It is here to prove the
    engine expresses more than one family, which is what makes `EntryTrigger` a seam rather than a
    rename. A breakdown bar that BreakoutHigh cannot fire on produces a trade through the mirror."""
    rows = _flat(3) + [("100", "100", "90", "90")] + _flat(4)
    series = _series(rows)
    gate = [True] * len(rows)

    reversion = run_arm(series, gate, _atr(series, "2"), _config(trigger=CloseBelowLow(3)))
    breakout = run_arm(series, gate, _atr(series, "2"), _config(trigger=BreakoutHigh(3)))

    assert reversion.signals == 1
    assert reversion.trades, "the mirror family produced a trade the engine could not express before"
    assert reversion.trades[0].signal_date == series.bars[3].session_date
    assert breakout.signals == 0, "and the refuted family sees nothing on the same bars"


def test_the_two_families_disagree_rather_than_sharing_an_answer() -> None:
    """A seam that passed both rules through the same path would look like this test's opposite:
    identical trade sets. Run over bars containing one breakout AND one breakdown, each family
    takes its own and neither takes both."""
    rows = _flat(3) + [("100", "115", "100", "115")] + _flat(3) + [("100", "100", "85", "85")] \
        + _flat(3)
    series = _series(rows)
    gate = [True] * len(rows)
    exits = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=1)

    up = run_arm(series, gate, _atr(series, "2"), _config(trigger=BreakoutHigh(3), exits=exits))
    down = run_arm(series, gate, _atr(series, "2"), _config(trigger=CloseBelowLow(3), exits=exits))

    up_signals = {t.signal_date for t in up.trades}
    down_signals = {t.signal_date for t in down.trades}
    assert up_signals, "the breakout family took something"
    assert down_signals, "so did the reversion family"
    assert not (up_signals & down_signals), "and they are not the same trades"
