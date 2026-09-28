"""`tools/attribute_pr040.py` - PR-040's book re-read by year and trailing window, descriptively.

What must hold: a year is compounded from its own months and nothing else, a trailing window is the
LAST months of the window, and both read the registration's own statistic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def attr():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("attribute_pr040", REPO / "tools" / "attribute_pr040.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_a_year_compounds_its_own_months_only(attr) -> None:
    book = {"2024-11": 0.10, "2024-12": 0.10, "2025-01": 0.50}
    hold = {"2024-11": 0.0, "2024-12": 0.0, "2025-01": 0.0}
    years = attr.by_year(book, hold)
    assert years["2024"] == pytest.approx(1.1 * 1.1 - 1)
    assert years["2025"] == pytest.approx(0.5)


def test_a_trailing_window_is_the_last_months(attr) -> None:
    months = [f"{2020 + i // 12}-{i % 12 + 1:02d}" for i in range(60)]
    book = {m: (0.02 if i >= 48 else 0.0) for i, m in enumerate(months)}
    hold = dict.fromkeys(months, 0.0)
    got = attr.trailing(book, hold, (12, 24))
    assert got["last_12_months"] == pytest.approx(1.02 ** 12 - 1)
    assert got["last_24_months"] == pytest.approx((1.02 ** 12) ** 0.5 - 1)


def test_a_window_longer_than_the_record_is_not_reported(attr) -> None:
    book = {"2024-01": 0.01, "2024-02": 0.01}
    assert attr.trailing(book, dict.fromkeys(book, 0.0), (12,)) == {}
