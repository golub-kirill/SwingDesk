"""The venue's regulatory fees: the committed schedule, its effective date, and daily aggregation.

Every case is pinned against the ONE real observation this project holds —
`docs/decisions/measurements/venue-fees-2026-09-05.json`, the `AIS` round trip — and against the
committed `registry/fee_schedule.yml` rather than numbers retyped into the test.

`DR-039` §9 is why that matters. The record's first draft predicted $0.01 of TAF from a rate that
was wrong, and the venue billed $0.01, because both rates round up to the same cent. **A check that
cannot fail is not a check**, so the sizes below are chosen to make each rate discriminate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.validation.backtest.fees import (
    FeeRefusal,
    RegulatoryRates,
    Sale,
    Schedule,
    day_fees,
    load_schedule,
    rates_on,
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def schedule() -> Schedule:
    """The COMMITTED schedule, not a fixture copy.

    Retyping the rates here would let the file and the test drift apart while both stayed green,
    which is the failure mode this whole record is about.
    """
    return load_schedule(REPO / "registry" / "fee_schedule.yml")


#: The AIS round trip. Buys on 09-03 across three names, the sell on 09-04.
SELL_DAY = date(2026, 9, 4)
BUY_DAY = date(2026, 9, 3)
AIS_PROCEEDS = Decimal("1190.51")
AIS_SHARES = Decimal(17)
#: AIS 17 + BTSG 18 + DINO 12 — every share bought that day, because CAT aggregates per account.
SHARES_BOUGHT = Decimal(47)


# ------------------------------------------------------- the observation, reproduced


def test_the_sell_day_reproduces_every_cent_the_venue_billed(schedule: Schedule) -> None:
    """$0.03 SEC, $0.01 TAF, $0.01 CAT — the only real fee data this project holds."""
    assert day_fees(SELL_DAY, schedule, sales=(Sale(AIS_PROCEEDS, AIS_SHARES),)) == {
        "sec": Decimal("0.03"),
        "taf": Decimal("0.01"),
        "cat": Decimal("0.01"),
    }


def test_the_buy_day_pays_cat_alone_and_nothing_else(schedule: Schedule) -> None:
    """SEC and TAF are sell-side. A day of pure buying owes CAT and no more.

    47 shares × 0.000003 = $0.000141, up to a cent — which is why the statement line reading
    "CAT fee for proceed of 12 trades" was a daily total and not a per-trade charge.
    """
    assert day_fees(BUY_DAY, schedule, shares_bought=SHARES_BOUGHT) == {
        "sec": Decimal("0.00"),
        "taf": Decimal("0.00"),
        "cat": Decimal("0.01"),
    }


# ------------------------------------------- the effective date, which is the point


def test_a_session_before_the_schedule_refuses_rather_than_charging_todays_rate(
    schedule: Schedule,
) -> None:
    """`DR-039` §6 could only warn about this; the schedule makes it impossible.

    Section 31 was $0.00 per million until 2026-04-04. A backtest opening in 2016 that silently
    charged the 2026 rate would be arithmetically consistent everywhere and wrong throughout, which
    is the failure no test catches.
    """
    refused = rates_on(date(2016, 8, 1), schedule)
    assert isinstance(refused, FeeRefusal)
    assert refused.code == "DATA"
    assert "2026-04-04" in refused.reason

    # And the refusal travels: a caller asking for a day's fees gets it, not a zero.
    assert isinstance(
        day_fees(date(2016, 8, 1), schedule, sales=(Sale(AIS_PROCEEDS, AIS_SHARES),)), FeeRefusal
    )


def test_the_day_the_schedule_starts_is_served_and_the_day_before_is_not(
    schedule: Schedule,
) -> None:
    """An off-by-one here silently extends or shortens the range the project can price."""
    assert isinstance(rates_on(date(2026, 4, 4), schedule), RegulatoryRates)
    assert isinstance(rates_on(date(2026, 4, 3), schedule), FeeRefusal)


def test_the_newest_applicable_rates_win_when_several_apply(schedule: Schedule) -> None:
    """Fixed in advance, because the file holds one entry today.

    A second entry lands the next time a rate moves, and this lookup is the part nobody will
    re-read then.
    """
    older = RegulatoryRates(
        effective=date(2026, 1, 1),
        sec_rate_on_value=Decimal("0"),
        taf_per_share=Decimal("0.000166"),
        taf_max_per_trade=Decimal("8.30"),
        cat_per_equivalent_share=Decimal("0.000003"),
    )
    two = Schedule(
        rates=(older, *schedule.rates),
        otc_cat_equivalence=schedule.otc_cat_equivalence,
        source="fixture",
    )
    assert rates_on(date(2026, 3, 1), two) is older
    assert rates_on(SELL_DAY, two) is schedule.rates[-1]


def test_a_schedule_with_no_rates_is_refused_at_construction() -> None:
    """It would refuse every session, which is indistinguishable from a loader that read nothing."""
    with pytest.raises(ValueError, match="can price nothing"):
        Schedule(rates=(), otc_cat_equivalence=Decimal("0.01"), source="empty")


# ------------------------------------ daily aggregation, and why per-trade is wrong


def test_a_day_is_aggregated_once_and_not_charged_trade_by_trade(schedule: Schedule) -> None:
    """The schedule's own rule, page 4, and the mistake a straightforward implementation makes.

    Ten sub-cent sales rounded UP individually cost ten cents of CAT. Aggregated, they cost one.
    """
    sales = tuple(Sale(Decimal("100.00"), Decimal(10)) for _ in range(10))
    aggregated = day_fees(SELL_DAY, schedule, sales=sales)
    assert not isinstance(aggregated, FeeRefusal)

    per_trade_sum = sum(
        (day_fees(SELL_DAY, schedule, sales=(sale,))["cat"] for sale in sales), Decimal(0)
    )
    assert aggregated["cat"] == Decimal("0.01")
    assert per_trade_sum == Decimal("0.10"), "the trap is a factor of ten here"


# --------------------------------------------- the rates themselves, made to bite


def test_the_taf_rate_is_the_brokers_and_the_size_makes_it_discriminate(
    schedule: Schedule,
) -> None:
    """345 shares is where 0.000195 and the FINRA page's 0.000166 stop agreeing.

    `DR-039` §9: the original check used a 17-share sell, where both rates round up to $0.01, so it
    passed against a wrong rate. This is the smallest sale that would have failed it.
    """
    charged = day_fees(SELL_DAY, schedule, sales=(Sale(Decimal("1000.00"), Decimal(345)),))
    assert not isinstance(charged, FeeRefusal)
    # 345 x 0.000195 = 0.0672750 -> $0.07;  345 x 0.000166 = 0.0572700 -> $0.06
    assert charged["taf"] == Decimal("0.07")


def test_the_taf_cap_binds_per_trade_and_the_schedules_two_numbers_agree(
    schedule: Schedule,
) -> None:
    """$9.79 at 50,205 shares, and 50,205 × 0.000195 = 9.789975 → $9.79.

    The cap and the rate corroborate each other, which is the only internal check the schedule
    offers. Asserted rather than admired.
    """
    current = schedule.rates[-1]
    assert current.taf_max_per_trade == Decimal("9.79")
    assert _up(Decimal(50_205) * current.taf_per_share) == Decimal("9.79")

    at_cap = day_fees(SELL_DAY, schedule, sales=(Sale(Decimal("1000000"), Decimal(50_205)),))
    over = day_fees(SELL_DAY, schedule, sales=(Sale(Decimal("2000000"), Decimal(100_410)),))
    assert at_cap["taf"] == over["taf"] == Decimal("9.79")


def test_the_cap_is_per_trade_so_two_capped_sales_pay_it_twice(schedule: Schedule) -> None:
    """Capping the DAY instead would halve the bill for an account that traded twice at size."""
    one = Sale(Decimal("1000000"), Decimal(50_205))
    assert day_fees(SELL_DAY, schedule, sales=(one, one))["taf"] == Decimal("19.58")


def test_an_otc_share_counts_a_hundredth_against_cat(schedule: Schedule) -> None:
    """The schedule's equivalence rule, and the only place a share is not one share."""
    sale = (Sale(Decimal("100"), Decimal(1_000_000)),)
    assert day_fees(SELL_DAY, schedule, sales=sale)["cat"] == Decimal("3.00")
    assert day_fees(SELL_DAY, schedule, sales=sale, otc=True)["cat"] == Decimal("0.03")


def test_the_sec_fee_is_charged_on_proceeds_and_taf_on_shares(schedule: Schedule) -> None:
    """Two fees, two denominators. Same shares, ten times the proceeds: SEC moves, TAF does not."""
    cheap = day_fees(SELL_DAY, schedule, sales=(Sale(Decimal("10000.00"), Decimal(1000)),))
    dear = day_fees(SELL_DAY, schedule, sales=(Sale(Decimal("100000.00"), Decimal(1000)),))
    assert cheap["sec"] == Decimal("0.21") and dear["sec"] == Decimal("2.06")
    assert cheap["taf"] == dear["taf"] == Decimal("0.20")


def test_a_refusal_is_not_a_zero(schedule: Schedule) -> None:
    """`AGENTS.md` §3. A zero reads as "this trade was free", a different claim entirely."""
    refused = day_fees(date(2020, 1, 2), schedule, sales=(Sale(Decimal("1000"), Decimal(10)),))
    assert isinstance(refused, FeeRefusal)


def _up(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding="ROUND_CEILING")
