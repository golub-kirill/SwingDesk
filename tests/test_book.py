"""The book: many instruments competing for a bounded number of slots.

`CARD-001` is a portfolio rule and `run_arm` is a per-instrument engine, so until `run_book` existed
the card's own family could not be simulated at all. These tests pin the four properties that
separate a book from a loop over instruments, and each of them is a rule from a document rather than
a preference:

  - **`deferred` is not `Skip`** (`ALLOCATION_SPEC` §5). A candidate that lost on capacity returns
    tomorrow; one that failed a gate does not.
  - **A slot freed today is available today** (`CHECKLIST_SPEC` §4), because otherwise capacity
    depends on the order the code runs in.
  - **The ranking decides who gets the slot**, and it is injected. An engine that ranked by whatever
    order it had would apply an alphabetical bias silently.
  - **A one-instrument book with room to spare agrees with `run_arm` trade for trade.** That is the
    equivalence that makes the two engines answer the same question when they should.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from tests.conftest import KNOWLEDGE_TIME

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.observation import Observation, ObservationSeries
from swingdesk.validation.backtest import (
    BacktestConfig,
    Capacity,
    CostModel,
    ExitPolicy,
    by_instrument_id,
    run_arm,
    run_book,
)
from swingdesk.validation.backtest.book import Candidate

FREE = CostModel(commission_per_share=Decimal(0), slippage_bps=Decimal(0))
ROOMY = Capacity(max_positions=99, max_open_risk=Decimal(99))


def _series(instrument_id: str, rows: list[tuple[str, str, str, str]]) -> BarSeries:
    """rows are (open, high, low, close), one per consecutive session."""
    bars = []
    for offset, (o, h, low, c) in enumerate(rows):
        session = date(2025, 1, 6) + timedelta(days=offset)
        bars.append(
            Bar(
                instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session,
                open=Decimal(o), high=Decimal(h), low=Decimal(low), close=Decimal(c),
                volume=1_000_000, knowledge_time=KNOWLEDGE_TIME,
            )
        )
    return BarSeries(
        instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
        knowledge_time=KNOWLEDGE_TIME, bars=tuple(bars),
    )


def _atr(series: BarSeries, value: str) -> ObservationSeries:
    return ObservationSeries(
        component="M18-T0280-v5.0", component_version=1, instrument_id=series.instrument_id,
        units="price units", parameters=(), validation_status="Not Applicable",
        knowledge_time=KNOWLEDGE_TIME,
        observations=tuple(
            Observation(
                component="M18-T0280-v5.0", component_version=1,
                instrument_id=series.instrument_id, event_time=bar.event_time,
                knowledge_time=KNOWLEDGE_TIME, value=Decimal(value), units="price units",
                parameters=(), validation_status="Not Applicable",
            )
            for bar in series.bars
        ),
    )


def _flat(count: int, price: str = "100") -> list[tuple[str, str, str, str]]:
    return [(price, price, price, price)] * count


def _fires_on(target: int):
    """A trigger that fires on exactly one bar index and is unevaluable before bar 2."""

    def trigger(series: BarSeries, index: int) -> bool | None:
        if index < 2:
            return None
        return index == target

    return trigger


def _config(trigger, **kwargs) -> BacktestConfig:
    defaults = dict(
        arm="TEST",
        exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20),
        costs=FREE,
        trigger=trigger,
        risk_per_trade=Decimal(1000),
    )
    defaults.update(kwargs)
    return BacktestConfig(**defaults)


def _book(names: list[str], rows, trigger, capacity=ROOMY, ranking=by_instrument_id, **kwargs):
    series = {name: _series(name, rows) for name in names}
    gates = {name: [True] * len(rows) for name in names}
    atr = {name: _atr(s, "2") for name, s in series.items()}
    return run_book(series, gates, atr, _config(trigger, **kwargs), capacity, ranking)


# ------------------------------------------------------- it agrees with the one-instrument engine


def test_a_one_name_book_with_room_agrees_with_run_arm() -> None:
    """The equivalence that makes two engines trustworthy. With capacity that never binds, a book
    holding one instrument must produce exactly the trades `run_arm` produces on it - same entry,
    same exit, same R. A divergence here means one of them is wrong about the rules they share."""
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(8)
    series = _series("TEST.1", rows)
    trigger = _fires_on(3)
    config = _config(trigger)

    alone = run_arm(series, [True] * len(rows), _atr(series, "2"), config)
    book = _book(["TEST.1"], rows, trigger)

    assert [t.model_dump() for t in book.trades] == [t.model_dump() for t in alone.trades]
    assert book.signals == alone.signals
    assert book.unevaluable_bars == alone.unevaluable_bars
    assert book.deferred == 0


# --------------------------------------------------------------------------- capacity, and defer


def test_capacity_binds_and_the_losers_are_DEFERRED_not_skipped() -> None:
    """`ALLOCATION_SPEC` §5. Four names all qualify on the same session and two slots exist, so two
    trade and two are deferred. Counting the two as `Skipped` would report a capital constraint as
    a rule rejection, and counting them nowhere would make the strategy look more selective."""
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(8)
    result = _book(
        ["AAA", "BBB", "CCC", "DDD"], rows, _fires_on(3),
        capacity=Capacity(max_positions=2, max_open_risk=Decimal(99)),
    )

    assert len({t.instrument_id for t in result.trades}) == 2
    assert result.deferred == 2
    assert result.signals == 4, "all four were admissible; capacity is not admissibility"
    assert sum(result.skipped.values()) == 0, "a deferred candidate is not a skipped one"
    assert result.max_concurrent == 2


def test_the_ranking_decides_which_candidates_get_the_slots() -> None:
    """Injected, never inferred. The same four candidates and the same two slots produce different
    books under different rules - which is the whole point of making it an argument."""
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(8)
    names = ["AAA", "BBB", "CCC", "DDD"]
    two_slots = Capacity(max_positions=2, max_open_risk=Decimal(99))

    def reversed_order(candidates: list[Candidate]) -> list[Candidate]:
        return sorted(candidates, key=lambda c: c.instrument_id, reverse=True)

    forward = _book(names, rows, _fires_on(3), capacity=two_slots)
    backward = _book(names, rows, _fires_on(3), capacity=two_slots, ranking=reversed_order)

    assert {t.instrument_id for t in forward.trades} == {"AAA", "BBB"}
    assert {t.instrument_id for t in backward.trades} == {"CCC", "DDD"}


def test_open_risk_binds_independently_of_the_position_count() -> None:
    """`DR-006` §1: the two caps are the same constraint counted twice only while every position
    risks a full R. A book with slots to spare must still refuse on risk."""
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(8)
    result = _book(
        ["AAA", "BBB", "CCC"], rows, _fires_on(3),
        capacity=Capacity(max_positions=99, max_open_risk=Decimal(2)),
    )
    assert len(result.trades) == 2
    assert result.deferred == 1


# ------------------------------------------------------------------ ordering within one session


def test_a_slot_freed_today_is_available_today() -> None:
    """`CHECKLIST_SPEC` §4 - open positions before candidates. One slot, one name exits on the
    session a second name qualifies. If candidates were evaluated first the second name would be
    deferred for no reason, and capacity would depend on the order the code happens to run in."""
    exiting = _flat(3) + [("100", "110", "100", "110")] + _flat(2) + [("100", "100", "90", "90")] \
        + _flat(5)
    waiting = _flat(3) + _flat(3) + [("100", "110", "100", "110")] + _flat(5)

    series = {"AAA": _series("AAA", exiting), "ZZZ": _series("ZZZ", waiting)}
    gates = {name: [True] * len(exiting) for name in series}
    atr = {name: _atr(s, "2") for name, s in series.items()}

    def trigger(s: BarSeries, index: int) -> bool | None:
        if index < 2:
            return None
        return (s.instrument_id == "AAA" and index == 3) or (s.instrument_id == "ZZZ" and index == 6)

    result = run_book(
        series, gates, atr,
        _config(trigger, exits=ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20)),
        Capacity(max_positions=1, max_open_risk=Decimal(99)), by_instrument_id,
    )

    assert {t.instrument_id for t in result.trades} == {"AAA", "ZZZ"}
    assert result.deferred == 0, "the freed slot was taken the same session"


def test_one_position_per_instrument_is_still_counted() -> None:
    """A name that re-triggers while held is an EXCLUSION from the trade set, and an unrecorded
    exclusion is a survivorship filter on the signal set whatever the intent."""

    def always(series: BarSeries, index: int) -> bool | None:
        return None if index < 2 else True

    result = _book(["AAA"], _flat(10), always)
    assert result.skipped["position_open"] > 0


# ------------------------------------------------------------------------------ the loop's shape


def test_an_instrument_with_no_bar_that_session_cannot_be_a_candidate() -> None:
    """Instruments are not required to share a calendar. A halted name has no bar for the session
    and must neither trade nor be counted as having declined."""
    rows = _flat(3) + [("100", "110", "100", "110")] + _flat(8)
    full = _series("AAA", rows)
    holed = BarSeries(
        instrument_id="ZZZ", interval=Interval.DAY, series=Series.RAW,
        knowledge_time=KNOWLEDGE_TIME,
        bars=tuple(b for b in _series("ZZZ", rows).bars if b.session_date != date(2025, 1, 9)),
    )
    series = {"AAA": full, "ZZZ": holed}
    gates = {"AAA": [True] * len(full.bars), "ZZZ": [True] * len(holed.bars)}
    atr = {"AAA": _atr(full, "2"), "ZZZ": _atr(holed, "2")}

    # Keyed to the SESSION, not to an index. An index-keyed trigger would fire on ZZZ anyway, one
    # session later, because removing a bar shifts every index after it - which is correct engine
    # behaviour and would make this test assert something else entirely.
    missing = date(2025, 1, 9)

    def on_the_missing_session(s: BarSeries, index: int) -> bool | None:
        if index < 2:
            return None
        return s.bars[index].session_date == missing

    result = run_book(
        series, gates, atr, _config(on_the_missing_session), ROOMY, by_instrument_id
    )
    assert {t.instrument_id for t in result.trades} == {"AAA"}, "ZZZ had no bar on the signal day"
    assert missing not in {b.session_date for b in holed.bars}


def test_a_position_open_at_the_end_is_closed_and_flagged() -> None:
    """Never dropped. Open positions at the end of a window are not randomly distributed, and
    discarding them is a survivorship filter applied to the outcome set."""
    result = _book(["AAA"], _flat(3) + [("100", "110", "100", "110")] + _flat(3), _fires_on(3))
    assert result.trades
    assert result.trades[-1].exit_reason.value == "end_of_data"


def test_misaligned_inputs_raise_rather_than_silently_shift() -> None:
    """A gate off by one bar is a look-ahead bug that produces plausible numbers."""
    series = {"AAA": _series("AAA", _flat(5))}
    with pytest.raises(ValueError, match="one entry per bar"):
        run_book(
            series, {"AAA": [True] * 3}, {"AAA": _atr(series["AAA"], "2")},
            _config(_fires_on(3)), ROOMY, by_instrument_id,
        )


def test_a_missing_gate_or_atr_raises_rather_than_skipping_the_instrument() -> None:
    """Silently dropping an instrument shrinks the universe without saying so, which is the
    survivorship shape this whole module is careful about."""
    series = {"AAA": _series("AAA", _flat(5))}
    with pytest.raises(ValueError, match="needs both a gate and an ATR"):
        run_book(series, {}, {}, _config(_fires_on(3)), ROOMY, by_instrument_id)
