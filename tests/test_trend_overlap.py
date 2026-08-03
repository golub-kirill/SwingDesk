"""PR-001's statistic, tested on constructed cases where the answer is known by hand.

The point of testing an analysis is that a wrong statistic produces a plausible number, and a
plausible number in a study nobody can check becomes a finding.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from swingdesk.decision_logic.trend import TrendDefinition, TrendInputs
from swingdesk.validation.studies import trend_overlap as study


def _inputs(close: str, short: str, long: str, structure: bool = True) -> TrendInputs:
    """Inputs every runnable definition can answer on.

    Pivots are supplied by default so all four definitions are comparable; pass structure=False to
    make STRUCTURE undecided on purpose.
    """
    pivots = (
        {"swing_highs": (Decimal("10"), Decimal("12")),
         "swing_lows": (Decimal("8"), Decimal("9"))}
        if structure else {}
    )
    return TrendInputs(
        close=Decimal(close), sma_short=Decimal(short), sma_long=Decimal(long), **pivots
    )


def test_jaccard_on_known_sets() -> None:
    assert study.jaccard(frozenset("ab"), frozenset("ab")) == Decimal(1)
    assert study.jaccard(frozenset("ab"), frozenset("cd")) == Decimal(0)
    assert study.jaccard(frozenset("abc"), frozenset("bcd")) == Decimal(2) / Decimal(4)


def test_two_empty_selections_agree_completely() -> None:
    """Both definitions selected nothing, so they agree about the session.

    Scoring this 0 would call perfect agreement total disagreement, and would drag the p10 down on
    exactly the quiet days the statistic says least about.
    """
    assert study.jaccard(frozenset(), frozenset()) == Decimal(1)


def test_undecided_is_neither_selected_nor_rejected() -> None:
    """A definition that cannot answer must not be recorded as having said no."""
    inputs = {
        "AAA": _inputs("110", "105", "100"),
        "BBB": TrendInputs(close=Decimal("110")),  # no moving averages: cannot answer
    }
    day = study.select(date(2025, 6, 2), inputs)

    assert day.selected["ABOVE_LONG_MA"] == frozenset({"AAA"})
    assert day.undecided["ABOVE_LONG_MA"] == frozenset({"BBB"})
    assert "BBB" not in day.selected["ABOVE_LONG_MA"]


def test_definitions_that_always_agree_score_one() -> None:
    inputs = {name: _inputs("110", "105", "100") for name in ("AAA", "BBB", "CCC")}
    daily = [study.select(date(2025, 6, 2), inputs) for _ in range(10)]
    result = study.summarise("US", 3, daily)

    assert result.sessions == 10
    assert all(pair.median == Decimal(1) for pair in result.pairs)
    assert result.mean_selected["ABOVE_LONG_MA"] == Decimal(3)


def test_a_and_c_diverge_when_price_sits_between_the_averages() -> None:
    """The constructed disagreement: A says yes, C says no, for every instrument."""
    inputs = {name: _inputs("102", "105", "100") for name in ("AAA", "BBB")}
    result = study.summarise("US", 2, [study.select(date(2025, 6, 2), inputs)])

    pair = next(p for p in result.pairs
                if {p.left, p.right} == {"ABOVE_LONG_MA", "PRICE_AND_STACK"})
    assert pair.median == Decimal(0)


def test_p10_catches_divergence_a_median_hides() -> None:
    """Seventeen sessions of agreement and three of total disagreement.

    The median is 1 and the study alone would call that interchangeable. The 10th percentile is 0,
    which is why PR-001 requires both.

    Three rather than one, deliberately. Nearest-rank puts the 10th percentile of n points at index
    round(0.1 x (n-1)), so on twenty sessions it lands on the third-smallest. A single outlier
    session shows up in `minimum`, not in `p10` - an artefact of a twenty-point sample that
    disappears at the ~2500 sessions PR-001 actually runs on, but one worth writing down rather
    than papering over with a friendlier estimator.
    """
    agree = {name: _inputs("110", "105", "100") for name in ("AAA", "BBB")}
    disagree = {name: _inputs("102", "105", "100") for name in ("AAA", "BBB")}
    daily = [study.select(date(2025, 6, 2), agree) for _ in range(17)]
    daily += [study.select(date(2025, 6, 20), disagree) for _ in range(3)]

    result = study.summarise("US", 2, daily)
    pair = next(p for p in result.pairs
                if {p.left, p.right} == {"ABOVE_LONG_MA", "PRICE_AND_STACK"})
    assert pair.median == Decimal(1)
    assert pair.p10 == Decimal(0)
    assert pair.minimum == Decimal(0)


def test_a_single_outlier_session_shows_in_minimum_not_p10() -> None:
    """States the estimator's behaviour rather than assuming it. One bad session in ten does not
    move a nearest-rank 10th percentile, and a study that did not know that would misread it."""
    agree = {name: _inputs("110", "105", "100") for name in ("AAA", "BBB")}
    disagree = {name: _inputs("102", "105", "100") for name in ("AAA", "BBB")}
    daily = [study.select(date(2025, 6, 2), agree) for _ in range(9)]
    daily.append(study.select(date(2025, 6, 20), disagree))

    result = study.summarise("US", 2, daily)
    pair = next(p for p in result.pairs
                if {p.left, p.right} == {"ABOVE_LONG_MA", "PRICE_AND_STACK"})
    assert pair.p10 == Decimal(1)
    assert pair.minimum == Decimal(0)


def test_verdict_thresholds_come_from_the_caller() -> None:
    """PR-001 fixed these numbers before the run. A decision rule living in analysis code is a
    decision rule that can be adjusted after seeing the result."""
    agree = {name: _inputs("110", "105", "100") for name in ("AAA", "BBB")}
    result = study.summarise("US", 2, [study.select(date(2025, 6, 2), agree)])
    assert result.verdict(Decimal("0.70"), Decimal("0.50"),
                          Decimal("0.40"), Decimal("0.25")) == "accept"

    split = {name: _inputs("102", "105", "100") for name in ("AAA", "BBB")}
    low = study.summarise("US", 2, [study.select(date(2025, 6, 2), split)])
    assert low.verdict(Decimal("0.70"), Decimal("0.50"),
                       Decimal("0.40"), Decimal("0.25")) == "reject"


def test_one_bad_pair_is_enough_to_reject() -> None:
    """The claim is that the FAMILY is interchangeable, so a single member that is not refutes it
    (PR-001 section 9) - even when every other pair agrees perfectly."""
    inputs = {name: _inputs("102", "105", "100") for name in ("AAA", "BBB")}
    result = study.summarise("US", 2, [study.select(date(2025, 6, 2), inputs)])

    perfect = [p for p in result.pairs if p.median == Decimal(1)]
    assert perfect, "some pairs do agree in this construction"
    assert result.verdict(Decimal("0.70"), Decimal("0.50"),
                          Decimal("0.40"), Decimal("0.25")) == "reject"


def test_adx_is_not_runnable_yet() -> None:
    """It needs a threshold with no course basis. Picking one would answer part of the question."""
    assert TrendDefinition.ADX_DI not in study.RUNNABLE
    assert len(study.RUNNABLE) == 4


def test_empty_window_summarises_without_crashing() -> None:
    result = study.summarise("CA", 0, [])
    assert result.sessions == 0 and result.pairs == []
    assert result.verdict(Decimal("0.70"), Decimal("0.50"),
                          Decimal("0.40"), Decimal("0.25")) == "inconclusive"


def test_a_definition_that_cannot_answer_does_not_drag_the_overlap_down() -> None:
    """The bug this test was written for.

    STRUCTURE has no pivots here, so it is undecided everywhere and selects nothing. Comparing it
    against a definition that selected every instrument scored 0 - "cannot answer" counted as
    "answered no", the conflation the three-valued verdict exists to prevent, arriving one level up
    at aggregation. Pairs are now compared only over instruments both could evaluate.
    """
    inputs = {name: _inputs("110", "105", "100", structure=False) for name in ("AAA", "BBB")}
    result = study.summarise("US", 2, [study.select(date(2025, 6, 2), inputs)])

    involving_structure = [p for p in result.pairs if "STRUCTURE" in (p.left, p.right)]
    assert involving_structure == [], "no co-decidable instruments, so no comparison is reported"

    others = [p for p in result.pairs if "STRUCTURE" not in (p.left, p.right)]
    assert others and all(p.median == Decimal(1) for p in others)


def test_pair_records_how_wide_the_comparison_was() -> None:
    """A pair judged on three instruments and one judged on forty deserve different belief."""
    inputs = {
        "AAA": _inputs("110", "105", "100"),
        "BBB": _inputs("110", "105", "100"),
        "CCC": _inputs("110", "105", "100", structure=False),
    }
    result = study.summarise("US", 3, [study.select(date(2025, 6, 2), inputs)])

    with_structure = next(p for p in result.pairs if "STRUCTURE" in (p.left, p.right))
    without = next(p for p in result.pairs if "STRUCTURE" not in (p.left, p.right))
    assert with_structure.mean_decidable == Decimal(2)
    assert without.mean_decidable == Decimal(3)
