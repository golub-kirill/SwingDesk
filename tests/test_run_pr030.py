"""`tools/run_pr030.py`: today's day limit, a limit-on-open and a market-on-open, on one entry.

The limit is the signal close, 100 here. What must hold, each a way to price the wrong order:

* **a day limit marketable at the open pays the ask**; one that is not RESTS and fills at the limit
  in the first minute that reaches it, paying nothing; one the price never reaches is MISSED;
* **a limit-on-open takes the cross or nothing**, a market-on-open the cross always;
* **a missed order is worth 0, and it is counted** - the unit is the drawn entry, so an order type
  that fills less is charged for it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from swingdesk.market_data.auctions import OPENING

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def run() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    return _load("_run_pr030", REPO / "tools" / "run_pr030.py")


@pytest.fixture(scope="module")
def world() -> ModuleType:
    return _load("_run_pr024_world_for_030", REPO / "tests" / "test_run_pr024.py")


@pytest.fixture(scope="module")
def helpers() -> ModuleType:
    return _load("_run_pr025_helpers_for_030", REPO / "tests" / "test_run_pr025.py")


def _priced(run, world, helpers, path, cross: float | None = None):
    entry, bars, minutes, entered = world._day_and_after(run.p24, path)
    open_cross = float(minutes[0].open) if cross is None else cross
    auctions = helpers._auctions(entered, open_cross, float(minutes[-1].close))
    got = run.price_entry(entry, helpers._series(bars), Decimal(2), tuple(minutes),
                          helpers._windows(world, entered), auctions, entered, None, Counter())
    return got, minutes


# --- the day limit ----------------------------------------------------------------------------------


def test_a_day_limit_marketable_at_the_open_pays_the_ask(run, world, helpers) -> None:
    """Opens at 99 with a 20 bps half-spread: the ask, 99.198, is under the 100 limit."""
    got, minutes = _priced(run, world, helpers, lambda i: 99.0)
    assert got.how[run.DAY] == run.MARKETABLE
    assert got.trades[run.DAY].entry_price == minutes[0].open * (1 + Decimal(20) / 10000)


def test_a_day_limit_above_the_market_rests_and_fills_at_the_limit(run, world, helpers) -> None:
    """Opens at 101, trades down to 99.5 from 11:10: the order fills AT 100, paying nothing."""
    got, _ = _priced(run, world, helpers, lambda i: 101.0 if i < 100 else 99.5)
    assert got.how[run.DAY] == run.RESTED
    assert got.trades[run.DAY].entry_price == Decimal(100)


def test_a_day_limit_the_price_never_reaches_is_missed_and_worth_nothing(run, world, helpers):
    got, _ = _priced(run, world, helpers, lambda i: 101.0)
    assert got.how[run.DAY] == run.MISSED
    assert all(got.value[(run.DAY, c)] == 0.0 for c in run.COSTINGS)
    assert run.DAY not in got.trades


def test_a_print_under_the_limit_with_the_ask_over_it_rests(run, world, helpers) -> None:
    """Opens at 99.9: the ask, 100.0998, is over the limit, so the order is not marketable - it
    rests at 100, and the first minute's low reaches it."""
    got, _ = _priced(run, world, helpers, lambda i: 99.9)
    assert got.how[run.DAY] == run.RESTED
    assert got.trades[run.DAY].entry_price == Decimal(100)


def test_a_resting_order_fills_on_the_minute_s_low_not_its_close(run, world, helpers) -> None:
    """Trades at 100.03 with a 0.05 range: every close is over the limit, every low under it."""
    got, _ = _priced(run, world, helpers, lambda i: 101.0 if i < 100 else 100.03)
    assert got.how[run.DAY] == run.RESTED


def test_a_joining_order_rests_only_after_a_late_cross(run, world, helpers) -> None:
    """The cross prints at 09:45 above the limit; the dip to 99.5 came at 09:35, before the order
    that waited for the cross existed on the book. The continuous-open order saw it."""
    from datetime import UTC

    entry, bars, minutes, entered = world._day_and_after(
        run.p24, lambda i: 99.5 if 5 <= i < 10 else 101.0)
    auctions = helpers._auctions(entered, 101.0, float(minutes[-1].close))
    late = entered.open_time.astimezone(UTC) + timedelta(minutes=15, milliseconds=200)
    auctions[OPENING] = (helpers._print(late, 101.0, 20000),)
    got = run.price_entry(entry, helpers._series(bars), Decimal(2), tuple(minutes),
                          helpers._windows(world, entered), auctions, entered, None, Counter())
    assert got.how[run.DAY] == run.RESTED
    assert got.how[run.JOINED] == run.MISSED


# --- the auction orders -----------------------------------------------------------------------------


def test_a_limit_on_open_takes_the_cross_or_nothing(run, world, helpers) -> None:
    under, _ = _priced(run, world, helpers, lambda i: 99.0)
    assert under.how[run.OPG] == run.CROSSED
    assert under.trades[run.OPG].entry_price == Decimal("99.0000")
    over, _ = _priced(run, world, helpers, lambda i: 101.0 if i < 100 else 99.5)
    assert over.how[run.OPG] == run.MISSED and over.value[(run.OPG, "net")] == 0.0


def test_a_market_on_open_takes_the_cross_always(run, world, helpers) -> None:
    got, _ = _priced(run, world, helpers, lambda i: 101.0)
    assert got.how[run.MOO] == run.CROSSED
    assert got.trades[run.MOO].entry_price == Decimal("101.0000")


def test_a_day_limit_that_joins_the_cross_rests_after_it_when_above(run, world, helpers) -> None:
    got, _ = _priced(run, world, helpers, lambda i: 101.0 if i < 100 else 99.5)
    assert got.how[run.JOINED] == run.RESTED
    assert got.trades[run.JOINED].entry_price == Decimal(100)
    joined, _ = _priced(run, world, helpers, lambda i: 99.0)
    assert joined.how[run.JOINED] == run.CROSSED


def test_the_cross_is_read_on_the_bars_basis(run, world, helpers) -> None:
    """A later 2-for-1 split: the tape printed 198 for a bar at 99 - still under the 100 limit."""
    entry, bars, minutes, entered = world._day_and_after(run.p24, lambda i: 99.0)
    plain = helpers._auctions(entered, 99.0, float(minutes[-1].close))
    doubled = {side: tuple(type(p)(at=p.at, price=p.price * 2, size=p.size, exchange=p.exchange,
                                   conditions=p.conditions) for p in prints)
               for side, prints in plain.items()}
    got = run.price_entry(entry, helpers._series(bars), Decimal(2), tuple(minutes),
                          helpers._windows(world, entered), doubled, entered, None, Counter())
    assert got.how[run.OPG] == run.CROSSED
    assert got.trades[run.OPG].entry_price == Decimal("99.0000")


def test_without_a_cross_the_auction_orders_are_unpriced_not_missed(run, world, helpers) -> None:
    entry, bars, minutes, entered = world._day_and_after(run.p24, lambda i: 99.0)
    auctions = helpers._auctions(entered, 99.0, 99.0, missing=(OPENING,))
    got = run.price_entry(entry, helpers._series(bars), Decimal(2), tuple(minutes),
                          helpers._windows(world, entered), auctions, entered, None, Counter())
    assert got.missing[run.OPG] == "no_opening_cross" and not got.priced(run.OPG)
    assert got.priced(run.DAY), "the day limit needs no cross"


# --- the reading ------------------------------------------------------------------------------------


def test_a_missed_order_is_charged_as_zero_in_the_contrast(run, world, helpers) -> None:
    import dataclasses

    missed, _ = _priced(run, world, helpers, lambda i: 101.0 if i < 100 else 99.5)
    rows = [dataclasses.replace(missed, entry=run.p24.Entry(
        "X", date(2023 + m // 12, 1 + m % 12, 2), date(2023 + m // 12, 1 + m % 12, 3)))
        for m in range(30)]
    cell = run.reading(rows, run.OPG, run.DAY, drawn=30, resamples=20)
    assert cell["pairs"] == 30
    assert cell["difference"]["estimate"] == pytest.approx(-missed.value[(run.DAY, "net")])


def test_fill_rates_count_how_each_order_fared(run, world, helpers) -> None:
    rows = [_priced(run, world, helpers, lambda i: 99.0)[0],
            _priced(run, world, helpers, lambda i: 101.0)[0]]
    rates = run.fill_rates(rows)
    assert rates[run.DAY] == {run.MARKETABLE: 1, run.MISSED: 1}
    assert rates[run.MOO] == {run.CROSSED: 2}


def test_the_run_goes_end_to_end_on_synthetic_stores(run, helpers, world, tmp_path) -> None:
    runner = _load("_run_pr025_for_030", REPO / "tools" / "run_pr025.py")
    args, entries = helpers._auction_world(tmp_path, world, runner)
    payload = run.build(args)
    assert payload["branch"] == "SMOKE" and payload["prereg"] == "PR-030"
    assert set(payload["cells"]) == {"G-D", "M-D", "J-D"}
    for key in ("country", "split", "perturbations", "fills", "missing_by_arm", "as_of"):
        assert key in payload
    assert sum(payload["fills"][run.MOO].values()) == len(entries)
    json.dumps(payload, default=run.p24._default)


def test_the_power_mode_writes_widths_and_no_level(run, helpers, world, tmp_path) -> None:
    runner = _load("_run_pr025_for_030_power", REPO / "tools" / "run_pr025.py")
    args, _ = helpers._auction_world(tmp_path, world, runner)
    estimate = run.power(args)
    assert set(estimate["widths"]) == {"G-D", "M-D", "J-D"}
    assert "cells" not in estimate and "fills" not in estimate


def test_the_orders_are_checked_against_the_studies_they_repeat(run, world, helpers,
                                                                tmp_path) -> None:
    """`D` marketable is `PR-024`'s `O`; `D` resting is not, and is not read as a difference."""
    marketable, _ = _priced(run, world, helpers, lambda i: 99.0)
    trade = marketable.trades[run.DAY]
    header = "instrument_id,session_date,arm,exit_date,exit_reason,per_dollar\n"

    def qa(value: float) -> Path:
        path = tmp_path / f"qa-{value}.csv"
        path.write_text(header + f"{marketable.entry.instrument_id},"
                        f"{marketable.entry.session_date},O,{trade.exit_date},"
                        f"{trade.exit_reason.value},{value}\n", encoding="utf-8")
        return path

    same = qa(marketable.value[(run.DAY, "net")])
    assert run.repeats_prior_studies([marketable], [(run.DAY, run.MARKETABLE, same, "O")])[run.DAY] == {
        "checked": 1, "differ": 0, "not_priced": 0, "other_fill": 0}
    off = qa(marketable.value[(run.DAY, "net")] + 0.001)
    assert run.repeats_prior_studies([marketable], [(run.DAY, run.MARKETABLE, off, "O")])[run.DAY][
        "differ"] == 1
    rested, _ = _priced(run, world, helpers, lambda i: 101.0 if i < 100 else 99.5)
    rested.trades[run.DAY] = trade
    assert run.repeats_prior_studies([rested], [(run.DAY, run.MARKETABLE, same, "O")])[run.DAY][
        "other_fill"] == 1


def test_the_difference_is_taken_apart_by_how_the_day_limit_fared(run, world, helpers) -> None:
    marketable, _ = _priced(run, world, helpers, lambda i: 99.0)
    rested, _ = _priced(run, world, helpers, lambda i: 101.0 if i < 100 else 99.5)
    parts = run.by_day_fill([marketable, rested, rested], run.OPG)
    assert parts[run.MARKETABLE]["entries"] == 1 and parts[run.RESTED]["entries"] == 2
    whole = sum(o.value[(run.OPG, "net")] - o.value[(run.DAY, "net")]
                for o in (marketable, rested, rested)) / 3
    assert sum(g["contribution"] for g in parts.values()) == pytest.approx(whole)
    assert parts[run.RESTED]["mean"] == pytest.approx(-rested.value[(run.DAY, "net")])


def test_the_registered_sources_name_each_order_s_own_fill(run) -> None:
    """Amendment A-1: `M` fills `CROSSED`; asked for anything else, its check reads no row."""
    assert dict((arm, how) for arm, how, _, _ in run.REPRODUCES) == {
        run.MOO: run.CROSSED, run.DAY: run.MARKETABLE}


def test_a_crossed_market_on_open_is_checked_against_its_row(run, world, helpers,
                                                             tmp_path) -> None:
    got, _ = _priced(run, world, helpers, lambda i: 101.0)
    trade = got.trades[run.MOO]
    path = tmp_path / "qa.csv"
    header = "instrument_id,session_date,arm,exit_date,exit_reason,per_dollar"
    row = (f"{got.entry.instrument_id},{got.entry.session_date},A,{trade.exit_date},"
           f"{trade.exit_reason.value},{got.value[(run.MOO, 'net')]}")
    path.write_text("\n".join((header, row, "")), encoding="utf-8")
    assert run.repeats_prior_studies([got], [(run.MOO, run.CROSSED, path, "A")])[run.MOO][
        "checked"] == 1


def test_the_print_test_is_dr040_s_not_the_ask(run, world, helpers) -> None:
    """Opens at 99.9 under a 100 limit: marketable by the print, resting by the ask."""
    got, _ = _priced(run, world, helpers, lambda i: 99.9)
    assert got.by_print == run.MARKETABLE and got.how[run.DAY] == run.RESTED
    never, _ = _priced(run, world, helpers, lambda i: 101.0)
    assert never.by_print == run.MISSED
