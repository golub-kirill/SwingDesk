"""PR-002's statistic, on constructed partitions where the answer is known.

The most important test here is the one where the partition is meaningless: a statistic that
declares separation on randomly-labelled trades would find a regime effect in noise, which is
exactly what the course's baseline requirement exists to prevent.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from swingdesk.contracts.trade import ExitReason, Trade
from swingdesk.validation.studies import regime_value as study


def _trade(net_target: str, index: int) -> Trade:
    entry, risk = Decimal(100), Decimal(4)
    signal = date(2025, 1, 6) + timedelta(days=index)
    return Trade(
        instrument_id=f"TEST.{index}", arm="NONE",
        signal_date=signal, entry_date=signal + timedelta(days=1),
        exit_date=signal + timedelta(days=5),
        entry_price=entry, stop_price=entry - risk,
        exit_price=entry + Decimal(net_target) * risk,
        shares=100, initial_risk_per_share=risk, costs=Decimal(0),
        mfe=max(Decimal(0), Decimal(net_target)), mae=min(Decimal(0), Decimal(net_target)),
        exit_reason=ExitReason.TIME,
    )


def test_a_meaningless_partition_does_not_separate() -> None:
    """The test that matters.

    Trades drawn from one distribution, labelled at random. A statistic that called this separation
    would find a regime effect in noise - and any partition of a noisy series produces cells with
    different means, which is why the baseline exists.
    """
    rng = random.Random(11)
    pattern = [1, -1, 2, -1, 0, 3, -1, -1, 1, 0]
    trades = [_trade(str(pattern[i % len(pattern)]), i) for i in range(300)]
    labelled = [(rng.choice(["X", "Y", "Z"]), trade) for trade in trades]

    result = study.evaluate("RANDOM", labelled, seed=5, resamples=500)
    assert not result.separates
    assert result.percentile < Decimal(95)


def test_a_real_separation_clears_the_baseline() -> None:
    """One cell of winners and one of losers, which no random split can reproduce."""
    winners = [(("GOOD"), _trade("3", i)) for i in range(100)]
    losers = [(("BAD"), _trade("-1", 100 + i)) for i in range(100)]

    result = study.evaluate("REAL", winners + losers, seed=5, resamples=500)
    assert result.separates
    assert result.observed_range == Decimal(4)
    assert result.percentile == Decimal(100)


def test_unlabelled_sessions_are_excluded_and_counted() -> None:
    """A session the classifier cannot label is not a regime.

    Assigning it a default one would invent the very thing under test.
    """
    labelled = [("A", _trade("1", i)) for i in range(10)]
    labelled += [(None, _trade("-5", 10 + i)) for i in range(10)]
    labelled += [("B", _trade("-1", 20 + i)) for i in range(10)]

    result = study.evaluate("V", labelled, seed=5, resamples=200)
    assert result.unlabelled == 10
    assert {cell.regime for cell in result.cells} == {"A", "B"}
    assert sum(cell.trades for cell in result.cells) == 20


def test_a_single_populated_cell_cannot_separate() -> None:
    result = study.evaluate("V", [("ONLY", _trade("1", i)) for i in range(20)],
                            seed=5, resamples=200)
    assert result.observed_range == Decimal(0)
    assert not result.separates
    assert result.resamples == 0, "no baseline is computed when there is nothing to compare"


def test_thin_cells_are_flagged_not_silently_used() -> None:
    """Regime breakdowns shatter a sample into cells; a verdict on a thin cell is noise with a
    label (WALKFORWARD_SPEC 7)."""
    labelled = [("BIG", _trade("1", i)) for i in range(50)]
    labelled += [("TINY", _trade("2", 50 + i)) for i in range(3)]

    result = study.evaluate("V", labelled, seed=5, resamples=200, min_trades_per_cell=20)
    assert result.thin_cells == ("TINY",)


def test_the_baseline_is_seeded_and_reproducible() -> None:
    labelled = [("A", _trade(str(i % 3 - 1), i)) for i in range(120)]
    labelled += [("B", _trade(str(i % 4 - 1), 120 + i)) for i in range(120)]

    first = study.evaluate("V", labelled, seed=99, resamples=300)
    second = study.evaluate("V", labelled, seed=99, resamples=300)
    third = study.evaluate("V", labelled, seed=100, resamples=300)

    assert (first.baseline_p95, first.percentile) == (second.baseline_p95, second.percentile)
    assert first.baseline_p95 != third.baseline_p95 or first.percentile != third.percentile


def test_cells_are_reported_in_a_stable_order() -> None:
    """Unordered output feeding a conclusion is the named determinism hazard."""
    labelled = [("Z", _trade("1", 0)), ("A", _trade("2", 1)), ("M", _trade("0", 2))]
    result = study.evaluate("V", labelled, seed=1, resamples=50)
    assert [cell.regime for cell in result.cells] == ["A", "M", "Z"]


def test_more_cells_do_not_manufacture_separation() -> None:
    """A four-way random split must not beat the baseline more often than a two-way one.

    The baseline uses the SAME cell sizes, so the extra spread a finer partition produces by chance
    is already in the comparison.
    """
    rng = random.Random(3)
    pattern = [1, -1, 2, -1, 0, 3, -1, -1]
    trades = [_trade(str(pattern[i % len(pattern)]), i) for i in range(400)]
    four = [(rng.choice(["A", "B", "C", "D"]), trade) for trade in trades]

    result = study.evaluate("FOUR", four, seed=8, resamples=500)
    assert not result.separates
