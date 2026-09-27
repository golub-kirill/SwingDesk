"""PR-039's two rules: which session an announcement moves, and whether a hold was exposed to it."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import run_pr039 as study  # noqa: E402


@pytest.mark.parametrize(("accepted", "expected"), [
    (datetime(2024, 5, 2, 12, 0, tzinfo=UTC), (date(2024, 5, 2), "open")),       # 08:00 New York
    (datetime(2024, 5, 2, 15, 0, tzinfo=UTC), (date(2024, 5, 2), "intraday")),   # 11:00
    (datetime(2024, 5, 2, 20, 30, tzinfo=UTC), (date(2024, 5, 3), "open")),      # 16:30, after close
    (datetime(2024, 5, 3, 21, 0, tzinfo=UTC), (date(2024, 5, 6), "open")),       # Friday evening
    (datetime(2024, 5, 4, 15, 0, tzinfo=UTC), (date(2024, 5, 6), "open")),       # Saturday
    (datetime(2024, 11, 29, 18, 30, tzinfo=UTC), (date(2024, 12, 2), "open")),   # after an early close
    (datetime(2024, 1, 3, 14, 29, tzinfo=UTC), (date(2024, 1, 3), "open")),      # 09:29 in winter
    (datetime(2024, 1, 3, 14, 31, tzinfo=UTC), (date(2024, 1, 3), "intraday")),  # 09:31 in winter
])
def test_an_announcement_moves_the_session_its_slot_says(accepted, expected) -> None:
    assert study.impact(accepted) == expected


def _trade(entry: date, exit_: date) -> study.Trade:
    return study.Trade("ranked", "TEST.1", entry, exit_, "stop", -1.0)


@pytest.mark.parametrize(("impact", "exposed"), [
    ((date(2024, 5, 2), "open"), False),       # already in the entry price
    ((date(2024, 5, 2), "intraday"), True),    # after the entry, on the entry day
    ((date(2024, 5, 3), "open"), True),
    ((date(2024, 5, 6), "open"), True),        # the exit day's open: the gap is the exit
    ((date(2024, 5, 7), "open"), False),       # after the exit
    ((date(2024, 4, 30), "intraday"), False),  # before the entry
])
def test_a_hold_is_exposed_only_to_an_impact_that_lands_while_it_is_held(impact, exposed) -> None:
    assert study.exposed(_trade(date(2024, 5, 2), date(2024, 5, 6)), [impact]) is exposed


def test_the_pool_counts_a_trade_sampled_by_two_arms_once_and_drops_the_3x_arms() -> None:
    same = study.Trade("ranked", "TEST.1", date(2024, 5, 2), date(2024, 5, 6), "stop", -1.0)
    trades = [same, study.Trade("ranked_top4", *[getattr(same, f) for f in
                                                  ("instrument_id", "entry_date", "exit_date",
                                                   "exit_reason", "net_r")]),
              study.Trade("ranked_3x", "TEST.2", date(2024, 5, 2), date(2024, 5, 6), "stop", -1.2)]
    assert study.pool(trades) == [same]


def test_every_trade_lands_in_exactly_one_bucket() -> None:
    trades = [_trade(date(2024, 5, 2), date(2024, 5, 6)),
              study.Trade("ranked", "FUND", date(2024, 5, 2), date(2024, 5, 6), "stop", -1.0),
              study.Trade("ranked", "GONE", date(2024, 5, 2), date(2024, 5, 6), "stop", -1.0)]
    buckets = study.split(trades, {"TEST.1": "dated", "FUND": "fund"},
                          {"TEST.1": [(date(2024, 5, 3), "open")]})
    assert {k: [t.instrument_id for t in v] for k, v in buckets.items()} == {
        "exposed": ["TEST.1"], "unexposed": [], "fund": ["FUND"], "unknown": ["GONE"]}


def test_only_an_etf_is_a_fund_and_an_undatable_company_is_unknown(tmp_path: Path) -> None:
    """A foreign issuer reports on Form 6-K, with no item codes: its results exist, undated."""
    path = tmp_path / "coverage.csv"
    path.write_text("symbol,cik,status,count,is_etf\n"
                    "AAPL,320193,with_announcements,48,false\n"
                    "SPY,884394,no_item_202,0,true\n"
                    "AZN,901832,no_item_202,0,false\n"
                    "DXJ,,no_cik,0,true\n"
                    "GONE,,no_cik,0,\n", encoding="utf-8")
    assert study.coverage(path) == {"AAPL": "dated", "SPY": "fund", "AZN": "unknown",
                                    "DXJ": "fund", "GONE": "unknown"}


def _pooled(exposed: int, unexposed: int, unknown: int = 0) -> dict[str, list[study.Trade]]:
    trade = _trade(date(2024, 5, 2), date(2024, 5, 6))
    return {"exposed": [trade] * exposed, "unexposed": [trade] * unexposed, "fund": [],
            "unknown": [trade] * unknown}


@pytest.mark.parametrize(("gap", "mean", "expected"), [
    ((0.1, 0.05, 0.15), (-0.2, -0.3, -0.1), ("accept", "FILTER_HELPS")),
    ((0.1, 0.05, 0.15), (0.2, 0.1, 0.3), ("accept", "FILTER_COSTS")),
    ((0.1, 0.05, 0.15), (0.0, -0.1, 0.1), ("accept", "RISK_ONLY")),
    ((-0.1, -0.15, -0.05), (0.0, -0.1, 0.1), ("reject", "REJECT")),
    ((0.0, -0.02, 0.02), (0.0, -0.1, 0.1), ("inconclusive", "NULL")),          # rules out 0.05
    ((0.0, -0.08, 0.08), (0.0, -0.1, 0.1), ("inconclusive", "INCONCLUSIVE")),  # cannot
])
def test_the_decision_rule_in_its_registered_order(gap, mean, expected) -> None:
    assert study.verdict(_pooled(200, 800), gap, mean, mde=0.05) == expected


@pytest.mark.parametrize("pooled", [_pooled(50, 800), _pooled(200, 300), _pooled(200, 800, 400)])
def test_too_few_exposed_too_small_a_pool_or_too_little_coverage_refuses(pooled) -> None:
    assert study.verdict(pooled, (0.1, 0.05, 0.15), (0.0, -0.1, 0.1), mde=0.05) == \
        ("refused", "REFUSED")
