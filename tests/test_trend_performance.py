"""PR-005's comparison, on constructed trade sets.

A permutation test that always says "different" is worse than no test, so two of these construct
arms that genuinely do not differ and assert the interval covers zero.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.validation.studies import trend_performance as study


def _trade(net_target: str, index: int = 0, arm: str = "A") -> Trade:
    """A trade whose net R is approximately `net_target`, with zero costs so it is exact."""
    entry = Decimal(100)
    risk = Decimal(4)
    exit_price = entry + Decimal(net_target) * risk
    signal = date(2025, 1, 6) + timedelta(days=index * 3)
    return Trade(
        instrument_id=f"TEST.{index}", arm=arm,
        signal_date=signal, entry_date=signal + timedelta(days=1),
        exit_date=signal + timedelta(days=5),
        entry_price=entry, stop_price=entry - risk, exit_price=exit_price,
        shares=100, initial_risk_per_share=risk, costs=Decimal(0),
        mfe=max(Decimal(0), Decimal(net_target)), mae=min(Decimal(0), Decimal(net_target)),
        exit_reason=ExitReason.TIME,
    )


def test_summary_reports_net_not_gross() -> None:
    trades = [_trade("1"), _trade("-1", 1), _trade("2", 2), _trade("-1", 3)]
    stats = study.summarise_arm("A", trades)

    assert stats.trades == 4
    assert stats.mean_r == Decimal("0.25")
    assert stats.hit_rate == Decimal("0.5")
    assert stats.exit_reasons == {"time": 4}


def test_empty_arm_summarises_to_zero_rather_than_crashing() -> None:
    stats = study.summarise_arm("D", [])
    assert stats.trades == 0 and stats.mean_r == Decimal(0)


def test_identical_arms_produce_an_interval_covering_zero() -> None:
    """The test must be able to say "no difference", or it is not a test."""
    left = [_trade(str(v), i) for i, v in enumerate([1, -1, 2, -1, 0, 1, -1, 3, -1, 0] * 5)]
    right = [_trade(str(v), i, "NONE") for i, v in enumerate([1, -1, 2, -1, 0, 1, -1, 3, -1, 0] * 5)]

    comparison = study.compare_to_reference("A", left, right, seed=1, resamples=2000)
    assert comparison.difference == Decimal(0)
    assert not comparison.outside_interval
    assert comparison.ci_low < 0 < comparison.ci_high


def test_a_large_separation_falls_outside_the_interval() -> None:
    winners = [_trade("3", i) for i in range(60)]
    losers = [_trade("-1", i, "NONE") for i in range(60)]

    comparison = study.compare_to_reference("A", winners, losers, seed=1, resamples=2000)
    assert comparison.difference == Decimal(4)
    assert comparison.outside_interval


def test_noise_of_the_right_size_stays_inside_the_interval() -> None:
    """A small mean gap between two samples drawn from the same shape is not a finding."""
    pattern = [1, -1, 2, -1, 0, 1, -1, 3, -1, 0]
    left = [_trade(str(v), i) for i, v in enumerate(pattern * 4)]
    right = [_trade(str(v), i, "NONE") for i, v in enumerate((pattern[1:] + pattern[:1]) * 4)]

    comparison = study.compare_to_reference("A", left, right, seed=7, resamples=2000)
    assert not comparison.outside_interval


def test_the_comparison_is_seeded_and_reproducible() -> None:
    """DETERMINISM_SPEC 3.4: no unseeded RNG anywhere."""
    left = [_trade(str(v), i) for i, v in enumerate([1, -1, 2, -1, 0] * 8)]
    right = [_trade(str(v), i, "NONE") for i, v in enumerate([0, 1, -1, 2, -1] * 8)]

    first = study.compare_to_reference("A", left, right, seed=42, resamples=500)
    second = study.compare_to_reference("A", left, right, seed=42, resamples=500)
    third = study.compare_to_reference("A", left, right, seed=43, resamples=500)

    assert (first.ci_low, first.ci_high) == (second.ci_low, second.ci_high)
    assert (first.ci_low, first.ci_high) != (third.ci_low, third.ci_high)


def test_ranking_is_deterministic_on_ties() -> None:
    """Unordered output feeding a conclusion is the named determinism hazard."""
    stats = [
        study.summarise_arm("B", [_trade("1")]),
        study.summarise_arm("A", [_trade("1")]),
        study.summarise_arm("C", [_trade("2")]),
    ]
    assert study.ranking(stats) == ("C", "A", "B")


def test_gap_exits_are_counted_separately() -> None:
    """The field that proves the harness did not assume every stop loses exactly 1R."""
    normal = _trade("-1", 0)
    gapped = normal.model_copy(update={"exit_reason": ExitReason.STOP_GAP})
    stats = study.summarise_arm("A", [normal, gapped])
    assert stats.gap_exits == 1
