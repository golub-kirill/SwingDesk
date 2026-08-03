"""The survivorship bound, checked by reconstructing the gap it claims to close."""

from __future__ import annotations

from decimal import Decimal

import pytest

from swingdesk.validation.studies import survivorship_bound as bound


def _gap_after(high_mean: Decimal, high_trades: int, low_mean: Decimal,
               missing: int, missing_r: Decimal) -> Decimal:
    adjusted = (Decimal(high_trades) * high_mean + Decimal(missing) * missing_r) / Decimal(
        high_trades + missing
    )
    return adjusted - low_mean


def test_the_break_even_actually_closes_the_gap() -> None:
    """The claim is checkable: add that many trades and the gap must reach the threshold."""
    result = bound.concentrated_break_even(
        high_mean=Decimal("0.2299"), high_trades=466,
        low_mean=Decimal("-0.1304"), low_trades=717,
        threshold=Decimal("0.2345"), missing_r=Decimal(-1),
    )
    assert result.is_reachable
    after = _gap_after(Decimal("0.2299"), 466, Decimal("-0.1304"), result.missing_trades, Decimal(-1))
    assert after <= Decimal("0.2345")

    one_fewer = _gap_after(
        Decimal("0.2299"), 466, Decimal("-0.1304"), result.missing_trades - 1, Decimal(-1)
    )
    assert one_fewer > Decimal("0.2345"), "the answer is the smallest number that works"


def test_worse_missing_trades_need_fewer_of_them() -> None:
    common = dict(high_mean=Decimal("0.2299"), high_trades=466,
                  low_mean=Decimal("-0.1304"), low_trades=717, threshold=Decimal("0.2345"))
    at_one = bound.concentrated_break_even(**common, missing_r=Decimal(-1))
    at_two = bound.concentrated_break_even(**common, missing_r=Decimal(-2))
    at_three = bound.concentrated_break_even(**common, missing_r=Decimal(-3))

    assert at_one.missing_trades > at_two.missing_trades > at_three.missing_trades


def test_missing_trades_that_are_not_bad_enough_can_never_close_it() -> None:
    """Missing trades performing better than the target cannot drag the cell to it."""
    result = bound.concentrated_break_even(
        high_mean=Decimal("0.5"), high_trades=100,
        low_mean=Decimal("0"), low_trades=100,
        threshold=Decimal("0.2"), missing_r=Decimal("0.4"),
    )
    assert not result.is_reachable


def test_a_gap_already_below_threshold_needs_nothing() -> None:
    result = bound.concentrated_break_even(
        high_mean=Decimal("0.10"), high_trades=100,
        low_mean=Decimal("0"), low_trades=100,
        threshold=Decimal("0.20"), missing_r=Decimal(-1),
    )
    assert result.missing_trades == 0


def test_proportional_shape_is_independent_of_the_missing_r() -> None:
    """Adding the same mean to every cell in proportion scales the gap by 1/(1+p); the R cancels.

    That is why the concentrated shape is the one that matters - it is the only one where how badly
    the missing trades did changes the answer.
    """
    fraction = bound.proportional_break_even(Decimal("0.3602"), Decimal("0.2345"))
    assert Decimal("0.30") < fraction < Decimal("0.40")


def test_proportional_needs_far_more_than_concentrated() -> None:
    """The whole point of computing both."""
    concentrated = bound.concentrated_break_even(
        high_mean=Decimal("0.2299"), high_trades=466,
        low_mean=Decimal("-0.1304"), low_trades=717,
        threshold=Decimal("0.2345"), missing_r=Decimal(-1),
    )
    proportional = bound.proportional_break_even(Decimal("0.3602"), Decimal("0.2345"))
    assert concentrated.fraction_of_total < proportional / 2


def test_no_gap_needs_no_missing_trades() -> None:
    assert bound.proportional_break_even(Decimal("0.10"), Decimal("0.20")) == Decimal(0)
    assert bound.proportional_break_even(Decimal(0), Decimal("0.20")) == Decimal(0)


def test_empty_cells_are_refused() -> None:
    with pytest.raises(ValueError, match="at least one trade"):
        bound.concentrated_break_even(Decimal(1), 0, Decimal(0), 10, Decimal("0.1"), Decimal(-1))
