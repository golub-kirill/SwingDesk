"""Rankings a study can pin, and the identity that makes one of them a trap.

`DR-018` §1 proved that on a single cross-section a MARKET benchmark cannot change a ranking - its
return is one constant for every name that day, so dividing by it is a strictly monotone transform
of the name's own return. **Point-to-point relative strength against an index IS raw return**, and a
study reporting an edge from it would be reporting momentum under another name.

That proof is arithmetic, so it is pinned here as a test rather than trusted to a document nobody
re-reads. The rest of this file pins the two forms that genuinely escape it, and the property that
matters more than any of them: **a ranking cannot see the future.**
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from tests.conftest import KNOWLEDGE_TIME

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.validation.backtest import (
    ByMarketPathStrength,
    ByRawReturn,
    BySectorRelativeStrength,
)
from swingdesk.validation.backtest.book import Candidate

START = date(2025, 1, 6)


def _series(instrument_id: str, closes: list[str]) -> BarSeries:
    bars = []
    for offset, close in enumerate(closes):
        session = START + timedelta(days=offset)
        value = Decimal(close)
        bars.append(
            Bar(
                instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session,
                open=value, high=value + 1, low=value - 1, close=value,
                volume=1_000_000, knowledge_time=KNOWLEDGE_TIME,
            )
        )
    return BarSeries(
        instrument_id=instrument_id, interval=Interval.DAY, series=Series.RAW,
        knowledge_time=KNOWLEDGE_TIME, bars=tuple(bars),
    )


def _candidate(instrument_id: str, index: int) -> Candidate:
    return Candidate(
        instrument_id=instrument_id, session_date=START + timedelta(days=index), index=index,
        close=Decimal(100), entry_price=Decimal(100), stop=Decimal(96),
        risk_per_share=Decimal(4), shares=250,
    )


def _ids(ordered: list[Candidate]) -> list[str]:
    return [candidate.instrument_id for candidate in ordered]


# --------------------------------------------------------------------- the control, and the trap


def test_raw_return_orders_strongest_first() -> None:
    series = {
        "AAA": _series("AAA", ["100", "100", "100", "100", "110"]),   # +10%
        "BBB": _series("BBB", ["100", "100", "100", "100", "130"]),   # +30%
        "CCC": _series("CCC", ["100", "100", "100", "100", "90"]),    # -10%
    }
    candidates = [_candidate(name, 4) for name in series]
    assert _ids(ByRawReturn(series, lookback=4)(candidates)) == ["BBB", "AAA", "CCC"]


def test_a_market_point_to_point_ranking_IS_the_raw_return_ranking() -> None:
    """`DR-018` §1, pinned as arithmetic rather than left in a document.

    Dividing every name's growth factor by ONE constant cannot reorder them. This test exists so
    that nobody adds a `ByMarketRelativeStrength` believing it is a different signal from
    `ByRawReturn` - it is the same ranking with a decorative denominator, and the way to tell is to
    compute it and look.
    """
    series = {
        "AAA": _series("AAA", ["100", "100", "100", "100", "110"]),
        "BBB": _series("BBB", ["100", "100", "100", "100", "130"]),
        "CCC": _series("CCC", ["100", "100", "100", "100", "90"]),
    }
    candidates = [_candidate(name, 4) for name in series]
    raw = _ids(ByRawReturn(series, lookback=4)(candidates))

    for benchmark_return in (Decimal("-0.5"), Decimal(0), Decimal("0.2"), Decimal(3)):
        scored = sorted(
            series,
            key=lambda name: -(
                (1 + (series[name].bars[4].close - series[name].bars[0].close)
                 / series[name].bars[0].close)
                / (1 + benchmark_return)
            ),
        )
        assert scored == raw, f"a benchmark of {benchmark_return} reordered a ranking; it cannot"


# ------------------------------------------------------------------ the forms that DO escape it


def test_the_market_path_form_can_disagree_with_raw_return() -> None:
    """`DR-018` §2. Share of sessions beating the benchmark is not a function of the endpoint, so
    a name that wins on most days while finishing lower can outrank one that gapped once.

    STEADY grinds up every session. LUMPY finishes higher but does it in a single jump and loses on
    every other session. Raw return prefers LUMPY; the path form prefers STEADY."""
    benchmark = _series("SPY", ["100", "100", "100", "100", "100"])
    series = {
        "STEADY": _series("STEADY", ["100", "101", "102", "103", "104"]),
        "LUMPY": _series("LUMPY", ["100", "99", "98", "97", "130"]),
    }
    candidates = [_candidate(name, 4) for name in series]

    assert _ids(ByRawReturn(series, lookback=4)(candidates)) == ["LUMPY", "STEADY"]
    assert _ids(ByMarketPathStrength(series, benchmark, lookback=4)(candidates)) \
        == ["STEADY", "LUMPY"]


def test_a_sector_denominator_can_reorder_where_a_market_one_cannot() -> None:
    """`DR-018` §7. Two names with the SAME return rank differently when their sectors differ,
    which is impossible for any common factor. That is the whole reason sector-relative strength is
    a cross-sectional signal and market point-to-point is not."""
    series = {
        "HOT": _series("HOT", ["100", "100", "100", "100", "120"]),
        "COLD": _series("COLD", ["100", "100", "100", "100", "120"]),
    }
    candidates = [_candidate(name, 4) for name in series]
    assert _ids(ByRawReturn(series, lookback=4)(candidates)) == ["COLD", "HOT"], "tie -> id order"

    ranking = BySectorRelativeStrength(
        series=series,
        sector_of={"HOT": "technology", "COLD": "utilities"},
        # HOT's sector ran away; COLD's went nowhere. Same return, different denominators.
        sector_return=lambda _session: {
            "technology": Decimal("0.50"), "utilities": Decimal("0.00")
        },
        lookback=4,
    )
    assert _ids(ranking(candidates)) == ["COLD", "HOT"]

    flipped = BySectorRelativeStrength(
        series=series,
        sector_of={"HOT": "technology", "COLD": "utilities"},
        sector_return=lambda _session: {
            "technology": Decimal("0.00"), "utilities": Decimal("0.50")
        },
        lookback=4,
    )
    assert _ids(flipped(candidates)) == ["HOT", "COLD"], "the denominator decided, not the return"


# -------------------------------------------------------------------- what must never be dropped


def test_an_unscorable_candidate_sorts_to_the_BOTTOM_rather_than_vanishing() -> None:
    """A dropped candidate is an unrecorded exclusion, and an unrecorded exclusion is a survivorship
    filter applied to the signal set whatever the intent. Bottom-ranked competes and loses, which is
    a different and honest claim."""
    series = {
        "LONG": _series("LONG", ["100", "100", "100", "100", "110"]),
        "SHORT": _series("SHORT", ["100", "101"]),  # no 4-session window
    }
    candidates = [_candidate("LONG", 4), _candidate("SHORT", 1)]
    ordered = ByRawReturn(series, lookback=4)(candidates)
    assert len(ordered) == 2, "nothing is dropped"
    assert _ids(ordered) == ["LONG", "SHORT"]


def test_a_candidate_with_no_sector_competes_and_loses() -> None:
    series = {
        "KNOWN": _series("KNOWN", ["100", "100", "100", "100", "105"]),
        "ORPHAN": _series("ORPHAN", ["100", "100", "100", "100", "150"]),
    }
    candidates = [_candidate(name, 4) for name in series]
    ranking = BySectorRelativeStrength(
        series=series, sector_of={"KNOWN": "utilities"},
        sector_return=lambda _s: {"utilities": Decimal(0)}, lookback=4,
    )
    ordered = ranking(candidates)
    assert len(ordered) == 2
    assert _ids(ordered) == ["KNOWN", "ORPHAN"], "the orphan outperformed and still ranks last"


# ------------------------------------------------------------------------------- no look-ahead


def test_no_ranking_can_see_past_the_decision_bar() -> None:
    """The property that matters more than any ordering. A ranking is handed the whole series and
    must read only `bars[:index + 1]`; the engine cannot enforce that, so this does.

    Same bars up to the decision session, wildly different futures. Every ranking must return the
    same order both times."""
    early = {
        "AAA": _series("AAA", ["100", "100", "100", "100", "110"]),
        "BBB": _series("BBB", ["100", "100", "100", "100", "130"]),
    }
    late = {
        "AAA": _series("AAA", ["100", "100", "100", "100", "110", "500", "900"]),
        "BBB": _series("BBB", ["100", "100", "100", "100", "130", "1", "1"]),
    }
    benchmark_early = _series("SPY", ["100", "100", "100", "100", "100"])
    benchmark_late = _series("SPY", ["100", "100", "100", "100", "100", "700", "3"])
    candidates = [_candidate(name, 4) for name in early]
    sectors = {"AAA": "technology", "BBB": "technology"}
    returns = {"technology": Decimal("0.1")}

    pairs = (
        (ByRawReturn(early, 4), ByRawReturn(late, 4)),
        (ByMarketPathStrength(early, benchmark_early, 4),
         ByMarketPathStrength(late, benchmark_late, 4)),
        (BySectorRelativeStrength(early, sectors, lambda _s: returns, 4),
         BySectorRelativeStrength(late, sectors, lambda _s: returns, 4)),
    )
    for without_future, with_future in pairs:
        assert _ids(without_future(candidates)) == _ids(with_future(candidates)), (
            f"{type(without_future).__name__} changed its answer when the FUTURE changed"
        )


def test_the_path_form_locates_the_benchmark_by_SESSION_not_by_its_last_bar() -> None:
    """The look-ahead test above is not enough on its own, and this is the case it misses.

    Measured: a mutant mapping every session to the benchmark's LAST index survived it, because
    both names' scores moved by the same amount and the ORDER - which is all that was asserted -
    did not change. A test that only checks order is blind to a window that shifts uniformly.

    So this pair is built to be order-sensitive to the window, **and the ids are chosen so the
    tie-break points the wrong way.** Measured under the mutant: both names score exactly 0.5, and a
    tie falls back to `instrument_id` - so `ZIG` must be the strong one and must sort last, or the
    tie-break would hand back the correct order by accident and the test would pass on a bug.
    """
    benchmark = _series("SPY", ["100", "100", "100", "100", "100", "100", "100"])
    series = {
        # gains on sessions 1-3, flat on 4. Named to sort LAST, so only a correct score puts it
        # first.
        "ZIG": _series("ZIG", ["100", "101", "102", "103", "103", "103", "103"]),
        # flat on 1-3, gains on 4
        "ABC": _series("ABC", ["100", "100", "100", "100", "104", "104", "104"]),
    }
    candidates = [_candidate(name, 4) for name in series]

    ordered = ByMarketPathStrength(series, benchmark, lookback=4)(candidates)
    assert _ids(ordered) == ["ZIG", "ABC"], (
        "ZIG beats the flat benchmark on 3 of the 4 sessions in the window and ABC on 1. A window "
        "ending anywhere but the decision session ties them at 0.5 and the id order takes over."
    )
