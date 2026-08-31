"""The RS line: `M31-T0464` and `M77-T1138`, one implementation claimed by both rows.

Three properties carry the component, and the third is the one a naive implementation gets wrong:

  - the ratio is rebased to 1.0 at the first SHARED session, so two instruments are comparable;
  - a session the benchmark does not hold emits **no value**, never a carried-forward one;
  - and the value at session T reads closes at T only, so nothing here can see forward.

`DR-018` §1's identity - that ranking a cross-section by this is ranking by raw return - is pinned
in `tests/test_ranking.py`, where the ranking that would misuse it lives.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from tests.conftest import KNOWLEDGE_TIME

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.derived_observations import relative_strength

START = date(2025, 1, 6)


def _series(instrument_id: str, closes: list[str | None],
            interval: Interval = Interval.DAY) -> BarSeries:
    """`None` in `closes` means the instrument has no bar for that session at all."""
    bars = []
    for offset, close in enumerate(closes):
        if close is None:
            continue
        session = START + timedelta(days=offset)
        value = Decimal(close)
        bars.append(
            Bar(
                instrument_id=instrument_id, interval=interval, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session, open=value, high=value + 1, low=value - 1, close=value,
                volume=1_000_000, knowledge_time=KNOWLEDGE_TIME,
            )
        )
    return BarSeries(
        instrument_id=instrument_id, interval=interval, series=Series.RAW,
        knowledge_time=KNOWLEDGE_TIME, bars=tuple(bars),
    )


def _values(observations) -> list[Decimal | None]:
    return [o.value for o in observations]


def test_the_line_starts_at_one_and_tracks_the_ratio() -> None:
    """Rebased at the first shared session. An instrument that moves exactly with the benchmark
    holds 1.0 forever, which is what "no relative strength" has to look like."""
    benchmark = _series("SPY", ["100", "110", "121"])
    together = _series("SAME", ["50", "55", "60.5"])   # +10% each session, like the benchmark
    ahead = _series("AHEAD", ["50", "60", "72"])       # +20% each session

    assert _values(relative_strength.compute(together, benchmark).observations) \
        == [Decimal(1), Decimal(1), Decimal(1)]

    line = _values(relative_strength.compute(ahead, benchmark).observations)
    assert line[0] == Decimal(1)
    assert line[1] > Decimal(1) and line[2] > line[1], "outperformance rises, and keeps rising"


def test_a_session_the_benchmark_does_not_hold_emits_NO_value() -> None:
    """`unavailable` is not a number. A missing denominator makes the comparison unanswerable, and
    carrying the previous benchmark close forward would answer it with something nobody measured -
    the same collapse `FAIL_CLOSED_POLICY` §3 forbids one layer up."""
    benchmark = _series("SPY", ["100", None, "121"])   # the benchmark did not trade on day 2
    instrument = _series("AAA", ["50", "55", "60.5"])

    values = _values(relative_strength.compute(instrument, benchmark).observations)
    assert values[0] == Decimal(1)
    assert values[1] is None, "no denominator, no value"
    assert values[2] is not None, "and it resumes when the benchmark does"


def test_the_base_is_the_first_SHARED_session_not_the_first_bar() -> None:
    """An instrument listed before the benchmark's history starts must not rebase on a session the
    benchmark cannot price. Getting this wrong shifts the whole line by a constant and looks fine."""
    benchmark = _series("SPY", [None, None, "100", "110"])
    instrument = _series("AAA", ["10", "20", "50", "55"])

    values = _values(relative_strength.compute(instrument, benchmark).observations)
    assert values[0] is None and values[1] is None
    assert values[2] == Decimal(1), "the base is the first session BOTH hold"
    assert values[3] == Decimal(1), "and +10% against +10% is flat"


def test_the_value_at_a_session_reads_that_session_only() -> None:
    """No look-ahead, and no smoothing either. Extending the future must not move a past value."""
    benchmark_short = _series("SPY", ["100", "110"])
    benchmark_long = _series("SPY", ["100", "110", "500", "3"])
    instrument_short = _series("AAA", ["50", "60"])
    instrument_long = _series("AAA", ["50", "60", "9000", "1"])

    short = _values(relative_strength.compute(instrument_short, benchmark_short).observations)
    long = _values(relative_strength.compute(instrument_long, benchmark_long).observations)
    assert long[: len(short)] == short, "a later bar changed an earlier value"


def test_a_zero_or_negative_close_emits_no_value_rather_than_dividing() -> None:
    benchmark = _series("SPY", ["100", "110"])
    instrument = _series("AAA", ["0", "60"])
    values = _values(relative_strength.compute(instrument, benchmark).observations)
    assert values[0] is None
    assert values[1] == Decimal(1), "the first PRICEABLE session is the base"


def test_mismatched_intervals_raise_rather_than_comparing_nothing() -> None:
    benchmark = _series("SPY", ["100", "110"], interval=Interval.HOUR)
    instrument = _series("AAA", ["50", "55"])
    with pytest.raises(ValueError, match="interval mismatch"):
        relative_strength.compute(instrument, benchmark)


def test_the_component_claims_exactly_ONE_catalogue_row_and_no_parameters() -> None:
    """**One function, one component id.** The first version of this module claimed `M31-T0464` AND
    `M77-T1138` - the same measure at the Setup stage - reasoning that one implementation beats two.
    Gate 11 refused it: Production Rules 3.8 forbids two components sharing one definition, and the
    rule is about what a catalogue row MEANS rather than about duplicated code. `M77-T1138` stays
    `registered` until someone reads the source PDFs and can say whether it names something
    distinct.

    `parameters` is empty on purpose: `rs.lookback` measures a CHANGE in this line and belongs to
    whatever consumes it, so this component can never refuse for want of a value."""
    assert {spec.component for spec in relative_strength.SPECS} == {"M31-T0464-v5.0"}
    benchmark = _series("SPY", ["100", "110"])
    computed = relative_strength.compute(_series("AAA", ["50", "55"]), benchmark)
    assert computed.parameters == ()
    assert computed.validation_status == "Not Applicable"


# ---------------------------------------------- `latest` is `compute`'s last value, and only that

def test_latest_equals_computes_last_observation() -> None:
    """The optimisation is only allowed if it changes nothing, so that is what is asserted.

    `latest` exists because `compute` over the live universe cost 41.8 seconds and built 2.6 million
    observations to use 1,186 of them. It may return a different NUMBER of observations; it may not
    return a different value.
    """
    cases = [
        (["10.00", "11.00", "12.00", "13.00"], ["100.00", "101.00", "102.00", "103.00"]),
        (["50.00", "50.00", "50.00"], ["100.00", "100.00", "100.00"]),
        (["10.00", "9.00", "8.00"], ["100.00", "110.00", "121.00"]),
        # A session the benchmark is missing in the MIDDLE - an empty observation that is not last.
        (["10.00", "11.00", "12.00"], ["100.00", None, "102.00"]),
    ]
    for closes, benchmark_closes in cases:
        series = _series("TEST.1", closes)
        benchmark = _series("BENCH", benchmark_closes)

        full = relative_strength.compute(series, benchmark).observations
        one = relative_strength.latest(series, benchmark).observations

        assert len(one) == 1, closes
        assert one[0].value == full[-1].value, closes
        assert one[0].event_time == full[-1].event_time, closes
        assert one[0].instrument_id == full[-1].instrument_id
        assert one[0].component == full[-1].component


def test_latest_is_empty_when_the_benchmark_lacks_the_final_session() -> None:
    """The case a "last non-empty value" shortcut gets wrong, and why `latest` is not one.

    `compute` emits an observation per BAR, so its last is the observation for the series' last bar
    - empty when the benchmark has no session for it. That is what a benchmark one session behind
    the candidate looks like, which is an ordinary evening rather than an exotic case, so a shortcut
    returning the last value that DID compute would differ exactly on the days it matters.
    """
    series = _series("TEST.1", ["10.00", "11.00", "12.00"])
    benchmark = _series("BENCH", ["100.00", "101.00", None])

    full = relative_strength.compute(series, benchmark).observations
    one = relative_strength.latest(series, benchmark).observations

    assert full[-1].value is None, "the fixture must exercise the empty case"
    assert len(one) == 1
    assert one[0].value is None
    assert one[0].event_time == full[-1].event_time

    # The shortcut this test forbids would have found a number: earlier sessions ARE shared.
    assert [o.value for o in full if o.value is not None], "earlier shared sessions exist"


def test_latest_carries_the_same_series_metadata_as_compute() -> None:
    """Both entry points return the component's own identity - version, units, validation status.

    They share one wrapper so they cannot drift, and this is what pins that they do.
    """
    series = _series("TEST.1", ["10.00", "11.00"])
    benchmark = _series("BENCH", ["100.00", "101.00"])

    full = relative_strength.compute(series, benchmark)
    one = relative_strength.latest(series, benchmark)

    for field in ("component", "component_version", "units", "validation_status", "instrument_id"):
        assert getattr(one, field) == getattr(full, field), field


def test_latest_refuses_a_timeframe_mismatch_like_compute_does() -> None:
    """Two entry points to one component must refuse the same nonsense the same way."""
    series = _series("TEST.1", ["10.00", "11.00"])
    hourly = _series("BENCH", ["100.00", "101.00"], interval=Interval.HOUR)
    with pytest.raises(ValueError, match="interval mismatch"):
        relative_strength.latest(series, hourly)


def test_latest_on_an_empty_series_returns_no_observation() -> None:
    """`compute` returns an empty tuple for a series with no bars; so must this."""
    empty = _series("TEST.1", [])
    benchmark = _series("BENCH", ["100.00"])
    assert relative_strength.latest(empty, benchmark).observations == ()
    assert relative_strength.compute(empty, benchmark).observations == ()
