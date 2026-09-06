"""The arithmetic under the quoted-spread measurement, and the two places it silently goes wrong.

`measure_quoted_spread.py` exists to replace an estimate with a measurement, so the ways it can be
wrong all produce a plausible number rather than an error:

* **the denominator** — `(ask - bid) / mid`, not over the bid. At a penny tick on a $100 stock the
  two differ by half a basis point, which is invisible; the fixture picks prices where they do not.
* **crossed and locked books** — dropped, never clamped to zero. A locked market's spread is
  undefined, not free, and averaging a zero in pulls the estimate toward the flattering side. This
  is the `DR-025` shape: the permissive outcome disguised as a safe default.
* **the session clock** — 09:30 in New York is 13:30Z in August and 14:30Z in February. A hardcoded
  offset samples half the year an hour out, at a time of day whose spread differs by a factor of
  six, and reports it as the opening spread.

No network. Every case is a literal quote list.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from datetime import time as clock
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def spread():
    return _load("_quoted_spread", "measure_quoted_spread.py")


@pytest.fixture(scope="module")
def probe():
    return _load("_probe_quotes", "probe_quotes.py")


def quote(bid, ask):
    return {"bp": bid, "ap": ask}


# --- the denominator -------------------------------------------------------------------------

def test_spread_is_measured_against_the_mid_not_the_bid(spread):
    """bid 90, ask 110: over the mid that is 2000 bps, over the bid it would be 2222."""
    assert spread.proportional_spread_bps([quote(90.0, 110.0)]) == Decimal(2000)


def test_spread_is_reported_in_basis_points(spread):
    """A one-cent spread on a ten-dollar stock is 10 bps, not 0.001 and not 1."""
    measured = spread.proportional_spread_bps([quote(9.995, 10.005)])
    assert measured == pytest.approx(Decimal(10), abs=Decimal("0.01"))


# --- crossed and locked books ----------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    pytest.param(quote(100.0, 100.0), id="locked"),
    pytest.param(quote(100.0, 99.0), id="crossed"),
    pytest.param(quote(0.0, 100.0), id="no bid"),
    pytest.param(quote(-5.0, 100.0), id="negative bid"),
    pytest.param({"bp": None, "ap": 100.0}, id="missing bid"),
    pytest.param({"ap": 100.0}, id="absent bid"),
    pytest.param({"bp": "100", "ap": "101"}, id="strings, not numbers"),
])
def test_an_unusable_quote_is_dropped_and_does_not_pull_the_median_down(spread, bad):
    """The good quote alone is 990.1 bps. Averaging any of these in would halve it.

    Two elements, so the median is their mean — the fixture is built so that a dropped filter
    changes the answer rather than merely widening it.
    """
    alone = spread.proportional_spread_bps([quote(99.0, 109.0)])
    assert alone == pytest.approx(Decimal("961.54"), abs=Decimal("0.01"))
    assert spread.proportional_spread_bps([quote(99.0, 109.0), bad]) == alone


def test_no_usable_quote_returns_none_rather_than_zero(spread):
    """Zero would read as a free market. `None` is what "the window had no two-sided quote" means."""
    assert spread.proportional_spread_bps([quote(100.0, 100.0), quote(50.0, 49.0)]) is None
    assert spread.proportional_spread_bps([]) is None


def test_the_probe_applies_the_same_rule(probe):
    """The probe's own reduction is a second copy of the arithmetic; it must not drift from it."""
    assert probe.median_spread_bps([quote(90.0, 110.0)]) == Decimal(2000)
    assert probe.median_spread_bps([quote(100.0, 100.0)]) is None


# --- the session clock -----------------------------------------------------------------------

def test_the_opening_bell_is_a_different_utc_hour_in_winter_and_summer(spread):
    """13:30Z in August, 14:30Z in February. A fixed offset gets one of them wrong."""
    assert spread.utc_start(date(2024, 8, 14), clock(9, 30)) == "2024-08-14T13:30:00Z"
    assert spread.utc_start(date(2024, 2, 14), clock(9, 30)) == "2024-02-14T14:30:00Z"


def test_the_close_is_converted_the_same_way(spread):
    assert spread.utc_start(date(2024, 8, 14), clock(15, 55)) == "2024-08-14T19:55:00Z"
    assert spread.utc_start(date(2024, 2, 14), clock(15, 55)) == "2024-02-14T20:55:00Z"


# --- the sampled population ------------------------------------------------------------------

HORIZON = date(2026, 9, 5)  # a store knowledge date, standing in for one


def test_every_sampled_date_is_a_wednesday_before_the_horizon(spread):
    """Monday and Friday carry weekend effects; a date the store cannot see has no tape to read."""
    days = spread.sample_dates([2016, 2019, 2022], HORIZON)
    assert days, "the sampler produced nothing to measure"
    assert all(d.weekday() == 2 for d in days)
    assert all(d < HORIZON for d in days)


def test_the_horizon_is_the_stores_knowledge_date_and_not_a_wall_clock(spread):
    """Two horizons, two populations. A sampler reading the machine clock cannot tell them apart.

    August 2022's Wednesday is the 17th, so a horizon on the 16th must exclude it and one on the
    18th must include it — the fixture straddles a single date rather than a whole year, because a
    year-wide gap would also pass against a hardcoded `today`.
    """
    before = spread.sample_dates([2022], date(2022, 8, 16))
    after = spread.sample_dates([2022], date(2022, 8, 18))
    assert date(2022, 8, 17) not in before
    assert date(2022, 8, 17) in after
    assert len(after) == len(before) + 1


def test_a_year_beyond_the_horizon_contributes_no_dates(spread):
    assert spread.sample_dates([HORIZON.year + 5], HORIZON) == []


def test_the_sample_is_fixed_so_two_runs_compare(spread):
    assert spread.sample_dates([2019, 2022], HORIZON) == spread.sample_dates([2019, 2022], HORIZON)


# --- the summary -----------------------------------------------------------------------------

def test_percentiles_order_and_mean(spread):
    values = [Decimal(n) for n in range(1, 101)]
    stats = spread.percentiles(values)
    assert stats["p10"] < stats["median"] < stats["p90"]
    assert stats["median"] == Decimal(51)
    assert stats["mean"] == Decimal("50.5")


def test_percentiles_survive_a_single_observation(spread):
    stats = spread.percentiles([Decimal(7)])
    assert set(stats.values()) == {Decimal(7)}


# --- what the constant is worth ----------------------------------------------------------------

def test_break_even_scales_linearly_off_the_published_pair(spread):
    """Half the gross needs half the cost to survive; the relation is linear by construction."""
    assert spread.break_even_round_trip_bps(
        Decimal("0.10"), Decimal("0.20"), Decimal(50)
    ) == Decimal(25)
    assert spread.break_even_round_trip_bps(
        Decimal("0.05"), Decimal("0.20"), Decimal(50)
    ) == Decimal("12.5")


def test_the_exit_surfaces_own_numbers_reproduce(spread):
    """The null's +0.1397R against 0.16998R of charged cost turns at 41.1 bps round trip."""
    point = spread.break_even_round_trip_bps(
        Decimal("0.13973409637359618"), Decimal("0.16998124002832227"), Decimal(50)
    )
    assert point == pytest.approx(Decimal("41.10"), abs=Decimal("0.01"))


def test_a_strategy_that_loses_gross_has_no_break_even(spread):
    """Zero would read as "free would be enough". It would not: nothing rescues a negative gross."""
    assert spread.break_even_round_trip_bps(
        Decimal("-0.01"), Decimal("0.17"), Decimal(50)
    ) is None
    assert spread.break_even_round_trip_bps(
        Decimal(0), Decimal("0.17"), Decimal(50)
    ) is None


def test_a_zero_cost_reference_refuses_rather_than_dividing(spread):
    assert spread.break_even_round_trip_bps(
        Decimal("0.14"), Decimal(0), Decimal(50)
    ) is None


# --- the credential boundary -----------------------------------------------------------------

def test_missing_credentials_refuse_rather_than_measure_nothing(spread, monkeypatch):
    """An empty result would read as "the universe is free to trade". It must raise instead."""
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    with pytest.raises(spread.QuoteFeedUnavailable):
        spread._credentials()
