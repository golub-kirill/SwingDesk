"""`tools/measure_after_tax.py` - the book against holding, after a yearly tax model.

What must hold: at a zero rate nothing changes; a realised gain is taxed in its own year, at half
the rate as a capital gain and at the whole rate as business income; a dividend is taxed at the
whole rate either way; a loss is carried forward rather than refunded; and a held position's price
gain is taxed only when sold.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tax():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("measure_after_tax",
                                                  REPO / "tools" / "measure_after_tax.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _years(tax, *rows):
    """One day a year: `(year, total return, dividend part)`."""
    return [tax.Day(date(year, 6, 1), total, dividend) for year, total, dividend in rows]


def test_a_zero_rate_changes_nothing(tax) -> None:
    days = _years(tax, (2020, 0.10, 0.01), (2021, -0.05, 0.01))
    expected = 1.10 * 0.95
    for treatment in tax.TREATMENTS:
        assert tax.realised_yearly(days, 0.0, treatment) == pytest.approx(expected)
    assert tax.held(days, 0.0, True) == pytest.approx(expected)


def test_a_realised_gain_is_taxed_by_its_treatment(tax) -> None:
    days = _years(tax, (2020, 0.10, 0.0))
    assert tax.realised_yearly(days, 0.5, "business_income") == pytest.approx(1.05)
    assert tax.realised_yearly(days, 0.5, "capital_gains") == pytest.approx(1.075)


def test_a_dividend_is_taxed_at_the_whole_rate_even_as_capital_gains(tax) -> None:
    days = _years(tax, (2020, 0.02, 0.02))
    assert tax.realised_yearly(days, 0.5, "capital_gains") == pytest.approx(1.01)


def test_a_loss_is_carried_forward_not_refunded(tax) -> None:
    days = _years(tax, (2020, -0.10, 0.0), (2021, 0.20, 0.0))
    # 0.90 after the loss, 1.08 after the gain; 0.18 gained, 0.10 of it offset: tax 0.5 x 0.08.
    assert tax.realised_yearly(days, 0.5, "business_income") == pytest.approx(1.08 - 0.04)


def test_held_price_gain_is_taxed_only_when_sold(tax) -> None:
    days = _years(tax, (2020, 0.10, 0.0))
    assert tax.held(days, 0.5, False) == pytest.approx(1.10)
    assert tax.held(days, 0.5, True) == pytest.approx(1.10 - 0.5 * 0.5 * 0.10)


def test_held_dividends_are_taxed_yearly_and_their_after_tax_part_joins_the_basis(tax) -> None:
    days = _years(tax, (2020, 0.02, 0.02))
    # Taxed 0.01 on the dividend; the 0.01 reinvested is basis, so selling realises no gain.
    assert tax.held(days, 0.5, False) == pytest.approx(1.01)
    assert tax.held(days, 0.5, True) == pytest.approx(1.01)


class _Registry:
    def __init__(self, low, high):
        self.values = {"tax.marginal_rate_low": low, "tax.marginal_rate_high": high}

    def decimal_value(self, parameter_id):
        from decimal import Decimal

        from swingdesk.platform.parameters import ParameterUnset

        value = self.values[parameter_id]
        if value is None:
            raise ParameterUnset(parameter_id)
        return Decimal(value), None


def test_the_owners_band_is_read_from_the_registry(tax) -> None:
    assert tax.rate_band(_Registry("0.20", "0.30")) == (0.20, 0.30)


def test_an_unset_band_refuses_rather_than_guessing(tax) -> None:
    assert isinstance(tax.rate_band(_Registry(None, "0.30")), str)


def test_a_band_upside_down_is_not_a_band(tax) -> None:
    assert isinstance(tax.rate_band(_Registry("0.30", "0.20")), str)


def test_the_owners_rows_are_marked_and_always_present(tax) -> None:
    days = _years(tax, (2020, 0.10, 0.0), (2021, 0.05, 0.0))
    rows = tax.grid(days, days, (0.25, 0.33))["rows"]
    marked = {row["rate"] for row in rows if row["owner_band"]}
    assert marked == {0.25, 0.33}
