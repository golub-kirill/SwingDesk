"""`tools/run_pr040.py` - `PR-035`'s book priced at the auction crosses (`DR-055` proof (1)).

What these hold: the price a session is priced at (the cross on the bars' basis, or the bar with a
flag), the fee on each side, the identity the arms must satisfy, and the order of the decision rule.
The split case is written from the tape's side - prints at twice the bar - because that is the unit
error that sank `PR-025`'s first run, and the smoke read found `IJR` exactly there.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pr40():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("run_pr040", REPO / "tools" / "run_pr040.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class _Bar:
    session_date: date
    open: Decimal
    close: Decimal


@dataclass(frozen=True)
class _Print:
    price: Decimal
    size: int = 1000
    at: datetime = datetime(2016, 1, 4, 14, 30, tzinfo=UTC)
    conditions: tuple[str, ...] = ("O",)


def _bars(*rows: tuple[date, str, str]) -> list[_Bar]:
    return [_Bar(d, Decimal(o), Decimal(c)) for d, o, c in rows]


D1, D2, D3 = date(2016, 1, 4), date(2016, 1, 5), date(2016, 1, 6)


def test_a_cross_at_twice_the_bar_is_a_split_and_prices_on_the_bars_basis(pr40) -> None:
    bars = _bars((D1, "54.13", "53.77"))
    crosses = {D1: (_Print(Decimal("108.26")), _Print(Decimal("107.54")))}
    [s] = pr40.priced_sessions(bars, {}, crosses, D1, D1)
    assert s.open == pytest.approx(54.13) and s.close == pytest.approx(53.77)
    assert s.tape_open == pytest.approx(108.26), "fees are levied on the shares that traded"
    assert s.crossed_open and s.crossed_close
    assert abs(s.gap_open) < 1e-9 and abs(s.gap_close) < 1e-9


def test_a_cross_off_its_bar_keeps_its_own_price(pr40) -> None:
    """Two basis points is a real difference between the print and the bar, and it stays."""
    bars = _bars((D1, "200.49", "201.02"))
    crosses = {D1: (_Print(Decimal("200.53")), _Print(Decimal("201.01")))}
    [s] = pr40.priced_sessions(bars, {}, crosses, D1, D1)
    assert s.open == pytest.approx(200.53) and s.close == pytest.approx(201.01)
    assert s.gap_open == pytest.approx(200.53 / 200.49 - 1)


def test_a_missing_cross_falls_back_to_the_bar_and_is_flagged(pr40) -> None:
    bars = _bars((D1, "100", "101"))
    [s] = pr40.priced_sessions(bars, {}, {D1: (None, _Print(Decimal("101")))}, D1, D1)
    assert s.open == pytest.approx(100.0) and not s.crossed_open and s.crossed_close
    [stand_in] = pr40.priced_sessions(bars, {}, {}, D1, D1, bars_as_crosses=True)
    assert stand_in.crossed_open and stand_in.crossed_close, "the power stand-in charges no penalty"


def test_the_fees_on_each_side(pr40) -> None:
    price = 100.0
    assert pr40.buy_cost(price, True, "auction") == pytest.approx(pr40.CAT_PER_SHARE / price)
    assert pr40.sell_cost(price, True, "auction") == pytest.approx(
        pr40.SEC_RATE + (pr40.TAF_PER_SHARE + pr40.CAT_PER_SHARE) / price)
    assert pr40.buy_cost(price, False, "auction") == pytest.approx(
        (pr40.CAT_PER_SHARE + pr40.MISSING_PENALTY) / price)
    assert pr40.buy_cost(price, True, "gross") == 0 and pr40.sell_cost(price, True, "gross") == 0
    assert pr40.sell_cost(price, True, "bars_pr035") == pytest.approx(0.005 / price)
    assert pr40.buy_cost(price, True, "auction_plus_half_cent") == pytest.approx(
        (pr40.CAT_PER_SHARE + 0.005) / price)


def test_at_zero_cost_the_night_and_the_session_compound_to_holding(pr40) -> None:
    bars = _bars((D1, "100", "101"), (D2, "102", "100.5"), (D3, "99", "103"))
    crosses = {d: (_Print(b.open), _Print(b.close)) for d, b in ((b.session_date, b) for b in bars)}
    sessions = pr40.priced_sessions(bars, {}, crosses, D1, D3)
    night, inside, held = pr40.arms(sessions, "gross")
    for day in (D2, D3):
        assert (1 + night[day]) * (1 + inside[day]) - 1 == pytest.approx(held[day], abs=1e-12)


def test_the_dividend_is_paid_to_the_night(pr40) -> None:
    bars = _bars((D1, "100", "100"), (D2, "99", "99"))
    sessions = pr40.priced_sessions(bars, {D2: 1.0}, {}, D1, D2, bars_as_crosses=True)
    night, inside, _ = pr40.arms(sessions, "gross")
    assert night[D2] == pytest.approx(0.0) and inside[D2] == pytest.approx(0.0)


def test_months_compound_and_the_recent_window_is_the_last_48(pr40) -> None:
    daily = {date(2016, 1, 4): 0.01, date(2016, 1, 5): 0.01, date(2016, 2, 1): -0.02}
    months = pr40.monthly(daily)
    assert months["2016-01"] == pytest.approx(1.01 ** 2 - 1)
    assert months["2016-02"] == pytest.approx(-0.02)
    many = {f"{2020 + i // 12}-{i % 12 + 1:02d}": 0.0 for i in range(60)}
    kept = pr40.recent(many)
    assert len(kept) == 48 and min(kept) == "2021-01"


@pytest.mark.parametrize(("lo", "hi", "recent", "checks", "expected"), [
    (0.01, 0.08, 0.02, {}, "ACCEPT"),
    (0.01, 0.08, -0.01, {}, "RECENT_FRAGILE"),
    (-0.08, -0.01, 0.02, {}, "REJECT"),
    (-0.03, 0.05, 0.02, {}, "INCONCLUSIVE"),
    (-0.01, 0.01, 0.02, {}, "NULL"),
    (0.01, 0.08, 0.02, {"crossed_share": 0.90}, "REFUSED"),
    (0.01, 0.08, 0.02, {"basis_ok": False}, "REFUSED"),
    (0.01, 0.08, 0.02, {"reproduces_pr035": False}, "REFUSED"),
])
def test_the_decision_rule_refuses_first_then_reads_the_interval(
    pr40, lo, hi, recent, checks, expected
) -> None:
    passing = {"crossed_share": 1.0, "basis_ok": True, "reproduces_pr035": True, **checks}
    primary = {"lo": lo, "hi": hi, "width": hi - lo}
    assert pr40.branch_for(primary, recent, passing, 2691, 129) == expected


def test_too_few_sessions_refuse(pr40) -> None:
    passing = {"crossed_share": 1.0, "basis_ok": True, "reproduces_pr035": True}
    assert pr40.branch_for({"lo": 0.01, "hi": 0.08, "width": 0.07}, 0.02, passing, 900, 129) \
        == "REFUSED"


def test_per_share_fees_are_charged_on_the_shares_that_traded(pr40) -> None:
    """On a split-adjusted session the tape's price is twice the bar's; a per-share fee is levied
    on the shares actually bought, so charging it on the bar's price would double it."""
    bars = _bars((D1, "54.13", "53.77"), (D2, "54.00", "54.20"))
    crosses = {D1: (_Print(Decimal("108.26")), _Print(Decimal("107.54"))),
               D2: (_Print(Decimal("108.00")), _Print(Decimal("108.40")))}
    sessions = pr40.priced_sessions(bars, {}, crosses, D1, D2)
    night, _, _ = pr40.arms(sessions, "auction")
    raw = (54.00 - 53.77) / 53.77
    fee = pr40.CAT_PER_SHARE / 107.54 + pr40.SEC_RATE + (pr40.TAF_PER_SHARE + pr40.CAT_PER_SHARE) / 108.00
    assert night[D2] == pytest.approx(raw - fee, abs=1e-12)


def test_the_reproduction_costing_reads_the_bars_not_the_crosses(pr40) -> None:
    """`bars_pr035` exists to rebuild `PR-035` on a known price source; fed the crosses, the
    reproduction check would compare the new answer with itself and could not fail."""
    bars = _bars((D1, "100.00", "100.00"), (D2, "101.00", "101.00"))
    crosses = {D1: (_Print(Decimal("100.00")), _Print(Decimal("100.50"))),
               D2: (_Print(Decimal("100.80")), _Print(Decimal("101.00")))}
    sessions = pr40.priced_sessions(bars, {}, crosses, D1, D2)
    night, _, _ = pr40.arms(sessions, "bars_pr035")
    assert night[D2] == pytest.approx((101.0 - 100.0) / 100.0 - 0.005 / 100.0 - 0.005 / 101.0)
