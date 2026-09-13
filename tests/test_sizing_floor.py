"""The owner's minimum stop distance - `risk.min_stop_distance_fraction`, ratified 2026-09-13.

`DR-005` charges 25 bps of price a side, so a stop closer to the entry than 0.5% of its price costs
more than the whole R in round trip before the market has moved. Three things must hold, and each
fails silently if it drifts:

* **under the floor refuses, and names the parameter** - a refusal an operator cannot trace to the
  owner's number reads as a data fault;
* **at the floor is sized, and the snapshot records the parameter** - the run's record must show the
  number it was held to;
* **an unset floor refuses by name** - never sized as though the check had passed.
"""

from __future__ import annotations

from decimal import Decimal

from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.trade_management.sizing import Refusal, RiskSnapshot, size_long

ADTV = Decimal(100_000_000)
FLOOR = "risk.min_stop_distance_fraction"


def test_a_stop_closer_than_the_floor_refuses_and_names_it(registry) -> None:
    got = size_long(Decimal("100"), Decimal("99.60"), "USD", registry, adtv=ADTV)  # 0.40% away
    assert isinstance(got, Refusal)
    assert (got.code, got.parameter_id) == ("RISK", FLOOR)
    assert "0.4000%" in got.reason


def test_a_stop_exactly_at_the_floor_is_sized_and_records_the_floor(registry) -> None:
    got = size_long(Decimal("100"), Decimal("99.50"), "USD", registry, adtv=ADTV)  # 0.50% away
    assert isinstance(got, RiskSnapshot)
    assert FLOOR in {use.id for use in got.parameters}


def test_a_t_bill_fund_is_refused_at_the_ratified_two_atr_stop(registry) -> None:
    """SGOV's daily range is about 0.011% of price (`TODO.md`), so its 2 ATR stop is ~0.02% away."""
    entry = Decimal("100.50")
    got = size_long(entry, entry - Decimal("0.022"), "USD", registry, adtv=ADTV)
    assert isinstance(got, Refusal) and got.parameter_id == FLOOR


def test_an_unset_floor_refuses_by_name(registry) -> None:
    unset = ParameterRegistry({
        FLOOR: {"id": FLOOR, "value": None, "provenance": "owner", "status": "owner", "unit": "",
                "named_in": ["test"]},
    })
    got = size_long(Decimal("100"), Decimal("90"), "USD", unset, adtv=ADTV)
    assert isinstance(got, Refusal)
    assert got.parameter_id == FLOOR, "an unset floor names itself rather than sizing past it"
