"""`tools/run_pr037.py` and `tools/measure_sector_power.py` - the sector-momentum instrument.

**The study was never registered**; the power measurement said the eleven-fund cross-section cannot
separate the effect its literature claims. What is tested here is the machinery that produced that
measurement, because the conclusion is only as good as the walk underneath it.

The things worth breaking a build over:

* **no look-ahead.** The signal reads month `t` and the return reads month `t + 1`. One off-by-one
  and the whole instrument reports the future;
* **a fund with no history is OUT of the ranking, never zero.** A zero would rank a fund that did
  not exist in the middle of the pool, and `XLC` did not exist before 2018;
* **the formation window SKIPS the decision month.** That month carries short-horizon reversal,
  which `PR-021` measured here at −25 points a year;
* **the bootstrap is PAIRED.** Resampling the strategy and the benchmark independently compares
  months that never happened together;
* **the minimum detectable effect is a width, and a width carries no sign** - which is the whole
  reason the measurement could run before a registration.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str):
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sector():
    return _load("run_pr037")


@pytest.fixture(scope="module")
def power_tool():
    return _load("measure_sector_power")


# --- the monthly series -------------------------------------------------------------------------


def _bar(session: date, close: float, *, fund: str = "XLK"):
    from swingdesk.contracts.market import Bar, Interval, Series

    return Bar(
        instrument_id=fund, interval=Interval.DAY, series=Series.RAW,
        event_time=datetime.combine(session, datetime.min.time(), tzinfo=UTC),
        session_date=session, open=Decimal(str(close)), high=Decimal(str(close)),
        low=Decimal(str(close)), close=Decimal(str(close)), volume=1_000,
        knowledge_time=datetime(2026, 9, 20, tzinfo=UTC),
    )


def test_a_month_compounds_its_daily_returns(sector) -> None:
    bars = [_bar(date(2026, 1, 5), 100.0), _bar(date(2026, 2, 2), 110.0),
            _bar(date(2026, 2, 20), 121.0)]
    got = sector.monthly_returns(bars, {})
    # January is dropped: its first session has no prior close.
    assert set(got) == {"2026-02"}
    assert got["2026-02"] == pytest.approx(121.0 / 100.0 - 1.0)


def test_a_dividend_paid_mid_month_reinvests_rather_than_landing_at_the_end(sector) -> None:
    bars = [_bar(date(2026, 1, 5), 100.0), _bar(date(2026, 2, 2), 100.0),
            _bar(date(2026, 2, 20), 100.0)]
    got = sector.monthly_returns(bars, {date(2026, 2, 2): 1.0})
    # +1% on the first step, then flat: 1.01, not 1.00 with a dollar bolted on at the end.
    assert got["2026-02"] == pytest.approx(0.01)


def test_the_first_stored_month_is_dropped(sector) -> None:
    bars = [_bar(date(2026, 1, 5), 100.0), _bar(date(2026, 1, 20), 110.0),
            _bar(date(2026, 2, 2), 121.0)]
    assert "2026-01" not in sector.monthly_returns(bars, {})


# --- formation and eligibility ------------------------------------------------------------------


def _months(n: int, start: int = 1) -> list[str]:
    return [f"20{20 + (start + i - 1) // 12:02d}-{(start + i - 1) % 12 + 1:02d}" for i in range(n)]


def test_the_formation_window_skips_the_decision_month(sector) -> None:
    months = _months(20)
    # A fund flat everywhere except the decision month, which doubles. The signal must not see it.
    series = dict.fromkeys(months, 0.0)
    series[months[13]] = 1.0
    assert sector.formation(series, months, 13) == pytest.approx(0.0)
    # And a month INSIDE the window does reach it.
    series2 = dict.fromkeys(months, 0.0)
    series2[months[12]] = 1.0
    assert sector.formation(series2, months, 13) == pytest.approx(1.0)


def test_the_window_is_twelve_months_long(sector) -> None:
    months = _months(20)
    series = dict.fromkeys(months, 0.0)
    series[months[1]] = 1.0
    # months[1] is 12 months before the window's end at months[12], so it is the oldest included.
    assert sector.formation(series, months, 13) == pytest.approx(1.0)
    assert sector.formation(series, months, 14) == pytest.approx(0.0)


def test_a_fund_with_a_missing_month_has_NO_signal_rather_than_a_zero(sector) -> None:
    months = _months(20)
    series = dict.fromkeys(months, 0.0)
    del series[months[5]]
    assert sector.formation(series, months, 13) is None


def test_a_fund_too_young_for_a_full_window_is_not_eligible(sector) -> None:
    months = _months(20)
    young = {m: 0.0 for m in months[10:]}
    old = dict.fromkeys(months, 0.0)
    got = sector.eligible({"XLC": young, "XLK": old}, months, 13)
    assert "XLC" not in got and "XLK" in got


def test_a_fund_that_has_stopped_trading_is_not_eligible(sector) -> None:
    months = _months(20)
    stopped = {m: 0.0 for m in months[:13]}      # a full window, but nothing in the decision month
    assert "XLK" not in sector.eligible({"XLK": stopped}, months, 13)


# --- the book -------------------------------------------------------------------------------------


@pytest.mark.parametrize(("eligible_count", "expected"), [(9, 3), (10, 4), (11, 4), (3, 1), (1, 1)])
def test_the_book_is_the_top_tercile_of_the_POOL(sector, eligible_count, expected) -> None:
    assert sector.hold_for(eligible_count) == expected


def test_the_book_takes_the_strongest_and_ties_break_reproducibly(sector) -> None:
    signals = {"XLE": 0.5, "XLK": 0.9, "XLF": 0.5, "XLU": 0.1, "XLV": 0.2, "XLP": 0.05,
               "XLY": 0.04, "XLI": 0.03, "XLB": 0.02}
    picks = sector.chosen(signals)
    assert len(picks) == 3
    assert "XLK" in picks
    assert picks == sector.chosen(dict(reversed(list(signals.items())))), "order must not matter"


def test_turnover_is_priced_on_the_CURRENT_book_not_a_constant(sector) -> None:
    # One of three replaced: 2/3 of the book trades at 5 bps.
    assert sector.turnover_cost(["A", "B", "C"], ["A", "B", "D"], 5.0) == pytest.approx(
        2.0 / 3.0 * 5.0 / 10_000.0)
    # One of four replaced: 2/4, and a constant denominator would misprice it.
    assert sector.turnover_cost(["A", "B", "C", "D"], ["A", "B", "C", "E"], 5.0) == pytest.approx(
        2.0 / 4.0 * 5.0 / 10_000.0)


def test_an_unchanged_book_costs_nothing(sector) -> None:
    assert sector.turnover_cost(["A", "B"], ["A", "B"], 5.0) == 0.0


def test_the_first_month_pays_an_entry_and_no_exit(sector) -> None:
    assert sector.turnover_cost([], ["A", "B", "C"], 5.0) == pytest.approx(5.0 / 10_000.0)


# --- the walk ------------------------------------------------------------------------------------


def test_the_signal_reads_month_t_and_the_RETURN_reads_month_t_plus_one(sector) -> None:
    months = _months(20)
    # XLK is the strongest over the formation window and then collapses in the held month.
    # A walk that read the same month would report the rise; this must report the collapse.
    strong = dict.fromkeys(months, 0.02)
    strong[months[14]] = -0.5
    weak = dict.fromkeys(months, 0.0)
    by_fund = {"XLK": strong, "XLE": weak, "XLF": weak, "XLU": weak, "XLV": weak, "XLP": weak}
    returns, trail = sector.walk(by_fund, months, 0.0)
    held = next(row for row in trail if row["held"] == months[14])
    assert "XLK" in held["picks"]
    assert returns[months[14]] < 0, "the held month's return, not the formation month's"


def test_every_held_month_is_the_one_AFTER_the_month_that_chose_it(sector) -> None:
    # The invariant, asserted on the index rather than on a return. A walk that read the same month
    # it decided on still produces a row for that month with a plausible number in it - the test
    # that only checked the number passed against exactly that mutant.
    months = _months(30)
    import random as _random

    rng = _random.Random(3)
    by_fund = {f: {m: rng.uniform(-0.05, 0.05) for m in months}
               for f in ("XLK", "XLE", "XLF", "XLU", "XLV", "XLP")}
    _, trail = sector.walk(by_fund, months, 0.0)
    assert trail
    position = {month: i for i, month in enumerate(months)}
    for row in trail:
        assert position[row["held"]] == position[row["decided"]] + 1


def test_the_power_proxy_walks_the_same_calendar_as_the_strategy(sector) -> None:
    # The proxy replaces the RANKING, never the calendar. It shares `walk`, so this is a test that
    # the sharing is real: a chooser that takes the first two funds must still be held one month
    # after it was chosen.
    months = _months(30)
    # Strength runs OPPOSITE to the alphabet, so the ranking and the chooser below can never
    # agree by accident - with six eligible funds the tercile is also two, and a test that only
    # counted the picks passed against a walk that ignored its chooser entirely.
    strength = {"XLB": 0.05, "XLE": 0.04, "XLF": 0.03, "XLK": 0.02, "XLU": 0.01, "XLV": 0.0}
    by_fund = {f: dict.fromkeys(months, r) for f, r in strength.items()}
    assert sector.chosen(dict.fromkeys(strength, 0.0)) != ("XLU", "XLV")
    _, trail = sector.walk(by_fund, months, 0.0,
                           choose=lambda signals: tuple(sorted(signals))[-2:])
    position = {month: i for i, month in enumerate(months)}
    assert trail
    for row in trail:
        assert position[row["held"]] == position[row["decided"]] + 1
        assert tuple(row["picks"]) == ("XLU", "XLV"), "the chooser decides the book"


def test_the_walk_holds_nothing_before_a_pool_exists(sector) -> None:
    months = _months(20)
    by_fund = {"XLK": dict.fromkeys(months, 0.01)}
    returns, _ = sector.walk(by_fund, months, 0.0)
    assert returns == {}, "one eligible fund is not a tercile of three"


def test_every_month_the_walk_reports_is_the_mean_of_what_it_held_less_the_cost(sector) -> None:
    months = _months(24)
    import random as _random

    rng = _random.Random(7)
    by_fund = {f: {m: rng.uniform(-0.05, 0.05) for m in months}
               for f in ("XLK", "XLE", "XLF", "XLU", "XLV", "XLP")}
    returns, trail = sector.walk(by_fund, months, 5.0)
    assert trail
    for row in trail:
        assert returns[row["held"]] == pytest.approx(row["gross"] - row["cost"])


# --- the benchmarks --------------------------------------------------------------------------------


def test_the_pool_benchmark_holds_only_what_the_strategy_could_have_chosen(sector) -> None:
    months = _months(20)
    old = dict.fromkeys(months, 0.10)
    young = {m: -0.50 for m in months[15:]}    # exists, but never has a formation window here
    got = sector.universe_returns({"XLK": old, "XLE": old, "XLF": old, "XLC": young},
                                  months, [months[16]])
    assert got[months[16]] == pytest.approx(0.10), "the ineligible fund must not drag the pool"


def test_vol_matching_gives_the_benchmark_the_strategy_s_volatility(sector) -> None:
    months = _months(24)
    calm = {m: 0.01 * (1 if i % 2 else -1) for i, m in enumerate(months)}
    wild = {m: 0.05 * (1 if i % 2 else -1) for i, m in enumerate(months)}
    matched = sector.scaled(calm, wild)
    import statistics

    assert statistics.stdev(matched.values()) == pytest.approx(
        statistics.stdev(wild.values()), rel=1e-9)


def test_geometric_excess_is_a_RATIO_of_compounded_returns(sector) -> None:
    # Up 10% a year against up 5%: the excess is 1.10/1.05 - 1, not 5 points.
    twelve = [1.10 ** (1 / 12) - 1] * 12
    slower = [(1.05 ** (1 / 12) - 1)] * 12
    assert sector.geometric_excess(twelve, slower) == pytest.approx(1.10 / 1.05 - 1.0, rel=1e-6)


def test_the_bootstrap_is_PAIRED_so_a_perfect_tracker_has_no_excess(sector) -> None:
    months = _months(60)
    import random as _random

    rng = _random.Random(11)
    bench = {m: rng.uniform(-0.06, 0.06) for m in months}
    same = dict(bench)
    cell = sector.paired_bootstrap(same, bench, 200)
    assert cell["estimate"] == pytest.approx(0.0, abs=1e-12)
    assert cell["width"] == pytest.approx(0.0, abs=1e-9), "paired months cannot disagree"


def test_rolling_windows_report_the_share_that_were_positive(sector) -> None:
    months = _months(60)
    strategy = dict.fromkeys(months, 0.01)
    bench = dict.fromkeys(months, 0.0)
    got = sector.rolling_excess(strategy, bench)
    assert got["windows"] == len(months) - 36 + 1
    assert got["share_positive"] == 1.0


# --- the decision rule -------------------------------------------------------------------------------


def _cell(lo, hi):
    return {"lo": lo, "hi": hi, "estimate": (lo + hi) / 2, "width": hi - lo}


@pytest.mark.parametrize(("excess", "adverse", "matched", "own", "months", "branch"), [
    (_cell(0.01, 0.05), _cell(0.005, 0.04), _cell(0.01, 0.04), _cell(0.01, 0.03), 200, "ACCEPT"),
    (_cell(0.01, 0.05), _cell(-0.01, 0.03), _cell(0.01, 0.04), _cell(0.01, 0.03), 200,
     "COST_FRAGILE"),
    (_cell(0.01, 0.05), _cell(0.005, 0.04), _cell(-0.01, 0.03), _cell(0.01, 0.03), 200,
     "PAID_FOR_EXPOSURE"),
    (_cell(0.01, 0.05), _cell(0.005, 0.04), _cell(0.01, 0.04), _cell(-0.01, 0.02), 200,
     "NOT_BETTER_HELD"),
    (_cell(-0.05, -0.01), _cell(-0.06, -0.02), _cell(-0.05, -0.01), _cell(-0.05, -0.01), 200,
     "REJECT"),
    (_cell(-0.05, 0.05), _cell(-0.06, 0.04), _cell(-0.05, 0.05), _cell(-0.05, 0.05), 200,
     "INCONCLUSIVE"),
    (_cell(-0.01, 0.01), _cell(-0.02, 0.01), _cell(-0.01, 0.01), _cell(-0.01, 0.01), 200, "NULL"),
    (_cell(0.01, 0.05), _cell(0.005, 0.04), _cell(0.01, 0.04), _cell(0.01, 0.03), 60, "REFUSED"),
])
def test_the_branches(sector, excess, adverse, matched, own, months, branch) -> None:
    assert sector.branch_for(excess, adverse, matched, own, months) == branch


def test_the_verdict_speaks_the_project_s_four_words(sector) -> None:
    assert set(sector.TOKEN.values()) <= {"accept", "reject", "inconclusive", "refused", "smoke"}
    assert sector.TOKEN["PAID_FOR_EXPOSURE"] == "inconclusive"
    assert sector.TOKEN["NOT_BETTER_HELD"] == "inconclusive"


# --- the power measurement ---------------------------------------------------------------------------


def test_the_minimum_detectable_effect_is_half_the_width_scaled_for_eighty_per_cent(power_tool) -> None:
    assert power_tool.minimum_detectable(0.0446) == pytest.approx(
        0.0446 / 2 * (1.96 + 0.84) / 1.96)


def test_the_measurement_declares_no_trials(power_tool, sector, tmp_path, monkeypatch) -> None:
    # The whole reason it could run before a registration: a random ranking carries no effect.
    monkeypatch.setattr(power_tool, "BOOK_SIZES", (3,))
    monkeypatch.setattr(sector, "power", lambda args, hold=None: {
        "widths": {"excess-vs-SPY-random-ranking": {"width": 0.05, "months": 300},
                   "excess-vs-own-pool-random-ranking": {"width": 0.04, "months": 300}}})
    payload = power_tool.measure(argparse.Namespace(data=tmp_path, as_of=None, resamples=10))
    assert payload["trials"] == 0
    assert payload["exploratory"] is True
    assert "RANDOM" in payload["why_no_trial"]


def test_the_measurement_does_not_call_the_best_book_the_answer(power_tool, sector, tmp_path,
                                                                monkeypatch) -> None:
    # Six of eleven has the narrowest interval and is 55% of the pool. Reading it as "answerable"
    # is the mistake the selective-book rule exists to prevent.
    widths = {3: 0.04, 4: 0.03, 5: 0.028, 6: 0.01}
    monkeypatch.setattr(power_tool, "BOOK_SIZES", tuple(widths))
    monkeypatch.setattr(sector, "power", lambda args, hold=None: {
        "widths": {"excess-vs-SPY-random-ranking": {"width": 0.06, "months": 300},
                   "excess-vs-own-pool-random-ranking":
                       {"width": widths.get(hold, 0.05), "months": 300}}})
    payload = power_tool.measure(argparse.Namespace(data=tmp_path, as_of=None, resamples=10))
    assert payload["best_minimum_detectable_among_selective_books"] == pytest.approx(
        power_tool.minimum_detectable(0.028))
    assert "6" in payload["by_book_size"], "the widest book is still REPORTED"


@pytest.mark.parametrize(("override", "eligible_count", "expected"), [
    (None, 11, 4),      # no override: the registered tercile
    (None, 9, 3),
    (2, 11, 2),         # the measurement asking what a book of two could detect
    (6, 11, 6),
    (6, 4, 4),          # never more funds than the pool holds
])
def test_the_power_proxy_draws_the_book_it_was_ASKED_for(sector, override, eligible_count,
                                                         expected) -> None:
    # The measurement asks what EACH size could detect. A proxy that quietly used the tercile
    # every time would report one number five times and the table would look like a finding.
    assert sector.book_size(override, eligible_count) == expected
